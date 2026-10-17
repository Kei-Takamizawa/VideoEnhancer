use crate::{engine, State};
use std::{
    io::Read,
    sync::{
        atomic::{AtomicUsize, Ordering},
        Arc, Condvar, Mutex,
    },
};
use tauri::{
    http::{Request, Response},
    Manager,
};

pub const CHUNK: u64 = 1024 * 1024;
fn chunk_size() -> u64 {
    #[cfg(feature = "e2e")]
    if let Ok(value) = std::env::var("VE_TEST_MEDIA_CHUNK_MIB") {
        if let Ok(mib @ (1 | 2 | 8)) = value.parse::<u64>() {
            return mib * 1024 * 1024;
        }
    }
    CHUNK
}
#[derive(Default)]
pub struct Fetches {
    active: Mutex<usize>,
    ready: Condvar,
    pub peak: AtomicUsize,
    pub total: AtomicUsize,
}
struct Permit<'a>(&'a Fetches);
impl Fetches {
    fn acquire(&self) -> Permit<'_> {
        let mut active = self.active.lock().unwrap_or_else(|e| e.into_inner());
        while *active >= 2 {
            active = self.ready.wait(active).unwrap_or_else(|e| e.into_inner());
        }
        *active += 1;
        self.peak.fetch_max(*active, Ordering::SeqCst);
        self.total.fetch_add(1, Ordering::SeqCst);
        Permit(self)
    }
}
impl Drop for Permit<'_> {
    fn drop(&mut self) {
        let mut active = self.0.active.lock().unwrap_or_else(|e| e.into_inner());
        *active -= 1;
        self.0.ready.notify_one();
    }
}
pub fn range(raw: Option<&str>, size: u64) -> engine::Result<(u64, u64)> {
    if size == 0 {
        return Err("Empty media".into());
    }
    let (start, end) = if let Some(raw) = raw {
        let (first, last) = raw
            .strip_prefix("bytes=")
            .and_then(|v| v.split_once('-'))
            .ok_or("Invalid range")?;
        if first.is_empty() {
            let count = last.parse::<u64>().map_err(|_| "Invalid range")?;
            if count == 0 {
                return Err("Invalid range".into());
            }
            (size.saturating_sub(count), size - 1)
        } else {
            (
                first.parse::<u64>().map_err(|_| "Invalid range")?,
                if last.is_empty() {
                    size - 1
                } else {
                    last.parse::<u64>().map_err(|_| "Invalid range")?
                },
            )
        }
    } else {
        (0, size - 1)
    };
    if start >= size || end < start {
        return Err("Range not satisfiable".into());
    }
    Ok((
        start,
        end.min(size - 1)
            .min(start.saturating_add(chunk_size() - 1)),
    ))
}
pub fn valid_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 128
        && id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}
pub fn serve(
    app: tauri::AppHandle,
    request: Request<Vec<u8>>,
    responder: tauri::UriSchemeResponder,
) {
    std::thread::spawn(move || {
        let response = (|| -> engine::Result<Response<Vec<u8>>> {
            if request.method() != "GET" && request.method() != "HEAD" {
                return Response::builder()
                    .status(405)
                    .body(vec![])
                    .map_err(|e| e.to_string());
            }
            let id = request.uri().path().trim_start_matches('/');
            if !valid_id(id) {
                return Err("Invalid job id".into());
            }
            let state = app.state::<Arc<State>>();
            let connection = state.connected()?;
            let url = format!("{}/queue/{id}/video", connection.base_url);
            let client = engine::client()?;
            let size = {
                let _permit = state.fetches.acquire();
                let head = client
                    .head(&url)
                    .bearer_auth(&connection.token)
                    .send()
                    .and_then(|r| r.error_for_status())
                    .map_err(|e| e.to_string())?;
                head.headers()
                    .get("content-length")
                    .and_then(|v| v.to_str().ok())
                    .and_then(|v| v.parse::<u64>().ok())
                    .ok_or("Invalid media length")?
            };
            let requested = request
                .headers()
                .get("range")
                .map(|v| v.to_str())
                .transpose()
                .map_err(|e| e.to_string())?;
            let (start, end) = match range(requested, size) {
                Ok(v) => v,
                Err(_) => {
                    return Response::builder()
                        .status(416)
                        .header("Content-Range", format!("bytes */{size}"))
                        .body(vec![])
                        .map_err(|e| e.to_string())
                }
            };
            let partial = requested.is_some() || end + 1 < size;
            let mut bytes = Vec::new();
            if request.method() == "GET" {
                let _permit = state.fetches.acquire();
                let mut upstream = client
                    .get(url)
                    .bearer_auth(&connection.token)
                    .header("Range", format!("bytes={start}-{end}"))
                    .send()
                    .and_then(|r| r.error_for_status())
                    .map_err(|e| e.to_string())?;
                if upstream.status() != 206 {
                    return Err("Engine ignored bounded Range request".into());
                }
                upstream
                    .by_ref()
                    .take(chunk_size() + 1)
                    .read_to_end(&mut bytes)
                    .map_err(|e| e.to_string())?;
                if bytes.len() as u64 != end - start + 1 {
                    return Err("Invalid engine media length".into());
                }
            }
            let mut response = Response::builder()
                .status(if partial { 206 } else { 200 })
                .header("Content-Type", "video/mp4")
                .header("Cache-Control", "no-store")
                .header("Content-Length", (end - start + 1).to_string())
                .header("Accept-Ranges", "bytes")
                .header("Access-Control-Allow-Origin", "http://tauri.localhost");
            if partial {
                response = response.header("Content-Range", format!("bytes {start}-{end}/{size}"));
            }
            response.body(bytes).map_err(|e| e.to_string())
        })()
        .unwrap_or_else(|error| {
            Response::builder()
                .status(502)
                .body(error.into_bytes())
                .unwrap()
        });
        responder.respond(response);
    });
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounds() {
        assert_eq!(range(Some("bytes=2-"), 10).unwrap(), (2, 9));
        assert_eq!(range(Some("bytes=-3"), 10).unwrap(), (7, 9));
        assert_eq!(range(None, 20_000_000).unwrap(), (0, CHUNK - 1));
        for v in ["bytes=9-2", "bytes=10-", "bytes=0-1,3-4", "bytes=-0"] {
            assert!(range(Some(v), 10).is_err());
        }
        assert!(!valid_id("../x"));
    }
}
