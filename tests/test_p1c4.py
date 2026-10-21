"""AV1 capability and optional adapter contracts without CUDA builds."""

from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch

from videoenhancer.media import encode
from videoenhancer.models.spandrel import SpandrelRestoreStage, SpandrelSizeStage
from videoenhancer.pipeline.stages import FrameBatch
from videoenhancer.service.compare import suggested_range
from videoenhancer.service.engine import Engine


def test_av1_probe_uses_production_encoder_at_full_hd(monkeypatch):
    calls = []

    class FakeEncoder:
        def __init__(self, path, width, height, rate, codec, backend, media):
            calls.append((width, height, rate, codec, backend))

        def write(self, frame):
            assert frame.shape == (3, 1080, 1920)

        def finish(self):
            calls.append("finished")

    monkeypatch.setattr(encode, "Encoder", FakeEncoder)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    zeros = torch.zeros
    monkeypatch.setattr(torch, "zeros", lambda shape, **_: zeros(shape))
    assert encode.probe_av1() == (True, None)
    assert calls == [(1920, 1080, Fraction(30), "av1", "cuda"), "finished"]


def test_av1_failure_reason_is_exposed_and_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        torch.cuda, "get_device_properties", lambda _: SimpleNamespace(total_memory=8_000_000_000)
    )
    monkeypatch.setattr("videoenhancer.logging.environment_info", lambda: {})
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cuda")
    monkeypatch.setattr(encode, "probe_av1", lambda: (False, "AV1: driver rejected encode"))
    warnings = []
    monkeypatch.setattr(
        "videoenhancer.service.engine.get_logger",
        lambda *_: SimpleNamespace(warning=lambda *args: warnings.append(args)),
    )
    engine = Engine(tmp_path)
    engine._environment()
    assert engine.health()["av1_supported"] is False
    assert engine.health()["av1_unavailable_reason"] == "AV1: driver rejected encode"
    assert warnings == [("AV1 probe: %s", "AV1: driver rejected encode")]
    engine.close()


@pytest.mark.parametrize("codec,retime", [("av1", True), ("hevc", False)])
def test_gpu_mux_retimes_ivf_only_at_exact_rational_rate(codec, retime, tmp_path, monkeypatch):
    captured = []
    monkeypatch.setattr(
        encode.proc, "run", lambda args, **_: captured.append(args) or SimpleNamespace(returncode=0)
    )
    encoder = encode.Encoder.__new__(encode.Encoder)
    encoder.backend, encoder.codec = "cuda", codec
    encoder.path = tmp_path / "output.mp4"
    encoder.rate = Fraction(60000, 1001)
    encoder.media = {"color_matrix": "bt709"}
    encoder.raw_path = tmp_path / "input.ivf"
    encoder.stream = encoder.raw_path.open("wb")
    encoder.encoder = SimpleNamespace(EndEncode=lambda: b"packet")
    encoder.finish()
    command = captured[0]
    filters = command[command.index("-bsf:v") + 1]
    assert ("setts=" in filters) is retime
    if retime:
        assert "time_base=1001/60000" in filters
    assert command[command.index("-c:v") + 1] == "copy"


@pytest.mark.parametrize("quality,expected", [(50, 0.5), (30, 0.7), (10, 0.9)])
def test_drunet_passes_publisher_quality_map_with_padding(quality, expected, tmp_path):
    manifest = {"architecture": "drunet", "architecture_params": {"quality_factor": quality}}
    stage = SpandrelRestoreStage(manifest, tmp_path / "unused", {"backend": "cpu"})
    seen = []

    class Descriptor:
        def model(self, image):
            seen.append(image)
            return image[:, :3]

    stage.model = Descriptor()
    image = torch.rand(1, 3, 19, 21)
    assert torch.equal(stage._frame(image), image)
    assert seen[0].shape == (1, 4, 24, 24)
    assert torch.allclose(seen[0][:, 3], torch.full((1, 24, 24), expected))


def test_tiled_size_preserves_all_pixels_and_frame_ownership(tmp_path):
    manifest = {"scale": 2, "architecture_params": {"tile_size": 64, "tile_overlap": 8}}
    stage = SpandrelSizeStage(manifest, tmp_path / "unused", {"backend": "cpu"})
    stage.dtype = torch.float32
    stage.model = lambda x: x.repeat_interleave(2, -2).repeat_interleave(2, -1)
    batch = FrameBatch(torch.rand(2, 3, 79, 91), (Fraction(0), Fraction(1, 30)), (0, 1))
    result = stage.process(batch)
    assert torch.equal(
        result.frames, batch.frames.repeat_interleave(2, -2).repeat_interleave(2, -1)
    )
    assert result.indices == batch.indices
    assert result.timestamps == batch.timestamps


