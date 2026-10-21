import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from videoenhancer.jobs.store import JobStore

RUNTIME = {"serve.json", "serve.lock", "controller.lock", "worker.lock", "deletion.lock"}
PART = re.compile(r"seg_\d{5}(?:\.tmp)?\.mp4\Z")


def regular_files(root: Path, *, tolerate_transient: bool = False) -> list[Path]:
    result = []

    def failed(error: OSError) -> None:
        if not tolerate_transient:
            raise error

    for folder, dirs, files in os.walk(root, followlinks=False, onerror=failed):
        for name in [*dirs, *files]:
            p = Path(folder) / name
            try:
                if p.is_symlink() or p.is_junction():
                    raise ValueError(f"App data contains a linked path: {p}.")
            except (FileNotFoundError, PermissionError):
                if not tolerate_transient:
                    raise
        result.extend(Path(folder) / name for name in files)
    return sorted(result)


def working_files(directory: Path) -> list[Path]:
    if directory.is_symlink() or directory.is_junction():
        raise ValueError("A job folder must not be a linked path.")
    return [
        p
        for p in directory.iterdir()
        if p.is_file()
        and not p.is_symlink()
        and (PART.fullmatch(p.name) or p.name == "assembled.tmp.mp4")
    ]


def protected_video_paths(store: JobStore) -> set[Path]:
    return {
        Path(value).resolve()
        for job in store.list_jobs()
        for value in (job["input"]["path"], job["output"])
    }


def storage_status(home: Path, store: JobStore) -> dict[str, Any]:
    def size(path: Path) -> int:
        try:
            return path.stat().st_size
        except (FileNotFoundError, PermissionError):
            return 0

    files = regular_files(home, tolerate_transient=True)
    total = sum(size(p) for p in files)
    models = sum(size(p) for p in files if p.is_relative_to(home / "models"))
    protected = protected_video_paths(store)
    unfinished = 0
    cleanup = []
    for job in store.list_jobs():
        if job["state"] == "done":
            continue
        try:
            parts = working_files(store.job_dir(job["id"]))
        except (FileNotFoundError, PermissionError):
            parts = []
        job_size = sum(size(p) for p in parts if p.resolve() not in protected)
        unfinished += job_size
        if job["state"] in {"failed", "cancelled"} and job_size:
            cleanup.append(
                {
                    "id": job["id"],
                    "name": Path(job["input"]["path"]).name,
                    "state": job["state"],
                    "date": job.get("finished_at"),
                    "bytes": job_size,
                }
            )
    return {
        "folder": str(home),
        "total_bytes": total,
        "models_bytes": models,
        "working_bytes": unfinished,
        "history_bytes": max(0, total - models - unfinished),
        "free_bytes": shutil.disk_usage(home).free,
        "cleanup": cleanup,
        "core_records_load": core_records_load(home, store),
    }


def check_startup_records(home: Path) -> None:
    """Read startup records without repairing files or changing recovery policy."""
    from videoenhancer.models.registry import validate_manifest
    from videoenhancer.schedule.windows import Schedule
    from videoenhancer.service.settings import read_settings

    paths = [home / "settings.json", home / "schedule.json"]
    paths.extend(sorted((home / "jobs").glob("*/manifest.json")))
    paths.extend(sorted((home / "models").glob("*/model.json")))
    paths.extend(sorted((home / "previews").glob("*/state.json")))
    paths.extend(sorted((home / "previews").glob("*/request.json")))
    for path in paths:
        if not path.exists():
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError("A startup record must be an object.")
            if path == home / "settings.json":
                read_settings(home)
            elif path == home / "schedule.json":
                Schedule.from_file(path)
            elif path.name == "manifest.json":
                job = JobStore._load_unlocked(path, include_analysis=False)
                if not {"id", "state", "settings", "input", "output", "segments"} <= job.keys():
                    raise ValueError("A job is missing startup fields.")
                if job.get("analysis_file"):
                    sidecar = path.parent / "analysis.json"
                    if sidecar.exists():
                        path = sidecar
                        if not isinstance(json.loads(sidecar.read_text(encoding="utf-8")), dict):
                            raise ValueError("Analysis must be an object.")
            elif path.name == "model.json":
                if validate_manifest(record)["id"] != path.parent.name:
                    raise ValueError("Model manifest id does not match its folder.")
            elif path.name == "state.json":
                if not {"id", "state"} <= record.keys():
                    raise ValueError("A preview state is missing startup fields.")
            elif path.name == "request.json":
                if not {"kind", "request"} <= record.keys():
                    raise ValueError("A preview request is missing startup fields.")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            relative = path.relative_to(home).as_posix()
            raise ValueError(
                "Move stopped. A file the app needs at start is damaged: "
                f"{relative}. Your data stays in the current folder."
            ) from error


