"""Opt-in Windows acceptance evidence: visible top-level windows every 100 ms."""

import ctypes
import json
import sys
import time
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path

import psutil


def main() -> None:
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    user = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

    def windows():
        result = []

        @callback_type
        def visit(handle, _):
            if user.IsWindowVisible(handle):
                name = ctypes.create_unicode_buffer(256)
                user.GetClassNameW(handle, name, 256)
                pid = wintypes.DWORD()
                user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
                result.append((int(handle), pid.value, name.value))
            return True

        user.EnumWindows(visit, 0)
        return result

    baseline = {handle for handle, _, _ in windows()}
    (folder / "ready").write_text("ready")
    events, seen, polls = [], set(), 0
    started = time.monotonic()
    while not (folder / "stop").exists() and time.monotonic() - started < 600:
        root_path = folder / "app.pid"
        root = int(root_path.read_text()) if root_path.exists() else 0
        descendants = {root}
        if root:
            try:
                descendants.update(p.pid for p in psutil.Process(root).children(recursive=True))
            except psutil.NoSuchProcess:
                pass
        for handle, pid, name in windows():
            if handle in baseline or handle in seen:
                continue
            console = name in {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"}
            extra = pid in descendants and not (pid == root and name == "Chrome_WidgetWin_1")
            if console or extra:
                seen.add(handle)
                events.append(
                    dict(
                        time=datetime.now(UTC).isoformat(),
                        hwnd=handle,
                        pid=pid,
                        window_class=name,
                        console=console,
                        owned_extra=extra,
                    )
                )
        polls += 1
        time.sleep(max(0, started + polls * 0.1 - time.monotonic()))
    own_path = folder / "own-windows.json"
    own = set(json.loads(own_path.read_text())) if own_path.exists() else set()
    events = [event for event in events if event["hwnd"] not in own]
    (folder / "windows.json").write_text(
        json.dumps(
            dict(
                poll_interval_ms=100,
                polls=polls,
                elapsed_seconds=time.monotonic() - started,
                unexpected_windows=events,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
