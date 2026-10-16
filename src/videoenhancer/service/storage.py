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


def regular_files(root: Path) -> list[Path]:
    result = []

    def failed(error: OSError) -> None:
        raise error

    for folder, dirs, files in os.walk(root, followlinks=False, onerror=failed):
        for name in [*dirs, *files]:
            p = Path(folder) / name
            if p.is_symlink() or p.is_junction():
                raise ValueError(f"App data contains a linked path: {p}.")
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
    files = regular_files(home)
    total = sum(p.stat().st_size for p in files)
    models = sum(p.stat().st_size for p in files if p.is_relative_to(home / "models"))
    protected = protected_video_paths(store)
    unfinished = 0
    cleanup = []
    for job in store.list_jobs():
        if job["state"] == "done":
            continue
        size = sum(
            p.stat().st_size
            for p in working_files(store.job_dir(job["id"]))
            if p.resolve() not in protected
        )
        unfinished += size
        if job["state"] in {"failed", "cancelled"} and size:
            cleanup.append({"id": job["id"], "state": job["state"], "bytes": size})
    return {
        "folder": str(home),
        "total_bytes": total,
        "models_bytes": models,
        "working_bytes": unfinished,
        "history_bytes": max(0, total - models - unfinished),
        "free_bytes": shutil.disk_usage(home).free,
        "cleanup": cleanup,
    }


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

    for p in regular_files(target):
        if p.suffix not in {".json", ".jsonl"}:
            continue
        raw = p.read_text(encoding="utf-8")
        try:
            if p.suffix == ".json":
                data = rebase(json.loads(raw))
                if p.name == "manifest.json" and data.get("history_hidden_until"):
                    remaining = data.get(
                        "history_undo_remaining", max(0, data["history_hidden_until"] - began)
                    )
                    if remaining > 0:
                        data["storage_move_undo"] = True
                        data["history_undo_remaining"] = remaining
                        data["history_hidden_until"] = time.time() + 315360000
                encoded = json.dumps(data, indent=2)
            else:
                records = []
                for line in raw.splitlines():
                    if not line.strip():
                        continue
                    entry = rebase(json.loads(line))
                    if p.name == "deletions.jsonl" and entry.get("guard"):
                        guard = Path(entry["guard"])
                        if guard.is_relative_to(target) and guard.exists():
                            info = guard.stat()
                            entry.update(guard_dev=info.st_dev, guard_ino=info.st_ino)
                    records.append(json.dumps(entry))
                encoded = "\n".join(records) + "\n"
        except (ValueError, TypeError):
            # Malformed durable records must not be silently published as a successful move.
            raise ValueError(f"Invalid app data record: {p.relative_to(target)}") from None
        p.write_text(encoded, encoding="utf-8")
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
    return {"files": len(files), "bytes": total, "source": str(source), "target": str(target)}


if __name__ == "__main__":

    def emit(value: Any) -> None:
        print(json.dumps(value), flush=True)

    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m videoenhancer.service.storage SOURCE TARGET")
    emit({"phase": "Verified", "result": copy_home(Path(sys.argv[1]), Path(sys.argv[2]), emit)})
