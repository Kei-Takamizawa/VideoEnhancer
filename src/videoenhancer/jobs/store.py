"""Atomic, schema-versioned persistence for local conversion jobs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from .segments import plan_segments

SCHEMA_VERSION = 1
JOB_STATES = {"queued", "running", "paused", "cancelled", "failed", "done"}


@contextmanager
def _manifest_lock(directory: Path) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / "manifest.lock"
    with lock_path.open("a+b") as lock:
        for attempt in range(100):
            try:
                if lock_path.stat().st_size == 0:
                    lock.seek(0)
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if attempt == 99:
                    raise TimeoutError(
                        f"Job manifest is busy: {directory}. Retry shortly."
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _home(home: Path | str | None) -> Path:
    if home is not None:
        return Path(home)
    from videoenhancer.config import get_home

    return get_home()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def input_identity(path: Path) -> dict[str, Any]:
    """Fingerprint metadata plus the file edges without hashing long videos."""
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        digest.update(source.read(1024 * 1024))
        source.seek(max(0, stat.st_size - 1024 * 1024))
        digest.update(source.read(1024 * 1024))
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "edge_hash": digest.hexdigest(),
    }


def validate_input(manifest: dict[str, Any]) -> None:
    expected = manifest["input"]
    path = Path(expected["path"])
    if not path.is_file():
        raise FileNotFoundError(
            f"Input for job {manifest['id']} is missing: {path}. Restore the file and retry."
        )
    actual = input_identity(path)
    if any(actual[key] != expected[key] for key in ("size", "mtime_ns", "edge_hash")):
        raise ValueError(
            f"Input for job {manifest['id']} has changed: {path}. "
            "Add the changed video as a new job."
        )


def estimated_output_size(input_size: int, media: dict[str, Any], settings: dict[str, Any]) -> int:
    """Conservative size heuristic for the preflight disk check."""
    short = min(
        int(media.get("display_width", media.get("width", 1))),
        int(media.get("display_height", media.get("height", 1))),
    )
    target = settings.get("short_side", "keep")
    scale = max(1.0, (int(target) / short) if target != "keep" and short > 0 else 1.0)
    fps_factor = 2.0 if settings.get("fps") == "2x" else 1.0
    # 0.7 limits huge overestimates for highly compressed inputs; retain
    # headroom for upscale, interpolation and audio.
    return max(input_size, int(input_size * max(1.0, scale * scale * fps_factor * 0.7)))


def require_disk_space(
    path: Path,
    estimated_bytes: int,
    disk_free: Callable[[Path], int] | int | None = None,
) -> None:
    probe_path = path
    while not probe_path.exists() and probe_path != probe_path.parent:
        probe_path = probe_path.parent
    free = (
        disk_free(probe_path)
        if callable(disk_free)
        else (disk_free if disk_free is not None else shutil.disk_usage(probe_path).free)
    )
    required = int(estimated_bytes * 2.2)
    if free < required:
        raise OSError(
            f"Insufficient disk space at {probe_path}: {free / 1e9:.2f} GB free, "
            f"about {required / 1e9:.2f} GB required. Free space or choose another output location."
        )


def _require_unreserved_output(store: JobStore, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"Output already exists: {destination}. Choose another output path.")
    for job in store.list_jobs():
        if job["state"] != "done" and Path(job["output"]).expanduser().resolve() == destination:
            raise FileExistsError(
                f"Output is reserved by unfinished job {job['id']}: {destination}. "
                "Choose another output path or finish that job first."
            )


def load_machine_profile(
    home: Path | str | None = None,
    *,
    gpu_name: str | None = None,
    driver: str | None = None,
    backend: str = "cuda",
    models: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Load the newest calibration for this exact GPU and driver, if any."""
    import platform

    cpu_name = platform.processor() or platform.machine()
    if backend == "cuda" and (gpu_name is None or driver is None):
        from videoenhancer.logging import environment_info

        environment = environment_info()
        gpu_name = gpu_name or environment.get("gpu")
        driver = driver or environment.get("driver")
    if backend == "cuda" and (not gpu_name or not driver):
        return None
    directory = _home(home) / "profiles"
    if not directory.exists():
        return None
    candidates = sorted(
        directory.glob("*.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True
    )
    for path in candidates:
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
            if (
                profile.get("schema_version") == 1
                and profile.get("backend", "cuda") == backend
                and (
                    (
                        profile.get("gpu_name") == gpu_name
                        and str(profile.get("driver")) == str(driver)
                    )
                    if backend == "cuda"
                    else profile.get("cpu_name") == cpu_name
                )
                and isinstance(profile.get("components"), dict)
            ):
                if "models" in profile:
                    entries = profile["models"]
                    if not isinstance(entries, dict):
                        continue
                    if models is not None:
                        identities = {value["id"]: value for value in models.values()}
                        profile["models"] = {
                            model_id: entry
                            for model_id, entry in entries.items()
                            if isinstance(entry, dict)
                            and entry.get("identity") == identities.get(model_id)
                            and model_id in identities
                        }
                return profile
        except (OSError, ValueError, TypeError):
            continue
    return None


class JobStore:
    def __init__(self, home: Path | str | None = None) -> None:
        self.home = _home(home)
        self.jobs_dir = self.home / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        if not job_id or Path(job_id).name != job_id or job_id in {".", ".."}:
            raise ValueError("Invalid job ID")
        return self.jobs_dir / job_id

    def load(self, job_id: str) -> dict[str, Any]:
        directory = self.job_dir(job_id)
        with _manifest_lock(directory):
            return self._load_unlocked(directory / "manifest.json")

    @staticmethod
    def _load_unlocked(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as source:
            manifest = json.load(source)
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Unsupported manifest schema in {path}; upgrade VideoEnhancer")
        return manifest

    def save(self, manifest: dict[str, Any]) -> None:
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported manifest schema")
        manifest.setdefault("control_generation", 0)
        directory = self.job_dir(str(manifest["id"]))
        directory.mkdir(parents=True, exist_ok=True)
        with _manifest_lock(directory):
            target = directory / "manifest.json"
            if target.exists():
                current = self._load_unlocked(target)
                if "position" in current:
                    manifest["position"] = current["position"]
                if int(current.get("control_generation", 0)) > int(
                    manifest.get("control_generation", 0)
                ):
                    manifest["state"] = current["state"]
                    manifest["control_generation"] = current["control_generation"]
            self._write_unlocked(manifest)
            if not (directory / "control.json").exists():
                self._write_control_unlocked(manifest)

    def _write_unlocked(self, manifest: dict[str, Any]) -> None:
        directory = self.job_dir(str(manifest["id"]))
        manifest["updated_at"] = _now()
        target = directory / "manifest.json"
        temporary = directory / f"manifest.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(manifest, stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs = [
            self.load(directory.name)
            for directory in self.jobs_dir.iterdir()
            if (directory / "manifest.json").is_file()
        ]
        return sorted(jobs, key=lambda job: (job.get("position", 10**9), job["created_at"]))

    def move(self, job_id: str, position: int) -> None:
        jobs = self.list_jobs()
        selected = next((job for job in jobs if job["id"] == job_id), None)
        if selected is None:
            raise KeyError(f"Unknown job: {job_id}")
        if position < 1 or position > len(jobs):
            raise ValueError(f"Position must be between 1 and {len(jobs)}")
        jobs.remove(selected)
        jobs.insert(position - 1, selected)
        for index, job in enumerate(jobs, start=1):
            directory = self.job_dir(str(job["id"]))
            with _manifest_lock(directory):
                latest = self._load_unlocked(directory / "manifest.json")
                if latest.get("position") != index:
                    latest["position"] = index
                    self._write_unlocked(latest)

    def set_state(self, job_id: str, state: str) -> dict[str, Any]:
        if state not in JOB_STATES:
            raise ValueError(f"Invalid job state: {state}")
        directory = self.job_dir(job_id)
        with _manifest_lock(directory):
            job = self._load_unlocked(directory / "manifest.json")
            if state == "queued":
                from videoenhancer.models.registry import validate_job_models

                validate_job_models(job, self.home)
            job["state"] = state
            job["control_generation"] = int(job.get("control_generation", 0)) + 1
            if state == "queued":
                for segment in job["segments"]:
                    if segment["state"] == "failed":
                        segment["state"] = "pending"
            self._write_unlocked(job)
            self._write_control_unlocked(job)
        return job

    def _write_control_unlocked(self, job: dict[str, Any]) -> None:
        directory = self.job_dir(str(job["id"]))
        target = directory / "control.json"
        temporary = directory / f"control.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(
                    {"state": job["state"], "generation": job.get("control_generation", 0)},
                    stream,
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def read_control_state(self, job_id: str) -> str:
        path = self.job_dir(job_id) / "control.json"
        if path.exists():
            with path.open("r", encoding="utf-8") as source:
                return str(json.load(source)["state"])
        return str(self.load(job_id)["state"])


def add_job(
    path: Path | str,
    settings: dict[str, Any] | None = None,
    output: Path | str | None = None,
    home: Path | str | None = None,
    *,
    disk_free: Callable[[Path], int] | int | None = None,
    target_segment_seconds: float = 180.0,
) -> dict[str, Any]:
    """Analyze an input and enqueue a durable, frame-exact conversion plan."""
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"Input is not a file: {source}")
    destination = (
        Path(output).expanduser().resolve()
        if output
        else source.with_name(f"{source.stem}_enhanced.mp4")
    )
    if destination == source:
        raise ValueError("Output path would overwrite the input video. Choose another output path.")
    chosen: dict[str, Any] = {
        "preset": "standard",
        "short_side": 1080,
        "fps": "2x",
        "codec": "hevc",
        "backend": "cuda",
        "keep_segments": False,
        "batch_size": 2,
    }
    if settings:
        chosen.update(settings)
    if chosen["short_side"] not in {"keep", 1080, 1440, 2160}:
        raise ValueError("short_side must be keep, 1080, 1440 or 2160")
    if chosen["fps"] not in {"off", "2x"}:
        raise ValueError("fps must be off or 2x")
    if chosen["backend"] not in {"cpu", "cuda"}:
        raise ValueError("backend must be cpu or cuda")
    store = JobStore(home)
    with _manifest_lock(store.jobs_dir):
        _require_unreserved_output(store, destination)
    identity = input_identity(source)
    # Check before the potentially long analysis pass, then again with the
    # measured media geometry before storing the job.
    require_disk_space(destination.parent, identity["size"], disk_free)
    require_disk_space(store.home, identity["size"], disk_free)
    from videoenhancer.media.analyze import analyze

    analysis = analyze(source, backend=chosen["backend"])
    media = analysis["media"]
    output_bytes = estimated_output_size(identity["size"], media, chosen)
    require_disk_space(destination.parent, output_bytes, disk_free)
    require_disk_space(store.home, output_bytes, disk_free)
    from videoenhancer.models.registry import record_models

    models = record_models(chosen, store.home, media)
    from videoenhancer.estimate import predict_segment

    profile = load_machine_profile(store.home, backend=chosen["backend"], models=models)
    fps = float(Fraction(str(media["cfr_fps"])))
    typical_frames = max(1, round(fps * 10))
    cost_per_frame = max(
        0.000001, predict_segment(media, chosen, typical_frames, profile) / typical_frames
    )
    segments = plan_segments(
        media,
        analysis.get("scene_cuts", []),
        predicted_seconds_per_frame=cost_per_frame,
        target_seconds=target_segment_seconds,
    )
    for segment in segments:
        segment["predicted_seconds"] = predict_segment(
            media, chosen, segment["end"] - segment["start"], profile
        )
    now = _now()
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": uuid.uuid4().hex,
        "input": identity,
        "output": str(destination),
        "settings": chosen,
        "models": models,
        "media": media,
        "cfr_map": analysis.get("cfr_map", []),
        "source_pts": analysis.get("source_pts", []),
        "keyframes": analysis.get("keyframes", []),
        "scene_cuts": analysis.get("scene_cuts", []),
        "analysis_seconds": analysis.get("analysis_seconds"),
        "segments": segments,
        "state": "queued",
        "position": len(store.list_jobs()) + 1,
        "created_at": now,
        "updated_at": now,
        "correction_factor": 1.0,
        "control_generation": 0,
        "machine_profile": profile,
        "timing": {"observations": [], "wasted_seconds": 0.0},
        "estimated_output_bytes": output_bytes,
    }
    with _manifest_lock(store.jobs_dir):
        _require_unreserved_output(store, destination)
        manifest["position"] = len(store.list_jobs()) + 1
        store.save(manifest)
    return manifest
