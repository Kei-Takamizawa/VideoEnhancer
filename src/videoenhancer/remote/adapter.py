"""In-process gateway adapter; no requests to the token-authenticated desktop API."""

import json
import logging
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from videoenhancer.remote.jobs import automatic_format, finish_estimate
from videoenhancer.remote.metadata import remote_info
from videoenhancer.remote.uploads import Uploads
from videoenhancer.service.settings import write_json


class PrivateJob(logging.Filter):
    def filter(self, record):
        # Remote jobs keep only the nameless activity log after completion.
        return False


class EngineAdapter:
    def __init__(self, engine, home: Path, settings: dict):
        self.engine = engine
        self.home = home
        self.settings = settings
        self._library = None
        self._library_lock = threading.Lock()
        self.lock = threading.RLock()
        self.uploads = Uploads(home / "remote/incoming")
        self.jobs: Any = None
        self.requests_path = home / "remote/requests.json"
        self.requests = (
            json.loads(self.requests_path.read_text(encoding="utf-8"))
            if self.requests_path.exists()
            else {}
        )
        if engine is not None:
            for job in engine.store.queue_jobs():
                if remote_info(job):
                    self.private_job(job["id"])

    @staticmethod
    def private_job(identifier):
        logger = logging.getLogger(f"videoenhancer.{identifier}")
        if not any(isinstance(item, PrivateJob) for item in logger.filters):
            logger.addFilter(PrivateJob())

    def expire_uploads(self):
        # Add holds this same lock until the upload's job is durably stored.
        with self.lock:
            owned = {
                remote["folder"]
                for job in (self.engine.store.list_jobs() if self.engine is not None else [])
                if (remote := remote_info(job)) and remote.get("folder")
            }
            self.uploads.sweep(owned)

    def operation(self, device, identifier):
        if self.requests.get(identifier) != device:
            raise ValueError("Check the link again.")
        return self.engine.operations.get(identifier) or {
            "id": identifier,
            "state": "failed",
            "error": "Check the link again.",
        }

    def track(self, device, operation):
        with self.lock:
            self.requests[operation["id"]] = device
            write_json(self.requests_path, self.requests)
        # Poll the owned result even when a fast operation finished before this response.
        return {"id": operation["id"], "state": "running"}

    def check_link(self, device, value):
        if not self.engine.link_tools.status()["available"]:
            return {"state": "tools_required", "tools_required": True}
        with self.lock:
            return self.track(device, self.engine.check_link({"url": value.get("url", "")}))

    def check_result(self, device, identifier):
        op = self.operation(device, identifier)
        result = {"id": identifier, "state": op["state"]}
        if op["state"] == "failed":
            result["error"] = "The link could not be checked. Check the URL and try again."
        if op["state"] != "done":
            return result
        entries = []
        ahead = self.jobs.ahead()
        for card in op.get("result", {}).get("entries", []):
            if card.get("error"):
                entries.append(
                    {
                        "key": card["key"],
                        "title": card.get("title", "Video"),
                        "error": "This entry cannot be downloaded. Choose another video.",
                    }
                )
                continue
            original, raw = self.engine.video_links.metadata(identifier, card["key"])
            from videoenhancer.service.video_links import format_reason

            selected = automatic_format(
                [
                    dict(
                        item,
                        id=str(item.get("format_id")),
                        disabled=format_reason(item) or item.get("transport_error"),
                    )
                    for item in raw.get("formats", [])
                    if item.get("vcodec") != "none"
                ]
            )
            row = {
                "key": card["key"],
                "title": card.get("title", "Video"),
                "duration": card.get("duration"),
            }
            if not selected:
                row["error"] = "No supported SDR video at 1080p or smaller was found."
            else:
                try:
                    self.engine.video_links.selected(original, raw, selected["id"])
                    estimate = self.engine.video_links.estimate(selected, self.defaults())
                    # Processing cost alone cannot predict an unstarted network transfer.
                    predicted = finish_estimate(None, ahead)
                    ahead = predicted["seconds"]
                    row.update(
                        width=selected["width"],
                        height=selected["height"],
                        duration=selected.get("duration"),
                        format_id=selected["id"],
                        estimate={**(estimate or {}), **predicted},
                    )
                except ValueError:
                    row["error"] = "The site did not provide a supported download."
            entries.append(row)
        result["entries"] = entries
        return result

    def defaults(self):
        return self.engine.chosen({"delete_original_after": False})

    def estimate(self, device, value):
        upload_id = value.get("upload_id")
        if upload_id:
            source = self.uploads.source(device, upload_id)
            status = self.uploads.status(device, upload_id)
            check = self.engine.estimate(
                {
                    "file": str(source),
                    "settings": self.defaults(),
                    "output": str(self.library.folder / ".estimate.mp4"),
                }
            )
            if check["warnings"]:
                raise ValueError(check["warnings"][0])
            estimate = check["presets"][self.defaults()["preset"]]
            media = status["media"]
            return {
                "entries": [
                    {
                        "key": upload_id,
                        "title": Path(status["name"]).stem,
                        "duration": media.get("duration"),
                        "width": media["width"],
                        "height": media["height"],
                        "estimate": {
                            **{key: estimate[key] for key in ("seconds", "low", "high")},
                            **finish_estimate(estimate["seconds"], self.jobs.ahead()),
                        },
                    }
                ]
            }
        result = self.check_result(device, str(value.get("check_id", "")))
        keys = value.get("entry_keys", [])
        if not isinstance(keys, list) or not keys or len(keys) > 200:
            raise ValueError("Choose at least one video.")
        rows = [row for row in result.get("entries", []) if row["key"] in keys]
        if len(rows) != len(set(keys)) or any(row.get("error") for row in rows):
            raise ValueError("Check the selected videos again.")
        ahead = self.jobs.ahead()
        for row in rows:
            estimate = row["estimate"]
            # Recompute cumulative finish using only the selected playlist entries.
            raw, info = self.engine.video_links.metadata(value["check_id"], row["key"])
            selected, _ = self.engine.video_links.selected(raw, info, row["format_id"])
            cost = self.engine.video_links.estimate(selected, self.defaults())
            row["estimate"] = {**(cost or {}), **finish_estimate(None, ahead)}
            ahead = row["estimate"]["seconds"]
        return {"entries": rows}

    def add(self, device, value):
        with self.lock, self.uploads.lock:
            rows = self.estimate(device, value)["entries"]
            added = []
            for row in rows:
                identifier = uuid.uuid4().hex
                output = self.library.folder / f".{identifier}.partial.mp4"
                self.library.folder.mkdir(parents=True, exist_ok=True)
                upload_id = value.get("upload_id")
                folder = (
                    self.uploads.folder / upload_id
                    if upload_id
                    else self.uploads.folder / identifier
                )
                if upload_id:
                    # A retried Add must never queue the same source twice.
                    existing = next(
                        (
                            job
                            for job in self.engine.store.queue_jobs()
                            if (remote_info(job) or {}).get("folder") == str(folder)
                        ),
                        None,
                    )
                    if existing:
                        added.append({"id": existing["id"]})
                        continue
                else:
                    existing = next(
                        (
                            job
                            for job in self.engine.store.queue_jobs()
                            if (remote_info(job) or {}).get("device") == device
                            and (remote_info(job) or {}).get("check_id") == value["check_id"]
                            and (remote_info(job) or {}).get("entry_key") == row["key"]
                        ),
                        None,
                    )
                    if existing:
                        added.append({"id": existing["id"]})
                        continue
                folder.mkdir(parents=True, exist_ok=True)
                remote = {"device": device, "title": row["title"], "folder": str(folder)}
                self.private_job(identifier)
                if upload_id:
                    job = self.engine.add(
                        {
                            "file": str(self.uploads.source(device, upload_id)),
                            "output": str(output),
                            "settings": self.defaults(),
                        },
                        remote=remote,
                        job_id=identifier,
                    )
                else:
                    remote["check_id"] = value["check_id"]
                    remote["entry_key"] = row["key"]
                    try:
                        job = self.engine.link_jobs.queue(
                            {
                                "check_id": value["check_id"],
                                "entry_key": row["key"],
                                "format_id": row["format_id"],
                                "output": str(output),
                                "settings": self.defaults(),
                            },
                            remote=remote,
                            job_id=identifier,
                        )
                    except Exception:
                        shutil.rmtree(folder)
                        raise
                added.append({"id": job["id"]})
            return {"added": added}

    @property
    def library(self):
        from videoenhancer.remote.library import Library, resolve_library_folder

        with self._library_lock:
            if self._library is None:
                folder = resolve_library_folder(self.settings.get("library_folder", ""))
                self._library = Library(self.home, folder)
            return self._library
