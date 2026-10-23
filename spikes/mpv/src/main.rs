mod capture;
mod composition;
mod mpv;
use base64::Engine;
use serde_json::{json, Value};
use std::{
    io::{self, BufRead},
    path::{Path, PathBuf},
    sync::mpsc,
    time::{Duration, Instant},
};
use tao::keyboard::KeyCode as VirtualKeyCode;
use tao::{
    dpi::{LogicalSize, PhysicalPosition, PhysicalSize},
    event::{ElementState, Event, MouseButton, MouseScrollDelta, WindowEvent},
    event_loop::{ControlFlow, EventLoop},
    platform::windows::{WindowBuilderExtWindows, WindowExtWindows},
    window::{Fullscreen, Window, WindowBuilder},
};
use webview2_com::Microsoft::Web::WebView2::Win32::*;
use windows::{
    core::HSTRING,
    Win32::{
        Foundation::{HWND, LPARAM, POINT, RECT, WPARAM},
        UI::{
            HiDpi::GetDpiForWindow,
            Input::KeyboardAndMouse::{GetDoubleClickTime, ReleaseCapture, SetCapture},
            WindowsAndMessaging::*,
        },
    },
};
use wry::{WebContext, WebView, WebViewBuilder, WebViewExtWindows};

struct Host {
    composed: Option<composition::Composition>,
    native: Option<mpv::Mpv>,
    second: Option<mpv::Mpv>,
    preview: Option<mpv::Mpv>,
    media: Vec<ICoreWebView2DevToolsProtocolEventReceiver>,
    view: Option<WebView>,
    overlay: Option<Window>,
    children: Vec<Window>,
}
impl Host {
    fn player(&self) -> Option<&mpv::Mpv> {
        self.native
            .as_ref()
            .or_else(|| self.composed.as_ref().map(|c| &c.mpv))
    }
    unsafe fn eval(&self, script: &str) -> Result<(), Box<dyn std::error::Error>> {
        if let Some(v) = &self.view {
            v.evaluate_script(script)?;
        }
        if let Some(c) = &self.composed {
            c.web.ExecuteScript(&HSTRING::from(script), None)?;
        }
        Ok(())
    }
    unsafe fn command(&self, args: &[&str]) -> Result<(), Box<dyn std::error::Error>> {
        if let Some(p) = self.player() {
            p.command(args)?;
        }
        if let Some(p) = &self.second {
            p.command(args)?;
        }
        Ok(())
    }
    unsafe fn properties(&self) -> Value {
        let mut value = serde_json::Map::new();
        if let Some(p) = self.player() {
            for name in [
                "time-pos",
                "duration",
                "pause",
                "hwdec-current",
                "frame-drop-count",
                "decoder-frame-drop-count",
                "current-vo",
                "video-params",
                "video-out-params",
                "estimated-vf-fps",
                "video-frame-info",
                "seeking",
                "eof-reached",
                "volume",
            ] {
                value.insert(name.into(), json!(p.property(name)));
            }
        }
        if let Some(p) = &self.second {
            value.insert("second-time".into(), json!(p.property("time-pos")));
            value.insert("second-hwdec".into(), json!(p.property("hwdec-current")));
        }
        Value::Object(value)
    }
    fn close_players(&mut self) {
        self.preview.take();
        self.second.take();
        self.native.take();
        self.composed.take();
    }
}

