"""Product size limits reject metadata before analysis or GPU admission."""

import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from videoenhancer.jobs.checks import geometry_warning, job_support_reason, source_warning
from videoenhancer.jobs.store import JobStore, add_job
from videoenhancer.media.probe import probe
from videoenhancer.pipeline.runner import process_segment
from videoenhancer.schedule.controller import run_queue
from videoenhancer.service.engine import Engine
from videoenhancer.service.server import LocalServer
from videoenhancer.service.settings import read_settings, save_settings, write_json


@pytest.mark.parametrize(
    "size,allowed",
    [((1080, 1920), True), ((1920, 1080), True), ((1081, 1920), False), ((1440, 2560), False)],
)
@pytest.mark.parametrize("preset", ["standard", "fast"])
def test_displayed_short_side_limit(tmp_path, size, allowed, preset):
    media = dict(width=size[0], height=size[1], display_width=size[0], display_height=size[1])
    settings = dict(preset=preset, short_side=1080, codec="hevc", fps="off")
    reason = geometry_warning(tmp_path, media, settings, {})
    if allowed:
        assert reason is None
    else:
        assert (
            reason == f"This video is larger than 1080p (short side {min(size)} px). "
            "VideoEnhancer processes videos up to 1080p."
        )


def test_rotation_uses_display_dimensions(video_factory, ffmpeg_run, tmp_path):
    source = video_factory(width=1920, height=1080, frames=2)
    rotated = tmp_path / "rotated.mp4"
    ffmpeg_run("-display_rotation", "90", "-i", str(source), "-c", "copy", str(rotated))
    media = probe(rotated, read_timeline=False).to_dict()
    assert (media["display_width"], media["display_height"]) == (1080, 1920)
    assert source_warning(media) is None


def test_even_processing_projection_does_not_admit_a_1081_pixel_source():
    media = dict(
        width=1081, height=1920, display_width=1080, display_height=1920, sample_aspect_ratio="1:1"
    )
    assert source_warning(media) == (
        "This video is larger than 1080p (short side 1081 px). "
        "VideoEnhancer processes videos up to 1080p."
    )


def test_anamorphic_limit_uses_the_projected_short_side():
    assert (
        source_warning(
            dict(width=2160, height=1081, display_width=1080, display_height=1081, sar="1/2")
        )
        is None
    )


def test_api_and_cli_refuse_before_analysis_and_compare(tmp_path, video_factory, monkeypatch):
    source = video_factory()
    metadata = probe(source, read_timeline=False).to_dict()
    metadata.update(width=1081, height=1920, display_width=1081, display_height=1920)

    def fake(*args, **kwargs):
        return SimpleNamespace(to_dict=lambda: metadata)

    monkeypatch.setattr("videoenhancer.service.engine.probe", fake)
    monkeypatch.setattr("videoenhancer.jobs.store.probe", fake)
    monkeypatch.setattr(
        "videoenhancer.media.analyze.analyze",
        lambda *a, **k: pytest.fail("Oversized source reached analysis"),
    )
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    monkeypatch.setattr(engine, "health", lambda: {"smart_app_control": {"blocked": False}})
    server = LocalServer(engine)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = {
            "file": str(source),
            "settings": {
                "preset": "fast",
                "backend": "cpu",
                "short_side": 1080,
                "fps": "off",
                "codec": "hevc",
            },
        }
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/v1/queue",
            data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + server.token, "Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(request, timeout=5)
        assert failure.value.code == 400
        assert json.load(failure.value)["error"] == source_warning(metadata)
        with pytest.raises(ValueError, match="larger than 1080p"):
            add_job(source, {"preset": "fast", "backend": "cpu"}, home=engine.home)
        for kind in ("trial", "compare"):
            with pytest.raises(ValueError, match="larger than 1080p"):
                engine.operation(kind, body)
        assert engine.store.list_jobs() == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        engine.close()


def legacy(job_id, source, output, width=1920, height=1080, target=1080, state="queued"):
    return dict(
        schema_version=1,
        id=job_id,
        input={"path": str(source)},
        output=str(output),
        state=state,
        settings=dict(preset="fast", backend="cuda", short_side=target, fps="off", codec="hevc"),
        media=dict(
            width=width,
            height=height,
            display_width=width,
            display_height=height,
            cfr_fps="30",
            duration=1,
            frame_count=30,
        ),
        segments=[dict(index=0, start=0, end=30, state="pending", predicted_seconds=1)],
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_legacy_queue_never_runs_and_finished_history_is_unchanged(tmp_path):
    home = tmp_path / "home"
    store = JobStore(home)
    source = tmp_path / "synthetic-placeholder.mp4"
    source.write_bytes(b"Metadata-only fixture, never decoded")
    for job in (
        legacy("large-source", source, tmp_path / "a.mp4", 3840, 2160),
        legacy("large-output", source, tmp_path / "b.mp4", target=2160),
        legacy("history", source, tmp_path / "c.mp4", 3840, 2160, 2160, "done"),
    ):
        store.save(job)
    finished = (store.job_dir("history") / "manifest.json").read_bytes()
    engine = Engine(home)
    try:
        engine._recover()
        run_queue(home=home, ignore_schedule=True)
        for job_id in ("large-source", "large-output"):
            job = store.load(job_id)
            assert job["state"] == "queued"
            assert job["error"].startswith("No longer supported:")
            assert job["unsupported_reason"] == job_support_reason(job)
            with pytest.raises(ValueError, match="No longer supported"):
                store.set_state(job_id, "queued")
        assert store.load("large-output")["settings"]["short_side"] == 2160
        assert (store.job_dir("history") / "manifest.json").read_bytes() == finished
        with pytest.raises(ValueError, match="No longer supported"):
            process_segment(
                store.load("large-source"),
                {"index": 0, "start": 0, "end": 1},
                tmp_path / "never.mp4",
                lambda: False,
            )
        assert not (tmp_path / "never.mp4").exists()
    finally:
        engine.close()


def test_settings_migration_is_logged_and_does_not_change_codec(tmp_path):
    write_json(tmp_path / "settings.json", {"short_side": 2160, "codec": "hevc", "theme": "dark"})
    assert read_settings(tmp_path)["short_side"] == 1440
    assert read_settings(tmp_path)["codec"] == "hevc"
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8")) == {
        "short_side": 1440,
        "codec": "hevc",
        "theme": "dark",
    }
    events = [
        json.loads(line)["event"]
        for line in (tmp_path / "videoenhancer.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events.count("Changed the saved default output size from 2160p to 1440p.") == 1
    with pytest.raises(ValueError, match="Invalid short_side"):
        save_settings(tmp_path, {"short_side": 2160})
