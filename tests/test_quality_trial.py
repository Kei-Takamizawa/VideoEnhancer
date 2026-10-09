"""Measured fidelity, joints and context-aware CLI trial outputs."""

import tempfile
from fractions import Fraction
from pathlib import Path

import pytest

from videoenhancer import cli
from videoenhancer.media.probe import probe
from videoenhancer.pipeline.quality import _ratio, measure_quality
from videoenhancer.trial import run_trial


@pytest.fixture
def trial_output():
    with tempfile.TemporaryDirectory(prefix="ve-trial-test-") as directory:
        yield Path(directory)


def test_quality_identical_file_and_known_joints(video_factory, build_manifest):
    source = video_factory(width=64, height=64, frames=12)
    job = build_manifest(source, preset="fast", fps="off")
    job["segments"] = [
        {"start": 0, "end": 6, "stats": {"clip_joints": [3]}},
        {"start": 6, "end": 12, "stats": {"clip_joints": [9]}},
    ]
    result = measure_quality(job, source)
    assert result["fidelity_frames"] == 12
    assert result["psnr_y_mean_db"] is None  # Infinity represented as valid JSON null.
    assert result["ssim_y_mean"] == pytest.approx(1)
    assert result["flicker_ratio"] == pytest.approx(1)
    assert result["clip_joint_count"] == 2
    assert result["segment_joint_count"] == 1
    assert result["seam_ratio"] > 0
    assert _ratio(0, 0) == 1
    assert _ratio(1, 0) is None
    job["scene_cuts"] = [3, 6, 9]
    excluded = measure_quality(job, source)
    assert excluded["excluded_joint_count"] == 3
    assert excluded["noncut_joint_count"] == 0
    assert excluded["seam_ratio"] is None
    assert len(excluded["joint_diagnostics"]) == 3
    assert all(
        detail["relative_seam"] == pytest.approx(1) for detail in excluded["joint_diagnostics"]
    )


def test_trial_cli_forwards_model_overrides(tmp_path, monkeypatch, capsys):
    captured = {}

    def trial(_input, **options):
        captured.update(options)
        return {
            "paths": {"report.json": "report.json"},
            "pipeline": {"fps": 2},
            "projected_whole_file_seconds": 100,
        }

    monkeypatch.setenv("VE_HOME", str(tmp_path))
    monkeypatch.setattr("videoenhancer.trial.run_trial", trial)
    assert (
        cli.main(
            [
                "trial",
                "input.mp4",
                "--restore-model",
                "custom",
                "--interp-model",
                "rife-4.25",
                "--seconds",
                "1",
                "--json",
            ]
        )
        == 0
    )
    assert captured["restore_model"] == "custom"
    assert captured["interp_model"] == "rife-4.25"


@pytest.mark.parametrize("backend", ["cpu", pytest.param("cuda", marks=pytest.mark.gpu)])
def test_trial_actual_pipeline_has_four_outputs_and_exact_frames(
    video_factory, trial_output, monkeypatch, backend
):
    if backend == "cuda":
        import torch

        if not torch.cuda.is_available():
            pytest.skip("CUDA required")
        pytest.importorskip("PyNvVideoCodec")
    from videoenhancer.pipeline.presets import PRESETS, _placeholder

    # Real decode/resize/interpolation/encode/metrics/split; no downloaded weights on CPU CI.
    monkeypatch.setitem(PRESETS, "fast", _placeholder)
    monkeypatch.setattr("videoenhancer.trial.record_models", lambda *_args: {})
    source = video_factory(width=256, height=256, frames=12)
    out = trial_output
    report = run_trial(
        source,
        start=2 / 30,
        seconds=6 / 30,
        preset="fast",
        backend=backend,
        short_side="keep",
        out=out,
    )
    assert {p.name for p in out.iterdir()} == {
        "original.mp4",
        "enhanced.mp4",
        "comparison_split.mp4",
        "report.json",
    }
    assert report["input_frames"] == 6
    assert probe(out / "original.mp4").frame_count == 6
    assert probe(out / "enhanced.mp4").frame_count == 12
    comparison = probe(out / "comparison_split.mp4")
    assert comparison.frame_count == 12
    assert Fraction(comparison.cfr_fps) == 60
    assert report["metrics"]["fidelity_frames"] == 1
    assert "Pre-encode" in report["metrics"]["method"]
    assert report["projected_whole_file_seconds"] > 0
