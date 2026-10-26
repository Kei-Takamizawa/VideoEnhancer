use crate::mpv::Mpv;
use std::{path::Path, sync::mpsc};
use webview2_com::{
    CreateCoreWebView2CompositionControllerCompletedHandler,
    CreateCoreWebView2EnvironmentCompletedHandler, Microsoft::Web::WebView2::Win32::*,
    NavigationCompletedEventHandler, NavigationStartingEventHandler,
    NewWindowRequestedEventHandler, ProcessFailedEventHandler, WebMessageReceivedEventHandler,
    WebResourceRequestedEventHandler,
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
}
impl Composition {
    pub unsafe fn new(
        hwnd: HWND,
        dll: &Path,
        profile: &Path,
        events: mpsc::Sender<String>,
        proxy: tao::event_loop::EventLoopProxy<()>,
        video_size: (u32, u32),
    ) -> Result<Self, Box<dyn std::error::Error>> {
        #[cfg(feature = "test-faults")]
        if std::env::var("VE_PLAYER_TEST_FAIL_D3D").as_deref() == Ok("1") {
            return Err("Simulated D3D11 device creation failure (test build only).".into());
        }
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
        input.SetRootVisualTarget(&html)?;
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
        web.add_NavigationCompleted(
            &NavigationCompletedEventHandler::create(Box::new(|_, args| {
                if let Some(args) = args {
                    let mut success = windows::core::BOOL::default();
                    let mut status = COREWEBVIEW2_WEB_ERROR_STATUS_UNKNOWN;
                    args.IsSuccess(&mut success)?;
                    args.WebErrorStatus(&mut status)?;
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
                let stream = SHCreateMemStream(Some(bytes));
                let response = environment.CreateWebResourceResponse(stream.as_ref(), status, &HSTRING::from("OK"),
                    &HSTRING::from(format!("Content-Type: {mime}\r\nCache-Control: no-store\r\nContent-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'\r\n")))?;
                args.SetResponse(&response)?;
            }
            Ok(())
        })), &mut token)?;
        web.Navigate(&HSTRING::from(
            "https://player.videoenhancer.invalid/player.html",
        ))?;
        device.Commit()?;
        let mut mpv = Mpv::configured(dll, None, &[])?;
        mpv.create_render(d3d.as_raw())?;
        Ok(Self {
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
        })
    }
    pub unsafe fn enable_pair(
        &self,
        _original: &Path,
    ) -> Result<String, Box<dyn std::error::Error>> {
        self.swap.ResizeBuffers(
            0,
            self.video_size.0 * 2,
            self.video_size.1,
            DXGI_FORMAT_UNKNOWN,
            DXGI_SWAP_CHAIN_FLAG(0),
        )?;
        Ok(format!(
            "[vid2]scale=w={}:h={}[original];[vid1][original]hstack=inputs=2[vo]",
            self.video_size.0, self.video_size.1
        ))
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
                left: w,
                top: 0.,
                right: if pair && enabled {
                    w * (1. + divider)
                } else {
                    w
                },
                bottom: h,
            })?;
        let transform = self.device.CreateScaleTransform()?;
        transform.SetScaleX2(effective)?;
        transform.SetScaleY2(effective)?;
        self._video.SetTransform(&transform)?;
        self.before.SetTransform(&transform)?;
        self._video.SetOffsetX2(offset_x)?;
        self._video.SetOffsetY2(offset_y)?;
        self.before.SetOffsetX2(offset_x - w * effective)?;
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
