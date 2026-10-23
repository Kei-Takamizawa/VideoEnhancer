use crate::mpv::Mpv;
use std::{path::Path, sync::mpsc};
use webview2_com::{
    CreateCoreWebView2CompositionControllerCompletedHandler,
    CreateCoreWebView2EnvironmentCompletedHandler, Microsoft::Web::WebView2::Win32::*,
    WebMessageReceivedEventHandler,
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
    _html: IDCompositionVisual,
}
impl Composition {
    pub unsafe fn new(
        hwnd: HWND,
        dll: &Path,
        profile: &Path,
        events: mpsc::Sender<String>,
    ) -> Result<Self, Box<dyn std::error::Error>> {
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
                Width: 960,
                Height: 540,
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
        let html = device.CreateVisual()?;
        root.AddVisual(&video, false, None)?;
        root.AddVisual(&html, true, None)?;
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
        web.add_WebMessageReceived(
            &WebMessageReceivedEventHandler::create(Box::new(move |_, args| {
                if let Some(args) = args {
                    let mut value = windows::core::PWSTR::null();
                    args.TryGetWebMessageAsString(&mut value)?;
                    let text = value.to_string()?;
                    windows::Win32::System::Com::CoTaskMemFree(Some(value.0.cast()));
                    let _ = events.send(text);
                }
                Ok(())
            })),
            &mut token,
        )?;
        web.NavigateToString(&HSTRING::from(include_str!("../controls.html")))?;
        device.Commit()?;
        let mut mpv = Mpv::new(dll, None)?;
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
            _html: html,
        })
    }
    pub unsafe fn resize(&self, width: u32, height: u32) -> Result<(), Box<dyn std::error::Error>> {
        if width == 0 || height == 0 {
            return Ok(());
        }
        self.swap.ResizeBuffers(
            0,
            width,
            height,
            DXGI_FORMAT_UNKNOWN,
            DXGI_SWAP_CHAIN_FLAG(0),
        )?;
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
