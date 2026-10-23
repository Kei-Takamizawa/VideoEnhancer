use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::os::windows::process::CommandExt;
use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};
use windows::Win32::{
    Foundation::CloseHandle,
    System::Threading::{GetExitCodeProcess, OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION},
};

pub type Result<T> = std::result::Result<T, String>;
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Connection {
    pub port: u16,
    pub token: String,
    pub pid: u32,
    pub base_url: String,
}
pub fn parse_connection(bytes: &[u8]) -> Result<Connection> {
    let data: Value = serde_json::from_slice(bytes).map_err(|e| e.to_string())?;
    let port = data["port"]
        .as_u64()
        .filter(|v| *v > 0 && *v <= 65535)
        .ok_or("Invalid engine port")? as u16;
    let token = data["token"]
        .as_str()
        .filter(|s| !s.is_empty() && s.len() <= 4096)
        .ok_or("Invalid engine token")?
        .to_owned();
    let pid = data["pid"]
        .as_u64()
        .filter(|p| *p > 0 && *p <= u32::MAX as u64)
        .ok_or("Invalid engine PID")? as u32;
    Ok(Connection {
        port,
        token,
        pid,
        base_url: format!("http://127.0.0.1:{port}/v1"),
    })
}
pub fn client() -> Result<reqwest::blocking::Client> {
    reqwest::blocking::Client::builder()
        .no_proxy()
        .timeout(Duration::from_secs(10))
        .build()
        .map_err(|e| e.to_string())
}
pub fn request(
    connection: &Connection,
    route: &str,
    method: &str,
    body: Option<&Value>,
) -> Result<Value> {
    let method = method
        .parse::<reqwest::Method>()
        .map_err(|e| e.to_string())?;
    let mut request = client()?
        .request(method, format!("{}/{route}", connection.base_url))
        .timeout(Duration::from_secs(if route == "shutdown" {
            20
        } else {
            5
        }))
        .bearer_auth(&connection.token);
    if let Some(body) = body {
        request = request.json(body);
    }
    let response = request.send().map_err(|e| e.to_string())?;
    let status = response.status();
    let data: Value = response.json().map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(data["error"]
            .as_str()
            .unwrap_or("Engine request failed")
            .to_owned());
    }
    Ok(data)
}
pub fn root() -> Result<PathBuf> {
    if let Some(root) = std::env::var_os("VE_ENGINE_ROOT") {
        return Ok(root.into());
    }
    let exe = std::env::current_exe().map_err(|e| e.to_string())?;
    let location = exe
        .parent()
        .ok_or("Executable folder missing")?
        .join("engine-location.json");
    if location.exists() {
        let value: Value = serde_json::from_slice(&fs::read(location).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
        return Ok(PathBuf::from(
            value["root"].as_str().ok_or("Invalid engine location")?,
        ));
    }
    if cfg!(debug_assertions) {
        Ok(Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../..")
            .canonicalize()
            .map_err(|e| e.to_string())?)
    } else {
        Err("engine-location.json is missing beside VideoEnhancer.exe".into())
    }
}
pub fn python(root: &Path) -> PathBuf {
    let configured = std::env::var_os("VE_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join(".venv/Scripts/python.exe"));
    let windowless = configured.with_file_name("pythonw.exe");
    if windowless.is_file() {
        windowless
    } else {
        configured
    }
}
pub fn reported_home_matches(health: &Value, home: &Path) -> bool {
    let Some(reported) = health["home"]
        .as_str()
        .map(Path::new)
        .filter(|p| p.is_absolute())
    else {
        return false;
    };
    match (reported.canonicalize(), home.canonicalize()) {
        (Ok(reported), Ok(expected)) => reported == expected,
        _ => false,
    }
}
pub fn start(home: &Path, hold: bool) -> Result<Connection> {
    let discovery = home.join("serve.json");
    if let Ok(bytes) = fs::read(&discovery) {
        if let Ok(connection) = parse_connection(&bytes) {
            if let Ok(health) = request(&connection, "health", "GET", None) {
                if reported_home_matches(&health, home) {
                    return Ok(connection);
                }
            }
        }
    }
    fs::create_dir_all(home).map_err(|e| e.to_string())?;
    let root = root()?;
    let python = python(&root);
    let log = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(home.join("service-start.log"))
        .map_err(|e| e.to_string())?;
    Command::new(python)
        .args(["-m", "videoenhancer.cli", "serve"])
        .current_dir(root)
        .env("VE_HOME", home)
        .env("VE_STARTUP_JSON_NOTICE", crate::storage::startup_notice())
        .env("VE_STORAGE_MOVE_HOLD", if hold { "1" } else { "0" })
        .creation_flags(0x08000000 | 0x00000008 | 0x00000200)
        .stdin(Stdio::null())
        .stdout(Stdio::from(log.try_clone().map_err(|e| e.to_string())?))
        .stderr(Stdio::from(log))
        .spawn()
        .map_err(|e| format!("The engine could not start: {e}. Check VE_PYTHON."))?;
    let deadline = Instant::now() + Duration::from_secs(30);
    while Instant::now() < deadline {
        thread::sleep(Duration::from_millis(200));
        if let Ok(bytes) = fs::read(&discovery) {
            if let Ok(connection) = parse_connection(&bytes) {
                if let Ok(health) = request(&connection, "health", "GET", None) {
                    if reported_home_matches(&health, home) {
                        return Ok(connection);
                    }
                }
            }
        }
    }
    Err("The engine did not become reachable. Check service-start.log, then Retry.".into())
}
pub fn alive(pid: u32) -> bool {
    unsafe {
        match OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid) {
            Ok(handle) => {
                let mut code = 0;
                let running = GetExitCodeProcess(handle, &mut code).is_ok() && code == 259;
                let _ = CloseHandle(handle);
                running
            }
            Err(_) => false,
        }
    }
}
pub fn stop(connection: &Connection) -> Result<()> {
    request(connection, "shutdown", "POST", Some(&json!({})))?;
    let deadline = Instant::now() + Duration::from_secs(20);
    while Instant::now() < deadline {
        if !alive(connection.pid) {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err("The engine could not stop cleanly. Retry Quit.".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn healthy_home_requires_an_existing_absolute_reported_path() {
        let home = std::env::temp_dir().join(format!("ve-health-home-{}", std::process::id()));
        fs::create_dir_all(&home).unwrap();
        assert!(reported_home_matches(&json!({"home":home}), &home));
        for health in [json!({}), json!({"home":""}), json!({"home":"relative"})] {
            assert!(!reported_home_matches(&health, &home));
        }
        fs::remove_dir(&home).unwrap();
        assert!(!reported_home_matches(&json!({"home":home}), &home));
    }
    #[test]
    fn discovery_validation() {
        assert!(parse_connection(br#"{"port":1,"pid":1,"token":"ok"}"#).is_ok());
        for raw in [
            br#"{"port":0,"pid":1,"token":"ok"}"#.as_slice(),
            br#"{"port":65536,"pid":1,"token":"ok"}"#,
            br#"{"port":2,"pid":0,"token":"ok"}"#,
            br#"{"port":2,"pid":1,"token":""}"#,
            b"torn",
        ] {
            assert!(parse_connection(raw).is_err());
        }
    }
}
