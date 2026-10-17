"""Desktop operations on the same durable queue used by the CLI."""

from __future__ import annotations

import copy
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from videoenhancer import __version__, proc
from videoenhancer.cli import _jobs_plan, _save_schedule, _schedule_payload
from videoenhancer.estimate import estimate_job
from videoenhancer.estimate.live import live_job
from videoenhancer.estimate.local import recent_correction
from videoenhancer.estimate.model import job_progress
from videoenhancer.jobs.store import (
    JobStore,
    _manifest_lock,
    add_job,
    estimated_output_size,
    input_identity,
    load_machine_profile,
    working_space_locations,
)
from videoenhancer.logging import get_logger
from videoenhancer.media.decode import choose_backend
from videoenhancer.media.probe import probe
from videoenhancer.models.registry import ModelRegistry, selected_models
from videoenhancer.schedule.controller import SystemClock, _kill_process_tree, run_queue
from videoenhancer.schedule.planner import build_plan
from videoenhancer.schedule.windows import Schedule
from videoenhancer.service.locks import OrderedLock, assert_io_unlocked
from videoenhancer.service.settings import read_settings, save_settings, write_json


class ServiceClock(SystemClock):
    def __init__(self, event: threading.Event):
        self.event = event

    def sleep(self, seconds: float) -> None:
        self.event.wait(seconds)


