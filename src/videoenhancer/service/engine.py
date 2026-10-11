"""Desktop operations on the same durable queue used by the CLI."""

from __future__ import annotations

import copy
import json
import os
import shutil
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
from videoenhancer.estimate.model import job_progress
from videoenhancer.jobs.store import (
    JobStore,
    add_job,
    estimated_output_size,
    input_identity,
    load_machine_profile,
)
from videoenhancer.logging import get_logger
from videoenhancer.media.decode import choose_backend
from videoenhancer.media.probe import probe
from videoenhancer.media.timing import output_size
from videoenhancer.models.registry import ModelRegistry, selected_models
from videoenhancer.schedule.controller import SystemClock, _kill_process_tree, run_queue
from videoenhancer.schedule.planner import build_plan
from videoenhancer.schedule.windows import Schedule
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
            "finalization_correction": profile.get("finalization_correction", 1) * ratio,
        }
    return result


class Engine:
    def __init__(
        self, home: Path, *, test_stuck_trial: bool = False, test_trial_timeout: float | None = None
    ):
        self.home = home.resolve()
        self._test_stuck_trial = test_stuck_trial
        self._test_trial_timeout = test_trial_timeout
        self.store = JobStore(home)
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.operations: dict[str, dict[str, Any]] = {}
        self.processes: dict[str, subprocess.Popen[Any]] = {}
        self.last_error: dict[str, Any] | None = None
        self.live_progress: dict[str, dict[str, Any]] = {}
        self._preparations: list[threading.Thread] = []
        self.preview_threads: dict[str, threading.Thread] = {}
        self.paused = False
        self.environment: dict[str, Any] = {}
        self.worker = threading.Thread(target=self._worker, name="engine-controller", daemon=True)
        self._health_thread = threading.Thread(target=self._environment, daemon=True)

    def start(self) -> None:
        self._recover()
        self._health_thread.start()
        self.worker.start()

    def _recover(self) -> None:
        for job in self.store.list_jobs():
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
        self.live_progress[job["id"]] = value

    def _environment(self) -> None:
        from videoenhancer.logging import environment_info

        self.environment = environment_info()
        try:
            import torch

            if torch.cuda.is_available():
                self.environment["vram_bytes"] = torch.cuda.get_device_properties(0).total_memory
                choose_backend("cuda")
                from videoenhancer.config import executable

                result = proc.run(
                    [
                        executable("ffmpeg"),
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "color=size=128x128:rate=1",
                        "-frames:v",
                        "1",
                        "-c:v",
                        "av1_nvenc",
                        "-f",
                        "null",
                        "-",
                    ],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                self.environment["av1_supported"] = result.returncode == 0
        except Exception as error:
            self._error(None, error)

    def _worker(self) -> None:
        while not self.stop.is_set():
            try:
                run_queue(
                    home=self.home,
                    clock=ServiceClock(self.stop),
                    stopped=self.stop.is_set,
                    between_segments=self._auxiliary,
                    on_error=self._error,
                    on_progress=self._progress,
                )
            except Exception as error:
                self._error(None, error)
                self.stop.wait(5)
            self.stop.wait(0.5)

    def close(self) -> None:
        self.stop.set()
        deadline = time.monotonic() + 15
        for thread in list(self.preview_threads.values()):
            thread.join(timeout=max(0, deadline - time.monotonic()))
            if thread.is_alive():
                raise RuntimeError("Preview has not stopped. Keep the app open and retry Quit.")
        for process in list(self.processes.values()):
            if process.poll() is None:
                _kill_process_tree(process.pid)
        if self.worker.ident is not None:
            self.worker.join(timeout=15)
        if self.worker.is_alive():
            raise RuntimeError("Engine has not stopped; keep the service open and retry Quit.")

    def health(self) -> dict[str, Any]:
        jobs = self.store.list_jobs()
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
        schedule = Schedule.from_file(self.home / "schedule.json")
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
        if any(op["state"] == "running" for op in self.operations.values()):
            state = "Running"
        sac = {"status": "unknown", "blocked": False, "message": None}
        if os.name == "nt":
            try:
                import winreg

                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy"
                ) as key:
                    value = winreg.QueryValueEx(key, "VerifiedAndReputablePolicyState")[0]
                sac["status"] = {0: "off", 1: "enforced", 2: "evaluation"}.get(value, "unknown")
            except OSError:
                pass
        errors = [str(j.get("error", "")) for j in jobs] + [
            self.last_error["message"] if self.last_error else ""
        ]
        problem = next((e for e in errors if "Smart App Control" in e), None)
        if problem:
            sac.update(blocked=True, message=problem)
        current = finalizing or running
        return {
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
            "av1_supported": self.environment.get("av1_supported", False),
        }

    def queue(self) -> dict[str, Any]:
        jobs = self.store.list_jobs()
        for job in jobs:
            if job["state"] == "running" and job["id"] in self.live_progress:
                job["progress"] = self.live_progress[job["id"]]
        plan = _jobs_plan([j for j in jobs if j["state"] != "preparing"], self.home, days=120)
        completion = {j["job_id"]: j for j in plan["jobs"]}
        rows = []
        for j in jobs:
            if j["state"] == "running" and j["id"] in self.live_progress:
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
                    "segments": len(j["segments"]),
                    **job_progress(j),
                    "log": str(self.store.job_dir(j["id"]) / "job.jsonl"),
                    "started_at": j.get("started_at"),
                    "finished_at": j.get("finished_at"),
                    "took_seconds": j.get("took_seconds"),
                    "output_bytes": Path(j["output"]).stat().st_size
                    if j["state"] == "done" and Path(j["output"]).is_file()
                    else None,
                    "preview_ready": bool(done),
                    "starts": next(
                        (step["start"] for step in plan["timeline"] if step["job_id"] == j["id"]),
                        None,
                    ),
                }
            )
        completions = [j["eta"] for j in rows if j["state"] not in {"cancelled", "failed"}]
        operations = copy.deepcopy(list(self.operations.values()))
        current = next((j for j in jobs if j["state"] == "running"), None)
        remaining = 0.0
        if current:
            active = next((s for s in current["segments"] if s["state"] == "running"), None)
            if active:
                remaining = max(
                    0.0,
                    float(active.get("predicted_seconds", 180))
                    - float(current.get("progress", {}).get("elapsed_seconds", 0)),
                )
        for op in operations:
            if op["state"] == "waiting":
                op["phase"] = (
                    f"Starts after the current step, about {int(remaining) // 60} min "
                    f"{int(remaining) % 60} s"
                    if current
                    else "Starting preview…"
                )
        return {
            "jobs": rows,
            "completion": max(completions) if completions and all(completions) else None,
            "operations": operations,
        }

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
        settings = {k: prefs[k] for k in ("preset", "codec", "short_side", "fps")}
        for key in ("restore_model", "interp_model"):
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
        return settings

    def output(self, source: Path, value: dict[str, Any]) -> Path:
        if value.get("output"):
            return Path(value["output"]).resolve()
        folder = value.get("output_folder") or read_settings(self.home)["output_folder"]
        return (
            Path(folder) if folder else source.parent / "enhanced"
        ) / f"{source.stem}_enhanced.mp4"

    def estimate(self, value: dict[str, Any]) -> dict[str, Any]:
        source = Path(value["file"]).resolve(strict=True)
        media = probe(source).to_dict()
        settings = self.chosen(value.get("settings", {}))
        output = self.output(source, value)
        size = source.stat().st_size
        needed = int(estimated_output_size(size, media, settings) * 2.2)
        ancestor = output.parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        free = shutil.disk_usage(ancestor).free
        warnings = []
        geometry = self.geometry_warning(media, settings)
        if geometry:
            warnings.append(geometry)
        if free < needed:
            warnings.append(f"Insufficient space: {free:,} bytes free; {needed:,} bytes required.")
        if str(media.get("color_transfer", "")) in {"smpte2084", "arib-std-b67"}:
            warnings.append("HDR is not supported. Choose an SDR video.")
        if self.health()["smart_app_control"]["blocked"]:
            warnings.append("Windows Smart App Control is blocking the video component.")
        comparisons = {}
        queue = self.store.list_jobs()
        for preset in ("standard", "fast"):
            from videoenhancer.estimate import predict_segment
            from videoenhancer.jobs.segments import plan_segments

            chosen = {**settings, "preset": preset}
            profile = load_machine_profile(self.home, backend=chosen["backend"])
            per_frame = predict_segment(media, chosen, max(1, media["frame_count"]), profile) / max(
                1, media["frame_count"]
            )
            virtual = {
                "id": "preview",
                "state": "queued",
                "media": media,
                "settings": chosen,
                "input": input_identity(source),
                "estimated_output_bytes": estimated_output_size(size, media, chosen),
                "segments": plan_segments(
                    media, [], predicted_seconds_per_frame=per_frame, target_seconds=180
                ),
                "machine_profile": profile,
            }
            estimate = estimate_job(virtual).to_dict()
            plan = _jobs_plan(queue + [virtual], self.home, 120)
            comparisons[preset] = {
                **estimate,
                "finish": next(
                    (j["completion"] for j in plan["jobs"] if j["job_id"] == "preview"), None
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
            control_generation=0,
        )
        with self.lock:
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
                if self.paused:
                    self.store.set_state(job_id, "paused")
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
        restore = selected_models(settings).get("restore")
        if (
            restore
            and ModelRegistry(self.home).manifest(restore, "restore")["architecture"]
            == "basicvsrpp"
        ):
            width, height = output_size(settings, media)
            if min(width, height) < 256:
                return (
                    f"Output too small: {width} x {height}. This restoration model requires "
                    "at least 256 pixels on both sides. Choose 1080 instead of Keep."
                )
        return None

    def remove(self, job_id: str) -> dict[str, Any]:
        import logging

        job = self.store.load(job_id)
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
        shutil.rmtree(directory)
        return {"removed": job_id, "output_preserved": True}

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
                manifests = [registry.manifest(model_id) for model_id in models]
                if len({m["task"] for m in manifests}) != 1:
                    raise ValueError("Choose models of the same category.")
                for model in manifests:
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
            "phase": f"Waiting for the current segment (about {waiting:.0f} seconds remaining)",
            "created_at": datetime.now().astimezone().isoformat(),
        }
        self.operations[op["id"]] = op
        self._save_operation(op)
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
        op = next((o for o in self.operations.values() if o["state"] == "waiting"), None)
        if not op or self.stop.is_set():
            return
        op.update(state="running", phase="Processing")
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
            self.processes.pop(op["id"], None)
            self._save_operation(op)
            if op["kind"] == "compare":
                if op["state"] != "done":
                    for path in (self.home / "previews" / op["id"]).glob("*.mp4"):
                        path.unlink(missing_ok=True)
                    op.pop("result", None)
                    self._save_operation(op)
                self._prune_compare_cache()

    def _prune_compare_cache(self) -> None:
        sessions = sorted(
            (
                o
                for o in self.operations.values()
                if o["kind"] == "compare" and o["state"] == "done"
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
            while True:
                try:
                    process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    progress_path = folder / "progress.json"
                    if progress_path.is_file():
                        op.update(json.loads(progress_path.read_text(encoding="utf-8")))
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
            for job in self.store.list_jobs():
                if job["state"] in {"queued", "paused"}:
                    job["machine_profile"] = load_machine_profile(
                        self.home, backend=job["settings"]["backend"], models=job.get("models")
                    )
                    self.store.save(job)
        op["result"] = result

    def dispatch(self, method: str, parts: list[str], value: dict[str, Any]) -> Any:
        if method == "GET" or "/".join(parts) in {"estimate", "trial/thumbnails", "queue"}:
            return self._dispatch(method, parts, value)
        with self.lock:
            started = time.monotonic()
            try:
                return self._dispatch(method, parts, value)
            finally:
                elapsed = time.monotonic() - started
                if elapsed > 0.5:
                    get_logger(self.home).warning("Mutation lock held for %.3f seconds", elapsed)

    def _dispatch(self, method: str, parts: list[str], value: dict[str, Any]) -> Any:
        route = "/".join(parts)
        if method == "GET":
            if route == "health":
                return self.health()
            if route == "queue":
                return self.queue()
            if route == "plan":
                jobs = [j for j in self.store.list_jobs() if j["state"] != "preparing"]
                for job in jobs:
                    if job["state"] == "running" and job["id"] in self.live_progress:
                        job["progress"] = self.live_progress[job["id"]]
                scenario = value.get("scenario", "expected")
                if scenario not in {"best", "expected", "worst"}:
                    raise ValueError("Estimate scenario must be best, expected or worst.")
                if scenario != "expected":
                    jobs = _scenario_jobs(jobs, scenario)
                return _jobs_plan(jobs, self.home, 120)
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
                return read_settings(self.home)
            if route == "models":
                registry = ModelRegistry(self.home)
                return [
                    {
                        **m,
                        "size_bytes": (registry.folder(m["id"]) / m["weights"]["filename"])
                        .stat()
                        .st_size
                        if m["weights_verified"]
                        else 0,
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
        if route == "estimate" and method == "POST":
            return self.estimate(value)
        if route == "queue" and method == "POST":
            return self.add(value)
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
                return self.store.set_state(
                    job_id,
                    {"pause": "paused", "resume": "queued", "cancel": "cancelled"}[action],
                )
        if route == "processing" and method == "POST":
            self.paused = bool(value["paused"])
            for job in self.store.list_jobs():
                if self.paused and job["state"] in {"queued", "running"}:
                    self.store.set_state(job["id"], "paused")
                elif not self.paused and job["state"] == "paused":
                    self.store.set_state(job["id"], "queued")
            return {"paused": self.paused}
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
                if job["state"] == "running" and job["id"] in self.live_progress:
                    job["progress"] = self.live_progress[job["id"]]
            return {
                "plan": build_plan(jobs, schedule, now, 120),
                "best": build_plan(_scenario_jobs(jobs, "best"), schedule, now, 120),
                "worst": build_plan(_scenario_jobs(jobs, "worst"), schedule, now, 120),
                "next_window": window.to_dict() if window else None,
            }
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
            model = registry.manifest(parts[1])
            if method == "DELETE":
                used = sum(
                    parts[1] in selected_models(j["settings"]).values()
                    for j in self.store.list_jobs()
                    if j["state"] not in {"done", "failed", "cancelled"}
                )
                if used:
                    raise ValueError(f"Used by {used} videos in the queue")
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
