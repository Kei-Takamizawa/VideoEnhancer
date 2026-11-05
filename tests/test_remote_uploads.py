"""Resumable uploads use bounded reads and never accept client filesystem paths."""

import hashlib
import io
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from videoenhancer.remote.uploads import Uploads


def test_expiration_uses_last_chunk_or_finish_and_preserves_jobs(tmp_path):
    now = [100.0]
    uploads = Uploads(tmp_path, clock=lambda: now[0], probe=lambda _: {"width": 32, "height": 32})
    unfinished, finished, owned = [uploads.create(device, "clip.mp4", 2)["id"] for device in "dfo"]
    now[0] += 100
    uploads.chunk("d", unfinished, 0, io.BytesIO(b"x"), 1)
    uploads.chunk("f", finished, 0, io.BytesIO(b"xx"), 2)
    now[0] += 100
    uploads.finish("f", finished, hashlib.sha256(b"xx").hexdigest())
    uploads.sweep({tmp_path / owned})
    now[0] += 86299
    uploads.sweep({tmp_path / owned})
    assert uploads.status("d", unfinished)["offset"] == 1
    assert uploads.status("f", finished)["ready"]
    now[0] += 1
    # A fresh service instance must expire persisted sessions too.
    uploads = Uploads(tmp_path, clock=lambda: now[0])
    uploads.sweep({tmp_path / owned})
    with pytest.raises(ValueError, match="This upload expired. Choose the video again."):
        uploads.status("d", unfinished)
    assert not (tmp_path / unfinished).exists()
    assert uploads.status("f", finished)["ready"]
    now[0] += 100
    uploads.sweep({tmp_path / owned})
    with pytest.raises(ValueError, match="This upload expired. Choose the video again."):
        uploads.status("f", finished)
    assert not (tmp_path / finished).exists()
    assert uploads.status("o", owned)


@pytest.mark.parametrize("operation", ["chunk", "finish"])
def test_slow_upload_does_not_block_status_and_rejects_concurrent_writes(
    tmp_path, monkeypatch, operation
):
    uploads = Uploads(tmp_path, probe=lambda _: {"width": 32, "height": 32})
    identifier, other = [uploads.create(device, "clip.mp4", 1)["id"] for device in ["d", "other"]]
    entered, release = threading.Event(), threading.Event()
    digest = hashlib.sha256(b"x").hexdigest()

    class SlowStream(io.BytesIO):
        def read(self, size):
            entered.set()
            assert release.wait(5)
            return super().read(size)

    original = hashlib.file_digest

    def slow_hash(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    if operation == "finish":
        uploads.chunk("d", identifier, 0, io.BytesIO(b"x"), 1)
        monkeypatch.setattr(hashlib, "file_digest", slow_hash)

        def work():
            return uploads.finish("d", identifier, digest)
    else:

        def work():
            return uploads.chunk("d", identifier, 0, SlowStream(b"x"), 1)

    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = pool.submit(work)
        try:
            assert entered.wait(2)
            assert pool.submit(uploads.status, "other", other).result(timeout=1)["offset"] == 0
            for action in (
                lambda: uploads.chunk("d", identifier, 0, io.BytesIO(b"x"), 1),
                lambda: uploads.finish("d", identifier, digest),
            ):
                with pytest.raises(ValueError, match="already being updated"):
                    pool.submit(action).result(timeout=1)
        finally:
            release.set()
        pending.result(timeout=2)


def test_upload_resume_hash_and_owner(tmp_path):
    data = b"synthetic video"

    def probe(_):
        return {"width": 1920, "height": 1080, "duration": 1}

    uploads = Uploads(tmp_path, probe=probe)
    item = uploads.create("device", "../../clip.mp4", len(data))
    identifier = item["id"]
    uploads.chunk("device", identifier, 0, io.BytesIO(data[:4]), 4)
    uploads = Uploads(tmp_path, probe=probe)
    assert uploads.status("device", identifier)["offset"] == 4
    with pytest.raises(ValueError):
        uploads.status("other", identifier)
    with pytest.raises(ValueError):
        uploads.chunk("device", identifier, 0, io.BytesIO(data), len(data))
    uploads.chunk("device", identifier, 4, io.BytesIO(data[4:]), len(data) - 4)
    item = uploads.finish("device", identifier, hashlib.sha256(data).hexdigest())
    assert item["ready"] and item["media"]["height"] == 1080
    assert uploads.source("device", identifier).is_relative_to(tmp_path)


@pytest.mark.parametrize("reason", ["hash", "size"])
def test_bad_upload_is_deleted(tmp_path, reason):
    uploads = Uploads(tmp_path, probe=lambda _: {"width": 3840, "height": 2160})
    identifier = uploads.create("device", "clip.mp4", 1)["id"]
    uploads.chunk("device", identifier, 0, io.BytesIO(b"x"), 1)
    digest = hashlib.sha256(b"x").hexdigest() if reason == "size" else "0" * 64
    with pytest.raises(ValueError, match="1080|hash"):
        uploads.finish("device", identifier, digest)
    assert not (tmp_path / identifier).exists()


def test_anamorphic_upload_checks_display_geometry_and_is_deleted(tmp_path):
    uploads = Uploads(
        tmp_path,
        probe=lambda _: {
            "width": 1080,
            "height": 1920,
            "display_width": 2160,
            "display_height": 1920,
            "sample_aspect_ratio": "2",
        },
    )
    identifier = uploads.create("device", "clip.mp4", 1)["id"]
    uploads.chunk("device", identifier, 0, io.BytesIO(b"x"), 1)
    with pytest.raises(ValueError, match="1080"):
        uploads.finish("device", identifier, hashlib.sha256(b"x").hexdigest())
    assert not (tmp_path / identifier).exists()


def test_limits_and_interrupted_chunk(tmp_path, monkeypatch):
    from collections import namedtuple

    usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr("shutil.disk_usage", lambda _: usage(100, 0, 100))
    uploads = Uploads(tmp_path)
    for size in (0, 91, 20_000_000_001, True):
        with pytest.raises(ValueError):
            uploads.create("device", "clip.mp4", size)
    identifier = uploads.create("device", "clip.mp4", 10)["id"]
    with pytest.raises(ValueError):
        uploads.chunk("device", identifier, 0, io.BytesIO(b"short"), 10)
    assert uploads.status("device", identifier)["offset"] == 0
