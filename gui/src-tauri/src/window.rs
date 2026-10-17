use crate::engine::Result;
use serde_json::Value;
use std::{
    os::windows::process::CommandExt,
    path::{Path, PathBuf},
    sync::atomic::Ordering,
};
use tauri::{Emitter, Manager};
use windows::{
    core::PCWSTR,
    Win32::UI::{Shell::ShellExecuteW, WindowsAndMessaging::SW_SHOWNORMAL},
};

pub const ZOOM: [u64; 6] = [80, 90, 100, 110, 125, 150];
pub const HEVC_STORE: &str = "ms-windows-store://pdp/?ProductId=9NMZLZ57R3T7";
pub fn memory_target(window: &tauri::WebviewWindow, low: bool) -> Result<()> {
    let (sender, receiver) = std::sync::mpsc::sync_channel(1);
    window
        .with_webview(move |platform| {
            use webview2_com::Microsoft::Web::WebView2::Win32::{
                ICoreWebView2_19, COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_LOW,
                COREWEBVIEW2_MEMORY_USAGE_TARGET_LEVEL_NORMAL,
            };
            use windows::core::Interface;
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
            let _ = sender.send(result.map_err(|e| e.to_string()));
        })
        .map_err(|e| e.to_string())?;
    receiver
        .recv_timeout(std::time::Duration::from_secs(5))
        .map_err(|e| e.to_string())?
}
#[link(name = "dwmapi")]
extern "system" {
    fn DwmSetWindowAttribute(
        hwnd: *mut std::ffi::c_void,
        attribute: u32,
        value: *const u32,
        size: u32,
    ) -> i32;
}

