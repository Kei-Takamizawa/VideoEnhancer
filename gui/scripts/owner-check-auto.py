"""Production owner check: input and WGC capture restricted to spawned processes."""

import argparse
import ctypes as c
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from ctypes import wintypes as w
from pathlib import Path

import psutil

WORK = Path(__file__).resolve().parents[3]
ROOT = WORK / "scratch/owner-check"
HOME = ROOT / "home"
EVIDENCE = WORK / "evidence/VE-P1e-3c2-F2"
STATE = EVIDENCE / "session.json"
U = c.WinDLL("user32", use_last_error=True)
U.GetForegroundWindow.restype = w.HWND
U.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
U.SetForegroundWindow.argtypes = [w.HWND]
U.SetProcessDpiAwarenessContext(c.c_void_p(-4))


class Mouse(c.Structure):
    _fields_ = [
        ("dx", w.LONG),
        ("dy", w.LONG),
        ("data", w.DWORD),
        ("flags", w.DWORD),
        ("time", w.DWORD),
        ("extra", c.c_size_t),
    ]


class Keyboard(c.Structure):
    _fields_ = [
        ("vk", w.WORD),
        ("scan", w.WORD),
        ("flags", w.DWORD),
        ("time", w.DWORD),
        ("extra", c.c_size_t),
    ]


class Payload(c.Union):
    _fields_ = [("mouse", Mouse), ("keyboard", Keyboard)]


class Input(c.Structure):
    _fields_ = [("kind", w.DWORD), ("payload", Payload)]


def send(hwnd, event):
    if U.GetForegroundWindow() != hwnd:
        raise RuntimeError("Foreground changed; input withheld")
    if U.SendInput(1, c.byref(event), c.sizeof(event)) != 1:
        raise c.WinError(c.get_last_error())


def save(state):
    STATE.write_text(json.dumps(state, indent=2))


def own(state):
    result = set()
    for pid, created in list(state.get("processes", {}).items()):
        try:
            proc = psutil.Process(int(pid))
            if abs(proc.create_time() - created) < 0.01:
                result.add(proc.pid)
                for child in proc.children(recursive=True):
                    result.add(child.pid)
                    state["processes"][str(child.pid)] = child.create_time()
        except psutil.Error:
            pass
    save(state)
    return result


def windows(state):
    pids = own(state)
    rows = []

    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        pid = w.DWORD()
        U.GetWindowThreadProcessId(hwnd, c.byref(pid))
        if pid.value in pids and U.IsWindowVisible(hwnd):
            title = c.create_unicode_buffer(512)
            U.GetWindowTextW(hwnd, title, 512)
            rect = w.RECT()
            U.GetWindowRect(hwnd, c.byref(rect))
            rows.append(
                dict(
                    hwnd=hwnd,
                    pid=pid.value,
                    title=title.value,
                    rect=[rect.left, rect.top, rect.right, rect.bottom],
                )
            )
        return True

    U.EnumWindows(visit, 0)
    return rows


def verify(state, hwnd):
    if hwnd not in [r["hwnd"] for r in windows(state)]:
        raise RuntimeError("Target is not a visible window in the spawned process tree")


def capture(state, hwnd, name):
    verify(state, hwnd)
    from windows_capture import WindowsCapture

    cap = WindowsCapture(window_hwnd=hwnd, cursor_capture=True, draw_border=False)
    seen = []

    @cap.event
    def on_frame_arrived(frame, control):
        frame.save_as_image(str(EVIDENCE / (name + ".png")))
        seen.append(dict(width=frame.width, height=frame.height, timespan=frame.timespan))
        control.stop()

    @cap.event
    def on_closed():
        pass

    control = cap.start_free_threaded()
    deadline = time.monotonic() + 8
    while not control.is_finished() and time.monotonic() < deadline:
        time.sleep(0.02)
    control.stop()
    if not seen:
        raise RuntimeError("No WGC frame within 8 seconds")
    return seen


