"""Metadata, bounded header probing and quality choices for explicit video links."""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import socket
import subprocess
import threading
import time
import unicodedata
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.estimate import estimate_job, predict_segment
from videoenhancer.jobs.checks import source_warning
from videoenhancer.jobs.segments import plan_segments
from videoenhancer.jobs.store import (
    JobStore,
    input_identity,
    load_machine_profile,
    require_disk_space,
)
from videoenhancer.media.probe import rational, target_rate
from videoenhancer.models.registry import ModelRegistry, selected_models
from videoenhancer.schedule.controller import _kill_process_tree
from videoenhancer.service.link_tools import ToolManager
from videoenhancer.service.settings import write_json

ENCRYPTION_ERROR = (
    "This site would send the video without encryption, so VideoEnhancer won't download it."
)
UNKNOWN_SIZE = (
    "VideoEnhancer can't read this video's size before downloading. "
    "It is checked after the download. If it is larger than 1080p or HDR, "
    "the job stops and the downloaded file is kept."
)
SIGN_IN_ERROR = "This video needs you to sign in to the site. Sign-in is not supported yet."


def video_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 16384 or any(ord(char) < 32 for char in value):
        raise ValueError("Paste an http or https video link.")
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Paste an http or https video link without sign-in details.")
    if parsed.port is not None and not 0 < parsed.port < 65536:
        raise ValueError("Invalid video-link port.")
    return urlunsplit(parsed)


def require_encrypted_format(original: str, selected: dict[str, Any]) -> None:
    for key in ("url", "manifest_url", "fragment_base_url"):
        if selected.get(key):
            target = video_url(selected[key])
            if urlsplit(original).scheme == "https" and urlsplit(target).scheme == "http":
                raise ValueError(ENCRYPTION_ERROR)
    base = selected.get("fragment_base_url") or selected.get("url") or original
    for fragment in selected.get("fragments") or []:
        path = fragment.get("url") or fragment.get("path")
        if path:
            target = video_url(urljoin(base, path))
            if urlsplit(original).scheme == "https" and urlsplit(target).scheme == "http":
                raise ValueError(ENCRYPTION_ERROR)


def thumbnail_url(original: str, value: str) -> str:
    target = video_url(value)
    if urlsplit(target).scheme == "http" and urlsplit(original).scheme != "http":
        raise ValueError("The thumbnail transport is not allowed.")
    parts = urlsplit(target)
    addresses = socket.getaddrinfo(
        parts.hostname,
        parts.port or (443 if parts.scheme == "https" else 80),
        type=socket.SOCK_STREAM,
    )
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("The thumbnail address is not public.")
    return target


