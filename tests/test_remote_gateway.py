"""Real HTTPS requests exercising the remote trust and authentication boundaries."""

import hashlib
import http.client
import json
import logging
import socket
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from videoenhancer.remote.gateway import Gateway, LANServer
from videoenhancer.remote.security import Devices


@pytest.fixture
def gateway(tmp_path, monkeypatch):
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


def request(
    gateway,
    path,
    method="GET",
    *,
    cookie=None,
    origin=True,
    host=None,
    secure=True,
    headers=None,
    body=None,
):
    port = gateway.https_port if secure else gateway.setup_port
    if secure:
        context = ssl.create_default_context(cafile=str(gateway.home / "remote" / "ca.crt"))
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=10)
    else:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    values = dict(headers or {})
    values["Host"] = host or f"127.0.0.1:{port}"
    if origin:
        values["Origin"] = f"https://127.0.0.1:{port}" if origin is True else origin
    if cookie:
        values["Cookie"] = cookie
    conn.request(method, path, body=body, headers=values)
    response = conn.getresponse()
    body = response.read()
    result = response.status, dict(response.getheaders()), body
    conn.close()
    return result


def pair(gateway):
    gateway.open_pairing()
    status, headers, _ = request(gateway, "/api/pair/claim", "POST")
    assert status == 200
    return headers["Set-Cookie"].split(";", 1)[0]


def test_unauthenticated_upload_body_reliably_returns_status(gateway):
    path = "/api/uploads/" + "a" * 32 + "/chunk?offset=0"
    for _ in range(50):
        assert request(gateway, path, "PUT", body=b"x" * 32000)[0] == 401
    assert request(gateway, path, "PUT", body=b"x" * 65537)[0] == 413


def test_gateway_start_expires_abandoned_uploads(tmp_path, monkeypatch):
    from videoenhancer.remote.uploads import Uploads

    monkeypatch.setattr("videoenhancer.remote.gateway.local_addresses", lambda: ["127.0.0.1"])
    uploads = Uploads(tmp_path / "remote/incoming", clock=lambda: 0)
    identifier = uploads.create("d", "clip.mp4", 1)["id"]
    gateway = Gateway(None, tmp_path, {"remote_https_port": 0, "remote_setup_port": 0})
    gateway.adapter.uploads.clock = lambda: 86400
    try:
        gateway.start()
        assert not (uploads.folder / identifier).exists()
    finally:
        gateway.close()


def test_authenticated_streamed_upload_resume_and_body_limits(gateway, monkeypatch):
    monkeypatch.setattr(
        gateway.adapter.uploads, "probe", lambda _: {"width": 1920, "height": 1080, "duration": 1}
    )
    value = json.dumps({"name": "Private title.mp4", "size": 6})
    assert request(gateway, "/api/uploads", "POST", body=value)[0] == 401
    cookie = pair(gateway)
    status, _, body = request(gateway, "/api/uploads", "POST", cookie=cookie, body=value)
    assert status == 200
    identifier = json.loads(body)["id"]
    path = f"/api/uploads/{identifier}"
    assert request(gateway, path + "/chunk?offset=0", "PUT", cookie=cookie, body=b"abc")[0] == 200
    assert json.loads(request(gateway, path, cookie=cookie)[2])["offset"] == 3
    assert request(gateway, path + "/chunk?offset=0", "PUT", cookie=cookie, body=b"abc")[0] == 400
    assert request(gateway, path + "/chunk?offset=3", "PUT", cookie=cookie, body=b"def")[0] == 200
    status, _, body = request(
        gateway,
        path + "/finish",
        "POST",
        cookie=cookie,
        body=json.dumps({"sha256": hashlib.sha256(b"abcdef").hexdigest()}),
    )
    assert status == 200 and json.loads(body)["ready"]
    assert request(gateway, "/api/uploads", "POST", cookie=cookie, body=b" " * 65537)[0] == 413
    assert request(gateway, path + "/chunk?offset=0", "PUT", body=b"x")[0] == 401


