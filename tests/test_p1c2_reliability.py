"""Real manifest locks, live forecasts and windowless Windows spawning."""

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_controller import FakeClock, _job
from test_reliability import _two_jobs

from videoenhancer import proc
from videoenhancer.estimate.model import estimate_job
from videoenhancer.jobs.store import JobStore, _manifest_lock
from videoenhancer.schedule import controller
from videoenhancer.schedule.planner import build_plan
from videoenhancer.schedule.windows import Schedule
from videoenhancer.service.engine import Engine


def test_live_frames_reduce_work_and_forecast_inside_step(tmp_path):
    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    job["segments"][0]["state"] = "running"
    job["state"] = "running"
    now = datetime(2026, 1, 1, tzinfo=UTC)
    schedule = Schedule.from_dict({}, __import__("zoneinfo").ZoneInfo("UTC"))
    work, ends = [], []
    for frames in (0, 100, 200):
        job["progress"] = dict(segment=0, frames_done=frames)
        work.append(estimate_job(job).seconds)
        ends.append(
            datetime.fromisoformat(build_plan([job], schedule, now)["jobs"][0]["completion"])
        )
    assert work[0] > work[1] > work[2]
    assert ends[0] > ends[1] > ends[2]


def test_queue_complete_override_waits_for_whole_queue(tmp_path):
    path = tmp_path / "schedule.json"
    value = dict(enabled=True, weekly=[], override_until="queue-complete")
    path.write_text(json.dumps(value), encoding="utf-8")
    schedule = Schedule.from_dict(value, __import__("zoneinfo").ZoneInfo("UTC"))
    assert schedule.current_interval(datetime(2026, 1, 1, tzinfo=UTC))
    assert not Schedule.clear_job_complete_override(path)
    assert json.loads(path.read_text(encoding="utf-8"))["override_until"] == "queue-complete"
    assert Schedule.clear_job_complete_override(path, queue_complete=True)
    assert json.loads(path.read_text(encoding="utf-8"))["override_until"] is None


def test_retry_endpoint_keeps_completed_segments(tmp_path):
    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    job["segments"][0]["state"] = "done"
    job["state"] = "failed"
    engine.store.save(job)
    result = engine.dispatch("POST", ["queue", job["id"], "retry"], {})
    assert result["state"] == "queued"
    assert result["segments"][0]["state"] == "done"
    with pytest.raises(ValueError, match="failed videos only"):
        engine.dispatch("POST", ["queue", job["id"], "retry"], {})


def test_real_stuck_trial_hits_test_deadline_outside_hours(tmp_path, video_factory):
    import psutil

    source = video_factory(width=320, height=180, frames=30)
    engine = Engine(tmp_path / "home", test_stuck_trial=True, test_trial_timeout=5)
    (engine.home / "schedule.json").write_text(
        json.dumps(dict(enabled=True, weekly=[])), encoding="utf-8"
    )
    op = engine.operation(
        "trial",
        dict(
            file=str(source),
            seconds=3,
            settings=dict(preset="fast", backend="cpu", short_side="keep"),
        ),
    )
    engine._auxiliary()
    assert op["state"] == "failed"
    assert op["error"] == "The preview took too long. Try again."
    marker = engine.home / "previews" / op["id"] / "test-stuck.pid"
    pid = int(marker.read_text(encoding="ascii"))
    import time

    deadline = time.monotonic() + 5
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not psutil.pid_exists(pid)
    assert not engine.processes


def test_result_preview_uses_cpu_and_completed_frames_only(
    tmp_path, video_factory, build_manifest, monkeypatch
):
    from videoenhancer.media.probe import probe
    from videoenhancer.pipeline.runner import process_segment
    from videoenhancer.service.preview import render_result_preview

    source = video_factory(width=96, height=64, frames=120)
    job = build_manifest(source, preset="p0-test")
    job.update(
        state="running",
        segments=[
            dict(index=0, start=0, end=60, state="done"),
            dict(index=1, start=60, end=120, state="running"),
        ],
    )
    directory = tmp_path / "job"
    directory.mkdir()
    process_segment(job, job["segments"][0], directory / "seg_00000.mp4", lambda: False)
    monkeypatch.setattr(
        "videoenhancer.pipeline.runner.process_segment",
        lambda *_a, **_kw: pytest.fail("Must reuse the completed result"),
    )
    folder = tmp_path / "preview"
    folder.mkdir()
    result = render_result_preview(job, directory, folder)
    assert result["uses_gpu"] is False
    assert probe(folder / "original-preview.mp4").frame_count == 120
    assert probe(folder / "enhanced-preview.mp4").frame_count == 120
    assert job["segments"][1]["state"] == "running"


