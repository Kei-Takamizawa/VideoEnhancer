"""User-private discovery, loopback HTTP and authenticated SSE."""

from __future__ import annotations

import contextlib
import hmac
import json
import os
import secrets
import signal
import subprocess
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from videoenhancer.service.engine import Engine

APP_ORIGIN = "app://videoenhancer"
DEV_ORIGIN = "http://127.0.0.1:5173"


@contextlib.contextmanager
def service_lock(home: Path) -> Iterator[None]:
    home.mkdir(parents=True, exist_ok=True)
    with (home / "serve.lock").open("a+b") as lock:
        try:
            lock.seek(0)
            if not lock.read(1):
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            port = "unknown"
            try:
                port = json.loads((home / "serve.json").read_text())["port"]
            except (OSError, ValueError, KeyError):
                pass
            raise RuntimeError(f"VideoEnhancer service already runs on port {port}.") from error
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def discovery(home: Path, port: int, token: str) -> None:
    path = home / "serve.json"
    temporary = home / "serve.private.tmp"
    temporary.unlink(missing_ok=True)
    temporary.touch(mode=0o600, exist_ok=False)
    if os.name == "nt":
        import csv
        import io

        identity = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        sid = next(csv.reader(io.StringIO(identity.stdout)))[1]
        subprocess.run(
            ["icacls", str(temporary), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
            capture_output=True,
            check=True,
            timeout=5,
        )
    else:
        temporary.chmod(0o600)
    temporary.write_text(
        json.dumps(
            {
                "port": port,
                "pid": os.getpid(),
                "token": token,
                "base_url": f"http://127.0.0.1:{port}/v1",
            }
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, engine: Engine):
        self.engine = engine
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", 0), Handler)


class Handler(BaseHTTPRequestHandler):
    server: LocalServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Request URLs/credentials and private filenames must not reach access logs.
        pass

    def _headers(self, status: int, mime: str, size: int | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin")
        if origin in {APP_ORIGIN, DEV_ORIGIN}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        if size is not None:
            self.send_header("Content-Length", str(size))
        self.end_headers()

    def _json(self, status: int, value: Any) -> None:
        raw = json.dumps(value, default=str, allow_nan=False).encode()
        self._headers(status, "application/json", len(raw))
        self.wfile.write(raw)

    def _local(self) -> bool:
        expected = f"127.0.0.1:{self.server.server_port}"
        return (
            self.headers.get("Host") == expected
            and self.headers.get("Origin") in {None, APP_ORIGIN, DEV_ORIGIN}
            and (
                self.headers.get("Origin") is not None
                or self.headers.get("Sec-Fetch-Site") != "cross-site"
            )
        )

    def do_OPTIONS(self) -> None:
        if not self._local():
            self._json(403, {"error": "Only the local desktop app is allowed."})
            return
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _request(self) -> None:
        try:
            if not self._local():
                self._json(403, {"error": "Only the local desktop app is allowed."})
                return
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied.encode(), ("Bearer " + self.server.token).encode()):
                self._json(401, {"error": "A valid bearer token is required."})
                return
            url = urlsplit(self.path)
            parts = url.path.strip("/").split("/")
            if not parts or parts.pop(0) != "v1":
                self._json(404, {"error": "Unknown API version."})
                return
            if parts == ["events"] and self.command == "GET":
                self._events()
                return
            if len(parts) == 4 and parts[0] == "operations" and parts[2] == "files":
                op_id, name = parts[1], parts[3]
                operation = self.server.engine.operations[op_id]
                if operation["state"] != "done" or name not in {"original", "enhanced"}:
                    raise ValueError("The preview is not ready.")
                path = self.server.engine.home / "previews" / op_id / f"{name}-preview.mp4"
                self._headers(200, "video/mp4", path.stat().st_size)
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        self.wfile.write(chunk)
                return
            value = {key: values[-1] for key, values in parse_qs(url.query).items()}
            length = int(self.headers.get("Content-Length", 0))
            if length < 0 or length > 1_000_000 or self.headers.get("Transfer-Encoding"):
                self._json(413, {"error": "Request body is too large or not supported."})
                return
            if length:
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError("Request body must be a JSON object.")
            if parts == ["shutdown"] and self.command == "POST":
                self.server.engine.close()
                self._json(200, {"stopped": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            with self.server.engine.lock:
                result = self.server.engine.dispatch(self.command, parts, value)
            self._json(200, result)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (KeyError, FileNotFoundError) as error:
            self._json(404, {"error": str(error)})
        except (ValueError, TypeError, OSError) as error:
            self._json(400, {"error": str(error)})
        except Exception as error:
            self._json(409, {"error": str(error)})

    def _events(self) -> None:
        self._headers(200, "text/event-stream")
        previous = ""
        heartbeat = time.monotonic()
        while not self.server.engine.stop.is_set():
            try:
                with self.server.engine.lock:
                    data = {
                        "queue": self.server.engine.queue(),
                        "health": self.server.engine.health(),
                        "plan": self.server.engine.dispatch("GET", ["plan"], {}),
                    }
                raw = json.dumps(data, default=str, allow_nan=False)
                if raw != previous:
                    self.wfile.write(f"event: update\ndata: {raw}\n\n".encode())
                    previous = raw
                if time.monotonic() - heartbeat >= 10:
                    self.wfile.write(b": heartbeat\n\n")
                    heartbeat = time.monotonic()
                self.wfile.flush()
                self.server.engine.stop.wait(1)
            except (BrokenPipeError, ConnectionResetError):
                return

    do_GET = _request
    do_POST = _request
    do_PUT = _request
    do_DELETE = _request


def serve(home: Path) -> int:
    try:
        with service_lock(home):
            engine = Engine(home)
            server = LocalServer(engine)
            discovery(home, server.server_port, server.token)
            engine.start()

            def stop(_signum: int, _frame: Any) -> None:
                engine.stop.set()
                threading.Thread(target=server.shutdown, daemon=True).start()

            signal.signal(signal.SIGINT, stop)
            signal.signal(signal.SIGTERM, stop)
            print(f"VideoEnhancer service on 127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever(poll_interval=0.25)
            finally:
                engine.close()
                server.server_close()
                (home / "serve.json").unlink(missing_ok=True)
        return 0
    except RuntimeError as error:
        print(str(error), flush=True)
        return 1
