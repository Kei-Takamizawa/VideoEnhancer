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
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user.GetWindowLongPtrW.restype = ctypes.c_ssize_t

    def windows():
        result = []

        @callback_type
        def visit(handle, _):
            if user.IsWindowVisible(handle):
                name = ctypes.create_unicode_buffer(256)
                user.GetClassNameW(handle, name, 256)
                pid = wintypes.DWORD()
                user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
                rect = wintypes.RECT()
                user.GetWindowRect(handle, ctypes.byref(rect))
                client = wintypes.RECT()
                user.GetClientRect(handle, ctypes.byref(client))
                result.append(
                    (
                        int(handle),
                        pid.value,
                        name.value,
                        [rect.left, rect.top, rect.right, rect.bottom],
                        [client.left, client.top, client.right, client.bottom],
                        user.GetWindowLongPtrW(handle, -20),
                    )
                )
            return True

        user.EnumWindows(visit, 0)
        return result

    baseline = {handle for handle, _, _, _, _, _ in windows()}
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
        for handle, pid, name, rect, client, exstyle in windows():
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
                        rect=rect,
                        client_rect=client,
                        extended_style=exstyle,
                    )
                )
        polls += 1
        time.sleep(max(0, started + polls * 0.1 - time.monotonic()))
    own_path = folder / "own-windows.json"
    own = set(json.loads(own_path.read_text())) if own_path.exists() else set()
    events = [event for event in events if event["hwnd"] not in own]
    non_display = [
        event
        for event in events
        if not event["console"]
        and (
            event["rect"][0] >= event["rect"][2]
            or event["rect"][1] >= event["rect"][3]
            or (
                event["extended_style"] & 0x80000
                and (
                    event["client_rect"][0] >= event["client_rect"][2]
                    or event["client_rect"][1] >= event["client_rect"][3]
                )
            )
        )
    ]
    events = [event for event in events if event not in non_display]
    (folder / "windows.json").write_text(
        json.dumps(
            dict(
                poll_interval_ms=100,
                polls=polls,
                elapsed_seconds=time.monotonic() - started,
                unexpected_windows=events,
                non_display_windows=non_display,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