def test_busiest_range_uses_motion_and_missing_data_uses_middle(monkeypatch, tmp_path):
    index = dict(media={"cfr_fps": "30"}, cfr_map=list(range(450)))
    monkeypatch.setattr("videoenhancer.service.compare.source_index", lambda *_: index)
    analysis = {"motion_scores": [{"frame": i, "delta": 10} for i in range(240, 390)]}
    assert suggested_range(tmp_path / "video", analysis)["first_frame"] == 240
    assert suggested_range(tmp_path / "video")["first_frame"] == 150


def test_qualified_catalog_has_measured_budget_and_plain_summaries(tmp_path):
    from videoenhancer.models.registry import ModelRegistry

    models = ModelRegistry(tmp_path).list_models()
    assert {m["id"] for m in models} == {
        "basicvsrpp-ntire21-decompress",
        "basicvsrpp-track1",
        "basicvsrpp-track2",
        "basicvsrpp-denoise",
        "scunet-real-psnr",
        "fbcnn-color",
        "drunet-deblock",
        "rife-4.25",
        "rife-4.26",
        "rife-4.25-lite",
        "span-liveaction-2x",
    }
    for model in models:
        catalog = model["catalog"]
        assert 1 <= len(catalog["summary"]) <= 90
        speed = catalog["reference_speed"]
        assert speed["fps"] > 0
        assert 0 < speed["sampled_process_peak_bytes"] <= 5_000_000_000
        assert speed["torch_allocated_bytes"] > 0
        assert speed["torch_reserved_bytes"] >= speed["torch_allocated_bytes"]
        assert speed["sampling_seconds"] == 1
        assert model["weights"]["bytes"] > 0
        if model["architecture"] == "basicvsrpp":
            assert not model["commercial_use_allowed"]


def test_archive_download_verifies_extracted_checkpoint(tmp_path, monkeypatch):
    import hashlib
    import json
    import zipfile

    from videoenhancer.models.registry import C1, ModelRegistry

    registry = ModelRegistry(tmp_path)
    model = registry.manifest(C1)
    content = b"verified checkpoint data"
    model["weights"].update(
        sha256=hashlib.sha256(content).hexdigest(),
        archive={"sha256": "a" * 64, "member": "checkpoint.pth"},
    )
    (registry.folder(C1) / "model.json").write_text(json.dumps(model))
    expected = []

    def download(target, url, digest, progress=None, expected_bytes=0):
        expected.append(digest)
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("checkpoint.pth", content)
            archive.writestr("untrusted.py", "raise RuntimeError('never import')")

    monkeypatch.setattr("videoenhancer.bench.basicvsr._verified_download", download)
    path = registry.weights(model, download=True)
    assert expected == ["a" * 64]
    assert path.read_bytes() == content
    assert not (path.parent / "untrusted.py").exists()
    assert not path.with_suffix(".publisher.zip").exists()
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        registry.weights(model)


def test_range_api_uses_prepared_motion_and_rejects_wrong_job_file(
    tmp_path, video_factory, monkeypatch
):
    from videoenhancer.media.source_index import source_identity
    from videoenhancer.service.engine import Engine

    source = video_factory()
    index = dict(media={"cfr_fps": "30"}, cfr_map=list(range(450)))
    analysis = dict(
        input=source_identity(source),
        motion_scores=[{"frame": i, "delta": 10} for i in range(240, 390)],
    )
    monkeypatch.setattr("videoenhancer.service.compare.source_index", lambda *_: index)
    engine = Engine(tmp_path / "home")
    monkeypatch.setattr(engine.store, "load", lambda _: analysis)
    chosen = engine.dispatch("POST", ["compare", "range"], dict(file=str(source), job_id="job"))
    assert chosen["first_frame"] == 240
    assert not engine.operations
    analysis["input"]["mtime_ns"] += 1
    fallback = engine.dispatch("POST", ["compare", "range"], dict(file=str(source), job_id="job"))
    assert fallback["first_frame"] == 150
    with pytest.raises(ValueError, match="must match its job"):
        engine.dispatch("POST", ["compare", "range"], dict(file=str(video_factory()), job_id="job"))
    engine.close()


def test_rife_variant_source_preparation_does_not_download_other_weights(tmp_path, monkeypatch):
    import hashlib
    import zipfile

    from videoenhancer.bench import rife

    monkeypatch.setenv("VE_HOME", str(tmp_path))
    cache = tmp_path / "adapter-sources"
    cache.mkdir()
    archive = cache / "practical-rife-source.zip"
    name = f"Practical-RIFE-{rife.SOURCE_COMMIT}"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{name}/LICENSE", "source fixture")
    monkeypatch.setattr(rife, "SOURCE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    monkeypatch.setattr(rife, "_download_drive", lambda *_: pytest.fail("Unselected weights"))
    source, checkpoint = rife._prepare_files(prepare_weights=False)
    assert source.name == name
    assert not checkpoint.exists()
    assert not (cache / "RIFEv4.25_0919.zip").exists()
