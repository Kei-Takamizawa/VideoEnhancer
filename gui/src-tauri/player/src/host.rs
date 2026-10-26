use crate::{composition::Composition, mpv::Mpv};
use base64::Engine;
use serde_json::{json, Value};
use std::{
    collections::{HashMap, VecDeque},
    io::{self, BufRead},
    path::Path,
    sync::mpsc,
    time::{Duration, Instant},
};
use tao::{
    dpi::{PhysicalPosition, PhysicalSize},
    event::{ElementState, Event, MouseButton, MouseScrollDelta, WindowEvent},
    event_loop::{ControlFlow, EventLoop},
    platform::windows::{WindowBuilderExtWindows, WindowExtWindows},
    window::{Fullscreen, WindowBuilder},
};
use videoenhancer_player::{Bootstrap, Command, Hover, Lifecycle, Request};
use webview2_com::Microsoft::Web::WebView2::Win32::*;
use windows::{
    core::HSTRING,
    Win32::{
        Foundation::{HWND, POINT},
        UI::{
            Input::KeyboardAndMouse::{ReleaseCapture, SetCapture},
            WindowsAndMessaging::{GetWindowRect, SetForegroundWindow},
        },
    },
};

include!(concat!(env!("OUT_DIR"), "/assets.rs"));
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

unsafe fn emit(c: &Composition, mut event: Value) {
    event["version"] = json!(1);
    println!("{event}");
    if let Err(error) = c
        .web
        .PostWebMessageAsJson(&HSTRING::from(event.to_string()))
    {
        eprintln!("Player event: {error}");
    }
}
unsafe fn reply(c: &Composition, id: u64, error: Option<&str>) {
    emit(
        c,
        videoenhancer_player::response(
            id,
            error.map_or_else(|| Ok(json!(true)), |error| Err(error.to_owned())),
        ),
    );
}

struct Preview {
    player: Option<Mpv>,
    hover: Hover,
    wanted: Option<(u64, i64)>,
    active: Option<(u64, i64)>,
    cache: VecDeque<(i64, String)>,
}
impl Preview {
    unsafe fn request(
        &mut self,
        generation: u64,
        seconds: f64,
        c: &Composition,
        dll: &Path,
        file: &Path,
        proxy: tao::event_loop::EventLoopProxy<()>,
    ) -> Result<()> {
        if !self.hover.request(generation) {
            return Ok(());
        }
        let key = (seconds * 10.).round() as i64;
        if let Some((_, image)) = self.cache.iter().find(|(k, _)| *k == key) {
            emit(
                c,
                json!({"event":"previewReady","generation":generation,"image":image,"cached":true}),
            );
            self.wanted = None;
            return Ok(());
        }
        self.wanted = Some((generation, key));
        if self.player.is_none() {
            let at = seconds.to_string();
            let mut player = Mpv::configured(
                dll,
                None,
                &[
                    ("hwdec", "no"),
                    ("pause", "yes"),
                    ("audio", "no"),
                    ("hr-seek", "no"),
                    ("vf", "scale=w=320:h=-2"),
                    ("start", &at),
                ],
            )?;
            player.create_sw()?;
            player.callbacks(proxy)?;
            player.command(&["loadfile", file.to_str().ok_or("Invalid media path")?])?;
            self.active = self.wanted;
            self.player = Some(player);
        } else if self.active.is_none() {
            self.seek()?;
        }
        Ok(())
    }
    unsafe fn seek(&mut self) -> Result<()> {
        if let (Some(player), Some(wanted)) = (&self.player, self.wanted) {
            player.command(&[
                "seek",
                &(wanted.1 as f64 / 10.).to_string(),
                "absolute+keyframes",
            ])?;
            self.active = Some(wanted);
        }
        Ok(())
    }
    unsafe fn poll(&mut self, c: &Composition) -> Result<()> {
        let Some(player) = &self.player else {
            return Ok(());
        };
        let ready = player.events().iter().any(|e| e["id"] == 21);
        if player.needs_render()? {
            let _ = player.sw_pixels(320, 180)?;
        }
        if !ready {
            return Ok(());
        }
        if let Some((generation, key)) = self.active.take() {
            if self.hover.current(generation) && self.wanted == Some((generation, key)) {
                let pixels = player.sw_pixels(320, 180)?;
                let mut bytes = Vec::new();
                {
                    let mut encoder = png::Encoder::new(&mut bytes, 320, 180);
                    encoder.set_color(png::ColorType::Rgba);
                    encoder.set_depth(png::BitDepth::Eight);
                    encoder.write_header()?.write_image_data(&pixels)?;
                }
                let image = format!(
                    "data:image/png;base64,{}",
                    base64::engine::general_purpose::STANDARD.encode(bytes)
                );
                emit(
                    c,
                    json!({"event":"previewReady","generation":generation,"image":image,"cached":false}),
                );
                self.cache.push_back((key, image));
                if self.cache.len() > 32 {
                    self.cache.pop_front();
                }
                self.wanted = None;
            }
        }
        self.seek()
    }
}