def test_real_manifest_lock_quarantines_only_one_job_and_retry_recovers(tmp_path, monkeypatch):
    store, first, second = _two_jobs(tmp_path)
    calls = []
    monkeypatch.setattr(controller, "validate_done_segments", lambda *_: False)
    monkeypatch.setattr(controller, "segment_file_valid", lambda *_: True)
    monkeypatch.setattr(
        "videoenhancer.media.mux.assemble", lambda job, *_a, **_kw: Path(job["output"])
    )

    class Executor:
        def run(self, job, _segment, output, *_a, **_kw):
            calls.append(job["id"])
            output.write_bytes(b"encoded")
            return controller.SegmentResult("done")

    with _manifest_lock(store.job_dir(first["id"])):
        controller.run_queue(
            home=store.home,
            ignore_schedule=True,
            clock=FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
            executor=Executor(),
        )
        marker = store.job_dir(first["id"]) / "quarantine.json"
        assert json.loads(marker.read_text(encoding="utf-8"))["timeouts"] == 3
        assert store.load(first["id"])["quarantined"]
        assert store.load(second["id"])["state"] == "done"
        assert calls == [second["id"]]
    store.set_state(first["id"], "queued")
    assert not marker.exists()
    controller.run_queue(
        home=store.home,
        ignore_schedule=True,
        clock=FakeClock(datetime(2026, 1, 1, tzinfo=UTC)),
        executor=Executor(),
    )
    assert store.load(first["id"])["state"] == "done"


def test_oversized_planner_matches_controller_clock(tmp_path, monkeypatch):
    from zoneinfo import ZoneInfo

    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    now = datetime(2026, 1, 1, 8, tzinfo=UTC)
    schedule = Schedule.from_dict(
        {"enabled": True, "weekly": [{"days": ["thu"], "start": "08:00", "end": "08:15"}]},
        ZoneInfo("UTC"),
    )
    monkeypatch.setattr("videoenhancer.estimate.predict_segment", lambda *_a, **_kw: 1200)
    monkeypatch.setattr("videoenhancer.schedule.planner.predict_segment", lambda *_a, **_kw: 1200)
    monkeypatch.setattr("videoenhancer.schedule.planner.predict_finalization", lambda *_: 0)
    monkeypatch.setattr(controller, "_schedule", lambda *_: schedule)
    monkeypatch.setattr(controller, "validate_done_segments", lambda *_: False)
    starts, ends = [], []
    clock = FakeClock(now)

    class Executor:
        def run(self, _job, _segment, _output, *_a, **_kw):
            starts.append(clock.now())
            clock.sleep(1200)
            ends.append(clock.now())
            return controller.SegmentResult("aborted")

    plan = build_plan([job], schedule, now, days=1)
    controller.run_queue(
        home=store.home, clock=clock, executor=Executor(), stopped=lambda: bool(ends)
    )
    step = plan["timeline"][0]
    assert abs((datetime.fromisoformat(step["start"]) - starts[0]).total_seconds()) <= 1
    assert abs((datetime.fromisoformat(step["end"]) - ends[0]).total_seconds()) <= 1
    assert step["overrun_seconds"] == 300
    assert controller.unit_admission(
        job,
        now + timedelta(seconds=31),
        SimpleNamespace(start=now, end=now + timedelta(seconds=60)),
    ) == (False, False)


@pytest.mark.skipif(os.name != "nt", reason="Real Windows pythonw spawn")
def test_real_pythonw_parent_spawns_windowless_segment_with_none_streams(
    tmp_path, video_factory, build_manifest
):
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    assert pythonw.is_file(), "Windows CI must provide pythonw.exe"
    source = video_factory(frames=12)
    job = build_manifest(source, preset="p0-test")
    segment = dict(index=0, start=0, end=12, predicted_seconds=30, state="running")
    job.update(schema_version=1, state="running", segments=[segment])
    store = JobStore(tmp_path / "home")
    store.save(job)
    request = tmp_path / "request.json"
    request.write_text(json.dumps(dict(job=job, segment=segment)), encoding="utf-8")
    script = tmp_path / "spawn_check.py"
    script.write_text(
        """import json, sys
from pathlib import Path
from videoenhancer.schedule.controller import ProcessExecutor
if __name__ == "__main__":
    root = Path(__file__).parent
    value = json.loads((root / "request.json").read_text(encoding="utf-8"))
    none_streams = sys.stdout is None and sys.stderr is None
    output = root / "home" / "jobs" / value["job"]["id"] / "output.mp4"
    result = ProcessExecutor().run(
        value["job"], value["segment"], output, lambda: False, batch_size=2)
    report = dict(none_streams=none_streams, executable=sys.executable,
                  status=result.status, error=result.error)
    (root / "result.json").write_text(json.dumps(report), encoding="utf-8")
""",
        encoding="utf-8",
    )
    proc.run(
        [str(pythonw), str(script)],
        timeout=90,
        check=True,
        env={**os.environ, "VE_HOME": str(store.home)},
    )
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert result["none_streams"]
    assert result["status"] == "done", result
    assert "pythonw.exe" in result["executable"].lower()
    assert (
        "pythonw.exe"
        in (store.job_dir(job["id"]) / "logs" / "seg_00000.log").read_text(encoding="utf-8").lower()
    )
