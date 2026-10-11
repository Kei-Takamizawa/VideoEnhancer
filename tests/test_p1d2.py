import copy

import pytest
from test_service import api as api

from videoenhancer.service.engine import Engine


def test_manifest_cache_invalidation_and_caller_mutation_isolation(tmp_path, monkeypatch):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    calls = []
    original = engine.store.load
    monkeypatch.setattr(
        engine.store, "load", lambda job_id: calls.append(job_id) or original(job_id)
    )
    first = engine.store.list_jobs()
    first[0]["settings"]["codec"] = "mutated"
    assert engine.store.list_jobs()[0]["settings"].get("codec") != "mutated"
    assert calls == [job["id"]]
    engine.store.set_state(job["id"], "paused")
    assert engine.store.list_jobs()[0]["state"] == "paused"
    assert len(calls) == 2
    engine.close()


def test_queue_metadata_preserves_timing_without_copying_quality_samples(tmp_path):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    job["segments"][0]["stats"] = dict(fps=12.5, inline_quality=[{"frame": 1}], memory_samples=[1])
    engine.store.save(job)
    metadata = engine.store.list_jobs(include_analysis=False)[0]
    assert metadata["segments"][0]["stats"] == {"fps": 12.5}
    assert engine.store.list_jobs()[0]["segments"][0]["stats"]["inline_quality"] == [{"frame": 1}]
    engine.close()


def test_history_cache_ignores_access_time_but_refreshes_changed_size(tmp_path):
    import os
    from pathlib import Path

    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    engine.store.set_state(job["id"], "done")
    source = Path(job["input"]["path"])
    engine.queue()
    cached = engine._history_rows[job["id"]][1]
    info = source.stat()
    os.utime(source, ns=(info.st_atime_ns + 10_000_000_000, info.st_mtime_ns))
    engine.queue()
    assert engine._history_rows[job["id"]][1] is cached
    source.write_bytes(b"changed synthetic bytes")
    row = engine.queue()["jobs"][0]
    assert row["original_bytes"] == len(b"changed synthetic bytes")
    assert engine._history_rows[job["id"]][1] is not cached
    engine.close()


def test_av1_cache_uses_exact_gpu_and_driver(tmp_path, monkeypatch):
    from videoenhancer.service.av1_cache import capabilities

    calls = []
    monkeypatch.setattr(
        "videoenhancer.media.encode.probe_av1", lambda: calls.append("probe") or (True, None)
    )
    monkeypatch.setattr(
        "videoenhancer.media.encode.av1_minimum_size", lambda: calls.append("minimum") or (130, 66)
    )
    first = capabilities(tmp_path, "RTX", "1")
    assert capabilities(tmp_path, "RTX", "1") == first
    assert calls == ["probe", "minimum"]
    capabilities(tmp_path, "RTX", "2")
    assert calls == ["probe", "minimum"] * 2


def test_hidden_cancel_failure_reappears_as_failed(tmp_path, monkeypatch):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    job.update(cancel_cleanup=True, remove_on_cancel=True, state="cancelled")
    engine.store.save(job)
    monkeypatch.setattr(engine, "remove", lambda _: (_ for _ in ()).throw(OSError("locked")))
    engine._finish_cancellations()
    result = engine.queue()["jobs"][0]
    assert result["state"] == "failed" and "locked" in result["error"]
    assert not engine.store.load(job["id"])["remove_on_cancel"]
    engine.close()


def test_clear_reports_partial_failure_and_restores_visibility(tmp_path, monkeypatch):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    engine.store.set_state(job["id"], "done")
    monkeypatch.setattr(engine, "remove", lambda _: (_ for _ in ()).throw(OSError("locked")))
    with pytest.raises(ValueError, match="not removed.*locked"):
        engine.history_action("clear", {})
    assert engine.queue()["jobs"][0]["id"] == job["id"]
    engine.close()


def test_stills_transport_requires_authorization_and_published_name(api):
    import urllib.error

    engine, _, request = api
    folder = engine.home / "previews" / "still"
    folder.mkdir(parents=True)
    raw = b"\x89PNG\r\n\x1a\nsynthetic"
    (folder / "original-first-look.png").write_bytes(raw)
    engine.operations["still"] = dict(
        id="still", kind="compare", state="running", result={"first_looks": [{"id": "original"}]}
    )
    with request("operations/still/stills/original") as response:
        assert response.headers["Content-Type"] == "image/png"
        assert response.read() == raw
    with pytest.raises(urllib.error.HTTPError) as forbidden:
        request("operations/still/stills/original", token=False)
    assert forbidden.value.code == 401
    with pytest.raises(urllib.error.HTTPError):
        request("operations/still/stills/unpublished")


def test_output_check_failure_keeps_original(tmp_path, monkeypatch):
    from test_controller import _job

    from videoenhancer.service.deletion import finish_original_deletions

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    job["settings"]["delete_original_after"] = True
    job["state"] = "done"
    engine.store.save(job)
    original = copy.deepcopy(job["input"])
    monkeypatch.setattr(
        "videoenhancer.service.deletion.verify_output",
        lambda _: (_ for _ in ()).throw(ValueError("forced check failure")),
    )
    finish_original_deletions(engine.store)
    assert "forced check failure" in engine.store.load(job["id"])["original_delete_result"]
    assert engine.store.load(job["id"])["input"] == original
    engine.close()


def test_b8_health_and_file_states_are_exposed_over_http(api):
    import json

    from test_controller import _job

    engine, _, request = api
    job = _job(engine.store, engine.home)
    with request("health") as response:
        assert json.load(response)["waiting_count"] == 1
    engine.store.set_state(job["id"], "done")
    with request("queue") as response:
        row = next(item for item in json.load(response)["jobs"] if item["id"] == job["id"])
        assert row["original_state"] == "present"
        assert row["output_state"] == "missing"


def test_live_operation_changes_do_not_break_event_snapshots(tmp_path):
    import threading

    engine = Engine(tmp_path / "home")
    stop = threading.Event()

    def mutate():
        while not stop.is_set():
            with engine.lock:
                engine.operations["live"] = dict(id="live", state="running", result={"items": []})
                engine.operations["live"]["result"]["items"].append({"progress": 30})
                engine.operations.pop("live")

    worker = threading.Thread(target=mutate)
    worker.start()
    try:
        for _ in range(50):
            snapshot = engine.event_snapshot()
            assert isinstance(snapshot["queue"]["operations"], list)
    finally:
        stop.set()
        worker.join(timeout=5)
        engine.close()


def test_manifest_scan_ignores_non_directory_entries(tmp_path, monkeypatch):
    import os

    from test_controller import _job

    from videoenhancer.jobs.store import JobStore

    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    lock = store.jobs_dir / "manifest.lock"
    lock.write_text("synthetic lock", encoding="utf-8")
    original = os.stat

    def checked_stat(path, *args, **kwargs):
        assert str(path) != str(lock / "manifest.json"), "lock file was treated as a job folder"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", checked_stat)
    assert [item["id"] for item in store.list_jobs()] == [job["id"]]
    assert store.event_state()[0][0][0] == job["id"]
