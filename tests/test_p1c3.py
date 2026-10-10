"""P1c-3 mutable settings, unstarted jobs, and real CPU preview cancellation."""

import threading
import time

import pytest
from test_controller import _job

from videoenhancer.jobs.store import JobStore
from videoenhancer.media.encode import Encoder
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import read_settings, save_settings


def test_seen_failures_persist_without_changing_defaults(tmp_path):
    initial = read_settings(tmp_path)
    updated = save_settings(tmp_path, {"seen_failures": ["one", "two"]})
    assert updated["preset"] == initial["preset"]
    assert read_settings(tmp_path)["seen_failures"] == ["one", "two"]
    with pytest.raises(ValueError, match="job ids"):
        save_settings(tmp_path, {"seen_failures": [42]})


def test_change_mode_reestimates_only_unstarted_jobs(tmp_path, monkeypatch):
    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    monkeypatch.setattr("videoenhancer.models.registry.record_models", lambda *_: {})
    monkeypatch.setattr(
        "videoenhancer.models.registry.ModelRegistry.weights", lambda *_args, **_kwargs: tmp_path
    )
    fast = store.change_mode(job["id"], "fast")
    standard = store.change_mode(job["id"], "standard")
    assert fast["segments"][0]["predicted_seconds"] < standard["segments"][0]["predicted_seconds"]
    assert fast["segments"][0]["start"] == standard["segments"][0]["start"]
    standard["started_at"] = "2026-10-10T00:00:00Z"
    store.save(standard)
    with pytest.raises(ValueError, match="Already started"):
        store.change_mode(job["id"], "fast")


@pytest.mark.parametrize("quit_app", [False, True])
def test_preview_close_or_quit_cancels_real_encoder_and_removes_partial(
    tmp_path, video_factory, build_manifest, monkeypatch, quit_app
):
    source = video_factory(frames=60)
    job = build_manifest(source, preset="p0-test")
    job.update(
        schema_version=1,
        state="done",
        output=str(tmp_path / "output.mp4"),
        segments=[dict(index=0, start=0, end=60, state="done")],
    )
    engine = Engine(tmp_path / "home")
    engine.store.save(job)
    directory = engine.store.job_dir(job["id"])
    process_segment(job, job["segments"][0], directory / "seg_00000.mp4", lambda: False)
    entered = threading.Event()
    original_write = Encoder.write

    def held_write(encoder, frame):
        original_write(encoder, frame)
        entered.set()
        deadline = time.monotonic() + 10
        while not engine.stop.is_set() and not any(
            op.get("cancel_requested") for op in engine.operations.values()
        ):
            assert time.monotonic() < deadline
            time.sleep(0.01)

    monkeypatch.setattr(Encoder, "write", held_write)
    op = engine.result_preview(job["id"])
    assert entered.wait(5)
    if quit_app:
        engine.close()
    else:
        engine.cancel_operation(op["id"])
        engine.preview_threads[op["id"]].join(timeout=5)
    assert not engine.preview_threads[op["id"]].is_alive()
    assert op["state"] == "cancelled"
    assert not list((engine.home / "previews" / op["id"]).glob("*.mp4"))
    assert (directory / "seg_00000.mp4").exists()
    monkeypatch.setattr(Encoder, "write", original_write)
    reopened = Engine(engine.home)
    next_op = reopened.result_preview(job["id"])
    reopened.preview_threads[next_op["id"]].join(timeout=10)
    assert next_op["id"] != op["id"]
    assert next_op["state"] == "done", next_op
    reopened.close()


def test_schedule_preview_bounds_and_bar_progress(tmp_path):
    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    response = engine.dispatch("POST", ["schedule", "preview"], {"enabled": False})

    def end(plan):
        return plan["jobs"][0]["completion"]

    assert end(response["best"]) < end(response["plan"]) < end(response["worst"])
    step = response["plan"]["timeline"][0]
    assert step["start_percent"] < step["end_percent"]
    assert engine.store.load(job["id"])["correction_factor"] == 1
