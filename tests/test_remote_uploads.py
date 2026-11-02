"""Resumable uploads use bounded reads and never accept client filesystem paths."""

import hashlib
import io

import pytest

from videoenhancer.remote.uploads import Uploads


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
