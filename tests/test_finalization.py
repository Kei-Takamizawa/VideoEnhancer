"""Finalization admission, phase accounting and sampled inline diagnostics."""

import json
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import torch

from videoenhancer import cli
from videoenhancer.bench.finalization import fit_finalization
from videoenhancer.estimate import estimate_job
from videoenhancer.estimate.model import job_progress, observe_finalization, predict_finalization
from videoenhancer.jobs.store import JobStore
from videoenhancer.media.decode import IndexedDecoder
from videoenhancer.media.probe import packet_timeline, probe
from videoenhancer.pipeline import runner
from videoenhancer.pipeline.inline_quality import STRIDE, aggregate_quality, luma
from videoenhancer.pipeline.stages import Blend2xStage, ResizeStage
from videoenhancer.schedule import controller
from videoenhancer.schedule.planner import build_plan
from videoenhancer.schedule.windows import Schedule


def test_calibration_recovers_known_nonnegative_coefficients():
    samples = [
        dict(output_bytes=b, output_frames=f, seconds=2 + b * 1e-7 + f * 1e-4)
        for b, f in ((1e5, 100), (1e6, 100), (1e5, 1000), (1e6, 1000))
    ]
    result = fit_finalization(samples)
    assert [result[k] for k in ("a", "b", "c")] == pytest.approx([2, 1e-7, 1e-4])


def test_finalization_in_remaining_plan_and_next_job_correction(tmp_path):
    profile = {"finalization": dict(status="measured", a=60, b=0, c=0), "components": {}}
    profile_path = tmp_path / "profiles" / "machine.json"
    profile_path.parent.mkdir()
    profile_path.write_text(json.dumps(profile))
    profile["profile_path"] = str(profile_path)
    job = dict(
        media={"width": 32, "height": 32, "cfr_fps": "30"},
        settings=dict(preset="passthrough", short_side="keep", fps="off"),
        state="queued",
        machine_profile=profile,
        segments=[dict(start=0, end=30, state="done")],
    )
    assert estimate_job(job).seconds == 60
    assert job_progress(job)["progress_percent"] < 100
    available = Schedule.from_dict(
        dict(enabled=True, weekly=[dict(days=["mon", "tue"], start="08:00", end="09:00")]),
        ZoneInfo("UTC"),
    )
    now = datetime(2026, 10, 5, 8, 59, 30, tzinfo=UTC)
    plan = build_plan([job], available, now, 2)
    assert plan["timeline"][0]["phase"] == "finalizing"
    assert plan["timeline"][0]["start"] == "2026-10-06T08:00:00+00:00"
    assert plan["jobs"][0]["completion"] == "2026-10-06T08:01:00+00:00"
    observe_finalization(job, 60, 120, tmp_path)
    updated = json.loads(profile_path.read_text())
    assert predict_finalization(job, updated) == pytest.approx(78)
    assert job["timing"]["finalization_observation"] == dict(predicted=60, actual=120)


