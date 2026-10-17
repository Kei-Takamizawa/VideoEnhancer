use crate::{engine, State};
use engine::Result;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::os::windows::{fs::MetadataExt, process::CommandExt};
use std::{
    fs,
    io::{BufRead, BufReader, Read, Write},
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
    sync::atomic::Ordering,
};

pub const OVERRIDE_MESSAGE: &str = "App data is set by VE_HOME. Unset it to use Move.";
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
    let migrated = migrate(&file, &legacy)?;
    let mut value = read(&file)?;
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
            value = json!({"active":next,"previous":home});
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
pub fn status(state: &State) -> Result<Value> {
    let mut value = read(&pointer()?)?;
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
    value["can_remove"] = json!(verify(state, &value).is_ok());
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
    let health = engine::request(&state.connected()?, "health", "GET", None)?;
    if !engine::reported_home_matches(&health, &a) {
        return Err("The engine is not using the verified active folder.".into());
    }
    let entries = saved["manifest"]
        .as_array()
        .ok_or("No verified move manifest")?
        .clone();
    let records = engine::request(&state.connected()?, "storage", "GET", None)?;
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
    let file = pointer()?;
    let mut saved = read(&file)?;
    let (old, entries) = verify(state, &saved)?;
    let bytes: u64 = entries.iter().filter_map(|e| e["size"].as_u64()).sum();
    let message=format!("Remove the old app data folder?\n{} · {} files · {:.2} GB\nThis permanently deletes the app's old copy. Your videos are not in this folder.",old.display(),entries.len(),bytes as f64/1e9);
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
    let mut removed = 0;
    let mut removed_bytes = 0;
    for entry in &entries {
        if entry["protected_video"] == true {
            continue;
        }
        let rel = relative(entry["path"].as_str().ok_or("Invalid move manifest")?)?;
        if no_links(&old, &rel).is_err() {
            continue;
        }
        let path = old.join(&rel);
        let Some(size) = matching_old_size(&path, entry) else {
            continue;
        };
        if fs::remove_file(&path).is_ok() {
            removed += 1;
            removed_bytes += size;
            let mut parent = path.parent();
            while let Some(folder) = parent {
                if folder == old {
                    break;
                }
                if fs::remove_dir(folder).is_err() {
                    break;
                }
                parent = folder.parent();
            }
        }
    }
    let kept = count_files(&old)?;
    let _ = fs::remove_dir(&old);
    saved
        .as_object_mut()
        .ok_or("Invalid pointer")?
        .remove("previous");
    saved.as_object_mut().unwrap().remove("manifest");
    write(&file, &saved)?;
    Ok(
        json!({"removed_files":removed,"removed_bytes":removed_bytes,"kept_files":kept,"folder":old,"message":format!("Removed {removed} files ({:.2} GB). Kept {kept} files that were not part of the move.\n{}",removed_bytes as f64/1e9,old.display())}),
    )
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
    if state.storage_busy.swap(true, Ordering::SeqCst) {
        return Err("App data is already moving.".into());
    }
    let source = state.home.lock().map_err(|e| e.to_string())?.clone();
    let result = (|| {
        *state.storage_progress.lock().map_err(|e| e.to_string())? =
            json!({"phase":"Preparing the service"});
        let connection = state.connected_internal()?;
        engine::request(&connection, "storage/prepare", "POST", Some(&json!({})))?;
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
    state.storage_busy.store(false, Ordering::SeqCst);
    result
}

#[cfg(test)]
mod tests {
    use super::*;
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