pub fn run() -> Result<()> {
    let mut line = String::new();
    io::stdin().read_line(&mut line)?;
    if line.len() > 64 * 1024 {
        return Err("Invalid bootstrap".into());
    }
    let boot: Bootstrap = serde_json::from_str(&line)?;
    let file = boot.resolve(&boot.output)?;
    let original = boot.original.as_ref().and_then(|h| boot.resolve(h).ok());
    if !(16..=16384).contains(&boot.video_width) || !(16..=16384).contains(&boot.video_height) {
        return Err("Invalid video size".into());
    }
    std::fs::create_dir_all(&boot.profile)?;
    // The helper's profile is explicitly supplied by the trusted parent.
    for (key, name) in [("APPDATA", "roaming"), ("LOCALAPPDATA", "local")] {
        let path = boot.profile.join(name);
        std::fs::create_dir_all(&path)?;
        std::env::set_var(key, path);
    }
    let dll = std::env::current_exe()?
        .parent()
        .ok_or("Missing player folder")?
        .join("libmpv-2.dll");
    let events = EventLoop::new();
    let window = WindowBuilder::new()
        .with_title("VideoEnhancer Player")
        .with_background_color((0, 0, 0, 255))
        .with_inner_size(PhysicalSize::new(
            boot.width.clamp(320, 7680),
            boot.height.clamp(180, 4320),
        ))
        .with_position(PhysicalPosition::new(boot.x, boot.y))
        .with_owner_window(boot.owner)
        .build(&events)?;
    let hwnd = HWND(window.hwnd() as _);
    if boot.owner != 0 {
        let mut owner = windows::Win32::Foundation::RECT::default();
        let mut own = windows::Win32::Foundation::RECT::default();
        unsafe {
            if GetWindowRect(HWND(boot.owner as _), &mut owner).is_ok()
                && GetWindowRect(hwnd, &mut own).is_ok()
            {
                window.set_outer_position(PhysicalPosition::new(
                    owner.left + (owner.right - owner.left - (own.right - own.left)) / 2,
                    owner.top + (owner.bottom - owner.top - (own.bottom - own.top)) / 2,
                ));
            }
        }
    }
    let (sender, receiver) = mpsc::channel::<String>();
    let proxy = events.create_proxy();
    let mut c = unsafe {
        Composition::new(
            hwnd,
            &dll,
            &boot.profile.join("webview"),
            sender.clone(),
            proxy.clone(),
            (boot.video_width, boot.video_height),
        )?
    };
    unsafe {
        let size = window.inner_size();
        c.resize(size.width, size.height)?;
        c.layout((size.width, size.height), false, false, 0.5, (1., 0., 0.))?;
        c.mpv.callbacks(proxy.clone())?;
        c.controller
            .MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC)?;
        c.mpv.observe()?;
    }
    let closed = sender.clone();
    let wake = proxy.clone();
    std::thread::spawn(move || {
        // Only the trusted parent owns stdin. It can close the helper, but cannot
        // turn the page's command channel into an arbitrary native command API.
        for line in io::stdin().lock().lines() {
            let Ok(line) = line else {
                break;
            };
            if line.len() <= videoenhancer_player::MAX_MESSAGE {
                let _ = closed.send(line);
                let _ = wake.send_event(());
            }
        }
        let _ = closed.send("parent-closed".into());
        let _ = wake.send_event(());
    });
    let mut lifecycle = Lifecycle::default();
    let mut requests = HashMap::<u64, (Instant, bool)>::new();
    let mut steps = HashMap::<u64, (f64, u64)>::new();
    let mut pair_commands = HashMap::<u64, (String, u8)>::new();
    let mut rendered = 0u64;
    let mut click = Instant::now() - Duration::from_secs(2);
    let mut state = json!({"event":"state","position":0,"duration":0,"paused":false,"decoder":""});
    let mut next_state = Instant::now();
    let mut first_frame = false;
    let mut pair = false;
    let mut before = false;
    let mut divider = 0.5f32;
    let mut transform = (1f32, 0f32, 0f32);
    let mut fullscreen = false;
    #[cfg(feature = "test-faults")]
    let mut idle_since: Option<Instant> = None;
    let mut cursor = POINT::default();
    let mut pressed = false;
    let mut preview = Preview {
        player: None,
        hover: Hover::default(),
        wanted: None,
        active: None,
        cache: VecDeque::new(),
    };
    let mut started = Instant::now();
    events.run(move |event, _, flow| unsafe {
        *flow = ControlFlow::WaitUntil(Instant::now() + Duration::from_millis(100));
        let size = window.inner_size();
        for message in receiver.try_iter() {
            if message == "webview-failed" { emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit; break; }
            if message == "parent-closed" { *flow = ControlFlow::Exit; break; }
            let request = match Request::parse(&message) {
                Ok(request) => request,
                Err(error) => {
                    let id = serde_json::from_str::<Value>(&message).ok().and_then(|v| v["id"].as_u64()).unwrap_or(0);
                    reply(&c, id, Some(&error)); continue;
                }
            };
            let id = request.id;
            if requests.contains_key(&id) { reply(&c, id, Some("Duplicate player request.")); continue; }
            let mut native = false;
            let mut waits_frame = false;
            let result = (|| -> Result<()> {
                let mut args: Vec<String> = vec![];
                match request.command {
                    Command::Open { handle } => {
                        let path = boot.resolve(&handle)?;
                        if handle != boot.output { return Err("This handle is not a playable output.".into()); }
                        #[cfg(feature = "test-faults")]
                        { idle_since = None; window.set_visible(true); }
                        lifecycle.open()?; first_frame = false; started = Instant::now();
                        args = vec!["loadfile".into(), path.to_str().ok_or("Invalid media path")?.into()]; waits_frame = true;
                    }
                    Command::Close => {
                        #[cfg(feature = "test-faults")]
                        let idle = std::env::var("VE_PLAYER_TEST_IDLE").as_deref() == Ok("1");
                        #[cfg(not(feature = "test-faults"))]
                        let idle = false;
                        if idle {
                            #[cfg(feature = "test-faults")]
                            { idle_since.get_or_insert_with(Instant::now); window.set_visible(false); }
                            args = vec!["stop".into()];
                        } else { let _ = c.controller.Close(); lifecycle = Lifecycle::Closed; *flow = ControlFlow::Exit; }
                    }
                    Command::Pause { paused } => args = vec!["set".into(), "pause".into(), if paused { "yes" } else { "no" }.into()],
                    Command::Seek { seconds } => { args = vec!["seek".into(), seconds.to_string(), "absolute+exact".into()]; waits_frame = true; }
                    Command::Step { forward } => {
                        if state["paused"] != true { return Err("Pause the video before stepping.".into()); }
                        args = vec![if forward { "frame-step" } else { "frame-back-step" }.into()]; waits_frame = true; steps.insert(id,(state["position"].as_f64().unwrap_or(0.),rendered));
                    }
                    Command::Speed { rate } => args = vec!["set".into(), "speed".into(), rate.to_string()],
                    Command::Volume { percent } => args = vec!["set".into(), "volume".into(), percent.to_string()],
                    Command::Mute { muted } => args = vec!["set".into(), "mute".into(), if muted { "yes" } else { "no" }.into()],
                    Command::Fullscreen { enabled } => { fullscreen = enabled; window.set_fullscreen(if enabled { Some(Fullscreen::Borderless(None)) } else { None }); }
                    Command::Transform { scale, x, y } => { transform = (scale as f32, x as f32, y as f32); }
                    Command::BeforeAfter { enabled } => { if original.is_none() { return Err("Before / After needs the original video.".into()); } before = enabled; if enabled && !pair { if !pair_commands.is_empty() { return Err("Before / After is still loading.".into()); } let path = original.as_deref().ok_or("Original missing")?; let graph = c.enable_pair(path)?; args = vec!["video-add".into(), path.to_str().ok_or("Invalid original path")?.into(), "auto".into()]; waits_frame = true; pair_commands.insert(id, (graph, 0)); } }
                    Command::Divider { fraction } => divider = fraction as f32,
                    Command::Preview { seconds, generation } => { preview.request(generation, seconds, &c, &dll, &file, proxy.clone())?; }
                }
                if !args.is_empty() {
                    let args: Vec<_> = args.iter().map(String::as_str).collect();
                    c.mpv.command_id(id, &args)?; native = true;
                }
                c.layout((size.width, size.height), pair, before, divider, transform)?;
                Ok(())
            })();
            match result {
                Err(error) => { eprintln!("Player request {id}: {error}"); reply(&c,id,Some("The player could not complete this action. Close it and try again.")); },
                Ok(()) if native => { requests.insert(id, (Instant::now(), waits_frame)); }
                Ok(()) => reply(&c, id, None),
            }
        }
        match event {
            Event::WindowEvent { window_id, event, .. } if window_id == window.id() => match event {
                WindowEvent::CloseRequested => { let _ = c.controller.Close(); *flow = ControlFlow::Exit; },
                WindowEvent::Resized(size) => {
                    if let Err(error) = c.resize(size.width, size.height).and_then(|_| c.layout((size.width, size.height), pair, before, divider, transform)) {
                        eprintln!("Player resize: {error}"); emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit;
                    }
                }
                WindowEvent::Moved(_) | WindowEvent::ScaleFactorChanged { .. } => { let _ = c.controller.NotifyParentWindowPositionChanged(); },
                WindowEvent::CursorMoved { position, .. } => {
                    cursor = POINT { x: position.x as _, y: position.y as _ };
                    let _ = c.input.SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_MOVE, if pressed { COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_LEFT_BUTTON } else { COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE }, 0, cursor);
                }
                WindowEvent::MouseInput { state, button: MouseButton::Left, .. } => {
                    pressed = state == ElementState::Pressed;
                    let _ = c.controller.MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);
                    let kind = if pressed { let _ = SetCapture(hwnd); let double = click.elapsed() < Duration::from_millis(windows::Win32::UI::Input::KeyboardAndMouse::GetDoubleClickTime() as u64); click = Instant::now(); if double { COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_DOUBLE_CLICK } else { COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_DOWN } } else { let _ = ReleaseCapture(); COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_UP };
                    let _ = c.input.SendMouseInput(kind, if pressed { COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_LEFT_BUTTON } else { COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE }, 0, cursor);
                }
                WindowEvent::MouseWheel { delta, .. } => {
                    let (x, y) = match delta { MouseScrollDelta::LineDelta(x,y) => (x*120.,y*120.), MouseScrollDelta::PixelDelta(p) => (p.x as f32,p.y as f32), _ => (0.,0.) };
                    if y != 0. { let _ = c.input.SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_WHEEL, if windows::Win32::UI::Input::KeyboardAndMouse::GetKeyState(0x11) < 0 { COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_CONTROL } else { COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE }, y as i32 as u32, cursor); }
                    if x != 0. { let _ = c.input.SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_HORIZONTAL_WHEEL, COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE, x as i32 as u32, cursor); }
                }
                _ => {}
            },
            Event::MainEventsCleared => {
                #[cfg(feature = "test-faults")]
                if idle_since.is_some_and(|at| at.elapsed() >= Duration::from_secs(29)) { let _ = c.controller.Close(); *flow = ControlFlow::Exit; }
                match c.mpv.needs_render().and_then(|dirty| if dirty { rendered += 1; c.draw() } else { Ok(()) }) {
                    Ok(()) => {}
                    Err(error) => { eprintln!("Player device/render: {error}"); emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit; }
                }
                for event in c.mpv.events() {
                    let kind = event["id"].as_i64().unwrap_or(0);
                    if kind == 22 {
                        let value = event["value"].as_str().unwrap_or("");
                        match event["name"].as_str().unwrap_or("") {
                            "time-pos" => { if let Ok(n) = value.parse::<f64>() { state["position"] = json!(n); } }
                            "duration" => { if let Ok(n) = value.parse::<f64>() { state["duration"] = json!(n); } }
                            "pause" => state["paused"] = json!(value == "yes"),
                            "hwdec-current" => state["decoder"] = json!(value),
                            "frame-drop-count" => state["dropped"] = json!(value),
                            "eof-reached" if value == "yes" => emit(&c, json!({"event":"eof"})),
                            _ => {}
                        }
                    }
                    if kind == 5 {
                        let id = event["reply"].as_u64().unwrap_or(0);
                        if event["error"].as_i64().unwrap_or(0) < 0 { requests.remove(&id); steps.remove(&id); pair_commands.remove(&id); reply(&c, id, Some("The player could not complete this action.")); }
                        else if let Some((graph, stage)) = pair_commands.get_mut(&id) {
                            // Each asynchronous command must finish before the graph can use vid2.
                            let result = if *stage == 0 {
                                *stage = 1;
                                c.mpv.command_id(id, &["set", "hwdec", "d3d11va-copy"])
                            } else {
                                c.mpv.command_id(id, &["set", "lavfi-complex", graph])
                            };
                            if result.is_err() { pair_commands.remove(&id); requests.remove(&id); reply(&c,id,Some("Before / After could not load.")); }
                            else if *stage == 2 { pair_commands.remove(&id); pair = true; let _ = c.layout((size.width,size.height),pair,before,divider,transform); }
                            else { *stage = 2; }
                        }
                        else if requests.get(&id).is_some_and(|(_, frame)| !frame) { requests.remove(&id); reply(&c, id, None); }
                    }
                    if kind == 21 {
                        if !first_frame {
                            first_frame = true; let _ = lifecycle.loaded();
                            emit(&c, json!({"event":"loaded","title":boot.title,"original":original.is_some(),"first_frame_ms":started.elapsed().as_secs_f64()*1000.,"hwnd":window.hwnd()}));
                        }
                        let ready: Vec<_> = requests.iter().filter(|(id, (_, frame))| *frame && !steps.contains_key(id) && !pair_commands.contains_key(id)).map(|(id, _)| *id).collect();
                        for id in ready { if let Some((at, _)) = requests.remove(&id) { emit(&c, json!({"reply":id,"result":{"latency_ms":at.elapsed().as_secs_f64()*1000.}})); } }
                    }
                    if kind == 7 && event["reason"] == 4 { emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit; }
                }
                let finished_steps: Vec<_> = steps.iter().filter(|(_, (before, serial))| rendered > *serial && state["position"].as_f64().is_some_and(|now| (now-*before).abs()>0.00001)).map(|(id,_)| *id).collect();
                for id in finished_steps { steps.remove(&id); if let Some((at,_))=requests.remove(&id) { emit(&c,json!({"reply":id,"result":{"latency_ms":at.elapsed().as_secs_f64()*1000.},"event":"stepDone"})); } }
                let timed_out: Vec<_> = requests.iter().filter(|(_, (at, _))| at.elapsed() > Duration::from_secs(10)).map(|(id, _)| *id).collect();
                for id in timed_out { requests.remove(&id); steps.remove(&id); pair_commands.remove(&id); reply(&c, id, Some("The player did not respond.")); }
                if !first_frame && started.elapsed() > Duration::from_secs(12) { emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit; }
                if next_state.elapsed() >= Duration::from_millis(100) { emit(&c, state.clone()); next_state = Instant::now(); }
                if let Err(error) = preview.poll(&c) { eprintln!("Hover preview: {error}"); }
            }
            Event::LoopDestroyed => {
                println!("{}", json!({"version":1,"event":"closed"}));
                let mut owner = windows::Win32::Foundation::RECT::default();
                if GetWindowRect(HWND(boot.owner as _), &mut owner).is_ok() { let _ = SetForegroundWindow(HWND(boot.owner as _)); }
            }
            _ => {}
        }
    });
}
