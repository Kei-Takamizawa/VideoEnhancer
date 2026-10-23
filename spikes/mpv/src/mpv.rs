use libloading::Library;
use std::{
    ffi::{c_char, c_void, CStr, CString},
    path::Path,
};

#[repr(C)]
pub struct Param {
    pub kind: i32,
    pub data: *mut c_void,
}
pub struct Mpv {
    library: Library,
    pub handle: *mut c_void,
    pub render: *mut c_void,
}
impl Mpv {
    pub unsafe fn new(path: &Path, wid: Option<isize>) -> Result<Self, Box<dyn std::error::Error>> {
        Self::configured(path, wid, &[])
    }
    pub unsafe fn configured(
        path: &Path,
        wid: Option<isize>,
        options: &[(&str, &str)],
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let library = Library::new(path)?;
        let create = library.get::<unsafe extern "C" fn() -> *mut c_void>(b"mpv_create\0")?;
        let handle = create();
        if handle.is_null() {
            return Err("mpv_create failed".into());
        }
        let this = Self {
            library,
            handle,
            render: std::ptr::null_mut(),
        };
        for (key, value) in [
            ("config", "no"),
            ("load-scripts", "no"),
            ("terminal", "no"),
            ("hwdec", "d3d11va"),
            ("keep-open", "yes"),
            ("input-default-bindings", "no"),
        ] {
            this.option(key, value)?;
        }
        if let Some(wid) = wid {
            this.option("wid", &wid.to_string())?;
            this.option("vo", "gpu-next")?;
            this.option("gpu-api", "d3d11")?;
        } else {
            this.option("vo", "libmpv")?;
        }
        for (key, value) in options {
            this.option(key, value)?;
        }
        let init = this
            .library
            .get::<unsafe extern "C" fn(*mut c_void) -> i32>(b"mpv_initialize\0")?;
        Self::check(init(handle))?;
        Ok(this)
    }
    pub unsafe fn events(&self) -> Vec<i32> {
        #[repr(C)]
        struct Event {
            id: i32,
            error: i32,
            userdata: u64,
            data: *mut c_void,
        }
        let Ok(wait) = self
            .library
            .get::<unsafe extern "C" fn(*mut c_void, f64) -> *const Event>(b"mpv_wait_event\0")
        else {
            return vec![];
        };
        let mut result = Vec::new();
        for _ in 0..100 {
            let p = wait(self.handle, 0.0);
            if p.is_null() || (*p).id == 0 {
                break;
            }
            result.push((*p).id);
        }
        result
    }
    pub unsafe fn create_sw(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        let mut params = [
            Param {
                kind: 1,
                data: c"sw".as_ptr() as _,
            },
            Param {
                kind: 0,
                data: std::ptr::null_mut(),
            },
        ];
        let f =
            self.library
                .get::<unsafe extern "C" fn(*mut *mut c_void, *mut c_void, *mut Param) -> i32>(
                    b"mpv_render_context_create\0",
                )?;
        Self::check(f(&mut self.render, self.handle, params.as_mut_ptr()))
    }
    pub unsafe fn sw_pixels(
        &self,
        width: i32,
        height: i32,
    ) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
        let mut dimensions = [width, height];
        let mut stride = width as usize * 4;
        // Vec<u32> guarantees the minimum four-byte pixel alignment required by mpv.
        let mut pixels = vec![0u32; width as usize * height as usize];
        let mut params = [
            Param {
                kind: 17,
                data: dimensions.as_mut_ptr().cast(),
            },
            Param {
                kind: 18,
                data: c"rgb0".as_ptr() as _,
            },
            Param {
                kind: 19,
                data: (&mut stride as *mut usize).cast(),
            },
            Param {
                kind: 20,
                data: pixels.as_mut_ptr().cast(),
            },
            Param {
                kind: 0,
                data: std::ptr::null_mut(),
            },
        ];
        let render = self
            .library
            .get::<unsafe extern "C" fn(*mut c_void, *mut Param) -> i32>(
                b"mpv_render_context_render\0",
            )?;
        Self::check(render(self.render, params.as_mut_ptr()))?;
        let mut bytes =
            std::slice::from_raw_parts(pixels.as_ptr().cast::<u8>(), pixels.len() * 4).to_vec();
        for pixel in bytes.as_chunks_mut::<4>().0 {
            pixel[3] = 255;
        }
        Ok(bytes)
    }
    fn check(code: i32) -> Result<(), Box<dyn std::error::Error>> {
        if code < 0 {
            Err(format!("libmpv error {code}").into())
        } else {
            Ok(())
        }
    }
    pub unsafe fn option(&self, key: &str, value: &str) -> Result<(), Box<dyn std::error::Error>> {
        let f =
            self.library
                .get::<unsafe extern "C" fn(*mut c_void, *const c_char, *const c_char) -> i32>(
                    b"mpv_set_option_string\0",
                )?;
        Self::check(f(
            self.handle,
            CString::new(key)?.as_ptr(),
            CString::new(value)?.as_ptr(),
        ))
    }
    pub unsafe fn command(&self, args: &[&str]) -> Result<(), Box<dyn std::error::Error>> {
        let strings: Vec<_> = args
            .iter()
            .map(|s| CString::new(*s))
            .collect::<Result<_, _>>()?;
        let mut ptrs: Vec<_> = strings.iter().map(|s| s.as_ptr()).collect();
        ptrs.push(std::ptr::null());
        let f = self
            .library
            .get::<unsafe extern "C" fn(*mut c_void, *const *const c_char) -> i32>(
                b"mpv_command\0",
            )?;
        Self::check(f(self.handle, ptrs.as_ptr()))
    }
    pub unsafe fn property(&self, name: &str) -> Option<String> {
        let get = self
            .library
            .get::<unsafe extern "C" fn(*mut c_void, *const c_char) -> *mut c_char>(
                b"mpv_get_property_string\0",
            )
            .ok()?;
        let p = get(self.handle, CString::new(name).ok()?.as_ptr());
        if p.is_null() {
            return None;
        }
        let value = CStr::from_ptr(p).to_string_lossy().into_owned();
        let free = self
            .library
            .get::<unsafe extern "C" fn(*mut c_void)>(b"mpv_free\0")
            .ok()?;
        free(p.cast());
        Some(value)
    }
    pub unsafe fn create_render(
        &mut self,
        device: *mut c_void,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let mut device = device;
        let mut params = [
            Param {
                kind: 1,
                data: c"d3d11".as_ptr() as _,
            },
            Param {
                kind: 21,
                data: (&mut device as *mut *mut c_void).cast(),
            },
            Param {
                kind: 0,
                data: std::ptr::null_mut(),
            },
        ];
        let f =
            self.library
                .get::<unsafe extern "C" fn(*mut *mut c_void, *mut c_void, *mut Param) -> i32>(
                    b"mpv_render_context_create\0",
                )?;
        Self::check(f(&mut self.render, self.handle, params.as_mut_ptr()))
    }
    pub unsafe fn draw(&self, texture: *mut c_void) -> Result<(), Box<dyn std::error::Error>> {
        let mut texture = texture;
        let mut block = 0i32;
        let mut params = [
            Param {
                kind: 22,
                data: (&mut texture as *mut *mut c_void).cast(),
            },
            Param {
                kind: 12,
                data: (&mut block as *mut i32).cast(),
            },
            Param {
                kind: 0,
                data: std::ptr::null_mut(),
            },
        ];
        let f = self
            .library
            .get::<unsafe extern "C" fn(*mut c_void, *mut Param) -> i32>(
                b"mpv_render_context_render\0",
            )?;
        Self::check(f(self.render, params.as_mut_ptr()))
    }
}
impl Drop for Mpv {
    fn drop(&mut self) {
        unsafe {
            if !self.render.is_null() {
                if let Ok(f) = self
                    .library
                    .get::<unsafe extern "C" fn(*mut c_void)>(b"mpv_render_context_free\0")
                {
                    f(self.render);
                }
            }
            if let Ok(f) = self
                .library
                .get::<unsafe extern "C" fn(*mut c_void)>(b"mpv_terminate_destroy\0")
            {
                f(self.handle);
            }
        }
    }
}
