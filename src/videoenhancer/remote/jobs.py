"""Remote-only job ownership, atomic library publication and terminal cleanup."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

from videoenhancer.remote.metadata import remote_info
from videoenhancer.remote.power import Awake
from videoenhancer.service.settings import write_json

TERMINAL = {"done", "failed", "cancelled"}


def clean_title(value):
    value = unicodedata.normalize("NFC", str(value))
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    value = value.encode("utf-16-le")[:240].decode("utf-16-le", errors="ignore").rstrip(" .")
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", value):
        value = "_" + value[:119]
    return value or "Video"


def publish(partial: Path, title):
    stem = clean_title(title) + " (enhanced)"
    for number in range(1, 100000):
        final = partial.parent / f"{stem}{' ' + str(number) if number > 1 else ''}.mp4"
        try:
            # A hard link atomically creates the final name without replacing any file.
            os.link(partial, final)
        except FileExistsError:
            continue
        partial.unlink()
        return final
    raise ValueError("There are too many videos with this title in the library.")


def activity(path, job, outcome, output_bytes, seconds, *, stamp=None):
    media = job.get("media", {})
    row = dict(
        time=stamp or datetime.now(UTC).isoformat(),
        outcome=outcome,
        preset=job["settings"]["preset"],
        resolution=[media.get("width"), media.get("height")],
        duration=media.get("duration"),
        output_bytes=output_bytes,
        processing_seconds=round(seconds, 3),
    )
    if outcome == "failed":
        row["error_category"] = "processing"
    previous = path.read_bytes() if path.exists() else b""
    line = json.dumps(row).encode() + b"\n"
    if stamp and line in previous.splitlines(keepends=True):
        return
    data = previous + line
    if len(data) > 1_000_000:
        data = data[-1_000_000:].split(b"\n", 1)[-1]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def finish_estimate(seconds: float | None, ahead: float | None = 0):
    if seconds is None or ahead is None:
        return {"finish": None, "seconds": None}
    total = max(0, seconds + ahead)
    return {"finish": (datetime.now(UTC) + timedelta(seconds=total)).isoformat(), "seconds": total}


def automatic_format(formats):
    supported = [
        row
        for row in formats
        if not row.get("disabled")
        and row.get("width")
        and row.get("height")
        and min(row["width"], row["height"]) <= 1080
        and row.get("dynamic_range", "SDR") in {None, "SDR"}
    ]
    return max(
        supported,
        key=lambda row: (
            min(row["width"], row["height"]),
            row.get("fps") or 0,
            row.get("tbr") or row.get("bytes") or 0,
        ),
        default=None,
    )


class RemoteJobs:
    """Sweep only at the controller's between-segments boundary, after handles close."""

    def __init__(self, adapter, push):
        self.adapter = adapter
        self.engine = adapter.engine
        self.home = adapter.home
        self.push = push
        self.lock = threading.RLock()
        self.path = self.home / "remote/finishing.json"
        self.records = (
            json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        )
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._watch, name="remote-power", daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=5)

    def _save(self):
        write_json(self.path, self.records)

    def owned(self, device, identifier):
        job = self.engine.store.load_existing(identifier)
        if not job or (remote_info(job) or {}).get("device") != device:
            raise ValueError("This video is no longer in progress.")
        return job

    def ahead(self):
        from videoenhancer.estimate import estimate_job
        from videoenhancer.estimate.live import live_job

        seconds = 0.0
        for job in self.engine.store.list_jobs():
            if job["state"] in TERMINAL:
                continue
            if job["state"] == "downloading" or not job.get("segments"):
                return None
            job = live_job(job, self.engine.live_progress.get(job["id"], {}))
            seconds += estimate_job(job).seconds
        return seconds

    def active(self, device):
        from videoenhancer.estimate import estimate_job
        from videoenhancer.estimate.live import live_job

        result = []
        ahead = 0.0
        for job in self.engine.store.list_jobs():
            if job["state"] in TERMINAL:
                continue
            estimate = None
            if job["state"] != "downloading" and job.get("segments"):
                current = live_job(job, self.engine.live_progress.get(job["id"], {}))
                estimate = estimate_job(current).seconds
            predicted = finish_estimate(estimate, ahead)
            ahead = predicted["seconds"]
            remote = remote_info(job) or {}
            if remote.get("device") == device:
                result.append(dict(id=job["id"], title=remote["title"], **predicted))
        return {"jobs": result}

    def cancel(self, device, identifier):
        self.owned(device, identifier)
        self.engine.cancel_job(identifier)
        return {"cancelled": True}

    def _watch(self):
        awake = None
        next_expiry = time.monotonic() + 3600
        try:
            while not self.stop.wait(0.5):
                if time.monotonic() >= next_expiry:
                    self.adapter.expire_uploads()
                    next_expiry = time.monotonic() + 3600
                busy = self.adapter.uploads.active() or any(
                    remote_info(job) for job in self.engine.store.queue_jobs()
                )
                if busy and awake is None:
                    awake = Awake()
                    awake.__enter__()
                elif not busy and awake is not None:
                    awake.__exit__()
                    awake = None
        finally:
            if awake:
                awake.__exit__()

    def sweep(self):
        with self.adapter.lock, self.lock:
            for job in self.engine.store.list_jobs():
                if remote_info(job) and job["state"] in TERMINAL:
                    self.records.setdefault(job["id"], {"job": job})
            if self.records:
                self._save()
            for identifier in list(self.records):
                try:
                    self._finish(identifier)
                except (OSError, ValueError):
                    import logging

                    logging.getLogger("videoenhancer.remote").warning("remote cleanup pending")

    def _finish(self, identifier):
        import shutil

        record = self.records[identifier]
        live = self.engine.store.load_existing(identifier)
        if live is not None:
            record["job"] = live
            self._save()
        job = record["job"]
        remote = remote_info(job)
        if not remote:
            raise ValueError("Remote ownership is missing.")
        if identifier in self.engine.processes or identifier in self.engine.link_jobs.active:
            return
        if any(
            t.is_alive() and t.name == f"prepare-{identifier}" for t in self.engine._preparations
        ):
            return
        if any(segment["state"] == "running" for segment in job.get("segments", [])):
            return
        partial = Path(job["output"])
        folder = Path(remote["folder"]).resolve()
        incoming = (self.home / "remote/incoming").resolve()
        if folder.parent != incoming or folder == incoming:
            raise ValueError("Remote source folder is outside incoming.")
        if partial.parent.resolve() != self.adapter.library.folder.resolve():
            raise ValueError("Remote output is outside the library.")
        final = Path(record["final"]) if record.get("final") else None
        if job["state"] == "done":
            if final is None:
                stem = clean_title(remote["title"]) + " (enhanced)"
                number = 1
                final = partial.parent / f"{stem}.mp4"
                while final.exists():
                    number += 1
                    final = partial.parent / f"{stem} {number}.mp4"
                record["final"] = str(final)
                self._save()
            if partial.exists():
                try:
                    os.link(partial, final)
                except FileExistsError:
                    if not os.path.samefile(partial, final):
                        record.pop("final")
                        self._save()
                        return
                partial.unlink()
            if not final.is_file():
                raise ValueError("The finished video is missing.")
        else:
            partial.unlink(missing_ok=True)
        # Delete job diagnostics before its input folder, so existing cleanup hooks can run.
        if self.engine.store.load_existing(identifier):
            self.engine.remove(identifier)
        if folder.exists():
            shutil.rmtree(folder)
        check_id = remote.get("check_id")
        if check_id:
            others = self.engine.store.list_jobs()
            if not any((remote_info(row) or {}).get("check_id") == check_id for row in others):
                preview = self.home / "previews" / check_id
                if preview.exists():
                    shutil.rmtree(preview)
                self.engine.operations.pop(check_id, None)
                with self.adapter.lock:
                    self.adapter.requests.pop(check_id, None)
                    write_json(self.adapter.requests_path, self.adapter.requests)
        if not record.get("logged"):
            seconds = sum(float(row.get("actual_seconds") or 0) for row in job.get("segments", []))
            seconds += float(job.get("analysis_seconds") or 0)
            seconds += float(job.get("timing", {}).get("finalization_seconds") or 0)
            record.setdefault("stamp", datetime.now(UTC).isoformat())
            self._save()
            activity(
                self.home / "remote/activity.log",
                job,
                job["state"],
                final.stat().st_size if final else 0,
                seconds,
                stamp=record["stamp"],
            )
            record["logged"] = True
            self._save()
        if job["state"] in {"done", "failed"}:
            item_id = self.adapter.library._identifier(final) if final else None
            self.push.finished(remote["device"], remote["title"], job["state"], item_id)
        self.records.pop(identifier)
        self._save()
        for cache in (
            self.engine.live_progress,
            self.engine._progress_received,
            self.engine._history_rows,
        ):
            cache.pop(identifier, None)
