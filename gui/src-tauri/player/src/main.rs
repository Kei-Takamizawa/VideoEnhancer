#[cfg(all(windows, feature = "test-faults"))]
mod capture;
#[cfg(windows)]
mod composition;
#[cfg(windows)]
mod follower;
#[cfg(windows)]
mod host;
#[cfg(windows)]
mod mpv;
#[cfg(windows)]
mod startup;
#[cfg(all(windows, feature = "test-faults"))]
mod telemetry;
fn main() {
    #[cfg(windows)]
    if let Err(error) = host::run() {
        eprintln!("Player initialization: {error}");
        println!(
            "{}",
            serde_json::json!({"version":1,"event":"error","error":"This video can't be played here. Open it in your default player instead."})
        );
        std::process::exit(1);
    }
    #[cfg(not(windows))]
    eprintln!("The native player is available on Windows only.");
}
