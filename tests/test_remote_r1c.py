"""Mac claims and library-side image contracts."""

import pytest

from videoenhancer.remote.security import device_label


def test_validated_mac_hint():
    agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Version/26.0 Safari/605.1"
    assert device_label(agent, "mac") == "Mac, Safari 26"
    assert device_label(agent.replace("Version/26.0", "Chrome/142.0"), "mac") == "Mac, Chrome 142"
    assert device_label(agent, "ipad") == "iPad, Safari 26"
    with pytest.raises(ValueError):
        device_label(agent, "<script>")
    with pytest.raises(ValueError):
        device_label("Windows Chrome/142.0", "mac")


def test_storyboard_plan():
    from videoenhancer.remote.thumbnails import storyboard_plan

    assert storyboard_plan(600, 1920, 1080) == (3, 160, 90, 200)
    assert storyboard_plan(10, 1080, 1920) == (2, 160, 284, 5)


@pytest.mark.parametrize("width,height,gop", [(320, 180, 10), (1080, 1920, 10), (320, 180, 300)])
def test_generated_images(tmp_path, ffmpeg_run, width, height, gop, monkeypatch):
    from videoenhancer.remote.library import Library
    from videoenhancer.remote.thumbnails import MAX_BYTES, Thumbnails

    library = Library(tmp_path / "home", tmp_path / "library")
    library.folder.mkdir()
    path = library.folder / "clip.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={width}x{height}:rate=10:duration=5",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-preset",
        "ultrafast",
        "-g",
        str(gop),
        str(path),
    )
    images = Thumbnails(library)
    identifier = library._identifier(path)
    index = images.generate(identifier)
    assert index["keyframe_only"] == (gop == 10)
    assert index["frames"] == 3
    assert index["height"] == round(160 * height / width / 2) * 2
    poster, etag = images.read(identifier, "poster.jpg")
    assert poster.startswith(b"\xff\xd8") and etag.startswith('"')
    assert sum(p.stat().st_size for p in images._folder(identifier).glob("[0-9]*.jpg")) <= MAX_BYTES
    assert len(library.list()) == 1
    if width == 320 and gop == 10:
        monkeypatch.setattr("videoenhancer.remote.thumbnails.MAX_BYTES", 1)
        with pytest.raises(ValueError, match="budget"):
            images.generate(identifier)
        assert not images._folder(identifier).with_name(identifier + ".pending").exists()

    orphan = library.folder / ".videoenhancer" / ("a" * 64)
    orphan.mkdir()
    (orphan / "0.jpg").write_bytes(b"orphan")
    images.cleanup()
    assert not orphan.exists()
    library.delete(identifier)
    assert not images._folder(identifier).exists()


def test_black_poster_skips_first_second(tmp_path, ffmpeg_run):
    from videoenhancer import proc
    from videoenhancer.config import executable
    from videoenhancer.remote.library import Library
    from videoenhancer.remote.thumbnails import Thumbnails

    library = Library(tmp_path / "home", tmp_path / "library")
    library.folder.mkdir()
    path = library.folder / "black.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "color=black:s=320x180:r=10:d=1",
        "-f",
        "lavfi",
        "-i",
        "color=white:s=320x180:r=10:d=3",
        "-filter_complex",
        "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        str(path),
    )
    images = Thumbnails(library)
    identifier = library._identifier(path)
    images.generate(identifier)
    pixels = proc.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-i",
            str(images._folder(identifier) / "poster.jpg"),
            "-vf",
            "scale=16:16,format=gray",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    assert sum(pixels) / len(pixels) > 200


def test_background_waits_for_gpu(tmp_path, monkeypatch):
    import threading

    from videoenhancer.remote.library import Library
    from videoenhancer.remote.thumbnails import Thumbnails

    library = Library(tmp_path / "home", tmp_path / "library")
    library.folder.mkdir()
    (library.folder / "clip.mp4").write_bytes(b"synthetic")
    images = Thumbnails(library)
    called = threading.Event()
    monkeypatch.setattr(images, "generate", lambda identifier: called.set())
    images.pause()
    images.thread.start()
    try:
        assert not called.wait(1.2)
        images.resume()
        assert called.wait(3)
    finally:
        images.close()


