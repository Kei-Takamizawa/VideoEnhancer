"""Desktop operations on the same durable queue used by the CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from videoenhancer import __version__
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


class Engine:
    def __init__(self, home: Path):
        self.home = home.resolve()
        self.store = JobStore(home)
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.operations: dict[str, dict[str, Any]] = {}
        self.processes: dict[str, subprocess.Popen[Any]] = {}
        self.last_error: str | None = None
        self.paused = False
        self.environment: dict[str, Any] = {}
        self.worker = threading.Thread(target=self._worker, name="engine-controller", daemon=True)
        self._health_thread = threading.Thread(target=self._environment, daemon=True)

    def start(self) -> None:
        self._health_thread.start()
        self.worker.start()

    def _environment(self) -> None:
        from videoenhancer.logging import environment_info

        self.environment = environment_info()
        try:
            import torch

            if torch.cuda.is_available():
                self.environment["vram_bytes"] = torch.cuda.get_device_properties(0).total_memory
                choose_backend("cuda")
                from videoenhancer.config import executable

                result = subprocess.run(
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
            self.last_error = str(error)

    def _worker(self) -> None:
        while not self.stop.is_set():
            try:
                run_queue(
                    home=self.home,
                    clock=ServiceClock(self.stop),
                    stopped=self.stop.is_set,
                    between_segments=self._auxiliary,
                )
            except Exception as error:
                self.last_error = str(error)
            self.stop.wait(0.5)

    def close(self) -> None:
        self.stop.set()
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
            else "Waiting for operating hours"
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
        errors = [str(j.get("error", "")) for j in jobs] + [self.last_error or ""]
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
        plan = _jobs_plan(jobs, self.home, days=120)
        completion = {j["job_id"]: j for j in plan["jobs"]}
        rows = []
        for j in jobs:
            done = [s for s in j["segments"] if s["state"] == "done"]
            active = next((s for s in j["segments"] if s["state"] == "running"), None)
            stats = done[-1].get("stats", {}) if done else {}
            rows.append(
                {
                    "id": j["id"],
                    "state": j["state"],
                    "input": j["input"]["path"],
                    "output": j["output"],
                    "settings": j["settings"],
                    "media": j["media"],
                    "error": j.get("error"),
                    "estimate": estimate_job(j).to_dict(),
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
                    "fps": stats.get("fps"),
                    "segment": active["index"] + 1 if active else len(done),
                    "segments": len(j["segments"]),
                    **job_progress(j),
                    "log": str(self.store.job_dir(j["id"]) / "job.jsonl"),
                }
            )
        completions = [j["eta"] for j in rows if j["state"] not in {"cancelled", "failed"}]
        return {
            "jobs": rows,
            "completion": max(completions) if completions and all(completions) else None,
            "operations": list(self.operations.values()),
        }

    def chosen(self, value: dict[str, Any]) -> dict[str, Any]:
        prefs = read_settings(self.home)
        settings = {k: prefs[k] for k in ("preset", "codec", "short_side", "fps")}
        settings.update(prefs["advanced"])
        settings.update(value)
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
        settings = self.chosen(value.get("settings", {}))
        registry = ModelRegistry(self.home)
        for task, model_id in selected_models(settings).items():
            registry.weights(registry.manifest(model_id, task), download=False)
        source = Path(value["file"]).resolve(strict=True)
        geometry = self.geometry_warning(probe(source).to_dict(), settings)
        if geometry:
            raise ValueError(geometry)
        job = add_job(
            source,
            settings,
            output=self.output(source, value),
            home=self.home,
            target_segment_seconds=float(value.get("segment_seconds", 180)),
        )
        if self.paused:
            return self.store.set_state(job["id"], "paused")
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
        if kind == "trial":
            if value.get("seconds", 5) not in {3, 5, 10}:
                raise ValueError("Trial length must be 3, 5 or 10 seconds.")
            value = {**value, "settings": self.chosen(value.get("settings", {}))}
            if value.get("job_id"):
                job = self.store.load(value["job_id"])
                if Path(value["file"]).resolve() != Path(job["input"]["path"]).resolve():
                    raise ValueError("The trial file must match its job.")
                value["settings"] = job["settings"]
            if value["settings"]["preset"] not in {"standard", "fast"}:
                raise ValueError("Trial preset must be Standard or Fast.")
            geometry = self.geometry_warning(
                probe(Path(value["file"])).to_dict(), value["settings"]
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
        return op

    def cancel_operation(self, op_id: str) -> dict[str, Any]:
        op = self.operations[op_id]
        op["cancel_requested"] = True
        if op["state"] == "waiting":
            op["state"] = "cancelled"
        process = self.processes.get(op_id)
        if process and process.poll() is None:
            _kill_process_tree(process.pid)
        return op

    def _auxiliary(self) -> None:
        op = next((o for o in self.operations.values() if o["state"] == "waiting"), None)
        if not op or self.stop.is_set():
            return
        if op["kind"] == "trial":
            schedule = Schedule.from_file(self.home / "schedule.json")
            if schedule.current_interval(datetime.now(schedule.zone)) is None:
                op["phase"] = "Waiting for operating hours"
                return
        op.update(state="running", phase="Processing")
        try:
            self._run_operation(op)
            op.update(state="cancelled" if op.get("cancel_requested") else "done", phase="Complete")
        except Exception as error:
            op.update(
                state="cancelled" if op.get("cancel_requested") else "failed", error=str(error)
            )
        finally:
            self.processes.pop(op["id"], None)

    def _run_operation(self, op: dict[str, Any]) -> None:
        folder = self.home / "previews" / op["id"]
        folder.mkdir(parents=True)
        value = op["request"]
        request_path = folder / "request.json"
        write_json(request_path, {"kind": op["kind"], "request": value, "folder": str(folder)})
        command = [sys.executable, "-m", "videoenhancer.service.operation", str(request_path)]
        schedule = Schedule.from_file(self.home / "schedule.json")
        interval = schedule.current_interval(datetime.now(schedule.zone))
        deadline = (
            interval.end.astimezone(UTC) + timedelta(seconds=value.get("seconds", 5))
            if op["kind"] == "trial" and interval
            else None
        )

        def abort() -> bool:
            nonlocal deadline
            if op["kind"] == "trial":
                current = Schedule.from_file(self.home / "schedule.json").current_interval(
                    datetime.now().astimezone()
                )
                candidate = (
                    current.end.astimezone(UTC) if current else datetime.now(UTC)
                ) + timedelta(seconds=value.get("seconds", 5))
                if deadline is None or candidate < deadline:
                    deadline = candidate
                if datetime.now(UTC) >= deadline:
                    op["cancel_requested"] = True
                    op["phase"] = "Operating window ended; retry in the next window"
            return self.stop.is_set() or bool(op.get("cancel_requested"))

        with (folder / "operation.log").open("wb") as errors:
            process = subprocess.Popen(
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
                    if abort():
                        _kill_process_tree(process.pid)
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
        route = "/".join(parts)
        if method == "GET":
            if route == "health":
                return self.health()
            if route == "queue":
                return self.queue()
            if route == "plan":
                jobs = self.store.list_jobs()
                scenario = value.get("scenario", "expected")
                if scenario not in {"best", "expected", "worst"}:
                    raise ValueError("Estimate scenario must be best, expected or worst.")
                if scenario != "expected":
                    for job in jobs:
                        estimate = estimate_job(job)
                        ratio = (estimate.low if scenario == "best" else estimate.high) / max(
                            estimate.seconds, 0.000001
                        )
                        job["correction_factor"] = job.get("correction_factor", 1) * ratio
                        profile = job.get("machine_profile") or {}
                        job["machine_profile"] = {
                            **profile,
                            "finalization_correction": profile.get("finalization_correction", 1)
                            * ratio,
                        }
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
        with self.lock:
            if route == "trial/thumbnails" and method == "POST":
                import base64

                from videoenhancer.config import executable

                source = Path(value["file"]).resolve(strict=True)
                media = probe(source)
                thumbnails = []
                for index in range(8):
                    result = subprocess.run(
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
                if action == "move":
                    self.store.move(job_id, int(value["position"]))
                    return {"moved": job_id}
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
                return {
                    "plan": build_plan(self.store.list_jobs(), schedule, now, 120),
                    "next_window": window.to_dict() if window else None,
                }
            if route == "schedule/override" and method == "POST":
                schedule = _schedule_payload(self.home)
                schedule["override_until"] = value.get("until")
                return _save_schedule(self.home, schedule)
            if route in {"trial", "calibrate"} and method == "POST":
                return self.operation(route, value)
            if len(parts) == 3 and parts[0] == "operations" and parts[2] == "cancel":
                return self.cancel_operation(parts[1])
            if route == "models" and method == "POST":
                return ModelRegistry(self.home).add(Path(value["folder"]))
            if len(parts) >= 2 and parts[0] == "models":
                registry = ModelRegistry(self.home)
                model = registry.manifest(parts[1])
                if method == "DELETE":
                    registry.remove(parts[1])
                    return {"removed": parts[1]}
                if len(parts) == 3 and parts[2] in {"download", "verify"}:
                    if parts[2] == "download":
                        from videoenhancer.models.registry import BUILTINS

                        if parts[1] not in BUILTINS:
                            raise ValueError("Downloads are for built-in models only.")
                        if not value.get("agree") or value.get("licence") != model["licence"]:
                            raise ValueError(
                                "Explicit licence consent is required before downloading."
                            )
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
