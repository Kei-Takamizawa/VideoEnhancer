"""Gateway jobs publish only complete outputs and leave no named history."""

import json

import pytest

from videoenhancer.remote.jobs import RemoteJobs, activity, automatic_format, clean_title, publish
from videoenhancer.remote.power import Awake


def test_clean_title_and_clash_publication(tmp_path):
    assert clean_title("CON.txt") == "_CON.txt"
    assert clean_title("a/b:*? .") == "a_b___"
    assert len(clean_title("x" * 300)) <= 120
    partial = tmp_path / ".abc.partial.mp4"
    partial.write_bytes(b"complete")
    (tmp_path / "Title (enhanced).mp4").write_bytes(b"keep")
    result = publish(partial, "Title")
    assert result.name == "Title (enhanced) 2.mp4"
    assert result.read_bytes() == b"complete" and not partial.exists()
    assert (tmp_path / "Title (enhanced).mp4").read_bytes() == b"keep"


def test_activity_is_nameless_and_bounded(tmp_path):
    path = tmp_path / "activity.log"
    job = dict(
        settings={"preset": "standard"},
        media={"width": 1920, "height": 1080, "duration": 1},
        input={"path": "secret/title.mp4"},
        source={"url": "https://secret.example/title"},
        error="private title",
    )
    for _ in range(6000):
        activity(path, job, "failed", 0, 2)
    data = path.read_text()
    assert "secret" not in data and "title" not in data and "https" not in data
    assert path.stat().st_size <= 1_000_000
    assert all(json.loads(line)["outcome"] == "failed" for line in data.splitlines())


def test_awake_released_even_on_failure():
    calls = []
    with pytest.raises(ValueError), Awake(calls.append):
        raise ValueError("synthetic")
    assert calls == [0x80000001, 0x80000000]


def test_automatic_format_is_best_1080_sdr():
    formats = [
        dict(id="720", width=1280, height=720),
        dict(id="1080", width=1920, height=1080),
        dict(id="hdr", width=1920, height=1080, dynamic_range="HDR"),
        dict(id="4k", width=3840, height=2160),
    ]
    assert automatic_format(formats)["id"] == "1080"


@pytest.mark.parametrize("outcome", ["done", "failed", "cancelled"])
def test_terminal_cleanup_keeps_only_finished_library_file(tmp_path, outcome):
    from types import SimpleNamespace

    from test_controller import _job

    from videoenhancer.remote.adapter import EngineAdapter
    from videoenhancer.service.engine import Engine

    home = tmp_path / "home"
    engine = Engine(home)
    adapter = EngineAdapter(engine, home, {"library_folder": str(tmp_path / "library")})
    notices = []
    push = SimpleNamespace(finished=lambda *args: notices.append(args))
    manager = RemoteJobs(adapter, push)
    job = _job(engine.store, tmp_path)
    incoming = home / "remote/incoming" / job["id"]
    incoming.mkdir(parents=True)
    source = incoming / "source.mp4"
    source.write_bytes(b"source")
    library = adapter.library.folder
    library.mkdir()
    partial = library / f".{job['id']}.partial.mp4"
    partial.write_bytes(b"result")
    job.update(
        state=outcome,
        input={"path": str(source)},
        output=str(partial),
        source={
            "downloaded_at": "2026-11-02T00:00:00Z",
            "remote": {"device": "device", "title": "Private title", "folder": str(incoming)},
        },
    )
    job["segments"][0]["state"] = "done" if outcome == "done" else "pending"
    check_id = "synthetic-check"
    job["source"]["remote"]["check_id"] = check_id
    preview = home / "previews" / check_id
    preview.mkdir(parents=True)
    (preview / "link-metadata.json").write_text("{}", encoding="utf-8")
    adapter.requests[check_id] = "device"
    engine.store.save(job)
    (engine.store.job_dir(job["id"]) / "working.bin").write_bytes(b"work")
    try:
        manager.sweep()
        assert not incoming.exists()
        assert not engine.store.job_dir(job["id"]).exists()
        assert not preview.exists() and check_id not in adapter.requests
        assert len(list(library.glob("*.mp4"))) == (1 if outcome == "done" else 0)
        log = (home / "remote/activity.log").read_text()
        assert "Private title" not in log and str(source) not in log
        assert len(log.splitlines()) == 1
        manager.sweep()
        assert len((home / "remote/activity.log").read_text().splitlines()) == 1
        assert bool(notices) == (outcome != "cancelled")
    finally:
        engine.close()


def test_cancelled_snapshot_refreshes_when_running_segment_stops(tmp_path):
    from types import SimpleNamespace

    from test_controller import _job

    from videoenhancer.remote.adapter import EngineAdapter
    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    adapter = EngineAdapter(engine, engine.home, {"library_folder": str(tmp_path / "library")})
    manager = RemoteJobs(adapter, SimpleNamespace(finished=lambda *_: None))
    job = _job(engine.store, tmp_path)
    folder = engine.home / "remote/incoming" / job["id"]
    folder.mkdir(parents=True)
    job.update(
        state="cancelled",
        source={
            "downloaded_at": "now",
            "remote": {"device": "d", "title": "Private", "folder": str(folder)},
        },
    )
    adapter.library.folder.mkdir()
    job["output"] = str(adapter.library.folder / ".partial.mp4")
    job["segments"][0]["state"] = "running"
    engine.store.save(job)
    try:
        manager.sweep()
        assert engine.store.job_dir(job["id"]).exists()
        engine._recover()
        manager.sweep()
        assert not engine.store.job_dir(job["id"]).exists()
    finally:
        engine.close()
