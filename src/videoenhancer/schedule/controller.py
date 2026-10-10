"""Foreground queue worker with schedule-aware, resumable segments."""

from __future__ import annotations

import contextlib
import ctypes
import json
import multiprocessing
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from videoenhancer import proc
from videoenhancer.estimate.model import observe_finalization, predict_finalization
from videoenhancer.files import retry_permission
from videoenhancer.jobs.segments import expected_duration, expected_frames
from videoenhancer.jobs.store import (
    JobQuarantinedError,
    JobStore,
    require_disk_space,
    validate_input,
)
from videoenhancer.logging import get_logger, log_job_header
from videoenhancer.schedule.admission import admit_step


class Clock(Protocol):
    def now(self) -> datetime: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now().astimezone()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class SegmentResult:
    status: str  # done, aborted or failed
    stats: dict[str, Any] | None = None
    error: str | None = None
    oom: bool = False
    stalled: bool = False


@dataclass
class SegmentProgress:
    frames_done: float = 0
    step: str = "Loading model"
    memory: dict[str, Any] | None = None


class SegmentWatchdog:
    def __init__(self, predicted: float, frames: int, started: float) -> None:
        self.predicted, self.frames, self.started = predicted, max(1, frames), started
        self.last_frame = started
        self.done = 0.0
        self.result_at: float | None = None

    def progress(self, frames: float, now: float) -> None:
        if frames > self.done:
            self.done, self.last_frame = frames, now

    def reason(self, now: float) -> str | None:
        if self.result_at is not None:
            return "exit grace" if now - self.result_at >= 15 else None
        if now - self.started > 3 * self.predicted + 300:
            return "wall time"
        if not self.done and now - self.started >= 300:
            return "no first frame"
        if self.done and now - self.last_frame >= max(180, 20 * self.predicted / self.frames):
            return "no new frame"
        return None


def _bound_segment_log(path: Path) -> None:
    if path.exists() and path.stat().st_size > 1024 * 1024:
        with path.open("r+b") as stream:
            stream.seek(-1024 * 1024, os.SEEK_END)
            tail = stream.read()
            stream.seek(0)
            stream.write(tail)
            stream.truncate()


def _windows_ctypes(name: str) -> Any:
    return getattr(ctypes, name)


def _attach_windows_job(pid: int) -> int:
    """Attach the idle child to a kill-on-close job before it may launch FFmpeg."""
    from ctypes import wintypes

    class BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimit),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel = _windows_ctypes("WinDLL")("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise _windows_ctypes("WinError")(_windows_ctypes("get_last_error")())
    process_handle = None
    try:
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise _windows_ctypes("WinError")(_windows_ctypes("get_last_error")())
        process_handle = kernel.OpenProcess(0x0100 | 0x0001, False, pid)
        if not process_handle:
            raise _windows_ctypes("WinError")(_windows_ctypes("get_last_error")())
        if not kernel.AssignProcessToJobObject(job, process_handle):
            raise _windows_ctypes("WinError")(_windows_ctypes("get_last_error")())
        return int(job)
    except Exception:
        kernel.CloseHandle(job)
        raise
    finally:
        if process_handle:
            kernel.CloseHandle(process_handle)


def _close_windows_job(handle: int | None) -> None:
    if handle is not None and os.name == "nt":
        from ctypes import wintypes

        close_handle = _windows_ctypes("WinDLL")("kernel32", use_last_error=True).CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        close_handle(handle)


def _set_linux_parent_death(expected_parent_pid: int) -> None:
    """Reap the encoder process group if SIGKILL destroys its parent worker."""
    if not sys.platform.startswith("linux"):
        return
    getattr(os, "setsid")()  # noqa: B009 - Linux-only API absent from Windows typing

    def terminate_group(_signum: int, _frame: Any) -> None:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        getattr(os, "killpg")(  # noqa: B009 - Linux-only API absent from Windows typing
            getattr(os, "getpgrp")(),  # noqa: B009
            getattr(signal, "SIGKILL"),  # noqa: B009
        )

    signal.signal(signal.SIGTERM, terminate_group)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_PDEATHSIG) failed")
    if os.getppid() != expected_parent_pid:
        terminate_group(signal.SIGTERM, None)