def test_image_routes_cookie_cache(gateway):
    from test_remote_gateway import pair, request

    images = gateway.thumbnails
    images.pause()
    library = gateway.adapter.library
    library.folder.mkdir(exist_ok=True)
    path = library.folder / "clip.mp4"
    path.write_bytes(b"synthetic")
    identifier = library._identifier(path)
    folder = images._folder(identifier)
    folder.mkdir()
    import json

    (folder / "storyboard.json").write_text(
        json.dumps({"signature": images.signature(path.stat())})
    )
    (folder / "poster.jpg").write_bytes(b"jpeg")
    (folder / "0.jpg").write_bytes(b"sheet")
    cookie = pair(gateway)
    for name in ("poster.jpg", "storyboard.json", "storyboard/0.jpg"):
        route = f"/api/library/{identifier}/{name}"
        assert request(gateway, route)[0] == 401
        status, headers, _ = request(gateway, route, cookie=cookie)
        assert status == 200
        assert headers["Cache-Control"] == "private, max-age=86400"
        assert (
            request(gateway, route, cookie=cookie, headers={"If-None-Match": headers["ETag"]})[0]
            == 304
        )
    assert request(gateway, f"/api/library/{identifier}/storyboard/1.jpg", cookie=cookie)[0] == 404


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    from videoenhancer.remote.gateway import Gateway

    monkeypatch.setattr("videoenhancer.remote.gateway.local_addresses", lambda: ["127.0.0.1"])
    service = Gateway(
        None,
        tmp_path,
        {
            "remote_https_port": 0,
            "remote_setup_port": 0,
            "library_folder": str(tmp_path / "library"),
        },
    )
    service.start()
    yield service
    service.close()


def test_claim_hint_boundary_and_paired_device_list(gateway):
    import json

    from test_remote_gateway import request

    agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/142.0 Safari/537.36"
    gateway.open_pairing()
    for hint in ("<script>", [], "mac"):
        headers = {"User-Agent": "Windows" if hint == "mac" else agent}
        assert (
            request(
                gateway,
                "/api/pair/claim",
                "POST",
                headers=headers,
                body=json.dumps({"platform": hint}),
            )[0]
            == 400
        )
    status, headers, _ = request(
        gateway,
        "/api/pair/claim",
        "POST",
        headers={"User-Agent": agent},
        body=json.dumps({"platform": "mac"}),
    )
    assert status == 200
    cookie = headers["Set-Cookie"].split(";", 1)[0]
    session = json.loads(request(gateway, "/api/session", cookie=cookie)[2])
    assert session["devices"] == [{"label": "Mac, Chrome 142", "created": session["paired_at"]}]
    assert all("secret" not in key for row in session["devices"] for key in row)


def test_idle_engine_boundaries_do_not_cancel_images(tmp_path, monkeypatch):
    import threading
    import time
    from types import SimpleNamespace

    from videoenhancer.service.engine import Engine

    calls = []
    images = SimpleNamespace(
        pause=lambda: calls.append("pause"), resume=lambda: calls.append("resume")
    )
    stop = threading.Event()
    engine = SimpleNamespace(
        stop=stop,
        storage_moving=False,
        _cleanup_checked=time.monotonic(),
        operations={},
        remote_jobs=SimpleNamespace(thumbnails=images, sweep=lambda: None),
        compare_worker=SimpleNamespace(close=lambda: None),
        _auxiliary=lambda: None,
        _progress=lambda *args: None,
        _error=lambda *args: None,
        ignore_schedule=True,
        home=tmp_path,
        paused=False,
    )

    def queue(**kwargs):
        kwargs["between_segments"]()
        kwargs["between_segments"]()
        kwargs["before_segment"]()
        stop.set()

    monkeypatch.setattr("videoenhancer.service.engine.run_queue", queue)
    Engine._worker(engine)
    assert calls == ["resume", "resume", "pause"]
