use crate::{engine, State};
use engine::Result;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::os::windows::{
    fs::{MetadataExt, OpenOptionsExt},
    process::CommandExt,
};
use std::{
    fs,
    io::{BufRead, BufReader, Read, Write},
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
    sync::atomic::Ordering,
};

pub const OVERRIDE_MESSAGE: &str = "App data is set by VE_HOME. Unset it to use Move.";
#[cfg(test)]
std::thread_local! { static HASH_READS: std::cell::Cell<usize> = const { std::cell::Cell::new(0) }; }
static STARTUP_NOTICE: std::sync::OnceLock<std::sync::Mutex<String>> = std::sync::OnceLock::new();
pub fn startup_notice() -> String {
    STARTUP_NOTICE
        .get_or_init(Default::default)
        .lock()
        .unwrap_or_else(|e| e.into_inner())
        .clone()
}
fn startup_pointer(path: &Path) -> Result<Value> {
    match read(path) {
        Ok(value) if value.is_object() => Ok(value),
        result => {
            let error = match result {
                Err(error) if error.starts_with("Invalid storage pointer") => error,
                Err(error) => return Err(error),
                _ => "Expected a JSON object at the top level.".into(),
            };
            let message = format!(
                "Skipped damaged JSON file {}: {}. The file was left unchanged.",
                path.display(),
                error
            );
            eprintln!("{message}");
            *STARTUP_NOTICE
                .get_or_init(Default::default)
                .lock()
                .unwrap_or_else(|e| e.into_inner()) = message;
            Ok(json!({}))
        }
    }
}
pub fn pointer() -> Result<PathBuf> {
    Ok(
        PathBuf::from(std::env::var_os("APPDATA").ok_or("APPDATA is missing")?)
            .join("VideoEnhancer/storage-location.json"),
    )
}
pub fn read(path: &Path) -> Result<Value> {
    match fs::read(path) {
        Ok(bytes) => {
            serde_json::from_slice(&bytes).map_err(|e| format!("Invalid storage pointer: {e}"))
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(json!({})),
        Err(e) => Err(e.to_string()),
    }
}
pub fn write(path: &Path, data: &Value) -> Result<()> {
    if path.exists() && !read(path)?.is_object() {
        return Err(
            "The storage pointer is damaged. Fix or remove it before saving a new location.".into(),
        );
    }
    fs::create_dir_all(path.parent().ok_or("Pointer parent missing")?)
        .map_err(|e| e.to_string())?;
    let temp = path.with_extension(format!("{}.tmp", std::process::id()));
    let mut file = fs::File::create(&temp).map_err(|e| e.to_string())?;
    file.write_all(
        serde_json::to_string(data)
            .map_err(|e| e.to_string())?
            .as_bytes(),
    )
    .map_err(|e| e.to_string())?;
    file.sync_all().map_err(|e| e.to_string())?;
    drop(file);
    // Windows rename does not replace an existing destination; MoveFileEx does.
    let from: Vec<u16> = temp
        .as_os_str()
        .to_string_lossy()
        .encode_utf16()
        .chain(Some(0))
        .collect();
    let to: Vec<u16> = path
        .as_os_str()
        .to_string_lossy()
        .encode_utf16()
        .chain(Some(0))
        .collect();
    #[link(name = "kernel32")]
    extern "system" {
        fn MoveFileExW(from: *const u16, to: *const u16, flags: u32) -> i32;
    }
    if unsafe { MoveFileExW(from.as_ptr(), to.as_ptr(), 1 | 8) } == 0 {
        return Err(std::io::Error::last_os_error().to_string());
    }
    Ok(())
}
pub fn migrate(canonical: &Path, legacy: &Path) -> Result<bool> {
    if !canonical.exists() && legacy.exists() {
        let value = read(legacy)?;
        write(canonical, &value)?;
        return Ok(true);
    }
    Ok(false)
}
pub fn startup() -> Result<PathBuf> {
    if let Some(home) = std::env::var_os("VE_HOME") {
        let path = PathBuf::from(home);
        if !path.is_absolute() {
            return Err("VE_HOME must be absolute.".into());
        }
        return Ok(path);
    }
    let file = pointer()?;
    let legacy = file
        .parent()
        .and_then(Path::parent)
        .ok_or("Pointer parent missing")?
        .join("videoenhancer-desktop/storage-location.json");
    let migrated = if !file.exists() && legacy.exists() {
        let value = startup_pointer(&legacy)?;
        if value["active"].is_string() {
            migrate(&file, &legacy)?
        } else {
            false
        }
    } else {
        false
    };
    let mut value = startup_pointer(&file)?;
    let default = PathBuf::from(std::env::var_os("LOCALAPPDATA").ok_or("LOCALAPPDATA is missing")?)
        .join("VideoEnhancer");
    loop {
        let home = value["active"]
            .as_str()
            .map(PathBuf::from)
            .unwrap_or_else(|| default.clone());
        if !home.is_absolute() {
            return Err("The app data pointer is not absolute.".into());
        }
        if value["active"].is_null() || home.is_dir() {
            if migrated {
                fs::create_dir_all(&home).map_err(|e| e.to_string())?;
                let mut log = fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(home.join("storage-migration.log"))
                    .map_err(|e| e.to_string())?;
                writeln!(
                    log,
                    "Migrated the legacy Electron storage pointer to the shared location."
                )
                .map_err(|e| e.to_string())?;
            }
            return Ok(home);
        }
        ensure_available_drive(&home)?;
        let answer = rfd::MessageDialog::new()
            .set_title("VideoEnhancer")
            .set_description(format!(
                "The app data folder was not found\n{}",
                home.display()
            ))
            .set_buttons(rfd::MessageButtons::YesNoCancelCustom(
                "Choose…".into(),
                "Use the previous folder".into(),
                "Quit".into(),
            ))
            .show();
        let next = match answer {
            rfd::MessageDialogResult::Custom(s) if s == "Choose…" => {
                rfd::FileDialog::new().pick_folder()
            }
            rfd::MessageDialogResult::Custom(s) if s == "Use the previous folder" => {
                value["previous"].as_str().map(PathBuf::from)
            }
            _ => return Err("Startup cancelled.".into()),
        };
        if let Some(next) = next.filter(|p| p.is_dir()) {
            value = json!({"active":next,"previous":home,"recovered":true});
            write(&file, &value)?;
        }
    }
}
pub fn relative(raw: &str) -> Result<PathBuf> {
    let p = Path::new(raw);
    if raw.is_empty()
        || raw.contains('\0')
        || p.components().any(|c| !matches!(c, Component::Normal(_)))
    {
        return Err("Unsafe manifest path".into());
    }
    Ok(p.into())
}
fn no_links(root: &Path, path: &Path) -> Result<()> {
    for ancestor in root.ancestors() {
        if fs::symlink_metadata(ancestor)
            .map_err(|e| e.to_string())?
            .file_attributes()
            & 0x400
            != 0
        {
            return Err("Linked app data is not removable".into());
        }
    }
    let mut at = root.to_path_buf();
    if fs::symlink_metadata(&at)
        .map_err(|e| e.to_string())?
        .file_attributes()
        & 0x400
        != 0
    {
        return Err("Linked app data is not removable".into());
    }
    for part in path.components() {
        at.push(part);
        if fs::symlink_metadata(&at)
            .map_err(|e| e.to_string())?
            .file_attributes()
            & 0x400
            != 0
        {
            return Err("Linked app data is not removable".into());
        }
    }
    Ok(())
}
pub struct BusyGuard<'a>(&'a std::sync::atomic::AtomicBool);
impl<'a> BusyGuard<'a> {
    fn acquire(busy: &'a std::sync::atomic::AtomicBool) -> Result<Self> {
        busy.compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .map_err(|_| {
                "App data is busy. Wait for the current operation to finish.".to_string()
            })?;
        Ok(Self(busy))
    }
}
impl Drop for BusyGuard<'_> {
    fn drop(&mut self) {
        self.0.store(false, Ordering::SeqCst);
    }
}
pub fn refresh(state: &State) -> Result<()> {
    let _busy = BusyGuard::acquire(&state.storage_busy)?;
    let saved = read(&pointer()?)?;
    let checked =
        verify(state, &saved).and_then(|(old, entries)| removal_eligibility(&old, &entries));
    *state
        .storage_verification
        .lock()
        .map_err(|e| e.to_string())? = json!({
        "pointer": saved, "can_remove": checked.is_ok(),
        "reason": checked.err().unwrap_or_default()
    });
    Ok(())
}
fn removal_eligibility(old: &Path, entries: &[Value]) -> Result<()> {
    if entries
        .iter()
        .any(|entry| removable_size(old, entry).is_some())
    {
        Ok(())
    } else {
        Err("No unchanged, accessible files from this move can be removed.".into())
    }
}
fn unverified_location_reason(value: &Value) -> &'static str {
    if value["recovered"] == true {
        "This location was recovered by the app. No verified move record is available, so the previous folder is kept."
    } else {
        "This folder was moved by an earlier version, so the app can't check it before removing it. Keeping it is safe."
    }
}
pub fn status(state: &State) -> Result<Value> {
    let mut value = read(&pointer()?)?;
    let verified = state
        .storage_verification
        .lock()
        .map_err(|e| e.to_string())?;
    let busy = state.storage_busy.load(Ordering::SeqCst);
    value["can_remove"] =
        json!(!busy && verified["pointer"] == value && verified["can_remove"] == true);
    value["remove_reason"] = verified["reason"].clone();
    value["busy"] = json!(busy);
    value["folder"] = json!(*state.home.lock().map_err(|e| e.to_string())?);
    let progress = state
        .storage_progress
        .lock()
        .map_err(|e| e.to_string())?
        .clone();
    for key in ["phase", "damaged", "copied_bytes", "total_bytes"] {
        value[key] = progress[key].clone();
    }
    value["disabled"] = json!(std::env::var_os("VE_HOME").is_some());
    if value["previous"].is_string() && !value["manifest"].is_array() {
        value["remove_reason"] = json!(unverified_location_reason(&value));
    }
    value["manifest"] = Value::Null;
    Ok(value)
}
fn verify(state: &State, saved: &Value) -> Result<(PathBuf, Vec<Value>)> {
    if std::env::var_os("VE_HOME").is_some() {
        return Err(OVERRIDE_MESSAGE.into());
    }
    let active = PathBuf::from(saved["active"].as_str().ok_or("No active folder")?);
    let old = PathBuf::from(saved["previous"].as_str().ok_or("No old folder")?);
    no_links(&old, Path::new(""))?;
    if !active.is_absolute() || !old.is_absolute() || old.parent().is_none() {
        return Err("Unsafe old folder".into());
    }
    let a = active.canonicalize().map_err(|e| e.to_string())?;
    let o = old.canonicalize().map_err(|e| e.to_string())?;
    safe_old_folder(&a, &o)?;
    let health = engine::request(&state.connected_internal()?, "health", "GET", None)?;
    if !engine::reported_home_matches(&health, &a) {
        return Err("The engine is not using the verified active folder.".into());
    }
    let entries = saved["manifest"]
        .as_array()
        .ok_or("No verified move manifest")?
        .clone();
    let records = engine::request(&state.connected_internal()?, "storage", "GET", None)?;
    if records["core_records_load"] != true {
        return Err("The active folder's core records could not be loaded.".into());
    }
    probe(&active)?;
    Ok((old, entries))
}
fn safe_old_folder(active: &Path, old: &Path) -> Result<()> {
    if !old.is_absolute() || old.parent().is_none() || active == old || active.starts_with(old) {
        return Err("The old folder is a drive root or contains the active folder.".into());
    }
    Ok(())
}
fn probe(active: &Path) -> Result<()> {
    let probe = active.join(format!(".ve-storage-write-check-{}", std::process::id()));
    let mut f = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&probe)
        .map_err(|e| e.to_string())?;
    let expected = b"VideoEnhancer storage probe";
    let result = (|| {
        f.write_all(expected).map_err(|e| e.to_string())?;
        f.sync_all().map_err(|e| e.to_string())?;
        if fs::read(&probe).map_err(|e| e.to_string())? != expected {
            return Err("App data probe read-back failed.".into());
        }
        Ok(())
    })();
    drop(f);
    let cleanup = fs::remove_file(probe).map_err(|e| e.to_string());
    result.and(cleanup)
}
pub fn remove_old(state: &State, parent: &tauri::WebviewWindow) -> Result<Value> {
    let _busy = BusyGuard::acquire(&state.storage_busy)?;
    let file = pointer()?;
    let saved = read(&file)?;
    let (old, entries) = verify(state, &saved)?;
    let deletable: Vec<_> = entries
        .iter()
        .filter(|entry| candidate_size(&old, entry).is_some())
        .collect();
    let bytes: u64 = deletable.iter().filter_map(|e| e["size"].as_u64()).sum();
    let message=format!("Remove the old app data folder?\n{} · {} files · {:.2} GB\nThis permanently deletes the app's old copy. Your videos are not in this folder.",old.display(),deletable.len(),bytes as f64/1e9);
    // The first custom button is the default. Cancel must be first.
    let confirm = || {
        rfd::MessageDialog::new()
            .set_parent(parent)
            .set_title("VideoEnhancer")
            .set_description(message)
            .set_buttons(rfd::MessageButtons::OkCancelCustom(
                "Cancel".into(),
                "Remove".into(),
            ))
            .show()
    };
    #[cfg(feature = "e2e")]
    let answer = match state
        .remove_confirmation
        .lock()
        .map_err(|e| e.to_string())?
        .take()
    {
        Some(true) => rfd::MessageDialogResult::Custom("Remove".into()),
        Some(false) => rfd::MessageDialogResult::Custom("Cancel".into()),
        None => confirm(),
    };
    #[cfg(not(feature = "e2e"))]
    let answer = confirm();
    if answer != rfd::MessageDialogResult::Custom("Remove".into()) {
        return Ok(json!({"cancelled":true}));
    }
    verify(state, &saved)?;
    let total: u64 = entries
        .iter()
        .filter_map(|entry| entry["size"].as_u64())
        .sum();
    let mut checked_bytes = 0;
    let outcome = remove_entries_progress(&old, &entries, |index, entry| {
        *state
            .storage_progress
            .lock()
            .unwrap_or_else(|e| e.into_inner()) = json!({
            "phase":format!("Removing old app data: {} ({}/{})",entry["path"].as_str().unwrap_or("file"),index+1,entries.len()),
            "copied_bytes":checked_bytes,"total_bytes":total
        });
        checked_bytes += entry["size"].as_u64().unwrap_or(0);
    });
    let latest = finish_removal(&file, &saved, &outcome.remaining)?;
    *state
        .storage_verification
        .lock()
        .map_err(|e| e.to_string())? = json!({"pointer":latest,"can_remove":false,"reason":if outcome.remaining.is_empty() { "There are no old app-data files to remove." } else { "Remaining files were kept because they could not be safely removed. Reopen Settings to check again." }});
    let kept = count_files(&old).ok();
    let _ = fs::remove_dir(&old);
    Ok(
        json!({"removed_files":outcome.files,"removed_bytes":outcome.bytes,"kept_files":kept,"kept_manifest_files":outcome.remaining.len(),"kept_reasons":outcome.reasons,"folder":old,
        "message":format!("Removed {} files ({:.2} GB). Kept {} move-manifest files: {}. Other unlisted files are kept.\n{}",outcome.files,outcome.bytes as f64/1e9,outcome.remaining.len(),reason_sentence(&outcome.reasons),old.display())}),
    )
}
fn finish_removal(file: &Path, saved: &Value, remaining: &[Value]) -> Result<Value> {
    let mut latest = read(file)?;
    if latest["active"] != saved["active"]
        || latest["previous"] != saved["previous"]
        || latest["manifest"] != saved["manifest"]
    {
        return Err("The storage pointer changed during removal. Its new value was kept.".into());
    }
    if remaining.is_empty() {
        latest
            .as_object_mut()
            .ok_or("Invalid pointer")?
            .remove("previous");
        latest.as_object_mut().unwrap().remove("manifest");
    } else {
        latest["manifest"] = json!(remaining);
    }
    write(file, &latest)?;
    Ok(latest)
}
fn removable_size(old: &Path, entry: &Value) -> Option<u64> {
    candidate_size(old, entry)?;
    matching_old_size(&old.join(relative(entry["path"].as_str()?).ok()?), entry)
}
fn ensure_available_drive(home: &Path) -> Result<()> {
    if home.ancestors().last().is_some_and(|root| !root.exists()) {
        return Err("The app data drive is unavailable. Reconnect it and restart VideoEnhancer. The saved location has been kept.".into());
    }
    Ok(())
}
fn ensure_no_previous(saved: &Value) -> Result<()> {
    if saved["previous"].is_string() {
        return Err("An earlier app data folder is still recorded. Remove the old copy before moving again.".into());
    }
    Ok(())
}
fn candidate_size(old: &Path, entry: &Value) -> Option<u64> {
    let rel = relative(entry["path"].as_str()?).ok()?;
    no_links(old, &rel).ok()?;
    let path = old.join(rel);
    let meta = fs::symlink_metadata(&path).ok()?;
    if entry["protected_video"] == true
        || !meta.is_file()
        || meta.file_attributes() & 0x400 != 0
        || Some(meta.len()) != entry["size"].as_u64()
    {
        return None;
    }
    let size = meta.len();
    // Check current delete access without modifying the file; check again after confirmation.
    fs::OpenOptions::new()
        .access_mode(0x10000)
        .share_mode(7)
        .open(path)
        .ok()?;
    Some(size)
}
struct Removal {
    files: usize,
    bytes: u64,
    remaining: Vec<Value>,
    reasons: Value,
}
#[cfg(test)]
fn remove_entries(old: &Path, entries: &[Value]) -> Removal {
    remove_entries_progress(old, entries, |_, _| {})
}
fn reason_sentence(reasons: &Value) -> String {
    reasons
        .as_object()
        .map(|items| {
            items
                .iter()
                .map(|(reason, count)| format!("{count} {reason}"))
                .collect::<Vec<_>>()
                .join("; ")
        })
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "none".into())
}
fn remove_entries_progress(
    old: &Path,
    entries: &[Value],
    mut progress: impl FnMut(usize, &Value),
) -> Removal {
    let mut result = Removal {
        files: 0,
        bytes: 0,
        remaining: vec![],
        reasons: json!({}),
    };
    for (index, entry) in entries.iter().enumerate() {
        progress(index, entry);
        let rel = entry["path"].as_str().and_then(|p| relative(p).ok());
        let path = rel.as_ref().map(|p| old.join(p));
        if path.as_ref().is_some_and(|p| matches!(fs::symlink_metadata(p), Err(e) if e.kind() == std::io::ErrorKind::NotFound)) { continue; }
        let reason = if entry["protected_video"] == true {
            Some("protected or blocked by a damaged manifest")
        } else if let Some(size) = removable_size(old, entry) {
            if let Some(path) = path.as_ref().filter(|p| fs::remove_file(p).is_ok()) {
                result.files += 1;
                result.bytes += size;
                let mut parent = path.parent();
                while let Some(folder) = parent {
                    if folder == old || fs::remove_dir(folder).is_err() {
                        break;
                    }
                    parent = folder.parent();
                }
                None
            } else {
                Some("locked or inaccessible")
            }
        } else {
            Some("changed, locked, linked or inaccessible")
        };
        if let Some(reason) = reason {
            let count = result.reasons[reason].as_u64().unwrap_or(0);
            result.reasons[reason] = json!(count + 1);
            result.remaining.push(entry.clone());
        }
    }
    result
}

