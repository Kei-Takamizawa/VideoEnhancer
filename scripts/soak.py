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


def _tree_rss(pid: int) -> int:
    total = 0
    try:
        process = psutil.Process(pid)
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


def _memory_growth(records: list[dict[str, Any]], key: str, started_epoch: float) -> int | None:
    values = [
        r for r in records if r.get(key) is not None and r["timestamp"] >= started_epoch + 600
    ]
    if not values:
        return None
    first, last = values[0]["timestamp"], values[-1]["timestamp"]
    if last - first < 600:
        return None
    early = [r[key] for r in values if r["timestamp"] <= first + 300]
    late = [r[key] for r in values if r["timestamp"] >= last - 300]
    return max(late) - max(early)


def _stop_owned(process: subprocess.Popen[str]) -> None:
    """Terminate only the worker tree launched by this supervisor."""
    try:
        parent = psutil.Process(process.pid)
        descendants = parent.children(recursive=True)
        # Native controller closure reaps its Windows kill-on-close engine job.
        for child in descendants:
            try:
                command = child.cmdline()
                if "videoenhancer.cli" in command and "run" in command:
                    child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            for child in reversed(descendants):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            process.kill()
            process.wait(timeout=15)
    except psutil.NoSuchProcess:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--preset", choices=("fast", "standard"), default="fast")
    parser.add_argument("--mode", choices=("complete", "stability"), default="complete")
    parser.add_argument("--scheduled-pauses", type=int, choices=(0, 1, 2), default=2)
    parser.add_argument("--sample-seconds", type=float, default=10)
    args = parser.parse_args()
    home, cli = get_home(), [sys.executable, "-m", "videoenhancer.cli"]
    store = JobStore(home)
    if store.list_jobs():
        parser.error("Use a fresh VE_HOME; this supervisor records one uninterrupted experiment.")
    reports = home / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    report_path, log_path = reports / "soak_report.json", reports / "soak.log"
    added = subprocess.run(
        [
            *cli,
            "--json",
            "add",
            str(args.input),
            "-o",
            str(args.output),
            "--backend",
            "cuda",
            "--preset",
            args.preset,
            "--keep-segments",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if added.returncode:
        print(added.stdout + added.stderr, flush=True)
        return added.returncode
    job_id = json.loads(added.stdout)["job_id"]
    original = store.load(job_id)
    initial = estimate_job(original).to_dict()
    if not initial["calibrated"]:
        parser.error("Run ve bench --calibrate before the soak; selected models must match.")
    now = datetime.now().astimezone()
    first_start = now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0)
    first_end = first_start + timedelta(minutes=45)
    second_start, second_end = first_end + timedelta(minutes=15), first_end + timedelta(minutes=30)
    third_start = second_end + timedelta(minutes=15)
    boundaries = [(first_end, second_start), (second_end, third_start)][: args.scheduled_pauses]
    if args.scheduled_pauses == 2:
        windows = [
            (first_start, first_end),
            (second_start, second_end),
            (third_start, third_start + timedelta(days=2)),
        ]
    elif args.scheduled_pauses == 1:
        windows = [(first_start, first_end), (second_start, second_start + timedelta(days=2))]
    else:
        windows = [(first_start, first_start + timedelta(days=2))]
    settings = _schedule(windows)
    schedule = Schedule(settings)
    schedule_path = home / "schedule.json"
    _write(schedule_path, settings)
    samples: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    paused_intervals: list[list[float]] = []
    paused_start: float | None = None
    prediction_ten: float | None = None
    stop_event: dict[str, Any] | None = None
    seen_done = 0
    total_frames = sum(s["end"] - s["start"] for s in original["segments"])
    started, started_epoch = time.perf_counter(), time.time()

    def active_wall() -> float:
        paused = sum(b - a for a, b in paused_intervals)
        if paused_start is not None:
            paused += time.time() - paused_start
        return time.perf_counter() - started - paused

    def command(name: str) -> None:
        result = subprocess.run(
            [*cli, name, job_id], capture_output=True, text=True, encoding="utf-8", check=False
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    print(f"Job {job_id}; calibrated initial estimate {initial['seconds']:.1f} s", flush=True)
    print(f"Schedule {windows}; mode {args.mode}; report {report_path}", flush=True)
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen([*cli, "run"], stdout=log, stderr=subprocess.STDOUT, text=True)
        stability_finish = False
        try:
            while process.poll() is None:
                job = store.load(job_id)
                done = [s for s in job["segments"] if s["state"] == "done"]
                completed = sum(s["end"] - s["start"] for s in done)
                active = any(s["state"] == "running" for s in job["segments"])
                now = datetime.now().astimezone()
                paused = (schedule.current_interval(now) is None and not active) or job[
                    "state"
                ] == "paused"
                if paused and paused_start is None:
                    paused_start = time.time()
                elif not paused and paused_start is not None:
                    paused_intervals.append([paused_start, time.time()])
                    paused_start = None
                elapsed = time.perf_counter() - started
                samples.append(
                    {
                        "elapsed_seconds": elapsed,
                        "timestamp": time.time(),
                        "time": now.isoformat(),
                        "rss_bytes": _tree_rss(process.pid),
                        "active": active,
                        "paused": paused,
                        "completed_frames": completed,
                    }
                )
                if len(done) != seen_done:
                    prediction = active_wall() + estimate_job(job).seconds
                    checkpoints.append(
                        {
                            "elapsed_seconds": elapsed,
                            "completed_frames": completed,
                            "fraction": completed / total_frames,
                            "predicted_total_seconds": prediction,
                        }
                    )
                    if completed / total_frames >= 0.1 and prediction_ten is None:
                        prediction_ten = prediction
                    seen_done = len(done)
                # Abrupt stop during a running segment, followed by actual queue recovery.
                if (
                    args.mode == "stability"
                    and stop_event is None
                    and active_wall() >= 2700
                    and active
                ):
                    stop_event = {
                        "timestamp": time.time(),
                        "completed_frames_before": completed,
                        "running_segment": next(
                            s["index"] for s in job["segments"] if s["state"] == "running"
                        ),
                    }
                    _stop_owned(process)
                    time.sleep(5)
                    command("resume")
                    process = subprocess.Popen(
                        [*cli, "run"], stdout=log, stderr=subprocess.STDOUT, text=True
                    )
                    stop_event["restarted_timestamp"] = time.time()
                    paused_intervals.append(
                        [stop_event["timestamp"], stop_event["restarted_timestamp"]]
                    )
                pause_verified = []
                for end, restart in boundaries:
                    during = [
                        s for s in samples if end <= datetime.fromisoformat(s["time"]) < restart
                    ]
                    after = [s for s in samples if datetime.fromisoformat(s["time"]) >= restart]
                    pause_verified.append(
                        bool(
                            during
                            and after
                            and any(s["paused"] for s in during)
                            and after[-1]["completed_frames"] > during[0]["completed_frames"]
                        )
                    )
                if (
                    args.mode == "stability"
                    and active_wall() >= 3600
                    and all(pause_verified)
                    and stop_event
                    and completed > stop_event["completed_frames_before"]
                ):
                    command("pause")
                    for _ in range(30):
                        if not any(s["state"] == "running" for s in store.load(job_id)["segments"]):
                            break
                        time.sleep(1)
                    _stop_owned(process)
                    stability_finish = True
                    break
                _write(
                    reports / "soak_progress.json",
                    {
                        "job_id": job_id,
                        "mode": args.mode,
                        "elapsed_seconds": elapsed,
                        "active_wall_seconds": active_wall(),
                        "state": job["state"],
                        "completed_frames": completed,
                        "total_frames": total_frames,
                        "initial_estimate": initial,
                        "prediction_at_ten_percent": prediction_ten,
                        "scheduled_pauses_verified": pause_verified,
                        "stop_event": stop_event,
                        "latest_sample": samples[-1],
                        "checkpoints": checkpoints,
                    },
                )
                if job["state"] == "failed":
                    _stop_owned(process)
                    break
                time.sleep(max(1, args.sample_seconds))
        finally:
            if process.poll() is None:
                _stop_owned(process)
    job = store.load(job_id)
    done = [s for s in job["segments"] if s["state"] == "done"]
    completed = sum(s["end"] - s["start"] for s in done)
    memory = [r for s in done for r in s.get("stats", {}).get("memory_samples", [])]
    rss_records = [{**s, "process_rss_bytes": s["rss_bytes"]} for s in samples if s["active"]]
    growth = {
        key: _memory_growth(memory, key, started_epoch)
        for key in ("process_dedicated_gpu_bytes", "torch_reserved_bytes", "process_rss_bytes")
    }
    growth["tree_rss_bytes"] = _memory_growth(rss_records, "process_rss_bytes", started_epoch)
    actual = active_wall()
    complete = job["state"] == "done"
    info = probe(args.output).to_dict() if complete else None
    initial_error = initial["seconds"] / actual - 1 if complete else None
    ten_error = prediction_ten / actual - 1 if complete and prediction_ten else None
    engine = sum(s.get("stats", {}).get("seconds", 0) for s in done)
    report = {
        "job_id": job_id,
        "mode": args.mode,
        "preset": args.preset,
        "state": job["state"],
        "complete": complete,
        "wall_seconds": time.perf_counter() - started,
        "actual_wall_excluding_pauses_seconds": actual,
        "paused_intervals_epoch": paused_intervals,
        "clock_origin_epoch": started_epoch,
        "initial_estimate": initial,
        "prediction_at_ten_percent": prediction_ten,
        "initial_estimate_relative_error": initial_error,
        "ten_percent_estimate_relative_error": ten_error,
        "scheduled_pauses_verified": pause_verified,
        "stop_resume_verified": bool(
            stop_event and completed > stop_event["completed_frames_before"]
        ),
        "stop_event": stop_event,
        "completed_input_frames": completed,
        "total_input_frames": total_frames,
        "expected_output_frames": total_frames * 2,
        "output_probe": info,
        "engine_seconds": engine,
        "input_fps": completed / engine if engine else None,
        "raw_flag_count": sum(s.get("stats", {}).get("raw_flag_count", 0) for s in done),
        "final_flag_count": sum(s.get("stats", {}).get("final_flag_count", 0) for s in done),
        "memory_growth_bytes": growth,
        "job_memory_samples": memory,
        "memory_comparison": (
            "Maximum in first and last five-minute windows after minute 10; epoch timestamps. "
            "Engine-PID PDH/Torch/RSS and separately sampled controller-tree RSS."
        ),
        "checkpoints": checkpoints,
        "samples": samples,
        "log_path": str(log_path),
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "schedule": settings,
        "analysis_seconds_excluded": job.get("analysis_seconds"),
    }
    report["estimate_pass"] = bool(
        complete
        and initial_error is not None
        and abs(initial_error) <= 0.3
        and ten_error is not None
        and abs(ten_error) <= 0.15
    )
    memory_pass = all(
        growth[k] is not None and growth[k] <= cap
        for k, cap in (
            ("process_dedicated_gpu_bytes", 150_000_000),
            ("torch_reserved_bytes", 100_000_000),
            ("tree_rss_bytes", 200_000_000),
        )
    )
    report["soak_pass"] = bool(
        complete
        and info
        and info["frame_count"] == total_frames * 2
        and info.get("audio_streams")
        and all(pause_verified)
        and memory_pass
    )
    report["stability_pass"] = bool(
        stability_finish
        and actual >= 3600
        and all(pause_verified)
        and report["stop_resume_verified"]
    )
    _write(report_path, report)
    print(
        f"Report {report_path}: complete={complete}, soak={report['soak_pass']}, "
        f"estimate={report['estimate_pass']}, stability={report['stability_pass']}",
        flush=True,
    )
    if args.mode == "stability":
        return 0 if report["stability_pass"] else 1
    return (
        0
        if report["estimate_pass"] and (report["soak_pass"] if args.scheduled_pauses else complete)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
