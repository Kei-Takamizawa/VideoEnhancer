"""Warm-worker lifetime and invalidation without requiring a GPU fault."""

import hashlib
import os
import threading
import time
from collections import deque

import pytest

from videoenhancer.schedule import controller


class Context:
    def __init__(self, results):
        self.results = deque(results)
        self.messages = deque()
        self.processes = []
        self.pipes = 0

    Event = staticmethod(threading.Event)

    def Pipe(self, **_kwargs):
        self.pipes += 1
        context = self

        class Receiver:
            def poll(self):
                return bool(context.messages)

            def recv(self):
                return context.messages.popleft()

            def close(self):
                pass

        class Sender:
            def send(self, value):
                if value is None:
                    context.processes[-1].alive = False
                else:
                    context.messages.append(context.results.popleft())

            def close(self):
                pass

        return Receiver(), Sender()

    def Process(self, **_kwargs):
        context = self

        class Process:
            pid = None
            exitcode = 0
            alive = False

            def start(self):
                self.alive = True
                context.messages.append(context.results.popleft())
                context.processes.append(self)

            def is_alive(self):
                return self.alive

            def terminate(self):
                self.alive = False

            def join(self, timeout):
                pass

        return Process()


def run(executor, path, settings=None, abort=lambda: False):
    return executor.run(
        {"settings": settings or {}, "media": {}},
        {"start": 0, "end": 2},
        path,
        abort,
        batch_size=1,
    )


def done(**stats):
    return controller.SegmentResult("done", stats=stats)


def test_worker_reuses_process_and_closes_after_shutdown(tmp_path):
    context = Context([done(), done()])
    executor = controller.ProcessExecutor(context=context, reuse=True)
    try:
        assert run(executor, tmp_path / "one.mp4").status == "done"
        assert run(executor, tmp_path / "two.mp4").status == "done"
        assert len(context.processes) == 1
        assert executor.worker is not None
    finally:
        executor.close()
    assert executor.worker is None
    assert not any(p.is_alive() for p in context.processes)


@pytest.mark.parametrize(
    "result",
    [
        controller.SegmentResult("failed", error="synthetic failure"),
        controller.SegmentResult("failed", stalled=True),
        controller.SegmentResult("failed", oom=True),
        controller.SegmentResult("aborted"),
        done(oom_retries=1),
        done(capped_oom_retries=1),
        done(uncapped_re_runs=1),
        done(spilled=True),
    ],
)
def test_worker_replaced_after_fault_or_retry(tmp_path, result):
    context = Context([result, done()])
    executor = controller.ProcessExecutor(context=context, reuse=True)
    try:
        run(executor, tmp_path / "one.mp4")
        assert executor.worker is None
        assert not context.processes[0].is_alive()
        run(executor, tmp_path / "two.mp4")
        assert len(context.processes) == 2
    finally:
        executor.close()


def test_worker_replaced_for_settings_and_fifty_parts(tmp_path):
    context = Context([done() for _ in range(52)])
    executor = controller.ProcessExecutor(context=context, reuse=True)
    try:
        for _ in range(50):
            run(executor, tmp_path / "part.mp4")
        assert executor.worker is None
        assert not context.processes[0].is_alive()
        run(executor, tmp_path / "part.mp4")
        run(executor, tmp_path / "part.mp4", {"restore_model": "changed"})
        assert len(context.processes) == 3
        assert not context.processes[1].is_alive()
    finally:
        executor.close()


def test_worker_replaced_when_retry_batch_size_changes(tmp_path):
    context = Context([done(), done()])
    executor = controller.ProcessExecutor(context=context, reuse=True)
    try:
        for batch in (1, 2):
            result = executor.run(
                {}, {"start": 0, "end": 2}, tmp_path / "part.mp4", lambda: False, batch_size=batch
            )
            assert result.status == "done"
        assert len(context.processes) == 2
        assert not context.processes[0].is_alive()
    finally:
        executor.close()


def test_worker_retires_after_a_progress_spill_even_with_incomplete_final_stats(tmp_path):
    context = Context([done()])
    context.messages.append(controller.SegmentProgress(memory={"spilled": True}))
    executor = controller.ProcessExecutor(context=context, reuse=True)
    assert run(executor, tmp_path / "part.mp4").status == "done"
    assert executor.worker is None and not context.processes[0].is_alive()


def test_cancel_discards_even_a_completed_result(tmp_path):
    context = Context([done()])
    executor = controller.ProcessExecutor(context=context, reuse=True)
    assert run(executor, tmp_path / "part.mp4", abort=lambda: True).status == "aborted"
    assert executor.worker is None
    assert not context.processes[0].is_alive()


