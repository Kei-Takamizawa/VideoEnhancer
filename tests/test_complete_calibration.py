import runpy
import sys
from datetime import UTC, datetime
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import SimpleNamespace

import pytest

from videoenhancer.bench import runner
from videoenhancer.estimate.model import estimate_job
from videoenhancer.schedule import controller
from videoenhancer.schedule.planner import build_plan
from videoenhancer.schedule.windows import Schedule


@pytest.mark.parametrize(
    "value",
    [
        {"components": {"decode": {"seconds_per_pixel_frame": None}}},
        {"startup_by_preset": {"standard": {"cold": None, "warm": 0.1}}},
        {"part_a": {"decode": {"status": "skipped", "reason": "missing sample"}}},
    ],
)
def test_measurement_guard_rejects_incomplete_terms(value):
    script = Path(__file__).parents[1] / "gui/scripts/estimate-complete-cycle.py"
    guard = runpy.run_path(str(script))["require_complete"]
    with pytest.raises(ValueError):
        guard(value)


def test_ffmpeg_decode_uses_portrait_dimensions(monkeypatch, tmp_path):
    commands = []

    def run(command, timeout=90):
        commands.append(command)
        return True, "", 0.1

    monkeypatch.setattr(runner, "_run", run)
    result = runner._bench_ffmpeg("ffmpeg", tmp_path)
    generated = [c[c.index("-i") + 1] for c in commands if "-f" in c and "lavfi" in c]
    assert "testsrc2=size=720x1280:rate=30" in generated
    assert "testsrc2=size=1080x1920:rate=30" in generated
    assert all(row["status"] == "measured" for row in result["decode"].values())


