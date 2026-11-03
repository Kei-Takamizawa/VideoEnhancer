"""CPU-only, interruptible library image sidecars; never retain decoded frames."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import threading
import time

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.remote import faces
from videoenhancer.service.settings import write_json

MAX_BYTES = 8_000_000


def current_images(index, signature):
    return (
        index.get("signature") == signature
        and index.get("version") == faces.VERSION
        and index.get("face_ready") is True
    )


def storyboard_plan(duration, width, height):
    interval = max(2, duration / 200)
    return (
        interval,
        160,
        max(2, round(160 * height / width / 2) * 2),
        max(1, math.ceil(duration / interval)),
    )


class Thumbnails:
    def __init__(self, library):
        self.library = library
        self.stop = threading.Event()
        self.busy = threading.Event()
        self.idle = threading.Event()
        self.idle.set()
        self.gate = threading.Lock()
        self.thread = threading.Thread(target=self._watch, name="library-images", daemon=True)

    def pause(self):
        with self.gate:
            self.busy.set()
        self.idle.wait()

    def resume(self):
        self.busy.clear()

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=20)

    def _cancelled(self):
        return self.stop.is_set() or self.busy.is_set()

    def _run(self, args):
        command = [
            executable("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-threads",
            "1",
            "-filter_threads",
            "1",
            *args,
        ]
        proc.run_cancellable(command, self._cancelled, timeout=600)

    def _folder(self, identifier):
        root = self.library.folder / ".videoenhancer"
        root.mkdir(exist_ok=True)
        if root.is_symlink() or root.is_junction():
            raise ValueError("Invalid image folder.")
        folder = root / identifier
        if folder.is_symlink() or folder.is_junction():
            raise ValueError("Invalid image folder.")
        return folder

    @staticmethod
    def signature(info):
        return hashlib.sha256(f"{info.st_size}:{info.st_mtime_ns}".encode()).hexdigest()

    def read(self, identifier, name):
        with self.library._lock:
            _, info = self.library._find(identifier)
            folder = self._folder(identifier)
            index = json.loads((folder / "storyboard.json").read_text(encoding="utf-8"))
            signature = self.signature(info)
            if index.get("signature") != signature:
                raise FileNotFoundError("Images are not ready.")
            target = folder / name
            if target.is_symlink() or target.is_junction():
                raise FileNotFoundError("Images are not ready.")
            data = target.read_bytes()
            return data, '"' + hashlib.sha256(data).hexdigest() + '"'

    def cleanup(self):
        with self.library._lock:
            identifiers = {self.library._identifier(path) for path, _ in self.library._entries()}
            root = self.library.folder / ".videoenhancer"
            if not root.exists():
                return
            if root.is_symlink() or root.is_junction():
                raise ValueError("Invalid image folder.")
            for folder in root.iterdir():
                if (
                    folder.is_dir()
                    and not folder.is_symlink()
                    and not folder.is_junction()
                    and folder.name not in identifiers
                ):
                    shutil.rmtree(folder)

    def generate(self, identifier):
        with self.library.acquire(identifier):
            path, info = self.library._find(identifier)
            metadata = self.library._probe(path)
            duration = metadata["duration"]
            interval, width, height, frames = storyboard_plan(
                duration, metadata["width"], metadata["height"]
            )
            folder = self._folder(identifier)
            staging = folder.with_name(identifier + ".pending")
            if staging.is_symlink() or staging.is_junction():
                raise ValueError("Invalid image folder.")
            staging.mkdir(exist_ok=True)
            try:
                if self._cancelled():
                    raise InterruptedError("Poster interrupted.")
                selected, face_ready, elapsed = None, False, 0.0
                try:
                    selected, elapsed = faces.select(
                        path, metadata, self.library.home, self._cancelled
                    )
                    face_ready = True
                except InterruptedError:
                    raise
                except Exception:
                    # Optional inference backends use their own exception hierarchy.
                    # Publish the usable R1c poster now; the watcher retries later.
                    pass
                # A small gray sample measures luma without an image-library dependency.
                position = selected["time"] if selected else duration * 0.1
                for attempt in range(0 if selected else 4):
                    sample = staging / "luma.raw"
                    self._run(
                        [
                            "-ss",
                            str(position),
                            "-protocol_whitelist",
                            "file,pipe",
                            "-i",
                            str(path),
                            "-frames:v",
                            "1",
                            "-vf",
                            "scale=16:16,format=gray",
                            "-f",
                            "rawvideo",
                            str(sample),
                        ]
                    )
                    pixels = sample.read_bytes()
                    sample.unlink()
                    if pixels and sum(pixels) / len(pixels) >= 16 or attempt == 3:
                        break
                    position = min(max(0, duration - 0.05), position + max(1, duration * 0.1))
                scale = "scale='if(gte(iw,ih),-2,270)':'if(gte(iw,ih),270,-2)'"
                self._run(
                    [
                        "-ss",
                        str(position),
                        "-protocol_whitelist",
                        "file,pipe",
                        "-i",
                        str(path),
                        "-frames:v",
                        "1",
                        "-vf",
                        scale,
                        "-q:v",
                        "4",
                        str(staging / "poster.jpg"),
                    ]
                )
                write_json(
                    staging / "poster.json",
                    {
                        **(selected or dict(time=position, N=0, face_count=0, unmasked_count=0)),
                        "version": faces.VERSION,
                        "face_ready": face_ready,
                        "seconds": elapsed,
                    },
                )
                # Keyframe-only decoding is accurate enough only when no gap exceeds the interval.
                keyframe_path = staging / "keyframes.json"
                proc.run_cancellable(
                    [
                        executable("ffprobe"),
                        "-v",
                        "error",
                        "-protocol_whitelist",
                        "file,pipe",
                        "-skip_frame",
                        "nokey",
                        "-select_streams",
                        "v:0",
                        "-show_frames",
                        "-show_entries",
                        "frame=best_effort_timestamp_time",
                        "-of",
                        "json",
                        "-o",
                        str(keyframe_path),
                        str(path),
                    ],
                    self._cancelled,
                    timeout=60,
                )
                keyframes = json.loads(keyframe_path.read_text(encoding="utf-8"))
                keyframe_path.unlink()
                stamps = [
                    float(row["best_effort_timestamp_time"])
                    for row in keyframes["frames"]
                    if "best_effort_timestamp_time" in row
                ]
                gaps = [b - a for a, b in zip([0, *stamps], [*stamps, duration], strict=True)]
                key_only = bool(stamps) and max(gaps) <= interval
                sheets = math.ceil(frames / 100)
                for quality in (5, 12, 24, 31):
                    for sheet in range(sheets):
                        count = min(100, frames - sheet * 100)
                        self._run(
                            [
                                *(["-skip_frame", "nokey"] if key_only else []),
                                "-ss",
                                str(sheet * 100 * interval),
                                "-protocol_whitelist",
                                "file,pipe",
                                "-i",
                                str(path),
                                "-an",
                                "-vf",
                                f"fps=1/{interval}:start_time=0,scale={width}:{height},tile=10x10:nb_frames={count}:padding=0:margin=0",
                                "-frames:v",
                                "1",
                                "-q:v",
                                str(quality),
                                str(staging / f"{sheet}.jpg"),
                            ]
                        )
                    if sum(file.stat().st_size for file in staging.glob("[0-9]*.jpg")) <= MAX_BYTES:
                        break
                else:
                    raise ValueError("Storyboard exceeds the image budget.")
                index = dict(
                    interval=interval,
                    width=width,
                    height=height,
                    frames=frames,
                    sheets=sheets,
                    signature=self.signature(info),
                    keyframe_only=key_only,
                    version=faces.VERSION,
                    face_ready=face_ready,
                )
                write_json(staging / "storyboard.json", index)
                with self.library._lock:
                    _, current = self.library._find(identifier)
                    if self.signature(current) != self.signature(info) or self._cancelled():
                        raise InterruptedError("Video changed or generation interrupted.")
                    if folder.exists():
                        shutil.rmtree(folder)
                    staging.replace(folder)
                return index
            finally:
                if staging.exists():
                    shutil.rmtree(staging)

    def _watch(self):
        retry = {}
        while not self.stop.wait(1):
            try:
                for path, info in self.library._entries():
                    identifier = self.library._identifier(path)
                    if retry.get(identifier, 0) > time.monotonic():
                        continue
                    try:
                        index = json.loads(
                            (self._folder(identifier) / "storyboard.json").read_text(
                                encoding="utf-8"
                            )
                        )
                        if current_images(index, self.signature(info)):
                            continue
                    except (OSError, ValueError):
                        pass
                    with self.gate:
                        if self._cancelled():
                            break
                        self.idle.clear()
                    try:
                        index = self.generate(identifier)
                        if not index.get("face_ready"):
                            retry[identifier] = time.monotonic() + 60
                    except InterruptedError:
                        pass
                    except (
                        OSError,
                        ValueError,
                        KeyError,
                        IndexError,
                        RuntimeError,
                        subprocess.SubprocessError,
                    ):
                        retry[identifier] = time.monotonic() + 60
                    finally:
                        self.idle.set()
                    break
            except (OSError, ValueError):
                self.stop.wait(5)
