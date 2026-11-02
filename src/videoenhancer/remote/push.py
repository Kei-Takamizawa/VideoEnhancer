"""Private, Apple-only encrypted Web Push notifications."""

from __future__ import annotations

import base64
import json
import logging
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid02, VapidException
from pywebpush import WebPushException, webpush

from .security import Devices, private_write

SUBJECT = "https://github.com/Kei-Takamizawa/VideoEnhancer"
_REASONS = frozenset(
    {
        "BadDeviceToken",
        "BadExpirationDate",
        "BadPriority",
        "BadTopic",
        "DeviceTokenNotForTopic",
        "DuplicateHeaders",
        "ExpiredProviderToken",
        "Forbidden",
        "IdleTimeout",
        "InternalServerError",
        "InvalidProviderToken",
        "MissingDeviceToken",
        "MissingProviderToken",
        "MissingTopic",
        "PayloadEmpty",
        "PayloadTooLarge",
        "ServiceUnavailable",
        "Shutdown",
        "TooManyProviderTokenUpdates",
        "TooManyRequests",
        "TopicDisallowed",
        "Unregistered",
        "BadJwtToken",
        "BadWebPushRequest",
        "BadTtl",
        "BadUrgency",
        "BadCrypto",
    }
)
_KEY_LOCK = threading.Lock()


def _decode(value: object, size: int) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
        raise ValueError("Invalid notification subscription.")
    try:
        decoded = base64.b64decode(
            value.rstrip("=") + "=" * (-len(value.rstrip("=")) % 4), altchars=b"-_", validate=True
        )
    except ValueError:
        raise ValueError("Invalid notification subscription.") from None
    if len(decoded) != size:
        raise ValueError("Invalid notification subscription.")
    return decoded


def _subscription(value: dict) -> dict:
    try:
        endpoint = value["endpoint"]
        if (
            not isinstance(endpoint, str)
            or len(endpoint) > 4096
            or any(ord(c) <= 32 or ord(c) >= 127 for c in endpoint)
        ):
            raise ValueError
        url = urlsplit(endpoint)
        if (
            url.scheme != "https"
            or url.hostname != "web.push.apple.com"
            or url.port not in (None, 443)
            or url.username is not None
            or url.password is not None
            or url.fragment
            or not url.path.startswith("/")
            or "\\" in endpoint
        ):
            raise ValueError
        keys = value["keys"]
        point = _decode(keys["p256dh"], 65)
        if point[0] != 4:
            raise ValueError
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
        _decode(keys["auth"], 16)
        return {"endpoint": endpoint, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}}
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid notification subscription.") from None


class _Session(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False

    def post(self, url, **kwargs):
        kwargs["allow_redirects"] = False
        return super().post(url, **kwargs)


class Push:
    def __init__(self, home: Path, devices: Devices, logger=None):
        self.devices = devices
        self.logger = logger or logging.getLogger(__name__)
        self.key_path = home / "remote" / "vapid.pem"
        with _KEY_LOCK:
            if not self.key_path.exists():
                key = ec.generate_private_key(ec.SECP256R1())
                private_write(
                    self.key_path,
                    key.private_bytes(
                        serialization.Encoding.PEM,
                        serialization.PrivateFormat.PKCS8,
                        serialization.NoEncryption(),
                    ),
                )
            key = serialization.load_pem_private_key(self.key_path.read_bytes(), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
            key.curve, ec.SECP256R1
        ):
            raise ValueError("Invalid notification signing key.")
        point = key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.public_key = base64.urlsafe_b64encode(point).decode().rstrip("=")
        # py_vapid strict mode only accepts mailto subjects, although RFC 8292 allows HTTPS.
        self.vapid = Vapid02(private_key=key, conf={"no-strict": True})

    def _save(self, device_id: str, subscription: dict | None) -> None:
        with self.devices.lock:
            updated = [dict(device) for device in self.devices.devices]
            for device in updated:
                if device["id"] == device_id:
                    if subscription is None:
                        device.pop("push_subscription", None)
                    else:
                        device["push_subscription"] = subscription
                    self.devices._save("devices.json", updated)
                    self.devices.devices = updated
                    return
            raise ValueError("Device is not paired.")

    def subscribe(self, device_id: str, subscription: dict) -> dict:
        self._save(device_id, _subscription(subscription))
        return {"ok": True}

    def subscribed(self, device_id: str) -> bool:
        with self.devices.lock:
            return any(
                d["id"] == device_id and d.get("push_subscription") for d in self.devices.devices
            )

    def _send(self, device_id: str, payload: dict) -> dict:
        with self.devices.lock:
            subscription = next(
                (d.get("push_subscription") for d in self.devices.devices if d["id"] == device_id),
                None,
            )
        if subscription is None:
            return {"ok": False, "status": None}
        response = None
        try:
            subscription = _subscription(subscription)
            with _Session() as session:
                response = webpush(
                    subscription,
                    data=json.dumps(payload),
                    vapid_private_key=self.vapid,
                    vapid_claims={"sub": SUBJECT},
                    timeout=15,
                    ttl=3600,
                    requests_session=session,
                )
        except WebPushException as exc:
            response = exc.response
        except (requests.RequestException, ValueError, OSError, VapidException):
            pass
        status = getattr(response, "status_code", None)
        reason = "unknown"
        if response is not None and not isinstance(response, str):
            try:
                candidate = response.json().get("reason")
                if isinstance(candidate, str) and candidate in _REASONS:
                    reason = candidate
            except (ValueError, AttributeError):
                pass
        self.logger.info("push status=%s reason=%s", status, reason)
        if status in (404, 410):
            with self.devices.lock:
                current = next(
                    (
                        d.get("push_subscription")
                        for d in self.devices.devices
                        if d["id"] == device_id
                    ),
                    None,
                )
                if current == subscription:
                    self._save(device_id, None)
        return {"ok": status is not None and 200 <= status < 300, "status": status}

    def test(self, device_id: str) -> dict:
        return self._send(
            device_id,
            {
                "title": "Notifications are on",
                "body": "You'll hear when a video is ready.",
                "url": "/",
            },
        )

    def finished(self, device_id: str, title: str, outcome: str, item_id=None) -> dict:
        if outcome == "cancelled":
            return {"ok": False, "status": None}
        # Bounded plain text; processing exceptions never become notification text.
        title = " ".join(str(title).split())[:120]
        if outcome == "done":
            identifier = str(item_id or "")
            url = (
                f"/#item={identifier}" if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier) else "/"
            )
            payload = {"title": "Ready", "body": f"{title} is in your library.", "url": url}
        else:
            payload = {
                "title": "Couldn't finish",
                "body": f"{title}: The video could not be processed. Please try again.",
                "url": "/",
            }
        return self._send(device_id, payload)
