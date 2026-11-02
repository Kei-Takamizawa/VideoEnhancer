import asyncio
import hashlib
import json
from datetime import timedelta

import pytest
from aiohttp import CookieJar
from aiohttp.test_utils import TestClient, TestServer
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

from server import State, certificates, make_app, token_hash


def test_certificate(tmp_path):
    certificates(tmp_path, ["videoenhancer.local", "testpc.local"], ["192.168.1.21"])
    root = x509.load_pem_x509_certificate((tmp_path / "ca.crt").read_bytes())
    cert = x509.load_pem_x509_certificate((tmp_path / "server.crt").read_bytes())
    cert.verify_directly_issued_by(root)
    assert cert.not_valid_after_utc - cert.not_valid_before_utc <= timedelta(days=398)
    assert cert.signature_hash_algorithm.name == "sha256"
    assert cert.public_key().key_size >= 2048
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert san.get_values_for_type(x509.DNSName) == ["videoenhancer.local", "testpc.local"]
    assert str(san.get_values_for_type(x509.IPAddress)[0]) == "192.168.1.21"
    assert cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value == x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH])
    assert cert.extensions.get_extension_for_class(x509.KeyUsage).value.digital_signature
    assert root.extensions.get_extension_for_class(x509.BasicConstraints).value.ca


def test_pairing_lifecycle(tmp_path):
    now = [100.0]
    state = State(tmp_path, tmp_path / "results.jsonl", ["localhost"], clock=lambda: now[0])
    assert state.claim() is None
    state.open_pairing(120)
    secret = state.claim()
    assert secret and state.claim() is None
    token = state.finish(secret)
    assert token and state.finish(secret) is None
    assert state.authorized(token)
    assert not state.authorized("wrong")
    assert token not in (tmp_path / "device.json").read_text()
    assert json.loads((tmp_path / "device.json").read_text())["token_hash"] == token_hash(token)
    state.open_pairing(120)
    now[0] += 120
    assert state.claim() is None
    state.open_pairing(120)
    secret = state.claim()
    now[0] += 1800
    assert state.finish(secret) is None
    state.open_pairing(120)
    token2 = state.finish(state.claim())
    assert state.authorized(token2) and not state.authorized(token)
    restored = State(tmp_path, tmp_path / "results.jsonl", ["localhost"])
    assert restored.authorized(token2)


def test_claim_survives_restart(tmp_path):
    first = State(tmp_path, tmp_path / "results.jsonl", ["localhost"])
    first.open_pairing(120)
    secret = first.claim()
    assert first.device_file.exists()
    restarted = State(tmp_path, tmp_path / "results.jsonl", ["localhost"])
    assert restarted.claim() is None
    assert restarted.finish(secret)
    assert restarted.finish(secret) is None


@pytest.fixture
async def client(tmp_path):
    state = State(tmp_path, tmp_path / "results.jsonl", ["127.0.0.1", "localhost"])
    state.open_pairing(120)
    token = state.finish(state.claim())
    app = make_app(state)
    async with TestClient(TestServer(app), cookie_jar=CookieJar(unsafe=True)) as client:
        client.session.headers["Authorization"] = "Bearer " + token
        yield client, state


@pytest.mark.asyncio
async def test_guards(client):
    c, state = client
    assert (await c.get("/api/config")).status == 200
    assert (await c.get("/api/config", headers={"Host": "attacker.example"})).status == 403
    assert (await c.post("/api/results", json={}, headers={"Origin": "https://attacker.example"})).status == 403
    assert (await c.post("/api/results", json={}, headers={"Origin": "http://localhost:8080"})).status == 403
    c.session.headers.clear()
    for path in ["/api/config", "/media/h264.mp4", "/api/events", "/api/upload/" + "a" * 64]:
        assert (await c.get(path)).status == 401
    assert (await c.get("/")).status == 200
    assert (await c.get("/pair/finish")).status == 200