def _scenario_jobs(jobs: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    result = copy.deepcopy(jobs)
    for job in result:
        estimate = estimate_job(job)
        ratio = (estimate.low if scenario == "best" else estimate.high) / max(
            estimate.seconds, 0.000001
        )
        job["correction_factor"] = job.get("correction_factor", 1) * ratio
        profile = job.get("machine_profile") or {}
        job["machine_profile"] = {
            **profile,
            "finalization_scenario_factor": profile.get("finalization_scenario_factor", 1) * ratio,
        }
    return result


class Engine:
    def __init__(
        self,
        home: Path,
        *,
        test_stuck_trial: bool = False,
        test_trial_timeout: float | None = None,
        test_lock_order: bool = False,
    ):
        self.home = home.resolve()
        self._test_stuck_trial = test_stuck_trial
        self._test_trial_timeout = test_trial_timeout
        self.store = JobStore(home)
        self.stop = threading.Event()
        self.lock = OrderedLock("engine state", 30, test_lock_order)
        self._mutation_lock = OrderedLock("mutation", 10, test_lock_order)
        self.operations: dict[str, dict[str, Any]] = {}
        self.processes: dict[str, subprocess.Popen[Any]] = {}
        self.last_error: dict[str, Any] | None = None
        self.live_progress: dict[str, dict[str, Any]] = {}
        self._preparations: list[threading.Thread] = []
        self.preview_threads: dict[str, threading.Thread] = {}
        self.download_threads: dict[str, threading.Thread] = {}
        self.storage_moving = False
        self._cleanup_checked = 0.0
        self.paused = os.environ.get("VE_STORAGE_MOVE_HOLD") == "1"
        self._event_lock = OrderedLock("published events", 20, test_lock_order)
        self._event_build_lock = threading.RLock()
        self._publishing = False
        self._publisher = threading.Thread(
            target=self._publish_events, daemon=True, name="event-publisher"
        )
        self._health_jobs_lock = threading.Lock()
        self._health_jobs_generation = -1
        self._health_jobs: list[dict[str, Any]] = []
        self._event_wire_key: tuple[Any, ...] | None = None
        self._event_wire = ""
        self._event_cache: dict[str, Any] | None = None
        self._event_key: tuple[Any, ...] | None = None
        self._event_built = 0.0
        self._history_rows: dict[str, tuple[Any, dict[str, Any]]] = {}
        self._history_timers: list[threading.Timer] = []
        self._history_threads: list[threading.Thread] = []
        self._lock_watchdog = threading.Thread(target=self._watch_locks, daemon=True)
        from videoenhancer.service.events import HomeWatcher

        self._home_watcher = HomeWatcher(self.home)
        self._structure_generation = -1
        self._structure_checked = 0.0
        self._structure_records: tuple[Any, Any] = ([], [])
        self._event_jobs: list[dict[str, Any]] = []
        self._event_running_jobs: list[dict[str, Any]] = []
        self._file_cache: dict[str, os.stat_result | None] = {}
        self._file_generation = 0
        self._file_checked = 0.0
        self._history_wire: dict[str, tuple[Any, str]] = {}
        self._progress_received: dict[str, tuple[float, dict[str, Any]]] = {}
        self._progress_wire = ""
        self._progress_built = 0.0
        self._schedule_stamp: Any = None
        self._schedule_cache: Any = None
        self._registry_checked = 0.0
        self._cached_sac: dict[str, Any] = {}
        self._speed_profile: dict[str, Any] = {}
        from videoenhancer.service.deletion import get_deletion

        self.deletion = get_deletion(self.home)
        self.environment: dict[str, Any] = {}
        self.worker = threading.Thread(target=self._worker, name="engine-controller", daemon=True)
        self._health_thread = threading.Thread(target=self._environment, daemon=True)

    def start(self) -> None:
        self._recover()
        self._home_watcher.start()
        self._health_thread.start()
        self.start_publication()
        self.worker.start()
        threading.Thread(
            target=self._deletion_recovery, name="deletion-recovery", daemon=True
        ).start()

    def start_publication(self) -> None:
        if not self._publishing:
            self._publishing = True
            self._publisher.start()
            self._lock_watchdog.start()

    def _watch_locks(self) -> None:
        while not self.stop.wait(0.5):
            for lock in (self.lock, self._mutation_lock, self._event_lock):
                if lock.owner is not None and not lock.warned and time.monotonic() - lock.since > 5:
                    lock.warned = True
                    get_logger(self.home).warning(
                        "Lock %s held over five seconds by thread %s\n%s",
                        lock.name,
                        lock.owner,
                        lock.stack,
                    )

    def _deletion_recovery(self) -> None:
        while not self.stop.wait(60):
            self.deletion.recover()
            self.refresh_terminal_files()

    def _recover(self) -> None:
        self.deletion.recover()
        for entry in self.deletion.completed_outcomes():
            try:
                job = self.store.load(entry["job_id"])
            except (FileNotFoundError, KeyError):
                continue
            for key, path in (("original", job["input"]["path"]), ("output", job["output"])):
                if os.path.normcase(os.path.abspath(path)) == os.path.normcase(
                    os.path.abspath(entry["path"])
                ):
                    job.setdefault("video_deletions", {})[key] = entry["result"]
                    self.store.save(job)
        for job in self.store.list_jobs():
            if job.get("history_hidden_until"):
                if job.pop("storage_move_undo", False):
                    self.store.save(job)
                    if "history_undo_remaining" not in job:
                        self._schedule_history_removal(job)
                    continue
                if "history_undo_remaining" in job:
                    self.remove(job["id"])
                    continue
                self._schedule_history_removal(job)
            if job["state"] == "running":
                for segment in job["segments"]:
                    if segment["state"] == "running":
                        segment["state"] = "pending"
                job["state"] = "queued"
                job["progress"] = {}
                self.store.save(job)
                for path in self.store.job_dir(job["id"]).glob("seg_*.tmp.*"):
                    path.unlink(missing_ok=True)
            elif job["state"] == "preparing":
                job.update(state="failed", error="Preparation was interrupted. Try again.")
                self.store.save(job)
        for folder in (self.home / "previews").glob("*"):
            state_path = folder / "state.json"
            if state_path.is_file():
                op = json.loads(state_path.read_text(encoding="utf-8"))
                if op["state"] in {"waiting", "running"}:
                    op.update(
                        state="failed",
                        phase="Interrupted. Try again.",
                        error="Interrupted. Try again.",
                    )
            elif (folder / "request.json").is_file():
                saved = json.loads((folder / "request.json").read_text(encoding="utf-8"))
                op = dict(
                    id=folder.name,
                    kind=saved["kind"],
                    request=saved["request"],
                    state="failed",
                    phase="Interrupted. Try again.",
                    error="Interrupted. Try again.",
                )
            else:
                continue
            self.operations[op["id"]] = op
            self._save_operation(op)

    def _save_operation(self, op: dict[str, Any]) -> None:
        folder = self.home / "previews" / op["id"]
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / "state.json", op)
        from videoenhancer.service.events import changed

        changed(self.home)

    def _error(self, job_id: str | None, error: Exception) -> None:
        self.last_error = {
            "time": datetime.now(UTC).isoformat(),
            "job_id": job_id,
            "message": str(error),
        }
        get_logger(self.home, job_id=job_id).error(
            "Controller error: %s", error, exc_info=(type(error), error, error.__traceback__)
        )

    def _progress(self, job: dict[str, Any], value: dict[str, Any]) -> None:
        with self.lock:
            now = time.monotonic()
            previous = self._progress_received.get(job["id"])
            old = (previous[1].get("progress") or {}) if previous else {}
            self.live_progress[job["id"]] = dict(value)
            if previous and all(
                old.get(key) == value.get(key)
                for key in ("frames_done", "segment", "phase", "step")
            ):
                return
            measured = dict(value)
            self._progress_received[job["id"]] = (
                now,
                copy.deepcopy(
                    {
                        **{
                            key: value
                            for key, value in job.items()
                            if key
                            not in {
                                "cfr_map",
                                "source_pts",
                                "scene_cuts",
                                "motion_scores",
                                "keyframes",
                            }
                        },
                        "progress": measured,
                    }
                ),
            )

    def _forecast_jobs(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self.lock:
            received = dict(self._progress_received)
        now = time.monotonic()
        result = []
        for job in jobs:
            if job["state"] == "running" and job.get("progress", {}).get("phase") != "finalizing":
                latest = received.get(job["id"])
                # The receipt carries the same complete metadata, not a reduced whitelist.
                current = {**job, "progress": latest[1]["progress"]} if latest else job
                work = live_job(current, current.get("progress") or {})
                if latest and work["progress"].get("cumulative_fps", 0) > 0:
                    elapsed = max(0, now - latest[0])
                    active = next(
                        (part for part in work["segments"] if part["state"] == "running"), None
                    )
                    if active:
                        work["progress"]["frames_done"] = min(
                            active["end"] - active["start"],
                            float(work["progress"].get("frames_done", 0))
                            + work["progress"]["fps"] * elapsed,
                        )
                result.append(work)
            else:
                result.append(dict(job))
        return result

    def _environment(self) -> None:
        from videoenhancer.logging import environment_info

        self.environment = environment_info()
        from videoenhancer.media.decode import software_decoder_support

        try:
            self.environment["software_decoders"] = software_decoder_support()
        except Exception as error:
            self.environment["software_decoders"] = {"vp9": False, "av1": False}
            self._error(None, error)
        try:
            import torch

            if torch.cuda.is_available():
                self.environment["vram_bytes"] = torch.cuda.get_device_properties(0).total_memory
                choose_backend("cuda")
                from videoenhancer.service.av1_cache import capabilities

                self.environment.update(
                    capabilities(
                        self.home,
                        str(self.environment.get("gpu") or ""),
                        str(self.environment.get("driver") or ""),
                    )
                )
                reason = self.environment.get("av1_unavailable_reason")
                if not (self.home / "settings.json").exists():
                    save_settings(
                        self.home,
                        {"codec": "av1" if self.environment.get("av1_supported") else "hevc"},
                    )
                if reason:
                    get_logger(self.home).warning("AV1 probe: %s", reason)
            else:
                self.environment.update(
                    av1_supported=False,
                    av1_unavailable_reason="CUDA hardware encoding is unavailable.",
                )
        except Exception as error:
            self.environment.update(
                av1_supported=False, av1_unavailable_reason=" ".join(str(error).split())
            )
            self._error(None, error)

        self._registry_checked = 0
        from videoenhancer.service.events import changed

        changed(self.home)

    def _worker(self) -> None:
        while not self.stop.is_set():
            try:
                if not self.storage_moving and time.monotonic() - self._cleanup_checked > 3600:
                    from videoenhancer.service.storage import cleanup_expired

                    with self._mutation_lock:
                        cleanup_expired(self.store)
                    self._cleanup_checked = time.monotonic()
                run_queue(
                    home=self.home,
                    clock=ServiceClock(self.stop),
                    stopped=self.stop.is_set,
                    paused_all=lambda: self.paused,
                    between_segments=self._auxiliary,
                    on_error=self._error,
                    on_progress=self._progress,
                )
            except Exception as error:
                self._error(None, error)
                self.stop.wait(5)
            self.stop.wait(0.5)

    def close(self) -> None:
        self._home_watcher.close()
        self.stop.set()
        for timer in self._history_timers:
            timer.cancel()
        deadline = time.monotonic() + 15
        for thread in self._history_threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
            if thread.is_alive():
                raise RuntimeError(
                    "File removal has not finished. Keep the app open and retry Quit."
                )
        if self._publisher.ident is not None:
            self._publisher.join(timeout=2)
        for thread in list(self.preview_threads.values()):
            thread.join(timeout=max(0, deadline - time.monotonic()))
            if thread.is_alive():
                raise RuntimeError("Preview has not stopped. Keep the app open and retry Quit.")
        for process in list(self.processes.values()):
            if process.poll() is None:
                _kill_process_tree(process.pid)
        for thread in list(self.download_threads.values()):
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("Model installation has not stopped. Retry Quit.")
        if self.worker.ident is not None:
            self.worker.join(timeout=15)
        if self.worker.is_alive():
            raise RuntimeError("Engine has not stopped; keep the service open and retry Quit.")

    def health(self, jobs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if jobs is None:
            from videoenhancer.service.events import generation

            with self._health_jobs_lock:
                current_generation = generation(self.home)
                if current_generation != self._health_jobs_generation:
                    _, self._health_jobs = self.store.event_state()
                    self._health_jobs_generation = current_generation
                jobs = self._health_jobs
        running = next((j for j in jobs if j["state"] == "running"), None)
        finalizing = next(
            (
                j
                for j in jobs
                if j.get("progress", {}).get("phase") == "finalizing"
                and j["state"] not in {"done", "failed", "cancelled", "paused"}
            ),
            None,
        )
        schedule_path = self.home / "schedule.json"
        schedule_stamp = (
            (schedule_path.stat().st_mtime_ns, schedule_path.stat().st_size)
            if schedule_path.exists()
            else None
        )
        if self._schedule_cache is None or schedule_stamp != self._schedule_stamp:
            self._schedule_cache = Schedule.from_file(schedule_path)
            self._schedule_stamp = schedule_stamp
        schedule = self._schedule_cache
        now = datetime.now(schedule.zone)
        window = schedule.current_interval(now)
        upcoming = schedule.next_interval(now)
        queued = any(j["state"] in {"queued", "running"} for j in jobs)
        state = (
            "Finalizing"
            if finalizing
            else "Running"
            if running
            else "Paused"
            if self.paused or any(j["state"] == "paused" for j in jobs) and not queued
            else "Waiting for your hours"
            if queued and window is None
            else "Idle"
        )
        if any(
            op["state"] == "running" and not op["request"].get("_network_only")
            for op in self.operations.values()
        ):
            state = "Running"
        if time.monotonic() - self._registry_checked >= 60 or not self._cached_sac:
            self._registry_checked = time.monotonic()
            sac = {"status": "unknown", "blocked": False, "message": None}
            if os.name == "nt":
                import winreg

                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy"
                    ) as key:
                        value = winreg.QueryValueEx(key, "VerifiedAndReputablePolicyState")[0]
                    sac["status"] = {0: "off", 1: "enforced", 2: "evaluation"}.get(value, "unknown")
                except OSError:
                    pass
            self._cached_sac = sac
            profile = (
                load_machine_profile(
                    self.home,
                    gpu_name=self.environment.get("gpu"),
                    driver=self.environment.get("driver"),
                )
                if self.environment.get("gpu")
                else None
            )
            installed = {
                m["id"] for m in ModelRegistry(self.home).list_models() if m.get("weights_verified")
            }
            reference_seconds = sum(
                float(entry.get("seconds", 0))
                for key, entry in (profile or {}).get("reference_pipelines", {}).items()
                if key.split(":")[0] in installed
            )
            calibration_seconds = float(
                (profile or {}).get("calibration_wall_seconds") or max(60, reference_seconds + 120)
            )
            self._speed_profile = {
                "source": (profile or {}).get("source", "defaults"),
                "driver_note": (profile or {}).get("driver_note"),
                "calibration_minutes": max(1, round(calibration_seconds / 60)),
                "profile_path": (profile or {}).get("profile_path"),
            }
        sac = dict(self._cached_sac)
        errors = [str(j.get("error", "")) for j in jobs] + [
            self.last_error["message"] if self.last_error else ""
        ]
        problem = next((e for e in errors if "Smart App Control" in e), None)
        if problem:
            sac.update(blocked=True, message=problem)
        current = finalizing or running
        return {
            "speed_profile": self._speed_profile,
            "storage_undo_ids": [
                j["id"]
                for j in jobs
                if j.get("history_undo_remaining") and j.get("history_hidden_until")
            ],
            "paused_all": self.paused,
            "waiting_count": sum(j["state"] in {"queued", "paused", "preparing"} for j in jobs),
            "version": __version__,
            **self.environment,
            "engine_state": state,
            "smart_app_control": sac,
            "job_id": current["id"] if current else None,
            "next_change": (
                None
                if not schedule.enabled and not schedule.override_until
                else window.end.isoformat()
                if window
                else upcoming.start.isoformat()
                if upcoming
                else None
            ),
            "next_change_kind": "Pauses" if window else "Starts",
            "last_error": self.last_error,
            "home": str(self.home),
            "deletion_notices": list(self.deletion.notices),
            "av1_supported": self.environment.get("av1_supported", False),
            "av1_unavailable_reason": self.environment.get(
                "av1_unavailable_reason", "Checking AV1 hardware encoding…"
            ),
        }

    def queue(
        self, jobs: list[dict[str, Any]] | None = None, plan: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        jobs = self.store.queue_jobs() if jobs is None else jobs
        jobs = [
            job
            for job in jobs
            if not job.get("history_hidden_until") and not job.get("remove_on_cancel")
        ]
        jobs = self._forecast_jobs(jobs)
        if plan is None:
            plan = _jobs_plan([j for j in jobs if j["state"] != "preparing"], self.home, days=120)
        completion = {j["job_id"]: j for j in plan["jobs"]}
        rows = []
        file_stats: dict[str, os.stat_result | None] = {}

        def file_info(path: str) -> os.stat_result | None:
            if path not in file_stats:
                try:
                    info = os.stat(path)
                    file_stats[path] = info if stat.S_ISREG(info.st_mode) else None
                except OSError:
                    file_stats[path] = None
            return file_stats[path]

        for j in jobs:
            terminal = j["state"] in {"done", "failed", "cancelled"}
            previous_row = self._history_rows.get(j["id"])
            if terminal and previous_row and previous_row[0][0] != j["updated_at"]:
                for path in (j["input"]["path"], j["output"]):
                    self._file_cache[path] = file_info(path)
            infos = []
            for path in (j["input"]["path"], j["output"]):
                if terminal:
                    if path not in self._file_cache:
                        self._file_cache[path] = file_info(path)
                    infos.append(self._file_cache[path])
                else:
                    infos.append(file_info(path))
            original_info, output_info = infos

            def content_stamp(info: os.stat_result | None) -> tuple[int, ...] | None:
                if info is None:
                    return None
                return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)

            stamp = (
                j["updated_at"],
                j["state"],
                j.get("control_generation"),
                tuple(
                    (notice["id"], notice["result"])
                    for notice in self.deletion.notices
                    if notice.get("job_id") == j["id"]
                ),
                content_stamp(original_info),
                content_stamp(output_info),
            )
            terminal = j["state"] in {"done", "failed", "cancelled"}
            cached = self._history_rows.get(j["id"])
            if terminal and cached is not None and cached[0] == stamp:
                rows.append(cached[1])
                continue
            if (
                j["state"] == "running"
                and j["id"] in self.live_progress
                and j.get("progress", {}).get("phase") != "finalizing"
            ):
                j["progress"] = self.live_progress[j["id"]]
            done = [s for s in j["segments"] if s["state"] == "done"]
            active = next((s for s in j["segments"] if s["state"] == "running"), None)
            stats = done[-1].get("stats", {}) if done else {}
            preview_running = any(
                op["kind"] in {"trial", "compare"} and op["state"] == "running"
                for op in list(self.operations.values())
            )
            if preview_running and j["state"] == "queued":
                j["progress"] = dict(phase="processing", step="Paused for a preview")
            rows.append(
                {
                    "id": j["id"],
                    "state": j["state"],
                    "input": j["input"]["path"],
                    "output": j["output"],
                    "settings": j["settings"],
                    "media": j["media"],
                    "error": j.get("error"),
                    "estimate": (
                        estimate_job(j).to_dict()
                        if j["state"] != "preparing"
                        else dict(seconds=0, low=0, high=0, calibrated=False)
                    ),
                    "eta": (
                        max(
                            (
                                e["end"]
                                for e in j.get("timing", {}).get("events", [])
                                if e.get("step") == "aggregating"
                            ),
                            default=j["updated_at"],
                        )
                        if j["state"] == "done"
                        else completion.get(j["id"], {}).get("completion")
                    ),
                    "position": j.get("position"),
                    "part_seconds": next(
                        (
                            segment.get("predicted_seconds", 0)
                            for segment in j["segments"]
                            if segment["state"] != "done"
                        ),
                        0,
                    ),
                    "overrun_seconds": max(
                        (
                            step.get("overrun_seconds", 0)
                            for step in plan["timeline"]
                            if step["job_id"] == j["id"]
                        ),
                        default=0,
                    ),
                    "fps": j.get("progress", {}).get("fps", stats.get("fps")),
                    "segment": active["index"] + 1 if active else len(done),
                    "completed_segments": len(done),
                    "segments": len(j["segments"]),
                    **job_progress(j),
                    "log": str(self.store.job_dir(j["id"]) / "job.jsonl"),
                    "started_at": j.get("started_at"),
                    "finished_at": j.get("finished_at"),
                    "took_seconds": j.get("took_seconds"),
                    "output_bytes": output_info.st_size
                    if j["state"] == "done" and output_info is not None
                    else None,
                    "mode": j["settings"]["preset"],
                    "original_bytes": original_info.st_size
                    if original_info is not None
                    else j["input"].get("size"),
                    "output_folder": str(Path(j["output"]).parent),
                    "failure_reason": j.get("error"),
                    "output_changed": bool(
                        output_info is not None
                        and j.get("output_identity")
                        and (
                            output_info.st_size != j["output_identity"].get("size")
                            or output_info.st_mtime_ns != j["output_identity"].get("mtime_ns")
                        )
                    ),
                    "file_removal_warnings": [
                        result
                        for result in j.get("video_deletions", {}).values()
                        if result.startswith("Kept:")
                    ],
                    "interpolation_fallback_parts": sum(
                        bool(part.get("stats", {}).get("interpolation_fallbacks"))
                        for part in j["segments"]
                    ),
                    "original_state": "present"
                    if original_info is not None
                    else "recycled"
                    if j.get("video_deletions", {}).get("original", j.get("original_delete_result"))
                    == "Moved to the Recycle Bin"
                    else "missing",
                    "output_state": "present"
                    if output_info is not None
                    else "recycled"
                    if j.get("video_deletions", {}).get("output") == "Moved to the Recycle Bin"
                    else "missing",
                    "original_delete_result": j.get("original_delete_result"),
                    "video_deletions": j.get("video_deletions", {}),
                    "deletion_notices": [
                        notice
                        for notice in self.deletion.notices
                        if notice.get("job_id") == j["id"]
                    ],
                    "cancel_cleanup": j.get("cancel_cleanup", False),
                    "preview_ready": bool(done),
                    "starts": next(
                        (step["start"] for step in plan["timeline"] if step["job_id"] == j["id"]),
                        None,
                    ),
                }
            )
            if terminal:
                self._history_rows[j["id"]] = (stamp, rows[-1])
        completions = [j["eta"] for j in rows if j["state"] not in {"cancelled", "failed"}]
        with self.lock:
            operations = json.loads(json.dumps(list(self.operations.values())))
        current = next((j for j in jobs if j["state"] == "running"), None)
        remaining = 0.0
        if current:
            active = next((s for s in current["segments"] if s["state"] == "running"), None)
            if active:
                packet = self.live_progress.get(current["id"]) or current.get("progress") or {}
                frames = float(packet.get("frames_done", 0))
                elapsed = float(packet.get("elapsed_seconds", 0))
                remaining = (
                    max(0, (active["end"] - active["start"] - frames) * elapsed / frames)
                    if frames > 0 and elapsed > 0
                    else float(active.get("predicted_seconds", 180))
                )
        for op in operations:
            if op["state"] == "waiting":
                op["remaining_seconds"] = remaining
                op["phase"] = (
                    f"Waiting for the current part of {Path(current['input']['path']).name} "
                    f"to finish · about {int(remaining) // 60}:{int(remaining) % 60:02d}"
                    if current
                    else "Starting…"
                )
        return {
            "jobs": rows,
            "history_revision": str(
                hash(
                    tuple(
                        (row["id"], self._history_rows.get(row["id"], (None,))[0])
                        for row in rows
                        if row["state"] in {"done", "failed", "cancelled"}
                    )
                )
            ),
            "completion": max(completions) if completions and all(completions) else None,
            "operations": operations,
        }

    def refresh_terminal_files(self, paths: list[str] | None = None) -> None:
        if paths is None:
            paths = [
                str(path)
                for job in (self._event_jobs or self.store.queue_jobs())
                if job["state"] in {"done", "failed", "cancelled"}
                for path in (job["input"]["path"], job["output"])
            ]
        with self._event_build_lock:
            updated = False
            for path in set(paths):
                before = self._file_cache.get(path)
                try:
                    info = os.stat(path)
                    self._file_cache[path] = info if stat.S_ISREG(info.st_mode) else None
                except OSError:
                    self._file_cache[path] = None
                after = self._file_cache[path]

                def stamp(info: os.stat_result | None) -> tuple[Any, ...] | None:
                    return (
                        (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)
                        if info
                        else None
                    )

                updated = updated or stamp(before) != stamp(after)
            self._file_checked = time.monotonic()
            if updated:
                self._file_generation += 1

    def event_snapshot(self) -> dict[str, Any]:
        """Rebuild structural data only after a change; progress is a separate packet."""
        from videoenhancer.service.events import generation

        with self._event_build_lock:
            now = time.monotonic()
            current_generation = generation(self.home)
            if current_generation != self._structure_generation or self._event_cache is None:
                revisions, health_jobs = self.store.event_state()
                self._structure_records = (
                    tuple(revisions),
                    [
                        job
                        for job in health_jobs
                        if job["state"] not in {"done", "failed", "cancelled"}
                    ],
                )
                self._structure_checked = now
                self._structure_generation = current_generation
            revisions, health_jobs = self._structure_records
            with self.lock:
                operation_key = tuple(
                    (
                        op["id"],
                        op.get("state"),
                        op.get("phase"),
                        op.get("percent"),
                        id(op.get("result")),
                        op.get("error"),
                    )
                    for op in self.operations.values()
                )
            health = self.health(health_jobs)
            key = (
                revisions,
                operation_key,
                self._schedule_stamp,
                self.paused,
                self._file_generation,
                json.dumps(health, sort_keys=True, default=str),
            )
            if key != self._event_key:
                jobs = self.store.queue_jobs()
                self._event_jobs = jobs
                self._event_running_jobs = [job for job in jobs if job["state"] == "running"]
                jobs = self._forecast_jobs(jobs)
                plan = _jobs_plan([j for j in jobs if j["state"] != "preparing"], self.home, 120)
                self._event_cache = {
                    "queue": self.queue(jobs, plan),
                    "plan": plan,
                    "health": health,
                }
                self._event_key, self._event_built = key, now
            return self._event_cache or {}

    def _publish_events(self) -> None:
        while not self.stop.is_set():
            try:
                self._build_event_message()
                self._build_progress_message()
            except Exception:
                get_logger(self.home).exception("Event publication failed")
            self.stop.wait(0.5)

    def event_message(self) -> str:
        if not self._publishing:
            return self._build_event_message()
        with self._event_lock:
            return self._event_wire

    def progress_message(self) -> str:
        if not self._publishing:
            return self._build_progress_message()
        with self._event_lock:
            return self._progress_wire

    def _build_event_message(self) -> str:
        """Share cached serialised terminal rows across clients."""
        with self._event_build_lock:
            snapshot = self.event_snapshot()
            if self._event_key != self._event_wire_key:
                queue = snapshot["queue"]
                wires = []
                for row in queue["jobs"]:
                    stamp = self._history_rows.get(row["id"], (None,))[0]
                    cached = self._history_wire.get(row["id"])
                    if (
                        row["state"] in {"done", "failed", "cancelled"}
                        and cached is not None
                        and cached[0] == stamp
                    ):
                        wire = cached[1]
                    else:
                        wire = json.dumps(row, default=str, allow_nan=False)
                        if row["state"] in {"done", "failed", "cancelled"}:
                            self._history_wire[row["id"]] = (stamp, wire)
                    wires.append(wire)
                small_queue = json.dumps(
                    {k: v for k, v in queue.items() if k != "jobs"}, default=str, allow_nan=False
                )
                queue_wire = '{"jobs":[' + ",".join(wires) + "]," + small_queue[1:]
                self._event_wire = (
                    '{"queue":'
                    + queue_wire
                    + ',"plan":'
                    + json.dumps(snapshot["plan"], default=str)
                    + ',"health":'
                    + json.dumps(snapshot["health"], default=str)
                    + "}"
                )
                self._event_wire_key = self._event_key
            return self._event_wire

    def _build_progress_message(self) -> str:
        with self._event_build_lock:
            now = time.monotonic()
            if now - self._progress_built < 1 and self._progress_wire:
                return self._progress_wire

            packets = []
            planning_jobs = self._forecast_jobs(
                [
                    job
                    for job in self._event_jobs
                    if job["state"] not in {"done", "failed", "cancelled"}
                ]
            )
            live_jobs = {job["id"]: job for job in planning_jobs if job["state"] == "running"}
            for work in live_jobs.values():
                row = work
                live = work.get("progress") or {}
                rate = float(live.get("fps") or 0)
                elapsed = 0.0
                status = job_progress(work)
                remaining = max(0, estimate_job(work).seconds - (elapsed if rate <= 0 else 0))
                packets.append(
                    dict(
                        id=row["id"],
                        percent=status["progress_percent"],
                        work_left=remaining,
                        finish_time="",
                        fps=rate or None,
                        phase=status["phase"],
                        step=status["step"],
                    )
                )
            if packets:
                plan = _jobs_plan(planning_jobs, self.home, 120)
                finishes = {job["job_id"]: job["completion"] for job in plan["jobs"]}
                for packet in packets:
                    packet["finish_time"] = finishes.get(packet["id"]) or ""
                for job in planning_jobs:
                    if job["id"] not in live_jobs and job["state"] == "queued":
                        packets.append(
                            dict(
                                id=job["id"],
                                percent=0,
                                work_left=estimate_job(job).seconds,
                                finish_time=finishes.get(job["id"]) or "",
                                phase="queued",
                                step="Waiting",
                            )
                        )
            self._progress_built = now
            self._progress_wire = (
                json.dumps({"progress": packets}, allow_nan=False) if packets else ""
            )
            return self._progress_wire

    def thumbnail(self, job_id: str) -> Path:
        import hashlib

        from videoenhancer.config import executable

        job = self.store.load(job_id)
        source = Path(job["output"] if job["state"] == "done" else job["input"]["path"])
        stat = source.stat()
        key = hashlib.sha256(
            f"{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode()
        ).hexdigest()
        folder = self.home / "cache" / "thumbnails"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{key}.jpg"
        if not target.exists():
            temporary = folder / f"{key}.{uuid.uuid4().hex}.jpg"
            try:
                proc.run(
                    [
                        executable("ffmpeg"),
                        "-v",
                        "error",
                        "-nostdin",
                        "-ss",
                        str(float(job["media"].get("duration", 0)) * 0.1),
                        "-i",
                        str(source),
                        "-vf",
                        "scale=266:266:force_original_aspect_ratio=decrease",
                        "-frames:v",
                        "1",
                        "-threads",
                        "2",
                        str(temporary),
                    ],
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return target

    def chosen(self, value: dict[str, Any]) -> dict[str, Any]:
        prefs = read_settings(self.home)
        settings = {
            k: prefs[k] for k in ("preset", "codec", "short_side", "fps", "delete_original_after")
        }
        for key in (
            "restore_model",
            "interp_model",
            "size_model",
            "restore_strength",
            "size_strength",
        ):
            if prefs[key]:
                settings[key] = prefs[key]
        settings.update(prefs["advanced"])
        settings.update(value)
        if settings["preset"] != "standard":
            settings.pop("restore_model", None)
        settings["backend"] = choose_backend(settings.get("backend", "auto"))
        if settings["preset"] not in {"standard", "fast", "passthrough", "resize", "p0-test"}:
            raise ValueError("Invalid preset.")
        if settings["codec"] not in {"h264", "hevc", "av1"}:
            raise ValueError("Invalid codec.")
        if settings["short_side"] not in {"keep", 1080, 1440, 2160}:
            raise ValueError("Invalid output short side.")
        if settings["fps"] not in {"off", "2x"}:
            raise ValueError("Invalid frame rate.")
        if settings.get("restore_strength", "medium") not in {"light", "medium", "strong"}:
            raise ValueError("Invalid cleanup strength.")
        if settings.get("size_strength", 0.2) not in {0.2, 0.6}:
            raise ValueError("Invalid enlarger strength.")
        if not isinstance(settings.get("delete_original_after", False), bool):
            raise ValueError("Delete original must be on or off.")
        return settings

    def output(self, source: Path, value: dict[str, Any]) -> Path:
        if value.get("output"):
            return Path(value["output"]).resolve()
        folder = value.get("output_folder") or read_settings(self.home)["output_folder"]
        return (
            Path(folder) if folder else source.parent / "enhanced"
        ) / f"{source.stem}_enhanced.mp4"

    def estimate(
        self, value: dict[str, Any], virtual_jobs: dict[str, list[dict[str, Any]]] | None = None
    ) -> dict[str, Any]:
        if "files" in value:
            files = value["files"]
            if (
                not isinstance(files, list)
                or not 1 <= len(files) <= 100
                or any(not isinstance(file, str) for file in files)
            ):
                raise ValueError("Choose between 1 and 100 videos.")
            virtuals: dict[str, list[dict[str, Any]]] = {"standard": [], "fast": []}
            previews: dict[str, Any] = {}
            for index, file in enumerate(files):
                item = {key: data for key, data in value.items() if key != "files"}
                item["settings"] = {
                    **value.get("settings", {}),
                    **value.get("file_settings", {}).get(file, {}),
                }
                if "output_folder" in item["settings"]:
                    item["output_folder"] = item["settings"]["output_folder"]
                try:
                    previews[file] = self.estimate(
                        {**item, "file": file, "virtual_id": f"preview-{index}"}, virtuals
                    )
                except Exception as error:
                    previews[file] = {"error": str(error), "warnings": [], "presets": {}}
            presets = {}
            plans = {}
            queued = self.store.list_jobs()
            for preset, jobs in virtuals.items():
                plan = _jobs_plan(queued + jobs, self.home, 120)
                plans[preset] = plan
                finish = {job["job_id"]: job["completion"] for job in plan["jobs"]}
                for index, file in enumerate(files):
                    if "error" in previews[file]:
                        continue
                    previews[file]["presets"][preset]["finish"] = finish.get(f"preview-{index}")
                estimates = [
                    preview["presets"][preset]
                    for preview in previews.values()
                    if "error" not in preview
                ]
                presets[preset] = {
                    key: sum(estimate[key] for estimate in estimates)
                    for key in ("seconds", "low", "high")
                }
                presets[preset].update(
                    calibrated=all(estimate["calibrated"] for estimate in estimates),
                    unknown_models=sorted(
                        {
                            model
                            for estimate in estimates
                            for model in estimate.get("unknown_models", [])
                        }
                    ),
                    finish=finish.get(f"preview-{len(files) - 1}"),
                )
            selected = []
            for index, file in enumerate(files):
                chosen = {
                    **value.get("settings", {}),
                    **value.get("file_settings", {}).get(file, {}),
                }
                preset = chosen.get("preset", "standard")
                if preset not in virtuals:
                    preset = "fast"
                selected.extend(job for job in virtuals[preset] if job["id"] == f"preview-{index}")
            selected_plan = (
                _jobs_plan(queued + selected, self.home, 120)
                if value.get("file_settings")
                else plans.get(self.chosen(value.get("settings", {}))["preset"], plans["fast"])
            )
            selected_finishes = {job["job_id"]: job["completion"] for job in selected_plan["jobs"]}
            for index, file in enumerate(files):
                if "error" not in previews[file]:
                    chosen = {
                        **value.get("settings", {}),
                        **value.get("file_settings", {}).get(file, {}),
                    }
                    previews[file]["presets"][
                        chosen.get("preset") if chosen.get("preset") in virtuals else "fast"
                    ]["finish"] = selected_finishes.get(f"preview-{index}")
            return {
                "files": previews,
                "presets": presets,
                "selected_seconds": sum(estimate_job(job).seconds for job in selected),
                "selected_finish": selected_finishes.get(selected[-1]["id"]) if selected else None,
            }
        source = Path(value["file"]).resolve(strict=True)
        media = probe(source, allow_hdr=True).to_dict()
        settings = self.chosen(value.get("settings", {}))
        output = self.output(source, value)
        size = source.stat().st_size
        output_bytes = estimated_output_size(size, media, settings)
        ancestor = output.parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        locations = working_space_locations(self.home, output.parent)
        needed = int(output_bytes * locations[0][1] * 1.1)
        free = shutil.disk_usage(locations[0][0]).free
        warnings = []
        support = self.environment.get("software_decoders", {})
        codec = media.get("codec")
        if codec in {"vp9", "av1"} and support.get(codec) is False:
            warnings.append(
                f"This FFmpeg build cannot read {str(codec).upper()} videos. "
                "Install a build with software decoding support."
            )
        geometry = self.geometry_warning(media, settings)
        if geometry:
            warnings.append(geometry)
        if settings["short_side"] != "keep" and min(
            media.get("display_width") or media.get("width", 720),
            media.get("display_height") or media.get("height", 1280),
        ) > int(settings["short_side"]):
            source_short = min(
                media.get("display_width") or media["width"],
                media.get("display_height") or media["height"],
            )
            warnings.append(
                f"This video is larger than {settings['short_side']}p, so output keeps its size "
                f"({source_short}p)."
            )
        for location, copies in locations:
            required = int(output_bytes * copies * 1.1)
            available = shutil.disk_usage(location).free
            if available < required:
                warnings.append(
                    f"Insufficient space: Needs {required / 1e9:.2f} GB, "
                    f"{available / 1e9:.2f} GB free on {location.anchor or location}."
                )
        if str(media.get("color_transfer", "")) in {"smpte2084", "arib-std-b67"}:
            warnings.append("HDR is not supported. Choose an SDR video.")
        if self.health()["smart_app_control"]["blocked"]:
            warnings.append("Windows Smart App Control is blocking the video component.")
        comparisons = {}
        queue = self.store.list_jobs()
        for preset in ("standard", "fast"):
            from videoenhancer.estimate import predict_segment
            from videoenhancer.jobs.segments import plan_segments

            chosen = self.chosen({**settings, "preset": preset})
            registry = ModelRegistry(self.home)
            identities = {}
            for task, model_id in selected_models(chosen, media).items():
                try:
                    identities[task] = registry.snapshot(model_id, task, download=False)
                except ValueError:
                    pass  # Preview estimates never install missing weights.
            profile = load_machine_profile(self.home, backend=chosen["backend"], models=identities)
            per_frame = predict_segment(media, chosen, max(1, media["frame_count"]), profile) / max(
                1, media["frame_count"]
            )
            virtual = {
                "id": value.get("virtual_id", "preview"),
                "state": "queued",
                "media": media,
                "settings": chosen,
                "input": input_identity(source),
                "estimated_output_bytes": estimated_output_size(size, media, chosen),
                "segments": plan_segments(
                    media, [], predicted_seconds_per_frame=per_frame, target_seconds=180
                ),
                "machine_profile": profile,
                "correction_factor": recent_correction(
                    self.store, chosen["preset"], profile, media, chosen
                ),
            }
            estimate = estimate_job(virtual).to_dict()
            if virtual_jobs is not None:
                virtual_jobs[preset].append(virtual)
                plan = {"jobs": []}
            else:
                plan = _jobs_plan(queue + [virtual], self.home, 120)
            comparisons[preset] = {
                **estimate,
                "finish": next(
                    (j["completion"] for j in plan["jobs"] if j["job_id"] == virtual["id"]), None
                ),
            }
        return {
            "media": media,
            "presets": comparisons,
            "warnings": warnings,
            "disk": {"free_bytes": free, "required_bytes": needed},
            "output": str(output),
        }

    def add(self, value: dict[str, Any]) -> dict[str, Any]:
        source = Path(value["file"]).resolve(strict=True)
        job_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()
        settings = {**read_settings(self.home), **value.get("settings", {})}
        check = self.estimate({**value, "file": str(source), "settings": settings})
        blocking = [
            warning
            for warning in check["warnings"]
            if not warning.startswith("This video is larger than")
        ]
        if blocking:
            raise ValueError(blocking[0])
        if settings.get("codec") == "av1":
            chosen = self.chosen(settings)
            warning = self.geometry_warning(probe(source, read_timeline=False).to_dict(), chosen)
            if warning:
                raise ValueError(warning)
        output = self.output(source, value)
        job = dict(
            schema_version=1,
            id=job_id,
            input={"path": str(source)},
            output=str(output),
            settings=settings,
            media=dict(display_width=0, display_height=0, cfr_fps="30", frame_count=0, duration=0),
            segments=[],
            state="preparing",
            created_at=now,
            updated_at=now,
            estimated_output_bytes=0,
            correction_factor=1,
            initial_estimate_seconds=check["presets"].get(
                settings["preset"], check["presets"]["fast"]
            )["seconds"],
            initial_finish_at=check["presets"].get(settings["preset"], check["presets"]["fast"])[
                "finish"
            ],
            control_generation=0,
        )
        with self._mutation_lock:
            from videoenhancer.jobs.store import _require_unreserved_output

            _require_unreserved_output(self.store, output)
            job["position"] = len(self.store.list_jobs()) + 1
            self.store.save(job)

        def prepare() -> None:
            try:
                chosen = self.chosen(settings)
                registry = ModelRegistry(self.home)
                for task, model_id in selected_models(chosen).items():
                    registry.weights(registry.manifest(model_id, task), download=False)
                geometry = self.geometry_warning(probe(source).to_dict(), chosen)
                if geometry:
                    raise ValueError(geometry)
                add_job(
                    source,
                    chosen,
                    output=output,
                    home=self.home,
                    job_id=job_id,
                    target_segment_seconds=float(value.get("segment_seconds", 180)),
                )
                self.store.patch_existing(
                    job_id,
                    {
                        "initial_estimate_seconds": job["initial_estimate_seconds"],
                        "initial_finish_at": job["initial_finish_at"],
                        "created_at": job["created_at"],
                    },
                )
            except Exception as error:
                self._error(job_id, error)
                latest = self.store.load(job_id)
                latest.update(state="failed", error=f"Preparation failed: {error}")
                self.store.save(latest)

        thread = threading.Thread(target=prepare, name=f"prepare-{job_id}", daemon=True)
        self._preparations.append(thread)
        thread.start()
        return job

    def geometry_warning(self, media: dict[str, Any], settings: dict[str, Any]) -> str | None:
        from videoenhancer.jobs.checks import geometry_warning

        return geometry_warning(self.home, media, settings, self.environment)

    def remove(self, job_id: str) -> dict[str, Any]:
        import logging

        job = self.store.load(job_id)
        directory = self.store.job_dir(job_id).resolve()
        if any(
            Path(path).resolve().is_relative_to(directory)
            for path in (job["input"]["path"], job["output"])
        ):
            raise ValueError("Kept: a recorded video path is inside this job's work folder.")
        if job["state"] not in {"done", "cancelled", "failed"}:
            raise ValueError("Cancel the job or wait for it to finish before removing it.")
        if any(s["state"] == "running" for s in job["segments"]):
            raise ValueError("The current segment is stopping; retry shortly.")
        for op in list(self.operations.values()):
            if op.get("job_id") == job_id:
                self.cancel_operation(op["id"])
                if op["state"] == "running":
                    raise ValueError("The trial is stopping; retry shortly.")
                folder = self.home / "previews" / op["id"]
                if folder.exists():
                    shutil.rmtree(folder)
                self.operations.pop(op["id"], None)
        previews = self.home / "previews"
        if previews.exists():
            for request in previews.glob("*/request.json"):
                data = json.loads(request.read_text())
                if data.get("request", {}).get("job_id") == job_id:
                    shutil.rmtree(request.parent)
        directory = self.store.job_dir(job_id)
        logger = logging.getLogger(f"videoenhancer.{job_id}")
        for handler in list(logger.handlers):
            filename = getattr(handler, "baseFilename", None)
            if filename and Path(filename).is_relative_to(directory):
                logger.removeHandler(handler)
                handler.close()
        with _manifest_lock(self.store.jobs_dir):
            shutil.rmtree(directory)
        return {"removed": job_id, "output_preserved": True}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        job = self.store.load(job_id)
        if job["state"] in {"done", "failed", "cancelled"}:
            raise ValueError("Cancel is available for unfinished videos only.")
        busy = job["state"] in {"running", "preparing"} or any(
            segment["state"] == "running" for segment in job["segments"]
        )
        job["cancel_cleanup"] = True
        job["remove_on_cancel"] = not any(segment["state"] == "done" for segment in job["segments"])
        self.store.save(job)
        job = self.store.set_state(job_id, "cancelled")
        if not busy:
            return self._clean_cancelled(job)
        return job

    def history_operation(self, action: str, value: dict[str, Any]) -> dict[str, Any]:
        self._validate_history_choices(value)
        ids = value.get("ids")
        if action == "clear":
            ids = [
                job["id"]
                for job in self.store.list_jobs()
                if job["state"] in {"done", "failed", "cancelled"}
            ]
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
            raise ValueError("Choose at least one History record.")
        jobs = [self.store.load(job_id) for job_id in dict.fromkeys(ids)]
        if any(job["state"] not in {"done", "failed", "cancelled"} for job in jobs):
            raise ValueError("Only finished, failed or cancelled records can be removed.")
        for key in ("output", "original"):
            if not isinstance(value.get(key, False), bool):
                raise ValueError("File removal choices must be on or off.")
        op: dict[str, Any] = dict(
            id=uuid.uuid4().hex,
            kind="history-removal",
            state="running",
            phase="Removing files",
            request={**value, "ids": ids},
            created_at=datetime.now().astimezone().isoformat(),
            percent=0,
            completed_files=0,
            total_files=len(jobs) * sum(bool(value.get(key)) for key in ("output", "original")),
            result={
                "ids": [],
                "undo_seconds": 10 if value.get("history", True) else 0,
                "files": {"moved": 0, "not_found": 0, "kept": 0},
                "kept": [],
            },
        )
        with self.lock:
            self.operations[op["id"]] = op
        self._save_operation(op)

        def remove_files() -> None:
            try:
                result = self.history_action("remove", {**value, "ids": ids}, op)
                with self.lock:
                    op.update(state="done", phase="Complete", percent=100, result=result)
                    op["completed_at"] = datetime.now().astimezone().isoformat()
            except Exception as error:
                with self.lock:
                    op.update(state="failed", error=str(error))
                self._error(None, error)
            finally:
                self._save_operation(op)

        thread = threading.Thread(target=remove_files, name=f"history-{op['id']}", daemon=True)
        self._history_threads.append(thread)
        response = copy.deepcopy(op)
        thread.start()
        return response

    def history_action(
        self, action: str, value: dict[str, Any], operation: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with self._mutation_lock:
            if action in {"remove", "clear"}:
                self._validate_history_choices(value)
            failures: list[str] = []
            kept: list[dict[str, str]] = []
            counts = {"moved": 0, "not_found": 0, "kept": 0}
            ids = value.get("ids")
            if action == "clear":
                ids = [
                    job["id"]
                    for job in self.store.list_jobs()
                    if job["state"] in {"done", "failed", "cancelled"}
                ]
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
                raise ValueError("Choose at least one History record.")
            jobs = [self.store.load(job_id) for job_id in dict.fromkeys(ids)]
            if any(job["state"] not in {"done", "failed", "cancelled"} for job in jobs):
                raise ValueError("Only finished, failed or cancelled records can be removed.")
            now = time.time()
            if action in {"undo", "pause-undo"} and any(
                not job.get("history_hidden_until") or job["history_hidden_until"] <= now
                for job in jobs
            ):
                raise ValueError("Undo is no longer available.")
            for job in jobs:
                if action == "pause-undo":
                    if value.get("paused") is True:
                        job["history_undo_remaining"] = max(
                            0, job.get("history_hidden_until", 0) - now
                        )
                        job["history_hidden_until"] = now + 315360000
                    elif value.get("paused") is False:
                        job["history_hidden_until"] = now + job.pop("history_undo_remaining", 0)
                        self._schedule_history_removal(job)
                    else:
                        raise ValueError("Undo pause must be on or off.")
                    self.store.save(job)
                elif action == "undo":
                    job["history_hidden_until"] = 0
                    self.store.save(job)
                else:
                    refused = False
                    for key in ("output", "original"):
                        if not isinstance(value.get(key, False), bool):
                            raise ValueError("File removal choices must be on or off.")
                        if value.get(key):
                            path = Path(job["output"] if key == "output" else job["input"]["path"])
                            assert_io_unlocked()
                            result = self.deletion.delete(path, job, self.store.list_jobs())
                            job.setdefault("video_deletions", {})[key] = result
                            self.store.save(job)
                            category = (
                                "moved"
                                if result == "Moved to the Recycle Bin"
                                else "not_found"
                                if result == "File not found"
                                else "kept"
                            )
                            counts[category] += 1
                            if category == "kept":
                                refused = True
                                kept.append({"id": job["id"], "reason": result})
                            if operation is not None:
                                with self.lock:
                                    operation["completed_files"] += 1
                                    operation.update(
                                        percent=100
                                        * operation["completed_files"]
                                        / operation["total_files"],
                                        current_file={
                                            "id": job["id"],
                                            "kind": key,
                                            "outcome": result,
                                        },
                                    )
                                    operation["result"].update(files=dict(counts), kept=list(kept))
                                self._save_operation(operation)
                            self.refresh_terminal_files([str(path)])
                    if refused or not value.get("history", True):
                        self.store.save(job)
                        continue
                    job["history_hidden_until"] = time.time() + 10
                    self.store.save(job)
                    self._schedule_history_removal(job)
                    if operation is not None:
                        with self.lock:
                            operation["result"]["ids"].append(job["id"])
                        self._save_operation(operation)
            if operation is not None:
                for job in jobs:
                    if job.get("history_hidden_until"):
                        job["history_hidden_until"] = time.time() + 10
                        self.store.save(job)
                        self._schedule_history_removal(job)
            if failures:
                raise ValueError("History entries not removed: " + "; ".join(failures))
            return {
                "ids": [
                    job["id"]
                    for job in jobs
                    if action in {"undo", "pause-undo"} or job.get("history_hidden_until")
                ],
                "undo_seconds": 10
                if action in {"remove", "clear"} and value.get("history", True)
                else 0,
                "files": counts,
                "kept": kept,
            }

    @staticmethod
    def _validate_history_choices(value: dict[str, Any]) -> None:
        for key in ("history", "output", "original"):
            if not isinstance(value.get(key, key == "history"), bool):
                raise ValueError("Removal choices must be on or off.")
        if not any(value.get(key, key == "history") for key in ("history", "output", "original")):
            raise ValueError("Choose at least one removal option.")

    def _schedule_history_removal(self, job: dict[str, Any]) -> None:
        def expire() -> None:
            with self._mutation_lock:
                if not (self.store.job_dir(job["id"]) / "manifest.json").exists():
                    return
                latest = self.store.load(job["id"])
                if (
                    latest.get("history_hidden_until", 0)
                    and latest["history_hidden_until"] <= time.time()
                ):
                    try:
                        self.remove(job["id"])
                    except Exception as error:
                        latest["history_hidden_until"] = 0
                        self.store.save(latest)
                        self._error(job["id"], error)

        timer = threading.Timer(max(0, job["history_hidden_until"] - time.time()), expire)
        timer.daemon = True
        self._history_timers.append(timer)
        timer.start()

    def _clean_cancelled(self, job: dict[str, Any]) -> dict[str, Any]:
        if job.get("remove_on_cancel"):
            return self.remove(job["id"])
        directory = self.store.job_dir(job["id"])
        videos = [Path(job["input"]["path"]).resolve(), Path(job["output"]).resolve()]
        for path in directory.iterdir():
            if any(
                video == path.resolve() or video.is_relative_to(path.resolve()) for video in videos
            ):
                continue
            if path.name in {
                "manifest.json",
                "analysis.json",
                "control.json",
                "manifest.lock",
                "logs",
            } or path.suffix in {".log", ".jsonl"}:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        job["cancel_cleanup"] = False
        self.store.save(job)
        return job

    def _finish_cancellations(self) -> None:
        for job in self.store.list_jobs():
            preparing = any(
                thread.name == f"prepare-{job['id']}" and thread.is_alive()
                for thread in self._preparations
            )
            if (
                job.get("cancel_cleanup")
                and not preparing
                and not any(segment["state"] == "running" for segment in job["segments"])
            ):
                try:
                    self._clean_cancelled(job)
                except Exception as error:
                    job.update(
                        state="failed",
                        remove_on_cancel=False,
                        cancel_cleanup=False,
                        history_hidden_until=0,
                        error=f"Cancellation cleanup failed: {error}",
                    )
                    job["control_generation"] = int(job.get("control_generation", 0)) + 1
                    self.store.save(job)
                    self._error(job["id"], error)

    def operation(self, kind: str, value: dict[str, Any]) -> dict[str, Any]:
        if kind in {"trial", "compare"}:
            if value.get("seconds", 5) not in {3, 5, 10}:
                raise ValueError("Trial length must be 3, 5 or 10 seconds.")
            value = {**value, "settings": self.chosen(value.get("settings", {}))}
            if value.get("job_id"):
                job = self.store.load(value["job_id"])
                if Path(value["file"]).resolve() != Path(job["input"]["path"]).resolve():
                    raise ValueError("The trial file must match its job.")
                value["settings"] = job["settings"]
            if kind == "compare":
                models = value.get("models")
                if (
                    not isinstance(models, list)
                    or any(not isinstance(model_id, str) for model_id in models)
                    or not 1 <= len(models) <= 3
                    or len(set(models)) != len(models)
                ):
                    raise ValueError("Choose one to three different models of the same category.")
                registry = ModelRegistry(self.home)
                from videoenhancer.service.compare import compare_manifest

                manifests = [compare_manifest(registry, model_id) for model_id in models]
                if len({m["task"] for m in manifests}) != 1:
                    raise ValueError("Choose models of the same category.")
                if manifests[0]["task"] == "restore" and value["settings"]["preset"] == "fast":
                    raise ValueError(
                        "Fast does not clean up. Switch this video to Standard "
                        "to compare cleanup models."
                    )
                for model in manifests:
                    if model["id"] == "standard-resize":
                        continue
                    registry.weights(model, download=False)
                for task, model_id in selected_models(value["settings"]).items():
                    registry.weights(registry.manifest(model_id, task), download=False)
            if value["settings"]["preset"] not in {"standard", "fast"}:
                raise ValueError("Trial preset must be Standard or Fast.")
            geometry = self.geometry_warning(
                probe(Path(value["file"]), read_timeline=False).to_dict(), value["settings"]
            )
            if geometry:
                raise ValueError(geometry)
        waiting = 0.0
        for job in self.store.list_jobs():
            for segment in job["segments"]:
                if segment["state"] == "running":
                    waiting += float(segment.get("predicted_seconds", 180))
        op = {
            "id": uuid.uuid4().hex,
            "kind": kind,
            "state": "waiting",
            "request": value,
            "job_id": value.get("job_id"),
            "phase": "Waiting for the current part",
            "remaining_seconds": waiting,
            "created_at": datetime.now().astimezone().isoformat(),
        }
        if kind == "compare":
            for previous in list(self.operations.values()):
                if previous["kind"] == "compare" and previous["state"] in {"waiting", "running"}:
                    self.cancel_operation(previous["id"])
        self.operations[op["id"]] = op
        self._save_operation(op)
        if kind == "download":
            op.update(state="running", phase="Starting…", remaining_seconds=None, percent=0)
            value["_network_only"] = True
            value.pop("_verified_weight", None)
            from videoenhancer.service.downloads import gpu_test_prediction

            value["_gpu_test_seconds"] = 15.0
            if self.environment.get("gpu"):
                model = ModelRegistry(self.home).manifest(value["model_id"])
                profile = load_machine_profile(
                    self.home,
                    gpu_name=self.environment["gpu"],
                    driver=self.environment.get("driver"),
                )
                value["_gpu_test_seconds"] = gpu_test_prediction(model, profile)
            thread = threading.Thread(
                target=self._download_network, args=(op,), daemon=True, name="model-download"
            )
            self.download_threads[op["id"]] = thread
            thread.start()
        if kind == "compare":
            from videoenhancer.service.compare import prime_cached

            cached = prime_cached(value, self.home / "previews" / op["id"])
            if cached:
                op["result"] = cached
                if cached.get("original") and len(cached["items"]) == len(value["models"]):
                    op.update(state="done", phase="Reused preview", percent=100)
                self._save_operation(op)
                self._prune_compare_cache()
        return op

    def result_preview(self, job_id: str) -> dict[str, Any]:
        job = self.store.load(job_id)
        if not any(s["state"] == "done" for s in job["segments"]):
            raise ValueError("The first completed step is not ready yet.")
        op: dict[str, Any] = dict(
            id=uuid.uuid4().hex,
            kind="result-preview",
            state="running",
            job_id=job_id,
            request=dict(job_id=job_id),
            phase="Reading the completed result…",
            created_at=datetime.now().astimezone().isoformat(),
        )
        self.operations[op["id"]] = op
        self._save_operation(op)

        def render() -> None:
            from videoenhancer.service.preview import render_result_preview

            try:
                result = render_result_preview(
                    job,
                    self.store.job_dir(job_id),
                    self.home / "previews" / op["id"],
                    lambda: self.stop.is_set() or bool(op.get("cancel_requested")),
                )
                if self.stop.is_set() or op.get("cancel_requested"):
                    raise InterruptedError("Preview cancelled.")
                result["preview"] = {
                    name: f"/v1/operations/{op['id']}/files/{name}"
                    for name in ("original", "enhanced")
                }
                op.update(result=result, state="done", phase="Complete")
            except Exception as error:
                cancelled = self.stop.is_set() or op.get("cancel_requested")
                op.update(state="cancelled" if cancelled else "failed", error=str(error))
            finally:
                if op["state"] != "done":
                    for partial in (self.home / "previews" / op["id"]).glob("*.mp4"):
                        partial.unlink(missing_ok=True)
                self._save_operation(op)

        thread = threading.Thread(target=render, name="result-preview", daemon=True)
        self.preview_threads[op["id"]] = thread
        self._preparations.append(thread)
        thread.start()
        return op

    def cancel_operation(self, op_id: str) -> dict[str, Any]:
        op = self.operations[op_id]
        op["cancel_requested"] = True
        if op["state"] == "waiting":
            op["state"] = "cancelled"
        self._save_operation(op)
        process = self.processes.get(op_id)
        if process and process.poll() is None:
            _kill_process_tree(process.pid)
        return op

    def _auxiliary(self) -> None:
        self._finish_cancellations()
        from videoenhancer.service.deletion import schedule_original_deletions

        schedule_original_deletions(self.store)
        op = next((o for o in self.operations.values() if o["state"] == "waiting"), None)
        if not op or self.stop.is_set():
            return
        op.update(state="running", phase="Processing")
        op["request"]["_gpu_admitted_at"] = time.perf_counter()
        self._save_operation(op)
        try:
            self._run_operation(op)
            op.update(state="cancelled" if op.get("cancel_requested") else "done", phase="Complete")
        except Exception as error:
            op.update(
                state="cancelled"
                if op.get("cancel_requested") and not op.get("timed_out")
                else "failed",
                error=str(error),
            )
        finally:
            process = self.processes.get(op["id"])
            if process is not None and process.poll() is None:
                _kill_process_tree(process.pid)
            self.processes.pop(op["id"], None)
            self._save_operation(op)
            if op["kind"] == "compare":
                with self._mutation_lock:
                    if op["state"] != "done":
                        from videoenhancer.service.compare import discard_incomplete

                        discard_incomplete(self.home / "previews" / op["id"])
                        op.pop("result", None)
                        self._save_operation(op)
                    self._prune_compare_cache()

    def _download_network(self, op: dict[str, Any]) -> None:
        try:
            self._run_operation(op)
            if self.stop.is_set() or op.get("cancel_requested"):
                op.update(state="cancelled")
            else:
                op["request"]["_network_only"] = False
                op["request"]["_network_percent"] = op.get("percent", 0)
                op["request"]["_phase_seconds"] = op.get("expected_phase_seconds", {})
                op["request"]["_verified_weight"] = op.get("result", {}).pop(
                    "verified_weight", None
                )
                op.update(
                    state="waiting",
                    phase="Waiting for the current part to finish",
                    remaining_seconds=self._part_wait(),
                )
        except Exception as error:
            op.update(
                state="cancelled" if op.get("cancel_requested") else "failed", error=str(error)
            )
        finally:
            self.processes.pop(op["id"], None)
            self._save_operation(op)

    def _part_wait(self) -> float:
        remaining = 0.0
        for job in self.store.list_jobs():
            packet = self.live_progress.get(job["id"], {})
            for segment in job["segments"]:
                if segment["state"] == "running":
                    frames = float(packet.get("frames_done", 0))
                    elapsed = float(packet.get("elapsed_seconds", 0))
                    count = float(segment["end"] - segment["start"])
                    remaining += (
                        max(0, (count - frames) * elapsed / frames)
                        if frames > 0 and elapsed > 0
                        else float(segment.get("predicted_seconds", 180))
                    )
        return remaining

    def _prune_compare_cache(self) -> None:
        sessions = sorted(
            (
                o
                for o in self.operations.values()
                if o["kind"] == "compare" and o["state"] in {"done", "cancelled", "failed"}
            ),
            key=lambda o: o.get("created_at", ""),
            reverse=True,
        )
        used = 0
        for index, session in enumerate(sessions):
            folder = self.home / "previews" / session["id"]
            size = sum(p.stat().st_size for p in folder.glob("*.mp4"))
            if index >= 5 or used + size > 2_000_000_000:
                for path in folder.glob("*.mp4"):
                    path.unlink(missing_ok=True)
                session.pop("result", None)
                session.update(
                    state="expired", phase="Preview removed to make room. Compare again."
                )
                self._save_operation(session)
            else:
                used += size

    def _run_operation(self, op: dict[str, Any]) -> None:
        folder = self.home / "previews" / op["id"]
        folder.mkdir(parents=True, exist_ok=True)
        value = op["request"]
        if op["kind"] == "download" and not value.get("_network_only", True):
            # The network worker's last snapshot belongs to a completed phase.
            write_json(
                folder / "progress.json",
                dict(
                    phase="Testing on the GPU",
                    percent=value.get("_network_percent", 0),
                    remaining_seconds=value.get("_phase_seconds", {}).get("gpu", 15),
                ),
            )
        request_path = folder / "request.json"
        write_json(request_path, {"kind": op["kind"], "request": value, "folder": str(folder)})
        command = [sys.executable, "-m", "videoenhancer.service.operation", str(request_path)]
        if op["kind"] == "trial" and self._test_stuck_trial:
            command.append("--test-stuck-trial")
        from videoenhancer.estimate import predict_segment

        predicted = 0.0
        if op["kind"] in {"trial", "compare"}:
            media = (
                self.store.load(value["job_id"])["media"]
                if value.get("job_id")
                else probe(Path(value["file"]), read_timeline=False).to_dict()
            )
            frames = max(1, round(value.get("seconds", 5) * float(Fraction(media["cfr_fps"]))))
            predicted = predict_segment(
                media, value["settings"], frames, load_machine_profile(self.home)
            )
            if op["kind"] == "compare":
                predicted *= len(value["models"])
        deadline = time.monotonic() + (
            self._test_trial_timeout
            if self._test_stuck_trial and self._test_trial_timeout is not None
            else max(600, 4 * predicted)
        )

        history_started = time.monotonic()
        if op["kind"] == "calibrate":
            predicted = float(self.health()["speed_profile"].get("calibration_minutes", 10)) * 60
        op["expected_seconds"] = max(1, predicted or 60)
        calibration_stages = [
            "Decode and encode",
            "Tensor stages",
            "End-to-end pipeline",
            "Installed models",
            "Reference pipelines",
            "Finalization",
        ]
        previous_stages = (
            (load_machine_profile(self.home) or {}).get("calibration_stages_seconds", {})
            if op["kind"] == "calibrate"
            else {}
        )
        stage_expected = {
            name: float(previous_stages.get(name, op["expected_seconds"] * weight))
            for name, weight in zip(
                calibration_stages, (0.15, 0.15, 0.10, 0.25, 0.25, 0.10), strict=True
            )
        }
        current_stage = ""
        stage_started = history_started
        history_sampled = -2.0
        if op["kind"] == "trial":
            op["percent_history"] = []

        def keep_progress() -> None:
            nonlocal history_sampled
            elapsed = time.monotonic() - history_started
            if op["kind"] == "trial" and elapsed - history_sampled >= 2:
                op["percent_history"].append(
                    {
                        "time": datetime.now(UTC).isoformat(),
                        "elapsed_seconds": elapsed,
                        "percent": op.get("percent", 0),
                    }
                )
                history_sampled = elapsed
                self._save_operation(op)

        def abort() -> bool:
            if op["kind"] in {"trial", "compare"} and time.monotonic() >= deadline:
                op["cancel_requested"] = True
                op["timed_out"] = True
                op["phase"] = "The preview took too long. Try again."
                op["error"] = op["phase"]
            return self.stop.is_set() or bool(op.get("cancel_requested"))

        with (folder / "operation.log").open("wb") as errors:
            process = proc.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=errors,
                env={**os.environ, "VE_HOME": str(self.home)},
            )
            self.processes[op["id"]] = process
            keep_progress()
            while True:
                try:
                    process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    progress_path = folder / "progress.json"
                    if progress_path.is_file():
                        try:
                            op.update(json.loads(progress_path.read_text(encoding="utf-8")))
                        except (PermissionError, FileNotFoundError):
                            # Atomic publication can briefly hide/lock this advisory file.
                            # Retry on the next poll and still honor cancellation below.
                            pass
                    elapsed = time.monotonic() - history_started
                    fraction = float(op.get("percent", 0)) / 100
                    if not fraction and op["kind"] != "download":
                        op["percent"] = min(95, elapsed / op["expected_seconds"] * 100)
                    if op["kind"] != "download":
                        op["remaining_seconds"] = max(
                            0,
                            (elapsed / fraction * (1 - fraction))
                            if fraction > 0.01 and op["kind"] != "calibrate"
                            else op["expected_seconds"] - elapsed,
                        )
                    if op["kind"] == "calibrate":
                        stage = str(op.get("phase", "")).split(":", 1)[0]
                        if stage != current_stage:
                            current_stage, stage_started = stage, time.monotonic()
                        if stage in calibration_stages:
                            stage_index = calibration_stages.index(stage)
                            op["remaining_seconds"] = max(
                                0, stage_expected[stage] - (time.monotonic() - stage_started)
                            ) + sum(
                                stage_expected[name]
                                for name in calibration_stages[stage_index + 1 :]
                            )
                    keep_progress()
                    if abort():
                        _kill_process_tree(process.pid)
        if op.get("timed_out"):
            raise TimeoutError(op["error"])
        if process.returncode:
            raise RuntimeError((folder / "operation.log").read_text(errors="replace")[-4000:])
        result = json.loads((folder / "result.json").read_text())
        if op["kind"] == "trial":
            from videoenhancer.config import executable
            from videoenhancer.media.mux import _run

            for name in ("original", "enhanced"):
                _run(
                    [
                        executable("ffmpeg"),
                        "-v",
                        "error",
                        "-nostdin",
                        "-i",
                        str(folder / f"{name}.mp4"),
                        "-an",
                        "-vf",
                        f"fps={result['output_fps']}",
                        "-c:v",
                        "libx264",
                        "-crf",
                        "16",
                        "-pix_fmt",
                        "yuv420p",
                        "-threads",
                        "2",
                        str(folder / f"{name}-preview.mp4"),
                    ],
                    abort,
                )
            result["preview"] = {
                name: f"/v1/operations/{op['id']}/files/{name}" for name in ("original", "enhanced")
            }
            if op.get("job_id"):
                from videoenhancer.estimate.model import update_correction

                job = self.store.load(op["job_id"])
                from videoenhancer.estimate import predict_segment

                baseline = predict_segment(
                    job["media"],
                    job["settings"],
                    result["input_frames"],
                    job.get("machine_profile"),
                    float(job.get("correction_factor", 1)),
                )
                actual = result["pipeline"]["seconds"]
                update_correction(job, baseline, actual)
                self.store.save(job)
        elif op["kind"] == "calibrate":
            self._registry_checked = 0
            for job in self.store.list_jobs():
                if job["state"] in {"queued", "paused"}:
                    job["machine_profile"] = load_machine_profile(
                        self.home, backend=job["settings"]["backend"], models=job.get("models")
                    )
                    self.store.save(job)
        op["result"] = result
        if op["kind"] == "download" and not value.get("_network_only", True):
            op["percent"] = 100
        if op["kind"] == "trial":
            op["percent"] = 100
            op["percent_history"].append(
                {
                    "time": datetime.now(UTC).isoformat(),
                    "elapsed_seconds": time.monotonic() - history_started,
                    "percent": 100,
                    "terminal": True,
                }
            )

    def dispatch(self, method: str, parts: list[str], value: dict[str, Any]) -> Any:
        cancelling_move = parts == ["storage", "prepare"] and value.get("cancel") is True
        if self.storage_moving and method != "GET" and not cancelling_move:
            raise ValueError("App data is moving. Wait for it to finish.")
        if method == "GET" or "/".join(parts) in {
            "estimate",
            "history/delete-files",
            "trial/thumbnails",
            "compare/range",
            "queue",
        }:
            return self._dispatch(method, parts, value)
        with self._mutation_lock:
            started = time.monotonic()
            previous_paused = self.paused
            try:
                try:
                    return self._dispatch(method, parts, value)
                finally:
                    from videoenhancer.service.events import changed

                    changed(self.home)
                    elapsed = time.monotonic() - started
                    if elapsed > 0.5:
                        get_logger(self.home).warning(
                            "Mutation lock held for %.3f seconds", elapsed
                        )
            except BaseException:
                if parts == ["storage", "prepare"]:
                    self.storage_moving = False
                    self.paused = previous_paused
                raise

    def _dispatch(self, method: str, parts: list[str], value: dict[str, Any]) -> Any:
        route = "/".join(parts)
        if (
            self.storage_moving
            and method != "GET"
            and not (route == "storage/prepare" and value.get("cancel") is True)
        ):
            raise ValueError("App data is moving. Wait for it to finish.")
        if route == "storage" and method == "GET":
            from videoenhancer.service.storage import storage_status

            return storage_status(self.home, self.store)
        if route == "storage/prepare" and method == "POST":
            if value.get("cancel") is True:
                self.storage_moving = False
                self.paused = getattr(self, "_storage_previous_paused", self.paused)
                return {"ready": False}
            from videoenhancer.service.storage import check_startup_records

            check_startup_records(self.home)
            busy = any(j["state"] in {"running", "preparing"} for j in self.store.list_jobs())
            busy = busy or (
                not self.paused and any(j["state"] == "queued" for j in self.store.list_jobs())
            )
            busy = busy or any(
                o["state"] in {"running", "waiting"} for o in self.operations.values()
            )
            busy = busy or any(t.is_alive() for t in self._history_threads)
            if busy:
                raise ValueError("Pause processing first.")
            self._storage_previous_paused = self.paused
            self.paused = True
            self.storage_moving = True
            return {"ready": True}
        if route == "storage/cleanup" and method == "POST":
            from videoenhancer.service.storage import cleanup_job

            ids = value.get("ids")
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
                raise ValueError("Choose failed or cancelled jobs to clean up.")
            return {"removed_bytes": sum(cleanup_job(self.store, i) for i in dict.fromkeys(ids))}
        if route == "errors/dismiss" and method == "POST":
            self.last_error = None
            return {"dismissed": True}
        if method == "GET":
            if route == "health":
                return self.health()
            if route == "queue":
                if value.get("refresh_files") == "true":
                    self.refresh_terminal_files()
                return self.queue()
            if route == "plan":
                jobs = [j for j in self.store.list_jobs() if j["state"] != "preparing"]
                jobs = self._forecast_jobs(jobs)
                scenario = value.get("scenario", "expected")
                if scenario not in {"best", "expected", "worst"}:
                    raise ValueError("Estimate scenario must be best, expected or worst.")
                if scenario != "expected":
                    jobs = _scenario_jobs(jobs, scenario)
                return _jobs_plan(jobs, self.home, 120)
            if len(parts) == 3 and parts[0] == "queue" and parts[2] == "json":
                record = self.store.load_existing(parts[1])
                if record is None:
                    raise FileNotFoundError("This History record was removed.")
                return record
            if len(parts) == 3 and parts[0] == "queue" and parts[2] == "log":
                self.store.load(parts[1])
                path = self.store.job_dir(parts[1]) / "job.jsonl"
                if not path.exists():
                    return {"text": "No log entries yet."}
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 64000))
                    return {"text": stream.read().decode("utf-8", errors="replace")}
            if route == "schedule":
                return Schedule.from_file(self.home / "schedule.json").to_dict()
            if route == "settings":
                if (
                    not (self.home / "settings.json").exists()
                    and self._health_thread.ident is not None
                ):
                    self._health_thread.join(timeout=10)
                return read_settings(self.home)
            if route == "models":
                registry = ModelRegistry(self.home)
                from videoenhancer.models.registry import C1, RIFE

                prefs = read_settings(self.home)
                defaults = {
                    prefs.get("restore_model") or C1,
                    prefs.get("interp_model") or RIFE,
                    prefs.get("size_model"),
                }
                used = {
                    model
                    for job in self.store.queue_jobs()
                    if job["state"] not in {"done", "failed", "cancelled"}
                    for model in selected_models(job["settings"]).values()
                }
                return [
                    {
                        **m,
                        "uninstall_reason": "Choose another default before uninstalling this model."
                        if m["id"] in defaults
                        else "An unfinished video uses this model."
                        if m["id"] in used
                        else "",
                        "size_bytes": (registry.folder(m["id"]) / m["weights"]["filename"])
                        .stat()
                        .st_size
                        if m["weights_verified"]
                        else m["weights"].get("bytes", 0),
                    }
                    for m in registry.list_models()
                ]
            if len(parts) == 2 and parts[0] == "operations":
                return self.operations[parts[1]]
            if len(parts) == 3 and parts[0] == "queue" and parts[2] == "details":
                job = self.store.load(parts[1])
                logs = []
                for path in sorted((self.store.job_dir(parts[1]) / "logs").glob("seg_*.log")):
                    logs.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
                return {
                    "text": json.dumps(job, indent=2)
                    + "\nSegment log (last 40 lines):\n"
                    + "\n".join(logs[-40:])
                }
        if route == "trial/thumbnails" and method == "POST":
            import base64

            from videoenhancer.config import executable

            source = Path(value["file"]).resolve(strict=True)
            media = probe(source)
            thumbnails = []
            for index in range(8):
                result = proc.run(
                    [
                        executable("ffmpeg"),
                        "-v",
                        "error",
                        "-nostdin",
                        "-ss",
                        str(max(0, media.duration - 0.1) * index / 7),
                        "-i",
                        str(source),
                        "-frames:v",
                        "1",
                        "-vf",
                        "scale=160:-2",
                        "-f",
                        "image2pipe",
                        "-c:v",
                        "mjpeg",
                        "-threads",
                        "1",
                        "-",
                    ],
                    capture_output=True,
                    check=True,
                    timeout=15,
                )
                thumbnails.append(
                    "data:image/jpeg;base64," + base64.b64encode(result.stdout).decode()
                )
            return {"thumbnails": thumbnails, "duration": media.duration}
        if route == "compare/range" and method == "POST":
            from videoenhancer.service.compare import suggested_range

            source = Path(value["file"]).resolve(strict=True)
            analysis = None
            if value.get("job_id"):
                analysis = self.store.load(value["job_id"])
                if source != Path(analysis["input"]["path"]).resolve():
                    raise ValueError("The comparison file must match its job.")
            else:
                from videoenhancer.media.source_index import source_identity

                identity = source_identity(source)
                analysis = next(
                    (
                        job
                        for job in self.store.list_jobs()
                        if all(job.get("input", {}).get(k) == v for k, v in identity.items())
                    ),
                    None,
                )
            return suggested_range(source, analysis)
        if route == "estimate" and method == "POST":
            return self.estimate(value)
        if route == "estimate/space" and method == "POST":
            files = value.get("files", [])
            if not isinstance(files, list) or len(files) > 100:
                raise ValueError("Choose up to 100 videos.")
            result = {}
            for file in files:
                try:
                    settings = self.chosen(
                        {
                            **value.get("settings", {}),
                            **value.get("file_settings", {}).get(file, {}),
                        }
                    )
                    source = Path(file).resolve(strict=True)
                    media = probe(source, read_timeline=False, allow_hdr=True).to_dict()
                    output = self.output(source, {"output_folder": settings.get("output_folder")})
                    ancestor = output.parent
                    while not ancestor.exists():
                        ancestor = ancestor.parent
                    warnings = []
                    geometry = self.geometry_warning(media, settings)
                    if geometry:
                        warnings.append(geometry)
                    output_bytes = estimated_output_size(source.stat().st_size, media, settings)
                    for location, copies in working_space_locations(self.home, output.parent):
                        needed = int(output_bytes * copies * 1.1)
                        free = shutil.disk_usage(location).free
                        if free < needed:
                            warnings.append(
                                f"Insufficient space: Needs {needed / 1e9:.2f} GB, "
                                f"{free / 1e9:.2f} GB free on {location.anchor or location}."
                            )
                    result[file] = {"warnings": warnings, "output": str(output)}
                except (OSError, ValueError):
                    continue  # The time estimate reports per-file failures.
            return {"files": result}
        if route == "queue" and method == "POST":
            return self.add(value)
        if route == "history/delete-files" and method == "POST":
            ids = value.get("ids")
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
                raise ValueError("Choose History records.")
            if any(
                not isinstance(value.get(key, False), bool) for key in ("output", "original")
            ) or not any(value.get(k) for k in ("output", "original")):
                raise ValueError("Choose output and/or original video files.")
            results = []
            for job_id in dict.fromkeys(ids):
                job = self.store.load(job_id)
                for key in ("output", "original"):
                    if value.get(key):
                        path = Path(job["output"] if key == "output" else job["input"]["path"])
                        result = self.deletion.delete(path, job, self.store.list_jobs())
                        job.setdefault("video_deletions", {})[key] = result
                        results.append(dict(id=job_id, file=key, result=result))
                        self.refresh_terminal_files([str(path)])
                self.store.patch_existing(
                    job_id, {"video_deletions": job.get("video_deletions", {})}
                )
            return {"results": results}
        if (
            len(parts) == 2
            and parts[0] == "history"
            and parts[1] in {"remove", "undo", "clear", "pause-undo"}
            and method == "POST"
        ):
            if parts[1] in {"remove", "clear"} and (value.get("output") or value.get("original")):
                return self.history_operation(parts[1], value)
            return self.history_action(parts[1], value)
        if len(parts) == 2 and parts[0] == "queue" and method == "DELETE":
            return self.remove(parts[1])
        if len(parts) == 3 and parts[0] == "queue" and method == "POST":
            job_id, action = parts[1:]
            if action == "mode":
                return self.store.change_mode(job_id, value.get("preset", ""))
            if action == "model":
                return self.store.change_mode(
                    job_id, self.store.load(job_id)["settings"]["preset"], value
                )
            if action == "move":
                self.store.move(job_id, int(value["position"]))
                return {"moved": job_id}
            if action == "retry":
                if self.store.load(job_id)["state"] != "failed":
                    raise ValueError("Retry is available for failed videos only.")
                return self.store.set_state(job_id, "queued")
            if action in {"pause", "resume", "cancel"}:
                if action == "cancel":
                    return self.cancel_job(job_id)
                if self.store.load(job_id)["state"] in {"done", "failed", "cancelled"}:
                    raise ValueError("Pause and Resume are available for unfinished videos only.")
                return self.store.set_state(
                    job_id,
                    {"pause": "paused", "resume": "queued", "cancel": "cancelled"}[action],
                )
        if route == "processing" and method == "POST":
            if type(value.get("paused")) is not bool:
                raise ValueError("Paused must be on or off.")
            self.paused = value["paused"]
            return {"paused": self.paused, "paused_all": self.paused}
        if route == "settings" and method == "PUT":
            return save_settings(self.home, value)
        if route == "schedule" and method == "PUT":
            return _save_schedule(self.home, value)
        if route == "schedule/preview" and method == "POST":
            schedule = Schedule.from_dict(value)
            now = datetime.now(schedule.zone)
            window = schedule.next_interval(now)
            jobs = self.store.list_jobs()
            for job in jobs:
                if (
                    job["state"] == "running"
                    and job["id"] in self.live_progress
                    and job.get("progress", {}).get("phase") != "finalizing"
                ):
                    job["progress"] = self.live_progress[job["id"]]
            result = {
                "plan": build_plan(jobs, schedule, now, 120),
                "next_window": window.to_dict() if window else None,
            }
            if value.get("include_range") is True:
                result.update(
                    best=build_plan(_scenario_jobs(jobs, "best"), schedule, now, 120),
                    worst=build_plan(_scenario_jobs(jobs, "worst"), schedule, now, 120),
                )
            return result
        if route == "schedule/override" and method == "POST":
            schedule = _schedule_payload(self.home)
            schedule["override_until"] = value.get("until")
            return _save_schedule(self.home, schedule)
        if route in {"trial", "compare", "calibrate"} and method == "POST":
            return self.operation(route, value)
        if len(parts) == 3 and parts[0] == "queue" and parts[2] == "preview" and method == "POST":
            return self.result_preview(parts[1])
        if len(parts) == 3 and parts[0] == "operations" and parts[2] == "cancel":
            return self.cancel_operation(parts[1])
        if route == "models" and method == "POST":
            return ModelRegistry(self.home).add(Path(value["folder"]))
        if len(parts) >= 2 and parts[0] == "models":
            registry = ModelRegistry(self.home)
            model = registry.public_manifest(parts[1])
            if method == "DELETE":
                from videoenhancer.models.registry import C1, RIFE

                prefs = read_settings(self.home)
                defaults = {
                    prefs.get("restore_model") or C1,
                    prefs.get("interp_model") or RIFE,
                    prefs.get("size_model"),
                }
                if parts[1] in defaults:
                    raise ValueError(
                        "The default for Standard. Choose another default before removing it."
                    )
                users = [
                    j
                    for j in self.store.list_jobs()
                    if j["state"] not in {"done", "failed", "cancelled"}
                    and parts[1] in selected_models(j["settings"]).values()
                ]
                used = sum(
                    parts[1] in selected_models(j["settings"]).values()
                    for j in self.store.list_jobs()
                    if j["state"] not in {"done", "failed", "cancelled"}
                )
                if used:
                    file = Path(users[0]["input"]["path"]).name
                    active = next((j for j in users if j["state"] == "running"), None)
                    if active:
                        file = Path(active["input"]["path"]).name
                    raise ValueError(
                        f"{used} videos in the queue use it, including {file}"
                        + (", which is being processed now" if active else "")
                    )
                if any(
                    (
                        parts[1]
                        in selected_models(o.get("request", {}).get("settings", {})).values()
                        or parts[1] in o.get("request", {}).get("models", [])
                    )
                    for o in self.operations.values()
                    if o["state"] in {"waiting", "running"}
                ):
                    raise ValueError("Used by a preview that is still running")
                registry.remove(parts[1])
                return {"removed": parts[1]}
            if len(parts) == 3 and parts[2] in {"download", "verify"}:
                if parts[2] == "download":
                    from videoenhancer.models.registry import BUILTINS

                    if parts[1] not in BUILTINS:
                        raise ValueError("Downloads are for built-in models only.")
                    if not value.get("agree") or value.get("licence") != model["licence"]:
                        raise ValueError("Explicit licence consent is required before downloading.")
                    write_json(
                        self.home / "consent" / f"{parts[1]}.json",
                        {
                            "licence": model["licence"],
                            "url": model["weights"].get("url"),
                            "accepted_at": datetime.now().astimezone().isoformat(),
                        },
                    )
                return self.operation(parts[2], {"model_id": parts[1]})

        raise KeyError("Unknown endpoint.")
