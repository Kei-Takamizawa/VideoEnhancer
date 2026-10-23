//! Self-test capture: DXGI duplication cropped to this process's own window.
//! Never saves the full desktop, and refuses capture behind a foreign foreground.
use std::{fs::File, io::BufWriter, path::Path};
use windows::{
    core::Interface,
    Win32::{
        Foundation::{HWND, RECT},
        Graphics::{Direct3D::D3D_DRIVER_TYPE_HARDWARE, Direct3D11::*, Dxgi::*},
        System::Threading::GetCurrentProcessId,
        UI::WindowsAndMessaging::{
            GetForegroundWindow, GetWindowRect, GetWindowThreadProcessId, IsIconic,
        },
    },
};

pub fn png_bytes(
    width: u32,
    height: u32,
    pixels: &[u8],
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let mut bytes = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut bytes, width, height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header()?;
        writer.write_image_data(pixels)?;
    }
    Ok(bytes)
}

pub unsafe fn save(
    hwnd: HWND,
    path: &Path,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let pid = GetCurrentProcessId();
    let mut owner = 0;
    GetWindowThreadProcessId(hwnd, Some(&mut owner));
    let mut foreground = 0;
    GetWindowThreadProcessId(GetForegroundWindow(), Some(&mut foreground));
    if owner != pid || foreground != pid || IsIconic(hwnd).as_bool() {
        return Err("Self-capture refused: window not owned, foreground belongs to another process, or minimised".into());
    }
    let mut rect = RECT::default();
    GetWindowRect(hwnd, &mut rect)?;
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
    let device = device.ok_or("No D3D11 device")?;
    let context = context.ok_or("No D3D11 context")?;
    let dxgi: IDXGIDevice = device.cast()?;
    let adapter = dxgi.GetAdapter()?;
    let mut selected = None;
    for index in 0..16 {
        let Ok(output) = adapter.EnumOutputs(index) else {
            break;
        };
        let desktop = output.GetDesc()?.DesktopCoordinates;
        if rect.left >= desktop.left
            && rect.top >= desktop.top
            && rect.right <= desktop.right
            && rect.bottom <= desktop.bottom
        {
            selected = Some((output.cast::<IDXGIOutput1>()?, desktop));
            break;
        }
    }
    let (output, desktop) = selected.ok_or("Window not fully within one attached output")?;
    let duplication = output.DuplicateOutput(&device)?;
    let mut info = DXGI_OUTDUPL_FRAME_INFO::default();
    let mut resource = None;
    duplication.AcquireNextFrame(2000, &mut info, &mut resource)?;
    let result = (|| -> Result<_, Box<dyn std::error::Error>> {
        let source: ID3D11Texture2D = resource.ok_or("No duplicated frame")?.cast()?;
        let width = (rect.right - rect.left) as u32;
        let height = (rect.bottom - rect.top) as u32;
        let mut desc = D3D11_TEXTURE2D_DESC::default();
        source.GetDesc(&mut desc);
        desc.Width = width;
        desc.Height = height;
        desc.Usage = D3D11_USAGE_STAGING;
        desc.BindFlags = 0;
        desc.MiscFlags = 0;
        desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ.0 as u32;
        let mut staging = None;
        device.CreateTexture2D(&desc, None, Some(&mut staging))?;
        let staging = staging.ok_or("No staging texture")?;
        let region = D3D11_BOX {
            left: (rect.left - desktop.left) as _,
            top: (rect.top - desktop.top) as _,
            front: 0,
            right: (rect.right - desktop.left) as _,
            bottom: (rect.bottom - desktop.top) as _,
            back: 1,
        };
        context.CopySubresourceRegion(&staging, 0, 0, 0, 0, &source, 0, Some(&region));
        let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
        context.Map(&staging, 0, D3D11_MAP_READ, 0, Some(&mut mapped))?;
        let mut pixels = vec![0u8; (width * height * 4) as usize];
        for y in 0..height as usize {
            let row = std::slice::from_raw_parts(
                (mapped.pData as *const u8).add(y * mapped.RowPitch as usize),
                width as usize * 4,
            );
            for x in 0..width as usize {
                let p = &mut pixels[(y * width as usize + x) * 4..][..4];
                p.copy_from_slice(&[row[x * 4 + 2], row[x * 4 + 1], row[x * 4], 255]);
            }
        }
        context.Unmap(&staging, 0);
        // Re-check foreground after readback; abort rather than save foreign content.
        let mut check = 0;
        GetWindowThreadProcessId(GetForegroundWindow(), Some(&mut check));
        if check != pid {
            return Err("Self-capture aborted: foreground changed".into());
        }
        let mut encoder = png::Encoder::new(BufWriter::new(File::create(path)?), width, height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        encoder.write_header()?.write_image_data(&pixels)?;
        let nonblack = pixels
            .as_chunks::<4>()
            .0
            .iter()
            .filter(|p| p[0] > 10 || p[1] > 10 || p[2] > 10)
            .count();
        Ok(
            serde_json::json!({"width":width,"height":height,"nonblack_fraction":nonblack as f64/(width*height) as f64,"method":"DXGI duplication; own-window crop only","rect":[rect.left,rect.top,rect.right,rect.bottom]}),
        )
    })();
    let _ = duplication.ReleaseFrame();
    result
}

/// Independent HWND-only WGC path used to distinguish black DXGI results.
pub unsafe fn save_wgc(
    hwnd: HWND,
    path: &Path,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    use windows::{
        Graphics::{
            Capture::{Direct3D11CaptureFramePool, GraphicsCaptureItem, GraphicsCaptureSession},
            DirectX::{Direct3D11::IDirect3DDevice, DirectXPixelFormat},
        },
        Win32::System::WinRT::{
            Direct3D11::{CreateDirect3D11DeviceFromDXGIDevice, IDirect3DDxgiInterfaceAccess},
            Graphics::Capture::IGraphicsCaptureItemInterop,
        },
    };
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
    session.StartCapture()?;
    let started = std::time::Instant::now();
    let frame = loop {
        if let Ok(frame) = pool.TryGetNextFrame() {
            break frame;
        }
        if started.elapsed() > std::time::Duration::from_secs(3) {
            session.Close()?;
            pool.Close()?;
            return Err("WGC returned no frame within 3 seconds".into());
        }
        std::thread::sleep(std::time::Duration::from_millis(10));
    };
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
    context.Unmap(&staging, 0);
    frame.Close()?;
    session.Close()?;
    pool.Close()?;
    std::fs::write(path, png_bytes(width as u32, height as u32, &pixels)?)?;
    let nonblack = pixels
        .as_chunks::<4>()
        .0
        .iter()
        .filter(|p| p[0] > 10 || p[1] > 10 || p[2] > 10)
        .count();
    Ok(
        serde_json::json!({"method":"Windows.Graphics.Capture; own HWND only","width":width,"height":height,"nonblack_fraction":nonblack as f64/(width*height) as f64}),
    )
}
