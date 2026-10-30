//! Test-only Windows.Graphics.Capture of this process's HWND, never the desktop.
use std::path::Path;
use windows::{
    core::Interface,
    Win32::{
        Foundation::HWND,
        Graphics::{Direct3D::D3D_DRIVER_TYPE_HARDWARE, Direct3D11::*, Dxgi::*},
        System::Threading::GetCurrentProcessId,
        UI::WindowsAndMessaging::GetWindowThreadProcessId,
    },
};
fn png_bytes(
    width: u32,
    height: u32,
    pixels: &[u8],
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let mut bytes = Vec::new();
    {
        let mut e = png::Encoder::new(&mut bytes, width, height);
        e.set_color(png::ColorType::Rgba);
        e.set_depth(png::BitDepth::Eight);
        e.write_header()?.write_image_data(pixels)?;
    }
    Ok(bytes)
}
use windows::{
    Graphics::{
        Capture::{
            Direct3D11CaptureFrame, Direct3D11CaptureFramePool, GraphicsCaptureItem,
            GraphicsCaptureSession,
        },
        DirectX::{Direct3D11::IDirect3DDevice, DirectXPixelFormat},
    },
    Win32::System::WinRT::{
        Direct3D11::{CreateDirect3D11DeviceFromDXGIDevice, IDirect3DDxgiInterfaceAccess},
        Graphics::Capture::IGraphicsCaptureItemInterop,
    },
};
struct Session {
    hwnd: HWND,
    device: ID3D11Device,
    context: ID3D11DeviceContext,
    pool: Direct3D11CaptureFramePool,
    session: GraphicsCaptureSession,
    last: std::sync::Arc<std::sync::Mutex<Option<Direct3D11CaptureFrame>>>,
    stop: std::sync::Arc<std::sync::atomic::AtomicBool>,
    reader: Option<std::thread::JoinHandle<()>>,
    seam: std::sync::Arc<std::sync::Mutex<SeamStats>>,
    gpu_lock: std::sync::Arc<std::sync::Mutex<()>>,
}
#[derive(Default)]
struct SeamStats {
    enabled: bool,
    frames: u64,
    gap_frames: u64,
    max_gap: usize,
    first_seconds: f64,
    last_seconds: f64,
    errors: u64,
    red_blue_frames: u64,
}

pub unsafe fn seam_watch(
    hwnd: HWND,
    enabled: bool,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    CAPTURE.with(|slot| {
        let mut slot = slot.borrow_mut();
        if slot.is_none() {
            *slot = Some(Session::new(hwnd)?);
        }
        let capture = slot.as_ref().ok_or("No capture session")?;
        if capture.hwnd != hwnd { return Err("Capture window changed".into()); }
        let mut stats = capture.seam.lock().map_err(|_| "Seam lock")?;
        if enabled { *stats = SeamStats { enabled: true, ..Default::default() }; }
        else { stats.enabled = false; }
        Ok(serde_json::json!({"frames":stats.frames,"red_blue_frames":stats.red_blue_frames,"gap_frames":stats.gap_frames,"max_gap_pixels":stats.max_gap,"first_seconds":stats.first_seconds,"last_seconds":stats.last_seconds,"errors":stats.errors,"method":"WGC every received own-window frame; red/blue synthetic center row"}))
    })
}

