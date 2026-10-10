"""Real CPU comparison transport; no production model accuracy or speed claims."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_model_registry import fake_model as fake_model

from videoenhancer.models.registry import C1, ModelRegistry
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.service.compare import render_compare
from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import save_settings


def test_catalog_does_not_change_existing_builtin_snapshot(tmp_path, monkeypatch):
    registry = ModelRegistry(tmp_path)
    manifest = registry.manifest(C1)
    legacy = {k: v for k, v in manifest.items() if k != "catalog"}
    (registry.folder(C1) / "model.json").write_text(json.dumps(legacy))
    monkeypatch.setattr(registry, "weights", lambda *_args, **_kwargs: Path("unused"))
    snapshot = registry.snapshot(C1, "restore")
    assert (
        snapshot["manifest_sha256"]
        == hashlib.sha256(
            json.dumps(legacy, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    assert registry.manifest(C1)["catalog"]["title"] == "Gentle cleanup"


def test_compare_uses_one_index_one_analysis_and_publishes_each_real_cpu_preview(
    tmp_path, video_factory, fake_model, monkeypatch
):
    folder, model, registry = fake_model
    home = registry.home
    monkeypatch.setenv("VE_HOME", str(home))
    ids = []
    for i in range(3):
        value = {**model, "id": f"fixture-{i}"}
        (folder / "model.json").write_text(json.dumps(value))
        registry.add(folder)
        ids.append(value["id"])
    import videoenhancer.service.compare as module

    counts = {"index": 0, "analysis": 0}
    index, analysis = module.source_index, module.analyze_range

    def indexed(*args, **kwargs):
        counts["index"] += 1
        return index(*args, **kwargs)

    def analyzed(*args, **kwargs):
        counts["analysis"] += 1
        return analysis(*args, **kwargs)

    def cpu_fixture(job, *args, **kwargs):
        job = copy.deepcopy(job)
        job["settings"].update(preset="passthrough", backend="cpu", fps="off")
        job["settings"].pop("restore_model", None)
        return process_segment(job, *args, **kwargs)

    monkeypatch.setattr(module, "source_index", indexed)
    monkeypatch.setattr(module, "analyze_range", analyzed)
    monkeypatch.setattr(module, "record_models", lambda *_: {})
    monkeypatch.setattr(module, "process_segment", cpu_fixture)
    destination = home / "previews" / "comparison"
    destination.mkdir(parents=True)
    result = render_compare(
        {
            "file": str(video_factory(frames=90)),
            "seconds": 3,
            "models": ids,
            "settings": {
                "preset": "standard",
                "backend": "cpu",
                "short_side": "keep",
                "fps": "off",
            },
        },
        destination,
    )
    assert counts == {"index": 1, "analysis": 1}
    assert [item["id"] for item in result["items"]] == ids
    assert all(item["fps"] > 0 for item in result["items"])
    assert len(list(destination.glob("*-preview.mp4"))) == 4
    assert not list(destination.glob("*-raw.mp4"))
    assert json.loads((destination / "progress.json").read_text())["percent"] == 100


def test_defaults_validate_weights_and_removal_protects_queued_models(
    tmp_path, fake_model, monkeypatch
):
    from test_controller import _job

    folder, model, registry = fake_model
    monkeypatch.setenv("VE_HOME", str(registry.home))
    registry.add(folder)
    prefs = save_settings(registry.home, {"restore_model": model["id"]})
    engine = Engine(registry.home)
    chosen = engine.chosen({"backend": "cpu"})
    assert chosen["restore_model"] == prefs["restore_model"]
    assert "restore_model" not in engine.chosen({"preset": "fast", "backend": "cpu"})
    job = _job(engine.store, tmp_path)
    job["settings"].update(preset="standard", restore_model=model["id"])
    engine.store.save(job)
    with pytest.raises(ValueError, match="Used by 1 videos"):
        engine.dispatch("DELETE", ["models", model["id"]], {})
    job["state"] = "done"
    engine.store.save(job)
    engine.dispatch("DELETE", ["models", model["id"]], {})
    assert not registry.folder(model["id"]).exists()
    engine.close()


def test_compare_cache_retains_five_sessions_and_two_gb(tmp_path):
    engine = Engine(tmp_path / "home")
    for i in range(7):
        op = dict(
            id=f"session-{i}", kind="compare", state="done", created_at=str(i), result={"items": []}
        )
        engine.operations[op["id"]] = op
        engine._save_operation(op)
        (engine.home / "previews" / op["id"] / "original-preview.mp4").write_bytes(b"preview")
    engine._prune_compare_cache()
    assert sum(o["state"] == "done" for o in engine.operations.values()) == 5
    assert not (engine.home / "previews/session-0/original-preview.mp4").exists()
    engine.close()
