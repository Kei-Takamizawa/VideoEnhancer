//! Exclusive render-thread ownership during asynchronous controls initialization.
use crate::mpv::Mpv;
use serde_json::json;
use std::{
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::{Duration, Instant},
};
use tao::event_loop::EventLoopProxy;
use windows::{
    core::Interface,
    Win32::{
        Foundation::HWND,
        Graphics::{
            Direct3D11::{ID3D11Device, ID3D11Texture2D},
            Dxgi::{IDXGISwapChain1, DXGI_PRESENT},
        },
    },
};

// SAFETY: DirectComposition objects are not thread-bound and Commit is thread-safe.
// The initialized picture tree precedes spawn; the final UI batch precedes the
// release/acquire handoff. No runtime rendering overlaps the joined startup worker.
// https://learn.microsoft.com/windows/win32/directcomp/architecture-and-components
pub struct CommitDevice(windows::Win32::Graphics::DirectComposition::IDCompositionDevice);
unsafe impl Send for CommitDevice {}
impl CommitDevice {
    pub fn new(device: windows::Win32::Graphics::DirectComposition::IDCompositionDevice) -> Self {
        Self(device)
    }
    fn commit(&self) -> windows::core::Result<()> {
        unsafe { self.0.Commit() }
    }
}
pub type Prepared = std::thread::JoinHandle<Result<Mpv, String>>;
pub fn prepare(dll: PathBuf) -> Prepared {
    std::thread::spawn(move || unsafe {
        Mpv::configured(&dll, None, &[]).map_err(|e| e.to_string())
    })
}
pub struct Startup {
    pub mpv: Mpv,
    pub state: serde_json::Value,
    pub first_present_ms: f64,
}

pub fn begin(
    prepared: Prepared,
    file: PathBuf,
    d3d: ID3D11Device,
    swap: IDXGISwapChain1,
    proxy: EventLoopProxy<()>,
    composition: CommitDevice,
    info: serde_json::Value,
) -> (
    Arc<AtomicBool>,
    std::thread::JoinHandle<Result<Startup, String>>,
) {
    let done = Arc::new(AtomicBool::new(false));
    let stop = done.clone();
    let worker = std::thread::spawn(move || unsafe {
        let run = || -> Result<Startup, Box<dyn std::error::Error>> {
            let began = Instant::now();
            let mut mpv = prepared
                .join()
                .map_err(|_| "Player preparation panicked")??;
            mpv.create_render(d3d.as_raw())?;
            mpv.callbacks(proxy)?;
            mpv.observe()?;
            if info["prewarm"] != true {
                mpv.command(&["loadfile", file.to_str().ok_or("Invalid path")?])?;
            }
            let mut loaded = false;
            let mut restarted = false;
            let mut first = None;
            let mut state =
                json!({"event":"state","position":0.,"duration":0.,"paused":false,"decoder":""});
            loop {
                for event in mpv.events() {
                    if event["id"] == 21 {
                        restarted = true;
                    }
                    if event["id"] == 8 {
                        loaded = true;
                    }
                    if event["id"] == 7 && event["reason"] == 4 {
                        return Err("Playback failed during startup".into());
                    }
                    if event["id"] == 22 {
                        let value = event["value"].as_str().unwrap_or("");
                        match event["name"].as_str().unwrap_or("") {
                            "time-pos" => {
                                if let Some(n) = event["value"]
                                    .as_f64()
                                    .or_else(|| value.parse::<f64>().ok())
                                {
                                    state["position"] = json!(n)
                                }
                            }
                            "duration" => {
                                if let Some(n) = event["value"]
                                    .as_f64()
                                    .or_else(|| value.parse::<f64>().ok())
                                {
                                    state["duration"] = json!(n)
                                }
                            }
                            "pause" => state["paused"] = json!(value == "yes"),
                            "hwdec-current" => state["decoder"] = json!(value),
                            "frame-drop-count" => state["dropped"] = json!(value),
                            _ => {}
                        }
                    }
                }
                if loaded && (mpv.needs_render()? || (restarted && first.is_none())) {
                    let texture: ID3D11Texture2D = swap.GetBuffer(0)?;
                    mpv.draw(texture.as_raw())?;
                    swap.Present(1, DXGI_PRESENT(0)).ok()?;
                    if restarted && first.is_none() {
                        composition.commit()?;
                        let ms = began.elapsed().as_secs_f64() * 1000.;
                        first = Some(ms);
                        println!(
                            "{}",
                            json!({"version":1,"event":"loaded","hwnd":info["hwnd"],"title":info["title"],"original":info["original"],"first_frame_ms":ms,"method":"first nonempty render and Present"})
                        );
                    }
                }
                if stop.load(Ordering::Acquire) && (first.is_some() || info["prewarm"] == true) {
                    composition.commit()?;
                    break;
                }
                if began.elapsed() > Duration::from_secs(12) {
                    return Err("First frame timed out".into());
                }
                std::thread::sleep(Duration::from_millis(1));
            }
            Ok(Startup {
                mpv,
                state,
                first_present_ms: first.unwrap_or(0.),
            })
        };
        run().map_err(|e| e.to_string())
    });
    (done, worker)
}

