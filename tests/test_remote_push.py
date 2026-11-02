"""Web Push tests; no request reaches a network service."""

import base64
import json
import logging
import time

import http_ece
import pytest
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from videoenhancer.remote.push import SUBJECT, Push
from videoenhancer.remote.security import Devices


def encoded(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def decoded(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@pytest.fixture
def setup_push(tmp_path, monkeypatch):
    # ACL subprocesses are covered by security tests, not by these crypto tests.
    monkeypatch.setattr(
        "videoenhancer.remote.push.private_write",
        lambda p, d: (p.parent.mkdir(parents=True, exist_ok=True), p.write_bytes(d)),
    )
    devices = Devices(tmp_path / "remote")
    devices.devices = [{"id": "ipad"}]
    monkeypatch.setattr(
        devices,
        "_save",
        lambda n, v: (
            devices.home.mkdir(parents=True, exist_ok=True),
            (devices.home / n).write_text(json.dumps(v)),
        ),
    )
    push = Push(tmp_path, devices)
    key = ec.generate_private_key(ec.SECP256R1())
    auth = b"a" * 16
    subscription = {
        "endpoint": "https://web.push.apple.com/secret-endpoint",
        "keys": {
            "p256dh": encoded(
                key.public_key().public_bytes(
                    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
                )
            ),
            "auth": encoded(auth),
        },
    }
    push.subscribe("ipad", subscription)
    sent = []

    def post(session, url, **kwargs):
        sent.append((url, kwargs))
        response = requests.Response()
        response.status_code = 201
        response._content = b"{}"
        return response

    monkeypatch.setattr(requests.Session, "post", post)
    return push, devices, subscription, key, auth, sent


def test_encryption_jwt_persistence(setup_push, tmp_path):
    push, devices, subscription, key, auth, sent = setup_push
    original = push.key_path.read_bytes()
    assert Push(tmp_path, devices).public_key == push.public_key
    assert push.key_path.read_bytes() == original
    assert push.finished("ipad", "Sample", "done", "abc123") == {"ok": True, "status": 201}
    url, request = sent[0]
    assert url == subscription["endpoint"]
    assert request["allow_redirects"] is False
    plaintext = http_ece.decrypt(
        request["data"], private_key=key, auth_secret=auth, version="aes128gcm"
    )
    assert json.loads(plaintext) == {
        "title": "Ready",
        "body": "Sample is in your library.",
        "url": "/#item=abc123",
    }
    authorization = request["headers"]["Authorization"]
    token = authorization.split("t=", 1)[1].split(",", 1)[0]
    header, claims, signature = token.split(".")
    assert json.loads(decoded(header))["alg"] == "ES256"
    claims_value = json.loads(decoded(claims))
    assert claims_value["aud"] == "https://web.push.apple.com"
    assert claims_value["sub"] == SUBJECT
    assert time.time() < claims_value["exp"] <= time.time() + 86400
    public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decoded(push.public_key))
    signature = decoded(signature)
    public.verify(
        encode_dss_signature(
            int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
        ),
        f"{header}.{claims}".encode(),
        ec.ECDSA(hashes.SHA256()),
    )
    assert Devices(devices.home).devices[0]["push_subscription"] == subscription


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://web.push.apple.com/x",
        "https://127.0.0.1/x",
        "https://web.push.apple.com.evil.test/x",
        "https://u@web.push.apple.com/x",
        "https://web.push.apple.com:444/x",
        "https://web.push.apple.com/x#fragment",
        "https://web.push.apple.com\\evil/x",
        "https://web.push.apple.com/\nx",
    ],
)
def test_reject_endpoints(setup_push, endpoint):
    push, _, subscription, _, _, sent = setup_push
    with pytest.raises(ValueError, match="Invalid notification"):
        push.subscribe("ipad", {**subscription, "endpoint": endpoint})
    assert not sent


@pytest.mark.parametrize(
    "field,value",
    [
        ("auth", "bad"),
        ("p256dh", encoded(b"\x04" + b"\x00" * 64)),
        ("auth", "+" * 22),
        ("p256dh", "x" * 87),
    ],
)
def test_reject_keys(setup_push, field, value):
    push, _, subscription, _, _, _ = setup_push
    subscription["keys"][field] = value
    with pytest.raises(ValueError):
        push.subscribe("ipad", subscription)


@pytest.mark.parametrize("status", [404, 410])
def test_drop_and_safe_log(setup_push, monkeypatch, caplog, status):
    push, devices, subscription, _, _, _ = setup_push

    def post(session, url, **kwargs):
        assert session.trust_env is False
        response = requests.Response()
        response.status_code = status
        response._content = b'{"reason":"Unregistered","secret":"private"}'
        return response

    monkeypatch.setattr(requests.Session, "post", post)
    with caplog.at_level(logging.INFO):
        assert push.test("ipad") == {"ok": False, "status": status}
    assert not push.subscribed("ipad")
    assert "push_subscription" not in Devices(devices.home).devices[0]
    assert f"status={status} reason=Unregistered" in caplog.text
    assert subscription["endpoint"] not in caplog.text
    assert "private" not in caplog.text


def test_failure_cancel_and_unknown_reason(setup_push, monkeypatch, caplog):
    push, _, _, key, auth, sent = setup_push
    assert push.finished("ipad", "Sample", "cancelled")["ok"] is False
    assert not sent
    push.finished("ipad", "Sample", "failed")
    payload = json.loads(
        http_ece.decrypt(sent[0][1]["data"], private_key=key, auth_secret=auth, version="aes128gcm")
    )
    assert payload == {
        "title": "Couldn't finish",
        "body": "Sample: The video could not be processed. Please try again.",
        "url": "/",
    }

    def post(session, url, **kwargs):
        response = requests.Response()
        response.status_code = 307
        response._content = b'{"reason":"https://secret.example/private"}'
        return response

    monkeypatch.setattr(requests.Session, "post", post)
    with caplog.at_level(logging.INFO):
        assert push.test("ipad")["ok"] is False
    assert "reason=unknown" in caplog.text
    assert "secret.example" not in caplog.text
    assert push.subscribed("ipad")


def test_network_error_never_leaks(setup_push, monkeypatch, caplog):
    push, _, _, _, _, _ = setup_push

    def post(session, url, **kwargs):
        raise requests.ConnectionError("secret endpoint and encrypted content")

    monkeypatch.setattr(requests.Session, "post", post)
    with caplog.at_level(logging.INFO):
        assert push.test("ipad") == {"ok": False, "status": None}
    assert "secret" not in caplog.text
    assert push.subscribed("ipad")


def test_unpaired_and_missing_subscription(setup_push):
    push, _, subscription, _, _, sent = setup_push
    with pytest.raises(ValueError, match="Device is not paired"):
        push.subscribe("other", subscription)
    assert not push.subscribed("other")
    assert push.test("other") == {"ok": False, "status": None}
    assert not sent
