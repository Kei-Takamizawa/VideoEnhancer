"""Manual poster API, persistence and obsolete model cleanup."""

import json
import logging

import pytest
from test_remote_gateway import gateway as gateway_fixture
from test_remote_gateway import pair, request


@pytest.fixture
def poster_gateway(tmp_path, monkeypatch):
    yield from gateway_fixture.__wrapped__(tmp_path, monkeypatch)


def test_manual_poster_api(poster_gateway, ffmpeg_run, monkeypatch):
    gateway = poster_gateway
    images = gateway.thumbnails
    images.pause()
    images.busy.clear()
    library = gateway.adapter.library
    library.folder.mkdir(exist_ok=True)
    path = library.folder / "clip.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=96x64:rate=10:duration=2",
        "-c:v",
        "libx264",
        "-threads",
        "1",
        str(path),
    )
    identifier = library._identifier(path)
    images.generate(identifier)
    old = images.read(identifier, "poster.jpg")[1]
    route = f"/api/library/{identifier}/poster"
    assert request(gateway, route, "POST", body='{"time":1}')[0] == 401
    cookie = pair(gateway)
    assert request(gateway, route, "POST", cookie=cookie, origin=False, body='{"time":1}')[0] == 403
    assert (
        request(gateway, route, "POST", cookie=cookie, host="evil.invalid", body='{"time":1}')[0]
        == 421
    )
    for value in (-1, 3, None, True, "1", float("nan"), float("inf")):
        assert (
            request(gateway, route, "POST", cookie=cookie, body=json.dumps({"time": value}))[0]
            == 400
        )
    for body in ("[]", "{}", "{"):
        assert request(gateway, route, "POST", cookie=cookie, body=body)[0] == 400
    status, _, body = request(gateway, route, "POST", cookie=cookie, body='{"time":1.2}')
    assert status == 200
    folder = images._folder(identifier)
    manual = (folder / "poster.jpg").read_bytes()
    assert json.loads((folder / "poster.json").read_text()) == {"source": "manual", "time": 1.2}
    assert images.read(identifier, "poster.jpg")[1] != old
    assert json.loads(body)["etag"] == images.read(identifier, "poster.jpg")[1]
    monkeypatch.setattr("videoenhancer.remote.thumbnails.VERSION", 999)
    images.generate(identifier)
    assert (folder / "poster.jpg").read_bytes() == manual
    assert json.loads((folder / "poster.json").read_text())["source"] == "manual"
    for position in (0, 2):
        assert (
            request(gateway, route, "POST", cookie=cookie, body=json.dumps({"time": position}))[0]
            == 200
        )


def test_start_removes_only_face_models(tmp_path, monkeypatch, caplog):
    from videoenhancer.remote.gateway import Gateway

    monkeypatch.setattr("videoenhancer.remote.gateway.local_addresses", lambda: ["127.0.0.1"])
    face = tmp_path / "models" / "face"
    face.mkdir(parents=True)
    (face / "obsolete.onnx").write_bytes(b"synthetic")
    keep = face.parent / "keep.onnx"
    keep.write_bytes(b"keep")
    service = Gateway(None, tmp_path, {"remote_https_port": 0, "remote_setup_port": 0})
    try:
        with caplog.at_level(logging.INFO, logger="videoenhancer.remote"):
            service.start()
        assert not face.exists()
        assert keep.read_bytes() == b"keep"
        assert caplog.text.count("Removed obsolete face models.") == 1
    finally:
        service.close()
