"""Independent bounded network scheduling and durable pause/recovery."""

import threading
import time

import pytest

from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import save_settings


def test_folder_and_disk_admission_fail_without_a_job(tmp_path, monkeypatch):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    video = dict(
        format_id="video",
        url="http://localhost/video.mp4",
        width=320,
        height=180,
        fps=30,
        duration=2,
        vcodec="h264",
        filesize=1000000,
    )
    entry = dict(id="synthetic", title="Synthetic", extractor="generic", formats=[video])
    monkeypatch.setattr(engine.video_links, "metadata", lambda *args: (video["url"], entry))
    value = dict(
        check_id="test",
        entry_key="0",
        format_id="video",
        settings=dict(preset="fast", backend="cpu"),
    )
    try:
        with pytest.raises(ValueError, match="Choose a video-download folder"):
            engine.link_jobs.queue(value)
        save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})

        def full(home, folder, required, **kwargs):
            assert kwargs["download_bytes"] == 1000000
            assert required > 0
            raise ValueError("Insufficient space")

        monkeypatch.setattr("videoenhancer.jobs.store.require_working_space", full)
        with pytest.raises(ValueError, match="Insufficient space"):
            engine.link_jobs.queue(value)
        assert engine.store.list_jobs() == []
    finally:
        engine.close()


@pytest.mark.parametrize("missing", [None, "fps", "width"])
def test_failed_transfer_retries_three_times_then_offers_retry(tmp_path, monkeypatch, missing):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
    video = dict(
        format_id="video",
        url="http://localhost/video.mp4",
        width=320,
        height=180,
        fps=30,
        duration=2,
        vcodec="h264",
    )
    if missing:
        video.pop(missing)
    entry = dict(id="synthetic", title="Synthetic", extractor="generic", formats=[video])
    monkeypatch.setattr(engine.video_links, "metadata", lambda *args: (video["url"], entry))
    calls = []

    def disconnected(*args):
        calls.append(time.monotonic())
        raise ValueError("Server disconnected")

    monkeypatch.setattr(engine.video_links, "download", disconnected)
    try:
        job = engine.link_jobs.queue(
            dict(
                check_id="test",
                entry_key="0",
                format_id="video",
                settings=dict(preset="fast", backend="cpu"),
            )
        )
        engine.link_jobs.download(job["id"])
        failed = engine.store.load(job["id"])
        assert len(calls) == 4
        assert failed["state"] == "failed"
        assert failed["error"] == "Server disconnected"
        row = engine.queue()["jobs"][0]
        assert row["error"] == "Server disconnected" and row["state"] == "failed"
        assert all(b - a >= delay for a, b, delay in zip(calls, calls[1:], [1, 2, 4], strict=False))
        retried = engine.link_jobs.retry(job["id"])
        assert retried["state"] == "downloading" and retried["download"]["retries"] == 0
        assert job["id"] in engine.link_jobs.pending
    finally:
        engine.close()


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_network_pool_limit_pause_and_recover(tmp_path, monkeypatch, limit):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    save_settings(
        engine.home,
        {"video_download_folder": str(tmp_path / "downloads"), "video_download_limit": limit},
    )
    video = dict(
        format_id="video",
        width=320,
        height=180,
        fps=30,
        duration=2,
        vcodec="h264",
        acodec="none",
        url="http://localhost/video.mp4",
    )
    entry = dict(id="synthetic", title="Synthetic", extractor="generic", formats=[video])
    monkeypatch.setattr(engine.video_links, "metadata", lambda *args: (video["url"], entry))
    gate = threading.Event()
    calls = []
    lock = threading.Lock()

    def download(job, paused, *args):
        with lock:
            calls.append(job["id"])
        while not gate.wait(0.02):
            if paused():
                raise InterruptedError("Paused")
        raise InterruptedError("Paused")

    monkeypatch.setattr(engine.video_links, "download", download)
    try:
        jobs = [
            engine.link_jobs.queue(
                dict(
                    check_id="test",
                    entry_key="0",
                    format_id="video",
                    settings=dict(preset="fast", fps="off", backend="cpu"),
                )
            )
            for _ in range(5)
        ]
        engine.link_jobs.recover()
        deadline = time.monotonic() + 5
        while len(calls) < limit and time.monotonic() < deadline:
            time.sleep(0.02)
        assert len(calls) == limit
        assert len(engine.link_jobs.active) == limit
        engine.paused = True
        gate.set()
        while engine.link_jobs.active and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not engine.link_jobs.active
        assert all(engine.store.load(job["id"])["state"] == "downloading" for job in jobs)
        assert len(calls) == limit
    finally:
        engine.close()
    restored = Engine(engine.home)
    restored.paused = True
    try:
        restored.link_jobs.recover()
        assert set(restored.link_jobs.pending) == {job["id"] for job in jobs}
    finally:
        restored.close()
