"""Disposable, LAN-only iPad measuring tool. Never import product code."""

import argparse
import asyncio
import base64
import hashlib
import html
import ipaddress
import json
import os
import plistlib
import re
import secrets
import socket
import ssl
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

WORK = Path(__file__).resolve().parents[3]
STATIC = Path(__file__).with_name("static")
DEFAULT_VAPID_SUBJECT = "https://github.com/Kei-Takamizawa/VideoEnhancer"
CHUNK = 4 * 1024 * 1024
MEDIA = {"h264.mp4", "hevc.mp4", "av1.mp4", "50MB.mp4", "500MB.mp4", "1GB.mp4"}


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def write_key(path, key):
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    os.chmod(path, 0o600)


def certificates(home, names, addresses):
    home.mkdir(parents=True, exist_ok=True)
    if (home / "ca.key").exists():
        ca_key = serialization.load_pem_private_key((home / "ca.key").read_bytes(), None)
        ca = x509.load_pem_x509_certificate((home / "ca.crt").read_bytes())
    else:
        ca_key = rsa.generate_private_key(65537, 2048)
        subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "VideoEnhancer Local CA (spike)")]
        )
        now = datetime.now(UTC)
        ca = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
            .add_extension(
                x509.KeyUsage(False, False, False, False, False, True, True, False, False), True
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
            .sign(ca_key, hashes.SHA256())
        )
        write_key(home / "ca.key", ca_key)
        (home / "ca.crt").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    # Reissue the leaf so changed DHCP addresses are always in its SAN.
    key = rsa.generate_private_key(65537, 2048)
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
        .issuer_name(ca.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=397))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(n) for n in names]
                + [x509.IPAddress(ipaddress.ip_address(a)) for a in addresses]
            ),
            False,
        )
        .add_extension(
            x509.KeyUsage(True, False, True, False, False, False, False, False, False), True
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False
        )
        .sign(ca_key, hashes.SHA256())
    )
    write_key(home / "server.key", key)
    (home / "server.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": "local.videoenhancer.spike",
        "PayloadUUID": str(uuid.uuid4()),
        "PayloadDisplayName": "VideoEnhancer Local CA (spike)",
        "PayloadContent": [
            {
                "PayloadType": "com.apple.security.root",
                "PayloadVersion": 1,
                "PayloadIdentifier": "local.videoenhancer.spike.ca",
                "PayloadUUID": str(uuid.uuid4()),
                "PayloadDisplayName": "VideoEnhancer Local CA (spike)",
                "PayloadContent": ca.public_bytes(serialization.Encoding.DER),
            }
        ],
    }
    (home / "ca.mobileconfig").write_bytes(plistlib.dumps(profile))


