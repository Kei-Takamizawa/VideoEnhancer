#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]
#[cfg(windows)]
mod commands;
#[cfg(windows)]
mod engine;
#[cfg(windows)]
mod media;
#[cfg(windows)]
mod player;
#[cfg(windows)]
mod storage;
#[cfg(windows)]
mod window;
#[cfg(windows)]
use serde_json::{json, Value};
#[cfg(windows)]
use std::{
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        Arc, Mutex,
    },
};
#[cfg(windows)]
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, TrayIconBuilder, TrayIconEvent},
    Emitter, Manager,
};

#[cfg(windows)]
pub struct State {
    home: Mutex<PathBuf>,
    appearance: Mutex<String>,
    startup_error: Mutex<String>,
    zoom_percent: AtomicU64,
    connection: Mutex<Option<engine::Connection>>,
    storage_busy: AtomicBool,
    storage_moving: AtomicBool,
    storage_progress: Mutex<Value>,
    storage_verification: Mutex<Value>,
    quitting: AtomicBool,
    tray_explained: AtomicBool,
    publishers: Mutex<Vec<String>>,
    fetches: media::Fetches,
    #[cfg(feature = "e2e")]
    dialog_files: Mutex<Option<Vec<String>>>,
    #[cfg(feature = "e2e")]
    storage_fixture: Mutex<Option<Value>>,
    #[cfg(feature = "e2e")]
    native_drop: Mutex<Vec<PathBuf>>,
    #[cfg(feature = "e2e")]
    remove_confirmation: Mutex<Option<bool>>,
    #[cfg(feature = "e2e")]
    copied_text: Mutex<String>,
}
#[cfg(windows)]
impl State {
    pub fn connected(&self) -> engine::Result<engine::Connection> {
        if self.storage_moving.load(Ordering::SeqCst) {
            return Err("App data is moving. Wait for it to finish.".into());
        }
        self.connected_internal()
    }
    pub fn connected_internal(&self) -> engine::Result<engine::Connection> {
        let mut current = self.connection.lock().map_err(|e| e.to_string())?;
        if current.is_none() {
            *current = Some(engine::start(
                &self.home.lock().map_err(|e| e.to_string())?,
                false,
            )?);
        }
        Ok(current.as_ref().unwrap().clone())
    }
}

#[cfg(all(test, windows))]
mod connection_tests {
    use super::*;

    #[test]
    fn storage_verification_and_removal_keep_commands_connected() {
        let state = State {
            home: Mutex::new(PathBuf::from("isolated-test")),
            startup_error: Mutex::new(String::new()),
            appearance: Mutex::new("dark".into()),
            zoom_percent: AtomicU64::new(100),
            connection: Mutex::new(Some(engine::Connection {
                port: 1,
                token: "test".into(),
                pid: 1,
                base_url: "http://127.0.0.1:1/v1".into(),
            })),
            storage_busy: AtomicBool::new(true),
            storage_moving: AtomicBool::new(false),
            storage_progress: Mutex::new(Value::Null),
            storage_verification: Mutex::new(Value::Null),
            quitting: AtomicBool::new(false),
            tray_explained: AtomicBool::new(false),
            publishers: Mutex::new(vec![]),
            fetches: media::Fetches::default(),
            #[cfg(feature = "e2e")]
            dialog_files: Mutex::new(None),
            #[cfg(feature = "e2e")]
            storage_fixture: Mutex::new(None),
            #[cfg(feature = "e2e")]
            native_drop: Mutex::new(vec![]),
            #[cfg(feature = "e2e")]
            remove_confirmation: Mutex::new(None),
            #[cfg(feature = "e2e")]
            copied_text: Mutex::new(String::new()),
        };
        assert!(state.connected().is_ok());
        state.storage_moving.store(true, Ordering::SeqCst);
        assert!(state.connected().is_err());
    }
}
#[cfg(not(windows))]
fn main() {
    println!("The desktop app requires Windows 11.");
}

