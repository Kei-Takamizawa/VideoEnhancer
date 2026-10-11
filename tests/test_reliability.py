"""P1c failure isolation, deadlines and live-state regression tests."""

from __future__ import annotations

import ast
import copy
import io
import json
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_controller import FakeClock, _job

from videoenhancer import proc
from videoenhancer.estimate.model import job_progress
from videoenhancer.files import retry_permission
from videoenhancer.jobs.store import JobStore
from videoenhancer.schedule import controller
from videoenhancer.service.engine import Engine
from videoenhancer.service.server import Handler


def test_every_engine_subprocess_uses_hidden_wrapper():
    root = Path(__file__).resolve().parents[1] / "src"
    for path in root.rglob("*.py"):
        if path.name == "proc.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = {"subprocess"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                aliases.update(a.asname or a.name for a in node.names if a.name == "subprocess")
            if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                assert not any(
                    a.name in {"run", "Popen", "call", "check_output", "check_call"}
                    for a in node.names
                ), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in aliases:
                    assert node.func.attr not in {
                        "run",
                        "Popen",
                        "call",
                        "check_output",
                        "check_call",
                    }, path


@pytest.mark.parametrize("text", [False, True])
def test_stderr_over_one_megabyte_never_blocks_stdout(text):
    result = proc.run(
        [sys.executable, "-c", "import sys; sys.stderr.write('x'*1500000); print('done')"],
        capture_output=True,
        text=text,
        timeout=10,
        check=True,
    )
    assert len(result.stderr) == 65536
    assert result.stdout.strip() == ("done" if text else b"done")


def test_permission_retry_schedule(monkeypatch):
    waits = []
    monkeypatch.setattr("videoenhancer.files.time.sleep", waits.append)
    attempts = []

    def busy():
        attempts.append(1)
        raise PermissionError("sharing violation")

    with pytest.raises(PermissionError):
        retry_permission(busy)
    assert waits == [0.2, 0.5, 1, 2, 4] and len(attempts) == 6


@pytest.mark.parametrize(
    "reason,frames,elapsed",
    [("no first frame", 0, 300), ("no new frame", 1, 182), ("wall time", 500, 601)],
)
def test_watchdog_limits(reason, frames, elapsed):
    watchdog = controller.SegmentWatchdog(100, 1000, 0)
    watchdog.progress(frames, 2)
    assert watchdog.reason(elapsed) == reason


def _fake_context(clock, messages, monkeypatch):
    killed = []
    monkeypatch.setattr(controller, "_kill_process_tree", killed.append)
    alive = [True]

    class Receiver:
        def poll(self):
            return bool(messages and clock.now().timestamp() >= messages[0][0])

        def recv(self):
            return messages.pop(0)[1]

        def close(self):
            pass

    class Process:
        pid = None
        exitcode = 0

        def start(self):
            pass

        def is_alive(self):
            return alive[0]

        def terminate(self):
            alive[0] = False

        def join(self, timeout):
            clock.value += timedelta(seconds=timeout)

    context = SimpleNamespace(
        Event=threading.Event,
        Process=lambda **_: Process(),
        Pipe=lambda **_: (Receiver(), SimpleNamespace(close=lambda: None)),
    )
    return context, alive


def test_hanging_child_before_result_is_terminated(tmp_path, monkeypatch):
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    context, alive = _fake_context(clock, [], monkeypatch)
    result = controller.ProcessExecutor(clock, context=context).run(
        {},
        dict(index=0, start=0, end=100, predicted_seconds=10),
        tmp_path / "output.mp4",
        lambda: False,
        batch_size=1,
    )
    assert result.stalled and not alive[0]
    assert (clock.now() - datetime(2026, 1, 1, tzinfo=UTC)).total_seconds() < 302


