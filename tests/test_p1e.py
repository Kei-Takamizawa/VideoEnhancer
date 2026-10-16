"""Owner-check regressions using synthetic media and isolated engine homes."""

import os
from datetime import UTC, datetime, timedelta

import pytest

from videoenhancer.jobs.store import JobStore, estimated_output_size, input_identity
from videoenhancer.media.probe import probe
from videoenhancer.service.deletion import VideoDeletion


@pytest.mark.parametrize(
    "existing,supported,expected",
    [(False, True, "av1"), (False, False, "hevc"), (True, True, "hevc")],
)
def test_first_run_codec_is_qualified_and_existing_preferences_are_preserved(
    tmp_path, monkeypatch, existing, supported, expected
):
    from types import SimpleNamespace

    import torch

    from videoenhancer.service.engine import Engine
    from videoenhancer.service.settings import read_settings, save_settings

    home = tmp_path / "home"
    if existing:
        save_settings(home, {"codec": "hevc"})
    monkeypatch.setattr("videoenhancer.logging.environment_info", lambda: {})
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        torch.cuda, "get_device_properties", lambda _: SimpleNamespace(total_memory=8 * 1024**3)
    )
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cuda")
    monkeypatch.setattr(
        "videoenhancer.service.av1_cache.capabilities", lambda *_: {"av1_supported": supported}
    )
    engine = Engine(home)
    try:
        engine._environment()
        assert read_settings(home)["codec"] == expected
    finally:
        engine.close()


def test_live_inference_rate_does_not_replace_pending_segment_cost():
    from videoenhancer.estimate.model import estimate_job, predict_finalization, predict_segment

    profile = {"live_seconds_per_frame": 0.1, "segment_overhead_seconds": 2}
    job = dict(
        state="running",
        media={"width": 32, "height": 32, "cfr_fps": "30"},
        settings={"preset": "passthrough", "short_side": "keep", "fps": "off"},
        machine_profile=profile,
        progress={"segment": 0, "frames_done": 50},
        segments=[
            dict(index=0, start=0, end=100, state="running"),
            dict(index=1, start=100, end=200, state="pending"),
        ],
    )
    without_live = {"segment_overhead_seconds": 2}
    expected = (
        5
        + predict_segment(job["media"], job["settings"], 100, without_live)
        + predict_finalization(job)
    )
    assert estimate_job(job).seconds == pytest.approx(expected)


def test_plan_restarts_interrupted_part_after_hours_gap(monkeypatch):
    from zoneinfo import ZoneInfo

    from videoenhancer.schedule.planner import build_plan
    from videoenhancer.schedule.windows import Schedule

    monkeypatch.setattr("videoenhancer.schedule.planner.predict_segment", lambda *_: 100)
    monkeypatch.setattr("videoenhancer.schedule.planner.predict_finalization", lambda *_: 0)
    schedule = Schedule.from_dict(
        dict(
            enabled=True,
            weekly=[
                dict(days=["mon"], start="08:00", end="08:15"),
                dict(days=["mon"], start="08:30", end="08:45"),
            ],
        ),
        ZoneInfo("UTC"),
    )
    job = dict(
        id="synthetic",
        state="running",
        settings={},
        media={},
        admitted_window_end="2026-10-12T08:15:00+00:00",
        allow_window_overrun=False,
        progress={"segment": 0, "frames_done": 50},
        segments=[dict(index=0, start=0, end=100, state="running")],
    )
    plan = build_plan([job], schedule, datetime(2026, 10, 12, 8, 14, 50, tzinfo=UTC))
    assert plan["timeline"][0]["phase"] == "interrupted work"
    assert plan["timeline"][0]["seconds"] == 10
    assert plan["jobs"][0]["completion"] == "2026-10-12T08:31:40+00:00"


def test_queue_projection_uses_positions_not_directory_order(tmp_path):
    store = JobStore(tmp_path / "home")
    for job_id, position in (("a", 3), ("b", 1), ("c", 2)):
        store.save(
            dict(
                schema_version=1,
                id=job_id,
                position=position,
                created_at="2026-01-01T00:00:00+00:00",
                state="paused",
                segments=[],
                media={},
                settings={},
            )
        )
    assert [job["id"] for job in store.queue_jobs()] == ["b", "c", "a"]


def test_larger_source_keeps_its_geometry_in_space_estimate():
    media = dict(display_width=3840, display_height=2160)
    settings = dict(short_side=1080, fps="off", codec="hevc")
    assert estimated_output_size(1_000_000, media, settings) == 700_000
    assert estimated_output_size(1_000_000, media, {**settings, "fps": "2x"}) == 1_400_000
    assert estimated_output_size(1_000_000, media, {**settings, "codec": "av1"}) == 600_000


def test_same_volume_reserves_segments_joined_and_final_temporary(tmp_path):
    from videoenhancer.jobs.store import require_working_space

    home = tmp_path / "home"
    output = tmp_path / "output"
    home.mkdir()
    output.mkdir()
    with pytest.raises(OSError, match="Insufficient"):
        require_working_space(home, output, 1000, 3299)
    require_working_space(home, output, 1000, 3300)