class State:
    def __init__(self, home, evidence, names, clock=time.time):
        self.home, self.evidence, self.names, self.clock = (
            Path(home),
            Path(evidence),
            set(names),
            clock,
        )
        for p in [self.home, self.home / "uploads", self.home / "media", self.evidence.parent]:
            p.mkdir(parents=True, exist_ok=True)
        self.device_file = self.home / "device.json"
        self.device = json.loads(self.device_file.read_text()) if self.device_file.exists() else {}
        self.pairing_file = self.home / "pairing.json"
        pairing = json.loads(self.pairing_file.read_text()) if self.pairing_file.exists() else {}
        self.deadline = pairing.get("deadline", 0)
        self.claim_hash = pairing.get("claim_hash")
        self.claim_deadline = pairing.get("claim_deadline", 0)
        self.locks = {}
        self.tasks = set()
        vapid_path = self.home / "vapid.key"
        if not vapid_path.exists():
            write_key(vapid_path, ec.generate_private_key(ec.SECP256R1()))
        key = serialization.load_pem_private_key(vapid_path.read_bytes(), None)
        raw = key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.vapid_public = base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def open_pairing(self, seconds):
        self.deadline = self.clock() + seconds
        self.claim_hash = None
        self.save_pairing()

    def save_pairing(self):
        self.pairing_file.write_text(
            json.dumps(
                {
                    "deadline": self.deadline,
                    "claim_hash": self.claim_hash,
                    "claim_deadline": self.claim_deadline,
                }
            ),
            encoding="utf-8",
        )

    def claim(self):
        if self.clock() >= self.deadline:
            return None
        self.deadline = 0
        secret = secrets.token_urlsafe(32)
        self.claim_hash = token_hash(secret)
        self.claim_deadline = self.clock() + 1800
        self.device = {"pairing_pending": True}
        self.device_file.write_text(json.dumps(self.device), encoding="utf-8")
        self.save_pairing()
        return secret

    def finish(self, secret):
        if not self.claim_hash or self.clock() >= self.claim_deadline:
            return None
        if not secrets.compare_digest(token_hash(secret), self.claim_hash):
            return None
        self.claim_hash = None
        token = secrets.token_urlsafe(32)
        self.device = {"token_hash": token_hash(token)}
        self.device_file.write_text(json.dumps(self.device), encoding="utf-8")
        self.save_pairing()
        return token

    def authorized(self, token):
        return bool(
            token and secrets.compare_digest(token_hash(token), self.device.get("token_hash", ""))
        )

    def record(self, result, user_agent="PC server"):
        record = dict(result)
        record.setdefault("display_mode", "server")
        record.setdefault("automated", getattr(self, "automated", False))
        record.update(timestamp=datetime.now(UTC).isoformat(), user_agent=user_agent)
        destination = (
            self.evidence.parent / "pc-results.jsonl" if record.get("automated") else self.evidence
        )
        with destination.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")


def push_response(response):
    # Copy only service diagnostics, never exception text, URLs or response bodies.
    result = {"status": None, "reason": None, "apns_id": None}
    if response is not None:
        result["status"] = response.status_code
        try:
            reason = response.json().get("reason")
            if isinstance(reason, str) and re.fullmatch(r"[A-Za-z]{1,80}", reason):
                result["reason"] = reason
        except (ValueError, AttributeError):
            pass
        identifier = response.headers.get("apns-id")
        if identifier and re.fullmatch(r"[a-fA-F0-9-]{36}", identifier):
            result["apns_id"] = identifier
    return result


def send_push(state, subscription, payload, **metadata):
    from py_vapid import Vapid
    from pywebpush import webpush

    endpoint = urlsplit(subscription["endpoint"])
    if (
        endpoint.scheme != "https"
        or endpoint.port not in {None, 443}
        or endpoint.username
        or endpoint.password
        or not (
            endpoint.hostname == "web.push.apple.com"
            or (endpoint.hostname or "").endswith(".push.apple.com")
        )
    ):
        state.record(
            {
                "test": "T3",
                **metadata,
                "phase": "send_error",
                "error": "InvalidAppleEndpoint",
                **push_response(None),
            }
        )
        return False
    origin = f"https://{endpoint.hostname}"
    claims = {
        "sub": getattr(state, "vapid_subject", DEFAULT_VAPID_SUBJECT),
        "aud": origin,
        "exp": int(time.time()) + 12 * 60 * 60,
    }
    try:
        subject = urlsplit(claims["sub"])
        if not (
            (
                subject.scheme == "https"
                and subject.hostname
                and not subject.username
                and not subject.password
            )
            or (
                subject.scheme == "mailto"
                and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", subject.path)
            )
        ):
            raise ValueError("Invalid VAPID contact URI")
        vapid = Vapid.from_file(str(state.home / "vapid.key"))
        # py-vapid's strict regex rejects valid HTTPS contact paths (RFC 8292 2.1).
        # Validate above, then bypass only that legacy contact regex.
        vapid.conf["no-strict"] = True
        response = webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=vapid,
            vapid_claims=claims,
            ttl=300,
            timeout=20,
        )
        result = {"phase": "sent", **push_response(response)}
    except Exception as exc:
        result = {
            "phase": "send_error",
            "error": type(exc).__name__,
            **push_response(getattr(exc, "response", None)),
        }
    state.record({"test": "T3", **metadata, **result})
    return result["phase"] == "sent"