def _redirect_child_stdout_to_stderr() -> None:
    """Keep native encoder diagnostics out of the CLI's JSON stdout."""
    if sys.stdout is None or sys.stderr is None:
        return
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    if os.name == "nt":
        from ctypes import wintypes

        kernel = _windows_ctypes("WinDLL")("kernel32", use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
        kernel.SetStdHandle.restype = wintypes.BOOL
        stderr_handle = kernel.GetStdHandle(0xFFFFFFF4)  # STD_ERROR_HANDLE
        if not kernel.SetStdHandle(0xFFFFFFF5, stderr_handle):  # STD_OUTPUT_HANDLE
            raise _windows_ctypes("WinError")(_windows_ctypes("get_last_error")())


def _child_run(
    manifest: dict[str, Any],
    segment: dict[str, Any],
    output: str,
    batch_size: int,
    parent_pid: int,
    start_event: Any,
    abort_event: Any,
    sender: Any,
) -> None:
    log_path = Path(output).parent / "logs" / f"seg_{int(segment.get('index', 0)):05d}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_stream = log_path.open("a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log_stream
    os.dup2(log_stream.fileno(), 1)
    os.dup2(log_stream.fileno(), 2)
    heartbeat_stop = threading.Event()
    state = SegmentProgress()
    send_lock = threading.Lock()

    def send(value: Any) -> None:
        with send_lock:
            sender.send(value)

    def heartbeat() -> None:
        while not heartbeat_stop.wait(2):
            try:
                send(SegmentProgress(state.frames_done, state.step, state.memory))
            except (OSError, EOFError):
                return

    def progress(value: dict[str, Any]) -> None:
        if "memory" in value:
            state.memory = value["memory"]
        else:
            state.frames_done = value["frames_done"]
            state.step = value["step"]

    heart = threading.Thread(target=heartbeat, name="ve-progress", daemon=True)
    try:
        _redirect_child_stdout_to_stderr()
        _set_linux_parent_death(parent_pid)
        if not start_event.wait(timeout=10):
            return
        print(f"Segment child executable: {sys.executable}", flush=True)
        send(state)
        heart.start()
        from videoenhancer.pipeline.runner import process_segment

        stats = process_segment(
            manifest,
            segment,
            Path(output),
            abort_event.is_set,
            batch_size=batch_size,
            progress=progress,
        )
        send(SegmentResult("done", stats=stats))
    except InterruptedError:
        send(SegmentResult("aborted"))
    except Exception as error:
        name = type(error).__name__
        oom = "outofmemory" in name.lower() or "out of memory" in str(error).lower()
        import traceback

        traceback.print_exc()
        send(SegmentResult("failed", error=f"{name}: {error}", oom=oom))
    finally:
        heartbeat_stop.set()
        if heart.ident is not None:
            heart.join(timeout=3)
        sender.close()
        log_stream.flush()


def _kill_process_tree(pid: int) -> None:
    if os.name == "nt":
        try:
            proc.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        return
    try:
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGKILL)
            return
    except ProcessLookupError:
        return
    try:
        import psutil

        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except (ImportError, OSError):
        pass


