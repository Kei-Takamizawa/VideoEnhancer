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
        let reader = std::thread::spawn(move || {
            while !ending.load(std::sync::atomic::Ordering::Acquire) {
                while let Ok(frame) = frame_pool.TryGetNextFrame() {
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
        })
    }
    unsafe fn save(
        &mut self,
        path: &Path,
    ) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
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
