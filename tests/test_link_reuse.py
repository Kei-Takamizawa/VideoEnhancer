"""Generic basename IDs need URL and pre-download media identity checks."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from videoenhancer.jobs.store import input_identity
from videoenhancer.service.video_links import VideoLinks


@pytest.mark.parametrize(
    "change,offered",
    [
        ({}, True),
        ({"webpage_url": "HTTP://LOCALHOST:8000/video.mp4#new"}, True),
        ({"webpage_url": "http://localhost:8001/video.mp4"}, False),
        ({"webpage_url": "http://127.0.0.1:8000/video.mp4"}, False),
        ({"webpage_url": "http://localhost:8000/Video.mp4"}, False),
        ({"webpage_url": "http://localhost:8000/video.mp4?token=new"}, False),
        ({"timestamp": 2}, False),
        ({"duration": 11}, False),
        ({"duration": 10.5}, True),
        ({"duration": None}, False),
        ({"width": None}, False),
        ({"height": 240}, False),
    ],
)
def test_generic_reuse(tmp_path, change, offered):
    path = tmp_path / "video.mkv"
    path.write_bytes(b"unchanged fixture")
    job = dict(
        id="a",
        input=input_identity(path),
        source=dict(
            extractor_key="Generic",
            id="video",
            url="http://localhost:8000/video.mp4#old",
            timestamp=1,
            downloaded_at="2026-10-18",
        ),
        media=dict(width=320, height=180, duration=10, cfr_fps="30"),
    )
    entry = dict(
        extractor_key="Generic",
        id="video",
        webpage_url="http://localhost:8000/video.mp4",
        timestamp=1,
        width=320,
        height=180,
        duration=10,
    )
    entry.update(deepcopy(change))
    links = VideoLinks.__new__(VideoLinks)
    assert bool(links.reusable(entry, SimpleNamespace(queue_jobs=lambda: [job]))) == offered


def test_site_identity_uses_extractor_key_and_id_only(tmp_path):
    path = tmp_path / "video.mkv"
    path.write_bytes(b"fixture")
    job = dict(
        id="a",
        input=input_identity(path),
        source=dict(extractor_key="Site", extractor="old-alias", id="1", url="https://old.test"),
    )
    links = VideoLinks.__new__(VideoLinks)
    assert (
        links.reusable(
            dict(
                extractor_key="Site", extractor="new-alias", id="1", webpage_url="https://new.test"
            ),
            SimpleNamespace(queue_jobs=lambda: [job]),
        )["job_id"]
        == "a"
    )
