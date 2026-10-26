use crate::mpv::Mpv;
use std::{path::Path, sync::mpsc};
use webview2_com::{
    CreateCoreWebView2CompositionControllerCompletedHandler,
    CreateCoreWebView2EnvironmentCompletedHandler, CursorChangedEventHandler,
    Microsoft::Web::WebView2::Win32::*, NavigationCompletedEventHandler,
    NavigationStartingEventHandler, NewWindowRequestedEventHandler, ProcessFailedEventHandler,
    WebMessageReceivedEventHandler, WebResourceRequestedEventHandler,
};
use windows::{
    core::{Interface, HSTRING, PCWSTR},
    Win32::{
        Foundation::{HWND, RECT},
        Graphics::{
            Direct3D::D3D_DRIVER_TYPE_HARDWARE,
            Direct3D11::*,
            DirectComposition::*,
            Dxgi::{Common::*, *},
        },
        UI::Shell::SHCreateMemStream,
    },
};

pub struct Composition {
    pub follower: Option<crate::follower::Follower>,
    d3d: ID3D11Device,
    dll: std::path::PathBuf,
    pub initial_state: serde_json::Value,
    pub profile: serde_json::Value,
    pub mpv: Mpv,
    pub web: ICoreWebView2,
    pub controller: ICoreWebView2Controller,
    pub input: ICoreWebView2CompositionController,
    swap: IDXGISwapChain1,
    device: IDCompositionDevice,
    // Keep the whole composition tree alive for the lifetime of the controller.
    _target: IDCompositionTarget,
    _root: IDCompositionVisual,
    _video: IDCompositionVisual,
    before: IDCompositionVisual,
    _html: IDCompositionVisual,
    video_size: (u32, u32),
    original_size: (u32, u32),
}
impl Composition {
    pub unsafe fn new(
        hwnd: HWND,
        dll: &Path,
        profile: &Path,
        events: mpsc::Sender<String>,
        proxy: tao::event_loop::EventLoopProxy<()>,
        video_size: (u32, u32),
        boot: &videoenhancer_player::Bootstrap,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        #[cfg(feature = "test-faults")]
        if std::env::var("VE_PLAYER_TEST_FAIL_D3D").as_deref() == Ok("1") {
            return Err("Simulated D3D11 device creation failure (test build only).".into());
        }
        let native_started = std::time::Instant::now();
        let prepared = crate::startup::prepare(dll.to_owned());
        let mut d3d = None;
        D3D11CreateDevice(
            None,
            D3D_DRIVER_TYPE_HARDWARE,
            Default::default(),
            D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            None,
            D3D11_SDK_VERSION,
            Some(&mut d3d),
            None,
            None,
        )?;
        let d3d = d3d.ok_or("D3D11 device missing")?;
        let dxgi: IDXGIDevice = d3d.cast()?;
        let factory: IDXGIFactory2 = dxgi.GetAdapter()?.GetParent()?;
        let swap = factory.CreateSwapChainForComposition(
            &d3d,
            &DXGI_SWAP_CHAIN_DESC1 {
                Width: video_size.0,
                Height: video_size.1,
                Format: DXGI_FORMAT_B8G8R8A8_UNORM,
                SampleDesc: DXGI_SAMPLE_DESC {
                    Count: 1,
                    Quality: 0,
                },
                BufferUsage: DXGI_USAGE_RENDER_TARGET_OUTPUT,
                BufferCount: 2,
                Scaling: DXGI_SCALING_STRETCH,
                SwapEffect: DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL,
                AlphaMode: DXGI_ALPHA_MODE_IGNORE,
                Flags: 0,
                ..Default::default()
            },
            None,
        )?;
        let device: IDCompositionDevice = DCompositionCreateDevice(&dxgi)?;
        let target = device.CreateTargetForHwnd(hwnd, true)?;
        let root = device.CreateVisual()?;
        let video = device.CreateVisual()?;
        video.SetContent(&swap)?;
        let before = device.CreateVisual()?;
        before.SetContent(&swap)?;
        let html = device.CreateVisual()?;
        root.AddVisual(&video, false, None)?;
        root.AddVisual(&before, true, &video)?;
        root.AddVisual(&html, true, &before)?;
        target.SetRoot(&root)?;
        let mut rect = RECT::default();
        windows::Win32::UI::WindowsAndMessaging::GetClientRect(hwnd, &mut rect)?;
        let fit =
            (rect.right as f32 / video_size.0 as f32).min(rect.bottom as f32 / video_size.1 as f32);
        let scale = device.CreateScaleTransform()?;
        scale.SetScaleX2(fit)?;
        scale.SetScaleY2(fit)?;
        video.SetTransform(&scale)?;
        video.SetOffsetX2((rect.right as f32 - video_size.0 as f32 * fit) / 2.)?;
        video.SetOffsetY2((rect.bottom as f32 - video_size.1 as f32 * fit) / 2.)?;
        // Keep the GDI poster until the first decoded frame commits this tree.
        let (ready, worker) = crate::startup::begin(
            prepared,
            boot.resolve(&boot.output)?,
            d3d.clone(),
            swap.clone(),
            proxy.clone(),
            crate::startup::CommitDevice::new(device.clone()),
            serde_json::json!({"hwnd":hwnd.0 as isize,"title":boot.title,"original":boot.original.is_some(),"prewarm":boot.prewarm}),
        );
        let native_ms = native_started.elapsed().as_secs_f64() * 1000.;
        let web_started = std::time::Instant::now();
        let (tx, rx) = mpsc::channel();
        let profile = HSTRING::from(profile.to_string_lossy().as_ref());
        CreateCoreWebView2EnvironmentCompletedHandler::wait_for_async_operation(
            Box::new(move |handler| {
                CreateCoreWebView2EnvironmentWithOptions(PCWSTR::null(), &profile, None, &handler)
                    .map_err(webview2_com::Error::WindowsError)
            }),
            Box::new(move |code, environment| {
                code?;
                tx.send(environment).unwrap();
                Ok(())
            }),
        )?;
        let environment_ms = web_started.elapsed().as_secs_f64() * 1000.;
        let controller_started = std::time::Instant::now();
        let environment: ICoreWebView2Environment3 =
            rx.recv()?.ok_or("WebView2 environment missing")?.cast()?;
        let (tx, rx) = mpsc::channel();
        let resource_environment = environment.clone();
        CreateCoreWebView2CompositionControllerCompletedHandler::wait_for_async_operation(
            Box::new(move |handler| {
                environment
                    .CreateCoreWebView2CompositionController(hwnd, &handler)
                    .map_err(webview2_com::Error::WindowsError)
            }),
            Box::new(move |code, controller| {
                code?;
                tx.send(controller).unwrap();
                Ok(())
            }),
        )?;
        let input = rx.recv()?.ok_or("Composition controller missing")?;
        let controller_ms = controller_started.elapsed().as_secs_f64() * 1000.;
        input.SetRootVisualTarget(&html)?;
        let cursor_input = input.clone();
        let mut cursor_token = 0;
        input.add_CursorChanged(
            &CursorChangedEventHandler::create(Box::new(move |_, _| {
                if windows::Win32::UI::WindowsAndMessaging::GetForegroundWindow() == hwnd {
                    let mut cursor = windows::Win32::UI::WindowsAndMessaging::HCURSOR::default();
                    cursor_input.Cursor(&mut cursor)?;
                    windows::Win32::UI::WindowsAndMessaging::SetCursor(Some(cursor));
                }
                Ok(())
            })),
            &mut cursor_token,
        )?;
        let controller: ICoreWebView2Controller = input.cast()?;
        let background: ICoreWebView2Controller2 = controller.cast()?;
        background.SetDefaultBackgroundColor(COREWEBVIEW2_COLOR {
            A: 0,
            R: 0,
            G: 0,
            B: 0,
        })?;
        controller.SetBounds(RECT {
            left: 0,
            top: 0,
            right: 960,
            bottom: 540,
        })?;
        controller.SetIsVisible(true)?;
        let web = controller.CoreWebView2()?;
        let mut token = 0;
        let failed = events.clone();
        let wake = proxy.clone();
        web.add_ProcessFailed(
            &ProcessFailedEventHandler::create(Box::new(move |_, _| {
                let _ = failed.send("webview-failed".into());
                let _ = wake.send_event(());
                Ok(())
            })),
            &mut token,
        )?;
        web.add_WebMessageReceived(
            &WebMessageReceivedEventHandler::create(Box::new(move |_, args| {
                if let Some(args) = args {
                    let mut value = windows::core::PWSTR::null();
                    args.TryGetWebMessageAsString(&mut value)?;
                    let text = value.to_string()?;
                    windows::Win32::System::Com::CoTaskMemFree(Some(value.0.cast()));
                    let _ = events.send(text);
                    let _ = proxy.send_event(());
                }
                Ok(())
            })),
            &mut token,
        )?;
        let settings = web.Settings()?;
        let page_started = std::time::Instant::now();
        web.add_NavigationCompleted(
            &NavigationCompletedEventHandler::create(Box::new(move |_, args| {
                if let Some(args) = args {
                    let mut success = windows::core::BOOL::default();
                    let mut status = COREWEBVIEW2_WEB_ERROR_STATUS_UNKNOWN;
                    args.IsSuccess(&mut success)?;
                    args.WebErrorStatus(&mut status)?;
                    println!("{}",serde_json::json!({"version":1,"event":"pageProfile","elapsed_ms":page_started.elapsed().as_secs_f64()*1000.,"success":success.as_bool()}));
                    eprintln!(
                        "Player navigation: success={} status={}",
                        success.as_bool(),
                        status.0
                    );
                }
                Ok(())
            })),
            &mut token,
        )?;
        settings.SetAreDevToolsEnabled(cfg!(debug_assertions))?;
        settings.SetAreDefaultContextMenusEnabled(false)?;
        settings.SetAreDefaultScriptDialogsEnabled(false)?;
        web.add_NavigationStarting(
            &NavigationStartingEventHandler::create(Box::new(|_, args| {
                if let Some(args) = args {
                    let mut uri = windows::core::PWSTR::null();
                    args.Uri(&mut uri)?;
                    let value = uri.to_string()?;
                    windows::Win32::System::Com::CoTaskMemFree(Some(uri.0.cast()));
                    args.SetCancel(value != "https://player.videoenhancer.invalid/player.html")?;
                }
                Ok(())
            })),
            &mut token,
        )?;
        web.add_NewWindowRequested(
            &NewWindowRequestedEventHandler::create(Box::new(|_, args| {
                if let Some(args) = args {
                    args.SetHandled(true)?;
                }
                Ok(())
            })),
            &mut token,
        )?;
        web.AddWebResourceRequestedFilter(
            &HSTRING::from("*"),
            COREWEBVIEW2_WEB_RESOURCE_CONTEXT_ALL,
        )?;
        let environment: ICoreWebView2Environment = resource_environment.cast()?;
        #[cfg(feature = "test-faults")]
        let mockup = std::env::var("VE_PLAYER_TEST_MOCKUP").as_deref() == Ok("1");
        web.add_WebResourceRequested(&WebResourceRequestedEventHandler::create(Box::new(move |_, args| {
            if let Some(args) = args {
                let request = args.Request()?;
                let mut uri = windows::core::PWSTR::null();
                request.Uri(&mut uri)?;
                let value = uri.to_string()?;
                windows::Win32::System::Com::CoTaskMemFree(Some(uri.0.cast()));
                let asset = value.strip_prefix("https://player.videoenhancer.invalid")
                    .and_then(|path| crate::host::ASSETS.iter().find(|asset| asset.0 == path));
                let (status, mime, bytes) = asset.map(|a| (200, a.1, a.2)).unwrap_or((403, "text/plain", b"Blocked"));
                #[cfg(feature="test-faults")]
                let bytes=if mockup && value=="https://player.videoenhancer.invalid/player.html" {include_bytes!("../../../../design/player/player_mockup.html").as_slice()} else {bytes};
                let stream = SHCreateMemStream(Some(bytes));
                let policy="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
                #[cfg(feature="test-faults")]
                let policy=if mockup {"default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'"} else {policy};
                let response = environment.CreateWebResourceResponse(stream.as_ref(), status, &HSTRING::from("OK"),
                    &HSTRING::from(format!("Content-Type: {mime}\r\nCache-Control: no-store\r\nContent-Security-Policy: {policy}\r\n")))?;
                args.SetResponse(&response)?;
            }
            Ok(())
        })), &mut token)?;
        web.Navigate(&HSTRING::from(
            "https://player.videoenhancer.invalid/player.html",
        ))?;
        ready.store(true, std::sync::atomic::Ordering::Release);
        let startup = worker.join().map_err(|_| "Startup worker panicked")??;
        let mpv = startup.mpv;
        Ok(Self {
            follower: None,
            d3d,
            dll: dll.to_owned(),
            initial_state: startup.state,
            profile: serde_json::json!({"native_ms":native_ms,"webview_environment_ms":environment_ms,"webview_controller_ms":controller_ms,"mpv_initialize_ms":mpv.init_ms,"file_first_present_ms":startup.first_present_ms}),
            mpv,
            web,
            controller,
            input,
            swap,
            device,
            _target: target,
            _root: root,
            _video: video,
            before,
            _html: html,
            video_size,
            original_size: if boot.original_width >= 16 && boot.original_height >= 16 {
                (boot.original_width, boot.original_height)
            } else {
                video_size
            },
        })
    }
    pub unsafe fn enable_pair(
        &mut self,
        original: &Path,
        proxy: tao::event_loop::EventLoopProxy<()>,
        position: f64,
        paused: bool,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let mut desc = self.swap.GetDesc1()?;
        desc.Width = self.original_size.0;
        desc.Height = self.original_size.1;
        let follower = crate::follower::Follower::new(
            &self.d3d, &desc, &self.dll, original, proxy, position, paused,
        )?;
        self.before.SetContent(&follower.surface)?;
        self.follower = Some(follower);
        Ok(())
    }
    pub unsafe fn layout(
        &self,
        size: (u32, u32),
        pair: bool,
        enabled: bool,
        divider: f32,
        transform: (f32, f32, f32),
    ) -> Result<(), Box<dyn std::error::Error>> {
        let (width, height) = size;
        let (scale, x, y) = transform;
        let w = self.video_size.0 as f32;
        let h = self.video_size.1 as f32;
        let fit = (width as f32 / w).min(height as f32 / h);
        let effective = fit * scale;
        let offset_x = (width as f32 - w * effective) / 2. + x * width as f32;
        let offset_y = (height as f32 - h * effective) / 2. + y * height as f32;
        self._video
            .SetClip2(&windows::Win32::Graphics::Direct2D::Common::D2D_RECT_F {
                left: if enabled { w * divider } else { 0. },
                top: 0.,
                right: w,
                bottom: h,
            })?;
        self.before
            .SetClip2(&windows::Win32::Graphics::Direct2D::Common::D2D_RECT_F {
                left: 0.,
                top: 0.,
                right: if pair && enabled {
                    self.original_size.0 as f32 * divider
                } else {
                    0.
                },
                bottom: h,
            })?;
        let transform = self.device.CreateScaleTransform()?;
        transform.SetScaleX2(effective)?;
        transform.SetScaleY2(effective)?;
        self._video.SetTransform(&transform)?;
        let original_transform = self.device.CreateScaleTransform()?;
        original_transform.SetScaleX2(effective * w / self.original_size.0 as f32)?;
        original_transform.SetScaleY2(effective * h / self.original_size.1 as f32)?;
        self.before.SetTransform(&original_transform)?;
        self._video.SetOffsetX2(offset_x)?;
        self._video.SetOffsetY2(offset_y)?;
        self.before.SetOffsetX2(offset_x)?;
        self.before.SetOffsetY2(offset_y)?;
        self.device.Commit()?;
        Ok(())
    }
    pub unsafe fn resize(&self, width: u32, height: u32) -> Result<(), Box<dyn std::error::Error>> {
        if width == 0 || height == 0 {
            return Ok(());
        }
        self.controller.SetBounds(RECT {
            left: 0,
            top: 0,
            right: width as _,
            bottom: height as _,
        })?;
        self.device.Commit()?;
        Ok(())
    }
    pub unsafe fn draw(&self) -> Result<(), Box<dyn std::error::Error>> {
        let texture: ID3D11Texture2D = self.swap.GetBuffer(0)?;
        self.mpv.draw(texture.as_raw())?;
        self.swap.Present(1, DXGI_PRESENT(0)).ok()?;
        Ok(())
    }
}
impl Drop for Composition {
    fn drop(&mut self) {
        unsafe {
            let _ = self.controller.Close();
        }
    }
}
