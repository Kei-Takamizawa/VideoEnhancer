"""Section 11 own-window layout proof and capture-free page-input timing."""

import argparse
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import time
from pathlib import Path

from PIL import Image

WORK = Path(__file__).resolve().parents[3]
EVIDENCE = WORK / "evidence/VE-P1e-3c2/run3"
MEDIA = WORK / "scratch/p1e3c2-run3-native"
spec = importlib.util.spec_from_file_location(
    "native", Path(__file__).with_name("player-acceptance.py")
)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
native.SCRATCH = MEDIA
native.EVIDENCE = EVIDENCE


def fixtures():
    MEDIA.mkdir(parents=True, exist_ok=True)
    for label, width, height, fps in [
        ("source", 1920, 1080, 30),
        ("landscape", 2560, 1440, 60),
        ("portrait-source", 270, 480, 30),
        ("portrait", 540, 960, 60),
    ]:
        target = MEDIA / f"{label}.mp4"
        if target.exists():
            continue
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={width}x{height}:rate={fps}:duration=15",
                "-c:v",
                "h264_nvenc",
                "-preset",
                "p1",
                "-cq",
                "28",
                "-pix_fmt",
                "yuv420p",
                str(target),
            ],
            check=True,
        )


def player(label, portrait=False):
    return native.Player(
        "portrait.mp4" if portrait else "landscape.mp4",
        label,
        540 if portrait else 2560,
        960 if portrait else 1440,
        "portrait-source.mp4" if portrait else "source.mp4",
        window_size=(540, 960) if portrait else (960, 540),
        original_size=(270, 480) if portrait else (1920, 1080),
    )


def timing():
    app = player("divider-timing")
    try:
        app.wait(lambda row: row.get("event") == "configured")
        time.sleep(0.1)
        app.request("testUi", action="before")
        app.request("pause", paused=False)
        time.sleep(1)
        app.request("testUi", action="benchmark")
        row = app.wait(lambda row: row.get("event") == "dividerBenchmark", timeout=20)["result"]
        (EVIDENCE / "divider-timing.json").write_text(json.dumps(row, indent=2))
        if row.get("error"):
            raise RuntimeError(row["error"])
        values = [r["total_ms"] for r in row["rows"]]
        uncertainty = min(c["rtt_ms"] for c in row["calibration"]) / 2 + 0.2
        assert len(values) == 20
        assert statistics.median(values) + uncertainty <= 34
        assert max(values) + uncertainty <= 50
        print(
            "20 capture-free page inputs:",
            len(values),
            "median",
            statistics.median(values),
            "worst",
            max(values),
            flush=True,
        )
    finally:
        app.close()


def capture(app, name):
    app.request("testUi", action="inspect")
    layout = app.wait(
        lambda row: row.get("event") == "dividerBenchmark" and row.get("result", {}).get("layout")
    )["result"]
    (EVIDENCE / f"{name}.json").write_text(json.dumps(layout, indent=2))
    app.request("selfCapture", name=name)
    shutil.copyfile(app.profile / f"{name}.png", EVIDENCE / f"{name}.png")
    # The opaque HWND's captured RGB is already composited. Keep raw RGBA too.
    Image.open(EVIDENCE / f"{name}.png").convert("RGB").save(EVIDENCE / f"{name}-rgb.png")


def layouts():
    rows = []
    for mockup in [False, True]:
        for portrait in [False, True]:
            os.environ["VE_PLAYER_TEST_MOCKUP"] = "1" if mockup else "0"
            label = ("mockup" if mockup else "product") + (
                "-portrait" if portrait else "-landscape"
            )
            app = player(label, portrait)
            try:
                app.wait(lambda row: row.get("event") == "startupProfile")
                if mockup:
                    app.request("testUi", action="mockupPortrait" if portrait else "mockup")
                else:
                    app.request("pause", paused=True)
                time.sleep(0.5)
                capture(app, label + "-paused")
                app.request("testUi", action="mockupHover" if mockup else "preview")
                time.sleep(0.6)
                capture(app, label + "-hover")
                app.request("testUi", action="mockupLeave" if mockup else "leavePreview")
                app.request("testUi", action="mockupBefore" if mockup else "before")
                time.sleep(0.3)
                capture(app, label + "-before")
                app.request("testUi", action="mockupZoom" if mockup else "zoom")
                time.sleep(0.3)
                capture(app, label + "-zoom")
                if mockup:
                    app.request("testUi", action="mockupPlay")
                else:
                    app.request("pause", paused=False)
                    app.request("testUi", action="show")
                time.sleep(0.2)
                capture(app, label + "-playing")
                rows.append({"label": label, "captures": 5})
            finally:
                app.close()
                rows[-1].update(
                    exit_code=app.process.returncode, remaining_children=app.remaining_children
                )
    (EVIDENCE / "layout-proof.json").write_text(json.dumps(rows, indent=2))
    html = (
        '<!doctype html><meta charset="utf-8"><title>Own-window mockup comparison</t'
        "itle><style>body{background:#222;color:white;font:16px sans-serif}section{d"
        "isplay:grid;grid-template-columns:1fr 1fr;gap:12px}img{max-width:100%}h2{gr"
        "id-column:1/-1}</style><h1>Product (left) / approved mockup (right)</h1><p>"
        "Own-window WGC RGB review copies; RGB bytes unchanged; "
        "raw RGBA originals retained. Mockup uses its own "
        "fakefs framing; demo toolbar is excluded. Native window frames remain.</p><"
        "section>"
    )
    deltas = []
    selectors = [
        ".osc-wrap",
        ".osc",
        ".ctrl",
        ".grp.left",
        ".grp.right",
        ".ob.play",
        ".titlebar",
        ".titlebar .ob",
        ".xrow",
        ".split",
        ".zoomchip",
    ]
    for shape in ["landscape", "portrait"]:
        for state in ["paused", "hover", "before", "zoom", "playing"]:
            html += (
                f'<h2>{shape}: {state}</h2><img src="product-{shape}-{state}-rgb.png">'
                f'<img src="mockup-{shape}-{state}-rgb.png">'
            )
            product = json.loads((EVIDENCE / f"product-{shape}-{state}.json").read_text())
            mockup = json.loads((EVIDENCE / f"mockup-{shape}-{state}.json").read_text())
            errors = []
            for selector in selectors:
                a, b = product["nodes"].get(selector), mockup["nodes"].get(selector)
                if a and b:
                    errors.extend(abs(a[k] - b[k]) for k in ["x", "y", "width", "height"])
            deltas.append(dict(shape=shape, state=state, max_geometry_delta_css_px=max(errors)))
    (EVIDENCE / "comparison.html").write_text(html + "</section>", encoding="utf-8")
    (EVIDENCE / "geometry-comparison.json").write_text(json.dumps(deltas, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["fixtures", "timing", "layouts"])
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault(
        "VE_PLAYER_EXE", str(WORK / "cache/tauri-target/release/VideoEnhancer-Player.exe")
    )
    {"fixtures": fixtures, "timing": timing, "layouts": layouts}[args.mode]()
