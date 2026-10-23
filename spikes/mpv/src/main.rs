mod composition;
mod mpv;
use std::{
    path::PathBuf,
    sync::mpsc,
    time::{Duration, Instant},
};
use tao::{
    dpi::{LogicalSize, PhysicalPosition},
    event::{ElementState, Event, MouseButton, WindowEvent},
    event_loop::{ControlFlow, EventLoop},
    platform::windows::{WindowBuilderExtWindows, WindowExtWindows},
    window::{Fullscreen, WindowBuilder},
};
use webview2_com::Microsoft::Web::WebView2::Win32::*;
use windows::Win32::Foundation::{HWND, POINT};
use wry::{WebContext, WebViewBuilder};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    unsafe {
        let args: Vec<_> = std::env::args().collect();
        if args.len() != 5 {
            return Err("Usage: mpv-embedding-spike B1|B2 DLL FILE SCRATCH_PROFILE".into());
        }
        let approach = args[1].clone();
        if approach != "B1" && approach != "B2" {
            return Err("Choose B1 or B2".into());
        }
        let dll = PathBuf::from(&args[2]).canonicalize()?;
        let file = PathBuf::from(&args[3]).canonicalize()?;
        let profile = PathBuf::from(&args[4]).canonicalize()?;
        let work = dll
            .parent()
            .and_then(|p| p.parent())
            .and_then(|p| p.parent())
            .ok_or("Invalid cache path")?;
        if !profile.is_absolute() || !profile.starts_with(work.join("scratch")) {
            return Err("WebView2 profile must be inside work/scratch".into());
        }
        // Set process-local data roots before native libraries create threads.
        for (key, folder) in [("APPDATA", "roaming"), ("LOCALAPPDATA", "local")] {
            let isolated = profile.join(folder);
            std::fs::create_dir_all(&isolated)?;
            std::env::set_var(key, isolated);
        }
        let events = EventLoop::new();
        let window = WindowBuilder::new()
            .with_title(format!("VE-P1e-3b {approach}"))
            .with_inner_size(LogicalSize::new(960., 540.))
            .build(&events)?;
        let hwnd = HWND(window.hwnd() as _);
        let (tx, rx) = mpsc::channel();
        let mut overlay = None;
        let mut context = WebContext::new(Some(profile.clone()));
        let mut view = None;
        let mut native = None;
        let mut composed = None;
        if approach == "B1" {
            composed = Some(composition::Composition::new(hwnd, &dll, &profile, tx)?);
        } else {
            let owned = WindowBuilder::new()
                .with_title("VE-P1e-3b HTML overlay")
                .with_decorations(false)
                .with_transparent(true)
                .with_owner_window(window.hwnd())
                .with_inner_size(window.inner_size())
                .build(&events)?;
            owned.set_outer_position(window.inner_position()?);
            view = Some(
                WebViewBuilder::new_with_web_context(&mut context)
                    .with_transparent(true)
                    .with_html(include_str!("../controls.html"))
                    .with_ipc_handler(move |request| {
                        let _ = tx.send(request.body().clone());
                    })
                    .build(&owned)?,
            );
            native = Some(mpv::Mpv::new(&dll, Some(window.hwnd()))?);
            overlay = Some(owned);
        }
        let player = || {
            native
                .as_ref()
                .unwrap_or_else(|| &composed.as_ref().unwrap().mpv)
        };
        player().command(&["loadfile", file.to_str().ok_or("Invalid file path")?])?;
        println!(
            "{}",
            serde_json::json!({"event":"ready","approach":approach,"mpv":player().property("mpv-version"),"ffmpeg":player().property("ffmpeg-version")})
        );
        let started = Instant::now();
        let autoclose = std::env::var("VE_MPV_SPIKE_AUTOCLOSE_MS")
            .ok()
            .and_then(|v| v.parse::<u64>().ok());
        let mut last = Instant::now();
        let mut telemetry = Instant::now();
        let mut cursor = POINT::default();
        let mut fullscreen = false;
        events.run(move |event,_,flow| {
        *flow=ControlFlow::WaitUntil(Instant::now()+Duration::from_millis(8));
        let player=native.as_ref().unwrap_or_else(|| &composed.as_ref().unwrap().mpv);
        while let Ok(message)=rx.try_recv() {
            println!("{}",serde_json::json!({"event":"input","message":message}));
            if let Ok(v)=serde_json::from_str::<serde_json::Value>(&message) {
                let result=match v["command"].as_str().unwrap_or("") {
                    "pause"=>player.command(&["cycle","pause"]),
                    "seek"=>player.command(&["seek",&v["value"].to_string(),"absolute+exact"]),
                    "relative"=>player.command(&["seek",&v["value"].to_string(),"relative+exact"]),
                    "volume"=>player.command(&["add","volume",&v["value"].to_string()]),
                    "fullscreen"=>{fullscreen = !fullscreen; window.set_fullscreen(if fullscreen{Some(Fullscreen::Borderless(None))}else{None});Ok(())},
                    _=>Ok(())
                };
                if let Err(e)=result {eprintln!("command: {e}")}
            }
        }
        match event {
            Event::WindowEvent{window_id,event,..} if window_id==window.id()=>match event {
                WindowEvent::CloseRequested=>{*flow=ControlFlow::Exit;},
                WindowEvent::Resized(size)=>{
                    if let Some(c)=&composed {if let Err(e)=c.resize(size.width,size.height){eprintln!("resize: {e}")}}
                    if let Some(o)=&overlay {o.set_inner_size(size); if let Ok(p)=window.inner_position(){o.set_outer_position(p)}}
                    if let Some(v)=&view {let _=v.set_bounds(wry::Rect{position:PhysicalPosition::new(0,0).into(),size:size.into()});}
                },
                WindowEvent::Moved(_)|WindowEvent::ScaleFactorChanged{..}=>{if let Some(o)=&overlay {if let Ok(p)=window.inner_position(){o.set_outer_position(p)} o.set_inner_size(window.inner_size());}},
                WindowEvent::CursorMoved{position,..}=>{cursor=POINT{x:position.x as _,y:position.y as _};if let Some(c)=&composed{let _=c.input.SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_MOVE,COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE,0,cursor);}},
                WindowEvent::MouseInput{state,button:MouseButton::Left,..}=>{if let Some(c)=&composed{let _=c.controller.MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);let _=c.input.SendMouseInput(if state==ElementState::Pressed{COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_DOWN}else{COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_UP},if state==ElementState::Pressed{COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_LEFT_BUTTON}else{COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE},0,cursor);}},
                _=>{}
            },
            Event::WindowEvent{event:WindowEvent::CloseRequested,..}=>*flow=ControlFlow::Exit,
            Event::MainEventsCleared=>{
                if autoclose.is_some_and(|ms|started.elapsed()>=Duration::from_millis(ms)) {*flow=ControlFlow::Exit;}
                if let Some(c)=&composed {if let Err(e)=c.draw(){eprintln!("draw: {e}");*flow=ControlFlow::Exit;}}
                if telemetry.elapsed()>=Duration::from_secs(1) {
                    println!("{}",serde_json::json!({"event":"telemetry","elapsed_ms":started.elapsed().as_millis(),"time":player.property("time-pos"),"hwdec":player.property("hwdec-current"),"vo":player.property("current-vo"),"drops":player.property("frame-drop-count"),"width":player.property("width"),"height":player.property("height")}));
                    telemetry=Instant::now();
                }
                if last.elapsed()>Duration::from_millis(100) {
                    let value=serde_json::json!({"approach":approach,"time":player.property("time-pos"),"duration":player.property("duration"),"hwdec":player.property("hwdec-current")});
                    let script=format!("window.update && window.update({value})");
                    if let Some(v)=&view {let _=v.evaluate_script(&script);}
                    if let Some(c)=&composed {let _=c.web.ExecuteScript(&windows::core::HSTRING::from(script),None);}
                    last=Instant::now();
                }
            },
            Event::LoopDestroyed=>{drop(view.take());drop(composed.take());drop(native.take());},
            _=>{}
        }
    });
    }
}
