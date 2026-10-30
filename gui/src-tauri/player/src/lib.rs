//! The only commands accepted from the embedded controls. Paths belong to the
//! trusted parent's bootstrap, and are never accepted from the controls page.
use serde::{Deserialize, Serialize};

/// Keep Enhanced underneath Original so independent clip rasterization cannot
/// expose a seam at fractional display scales. Coordinates are native pixels.
pub fn divider_clips(original_width: u32, divider: f32) -> (f32, f32) {
    (0., original_width as f32 * divider)
}

#[cfg(test)]
mod divider_tests {
    #[test]
    fn divider_has_full_underlay_and_correct_original_edge() {
        for (video, original) in [(1920, 1280), (2560, 1920), (1080, 720), (720, 1920)] {
            for scale in [0.125, 1. / 3., 0.5, 627. / 1080., 1., 1.75, 4.] {
                for offset in [-537.25, 0., 71.75] {
                    for i in 0..=1000 {
                        let fraction = i as f32 / 1000.;
                        let (after, before) = super::divider_clips(original, fraction);
                        // The full underlay covers pixels even if Original's
                        // independently rasterized edge rounds down.
                        assert_eq!(after, 0.);
                        let expected_edge = offset + video as f32 * fraction * scale;
                        let before_screen =
                            offset + before * (scale * video as f32 / original as f32);
                        assert!((expected_edge - before_screen).abs() < 0.01);
                    }
                }
            }
        }
    }
}
use std::{collections::HashMap, path::PathBuf};

pub const VERSION: u32 = 1;
pub const MAX_MESSAGE: usize = 16 * 1024;

/// Native acknowledgement and playback restart are independent events.
#[derive(Debug, Default)]
pub struct FrameCompletion {
    pub acknowledged: bool,
    restarted: bool,
}
impl FrameCompletion {
    pub fn observe_restart(&mut self) {
        self.restarted = true;
    }
    pub fn ready(&self, follower_aligned: bool) -> bool {
        self.acknowledged && self.restarted && follower_aligned
    }
}

#[cfg(test)]
mod completion_tests {
    use super::FrameCompletion;

    #[test]
    fn restart_before_ack_is_retained_until_follower_catches_up() {
        let mut completion = FrameCompletion::default();
        completion.observe_restart();
        assert!(!completion.ready(true));
        completion.acknowledged = true;
        assert!(!completion.ready(false));
        assert!(completion.ready(true));
    }

    #[test]
    fn acknowledgement_without_restart_cannot_complete_a_seek() {
        let mut completion = FrameCompletion {
            acknowledged: true,
            ..Default::default()
        };
        assert!(!completion.ready(true));
        completion.observe_restart();
        assert!(!completion.ready(false));
        assert!(completion.ready(true));
    }
}

/// A result is always addressed to the originating request, including errors.
pub fn response(id: u64, result: Result<serde_json::Value, String>) -> serde_json::Value {
    match result {
        Ok(value) => serde_json::json!({"version":VERSION,"reply":id,"result":value}),
        Err(error) => serde_json::json!({"version":VERSION,"reply":id,"error":error}),
    }
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub version: u32,
    pub id: u64,
    pub command: Command,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "camelCase", deny_unknown_fields)]
pub enum Command {
    #[cfg(feature = "test-faults")]
    TestClock,
    #[cfg(feature = "test-faults")]
    TestSeam {
        enabled: bool,
    },
    #[cfg(feature = "test-faults")]
    TestReport {
        result: serde_json::Value,
    },
    #[cfg(feature = "test-faults")]
    SelfCapture {
        name: String,
    },
    #[cfg(feature = "test-faults")]
    TestUi {
        action: String,
    },
    Open {
        handle: String,
    },
    Close,
    Cursor {
        hidden: bool,
    },
    Pause {
        paused: bool,
    },
    Seek {
        seconds: f64,
    },
    Step {
        forward: bool,
    },
    Speed {
        rate: f64,
    },
    Volume {
        percent: f64,
    },
    Mute {
        muted: bool,
    },
    Fullscreen {
        enabled: bool,
    },
    Transform {
        scale: f64,
        x: f64,
        y: f64,
    },
    BeforeAfter {
        enabled: bool,
    },
    Divider {
        fraction: f64,
        #[cfg(feature = "test-faults")]
        #[serde(default)]
        input_ms: Option<f64>,
    },
    Preview {
        seconds: f64,
        generation: u64,
    },
}

