"""Section 10 measurements using synthetic media and the player's private IPC."""

import argparse
import importlib.util
import json
import statistics
import subprocess
import time
from pathlib import Path

from videoenhancer.jobs.pdh import ProcessMemoryCounters

WORK = Path(__file__).resolve().parents[3]
EVIDENCE = WORK / "evidence/VE-P1e-3c2/run2"
MEDIA = WORK / "scratch/p1e3c2-native"
spec = importlib.util.spec_from_file_location(
    "native", Path(__file__).with_name("player-acceptance.py")
)
assert spec is not None and spec.loader is not None
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
native.EVIDENCE = EVIDENCE


def barcode(width, height, y):
    filters = []
    for left in [0.1, 0.7]:
        x = round(width * left)
        top = round(height * y)
        unit = max(4, width // 160)
        filters.append(f"drawbox=x={x}:y={top}:w={unit * 12}:h={unit * 2}:color=black:t=fill")
        for bit in range(12):
            filters.append(
                f"drawbox=x={x + bit * unit}:y={top}:w={unit}:h={unit * 2}:"
                f"color=white:t=fill:enable='mod(floor(n/{2**bit}),2)'"
            )
    return filters


def fixtures():
    MEDIA.mkdir(parents=True, exist_ok=True)
    ffmpeg = WORK / "cache/mpv-lgpl/ffmpeg/ffmpeg.exe"
    for source, target in [(1080, 1440), (720, 1080)]:
        width = source * 16 // 9
        original = MEDIA / f"review-original-{source}.mp4"
        enhanced = MEDIA / f"review-output-{target}.mp4"
        font = "C\\:/Windows/Fonts/consola.ttf"
        if not original.exists():
            filters = barcode(width, source, 0.3) + [
                f"drawtext=fontfile='{font}':text='source %{{n}}':"
                "x=30:y=70:fontsize=60:fontcolor=white"
            ]
            subprocess.run(
                [
                    str(ffmpeg),
                    "-v",
                    "error",
                    "-nostdin",
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc2=size={width}x{source}:rate=30:duration=65",
                    "-vf",
                    ",".join(filters),
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    "p1",
                    "-b:v",
                    "2M",
                    "-an",
                    str(original),
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        if not enhanced.exists():
            width = target * 16 // 9
            filters = [
                "fps=60",
                f"scale={width}:{target}",
                *barcode(width, target, 0.4),
                f"drawtext=fontfile='{font}':text='output %{{n}}':"
                "x=w-480:y=70:fontsize=60:fontcolor=white",
            ]
            subprocess.run(
                [
                    str(ffmpeg),
                    "-v",
                    "error",
                    "-nostdin",
                    "-i",
                    str(original),
                    "-vf",
                    ",".join(filters),
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    "p1",
                    "-b:v",
                    "3M",
                    "-an",
                    str(enhanced),
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )


def profile(label):
    rows = []
    for index in range(5):
        player = native.Player("review-output-1080.mp4", f"{label}-{index}", 1920, 1080)
        phases = player.wait(lambda r: r.get("event") == "startupProfile")
        page = player.wait(lambda r: r.get("event") == "pageProfile")
        rows.append(
            dict(
                cold_ms=player.cold_ms,
                spawn_ms=player.spawn_ms,
                loaded=player.loaded,
                phases=phases,
                page=page,
            )
        )
        player.close()
        (EVIDENCE / f"{label}.json").write_text(json.dumps(rows, indent=2))
    print(label, "median", statistics.median(r["cold_ms"] for r in rows), flush=True)


def pairs(label):
    rows = []
    for original, output in [(1080, 1440), (720, 1080)]:
        player = native.Player(
            f"review-output-{output}.mp4",
            f"{label}-{output}",
            output * 16 // 9,
            output,
            f"review-original-{original}.mp4",
        )
        counters = ProcessMemoryCounters()
        try:
            player.request("beforeAfter", enabled=True)
            player.wait(
                lambda p: p.get("event") == "state" and p.get("original_decoder") == "d3d11va"
            )
            time.sleep(1)
            player.request("volume", percent=100)
            start_state = dict(player.state)
            samples = [native.sample(player, counters)]
            for _ in range(60):
                time.sleep(1)
                samples.append(native.sample(player, counters))
            player.request("pause", paused=True)
            a, b = samples[0], samples[-1]
            first = {p["pid"]: p["cpu"] for p in a["processes"]}
            cpu = sum(p["cpu"] - first[p["pid"]] for p in b["processes"] if p["pid"] in first)
            row = dict(
                original=original,
                output=output,
                samples=samples,
                cpu_percent=cpu / (b["at"] - a["at"]) * 100,
                state=player.state,
                start_state=start_state,
                dropped_during_interval=int(player.state.get("dropped", 0))
                - int(start_state.get("dropped", 0)),
                original_dropped_during_interval=int(player.state.get("original_dropped", 0))
                - int(start_state.get("original_dropped", 0)),
            )
            rows.append(row)
        finally:
            counters.close()
            player.close()
        (EVIDENCE / f"{label}.json").write_text(json.dumps(rows, indent=2))
        print(label, output, row["cpu_percent"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["fixtures", "profile", "pairs"])
    parser.add_argument("--label", default="before")
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    {
        "fixtures": fixtures,
        "profile": lambda: profile(args.label),
        "pairs": lambda: pairs(args.label),
    }[args.mode]()