def make_app(state, plain=False):
    static_paths = {
        "/",
        "/app.js",
        "/style.css",
        "/sw.js",
        "/manifest.json",
        "/icon.svg",
        "/pair/finish",
    }

    async def request_log(request, response):
        # Only fixed route templates: never owner paths, file names or query strings.
        route = request.match_info.route.resource
        path = route.canonical if route is not None else "<unmatched>"
        mode = request.headers.get("X-Display-Mode", "unknown")
        if mode not in {"standalone", "browser"}:
            mode = "unknown"
        entry = {
            "time": datetime.now(UTC).isoformat(),
            "method": request.method,
            "path": path,
            "status": response.status,
            "device_cookie": "yes" if "ve_device" in request.cookies else "no",
            "display_mode": mode,
        }
        with (state.evidence.parent / "owner-server.log").open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry) + "\n")

    @web.middleware
    async def guard(request, handler):
        try:
            host = urlsplit("//" + request.host)
            if host.hostname not in state.names or host.username or host.password:
                raise ValueError()
            origin = request.headers.get("Origin")
            if origin:
                parsed = urlsplit(origin)
                local_port = request.transport.get_extra_info("sockname")[1]
                if (
                    parsed.scheme != "https"
                    or parsed.hostname not in state.names
                    or parsed.port not in {8443, local_port}
                    or parsed.path
                    or parsed.username
                ):
                    raise ValueError()
        except ValueError:
            raise web.HTTPForbidden(text="Host or Origin rejected") from None
        if (
            not plain
            and request.path not in static_paths
            and request.path not in {"/api/pair/finish", "/pair/claim"}
        ):
            token = request.cookies.get("ve_device", "")
            if request.headers.get("Authorization", "").startswith("Bearer "):
                token = request.headers["Authorization"][7:]
            if not state.authorized(token):
                raise web.HTTPUnauthorized(text="Pair this device first")
        response = await handler(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; media-src 'self' blob:; "
            "worker-src 'self'; frame-ancestors 'none'"
        )
        return response

    app = web.Application(middlewares=[guard], client_max_size=CHUNK + 65536)

    app.on_response_prepare.append(request_log)

    async def pair(request):
        secret = state.claim()
        if not secret:
            return web.Response(
                text=(
                    "<h1>Pairing is closed</h1>"
                    "<p>Ask the operator to restart with --redo-pairing.</p>"
                ),
                content_type="text/html",
            )
        host = html.escape(urlsplit("//" + request.host).hostname)
        return web.Response(
            text=f"""<!doctype html><meta name="viewport" content="width=device-width">
<h1>Pairing claimed</h1>
<p>Keep this tab open. Install the <a href="/ca.mobileconfig">CA profile</a>
(<a href="/ca.crt">certificate</a>).</p>
<ol><li>Settings &gt; General &gt; VPN &amp; Device Management:
install VideoEnhancer Local CA (spike).</li>
<li>Settings &gt; General &gt; About &gt; Certificate Trust Settings:
enable full trust.</li>
<li>Return here within 30 minutes and
<a href="https://{host}:8443/pair/finish#{secret}">finish pairing</a>.</li></ol>""",
            content_type="text/html",
        )

    async def ca(request):
        name = request.match_info["name"]
        return web.FileResponse(
            state.home / name,
            headers={
                "Content-Type": "application/x-apple-aspen-config"
                if name.endswith("mobileconfig")
                else "application/x-x509-ca-cert"
            },
        )

    if plain:
        app.router.add_get("/pair", pair, allow_head=False)
        app.router.add_get("/{name:ca\\.mobileconfig|ca\\.crt}", ca)
        return app

    async def static(request):
        name = request.path.lstrip("/")
        if name in {"", "pair/finish"}:
            name = "index.html"
        return web.FileResponse(STATIC / name)

    for path in static_paths:
        app.router.add_get(path, static)

    async def finish(request):
        data = await request.json()
        secret = data.get("secret", "")
        if not isinstance(secret, str):
            raise web.HTTPBadRequest() from None
        token = state.finish(secret)
        if not token:
            raise web.HTTPForbidden(text="Claim expired or used")
        response = web.json_response({"paired": True})
        response.set_cookie(
            "ve_device",
            token,
            secure=True,
            httponly=True,
            samesite="Strict",
            max_age=31536000,
            path="/",
        )
        return response

    async def claim(request):
        secret = state.claim()
        if not secret:
            raise web.HTTPForbidden(text="Pairing is closed. Ask the operator for --redo-pairing.")
        token = state.finish(secret)
        response = web.json_response({"paired": True})
        response.set_cookie(
            "ve_device",
            token,
            secure=True,
            httponly=True,
            samesite="Strict",
            max_age=31536000,
            path="/",
        )
        return response

    async def config(request):
        return web.json_response({"vapid": state.vapid_public, "chunk_bytes": CHUNK})

    async def results(request):
        data = await request.json()
        if not isinstance(data, dict) or data.get("test") not in {f"T{i}" for i in range(1, 10)}:
            raise web.HTTPBadRequest(text="Unknown test")
        data.setdefault("display_mode", request.headers.get("X-Display-Mode", "unknown"))
        state.record(data, request.headers.get("User-Agent", ""))
        return web.json_response({"recorded": True})

    def upload_path(request):
        digest = request.match_info["digest"]
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise web.HTTPBadRequest(text="Expected SHA-256")
        return state.home / "uploads" / digest

    async def upload_status(request):
        path = upload_path(request)
        return web.json_response({"offset": path.stat().st_size if path.exists() else 0})

    async def upload_chunk(request):
        path = upload_path(request)
        lock = state.locks.setdefault(path.name, asyncio.Lock())
        async with lock:
            try:
                offset = int(request.query.get("offset", "-1"))
            except ValueError:
                raise web.HTTPBadRequest() from None
            size = path.stat().st_size if path.exists() else 0
            if offset != size:
                raise web.HTTPConflict(text="Resume from server offset")
            try:
                data = await request.read()
            except ConnectionResetError:
                raise web.HTTPBadRequest(
                    text="Upload interrupted; query offset and resume"
                ) from None
            if len(data) > CHUNK or size + len(data) > 8_000_000_000:
                raise web.HTTPRequestEntityTooLarge(max_size=CHUNK, actual_size=len(data))
            with path.open("ab") as f:
                f.write(data)
        return web.json_response({"offset": size + len(data)})

    async def upload_finish(request):
        path = upload_path(request)
        data = await request.json()
        async with state.locks.setdefault(path.name, asyncio.Lock()):
            if not path.exists() or path.stat().st_size != data.get("size"):
                raise web.HTTPConflict(text="Size mismatch")

            def digest_file():
                with path.open("rb") as f:
                    return hashlib.file_digest(f, "sha256").hexdigest()

            digest = await asyncio.to_thread(digest_file)
            if digest != path.name:
                raise web.HTTPUnprocessableEntity(text="Hash mismatch")
        return web.json_response({"sha256": digest, "bytes": path.stat().st_size})

    async def media(request):
        name = request.match_info["name"]
        if name not in MEDIA or not (state.home / "media" / name).is_file():
            raise web.HTTPNotFound()
        path = state.home / "media" / name
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        headers = {
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-store",
        }
        if "download" in request.query:
            headers["Content-Disposition"] = f'attachment; filename="{name}"'
        raw = request.headers.get("Range")
        if raw:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", raw)
            try:
                if not match or not any(match.groups()):
                    raise ValueError()
                a, b = match.groups()
                if a:
                    start, end = int(a), min(int(b), size - 1) if b else size - 1
                else:
                    suffix = int(b)
                    if suffix == 0:
                        raise ValueError()
                    start, end = max(0, size - suffix), size - 1
                if start > end or start >= size:
                    raise ValueError()
            except ValueError:
                return web.Response(
                    status=416, headers={**headers, "Content-Range": f"bytes */{size}"}
                )
            status = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        headers["Content-Length"] = str(end - start + 1)
        response = web.StreamResponse(status=status, headers=headers)
        started, sent, complete = time.perf_counter(), 0, False
        await response.prepare(request)
        try:
            if request.method != "HEAD":
                with path.open("rb") as f:
                    f.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = f.read(min(1024 * 1024, remaining))
                        await response.write(chunk)
                        remaining -= len(chunk)
                        sent += len(chunk)
            await response.write_eof()
            complete = True
        except ConnectionError:
            pass
        finally:
            run = request.query.get("run", "")
            if "download" in request.query and re.fullmatch(r"[a-zA-Z0-9-]{1,64}", run):
                elapsed = time.perf_counter() - started
                state.record(
                    {
                        "test": "T6",
                        "phase": "server_transfer",
                        "run": run,
                        "bytes": sent,
                        "seconds": elapsed,
                        "MB_s": sent / 1e6 / elapsed,
                        "complete": complete,
                        "range": raw,
                        "automated": getattr(state, "automated", False),
                        "display_mode": request.headers.get("X-Display-Mode", "unknown"),
                    },
                    request.headers.get("User-Agent", ""),
                )
        return response

    async def events(request):
        response = web.StreamResponse(
            headers={"Content-Type": "text/event-stream", "Cache-Control": "no-store"}
        )
        await response.prepare(request)
        try:
            while True:
                await response.write(
                    f"data: {json.dumps({'server_ms': int(time.time() * 1000)})}\n\n".encode()
                )
                await asyncio.sleep(1)
        except (ConnectionError, asyncio.CancelledError):
            pass
        return response

    async def push_subscribe(request):
        data = await request.json()
        subscription = data.get("subscription", {})
        # Never let a paired browser turn the PC into an arbitrary HTTP client.
        endpoint = urlsplit(subscription.get("endpoint", ""))
        if (
            endpoint.scheme != "https"
            or endpoint.port not in {None, 443}
            or endpoint.username
            or not (
                endpoint.hostname == "web.push.apple.com"
                or (endpoint.hostname or "").endswith(".push.apple.com")
            )
        ):
            raise web.HTTPBadRequest(text="This spike accepts Apple push endpoints only")
        if not all(
            isinstance(subscription.get("keys", {}).get(k), str) for k in ["p256dh", "auth"]
        ):
            raise web.HTTPBadRequest(text="Missing push keys")
        run = secrets.token_hex(8)
        (state.home / "subscription.json").write_text(json.dumps(subscription), encoding="utf-8")
        diagnostics = {
            "notification_permission": data.get("notification_permission", "unknown"),
            "push_manager": data.get("push_manager", False),
            "push_endpoint_host": endpoint.hostname,
        }
        mode = request.headers.get("X-Display-Mode", "unknown")
        automated = getattr(state, "automated", False)

        async def send(delay):
            await asyncio.sleep(delay)
            await asyncio.to_thread(
                send_push,
                state,
                subscription,
                {
                    "title": "VideoEnhancer spike",
                    "body": f"Test push after {delay} seconds",
                    "run": run,
                    "delay": delay,
                },
                **diagnostics,
                display_mode=mode,
                automated=automated,
                run=run,
                delay=delay,
            )

        for delay in [10, 60]:
            task = asyncio.create_task(send(delay))
            state.tasks.add(task)
            task.add_done_callback(state.tasks.discard)
        return web.json_response({"scheduled": [10, 60], "run": run})

    async def cleanup(app):
        for task in list(state.tasks):
            task.cancel()
        await asyncio.gather(*state.tasks, return_exceptions=True)

    app.on_cleanup.append(cleanup)
    app.router.add_post("/pair/claim", claim)
    app.router.add_post("/api/pair/finish", finish)
    app.router.add_get("/api/config", config)
    app.router.add_post("/api/results", results)
    app.router.add_get("/api/upload/{digest}", upload_status)
    app.router.add_put("/api/upload/{digest}", upload_chunk)
    app.router.add_post("/api/upload/{digest}/finish", upload_finish)
    app.router.add_get("/media/{name}", media)
    app.router.add_get("/api/events", events)
    app.router.add_post("/api/push", push_subscribe)
    return app