pub fn theme(window: &tauri::WebviewWindow, value: &str) -> Result<()> {
    let chosen = match value {
        "dark" => Some(tauri::Theme::Dark),
        "light" => Some(tauri::Theme::Light),
        "system" => None,
        _ => return Err("Invalid theme.".into()),
    };
    window.set_theme(chosen).map_err(|e| e.to_string())?;
    repaint(window, value)
}
pub fn repaint(window: &tauri::WebviewWindow, value: &str) -> Result<()> {
    let chosen = match value {
        "dark" => Some(tauri::Theme::Dark),
        "light" => Some(tauri::Theme::Light),
        _ => None,
    };
    let dark = chosen.unwrap_or(window.theme().map_err(|e| e.to_string())?) == tauri::Theme::Dark;
    let (caption, text, bg) = if dark {
        (
            0x0014181c,
            0x00bdcfdc,
            tauri::window::Color(28, 24, 20, 255),
        )
    } else {
        (
            0x00e6eff5,
            0x003f4a57,
            tauri::window::Color(245, 239, 230, 255),
        )
    };
    window
        .set_background_color(Some(bg))
        .map_err(|e| e.to_string())?;
    let hwnd = window.hwnd().map_err(|e| e.to_string())?.0;
    for (attribute, value) in [(35, caption), (36, text)] {
        let status = unsafe { DwmSetWindowAttribute(hwnd, attribute, &value, 4) };
        if status < 0 {
            return Err(format!("DWM attribute {attribute} failed: {status}"));
        }
    }
    Ok(())
}
pub fn show(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}
pub fn zoom(window: &tauri::WebviewWindow, percent: u64) -> Result<()> {
    if !ZOOM.contains(&percent) {
        return Err("Choose a supported zoom level.".into());
    }
    window
        .set_zoom(percent as f64 / 100.)
        .map_err(|e| e.to_string())?;
    window
        .emit("zoom-changed", percent)
        .map_err(|e| e.to_string())
}
pub fn valid_path(raw: &str, directory: bool) -> Result<PathBuf> {
    let path = Path::new(raw);
    if !path.is_absolute() || raw.contains('\0') || raw.len() > 32767 {
        return Err("Choose an absolute local path.".into());
    }
    if if directory {
        !path.is_dir()
    } else {
        !path.is_file()
    } {
        return Err("The path does not exist.".into());
    }
    Ok(path.to_owned())
}
pub fn external_allowed(raw: &str, publishers: &[String]) -> bool {
    if raw == HEVC_STORE {
        return true;
    }
    let Ok(url) = reqwest::Url::parse(raw) else {
        return false;
    };
    if url.scheme() != "https"
        || !url.username().is_empty()
        || url.password().is_some()
        || url.port().is_some()
    {
        return false;
    }
    if publishers.iter().any(|item| item == url.as_str()) {
        return true;
    }
    url.host_str() == Some("github.com")
        && (url
            .path()
            .starts_with("/Kei-Takamizawa/VideoEnhancer/blob/main/docs/")
            || url
                .path()
                .strip_prefix("/Kei-Takamizawa/VideoEnhancer/pull/")
                .is_some_and(|id| {
                    !id.is_empty()
                        && id
                            .split('/')
                            .next()
                            .is_some_and(|part| part.bytes().all(|b| b.is_ascii_digit()))
                }))
}
pub fn open(raw: &str, reveal: bool) -> Result<()> {
    if reveal {
        let status = std::process::Command::new("explorer.exe")
            .raw_arg(format!("/select,\"{}\"", raw.replace('/', "\\")))
            .spawn()
            .map_err(|e| e.to_string())?;
        drop(status);
        return Ok(());
    }
    let target: Vec<u16> = raw.encode_utf16().chain(Some(0)).collect();
    let result = unsafe {
        ShellExecuteW(
            None,
            PCWSTR::null(),
            PCWSTR(target.as_ptr()),
            PCWSTR::null(),
            PCWSTR::null(),
            SW_SHOWNORMAL,
        )
    };
    if result.0 as isize <= 32 {
        Err("Windows could not open this item.".into())
    } else {
        Ok(())
    }
}
pub fn startup(settings: &Value) -> Result<()> {
    // Test builds never alter the owner's Run key.
    if cfg!(feature = "e2e") {
        return Ok(());
    }
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let command = format!("\"{}\" --hidden", exe.display());
    let root = winreg::RegKey::predef(winreg::enums::HKEY_CURRENT_USER);
    let path = "Software\\Microsoft\\Windows\\CurrentVersion\\Run";
    let entries = match root.open_subkey_with_flags(path, winreg::enums::KEY_READ) {
        Ok(key) => key
            .enum_values()
            .filter_map(|value| {
                value.ok().and_then(|(name, _)| {
                    key.get_value::<String, _>(&name)
                        .ok()
                        .map(|value| (name, value))
                })
            })
            .collect(),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            std::collections::BTreeMap::new()
        }
        Err(error) => return Err(error.to_string()),
    };
    let old_exe = exe
        .parent()
        .and_then(Path::parent)
        .ok_or("Package folder missing")?
        .join("VideoEnhancer-win32-x64/VideoEnhancer.exe");
    let changes = startup_changes(
        &entries,
        &command,
        &old_exe,
        settings["start_with_windows"] == true,
    );
    if changes.is_empty() {
        return Ok(());
    }
    let (key, _) = root.create_subkey(path).map_err(|e| e.to_string())?;
    for (name, value) in changes {
        if let Some(value) = value {
            key.set_value(name, &value).map_err(|e| e.to_string())?;
        } else {
            key.delete_value(name).map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}
pub fn old_electron_entry(command: &str, expected: &Path) -> bool {
    let path = command
        .trim()
        .strip_prefix('"')
        .and_then(|rest| rest.split_once('"').map(|v| v.0));
    path.is_some_and(|p| Path::new(p) == expected)
}
pub fn startup_changes(
    entries: &std::collections::BTreeMap<String, String>,
    command: &str,
    old_exe: &Path,
    enabled: bool,
) -> Vec<(String, Option<String>)> {
    let mut changes = vec![];
    if enabled {
        for (name, value) in entries {
            if old_electron_entry(value, old_exe) {
                changes.push((name.clone(), None));
            }
        }
        changes.push(("VideoEnhancer".into(), Some(command.into())));
    } else if entries.get("VideoEnhancer").map(String::as_str) == Some(command) {
        changes.push(("VideoEnhancer".into(), None));
    }
    changes
}
pub fn quit(app: &tauri::AppHandle) {
    let handle = app.clone();
    std::thread::spawn(move || {
        let state = handle.state::<std::sync::Arc<crate::State>>();
        let result = state.connected().and_then(|c| crate::engine::stop(&c));
        match result {
            Ok(()) => {
                state.quitting.store(true, Ordering::SeqCst);
                handle.exit(0);
            }
            Err(error) => {
                show(&handle);
                let _ = handle.emit(
                    "desktop-error",
                    format!("The engine could not stop cleanly. Retry Quit. {error}"),
                );
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn links() {
        assert!(external_allowed(
            "https://github.com/Kei-Takamizawa/VideoEnhancer/pull/6",
            &[]
        ));
        for url in [
            "javascript:alert(1)",
            "https://github.com.evil.test/Kei-Takamizawa/VideoEnhancer/pull/6",
            "https://github.com/Kei-Takamizawa/VideoEnhancer/blob/main/docs/../../x",
            "https://evil.test/",
        ] {
            assert!(!external_allowed(url, &[]));
        }
    }
    #[test]
    fn paths() {
        for path in ["relative", "C:\\missing-p1t-file", "C:\\bad\0"] {
            assert!(valid_path(path, false).is_err());
        }
    }
    #[test]
    fn old_startup_exact() {
        let expected = Path::new(r"C:\fixture\VideoEnhancer-win32-x64\VideoEnhancer.exe");
        assert!(old_electron_entry(
            r#""C:\fixture\VideoEnhancer-win32-x64\VideoEnhancer.exe" --hidden"#,
            expected
        ));
        assert!(!old_electron_entry(
            r#""C:\other\VideoEnhancer.exe" --hidden"#,
            expected
        ));
    }
    #[test]
    fn fake_registry_migrates_only_matching_command() {
        let old = Path::new(r"C:\fixture\VideoEnhancer-win32-x64\VideoEnhancer.exe");
        let entries = std::collections::BTreeMap::from([
            (
                "legacy".into(),
                r#""C:\fixture\VideoEnhancer-win32-x64\VideoEnhancer.exe" --hidden"#.into(),
            ),
            (
                "unrelated".into(),
                r#""C:\other\VideoEnhancer.exe" --hidden"#.into(),
            ),
        ]);
        let command = r#""C:\fixture\VideoEnhancer\VideoEnhancer.exe" --hidden"#;
        let changes = startup_changes(&entries, command, old, true);
        assert!(changes.contains(&("legacy".into(), None)));
        assert!(!changes.iter().any(|(name, _)| name == "unrelated"));
        assert!(changes.contains(&("VideoEnhancer".into(), Some(command.into()))));
        let mut registered = entries;
        registered.insert("VideoEnhancer".into(), command.into());
        assert_eq!(
            startup_changes(&registered, command, old, false),
            vec![("VideoEnhancer".into(), None)]
        );
    }
}
