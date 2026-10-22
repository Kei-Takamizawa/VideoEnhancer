"""Durable download admission and an independent, bounded network worker pool."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from videoenhancer.jobs.checks import source_warning
from videoenhancer.jobs.store import (
    _manifest_lock,
    _require_unreserved_output,
    add_job,
    input_identity,
)
from videoenhancer.media.probe import probe, rational, target_rate
from videoenhancer.schedule.controller import _kill_process_tree
from videoenhancer.service.settings import read_settings
from videoenhancer.service.video_links import safe_filename, video_url

if TYPE_CHECKING:
    from videoenhancer.service.engine import Engine


class LinkJobs:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.pending: dict[str, None] = {}
        self.active: dict[str, threading.Thread] = {}
        self.cancelled: set[str] = set()
        self.wake = threading.Event()
        self.thread = threading.Thread(
            target=self.run, name="video-download-scheduler", daemon=True
        )

    def recover(self) -> None:
        for job in self.engine.store.queue_jobs():
            if job["state"] == "downloading":
                self.pending[job["id"]] = None
        self.thread.start()

    def queue(self, value: dict[str, Any]) -> dict[str, Any]:
        engine = self.engine
        original, entry = engine.video_links.metadata(
            str(value.get("check_id", "")), str(value.get("entry_key", ""))
        )
        settings = engine.chosen(value.get("settings", {}))
        video, audio = engine.video_links.selected(original, entry, str(value.get("format_id", "")))
        preferences = read_settings(engine.home)
        reuse_id = str(value.get("reuse_job_id") or "")
        reused = engine.video_links.reusable(entry, engine.store) if reuse_id else None
        if reuse_id and (not reused or reused["job_id"] != reuse_id):
            raise ValueError("The downloaded file changed or is missing. Check the link again.")
        if not reused and not preferences["video_download_folder"]:
            raise ValueError("Choose a video-download folder before adding this link.")
        folder = (
            Path(preferences["video_download_folder"])
            if not reused
            else Path(reused["path"]).parent
        )
        if not folder.is_absolute():
            raise ValueError("Choose an absolute video-download folder.")
        folder.mkdir(parents=True, exist_ok=True)
        job_id = uuid.uuid4().hex
        title = safe_filename(entry.get("title") or "Video", str(entry.get("id", "video")))
        source_path = Path(reused["path"]) if reused else folder / (title + ".mkv")
        selected = [video] + ([audio] if audio else [])
        download_bytes = sum(
            int(item.get("filesize") or item.get("filesize_approx") or 0) for item in selected
        )
        estimate = engine.video_links.estimate(video, settings)
        rate = target_rate(rational(video.get("fps"))) if video.get("fps") else None
        media = dict(
            display_width=video.get("width") or None,
            display_height=video.get("height") or None,
            width=video.get("width") or None,
            height=video.get("height") or None,
            cfr_fps=str(rate) if rate else None,
            duration=video.get("duration") or None,
            frame_count=max(1, round(float(rate) * float(video["duration"])))
            if rate and video.get("duration")
            else None,
        )
        now = datetime.now(UTC).isoformat()
        source = dict(
            url=video_url(entry.get("webpage_url") or original),
            request_url=original,
            entry_url=video_url(entry["webpage_url"]) if entry.get("webpage_url") else None,
            extractor=entry.get("extractor") or entry.get("extractor_key") or "generic",
            extractor_key=entry.get("extractor_key") or entry.get("extractor") or "Generic",
            id=str(entry.get("id")),
            format=str(video["format_id"]),
            title=entry.get("title") or title,
        )
        if reused:
            previous = engine.store.load(reuse_id)
            source.update(
                format=previous["source"]["format"],
                downloaded_at=previous["source"].get("downloaded_at", previous.get("created_at")),
                reused_from_job=reuse_id,
                timestamp=previous["source"].get("timestamp"),
            )
        with engine._mutation_lock:
            if engine.storage_moving:
                raise ValueError("App data is moving. Wait for it to finish.")
            if not reused and (
                source_path.exists()
                or any(j["input"]["path"] == str(source_path) for j in engine.store.queue_jobs())
            ):
                source_path = folder / (title + f" [{job_id[:8]}].mkv")
            output = engine.output(source_path, value)
            from videoenhancer.jobs import store as job_store

            input_bytes = source_path.stat().st_size if reused else download_bytes
            # Unknown dimensions cannot support an output-size estimate. The
            # downloaded file gets the full output/working-space check in add_job.
            estimated_bytes = (
                job_store.estimated_output_size(max(1, input_bytes), media, settings)
                if media["width"] and media["height"]
                else 0
            )
            job_store.require_working_space(
                engine.home,
                output.parent,
                estimated_bytes,
                download_folder=folder,
                download_bytes=0 if reused else download_bytes,
            )
            job: dict[str, Any] = dict(
                schema_version=1,
                id=job_id,
                state="downloading",
                input=input_identity(source_path) if reused else {"path": str(source_path)},
                output=str(output),
                source=source,
                settings=settings,
                media=media,
                segments=[],
                created_at=now,
                updated_at=now,
                control_generation=0,
                position=len(engine.store.queue_jobs()) + 1,
                estimated_output_bytes=0,
                link_estimate=estimate,
                machine_profile=engine.video_links.profile(settings, media) if estimate else None,
                link_unanalysed=True,
                download=dict(
                    phase="Using the downloaded file" if reused else "Waiting to download",
                    bytes=0,
                    total_bytes=download_bytes or None,
                    percent=0,
                    ready_at=None,
                    retries=0,
                ),
            )
            with _manifest_lock(engine.store.jobs_dir):
                _require_unreserved_output(engine.store, output, job_id)
                engine.store.save(job)
            self.pending[job_id] = None
            self.wake.set()
        return job

    def run(self) -> None:
        engine = self.engine
        while not engine.stop.is_set():
            try:
                if self.pending and not engine.paused and not engine.storage_moving:
                    limit = read_settings(engine.home)["video_download_limit"]
                    for job_id in list(self.pending):
                        if len(self.active) >= limit:
                            break
                        if job_id in self.active:
                            continue
                        job = engine.store.load_existing(job_id)
                        if not job or job["state"] != "downloading":
                            self.pending.pop(job_id, None)
                            continue
                        thread = threading.Thread(
                            target=self.download,
                            args=(job_id,),
                            name=f"link-download-{job_id}",
                            daemon=True,
                        )
                        self.active[job_id] = thread
                        thread.start()
            except Exception as error:
                engine._error(None, error)
                engine.stop.wait(5)
            self.wake.wait(0.5 if self.pending else 1)
            self.wake.clear()

    def download(self, job_id: str) -> None:
        engine = self.engine

        def paused() -> bool:
            return engine.stop.is_set() or engine.paused or job_id in self.cancelled

        last_saved = 0.0

        def process_changed(child) -> None:
            if child is None:
                engine.processes.pop(job_id, None)
            else:
                engine.processes[job_id] = child

        def progress(packet: dict[str, Any]) -> None:
            nonlocal last_saved
            if time.monotonic() - last_saved < 0.5 and packet.get("phase") == "Downloading":
                return
            latest = engine.store.load_existing(job_id)
            if not latest or latest["state"] != "downloading":
                raise InterruptedError("Video download cancelled.")
            engine.store.patch_existing(
                job_id, {"download": {**latest.get("download", {}), **packet}}
            )
            last_saved = time.monotonic()

        try:
            job = engine.store.load(job_id)
            while True:
                if paused():
                    raise InterruptedError("Video download paused.")
                try:
                    final = engine.video_links.download(job, paused, process_changed, progress)
                    break
                except InterruptedError:
                    raise
                except Exception:
                    retries = int(job.get("download", {}).get("retries", 0))
                    if retries >= 3:
                        raise
                    retries += 1
                    job["download"] = {
                        **job.get("download", {}),
                        "retries": retries,
                        "phase": "Waiting to retry the download",
                        "ready_at": None,
                    }
                    engine.store.patch_existing(job_id, {"download": job["download"]})
                    until = time.monotonic() + 2 ** (retries - 1)
                    while time.monotonic() < until:
                        if paused():
                            raise InterruptedError("Video download paused.") from None
                        time.sleep(0.1)
            identity = input_identity(final)
            with engine._mutation_lock:
                latest = engine.store.load_existing(job_id)
                if not latest:
                    return
                source = {
                    **job["source"],
                    "downloaded_at": job["source"].get("downloaded_at")
                    or datetime.now(UTC).isoformat(),
                }
                engine.store.patch_existing(job_id, {"input": identity, "source": source})
                if paused():
                    raise InterruptedError("Video download paused.")
                engine.store.patch_existing(
                    job_id,
                    {
                        "state": "preparing",
                        "download": {
                            **latest.get("download", {}),
                            "phase": "Download complete",
                            "percent": 100,
                            "remaining_seconds": 0,
                            "ready_at": None,
                        },
                    },
                )
                engine._preparations.append(threading.current_thread())
            media = probe(final, allow_hdr=True, read_timeline=False).to_dict()
            warning = source_warning(media)
            if warning:
                raise ValueError(warning)
            if media.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
                raise ValueError("HDR is not supported. Choose an SDR video.")
            add_job(
                final,
                job["settings"],
                output=job["output"],
                home=engine.home,
                job_id=job_id,
                source_info=source,
            )
        except InterruptedError:
            latest = engine.store.load_existing(job_id)
            if latest and latest["state"] == "downloading":
                engine.store.patch_existing(
                    job_id,
                    {
                        "download": {
                            **latest.get("download", {}),
                            "phase": "Paused",
                            "ready_at": None,
                            "bytes_per_second": None,
                            "remaining_seconds": None,
                        }
                    },
                )
        except Exception as error:
            latest = engine.store.load_existing(job_id)
            if latest and latest["state"] not in {"cancelled", "done"}:
                engine.store.patch_existing(job_id, {"state": "failed", "error": str(error)})
        finally:
            process_changed(None)
            try:
                latest = engine.store.load_existing(job_id)
                if latest and latest.get("cancel_cleanup"):
                    with engine._mutation_lock:
                        engine._clean_cancelled(latest)
                latest = engine.store.load_existing(job_id)
                if not latest or latest["state"] != "downloading":
                    self.pending.pop(job_id, None)
            finally:
                self.active.pop(job_id, None)
                self.wake.set()

    def cancel(self, job_id: str) -> None:
        self.cancelled.add(job_id)
        child = self.engine.processes.get(job_id)
        if child and child.poll() is None:
            _kill_process_tree(child.pid)
        self.wake.set()

    def retry(self, job_id: str) -> dict[str, Any]:
        job = self.engine.store.load(job_id)
        job.update(state="downloading")
        job.pop("error", None)
        job["download"] = {
            **job.get("download", {}),
            "retries": 0,
            "phase": "Waiting to download",
            "ready_at": None,
        }
        self.engine.store.save(job)
        self.cancelled.discard(job_id)
        self.pending[job_id] = None
        self.wake.set()
        return job
