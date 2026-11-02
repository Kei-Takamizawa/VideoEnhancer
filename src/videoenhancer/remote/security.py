"""User-private persistence, explicit IPv4 allowlist and device pairing."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from typing import Any

from videoenhancer import proc

NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "127.0.0.0/8")
)


def private_ipv4(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
        return isinstance(address, ipaddress.IPv4Address) and any(
            address in net for net in NETWORKS
        )
    except ValueError:
        return False


def private_write(path: Path, data: bytes) -> None:
    """Protect a fresh temporary file before writing any secret, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.touch(mode=0o600, exist_ok=False)
    try:
        if os.name == "nt":
            import csv
            import io

            identity = proc.run(
                ["whoami", "/user", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
                timeout=5,
            )
            sid = next(csv.reader(io.StringIO(identity.stdout)))[1]
            proc.run(
                ["icacls", str(temporary), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
                capture_output=True,
                check=True,
                timeout=5,
            )
        else:
            temporary.chmod(0o600)
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def cookie_secret(header: str | None) -> str:
    cookie = SimpleCookie()
    try:
        cookie.load(header or "")
        value = cookie.get("ve_device")
        return value.value if value else ""
    except CookieError:
        return ""


def device_label(agent: str) -> str:
    kind = "iPad" if "iPad" in agent or "Macintosh" in agent and "Mobile" in agent else "Browser"
    version = re.search(r"Version/(\d{1,3})", agent)
    return f"{kind}, Safari {version.group(1)}" if version else kind


class Devices:
    def __init__(self, home: Path, clock=time.time):
        self.home = home
        self.clock = clock
        self.lock = threading.RLock()
        self.attempts: dict[str, deque[float]] = defaultdict(deque)
        self.devices: list[dict[str, Any]] = self._read("devices.json", [])
        self.deadline = self._read("pairing.json", {}).get("closes_at", 0)

    def _read(self, name: str, default: Any) -> Any:
        path = self.home / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

    def _save(self, name: str, value: Any) -> None:
        private_write(self.home / name, json.dumps(value).encode())

    @property
    def pairing_open(self) -> bool:
        with self.lock:
            return self.clock() < self.deadline

    def open_pairing(self) -> float:
        with self.lock:
            self.deadline = self.clock() + 120
            self._save("pairing.json", {"closes_at": self.deadline})
            return self.deadline

    def claim(self, address: str, agent: str) -> tuple[int, str]:
        with self.lock:
            now = self.clock()
            attempts = self.attempts[address]
            while attempts and attempts[0] <= now - 60:
                attempts.popleft()
            if len(attempts) >= 5:
                return 429, "Too many pairing attempts. Wait one minute and try again."
            attempts.append(now)
            if not self.pairing_open:
                return 409, "Run 'VideoEnhancer - Redo pairing' on the PC, then try again."
            secret = secrets.token_urlsafe(32)
            stamp = datetime.fromtimestamp(now, UTC).isoformat()
            device = {
                "id": uuid.uuid4().hex,
                "secret_hash": hashlib.sha256(secret.encode()).hexdigest(),
                "label": device_label(agent),
                "created": stamp,
                "last_seen": stamp,
            }
            # Close durably before publishing a device; failed writes must not issue cookies.
            self.deadline = 0
            self._save("pairing.json", {"closes_at": 0})
            self._save("devices.json", [*self.devices, device])
            self.devices.append(device)
            return 200, secret

    def authenticate(self, secret: str) -> dict[str, Any] | None:
        if not secret or len(secret) > 128:
            return None
        digest = hashlib.sha256(secret.encode()).hexdigest()
        with self.lock:
            for device in self.devices:
                if secrets.compare_digest(digest, device["secret_hash"]):
                    stamp = datetime.fromtimestamp(self.clock(), UTC).isoformat()
                    if device["last_seen"][:16] != stamp[:16]:
                        device["last_seen"] = stamp
                        self._save("devices.json", self.devices)
                    return dict(device)
        return None
