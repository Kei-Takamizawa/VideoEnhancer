import copy
import json
from pathlib import Path

import pytest

from videoenhancer.bench.finalization import preserve_finalization_curve
from videoenhancer.estimate.local import apply_local, read_local, record_completed
from videoenhancer.estimate.model import estimate_job, predict_finalization, predict_segment
from videoenhancer.estimate.startup import ESTIMATE_REVISION, cold_parts, startup_seconds
from videoenhancer.service.downloads import gpu_test_prediction

MEDIA = dict(width=720, height=1280, cfr_fps="30", frame_count=300)
SETTINGS = dict(preset="fast", short_side=1080, fps="2x", backend="cuda")


def job(count):
    return dict(
        id="synthetic",
        media=MEDIA,
        settings=SETTINGS,
        state="queued",
        segments=[
            dict(index=i, start=i * 30, end=(i + 1) * 30, state="pending") for i in range(count)
        ],
    )


@pytest.mark.parametrize(
    "count,expected", [(1, [0]), (2, [0]), (50, [0]), (51, [0, 50]), (120, [0, 50, 100])]
)
def test_initial_cold_parts(count, expected):
    assert [i for i, cold in cold_parts(job(count)).items() if cold] == expected


def test_resume_and_failed_retry_reset_worker_lifetime():
    manifest = job(120)
    for part in manifest["segments"][:23]:
        part["state"] = "done"
    manifest["timing"] = {"worker_parts": 0}
    assert [i for i, cold in cold_parts(manifest).items() if cold] == [0, 23, 73]
    manifest["timing"]["worker_parts"] = 23
    manifest["segments"][23]["state"] = "failed"
    assert cold_parts(manifest)[23]
    manifest["segments"][23].update(state="pending", startup_kind="cold")
    assert cold_parts(manifest)[23]
    manifest["state"] = "paused"
    manifest["segments"][23].pop("startup_kind")
    assert cold_parts(manifest)[23]


def test_job_estimate_uses_cold_then_warm_and_replacement():
    manifest = job(51)
    profile = {"startup_by_preset": {"fast": {"cold": 8, "warm": 0.2}}}
    baseline = {"startup_by_preset": {"fast": 0}}
    assert estimate_job(manifest, profile).seconds - estimate_job(manifest, baseline).seconds == (
        pytest.approx(2 * 8 + 49 * 0.2)
    )
    assert predict_segment(MEDIA, SETTINGS, 30, profile) - predict_segment(
        MEDIA, SETTINGS, 30, profile, cold=False
    ) == pytest.approx(7.8)


def test_legacy_flat_and_qualification_always_cold():
    assert startup_seconds({"startup_by_preset": {"fast": 3}}, "fast", False) == 3
    profile = {"startup_by_preset": {"fast": {"cold": 8, "warm": 0.2}}}
    assert gpu_test_prediction(dict(id="synthetic", task="interpolate"), profile) == 8


def test_local_learning_keeps_last_twenty_of_each_kind_and_preset(tmp_path):
    profile = {
        "estimate_revision": ESTIMATE_REVISION,
        "startup_by_preset": {"fast": {"cold": 8, "warm": 0.2}},
    }
    manifest = job(50)
    manifest["machine_profile"] = profile
    for i, part in enumerate(manifest["segments"]):
        part.update(
            state="done",
            stats=dict(startup_kind="cold" if i % 2 else "warm", per_part_startup_seconds=i + 1),
        )
    record_completed(manifest, tmp_path)
    learned = apply_local(tmp_path, profile)
    assert learned["startup_by_preset"]["fast"] == {"cold": 31, "warm": 30}
    assert "standard" not in learned["startup_by_preset"]
    old = (tmp_path / "timing-observations.json").read_bytes()
    assert read_local(tmp_path, {**profile, "estimate_revision": "old"}) == {}
    assert (tmp_path / "timing-observations.json").read_bytes() == old
    manifest["segments"][0]["stats"]["spilled"] = True
    manifest["id"] = "spilled"
    record_completed(manifest, tmp_path)
    assert (tmp_path / "timing-observations.json").read_bytes() == old


@pytest.mark.parametrize("minutes", [1, 10, 30, 120])
def test_calibration_retains_curve_predictions(minutes):
    path = Path(__file__).parents[1] / "src/videoenhancer/estimate/profiles/rtx-4060-ti-8gb.json"
    profile = json.loads(path.read_text())
    original = copy.deepcopy(profile["finalization"])
    manifest = job(1)
    manifest["segments"][0]["end"] = minutes * 60 * 30
    manifest["estimated_output_bytes"] = minutes * 1_000_000
    before = predict_finalization(manifest, profile)
    profile["finalization"] = preserve_finalization_curve(original, dict(a=100, b=1, c=1))
    assert profile["finalization"]["points"] == original["points"]
    assert profile["finalization"]["samples"] == original["samples"]
    assert predict_finalization(manifest, profile) == before


def test_unknown_gpu_uses_tiny_clip_fit():
    tiny = dict(status="measured", a=3, b=0.1, c=0.2)
    finalization = preserve_finalization_curve({}, tiny)
    manifest = job(1)
    manifest["estimated_output_bytes"] = 100
    assert predict_finalization(manifest, {"finalization": finalization}) == pytest.approx(
        (3 + 10 + 60 * 0.2) * 1.15
    )


def test_unknown_gpu_keeps_an_existing_measured_curve(monkeypatch):
    from videoenhancer.bench.finalization import builtin_finalization

    curve = {"points": [{"output_frames": 3600}], "samples": ["measured"]}
    monkeypatch.setattr(
        "videoenhancer.jobs.store.load_machine_profile", lambda *a, **kw: {"finalization": curve}
    )
    assert builtin_finalization("synthetic unknown GPU", "cuda") == curve


def test_startup_calibration_uses_three_real_executor_requests_per_preset(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from videoenhancer.bench import startup

    requests = []
    closed = []

    class Executor:
        def __init__(self, clock, *, reuse):
            assert reuse is True

        def run(self, manifest, part, output, abort, *, batch_size):
            assert "id" not in manifest  # Standalone executor must not look up a queue manifest.
            requests.append((manifest["settings"]["preset"], part["index"]))
            index = part["index"]
            return SimpleNamespace(
                status="done",
                stats={
                    "startup_kind": "cold" if index == 0 else "warm",
                    "per_part_startup_seconds": [4, 0.1, 0.2][index],
                },
            )

        def close(self):
            closed.append(True)

    monkeypatch.setattr(startup, "ProcessExecutor", Executor)
    monkeypatch.setattr(startup.proc, "run", lambda *a, **kw: None)
    monkeypatch.setattr(startup, "executable", lambda name: name)
    monkeypatch.setattr(startup, "analyze", lambda *a, **kw: {"media": MEDIA})
    monkeypatch.setattr(startup, "record_models", lambda *a, **kw: {})
    terms = startup.calibrate_startup(tmp_path, "cuda")
    for preset in ("standard", "fast"):
        assert terms[preset]["cold"] == 4
        assert terms[preset]["warm"] == pytest.approx(0.15)
        assert [(mode, i) for mode, i in requests if mode == preset] == [
            (preset, i) for i in range(3)
        ]
    assert len(closed) == 2
