"""User-private discovery, loopback HTTP and authenticated SSE."""

from __future__ import annotations

import contextlib
import hmac
import json
import os
import secrets
import signal
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from videoenhancer import proc
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

        identity = proc.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
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
        engine.start_publication()


class Handler(BaseHTTPRequestHandler):
    def handle(self) -> None:
        try:
            super().handle()
        except ConnectionError:
            # Closing or reconnecting the desktop can abort a loopback socket.
            # It does not change the queue or stop the processing worker.
            return

    server: LocalServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Request URLs/credentials and private filenames must not reach access logs.
        pass

    def _headers(
        self,
        status: int,
        mime: str,
        size: int | None = None,
        extra: dict[str, str] | None = None,
    ) -> None:
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
        for key, value in (extra or {}).items():
            self.send_header(key, value)
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
            parts = [unquote(part) for part in url.path.strip("/").split("/")]
            if not parts or parts.pop(0) != "v1":
                self._json(404, {"error": "Unknown API version."})
                return
            if parts == ["events"] and self.command == "GET":
                self._events()
                return
            if (
                len(parts) == 3
                and parts[0] == "queue"
                and parts[2] == "video"
                and self.command in {"GET", "HEAD"}
            ):
                job = self.server.engine.store.load(parts[1])
                if job["state"] not in {"done", "failed", "cancelled"}:
                    raise ValueError("Only History videos can be played here.")
                path = Path(job["output"])
                if not path.is_file():
                    path = Path(job["input"]["path"])
                from videoenhancer.service.media import byte_range

                size = path.stat().st_size
                requested = self.headers.get("Range")
                try:
                    start, end = byte_range(requested, size)
                except ValueError:
                    self._headers(
                        416,
                        "video/mp4",
                        0,
                        {"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
                    )
                    return
                headers = {"Accept-Ranges": "bytes"}
                if requested is not None:
                    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
                self._headers(
                    206 if requested is not None else 200,
                    "video/mp4",
                    max(0, end - start + 1),
                    headers,
                )
                if self.command == "HEAD":
                    return
                with path.open("rb") as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining > 0 and (chunk := stream.read(min(64 * 1024, remaining))):
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return
            if (
                len(parts) == 3
                and parts[0] == "queue"
                and parts[2] == "thumbnail"
                and self.command == "GET"
            ):
                path = self.server.engine.thumbnail(parts[1])
                raw = path.read_bytes()
                self._headers(200, "image/jpeg", len(raw))
                self.wfile.write(raw)
                return
            if len(parts) == 4 and parts[0] == "operations" and parts[2] == "stills":
                op_id, name = parts[1], parts[3]
                operation = self.server.engine.operations[op_id]
                allowed = {
                    item["id"] for item in operation.get("result", {}).get("first_looks", [])
                }
                if name not in allowed:
                    raise ValueError("The first look is not ready.")
                path = self.server.engine.home / "previews" / op_id / f"{name}-first-look.png"
                raw = path.read_bytes()
                self._headers(200, "image/png", len(raw))
                self.wfile.write(raw)
                return
            if len(parts) == 4 and parts[0] == "operations" and parts[2] == "files":
                op_id, name = parts[1], parts[3]
                operation = self.server.engine.operations[op_id]
                result = operation.get("result", {})
                allowed = {"original", "enhanced"} if operation["state"] == "done" else set()
                if operation["kind"] == "compare":
                    allowed = {item["id"] for item in result.get("items", [])}
                    if result.get("original"):
                        allowed.add("original")
                if name not in allowed:
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
            result = self.server.engine.dispatch(self.command, parts, value)
            self._json(200, result)
        except ConnectionError:
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
        previous_progress = ""
        heartbeat = time.monotonic()
        while not self.server.engine.stop.is_set():
            try:
                raw = self.server.engine.event_message()
                if raw != previous:
                    self.wfile.write(f"event: update\ndata: {raw}\n\n".encode())
                    previous = raw
                progress = self.server.engine.progress_message()
                if progress and progress != previous_progress:
                    self.wfile.write(f"event: progress\ndata: {progress}\n\n".encode())
                    previous_progress = progress
                if time.monotonic() - heartbeat >= 1:
                    self.wfile.write(b": heartbeat\n\n")
                    heartbeat = time.monotonic()
                self.wfile.flush()
                self.server.engine.stop.wait(1)
            except ConnectionError:
                return
            except Exception:
                from videoenhancer.logging import get_logger

                get_logger(self.server.engine.home).exception("SSE snapshot failed")
                try:
                    self.wfile.write(b"event: error\ndata: Snapshot unavailable. Retrying.\n\n")
                    self.wfile.flush()
                except OSError:
                    return
                self.server.engine.stop.wait(1)

    do_GET = _request
    do_POST = _request
    do_HEAD = _request
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
            from videoenhancer.logging import get_logger

            get_logger(home).info("Service executable: %s", sys.executable)
            if sys.stdout is not None:
                print(f"VideoEnhancer service on 127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever(poll_interval=0.25)
            finally:
                engine.close()
                server.server_close()
                (home / "serve.json").unlink(missing_ok=True)
        return 0
    except RuntimeError as error:
        if sys.stdout is not None:
            print(str(error), flush=True)
        return 1