class ProcessExecutor:
    """Run one segment in a child so a hung encoder can be killed promptly."""

    def __init__(
        self,
        clock: Clock | None = None,
        progress: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
        context: Any = None,
    ) -> None:
        self.clock = clock or SystemClock()
        self.progress = progress
        self.context = context

    def run(
        self,
        manifest: dict[str, Any],
        segment: dict[str, Any],
        output: Path,
        abort: Callable[[], bool],
        *,
        batch_size: int,
    ) -> SegmentResult:
        context = self.context or multiprocessing.get_context("spawn")
        if os.name == "nt" and Path(sys.executable).name.lower() == "pythonw.exe":
            context.set_executable(sys.executable)
        start_event = context.Event()
        event = context.Event()
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=_child_run,
            args=(
                manifest,
                segment,
                str(output),
                batch_size,
                os.getpid(),
                start_event,
                event,
                sender,
            ),
            daemon=False,
        )
        process.start()
        sender.close()
        job_handle: int | None = None
        aborted = False
        abort_started = 0.0
        forced = False
        received_result: Any = None
        pipe_open = True

        def now_seconds() -> float:
            return self.clock.now().timestamp()

        started = now_seconds()
        watchdog = SegmentWatchdog(
            float(segment.get("predicted_seconds", 180)),
            int(segment.get("end", 1) - segment.get("start", 0)),
            started,
        )
        last_log_trim = started
        last_manifest = started - 10
        log_path = output.parent / "logs" / f"seg_{int(segment.get('index', 0)):05d}.log"
        try:
            if os.name == "nt" and process.pid is not None:
                try:
                    job_handle = _attach_windows_job(process.pid)
                except OSError as error:
                    return SegmentResult(
                        "failed",
                        error=f"Cannot protect segment subprocesses from orphaning: {error}",
                    )
            start_event.set()
            while process.is_alive():
                # Drain before joining: a result larger than the pipe buffer blocks
                # the child in send(), so waiting for its exit first deadlocks.
                now = now_seconds()
                while pipe_open:
                    try:
                        if not receiver.poll():
                            break
                        message = receiver.recv()
                    except (EOFError, OSError):
                        pipe_open = False
                        break
                    if isinstance(message, SegmentProgress):
                        watchdog.progress(message.frames_done, now)
                        elapsed = max(0.001, now - started)
                        live = dict(
                            phase="processing",
                            step=message.step,
                            frames_done=message.frames_done,
                            fps=message.frames_done / elapsed,
                            elapsed_seconds=elapsed,
                            segment=segment.get("index", 0),
                            memory=message.memory,
                        )
                        if self.progress is not None:
                            self.progress(manifest, live)
                        if "id" in manifest and now - last_manifest >= 10:
                            store = JobStore(output.parent.parent.parent)
                            latest = store.load(manifest["id"])
                            latest["progress"] = live
                            store.save(latest)
                            last_manifest = now
                    elif isinstance(message, SegmentResult):
                        received_result = message
                        watchdog.result_at = now
                if now - last_log_trim >= 1:
                    _bound_segment_log(log_path)
                    last_log_trim = now
                stalled = watchdog.reason(now)
                if stalled:
                    if process.pid is not None:
                        _kill_process_tree(process.pid)
                    if process.is_alive():
                        process.terminate()
                    process.join(timeout=1)
                    if stalled == "exit grace" and isinstance(received_result, SegmentResult):
                        return received_result
                    return SegmentResult("failed", error=f"Watchdog: {stalled}", stalled=True)
                if abort() and not aborted:
                    aborted = True
                    abort_started = now
                    event.set()
                if aborted and not forced and now - abort_started >= 7:
                    forced = True
                    if process.pid is not None:
                        _kill_process_tree(process.pid)
                    if process.is_alive():
                        process.terminate()
                process.join(timeout=0.25)
            if aborted:
                return SegmentResult("aborted")
            if isinstance(received_result, SegmentResult):
                return received_result
            if pipe_open and receiver.poll():
                result = receiver.recv()
                if isinstance(result, SegmentResult):
                    return result
            return SegmentResult(
                "failed", error=f"Worker exited with code {process.exitcode}; retry the segment"
            )
        finally:
            if process.is_alive():
                event.set()
                process.join(timeout=7)
                if process.is_alive():
                    if process.pid is not None:
                        _kill_process_tree(process.pid)
                    if process.is_alive():
                        process.terminate()
                    process.join(timeout=1)
            receiver.close()
            _close_windows_job(job_handle)
            _bound_segment_log(log_path)


@contextlib.contextmanager
def _worker_lock(home: Path) -> Iterator[None]:
    """Hold an OS lock to prevent two workers processing the same queue."""
    home.mkdir(parents=True, exist_ok=True)
    lock_path = home / "worker.lock"
    try:
        lock_file = lock_path.open("a+b")
    except OSError as error:
        raise RuntimeError("Another VideoEnhancer worker is already running") from error
    with lock_file as lock:
        try:
            lock.seek(0)
            if not lock.read(1):
                lock.seek(0)
                lock.write(b"0")
                lock.flush()
        except OSError as error:
            raise RuntimeError("Another VideoEnhancer worker is already running") from error
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Another VideoEnhancer worker is already running") from error
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def _prevent_sleep() -> Iterator[None]:
    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    try:
        yield
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def _utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC)


def _cleanup_temps(job_dir: Path) -> None:
    for path in job_dir.glob("seg_*.tmp.*"):
        path.unlink(missing_ok=True)


def _video_contract_valid(manifest: dict[str, Any], observed: Any) -> bool:
    from videoenhancer.media.timing import output_rate, output_size

    width, height = output_size(manifest["settings"], manifest["media"])
    expected_rate = output_rate(manifest["settings"], manifest["media"])
    observed_rate = Fraction(str(observed.average_fps))
    rate_error = abs(float(observed_rate - expected_rate))
    return (
        int(observed.width) == width
        and int(observed.height) == height
        and observed.codec == manifest["settings"].get("codec", "hevc")
        and rate_error <= max(0.001, float(expected_rate) * 0.0001)
        and int(observed.rotation) == 0
    )


def segment_file_valid(manifest: dict[str, Any], segment: dict[str, Any], path: Path) -> bool:
    from videoenhancer.media.probe import probe

    if not path.is_file():
        return False
    try:
        observed = probe(path, count_packets=True)
        count = int(observed.frame_count)
        target = expected_duration(manifest, segment)
        tolerance = 1.1 * target / max(1, expected_frames(manifest, segment))
        return (
            count == expected_frames(manifest, segment)
            and abs(float(observed.duration) - target) <= tolerance
            and _video_contract_valid(manifest, observed)
        )
    except (OSError, ValueError, ZeroDivisionError, AttributeError, subprocess.CalledProcessError):
        return False