impl Request {
    pub fn parse(raw: &str) -> Result<Self, String> {
        if raw.len() > MAX_MESSAGE {
            return Err("Player message is too large.".into());
        }
        let request: Self = serde_json::from_str(raw).map_err(|_| "Invalid player request.")?;
        if request.version != VERSION || request.id == 0 {
            return Err("Unsupported player protocol.".into());
        }
        let valid = match &request.command {
            #[cfg(feature = "test-faults")]
            Command::TestClock | Command::TestReport { .. } => true,
            #[cfg(feature = "test-faults")]
            Command::TestSeam { .. } => true,
            #[cfg(feature = "test-faults")]
            Command::SelfCapture { name } => valid_handle(name),
            #[cfg(feature = "test-faults")]
            Command::TestUi { action } => [
                "show",
                "blur",
                "preview",
                "help",
                "details",
                "speed",
                "before",
                "letterbox",
                "mockup",
                "portrait",
                "mockupPortrait",
                "mockupPlay",
                "mockupHover",
                "mockupBefore",
                "benchmark",
                "inspect",
                "leavePreview",
                "mockupLeave",
                "zoom",
                "mockupZoom",
                "clean",
            ]
            .contains(&action.as_str()),
            Command::Open { handle } => valid_handle(handle),
            Command::Seek { seconds } | Command::Preview { seconds, .. } => {
                seconds.is_finite() && (0.0..=864000.0).contains(seconds)
            }
            Command::Speed { rate } => rate.is_finite() && (0.25..=4.0).contains(rate),
            Command::Volume { percent } => percent.is_finite() && (0.0..=100.0).contains(percent),
            Command::Divider { fraction, .. } => {
                fraction.is_finite() && (0.0..=1.0).contains(fraction)
            }
            Command::Transform { scale, x, y } => {
                scale.is_finite()
                    && (1.0..=8.0).contains(scale)
                    && x.is_finite()
                    && y.is_finite()
                    && x.abs() <= 8.0
                    && y.abs() <= 8.0
            }
            _ => true,
        };
        if !valid {
            return Err("Player argument is out of range.".into());
        }
        Ok(request)
    }
}

pub fn valid_handle(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'-' || c == b'_')
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Bootstrap {
    pub version: u32,
    pub owner: isize,
    pub width: u32,
    pub height: u32,
    pub x: i32,
    pub y: i32,
    pub profile: PathBuf,
    pub handles: HashMap<String, PathBuf>,
    #[serde(default)]
    pub prewarm: bool,
    #[serde(default)]
    pub original_width: u32,
    #[serde(default)]
    pub original_height: u32,
    pub output: String,
    pub original: Option<String>,
    pub title: String,
    pub video_width: u32,
    pub video_height: u32,
}
impl Bootstrap {
    pub fn resolve(&self, handle: &str) -> Result<PathBuf, String> {
        if self.version != VERSION || !valid_handle(handle) {
            return Err("Invalid media handle.".into());
        }
        let path = self.handles.get(handle).ok_or("Unknown media handle.")?;
        if !path.is_absolute() || !path.is_file() {
            return Err("This video is no longer available.".into());
        }
        path.canonicalize()
            .map_err(|_| "This video is no longer available.".into())
    }
}

/// Explicit lifecycle; the process exits on close, releasing all native modules.
#[derive(Debug, Default, PartialEq, Eq)]
pub enum Lifecycle {
    #[default]
    Dormant,
    Opening,
    Playing,
    Closed,
    Failed,
}
impl Lifecycle {
    pub fn open(&mut self) -> Result<(), String> {
        if !matches!(self, Self::Dormant | Self::Playing) {
            return Err("Player is already open.".into());
        }
        *self = Self::Opening;
        Ok(())
    }
    pub fn loaded(&mut self) -> Result<(), String> {
        if !matches!(self, Self::Opening) {
            return Err("Unexpected loaded event.".into());
        }
        *self = Self::Playing;
        Ok(())
    }
}