@pytest.mark.parametrize("override", [False, True])
def test_decode_generates_missing_samples_and_removes_them(monkeypatch, tmp_path, override):
    monkeypatch.delenv("VE_SAMPLES_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner, "_ffmpeg", lambda: "ffmpeg")
    generated = []
    supplied = []
    if override:
        supplied = [tmp_path / "h264.mp4", tmp_path / "hevc.mp4"]
        for path in supplied:
            path.write_bytes(b"override")
        monkeypatch.setenv("VE_SAMPLES_DIR", str(tmp_path))

    def run(command, timeout=90):
        if "-x265-params" in command:
            assert command.index("-x265-params") > command.index("-i")
        path = Path(command[-1])
        path.write_bytes(b"synthetic")
        generated.append(path)
        return True, "", 0.1

    monkeypatch.setattr(runner, "_run", run)

    class Decoder:
        def __init__(self, path, **kwargs):
            self.path = Path(path)

        def get_stream_metadata(self):
            hevc = "hevc" in self.path.name
            return SimpleNamespace(
                codec_name="hevc" if hevc else "h264",
                width=1080 if hevc else 720,
                height=1920 if hevc else 1280,
                num_frames=48,
            )

        def get_batch_frames(self, count):
            return [object()] * count

    monkeypatch.setitem(sys.modules, "PyNvVideoCodec", SimpleNamespace(SimpleDecoder=Decoder))
    result = runner._bench_pynvc_samples()
    assert all(result[key]["status"] == "measured" for key in ("h264_720x1280", "hevc_1080x1920"))
    assert all(result[key]["fps"] > 0 for key in result)
    assert len(generated) == (0 if override else 2)
    assert all(not path.exists() for path in generated)
    assert all(path.read_bytes() == b"override" for path in supplied)

    if not override:
        from videoenhancer.bench import calibration, finalization, reference, startup

        monkeypatch.setitem(
            sys.modules,
            "PyNvVideoCodec",
            SimpleNamespace(
                SimpleDecoder=Decoder,
                __spec__=ModuleSpec("PyNvVideoCodec", loader=None),
            ),
        )
        fake_cuda = SimpleNamespace(
            reset_peak_memory_stats=lambda: None,
            synchronize=lambda: None,
            max_memory_allocated=lambda: 0,
        )
        monkeypatch.setitem(
            sys.modules,
            "torch",
            SimpleNamespace(
                cuda=fake_cuda,
                version=SimpleNamespace(cuda="fake"),
                __version__="fake",
            ),
        )
        monkeypatch.setattr(
            runner, "_gpu_info", lambda _: dict(available=True, name="synthetic", driver="fake")
        )
        monkeypatch.setattr(runner._ResourceSampler, "start", lambda _: None)
        monkeypatch.setattr(runner._ResourceSampler, "stop", lambda _: None)
        monkeypatch.setattr(runner, "_bench_tensor_stages", lambda *a: {})
        monkeypatch.setattr(runner, "_bench_nvenc", lambda *a: {})
        monkeypatch.setattr(
            runner, "_bench_pipeline_end_to_end", lambda *a: dict(status="not exercised")
        )
        monkeypatch.setattr(calibration, "calibrate_models", lambda **kw: {})
        monkeypatch.setattr(reference, "calibrate_references", lambda *a, **kw: {})
        monkeypatch.setattr(reference, "reference_size_points", lambda p: {})
        monkeypatch.setattr(startup, "calibrate_startup", lambda *a: {})
        monkeypatch.setattr(finalization, "builtin_finalization", lambda *a: {})
        monkeypatch.setattr(finalization, "calibrate_finalization", lambda *a: dict(a=1, b=0, c=0))
        report = runner.run_bench(calibrate=True, output_dir=tmp_path / "report")
        coefficient = report["profile"]["components"]["decode"]["seconds_per_pixel_frame"]
        assert coefficient is not None and coefficient > 0
        assert all(not path.exists() for path in generated)


def test_p0_passes_analyzed_timestamps(monkeypatch, tmp_path):
    from videoenhancer.media import analyze
    from videoenhancer.pipeline import runner as pipeline

    analyzed = dict(
        media={},
        cfr_map=[0, 1],
        scene_cuts=[],
        source_pts=[0, 0.03],
        keyframes=[0],
        analysis_seconds=0.1,
    )
    monkeypatch.setattr(runner, "_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(runner, "_run", lambda *a, **k: (True, "", 0.1))
    monkeypatch.setattr(analyze, "analyze", lambda *a, **k: analyzed)

    def process(manifest, *args, **kwargs):
        assert manifest["source_pts"] == analyzed["source_pts"]
        assert manifest["keyframes"] == analyzed["keyframes"]
        (tmp_path / "p0_end_to_end_output.mp4").write_bytes(b"output")
        return dict(
            output_frames=4,
            input_frames=2,
            seconds=1,
            fps=2,
            peak_torch_vram_bytes=0,
            peak_rss_bytes=0,
        )

    monkeypatch.setattr(pipeline, "process_segment", process)
    result = runner._bench_pipeline_end_to_end(
        SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True)), tmp_path
    )
    assert result["status"] == "measured", result


@pytest.mark.parametrize("used", [0, 23, 49, 50])
@pytest.mark.parametrize("preset", ["standard", "fast"])
def test_scheduling_readers_match_estimator(monkeypatch, used, preset):
    job = dict(
        id="synthetic",
        state="running",
        timing=dict(worker_parts=used),
        media=dict(width=720, height=1280, cfr_fps="30", frame_count=900),
        settings=dict(preset=preset, short_side=1080, fps="2x", backend="cuda"),
        machine_profile={"startup_by_preset": {preset: {"cold": 8, "warm": 0.2}}},
        segments=[dict(index=i, start=i * 30, end=(i + 1) * 30, state="pending") for i in range(3)],
    )
    now = datetime(2026, 11, 1, tzinfo=UTC)
    schedule = Schedule(dict(enabled=False, timezone="UTC"))
    plan = build_plan([job], schedule, now)
    assert sum(row["seconds"] for row in plan["timeline"]) == pytest.approx(
        estimate_job(job).seconds, abs=1
    )
    predictions = []
    monkeypatch.setattr(
        controller, "admit_step", lambda seconds, *a: (predictions.append(seconds) or True, False)
    )
    for part in job["segments"]:
        controller.unit_admission(job, now, schedule.current_interval(now))
        part["state"] = "done"
        job["timing"]["worker_parts"] = (job["timing"]["worker_parts"] % 50) + 1
    assert sum(predictions) == pytest.approx(
        sum(row["seconds"] for row in plan["timeline"] if row["phase"] == "processing"), abs=1
    )
