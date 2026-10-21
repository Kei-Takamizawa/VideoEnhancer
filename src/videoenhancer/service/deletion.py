"""Journalled, hard-link-guarded recycling of recorded video paths."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import stat
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

# Windows-only entry points are absent from non-Windows ctypes type stubs.
_windows_ctypes: Any = ctypes


def fingerprint(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        first = stream.read(1024 * 1024)
        stream.seek(max(0, size - 1024 * 1024))
        last = stream.read(1024 * 1024)
    return dict(
        size=size,
        first_sha256=hashlib.sha256(first).hexdigest(),
        last_sha256=hashlib.sha256(last).hexdigest(),
    )


class WindowsFiles:
    kernel: Any

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Video recycling requires Windows.")
        self.kernel = _windows_ctypes.WinDLL("kernel32", use_last_error=True)

    def preflight(self, path: Path) -> int:
        kernel = self.kernel
        for parent in (path, *path.parents):
            attrs = kernel.GetFileAttributesW(str(parent))
            if attrs == -1 or attrs & 0x400:
                raise OSError("the path is a reparse point or cannot be inspected")
        root = ctypes.create_unicode_buffer(32768)
        if not kernel.GetVolumePathNameW(str(path), root, len(root)):
            raise _windows_ctypes.WinError(_windows_ctypes.get_last_error())
        if kernel.GetDriveTypeW(root.value) != 3:
            raise OSError("the file is not on a local fixed drive")
        filesystem = ctypes.create_unicode_buffer(256)
        if not kernel.GetVolumeInformationW(
            root.value, None, 0, None, None, None, filesystem, len(filesystem)
        ):
            raise _windows_ctypes.WinError(_windows_ctypes.get_last_error())
        if filesystem.value.upper() not in {"NTFS", "REFS"}:
            raise OSError("the volume does not support the required hard-link guard")
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x200080, None)
        if handle == ctypes.c_void_p(-1).value:
            raise OSError("the file is in use or cannot be opened exclusively")
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)
        return int(kernel.GetFileAttributesW(str(path)))

    def attributes(self, path: Path, value: int) -> None:
        if not self.kernel.SetFileAttributesW(str(path), value):
            raise _windows_ctypes.WinError(_windows_ctypes.get_last_error())

    def restore(self, guard: Path, path: Path) -> None:
        # No MOVEFILE_REPLACE_EXISTING: a concurrent new path is never overwritten.
        if not self.kernel.MoveFileExW(str(guard), str(path), 8):
            raise _windows_ctypes.WinError(_windows_ctypes.get_last_error())

    def unlink_guard(self, path: Path) -> None:
        kernel = self.kernel
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        handle = kernel.CreateFileW(str(path), 0x10000, 7, None, 3, 0x200080, None)
        if handle == ctypes.c_void_p(-1).value:
            raise OSError("the guard could not be opened for removal")
        kernel.SetFileInformationByHandle.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        try:
            flags = ctypes.c_uint32(0x1 | 0x2 | 0x10)
            if not kernel.SetFileInformationByHandle(
                handle, 21, ctypes.byref(flags), ctypes.sizeof(flags)
            ):
                raise OSError("the guard could not be removed; its bytes were retained")
        finally:
            kernel.CloseHandle(handle)

    def bin_refusal(self, path: Path) -> str:
        if os.name != "nt":
            return ""
        import winreg

        kernel = self.kernel
        root, volume = ctypes.create_unicode_buffer(32768), ctypes.create_unicode_buffer(32768)
        if not kernel.GetVolumePathNameW(
            str(path), root, len(root)
        ) or not kernel.GetVolumeNameForVolumeMountPointW(root.value, volume, len(volume)):
            return ""
        volume_id = volume.value[volume.value.find("{") : volume.value.find("}") + 1]
        base = r"Software\Microsoft\Windows\CurrentVersion"

        def read(hive: Any, key: str, name: str) -> int | None:
            try:
                with winreg.OpenKey(hive, key) as opened:
                    return int(winreg.QueryValueEx(opened, name)[0])
            except OSError:
                return None

        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            if read(hive, base + r"\Policies\Explorer", "NoRecycleFiles") == 1:
                return "the Recycle Bin is turned off for this drive"
        key = base + r"\Explorer\BitBucket\Volume" + "\\" + volume_id
        if read(winreg.HKEY_CURRENT_USER, key, "NukeOnDelete") == 1:
            return "the Recycle Bin is turned off for this drive"
        capacity = read(winreg.HKEY_CURRENT_USER, key, "MaxCapacity")
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            percentage = read(hive, base + r"\Policies\Explorer", "RecycleBinSize")
            if percentage is not None:
                total = ctypes.c_ulonglong()
                kernel.GetDiskFreeSpaceExW(root.value, None, ctypes.byref(total), None)
                capacity = int(total.value * percentage / 100 / (1024 * 1024))
        return (
            "the file is too big for the Recycle Bin"
            if capacity is not None and path.stat().st_size > capacity * 1024 * 1024
            else ""
        )

    def recycle(self, path: Path, post: Callable[[bool, str | None], None]) -> str:
        """IFileOperation with a real PostDeleteItem progress sink, no confirmation suppression."""
        import uuid as uu

        ptr, hr, uint = ctypes.c_void_p, ctypes.c_long, ctypes.c_uint32
        callback = _windows_ctypes.WINFUNCTYPE

        class Guid(ctypes.Structure):
            _fields_ = [("bytes", ctypes.c_ubyte * 16)]

        def guid(value: str) -> Guid:
            return Guid((ctypes.c_ubyte * 16).from_buffer_copy(uu.UUID(value).bytes_le))

        ole = _windows_ctypes.OleDLL("ole32")
        shell = _windows_ctypes.WinDLL("shell32")
        ole.CoInitializeEx(None, 2)
        operation, item = ptr(), ptr()
        refs = [1]
        outcome = [False, "the shell refused the operation"]
        signatures = [
            [ptr, ptr],
            [],
            [],
            [],
            [hr],
            [uint, ptr, ptr],
            [uint, ptr, ptr, hr, ptr],
            [uint, ptr, ptr, ptr],
            [uint, ptr, ptr, ptr, hr, ptr],
            [uint, ptr, ptr, ptr],
            [uint, ptr, ptr, ptr, hr, ptr],
            [uint, ptr],
            [uint, ptr, hr, ptr],
            [uint, ptr, ptr],
            [uint, ptr, ptr, ptr, uint, hr, ptr],
            [uint, uint],
            [],
            [],
            [],
        ]

        class Sink(ctypes.Structure):
            _fields_ = [("vtable", ctypes.POINTER(ptr))]

        sink = Sink()
        callbacks = []
        sink_iid = uu.UUID("04b0f1a7-9490-44bc-96e1-4296a31252e2").bytes_le
        unknown_iid = uu.UUID("00000000-0000-0000-c000-000000000046").bytes_le

        def query(_this: Any, iid: Any, out: Any) -> int:
            if ctypes.string_at(iid, 16) not in (sink_iid, unknown_iid):
                ctypes.cast(out, ctypes.POINTER(ptr))[0] = None
                return -2147467262
            ctypes.cast(out, ctypes.POINTER(ptr))[0] = ctypes.addressof(sink)
            refs[0] += 1
            return 0

        def deleted(_this: Any, flags: Any, old: Any, result: int, created: Any) -> int:
            outcome[0] = result >= 0 and bool(created)
            outcome[1] = (
                "" if result >= 0 else "Windows could not move this file to the Recycle Bin"
            )
            try:
                bin_path = None
                if outcome[0]:
                    name = ptr()
                    try:
                        invoke(created, 5, [uint, ptr], 0x80058000, ctypes.byref(name))
                        bin_path = ctypes.wstring_at(name)
                    finally:
                        if name:
                            ole.CoTaskMemFree.argtypes = [ptr]
                            ole.CoTaskMemFree(name)
                post(bool(outcome[0]), bin_path)
                return 0
            except Exception:
                return -2147467259

        for index, args in enumerate(signatures):
            fn: Any = (
                query
                if index == 0
                else deleted
                if index == 12
                else (lambda _this: refs.__setitem__(0, refs[0] + 1) or refs[0])
                if index == 1
                else (lambda _this: refs.__setitem__(0, refs[0] - 1) or refs[0])
                if index == 2
                else (lambda *_args: 0)
            )
            callbacks.append(callback(uint if index in (1, 2) else hr, ptr, *args)(fn))
        table = (ptr * len(callbacks))(*(ctypes.cast(c, ptr).value for c in callbacks))
        sink.vtable = ctypes.cast(table, ctypes.POINTER(ptr))

        def invoke(obj: Any, index: int, types: list[Any], *args: Any) -> int:
            vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ptr))).contents
            result = callback(hr, ptr, *types)(vtable[index])(obj, *args)
            if result < 0:
                raise OSError("Windows could not complete the Recycle Bin operation")
            return int(result)

        try:
            clsid = guid("3ad05575-8857-4850-9277-11b85bdb8e09")
            iid = guid("947aab5f-0a5c-4c13-b4d6-4bf7836fc9f8")
            ole.CoCreateInstance(
                ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(operation)
            )
            shell.SHCreateItemFromParsingName.argtypes = [ctypes.c_wchar_p, ptr, ptr, ptr]
            iid_item = guid("43826d1e-e718-42ee-bc55-a1e261c37bfe")
            result = shell.SHCreateItemFromParsingName(
                str(path), None, ctypes.byref(iid_item), ctypes.byref(item)
            )
            if result < 0 or not operation or not item:
                raise OSError("Could not create the shell operation.")
            # Confirmation suppression is allowed only with the verified hard-link guard.
            invoke(operation, 5, [uint], 0x10 | 0x4 | 0x400 | 0x100000 | 0x80000)
            invoke(operation, 18, [ptr, ptr], item, ctypes.byref(sink))
            invoke(operation, 21, [])
            return str(outcome[1])
        finally:
            if item:
                invoke(item, 2, [])
            if operation:
                invoke(operation, 2, [])
            ole.CoUninitialize()


@contextmanager
def deletion_lock(home: Path) -> Iterator[None]:
    home.mkdir(parents=True, exist_ok=True)
    with (home / "deletion.lock").open("a+b") as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BlockingIOError("another video deletion is in progress") from None
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def same_file(first: Path, second: Path) -> bool:
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def owner_alive(entry: dict[str, Any]) -> bool:
    try:
        return (
            abs(
                psutil.Process(int(entry["owner_pid"])).create_time()
                - float(entry["owner_started"])
            )
            < 0.001
        )
    except psutil.AccessDenied:
        return True
    except (psutil.NoSuchProcess, KeyError, ValueError):
        return False


class VideoDeletion:
    def __init__(self, home: Path, files: Any = None):
        self.home, self.files = home, files
        self.journal = home / "deletions.jsonl"
        self.lock = threading.RLock()
        self.notices: list[dict[str, Any]] = []

    def _append(self, entry: dict[str, Any], phase: str, **extra: Any) -> None:
        entry.update(
            phase=phase,
            time=datetime.now(UTC).isoformat(),
            owner_pid=os.getpid(),
            owner_started=psutil.Process().create_time(),
            **extra,
        )
        self.home.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _retained(self, entry: dict[str, Any], reason: str) -> str:
        result = f"Kept: {reason}. Original bytes retained at {entry['guard']}"
        self._append(entry, "retained", result=result)
        self.notices = [n for n in self.notices if n.get("id") != entry["id"]]
        self.notices.append(
            dict(
                id=entry["id"],
                job_id=entry.get("job_id"),
                path=entry["path"],
                guard=entry["guard"],
                result=result,
            )
        )
        return result

    def _unlink_guard(self, guard: Path) -> None:
        files = self.files or WindowsFiles()
        if hasattr(files, "unlink_guard"):
            files.unlink_guard(guard)
        else:
            guard.unlink()

    def _finish(
        self, entry: dict[str, Any], reason: str = "the Recycle Bin did not take the file"
    ) -> str:
        path, guard = Path(entry["path"]), Path(entry["guard"])
        files = self.files or WindowsFiles()
        expected = {key: entry[key] for key in ("size", "first_sha256", "last_sha256")}
        if guard.exists() and fingerprint(guard) != expected:
            return self._retained(entry, "guard verification failed")
        bin_path = Path(entry["bin_path"]) if entry.get("bin_path") else None
        if not guard.exists():
            if entry["phase"] == "confirmed" and bin_path and bin_path.exists():
                info = bin_path.stat()
                if (info.st_dev, info.st_ino) == (
                    entry.get("guard_dev"),
                    entry.get("guard_ino"),
                ) and fingerprint(bin_path) == expected:
                    self._append(entry, "resolved", result="Moved to the Recycle Bin")
                    return "Moved to the Recycle Bin"
            if path.exists() and fingerprint(path) == expected:
                result = f"Kept: {reason}"
                self._append(entry, "resolved", result=result)
                return result
            return self._retained(entry, "the original and guard could not be verified")
        if not path.exists() and bin_path and same_file(bin_path, guard):
            self._append(entry, "confirmed")
            self._unlink_guard(guard)
            result = "Moved to the Recycle Bin"
        elif not path.exists():
            if bin_path:
                reason = "the Recycle Bin item was not this file"
            files.restore(guard, path)
            if fingerprint(path) != expected:
                return self._retained(entry, "restored file verification failed")
            result = f"Kept: {reason}"
        elif same_file(path, guard):
            self._unlink_guard(guard)
            result = f"Kept: {reason}"
        else:
            return self._retained(entry, "the original path changed")
        self._append(entry, "resolved", result=result)
        self.notices = [n for n in self.notices if n.get("id") != entry["id"]]
        return result

    def _recover_locked(self) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        if self.journal.exists():
            for line in self.journal.read_text(encoding="utf-8").splitlines():
                try:
                    value = json.loads(line)
                    latest[value["id"]] = value
                except (ValueError, KeyError):
                    continue
        results = []
        for entry in latest.values():
            if entry["phase"] == "resolved":
                continue
            path, guard = Path(entry["path"]), Path(entry["guard"])
            if owner_alive(entry):
                result = f"Kept: deletion owner is alive. Original bytes retained at {guard}"
            elif guard.parent != path.parent or not guard.name.startswith(
                f".{path.name}.ve-guard-"
            ):
                result = f"Kept: invalid guard journal. Inspect {guard}"
            else:
                try:
                    result = self._finish(entry, "an interrupted deletion was recovered")
                except Exception as error:
                    result = self._retained(entry, str(error) or "recovery could not complete")
            results.append(
                dict(
                    id=entry["id"],
                    job_id=entry.get("job_id"),
                    path=str(path),
                    guard=str(guard),
                    result=result,
                )
            )
        self.notices = [
            r for r in results if r["result"].startswith("Kept:") and Path(r["guard"]).exists()
        ]
        return results

    def recover(self) -> list[dict[str, Any]]:
        with self.lock:
            try:
                with deletion_lock(self.home):
                    return self._recover_locked()
            except BlockingIOError:
                return []

    def completed_outcomes(self) -> list[dict[str, Any]]:
        """Replay durable shell outcomes into manifests without restoring files."""
        latest: dict[str, dict[str, Any]] = {}
        if self.journal.exists():
            for line in self.journal.read_text(encoding="utf-8").splitlines():
                try:
                    entry = json.loads(line)
                    latest[entry["id"]] = entry
                except (ValueError, KeyError):
                    continue
        return [entry for entry in latest.values() if entry.get("phase") == "resolved"]

    def delete(self, path: Path, job: dict[str, Any], jobs: list[dict[str, Any]]) -> str:
        with self.lock:
            try:
                with deletion_lock(self.home):
                    self._recover_locked()
                    return self._delete_locked(path, job, jobs)
            except BlockingIOError:
                return "Kept: another video deletion is in progress"

    def _delete_locked(self, path: Path, job: dict[str, Any], jobs: list[dict[str, Any]]) -> str:
        from videoenhancer.jobs.store import input_identity

        entry = None
        try:
            allowed = {
                os.path.normcase(os.path.abspath(job["input"]["path"])),
                os.path.normcase(os.path.abspath(job["output"])),
            }
            if os.path.normcase(os.path.abspath(path)) not in allowed:
                raise OSError("the path is not recorded by this job")
            if not path.exists() and not path.is_symlink():
                return "File not found"
            if not stat.S_ISREG(path.lstat().st_mode) or path.is_symlink():
                raise OSError("the path is not a regular file")
            is_original = os.path.normcase(os.path.abspath(path)) == os.path.normcase(
                os.path.abspath(job["input"]["path"])
            )
            expected = job["input"] if is_original else job.get("output_identity")
            actual = input_identity(path)
            if expected:
                match = all(
                    actual.get(k) == expected.get(k) for k in ("size", "mtime_ns", "edge_hash")
                )
            else:
                from fractions import Fraction

                from videoenhancer.media.probe import probe
                from videoenhancer.media.timing import output_rate

                started = datetime.fromisoformat(job.get("started_at", "")).timestamp()
                finished = datetime.fromisoformat(job.get("finished_at", "")).timestamp()
                rate = output_rate(job["settings"], job["media"])
                source_frames = len(job.get("cfr_map", [])) or int(job["media"]["frame_count"])
                planned = float(source_frames / Fraction(job["media"]["cfr_fps"]))
                match = (
                    started <= actual["mtime_ns"] / 1e9 <= finished + 60
                    and abs(probe(path, read_timeline=False).duration - planned)
                    <= float(1 / rate) + 1e-6
                )
            if not match:
                return "Kept: the file changed after this job used it"
            for other in jobs:
                if other["state"] not in {"done", "failed", "cancelled"} and any(
                    same_file(Path(p), path) for p in (other["input"]["path"], other["output"])
                ):
                    raise OSError("an unfinished job uses this file")
            files = self.files or WindowsFiles()
            attrs = files.preflight(path)
            refusal = files.bin_refusal(path) if hasattr(files, "bin_refusal") else ""
            if refusal:
                return f"Kept: {refusal}"
            guard = path.with_name(f".{path.name}.ve-guard-{uuid.uuid4().hex}")
            entry = dict(
                id=uuid.uuid4().hex,
                job_id=job["id"],
                path=str(path.absolute()),
                guard=str(guard.absolute()),
                attributes=attrs,
                owner_pid=os.getpid(),
                owner_started=psutil.Process().create_time(),
                **fingerprint(path),
            )
            self._append(entry, "planned")
            os.link(path, guard)
            info = guard.stat()
            self._append(entry, "guarded", guard_dev=info.st_dev, guard_ino=info.st_ino)
            # Recheck immediately before the shell; the bin identity closes the remaining race.
            if not same_file(path, guard) or input_identity(path) != actual:
                raise OSError("the original changed during preflight")
            reason = files.recycle(
                path,
                lambda recycled, bin_path=None: self._append(
                    entry, "shell", recycled=recycled, bin_path=bin_path
                ),
            )
            return self._finish(
                entry, reason or "the Recycle Bin did not confirm the original file"
            )
        except Exception as error:
            if entry:
                try:
                    return self._finish(entry, str(error) or "the shell could not complete")
                except Exception as recovery_error:
                    return self._retained(
                        entry, str(recovery_error) or "recovery could not complete"
                    )
            return f"Kept: {str(error) or 'the file could not be safely inspected'}"


_deletions: dict[str, VideoDeletion] = {}
_registry_lock = threading.Lock()


def get_deletion(home: Path) -> VideoDeletion:
    key = os.path.normcase(str(home.resolve()))
    with _registry_lock:
        return _deletions.setdefault(key, VideoDeletion(home))


def verify_output(job: dict[str, Any]) -> None:
    from fractions import Fraction

    from videoenhancer import proc
    from videoenhancer.config import executable
    from videoenhancer.media.mux import _audio_duration_matches
    from videoenhancer.media.probe import probe
    from videoenhancer.media.timing import output_rate

    output = Path(job["output"])
    result = probe(output, count_packets=True)
    proc.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-xerror",
            "-nostdin",
            "-i",
            str(output),
            "-map",
            "0:v:0",
            "-threads",
            "2",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
    )
    rate = output_rate(job["settings"], job["media"])
    source_rate = Fraction(job["media"]["cfr_fps"])
    source_frames = len(job.get("cfr_map", [])) or int(job["media"]["frame_count"])
    expected = source_frames * rate / source_rate
    if result.frame_count != expected:
        raise ValueError("output frame count does not match")
    if abs(result.duration - float(expected / rate)) > float(1 / rate) + 1e-6:
        raise ValueError("output duration does not match within one frame")
    original_audio = job["media"].get("audio_streams", [])
    if len(original_audio) != len(result.audio_streams):
        raise ValueError("output audio stream count does not match the source")
    for original, actual in zip(original_audio, result.audio_streams, strict=True):
        if abs(original["start_offset"] - actual["start_offset"]) > 0.020:
            raise ValueError("output audio timing does not match the source")
        if not _audio_duration_matches(original, actual):
            raise ValueError("output audio duration does not match the source")


def finish_original_deletions(store: Any) -> None:
    """Decode off the queue thread, then merge only deletion fields into current history."""
    deletion = get_deletion(store.home)
    deletion.recover()
    for job in store.list_jobs():
        if (
            job["state"] != "done"
            or not job["settings"].get("delete_original_after")
            or (job.get("original_delete_result") and not job.get("original_delete_pending"))
        ):
            continue
        source = Path(job["input"]["path"])
        shared = any(
            other["id"] != job["id"]
            and other["state"] not in {"done", "failed", "cancelled"}
            and same_file(Path(other["input"]["path"]), source)
            for other in store.list_jobs()
        )
        result = "Original kept: another unfinished video uses it"
        if not shared:
            try:
                verify_output(job)
                latest = store.load_existing(job["id"])
                if latest is None:
                    continue
                if latest["state"] != "done" or not latest["settings"].get("delete_original_after"):
                    continue
                result = deletion.delete(source, latest, store.list_jobs())
                result = (
                    result
                    if result == "Moved to the Recycle Bin"
                    else "Original kept: " + result.removeprefix("Kept: ")
                )
            except FileNotFoundError:
                if not (store.job_dir(job["id"]) / "manifest.json").exists():
                    continue
                result = "Original kept: a required video file is missing"
            except Exception as error:
                result = f"Original kept: {str(error) or 'output verification did not complete'}"
        store.patch_existing(
            job["id"], dict(original_delete_pending=shared, original_delete_result=result)
        )


_tasks: dict[str, threading.Thread] = {}
_tasks_lock = threading.Lock()
_tasks_generation: dict[str, int] = {}


def schedule_original_deletions(store: Any) -> None:
    key = os.path.normcase(str(store.home.resolve()))
    with _tasks_lock:
        if key in _tasks and _tasks[key].is_alive():
            return
        from videoenhancer.service.events import generation

        current = generation(store.home)
        if _tasks_generation.get(key) == current:
            return
        _tasks_generation[key] = current
        if not any(
            job["state"] == "done"
            and job["settings"].get("delete_original_after")
            and (not job.get("original_delete_result") or job.get("original_delete_pending"))
            for job in store.queue_jobs()
        ):
            return
        thread = threading.Thread(
            target=finish_original_deletions, args=(store,), name="video-deletion", daemon=True
        )
        _tasks[key] = thread
        thread.start()


def wait_original_deletions(home: Path, timeout: float | None = None) -> None:
    with _tasks_lock:
        thread = _tasks.get(os.path.normcase(str(home.resolve())))
    if thread:
        thread.join(timeout)
