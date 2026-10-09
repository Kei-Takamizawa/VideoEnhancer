"""Model data validation, stage selection and durable provenance."""

import copy
import json
import shutil
import weakref
from fractions import Fraction

import pytest
import torch

from videoenhancer import cli
from videoenhancer.jobs.store import JobStore, add_job
from videoenhancer.models.registry import (
    ADAPTERS,
    C1,
    RIFE,
    ModelRegistry,
    record_models,
    register_adapter,
    sha256,
    validate_job_models,
    validate_manifest,
)
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.pipeline.stages import FrameBatch, Stage


def test_adapter_source_path_rejects_model_folder_redirect(tmp_path, monkeypatch):
    from videoenhancer.models.sources import source_path

    home = tmp_path / "home"
    cache = home / "adapter-sources"
    model = home / "models" / "custom"
    monkeypatch.setenv("VE_HOME", str(home))
    # Resolve is mocked so Windows developer-mode symlink privileges are unnecessary.
    redirected = cache / "upstream" / "net.py"
    original_resolve = type(cache).resolve

    def resolve(path, *args, **kwargs):
        if path == redirected:
            return model / "net.py"
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(type(cache), "resolve", resolve)
    assert source_path(cache, cache / "safe" / "net.py") == cache / "safe" / "net.py"
    with pytest.raises(ValueError, match="outside model data"):
        source_path(cache, redirected)


def test_calibration_records_identity_and_counts_computed_pairs(fake_model, monkeypatch):
    from videoenhancer.bench.calibration import calibrate_models
    from videoenhancer.pipeline.stages import Blend2xStage

    class InferenceBlend(Blend2xStage):
        def process(self, batch):
            assert torch.is_inference_mode_enabled()
            return super().process(batch)

    folder, model, registry = fake_model
    registry.add(folder)
    paired = copy.deepcopy(model)
    paired.update(
        id="test-interp",
        architecture="blend-test",
        task="interpolate",
        temporal=True,
        clip_length=8,
        clip_overlap=1,
    )
    incoming = folder.parent / "interpolation"
    incoming.mkdir()
    shutil.copyfile(folder / "weights.pt", incoming / "weights.pt")
    (incoming / "model.json").write_text(json.dumps(paired), encoding="utf-8")
    monkeypatch.setitem(
        ADAPTERS, "blend-test", ("interpolate", lambda *_: InferenceBlend(Fraction(30)))
    )
    registry.add(incoming)
    monkeypatch.setattr(
        registry,
        "list_models",
        lambda: [registry.manifest(model["id"]), registry.manifest(paired["id"])],
    )
    results = calibrate_models(
        registry, backend="cpu", restore_size=(32, 32), interpolate_size=(32, 32), repeats=2
    )
    for model_id, processed in ((model["id"], 2), (paired["id"], 8)):
        entry = results[model_id]
        assert entry["status"] == "measured"
        assert entry["identity"]["sha256"] == model["weights"]["sha256"]
        assert entry["processed_frames_or_pairs"] == processed
        assert entry["seconds_per_pixel_frame"] == pytest.approx(
            entry["median_seconds"] / (32 * 32 * processed)
        )


class IdentityRestore(Stage):
    name = "restore"
    single_frame = True
    clip_length = 1
    clip_overlap = 0


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    def factory(_manifest, _weights, _settings, _rate, _cuts):
        return IdentityRestore()

    monkeypatch.setitem(ADAPTERS, "identity-test", ("restore", factory))
    monkeypatch.setenv("VE_HOME", str(tmp_path / "home"))
    folder = tmp_path / "incoming"
    folder.mkdir()
    (folder / "weights.pt").write_bytes(b"fake weights are never deserialized")
    model = dict(
        id="test-restore",
        display_name="Test restoration",
        version="1",
        description="CPU test",
        task="restore",
        architecture="identity-test",
        architecture_params={},
        weights=dict(filename="weights.pt", sha256=sha256(folder / "weights.pt")),
        licence="Test fixture only",
        commercial_use_allowed=False,
        scale=1,
        temporal=False,
        precision="fp32",
    )
    (folder / "model.json").write_text(json.dumps(model), encoding="utf-8")
    return folder, model, ModelRegistry()