def private_addresses():
    ranges = [ipaddress.ip_network(n) for n in ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]]
    return sorted(
        {
            a[4][0]
            for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
            if any(ipaddress.ip_address(a[4][0]) in r for r in ranges)
        }
    )


async def serve(args):
    from zeroconf import IPVersion, ServiceInfo
    from zeroconf.asyncio import AsyncZeroconf

    addresses = private_addresses()
    binds = args.bind or addresses
    if not getattr(args, "push_selftest", False) and (
        not binds or any(a not in addresses and a != "127.0.0.1" for a in binds)
    ):
        raise SystemExit(
            "Bind must be one of this PC's private IPv4 addresses (or loopback for tests)"
        )
    names = ["videoenhancer.local", socket.gethostname().lower() + ".local"]
    home = args.home.resolve()
    if not home.is_relative_to(WORK / "scratch"):
        raise SystemExit("Spike home must be below work/scratch")
    evidence = (
        WORK
        / "evidence"
        / "VE-R0c"
        / ("pc-results.jsonl" if getattr(args, "automated", False) else "ipad-results.jsonl")
    )
    if getattr(args, "push_selftest", False):
        if not (home / "subscription.json").exists() or not (home / "vapid.key").exists():
            print("No stored subscription/key. Subscribe from the paired app first.")
            raise SystemExit(1)
        state = State(home, evidence, names)
        state.vapid_subject = args.vapid_subject
        ok = await asyncio.to_thread(
            send_push,
            state,
            json.loads((home / "subscription.json").read_text()),
            {"title": "VideoEnhancer spike", "body": "PC push self-test"},
            selftest=True,
        )
        print(
            "Push self-test "
            + ("sent" if ok else "failed")
            + "; status/reason recorded in VE-R0c/ipad-results.jsonl"
        )
        raise SystemExit(0 if ok else 1)
    certificates(home, names, addresses + (["127.0.0.1"] if "127.0.0.1" in binds else []))
    state = State(home, evidence, names + addresses + ["127.0.0.1"])
    state.vapid_subject = getattr(args, "vapid_subject", DEFAULT_VAPID_SUBJECT)
    state.automated = getattr(args, "automated", False)
    if args.redo_pairing or not state.pairing_file.exists():
        state.open_pairing(args.pair_seconds)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(home / "server.crt", home / "server.key")
    runners = []
    zeroconf = None
    info = None
    try:
        for plain, port in [(True, 8080), (False, 8443)]:
            runner = web.AppRunner(make_app(state, plain), access_log=None)
            await runner.setup()
            runners.append(runner)
            for bind in binds:
                await web.TCPSite(
                    runner, bind, port, ssl_context=None if plain else context
                ).start()
        if not args.no_mdns:
            zeroconf = AsyncZeroconf(interfaces=addresses, ip_version=IPVersion.V4Only)
            info = ServiceInfo(
                "_https._tcp.local.",
                "VideoEnhancer spike._https._tcp.local.",
                addresses=[socket.inet_aton(a) for a in addresses],
                port=8443,
                server="videoenhancer.local.",
                properties={"path": "/"},
            )
            await zeroconf.async_register_service(info, allow_name_change=False)
        print(
            json.dumps(
                {
                    "ready": True,
                    "binds": binds,
                    "http": 8080,
                    "https": 8443,
                    "mdns": bool(zeroconf),
                    "pair_seconds": args.pair_seconds,
                }
            ),
            flush=True,
        )
        await asyncio.Event().wait()
    finally:
        if zeroconf:
            if info:
                await zeroconf.async_unregister_service(info)
            await zeroconf.async_close()
        for runner in runners:
            await runner.cleanup()


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=WORK / "scratch" / "ipad-spike")
    parser.add_argument("--redo-pairing", action="store_true")
    parser.add_argument("--pair-seconds", type=float, default=120)
    parser.add_argument(
        "--bind", action="append", help="Repeat for each LAN address; default: all private IPv4"
    )
    parser.add_argument("--no-mdns", action="store_true", help="Only for isolated automated tests")
    parser.add_argument(
        "--push-selftest",
        action="store_true",
        help="Send once using the stored subscription; no listeners",
    )
    parser.add_argument("--vapid-subject", default=DEFAULT_VAPID_SUBJECT)
    return parser


if __name__ == "__main__":
    try:
        asyncio.run(serve(argument_parser().parse_args()))
    except KeyboardInterrupt:
        pass
