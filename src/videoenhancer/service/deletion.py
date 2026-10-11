"""Journalled, hard-link-guarded recycling of recorded video paths."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import stat
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

    def recycle(self, path: Path, post: Callable[[bool], None]) -> str:
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
            outcome[1] = "" if result >= 0 else f"shell error 0x{result & 0xFFFFFFFF:08x}"
            try:
                post(bool(outcome[0]))
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
                raise OSError(f"Shell operation failed: 0x{result & 0xFFFFFFFF:08x}")
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
            # SILENT + NOERRORUI + EARLYFAILURE + RECYCLEONDELETE; never NOCONFIRMATION.
            invoke(operation, 5, [uint], 0x4 | 0x400 | 0x100000 | 0x80000)
            invoke(operation, 18, [ptr, ptr], item, ctypes.byref(sink))
            invoke(operation, 21, [])
            return str(outcome[1])
        finally:
            if item:
                invoke(item, 2, [])
            if operation:
                invoke(operation, 2, [])
            ole.CoUninitialize()


class VideoDeletion:
    def __init__(self, home: Path, files: Any = None):
        self.home, self.files = home, files
        self.journal = home / "deletions.jsonl"
        self.lock = threading.RLock()

    def _append(self, entry: dict[str, Any], phase: str, **extra: Any) -> None:
        entry.update(phase=phase, time=datetime.now(UTC).isoformat(), **extra)
        self.home.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _finish(
        self, entry: dict[str, Any], reason: str = "the Recycle Bin did not take the file"
    ) -> str:
        path, guard = Path(entry["path"]), Path(entry["guard"])
        files = self.files or WindowsFiles()
        expected = {key: entry[key] for key in ("size", "first_sha256", "last_sha256")}
        if guard.exists() and fingerprint(guard) != expected:
            raise OSError("guard verification failed; the guard was retained")
        if not path.exists():
            if not guard.exists():
                if entry.get("recycled") and entry["phase"] == "confirmed":
                    self._append(entry, "resolved", result="Moved to the Recycle Bin")
                    return "Moved to the Recycle Bin"
                raise OSError("the original and guard are both unavailable")
            if entry.get("recycled"):
                self._append(entry, "confirmed")
                files.attributes(guard, entry["attributes"])
                guard.unlink()
                result = "Moved to the Recycle Bin"
            else:
                files.restore(guard, path)
                files.attributes(path, entry["attributes"])
                if fingerprint(path) != expected:
                    raise OSError("restored file verification failed")
                result = "Kept: the Recycle Bin did not take the file"
        else:
            if guard.exists():
                if not os.path.samefile(path, guard):
                    raise OSError("the original path changed; the guard was retained")
                files.attributes(guard, entry["attributes"])
                guard.unlink()
            if fingerprint(path) != expected:
                raise OSError("the kept file verification failed")
            files.attributes(path, entry["attributes"])
            result = f"Kept: {reason}"
        self._append(entry, "resolved", result=result)
        return result

    def recover(self) -> list[dict[str, Any]]:
        with self.lock:
            if not self.journal.exists():
                return []
            latest = {}
            for line in self.journal.read_text(encoding="utf-8").splitlines():
                try:
                    value = json.loads(line)
                    latest[value["id"]] = value
                except (ValueError, KeyError):
                    continue  # A torn append cannot authorize deleting an orphan guard.
            results = []
            for entry in latest.values():
                if entry["phase"] == "resolved":
                    continue
                path, guard = Path(entry["path"]), Path(entry["guard"])
                if guard.parent != path.parent or not guard.name.startswith(
                    f".{path.name}.ve-guard-"
                ):
                    results.append(dict(path=str(path), result="Kept: invalid guard journal"))
                    continue
                try:
                    result = self._finish(entry, "an interrupted deletion was recovered")
                except OSError as error:
                    result = f"Kept: {error}"
                results.append(dict(path=str(path), result=result))
            return results

    def delete(self, path: Path, job: dict[str, Any], jobs: list[dict[str, Any]]) -> str:
        with self.lock:
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
                for other in jobs:
                    if other["state"] not in {"done", "failed", "cancelled"} and any(
                        os.path.normcase(os.path.abspath(p))
                        == os.path.normcase(os.path.abspath(path))
                        for p in (other["input"]["path"], other["output"])
                    ):
                        raise OSError("an unfinished job uses this file")
                files = self.files or WindowsFiles()
                attrs = files.preflight(path)
                guard = path.with_name(f".{path.name}.ve-guard-{uuid.uuid4().hex}")
                entry = dict(
                    id=uuid.uuid4().hex,
                    path=str(path.absolute()),
                    guard=str(guard.absolute()),
                    attributes=attrs,
                    **fingerprint(path),
                )
                self._append(entry, "planned")
                os.link(path, guard)
                files.attributes(guard, attrs | 2)
                if not os.path.samefile(path, guard) or fingerprint(guard) != {
                    k: entry[k] for k in ("size", "first_sha256", "last_sha256")
                }:
                    raise OSError("the original changed during preflight")
                self._append(entry, "guarded")
                reason = files.recycle(
                    path, lambda recycled: self._append(entry, "shell", recycled=recycled)
                )
                return self._finish(entry, reason or "the shell left the file in place")
            except OSError as error:
                if entry:
                    try:
                        return self._finish(entry, str(error))
                    except OSError as recovery_error:
                        return f"Kept: {recovery_error}"
                return f"Kept: {error}"


def verify_output(job: dict[str, Any]) -> None:
    from fractions import Fraction

    from videoenhancer import proc
    from videoenhancer.config import executable
    from videoenhancer.media.timing import output_rate

    output = Path(job["output"])
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
    result = json.loads(
        proc.run(
            [
                executable("ffprobe"),
                "-v",
                "error",
                "-count_frames",
                "-show_entries",
                "stream=codec_type,nb_read_frames,duration:format=duration",
                "-of",
                "json",
                str(output),
            ],
            check=True,
            capture_output=True,
        ).stdout
    )
    streams = result["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    rate = output_rate(job["settings"], job["media"])
    source_rate = Fraction(job["media"]["cfr_fps"])
    expected = int(job["media"]["frame_count"]) * rate / source_rate
    if int(video.get("nb_read_frames", 0)) != expected:
        raise ValueError("output frame count does not match")
    duration = float(video.get("duration", result["format"]["duration"]))
    if abs(duration - float(expected / rate)) > float(1 / rate) + 1e-6:
        raise ValueError("output duration does not match within one frame")
    if job["media"].get("audio_streams") and not any(s["codec_type"] == "audio" for s in streams):
        raise ValueError("output audio is missing")


def finish_original_deletions(store: Any) -> None:
    """Retry shared originals only after every dependent unfinished job has ended."""
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
            and os.path.normcase(os.path.abspath(other["input"]["path"]))
            == os.path.normcase(os.path.abspath(source))
            for other in store.list_jobs()
        )
        job["original_delete_pending"] = shared
        if shared:
            job["original_delete_result"] = "Original kept: another unfinished video uses it"
        else:
            try:
                verify_output(job)
                result = VideoDeletion(store.home).delete(source, job, store.list_jobs())
                job["original_delete_result"] = (
                    result
                    if result == "Moved to the Recycle Bin"
                    else "Original kept: " + result.removeprefix("Kept: ")
                )
            except Exception as error:
                job["original_delete_result"] = f"Original kept: {error}"
        store.save(job)