unsafe fn measure_seam(
    device: &ID3D11Device,
    context: &ID3D11DeviceContext,
    frame: &Direct3D11CaptureFrame,
    stats: &mut SeamStats,
) -> Result<(), Box<dyn std::error::Error>> {
    let access: IDirect3DDxgiInterfaceAccess = frame.Surface()?.cast()?;
    let source: ID3D11Texture2D = access.GetInterface()?;
    let mut desc = D3D11_TEXTURE2D_DESC::default();
    source.GetDesc(&mut desc);
    desc.Usage = D3D11_USAGE_STAGING;
    desc.BindFlags = 0;
    desc.MiscFlags = 0;
    desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ.0 as _;
    let mut staging = None;
    device.CreateTexture2D(&desc, None, Some(&mut staging))?;
    let staging = staging.ok_or("No staging")?;
    context.CopyResource(&staging, &source);
    let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
    context.Map(&staging, 0, D3D11_MAP_READ, 0, Some(&mut mapped))?;
    let row = std::slice::from_raw_parts(
        (mapped.pData as *const u8).add(desc.Height as usize / 2 * mapped.RowPitch as usize),
        desc.Width as usize * 4,
    );
    let colored = |x: usize| {
        let p = &row[x * 4..][..4];
        p[1] < 80 && p[0] as u16 + p[2] as u16 > 230
    };
    let red = row
        .as_chunks::<4>()
        .0
        .iter()
        .filter(|p| p[2] > 160 && p[0] < 80 && p[1] < 80)
        .count();
    let blue = row
        .as_chunks::<4>()
        .0
        .iter()
        .filter(|p| p[0] > 160 && p[2] < 80 && p[1] < 80)
        .count();
    if red >= 8 && blue >= 8 {
        stats.red_blue_frames += 1;
    } else {
        stats.errors += 1;
    }
    let first = (0..desc.Width as usize).find(|&x| colored(x));
    let last = (0..desc.Width as usize).rfind(|&x| colored(x));
    let mut max_gap = 0;
    if let (Some(first), Some(last)) = (first, last) {
        let mut gap = 0;
        for x in first..=last {
            gap = if colored(x) { 0 } else { gap + 1 };
            max_gap = max_gap.max(gap);
        }
    } else {
        stats.errors += 1;
    }
    context.Unmap(&staging, 0);
    let at = frame.SystemRelativeTime()?.Duration as f64 / 10_000_000.;
    if stats.frames == 0 {
        stats.first_seconds = at;
    }
    stats.last_seconds = at;
    stats.frames += 1;
    if max_gap > 0 {
        stats.gap_frames += 1;
    }
    stats.max_gap = stats.max_gap.max(max_gap);
    Ok(())
}
thread_local! {static CAPTURE:std::cell::RefCell<Option<Session>>=const {std::cell::RefCell::new(None)};}
pub fn shutdown() {
    CAPTURE.with(|slot| {
        slot.borrow_mut().take();
    });
}
pub unsafe fn save_wgc(
    hwnd: HWND,
    path: &Path,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    CAPTURE.with(|slot| {
        let mut slot = slot.borrow_mut();
        for _ in 0..3 {
            if slot.is_none() {
                *slot = Some(Session::new(hwnd)?);
            }
            let capture = slot.as_mut().ok_or("No capture session")?;
            if capture.hwnd != hwnd {
                return Err("Capture window changed".into());
            }
            match capture.save(path) {
                Err(error) if error.to_string() == "WGC resize" => {
                    slot.take();
                }
                value => return value,
            }
        }
        Err("WGC window kept resizing".into())
    })
}

