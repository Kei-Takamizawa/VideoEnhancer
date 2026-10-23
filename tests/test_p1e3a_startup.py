"""Damaged startup records are retained verbatim in isolated homes."""

import json

import pytest

from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import DEFAULTS, read_settings, save_settings


@pytest.mark.parametrize("raw", [b'{"theme":', b"not JSON", b"[]"])
def test_damaged_settings_use_defaults_and_refuse_save(tmp_path, raw, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_bytes(raw)
    assert read_settings(tmp_path) == DEFAULTS
    with pytest.raises(ValueError, match="damaged"):
        save_settings(tmp_path, {"theme": "dark"})
    assert path.read_bytes() == raw
    monkeypatch.setenv("VE_STORAGE_MOVE_HOLD", "1")
    monkeypatch.setattr(Engine, "_environment", lambda self: None)
    engine = Engine(tmp_path)
    try:
        engine.start()
        assert engine.dispatch("GET", ["settings"], {})["theme"] == DEFAULTS["theme"]
        assert path.read_bytes() == raw
    finally:
        engine.close()
    path.write_text("{}", encoding="utf-8")
    assert save_settings(tmp_path, {"theme": "dark"})["theme"] == "dark"


@pytest.mark.parametrize("filename", ["state.json", "request.json"])
@pytest.mark.parametrize("raw", [b'{"state":', b"not JSON", b"[]"])
def test_damaged_preview_does_not_stop_recovery(tmp_path, filename, raw, monkeypatch):
    monkeypatch.setenv("VE_STORAGE_MOVE_HOLD", "1")
    monkeypatch.setattr(Engine, "_environment", lambda self: None)
    folder = tmp_path / "previews" / ("a" * 32)
    folder.mkdir(parents=True)
    path = folder / filename
    path.write_bytes(raw)
    valid = tmp_path / "previews" / ("b" * 32)
    valid.mkdir()
    (valid / "state.json").write_text(
        json.dumps({"id": "b" * 32, "kind": "compare", "state": "done", "request": {}}),
        encoding="utf-8",
    )
    engine = Engine(tmp_path)
    try:
        engine.start()
        assert "b" * 32 in engine.operations
        assert "a" * 32 not in engine.operations
        assert path.read_bytes() == raw
    finally:
        engine.close()


@pytest.mark.parametrize("kind", ["schedule", "profile", "timing", "model", "tool", "av1"])
@pytest.mark.parametrize("raw", [b'{"broken":', b"not JSON", b"[]"])
def test_other_startup_json_is_skipped_without_rewrite(tmp_path, monkeypatch, kind, raw):
    from videoenhancer.estimate.local import read_local
    from videoenhancer.jobs.store import load_machine_profile
    from videoenhancer.models.registry import ModelRegistry
    from videoenhancer.schedule.windows import Schedule
    from videoenhancer.service.av1_cache import capabilities
    from videoenhancer.service.link_tools import ToolManager

    paths = {
        "schedule": "schedule.json",
        "profile": "profiles/synthetic.json",
        "timing": "timing-observations.json",
        "model": "models/rife-4.25/model.json",
        "tool": "tools/yt-dlp/installed.json",
        "av1": "av1-capabilities.json",
    }
    path = tmp_path / paths[kind]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    monkeypatch.setattr("videoenhancer.media.encode.probe_av1", lambda: (False, "synthetic"))
    if kind == "schedule":
        Schedule.from_file(path)
    elif kind == "profile":
        load_machine_profile(tmp_path, backend="cpu")
    elif kind == "timing":
        read_local(tmp_path, None)
    elif kind == "model":
        ModelRegistry(tmp_path).list_models()
    elif kind == "tool":
        ToolManager(tmp_path).status()
    else:
        capabilities(tmp_path, "synthetic", "fixture")
    assert path.read_bytes() == raw
    monkeypatch.setenv("VE_STORAGE_MOVE_HOLD", "1")
    monkeypatch.setattr(Engine, "_environment", lambda self: None)
    engine = Engine(tmp_path)
    try:
        engine.start()
        assert engine.health()["paused_all"] is True
        assert path.read_bytes() == raw
    finally:
        engine.close()


@pytest.mark.parametrize("filename", ["manifest.json", "analysis.json"])
@pytest.mark.parametrize("raw", [b'{"state":', b"not JSON", b"[]"])
def test_damaged_job_does_not_block_other_jobs(tmp_path, monkeypatch, filename, raw):
    monkeypatch.setenv("VE_STORAGE_MOVE_HOLD", "1")
    monkeypatch.setattr(Engine, "_environment", lambda self: None)
    for letter in ("a", "b"):
        folder = tmp_path / "jobs" / (letter * 32)
        folder.mkdir(parents=True)
        manifest = dict(
            id=letter * 32,
            schema_version=1,
            state="done",
            segments=[],
            input={"path": str(tmp_path / "source.mp4")},
            output=str(tmp_path / "out.mp4"),
            settings={"preset": "fast"},
            media={},
            created_at="2026-10-22T00:00:00Z",
            updated_at="2026-10-22T00:00:00Z",
        )
        if filename == "analysis.json":
            manifest["analysis_file"] = "analysis.json"
            (folder / filename).write_text("{}", encoding="utf-8")
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    path = tmp_path / "jobs" / ("a" * 32) / filename
    path.write_bytes(raw)
    engine = Engine(tmp_path)
    try:
        engine.start()
        assert [j["id"] for j in engine.store.list_jobs(skip_damaged=True)] == ["b" * 32]
        assert path.read_bytes() == raw
        assert any(j["id"] == "a" * 32 and j["record_error"] for j in engine.store.queue_jobs())
    finally:
        engine.close()


@pytest.mark.parametrize("raw", [b'{"state":', b"not JSON", b"[]"])
def test_damaged_control_is_never_overwritten_by_state_updates(tmp_path, raw):
    from videoenhancer.jobs.store import JobStore

    store = JobStore(tmp_path)
    job = dict(id="a" * 32, state="queued")
    path = store.job_dir(job["id"]) / "control.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    store._write_control_unlocked(job)
    assert path.read_bytes() == raw
