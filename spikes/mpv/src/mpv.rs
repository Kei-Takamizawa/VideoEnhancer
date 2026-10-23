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
        let init = this
            .library
            .get::<unsafe extern "C" fn(*mut c_void) -> i32>(b"mpv_initialize\0")?;
        Self::check(init(handle))?;
        Ok(this)
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
