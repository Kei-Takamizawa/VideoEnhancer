//! Test-only QPC timing; capture is never started by this probe.
#[link(name = "kernel32")]
unsafe extern "system" {
    fn QueryPerformanceCounter(value: *mut i64) -> i32;
    fn QueryPerformanceFrequency(value: *mut i64) -> i32;
}
pub fn qpc() -> f64 {
    unsafe {
        let mut now = 0;
        let mut frequency = 0;
        assert_ne!(QueryPerformanceCounter(&mut now), 0);
        assert_ne!(QueryPerformanceFrequency(&mut frequency), 0);
        now as f64 * 1000. / frequency as f64
    }
}
pub fn receipt(message: &str) -> (f64, String) {
    if let Some(rest) = message.strip_prefix("qpc:") {
        if let Some((time, text)) = rest.split_once(':') {
            if let Ok(time) = time.parse() {
                return (time, text.into());
            }
        }
    }
    (qpc(), message.into())
}

pub unsafe fn sample(
    c: &crate::composition::Composition,
    metric: &(u64, f64, f64, f64, f64),
) -> Option<serde_json::Value> {
    let (id, input, received, begin, commit) = metric;
    // Snapshot the NEXT frame after the clip Commit, before waiting. Reading only
    // after completion would select the following frame and add a whole refresh.
    let first = c.frame_statistics().ok()?;
    let first_estimate = first.nextEstimatedFrameTime as f64 * 1000. / first.timeFrequency as f64;
    c.wait_commit().ok()?;
    let completed = qpc();
    let stats = c.frame_statistics().ok()?;
    let processed = stats.lastFrameTime as f64 * 1000. / stats.timeFrequency as f64;
    // Keep the later assigned batch frame. Never use a prediction whose deadline
    // the clip batch missed; retain the following-frame estimate in that case.
    let assigned = first_estimate.max(processed);
    let presentation = if assigned > completed {
        assigned
    } else {
        stats.nextEstimatedFrameTime as f64 * 1000. / stats.timeFrequency as f64
    };
    if presentation < completed {
        return None;
    }
    let swap = c.swap_statistics().ok();
    Some(
        serde_json::json!({"reply":id,"result":{"input_ms":input,"received_qpc_ms":received,"commit_begin_qpc_ms":begin,"commit_qpc_ms":commit,"frame_qpc_ms":processed,"next_estimated_qpc_ms":presentation,"first_estimated_qpc_ms":first_estimate,"commit_completed_qpc_ms":completed,"after_completion_next_qpc_ms":stats.nextEstimatedFrameTime as f64*1000./stats.timeFrequency as f64,"swap_sync_qpc":swap.map(|s|s.SyncQPCTime),"statistics_observed_qpc_ms":qpc()}}),
    )
}