def test_pairing_single_claim_secret_hash_cookie_and_session(gateway):
    assert json.loads(request(gateway, "/api/session")[2]) == {
        "paired": False,
        "pairing_open": False,
    }
    gateway.open_pairing()
    status, headers, _ = request(
        gateway, "/api/pair/claim", "POST", headers={"User-Agent": "iPad Version/27.0 Safari/605"}
    )
    assert status == 200
    cookie = headers["Set-Cookie"]
    for value in ("HttpOnly", "Secure", "SameSite=Strict", "Path=/", "Max-Age=34560000"):
        assert value in cookie
    secret = cookie.split(";", 1)[0].split("=", 1)[1]
    saved = (gateway.home / "remote" / "devices.json").read_text()
    assert secret not in saved
    assert hashlib.sha256(secret.encode()).hexdigest() in saved
    assert not gateway.devices.pairing_open
    assert request(gateway, "/api/pair/claim", "POST")[0] == 409
    session = json.loads(request(gateway, "/api/session", cookie=cookie)[2])
    assert session["paired"] and session["device_label"] == "iPad, Safari 27"
    gateway.open_pairing()
    assert json.loads(request(gateway, "/api/session", cookie=cookie)[2])["paired"]


def test_pairing_deadline_rate_limit_and_concurrency(tmp_path):
    clock = [1000]
    devices = Devices(tmp_path, clock=lambda: clock[0])
    devices.open_pairing()
    clock[0] += 120
    assert devices.claim("192.168.1.1", "iPad")[0] == 409
    devices.open_pairing()
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(devices.claim("192.168.1.2", "iPad")))
        for _ in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(status for status, _ in results) == [200, 409, 409, 409, 409, 429]
    clock[0] += 60
    devices.open_pairing()
    assert devices.claim("192.168.1.2", "iPad")[0] == 200
    assert len(Devices(tmp_path).devices) == 2


@pytest.mark.parametrize(
    "route,method",
    [
        ("/api/library", "GET"),
        ("/api/storage", "GET"),
        ("/api/library/abc/video", "GET"),
        ("/api/library/abc", "DELETE"),
        ("/api/library/abc/download-link", "POST"),
        ("/api/client-event", "POST"),
    ],
)
@pytest.mark.parametrize("cookie", [None, "ve_device=wrong"])
def test_all_protected_routes_reject_bad_cookie(gateway, route, method, cookie):
    assert request(gateway, route, method, cookie=cookie)[0] == 401


def test_host_origin_and_security_headers(gateway):
    assert request(gateway, "/api/session", host="evil.invalid:8443")[0] == 421
    assert request(gateway, "/api/session", host="127.0.0.1:1")[0] == 421
    gateway.open_pairing()
    for method, route in (("POST", "/api/pair/claim"), ("DELETE", "/api/library/abc")):
        for origin in (False, "https://evil.invalid"):
            assert request(gateway, route, method, origin=origin)[0] == 403
    _, headers, _ = request(gateway, "/api/session")
    assert headers["Cache-Control"] == "no-store"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "'unsafe-inline'" not in headers["Content-Security-Policy"]


def test_http_is_setup_only_and_never_sets_cookie(gateway):
    for path in ("/", "/ca.mobileconfig", "/ca.cer"):
        status, headers, body = request(gateway, path, secure=False)
        assert status == 200
        if path == "/":
            assert b"Redo pairing" in body and b"Certificate Trust Settings" in body
        assert "Set-Cookie" not in headers
    gateway.open_pairing()
    status, _, body = request(gateway, "/", secure=False)
    assert status == 200
    assert b"Certificate Trust Settings" in body
    assert request(gateway, "/ca.mobileconfig", secure=False)[0] == 200
    assert request(gateway, "/ca.cer", secure=False)[0] == 200
    for path in ("/api/session", "/api/library", "/app.mjs"):
        assert request(gateway, path, secure=False)[0] == 404
    assert request(gateway, "/api/pair/claim", "POST", secure=False)[0] == 404


def test_stalled_tls_client_does_not_delay_next_request(gateway):
    import time

    with socket.create_connection(("127.0.0.1", gateway.https_port), timeout=5):
        started = time.monotonic()
        assert request(gateway, "/api/session")[0] == 200
        assert time.monotonic() - started < 1


