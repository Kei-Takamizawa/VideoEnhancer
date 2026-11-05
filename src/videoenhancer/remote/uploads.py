"""Device-owned, bounded, durable upload sessions under the incoming folder."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from videoenhancer.jobs.checks import source_warning
from videoenhancer.service.settings import write_json

MAX_FILE = 20_000_000_000
MAX_CHUNK = 4 * 1024 * 1024


class UploadConflict(ValueError):
    """A device must finish its current upload before starting another."""


def probe_video(path):
    from videoenhancer.media.probe import probe

    return probe(path, allow_hdr=True, read_timeline=False).to_dict()


class Uploads:
    def __init__(self, folder: Path, *, probe=probe_video, clock=time.time):
        self.folder = folder.resolve()
        self.probe = probe
        self.lock = threading.RLock()
        self.last_activity = 0.0
        self.clock = clock
        self.busy = set()

    @contextmanager
    def _update(self, device, identifier):
        with self.lock:
            item, directory = self._load(device, identifier)
            if identifier in self.busy:
                raise ValueError("This upload is already being updated. Try again shortly.")
            self.busy.add(identifier)
        try:
            yield item, directory
        finally:
            with self.lock:
                self.busy.remove(identifier)

    def sweep(self, owned):
        with self.lock:
            protected = {Path(folder).resolve() for folder in owned}
            for metadata in self.folder.glob("*/upload.json"):
                directory = self._directory(metadata.parent.name)
                if directory in protected or directory.name in self.busy:
                    continue
                item = json.loads(metadata.read_text(encoding="utf-8"))
                updated = item.get("updated_at", metadata.stat().st_mtime)
                if self.clock() - updated >= 86400:
                    shutil.rmtree(directory)

    def active(self):
        return time.monotonic() - self.last_activity < 60

    def _directory(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise ValueError("Invalid upload.")
        directory = self.folder / identifier
        if directory.is_symlink() or directory.resolve().parent != self.folder:
            raise ValueError("Invalid upload.")
        return directory

    def _load(self, device, identifier):
        directory = self._directory(identifier)
        try:
            item = json.loads((directory / "upload.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError("This upload expired. Choose the video again.") from None
        if item["device"] != device:
            raise ValueError("This upload belongs to another device.")
        return item, directory

    def create(self, device, name, size):
        if not isinstance(name, str) or not 1 <= len(name) <= 255:
            raise ValueError("Choose a video file.")
        if type(size) is not int or not 0 < size <= MAX_FILE:
            raise ValueError("Choose a video no larger than 20 GB.")
        with self.lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            reserved = 0
            for metadata in self.folder.glob("*/upload.json"):
                item = json.loads(metadata.read_text(encoding="utf-8"))
                if item["device"] == device and not item["ready"]:
                    raise UploadConflict("One upload at a time. Resume the unfinished upload.")
                reserved += max(0, item["size"] - item["offset"])
            if size + reserved > int(shutil.disk_usage(self.folder).free * 0.9):
                raise ValueError("There is not enough free space on the PC for this upload.")
            identifier = uuid.uuid4().hex
            directory = self._directory(identifier)
            directory.mkdir()
            item = dict(
                id=identifier,
                device=device,
                name=name,
                size=size,
                offset=0,
                ready=False,
                updated_at=self.clock(),
            )
            (directory / "source").touch()
            write_json(directory / "upload.json", item)
            self.last_activity = time.monotonic()
            return self._public(item)

    @staticmethod
    def _public(item):
        return {key: value for key, value in item.items() if key not in {"device", "updated_at"}}

    def status(self, device, identifier):
        with self.lock:
            item, _ = self._load(device, identifier)
            return self._public(item)

    def source(self, device, identifier):
        with self.lock:
            item, directory = self._load(device, identifier)
            if not item["ready"]:
                raise ValueError("Finish the upload first.")
            return directory / "source"

    def chunk(self, device, identifier, offset, stream, length):
        with self._update(device, identifier) as (item, directory):
            self.last_activity = time.monotonic()
            if (
                item["ready"]
                or type(offset) is not int
                or offset != item["offset"]
                or not 0 < length <= MAX_CHUNK
                or offset + length > item["size"]
            ):
                raise ValueError("Check the upload status before resuming.")
            with (directory / "source").open("r+b") as target:
                target.seek(offset)
                try:
                    remaining = length
                    while remaining:
                        block = stream.read(min(65536, remaining))
                        if not block:
                            raise ValueError("The upload was interrupted. Resume it to continue.")
                        target.write(block)
                        remaining -= len(block)
                    target.flush()
                    os.fsync(target.fileno())
                except Exception:
                    target.truncate(offset)
                    raise
            item["offset"] += length
            item["updated_at"] = self.clock()
            write_json(directory / "upload.json", item)
            return self._public(item)

    def finish(self, device, identifier, digest):
        with self._update(device, identifier) as (item, directory):
            if item["ready"]:
                return self._public(item)
            if item["offset"] != item["size"]:
                raise ValueError("Finish uploading the video first.")
            try:
                with (directory / "source").open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                if not isinstance(digest, str) or digest != actual:
                    raise ValueError("The upload hash did not match. Choose the video again.")
                media = self.probe(directory / "source")
                if reason := source_warning(media):
                    raise ValueError(reason)
                if media.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
                    raise ValueError("HDR is not supported. Choose an SDR video.")
            except Exception:
                shutil.rmtree(directory)
                raise
            item.update(ready=True, media=media, updated_at=self.clock())
            write_json(directory / "upload.json", item)
            self.last_activity = 0
            return self._public(item)