#[derive(Default)]
pub struct Hover {
    latest: u64,
}
impl Hover {
    pub fn request(&mut self, generation: u64) -> bool {
        if generation <= self.latest {
            return false;
        }
        self.latest = generation;
        true
    }
    pub fn current(&self, generation: u64) -> bool {
        generation == self.latest
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn prewarm_requires_an_explicit_trusted_bootstrap_flag() {
        let mut value = serde_json::json!({"version":1,"owner":0,"width":960,"height":540,"x":0,"y":0,"profile":"scratch","handles":{},"output":"output","original":null,"title":"Synthetic","video_width":1920,"video_height":1080});
        let cold: Bootstrap = serde_json::from_value(value.clone()).unwrap();
        assert!(!cold.prewarm);
        value["prewarm"] = serde_json::json!(true);
        let warm: Bootstrap = serde_json::from_value(value).unwrap();
        assert!(warm.prewarm);
    }
    #[cfg(not(feature = "test-faults"))]
    #[test]
    fn production_rejects_capture_and_test_ui_commands() {
        assert!(Request::parse(
            r#"{"version":1,"id":1,"command":{"type":"selfCapture","name":"own"}}"#
        )
        .is_err());
        assert!(Request::parse(
            r#"{"version":1,"id":1,"command":{"type":"testUi","action":"show"}}"#
        )
        .is_err());
    }
    #[cfg(not(feature = "test-faults"))]
    #[test]
    fn production_rejects_clock_reports_and_divider_instrumentation() {
        for command in [
            r#"{"type":"testClock"}"#,
            r#"{"type":"testSeam","enabled":true}"#,
            r#"{"type":"testReport","result":{}}"#,
            r#"{"type":"divider","fraction":0.5,"input_ms":10}"#,
        ] {
            assert!(
                Request::parse(&format!(r#"{{"version":1,"id":1,"command":{command}}}"#)).is_err()
            );
        }
    }
    #[cfg(feature = "test-faults")]
    #[test]
    fn capture_names_and_test_actions_cannot_escape_the_test_surface() {
        assert!(Request::parse(
            r#"{"version":1,"id":1,"command":{"type":"selfCapture","name":"../../outside"}}"#
        )
        .is_err());
        assert!(Request::parse(r#"{"version":1,"id":1,"command":{"type":"testUi","action":"execute arbitrary script"}}"#).is_err());
    }

    #[test]
    fn replies_route_out_of_order_success_and_error_to_their_callers() {
        let first =
            Request::parse(r#"{"version":1,"id":41,"command":{"type":"pause","paused":true}}"#)
                .unwrap();
        let second =
            Request::parse(r#"{"version":1,"id":42,"command":{"type":"volume","percent":30}}"#)
                .unwrap();
        let second_reply = response(second.id, Err("Unavailable".into()));
        let first_reply = response(first.id, Ok(serde_json::json!(true)));
        assert_eq!(
            second_reply,
            serde_json::json!({"version":1,"reply":42,"error":"Unavailable"})
        );
        assert_eq!(
            first_reply,
            serde_json::json!({"version":1,"reply":41,"result":true})
        );
    }
    #[test]
    fn schema_rejects_injection_versions_and_bad_numbers() {
        for command in [
            r#"{"type":"command","args":["loadfile","C:/secret"]}"#,
            r#"{"type":"open","handle":"../video"}"#,
            r#"{"type":"seek","seconds":-1}"#,
            r#"{"type":"speed","rate":100}"#,
            r#"{"type":"transform","scale":9,"x":0,"y":0}"#,
            r#"{"type":"pause","paused":true,"path":"C:/secret"}"#,
        ] {
            assert!(
                Request::parse(&format!(r#"{{"version":1,"id":7,"command":{command}}}"#)).is_err()
            );
        }
        assert!(Request::parse(r#"{"version":2,"id":1,"command":{"type":"close"}}"#).is_err());
        let request =
            Request::parse(r#"{"version":1,"id":7,"command":{"type":"seek","seconds":1.5}}"#)
                .unwrap();
        assert_eq!(request.id, 7);
        assert!(matches!(request.command, Command::Seek { seconds: 1.5 }));
    }
    #[test]
    fn hover_and_lifecycle_ignore_stale_work() {
        let mut hover = Hover::default();
        assert!(hover.request(2));
        assert!(!hover.request(1));
        assert!(!hover.current(1));
        assert!(hover.current(2));
        let mut state = Lifecycle::default();
        assert_eq!(state, Lifecycle::Dormant);
        assert!(state.loaded().is_err());
        state.open().unwrap();
        assert!(state.open().is_err());
        state.loaded().unwrap();
        assert_eq!(state, Lifecycle::Playing);
        state = Lifecycle::Closed;
        assert!(state.open().is_err());
    }
    #[test]
    fn only_session_handles_resolve_to_existing_absolute_files() {
        let folder = std::env::temp_dir().join(format!("ve-player-handles-{}", std::process::id()));
        std::fs::create_dir_all(&folder).unwrap();
        let file = folder.join("synthetic.mp4");
        std::fs::write(&file, b"synthetic handle fixture").unwrap();
        let mut boot = Bootstrap {
            version: VERSION,
            owner: 0,
            width: 320,
            height: 180,
            x: 0,
            y: 0,
            profile: folder.clone(),
            handles: HashMap::from([("output".into(), file.clone())]),
            prewarm: false,
            original_width: 0,
            original_height: 0,
            output: "output".into(),
            original: None,
            title: "Synthetic".into(),
            video_width: 320,
            video_height: 180,
        };
        assert_eq!(
            boot.resolve("output").unwrap(),
            file.canonicalize().unwrap()
        );
        for value in [
            "unknown",
            "../output",
            "C:/secret.mp4",
            "https://example.com/video",
        ] {
            assert!(boot.resolve(value).is_err());
        }
        boot.handles
            .insert("relative".into(), PathBuf::from("relative.mp4"));
        assert!(boot.resolve("relative").is_err());
        std::fs::remove_file(&file).unwrap();
        assert!(boot.resolve("output").is_err());
        std::fs::remove_dir(&folder).unwrap();
    }
}