@pytest.mark.asyncio
async def test_http_surface_and_pair_race(tmp_path):
    state = State(tmp_path, tmp_path / "r.jsonl", ["127.0.0.1"])
    state.open_pairing(120)
    async with TestClient(TestServer(make_app(state, plain=True))) as c:
        results = await asyncio.gather(c.get("/pair"), c.get("/pair"))
        pages = [await r.text() for r in results]
        assert sum("pair/finish#" in p for p in pages) == 1
        assert sum("Pairing is closed" in p for p in pages) == 1
        for path in ["/", "/api/config", "/media/h264.mp4", "/pair/finish"]:
            assert (await c.get(path)).status == 404


@pytest.mark.asyncio
async def test_finish_cookie(client):
    c, state = client
    state.open_pairing(120)
    secret = state.claim()
    c.session.headers.clear()
    response = await c.post("/api/pair/finish", json={"secret": secret})
    assert response.status == 200
    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert (await c.post("/api/pair/finish", json={"secret": secret})).status == 403


@pytest.mark.asyncio
async def test_upload_resume_hash(client):
    c, state = client
    data = b"synthetic video" * 1000
    digest = hashlib.sha256(data).hexdigest()
    path = "/api/upload/" + digest
    assert (await (await c.get(path)).json())["offset"] == 0
    assert (await c.put(path + "?offset=0", data=data[:1000])).status == 200
    assert (await (await c.get(path)).json())["offset"] == 1000
    assert (await c.put(path + "?offset=0", data=data)).status == 409
    assert (await c.put(path + "?offset=1000", data=data[1000:])).status == 200
    response = await c.post(path + "/finish", json={"size": len(data)})
    assert response.status == 200
    assert (await response.json())["sha256"] == digest
    assert (state.home / "uploads" / digest).read_bytes() == data
    assert (await c.post(path + "/finish", json={"size": len(data) + 1})).status == 409
    bad = "/api/upload/" + "0" * 64
    await c.put(bad + "?offset=0", data=b"wrong")
    assert (await c.post(bad + "/finish", json={"size": 5})).status == 422
    assert (await c.put("/api/upload/invalid?offset=0", data=b"x")).status == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("range_header,status,body,content_range", [
    (None, 200, b"0123456789", None),
    ("bytes=2-5", 206, b"2345", "bytes 2-5/10"),
    ("bytes=6-", 206, b"6789", "bytes 6-9/10"),
    ("bytes=-3", 206, b"789", "bytes 7-9/10"),
    ("bytes=0-999", 206, b"0123456789", "bytes 0-9/10"),
    ("bytes=20-", 416, b"", "bytes */10"),
    ("bytes=4-2", 416, b"", "bytes */10"),
    ("bytes=0-1,3-4", 416, b"", "bytes */10"),
])
async def test_ranges(client, range_header, status, body, content_range):
    c, state = client
    (state.home / "media" / "h264.mp4").write_bytes(b"0123456789")
    headers = {"Range": range_header} if range_header else {}
    response = await c.get("/media/h264.mp4", headers=headers)
    assert response.status == status
    assert await response.read() == body
    assert response.headers.get("Content-Range") == content_range
    assert response.headers["Accept-Ranges"] == "bytes"


@pytest.mark.asyncio
async def test_results(client):
    c, state = client
    assert (await c.post("/api/results", json={"test": "T1", "pass": True})).status == 200
    record = json.loads(state.evidence.read_text())
    assert record["test"] == "T1" and record["timestamp"] and record["user_agent"]


@pytest.mark.asyncio
async def test_download_measurement(client):
    c, state = client
    (state.home / "media" / "1GB.mp4").write_bytes(b"synthetic")
    response = await c.get("/media/1GB.mp4?download=1&run=pc-test")
    assert await response.read() == b"synthetic"
    assert "attachment" in response.headers["Content-Disposition"]
    result = json.loads(state.evidence.read_text())
    assert result["test"] == "T6" and result["bytes"] == 9
    assert result["complete"] and result["MB_s"] > 0

