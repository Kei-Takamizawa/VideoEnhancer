"""Folder-backed remote library with opaque identifiers and bounded metadata probes."""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import threading
from collections.abc import Iterator
from os import open as open_descriptor
from pathlib import Path
from typing import Any, BinaryIO

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.service.settings import write_json

_EXTENSIONS = {".mp4", ".m4v", ".mov"}
_ID = re.compile(r"[0-9a-f]{64}\Z")
_RANGE = re.compile(r"bytes=(\d*)-(\d*)\Z")


class InUseError(PermissionError):
    """An active gateway transfer prevents permanent deletion."""


def resolve_library_folder(value: str) -> Path:
    if value:
        folder = Path(value).expanduser()
        if not folder.is_absolute():
            raise ValueError("The library folder must be an absolute path.")
        return folder
    if os.name == "nt" and Path("D:/").exists():
        return Path("D:/VideoEnhancer/完成動画")
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Videos" / "VideoEnhancer"


def parse_range(header: str | None, size: int) -> tuple[int, int]:
    """Return one inclusive byte range; multipart and unsatisfiable ranges raise ValueError."""
    if header is None:
        return 0, size - 1
    match = _RANGE.fullmatch(header)
    if not match or size <= 0:
        raise ValueError("The requested byte range is not available.")
    first, last = match.groups()
    if not first and not last:
        raise ValueError("The requested byte range is not available.")
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    else:
        suffix = int(last)
        if suffix <= 0:
            raise ValueError("The requested byte range is not available.")
        start, end = max(0, size - suffix), size - 1
    if start >= size or start > end:
        raise ValueError("The requested byte range is not available.")
    return start, end


class Library:
    def __init__(self, home: Path, folder: Path):
        self.home = Path(home)
        self.folder = Path(folder)
        if not self.folder.is_absolute():
            raise ValueError("The library folder must be an absolute path.")
        self._lock = threading.RLock()
        self._active: dict[str, int] = {}
        self._cache_path = self.home / "remote" / "library-probes.json"
        try:
            cached = json.loads(self._cache_path.read_text(encoding="utf-8"))
            self._cache = cached if isinstance(cached, dict) else {}
        except (OSError, ValueError):
            self._cache = {}

    @staticmethod
    def _entry(path: Path, root: Path) -> os.stat_result | None:
        if (
            path.suffix.lower() not in _EXTENSIONS
            or path.name.startswith((".", "~"))
            or path.stem.lower().endswith((".part", ".partial", ".tmp", ".download"))
        ):
            return None
        try:
            info = path.lstat()
            attributes = getattr(info, "st_file_attributes", 0)
            if (
                not stat.S_ISREG(info.st_mode)
                or attributes & (stat.FILE_ATTRIBUTE_REPARSE_POINT | stat.FILE_ATTRIBUTE_HIDDEN)
                or path.resolve(strict=True).parent != root
            ):
                return None
            return info
        except (OSError, RuntimeError):
            return None

    def _entries(self) -> list[tuple[Path, os.stat_result]]:
        self.folder.mkdir(parents=True, exist_ok=True)
        root = self.folder.resolve(strict=True)
        return [
            (path, info)
            for path in self.folder.iterdir()
            if (info := self._entry(path, root)) is not None
        ]

    @staticmethod
    def _identifier(path: Path) -> str:
        return hashlib.sha256(path.name.encode("utf-8")).hexdigest()

    @staticmethod
    def _signature(info: os.stat_result) -> tuple[int, int]:
        return info.st_size, info.st_mtime_ns

    def _find(self, identifier: str) -> tuple[Path, os.stat_result]:
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            raise ValueError("Invalid library item.")
        for path, info in self._entries():
            if self._identifier(path) == identifier:
                return path, info
        raise FileNotFoundError("This video is no longer in the library.")

    def _probe(self, path: Path) -> dict[str, Any]:
        result = proc.run(
            [
                executable("ffprobe"),
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format=duration:stream=width,height,codec_name,duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=15,
        )
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        duration = float(stream.get("duration", data.get("format", {}).get("duration", 0)))
        width, height = int(stream["width"]), int(stream["height"])
        if not math.isfinite(duration) or duration < 0 or width <= 0 or height <= 0:
            raise ValueError("Invalid video metadata.")
        return {
            "duration": duration,
            "width": width,
            "height": height,
            "codec": str(stream["codec_name"]),
        }

    def _item(self, path: Path, info: os.stat_result) -> dict[str, Any]:
        return {
            "id": self._identifier(path),
            "name": path.stem,
            "filename": path.name,
            "size": info.st_size,
            "modified": info.st_mtime,
            "mime": "video/quicktime" if path.suffix.lower() == ".mov" else "video/mp4",
        }

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            items = []
            updated_cache = {}
            for path, info in self._entries():
                signature = [path.name, *self._signature(info)]
                identifier = self._identifier(path)
                cached = self._cache.get(identifier)
                if isinstance(cached, dict) and cached.get("signature") == signature:
                    metadata = cached.get("metadata", {})
                else:
                    try:
                        metadata = self._probe(path)
                    except (
                        OSError,
                        ValueError,
                        KeyError,
                        IndexError,
                        TypeError,
                        subprocess.SubprocessError,
                    ):
                        metadata = {
                            "duration": None,
                            "width": None,
                            "height": None,
                            "codec": None,
                            "error": "Can't read this video",
                        }
                current = self._entry(path, self.folder.resolve(strict=True))
                if current is None or self._signature(current) != self._signature(info):
                    continue
                updated_cache[identifier] = {"signature": signature, "metadata": metadata}
                items.append({**self._item(path, info), **metadata})
            if updated_cache != self._cache:
                write_json(self._cache_path, updated_cache)
                self._cache = updated_cache
            return sorted(items, key=lambda item: (-item["modified"], item["name"]))

    def storage(self) -> dict[str, Any]:
        with self._lock:
            entries = self._entries()
            usage = shutil.disk_usage(self.folder)
            drive = self.folder.resolve().drive or "/"
            return {
                "total": usage.total,
                "free": usage.free,
                "library_bytes": sum(info.st_size for _, info in entries),
                "drive_label": drive,
            }

    @contextlib.contextmanager
    def acquire(self, identifier: str) -> Iterator[tuple[BinaryIO, dict[str, Any]]]:
        with self._lock:
            path, before = self._find(identifier)
            descriptor = open_descriptor(
                path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
            )
            stream = os.fdopen(descriptor, "rb")
            try:
                current_path, after = self._find(identifier)
                opened = os.fstat(stream.fileno())
                if (
                    current_path != path
                    or not stat.S_ISREG(opened.st_mode)
                    or not os.path.samestat(before, opened)
                    or not os.path.samestat(after, opened)
                    or self._signature(before) != self._signature(opened)
                ):
                    raise FileNotFoundError("This video changed. Refresh the library.")
                self._active[identifier] = self._active.get(identifier, 0) + 1
            except BaseException:
                stream.close()
                raise
        try:
            yield stream, self._item(path, opened)
        finally:
            with self._lock:
                stream.close()
                self._active[identifier] -= 1
                if not self._active[identifier]:
                    del self._active[identifier]

    def delete(self, identifier: str) -> None:
        with self._lock:
            path, _ = self._find(identifier)
            if self._active.get(identifier):
                raise InUseError(
                    "This video is being streamed or downloaded. Try again afterwards."
                )
            path.unlink()
            self._cache.pop(identifier, None)
            write_json(self._cache_path, self._cache)