def test_manifest_valid_and_missing_field(fake_model):
    _, model, _ = fake_model
    assert validate_manifest(model)["id"] == "test-restore"
    invalid = copy.deepcopy(model)
    del invalid["licence"]
    with pytest.raises(ValueError, match="missing fields: licence"):
        validate_manifest(invalid)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("architecture", "unknown", "Unknown model adapter"),
        ("task", "interpolate", "requires task restore"),
        ("precision", "bf16", "precision"),
        ("id", "../unsafe", "Model id"),
        ("id", "con", "reserved Windows"),
        ("scale", 4, "scale=1"),
        ("commercial_use_allowed", "yes", "boolean"),
        ("licence", "", "nonempty"),
    ],
)
def test_manifest_rejects_invalid_data(fake_model, field, value, match):
    _, model, _ = fake_model
    invalid = copy.deepcopy(model)
    invalid[field] = value
    with pytest.raises(ValueError, match=match):
        validate_manifest(invalid)


@pytest.mark.parametrize("filename", ["../weights.pt", "sub/weights.pt", "x:stream", "x\\y"])
def test_manifest_rejects_weight_path_traversal(fake_model, filename):
    _, model, _ = fake_model
    invalid = copy.deepcopy(model)
    invalid["weights"]["filename"] = filename
    with pytest.raises(ValueError, match="plain filename"):
        validate_manifest(invalid)