#[cfg(windows)]
fn initial_state() -> Option<(Arc<State>, Value)> {
    let home = match storage::startup() {
        Ok(home) => home,
        Err(error) => {
            if error != "Startup cancelled." {
                rfd::MessageDialog::new()
                    .set_title("VideoEnhancer")
                    .set_description(error)
                    .show();
            }
            return None;
        }
    };
    let initial: Value = std::fs::read(home.join("settings.json"))
        .ok()
        .and_then(|b| serde_json::from_slice(&b).ok())
        .unwrap_or_else(|| json!({}));
    let state = Arc::new(State {
        home: Mutex::new(home),
        startup_error: Mutex::new(String::new()),
        appearance: Mutex::new(initial["theme"].as_str().unwrap_or("system").to_owned()),
        zoom_percent: AtomicU64::new(
            initial["zoom"]
                .as_u64()
                .filter(|v| window::ZOOM.contains(v))
                .unwrap_or(100),
        ),
        connection: Mutex::new(None),
        storage_busy: AtomicBool::new(false),
        storage_moving: AtomicBool::new(false),
        storage_progress: Mutex::new(json!({"phase":"Idle"})),
        storage_verification: Mutex::new(Value::Null),
        quitting: AtomicBool::new(false),
        tray_explained: AtomicBool::new(initial["tray_explained"] == true),
        publishers: Mutex::new(vec![]),
        fetches: media::Fetches::default(),
        #[cfg(feature = "e2e")]
        dialog_files: Mutex::new(None),
        #[cfg(feature = "e2e")]
        storage_fixture: Mutex::new(None),
        #[cfg(feature = "e2e")]
        native_drop: Mutex::new(vec![]),
        #[cfg(feature = "e2e")]
        remove_confirmation: Mutex::new(None),
        #[cfg(feature = "e2e")]
        copied_text: Mutex::new(String::new()),
    });
    Some((state, initial))
}