@pytest.mark.parametrize("global_pause", [True, False])
def test_scheduler_releases_warm_worker_before_waiting_on_pause(
    tmp_path, monkeypatch, global_pause
):
    context = Context([done(), done()])
    executor = controller.ProcessExecutor(context=context, reuse=True)
    assert run(executor, tmp_path / "part.mp4").status == "done"
    assert executor.worker is not None
    executor.worker["job_id"] = "synthetic-paused-job"
    monkeypatch.setattr(controller.JobStore, "read_control_state", lambda *_args: "paused")
    observed = []

    def boundary():
        observed.append(executor.worker is None and not context.processes[0].is_alive())

    controller.run_queue(
        home=tmp_path / "queue",
        executor=executor,
        paused_all=lambda: global_pause,
        between_segments=boundary,
        stopped=lambda: bool(observed),
    )
    assert observed == [True]
    try:
        assert run(executor, tmp_path / "next.mp4").status == "done"
        assert len(context.processes) == 2
    finally:
        executor.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows kill-on-close protection")
def test_worker_dies_before_start_if_windows_protection_fails(tmp_path, monkeypatch):
    context = Context([done()])
    make_process = context.Process

    def process(**kwargs):
        child = make_process(**kwargs)
        child.pid = 123
        return child

    def refuse(_pid):
        raise OSError("Synthetic protection failure")

    context.Process = process
    monkeypatch.setattr(controller, "_attach_windows_job", refuse)
    monkeypatch.setattr(controller, "_kill_process_tree", lambda _pid: None)
    executor = controller.ProcessExecutor(context=context, reuse=True)
    result = run(executor, tmp_path / "part.mp4")
    assert result.status == "failed" and "protect" in result.error
    assert not context.processes[0].is_alive() and executor.worker is None


def test_real_worker_reuses_pid_and_exits_after_cancel(video_factory, build_manifest, tmp_path):
    source = video_factory(frames=12)
    manifest = build_manifest(source, fps="off")
    manifest.pop("id")  # Direct executor test, without a queue store.
    executor = controller.ProcessExecutor(reuse=True)
    process = None
    try:
        first = executor.run(
            manifest,
            {"index": 0, "start": 0, "end": 6},
            tmp_path / "first.mp4",
            lambda: False,
            batch_size=2,
        )
        assert first.status == "done", first.error
        assert executor.worker is not None
        process = executor.worker["process"]
        second = executor.run(
            manifest,
            {"index": 1, "start": 6, "end": 12},
            tmp_path / "second.mp4",
            lambda: False,
            batch_size=2,
        )
        assert second.status == "done", second.error
        assert second.stats is not None
        timeline = second.stats["pipeline_timeline"]
        assert set(timeline) == {"decode", "compute", "encode"}
        for stage in timeline.values():
            assert stage["end_seconds"] >= stage["start_seconds"] >= 0
            assert (
                stage.get("upstream_seconds", 0) + stage.get("downstream_seconds", 0)
                <= stage["wall_seconds"]
            )
        assert executor.worker is not None
        assert executor.worker["process"].pid == process.pid
        cold = controller.ProcessExecutor().run(
            manifest,
            {"index": 1, "start": 6, "end": 12},
            tmp_path / "cold.mp4",
            lambda: False,
            batch_size=2,
        )
        assert cold.status == "done", cold.error
        assert (
            hashlib.sha256((tmp_path / "second.mp4").read_bytes()).digest()
            == hashlib.sha256((tmp_path / "cold.mp4").read_bytes()).digest()
        )
        failed = executor.run(
            manifest,
            {"index": 2, "start": 100, "end": 102},
            tmp_path / "invalid-range.mp4",
            lambda: False,
            batch_size=2,
        )
        assert failed.status == "failed"
        assert executor.worker is None and not process.is_alive()
        assert (
            executor.run(
                manifest,
                {"index": 0, "start": 0, "end": 6},
                tmp_path / "restarted.mp4",
                lambda: False,
                batch_size=2,
            ).status
            == "done"
        )
        assert executor.worker is not None
        process = executor.worker["process"]
        cancelling = time.perf_counter()
        cancelled = executor.run(
            manifest,
            {"index": 0, "start": 0, "end": 6},
            tmp_path / "cancelled.mp4",
            lambda: True,
            batch_size=2,
        )
        assert cancelled.status == "aborted"
        assert not process.is_alive()
        assert time.perf_counter() - cancelling <= 5
    finally:
        executor.close()
    assert process is not None and not process.is_alive()
