"""Drive only a spawned player's IPC and inspect every received WGC frame."""

import argparse
import importlib.util
import json
import math
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=640)
    parser.add_argument("--stepped", action="store_true")
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use an alphanumeric label")
    work = Path(__file__).resolve().parents[3]
    scratch = work / "scratch/p1e3d1"
    evidence = work / "evidence/VE-P1e-3d1"
    spec = importlib.util.spec_from_file_location(
        "native", Path(__file__).with_name("player-acceptance.py")
    )
    assert spec is not None and spec.loader is not None
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    native.SCRATCH, native.EVIDENCE = scratch, evidence
    player = native.Player(
        "seam-blue.mp4",
        args.label,
        1920,
        1080,
        original="seam-red.mp4",
        original_size=(1280, 720),
        window_size=(args.width, args.height),
    )
    report = {
        "pid": player.process.pid,
        "executable_sha256": player.executable_sha256,
        "window_size": [args.width, args.height],
        "stepped": args.stepped,
    }
    try:
        player.request("beforeAfter", enabled=True)
        player.request("pause", paused=False)
        time.sleep(1)
        player.request("testSeam", enabled=True)
        began = time.perf_counter()
        commands = 0
        while time.perf_counter() - began < 60:
            elapsed = time.perf_counter() - began
            phase = commands * 7 % 1600
            fraction = (
                0.1 + min(phase, 1600 - phase) / 1000
                if args.stepped
                else 0.5 + 0.4 * math.sin(elapsed * math.pi)
            )
            player.request("divider", fraction=fraction)
            commands += 1
            time.sleep(max(0, began + commands / 60 - time.perf_counter()))
        _, result = player.request("testSeam", enabled=False)
        report.update(
            result=result["result"], commands=commands, seconds=time.perf_counter() - began
        )
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        player.close()
        report["remaining_children"] = player.remaining_children
        (evidence / f"{args.label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