def test_client_events_are_authenticated_bounded_and_never_log_names(gateway, caplog):
    cookie = pair(gateway)
    event = {
        "kind": "share_failure",
        "error_name": "NotAllowedError",
        "error_message": "Failed to share private-video.mp4",
        "size_bytes": 123,
        "can_share": False,
        "phase": "share",
        "filename": "private-video.mp4",
    }
    body = json.dumps(event)
    assert request(gateway, "/api/client-event", "POST", body=body)[0] == 401
    assert (
        request(gateway, "/api/client-event", "POST", cookie=cookie, origin=False, body=body)[0]
        == 403
    )
    assert request(gateway, "/api/client-event", "POST", cookie=cookie, body="x" * 2049)[0] == 413
    with caplog.at_level(logging.INFO, logger="videoenhancer.remote"):
        assert request(gateway, "/api/client-event", "POST", cookie=cookie, body=body)[0] == 200
    assert "NotAllowedError" in caplog.text
    assert "private-video" not in caplog.text
    assert request(gateway, "/api/client-event", "POST", cookie=cookie, body="[]")[0] == 400


def test_download_tokens_ranges_expiry_hashes_and_log_redaction(gateway, caplog, monkeypatch):
    from urllib.parse import urlsplit

    cookie = pair(gateway)
    folder = gateway.home / "library"
    folder.mkdir()
    (folder / "日本語.mp4").write_bytes(b"0123456789")
    identifier = gateway.adapter.library.list()[0]["id"]
    route = f"/api/library/{identifier}/download-link"
    assert request(gateway, route, "POST")[0] == 401
    assert request(gateway, route, "POST", cookie=cookie, origin=False)[0] == 403
    status, _, body = request(gateway, route, "POST", cookie=cookie)
    assert status == 200
    url = json.loads(body)["url"]
    path = urlsplit(url).path
    token = path.split("/")[-1]
    assert len(bytes.fromhex(token)) == 32
    assert token not in repr(gateway.downloads)
    assert hashlib.sha256(token.encode()).hexdigest() in gateway.downloads
    with caplog.at_level(logging.INFO, logger="videoenhancer.remote"):
        assert request(gateway, path, "HEAD")[0] == 200
        status, headers, data = request(gateway, path, headers={"Range": "bytes=0-3"})
        assert status == 206 and data == b"0123"
        assert "filename*=UTF-8''%E6%97%A5%E6%9C%AC%E8%AA%9E.mp4" in headers["Content-Disposition"]
        assert request(gateway, path, headers={"Range": "bytes=4-"})[2] == b"456789"
        assert request(gateway, path)[0] == 404
    assert token not in caplog.text and "GET /dl/{token}" in caplog.text
    new_path = urlsplit(json.loads(request(gateway, route, "POST", cookie=cookie)[2])["url"]).path
    monkeypatch.setattr("videoenhancer.remote.gateway.time.monotonic", lambda: 10**12)
    assert request(gateway, new_path)[0] == 404


@pytest.mark.parametrize("path", ["/apple-touch-icon-precomposed.png", "/favicon.ico"])
def test_icon_probes_do_not_return_404(gateway, path):
    assert request(gateway, path)[0] in {200, 204}


def test_unsupported_method_keeps_security_headers_without_echo(gateway):
    status, headers, body = request(gateway, "/secret-input", "TRACE")
    assert status == 501
    assert "secret-input" not in body.decode()
    assert headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_logs_have_only_method_template_status_duration(gateway, caplog, monkeypatch):
    logged = threading.Event()
    original = gateway.logger.info

    def record(*args, **kwargs):
        original(*args, **kwargs)
        logged.set()

    monkeypatch.setattr(gateway.logger, "info", record)
    with caplog.at_level(logging.INFO, logger="videoenhancer.remote"):
        request(
            gateway,
            "/api/library/private-name.mp4/video?secret=private-secret",
            cookie="ve_device=private-cookie",
        )
        assert logged.wait(2), "The completed request did not produce an access log."
    message = caplog.records[-1].getMessage()
    assert message.startswith("GET /api/library/{id}/video 401 ")
    assert all(
        value not in message for value in ("private-name", "private-secret", "private-cookie", "?")
    )