def inventory():
    def size(path):
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0

    return dict(
        free={d: shutil.disk_usage(d + ":/").free for d in ["C", "D"]},
        sizes={
            str(p.relative_to(WORK)): size(p)
            for p in [
                WORK / "package/VideoEnhancer-candidate",
                EVIDENCE,
                WORK / "scratch",
                WORK / "cache",
                HOME,
                ROOT / "candidate-nodll",
            ]
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "launch",
            "prepare",
            "timedopen",
            "divider",
            "soak",
            "batch",
            "windows",
            "capture",
            "click",
            "move",
            "drag",
            "zoom",
            "key",
            "api",
            "close",
            "inventory",
        ],
    )
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {"processes": {}}
    if args.action == "launch":
        if own(state):
            raise RuntimeError("Previous spawned processes still running")
        (EVIDENCE / "disk-start.json").write_text(json.dumps(inventory(), indent=2))
        HOME.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            VE_HOME=str(HOME),
            APPDATA=str(HOME / "roaming"),
            LOCALAPPDATA=str(HOME / "local"),
            WEBVIEW2_USER_DATA_FOLDER=str(HOME / "webview"),
        )
        executable = WORK / "package/VideoEnhancer-candidate/VideoEnhancer.exe"
        if args.args == ["nodll"]:
            target = ROOT / "candidate-nodll"
            shutil.copytree(executable.parent, target)
            for dll in ["libmpv-2.dll", "libspirv-cross-c-shared.dll", "libwinpthread-1.dll"]:
                (target / dll).unlink()
            executable = target / "VideoEnhancer.exe"
        app = subprocess.Popen(
            [str(executable)],
            env=env,
            stdout=(EVIDENCE / "app.stdout.log").open("w"),
            stderr=(EVIDENCE / "app.stderr.log").open("w"),
        )
        state["processes"][str(app.pid)] = psutil.Process(app.pid).create_time()
        save(state)
        time.sleep(5)
        print(json.dumps(windows(state)))
    elif args.action == "windows":
        print(json.dumps(windows(state)))
    elif args.action == "inventory":
        print(json.dumps(inventory(), indent=2))
    elif args.action == "timedopen":
        from windows_capture import WindowsCapture

        hwnd, x, y = map(int, args.args[:3])
        name = args.args[3]
        verify(state, hwnd)
        U.SetForegroundWindow(hwnd)
        time.sleep(0.1)
        point = w.POINT(x, y)
        U.ClientToScreen(hwnd, c.byref(point))
        send(
            hwnd,
            Input(
                0,
                Payload(
                    mouse=Mouse(
                        round(point.x * 65535 / (U.GetSystemMetrics(0) - 1)),
                        round(point.y * 65535 / (U.GetSystemMetrics(1) - 1)),
                        0,
                        0x8001,
                        0,
                        0,
                    )
                ),
            ),
        )
        if name == "warm":
            time.sleep(0.6)
            U.SetForegroundWindow(hwnd)
            time.sleep(0.05)
        began = time.perf_counter()
        send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 0, 2, 0, 0))))
        send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 0, 4, 0, 0))))
        target = None
        while time.perf_counter() - began < 5:
            target = next((r for r in windows(state) if r["title"] == "VideoEnhancer Player"), None)
            if target:
                break
            time.sleep(0.005)
        if not target:
            raise RuntimeError("Player window absent for 5 seconds")
        cap = WindowsCapture(window_hwnd=target["hwnd"], cursor_capture=True, draw_border=False)
        rows = []

        @cap.event
        def on_frame_arrived(frame, control):
            elapsed = (time.perf_counter() - began) * 1000
            if not rows or elapsed - rows[-1]["ms"] >= 25:
                file = f"{name}-open-{len(rows):02}.png"
                frame.save_as_image(str(EVIDENCE / file))
                rows.append({"file": file, "ms": elapsed, "timespan": frame.timespan})
            if elapsed > 1600:
                control.stop()

        @cap.event
        def on_closed():
            pass

        cap.start()
        (EVIDENCE / (name + "-open.json")).write_text(
            json.dumps({"window": target, "captures": rows}, indent=2)
        )
        print(json.dumps({"window": target, "captures": rows}))
    elif args.action == "divider":
        hwnd = int(args.args[0])
        verify(state, hwnd)
        from windows_capture import WindowsCapture

        cap = WindowsCapture(window_hwnd=hwnd, cursor_capture=True, draw_border=False)
        pending = []
        rows = []

        @cap.event
        def on_frame_arrived(frame, control):
            if (
                pending
                and frame.timespan / 1e7 >= pending[0][1]
                and (
                    frame.frame_buffer[642:650, pending[0][2] - 3 : pending[0][2] + 3, :3].min(
                        axis=2
                    )
                    > 200
                ).sum()
                > 20
            ):
                index, began, x = pending.pop(0)
                frame.save_as_image(str(EVIDENCE / f"divider-timed-{index:02}.png"))
                rows.append(
                    {
                        "index": index,
                        "x": x,
                        "input_to_capture_ms": (time.perf_counter() - began) * 1000,
                        "frame_qpc": frame.timespan / 1e7,
                    }
                )

        @cap.event
        def on_closed():
            pass

        control = cap.start_free_threaded()
        try:
            time.sleep(0.3)
            for i in range(20):
                x = 900 if i % 2 == 0 else 400
                point = w.POINT(x, 607)
                U.ClientToScreen(hwnd, c.byref(point))
                send(
                    hwnd,
                    Input(
                        0,
                        Payload(
                            mouse=Mouse(
                                round(point.x * 65535 / (U.GetSystemMetrics(0) - 1)),
                                round(point.y * 65535 / (U.GetSystemMetrics(1) - 1)),
                                0,
                                0x8001,
                                0,
                                0,
                            )
                        ),
                    ),
                )
                pending.append((i, time.perf_counter(), x))
                send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 0, 2, 0, 0))))
                send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 0, 4, 0, 0))))
                time.sleep(0.4)
        finally:
            control.stop()
            (EVIDENCE / "divider-timing.json").write_text(json.dumps(rows, indent=2))
        print(json.dumps(rows))
    elif args.action == "soak":
        hwnd = int(args.args[0])
        verify(state, hwnd)
        from windows_capture import WindowsCapture

        cap = WindowsCapture(window_hwnd=hwnd, cursor_capture=True, draw_border=False)
        started = time.perf_counter()
        rows = []

        @cap.event
        def on_frame_arrived(frame, control):
            elapsed = time.perf_counter() - started
            if elapsed >= (len(rows) + 1) * 3 and len(rows) < 21:
                name = f"sync-{len(rows):02}.png"
                frame.save_as_image(str(EVIDENCE / name))
                rows.append({"file": name, "elapsed": elapsed, "timespan": frame.timespan})
                (EVIDENCE / "soak.json").write_text(json.dumps(rows, indent=2))

        @cap.event
        def on_closed():
            pass

        control = cap.start_free_threaded()
        try:
            for _ in range(3):
                time.sleep(17)
                send(hwnd, Input(1, Payload(keyboard=Keyboard(0x24, 0, 0, 0, 0))))
                send(hwnd, Input(1, Payload(keyboard=Keyboard(0x24, 0, 2, 0, 0))))
            time.sleep(12.5)
        finally:
            control.stop()
        print(json.dumps(rows))
    elif args.action == "batch":
        plan = json.loads((EVIDENCE / args.args[0]).read_text())
        log = []
        for action in plan:
            began = time.perf_counter()
            try:
                if action[0] == "wait":
                    time.sleep(float(action[1]))
                    output = ""
                else:
                    run = subprocess.run(
                        [os.sys.executable, "-B", __file__, *map(str, action)],
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    output = run.stdout + run.stderr
                    if run.returncode:
                        raise RuntimeError(output)
                log.append(
                    {
                        "action": action,
                        "elapsed_ms": (time.perf_counter() - began) * 1000,
                        "output": output,
                    }
                )
            except Exception as error:
                log.append({"action": action, "error": str(error)})
            (EVIDENCE / (args.args[0] + ".result.json")).write_text(json.dumps(log, indent=2))
        print(json.dumps(log))
    elif args.action in ["api", "prepare"]:
        discovery = json.loads((HOME / "serve.json").read_text())
        if discovery["pid"] not in own(state):
            raise RuntimeError("Engine is outside spawned process tree")
        if args.action == "prepare":
            for shape in ["landscape", "portrait"]:
                source = HOME / "inputs" / f"{shape}.mp4"
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / "clips" / source.name, source)
                body = json.dumps(
                    {
                        "file": str(source),
                        "output_folder": str(HOME / "outputs"),
                        "settings": {
                            "preset": "fast",
                            "codec": "hevc",
                            "short_side": "keep",
                            "fps": "off",
                        },
                    }
                ).encode()
                req = urllib.request.Request(
                    discovery["base_url"] + "/queue",
                    data=body,
                    headers={
                        "Authorization": "Bearer " + discovery["token"],
                        "Content-Type": "application/json",
                    },
                )
                try:
                    print(urllib.request.urlopen(req, timeout=120).read().decode())
                except urllib.error.HTTPError as error:
                    print(error.read().decode())
                    raise
            return
        route = args.args[0]
        body = args.args[1].encode() if len(args.args) > 1 else None
        request = urllib.request.Request(
            discovery["base_url"] + "/" + route,
            data=body,
            headers={
                "Authorization": "Bearer " + discovery["token"],
                "Content-Type": "application/json",
            },
        )
        print(urllib.request.urlopen(request, timeout=120).read().decode())
    elif args.action == "close":
        for row in windows(state):
            U.PostMessageW(row["hwnd"], 0x10, 0, 0)
        time.sleep(5)
        for pid in own(state):
            try:
                psutil.Process(pid).terminate()
            except psutil.Error:
                pass
        time.sleep(2)
        print(json.dumps({"remaining": sorted(own(state)), "pids": state["processes"]}))
    else:
        hwnd = int(args.args[0])
        verify(state, hwnd)
        if args.action == "capture":
            print(json.dumps(capture(state, hwnd, args.args[1])))
        else:
            U.SetForegroundWindow(hwnd)
            time.sleep(0.1)
            if U.GetForegroundWindow() != hwnd:
                raise RuntimeError("Cannot verify target as foreground; input withheld")
            if args.action == "key":
                key = int(args.args[1], 0)
                send(hwnd, Input(1, Payload(keyboard=Keyboard(key, 0, 0, 0, 0))))
                send(hwnd, Input(1, Payload(keyboard=Keyboard(key, 0, 2, 0, 0))))
            else:
                x, y = map(int, args.args[1:3])
                point = w.POINT(x, y)
                U.ClientToScreen(hwnd, c.byref(point))
                sx, sy = U.GetSystemMetrics(0), U.GetSystemMetrics(1)
                send(
                    hwnd,
                    Input(
                        0,
                        Payload(
                            mouse=Mouse(
                                round(point.x * 65535 / (sx - 1)),
                                round(point.y * 65535 / (sy - 1)),
                                0,
                                0x8001,
                                0,
                                0,
                            )
                        ),
                    ),
                )
                if args.action == "click":
                    send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 0, 2, 0, 0))))
                    send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 0, 4, 0, 0))))
                elif args.action == "drag":
                    send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 0, 2, 0, 0))))
                    target = w.POINT(int(args.args[3]), int(args.args[4]))
                    U.ClientToScreen(hwnd, c.byref(target))
                    for i in range(1, 11):
                        px = point.x + (target.x - point.x) * i / 10
                        py = point.y + (target.y - point.y) * i / 10
                        send(
                            hwnd,
                            Input(
                                0,
                                Payload(
                                    mouse=Mouse(
                                        round(px * 65535 / (sx - 1)),
                                        round(py * 65535 / (sy - 1)),
                                        0,
                                        0x8001,
                                        0,
                                        0,
                                    )
                                ),
                            ),
                        )
                        time.sleep(0.015)
                    send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 0, 4, 0, 0))))
                elif args.action == "zoom":
                    send(hwnd, Input(1, Payload(keyboard=Keyboard(0x11, 0, 0, 0, 0))))
                    send(hwnd, Input(0, Payload(mouse=Mouse(0, 0, 120, 0x800, 0, 0))))
                    send(hwnd, Input(1, Payload(keyboard=Keyboard(0x11, 0, 2, 0, 0))))
            print("Input delivered to verified own foreground HWND", hwnd)


if __name__ == "__main__":
    main()
