"""Bounded own-process native-player checks using only synthetic media."""

import argparse
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--seconds", type=float, default=1)
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use an alphanumeric label")
    work = Path(__file__).resolve().parents[3]
    evidence = work / "evidence/VE-P1e-3c2"
    evidence.mkdir(parents=True, exist_ok=True)
    scratch = work / "scratch/p1e3c2-native"
    scratch.mkdir(parents=True, exist_ok=True)
    folder = Path(os.environ["CARGO_TARGET_DIR"]) / "debug"
    handles = {"output": str(args.fixture.resolve(strict=True))}
    if args.original:
        handles["original"] = str(args.original.resolve(strict=True))
    boot = dict(
        version=1,
        owner=0,
        width=960,
        height=540,
        x=100,
        y=100,
        profile=str(scratch / args.label),
        handles=handles,
        output="output",
        original="original" if args.original else None,
        title="Synthetic player acceptance",
        video_width=args.width,
        video_height=args.height,
    )
    events = queue.Queue()
    records = []
    started = time.perf_counter()
    with (evidence / f"{args.label}.stderr.log").open("w", encoding="utf-8") as log:
        player = subprocess.Popen(
            [str(folder / "VideoEnhancer-Player.exe")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        def read():
            for line in player.stdout:
                packet = json.loads(line)
                records.append(packet)
                events.put(packet)

        threading.Thread(target=read, daemon=True).start()
        try:
            player.stdin.write(json.dumps(boot) + "\n")
            player.stdin.flush()
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    packet = events.get(timeout=0.5)
                except queue.Empty:
                    if player.poll() is not None:
                        raise RuntimeError(
                            f"Helper exited {player.returncode} before loaded"
                        ) from None
                    continue
                if packet.get("event") == "error":
                    raise RuntimeError("Helper reported a playback error")
                if packet.get("event") == "loaded":
                    print(
                        "loaded",
                        round((time.perf_counter() - started) * 1000, 3),
                        "ms",
                        "hwnd",
                        packet.get("hwnd"),
                        flush=True,
                    )
                    break
            else:
                raise TimeoutError("No loaded event")
            time.sleep(args.seconds)
            player.stdin.write(
                json.dumps(dict(version=1, id=1000000, command=dict(type="close"))) + "\n"
            )
            player.stdin.flush()
            player.wait(timeout=5)
            print("exit", player.returncode)
            if player.returncode:
                raise RuntimeError("Helper failed")
        finally:
            if player.poll() is None:
                player.kill()
                player.wait()
            (evidence / f"{args.label}.ndjson").write_text(
                "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
            )


if __name__ == "__main__":
    main()
