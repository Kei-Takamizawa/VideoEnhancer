"""Capture only the failed desktop process tree and its native windows."""

from __future__ import annotations

import ctypes
import json
import sys
from ctypes import wintypes

import psutil


def inspect(pid: int) -> dict:
    processes = []
    try:
        root = psutil.Process(pid)
        for process in [root, *root.children(recursive=True)]:
            try:
                arguments = process.cmdline()
                processes.append(
                    {
                        "pid": process.pid,
                        "name": process.name(),
                        "status": process.status(),
                        "arguments": [
                            "<redacted>" if "token" in value.lower() else value
                            for value in arguments
                        ],
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except psutil.NoSuchProcess:
        pass
    owned = {row["pid"] for row in processes}
    windows = []
    user = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.SendMessageTimeoutW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_size_t),
    ]

    def describe(handle) -> dict:
        text = ctypes.create_unicode_buffer(1024)
        name = ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(handle, text, len(text))
        user.GetClassNameW(handle, name, len(name))
        if not text.value and name.value in {"Static", "Button"}:
            result = ctypes.c_size_t()
            user.SendMessageTimeoutW(
                handle, 0x000D, len(text), ctypes.addressof(text), 2, 200, ctypes.byref(result)
            )
        return {
            "handle": handle,
            "class": name.value,
            "text": text.value,
            "visible": bool(user.IsWindowVisible(handle)),
        }

    @callback_type
    def visit(handle, _):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value in owned:
            window = describe(handle)
            window["pid"] = owner.value
            children = []

            @callback_type
            def child(child_handle, _):
                if len(children) < 100:
                    children.append(describe(child_handle))
                return True

            user.EnumChildWindows(handle, child, 0)
            window["children"] = children
            windows.append(window)
        return True

    user.EnumWindows(visit, 0)
    return {"root_pid": pid, "processes": processes, "windows": windows}


if __name__ == "__main__":
    print(json.dumps(inspect(int(sys.argv[1])), ensure_ascii=True))
