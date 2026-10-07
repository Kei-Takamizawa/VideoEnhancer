"""Persistence, disk preflight and segment-boundary tests."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from videoenhancer.jobs.segments import expected_frames, plan_segments
from videoenhancer.jobs.store import JobStore, add_job, input_identity, load_machine_profile


def _manifest(tmp_path: Path, job_id: str) -> dict:
    source = tmp_path / "source.bin"
    source.write_bytes(b"test input")
    now = datetime.now(UTC).isoformat()
    return {
        "schema_version": 1,
        "id": job_id,
        "input": input_identity(source),
        "settings": {"fps": "2x"},
        "media": {"frame_count": 300, "cfr_fps": "30/1"},
        "scene_cuts": [],
        "segments": [{"index": 0, "start": 0, "end": 300, "state": "failed"}],
        "state": "failed",
        "created_at": now,
        "updated_at": now,
        "timing": {"observations": []},
    }


def test_store_atomic_save_resume_and_reorder(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    first = _manifest(tmp_path, "first")
    second = _manifest(tmp_path, "second")
    first["position"], second["position"] = 1, 2
    store.save(first)
    store.save(second)
    stale_first = store.load("first")
    assert json.loads((store.job_dir("first") / "manifest.json").read_text())["id"] == "first"
    assert not list(store.job_dir("first").glob("manifest.*.tmp"))
    store.move("second", 1)
    assert [job["id"] for job in store.list_jobs()] == ["second", "first"]
    stale_first["state"] = "running"
    store.save(stale_first)
    assert store.load("first")["position"] == 2
    resumed = store.set_state("first", "queued")
    assert resumed["segments"][0]["state"] == "pending"
    with pytest.raises(ValueError):
        store.job_dir("../elsewhere")


def test_manifest_readers_serialize_with_atomic_writes(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    manifest = _manifest(tmp_path, "job")
    manifest["revision"] = 0
    store.save(manifest)
    start = threading.Barrier(2)

    def write_revisions() -> None:
        start.wait()
        for revision in range(1, 51):
            current = store.load("job")
            current["revision"] = revision
            store.save(current)

    def read_revisions() -> list[int]:
        start.wait()
        return [store.load("job")["revision"] for _ in range(100)]

    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(write_revisions)
        reader = executor.submit(read_revisions)
        writer.result(timeout=10)
        revisions = reader.result(timeout=10)
    assert all(0 <= revision <= 50 for revision in revisions)
    assert store.load("job")["revision"] == 50


def test_worker_save_cannot_overwrite_newer_pause_request(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    manifest = _manifest(tmp_path, "job")
    manifest["state"] = "queued"
    store.save(manifest)
    stale_worker_copy = store.load("job")
    store.set_state("job", "paused")
    stale_worker_copy["state"] = "running"
    stale_worker_copy["segments"][0]["state"] = "done"
    store.save(stale_worker_copy)
    current = store.load("job")
    assert current["state"] == "paused"
    assert current["segments"][0]["state"] == "done"
    assert store.read_control_state("job") == "paused"
    assert (store.job_dir("job") / "control.json").stat().st_size < 100


def test_segment_plan_respects_cuts_and_exact_frames() -> None:
    media = {"frame_count": 3000, "cfr_fps": "30/1"}
    segments = plan_segments(
        media, [450, 900, 1360, 1800, 2250, 2700], predicted_seconds_per_frame=0.4
    )
    assert segments[0]["end"] == 450
    assert segments[-1]["end"] == 3000
    assert all(
        right["start"] == left["end"]
        for left, right in zip(segments[:-1], segments[1:], strict=True)
    )
    assert all(60 <= segment["end"] - segment["start"] <= 1800 for segment in segments)
    assert (
        sum(
            expected_frames(
                {"media": media, "settings": {"fps": "2x", "preset": "passthrough"}}, segment
            )
            for segment in segments
        )
        == 3000
    )
    assert (
        sum(
            expected_frames(
                {"media": media, "settings": {"fps": "2x", "preset": "p0-test"}}, segment
            )
            for segment in segments
        )
        == 6000
    )


def test_add_job_rejects_low_disk_before_analysis(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"0" * 1024)
    with pytest.raises(OSError, match="Insufficient disk space"):
        add_job(source, home=tmp_path / "home", disk_free=0)
    assert not list((tmp_path / "home" / "jobs").glob("*/manifest.json"))


def test_add_job_reserves_output_of_unfinished_job(tmp_path: Path, monkeypatch: Any) -> None:
    from videoenhancer.media import analyze as media_analyze

    source = tmp_path / "source.mp4"
    source.write_bytes(b"input")
    output = tmp_path / "result.mp4"
    analyses = []

    def fake_analyze(_path: Path, backend: str) -> dict:
        analyses.append(backend)
        return {
            "media": {
                "frame_count": 30,
                "cfr_fps": "30",
                "display_width": 32,
                "display_height": 32,
            },
            "cfr_map": list(range(30)),
            "scene_cuts": [],
        }

    monkeypatch.setattr(media_analyze, "analyze", fake_analyze)
    options = {"preset": "passthrough", "short_side": "keep", "fps": "off", "backend": "cpu"}
    first = add_job(source, settings=options, output=output, home=tmp_path / "home")
    with pytest.raises(FileExistsError, match="reserved by unfinished job"):
        add_job(
            source,
            settings={**options, "codec": "h264"},
            output=output,
            home=tmp_path / "home",
        )
    assert analyses == ["cpu"]
    assert len(JobStore(tmp_path / "home").list_jobs()) == 1
    assert JobStore(tmp_path / "home").load(first["id"])["output"] == str(output)


def test_add_job_checks_home_volume_before_analysis(tmp_path: Path, monkeypatch: Any) -> None:
    from videoenhancer.media import analyze as media_analyze

    source = tmp_path / "source.mp4"
    source.write_bytes(b"input")
    home = tmp_path / "home"
    output_dir = tmp_path / "output-volume"
    output_dir.mkdir()
    monkeypatch.setattr(media_analyze, "analyze", lambda *_args, **_kwargs: pytest.fail("analyzed"))

    def disk_free(path: Path) -> int:
        return 0 if path == home else 1_000_000

    with pytest.raises(OSError, match="Insufficient disk space"):
        add_job(source, output=output_dir / "result.mp4", home=home, disk_free=disk_free)


def test_machine_profile_requires_matching_gpu_and_driver(tmp_path: Path) -> None:
    directory = tmp_path / "profiles"
    directory.mkdir()
    profile = {
        "schema_version": 1,
        "gpu_name": "RTX Test",
        "driver": "999.1",
        "components": {"decode": {"seconds_per_pixel_frame": None}},
    }
    (directory / "test.json").write_text(json.dumps(profile), encoding="utf-8")
    assert load_machine_profile(tmp_path, gpu_name="RTX Test", driver="999.1") == profile
    assert load_machine_profile(tmp_path, gpu_name="Other GPU", driver="999.1") is None


def test_model_profile_identity_change_drops_stale_coefficient(tmp_path):
    directory = tmp_path / "profiles"
    directory.mkdir()
    identity = {"id": "custom", "version": "1", "sha256": "a" * 64, "manifest_sha256": "b" * 64}
    profile = dict(
        schema_version=1,
        gpu_name="RTX Test",
        driver="999.1",
        components={},
        models={"custom": {"identity": identity, "seconds_per_pixel_frame": 1e-6}},
    )
    (directory / "test.json").write_text(json.dumps(profile), encoding="utf-8")
    matching = load_machine_profile(
        tmp_path, gpu_name="RTX Test", driver="999.1", models={"restore": identity}
    )
    assert matching["models"] == profile["models"]
    changed = {**identity, "version": "2"}
    stale = load_machine_profile(
        tmp_path, gpu_name="RTX Test", driver="999.1", models={"restore": changed}
    )
    assert stale["models"] == {}