def test_hanging_child_after_result_keeps_result(tmp_path, monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FakeClock(start)
    expected = controller.SegmentResult("done", stats={"input_frames": 20})
    context, alive = _fake_context(clock, [(start.timestamp() + 1, expected)], monkeypatch)
    result = controller.ProcessExecutor(clock, context=context).run(
        {}, dict(start=0, end=20), tmp_path / "output.mp4", lambda: False, batch_size=1
    )
    assert result == expected and not alive[0]
    assert 16 <= (clock.now() - start).total_seconds() <= 18


def test_progress_moves_inside_segment(tmp_path):
    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    job["segments"][0]["state"] = "running"
    percentages = []
    for frames in (0, 50, 100, 300):
        job["progress"] = dict(phase="processing", segment=0, frames_done=frames)
        percentages.append(job_progress(job)["progress_percent"])
    assert percentages == [0, pytest.approx(100 / 6), pytest.approx(100 / 3), 99.9]


def _two_jobs(tmp_path):
    store = JobStore(tmp_path / "home")
    first = _job(store, tmp_path)
    second = copy.deepcopy(first)
    second.update(id="second-job", position=2, output=str(tmp_path / "second.mp4"))
    store.save(second)
    return store, first, second


@pytest.mark.parametrize("failure", ["stall", "input", "replace", "controller"])
def test_bad_job_does_not_block_next(tmp_path, monkeypatch, failure):
    store, first, second = _two_jobs(tmp_path)
    calls = []
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    monkeypatch.setattr(controller, "validate_done_segments", lambda *_: False)
    monkeypatch.setattr(controller, "segment_file_valid", lambda *_: True)
    original_validate = controller.validate_input
    if failure == "input":

        def validate(job):
            if job["id"] == first["id"]:
                raise PermissionError("locked")
            return original_validate(job)

        monkeypatch.setattr(controller, "validate_input", validate)
    if failure == "controller":

        def validate_done(job, _directory):
            if job["id"] == first["id"]:
                raise OSError("controller failure")
            return False

        monkeypatch.setattr(controller, "validate_done_segments", validate_done)
    if failure == "replace":
        real_replace = controller.os.replace

        def replace(source, destination):
            if "seg_" in str(source) and first["id"] in str(source):
                raise PermissionError("locked output")
            return real_replace(source, destination)

        monkeypatch.setattr(controller.os, "replace", replace)
        monkeypatch.setattr("videoenhancer.files.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "videoenhancer.media.mux.assemble", lambda job, *_a, **_kw: Path(job["output"])
    )

    class Executor:
        def run(self, job, _segment, output, *_a, **_kw):
            calls.append(job["id"])
            if failure == "stall" and job["id"] == first["id"]:
                return controller.SegmentResult("failed", stalled=True)
            output.write_bytes(b"encoded")
            return controller.SegmentResult("done")

    controller.run_queue(home=store.home, ignore_schedule=True, clock=clock, executor=Executor())
    assert store.load(first["id"])["state"] == "failed"
    assert store.load(second["id"])["state"] == "done"
    if failure == "stall":
        assert calls.count(first["id"]) == 2
        assert "stopped responding" in store.load(first["id"])["error"]


def test_oversized_finalization_is_admitted_at_window_start(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    job["segments"][0]["state"] = "done"
    now = datetime(2026, 1, 1, tzinfo=UTC)
    interval = SimpleNamespace(start=now, end=now + timedelta(seconds=10))
    monkeypatch.setattr(controller, "predict_finalization", lambda _: 60)
    assert controller.unit_admission(job, now, interval) == (True, True)
    assert controller.unit_admission(job, now + timedelta(seconds=40), interval) == (False, False)


def test_short_second_job_is_admitted_before_long_head(tmp_path, monkeypatch):
    store, first, second = _two_jobs(tmp_path)
    second["segments"][0]["end"] = 1
    store.save(second)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FakeClock(now)
    interval = SimpleNamespace(start=now - timedelta(seconds=200), end=now + timedelta(seconds=45))
    monkeypatch.setattr(
        controller, "_schedule", lambda *_: SimpleNamespace(current_interval=lambda _: interval)
    )
    monkeypatch.setattr(
        "videoenhancer.estimate.predict_segment", lambda _m, _s, count, *_a, **_kw: count
    )
    monkeypatch.setattr(controller, "validate_done_segments", lambda *_: False)
    stopped = []

    class Executor:
        def run(self, job, *_a, **_kw):
            stopped.append(job["id"])
            return controller.SegmentResult("aborted")

    controller.run_queue(
        home=store.home, clock=clock, executor=Executor(), stopped=lambda: bool(stopped)
    )
    assert stopped == [second["id"]]


def test_restart_recovers_all_running_jobs_and_operations(tmp_path):
    store, first, second = _two_jobs(tmp_path)
    for job in (first, second):
        job["state"] = "running"
        job["segments"][0]["state"] = "running"
        store.save(job)
    engine = Engine(store.home)
    op = dict(id="preview-one", kind="trial", state="running", request={})
    engine._save_operation(op)
    engine._recover()
    assert all(
        j["state"] == "queued" and j["segments"][0]["state"] == "pending" for j in store.list_jobs()
    )
    assert engine.operations[op["id"]]["error"] == "Interrupted. Try again."
    assert (
        json.loads((store.home / "previews" / op["id"] / "state.json").read_text())["state"]
        == "failed"
    )


def test_sse_snapshot_exception_sends_error_then_keeps_stream(tmp_path):
    engine = Engine(tmp_path / "home")
    output = io.BytesIO()
    calls = []

    def snapshot():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("injected snapshot failure")
        engine.stop.set()
        return {"jobs": []}

    engine.queue = snapshot
    handler = object.__new__(Handler)
    handler.server = SimpleNamespace(engine=engine)
    handler.wfile = output
    handler._headers = lambda *_: None
    handler._events()
    assert b"event: error" in output.getvalue() and b"event: update" in output.getvalue()
