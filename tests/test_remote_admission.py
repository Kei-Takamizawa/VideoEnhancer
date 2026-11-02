"""Remote admission reuses the engine without changing desktop preferences."""

import shutil
import time

from videoenhancer.remote.adapter import EngineAdapter
from videoenhancer.remote.gateway import Gateway
from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import read_settings


def test_playlist_keeps_supported_entries_and_unknown_network_finish(tmp_path):
    from types import SimpleNamespace

    metadata_calls = []
    video = {
        "format_id": "v",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "duration": 1,
        "vcodec": "h264",
    }

    def metadata(check, key):
        metadata_calls.append(key)
        assert key == "good"
        return "https://example.test/video", {"formats": [video]}

    engine = SimpleNamespace(
        store=SimpleNamespace(queue_jobs=lambda: []),
        operations={
            "check": {
                "state": "done",
                "result": {
                    "entries": [
                        {
                            "key": "bad",
                            "title": "Unavailable",
                            "error": "Live video is not supported.",
                        },
                        {"key": "good", "title": "Synthetic", "duration": 1},
                    ]
                },
            }
        },
        chosen=lambda _: {"preset": "standard"},
        video_links=SimpleNamespace(
            metadata=metadata,
            selected=lambda *args: (video, None),
            estimate=lambda *args: {"seconds": 20, "low": 15, "high": 25},
        ),
    )
    adapter = EngineAdapter(engine, tmp_path, {})
    adapter.jobs = SimpleNamespace(ahead=lambda: 0)
    adapter.requests["check"] = "device"
    result = adapter.check_result("device", "check")
    assert metadata_calls == ["good"]
    assert result["entries"][0]["error"]
    assert result["entries"][1]["format_id"] == "v"
    assert result["entries"][1]["estimate"]["finish"] is None
    assert result["entries"][1]["estimate"]["seconds"] is None


def test_gateway_ignores_schedule_without_rewriting_it(tmp_path, monkeypatch):
    from videoenhancer.service import engine as module

    engine = Engine(tmp_path / "home")
    schedule = engine.home / "schedule.json"
    original = '{"enabled":true,"windows":[]}'
    schedule.write_text(original)
    gateway = Gateway(engine, engine.home, {"library_folder": str(tmp_path / "library")})
    observed = []

    def run_queue(**kwargs):
        observed.append(kwargs["ignore_schedule"])
        engine.stop.set()

    monkeypatch.setattr(module, "run_queue", run_queue)
    engine._cleanup_checked = time.monotonic()
    try:
        engine._worker()
        assert observed == [True]
        assert schedule.read_text() == original
    finally:
        gateway.close()
        engine.close()


def test_interrupted_remote_upload_preparation_resumes_own_output(
    tmp_path, video_factory, monkeypatch
):
    from videoenhancer.service import engine as module

    engine = Engine(tmp_path / "home")
    source = video_factory()
    folder = engine.home / "remote/incoming/session"
    folder.mkdir(parents=True)
    source = shutil.copyfile(source, folder / "source.mp4")
    settings = {
        "preset": "passthrough",
        "codec": "h264",
        "short_side": "keep",
        "fps": "off",
        "backend": "cpu",
    }
    output = tmp_path / "library/.owned.partial.mp4"
    remote = {"device": "d", "title": "Synthetic clip", "folder": str(folder)}
    original = module.add_job

    def interrupted(*args, **kwargs):
        engine.stop.set()
        raise InterruptedError("Service is stopping")

    monkeypatch.setattr(module, "add_job", interrupted)
    try:
        job = engine.add(
            {"file": str(source), "output": str(output), "settings": settings}, remote=remote
        )
        engine._preparations[-1].join(timeout=5)
        assert engine.store.load(job["id"])["state"] == "preparing"
        assert source.exists()
        engine.stop.clear()
        monkeypatch.setattr(module, "add_job", original)
        engine._recover()
        engine._preparations[-1].join(timeout=20)
        recovered = engine.store.load(job["id"])
        assert recovered["state"] == "queued", recovered.get("error")
        assert recovered["source"]["remote"] == remote
        assert read_settings(engine.home)["video_download_folder"] == ""
    finally:
        engine.close()
