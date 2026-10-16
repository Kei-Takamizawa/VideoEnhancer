"""Engine-home change generations and native Windows directory notifications."""

from __future__ import annotations

import ctypes
import os
import struct
import threading
from pathlib import Path
from typing import Any

_versions: dict[str, int] = {}
_lock = threading.Lock()
_windows: Any = ctypes


def generation(home: Path) -> int:
    with _lock:
        return _versions.get(os.path.normcase(str(home.resolve())), 0)


def changed(home: Path) -> None:
    with _lock:
        key = os.path.normcase(str(home.resolve()))
        _versions[key] = _versions.get(key, 0) + 1


class HomeWatcher:
    def __init__(self, home: Path):
        self.home = home
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="engine-home-watch", daemon=True)

    def start(self) -> None:
        if os.name == "nt":
            self.thread.start()

    def _run(self) -> None:
        kernel = _windows.WinDLL("kernel32", use_last_error=True)
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
        kernel.ReadDirectoryChangesW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(str(self.home), 1, 7, None, 3, 0x02000000, None)
        if handle == ctypes.c_void_p(-1).value:
            return
        try:
            buffer = ctypes.create_string_buffer(65536)
            count = ctypes.c_uint32()
            while not self.stop.is_set():
                if not kernel.ReadDirectoryChangesW(
                    handle,
                    buffer,
                    len(buffer),
                    True,
                    1 | 2 | 8 | 0x10,
                    ctypes.byref(count),
                    None,
                    None,
                ):
                    break
                if count.value == 0:
                    changed(self.home)
                offset = 0
                while offset < count.value:
                    following, _action, length = struct.unpack_from("<III", buffer.raw, offset)
                    name = (
                        buffer.raw[offset + 12 : offset + 12 + length]
                        .decode("utf-16-le")
                        .lower()
                        .replace("\\", "/")
                    )
                    if (
                        name in {"schedule.json", "settings.json", "deletions.jsonl"}
                        or name.endswith(("/manifest.json", "/quarantine.json", "/state.json"))
                        or name.startswith("profiles/")
                        and name.endswith(".json")
                    ):
                        changed(self.home)
                    if not following:
                        break
                    offset += following
        finally:
            kernel.CloseHandle(handle)

    def close(self) -> None:
        self.stop.set()
        if self.thread.native_id is not None and self.thread.is_alive():
            kernel = _windows.WinDLL("kernel32", use_last_error=True)
            kernel.OpenThread.restype = ctypes.c_void_p
            kernel.OpenThread.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            kernel.CancelSynchronousIo.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenThread(1, False, self.thread.native_id)
            if handle:
                kernel.CancelSynchronousIo(handle)
                kernel.CloseHandle(handle)
            self.thread.join(2)