def core_records_load(home: Path, store: JobStore) -> bool:
    """Check live startup records without repairing missing registry files."""
    from videoenhancer.models.registry import BUILTINS, ModelRegistry
    from videoenhancer.schedule.windows import Schedule
    from videoenhancer.service.settings import read_settings

    try:
        if not (home / "settings.json").is_file() or not (home / "jobs").is_dir():
            return False
        if any(not (home / "models" / name / "model.json").is_file() for name in BUILTINS):
            return False
        read_settings(home)
        Schedule.from_file(home / "schedule.json")
        store.list_jobs()
        for path in store.jobs_dir.glob("*/manifest.json"):
            store._load_unlocked(path)
        registry = ModelRegistry(home)
        for path in registry.root.glob("*/model.json"):
            registry.manifest(path.parent.name)
        for folder in (home / "previews").glob("*"):
            state = folder / "state.json"
            request = folder / "request.json"
            if state.is_file():
                record = json.loads(state.read_text(encoding="utf-8"))
                if not isinstance(record, dict) or not {"state", "id"} <= record.keys():
                    return False
            elif request.is_file():
                record = json.loads(request.read_text(encoding="utf-8"))
                if not isinstance(record, dict) or not {"kind", "request"} <= record.keys():
                    return False
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


def cleanup_job(store: JobStore, job_id: str, *, _protected: set[Path] | None = None) -> int:
    protected = protected_video_paths(store) if _protected is None else _protected
    directory = store.job_dir(job_id)
    if (
        store.jobs_dir.is_symlink()
        or store.jobs_dir.is_junction()
        or not directory.resolve().is_relative_to(store.home.resolve())
    ):
        raise ValueError("A job folder must stay inside app data.")
    with store._lock(directory):
        job = store._load_unlocked(directory / "manifest.json")
        if job["state"] not in {"failed", "cancelled"}:
            raise ValueError("Only failed or cancelled jobs can be cleaned up.")
        protected.update(Path(v).resolve() for v in (job["input"]["path"], job["output"]))
        files = [p for p in working_files(directory) if p.resolve() not in protected]
        if not files:
            return 0
        # Save a durable restart marker before removing any checkpointed data.
        job["working_files_cleaned"] = True
        job.pop("finalization", None)
        for segment in job["segments"]:
            segment["state"] = "pending"
            segment.pop("stats", None)
        store._write_unlocked(job)
        removed = 0
        for p in files:
            # Links are refused even if swapped after enumeration.
            if p.is_symlink() or p.is_junction():
                raise ValueError("A working file became a linked path.")
            removed += p.stat().st_size
            p.unlink()
        return removed


def cleanup_expired(store: JobStore, now: float | None = None) -> None:
    from videoenhancer.service.settings import read_settings

    if not read_settings(store.home)["cleanup_working_files"]:
        return
    cutoff = (time.time() if now is None else now) - 7 * 86400
    protected = protected_video_paths(store)
    for job in store.list_jobs():
        if job["state"] not in {"failed", "cancelled"} or not job.get("finished_at"):
            continue
        if datetime.fromisoformat(job["finished_at"]).timestamp() <= cutoff:
            try:
                cleanup_job(store, job["id"], _protected=protected)
            except (OSError, ValueError):
                from videoenhancer.logging import get_logger

                get_logger(store.home).warning(
                    "Working-file cleanup failed for %s", job["id"], exc_info=True
                )