def test_fake_clock_waits_then_logs_finalization_without_default_full_pass(tmp_path, monkeypatch):
    from test_controller import FakeClock, _job

    from videoenhancer.media import mux
    from videoenhancer.pipeline import quality

    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    job["segments"][0]["state"] = "done"
    job["machine_profile"] = {"finalization": dict(a=60, b=0, c=0)}
    store.save(job)
    monkeypatch.setattr(controller, "validate_done_segments", lambda *_: False)
    monkeypatch.setattr(
        quality, "measure_quality", lambda *_a, **_kw: pytest.fail("Default full pass")
    )
    start = datetime(2026, 10, 5, 8, 59, 30, tzinfo=UTC)
    clock = FakeClock(start)

    def skip_closed_hours():
        if clock.value >= datetime(2026, 10, 5, 9, tzinfo=UTC):
            clock.value = max(clock.value, datetime(2026, 10, 6, 8, tzinfo=UTC))

    clock.on_sleep = skip_closed_hours
    schedule = Schedule.from_dict(
        dict(enabled=True, weekly=[dict(days=["mon", "tue"], start="08:00", end="09:00")]),
        ZoneInfo("UTC"),
    )
    monkeypatch.setattr(controller, "_schedule", lambda *_: schedule)

    def assemble(manifest, _directory, abort, *, validation_started):
        assert clock.now() == datetime(2026, 10, 6, 8, tzinfo=UTC)
        assert job_progress(store.load(job["id"]))["progress_percent"] < 100
        clock.value += timedelta(seconds=10)
        validation_started()
        assert job_progress(store.load(job["id"]))["step"] == "validating"
        assert job_progress(store.load(job["id"]))["progress_percent"] < 100
        clock.value += timedelta(seconds=5)
        assert not abort()
        Path(manifest["output"]).write_bytes(b"valid")
        return Path(manifest["output"])

    monkeypatch.setattr(mux, "assemble", assemble)
    controller.run_queue(home=store.home, clock=clock)
    result = store.load(job["id"])
    assert result["state"] == "done"
    events = result["timing"]["events"]
    assert {event["step"] for event in events} == {
        "assembling",
        "validating",
        "aggregating",
        "scheduler_wait",
    }
    assert all(event["elapsed_seconds"] >= 0 for event in events)
    records = [
        json.loads(line)
        for line in (store.job_dir(job["id"]) / "job.jsonl").read_text().splitlines()
    ]
    actions = {record.get("action") for record in records}
    assert all(
        f"{name}_{boundary}" in actions
        for name in ("assembling", "validating", "aggregating", "scheduler_wait")
        for boundary in ("start", "end")
    )
    assert job_progress(result)["progress_percent"] == 100


