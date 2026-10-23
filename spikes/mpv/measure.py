"""Self-tests and raw measurements for this spike's own windows only."""

import argparse
import base64
import importlib.util
import json
import os
import queue
import random
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import psutil
from PIL import Image, ImageChops, ImageStat

sys.dont_write_bytecode = True

WORK = Path(__file__).resolve().parents[3]
SPIKE = WORK / "repo/spikes/mpv"
EVIDENCE = WORK / "evidence" / os.environ.get("VE_MPV_CYCLE", "VE-P1e-3c1")
SCRATCH = WORK / "scratch/mpv-spike"
CACHE = WORK / "cache/mpv-lgpl"
EXE = CACHE / "spike-target/debug/mpv-embedding-spike.exe"
CLIPS = [
    ("h264-1080p30.mp4", 30),
    ("hevc-main10-1440p60.mp4", 60),
    ("av1-10bit-1440p60.mp4", 60),
    ("vp9-1080p60.mp4", 60),
    ("hevc-rotation-display.mp4", 30),
]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        name = self.path.split("?")[0].lstrip("/")
        if name == "player":
            body = (
                (SPIKE / "controls.html").read_bytes()
                + b"<script>"
                + (SPIKE / "html5.js").read_bytes()
                + b"</script>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        allowed = {n for n, _ in CLIPS} | {"probe.mkv", "probe.webm", "probe.mov"}
        if name not in allowed:
            self.send_error(404)
            return
        path = SCRATCH / name
        size = path.stat().st_size
        start, end = 0, size - 1
        ranged = self.headers.get("Range")
        if ranged:
            first, last = ranged.removeprefix("bytes=").split("-")
            start = int(first or 0)
            end = min(int(last) if last else size - 1, size - 1)
        self.send_response(206 if ranged else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if ranged:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    part = stream.read(min(1024 * 1024, remaining))
                    if not part:
                        break
                    self.wfile.write(part)
                    remaining -= len(part)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *args):
        pass


class Client:
    def __init__(self, mode, clip, label, base_url):
        self.mode, self.clip, self.label = mode, clip, label
        self.sequence = 0
        self.queue = queue.Queue()
        self.deferred = []
        profile = SCRATCH / ("profile-" + label)
        profile.mkdir(parents=True, exist_ok=True)
        self.log = (EVIDENCE / (label + ".jsonl")).open("w", encoding="utf-8")
        self.err = (EVIDENCE / (label + ".stderr.log")).open("w", encoding="utf-8")
        env = os.environ.copy()
        env.pop("VE_MPV_SPIKE_AUTOCLOSE_MS", None)
        env["VE_MPV_SPIKE_TEST"] = "1"
        env["VE_MPV_HTML_URL"] = base_url + "/player"
        if mode == "STACK":
            env["VE_MPV_EXTERNAL"] = str(SCRATCH / clip)
            env.setdefault("VE_MPV_GRAPH", "[vid1][vid2]hstack=inputs=2[vo]")
        self.started = time.perf_counter()
        self.process = subprocess.Popen(
            [
                str(EXE),
                mode,
                os.environ.get("VE_MPV_DLL", str(CACHE / "libmpv-2.dll")),
                str(SCRATCH / clip),
                str(profile),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.err,
            text=True,
            encoding="utf-8",
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.ready = self.wait(lambda r: r.get("event") == "ready", 30)
            self.ready_ms = (time.perf_counter() - self.started) * 1000
            time.sleep(0.4)
            if mode == "HTML5":
                self.js("document.readyState")
                self.call(op="media")
        except BaseException:
            self.close()
            raise

    def _read(self):
        for line in self.process.stdout:
            try:
                value = json.loads(line)
                self.log.write(json.dumps({"received": time.perf_counter(), **value}) + "\n")
                self.log.flush()
                self.queue.put(value)
            except json.JSONDecodeError:
                self.log.write(json.dumps({"non_json": line}) + "\n")

    def wait(self, predicate, timeout=20):
        for i, value in enumerate(self.deferred):
            if predicate(value):
                return self.deferred.pop(i)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                value = self.queue.get(timeout=min(0.5, deadline - time.monotonic()))
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(f"Prototype exited {self.process.returncode}") from None
                continue
            if predicate(value):
                return value
            self.deferred.append(value)
        raise TimeoutError("Prototype response timeout")

    def send(self, **request):
        self.sequence += 1
        request["id"] = self.sequence
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        return self.sequence

    def call(self, **request):
        key = self.send(**request)
        value = self.wait(lambda r: r.get("reply") == key)
        if "error" in value:
            raise RuntimeError(value["error"])
        return value.get("result")

    def js(self, expression):
        self.sequence += 1
        key = "js-" + str(self.sequence)
        encoded_key = json.dumps(key)
        script = (
            f"Promise.resolve({expression}).then("
            f"result=>send({{test_result:{encoded_key},result}}))"
            f".catch(e=>send({{test_result:{encoded_key},error:String(e)}}));"
        )
        self.call(op="eval", script=script)
        value = self.wait(lambda r: r.get("test_result") == key)
        if value.get("error"):
            raise RuntimeError(value["error"])
        return value.get("result")

    def html(self, action, value):
        self.sequence += 1
        key = "html-" + str(self.sequence)
        self.call(
            op="eval",
            script=f"htmlBench({json.dumps(key)},{json.dumps(action)},{json.dumps(value)})",
        )
        return self.wait(lambda r: r.get("test_result") == key)

    def cdp(self, method, params):
        key = self.send(op="cdp", method=method, params=params)
        ack = self.wait(lambda r: r.get("reply") == key)
        if ack.get("error"):
            return ack
        return self.wait(lambda r: r.get("test_result") == key)

    def props(self):
        return self.js("htmlMetrics()") if self.mode == "HTML5" else self.call(op="properties")

    def command(self, *args):
        return self.call(op="command", args=list(args))

    def capture(self, suffix):
        name = self.label + "-" + suffix + ".png"
        try:
            result = self.call(op="capture", name=name)
        except Exception as error:
            result = {"nonblack_fraction": 0, "dxgi_error": str(error)}
        if result.get("nonblack_fraction", 0) < 0.01:
            if self.mode in ("B1", "B2", "HTML5", "AB", "STACK"):
                wgc_name = name.replace(".png", "-wgc.png")
                try:
                    result = self.call(op="capture", name=wgc_name, wgc=True)
                    name = wgc_name
                except Exception as error:
                    raise RuntimeError(f"DXGI crop is black; WGC failed: {error}") from error
            if result.get("nonblack_fraction", 0) < 0.01:
                raise RuntimeError("Capture returned black pixels; visible-frame tests unavailable")
        result["file"] = name
        return result

    def close(self):
        if self.process.poll() is None:
            try:
                self.call(op="quit")
                self.process.wait(timeout=10)
            except Exception:
                # Only this Popen child's PID is terminated, never owner processes.
                self.process.terminate()
                self.process.wait(timeout=10)
        self.err.close()


def memory(pid):
    spec = importlib.util.spec_from_file_location(
        "spike_pdh", WORK / "repo/src/videoenhancer/jobs/pdh.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    counter = module.ProcessMemoryCounters()
    return counter


def sample(pid, counter):
    parent = psutil.Process(pid)
    processes = [parent] + parent.children(recursive=True)
    values, cpu, rss = [], 0.0, 0
    for process in processes:
        try:
            u, s = counter.read(process.pid)
            values.append((u, s))
            times = process.cpu_times()
            cpu += times.user + times.system
            rss += process.memory_info().rss
        except psutil.Error:
            continue
    return {
        "at": time.perf_counter(),
        "pids": [p.pid for p in processes],
        "dedicated_bytes": sum(v[0] or 0 for v in values),
        "shared_bytes": sum(v[1] or 0 for v in values),
        "cpu_seconds": cpu,
        "rss_bytes": rss,
    }


def attempt(function, *args, **kwargs):
    try:
        return {"status": "MEASURED", "value": function(*args, **kwargs)}
    except Exception as error:
        return {"status": "UNAVAILABLE", "reason": str(error)}


def gui_test(client):
    results = {"state": client.call(op="state")}
    results["dom_geometry"] = client.js(
        "({width:innerWidth,height:innerHeight,bar:document.querySelector('#bar').getBoundingClientRect().toJSON()})"
    )
    client.command("set", "pause", "yes")
    client.call(op="track", args=["seek", "6", "absolute+exact"])
    time.sleep(0.3)
    results["visible"] = attempt(client.capture, "controls")
    client.js("(()=>{document.querySelector('#bar').style.visibility='hidden';return true})()")
    time.sleep(0.2)
    results["hidden"] = attempt(client.capture, "hidden")
    client.js("(()=>{document.querySelector('#bar').style.visibility='visible';return true})()")
    if results["visible"]["status"] == results["hidden"]["status"] == "MEASURED":
        a = Image.open(EVIDENCE / results["visible"]["value"]["file"]).convert("RGB")
        b = Image.open(EVIDENCE / results["hidden"]["value"]["file"]).convert("RGB")
        # Blank portions under the bar, away from glyphs/track. Nonzero video
        # texture and near-identical pixels reject an opaque panel implementation.
        width, height = a.size
        rois = [
            (width // 2, height - 80, width - 100, height - 65),
            (30, height - 115, 260, height - 80),
        ]
        comparisons = []
        for roi in rois:
            difference = ImageStat.Stat(ImageChops.difference(a.crop(roi), b.crop(roi)))
            comparisons.append(
                {
                    "roi": roi,
                    "mean_absolute_error": sum(difference.mean) / 3,
                    "video_stddev": sum(ImageStat.Stat(b.crop(roi)).stddev) / 3,
                }
            )
        results["transparent_pixels"] = comparisons
        # Require visible controls as well as unchanged video; video alone must
        # never pass the alpha test (the first B1 run exposed exactly that bug).
        difference = ImageChops.difference(a, b)
        results["controls_changed_pixels"] = sum(
            max(pixel) > 3 for pixel in difference.get_flattened_data()
        )
        region = (30, height - 54, width - 30, height - 20)
        delta = difference.crop(region)
        results["bar_region"] = region
        results["bar_matching_fraction"] = sum(
            max(pixel) <= 3 for pixel in delta.get_flattened_data()
        ) / (delta.width * delta.height)
        geometry = results["dom_geometry"]
        scale = (width - 2) / geometry["width"]
        title = height - geometry["height"] * scale - 1
        bar = geometry["bar"]
        # Sample unpainted padding INSIDE the control bar. Painted text, shadows
        # and the seek track are intentionally excluded from this alpha oracle.
        blank = (
            round(1 + (bar["left"] + 20) * scale),
            round(title + (bar["top"] + 2) * scale),
            round(1 + (bar["right"] - 20) * scale),
            round(title + (bar["top"] + 6) * scale),
        )
        results["blank_band"] = blank
        results["blank_band_error"] = sum(ImageStat.Stat(difference.crop(blank)).mean) / 3
        results["blank_band_video_stddev"] = sum(ImageStat.Stat(b.crop(blank)).stddev) / 3
        results["alpha_test"] = (
            "PASS"
            if (
                results["controls_changed_pixels"] > 100
                and results["blank_band_error"] <= 1
                and results["blank_band_video_stddev"] > 10
            )
            else "UNAVAILABLE_OR_FAIL"
        )
    # Exercise actual WebView2 input dispatch, not DOM click() alone.
    results["cdp_pointer"] = client.cdp(
        "Input.dispatchMouseEvent",
        {"type": "mousePressed", "x": 65, "y": 510, "button": "left", "clickCount": 1},
    )
    results["cdp_pointer_release"] = client.cdp(
        "Input.dispatchMouseEvent",
        {"type": "mouseReleased", "x": 65, "y": 510, "button": "left", "clickCount": 1},
    )
    results["cdp_wheel"] = client.cdp(
        "Input.dispatchMouseEvent",
        {"type": "mouseWheel", "x": 300, "y": 220, "deltaX": 0, "deltaY": -120},
    )
    results["cdp_key"] = client.cdp(
        "Input.dispatchKeyEvent",
        {"type": "keyDown", "key": " ", "code": "Space", "windowsVirtualKeyCode": 32},
    )
    client.cdp(
        "Input.dispatchKeyEvent",
        {"type": "keyUp", "key": " ", "code": "Space", "windowsVirtualKeyCode": 32},
    )
    time.sleep(0.2)
    results["after_html_input"] = client.props()
    client.command("set", "pause", "no")
    results["moving_a"] = attempt(client.capture, "moving-a")
    time.sleep(0.25)
    results["moving_b"] = attempt(client.capture, "moving-b")
    client.command("set", "pause", "yes")
    results["after_moving"] = client.props()
    # Native messages go exclusively to the prototype's own host HWND.
    for message, wparam in [
        (0x0200, 0),
        (0x0201, 1),
        (0x0202, 0),
        (0x0201, 1),
        (0x0202, 0),
        (0x020A, 120 << 16),
    ]:
        client.call(op="input", message=message, wparam=wparam, lparam=200 | (200 << 16))
    time.sleep(0.3)
    results["after_native_input"] = client.call(op="state")
    if results["after_native_input"]["fullscreen"]:
        client.call(op="window", action="fullscreen")
    client.call(op="input", message=0x100, wparam=32, lparam=0)
    client.call(op="input", message=0x101, wparam=32, lparam=0)
    time.sleep(0.2)
    results["after_native_keyboard"] = client.props()
    time.sleep(0.6)
    slider = client.js(
        "({dpr:devicePixelRatio,rect:document.querySelector('#seek').getBoundingClientRect().toJSON()})"
    )
    rect = slider["rect"]
    start_x = rect["left"] + rect["width"] * 0.2
    end_x = rect["left"] + rect["width"] * 0.75
    y = rect["top"] + rect["height"] / 2
    if client.mode == "B1":
        for message, x, buttons in [
            (0x200, start_x, 0),
            (0x201, start_x, 1),
            (0x200, end_x, 1),
            (0x202, end_x, 0),
        ]:
            position = round(x * slider["dpr"]) | (round(y * slider["dpr"]) << 16)
            client.call(op="input", message=message, wparam=buttons, lparam=position)
    else:
        for kind, x in [("mousePressed", start_x), ("mouseMoved", end_x), ("mouseReleased", end_x)]:
            client.cdp(
                "Input.dispatchMouseEvent",
                {
                    "type": kind,
                    "x": x,
                    "y": y,
                    "button": "left",
                    "buttons": 0 if kind == "mouseReleased" else 1,
                    "clickCount": 1,
                },
            )
    time.sleep(0.5)
    results["after_seek_drag"] = client.props()
    states = []
    for action in ["resize", "maximise", "minimise", "restore", "fullscreen", "fullscreen"]:
        client.call(op="window", action=action, width=976, height=579)
        time.sleep(0.2)
        state = {"action": action, "state": client.call(op="state")}
        if action != "minimise":
            state["capture"] = attempt(client.capture, "state-" + str(len(states)))
        states.append(state)
    for dpi in [96, 120, 144, 96]:
        client.call(op="window", action="dpi", dpi=dpi)
        time.sleep(0.15)
        states.append({"simulated_dpi": dpi, "state": client.call(op="state")})
    results["window_states"] = states
    results["real_dpi_moves"] = (
        "NOT_AVAILABLE if single monitor at one scale; "
        "simulated messages are not real monitor moves"
    )
    return results


def playback(client, clip, fps, base_url, duration):
    result = {
        "mode": client.mode,
        "clip": clip,
        "ready_ms": client.ready_ms,
        "first_frame": [],
        "seeks": [],
        "steps": [],
        "playback_samples": [],
    }
    client.js("(()=>{seek.onpointermove=null;return true})()")
    for run in range(5):
        if client.mode == "HTML5":
            value = client.html("load", base_url + "/" + clip + f"?run={run}")
        else:
            value = attempt(client.call, op="track", args=["loadfile", str(SCRATCH / clip)])
        result["first_frame"].append(value)
    if client.mode == "HTML5" and all(v.get("error") for v in result["first_frame"]):
        reason = result["first_frame"][-1]["error"]
        result["seeks"] = [{"status": "UNAVAILABLE", "reason": reason} for _ in range(20)]
        result["steps"] = [{"status": "UNAVAILABLE", "reason": reason} for _ in range(3)]
        result["playback_unavailable"] = reason
        return result
    rng = random.Random(1337)
    for _ in range(20):
        target = rng.uniform(2, 58)
        if client.mode == "HTML5":
            value = client.html("seek", target)
        else:
            value = attempt(client.call, op="track", args=["seek", str(target), "absolute+exact"])
        result["seeks"].append({"target": target, "sample": value})
    # Exactness is judged independently with captured burned-in frame numbers.
    if client.mode == "HTML5":
        client.js("(()=>{video.pause();return true})()")
        result["step_initial_seek"] = client.html("seek", 6)
    else:
        client.command("set", "pause", "yes")
        result["step_initial_seek"] = attempt(
            client.call, op="track", args=["seek", "6", "absolute+exact"]
        )
    for index, direction in enumerate([1, 1, -1]):
        if client.mode == "HTML5":
            value = client.html("step", direction / fps)
        else:
            value = attempt(
                client.call, op="track", args=["frame-step" if direction > 0 else "frame-back-step"]
            )
        time.sleep(0.2)
        result["steps"].append(
            {
                "direction": direction,
                "sample": value,
                "capture": attempt(client.capture, "step-" + str(index))
                if os.environ.get("VE_MPV_CAPTURE") != "0"
                else {"status": "NOT_RUN", "reason": "Capture disabled for timing run"},
            }
        )
    if client.mode == "HTML5":
        client.html("seek", 0)
        client.js("video.play()")
    else:
        client.call(op="track", args=["seek", "0", "absolute+exact"])
        client.command("set", "pause", "no")
    counter = memory(client.process.pid)
    try:
        start_props = client.props()
        start = time.perf_counter()
        while time.perf_counter() - start < duration:
            result["playback_samples"].append(sample(client.process.pid, counter))
            if len(result["playback_samples"]) % 15 == 0:
                print(
                    json.dumps(
                        {"progress": client.label, "seconds": len(result["playback_samples"])}
                    ),
                    flush=True,
                )
            time.sleep(max(0, start + len(result["playback_samples"]) - time.perf_counter()))
        result["playback_wall_seconds"] = time.perf_counter() - start
        result["start_properties"] = start_props
        result["end_properties"] = client.props()
        client.call(op="close-player")
        result["after_close"] = []
        for _ in range(5):
            result["after_close"].append(sample(client.process.pid, counter))
            time.sleep(1)
    finally:
        counter.close()
    return result


def preview(client):
    samples = []
    for at in [0, 4, 10, 20, 40, 50, 3, 30, 15, 55]:
        started = time.perf_counter()
        client.call(op="preview", time=at)
        value = None
        while time.perf_counter() - started < 10:
            value = client.call(op="preview-frame")
            if (
                value.get("time") is not None
                and value.get("seeking") == "no"
                and value.get("bytes", 0) > 1000
            ):
                break
            time.sleep(0.01)
        # Wait for the actual image decode rather than a fixed grace period.
        image = client.js(
            "(()=>{const im=document.querySelector('#preview img');"
            "return im.decode().then(()=>({src:im.src,width:im.naturalWidth,"
            "height:im.naturalHeight}));})()"
        )
        shown_ms = (time.perf_counter() - started) * 1000
        uri = image["src"]
        name = client.label + "-hover-" + str(at) + ".png"
        (EVIDENCE / name).write_bytes(base64.b64decode(uri.split(",", 1)[1]))
        samples.append(
            {
                "target": at,
                "latency_ms": shown_ms,
                "result": value,
                "image": name,
                "decoded_width": image["width"],
            }
        )
        cached_start = time.perf_counter()
        cached = client.call(op="preview", time=at)
        decoded = client.js("document.querySelector('#preview img').decode().then(()=>true)")
        samples[-1]["cached_ms"] = (time.perf_counter() - cached_start) * 1000
        samples[-1]["cached_result"] = cached
        samples[-1]["cached_image_complete"] = decoded
    client.js("(()=>{preview.style.display='block';preview.style.left='250px';return true})()")
    positions = [(index * 17) % 60 + 0.1 for index in range(99)] + [41.1]
    keys = [client.send(op="preview", time=at) for at in positions]
    replies = [client.wait(lambda r, key=key: r.get("reply") == key) for key in keys]
    deadline = time.monotonic() + 10
    latest = {}
    while time.monotonic() < deadline:
        latest = client.call(op="preview-frame")
        if latest.get("key") == 411 and latest.get("seeking") == "no":
            break
        time.sleep(0.01)
    return {
        "samples": samples,
        "burst": {
            "requests": len(keys),
            "cancelled": sum(
                isinstance(r.get("result"), dict) and r["result"].get("cancelled", False)
                for r in replies
            ),
            "latest": latest,
            "status": "PASS" if latest.get("key") == 411 else "FAIL",
        },
        "capture": attempt(client.capture, "preview"),
    }


def sync(client, duration):
    client.command("seek", "0", "absolute+exact")
    client.command("set", "pause", "no")
    counter = memory(client.process.pid)
    rows = []
    changes = []
    state = client.call(op="state")
    start = time.perf_counter()
    try:
        for _ in range(duration):
            if os.environ.get("VE_MPV_MOVABLE_DIVIDER") and len(rows) in (20, 40):
                divider = 0.25 if len(rows) == 20 else 0.75
                graph = (
                    f"[vid1]crop=iw*{divider}:ih:0:0[l];"
                    f"[vid2]crop=iw*{1 - divider}:ih:iw*{divider}:0[r];"
                    "[l][r]hstack=inputs=2[vo]"
                )
                begin = time.perf_counter()
                reply = client.call(op="track", args=["set", "lavfi-complex", graph])
                changes.append(
                    {
                        "divider": divider,
                        "graph": graph,
                        "reply": reply,
                        "wall_ms": (time.perf_counter() - begin) * 1000,
                    }
                )
            props = client.props()
            row = {
                "elapsed": time.perf_counter() - start,
                "properties": props,
                "memory": sample(client.process.pid, counter),
            }
            if props.get("second-time") is not None:
                row["drift_ms"] = abs(float(props["time-pos"]) - float(props["second-time"])) * 1000
            if (
                client.mode == "STACK"
                and (len(rows) + 1) % 10 == 0
                and os.environ.get("VE_MPV_CAPTURE") != "0"
            ):
                row["capture"] = attempt(client.capture, "sync-" + str(len(rows) + 1))
            rows.append(row)
            time.sleep(max(0, start + len(rows) - time.perf_counter()))
    finally:
        counter.close()
    return {
        "samples": rows,
        "state": state,
        "graph": os.environ.get("VE_MPV_GRAPH", "[vid1][vid2]hstack=inputs=2[vo]"),
        "divider_changes": changes,
        "capture": attempt(client.capture, "sync")
        if os.environ.get("VE_MPV_CAPTURE") != "0"
        else {"status": "NOT_RUN", "reason": "Capture disabled"},
    }


def lazy(client):
    process = psutil.Process(client.process.pid)

    def loaded():
        return [m.path for m in process.memory_maps() if Path(m.path).name == "libmpv-2.dll"]

    counter = memory(client.process.pid)
    try:
        result = {"before": sample(process.pid, counter), "dll_before": loaded()}
        result["open"] = client.call(op="open-player")
        time.sleep(1)
        result["dll_open"] = loaded()
        result["playing"] = sample(process.pid, counter)
        result["properties"] = client.props()
        result["versions"] = client.call(op="versions")
        result["close"] = client.call(op="close-player")
        result["after_close"] = []
        for _ in range(5):
            time.sleep(1)
            result["after_close"].append(sample(process.pid, counter))
        result["dll_after"] = loaded()
        result["host_alive"] = process.is_running()
        return result
    finally:
        counter.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["B1", "B2", "HTML5", "AB", "STACK"], required=True)
    parser.add_argument("--clip", default=CLIPS[0][0])
    parser.add_argument(
        "--phase",
        choices=[
            "gui",
            "bench",
            "preview",
            "sync",
            "probe",
            "container",
            "codec",
            "overlay",
            "focus",
            "lazy",
        ],
        default="probe",
    )
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Label must be a safe filename")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    client = None
    result = {"phase": args.phase, "mode": args.mode, "clip": args.clip}
    try:
        if args.phase == "lazy":
            os.environ["VE_MPV_DEFER_OPEN"] = "1"
        client = Client(args.mode, args.clip, args.label, base_url)
        if args.phase == "gui":
            result.update(gui_test(client))
        elif args.phase == "bench":
            fps = dict(CLIPS).get(args.clip, 30)
            result.update(playback(client, args.clip, fps, base_url, args.seconds))
        elif args.phase == "preview":
            result.update(preview(client))
        elif args.phase == "sync":
            result.update(sync(client, args.seconds))
        elif args.phase == "lazy":
            result.update(lazy(client))
        elif args.phase == "container":
            result["first_frame"] = attempt(
                client.call, op="track", args=["loadfile", str(SCRATCH / args.clip)]
            )
            result["seek"] = attempt(
                client.call, op="track", args=["seek", "32.125", "absolute+exact"]
            )
            result["capture"] = attempt(client.capture, "container")
        elif args.phase == "codec":
            result["load"] = client.html("load", base_url + "/" + args.clip)
            time.sleep(1)
            result["properties"] = client.props()
        elif args.phase == "focus":
            client.command("set", "pause", "yes")
            result["before"] = client.props()
            for kind in ("mousePressed", "mouseReleased"):
                client.cdp(
                    "Input.dispatchMouseEvent",
                    {"type": kind, "x": 65, "y": 510, "button": "left", "clickCount": 1},
                )
            result["focus"] = client.js(
                "({id:document.activeElement.id,documentFocused:document.hasFocus()})"
            )
            time.sleep(0.1)
            result["after_pointer"] = client.props()
            client.cdp(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "key": " ", "code": "Space", "windowsVirtualKeyCode": 32},
            )
            client.cdp(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": " ", "code": "Space", "windowsVirtualKeyCode": 32},
            )
            time.sleep(0.1)
            result["after_key"] = client.props()
        elif args.phase == "overlay":
            client.command("set", "pause", "yes")
            client.call(op="track", args=["seek", "6", "absolute+exact"])
            result["captures"] = []
            for visible in (True, False):
                visibility = "visible" if visible else "hidden"
                client.js(
                    "(()=>{document.querySelector('#bar').style.visibility="
                    + json.dumps(visibility)
                    + ";return true})()"
                )
                time.sleep(0.2)
                name = args.label + "-" + visibility + ".png"
                captured = attempt(client.call, op="capture", name=name, wgc=True, overlay=True)
                row = {"visible": visible, "capture": captured, "file": name}
                if captured["status"] == "MEASURED":
                    image = Image.open(EVIDENCE / name).convert("RGBA")
                    alpha = image.getchannel("A")
                    row["alpha_zero_fraction"] = sum(
                        value == 0 for value in alpha.get_flattened_data()
                    ) / (image.width * image.height)
                    row["alpha_extrema"] = alpha.getextrema()
                result["captures"].append(row)
        else:
            time.sleep(1)
            result.update(
                {
                    "properties": client.props(),
                    "state": client.call(op="state"),
                    "capture": attempt(client.capture, "probe"),
                }
            )
    except Exception as error:
        result["failure"] = repr(error)
    finally:
        if client:
            client.close()
            result["exit_code"] = client.process.returncode
        server.shutdown()
        (EVIDENCE / (args.label + "-results.json")).write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "finished": args.label,
                "failure": result.get("failure"),
                "exit": result.get("exit_code"),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
