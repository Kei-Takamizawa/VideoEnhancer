"""Focused deferred-finding regressions with synthetic metadata only."""

from types import SimpleNamespace

from videoenhancer.jobs.store import JobStore
from videoenhancer.service.engine import Engine
from videoenhancer.service.link_tools import ToolManager
from videoenhancer.service.video_links import VideoLinks


def test_reanalysis_keeps_runtime_decoder_choice(tmp_path, monkeypatch):
    job = dict(
        id="a" * 32,
        state="queued",
        analysis_missing=True,
        input={"path": str(tmp_path / "source.mp4")},
        settings={"backend": "cuda"},
        decoder="ffmpeg",
        decoder_reason="Runtime NVDEC mismatch: synthetic",
        decoder_events=[{"decoder": "ffmpeg", "segment": 0}],
    )
    monkeypatch.setattr("videoenhancer.jobs.store.input_identity", lambda _: job["input"])
    monkeypatch.setattr(
        "videoenhancer.jobs.store.probe", lambda *a, **k: SimpleNamespace(to_dict=lambda: {})
    )
    monkeypatch.setattr(
        "videoenhancer.media.analyze.analyze",
        lambda *a, **k: {"decoder": "nvdec", "decoder_reason": "Timestamp scan passed."},
    )
    store = JobStore(tmp_path)
    monkeypatch.setattr(store, "save", lambda _: None)
    monkeypatch.setattr(store, "load", lambda _: job)
    assert store.ensure_analysis(job)["decoder"] == "ffmpeg"
    assert job["decoder_reason"] == "Runtime NVDEC mismatch: synthetic"


def test_invalid_audio_choice_does_not_disable_video(tmp_path):
    links = VideoLinks(tmp_path, ToolManager(tmp_path))
    video = dict(
        format_id="v",
        vcodec="h264",
        acodec="none",
        url="https://example.com/v",
        width=640,
        height=360,
        fps=30,
        duration=2,
    )
    audio = dict(format_id="a", vcodec="none", acodec="aac", url="https://example.com/a")
    invalid = {**audio, "format_id": "insecure", "url": "http://example.com/a"}
    chosen, selected = links.selected(
        "https://example.com/watch", {"formats": [video, audio, invalid]}, "v"
    )
    assert chosen == video
    assert selected == audio


def test_finished_observations_refresh_link_profile(tmp_path, monkeypatch):
    links = VideoLinks(tmp_path, ToolManager(tmp_path))
    links.hardware = {"gpu": "synthetic", "driver": "fixture"}
    calls = []

    def profile(*args, **kwargs):
        calls.append(True)
        return {"revision": len(calls)}

    monkeypatch.setattr("videoenhancer.service.video_links.load_machine_profile", profile)
    settings = {"backend": "cpu", "preset": "passthrough", "fps": "off"}
    media = {"cfr_fps": "30"}
    assert links.profile(settings, media)["revision"] == 1
    assert links.profile(settings, media)["revision"] == 1
    (tmp_path / "timing-observations.json").write_text('{"jobs": []}', encoding="utf-8")
    assert links.profile(settings, media)["revision"] == 2


def test_tool_changes_are_already_refused_during_link_checks(tmp_path):
    import pytest

    engine = Engine(tmp_path)
    engine.operations["synthetic"] = {"kind": "link check", "state": "running"}
    try:
        for action in ("install", "uninstall"):
            with pytest.raises(ValueError, match="link checks"):
                engine.link_tools_operation(action, {})
    finally:
        engine.close()


def test_missing_analysis_refuses_high_depth_with_exact_reason(tmp_path, monkeypatch):
    import pytest

    job = dict(
        id="a" * 32,
        state="queued",
        analysis_missing=True,
        input={"path": str(tmp_path / "source.mkv")},
        settings={"backend": "cpu"},
    )
    monkeypatch.setattr("videoenhancer.jobs.store.input_identity", lambda _: job["input"])
    monkeypatch.setattr(
        "videoenhancer.jobs.store.probe",
        lambda *a, **k: SimpleNamespace(
            to_dict=lambda: {"bit_depth": 12, "pixel_format": "yuv420p12le"}
        ),
    )

    def unexpected_analysis(*args, **kwargs):
        raise AssertionError("High-depth analysis must not start.")

    monkeypatch.setattr("videoenhancer.media.analyze.analyze", unexpected_analysis)
    with pytest.raises(ValueError) as refused:
        JobStore(tmp_path).ensure_analysis(job)
    assert (
        str(refused.value)
        == "This video uses 12-bit color. VideoEnhancer accepts 8-bit and 10-bit videos only."
    )


def test_recovered_preparation_refuses_high_depth_with_exact_reason(tmp_path, monkeypatch):
    source = tmp_path / "synthetic.mkv"
    source.write_bytes(b"metadata fixture, never decoded")
    monkeypatch.setattr(
        "videoenhancer.service.engine.probe",
        lambda *a, **k: SimpleNamespace(
            to_dict=lambda: {"bit_depth": 12, "pixel_format": "yuv420p12le"}
        ),
    )
    engine = Engine(tmp_path / "home")
    job = dict(
        schema_version=1,
        id="a" * 32,
        state="preparing",
        input={"path": str(source)},
        output=str(tmp_path / "out.mp4"),
        settings={"backend": "cpu", "preset": "fast"},
        media={},
        segments=[],
        created_at="2026-10-22T00:00:00Z",
    )
    engine.store.save(job)
    try:
        engine._recover()
        result = engine.store.load(job["id"])
        assert result["state"] == "failed"
        assert (
            result["error"]
            == "This video uses 12-bit color. VideoEnhancer accepts 8-bit and 10-bit videos only."
        )
        assert source.read_bytes() == b"metadata fixture, never decoded"
    finally:
        engine.close()
