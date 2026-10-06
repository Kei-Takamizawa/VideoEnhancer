"""Verify three real worker crashes against an uninterrupted 3-minute conversion."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import psutil

from videoenhancer.jobs.store import JobStore, add_job

from videoenhancer.config import executable
from videoenhancer.media.decode import read_exact
from videoenhancer.media.probe import probe


def _worker(home: Path) -> int:
    from videoenhancer.schedule.controller import run_queue

    run_queue(home=home, ignore_schedule=True)
    return 0


def _start_worker(home: Path, log: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["VE_HOME"] = str(home)
    env["PYTHONUNBUFFERED"] = "1"
    with log.open("wb") as stream:
        return subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker", str(home)],
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )


def _actual_worker_pid(process: subprocess.Popen) -> int:
    """Resolve the real Python process beneath a Windows venv launcher."""
    parent = psutil.Process(process.pid)
    for child in parent.children(recursive=True):
        try:
            arguments = child.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if "--worker" in arguments and any(Path(a).name == Path(__file__).name for a in arguments):
            return child.pid
    return process.pid


def _hard_kill(process: subprocess.Popen, pid: int) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
    else:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    process.wait(timeout=15)


def _wait_success(process: subprocess.Popen, log: Path) -> None:
    code = process.wait(timeout=600)
    if code:
        raise RuntimeError(
            f"Worker exited {code}. Read {log}:\n{log.read_text(errors='replace')[-4000:]}"
        )


def _wait_active_segment(
    process: subprocess.Popen,
    store: JobStore,
    job_id: str,
    minimum_done: int,
    log: Path,
) -> dict[str, Any]:
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Worker exited before the crash point. Read {log}.")
        manifest = store.load(job_id)
        done = sum(segment["state"] == "done" for segment in manifest["segments"])
        active = next((s for s in manifest["segments"] if s["state"] == "running"), None)
        files = [
            {"name": path.name, "bytes": path.stat().st_size}
            for path in store.job_dir(job_id).glob("seg_*.tmp.*")
            if path.exists() and path.stat().st_size > 4096
        ]
        if active is not None and done >= minimum_done and files:
            return {
                "segment_index": active["index"],
                "done_segments": done,
                "temporary_files": files,
            }
        time.sleep(0.02)
    raise TimeoutError(f"No segment reached the requested crash point; read {log}.")


def _generate(path: Path) -> None:
    command = [
        executable("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x180:rate=30,noise=alls=4:allf=t+u:all_seed=7",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000",
        "-t",
        "180",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-g",
        "60",
        "-bf",
        "0",
        "-threads",
        "2",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(path),
    ]
    subprocess.run(command, check=True, timeout=120)


def _compare(baseline: Path, resumed: Path, backend: str) -> dict[str, Any]:
    original, actual = probe(baseline, count_frames=True), probe(resumed, count_frames=True)
    if original.frame_count != actual.frame_count:
        raise AssertionError(
            f"Frame counts differ: {original.frame_count} vs {actual.frame_count}."
        )
    depth = original.bit_depth
    pixel_format = "yuv420p10le" if depth > 8 else "yuv420p"
    processes = [
        subprocess.Popen(
            [
                executable("ffmpeg"),
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-an",
                "-pix_fmt",
                pixel_format,
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for path in (baseline, resumed)
    ]
    pixels = original.width * original.height
    frame_size = pixels * 3 // 2 * (2 if depth > 8 else 1)
    identical = 0
    minimum_psnr = float("inf")
    digest = hashlib.sha256()
    try:
        for index in range(original.frame_count):
            data = [read_exact(p.stdout, frame_size) for p in processes]
            if any(len(frame) != frame_size for frame in data):
                raise AssertionError(f"Incomplete decode at output frame {index}.")
            hashes = [hashlib.sha256(frame).digest() for frame in data]
            digest.update(hashes[0])
            if hashes[0] == hashes[1]:
                identical += 1
            elif backend == "cpu":
                raise AssertionError(f"CPU per-frame hashes differ at output frame {index}.")
            else:
                arrays = [
                    np.frombuffer(frame, dtype=np.uint16 if depth > 8 else np.uint8).astype(
                        np.float64
                    )
                    for frame in data
                ]
                mse = float(np.mean((arrays[0] - arrays[1]) ** 2))
                psnr = float(10 * np.log10(((1 << depth) - 1) ** 2 / mse))
                minimum_psnr = min(minimum_psnr, psnr)
                if psnr < 50:
                    raise AssertionError(f"GPU frame {index}: PSNR {psnr:.3f} dB < 50 dB.")
        for process in processes:
            assert process.stdout is not None
            if process.stdout.read(1):
                raise AssertionError("Decoded more frames than ffprobe reported.")
            _, stderr = process.communicate(timeout=30)
            if process.returncode:
                raise RuntimeError(stderr.decode(errors="replace"))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()
    return {
        "output_frames": original.frame_count,
        "comparison_bit_depth": depth,
        "identical_frame_hashes": identical,
        "all_frames_identical": identical == original.frame_count,
        "minimum_frame_psnr_db": None if minimum_psnr == float("inf") else minimum_psnr,
        "psnr_note": "Infinite for identical frames; null minimum means every frame is identical.",
        "baseline_frame_hashes_digest": digest.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--work-dir", type=Path, default=Path(".ve-home/resume"))
    parser.add_argument("--report-dir", type=Path, default=Path(".ve-home/reports"))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return _worker(args.worker)
    started = time.monotonic()
    run_dir = args.work_dir.resolve() / f"{args.backend}-{uuid.uuid4().hex[:10]}"
    run_dir.mkdir(parents=True)
    report: dict[str, Any] = {
        "status": "FAIL",
        "backend": args.backend,
        "seed": args.seed,
        "work_dir": str(run_dir),
        "crashes": [],
    }
    active: subprocess.Popen | None = None
    try:
        source = run_dir / "three_minutes.mp4"
        _generate(source)
        source_info = probe(source, count_frames=True)
        if source_info.frame_count != 5400:
            raise AssertionError(f"Expected 5400 source frames, got {source_info.frame_count}.")
        settings = {
            "backend": args.backend,
            "preset": "p0-test",
            "short_side": "keep",
            "fps": "2x",
            "codec": "h264" if args.backend == "cpu" else "hevc",
            "lossless": True,
            "keep_segments": False,
        }
        baseline_home, resumed_home = run_dir / "baseline_home", run_dir / "resumed_home"
        baseline = add_job(source, settings, run_dir / "baseline.mp4", home=baseline_home)
        initial = copy.deepcopy(baseline)
        store = JobStore(resumed_home)
        initial.update(id=uuid.uuid4().hex, output=str(run_dir / "resumed.mp4"))
        store.save(initial)
        if len(initial["segments"]) < 3:
            raise AssertionError("The 3-minute input must contain at least 3 segments.")
        report.update(
            input_frames=5400,
            expected_output_frames=10800,
            segments=len(initial["segments"]),
            analysis_seconds=baseline["analysis_seconds"],
        )
        print(f"[{args.backend}] Baseline: {len(initial['segments'])} segments", flush=True)
        log = run_dir / "baseline_worker.log"
        active = _start_worker(baseline_home, log)
        _wait_success(active, log)
        active = None
        if JobStore(baseline_home).load(baseline["id"])["state"] != "done":
            raise AssertionError("The baseline worker did not complete its job.")
        generator = random.Random(args.seed)
        for point in range(3):
            log = run_dir / f"crash_worker_{point}.log"
            active = _start_worker(resumed_home, log)
            checkpoint = _wait_active_segment(active, store, initial["id"], point, log)
            delay = generator.uniform(0.25, 1.0)
            time.sleep(delay)
            current = store.load(initial["id"])
            if not any(s["state"] == "running" for s in current["segments"]):
                raise AssertionError(
                    "The crash trigger missed active processing; rerun with another seed."
                )
            pid = _actual_worker_pid(active)
            checkpoint.update(worker_pid=pid, launcher_pid=active.pid, random_delay_seconds=delay)
            _hard_kill(active, pid)
            active = None
            report["crashes"].append(checkpoint)
            print(
                f"[{args.backend}] Hard crash {point + 1}: segment {checkpoint['segment_index']}, "
                f"delay {delay:.3f}s, PID {pid}",
                flush=True,
            )
        log = run_dir / "final_worker.log"
        active = _start_worker(resumed_home, log)
        _wait_success(active, log)
        active = None
        final = store.load(initial["id"])
        if final["state"] != "done":
            raise AssertionError(f"Resumed job state: {final['state']}.")
        comparison = _compare(Path(baseline["output"]), Path(final["output"]), args.backend)
        if comparison["output_frames"] != 10800:
            raise AssertionError("The final output does not have exactly 2*N frames.")
        temporary = [
            str(path)
            for home in (baseline_home, resumed_home)
            for path in home.rglob("*")
            if path.is_file() and (".tmp" in path.name or ".raw." in path.name)
        ]
        if temporary:
            raise AssertionError(f"Temporary files remain: {temporary}.")
        report.update(comparison, temporary_files=temporary, status="PASS")
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        print(report["error"], file=sys.stderr, flush=True)
    finally:
        if active is not None and active.poll() is None:
            _hard_kill(active, _actual_worker_pid(active))
        report["wall_seconds"] = time.monotonic() - started
        args.report_dir.mkdir(parents=True, exist_ok=True)
        destination = args.report_dir / f"resume_{args.backend}.json"
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Resume verification {report['status']}: {destination.resolve()}", flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
