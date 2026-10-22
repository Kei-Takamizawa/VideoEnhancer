"""Damaged startup records are retained verbatim in isolated homes."""

import json

import pytest

from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import DEFAULTS, read_settings, save_settings


@pytest.mark.parametrize("raw", [b'{"theme":', b"not JSON", b"[]"])
def test_damaged_settings_use_defaults_and_refuse_save(tmp_path, raw):
    path = tmp_path / "settings.json"
    path.write_bytes(raw)
    assert read_settings(tmp_path) == DEFAULTS
    with pytest.raises(ValueError, match="damaged"):
        save_settings(tmp_path, {"theme": "dark"})
    assert path.read_bytes() == raw
    path.write_text("{}", encoding="utf-8")
    assert save_settings(tmp_path, {"theme": "dark"})["theme"] == "dark"


@pytest.mark.parametrize("filename", ["state.json", "request.json"])
@pytest.mark.parametrize("raw", [b'{"state":', b"not JSON", b"[]"])
def test_damaged_preview_does_not_stop_recovery(tmp_path, filename, raw):
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
        engine._recover()
        assert "b" * 32 in engine.operations
        assert "a" * 32 not in engine.operations
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