impl Session {
    unsafe fn new(hwnd: HWND) -> Result<Self, Box<dyn std::error::Error>> {
        let mut pid = 0;
        GetWindowThreadProcessId(hwnd, Some(&mut pid));
        if pid != GetCurrentProcessId() {
            return Err("WGC target not owned by prototype".into());
        }
        if !GraphicsCaptureSession::IsSupported()? {
            return Err("WGC unsupported".into());
        }
        let factory: IGraphicsCaptureItemInterop =
            windows::core::factory::<GraphicsCaptureItem, IGraphicsCaptureItemInterop>()?;
        let item: GraphicsCaptureItem = factory.CreateForWindow(hwnd)?;
        let mut device = None;
        let mut context = None;
        D3D11CreateDevice(
            None,
            D3D_DRIVER_TYPE_HARDWARE,
            Default::default(),
            D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            None,
            D3D11_SDK_VERSION,
            Some(&mut device),
            None,
            Some(&mut context),
        )?;
        let device = device.ok_or("No device")?;
        let context = context.ok_or("No context")?;
        let dxgi: IDXGIDevice = device.cast()?;
        let winrt: IDirect3DDevice = CreateDirect3D11DeviceFromDXGIDevice(&dxgi)?.cast()?;
        let pool = Direct3D11CaptureFramePool::CreateFreeThreaded(
            &winrt,
            DirectXPixelFormat::B8G8R8A8UIntNormalized,
            2,
            item.Size()?,
        )?;
        let session = pool.CreateCaptureSession(&item)?;
        let last = std::sync::Arc::new(std::sync::Mutex::new(None::<Direct3D11CaptureFrame>));
        let latest = last.clone();
        let frame_pool = pool.clone();
        let stop = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
        let ending = stop.clone();
        let seam = std::sync::Arc::new(std::sync::Mutex::new(SeamStats::default()));
        let measured = seam.clone();
        let capture_device = device.clone();
        let capture_context = context.clone();
        let gpu_lock = std::sync::Arc::new(std::sync::Mutex::new(()));
        let capture_lock = gpu_lock.clone();
        let reader = std::thread::spawn(move || {
            while !ending.load(std::sync::atomic::Ordering::Acquire) {
                while let Ok(frame) = frame_pool.TryGetNextFrame() {
                    if let Ok(mut stats) = measured.lock() {
                        if stats.enabled {
                            if let Ok(_guard) = capture_lock.lock() {
                                if measure_seam(
                                    &capture_device,
                                    &capture_context,
                                    &frame,
                                    &mut stats,
                                )
                                .is_err()
                                {
                                    stats.errors += 1;
                                }
                            }
                        }
                    }
                    if let Ok(mut latest) = latest.lock() {
                        if let Some(old) = latest.replace(frame) {
                            let _ = old.Close();
                        }
                    }
                }
                std::thread::sleep(std::time::Duration::from_millis(1));
            }
        });
        session.StartCapture()?;
        Ok(Self {
            hwnd,
            device,
            context,
            pool,
            session,
            last,
            stop,
            reader: Some(reader),
            seam,
            gpu_lock,
        })
    }
    unsafe fn save(
        &mut self,
        path: &Path,
    ) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
        let _gpu_guard = self.gpu_lock.lock().map_err(|_| "Capture GPU lock")?;
        let started = std::time::Instant::now();
        while self.last.lock().map_err(|_| "Capture lock")?.is_none() {
            if started.elapsed() > std::time::Duration::from_secs(3) {
                return Err("No WGC frame".into());
            }
            std::thread::sleep(std::time::Duration::from_millis(1));
        }
        let current = self.last.lock().map_err(|_| "Capture lock")?;
        let frame = current.as_ref().ok_or("No WGC frame")?;
        let access: IDirect3DDxgiInterfaceAccess = frame.Surface()?.cast()?;
        let source: ID3D11Texture2D = access.GetInterface()?;
        let mut desc = D3D11_TEXTURE2D_DESC::default();
        source.GetDesc(&mut desc);
        let requested = frame.ContentSize()?;
        if requested.Width as u32 != desc.Width || requested.Height as u32 != desc.Height {
            return Err("WGC resize".into());
        }

        desc.Usage = D3D11_USAGE_STAGING;
        desc.BindFlags = 0;
        desc.MiscFlags = 0;
        desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ.0 as _;
        let mut staging = None;
        self.device
            .CreateTexture2D(&desc, None, Some(&mut staging))?;
        let staging = staging.ok_or("No staging")?;
        self.context.CopyResource(&staging, &source);
        let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
        self.context
            .Map(&staging, 0, D3D11_MAP_READ, 0, Some(&mut mapped))?;
        let size = frame.ContentSize()?;
        let width = size.Width as usize;
        let height = size.Height as usize;
        let mut pixels = vec![0u8; width * height * 4];
        for y in 0..height {
            let row = std::slice::from_raw_parts(
                (mapped.pData as *const u8).add(y * mapped.RowPitch as usize),
                width * 4,
            );
            for x in 0..width {
                pixels[(y * width + x) * 4..][..4].copy_from_slice(&[
                    row[x * 4 + 2],
                    row[x * 4 + 1],
                    row[x * 4],
                    row[x * 4 + 3],
                ]);
            }
        }
        self.context.Unmap(&staging, 0);
        let frame_qpc_seconds = frame.SystemRelativeTime()?.Duration as f64 / 10_000_000.;
        drop(current);
        std::fs::write(path, png_bytes(width as u32, height as u32, &pixels)?)?;
        let nonblack = pixels
            .as_chunks::<4>()
            .0
            .iter()
            .filter(|p| p[0] > 10 || p[1] > 10 || p[2] > 10)
            .count();
        Ok(
            serde_json::json!({"method":"Windows.Graphics.Capture; own HWND only","width":width,"height":height,"frame_qpc_seconds":frame_qpc_seconds,"nonblack_fraction":nonblack as f64/(width*height) as f64}),
        )
    }
}
impl Drop for Session {
    fn drop(&mut self) {
        self.stop.store(true, std::sync::atomic::Ordering::Release);
        if let Some(reader) = self.reader.take() {
            let _ = reader.join();
        }
        if let Ok(mut last) = self.last.lock() {
            if let Some(frame) = last.take() {
                let _ = frame.Close();
            }
        }
        let _ = self.session.Close();
        let _ = self.pool.Close();
    }
}
