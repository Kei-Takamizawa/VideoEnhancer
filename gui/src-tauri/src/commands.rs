use crate::{engine, storage, window, State};
use serde_json::{json, Value};
use std::{
    fs,
    io::Write,
    sync::{atomic::Ordering, Arc},
};
#[cfg(feature = "e2e")]
use tauri::Emitter;
use tauri::Manager;

fn text(args: &Value) -> engine::Result<&str> {
    args.as_str()
        .ok_or_else(|| "Invalid command argument.".into())
}
fn source_target(value: &str) -> engine::Result<String> {
    if value.len() > 8192 || value.chars().any(char::is_control) {
        return Err("Invalid source link.".into());
    }
    let url = reqwest::Url::parse(value).map_err(|_| "Invalid source link.")?;
    if !matches!(url.scheme(), "http" | "https")
        || url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
    {
        return Err("Invalid source link.".into());
    }
    Ok(url.to_string())
}

#[cfg(test)]
mod source_tests {
    use super::source_target;
    #[test]
    fn validates_and_normalizes_source_links() {
        for value in [
            "javascript:alert(1)",
            "file:///C:/video.mp4",
            "ftp://example.com/a",
            "https://user:pass@example.com/",
        ] {
            assert!(source_target(value).is_err());
        }
        assert_eq!(
            source_target("https://example.com/a\"b").unwrap(),
            "https://example.com/a%22b"
        );
        assert_eq!(
            source_target("http://example.com/video").unwrap(),
            "http://example.com/video"
        );
    }
}
pub fn execute(
    app: &tauri::AppHandle,
    state: &State,
    operation: &str,
    args: Value,
) -> engine::Result<Value> {
    let window = app
        .get_webview_window("main")
        .ok_or("Main window missing")?;
    match operation {
        "memoryTarget" => {
            window::memory_target(&window, args.as_bool().ok_or("Invalid memory target")?)?;
            Ok(Value::Null)
        }
        "connection" => {
            let connection = state.connected()?;
            let settings = engine::request(&connection, "settings", "GET", None)?;
            let mut value = serde_json::to_value(connection).map_err(|e| e.to_string())?;
            value["zoom_percent"] = json!(settings["zoom"]
                .as_u64()
                .filter(|v| window::ZOOM.contains(v))
                .unwrap_or(100));
            Ok(value)
        }
        "ready" => {
            if !std::env::args().any(|a| a == "--hidden") {
                window.show().map_err(|e| e.to_string())?;
            }
            Ok(Value::Null)
        }
        "reload" => {
            window
                .eval("location.reload()")
                .map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "restartEngine" => {
            engine::stop(&state.connected()?)?;
            *state.connection.lock().map_err(|e| e.to_string())? = None;
            serde_json::to_value(state.connected()?).map_err(|e| e.to_string())
        }
        "theme" => {
            window::theme(&window, text(&args)?)?;
            *state.appearance.lock().map_err(|e| e.to_string())? = text(&args)?.to_owned();
            Ok(Value::Null)
        }
        "zoom" => {
            let percent = args.as_u64().ok_or("Invalid zoom")?;
            if !window::ZOOM.contains(&percent) {
                return Err("Choose a supported zoom level.".into());
            }
            engine::request(
                &state.connected()?,
                "settings",
                "PUT",
                Some(&json!({"zoom":percent})),
            )?;
            window::zoom(&window, percent)?;
            state.zoom_percent.store(percent, Ordering::SeqCst);
            Ok(json!(percent))
        }
        "hide" => {
            engine::request(
                &state.connected()?,
                "settings",
                "PUT",
                Some(&json!({"tray_explained":true})),
            )?;
            state.tray_explained.store(true, Ordering::SeqCst);
            window.hide().map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "fullscreen" => {
            window
                .set_fullscreen(args.as_bool().ok_or("Invalid fullscreen state")?)
                .map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "files" => {
            let kind = text(&args)?;
            if kind != "videos" && kind != "folder" {
                return Err("Invalid dialog kind.".into());
            }
            #[cfg(feature = "e2e")]
            if let Some(files) = state
                .dialog_files
                .lock()
                .map_err(|e| e.to_string())?
                .clone()
            {
                return Ok(json!(files));
            }
            let dialog = rfd::FileDialog::new()
                .set_parent(&window)
                .set_title("VideoEnhancer");
            let files = if kind == "folder" {
                dialog.pick_folder().into_iter().collect::<Vec<_>>()
            } else {
                dialog
                    .add_filter("Videos", &["mp4", "mkv", "mov", "avi", "webm", "m4v"])
                    .pick_files()
                    .unwrap_or_default()
            };
            Ok(json!(files))
        }
        "openFolder" | "reveal" | "play" => {
            let raw = text(&args)?;
            let directory = operation == "openFolder"
                || (operation == "reveal" && std::path::Path::new(raw).is_dir());
            let path = window::valid_path(raw, directory)?;
            window::open(&path.to_string_lossy(), operation == "reveal")?;
            Ok(Value::Null)
        }
        "openExternal" => {
            let url = text(&args)?;
            let normalized =
                window::external_target(url, &state.publishers.lock().map_err(|e| e.to_string())?)?;
            window::open(&normalized, false)?;
            Ok(Value::Null)
        }
        "sourceLink" => {
            let id = text(&args)?;
            if id.len() != 32 || !id.bytes().all(|c| c.is_ascii_hexdigit()) {
                return Err("Invalid job ID.".into());
            }
            let record = engine::request(
                &state.connected()?,
                &format!("queue/{id}/source"),
                "GET",
                None,
            )?;
            let source = record["url"].as_str().ok_or("Source link missing.")?;
            let normalized = source_target(source)?;
            window::open(&normalized, false)?;
            Ok(Value::Null)
        }
        "copy" => {
            let s = text(&args)?;
            if s.chars().count() > 100000 {
                return Err("Details are too large.".into());
            }
            arboard::Clipboard::new()
                .and_then(|mut c| c.set_text(s))
                .map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "logRendererError" => {
            let s = text(&args)?;
            let home = state.home.lock().map_err(|e| e.to_string())?;
            fs::create_dir_all(&*home).map_err(|e| e.to_string())?;
            let mut log = fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(home.join("renderer-errors.log"))
                .map_err(|e| e.to_string())?;
            writeln!(log, "{}", s.chars().take(64000).collect::<String>())
                .map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "storageStatus" => {
            #[cfg(feature = "e2e")]
            if let Some(value) = state
                .storage_fixture
                .lock()
                .map_err(|e| e.to_string())?
                .clone()
            {
                return Ok(value);
            }
            if args.as_bool().unwrap_or(false) {
                storage::refresh(state)?;
            }
            storage::status(state)
        }
        "moveStorage" => {
            #[cfg(feature = "e2e")]
            if state
                .storage_fixture
                .lock()
                .map_err(|e| e.to_string())?
                .is_some()
            {
                std::thread::sleep(std::time::Duration::from_millis(1200));
                return Ok(json!({"moved":true}));
            }
            storage::relocate(state, text(&args)?)
        }
        "removeOldStorage" => storage::remove_old(state, &window),
        _ => Err("Unknown desktop command.".into()),
    }
}
#[tauri::command]
pub async fn desktop_command(
    app: tauri::AppHandle,
    state: tauri::State<'_, Arc<State>>,
    operation: String,
    args: Value,
) -> engine::Result<Value> {
    if operation.len() > 64 {
        return Err("Invalid command".into());
    }
    let state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || execute(&app, &state, &operation, args))
        .await
        .map_err(|e| e.to_string())?
}

#[cfg(feature = "e2e")]
#[tauri::command]
pub async fn desktop_test(
    app: tauri::AppHandle,
    state: tauri::State<'_, Arc<State>>,
    operation: String,
    args: Value,
) -> engine::Result<Value> {
    let window = app.get_webview_window("main").ok_or("Window missing")?;
    match operation.as_str() {
        "memory-target" => {
            use webview2_com::Microsoft::Web::WebView2::Win32::{
                ICoreWebView2_19, COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_LOW,
                COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_NORMAL,
            };
            use windows::core::Interface;
            let low = args.as_bool().ok_or("Invalid memory target")?;
            let (sender, receiver) = tauri::async_runtime::channel(1);
            window
                .with_webview(move |platform| {
                    let result = unsafe {
                        platform.controller().CoreWebView2().and_then(|core| {
                            core.cast::<ICoreWebView2_19>().and_then(|core| {
                                core.SetMemoryUsageTargetLevel(if low {
                                    COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_LOW
                                } else {
                                    COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_NORMAL
                                })
                            })
                        })
                    };
                    let _ = sender.try_send(result.map_err(|e| e.to_string()));
                })
                .map_err(|e| e.to_string())?;
            let mut receiver = receiver;
            receiver
                .recv()
                .await
                .ok_or("Memory target response missing")??;
            Ok(Value::Null)
        }
        "remove-confirmation" => {
            *state
                .remove_confirmation
                .lock()
                .map_err(|e| e.to_string())? = Some(args.as_bool().ok_or("Invalid confirmation")?);
            Ok(Value::Null)
        }
        "files" => {
            *state.dialog_files.lock().map_err(|e| e.to_string())? =
                Some(serde_json::from_value(args).map_err(|e| e.to_string())?);
            Ok(Value::Null)
        }
        "size" => {
            window
                .set_size(tauri::LogicalSize::new(
                    args[0].as_f64().ok_or("width")?,
                    args[1].as_f64().ok_or("height")?,
                ))
                .map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "close" => {
            window.close().map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "show" => {
            window::show(&app);
            Ok(Value::Null)
        }
        "quit" => {
            window::quit(&app);
            Ok(Value::Null)
        }
        "exit" => {
            state.quitting.store(true, Ordering::SeqCst);
            app.exit(0);
            Ok(Value::Null)
        }
        "drop" => {
            window
                .emit("native-file-drop", args)
                .map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "state" => {
            let size = window.inner_size().map_err(|e| e.to_string())?;
            let position = window.outer_position().map_err(|e| e.to_string())?;
            Ok(
                json!({"visible":window.is_visible().map_err(|e|e.to_string())?,"fullscreen":window.is_fullscreen().map_err(|e|e.to_string())?,"media_peak":state.fetches.peak.load(Ordering::SeqCst),"media_total":state.fetches.total.load(Ordering::SeqCst),"width":size.width,"height":size.height,"x":position.x,"y":position.y}),
            )
        }
        "fullscreen" => {
            window
                .set_fullscreen(args.as_bool().ok_or("Invalid fullscreen state")?)
                .map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "handle" => Ok(json!(window.hwnd().map_err(|e| e.to_string())?.0 as usize)),
        "clipboard" => Ok(json!(arboard::Clipboard::new()
            .and_then(|mut c| c.get_text())
            .map_err(|e| e.to_string())?)),
        "startup" => Ok(
            engine::request(&state.connected()?, "settings", "GET", None)?["start_with_windows"]
                .clone(),
        ),
        "storage-fixture" => {
            *state.storage_fixture.lock().map_err(|e| e.to_string())? = Some(args);
            Ok(Value::Null)
        }
        "arrange" => {
            window
                .set_always_on_top(args["topmost"].as_bool().unwrap_or(false))
                .map_err(|e| e.to_string())?;
            window
                .set_position(tauri::LogicalPosition::new(
                    args["x"].as_f64().ok_or("x")?,
                    args["y"].as_f64().ok_or("y")?,
                ))
                .map_err(|e| e.to_string())?;
            window
                .set_size(tauri::LogicalSize::new(1100., 700.))
                .map_err(|e| e.to_string())?;
            Ok(Value::Null)
        }
        "native-drop" => Ok(json!(*state
            .native_drop
            .lock()
            .map_err(|e| e.to_string())?)),
        _ => Err("Unknown test operation".into()),
    }
}