def _assembled_file_valid(manifest: dict[str, Any], path: Path) -> bool:
    from videoenhancer.media.mux import _audio_duration_matches
    from videoenhancer.media.probe import probe

    if not path.is_file():
        return False
    try:
        observed = probe(path, count_packets=True)
        expected_count = sum(expected_frames(manifest, segment) for segment in manifest["segments"])
        expected_time = sum(
            expected_duration(manifest, segment) for segment in manifest["segments"]
        )
        tolerance = 1.1 * expected_time / max(1, expected_count)
        return (
            int(observed.frame_count) == expected_count
            and abs(float(observed.duration) - expected_time) <= tolerance
            and _video_contract_valid(manifest, observed)
            and "mp4" in observed.container
            and len(observed.audio_streams) == len(manifest["media"].get("audio_streams", []))
            and all(
                abs(original["start_offset"] - actual["start_offset"]) <= 0.020
                and _audio_duration_matches(original, actual)
                for original, actual in zip(
                    manifest["media"].get("audio_streams", []), observed.audio_streams, strict=True
                )
            )
        )
    except (OSError, ValueError, ZeroDivisionError, AttributeError, subprocess.CalledProcessError):
        return False


def validate_done_segments(manifest: dict[str, Any], job_dir: Path) -> bool:
    """Re-queue files that are missing or fail frame and duration checks."""
    changed = False
    _cleanup_temps(job_dir)
    for segment in manifest["segments"]:
        if segment["state"] == "running":
            segment["state"] = "pending"
            changed = True
        if segment["state"] != "done":
            continue
        path = job_dir / f"seg_{segment['index']:05d}.mp4"
        if not segment_file_valid(manifest, segment, path):
            segment["state"] = "pending"
            path.unlink(missing_ok=True)
            changed = True
    return changed


def _schedule(home: Path, now: datetime, ignore: bool) -> Any:
    if ignore:
        return None
    from videoenhancer.schedule.windows import Schedule

    zone = now.tzinfo if isinstance(now.tzinfo, ZoneInfo) else None
    return Schedule.from_file(home / "schedule.json", zone=zone)


def finalization_abort(
    store: JobStore, job_id: str, clock: Clock, ignore_schedule: bool, stopped: Callable[[], bool]
) -> Callable[[], bool]:
    def abort() -> bool:
        if stopped() or store.read_control_state(job_id) not in {"queued", "running"}:
            return True
        now = clock.now()
        return (
            not ignore_schedule and _schedule(store.home, now, False).current_interval(now) is None
        )

    return abort


def unit_admission(job: dict[str, Any], now: datetime, interval: Any) -> tuple[bool, bool]:
    """Return (admitted, allowed overrun) for the next segment or finalization."""
    if interval is None:
        return False, False
    pending = next((s for s in job["segments"] if s["state"] != "done"), None)
    if pending is None:
        prediction = predict_finalization(job)
    else:
        from videoenhancer.estimate import predict_segment

        prediction = predict_segment(
            job["media"],
            job["settings"],
            pending["end"] - pending["start"],
            job.get("machine_profile"),
            float(job.get("correction_factor", 1)),
        )
    return admit_step(prediction, pending is None, now, interval)


class FinalizationTimer:
    def __init__(self, store: JobStore, job_id: str, clock: Clock) -> None:
        self.store, self.job_id, self.clock = store, job_id, clock
        self.step: str | None = None
        self.started = clock.now()
        self.logger = get_logger(store.home, job_id=job_id)

    def begin(self, name: str) -> None:
        self.step, self.started = name, self.clock.now()
        job = self.store.load(self.job_id)
        calibration = (job.get("machine_profile") or {}).get("finalization", {})
        samples = calibration.get("samples", [])
        assembly = sum(s["assembling_seconds"] for s in samples)
        validation = sum(s["validating_seconds"] for s in samples)
        share = assembly / (assembly + validation) if assembly + validation else 0.65
        fractions = {"assembling": 0.0, "validating": share * 0.99, "aggregating": 0.99}
        job["progress"] = dict(
            phase="finalizing", step=name, percent=0.0, finalization_fraction=fractions[name]
        )
        self.store.save(job)
        self.logger.info(
            "Finalization %s start", name, extra={"job_id": self.job_id, "action": f"{name}_start"}
        )

    def end(self) -> None:
        if self.step is None:
            return
        duration = max(0.0, (_utc(self.clock.now()) - _utc(self.started)).total_seconds())
        job = self.store.load(self.job_id)
        job.setdefault("timing", {}).setdefault("events", []).append(
            dict(
                step=self.step,
                start=self.started.isoformat(),
                end=self.clock.now().isoformat(),
                elapsed_seconds=duration,
            )
        )
        job["progress"]["percent"] = 100.0
        self.store.save(job)
        self.logger.info(
            "Finalization %s end",
            self.step,
            extra={
                "job_id": self.job_id,
                "action": f"{self.step}_end",
                "elapsed_seconds": duration,
            },
        )
        self.step = None

    def validation(self) -> None:
        self.end()
        self.begin("validating")