def public_socket(address, timeout=None, source_address=None):
    """Connect to the validated addresses, without a second hostname lookup."""
    addresses = socket.getaddrinfo(*address, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("The thumbnail address is not public.")
    last_error = None
    for family, kind, protocol, _, target in addresses:
        connection = socket.socket(family, kind, protocol)
        try:
            if isinstance(timeout, (int, float)) or timeout is None:
                connection.settimeout(timeout)
            if source_address:
                connection.bind(source_address)
            connection.connect(target)
            return connection
        except OSError as error:
            last_error = error
            connection.close()
    raise OSError("Could not connect to the public thumbnail address.") from last_error


def public_http(connection_type, host, **kwargs):
    connection = connection_type(host, **kwargs)
    connection._create_connection = public_socket
    return connection


class PublicHTTP(urllib.request.HTTPHandler):
    def http_open(self, request):
        return self.do_open(
            lambda host, **kw: public_http(http.client.HTTPConnection, host, **kw), request
        )


class PublicHTTPS(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(
            lambda host, **kw: public_http(http.client.HTTPSConnection, host, **kw),
            request,
            context=getattr(self, "_context", None),
        )


def safe_filename(title: str, video_id: str) -> str:
    def clean(value: str, limit: int) -> str:
        value = unicodedata.normalize("NFC", str(value))
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
        value = (
            value.encode("utf-16-le")[: limit * 2].decode("utf-16-le", errors="ignore").rstrip(" .")
        )
        if re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", value):
            value = "_" + value
        return value or "video"

    return f"{clean(title, 120)} [{clean(video_id, 40)}]"


def run_tool(
    command: list[str],
    cancelled: Callable[[], bool],
    process_changed: Callable[[proc.Popen | None], None],
    *,
    timeout: float = 600,
    line: Callable[[str], None] | None = None,
    environment: dict[str, str] | None = None,
    limit: int = 128_000_000,
) -> tuple[str, str]:
    if cancelled():
        raise InterruptedError("Link operation cancelled.")
    output = bytearray()
    overflow = threading.Event()
    reader_errors: list[Exception] = []
    with proc.Popen(
        command,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    ) as child:
        process_changed(child)
        assert child.stdout is not None
        stream = child.stdout
        read = getattr(stream, "read1", stream.read)

        def drain() -> None:
            pending = b""
            try:
                while block := read(65536):
                    if len(output) + len(block) > limit:
                        overflow.set()
                        break
                    output.extend(block)
                    if line:
                        pending += block
                        while b"\n" in pending:
                            packet, pending = pending.split(b"\n", 1)
                            line(packet.decode("utf-8", errors="replace"))
                        if len(pending) > 65536:
                            pending = pending[-65536:]
            except Exception as error:
                reader_errors.append(error)
            finally:
                stream.close()

        reader = threading.Thread(target=drain, daemon=True, name="link-tool-stdout")
        reader.start()
        deadline = time.monotonic() + timeout
        try:
            while child.poll() is None:
                if reader_errors:
                    raise reader_errors[0]
                if cancelled():
                    raise InterruptedError("Link operation cancelled.")
                if overflow.is_set():
                    raise ValueError("The site's response is too large.")
                if time.monotonic() >= deadline:
                    raise TimeoutError("The video-link request took too long.")
                time.sleep(0.05)
            reader.join(timeout=2)
            if reader_errors:
                raise reader_errors[0]
            if reader.is_alive():
                raise ValueError("The link tool did not finish its response.")
            child.stdout = None
            if cancelled():
                raise InterruptedError("Link operation cancelled.")
            if overflow.is_set():
                raise ValueError("The site's response is too large.")
            _, diagnostics_raw = child.communicate(timeout=2)
            diagnostics = (
                diagnostics_raw.decode("utf-8", errors="replace")
                if isinstance(diagnostics_raw, bytes)
                else (diagnostics_raw or "")
            )
            if child.returncode:
                raise ValueError(
                    diagnostics.strip() or "The site did not provide a downloadable video."
                )
            return output.decode("utf-8", errors="replace"), diagnostics
        finally:
            if child.poll() is None:
                _kill_process_tree(child.pid)
            child.wait(timeout=10)
            reader.join(timeout=2)
            process_changed(None)


def header_probe(
    original: str,
    item: dict[str, Any],
    cancelled: Callable[[], bool],
    process_changed: Callable[[proc.Popen | None], None],
) -> dict[str, Any] | None:
    require_encrypted_format(original, item)
    allowed = "https,tls,tcp" + (",http" if urlsplit(original).scheme == "http" else "")
    headers = []
    for key, value in item.get("http_headers", {}).items():
        if (
            not isinstance(key, str)
            or not isinstance(value, str)
            or not re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+", key)
            or "\r" in value
            or "\n" in value
        ):
            raise ValueError("The site returned invalid video request headers.")
        headers.append(f"{key}: {value}\r\n")
    command = [
        executable("ffprobe"),
        "-v",
        "error",
        "-protocol_whitelist",
        allowed,
        "-rw_timeout",
        "10000000",
        "-probesize",
        "1000000",
        "-analyzeduration",
        "1000000",
    ]
    if headers:
        command += ["-headers", "".join(headers)]
    command += ["-show_streams", "-show_format", "-of", "json", video_url(item["url"])]
    try:
        raw, _ = run_tool(command, cancelled, process_changed, timeout=20, limit=2_000_000)
        info = json.loads(raw)
        stream = next(
            s
            for s in info["streams"]
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        )
        width, height = int(stream["width"]), int(stream["height"])
        rotation = round(float(stream.get("tags", {}).get("rotate", 0))) % 360
        for side in stream.get("side_data_list", []):
            if "rotation" in side:
                rotation = round(float(side["rotation"])) % 360
        if rotation not in {0, 90, 180, 270}:
            return None
        sar = rational(stream.get("sample_aspect_ratio", "1:1"), Fraction(1))
        if sar <= 0:
            return None
        square_width = max(1, round(width * sar))
        display = (height, square_width) if rotation in {90, 270} else (square_width, height)
        rate = rational(stream.get("avg_frame_rate")) or rational(stream.get("r_frame_rate"))
        duration = float(stream.get("duration") or info.get("format", {}).get("duration") or 0)
        if not all(math.isfinite(v) and v > 0 for v in (*display, duration)):
            return None
        audio = next((s for s in info["streams"] if s.get("codec_type") == "audio"), {})
        return dict(
            width=display[0],
            height=display[1],
            fps=float(rate) if rate > 0 else None,
            duration=duration,
            vcodec=stream.get("codec_name"),
            acodec=audio.get("codec_name", "none"),
            color_transfer=stream.get("color_transfer"),
            dynamic_range="HDR"
            if stream.get("color_transfer") in {"smpte2084", "arib-std-b67"}
            else "SDR",
            rotation=rotation,
        )
    except InterruptedError:
        raise
    except (ValueError, TimeoutError, KeyError, StopIteration, TypeError) as error:
        if (
            re.search(r"Protocol\s+'http'\s+not on whitelist", str(error), re.I)
            and urlsplit(original).scheme == "https"
        ):
            raise ValueError(ENCRYPTION_ERROR) from error
        return None


def format_reason(item: dict[str, Any]) -> str | None:
    if item.get("has_drm"):
        return "DRM-protected videos are not supported."
    if item.get("dynamic_range") not in {None, "SDR"} or item.get("color_transfer") in {
        "smpte2084",
        "arib-std-b67",
    }:
        return "HDR is not supported yet"
    if item.get("width") and item.get("height"):
        return source_warning(item)
    return None


def best_format(formats: list[dict[str, Any]], output: str | int) -> dict[str, Any] | None:
    supported = [
        item for item in formats if not format_reason(item) and not item.get("transport_error")
    ]
    known = [item for item in supported if item.get("width") and item.get("height")]
    target = 1080 if output == "keep" else min(1080, int(output))
    below = [item for item in known if min(item["width"], item["height"]) <= target]
    if below:
        return max(
            below,
            key=lambda item: (
                min(item["width"], item["height"]),
                item.get("fps") or 0,
                item.get("tbr") or item.get("vbr") or 0,
            ),
        )
    return supported[0] if supported else None


def format_estimate(
    item: dict[str, Any], settings: dict[str, Any], home: Path, *, profile: Any = ...
) -> dict[str, Any] | None:
    if not all(item.get(k) for k in ("width", "height", "fps", "duration")):
        return None
    rate = target_rate(rational(item["fps"]))
    media = dict(
        width=item["width"],
        height=item["height"],
        display_width=item["width"],
        display_height=item["height"],
        cfr_fps=str(rate),
        frame_count=max(1, round(float(rate) * item["duration"])),
        duration=item["duration"],
    )
    registry = ModelRegistry(home)
    identities = {}
    for task, model_id in selected_models(settings, media).items():
        try:
            identities[task] = registry.snapshot(model_id, task, download=False)
        except ValueError:
            pass
    if profile is ...:
        profile = load_machine_profile(home, backend=settings["backend"], models=identities)
    frames = media["frame_count"]
    per_frame = predict_segment(media, settings, frames, profile) / frames
    job = dict(
        media=media,
        settings=settings,
        segments=plan_segments(
            media, [], predicted_seconds_per_frame=per_frame, target_seconds=180
        ),
        machine_profile=profile,
        correction_factor=1,
    )
    return estimate_job(job).to_dict()


class VideoLinks:
    def __init__(self, home: Path, tools: ToolManager):
        self.home, self.tools = home, tools
        self.hardware: dict[str, Any] | None = None
        self._profiles: dict[str, Any] = {}
        self._profile_lock = threading.Lock()

    def profile(self, settings: dict[str, Any], media: dict[str, Any]) -> Any:
        with self._profile_lock:
            if self.hardware is None:
                from videoenhancer.logging import environment_info

                self.hardware = environment_info()
            registry = ModelRegistry(self.home)
            identities = {}
            for task, model_id in selected_models(settings, media).items():
                try:
                    identities[task] = registry.snapshot(model_id, task, download=False)
                except ValueError:
                    pass
            key = json.dumps(
                [
                    settings["backend"],
                    self.hardware.get("gpu"),
                    self.hardware.get("driver"),
                    identities,
                ],
                sort_keys=True,
            )
            if key not in self._profiles:
                self._profiles[key] = load_machine_profile(
                    self.home,
                    backend=settings["backend"],
                    gpu_name=self.hardware.get("gpu") or "",
                    driver=self.hardware.get("driver") or "",
                    models=identities,
                )
            return self._profiles[key]

    def estimate(self, item: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any] | None:
        if not all(item.get(k) for k in ("width", "height", "fps", "duration")):
            return None
        media = dict(item, cfr_fps=str(target_rate(rational(item["fps"]))))
        return format_estimate(item, settings, self.home, profile=self.profile(settings, media))

    def cleanup_download(self, job: dict[str, Any]) -> None:
        if not job.get("source") or job["source"].get("downloaded_at"):
            return
        if not re.fullmatch(r"[0-9a-f]{32}", job["id"]):
            raise ValueError("Invalid download job ID.")
        folder = Path(job["input"]["path"]).parent
        prefix = f".ve-{job['id']}."
        for path in folder.iterdir() if folder.is_dir() else []:
            if path.name.startswith(prefix) and path.is_file() and not path.is_symlink():
                path.unlink()

    def arguments(self) -> tuple[list[str], dict[str, str]]:
        downloader = self.tools.executable("yt-dlp")
        deno = self.tools.executable("deno")
        environment = {**os.environ, "DENO_DIR": str(self.home / "tools/deno/cache")}
        return [
            str(downloader),
            "--ignore-config",
            "--cache-dir",
            str(self.home / "tools/yt-dlp/cache"),
            "--no-plugin-dirs",
            "--no-js-runtimes",
            "--js-runtimes",
            f"deno:{deno}",
            "--ffmpeg-location",
            str(Path(executable("ffmpeg")).parent),
        ], environment

    def save_check(self, check_id: str, result: dict[str, Any]) -> dict[str, Any]:
        write_json(self.home / "previews" / check_id / "link-metadata.json", result)
        return {key: value for key, value in result.items() if key != "raw_entries"}

    def metadata(self, check_id: str, entry_key: str) -> tuple[str, dict[str, Any]]:
        if not re.fullmatch(r"[0-9a-f]{32}", check_id):
            raise ValueError("Check the video link again.")
        saved = json.loads(
            (self.home / "previews" / check_id / "link-metadata.json").read_text(encoding="utf-8")
        )
        entry = next((row["info"] for row in saved["raw_entries"] if row["key"] == entry_key), None)
        if entry is None:
            raise ValueError("Check the video link again.")
        return saved["url"], entry

    def selected(
        self, original: str, entry: dict[str, Any], format_id: str
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        video = next(
            (
                item
                for item in entry["formats"]
                if str(item.get("format_id")) == format_id and item.get("vcodec") != "none"
            ),
            None,
        )
        if not video:
            raise ValueError("Choose an available video quality.")
        reason = video.get("transport_error") or format_reason(video)
        if reason:
            raise ValueError(reason)
        require_encrypted_format(original, video)
        audio = next(
            (
                item
                for item in reversed(entry["formats"])
                if item.get("vcodec") == "none"
                and item.get("acodec") != "none"
                and not item.get("has_drm")
            ),
            None,
        )
        if audio:
            require_encrypted_format(original, audio)
        return video, audio

    def reusable(self, entry: dict[str, Any], store: JobStore) -> dict[str, Any] | None:
        extractor = entry.get("extractor_key") or entry.get("extractor") or "Generic"
        for job in reversed(store.queue_jobs()):
            source = job.get("source", {})
            stored_extractor = source.get("extractor_key") or source.get("extractor", "")
            if stored_extractor.lower() != str(extractor).lower() or source.get("id") != str(
                entry.get("id")
            ):
                continue
            if str(extractor).lower() == "generic":

                def normalized(value: str) -> str:
                    parts = urlsplit(value)
                    return urlunsplit(
                        (parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, "")
                    )

                if normalized(source.get("url", "")) != normalized(entry.get("webpage_url", "")):
                    continue
                if (
                    entry.get("timestamp") is not None
                    and source.get("timestamp") is not None
                    and entry["timestamp"] != source["timestamp"]
                ):
                    continue
                media = job.get("media", {})
                formats = entry.get("formats") or [entry]
                matched = False
                for item in formats:
                    duration = item.get("duration") or entry.get("duration")
                    if not all(
                        (item.get("width"), item.get("height"), duration, media.get("duration"))
                    ):
                        continue
                    if (item["width"], item["height"]) == (
                        media.get("display_width", media.get("width")),
                        media.get("display_height", media.get("height")),
                    ) and abs(float(duration or 0) - float(media["duration"])) <= 0.5:
                        matched = True
                        break
                if not matched:
                    continue
            try:
                path = Path(job["input"]["path"])
                if path.is_file() and input_identity(path) == job["input"]:
                    return dict(
                        job_id=job["id"],
                        date=source.get("downloaded_at", job.get("created_at")),
                        path=str(path),
                        media=job.get("media", {}),
                    )
            except OSError:
                pass
        return None

    def thumbnail(self, check_id: str, entry_key: str) -> tuple[str, bytes]:
        original, entry = self.metadata(check_id, entry_key)
        target = thumbnail_url(original, entry["thumbnail"])
        key = hashlib.sha256(target.encode()).hexdigest()
        folder = self.home / "cache/link-thumbnails"
        folder.mkdir(parents=True, exist_ok=True)
        cached = folder / key
        if cached.is_file():
            data = cached.read_bytes()
        else:

            class HttpRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    thumbnail_url(original, newurl)
                    return super().redirect_request(req, fp, code, msg, headers, newurl)

            request = urllib.request.Request(target, headers={"User-Agent": "VideoEnhancer"})
            with urllib.request.build_opener(PublicHTTP(), PublicHTTPS(), HttpRedirect()).open(
                request, timeout=10
            ) as response:
                thumbnail_url(original, response.url)
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("The thumbnail is too large.")
        mime = (
            "image/jpeg"
            if data.startswith(b"\xff\xd8\xff")
            else "image/png"
            if data.startswith(b"\x89PNG\r\n\x1a\n")
            else "image/webp"
            if data.startswith(b"RIFF") and data[8:12] == b"WEBP"
            else "image/gif"
            if data.startswith((b"GIF87a", b"GIF89a"))
            else None
        )
        if not mime:
            raise ValueError("The site did not return a supported thumbnail.")
        if not cached.exists():
            cached.write_bytes(data)
        return mime, data

    def download(
        self,
        job: dict[str, Any],
        cancelled: Callable[[], bool],
        process_changed: Callable[[proc.Popen | None], None],
        progress: Callable[[dict[str, Any]], None],
    ) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", job["id"]):
            raise ValueError("Invalid download job ID.")
        source = job["source"]
        final = Path(job["input"]["path"])
        if (
            source.get("downloaded_at")
            and final.is_file()
            and input_identity(final) == job["input"]
        ):
            return final
        entry_url = source.get("entry_url") or (
            source.get("url") if source.get("url") != source["request_url"] else None
        )
        result = self.check(
            entry_url or source["request_url"],
            job["settings"],
            cancelled,
            process_changed,
            lambda packet: progress({"phase": packet["phase"]}),
            **({"single": True} if entry_url else {}),
        )
        entry = next(
            (
                row["info"]
                for row in result["raw_entries"]
                if str(row["info"].get("id")) == source["id"]
                and str(
                    row["info"].get("extractor_key") or row["info"].get("extractor") or "generic"
                ).lower()
                == str(source.get("extractor_key") or source["extractor"]).lower()
            ),
            None,
        )
        if entry is None:
            raise ValueError("This video is no longer available at the checked link.")
        video, audio = self.selected(result["url"], entry, source["format"])
        selected = [video] + ([audio] if audio else [])
        total_estimate = sum(
            float(item.get("filesize") or item.get("filesize_approx") or 0) for item in selected
        )
        require_disk_space(final.parent, max(1, int(total_estimate)), copies=2)
        safe_keys = {
            "url",
            "manifest_url",
            "fragment_base_url",
            "fragments",
            "http_headers",
            "ext",
            "protocol",
            "width",
            "height",
            "fps",
            "vcodec",
            "acodec",
            "tbr",
            "abr",
            "vbr",
            "asr",
            "audio_channels",
            "filesize",
            "filesize_approx",
            "dynamic_range",
        }
        formats = []
        components = [(video, "video")]
        if audio:
            components.append((audio, "audio"))
        for item, name in components:
            clean = {key: value for key, value in item.items() if key in safe_keys}
            chunk = item.get("downloader_options", {}).get("http_chunk_size")
            if type(chunk) is int and chunk > 0:
                clean["downloader_options"] = {"http_chunk_size": chunk}
            clean["url"] = video_url(clean["url"])
            clean["format_id"] = name
            if not re.fullmatch(r"[A-Za-z0-9]{1,10}", str(clean.get("ext", ""))):
                clean["ext"] = "mp4" if name == "video" else "m4a"
            for fragment in clean.get("fragments", []):
                fragment_url = fragment.get("url") or fragment.get("path")
                if fragment_url:
                    video_url(urljoin(clean.get("fragment_base_url") or clean["url"], fragment_url))
            if name == "video" and audio:
                clean["acodec"] = "none"
            formats.append(clean)
        work = self.home / "jobs" / job["id"]
        info_file = work / "download-info.json"
        write_json(
            info_file,
            dict(
                id=job["id"],
                title=job["id"],
                extractor=source["extractor"],
                extractor_key=entry.get("extractor_key") or "Generic",
                webpage_url=source["url"],
                duration=entry.get("duration"),
                formats=formats,
            ),
        )
        temporary = final.parent / f".ve-{job['id']}"
        completed = Path(str(temporary) + ".mkv")
        completed.unlink(missing_ok=True)
        args, environment = self.arguments()
        template = (
            'download:VE_PROGRESS:{"downloaded_bytes":%(progress.downloaded_bytes|0)s,'
            '"total_bytes":%(progress.total_bytes|0)s,'
            '"total_bytes_estimate":%(progress.total_bytes_estimate|0)s,'
            '"speed":%(progress.speed|0)s,"eta":%(progress.eta|0)s,'
            '"filename":%(progress.filename)j,"status":%(progress.status)j}'
        )
        files: dict[str, dict[str, Any]] = {}
        last_percent = 0.0

        def packet(line: str) -> None:
            nonlocal last_percent
            if not line.startswith("VE_PROGRESS:"):
                return
            try:
                item = json.loads(line.removeprefix("VE_PROGRESS:"))
            except (ValueError, TypeError):
                return
            files[str(item.get("filename"))] = item
            done = sum(float(row.get("downloaded_bytes") or 0) for row in files.values())
            total = max(
                total_estimate,
                sum(
                    float(row.get("total_bytes") or row.get("total_bytes_estimate") or 0)
                    for row in files.values()
                ),
            )
            speed = float(item.get("speed") or 0)
            remaining = max(0, total - done) / speed if total and speed else None
            last_percent = max(last_percent, min(98, done / total * 98)) if total else last_percent
            require_disk_space(final.parent, max(1, int(max(0, total - done))), copies=2)
            progress(
                dict(
                    phase="Downloading",
                    percent=last_percent if total else None,
                    bytes=done,
                    total_bytes=total or None,
                    bytes_per_second=speed or None,
                    remaining_seconds=remaining,
                    ready_at=datetime.fromtimestamp(time.time() + remaining, UTC).isoformat()
                    if remaining is not None
                    else None,
                )
            )

        run_tool(
            [
                *args,
                "--load-info-json",
                str(info_file),
                "--no-simulate",
                "--no-playlist",
                "--continue",
                "--no-overwrites",
                "--newline",
                "--progress",
                "--progress-template",
                template,
                "--merge-output-format",
                "mkv",
                "--remux-video",
                "mkv",
                "-f",
                "video+audio" if audio else "video",
                "-o",
                str(temporary) + ".%(ext)s",
                "--retries",
                "0",
                "--fragment-retries",
                "0",
                "--abort-on-unavailable-fragments",
            ],
            cancelled,
            process_changed,
            line=packet,
            environment=environment,
            timeout=86400,
        )
        completed = Path(str(temporary) + ".mkv")
        if cancelled():
            raise InterruptedError("Video download paused.")
        if not completed.is_file():
            raise ValueError("The download did not produce its finished video.")
        expected = video.get("duration") or entry.get("duration")
        if expected:
            from videoenhancer.media.probe import probe

            actual = float(
                probe(completed, allow_hdr=True, read_timeline=False).to_dict()["duration"]
            )
            if float(expected) - actual > max(1, float(expected) * 0.01):
                raise ValueError(
                    f"The download is incomplete ({actual:g} s of {float(expected):g} s). "
                    "Retry the download."
                )
        if final.exists():
            raise ValueError("A file now exists at the download destination. It was kept.")
        completed.rename(final)
        source["timestamp"] = entry.get("timestamp")
        return final

    def check(
        self,
        value: str,
        settings: dict[str, Any],
        cancelled: Callable[[], bool],
        process_changed: Callable[[proc.Popen | None], None],
        progress: Callable[[dict[str, Any]], None],
        *,
        single: bool = False,
    ) -> dict[str, Any]:
        url = video_url(value)
        args, environment = self.arguments()
        try:
            raw, _ = run_tool(
                [
                    *args,
                    "-J",
                    *(["--no-playlist"] if single else ["--playlist-end", "200"]),
                    "--",
                    url,
                ],
                cancelled,
                process_changed,
                environment=environment,
            )
            metadata = json.loads(raw)
        except ValueError as error:
            text = " ".join(str(error).split())
            if re.search(r"sign.?in|log.?in|authentication|403|cookies", text, re.I):
                raise ValueError(SIGN_IN_ERROR) from error
            installed = self.tools.status()["installed"].get("yt-dlp", {})
            released = datetime.fromisoformat(
                installed.get("released", datetime.now(UTC).isoformat()).replace("Z", "+00:00")
            )
            hint = (
                " Update link tools."
                if (datetime.now(UTC) - released).total_seconds() > 60 * 86400
                else ""
            )
            raise ValueError(text[-400:] + hint) from error
        entries = (
            metadata.get("entries")
            if metadata.get("_type") in {"playlist", "multi_video"}
            else [metadata]
        )
        cards = []
        raw_entries = []
        for index, entry in enumerate((entries or [])[:200]):
            if cancelled():
                raise InterruptedError("Link check cancelled.")
            if not entry:
                continue
            progress(dict(phase=f"Checking video {index + 1}", checked=index + 1))
            key = str(index)
            if entry.get("_type") in {"playlist", "multi_video"}:
                cards.append(
                    dict(
                        key=key,
                        title=entry.get("title", "List"),
                        error=(
                            "This link is a list of lists. Paste the link of one list, "
                            "for example a channel's Videos tab."
                        ),
                    )
                )
                continue
            if entry.get("is_live") or entry.get("live_status") in {
                "is_live",
                "is_upcoming",
                "post_live",
            }:
                cards.append(
                    dict(
                        key=key,
                        title=entry.get("title", "Video"),
                        error="Live streams and upcoming videos are not supported.",
                    )
                )
                continue
            formats = []
            for original in entry.get("formats") or [entry]:
                if original.get("vcodec") == "none":
                    continue
                item = {
                    **original,
                    "duration": entry.get("duration") or original.get("duration"),
                    "http_headers": original.get("http_headers") or entry.get("http_headers", {}),
                }
                item.setdefault("format_id", "direct")
                try:
                    if not item.get("url"):
                        raise ValueError("This video has no usable download URL.")
                    video_url(item["url"])
                    require_encrypted_format(url, item)
                    if not all(
                        item.get(k) for k in ("width", "height", "duration")
                    ) and not format_reason(item):
                        extra = header_probe(url, item, cancelled, process_changed)
                        if extra:
                            item.update(extra)
                except ValueError as error:
                    item["transport_error"] = str(error)
                formats.append(item)
            entry["formats"] = formats + [
                f for f in entry.get("formats", []) if f.get("vcodec") == "none"
            ]
            selected = best_format(formats, settings["short_side"])
            card: dict[str, Any] = dict(
                key=key,
                title=entry.get("title") or entry.get("id") or "Video",
                site=entry.get("extractor_key") or entry.get("extractor") or urlsplit(url).hostname,
                uploader=entry.get("uploader") or entry.get("creator") or "",
                duration=entry.get("duration"),
                thumbnail=bool(entry.get("thumbnail")),
                formats=[],
                selected=selected.get("format_id") if selected else None,
            )
            for item in formats:
                if (
                    item.get("width")
                    and item.get("height")
                    and min(item["width"], item["height"]) > 1080
                ):
                    continue
                reason = item.get("transport_error") or format_reason(item)
                audio_size = 0
                if not reason:
                    try:
                        _, audio = self.selected(url, entry, str(item["format_id"]))
                        if audio:
                            audio_size = int(
                                audio.get("filesize") or audio.get("filesize_approx") or 0
                            )
                    except ValueError as error:
                        reason = str(error)
                        item["transport_error"] = reason
                video_size = item.get("filesize") or item.get("filesize_approx")
                card["formats"].append(
                    dict(
                        id=str(item.get("format_id", "direct")),
                        width=item.get("width"),
                        height=item.get("height"),
                        fps=item.get("fps"),
                        codec=item.get("vcodec") or "unknown",
                        dynamic_range=item.get("dynamic_range") or "SDR",
                        bytes=int(video_size) + audio_size if video_size else None,
                        estimate=self.estimate(item, settings) if not reason else None,
                        disabled=reason,
                        unknown_size=not all(item.get(k) for k in ("width", "height", "duration")),
                    )
                )
            if selected and selected.get("transport_error"):
                selected = None
            card["selected"] = selected.get("format_id") if selected else None
            if not formats:
                card["error"] = "The site did not provide a downloadable video."
            elif not selected:
                card["error"] = next(
                    (
                        f.get("transport_error") or format_reason(f)
                        for f in formats
                        if f.get("transport_error") or format_reason(f)
                    ),
                    "No supported video format was found.",
                )
            else:
                card["duration"] = selected.get("duration")
                card["unknown_size"] = not all(
                    selected.get(k) for k in ("width", "height", "duration")
                )
            cards.append(card)
            raw_entries.append(dict(key=key, info=entry))
        return dict(
            url=url,
            title=metadata.get("title"),
            playlist=metadata.get("_type") in {"playlist", "multi_video"},
            entries=cards,
            raw_entries=raw_entries,
        )
