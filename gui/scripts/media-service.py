"""Production engine/Range handler with isolated synthetic History for M2 only."""

import copy
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from videoenhancer.config import executable
from videoenhancer.jobs.store import input_identity
from videoenhancer.service import server as transport
from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import save_settings

home, media, template_path, codec = (
    Path(sys.argv[1]),
    Path(sys.argv[2]),
    Path(sys.argv[3]),
    sys.argv[4],
)
if "scratch" not in home.resolve().parts or codec not in {"h264", "av1"}:
    raise ValueError("Use an isolated scratch home and an approved M2 codec.")
home.mkdir(parents=True, exist_ok=True)
if os.environ.get("VE_TEST_ALLOW_LEGACY_ORIGIN") == "1":
    # Process-local comparison override only; production origin policy is unchanged.
    transport.APP_ORIGIN = "app://videoenhancer"

engine = Engine(home)
engine.paused = True
save_settings(
    home,
    {
        "theme": "dark",
        "tour_completed": True,
        "tray_explained": True,
        "cleanup_working_files": False,
        "start_with_windows": False,
    },
)
record = copy.deepcopy(json.loads(template_path.read_text(encoding="utf-8")))
file = media / f"{codec}-1440-large.mp4"
record.update(
    id=file.stem,
    state="done",
    input=input_identity(media / f"{codec}-1080.mp4"),
    output=str(file),
    output_identity=input_identity(file),
)
record["settings"].update(codec=codec, short_side=1440, delete_original_after=False)
for key in (
    "history_hidden_until",
    "history_undo_remaining",
    "remove_on_cancel",
    "storage_move_undo",
):
    record.pop(key, None)
engine.store.save(record)

# Seed the thumbnail cache with a small synthetic image. Do not decode the 1440p
# output as an input to a thumbnail-generation job under the designer's size rule.
stat = file.stat()
key = hashlib.sha256(f"{file.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()
thumbnail = home / "cache" / "thumbnails" / f"{key}.jpg"
thumbnail.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(
    [
        executable("ffmpeg"),
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=gray:s=266x150",
        "-frames:v",
        "1",
        "-threads",
        "2",
        str(thumbnail),
    ],
    check=True,
    capture_output=True,
    creationflags=0x08000000,
)

lock = threading.Lock()
counters = {"media_active": 0, "media_peak": 0, "media_total": 0}
developer_m3 = os.environ.get("VE_DEV_M3_MEDIA") == "1"
tokens = {}


class MeasuringHandler(transport.Handler):
    def _request(self):
        route = urlsplit(self.path).path
        if developer_m3 and route == "/v1/fixture-url" and self.command == "POST":
            if not self._local() or not hmac.compare_digest(
                self.headers.get("Authorization", ""), "Bearer " + self.server.token
            ):
                self._json(403, {"error": "Denied"})
                return
            self.close_connection = True
            token = secrets.token_hex(16)
            with lock:
                tokens.clear()
                tokens[token] = time.monotonic() + 600
            self._json(
                200,
                {"url": f"http://127.0.0.1:{self.server.server_port}/v1/fixture-playback/{token}"},
            )
            return
        if (
            developer_m3
            and route.startswith("/v1/fixture-playback/")
            and self.command in {"GET", "HEAD"}
        ):
            with lock:
                expires = tokens.get(route.rsplit("/", 1)[1], 0)
            if expires > time.monotonic() and not self.headers.get("Origin"):
                # A signed URL is the local prototype's media capability.
                self.headers["Origin"] = transport.APP_ORIGIN
            if not self._local() or expires <= time.monotonic():
                self._json(403, {"error": "Expired or invalid media URL"})
                return
            self.path = f"/v1/queue/{file.stem}/video"
            if self.headers.get("Authorization"):
                del self.headers["Authorization"]
            self.headers["Authorization"] = "Bearer " + self.server.token
        is_media = urlsplit(self.path).path == f"/v1/queue/{file.stem}/video" and self.command in {
            "GET",
            "HEAD",
        }
        if not is_media:
            return super()._request()
        with lock:
            counters["media_active"] += 1
            counters["media_total"] += 1
            counters["media_peak"] = max(counters["media_peak"], counters["media_active"])
        try:
            return super()._request()
        finally:
            with lock:
                counters["media_active"] -= 1
                print(json.dumps(counters), flush=True)


MeasuringHandler.do_GET = MeasuringHandler._request
MeasuringHandler.do_HEAD = MeasuringHandler._request
MeasuringHandler.do_POST = MeasuringHandler._request
with transport.service_lock(home):
    server = transport.LocalServer(engine)
    server.RequestHandlerClass = MeasuringHandler
    engine.start()
    transport.discovery(home, server.server_port, server.token)
    print(json.dumps({"ready": True}), flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        engine.close()
        server.server_close()
        (home / "serve.json").unlink(missing_ok=True)
