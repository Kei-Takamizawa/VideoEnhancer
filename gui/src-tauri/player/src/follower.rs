//! A silent zero-copy decoder following the enhanced video's clock.
use crate::mpv::Mpv;
use std::{
    path::Path,
    time::{Duration, Instant},
};
use windows::{
    core::Interface,
    Win32::Graphics::{
        Direct3D11::{ID3D11Device, ID3D11Texture2D},
        Dxgi::{IDXGIDevice, IDXGIFactory2, IDXGISwapChain1, DXGI_PRESENT, DXGI_SWAP_CHAIN_DESC1},
    },
};

pub struct Follower {
    pub player: Mpv,
    pub surface: IDXGISwapChain1,
    pub position: f64,
    pub target: f64,
    pub ready: bool,
    pub decoder: String,
    pub dropped: String,
    speed: f64,
    paused: bool,
    loaded: bool,
    initial_ready: bool,
    pending_seek: bool,
    restarted: bool,
    adjusted: Instant,
}
impl Follower {
    pub unsafe fn new(
        d3d: &ID3D11Device,
        desc: &DXGI_SWAP_CHAIN_DESC1,
        dll: &Path,
        file: &Path,
        proxy: tao::event_loop::EventLoopProxy<()>,
        position: f64,
        paused: bool,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        let dxgi: IDXGIDevice = d3d.cast()?;
        let factory: IDXGIFactory2 = dxgi.GetAdapter()?.GetParent()?;
        let surface = factory.CreateSwapChainForComposition(d3d, desc, None)?;
        let mut player = Mpv::configured(
            dll,
            None,
            &[
                ("audio", "no"),
                ("pause", if paused { "yes" } else { "no" }),
                ("start", &position.to_string()),
            ],
        )?;
        player.create_render(d3d.as_raw())?;
        player.callbacks(proxy)?;
        player.observe()?;
        player.command(&["loadfile", file.to_str().ok_or("Invalid original path")?])?;
        Ok(Self {
            player,
            surface,
            position: 0.,
            target: position,
            ready: false,
            decoder: String::new(),
            dropped: String::new(),
            speed: 1.,
            paused,
            loaded: false,
            initial_ready: false,
            pending_seek: false,
            restarted: false,
            adjusted: Instant::now(),
        })
    }
    pub fn aligned(&self, master: f64, paused: bool) -> bool {
        self.ready
            && if paused {
                (self.target - master).abs() < 0.00001
                    && (self.position - master).abs() < 1. / 30. + 0.00001
            } else {
                (self.position - master).abs() < 0.1
            }
    }
    pub unsafe fn set_speed(&mut self, rate: f64) -> Result<(), Box<dyn std::error::Error>> {
        self.speed = rate;
        self.player.command(&["set", "speed", &rate.to_string()])
    }
    pub unsafe fn set_paused(&mut self, paused: bool) -> Result<(), Box<dyn std::error::Error>> {
        self.player
            .command(&["set", "pause", if paused { "yes" } else { "no" }])?;
        self.paused = paused;
        self.adjusted = Instant::now();
        Ok(())
    }
    pub unsafe fn exact(
        &mut self,
        seconds: f64,
        paused: bool,
    ) -> Result<(), Box<dyn std::error::Error>> {
        self.target = seconds;
        self.paused = paused;
        self.ready = false;
        self.restarted = false;
        self.pending_seek = true;
        if self.initial_ready {
            self.apply_pending()?;
        }
        Ok(())
    }
    unsafe fn apply_pending(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        self.player
            .command(&["set", "pause", if self.paused { "yes" } else { "no" }])?;
        self.player
            .command(&["seek", &self.target.to_string(), "absolute+exact"])?;
        self.pending_seek = false;
        self.ready = false;
        self.restarted = false;
        self.adjusted = Instant::now();
        Ok(())
    }
    pub unsafe fn poll(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        for event in self.player.events() {
            if event["id"] == 8 {
                self.loaded = true;
            }
            if event["id"] == 21 {
                self.initial_ready = true;
                self.restarted = true;
            }
            if event["id"] == 7 && event["reason"] == 4 {
                return Err("Original playback failed".into());
            }
            if event["id"] == 22 {
                let value = event["value"].as_str().unwrap_or("");
                match event["name"].as_str().unwrap_or("") {
                    "time-pos" => {
                        if let Some(n) = event["value"]
                            .as_f64()
                            .or_else(|| value.parse::<f64>().ok())
                        {
                            self.position = n;
                        }
                    }
                    "hwdec-current" => self.decoder = value.into(),
                    "frame-drop-count" => self.dropped = value.into(),
                    _ => {}
                }
            }
        }
        if self.initial_ready && self.pending_seek {
            self.apply_pending()?;
        }
        if self.loaded && self.player.needs_render()? {
            let texture: ID3D11Texture2D = self.surface.GetBuffer(0)?;
            self.player.draw(texture.as_raw())?;
            self.surface.Present(0, DXGI_PRESENT(0)).ok()?;
        }
        if self.restarted && self.adjusted.elapsed() >= Duration::from_millis(70) {
            self.ready = true;
        }
        Ok(())
    }
    pub unsafe fn synchronize(
        &mut self,
        master: f64,
        paused: bool,
    ) -> Result<(), Box<dyn std::error::Error>> {
        if paused {
            if !self.paused || (self.target - master).abs() > 0.00001 {
                self.exact(master, true)?;
            }
        } else if self.paused {
            self.set_paused(false)?;
        } else if self.initial_ready && self.adjusted.elapsed() >= Duration::from_millis(250) {
            let error = master - self.position;
            if error.abs() > 0.15 {
                self.exact(master, false)?;
            } else {
                let speed = self.speed * (1. + error * 0.5).clamp(0.95, 1.05);
                self.player.command(&["set", "speed", &speed.to_string()])?;
                self.adjusted = Instant::now();
            }
        }
        Ok(())
    }
}
