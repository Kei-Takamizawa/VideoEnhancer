"""Injected-clock worker behavior at schedule and control boundaries."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from videoenhancer.jobs.store import JobStore, input_identity
from videoenhancer.schedule import controller


class FakeClock:
    def __init__(self, start: datetime, on_sleep: Any = None) -> None:
        self.value = start
        self.on_sleep = on_sleep

    def now(self) -> datetime:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)
        if self.on_sleep:
            self.on_sleep()


def _job(store: JobStore, tmp_path: Path) -> dict[str, Any]:
    source = tmp_path / "input.mp4"
    source.write_bytes(b"example")
    job = {
        "schema_version": 1,
        "id": "unit-job",
        "input": input_identity(source),
        "output": str(tmp_path / "output.mp4"),
        "estimated_output_bytes": 10,
        "settings": {
            "preset": "passthrough",
            "short_side": "keep",
            "fps": "off",
            "backend": "cpu",
            "batch_size": 2,
        },
        "media": {
            "width": 32,
            "height": 32,
            "display_width": 32,
            "display_height": 32,
            "cfr_fps": "30/1",
            "frame_count": 300,
        },
        "scene_cuts": [],
        "cfr_map": list(range(300)),
        "segments": [
            {"index": 0, "start": 0, "end": 300, "state": "pending", "predicted_seconds": 180}
        ],
        "state": "queued",
        "position": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "correction_factor": 1.0,
        "timing": {"observations": [], "wasted_seconds": 0.0},
    }
    store.save(job)
    return job


def test_controller_does_not_start_segment_that_overruns_window(
    tmp_path: Path, monkeypatch: Any
) -> None:
    store = JobStore(tmp_path / "home")
    _job(store, tmp_path)
    start = datetime(2026, 1, 1, 22, 14, 45, tzinfo=UTC)
    clock = FakeClock(start, lambda: store.set_state("unit-job", "cancelled"))

    class Schedule:
        def current_interval(self, _now: datetime) -> Any:
            return type("Interval", (), {"end": start + timedelta(seconds=15)})()

    class Executor:
        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("A segment must not start with only 15 seconds left")

    monkeypatch.setattr(controller, "_schedule", lambda *_args: Schedule())
    monkeypatch.setattr(controller, "validate_done_segments", lambda *_args: False)
    controller.run_queue(home=store.home, clock=clock, executor=Executor())
    assert store.load("unit-job")["segments"][0]["state"] == "pending"


def test_controller_aborts_and_requeues_on_pause(tmp_path: Path, monkeypatch: Any) -> None:
    store = JobStore(tmp_path / "home")
    _job(store, tmp_path)
    clock = FakeClock(
        datetime(2026, 1, 1, tzinfo=UTC),
        lambda: store.set_state("unit-job", "cancelled"),
    )

    class Executor:
        def run(
            self, _manifest: Any, _segment: Any, output: Path, abort: Any, **_kwargs: Any
        ) -> controller.SegmentResult:
            output.write_bytes(b"partial")
            clock.value += timedelta(seconds=3)
            store.set_state("unit-job", "paused")
            assert abort()
            return controller.SegmentResult("aborted")

    monkeypatch.setattr(controller, "validate_done_segments", lambda *_args: False)
    controller.run_queue(ignore_schedule=True, home=store.home, clock=clock, executor=Executor())
    result = store.load("unit-job")
    assert result["state"] == "cancelled"
    assert result["segments"][0]["state"] == "pending"
    assert result["timing"]["wasted_seconds"] == 3
    assert not list(store.job_dir("unit-job").glob("seg_*.tmp.*"))


def test_invalid_done_segment_is_requeued_and_stale_temp_removed(
    tmp_path: Path, monkeypatch: Any
) -> None:
    store = JobStore(tmp_path / "home")
    manifest = _job(store, tmp_path)
    manifest["segments"][0]["state"] = "done"
    job_dir = store.job_dir("unit-job")
    finished = job_dir / "seg_00000.mp4"
    stale = job_dir / "seg_00000.tmp.mp4"
    finished.write_bytes(b"corrupted")
    stale.write_bytes(b"partial")
    monkeypatch.setattr(controller, "segment_file_valid", lambda *_args: False)
    assert controller.validate_done_segments(manifest, job_dir)
    assert manifest["segments"][0]["state"] == "pending"
    assert not finished.exists() and not stale.exists()


@pytest.mark.parametrize(
    ("wrong_field", "wrong_value"),
    [("width", 64), ("average_fps", "24"), ("codec", "h264")],
)
def test_resume_rejects_wrong_video_contract(
    tmp_path: Path, monkeypatch: Any, wrong_field: str, wrong_value: Any
) -> None:
    from videoenhancer.media import probe as media_probe

    store = JobStore(tmp_path / "home")
    manifest = _job(store, tmp_path)
    segment = manifest["segments"][0]
    path = store.job_dir("unit-job") / "seg_00000.mp4"
    path.write_bytes(b"existing")
    observed = {
        "frame_count": 300,
        "duration": 10.0,
        "width": 32,
        "height": 32,
        "average_fps": "30",
        "codec": "hevc",
        "rotation": 0,
    }
    monkeypatch.setattr(media_probe, "probe", lambda *_args, **_kwargs: SimpleNamespace(**observed))
    assert controller.segment_file_valid(manifest, segment, path)
    assert controller._assembled_file_valid(manifest, path)
    observed[wrong_field] = wrong_value
    assert not controller.segment_file_valid(manifest, segment, path)
    assert not controller._assembled_file_valid(manifest, path)


def test_child_native_stdout_is_redirected_to_stderr() -> None:
    command = (
        "import os; "
        "from videoenhancer.schedule.controller import _redirect_child_stdout_to_stderr; "
        "_redirect_child_stdout_to_stderr(); "
        "os.write(1, b'native diagnostic\\n')"
    )
    result = subprocess.run([sys.executable, "-c", command], capture_output=True, check=True)
    assert result.stdout == b""
    assert result.stderr == b"native diagnostic\n"


def test_worker_checks_home_volume_before_segment(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "home")
    _job(store, tmp_path)

    class Executor:
        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("Segment started despite low home volume")

    def disk_free(path: Path) -> int:
        return 0 if store.home in (path, *path.parents) else 1_000_000

    controller.run_queue(
        ignore_schedule=True,
        home=store.home,
        clock=FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
        executor=Executor(),
        disk_free=disk_free,
    )
    result = store.load("unit-job")
    assert result["state"] == "failed"
    assert "Segment storage preflight failed" in result["error"]
    assert result["segments"][0]["state"] == "pending"


def test_worker_retries_oom_with_one_frame_batch(tmp_path: Path, monkeypatch: Any) -> None:
    from videoenhancer.media import mux

    store = JobStore(tmp_path / "home")
    _job(store, tmp_path)
    schedule_path = store.home / "schedule.json"
    schedule_path.write_text(
        json.dumps(
            {"schema_version": 1, "enabled": True, "weekly": [], "override_until": "job-complete"}
        ),
        encoding="utf-8",
    )
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    batches: list[int] = []

    class Executor:
        def run(
            self, _manifest: Any, _segment: Any, output: Path, _abort: Any, *, batch_size: int
        ) -> controller.SegmentResult:
            batches.append(batch_size)
            clock.value += timedelta(seconds=2)
            if len(batches) == 1:
                output.write_bytes(b"partial")
                return controller.SegmentResult("failed", error="CUDA out of memory", oom=True)
            output.write_bytes(b"complete")
            return controller.SegmentResult("done", stats={"frames": 300})

    def assemble(manifest: dict, _job_dir: Path, abort: Any) -> Path:
        assert not abort()
        output = Path(manifest["output"])
        output.write_bytes(b"assembled")
        return output

    monkeypatch.setattr(controller, "segment_file_valid", lambda *_args: True)
    monkeypatch.setattr(mux, "assemble", assemble)
    controller.run_queue(
        ignore_schedule=True,
        home=store.home,
        clock=clock,
        executor=Executor(),
        disk_free=1_000_000,
    )
    assert batches == [2, 1]
    result = store.load("unit-job")
    assert result["state"] == "done"
    assert result["segments"][0]["state"] == "done"
    assert json.loads(schedule_path.read_text(encoding="utf-8"))["override_until"] is None


def test_worker_aborts_at_window_end_and_resumes_next_window(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from videoenhancer.media import mux

    store = JobStore(tmp_path / "home")
    _job(store, tmp_path)
    first_start = datetime(2026, 1, 1, 22, 0, tzinfo=UTC)
    first_end = first_start + timedelta(minutes=5)
    next_start = first_start + timedelta(days=1)
    next_end = next_start + timedelta(minutes=5)

    def on_sleep() -> None:
        clock.value = next_start

    clock = FakeClock(first_start, on_sleep)

    class Schedule:
        def current_interval(self, now: datetime) -> Any:
            if first_start <= now < first_end:
                return type("Interval", (), {"end": first_end})()
            if next_start <= now < next_end:
                return type("Interval", (), {"end": next_end})()
            return None

        def next_interval(self, _now: datetime) -> Any:
            return type("Interval", (), {"start": next_start})()

    runs = 0

    class Executor:
        def run(
            self, _manifest: Any, _segment: Any, output: Path, abort: Any, **_kwargs: Any
        ) -> controller.SegmentResult:
            nonlocal runs
            runs += 1
            if runs == 1:
                output.write_bytes(b"partial")
                clock.value = first_end + timedelta(seconds=1)
                assert abort()
                return controller.SegmentResult("aborted")
            output.write_bytes(b"complete")
            clock.value += timedelta(seconds=3)
            return controller.SegmentResult("done")

    def assemble(manifest: dict, _job_dir: Path, abort: Any) -> Path:
        assert not abort()
        output = Path(manifest["output"])
        output.write_bytes(b"assembled")
        return output

    monkeypatch.setattr(controller, "_schedule", lambda *_args: Schedule())
    monkeypatch.setattr(controller, "segment_file_valid", lambda *_args: True)
    monkeypatch.setattr(mux, "assemble", assemble)
    controller.run_queue(home=store.home, clock=clock, executor=Executor(), disk_free=1_000_000)
    assert runs == 2
    result = store.load("unit-job")
    assert result["state"] == "done"
    assert result["timing"]["wasted_seconds"] == 301


def test_only_one_worker_can_hold_queue_lock(tmp_path: Path) -> None:
    with controller._worker_lock(tmp_path):
        with pytest.raises(RuntimeError, match="already running"):
            with controller._worker_lock(tmp_path):
                pass


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object test")
def test_hard_killed_parent_reaps_segment_subprocess() -> None:
    psutil = pytest.importorskip("psutil")
    script = (
        "import subprocess,sys,time; "
        "from videoenhancer.schedule.controller import _attach_windows_job; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "_attach_windows_job(child.pid); print(child.pid,flush=True); time.sleep(60)"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = None
    try:
        assert parent.stdout is not None
        line = parent.stdout.readline().strip()
        assert line.isdigit(), parent.stderr.read() if parent.stderr else "No child PID"
        child_pid = int(line)
        assert psutil.pid_exists(child_pid)
        parent.kill()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 5
        while psutil.pid_exists(child_pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not psutil.pid_exists(child_pid)
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        if child_pid and psutil.pid_exists(child_pid):
            psutil.Process(child_pid).kill()


def _process_active(psutil, pid: int) -> bool:
    try:
        if not psutil.pid_exists(pid):
            return False
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def test_parent_death_poll_handles_process_disappearing_between_checks(monkeypatch):
    psutil = pytest.importorskip("psutil")
    monkeypatch.setattr(psutil, "pid_exists", lambda _pid: True)

    def disappearing_process(pid):
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", disappearing_process)
    assert not _process_active(psutil, 12345)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux parent-death signal test")
def test_linux_hard_killed_parent_reaps_ffmpeg_subtree(tmp_path: Path) -> None:
    psutil = pytest.importorskip("psutil")
    marker = tmp_path / "grandchild.pid"
    child_code = (
        "import os,subprocess,sys,time; "
        "from videoenhancer.schedule.controller import _set_linux_parent_death; "
        "_set_linux_parent_death(int(sys.argv[1])); "
        "grand=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); "
        "open(sys.argv[2],'w').write(str(grand.pid)); time.sleep(60)"
    )
    parent_code = (
        "import os,subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c',"
        f"{child_code!r},str(os.getpid()),sys.argv[1]]); "
        "print(child.pid,flush=True); time.sleep(60)"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", parent_code, str(marker)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    child_pid = None
    grandchild_pid = None
    try:
        assert parent.stdout is not None
        child_pid = int(parent.stdout.readline().strip())
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists(), parent.stderr.read() if parent.stderr else "Child did not start"
        grandchild_pid = int(marker.read_text())
        parent.kill()
        parent.wait(timeout=5)

        def active(pid: int) -> bool:
            return _process_active(psutil, pid)

        deadline = time.monotonic() + 5
        while (active(child_pid) or active(grandchild_pid)) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not active(child_pid) and not active(grandchild_pid)
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        for pid in (child_pid, grandchild_pid):
            if pid and psutil.pid_exists(pid):
                try:
                    process = psutil.Process(pid)
                    if process.status() != psutil.STATUS_ZOMBIE:
                        process.kill()
                except psutil.NoSuchProcess:
                    pass
