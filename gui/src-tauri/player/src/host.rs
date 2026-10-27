use crate::{composition::Composition, mpv::Mpv};
use base64::Engine;
use serde_json::{json, Value};
use std::{
    collections::{HashMap, HashSet, VecDeque},
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
        let (width, height) = c.preview_size();
        let ready = player.events().iter().any(|e| e["id"] == 21);
        if player.needs_render()? {
            let _ = player.sw_pixels(width, height)?;
        }
        if !ready {
            return Ok(());
        }
        if let Some((generation, key)) = self.active.take() {
            if self.hover.current(generation) && self.wanted == Some((generation, key)) {
                let pixels = player.sw_pixels(width, height)?;
                let mut bytes = Vec::new();
                {
                    let mut encoder = png::Encoder::new(&mut bytes, width as u32, height as u32);
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
    let process_started = Instant::now();
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
    if boot.original_width > 16384 || boot.original_height > 16384 {
        return Err("Invalid original size".into());
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
    let window_started = Instant::now();
    let window = WindowBuilder::new()
        .with_title("VideoEnhancer Player")
        .with_visible(!boot.prewarm)
        .with_background_color((0, 0, 0, 255))
        .with_inner_size(PhysicalSize::new(
            boot.width.clamp(320, 7680),
            boot.height.clamp(180, 4320),
        ))
        .with_position(PhysicalPosition::new(boot.x, boot.y))
        .with_owner_window(boot.owner)
        .build(&events)?;
    let hwnd = HWND(window.hwnd() as _);
    if let Ok(poster) = boot.resolve("poster") {
        if let Err(error) = unsafe { crate::startup::poster(hwnd, &poster) } {
            eprintln!("Poster: {error}");
        } else {
            println!(
                "{}",
                json!({"version":1,"event":"poster","hwnd":window.hwnd(),"elapsed_ms":process_started.elapsed().as_secs_f64()*1000.})
            );
        }
    }
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
    let window_ms = window_started.elapsed().as_secs_f64() * 1000.;
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
            &boot,
        )?
    };
    unsafe {
        let size = window.inner_size();
        c.resize(size.width, size.height)?;
        c.layout((size.width, size.height), false, false, 0.5, (1., 0., 0.))?;

        c.controller
            .MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC)?;
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
    println!(
        "{}",
        json!({"version":1,"event":"startupProfile","window_ms":window_ms,"phases":c.profile,"total_ms":process_started.elapsed().as_secs_f64()*1000.})
    );
    let mut lifecycle = Lifecycle::default();
    #[cfg(feature = "test-faults")]
    let mut divider_metrics: Vec<(u64, f64, f64, f64, f64)> = Vec::new();
    let mut requests = HashMap::<u64, (Instant, bool)>::new();
    let mut native_ack = HashSet::<u64>::new();
    let mut restarted = HashSet::<u64>::new();
    let mut seek_targets = HashMap::<u64, f64>::new();
    let mut steps = HashMap::<u64, (f64, u64)>::new();

    let mut rendered = 0u64;
    let mut click = Instant::now() - Duration::from_secs(2);
    let mut state = c.initial_state.clone();
    let mut next_state = Instant::now();
    let mut first_frame = !boot.prewarm;
    let mut playback_restarted = false;
    let mut activated = !boot.prewarm;
    let mut attached = false;
    let mut pair = false;
    let mut before = false;
    let mut divider = 0.5f32;
    let mut playback_rate = 1.;
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
    if boot.prewarm {
        println!(
            "{}",
            json!({"version":1,"event":"ready","hwnd":window.hwnd()})
        );
    }
    events.run(move |event, _, flow| unsafe {
        *flow = ControlFlow::WaitUntil(Instant::now() + Duration::from_millis(100));
        let size = window.inner_size();
        for message in receiver.try_iter() {
            if message == "webview-failed" { emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit; break; }
            if message == "parent-activate" && !activated {
                activated=true;window.set_visible(true);let _=SetForegroundWindow(hwnd);started=Instant::now();first_frame=false;playback_restarted=false;lifecycle=Lifecycle::Opening;
                if let Ok(path)=boot.resolve("poster") {if let Ok(bytes)=std::fs::read(path) {emit(&c,json!({"event":"poster","image":format!("data:image/jpeg;base64,{}",base64::engine::general_purpose::STANDARD.encode(bytes))}));}}
                if let Some(path)=file.to_str() {if c.mpv.command(&["loadfile",path]).is_err() {emit(&c,json!({"event":"error"}));*flow=ControlFlow::Exit;}}
                continue;
            }
            if message == "parent-closed" { *flow = ControlFlow::Exit; break; }
            #[cfg(feature = "test-faults")]
            let (received, message) = crate::telemetry::receipt(&message);
            let request = match Request::parse(&message) {
                Ok(request) => request,
                Err(error) => {
                    let id = serde_json::from_str::<Value>(&message).ok().and_then(|v| v["id"].as_u64()).unwrap_or(0);
                    reply(&c, id, Some(&error)); continue;
                }
            };
            let id = request.id;
            if requests.contains_key(&id) { reply(&c, id, Some("Duplicate player request.")); continue; }
            #[cfg(feature = "test-faults")]
            let mut completed = false;
            #[cfg(not(feature = "test-faults"))]
            let completed = false;
            #[cfg(feature = "test-faults")]
            let mut input_metric = None;
            let mut native = false;
            let mut waits_frame = false;
            let result = (|| -> Result<()> {
                let mut args: Vec<String> = vec![];
                match request.command {
                    #[cfg(feature = "test-faults")]
                    Command::TestClock => { emit(&c,json!({"reply":id,"result":{"qpc_ms":crate::telemetry::qpc()}})); completed=true; }
                    #[cfg(feature = "test-faults")]
                    Command::TestReport { result } => { emit(&c,json!({"event":"dividerBenchmark","result":result})); completed=true; }
                    #[cfg(feature = "test-faults")]
                    Command::SelfCapture { name } => {
                        let path=boot.profile.join(format!("{name}.png"));
                        let value=crate::capture::save_wgc(hwnd,&path)?;
                        emit(&c,json!({"reply":id,"result":value})); completed=true;
                    }
                    #[cfg(feature = "test-faults")]
                    Command::TestUi { action } => {
                        let script=match action.as_str() {
                         "clean"=>"document.querySelector('.controls').style.visibility='hidden';document.querySelector('header').style.visibility='hidden'",
                         "benchmark"=>include_str!("benchmark.js"),
                         "inspect"=>include_str!("layout-inspect.js"),
                         "leavePreview"=>"document.querySelector('[aria-label=Seek]').dispatchEvent(new PointerEvent('pointerout',{bubbles:true,relatedTarget:document.querySelector('header')}))",
                         "mockupLeave"=>"document.querySelector('#seek').dispatchEvent(new PointerEvent('pointerleave',{bubbles:true}))",
                         "zoom"=>"document.querySelector('main').dispatchEvent(new WheelEvent('wheel',{ctrlKey:true,deltaY:-100,bubbles:true,cancelable:true}))",
                         "mockupZoom"=>"document.querySelector('#area').dispatchEvent(new WheelEvent('wheel',{ctrlKey:true,deltaY:-100,bubbles:true,cancelable:true}))",
                         "portrait"=>{window.set_inner_size(PhysicalSize::new(540,960));"void 0"},
                         "mockupPortrait"=>"document.querySelector('#segP').click();document.querySelector('.player').classList.add('fakefs')",
                         "mockupPlay"=>"document.querySelector('#playBtn').click()",
                         "mockupHover"=>"(()=>{const e=document.querySelector('#seek'),r=e.getBoundingClientRect();e.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:r.x+r.width*.4,clientY:r.y+4}));})()",
                         "mockupBefore"=>"document.querySelector('#baBtn').click()",
                         "mockup"=>"document.querySelector('#segL').click();document.querySelector('.player').classList.add('fakefs')",
                         "letterbox"=>{window.set_inner_size(PhysicalSize::new(960,if size.height==640 {540}else{640}));"void 0"},
                         "show" => {let _=c.input.SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_MOVE,COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE,0,POINT{x:450,y:300});"document.querySelector('.controls').style.visibility='';document.querySelector('header').style.visibility='';document.querySelector('main').dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:450,clientY:300}))"},
                         "blur" => "document.activeElement.blur()",
                         "preview" => "(()=>{const e=document.querySelector('[aria-label=Seek]'),r=e.getBoundingClientRect();e.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:r.x+r.width*.4,clientY:r.y+4}));})()",
                         "help"=>"document.querySelector('[aria-label=\"Keyboard shortcuts\"]').click()",
                         "details"=>"document.querySelector('[aria-label=Details]').click()",
                         "speed"=>"document.querySelector('[aria-label=\"Playback speed\"]').click()",
                         "before"=>"document.querySelector('[aria-label=\"Before / After\"]').click()",
                         _=>return Err("Unsupported self-test action".into())};
                        c.web.ExecuteScript(&HSTRING::from(script),None)?;
                    }
                    Command::Open { handle } => {
                        let path = boot.resolve(&handle)?;
                        if handle != boot.output { return Err("This handle is not a playable output.".into()); }
                        #[cfg(feature = "test-faults")]
                        { idle_since = None; window.set_visible(true); }
                        if !attached { attached=true; if !boot.prewarm {lifecycle.open()?;lifecycle.loaded()?;} emit(&c,json!({"event":"configured","title":boot.title,"original":original.is_some(),"video_width":boot.video_width,"video_height":boot.video_height,"hwnd":window.hwnd()})); return Ok(()); }
                        lifecycle.open()?; first_frame = false; playback_restarted=false; started = Instant::now();seek_targets.insert(id,0.);
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
                    Command::Pause { paused } => {if let Some(follower)=&mut c.follower {follower.set_paused(paused)?;} args = vec!["set".into(), "pause".into(), if paused { "yes" } else { "no" }.into()];},
                    Command::Seek { seconds } => { if let Some(f)=&mut c.follower {f.exact(seconds,state["paused"]==true)?;} seek_targets.insert(id,seconds); args = vec!["seek".into(), seconds.to_string(), "absolute+exact".into()]; waits_frame = true; }
                    Command::Step { forward } => {
                        if state["paused"] != true { return Err("Pause the video before stepping.".into()); }
                        args = vec![if forward { "frame-step" } else { "frame-back-step" }.into()]; waits_frame = true; steps.insert(id,(state["position"].as_f64().unwrap_or(0.),rendered));
                    }
                    Command::Speed { rate } => {playback_rate=rate;if let Some(f)=&mut c.follower {f.set_speed(rate)?;}args = vec!["set".into(), "speed".into(), rate.to_string()];},
                    Command::Volume { percent } => args = vec!["set".into(), "volume".into(), percent.to_string()],
                    Command::Mute { muted } => args = vec!["set".into(), "mute".into(), if muted { "yes" } else { "no" }.into()],
                    Command::Fullscreen { enabled } => { fullscreen = enabled; window.set_fullscreen(if enabled { Some(Fullscreen::Borderless(None)) } else { None }); }
                    Command::Transform { scale, x, y } => { transform = (scale as f32, x as f32, y as f32); }
                    Command::BeforeAfter { enabled } => { if original.is_none() { return Err("Before / After needs the original video.".into()); } before = enabled; if enabled && !pair { c.enable_pair(original.as_deref().ok_or("Original missing")?,proxy.clone(),state["position"].as_f64().unwrap_or(0.),state["paused"]==true)?; if let Some(f)=&mut c.follower {f.set_speed(playback_rate)?;}pair=true; } }
                    Command::Divider { fraction, #[cfg(feature = "test-faults")] input_ms } => {
                        divider = fraction as f32;
                        #[cfg(feature = "test-faults")] { input_metric=input_ms; }
                    },
                    Command::Preview { seconds, generation } => { preview.request(generation, seconds, &c, &dll, &file, proxy.clone())?; }
                }
                if !args.is_empty() {
                    let args: Vec<_> = args.iter().map(String::as_str).collect();
                    c.mpv.command_id(id, &args)?; native = true;
                }
                #[cfg(feature = "test-faults")]
                let commit_begin=crate::telemetry::qpc();
                c.layout((size.width, size.height), pair, before, divider, transform)?;
                #[cfg(feature = "test-faults")]
                if let Some(input)=input_metric {
                    let metric=(id,input,received,commit_begin,crate::telemetry::qpc());
                    if let Some(packet)=crate::telemetry::sample(&c,&metric) {emit(&c,packet);} else {divider_metrics.push(metric);}
                    completed=true;
                }
                Ok(())
            })();
            match result {
                Err(error) => { eprintln!("Player request {id}: {error}"); reply(&c,id,Some("The player could not complete this action. Close it and try again.")); },
                Ok(()) if completed => {},
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
                divider_metrics.retain(|metric| {
                    if let Some(packet)=crate::telemetry::sample(&c,metric) {emit(&c,packet);return false;}
                    if crate::telemetry::qpc()-metric.4>2000. {reply(&c,metric.0,Some("Frame statistics did not advance."));return false;} true
                });
                if !activated && process_started.elapsed()>=Duration::from_secs(30) {*flow=ControlFlow::Exit;}

                #[cfg(feature = "test-faults")]
                if idle_since.is_some_and(|at| at.elapsed() >= Duration::from_secs(29)) { let _ = c.controller.Close(); *flow = ControlFlow::Exit; }
                let rendered_before=rendered;
                match c.mpv.needs_render().and_then(|dirty| if dirty { rendered += 1; c.draw() } else { Ok(()) }) {
                    Ok(()) => {if !first_frame && playback_restarted && activated && rendered>rendered_before {
                        first_frame=true;let _=lifecycle.loaded();emit(&c,json!({"event":"loaded","title":boot.title,"original":original.is_some(),"first_frame_ms":started.elapsed().as_secs_f64()*1000.,"hwnd":window.hwnd(),"method":"render/present after playback restart"}));
                    }}
                    Err(error) => { eprintln!("Player device/render: {error}"); emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit; }
                }
                for event in c.mpv.events() {
                    let kind = event["id"].as_i64().unwrap_or(0);
                    if kind == 22 {
                        let value = event["value"].as_str().unwrap_or("");
                        match event["name"].as_str().unwrap_or("") {
                            "time-pos" => { if let Some(n) = event["value"].as_f64().or_else(||value.parse::<f64>().ok()) { state["position"] = json!(n); } }
                            "duration" => { if let Some(n) = event["value"].as_f64().or_else(||value.parse::<f64>().ok()) { state["duration"] = json!(n); } }
                            "pause" => state["paused"] = json!(value == "yes"),
                            "hwdec-current" => state["decoder"] = json!(value),
                            "frame-drop-count" => state["dropped"] = json!(value),
                            "eof-reached" if value == "yes" => emit(&c, json!({"event":"eof"})),
                            _ => {}
                        }
                    }
                    if kind == 5 {
                        let id = event["reply"].as_u64().unwrap_or(0);
                        if requests.get(&id).is_some_and(|(_,frame)|*frame) && event["error"].as_i64().unwrap_or(0)>=0 {native_ack.insert(id);}
                        if event["error"].as_i64().unwrap_or(0) < 0 { native_ack.remove(&id); restarted.remove(&id); seek_targets.remove(&id); requests.remove(&id); steps.remove(&id); reply(&c, id, Some("The player could not complete this action.")); }
                        else if requests.get(&id).is_some_and(|(_, frame)| !frame) { requests.remove(&id); reply(&c, id, None); }
                    }
                    if kind == 21 {
                        for (id,(_,frame)) in &requests {if *frame && native_ack.contains(id) && seek_targets.get(id).is_none_or(|target|(state["position"].as_f64().unwrap_or(0.)-target).abs()<0.1) {restarted.insert(*id);}}

                        playback_restarted=true;
                        let ready: Vec<_> = requests.iter().filter(|(id, (_, frame))| *frame && native_ack.contains(id) && seek_targets.get(id).is_none_or(|target| (state["position"].as_f64().unwrap_or(0.)-target).abs()<0.1) && !steps.contains_key(id) && c.follower.as_ref().is_none_or(|f|f.aligned(state["position"].as_f64().unwrap_or(0.),state["paused"]==true))).map(|(id, _)| *id).collect();
                        for id in ready { if let Some((at, _)) = requests.remove(&id) { emit(&c, json!({"reply":id,"result":{"latency_ms":at.elapsed().as_secs_f64()*1000.}})); } }
                    }
                    if kind == 7 && event["reason"] == 4 { emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit; }
                }
                if let Some(follower)=&mut c.follower {
                    if let Err(error)=follower.poll().and_then(|_|follower.synchronize(state["position"].as_f64().unwrap_or(0.),state["paused"]==true)) {eprintln!("Original: {error}");emit(&c,json!({"event":"error"}));*flow=ControlFlow::Exit;}
                    if let Some(follower)=&c.follower {state["original_position"]=json!(follower.position);state["original_decoder"]=json!(follower.decoder);state["original_dropped"]=json!(follower.dropped);}
                }
                if c.follower.as_ref().is_some_and(|f|f.aligned(state["position"].as_f64().unwrap_or(0.),state["paused"]==true)) {
                    let ready:Vec<_>=requests.iter().filter(|(id,(_,frame))|*frame && native_ack.contains(id) && restarted.contains(id) && !steps.contains_key(id)).map(|(id,_)|*id).collect();
                    for id in ready {if let Some((at,_))=requests.remove(&id) {emit(&c,json!({"reply":id,"result":{"latency_ms":at.elapsed().as_secs_f64()*1000.}}));}}
                }
                let finished_steps: Vec<_> = steps.iter().filter(|(id, (before, serial))| native_ack.contains(id) && c.follower.as_ref().is_none_or(|f| f.aligned(state["position"].as_f64().unwrap_or(0.),state["paused"]==true)) && rendered > *serial && state["position"].as_f64().is_some_and(|now| (now-*before).abs()>0.00001)).map(|(id,_)| *id).collect();
                for id in finished_steps { steps.remove(&id); if let Some((at,_))=requests.remove(&id) { emit(&c,json!({"reply":id,"result":{"latency_ms":at.elapsed().as_secs_f64()*1000.},"event":"stepDone","target_seconds":state["position"],"original_target_seconds":c.follower.as_ref().map(|f|f.target)})); } }
                let timed_out: Vec<_> = requests.iter().filter(|(_, (at, _))| at.elapsed() > Duration::from_secs(10)).map(|(id, _)| *id).collect();
                for id in timed_out { requests.remove(&id); steps.remove(&id); reply(&c, id, Some("The player did not respond.")); }
                if activated && !first_frame && started.elapsed() > Duration::from_secs(12) { emit(&c, json!({"event":"error"})); *flow = ControlFlow::Exit; }
                native_ack.retain(|id|requests.contains_key(id));restarted.retain(|id|requests.contains_key(id));seek_targets.retain(|id,_|requests.contains_key(id));
                if next_state.elapsed() >= Duration::from_millis(100) { emit(&c, state.clone()); next_state = Instant::now(); }
                if let Err(error) = preview.poll(&c) { eprintln!("Hover preview: {error}"); }
            }
            Event::LoopDestroyed => {
                #[cfg(feature="test-faults")]
                crate::capture::shutdown();
                println!("{}", json!({"version":1,"event":"closed"}));
                let mut owner = windows::Win32::Foundation::RECT::default();
                if GetWindowRect(HWND(boot.owner as _), &mut owner).is_ok() { let _ = SetForegroundWindow(HWND(boot.owner as _)); }
            }
            _ => {}
        }
    });
}
