"""Verify a two-hour GPU job, two scheduled pauses, memory and ETA accuracy."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil

from videoenhancer.config import get_home
from videoenhancer.estimate import estimate_job
from videoenhancer.jobs.store import JobStore
from videoenhancer.media.probe import probe
from videoenhancer.schedule.windows import Schedule


def _schedule(windows: list[tuple[datetime, datetime]]) -> dict[str, Any]:
    by_date: dict[str, list[dict[str, str]]] = {}
    for start, end in windows:
        cursor = start
        while cursor < end:
            midnight = (cursor + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            boundary = min(midnight, end)
            by_date.setdefault(cursor.date().isoformat(), []).append(
                {"start": cursor.strftime("%H:%M"), "end": boundary.strftime("%H:%M")}
            )
            cursor = boundary
    return {
        "schema_version": 1,
        "enabled": True,
        "weekly": [],
        "exceptions": [{"date": day, "windows": values} for day, values in sorted(by_date.items())],
        "override_until": None,
    }


def _tree_rss(process: psutil.Process) -> int:
    total = 0
    try:
        for member in [process, *process.children(recursive=True)]:
            try:
                total += member.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return total


def _gpu() -> int | None:
    try:
        import pynvml

        pynvml.nvmlInit()
        return int(pynvml.nvmlDeviceGetMemoryInfo(pynvml.nvmlDeviceGetHandleByIndex(0)).used)
    except Exception:
        return None


def _write(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sample-seconds", type=float, default=10)
    args = parser.parse_args()
    home = get_home()
    store = JobStore(home)
    output = args.output or args.input.with_name(f"{args.input.stem}_enhanced.mp4")
    cli = [sys.executable, "-m", "videoenhancer.cli"]
    reports = home / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    report_path = reports / "soak_report.json"
    prior_report = (
        json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    )
    unfinished = [job for job in store.list_jobs() if job["state"] != "done"]
    if unfinished:
        if (
            len(unfinished) != 1
            or unfinished[0]["state"] not in {"queued", "paused"}
            or Path(unfinished[0]["input"]["path"]).resolve() != args.input.resolve()
            or Path(unfinished[0]["output"]).resolve() != output.resolve()
        ):
            parser.error("VE_HOME must contain only the matching queued or paused soak job.")
        job_id = unfinished[0]["id"]
        original = store.load(job_id)
        if prior_report.get("job_id") != job_id:
            prior_report = {}
    else:
        added = subprocess.run(
            [*cli, "--json", "add", str(args.input), "-o", str(output), "--backend", "cuda"],
            capture_output=True,
            text=True,
            check=False,
        )
        if added.returncode:
            print(added.stdout, end="")
            print(added.stderr, end="", file=sys.stderr)
            return added.returncode
        job_id = json.loads(added.stdout)["job_id"]
        original = store.load(job_id)
    initial_estimate = estimate_job(original).to_dict()
    if prior_report:
        initial_estimate = prior_report["initial_estimate"]
    if not initial_estimate["calibrated"]:
        parser.error("Run ve bench --calibrate in this VE_HOME before the soak.")
    now = datetime.now().astimezone()
    first_start = now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0)
    first_end = first_start + timedelta(minutes=15)
    if (first_end - now).total_seconds() < 300:
        first_end += timedelta(minutes=15)
    second_start = first_end + timedelta(minutes=15)
    second_end = second_start + timedelta(minutes=15)
    third_start = second_end + timedelta(minutes=15)
    windows = [
        (first_start, first_end),
        (second_start, second_end),
        (third_start, third_start + timedelta(hours=12)),
    ]
    settings = _schedule(windows)
    schedule_path = home / "schedule.json"
    saved = schedule_path.read_bytes() if schedule_path.exists() else None
    Schedule(settings)
    _write(schedule_path, settings)
    log_path = reports / "soak.log"
    samples: list[dict[str, Any]] = list(prior_report.get("samples", []))
    checkpoints: list[dict[str, Any]] = list(prior_report.get("checkpoints", []))
    seen_done = sum(s["state"] == "done" for s in original["segments"])
    estimate_at_ten_percent: float | None = prior_report.get("prediction_at_ten_percent")
    total_frames = sum(s["end"] - s["start"] for s in original["segments"])
    gpu_baseline = prior_report.get("nvml_baseline_bytes", _gpu())
    wall_offset = float(prior_report.get("wall_seconds", 0.0))
    started = time.perf_counter() - wall_offset
    print(f"Job {job_id}; initial estimate {initial_estimate['seconds']:.1f} s", flush=True)
    print(f"Windows: {windows}; report: {report_path}", flush=True)
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(
                f"\n--- soak worker restarted at {datetime.now().astimezone().isoformat()} ---\n"
            )
            log.flush()
            process = subprocess.Popen([*cli, "run"], stdout=log, stderr=subprocess.STDOUT)
            measured = psutil.Process(process.pid)
            while process.poll() is None:
                elapsed = time.perf_counter() - started
                job = store.load(job_id)
                done = [s for s in job["segments"] if s["state"] == "done"]
                completed_frames = sum(s["end"] - s["start"] for s in done)
                active = any(s["state"] == "running" for s in job["segments"])
                samples.append(
                    {
                        "elapsed_seconds": elapsed,
                        "time": datetime.now().astimezone().isoformat(),
                        "rss_bytes": _tree_rss(measured),
                        "nvml_used_bytes": _gpu(),
                        "active": active,
                        "completed_frames": completed_frames,
                    }
                )
                if len(done) != seen_done:
                    actual = sum(s.get("actual_seconds", 0) for s in done)
                    prediction = actual + estimate_job(job).seconds
                    checkpoints.append(
                        {
                            "elapsed_seconds": elapsed,
                            "completed_frames": completed_frames,
                            "fraction": completed_frames / total_frames,
                            "predicted_total_seconds": prediction,
                        }
                    )
                    if completed_frames / total_frames >= 0.1 and estimate_at_ten_percent is None:
                        estimate_at_ten_percent = prediction
                    seen_done = len(done)
                if len(samples) % 6 == 1:
                    _write(
                        reports / "soak_progress.json",
                        {
                            "job_id": job_id,
                            "elapsed_seconds": elapsed,
                            "state": job["state"],
                            "completed_frames": completed_frames,
                            "total_frames": total_frames,
                            "completed_segments": len(done),
                            "total_segments": len(job["segments"]),
                            "initial_estimate": initial_estimate,
                            "checkpoints": checkpoints,
                            "latest_sample": samples[-1],
                        },
                    )
                time.sleep(max(1, args.sample_seconds))
    finally:
        if saved is None:
            schedule_path.unlink(missing_ok=True)
        else:
            schedule_path.write_bytes(saved)
    elapsed = time.perf_counter() - started
    job = store.load(job_id)
    done = [s for s in job["segments"] if s["state"] == "done"]
    actual_total = sum(s.get("actual_seconds", 0) for s in done)
    engine_seconds = sum(s.get("stats", {}).get("seconds", 0) for s in done)
    pauses = []
    for end, restart in [(first_end, second_start), (second_end, third_start)]:
        before = [s for s in samples if datetime.fromisoformat(s["time"]) < end]
        during = [s for s in samples if end <= datetime.fromisoformat(s["time"]) < restart]
        after = [s for s in samples if datetime.fromisoformat(s["time"]) >= restart]
        last_before = before[-1]["completed_frames"] if before else 0
        pauses.append(
            bool(
                during
                and after
                and last_before > 0
                and any(not s["active"] for s in during)
                and after[-1]["completed_frames"] > last_before
            )
        )
    active_samples = [s for s in samples if s["elapsed_seconds"] >= 600 and s["active"]]
    reference, ending = active_samples[:30], active_samples[-30:]

    def growth(key: str) -> int | None:
        early = [s[key] for s in reference if s[key] is not None]
        late = [s[key] for s in ending if s[key] is not None]
        return max(late) - max(early) if early and late else None

    rss_growth, vram_growth = growth("rss_bytes"), growth("nvml_used_bytes")
    info = probe(output).to_dict() if output.is_file() else None
    expected = total_frames * 2
    initial_error = (initial_estimate["seconds"] / actual_total - 1) if actual_total else None
    corrected_error = (
        (estimate_at_ten_percent / actual_total - 1)
        if actual_total and estimate_at_ten_percent
        else None
    )
    report = {
        "job_id": job_id,
        "input": str(args.input.resolve()),
        "output": str(output.resolve()),
        "state": job["state"],
        "exit_code": process.returncode,
        "wall_seconds": elapsed,
        "processing_seconds_including_worker_and_validation": actual_total,
        "engine_seconds": engine_seconds,
        "input_fps": total_frames / engine_seconds if engine_seconds else None,
        "analysis_seconds": job["analysis_seconds"],
        "scheduled_pauses_verified": pauses,
        "schedule": settings,
        "initial_estimate": initial_estimate,
        "prediction_at_ten_percent": estimate_at_ten_percent,
        "initial_estimate_relative_error": initial_error,
        "corrected_estimate_relative_error": corrected_error,
        "rss_peak_bytes": max(s["rss_bytes"] for s in samples),
        "rss_growth_bytes": rss_growth,
        "nvml_baseline_bytes": gpu_baseline,
        "nvml_peak_bytes": max((s["nvml_used_bytes"] or 0) for s in samples),
        "vram_growth_bytes": vram_growth,
        "torch_peak_bytes": max(
            (s.get("stats", {}).get("peak_torch_vram_bytes", 0) for s in done), default=0
        ),
        "expected_output_frames": expected,
        "output_probe": info,
        "crashes": sum(s["state"] == "failed" for s in job["segments"]),
        "temp_files_remaining": len(list(store.job_dir(job_id).glob("*.tmp.*"))),
        "checkpoints": checkpoints,
        "samples": samples,
        "memory_comparison": (
            "Maximum of first/last 30 active samples after minute 10; "
            "whole worker process tree RSS; total device NVML memory."
        ),
        "log_path": str(log_path),
    }
    report["soak_pass"] = bool(
        job["state"] == "done"
        and all(pauses)
        and info
        and info["frame_count"] == expected
        and rss_growth is not None
        and rss_growth <= 200_000_000
        and vram_growth is not None
        and vram_growth <= 100_000_000
        and not report["crashes"]
    )
    report["estimate_pass"] = bool(
        initial_error is not None
        and abs(initial_error) <= 0.3
        and corrected_error is not None
        and abs(corrected_error) <= 0.15
    )
    _write(report_path, report)
    print(
        f"Report: {report_path}; soak PASS={report['soak_pass']}; "
        f"estimate PASS={report['estimate_pass']}"
    )
    return 0 if report["soak_pass"] and report["estimate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
