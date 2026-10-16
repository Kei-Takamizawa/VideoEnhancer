"""One cumulative active-part forecast shared by snapshots and progress packets."""

from typing import Any

from videoenhancer.estimate.model import predict_segment


def live_job(job: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    live = dict(progress)
    active = next((part for part in job.get("segments", []) if part["state"] == "running"), None)
    result = {**job, "progress": live}
    if not active or live.get("segment") != active["index"] or live.get("phase") == "finalizing":
        return result
    count = max(1, active["end"] - active["start"])
    frames = min(count, max(0, float(live.get("frames_done", 0))))
    elapsed = max(0, float(live.get("elapsed_seconds", 0)))
    profile = {
        key: value
        for key, value in (job.get("machine_profile") or {}).items()
        if key != "live_seconds_per_frame"
    }
    prediction = predict_segment(
        job["media"], job["settings"], count, profile, float(job.get("correction_factor", 1))
    )
    predicted_rate = count / max(0.001, prediction)
    observed_rate = frames / elapsed if elapsed > 0 else 0
    # Start with the prediction; either maturity threshold completes the blend.
    weight = min(1, max(frames / count / 0.2, elapsed / 15)) if observed_rate else 0
    rate = (1 - weight) * predicted_rate + weight * observed_rate
    live["fps"] = rate
    live["cumulative_fps"] = observed_rate
    live["rate_blend"] = weight
    if rate > 0:
        result["machine_profile"] = {**profile, "live_seconds_per_frame": 1 / rate}
    return result
