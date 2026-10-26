//! An optional process boundary around libmpv and its GPU driver.
use crate::{engine, media, State};
use serde_json::{json, Value};
use std::{
    fs,
    io::{BufRead, BufReader, Write},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicU64, Ordering},
        mpsc, Arc, Mutex,
    },
    time::Duration,
};
use tauri::{Emitter, Manager};
use videoenhancer_player::Bootstrap;

static HELPER: Mutex<Option<Arc<Mutex<Child>>>> = Mutex::new(None);
static SESSION: AtomicU64 = AtomicU64::new(0);
static SEQUENCE: AtomicU64 = AtomicU64::new(0);
const FALLBACK: &str = "This video can't be played here. Open it in your default player instead.";
pub fn close() {
    SESSION.fetch_add(1, Ordering::SeqCst);
    if let Ok(mut helper) = HELPER.lock() {
        if let Some(child) = helper.take() {
            if let Ok(mut child) = child.lock() {
                let _ = child.kill();
            }
        }
    }
}
pub fn open(app: &tauri::AppHandle, state: &State, id: &str) -> engine::Result<Value> {
    close();
    let generation = SESSION.fetch_add(1, Ordering::SeqCst) + 1;
    if !media::valid_id(id) {
        return Err("Invalid media handle.".into());
    }
    let folder = std::env::current_exe()
        .map_err(|e| e.to_string())?
        .parent()
        .ok_or(FALLBACK)?
        .to_owned();
    let executable = folder.join("VideoEnhancer-Player.exe");
    if !executable.is_file()
        || [
            "libmpv-2.dll",
            "libspirv-cross-c-shared.dll",
            "libwinpthread-1.dll",
        ]
        .iter()
        .any(|name| !folder.join(name).is_file())
    {
        return Err(FALLBACK.into());
    }
    let queue = engine::request(&state.connected()?, "queue", "GET", None)?;
    let job = queue["jobs"]
        .as_array()
        .and_then(|rows| rows.iter().find(|row| row["id"] == id))
        .ok_or("This video is no longer in History.")?;
    let handles = media::player_handles(job)?;
    let window = app
        .get_webview_window("main")
        .ok_or("Main window missing")?;
    let size = window.inner_size().map_err(|e| e.to_string())?;
    let position = window.inner_position().map_err(|e| e.to_string())?;
    let short_side = job["settings"]["short_side"].as_u64().or_else(|| {
        job["settings"]["short_side"]
            .as_str()
            .and_then(|s| s.parse().ok())
    });
    let input_w = job["media"]["display_width"]
        .as_u64()
        .ok_or("Missing video dimensions")?;
    let input_h = job["media"]["display_height"]
        .as_u64()
        .ok_or("Missing video dimensions")?;
    let factor = short_side
        .map(|n| (n as f64 / input_w.min(input_h).max(1) as f64).max(1.))
        .unwrap_or(1.);
    let video_width = ((input_w as f64 * factor / 2.).round_ties_even() as u32 * 2).max(16);
    let video_height = ((input_h as f64 * factor / 2.).round_ties_even() as u32 * 2).max(16);
    let width = size.width.min(video_width).max(320);
    let height = size.height.min(video_height).max(180);
    let profile = state
        .home
        .lock()
        .map_err(|e| e.to_string())?
        .join("player-profiles")
        .join(format!(
            "{}-{}",
            std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)
        ));
    let boot = Bootstrap {
        version: 1,
        owner: window.hwnd().map_err(|e| e.to_string())?.0 as isize,
        width,
        height,
        x: position.x + (size.width as i32 - width as i32) / 2,
        y: position.y + (size.height as i32 - height as i32) / 2,
        profile: profile.clone(),
        output: "output".into(),
        original: handles.contains_key("original").then(|| "original".into()),
        handles,
        title: std::path::Path::new(job["output"].as_str().unwrap_or("VideoEnhancer"))
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned(),
        video_width,
        video_height,
    };
    if SESSION.load(Ordering::SeqCst) != generation {
        return Err("Player closed.".into());
    }
    fs::create_dir_all(&profile).map_err(|e| e.to_string())?;
    let log = fs::OpenOptions::new()
        .append(true)
        .create(true)
        .open(
            state
                .home
                .lock()
                .map_err(|e| e.to_string())?
                .join("player.log"),
        )
        .map_err(|e| e.to_string())?;
    let mut command = Command::new(executable);
    // WebView2 environment variables override its explicit profile argument.
    // Do not share the main WebView's profile, CDP port or browser process.
    command.env_remove("WEBVIEW2_USER_DATA_FOLDER");
    command.env_remove("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS");
    use std::os::windows::process::CommandExt;
    command.creation_flags(0x08000000);
    let mut child = command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(log)
        .spawn()
        .map_err(|_| FALLBACK)?;
    let mut input = child.stdin.take().ok_or(FALLBACK)?;
    let output = child.stdout.take().ok_or(FALLBACK)?;
    writeln!(
        input,
        "{}",
        serde_json::to_string(&boot).map_err(|e| e.to_string())?
    )
    .map_err(|_| FALLBACK)?;
    input.flush().map_err(|_| FALLBACK)?;
    let child = Arc::new(Mutex::new(child));
    {
        let mut helper = HELPER.lock().map_err(|e| e.to_string())?;
        if SESSION.load(Ordering::SeqCst) != generation {
            if let Ok(mut child) = child.lock() {
                let _ = child.kill();
            }
            return Err("Player closed.".into());
        }
        *helper = Some(child.clone());
    }
    let (ready, waiting) = mpsc::sync_channel(1);
    let app = app.clone();
    let job_id = id.to_owned();
    std::thread::spawn(move || {
        let _input = input;
        let mut ready = Some(ready);
        let mut failed = false;
        let mut closed = false;
        for line in BufReader::new(output).lines() {
            let Ok(line) = line else {
                break;
            };
            let Ok(event) = serde_json::from_str::<Value>(&line) else {
                continue;
            };
            match event["event"].as_str() {
                Some("loaded") => {
                    if let Some(ready) = ready.take() {
                        let _ = ready.send(Ok(()));
                    }
                }
                Some("error") => {
                    failed = true;
                    if let Some(ready) = ready.take() {
                        let _ = ready.send(Err(FALLBACK));
                    }
                    if SESSION.load(Ordering::SeqCst) == generation {
                        let _ = app.emit("player-error", json!({"id":job_id,"message":FALLBACK}));
                    }
                }
                Some("closed") => closed = true,
                _ => {}
            }
        }
        if let Some(ready) = ready {
            let _ = ready.send(Err(FALLBACK));
        }
        let success = closed
            || child
                .lock()
                .ok()
                .and_then(|mut c| c.try_wait().ok().flatten())
                .is_some_and(|s| s.success());
        if !success && !failed && SESSION.load(Ordering::SeqCst) == generation {
            let _ = app.emit("player-error", json!({"id":job_id,"message":FALLBACK}));
        }
        if SESSION.load(Ordering::SeqCst) == generation {
            let _ = app.emit("player-closed", json!({"id":job_id}));
        }
        if SESSION.load(Ordering::SeqCst) == generation {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }
        std::thread::sleep(Duration::from_secs(2));
        if let Err(error) = fs::remove_dir_all(&profile) {
            eprintln!("Player profile cleanup: {error}");
        }
    });
    match waiting.recv_timeout(Duration::from_secs(15)) {
        Ok(Ok(())) => Ok(json!(true)),
        _ => {
            close();
            Err(FALLBACK.into())
        }
    }
}
