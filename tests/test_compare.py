"""Real CPU comparison transport; no production model accuracy or speed claims."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_model_registry import fake_model as fake_model

from videoenhancer.models.registry import C1, ModelRegistry
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.service.compare import cache_key, render_compare
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
        observer = kwargs.get("frame_observer")

        def capture(frame, index):
            if index == 7:
                captured.append(
                    frame.float()
                    .clamp(0, 1)
                    .mul(255)
                    .round()
                    .byte()
                    .permute(1, 2, 0)
                    .contiguous()
                    .cpu()
                    .numpy()
                    .tobytes()
                )
            if observer:
                observer(frame, index)

        kwargs["frame_observer"] = capture
        return process_segment(job, *args, **kwargs)

    captured = []
    monkeypatch.setattr(module, "source_index", indexed)
    monkeypatch.setattr(module, "analyze_range", analyzed)
    monkeypatch.setattr(module, "record_models", lambda *_: {})
    monkeypatch.setattr(module, "process_segment", cpu_fixture)
    destination = home / "previews" / "comparison"
    destination.mkdir(parents=True)
    source_path = video_factory(frames=90)
    result = render_compare(
        {
            "file": str(source_path),
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
    from videoenhancer import proc
    from videoenhancer.config import executable

    assert len(captured) == len(ids)
    for model_id, raw in zip(ids, captured, strict=True):
        decoded = proc.run(
            [
                executable("ffmpeg"),
                "-v",
                "error",
                "-i",
                str(destination / f"{model_id}-first-look.png"),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
        ).stdout
        assert decoded == raw
    reused_folder = home / "previews" / "reused"
    reused_folder.mkdir()
    monkeypatch.setattr(
        module,
        "process_segment",
        lambda *_a, **_k: pytest.fail("Cached models must not render again"),
    )
    monkeypatch.setattr(
        module, "Encoder", lambda *_a, **_k: pytest.fail("Cached Original must not render again")
    )
    reused = render_compare(
        {
            "file": str(source_path),
            "seconds": 3,
            "models": ids[:2],
            "settings": {
                "preset": "standard",
                "backend": "cpu",
                "short_side": "keep",
                "fps": "off",
            },
        },
        reused_folder,
    )
    assert reused["original_reused"]
    assert all(item["reused"] for item in reused["items"])
    settings = {"preset": "standard", "backend": "cpu", "short_side": "keep", "fps": "off"}
    engine = Engine(home)
    monkeypatch.setattr(engine, "chosen", lambda _: settings)
    monkeypatch.setattr(ModelRegistry, "weights", lambda *_a, **_k: Path("unused"))
    monkeypatch.setattr(engine, "geometry_warning", lambda *_: None)
    immediate = engine.operation(
        "compare", dict(file=str(source_path), seconds=3, models=ids[:2], settings=settings)
    )
    assert immediate["state"] == "done"
    assert immediate["result"]["original_reused"]
    assert all(item["reused"] for item in immediate["result"]["items"])
    assert not engine.processes
    engine.close()
    before = cache_key(source_path, 0, 90, settings, ids[0], registry)
    assert cache_key(source_path, 1, 90, settings, ids[0], registry) != before
    assert (
        cache_key(source_path, 0, 90, {**settings, "short_side": 1080}, ids[0], registry) != before
    )
    model_path = registry.folder(ids[0]) / "model.json"
    changed = json.loads(model_path.read_text())
    changed["weights"]["sha256"] = "a" * 64
    model_path.write_text(json.dumps(changed))
    assert cache_key(source_path, 0, 90, settings, ids[0], registry) != before
    changed["weights"]["sha256"] = model["weights"]["sha256"]
    model_path.write_text(json.dumps(changed))
    source_path.touch()
    assert cache_key(source_path, 0, 90, settings, ids[0], registry) != before


def test_new_compare_cancels_previous_compare_only(fake_model, monkeypatch):
    from types import SimpleNamespace

    folder, model, registry = fake_model
    registry.add(folder)
    engine = Engine(registry.home)
    settings = {"preset": "standard", "restore_model": model["id"], "fps": "off", "backend": "cpu"}
    monkeypatch.setattr(engine, "chosen", lambda _: settings)
    monkeypatch.setattr(engine, "geometry_warning", lambda *_: None)
    monkeypatch.setattr(
        "videoenhancer.service.engine.probe", lambda *_a, **_k: SimpleNamespace(to_dict=lambda: {})
    )
    killed = []
    monkeypatch.setattr("videoenhancer.service.engine._kill_process_tree", killed.append)
    request = {"file": str(folder / model["weights"]["filename"]), "models": [model["id"]]}
    old = engine.operation("compare", request)
    old["state"] = "running"
    engine.processes[old["id"]] = SimpleNamespace(pid=12345, poll=lambda: None)
    trial = engine.operation("trial", {"file": request["file"]})
    new = engine.operation("compare", request)
    assert old["cancel_requested"] is True
    assert killed == [12345]
    assert "cancel_requested" not in trial
    assert new["state"] == "waiting"
    engine.processes.clear()
    engine.close()


def test_current_licence_display_preserves_existing_resume_identity(tmp_path, monkeypatch):
    registry = ModelRegistry(tmp_path)
    path = registry.folder(C1) / "model.json"
    legacy = registry.manifest(C1)
    legacy.update(licence="Apache-2.0", commercial_use_allowed=True)
    path.write_text(json.dumps(legacy))
    monkeypatch.setattr(registry, "weights", lambda *_args, **_kwargs: Path("unused"))
    before = registry.snapshot(C1, "restore")
    public = registry.public_manifest(C1)
    assert public["licence"] == "Code Apache-2.0; the weights' terms are not stated"
    assert public["commercial_use_allowed"] is False
    assert next(m for m in registry.list_models() if m["id"] == C1)["licence"] == public["licence"]
    assert registry.snapshot(C1, "restore") == before
    assert registry.manifest(C1)["licence"] == "Apache-2.0"


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
    with pytest.raises(ValueError, match="default for Standard"):
        engine.dispatch("DELETE", ["models", model["id"]], {})
    save_settings(registry.home, {"restore_model": ""})
    with pytest.raises(ValueError, match="1 videos in the queue use it"):
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


def test_cache_record_cannot_copy_a_file_outside_its_session(tmp_path):
    from videoenhancer.service.compare import reuse_preview

    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (tmp_path / "private.mp4").write_bytes(b"must not be copied")
    (old / "cache.json").write_text(json.dumps({"key": {"filename": "../private.mp4", "fps": 30}}))
    assert reuse_preview(new, "key", "original") is None
    assert not (new / "original-preview.mp4").exists()