def test_codec_space_refresh_updates_av1_geometry_without_time_estimation(
    tmp_path, video_factory, monkeypatch
):
    from videoenhancer.service.engine import Engine

    source = video_factory(width=96, height=64)
    engine = Engine(tmp_path / "home")
    engine.environment.update(av1_supported=True, av1_min_width=256, av1_min_height=128)
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cuda")
    monkeypatch.setattr(
        engine, "estimate", lambda *_: pytest.fail("Space refresh must not estimate time")
    )
    try:
        for codec, blocked in (("av1", True), ("hevc", False)):
            result = engine.dispatch(
                "POST",
                ["estimate", "space"],
                {
                    "files": [str(source)],
                    "settings": {
                        "preset": "fast",
                        "backend": "cuda",
                        "short_side": "keep",
                        "fps": "off",
                        "codec": codec,
                    },
                },
            )
            assert (
                any(
                    "too small for AV1" in warning
                    for warning in result["files"][str(source)]["warnings"]
                )
                == blocked
            )
    finally:
        engine.close()


@pytest.mark.parametrize("transfer", ["smpte2084", "arib-std-b67"])
def test_correct_bt2020_hdr_tags_reach_warning_probe(tmp_path, ffmpeg_run, transfer):
    source = tmp_path / "hdr.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "color=size=3840x2160:rate=30",
        "-frames:v",
        "3",
        "-c:v",
        "libx265",
        "-preset",
        "ultrafast",
        "-threads",
        "2",
        "-x265-params",
        "pools=1:frame-threads=1:colorprim=9:colormatrix=9:transfer="
        + ("16" if transfer == "smpte2084" else "18"),
        "-pix_fmt",
        "yuv420p10le",
        "-colorspace",
        "bt2020nc",
        "-color_primaries",
        "bt2020",
        "-color_trc",
        transfer,
        str(source),
    )
    media = probe(source, allow_hdr=True)
    assert media.color_matrix == "bt2020nc"
    assert media.color_transfer == transfer
    with pytest.raises(ValueError, match="HDR"):
        probe(source)


@pytest.mark.parametrize("case", ["valid", "before_start", "after_finish", "wrong_duration"])
def test_legacy_output_requires_both_time_window_and_duration(
    tmp_path, video_factory, monkeypatch, case
):
    from test_deletion import FakeFiles

    output = video_factory(frames=30)
    now = datetime.now(UTC)
    stamp = now.timestamp()
    if case == "before_start":
        stamp -= 10
    elif case == "after_finish":
        stamp += 70
    os.utime(output, (stamp, stamp))
    original = tmp_path / "original.mp4"
    original.write_bytes(b"synthetic original")
    job = dict(
        id="legacy",
        state="done",
        input=input_identity(original),
        output=str(output),
        settings={"fps": "off"},
        media={"cfr_fps": "30", "frame_count": 60 if case == "wrong_duration" else 30},
        started_at=(now - timedelta(seconds=1)).isoformat(),
        finished_at=now.isoformat(),
    )
    result = VideoDeletion(tmp_path / "home", FakeFiles()).delete(output, job, [job])
    assert result == "Moved to the Recycle Bin" if case == "valid" else result.startswith("Kept:")


def test_weight_hash_cache_invalidates_on_file_change(tmp_path):
    from videoenhancer.models.registry import sha256

    path = tmp_path / "weights.bin"
    path.write_bytes(b"first")
    first = sha256(path)
    assert sha256(path) == first
    path.write_bytes(b"second")
    assert sha256(path) != first


def test_remove_with_files_keeps_changed_record_and_undo_restores_only_records(tmp_path):
    from test_controller import _job
    from test_deletion import FakeFiles

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    try:
        job = _job(engine.store, tmp_path)
        output = tmp_path / "output.mp4"
        output.write_bytes(b"synthetic output")
        job.update(state="done", output_identity=input_identity(output))
        engine.store.save(job)
        engine.deletion = VideoDeletion(engine.home, FakeFiles())
        result = engine.history_action("remove", {"ids": [job["id"]], "output": True})
        assert result["files"] == {"moved": 1, "not_found": 0, "kept": 0}
        assert not engine.queue()["jobs"]
        engine.history_action("undo", {"ids": result["ids"]})
        assert engine.queue()["jobs"][0]["id"] == job["id"]
        assert not output.exists()
        output.write_bytes(b"replacement")
        refused = engine.history_action("remove", {"ids": [job["id"]], "output": True})
        assert refused["files"]["kept"] == 1
        assert engine.queue()["jobs"][0]["id"] == job["id"]
    finally:
        engine.close()


def test_analysis_sidecar_is_written_once_and_survives_cancel_cleanup(tmp_path):
    import json

    from test_controller import _job

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    try:
        job = _job(engine.store, tmp_path)
        sidecar = engine.store.job_dir(job["id"]) / "analysis.json"
        stamp = sidecar.stat().st_mtime_ns
        job["segments"][0]["state"] = "done"
        engine.store.save(job)
        assert sidecar.stat().st_mtime_ns == stamp
        raw = json.loads((sidecar.parent / "manifest.json").read_text())
        assert "cfr_map" not in raw
        engine.cancel_job(job["id"])
        assert engine.store.load(job["id"])["cfr_map"] == list(range(300))
    finally:
        engine.close()