def test_install_verify_list_remove_and_ignore_code(fake_model):
    folder, model, registry = fake_model
    (folder / "adapter.py").write_text("raise RuntimeError('must never execute')", encoding="utf-8")
    registry.add(folder)
    installed = registry.folder(model["id"])
    assert {p.name for p in installed.iterdir()} == {"model.json", "weights.pt"}
    assert next(m for m in registry.list_models() if m["id"] == model["id"])["weights_verified"]
    with pytest.raises(ValueError, match="expected interpolate"):
        registry.manifest(model["id"], "interpolate")
    with pytest.raises(ValueError, match="already installed"):
        registry.add(folder)
    with pytest.raises(ValueError, match="built-in"):
        registry.remove(C1)
    (installed / "weights.pt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        registry.weights(model, download=True)
    assert not next(m for m in registry.list_models() if m["id"] == model["id"])["weights_verified"]
    registry.remove(model["id"])
    assert not installed.exists()


def test_add_rejects_missing_or_wrong_hash(fake_model):
    folder, _, registry = fake_model
    (folder / "weights.pt").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        registry.add(folder)
    (folder / "weights.pt").unlink()
    with pytest.raises(ValueError, match="missing"):
        registry.add(folder)


def test_register_adapter_rejects_duplicate(fake_model):
    with pytest.raises(ValueError, match="already registered"):
        register_adapter("identity-test", "restore", lambda *_args: IdentityRestore())


@pytest.mark.parametrize("preset", ["fast", "standard", "resize", "p0-test", "passthrough"])
def test_fake_registered_adapter_runs_cpu_pipeline(
    fake_model, video_factory, build_manifest, tmp_path, monkeypatch, preset
):
    calls = []

    def process(_self, batch):
        calls.append(batch.indices)
        return batch

    monkeypatch.setattr(IdentityRestore, "process", process)
    folder, model, registry = fake_model
    registry.add(folder)
    source = video_factory(width=64, height=64, frames=9)
    job = build_manifest(source, preset=preset, fps="off", restore_model=model["id"])
    job["models"] = record_models(job["settings"], registry.home)
    stats = process_segment(
        job, {"index": 0, "start": 0, "end": 9}, tmp_path / "registered.mp4", lambda: False
    )
    assert stats["output_frames"] == 9
    assert stats["luma_outliers"] == []
    assert calls, "An explicitly selected restoration adapter must actually process frames."


def test_single_frame_restore_supplies_interpolation_context(
    fake_model, video_factory, build_manifest, tmp_path, monkeypatch
):
    from videoenhancer.pipeline import runner
    from videoenhancer.pipeline.stages import Blend2xStage

    folder, model, registry = fake_model
    registry.add(folder)
    source = video_factory(width=64, height=64, frames=6)
    job = build_manifest(source, preset="fast", fps="2x", restore_model=model["id"])
    create = ModelRegistry.create_stage

    def stage(self, model_id, task, settings, rate, cuts):
        if task == "interpolate":
            return Blend2xStage(rate, cuts)
        return create(self, model_id, task, settings, rate, cuts)

    monkeypatch.setattr(ModelRegistry, "create_stage", stage)
    encoded = []
    write = runner.Encoder.write

    def capture(encoder, frame):
        encoded.append(frame.clone())
        write(encoder, frame)

    monkeypatch.setattr(runner.Encoder, "write", capture)
    stats = process_segment(
        job, {"index": 0, "start": 0, "end": 6}, tmp_path / "context.mp4", lambda: False
    )
    assert stats["output_frames"] == 12
    for index in range(0, 10, 2):
        assert torch.equal(encoded[index + 1], (encoded[index] + encoded[index + 2]) * 0.5)
    assert torch.equal(encoded[-1], encoded[-2])


def test_previous_restore_clip_is_released_before_next_inference(
    fake_model, video_factory, build_manifest, tmp_path, monkeypatch
):
    folder, model, registry = fake_model
    registry.add(folder)
    references = []

    class CheckRelease(IdentityRestore):
        def process(self, batch):
            assert all(
                reference() is None or reference() is batch.frames for reference in references
            )
            if not references or references[-1]() is not batch.frames:
                references.append(weakref.ref(batch.frames))
            return batch

    monkeypatch.setitem(ADAPTERS, "identity-test", ("restore", lambda *_args: CheckRelease()))
    source = video_factory(width=64, height=64, frames=6)
    job = build_manifest(source, preset="fast", fps="off", restore_model=model["id"])
    process_segment(
        job, {"index": 0, "start": 0, "end": 6}, tmp_path / "release.mp4", lambda: False
    )
    assert len(references) == 6


def test_add_job_records_models_and_resume_refuses_changes(fake_model, video_factory, tmp_path):
    folder, model, registry = fake_model
    registry.add(folder)
    source = video_factory(width=64, height=64, frames=6)
    job = add_job(
        source,
        dict(preset="fast", backend="cpu", fps="off", short_side="keep", restore_model=model["id"]),
        tmp_path / "output.mp4",
        registry.home,
    )
    expected = job["models"]["restore"]
    assert (expected["id"], expected["version"], expected["sha256"]) == (
        model["id"],
        "1",
        model["weights"]["sha256"],
    )
    validate_job_models(job, registry.home)
    path = registry.folder(model["id"]) / "model.json"
    model["precision"] = "fp16"
    path.write_text(json.dumps(model), encoding="utf-8")
    with pytest.raises(ValueError, match="changed.*resume refused"):
        JobStore(registry.home).set_state(job["id"], "queued")
    with pytest.raises(ValueError, match="changed.*resume refused"):
        process_segment(job, job["segments"][0], tmp_path / "refused.mp4", lambda: False)
    model["precision"] = "fp32"
    path.write_text(json.dumps(model), encoding="utf-8")
    (path.parent / "weights.pt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        JobStore(registry.home).set_state(job["id"], "queued")


def test_cli_models_commands(fake_model, capsys):
    folder, model, _ = fake_model
    assert cli.main(["models", "add", str(folder), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == model["id"]
    assert cli.main(["models", "list", "--json"]) == 0
    assert any(m["id"] == model["id"] for m in json.loads(capsys.readouterr().out))
    assert cli.main(["models", "remove", C1, "--json"]) == 1
    assert "built-in" in capsys.readouterr().err
    assert cli.main(["models", "remove", model["id"]]) == 0


def test_cli_override_parsing():
    args = cli._parser().parse_args(
        [
            "enhance",
            "input.mp4",
            "--restore-model",
            "custom-restore",
            "--interp-model",
            RIFE,
        ]
    )
    assert args.restore_model == "custom-restore"
    assert args.interp_model == RIFE


def test_builtin_manifest_schema(tmp_path):
    registry = ModelRegistry(tmp_path)
    assert registry.manifest(C1, "restore")["architecture_params"] == {
        "mid_channels": 128,
        "num_blocks": 25,
    }
    assert registry.manifest(RIFE, "interpolate")["precision"] == "fp16"
    assert all(not model["weights_verified"] for model in registry.list_models())


def test_spandrel_restricted_loader_processes_real_single_frame_model(fake_model):
    """Random test weights validate the adapter; they are not a benchmark candidate."""
    pytest.importorskip("spandrel")
    from spandrel.architectures.SPAN.__arch.span import SPAN

    folder, model, registry = fake_model
    network = SPAN(num_in_ch=3, num_out_ch=3, feature_channels=8, upscale=1)
    torch.save(network.state_dict(), folder / "weights.pt")
    model["architecture"] = "spandrel"
    model["weights"]["sha256"] = sha256(folder / "weights.pt")
    (folder / "model.json").write_text(json.dumps(model), encoding="utf-8")
    registry.add(folder)
    stage = registry.create_stage(model["id"], "restore", {"backend": "cpu"}, Fraction(30), set())
    stage.load()
    batch = FrameBatch(torch.full((2, 3, 16, 16), 0.5), (Fraction(0), Fraction(1, 30)), (0, 1))
    try:
        stage.warmup(batch)
        result = stage.process(batch)
        assert result.frames.shape == batch.frames.shape
        assert torch.isfinite(result.frames).all()
        assert result.timestamps == batch.timestamps
        assert result.indices == batch.indices
    finally:
        stage.release()


def test_builtin_c1_first_use_download_verifies_hash(tmp_path, monkeypatch):
    registry = ModelRegistry(tmp_path)
    model = registry.manifest(C1)
    payload = b"download fixture"
    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(payload)
    model["weights"]["sha256"] = sha256(fixture)
    calls = []

    def download(path, url, expected):
        calls.append((url, expected))
        path.write_bytes(payload)
        return path

    monkeypatch.setattr("videoenhancer.bench.basicvsr._verified_download", download)
    assert registry.weights(model, download=True).read_bytes() == payload
    assert calls == [(model["weights"]["url"], model["weights"]["sha256"])]
    assert registry.weights(model, download=True).read_bytes() == payload
    assert len(calls) == 1


@pytest.mark.gpu
def test_reregistered_c1_is_bit_identical_to_legacy_and_builtin(tmp_path, gpu_available):
    """Real weights, short CUDA clip, exact tensor equality (no tolerance)."""
    from videoenhancer.models.basicvsr import BasicVSRRestoreStage
    from videoenhancer.models.registry import ModelRegistry

    registry = ModelRegistry()
    builtin = registry.manifest(C1, "restore")
    weights = registry.weights(builtin, download=True)
    incoming = tmp_path / "c1-copy"
    incoming.mkdir()
    model = copy.deepcopy(builtin)
    model["id"] = "c1-equivalence-test"
    shutil.copyfile(weights, incoming / weights.name)
    (incoming / "model.json").write_text(json.dumps(model), encoding="utf-8")
    test_registry = ModelRegistry(tmp_path / "registry")
    test_registry.add(incoming)
    bare = tmp_path / "c1-bare-state"
    bare.mkdir()
    checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
    state = {
        key.removeprefix("generator."): value
        for key, value in checkpoint["state_dict"].items()
        if key != "step_counter"
    }
    torch.save(state, bare / weights.name)
    bare_manifest = copy.deepcopy(model)
    bare_manifest["id"] = "c1-bare-state-test"
    bare_manifest["weights"]["sha256"] = sha256(bare / weights.name)
    (bare / "model.json").write_text(json.dumps(bare_manifest), encoding="utf-8")
    test_registry.add(bare)
    del state, checkpoint
    settings = {"backend": "cuda", "clip_length": 3, "clip_overlap": 1}
    torch.manual_seed(1234)
    frames = torch.rand((3, 3, 256, 256), device="cuda", dtype=torch.float16)
    batch = FrameBatch(frames, tuple(Fraction(i, 30) for i in range(3)), (0, 1, 2))
    outputs = []
    for stage in (
        BasicVSRRestoreStage(settings),
        registry.create_stage(C1, "restore", settings, Fraction(30), set()),
        test_registry.create_stage(model["id"], "restore", settings, Fraction(30), set()),
        test_registry.create_stage(bare_manifest["id"], "restore", settings, Fraction(30), set()),
    ):
        stage.load()
        try:
            outputs.append(stage.process(batch).frames.cpu())
        finally:
            stage.release()
    assert torch.equal(outputs[0], outputs[1])
    assert torch.equal(outputs[1], outputs[2])
    assert torch.equal(outputs[2], outputs[3])


@pytest.mark.gpu
def test_registry_rife_matches_legacy_short_pair(gpu_available):
    from videoenhancer.models.rife import RifeInterpolateStage

    settings = {"backend": "cuda"}
    registry = ModelRegistry()
    torch.manual_seed(42)
    frames = torch.rand((2, 3, 64, 64), device="cuda", dtype=torch.float16)
    batch = FrameBatch(frames, (Fraction(0), Fraction(1, 30)), (0, 1))
    outputs = []
    for stage in (
        RifeInterpolateStage(Fraction(30), set(), settings),
        registry.create_stage(RIFE, "interpolate", settings, Fraction(30), set()),
    ):
        stage.load()
        try:
            outputs.append(stage.process(batch).frames.cpu())
        finally:
            stage.release()
    assert torch.equal(outputs[0], outputs[1])