unsafe fn align_overlay(owner: &Window, overlay: &Window) {
    if let Ok(position) = owner.inner_position() {
        let size = owner.inner_size();
        if let Err(error) = SetWindowPos(
            HWND(overlay.hwnd() as _),
            None,
            position.x,
            position.y,
            size.width as i32,
            size.height as i32,
            SWP_NOZORDER | SWP_NOACTIVATE,
        ) {
            eprintln!("overlay alignment: {error}");
        }
    }
}
unsafe fn request(
    v: &Value,
    host: &mut Host,
    window: &Window,
    dll: &Path,
    file: &Path,
    evidence: &Path,
    fullscreen: &mut bool,
) -> Result<Value, Box<dyn std::error::Error>> {
    let hwnd = HWND(window.hwnd() as _);
    match v["op"].as_str().unwrap_or("") {
        "cdp" => {
            let core = if let Some(c) = &host.composed {
                c.web.clone()
            } else {
                host.view.as_ref().ok_or("No webview")?.webview()
            };
            let id = v["id"].clone();
            let handler = webview2_com::CallDevToolsProtocolMethodCompletedHandler::create(
                Box::new(move |status, result| {
                    println!(
                        "{}",
                        json!({"test_result":id,"status":status.err().map(|e|e.to_string()),"result":result})
                    );
                    Ok(())
                }),
            );
            core.CallDevToolsProtocolMethod(
                &HSTRING::from(v["method"].as_str().ok_or("method")?),
                &HSTRING::from(v["params"].to_string()),
                &handler,
            )?;
            Ok(json!(true))
        }
        "media" => {
            let core = host.view.as_ref().ok_or("No webview")?.webview();
            let receiver = core.GetDevToolsProtocolEventReceiver(&HSTRING::from(
                "Media.playerPropertiesChanged",
            ))?;
            let mut token = 0;
            receiver.add_DevToolsProtocolEventReceived(&webview2_com::DevToolsProtocolEventReceivedEventHandler::create(Box::new(move|_,args|{if let Some(args)=args{let mut raw=windows::core::PWSTR::null();args.ParameterObjectAsJson(&mut raw)?;let text=raw.to_string()?;windows::Win32::System::Com::CoTaskMemFree(Some(raw.0.cast()));println!("{}",json!({"event":"media-properties","data":serde_json::from_str::<Value>(&text).unwrap_or(json!(text))}));}Ok(())})),&mut token)?;
            host.media.push(receiver);
            core.CallDevToolsProtocolMethod(
                &HSTRING::from("Media.enable"),
                &HSTRING::from("{}"),
                None,
            )?;
            Ok(json!(true))
        }
        "properties" => Ok(host.properties()),
        "command" => {
            let strings: Vec<_> = v["args"]
                .as_array()
                .ok_or("args missing")?
                .iter()
                .map(|s| s.as_str().ok_or("non-string argument"))
                .collect::<Result<_, _>>()?;
            host.command(&strings)?;
            Ok(json!(true))
        }
        "eval" => {
            host.eval(v["script"].as_str().ok_or("script missing")?)?;
            Ok(json!(true))
        }
        "capture" => {
            let name = v["name"].as_str().ok_or("name missing")?;
            if name.contains(['/', '\\', ':']) || !name.ends_with(".png") {
                return Err("Invalid capture name".into());
            }
            let target = if v["overlay"] == true {
                HWND(host.overlay.as_ref().ok_or("No owned overlay")?.hwnd() as _)
            } else {
                hwnd
            };
            let _ = SetForegroundWindow(target);
            if v["wgc"] == true {
                capture::save_wgc(target, &evidence.join(name))
            } else {
                capture::save(target, &evidence.join(name))
            }
        }
        "state" => {
            let mut rect = RECT::default();
            GetWindowRect(hwnd, &mut rect)?;
            Ok(
                json!({"rect":[rect.left,rect.top,rect.right,rect.bottom],"client_size":[window.inner_size().width,window.inner_size().height],"overlay_visible":host.overlay.as_ref().map(|o|IsWindowVisible(HWND(o.hwnd() as _)).as_bool()),"dpi":GetDpiForWindow(hwnd),"monitors":GetSystemMetrics(SM_CMONITORS),"minimised":IsIconic(hwnd).as_bool(),"maximised":IsZoomed(hwnd).as_bool(),"fullscreen":*fullscreen,"overlay":host.overlay.as_ref().map(|o|{let mut r=RECT::default();let _=GetWindowRect(HWND(o.hwnd() as _),&mut r);[r.left,r.top,r.right,r.bottom]})}),
            )
        }
        "window" => {
            match v["action"].as_str().unwrap_or("") {
                "resize" => {
                    SetWindowPos(
                        hwnd,
                        None,
                        100,
                        100,
                        v["width"].as_i64().unwrap_or(976) as i32,
                        v["height"].as_i64().unwrap_or(579) as i32,
                        SWP_NOZORDER,
                    )?;
                }
                "maximise" => {
                    let _ = ShowWindow(hwnd, SW_MAXIMIZE);
                }
                "minimise" => {
                    let _ = ShowWindow(hwnd, SW_MINIMIZE);
                }
                "restore" => {
                    let _ = ShowWindow(hwnd, SW_RESTORE);
                }
                "fullscreen" => {
                    *fullscreen = !*fullscreen;
                    window.set_fullscreen(if *fullscreen {
                        Some(Fullscreen::Borderless(None))
                    } else {
                        None
                    });
                }
                "dpi" => {
                    let dpi = v["dpi"].as_u64().unwrap_or(96) as usize;
                    let mut rect = RECT::default();
                    GetWindowRect(hwnd, &mut rect)?;
                    let _ = SendMessageW(
                        hwnd,
                        WM_DPICHANGED,
                        Some(WPARAM(dpi | (dpi << 16))),
                        Some(LPARAM((&rect as *const RECT) as isize)),
                    );
                }
                _ => return Err("Unknown window action".into()),
            }
            Ok(json!(true))
        }
        "input" => {
            let target = if v["target"] == "html" {
                host.overlay
                    .as_ref()
                    .map(|o| HWND(o.hwnd() as _))
                    .unwrap_or(hwnd)
            } else {
                hwnd
            };
            let message = v["message"].as_u64().ok_or("message missing")? as u32;
            if ![
                WM_MOUSEMOVE,
                WM_LBUTTONDOWN,
                WM_LBUTTONUP,
                WM_LBUTTONDBLCLK,
                WM_MOUSEWHEEL,
                WM_KEYDOWN,
                WM_KEYUP,
            ]
            .contains(&message)
            {
                return Err("Input message not allowed".into());
            }
            PostMessageW(
                Some(target),
                message,
                WPARAM(v["wparam"].as_u64().unwrap_or(0) as usize),
                LPARAM(v["lparam"].as_i64().unwrap_or(0) as isize),
            )?;
            Ok(json!(true))
        }
        "preview" => {
            if host.preview.is_none() {
                let at = v["time"].as_f64().unwrap_or(0.0).to_string();
                let mut p = mpv::Mpv::configured(
                    dll,
                    None,
                    &[
                        ("hwdec", "no"),
                        ("pause", "yes"),
                        ("audio", "no"),
                        ("start", &at),
                    ],
                )?;
                p.create_sw()?;
                p.command(&["loadfile", file.to_str().ok_or("path")?])?;
                host.preview = Some(p);
                return Ok(json!({"loading":true}));
            }
            let p = host.preview.as_ref().unwrap();
            let at = v["time"].as_f64().unwrap_or(0.0);
            p.command(&["seek", &at.to_string(), "absolute+exact"])?;
            Ok(json!(true))
        }
        "preview-frame" => {
            let p = host.preview.as_ref().ok_or("Preview not started")?;
            let pixels = p.sw_pixels(320, 180)?;
            let png = capture::png_bytes(320, 180, &pixels)?;
            let uri = format!(
                "data:image/png;base64,{}",
                base64::engine::general_purpose::STANDARD.encode(&png)
            );
            host.eval(&format!("document.querySelector('#preview img').src={};hoverTime.value=Number({}).toFixed(2);",json!(uri),json!(p.property("time-pos"))))?;
            Ok(
                json!({"time":p.property("time-pos"),"seeking":p.property("seeking"),"bytes":png.len()}),
            )
        }
        "close-player" => {
            host.eval(
                "if(window.video){video.pause();video.removeAttribute('src');video.load();}",
            )?;
            host.close_players();
            Ok(json!(true))
        }
        _ => Err("Unknown operation".into()),
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    unsafe {
        let args: Vec<_> = std::env::args().collect();
        if args.len() != 5 {
            return Err("Usage: spike B1|B2|HTML5|AB|STACK DLL FILE SCRATCH_PROFILE".into());
        }
        let approach = args[1].clone();
        if !["B1", "B2", "HTML5", "AB", "STACK"].contains(&approach.as_str()) {
            return Err("Unknown approach".into());
        }
        let dll = PathBuf::from(&args[2]).canonicalize()?;
        let file = PathBuf::from(&args[3]).canonicalize()?;
        let profile = PathBuf::from(&args[4]).canonicalize()?;
        let work = dll
            .parent()
            .and_then(|p| p.parent())
            .and_then(|p| p.parent())
            .ok_or("Invalid cache path")?;
        if !profile.starts_with(work.join("scratch")) {
            return Err("Profile must be inside work/scratch".into());
        }
        for (key, folder) in [("APPDATA", "roaming"), ("LOCALAPPDATA", "local")] {
            let isolated = profile.join(folder);
            std::fs::create_dir_all(&isolated)?;
            std::env::set_var(key, isolated);
        }
        let evidence = work.join("evidence/VE-P1e-3b/section13");
        std::fs::create_dir_all(&evidence)?;
        let events = EventLoop::new();
        let window = WindowBuilder::new()
            .with_title(format!("VE-P1e-3b {approach}"))
            .with_inner_size(LogicalSize::new(960., 540.))
            .with_position(PhysicalPosition::new(100, 100))
            .build(&events)?;
        let heartbeat = events.create_proxy();
        std::thread::spawn(move || loop {
            std::thread::sleep(Duration::from_millis(8));
            if heartbeat.send_event(()).is_err() {
                break;
            }
        });
        let hwnd = HWND(window.hwnd() as _);
        let (tx, rx) = mpsc::channel::<String>();
        let mut context = WebContext::new(Some(profile.clone()));
        let mut host = Host {
            composed: None,
            native: None,
            second: None,
            preview: None,
            media: vec![],
            view: None,
            overlay: None,
            children: vec![],
        };
        if approach == "B1" {
            host.composed = Some(composition::Composition::new(
                hwnd,
                &dll,
                &profile,
                tx.clone(),
            )?);
        } else {
            let target = if approach == "HTML5" {
                &window
            } else {
                let owned = WindowBuilder::new()
                    .with_title("VE-P1e-3b HTML overlay")
                    .with_decorations(false)
                    .with_resizable(false)
                    .with_transparent(true)
                    .with_owner_window(window.hwnd())
                    .with_inner_size(window.inner_size())
                    .build(&events)?;
                let position = window.inner_position()?;
                let size = window.inner_size();
                let own = HWND(owned.hwnd() as _);
                if SetWindowLongPtrW(
                    own,
                    GWL_STYLE,
                    (WS_POPUP | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS).0 as isize,
                ) == 0
                {
                    return Err("Overlay style update failed".into());
                }
                SetWindowPos(
                    own,
                    None,
                    position.x,
                    position.y,
                    size.width as i32,
                    size.height as i32,
                    SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
                )?;
                owned.set_outer_position(position);
                host.overlay = Some(owned);
                host.overlay.as_ref().unwrap()
            };
            let sender = tx.clone();
            let builder = WebViewBuilder::new_with_web_context(&mut context)
                .with_transparent(true)
                .with_ipc_handler(move |r| {
                    let _ = sender.send(r.body().clone());
                });
            host.view = Some(if approach == "HTML5" {
                builder
                    .with_url(std::env::var("VE_MPV_HTML_URL")?)
                    .build(target)?
            } else {
                builder
                    .with_html(include_str!("../controls.html"))
                    .build(target)?
            });
            if approach == "AB" {
                for index in 0..2 {
                    let child = WindowBuilder::new()
                        .with_decorations(false)
                        .with_parent_window(window.hwnd())
                        .with_inner_size(PhysicalSize::new(480, 540))
                        .with_position(PhysicalPosition::new(index * 480, 0))
                        .build(&events)?;
                    let p = mpv::Mpv::new(&dll, Some(child.hwnd()))?;
                    if index == 0 {
                        host.native = Some(p)
                    } else {
                        host.second = Some(p)
                    }
                    host.children.push(child);
                }
            } else if approach == "STACK" {
                host.native = Some(mpv::Mpv::configured(
                    &dll,
                    Some(window.hwnd()),
                    &[
                        ("hwdec", "d3d11va-copy"),
                        ("external-files", file.to_str().ok_or("path")?),
                        ("lavfi-complex", "[vid1][vid2]hstack=inputs=2[vo]"),
                    ],
                )?);
            } else if approach != "HTML5" {
                host.native = Some(mpv::Mpv::new(&dll, Some(window.hwnd()))?);
            }
        }
        if std::env::var_os("VE_MPV_SPIKE_TEST").is_some() {
            let sender = tx.clone();
            std::thread::spawn(move || {
                for line in io::stdin().lock().lines() {
                    match line {
                        Ok(line) => {
                            if sender.send(line).is_err() {
                                break;
                            }
                        }
                        Err(_) => break,
                    }
                }
            });
        }
        host.command(&["loadfile", file.to_str().ok_or("path")?])?;
        println!(
            "{}",
            json!({"event":"ready","approach":approach,"pid":std::process::id(),"hwnd":window.hwnd(),"properties":host.properties()})
        );
        let started = Instant::now();
        let autoclose = std::env::var("VE_MPV_SPIKE_AUTOCLOSE_MS")
            .ok()
            .and_then(|s| s.parse::<u64>().ok());
        let mut telemetry = Instant::now();
        let mut last = Instant::now();
        let mut cursor = POINT::default();
        let mut pressed = false;
        let mut fullscreen = false;
        let mut click = Instant::now() - Duration::from_secs(2);
        let mut pending: Option<(Value, Instant)> = None;
        events.run(move |event,_,flow| {
        *flow=ControlFlow::WaitUntil(Instant::now()+Duration::from_millis(2));
        while let Ok(message)=rx.try_recv(){
            let Ok(v)=serde_json::from_str::<Value>(&message) else {continue};
            if v["op"]=="quit" {*flow=ControlFlow::Exit;println!("{}",json!({"reply":v["id"],"result":true}));continue}
            if v["op"]=="await-frame" {pending=Some((v,Instant::now()));continue}
            if v["op"]=="track" {if let Some(p)=host.player(){let _=p.events();} let mut tracked=v.clone();tracked["_before"]=host.player().map(|p|json!(p.property("time-pos"))).unwrap_or(Value::Null);pending=Some((tracked,Instant::now()));let strings:Vec<_>=v["args"].as_array().unwrap().iter().filter_map(|s|s.as_str()).collect();if let Err(e)=host.command(&strings){pending.take();println!("{}",json!({"reply":v["id"],"error":e.to_string()}));}continue}
            if v.get("op").is_some(){let r=request(&v,&mut host,&window,&dll,&file,&evidence,&mut fullscreen);println!("{}",match r{Ok(value)=>json!({"reply":v["id"],"result":value}),Err(e)=>json!({"reply":v["id"],"error":e.to_string()})});continue}
            if v.get("test_result").is_some(){println!("{}",v);continue}
            println!("{}",json!({"event":"input","data":v}));
            match v["command"].as_str().unwrap_or(""){
                "pause"=>{let _=host.command(&["cycle","pause"]);},
                "seek"=>{let _=host.command(&["seek",&v["value"].to_string(),"absolute+exact"]);},
                "relative"=>{let _=host.command(&["seek",&v["value"].to_string(),"relative+exact"]);},
                "volume"=>{let _=host.command(&["add","volume",&v["value"].to_string()]);},
                "fullscreen"=>{fullscreen = !fullscreen;window.set_fullscreen(if fullscreen{Some(Fullscreen::Borderless(None))}else{None});},
                "hover"=>{let _=request(&json!({"op":"preview","time":v["value"]}),&mut host,&window,&dll,&file,&evidence,&mut fullscreen);},
                _=>{}
            }
        }
        match event {
            Event::WindowEvent{window_id,event,..} if window_id==window.id()=>match event {
                WindowEvent::CloseRequested=>*flow=ControlFlow::Exit,
                WindowEvent::Resized(size)=>{
                    if let Some(c)=&host.composed{if let Err(e)=c.resize(size.width,size.height){eprintln!("resize: {e}")}}
                    if let Some(o)=&host.overlay{align_overlay(&window,o);}
                    if let Some(v)=&host.view{let _=v.set_bounds(wry::Rect{position:PhysicalPosition::new(0,0).into(),size:size.into()});}
                    for(i,child)in host.children.iter().enumerate(){child.set_inner_size(PhysicalSize::new(size.width/2,size.height));child.set_outer_position(PhysicalPosition::new(i as i32*size.width as i32/2,0));}
                },
                WindowEvent::Moved(_)|WindowEvent::ScaleFactorChanged{..}=>{if let Some(o)=&host.overlay{align_overlay(&window,o);}println!("{}",json!({"event":"geometry"}));},
                WindowEvent::CursorMoved{position,..}=>{cursor=POINT{x:position.x as _,y:position.y as _};if let Some(c)=&host.composed{let _=c.input.SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_MOVE,if pressed{COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_LEFT_BUTTON}else{COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE},0,cursor);}},
                WindowEvent::MouseInput{state,button:MouseButton::Left,..}=>{pressed=state==ElementState::Pressed;if let Some(c)=&host.composed{let _=c.controller.MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);let kind=if pressed{let _=SetCapture(hwnd);let double=click.elapsed()<Duration::from_millis(GetDoubleClickTime() as u64);click=Instant::now();if double{COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_DOUBLE_CLICK}else{COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_DOWN}}else{let _=ReleaseCapture();COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_UP};let _=c.input.SendMouseInput(kind,if pressed{COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_LEFT_BUTTON}else{COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE},0,cursor);}},
                WindowEvent::KeyboardInput{event:input,..}=>{if let Some(c)=&host.composed{{let code=input.physical_key;let key=match code{VirtualKeyCode::Space=>Some((" ","Space",32)),VirtualKeyCode::KeyF=>Some(("f","KeyF",70)),VirtualKeyCode::ArrowLeft=>Some(("ArrowLeft","ArrowLeft",37)),VirtualKeyCode::ArrowRight=>Some(("ArrowRight","ArrowRight",39)),VirtualKeyCode::Tab=>Some(("Tab","Tab",9)),_=>None};if let Some((key,code,vk))=key{let params=json!({"type":if input.state==ElementState::Pressed{"keyDown"}else{"keyUp"},"key":key,"code":code,"windowsVirtualKeyCode":vk});let _=c.web.CallDevToolsProtocolMethod(&HSTRING::from("Input.dispatchKeyEvent"),&HSTRING::from(params.to_string()),None);}}}},
WindowEvent::MouseWheel{delta,..}=>{if let Some(c)=&host.composed{let y=match delta{MouseScrollDelta::LineDelta(_,y)=>y*120.,MouseScrollDelta::PixelDelta(p)=>p.y as f32,_=>0.};let _=c.input.SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_WHEEL,COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE,y as i32 as u32,cursor);}},
                _=>{}
            },
            Event::WindowEvent{event:WindowEvent::CloseRequested,..}=>*flow=ControlFlow::Exit,
            Event::MainEventsCleared=>{
                if autoclose.is_some_and(|ms|started.elapsed()>=Duration::from_millis(ms)){*flow=ControlFlow::Exit;}
                if let Some(c)=&host.composed {if let Err(e)=c.draw(){eprintln!("draw: {e}")}}
                if let Some(p)=host.player(){for id in p.events(){println!("{}",json!({"event":"mpv-event","kind":id,"elapsed_ms":started.elapsed().as_secs_f64()*1000.}));if id==21 {if let Some((v,t))=pending.take(){println!("{}",json!({"reply":v["id"],"result":{"latency_ms":t.elapsed().as_secs_f64()*1000.,"properties":host.properties()}}));}}}}
                if let Some((v,t))=&pending {let stepping=v["args"][0].as_str().is_some_and(|s|s.starts_with("frame-"));let changed=host.player().is_some_and(|p|json!(p.property("time-pos"))!=v["_before"]);if stepping && changed && t.elapsed()>Duration::from_millis(40){let(v,t)=pending.take().unwrap();println!("{}",json!({"reply":v["id"],"result":{"latency_ms":t.elapsed().as_secs_f64()*1000.,"method":"time-pos change after frame step; capture needed for exactness","properties":host.properties()}}));}}
if let Some(p)=&host.preview{let mut ready=false;for id in p.events(){if id==21{ready=true;}}if ready{let _=request(&json!({"op":"preview-frame"}),&mut host,&window,&dll,&file,&evidence,&mut fullscreen);}}
                if pending.as_ref().is_some_and(|(_,t)|t.elapsed()>Duration::from_secs(15)){let(v,_)=pending.take().unwrap();println!("{}",json!({"reply":v["id"],"error":"playback-restart timeout"}));}
                if telemetry.elapsed()>=Duration::from_secs(1){println!("{}",json!({"event":"telemetry","elapsed_ms":started.elapsed().as_millis(),"properties":host.properties()}));telemetry=Instant::now();}
                if last.elapsed()>Duration::from_millis(100){if approach!="HTML5"{let p=host.properties();let value=json!({"approach":approach,"time":p["time-pos"],"duration":p["duration"],"hwdec":p["hwdec-current"]});let _=host.eval(&format!("window.update && window.update({value})"));}
                if host.preview.is_some(){let _=request(&json!({"op":"preview-frame"}),&mut host,&window,&dll,&file,&evidence,&mut fullscreen);}last=Instant::now();}
            },
            Event::LoopDestroyed=>{host.view.take();host.close_players();},
            _=>{}
        }
    });
    }
}