fn matching_old_size(path: &Path, entry: &Value) -> Option<u64> {
    let meta = fs::symlink_metadata(path).ok()?;
    if entry["protected_video"] == true
        || !meta.is_file()
        || meta.file_attributes() & 0x400 != 0
        || Some(meta.len()) != entry["size"].as_u64()
    {
        return None;
    }
    if let Some(expected) = entry["sha256"].as_str() {
        #[cfg(test)]
        HASH_READS.with(|count| count.set(count.get() + 1));
        let mut stream = fs::File::open(path).ok()?;
        let mut hasher = Sha256::new();
        let mut buffer = [0u8; 65536];
        loop {
            let count = stream.read(&mut buffer).ok()?;
            if count == 0 {
                break;
            }
            hasher.update(&buffer[..count]);
        }
        if format!("{:x}", hasher.finalize()) != expected {
            return None;
        }
    }
    Some(meta.len())
}
fn count_files(root: &Path) -> Result<usize> {
    let mut count = 0;
    for entry in fs::read_dir(root).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let meta = fs::symlink_metadata(entry.path()).map_err(|e| e.to_string())?;
        if meta.is_dir() && meta.file_attributes() & 0x400 == 0 {
            count += count_files(&entry.path())?;
        } else {
            count += 1;
        }
    }
    Ok(count)
}
pub fn relocate(state: &State, target: &str) -> Result<Value> {
    if std::env::var_os("VE_HOME").is_some() {
        return Err(OVERRIDE_MESSAGE.into());
    }
    ensure_no_previous(&read(&pointer()?)?)?;
    let target = PathBuf::from(target);
    if !target.is_absolute() || target.to_string_lossy().contains('\0') {
        return Err("Choose an absolute folder.".into());
    }
    if target.exists()
        && (!target.is_dir()
            || fs::read_dir(&target)
                .map_err(|e| e.to_string())?
                .next()
                .is_some())
    {
        return Err("The target must be new or empty.".into());
    }
    let _busy = BusyGuard::acquire(&state.storage_busy)?;
    *state
        .storage_verification
        .lock()
        .map_err(|e| e.to_string())? = Value::Null;
    let source = state.home.lock().map_err(|e| e.to_string())?.clone();
    let mut _moving = None;
    let result = (|| {
        *state.storage_progress.lock().map_err(|e| e.to_string())? =
            json!({"phase":"Preparing the service"});
        let connection = state.connected_internal()?;
        engine::request(&connection, "storage/prepare", "POST", Some(&json!({})))?;
        _moving = Some(BusyGuard::acquire(&state.storage_moving)?);
        engine::stop(&connection)?;
        let root = engine::root()?;
        *state.storage_progress.lock().map_err(|e| e.to_string())? =
            json!({"phase":"Copying and verifying","copied_bytes":0});
        let mut copy = Command::new(engine::python(&root))
            .args(["-m", "videoenhancer.service.storage"])
            .arg(&source)
            .arg(&target)
            .current_dir(root)
            .env("VE_HOME", &source)
            .creation_flags(0x08000000)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| e.to_string())?;
        let mut stderr = copy.stderr.take().ok_or("Copy diagnostics missing")?;
        let diagnostics = std::thread::spawn(move || {
            let mut tail = Vec::new();
            let mut buffer = [0u8; 4096];
            while let Ok(count) = stderr.read(&mut buffer) {
                if count == 0 {
                    break;
                }
                tail.extend_from_slice(&buffer[..count]);
                if tail.len() > 8000 {
                    tail.drain(..tail.len() - 8000);
                }
            }
            tail
        });
        let mut copied = None;
        let stdout = copy.stdout.take().ok_or("Copy progress missing")?;
        for line in BufReader::new(stdout).lines() {
            let line = match line {
                Ok(line) => line,
                Err(error) => {
                    let _ = copy.kill();
                    let _ = copy.wait();
                    let _ = diagnostics.join();
                    return Err(error.to_string());
                }
            };
            if let Ok(value) = serde_json::from_str::<Value>(&line) {
                if value.get("result").is_some() {
                    copied = Some(value);
                } else {
                    *state.storage_progress.lock().map_err(|e| e.to_string())? = value;
                }
            }
        }
        let outcome = copy.wait().map_err(|e| e.to_string())?;
        let stderr = diagnostics.join().map_err(|_| "Copy diagnostics failed")?;
        if !outcome.success() {
            return Err(String::from_utf8_lossy(&stderr).into_owned());
        }
        let copied = copied.ok_or("Missing copy result")?;
        *state.storage_progress.lock().map_err(|e| e.to_string())? =
            json!({"phase":"Starting the service"});
        let next = engine::start(&target, true)?;
        if let Err(error) = write(
            &pointer()?,
            &json!({"active":target,"previous":source,"manifest":copied["result"]["manifest"]}),
        ) {
            let _ = engine::stop(&next);
            return Err(error);
        }
        *state.home.lock().map_err(|e| e.to_string())? = target.clone();
        *state.connection.lock().map_err(|e| e.to_string())? = Some(next);
        *state.storage_progress.lock().map_err(|e| e.to_string())? =
            json!({"phase":"Move completed","damaged":copied["result"]["damaged"]});
        Ok(json!({"moved":true,"folder":target,"damaged":copied["result"]["damaged"]}))
    })();
    if result.is_err() {
        if let Ok(c) = state.connected_internal() {
            let _ = engine::request(&c, "storage/prepare", "POST", Some(&json!({"cancel":true})));
        }
        *state.connection.lock().map_err(|e| e.to_string())? = None;
        let _ = engine::start(&source, false);
        *state.storage_progress.lock().map_err(|e| e.to_string())? =
            json!({"phase":"Move failed; the previous folder is still in use"});
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn removal_requires_an_unchanged_accessible_unprotected_file() {
        let root = std::env::temp_dir().join(format!("ve-empty-remove-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        fs::write(root.join("record"), b"first").unwrap();
        let valid =
            json!({"path":"record","size":5,"sha256":format!("{:x}",Sha256::digest(b"first"))});
        assert!(removal_eligibility(&root, &[]).is_err());
        let mut protected = valid.clone();
        protected["protected_video"] = json!(true);
        assert!(removal_eligibility(&root, &[protected]).is_err());
        assert!(removal_eligibility(&root, std::slice::from_ref(&valid)).is_ok());
        fs::write(root.join("record"), b"other").unwrap();
        assert!(removal_eligibility(&root, std::slice::from_ref(&valid)).is_err());
        fs::remove_file(root.join("record")).unwrap();
        assert!(removal_eligibility(&root, &[valid]).is_err());
        fs::remove_dir(root).unwrap();
    }

    #[test]
    fn recovered_location_is_distinct_from_a_legacy_move() {
        let recovered = unverified_location_reason(&json!({"recovered":true}));
        assert!(recovered.contains("recovered by the app"));
        assert!(!recovered.contains("earlier version"));
        assert!(unverified_location_reason(&json!({})).contains("earlier version"));
    }

    #[test]
    fn remove_hashes_once_after_metadata_only_confirmation_and_reports_progress() {
        let root = std::env::temp_dir().join(format!("ve-one-hash-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let path = root.join("record.json");
        fs::write(&path, b"first").unwrap();
        let entry = json!({"path":"record.json","size":5,"sha256":format!("{:x}",Sha256::digest(b"first"))});
        HASH_READS.with(|count| count.set(0));
        assert_eq!(candidate_size(&root, &entry), Some(5));
        let mut progress = vec![];
        let result = remove_entries_progress(&root, &[entry], |index, entry| {
            progress.push((index, entry["path"].clone()))
        });
        assert_eq!(result.files, 1);
        assert_eq!(progress.len(), 1);
        HASH_READS.with(|count| assert_eq!(count.get(), 1));
        fs::remove_dir(root).unwrap();
    }

    #[test]
    fn second_move_is_refused_and_result_reasons_are_sentences() {
        let saved = json!({"active":"new","previous":"old","manifest":[{"path":"kept"}]});
        let before = saved.clone();
        assert!(ensure_no_previous(&saved)
            .unwrap_err()
            .contains("Remove the old copy"));
        assert_eq!(saved, before);
        assert_eq!(reason_sentence(&json!({"locked":2})), "2 locked");
        assert!(!reason_sentence(&json!({"locked":2})).contains('{'));
    }

    #[test]
    fn damaged_pointer_is_preserved_and_cannot_be_silently_overwritten() {
        let root = std::env::temp_dir().join(format!("ve-damaged-pointer-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let path = root.join("pointer.json");
        for raw in [b"{torn".as_slice(), b"not JSON", b"[]"] {
            fs::write(&path, raw).unwrap();
            assert_eq!(startup_pointer(&path).unwrap(), json!({}));
            assert!(write(&path, &json!({"active":"replacement"})).is_err());
            assert_eq!(fs::read(&path).unwrap(), raw);
        }
        fs::remove_file(path).unwrap();
        fs::remove_dir(root).unwrap();
    }

    #[test]
    fn disconnected_drive_keeps_pointer_bytes() {
        let letter = ('A'..='Z')
            .find(|letter| !Path::new(&format!("{letter}:\\")).exists())
            .unwrap();
        let home = PathBuf::from(format!("{letter}:\\synthetic\\VideoEnhancer"));
        assert!(ensure_available_drive(&home)
            .unwrap_err()
            .contains("saved location has been kept"));
    }
    #[test]
    fn pointer_write_rechecks_active_folder_and_keeps_remaining_manifest_for_retry() {
        let root = std::env::temp_dir().join(format!("ve-p1f-pointer-{}", std::process::id()));
        let file = root.join("pointer.json");
        let saved = json!({"active":"D:\\scratch\\new","previous":"D:\\scratch\\old","manifest":[{"path":"kept","size":4}],"extra":"preserved"});
        write(&file, &saved).unwrap();
        let kept = finish_removal(&file, &saved, saved["manifest"].as_array().unwrap()).unwrap();
        assert_eq!(kept["previous"], saved["previous"]);
        assert_eq!(kept["extra"], "preserved");
        let changed = json!({"active":"D:\\scratch\\other","previous":"D:\\scratch\\new"});
        write(&file, &changed).unwrap();
        assert!(finish_removal(&file, &saved, &[]).is_err());
        assert_eq!(read(&file).unwrap(), changed);
        write(&file, &saved).unwrap();
        let done = finish_removal(&file, &saved, &[]).unwrap();
        assert!(done["previous"].is_null() && done["manifest"].is_null());
        fs::remove_file(file).unwrap();
        fs::remove_dir(root).unwrap();
    }
    #[test]
    fn one_busy_guard_excludes_move_remove_and_verification_and_releases_on_error() {
        let busy = std::sync::atomic::AtomicBool::new(false);
        let first = BusyGuard::acquire(&busy).unwrap();
        std::thread::scope(|scope| {
            scope
                .spawn(|| assert!(BusyGuard::acquire(&busy).is_err()))
                .join()
                .unwrap();
        });
        drop(first);
        let fails = || -> Result<()> {
            let _guard = BusyGuard::acquire(&busy)?;
            Err("fixture error".into())
        };
        assert!(fails().is_err());
        assert!(BusyGuard::acquire(&busy).is_ok());
    }
    #[test]
    fn retained_manifest_can_retry_changed_and_locked_files_without_touching_protected_or_unknown_files(
    ) {
        let root = std::env::temp_dir().join(format!("ve-p1f-remove-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        for name in ["good", "changed", "locked", "protected", "unknown"] {
            fs::write(root.join(name), b"first").unwrap();
        }
        let entries: Vec<Value> = ["good","changed","locked","protected"].into_iter().map(|name| json!({"path":name,"size":5,"sha256":format!("{:x}",Sha256::digest(b"first")),"protected_video":name=="protected"})).collect();
        fs::write(root.join("changed"), b"other").unwrap();
        let locked = fs::OpenOptions::new()
            .read(true)
            .share_mode(0)
            .open(root.join("locked"))
            .unwrap();
        assert_eq!(
            entries
                .iter()
                .filter(|e| removable_size(&root, e).is_some())
                .count(),
            1
        );
        let first = remove_entries(&root, &entries);
        assert_eq!(first.files, 1);
        assert_eq!(first.bytes, 5);
        assert_eq!(first.remaining.len(), 3);
        assert!(root.join("unknown").is_file());
        drop(locked);
        fs::write(root.join("changed"), b"first").unwrap();
        let retried = remove_entries(&root, &first.remaining);
        assert_eq!(retried.files, 2);
        assert_eq!(retried.remaining.len(), 1);
        assert_eq!(fs::read(root.join("protected")).unwrap(), b"first");
        for name in ["protected", "unknown"] {
            fs::remove_file(root.join(name)).unwrap();
        }
        fs::remove_dir(root).unwrap();
    }
    #[test]
    fn old_file_manifest_matches_size_hash_and_video_protection() {
        let file = std::env::temp_dir().join(format!("ve-old-manifest-{}.txt", std::process::id()));
        fs::write(&file, b"first").unwrap();
        let mut entry = json!({"size":5,"sha256":format!("{:x}",Sha256::digest(b"first"))});
        assert_eq!(matching_old_size(&file, &entry), Some(5));
        fs::write(&file, b"other").unwrap();
        assert_eq!(matching_old_size(&file, &entry), None);
        entry["sha256"] = Value::Null;
        assert_eq!(matching_old_size(&file, &entry), Some(5));
        entry["size"] = json!(6);
        assert_eq!(matching_old_size(&file, &entry), None);
        entry["size"] = json!(5);
        entry["protected_video"] = json!(true);
        assert_eq!(matching_old_size(&file, &entry), None);
        fs::remove_file(&file).unwrap();
        assert_eq!(matching_old_size(&file, &entry), None);
    }
    #[test]
    fn resolved_old_folder_cannot_be_a_drive_root_or_active_ancestor() {
        let active = Path::new("D:\\scratch\\new");
        for old in ["C:\\", "D:\\", "D:\\scratch", "D:\\scratch\\new"] {
            assert!(safe_old_folder(active, Path::new(old)).is_err());
        }
        assert!(safe_old_folder(active, Path::new("D:\\scratch\\old")).is_ok());
    }
    #[test]
    fn probe_checks_read_write_remove_and_fails_closed() {
        let root = std::env::temp_dir().join(format!("ve-probe-test-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        assert!(probe(&root).is_ok());
        assert_eq!(fs::read_dir(&root).unwrap().count(), 0);
        let blocked = root.join(format!(".ve-storage-write-check-{}", std::process::id()));
        fs::create_dir(&blocked).unwrap();
        assert!(probe(&root).is_err());
        fs::remove_dir(blocked).unwrap();
        fs::remove_dir(&root).unwrap();
        assert!(probe(&root).is_err());
    }
    #[test]
    fn manifest_paths() {
        for p in ["../escape", "/root", "C:\\root", "a/../b", ""] {
            assert!(relative(p).is_err());
        }
        assert!(relative("jobs/a/manifest.json").is_ok());
    }
    #[test]
    fn migration() {
        let root = std::env::temp_dir().join(format!("ve-pointer-test-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let legacy = root.join("legacy.json");
        let dest = root.join("canonical.json");
        write(&legacy, &json!({"active":"C:\\isolated"})).unwrap();
        assert!(migrate(&dest, &legacy).unwrap());
        assert!(!migrate(&dest, &legacy).unwrap());
        assert_eq!(read(&dest).unwrap()["active"], "C:\\isolated");
        fs::remove_file(dest).unwrap();
        fs::remove_file(legacy).unwrap();
        fs::remove_dir(root).unwrap();
    }
}