def digest(p: Path) -> str:
    with p.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy_home(source: Path, target: Path, progress: Any = None) -> dict[str, Any]:
    """Copy a stopped home; callers alone publish the location after verification."""
    source = source.resolve(strict=True)
    target = target.absolute()
    if target.is_symlink() or target.is_junction():
        raise ValueError("Choose a new or empty folder without linked paths.")
    # Resolve parents to reject junction aliases and nested copies.
    resolved = target.resolve()
    if resolved == source or resolved.is_relative_to(source) or source.is_relative_to(resolved):
        raise ValueError("Choose a separate new or empty folder.")
    for parent in [target, *target.parents]:
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("Choose a folder without linked paths.")
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError("The target must be a new or empty folder.")
    files = [
        p
        for p in regular_files(source)
        if not (p.parent == source and (p.name in RUNTIME or p.name.endswith(".lock")))
    ]
    total = sum(p.stat().st_size for p in files)
    probe = target.parent
    while not probe.exists():
        probe = probe.parent
    if shutil.disk_usage(probe).free < total:
        raise OSError("The target drive does not have enough free space.")
    target.mkdir(parents=True, exist_ok=True)
    began = time.time()
    copied = 0
    identities: dict[tuple[int, int], Path] = {}
    expected = {}
    for p in files:
        dest = target / p.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        before = p.stat()
        expected[p.relative_to(source).as_posix()] = (before.st_size, digest(p))
        key = (before.st_dev, before.st_ino)
        if before.st_nlink > 1 and key in identities:
            os.link(identities[key], dest)
        else:
            shutil.copy2(p, dest)
            identities[key] = dest
        if (
            dest.stat().st_size != before.st_size
            or digest(dest) != expected[p.relative_to(source).as_posix()][1]
        ):
            raise OSError(f"Copy verification failed: {p.relative_to(source)}")
        after = p.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise OSError("App data changed during the copy. Retry while processing is paused.")
        copied += before.st_size
        if progress:
            progress(
                {"phase": "Copying and verifying", "copied_bytes": copied, "total_bytes": total}
            )

    # Historical input/output locations outside app data and external deletion guards stay put.
    def rebase(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: rebase(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rebase(v) for v in value]
        if isinstance(value, str):
            candidate = Path(value)
            try:
                if candidate.is_absolute() and candidate.is_relative_to(source):
                    return str(target / candidate.relative_to(source))
            except (ValueError, OSError):
                pass
        return value

    damaged: dict[str, int] = {}
    for p in regular_files(target):
        if p.suffix not in {".json", ".jsonl"}:
            continue
        raw = p.read_bytes()
        try:
            if p.suffix == ".json":
                data = rebase(json.loads(raw))
                if (
                    p.name == "manifest.json"
                    and isinstance(data, dict)
                    and data.get("history_hidden_until")
                ):
                    remaining = data.get(
                        "history_undo_remaining", max(0, data["history_hidden_until"] - began)
                    )
                    if remaining > 0:
                        data["storage_move_undo"] = True
                        data["history_undo_remaining"] = remaining
                        data["history_hidden_until"] = time.time() + 315360000
                encoded = json.dumps(data, indent=2)
            else:
                records: list[bytes] = []
                for line in raw.splitlines(keepends=True):
                    if not line.strip():
                        records.append(line)
                        continue
                    try:
                        entry = rebase(json.loads(line))
                    except (ValueError, TypeError, UnicodeError):
                        key = p.relative_to(target).as_posix()
                        damaged[key] = damaged.get(key, 0) + 1
                        records.append(line)
                        continue
                    if (
                        p.name == "deletions.jsonl"
                        and isinstance(entry, dict)
                        and entry.get("guard")
                    ):
                        guard = Path(entry["guard"])
                        if guard.is_relative_to(target) and guard.exists():
                            info = guard.stat()
                            entry.update(guard_dev=info.st_dev, guard_ino=info.st_ino)
                    ending = (
                        b"\r\n"
                        if line.endswith(b"\r\n")
                        else b"\n"
                        if line.endswith(b"\n")
                        else b""
                    )
                    records.append(json.dumps(entry).encode("utf-8") + ending)
                encoded = b"".join(records)
        except (ValueError, TypeError, UnicodeError):
            key = p.relative_to(target).as_posix()
            damaged[key] = damaged.get(key, 0) + 1
            continue
        p.write_bytes(encoded.encode("utf-8") if isinstance(encoded, str) else encoded)
    # Verify the source is unchanged, including the complete file set, before returning.
    current = [
        p
        for p in regular_files(source)
        if not (p.parent == source and (p.name in RUNTIME or p.name.endswith(".lock")))
    ]
    if {p.relative_to(source).as_posix() for p in current} != set(expected):
        raise OSError("App data changed during the copy.")
    for p in current:
        if (p.stat().st_size, digest(p)) != expected[p.relative_to(source).as_posix()]:
            raise OSError("App data changed during the copy.")
    protected = set()
    damaged_manifests = False
    for p in files:
        if p.name == "manifest.json" and p.is_relative_to(source / "jobs"):
            try:
                record = json.loads(p.read_bytes())
                protected.update(
                    Path(v).resolve() for v in (record["input"]["path"], record["output"])
                )
            except (ValueError, TypeError, UnicodeError, KeyError):
                damaged_manifests = True
    manifest = [
        {
            "path": name,
            "size": info[0],
            "sha256": info[1],
            "active_size": (target / name).stat().st_size,
            # Damaged jobs can hide input/output names with any extension.
            "protected_video": (source / name).resolve() in protected or damaged_manifests,
        }
        for name, info in expected.items()
    ]
    return {
        "files": len(files),
        "bytes": total,
        "source": str(source),
        "target": str(target),
        "manifest": manifest,
        "damaged": damaged,
    }


if __name__ == "__main__":

    def emit(value: Any) -> None:
        print(json.dumps(value), flush=True)

    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m videoenhancer.service.storage SOURCE TARGET")
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    check_startup_records(source)
    result = copy_home(source, target, emit)
    check_startup_records(target)
    emit({"phase": "Verified", "result": result})