def test_source_is_closed_before_tls_or_http_response():
    class Connection:
        closed = False

        def close(self):
            self.closed = True

        def settimeout(self, _value):
            pass

    rejected, accepted = Connection(), Connection()

    class Socket:
        pending = iter([(rejected, ("8.8.8.8", 1)), (accepted, ("192.168.1.1", 1))])

        def accept(self):
            return next(self.pending)

    server = LANServer.__new__(LANServer)
    server.socket = Socket()
    server.context = None
    with pytest.raises(OSError, match="Source address"):
        server.get_request()
    connection, address = server.get_request()
    assert rejected.closed and not accepted.closed
    assert connection is accepted and address[0] == "192.168.1.1"


def test_failed_tls_handshake_does_not_block_shutdown(gateway):
    with socket.create_connection(("127.0.0.1", gateway.https_port), timeout=5) as connection:
        connection.sendall(b"not a TLS handshake\r\n")
        try:
            assert connection.recv(1) == b""
        except ConnectionResetError:
            # Windows can reset a rejected TLS socket instead of returning EOF.
            pass
    stopped = threading.Event()

    def close():
        gateway.close()
        stopped.set()

    thread = threading.Thread(target=close, daemon=True)
    thread.start()
    assert stopped.wait(5), "A rejected TLS handshake blocked gateway shutdown"
    thread.join(timeout=5)


def test_concurrent_first_requests_share_one_library(tmp_path, monkeypatch):
    from videoenhancer.remote.adapter import EngineAdapter

    ready = threading.Barrier(9)
    constructing = threading.Event()
    release = threading.Event()
    calls = []

    class Library:
        def __init__(self, home, folder):
            calls.append(self)
            constructing.set()
            assert release.wait(5)

    monkeypatch.setattr("videoenhancer.remote.library.Library", Library)
    adapter = EngineAdapter(None, tmp_path, {"library_folder": str(tmp_path / "library")})

    def first_request():
        ready.wait(timeout=5)
        return adapter.library

    with ThreadPoolExecutor(max_workers=8) as executor:
        requests = [executor.submit(first_request) for _ in range(8)]
        ready.wait(timeout=5)
        assert constructing.wait(5)
        # Give the simultaneous requests time to contend while construction is blocked.
        threading.Event().wait(0.1)
        release.set()
        libraries = [request.result(timeout=5) for request in requests]
    assert len(calls) == 1
    assert all(library is libraries[0] for library in libraries)


def test_delete_while_stream_active_and_after_release(gateway):
    cookie = pair(gateway)
    folder = gateway.home / "library"
    folder.mkdir()
    (folder / "sample.mp4").write_bytes(b"synthetic")
    library = gateway.adapter.library
    identifier = library.list()[0]["id"]
    with library.acquire(identifier):
        status, _, body = request(gateway, f"/api/library/{identifier}", "DELETE", cookie=cookie)
        assert status == 409 and b"in use" in body
    assert request(gateway, f"/api/library/{identifier}", "DELETE", cookie=cookie)[0] == 200
    assert library.list() == []


@pytest.mark.parametrize(
    "range_header,expected,body",
    [
        ("bytes=0-0", 206, b"0"),
        ("bytes=3-5", 206, b"345"),
        ("bytes=-2", 206, b"89"),
        ("bytes=99-", 416, b""),
        ("bytes=0-1,3-4", 416, b""),
        (None, 200, b"0123456789"),
    ],
)
def test_real_range_streams(gateway, range_header, expected, body):
    cookie = pair(gateway)
    folder = gateway.home / "library"
    folder.mkdir()
    (folder / "sample.mp4").write_bytes(b"0123456789")
    library = gateway.adapter.library
    item = library.list()[0]
    status, headers, actual = request(
        gateway,
        f"/api/library/{item['id']}/video",
        cookie=cookie,
        headers={"Range": range_header} if range_header else {},
    )
    assert status == expected
    assert actual == body
    assert headers["Accept-Ranges"] == "bytes"
    assert int(headers["Content-Length"]) == len(body)
    assert headers["Content-Type"] == "video/mp4" if status != 416 else True