def run_queue(
    ignore_schedule: bool = False,
    home: Path | str | None = None,
    *,
    job_ids: set[str] | None = None,
    clock: Clock | None = None,
    executor: Any = None,
    disk_free: Callable[[Path], int] | int | None = None,
    stopped: Callable[[], bool] = lambda: False,
    between_segments: Callable[[], None] = lambda: None,
    on_error: Callable[[str | None, Exception], None] | None = None,
    on_progress: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
) -> None:
    """Process queued jobs until no runnable job remains.

    Clock and executor injection make the schedule and abort behavior testable
    without sleeping or encoding a real video.
    """
    store = JobStore(home)
    clock = clock or SystemClock()
    executor = executor or ProcessExecutor(clock, on_progress)
    get_logger(store.home)
    stop = False
    validated: set[str] = set()
    headers_logged: set[str] = set()
    previous_handler = None
    failures: dict[str, int] = {}
    waiting: dict[str, tuple[str, datetime]] = {}

    def timed_wait(job: dict[str, Any], seconds: float, reason: str) -> None:
        logger = get_logger(store.home, job_id=job["id"])
        started = clock.now()
        previous = waiting.get(job["id"])
        if (
            previous
            and previous[0] == reason
            and (_utc(started) - _utc(previous[1])).total_seconds() < 600
        ):
            clock.sleep(seconds)
            return
        waiting[job["id"]] = (reason, started)
        logger.info(
            "Scheduler wait start: %s",
            reason,
            extra={"job_id": job["id"], "action": "scheduler_wait_start"},
        )
        clock.sleep(seconds)
        duration = max(0.0, (_utc(clock.now()) - _utc(started)).total_seconds())
        latest = store.load(job["id"])
        event = dict(
            step="scheduler_wait",
            reason=reason,
            start=started.isoformat(),
            end=clock.now().isoformat(),
            elapsed_seconds=duration,
        )
        latest.setdefault("timing", {}).setdefault("events", []).append(event)
        store.save(latest)
        logger.info(
            "Scheduler wait end: %s",
            reason,
            extra={
                "job_id": job["id"],
                "action": "scheduler_wait_end",
                "elapsed_seconds": duration,
            },
        )

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop
        stop = True

    if threading.current_thread() is threading.main_thread():
        previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, request_stop)
    try:
        with _worker_lock(store.home):
            while not stop and not stopped():
                between_segments()
                if stopped():
                    break
                jobs = store.list_jobs()
                if job_ids is not None:
                    jobs = [job for job in jobs if job["id"] in job_ids]
                runnable = [job for job in jobs if job["state"] in {"queued", "running"}]
                if not runnable:
                    if any(job["state"] == "paused" for job in jobs):
                        timed_wait(
                            next(job for job in jobs if job["state"] == "paused"), 2, "paused"
                        )
                        continue
                    return
                manifest = runnable[0]
                selection_now = clock.now()
                selection_schedule = _schedule(store.home, selection_now, ignore_schedule)
                selection_interval = (
                    selection_schedule.current_interval(selection_now)
                    if selection_schedule is not None
                    else None
                )
                overrun = False
                if selection_schedule is not None and selection_interval is not None:
                    for candidate in runnable:
                        admitted, candidate_overrun = unit_admission(
                            candidate, selection_now, selection_interval
                        )
                        if admitted:
                            manifest, overrun = candidate, candidate_overrun
                            break
                job_id = manifest["id"]
                try:
                    if overrun and selection_interval is not None:
                        manifest["admitted_window_end"] = selection_interval.end.isoformat()
                        store.save(manifest)
                    job_dir = store.job_dir(job_id)
                    job_logger = get_logger(store.home, job_id=job_id)
                    if job_id not in headers_logged:
                        log_job_header(job_logger, job_id)
                        headers_logged.add(job_id)
                    try:
                        validate_input(manifest)
                    except (OSError, ValueError) as error:
                        manifest["state"] = "failed"
                        manifest["error"] = (
                            "The file could not be opened. It may be in use, or in a cloud folder "
                            "that is not downloaded to this PC."
                            if isinstance(error, OSError)
                            and not isinstance(error, FileNotFoundError)
                            else str(error)
                        )
                        store.save(manifest)
                        job_logger.error(
                            "Job %s input failed: %s", job_id, error, extra={"job_id": job_id}
                        )
                        continue
                    if job_id not in validated:
                        if validate_done_segments(manifest, job_dir):
                            store.save(manifest)
                        validated.add(job_id)
                    pending = next(
                        (segment for segment in manifest["segments"] if segment["state"] != "done"),
                        None,
                    )
                    if pending is None:
                        from videoenhancer.media.mux import assemble

                        now = clock.now()
                        schedule = _schedule(store.home, now, ignore_schedule)
                        prediction = predict_finalization(manifest)
                        interval = schedule.current_interval(now) if schedule is not None else None
                        if schedule is not None and (
                            interval is None or not unit_admission(manifest, now, interval)[0]
                        ):
                            upcoming = schedule.next_interval(now)
                            wait = (
                                max(0.1, (_utc(upcoming.start) - _utc(now)).total_seconds())
                                if upcoming
                                else 30
                            )
                            if interval is not None:
                                wait = max(0.1, (_utc(interval.end) - _utc(now)).total_seconds())
                            timed_wait(manifest, min(wait, 30), "finalization admission")
                            continue

                        assembly_abort = finalization_abort(
                            store,
                            job_id,
                            clock,
                            ignore_schedule or overrun,
                            lambda: stop or stopped(),
                        )

                        finalize_started = clock.now()
                        timer = FinalizationTimer(store, job_id, clock)
                        begin_step = timer.begin
                        end_step = timer.end
                        start_validation = timer.validation

                        try:
                            begin_step("assembling")
                            destination = Path(manifest["output"])
                            if destination.exists():
                                start_validation()
                                if not _assembled_file_valid(manifest, destination):
                                    raise ValueError(
                                        f"Existing output is invalid: {destination}. "
                                        "Move it aside and resume the job."
                                    )
                                result_path = destination
                            else:
                                require_disk_space(
                                    destination.parent,
                                    int(manifest["estimated_output_bytes"]),
                                    disk_free,
                                )
                                result_path = assemble(
                                    manifest,
                                    job_dir,
                                    abort=assembly_abort,
                                    validation_started=start_validation,
                                )
                            end_step()
                            if assembly_abort():
                                raise InterruptedError("Finalization was interrupted.")
                            if stop or store.load(job_id)["state"] not in {"queued", "running"}:
                                continue
                            begin_step("aggregating")
                            manifest = store.load(job_id)
                            if manifest["settings"].get("preset") in {"fast", "standard"}:
                                from videoenhancer.pipeline.inline_quality import aggregate_quality

                                manifest["quality"] = aggregate_quality(manifest)
                                manifest["detector"] = {
                                    "raw_flag_count": sum(
                                        item.get("stats", {}).get("raw_flag_count", 0)
                                        for item in manifest["segments"]
                                    ),
                                    "final_flag_count": sum(
                                        item.get("stats", {}).get(
                                            "final_flag_count",
                                            len(item.get("stats", {}).get("luma_outliers", [])),
                                        )
                                        for item in manifest["segments"]
                                    ),
                                    "counting": "Owned indices per segment; final is post-repair.",
                                }
                            store.save(manifest)
                            end_step()
                            if assembly_abort():
                                raise InterruptedError("Finalization was interrupted.")
                            manifest = store.load(job_id)
                            observed = max(
                                0.0, (_utc(clock.now()) - _utc(finalize_started)).total_seconds()
                            )
                            observe_finalization(manifest, prediction, observed, store.home)
                            manifest["state"] = "done"
                            manifest["result"] = str(result_path)
                            store.save(manifest)
                            if not manifest["settings"].get("keep_segments"):
                                for path in job_dir.glob("seg_*.mp4"):
                                    path.unlink(missing_ok=True)
                            from videoenhancer.schedule.windows import Schedule

                            Schedule.clear_job_complete_override(
                                store.home / "schedule.json",
                                queue_complete=all(
                                    j["state"] in {"done", "failed", "cancelled"}
                                    for j in store.list_jobs()
                                ),
                            )
                            job_logger.info(
                                "Job %s completed: %s",
                                job_id,
                                result_path,
                                extra={"job_id": job_id},
                            )
                        except InterruptedError:
                            end_step()
                            job_logger.warning(
                                "Job %s assembly interrupted; it will resume later",
                                job_id,
                                extra={"job_id": job_id},
                            )
                        except Exception as error:
                            end_step()
                            manifest = store.load(job_id)
                            manifest["state"] = "failed"
                            manifest["error"] = (
                                f"Assembly failed: {error}. Check disk space and retry."
                            )
                            store.save(manifest)
                            job_logger.error(manifest["error"], extra={"job_id": job_id})
                        continue
                    if pending["state"] == "failed":
                        manifest["state"] = "failed"
                        store.save(manifest)
                        continue
                    now = clock.now()
                    schedule = _schedule(store.home, now, ignore_schedule)
                    interval = schedule.current_interval(now) if schedule is not None else None
                    if schedule is not None and interval is None:
                        upcoming = schedule.next_interval(now)
                        seconds = (
                            max(0.1, (_utc(upcoming.start) - _utc(now)).total_seconds())
                            if upcoming
                            else 30
                        )
                        timed_wait(manifest, min(seconds, 30), "outside operating hours")
                        continue
                    from videoenhancer.estimate import predict_segment, update_correction

                    prediction = predict_segment(
                        manifest["media"],
                        manifest["settings"],
                        pending["end"] - pending["start"],
                        manifest.get("machine_profile"),
                        correction=float(manifest.get("correction_factor", 1.0)),
                    )
                    if (
                        interval is not None
                        and _utc(now) + timedelta(seconds=prediction * 1.1 + 30)
                        > _utc(interval.end)
                        and not overrun
                    ):
                        timed_wait(
                            manifest,
                            min(30, max(0.1, (_utc(interval.end) - _utc(now)).total_seconds())),
                            "segment admission",
                        )
                        continue
                    latest = store.load(job_id)
                    if latest["state"] not in {"queued", "running"}:
                        continue
                    try:
                        require_disk_space(
                            job_dir, int(latest["estimated_output_bytes"]), disk_free
                        )
                    except OSError as error:
                        latest["state"] = "failed"
                        latest["error"] = f"Segment storage preflight failed: {error}"
                        store.save(latest)
                        job_logger.error(latest["error"], extra={"job_id": job_id})
                        continue
                    manifest = latest
                    manifest["progress"] = dict(phase="processing", step="segments", percent=0.0)
                    segment = manifest["segments"][pending["index"]]
                    segment["predicted_seconds"] = prediction
                    segment["state"] = "running"
                    manifest["state"] = "running"
                    store.save(manifest)
                    index = int(segment["index"])
                    temp_path = job_dir / f"seg_{index:05d}.tmp.mp4"
                    final_path = job_dir / f"seg_{index:05d}.mp4"
                    temp_path.unlink(missing_ok=True)
                    started = clock.now()
                    reason = ""
                    schedule_path = store.home / "schedule.json"
                    schedule_state: dict[str, Any] = {
                        "value": schedule,
                        "mtime": schedule_path.stat().st_mtime_ns if schedule_path.exists() else 0,
                        "checked": _utc(started) - timedelta(seconds=2),
                    }

                    def should_abort(
                        target_job_id: str = job_id,
                        schedule_cache: dict[str, Any] = schedule_state,
                        path: Path = schedule_path,
                        allowed_overrun: bool = overrun,
                    ) -> bool:
                        nonlocal reason
                        if stop or stopped():
                            reason = "interrupt"
                            return True
                        state = store.read_control_state(target_job_id)
                        if state not in {"queued", "running"}:
                            reason = state
                            return True
                        if not ignore_schedule and not allowed_overrun:
                            current = clock.now()
                            if (_utc(current) - schedule_cache["checked"]).total_seconds() >= 1:
                                mtime = path.stat().st_mtime_ns if path.exists() else 0
                                if mtime != schedule_cache["mtime"]:
                                    schedule_cache["value"] = _schedule(store.home, current, False)
                                    schedule_cache["mtime"] = mtime
                                schedule_cache["checked"] = _utc(current)
                            if schedule_cache["value"].current_interval(current) is None:
                                reason = "schedule window ended"
                                return True
                        return False

                    next_pause = interval.end.isoformat(timespec="minutes") if interval else "none"
                    job_logger.info(
                        "Job %s segment %d/%d started; ETA %.0f s; next pause %s",
                        job_id,
                        index + 1,
                        len(manifest["segments"]),
                        prediction,
                        next_pause,
                        extra={"job_id": job_id, "segment": index},
                    )
                    batch_size = int(manifest["settings"].get("batch_size", 2))
                    with _prevent_sleep():
                        try:
                            result = executor.run(
                                manifest, segment, temp_path, should_abort, batch_size=batch_size
                            )
                            if result.stalled:
                                _cleanup_temps(job_dir)
                                job_logger.warning(
                                    "Segment watchdog fired; retrying in a fresh child",
                                    extra={"job_id": job_id, "segment": index},
                                )
                                result = executor.run(
                                    manifest,
                                    segment,
                                    temp_path,
                                    should_abort,
                                    batch_size=batch_size,
                                )
                            if result.oom and batch_size > 1:
                                temp_path.unlink(missing_ok=True)
                                job_logger.warning(
                                    "Segment %d ran out of GPU memory; retrying with batch size 1",
                                    index,
                                    extra={"job_id": job_id, "segment": index},
                                )
                                result = executor.run(
                                    manifest, segment, temp_path, should_abort, batch_size=1
                                )
                        except Exception as error:
                            result = SegmentResult(
                                "failed",
                                error=f"Worker process error: {type(error).__name__}: {error}",
                            )
                    elapsed = max(0.0, (_utc(clock.now()) - _utc(started)).total_seconds())
                    manifest = store.load(job_id)
                    segment = manifest["segments"][index]
                    control_state = store.read_control_state(job_id)
                    window_closed = (
                        not ignore_schedule
                        and not overrun
                        and _schedule(store.home, clock.now(), False).current_interval(clock.now())
                        is None
                    )
                    if result.status == "done" and (
                        stop or control_state not in {"queued", "running"} or window_closed
                    ):
                        result = SegmentResult("aborted")
                    if result.status == "done":
                        if not segment_file_valid(manifest, segment, temp_path):
                            result = SegmentResult(
                                "failed",
                                error="encoder segment failed frame-count or duration validation",
                            )
                        else:
                            retry_permission(os.replace, temp_path, final_path)
                            segment["state"] = "done"
                            segment["actual_seconds"] = elapsed
                            segment["stats"] = result.stats or {}
                            memory_samples = segment["stats"].get("memory_samples", [])
                            if memory_samples:
                                job_logger.info(
                                    "Memory samples for segment %d: %s",
                                    index,
                                    json.dumps(memory_samples, separators=(",", ":")),
                                    extra={"job_id": job_id, "segment": index},
                                )
                            update_correction(manifest, prediction, elapsed)
                            if manifest["state"] == "running":
                                manifest["state"] = "queued"
                            store.save(manifest)
                            failures.pop(job_id, None)
                            fps = (segment["end"] - segment["start"]) / elapsed if elapsed else 0.0
                            job_logger.info(
                                "Job %s segment %d/%d complete; %.1f fps; %.0f s",
                                job_id,
                                index + 1,
                                len(manifest["segments"]),
                                fps,
                                elapsed,
                                extra={
                                    "job_id": job_id,
                                    "segment": index,
                                    "elapsed_seconds": elapsed,
                                },
                            )
                    if result.status == "aborted":
                        temp_path.unlink(missing_ok=True)
                        segment["state"] = "pending"
                        manifest.setdefault("timing", {}).setdefault("wasted_seconds", 0.0)
                        manifest["timing"]["wasted_seconds"] += elapsed
                        if manifest["state"] == "running":
                            manifest["state"] = "queued"
                        store.save(manifest)
                        job_logger.warning(
                            "Job %s segment %d aborted after %.0f s (%s); it will resume later",
                            job_id,
                            index + 1,
                            elapsed,
                            reason or "requested",
                            extra={"job_id": job_id, "segment": index, "elapsed_seconds": elapsed},
                        )
                    if result.status == "failed":
                        temp_path.unlink(missing_ok=True)
                        segment["state"] = "failed"
                        manifest["state"] = "failed"
                        manifest["error"] = (
                            f"Processing stopped responding at segment {index + 1} of "
                            f"{len(manifest['segments'])}. Retry, or use Copy details to report it."
                            if result.stalled
                            else f"Segment {index + 1} failed: {result.error}. "
                            "Check the job log, then resume the job."
                        )
                        store.save(manifest)
                        job_logger.error(
                            manifest["error"], extra={"job_id": job_id, "segment": index}
                        )
                except JobQuarantinedError as error:
                    if on_error is not None:
                        on_error(job_id, error)
                    continue
                except Exception as error:
                    job_logger = get_logger(store.home, job_id=job_id)
                    job_logger.exception("Controller error", extra={"job_id": job_id})
                    if on_error is not None:
                        on_error(job_id, error)
                    failures[job_id] = failures.get(job_id, 0) + 1
                    clock.sleep(5 if failures[job_id] == 1 else 30)
                    latest = store.load(job_id)
                    if latest.get("quarantined"):
                        continue
                    for item in latest["segments"]:
                        if item["state"] == "running":
                            item["state"] = "pending"
                    latest["state"] = "queued" if failures[job_id] == 1 else "failed"
                    latest["error"] = (
                        "Processing could not continue after two attempts. Retry, or use Copy "
                        "details to report it."
                    )
                    store.save(latest)
                    _cleanup_temps(store.job_dir(job_id))
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGINT, previous_handler)