def test_inline_cpu_job_matches_independent_sampled_posthoc(
    video_factory, build_manifest, tmp_path, monkeypatch
):
    source = video_factory(frames=24)
    job = build_manifest(source)
    job["settings"].update(preset="fast", fps="2x", short_side=96)
    monkeypatch.setattr("videoenhancer.models.registry.validate_job_models", lambda *_: None)
    monkeypatch.setattr(
        runner, "create_stages", lambda *_: [ResizeStage(144, 96), Blend2xStage(Fraction(30))]
    )
    encoded = []
    original_encoder = runner.Encoder

    class CapturingEncoder(original_encoder):
        def write(self, frame):
            encoded.append(frame.detach().clone())
            super().write(frame)

    monkeypatch.setattr(runner, "Encoder", CapturingEncoder)
    segment = dict(index=0, start=0, end=24, state="done")
    job["segments"] = [segment]
    segment["stats"] = runner.process_segment(job, segment, tmp_path / "output.mp4", lambda: False)
    references = list(
        IndexedDecoder(source, job["media"], "cpu", job).frames(job["cfr_map"], lambda: False)
    )
    psnr, ssim = [], []
    for index in range(0, len(encoded), STRIDE):
        x = luma(references[index // 2])
        y = luma(
            torch.nn.functional.interpolate(
                encoded[index][None].float(), size=x.shape, mode="area"
            )[0]
        )
        mse = float((x - y).square().mean())
        psnr.append(-10 * __import__("math").log10(mse) if mse else float("inf"))
        # Independent full-frame replay: enumerate the 8x8 windows explicitly.
        wx = x.unfold(0, 8, 4).unfold(1, 8, 4).reshape(-1, 64)
        wy = y.unfold(0, 8, 4).unfold(1, 8, 4).reshape(-1, 64)
        mx, my = wx.mean(1), wy.mean(1)
        vx, vy = wx.var(1, unbiased=False), wy.var(1, unbiased=False)
        covariance = ((wx - mx[:, None]) * (wy - my[:, None])).mean(1)
        ssim.append(
            float(
                (
                    ((2 * mx * my + 0.01**2) * (2 * covariance + 0.03**2))
                    / ((mx * mx + my * my + 0.01**2) * (vx + vy + 0.03**2))
                ).mean()
            )
        )
    result = aggregate_quality(job)
    assert result["fidelity_frames"] == 5
    assert (
        result["psnr_y_mean_db"] is None
        if any(v == float("inf") for v in psnr)
        else result["psnr_y_mean_db"] == pytest.approx(sum(psnr) / len(psnr), abs=1e-5)
    )
    assert result["ssim_y_mean"] == pytest.approx(sum(ssim) / len(ssim), abs=2e-5)
    assert segment["stats"]["inline_quality_seconds"] >= 0


@pytest.mark.parametrize("codec", ["h264", "hevc", "av1"])
def test_own_encoded_packet_count_equals_decoded_count(
    codec, video_factory, build_manifest, tmp_path
):
    source = video_factory(frames=13)
    job = build_manifest(source, fps="off")
    job["settings"]["codec"] = codec
    segment = dict(index=0, start=0, end=13)
    target = tmp_path / "encoded.mp4"
    runner.process_segment(job, segment, target, lambda: False)
    info = probe(target)
    pts, _ = packet_timeline(target, Fraction(info.time_base))
    assert len(pts) == info.frame_count == probe(target, count_frames=True).frame_count == 13


def test_report_full_quality_uses_opt_in_only(
    video_factory, build_manifest, tmp_path, monkeypatch, capsys
):
    from videoenhancer.jobs.store import input_identity

    source = video_factory(frames=12)
    job = build_manifest(source, fps="off")
    job.update(
        id="report-test",
        schema_version=1,
        state="done",
        position=0,
        input=input_identity(source),
        output=str(source),
        result=str(source),
        segments=[],
        updated_at="",
        created_at="",
    )
    store = JobStore(tmp_path / "home")
    store.save(job)
    monkeypatch.setenv("VE_HOME", str(store.home))
    assert cli.main(["--json", "report", "--full-quality", job["id"]]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["full_quality"]["fidelity_frames"] == 12
    assert store.load(job["id"]).get("quality") is None


def test_temporal_partials_match_full_replay_at_clip_and_segment_joints():
    from videoenhancer.pipeline.inline_quality import _merge_temporal, temporal_partial

    images = {
        i: torch.full((3, 16, 16), value)
        for i, value in enumerate([0.1, 0.2, 0.23, 0.4, 0.44, 0.5])
    }
    joints, excluded = {2, 3}, {2}
    full = _merge_temporal([temporal_partial(images, joints, excluded)], joints, excluded)
    split = _merge_temporal(
        [
            temporal_partial({i: images[i] for i in range(3)}, joints, excluded),
            temporal_partial({i: images[i] for i in range(3, 6)}, joints, excluded),
        ],
        joints,
        excluded,
    )
    assert split["mean_difference"] == pytest.approx(full["mean_difference"], abs=1e-7)
    assert split["baseline"] == pytest.approx(full["baseline"], abs=1e-7)
    assert split["regular_count"] == full["regular_count"]
    assert sorted(split["details"], key=lambda d: d["frame_index"]) == sorted(
        full["details"], key=lambda d: d["frame_index"]
    )
    job = dict(
        settings=dict(preset="fast", fps="2x", short_side="keep"),
        media=dict(width=32, height=32, cfr_fps="30"),
        scene_cuts=[],
        segments=[
            dict(
                start=0,
                end=3,
                stats=dict(
                    inline_quality=dict(
                        fidelity=dict(
                            count=0,
                            finite_count=0,
                            psnr_sum=0,
                            psnr_min=None,
                            ssim_sum=0,
                            ssim_min=1,
                        ),
                        source=temporal_partial({i: images[i] for i in range(3)}, set(), set()),
                        output=temporal_partial(images, {3}, set()),
                    )
                ),
            )
        ],
    )
    assert aggregate_quality(job)["seam_ratio"] is None


def test_progress_cannot_round_to_100_before_done():
    job = dict(
        media=dict(width=32, height=32, cfr_fps="30"),
        settings=dict(preset="passthrough", short_side="keep", fps="off"),
        machine_profile=dict(finalization=dict(a=1e-9, b=0, c=0)),
        segments=[dict(start=0, end=30, state="done")],
        state="queued",
    )
    assert f"{cli._progress(job):.1f}" == "99.9"
    job["state"] = "done"
    assert f"{cli._progress(job):.1f}" == "100.0"


def test_fidelity_handles_small_allowed_frame_geometry():
    from videoenhancer.pipeline.inline_quality import fidelity

    psnr, ssim = fidelity(torch.full((3, 4, 4), 0.5), torch.full((3, 4, 4), 0.5))
    assert psnr == float("inf")
    assert ssim == pytest.approx(1, abs=1e-5)