/// Paint a trusted session poster before the GPU or browser starts.
pub unsafe fn poster(hwnd: HWND, path: &std::path::Path) -> Result<(), Box<dyn std::error::Error>> {
    use windows::{
        core::HSTRING,
        Win32::{
            Graphics::{Gdi::*, Imaging::*},
            System::Com::*,
        },
    };
    let factory: IWICImagingFactory =
        CoCreateInstance(&CLSID_WICImagingFactory, None, CLSCTX_INPROC_SERVER)?;
    let decoder = factory.CreateDecoderFromFilename(
        &HSTRING::from(path.to_string_lossy().as_ref()),
        None,
        windows::Win32::Foundation::GENERIC_READ,
        WICDecodeMetadataCacheOnLoad,
    )?;
    let frame = decoder.GetFrame(0)?;
    let converter = factory.CreateFormatConverter()?;
    converter.Initialize(
        &frame,
        &GUID_WICPixelFormat32bppBGRA,
        WICBitmapDitherTypeNone,
        None,
        0.,
        WICBitmapPaletteTypeCustom,
    )?;
    let (mut width, mut height) = (0, 0);
    converter.GetSize(&mut width, &mut height)?;
    if width > 4096 || height > 4096 {
        return Err("Poster is too large".into());
    }
    let mut pixels = vec![0u8; (width * height * 4) as usize];
    converter.CopyPixels(std::ptr::null(), width * 4, &mut pixels)?;
    let mut rect = windows::Win32::Foundation::RECT::default();
    windows::Win32::UI::WindowsAndMessaging::GetClientRect(hwnd, &mut rect)?;
    let scale = (rect.right as f64 / width as f64).min(rect.bottom as f64 / height as f64);
    let (w, h) = (
        (width as f64 * scale) as i32,
        (height as f64 * scale) as i32,
    );
    let info = BITMAPINFO {
        bmiHeader: BITMAPINFOHEADER {
            biSize: std::mem::size_of::<BITMAPINFOHEADER>() as _,
            biWidth: width as _,
            biHeight: -(height as i32),
            biPlanes: 1,
            biBitCount: 32,
            biCompression: BI_RGB.0,
            ..Default::default()
        },
        ..Default::default()
    };
    let dc = GetDC(Some(hwnd));
    StretchDIBits(
        dc,
        (rect.right - w) / 2,
        (rect.bottom - h) / 2,
        w,
        h,
        0,
        0,
        width as _,
        height as _,
        Some(pixels.as_ptr().cast()),
        &info,
        DIB_RGB_COLORS,
        SRCCOPY,
    );
    ReleaseDC(Some(hwnd), dc);
    Ok(())
}