#[cfg(windows)]
fn main() {
    #[cfg(feature = "e2e")]
    eprintln!("E2E startup: main");
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            window::show(app)
        }))
        .register_asynchronous_uri_scheme_protocol("ve-media", |context, request, responder| {
            media::serve(context.app_handle().clone(), request, responder)
        })
        .on_page_load(|window, event| {
            if event.event() == tauri::webview::PageLoadEvent::Finished {
                let _ = window.eval("window.dispatchEvent(new Event('desktop-loaded'))");
            }
        })
        .on_window_event(|window, event| {
            let state = window.state::<Arc<State>>();
            #[cfg(feature = "e2e")]
            if matches!(event, tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed) {
                eprintln!("E2E lifecycle: time_ms={} event={:?} quitting={} reason={}",
                    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_millis(),
                    event, state.quitting.load(Ordering::SeqCst),
                    if state.quitting.load(Ordering::SeqCst) { "Quit requested" } else { "native window event; origin unknown" });
            }
            match event {
                tauri::WindowEvent::CloseRequested { api, .. }
                    if !state.quitting.load(Ordering::SeqCst) =>
                {
                    api.prevent_close();
                    if state.tray_explained.load(Ordering::SeqCst) {
                        let _ = window.hide();
                    } else {
                        let _ = window.emit("tray-explanation", ());
                    }
                }
                tauri::WindowEvent::DragDrop(tauri::DragDropEvent::Enter { paths, .. }) => {
                    let _ = window.emit("native-file-drop", json!({"type":"enter","paths":paths}));
                }
                tauri::WindowEvent::DragDrop(tauri::DragDropEvent::Drop { paths, .. }) => {
                    #[cfg(feature = "e2e")]
                    if let Ok(mut saved) = state.native_drop.lock() {
                        *saved = paths.clone();
                    }
                    let _ = window.emit("native-file-drop", json!({"type":"drop","paths":paths}));
                }
                tauri::WindowEvent::DragDrop(tauri::DragDropEvent::Leave) => {
                    let _ = window.emit("native-file-drop", json!({"type":"leave","paths":[]}));
                }
                tauri::WindowEvent::ThemeChanged(_) => {
                    if let Some(webview) = window.app_handle().get_webview_window("main") {
                        if let Ok(theme) = state.appearance.lock() {
                            let _ = window::repaint(&webview, &theme);
                        }
                    }
                }
                _ => {}
            }
        })
        .setup(move |app| {
            #[cfg(feature = "e2e")]
            eprintln!("E2E startup: setup, resolving isolated home");
            // The single-instance plugin runs first; a second launch only focuses it.
            let Some((state, initial)) = initial_state() else {
                std::process::exit(0);
            };
            app.manage(state);
            #[cfg(feature = "e2e")]
            eprintln!("E2E startup: home resolved");
            #[cfg(feature = "e2e")]
            app.add_capability(
                tauri::ipc::CapabilityBuilder::new("e2e-main")
                    .window("main")
                    .permission("allow-desktop-test"),
            )?;
            let link_handle = app.handle().clone();
            #[cfg(feature = "e2e")]
            eprintln!("E2E startup: creating webview");
            let webview_builder =
                tauri::WebviewWindowBuilder::from_config(app, &app.config().app.windows[0])?
                    .on_navigation(|url| {
                        url.origin().ascii_serialization() == "http://tauri.localhost"
                            || (cfg!(debug_assertions)
                                && url.origin().ascii_serialization() == "http://127.0.0.1:5173")
                    })
                    .on_new_window(move |url, _| {
                        let state = link_handle.state::<Arc<State>>();
                        if let Ok(urls) = state.publishers.lock() {
                            if window::external_allowed(url.as_str(), &urls) {
                                let _ = window::open(url.as_str(), false);
                            }
                        }
                        tauri::webview::NewWindowResponse::Deny
                    });
            #[cfg(feature = "cdp")]
            let webview_builder = {
                // Elevated CI hosts ignore environment-only WebView2 debugging flags.
                let port = std::env::var("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS")
                    .ok()
                    .and_then(|args| {
                        args.split_ascii_whitespace()
                            .find_map(|arg| arg.strip_prefix("--remote-debugging-port="))
                            .and_then(|port| port.parse::<u16>().ok())
                    })
                    .filter(|port| *port != 0);
                if let Some(port) = port {
                    webview_builder.additional_browser_args(&format!(
                        "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection --autoplay-policy=no-user-gesture-required --remote-debugging-port={port}"
                    ))
                } else {
                    webview_builder
                }
            };
            let webview = webview_builder.build()?;
            #[cfg(feature = "e2e")]
            eprintln!("E2E startup: webview created");
            window::theme(&webview, initial["theme"].as_str().unwrap_or("system"))
                .map_err(std::io::Error::other)?;
            let percent = initial["zoom"]
                .as_u64()
                .filter(|v| window::ZOOM.contains(v))
                .unwrap_or(100);
            window::zoom(&webview, percent).map_err(std::io::Error::other)?;
            // Disable WebView2 scaling and browser commands; app zoom uses the explicit seam.
            webview.with_webview(|platform| unsafe {
                use webview2_com::Microsoft::Web::WebView2::Win32::{
                    ICoreWebView2Settings3, ICoreWebView2Settings5,
                };
                use windows::core::Interface;
                if let Ok(core) = platform.controller().CoreWebView2() {
                    if let Ok(settings) = core.Settings() {
                        let _ = settings.SetIsZoomControlEnabled(false);
                        let _ = settings.SetAreDevToolsEnabled(false);
                        if let Ok(s) = settings.cast::<ICoreWebView2Settings3>() {
                            let _ = s.SetAreBrowserAcceleratorKeysEnabled(false);
                        }
                        if let Ok(s) = settings.cast::<ICoreWebView2Settings5>() {
                            let _ = s.SetIsPinchZoomEnabled(false);
                        }
                    }
                }
            })?;
            let open = MenuItem::with_id(app, "open", "Open VideoEnhancer", true, None::<&str>)?;
            let pause = MenuItem::with_id(app, "pause", "Pause processing", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let separator = PredefinedMenuItem::separator(app)?;
            let menu = Menu::with_items(app, &[&open, &pause, &separator, &quit])?;
            TrayIconBuilder::new()
                .icon(tauri::image::Image::from_bytes(include_bytes!(
                    "../icons/icon.png"
                ))?)
                .tooltip("VideoEnhancer")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => window::show(app),
                    "quit" => window::quit(app),
                    "pause" => {
                        let handle = app.clone();
                        std::thread::spawn(move || {
                            let state = handle.state::<Arc<State>>();
                            if let Ok(c) = state.connected() {
                                if let Ok(h) = engine::request(&c, "health", "GET", None) {
                                    let _ = engine::request(
                                        &c,
                                        "processing",
                                        "POST",
                                        Some(&json!({"paused":h["paused_all"]!=true})),
                                    );
                                }
                            }
                        });
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::DoubleClick {
                        button: MouseButton::Left,
                        ..
                    } = event
                    {
                        window::show(tray.app_handle());
                    }
                })
                .build(app)?;
            #[cfg(feature = "e2e")]
            eprintln!("E2E startup: tray created");
            let handle = app.handle().clone();
            std::thread::spawn(move || loop {
                std::thread::sleep(std::time::Duration::from_secs(3));
                let state = handle.state::<Arc<State>>();
                if state.quitting.load(Ordering::SeqCst) {
                    break;
                }
                if let Ok(c) = state.connected() {
                    if let Ok(settings) = engine::request(&c, "settings", "GET", None) {
                        if let Ok(mut previous) = state.startup_error.lock() {
                            if window::startup_status(&mut previous, window::startup(&settings)) {
                                let _ = handle.emit("startup-status", previous.clone());
                                if !previous.is_empty() {
                                    use std::io::Write;
                                    if let Ok(home) = state.home.lock() {
                                        if let Ok(mut log) = std::fs::OpenOptions::new().create(true).append(true).open(home.join("startup-errors.log")) {
                                            let _ = writeln!(log, "{}", *previous);
                                        }
                                    }
                                }
                            }
                        }
                        if let Some(webview) = handle.get_webview_window("main") {
                            let preferred = settings["theme"].as_str().unwrap_or("system");
                            let changed = state
                                .appearance
                                .lock()
                                .is_ok_and(|value| *value != preferred);
                            if changed && window::theme(&webview, preferred).is_ok() {
                                if let Ok(mut value) = state.appearance.lock() {
                                    *value = preferred.to_owned();
                                }
                            }
                            if let Some(percent) = settings["zoom"]
                                .as_u64()
                                .filter(|v| window::ZOOM.contains(v))
                            {
                                if state.zoom_percent.load(Ordering::SeqCst) != percent
                                    && window::zoom(&webview, percent).is_ok()
                                {
                                    state.zoom_percent.store(percent, Ordering::SeqCst);
                                }
                            }
                        }
                        state
                            .tray_explained
                            .store(settings["tray_explained"] == true, Ordering::SeqCst);
                    }
                    if let Ok(health) = engine::request(&c, "health", "GET", None) {
                        let _ = pause.set_text(if health["paused_all"] == true {
                            "Resume processing"
                        } else {
                            "Pause processing"
                        });
                    }
                    if let Ok(models) = engine::request(&c, "models", "GET", None) {
                        if let Some(models) = models.as_array() {
                            if let Ok(mut urls) = state.publishers.lock() {
                                *urls = models
                                    .iter()
                                    .filter(|m| m["builtin"] == true)
                                    .filter_map(|m| m["publisher_url"].as_str().map(str::to_owned))
                                    .collect();
                            }
                        }
                    }
                }
            });
            Ok(())
        });
    #[cfg(feature = "e2e")]
    let builder = builder.invoke_handler(tauri::generate_handler![
        commands::desktop_command,
        commands::desktop_test
    ]);
    #[cfg(not(feature = "e2e"))]
    let builder = builder.invoke_handler(tauri::generate_handler![commands::desktop_command]);
    let context = tauri::generate_context!();
    #[cfg(feature = "e2e")]
    let context = {
        let mut context = context;
        // Test launches must never hand off to the owner's production instance.
        // The namespace is still shared by every E2E launch, preserving the
        // existing single-instance checks within the test application.
        context.config_mut().identifier.push_str(".e2e");
        context
    };
    let app = builder
        .build(context)
        .expect("Could not initialize VideoEnhancer");
    app.run(|handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            player::close();
        }
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            if !handle.state::<Arc<State>>().quitting.load(Ordering::SeqCst) {
                api.prevent_exit();
            }
        }
    });
}
