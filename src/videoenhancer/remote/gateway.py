"""IPv4 LAN HTTPS gateway with device cookies and public HTTP setup."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import mimetypes
import os
import re
import secrets
import socket
import ssl
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlsplit

from videoenhancer.remote.adapter import EngineAdapter
from videoenhancer.remote.certificates import ensure_certificates, local_addresses
from videoenhancer.remote.security import Devices, cookie_secret, private_ipv4

WEB = Path(__file__).with_name("web")
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; media-src 'self' blob:; manifest-src 'self'; worker-src 'self'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
)

PAIRING_HELP = (
    "When you are ready to pair, click 'VideoEnhancer - Redo pairing' on the PC, "
    "then tap Pair this iPad within 2 minutes."
)


@dataclass
class Download:
    identifier: str
    expires: float
    ranges: list[tuple[int, int]] = field(default_factory=list)
    active: bool = False


class LANServer(ThreadingHTTPServer):
    address_family = socket.AF_INET
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, gateway, *, secure=False, context=None):
        self.gateway = gateway
        self.secure = secure
        self.context = context
        super().__init__(address, Handler)

    def get_request(self):
        connection, address = self.socket.accept()
        if not private_ipv4(address[0]):
            connection.close()
            raise OSError("Source address is not allowed.")
        connection.settimeout(15)
        if self.context is not None:
            try:
                connection = self.context.wrap_socket(
                    connection, server_side=True, do_handshake_on_connect=False
                )
            except (OSError, ssl.SSLError):
                connection.close()
                # Return control to serve_forever so a rejected handshake cannot block shutdown.
                raise
        return connection, address

    def process_request_thread(self, request, client_address):
        try:
            if isinstance(request, ssl.SSLSocket):
                request.do_handshake()
            super().process_request_thread(request, client_address)
        except (OSError, ssl.SSLError):
            self.shutdown_request(request)

    def handle_error(self, request, client_address):
        # No traceback may expose request data or library paths.
        pass


class Gateway:
    def __init__(self, engine, home: Path, settings: dict):
        self.home = home
        self.settings = settings
        self.pc_name = os.environ.get("COMPUTERNAME") or socket.gethostname().split(".")[0]
        self.certificates = ensure_certificates(home / "remote", self.pc_name, local_addresses())
        self.devices = Devices(home / "remote")
        self.adapter = EngineAdapter(engine, home, settings)
        self.servers: list[LANServer] = []
        self.threads: list[threading.Thread] = []
        self.logger = logging.getLogger("videoenhancer.remote")
        self.https_port = settings.get("remote_https_port", 8443)
        self.setup_port = settings.get("remote_setup_port", 8080)
        self.downloads: dict[str, Download] = {}
        self.download_lock = threading.Lock()

    def start(self):
        if self.servers:
            return
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            self.home / "remote" / "server.crt", self.home / "remote" / "server.key"
        )
        try:
            secure = LANServer(("0.0.0.0", self.https_port), self, secure=True, context=context)
            self.servers.append(secure)
            self.https_port = secure.server_port
            setup = LANServer(("0.0.0.0", self.setup_port), self)
            self.servers.append(setup)
            self.setup_port = setup.server_port
            for server in self.servers:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                self.threads.append(thread)
        except Exception:
            self.close()
            raise

    def close(self):
        for server, thread in zip(self.servers, self.threads, strict=False):
            server.shutdown()
            thread.join(timeout=5)
        for server in self.servers:
            server.server_close()
        self.servers.clear()
        self.threads.clear()

    def status(self):
        return {
            "gateway_running": bool(self.servers),
            "pc_name": self.pc_name,
            "addresses": [
                f"https://{host}:{self.https_port}/"
                for host in [self.certificates.names[0], *self.certificates.addresses]
            ],
            "setup_address": f"http://{self.certificates.names[0]}:{self.setup_port}/",
            "cert_expires": self.certificates.expires,
            "paired_devices": len(self.devices.devices),
            "pairing_open": self.devices.pairing_open,
            "closes_at": datetime.fromtimestamp(self.devices.deadline, UTC).isoformat(),
        }

    def open_pairing(self):
        self.devices.open_pairing()
        return self.status()


class Handler(BaseHTTPRequestHandler):
    server: LANServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        # Parser/method errors use the same security headers and never echo input.
        self._error(code, "The request is invalid.")

    def _send(self, status, body=b"", mime="application/json", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self._status = status
        if getattr(self, "command", None) != "HEAD":
            self.wfile.write(body)

    def _json(self, status, value, headers=None):
        self._send(status, json.dumps(value).encode(), headers=headers)

    def _error(self, status, message):
        self._json(status, {"error": message})

    def _route_template(self, path):
        if path.startswith("/dl/"):
            return "/dl/{token}"
        if path.startswith("/api/library/"):
            return "/api/library/{id}/video" if path.endswith("/video") else "/api/library/{id}"
        if path in {
            "/api/library",
            "/api/storage",
            "/api/session",
            "/api/pair/claim",
            "/api/client-event",
        }:
            return path
        return "/static" if not path.startswith("/api/") else "/api/unknown"

    def _request(self):
        started = time.monotonic()
        path = urlsplit(self.path).path
        self._status = 500
        try:
            self._dispatch(path)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except FileNotFoundError:
            self._error(404, "This video is no longer available.")
        except PermissionError:
            self._error(
                409, "This video is in use. Stop playback or wait for the download to finish."
            )
        except ValueError:
            self._error(400, "The request is invalid.")
        except OSError:
            self._error(503, "The PC cannot read the library right now. Try again.")
        except Exception:
            self._error(500, "The PC could not complete this request. Try again.")
        finally:
            self.server.gateway.logger.info(
                "%s %s %s %.3f",
                self.command,
                self._route_template(path),
                self._status,
                time.monotonic() - started,
            )

    def _dispatch(self, path):
        gateway = self.server.gateway
        port = self.server.server_port
        hosts = {
            f"{name.lower()}:{port}"
            for name in [*gateway.certificates.names, *gateway.certificates.addresses]
        }
        host = self.headers.get("Host", "")
        if len(self.headers.get_all("Host", [])) != 1 or host.lower() not in hosts:
            return self._error(421, "Use the VideoEnhancer address shown on the PC.")
        if not self.server.secure:
            return self._setup(path)
        if self.command not in {"GET", "HEAD"}:
            if (
                len(self.headers.get_all("Origin", [])) != 1
                or self.headers.get("Origin") != f"https://{host}"
            ):
                return self._error(403, "Open VideoEnhancer from its own Home Screen app.")
            lengths = self.headers.get_all("Content-Length", [])
            length_text = self.headers.get("Content-Length", "0")
            if (
                self.headers.get("Transfer-Encoding")
                or len(lengths) > 1
                or not length_text.isdecimal()
            ):
                return self._error(400, "The request body is invalid.")
            length = int(length_text)
            if path == "/api/client-event" and length > 2048:
                return self._error(413, "The request body is too large.")
            if path != "/api/client-event" and length not in {0, 2}:
                return self._error(400, "The request body is invalid.")
            self.body = self.rfile.read(length) if length else b""
        device = gateway.devices.authenticate(cookie_secret(self.headers.get("Cookie")))
        if path == "/api/session" and self.command == "GET":
            if not device:
                return self._json(
                    200, {"paired": False, "pairing_open": gateway.devices.pairing_open}
                )
            return self._json(
                200,
                {
                    "paired": True,
                    "device_label": device["label"],
                    "paired_at": device["created"],
                    "pc_name": gateway.pc_name,
                    "addresses": gateway.status()["addresses"],
                    "cert_expires": gateway.certificates.expires,
                    "version": "0.1.0",
                    "share_limit_bytes": gateway.settings.get("share_limit_bytes", 900_000_000),
                },
            )
        if path == "/api/pair/claim" and self.command == "POST":
            status, value = gateway.devices.claim(
                self.client_address[0], self.headers.get("User-Agent", "")
            )
            if status != 200:
                return self._error(status, value)
            return self._json(
                200,
                {"paired": True},
                {
                    "Set-Cookie": f"ve_device={value}; HttpOnly; Secure; "
                    "SameSite=Strict; Path=/; Max-Age=34560000"
                },
            )
        if path.startswith("/dl/") and self.command in {"GET", "HEAD"}:
            return self._download(path[4:])
        if not path.startswith("/api/"):
            return self._static(path)
        if not device:
            return self._error(401, "Pair this iPad to use VideoEnhancer.")
        if path == "/api/client-event" and self.command == "POST":
            return self._client_event()
        library = gateway.adapter.library
        if path == "/api/library" and self.command == "GET":
            return self._json(200, {"items": library.list()})
        if path == "/api/storage" and self.command == "GET":
            return self._json(200, library.storage())
        parts = path.strip("/").split("/")
        if (
            len(parts) == 4
            and parts[:2] == ["api", "library"]
            and parts[3] == "download-link"
            and self.command == "POST"
        ):
            with library.acquire(parts[2]):
                token = secrets.token_hex(32)
                digest = hashlib.sha256(token.encode()).hexdigest()
                with gateway.download_lock:
                    gateway.downloads = {
                        key: value
                        for key, value in gateway.downloads.items()
                        if value.expires > time.monotonic()
                    }
                    if len(gateway.downloads) >= 256:
                        return self._error(429, "Too many download links. Try again later.")
                    gateway.downloads[digest] = Download(parts[2], time.monotonic() + 600)
            return self._json(200, {"url": f"https://{host}/dl/{token}"})
        if (
            len(parts) == 4
            and parts[:2] == ["api", "library"]
            and parts[3] == "video"
            and self.command in {"GET", "HEAD"}
        ):
            return self._video(parts[2])
        if len(parts) == 3 and parts[:2] == ["api", "library"] and self.command == "DELETE":
            library.delete(parts[2])
            return self._json(200, {"deleted": True})
        return self._error(404, "This page is not available.")

    def _setup(self, path):
        gateway = self.server.gateway
        if self.command not in {"GET", "HEAD"}:
            return self._error(404, "This page is not available.")
        if path in {"/ca.mobileconfig", "/ca.cer"}:
            mime = (
                "application/x-apple-aspen-config"
                if path.endswith("mobileconfig")
                else "application/pkix-cert"
            )
            return self._send(200, (gateway.home / "remote" / path[1:]).read_bytes(), mime)
        if path != "/":
            return self._error(404, "This page is not available.")
        address = html.escape(gateway.status()["addresses"][0], quote=True)
        pairing = (
            "Pairing is open now (2-minute window)."
            if gateway.devices.pairing_open
            else "Pairing is closed."
        )
        body = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Set up VideoEnhancer</title><h1>Set up VideoEnhancer</h1><ol>
<li><a href="/ca.mobileconfig">Install the VideoEnhancer CA profile</a>
(or <a href="/ca.cer">download the certificate</a>).</li>
<li>Open Settings &gt; General &gt; VPN &amp; Device Management.
Select VideoEnhancer Local CA, then tap Install.</li>
<li>Open Settings &gt; General &gt; About &gt; Certificate Trust Settings.
Turn on full trust for VideoEnhancer Local CA.</li>
<li><a href="{address}">Open VideoEnhancer over HTTPS</a>.
In Safari, tap Share &gt; Add to Home Screen, with Open as Web App on.</li>
<li>Open the Home Screen app and tap Pair this iPad before the pairing window closes.</li>
</ol><p>{pairing}</p><p>{html.escape(PAIRING_HELP)}</p></html>'''
        return self._send(200, body.encode(), "text/html; charset=utf-8")

    def _static(self, path):
        if self.command not in {"GET", "HEAD"}:
            return self._error(404, "This page is not available.")
        if path == "/favicon.ico":
            return self._send(204)
        if path == "/apple-touch-icon-precomposed.png":
            path = "/apple-touch-icon.png"
        target = WEB / ("index.html" if path == "/" else path.lstrip("/"))
        # All assets are shipped flat; no arbitrary filesystem traversal.
        if target.parent != WEB or not target.is_file() or target.is_symlink():
            return self._error(404, "This page is not available.")
        mime = {
            ".js": "text/javascript",
            ".mjs": "text/javascript",
            ".webmanifest": "application/manifest+json",
        }.get(target.suffix)
        return self._send(
            200,
            target.read_bytes(),
            mime or mimetypes.guess_type(target.name)[0] or "application/octet-stream",
        )

    def _client_event(self):
        event = json.loads(self.body)
        if not isinstance(event, dict) or event.get("kind") not in {
            "share_failure",
            "load_failure",
            "share_check",
        }:
            raise ValueError("Invalid client event.")
        if event.get("phase") not in {"load", "share", "playback"}:
            raise ValueError("Invalid phase.")
        size = event.get("size_bytes")
        if type(size) is not int or not 0 <= size <= 2**53 - 1:
            raise ValueError("Invalid size.")
        can_share = event.get("can_share")
        if can_share is not None and type(can_share) is not bool:
            raise ValueError("Invalid sharing result.")
        name = event.get("error_name", "")
        # Browser-supplied strings are untrusted and may include filenames or URLs.
        known_names = {
            "",
            "Error",
            "TypeError",
            "RangeError",
            "NotAllowedError",
            "AbortError",
            "DataError",
            "NotSupportedError",
            "SecurityError",
            "InvalidStateError",
            "NetworkError",
            "NotReadableError",
            "MediaError",
        }
        name = name if isinstance(name, str) and name in known_names else "Error"
        message = event.get("error_message", "")
        safe_messages = {
            "",
            "Failed to fetch",
            "Load failed",
            "The operation is not allowed.",
            "The request is not allowed by the user agent or the platform in the current "
            "context, possibly because the user denied permission.",
            "File sharing is unavailable on this iPad.",
        }
        message = (
            message
            if isinstance(message, str) and message in safe_messages
            else "Browser operation failed."
        )
        self.server.gateway.logger.info(
            "client-event %s",
            json.dumps(
                {
                    "kind": event["kind"],
                    "error_name": name,
                    "error_message": message[:200],
                    "size_bytes": size,
                    "can_share": can_share,
                    "phase": event["phase"],
                }
            ),
        )
        return self._json(200, {"recorded": True})

    def _download(self, token):
        gateway = self.server.gateway
        if not re.fullmatch(r"[0-9a-f]{64}", token):
            return self._error(404, "This download link is no longer available.")
        digest = hashlib.sha256(token.encode()).hexdigest()
        with gateway.download_lock:
            download = gateway.downloads.get(digest)
            if download is None or download.expires <= time.monotonic():
                gateway.downloads.pop(digest, None)
                return self._error(404, "This download link is no longer available.")
            if download.active:
                return self._error(409, "This download is already in progress.")
            download.active = True
        try:
            completed = self._video(download.identifier, attachment=True)
            if completed is not None:
                start, end, size = completed
                with gateway.download_lock:
                    ranges = sorted([*download.ranges, (start, end)])
                    merged = []
                    for first, last in ranges:
                        if merged and first <= merged[-1][1] + 1:
                            merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
                        else:
                            merged.append((first, last))
                    download.ranges = merged
                    if merged == [(0, size - 1)]:
                        gateway.downloads.pop(digest, None)
        finally:
            with gateway.download_lock:
                download.active = False

    def _video(self, identifier, *, attachment=False):
        from videoenhancer.remote.library import parse_range

        with self.server.gateway.adapter.library.acquire(identifier) as (stream, item):
            size = item["size"]
            try:
                start, end = parse_range(self.headers.get("Range"), size)
            except ValueError:
                return self._send(
                    416, headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"}
                )
            count = max(0, end - start + 1)
            self.send_response(206 if self.headers.get("Range") else 200)
            self.send_header("Content-Type", item.get("mime", "video/mp4"))
            self.send_header("Content-Length", str(count))
            self.send_header("Accept-Ranges", "bytes")
            if attachment:
                self.send_header(
                    "Content-Disposition",
                    "attachment; filename*=UTF-8''" + quote(item["filename"], safe=""),
                )
            if self.headers.get("Range"):
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            self._status = 206 if self.headers.get("Range") else 200
            if self.command == "HEAD":
                return
            stream.seek(start)
            while count:
                data = stream.read(min(256 * 1024, count))
                if not data:
                    break
                self.wfile.write(data)
                count -= len(data)
            self.wfile.flush()
            if count == 0:
                return start, end, size

    do_GET = _request
    do_HEAD = _request
    do_POST = _request
    do_DELETE = _request
    do_PUT = _request
    do_OPTIONS = _request
    do_PATCH = _request
