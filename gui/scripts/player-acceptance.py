"""Own-helper IPC measurements; presentation signals are not display photons."""

import argparse
import base64
import hashlib
import json
import os
import queue
import random
import shutil
import statistics
import subprocess
import threading
import time
from pathlib import Path

import psutil

from videoenhancer.jobs.pdh import ProcessMemoryCounters

WORK = Path(__file__).resolve().parents[3]
SCRATCH = WORK / "scratch/p1e3c2-native"
EVIDENCE = WORK / "evidence/VE-P1e-3c2"


class Player:
    def __init__(
        self, clip, label, width, height, original=None, window_size=(960, 540), original_size=None
    ):
        self.events = queue.Queue()
        self.rows = []
        self.state = {}
        self.deferred = []
        self.sequence = 1000000
        self.log = (EVIDENCE / f"{label}.stderr.log").open("w", encoding="utf-8")
        self.profile = SCRATCH / label
        self.started = time.perf_counter()
        executable = Path(
            os.environ.get(
                "VE_PLAYER_EXE",
                str(Path(os.environ["CARGO_TARGET_DIR"]) / "debug/VideoEnhancer-Player.exe"),
            )
        ).resolve(strict=True)
        if not executable.is_relative_to(WORK):
            raise ValueError("Player executable must stay inside work")
        self.process = subprocess.Popen(
            [str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.spawn_ms = (time.perf_counter() - self.started) * 1000
        handles = {"output": str(SCRATCH / clip)}
        if (SCRATCH / "review-poster.jpg").exists():
            handles["poster"] = str(SCRATCH / "review-poster.jpg")
        if original:
            handles["original"] = str(SCRATCH / original)
        import re

        size_match = re.search(r"review-original-(\d+)", original or "")
        original_height = int(size_match.group(1)) if size_match else height
        boot = dict(
            version=1,
            owner=0,
            width=window_size[0],
            height=window_size[1],
            x=100,
            y=100,
            profile=str(self.profile),
            handles=handles,
            output="output",
            original="original" if original else None,
            title="Synthetic acceptance",
            original_width=original_size[0] if original_size else original_height * 16 // 9,
            original_height=original_size[1] if original_size else original_height,
            video_width=width,
            video_height=height,
        )

        def read():
            for line in self.process.stdout:
                packet = json.loads(line)
                record = dict(packet)
                if "image" in record:
                    record["image_sha256"] = hashlib.sha256(
                        base64.b64decode(record.pop("image").split(",", 1)[1])
                    ).hexdigest()
                self.rows.append(record)
                self.events.put(packet)

        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        self.process.stdin.write(json.dumps(boot) + "\n")
        self.process.stdin.flush()
        self.executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
        self.loaded = self.wait(lambda row: row.get("event") == "loaded")
        self.cold_ms = (time.perf_counter() - self.started) * 1000

    def wait(self, match, timeout=20):
        for index, packet in enumerate(self.deferred):
            if match(packet):
                return self.deferred.pop(index)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                packet = self.events.get(timeout=0.2)
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(f"Helper exited {self.process.returncode}") from None
                continue
            if packet.get("event") == "state":
                self.state = packet
            if packet.get("event") == "error":
                raise RuntimeError("Helper reported playback error")
            if match(packet):
                if packet.get("error"):
                    raise RuntimeError(packet["error"])
                return packet
            if packet.get("event") != "state":
                self.deferred.append(packet)
        raise TimeoutError("Player event timeout")

    def request(self, kind, **args):
        self.sequence += 1
        started = time.perf_counter()
        self.process.stdin.write(
            json.dumps(dict(version=1, id=self.sequence, command=dict(type=kind, **args))) + "\n"
        )
        self.process.stdin.flush()
        result = self.wait(lambda packet: packet.get("reply") == self.sequence)
        return (time.perf_counter() - started) * 1000, result

    def close(self):
        children = (
            psutil.Process(self.process.pid).children(recursive=True)
            if self.process.poll() is None
            else []
        )
        if self.process.poll() is None:
            try:
                self.request("close")
                self.process.wait(timeout=5)
            except (RuntimeError, TimeoutError, OSError):
                pass
            finally:
                if self.process.poll() is None:
                    self.process.kill()
                    self.process.wait()
        _, alive = psutil.wait_procs(children, timeout=10)
        self.remaining_children = [p.pid for p in alive]
        self.reader.join(timeout=1)
        self.log.close()
        (EVIDENCE / f"{self.profile.name}.ndjson").write_text(
            "".join(json.dumps(row) + "\n" for row in self.rows), encoding="utf-8"
        )
        # Only this helper's exited profile; no scratch-wide cleanup here.
        if self.remaining_children:
            raise RuntimeError(f"Player child processes have not exited: {self.remaining_children}")
        shutil.rmtree(self.profile)


def sample(player, counters):
    parent = psutil.Process(player.process.pid)
    processes = [parent, *parent.children(recursive=True)]
    values = []
    for process in processes:
        try:
            gpu = counters.read(process.pid)
            cpu = process.cpu_times()
            memory = process.memory_info()
            values.append(
                dict(
                    pid=process.pid,
                    cpu=cpu.user + cpu.system,
                    private=memory.private,
                    handles=process.num_handles(),
                    dedicated=gpu[0],
                    shared=gpu[1],
                )
            )
        except psutil.Error:
            continue
    return dict(at=time.perf_counter(), processes=values)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--clip", default="h264-1080p30.mp4")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--original")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--mode", choices=["bench", "soak"], default="bench")
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use an alphanumeric label")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    result = dict(label=args.label, runs=[], errors=[])
    counters = ProcessMemoryCounters()
    started = time.monotonic()
    try:
        cycles = 0
        while (time.monotonic() - started < args.seconds) if args.mode == "soak" else cycles < 5:
            player = None
            row = {}
            result["runs"].append(row)
            try:
                player = Player(
                    args.clip, f"{args.label}-{cycles}", args.width, args.height, args.original
                )
                row["cold_ms"] = player.cold_ms
                row["executable_sha256"] = player.executable_sha256
                if args.mode == "soak":
                    row["open"] = sample(player, counters)
                    time.sleep(20)
                    row["after_play"] = sample(player, counters)
                elif cycles == 0:
                    row["warm_ms"] = [player.request("open", handle="output")[0] for _ in range(5)]
                    row["seeks_ms"] = [
                        player.request("seek", seconds=at)[0]
                        for at in random.Random(3).sample(range(2, 61), 20)
                    ]
                    player.request("seek", seconds=0)
                    if args.original:
                        row["enable_pair_ms"] = player.request("beforeAfter", enabled=True)[0]
                        row["divider_ack_ms"] = [
                            player.request("divider", fraction=f)[0]
                            for f in [0.1, 0.9, 0.25, 0.75, 0.5]
                        ]
                    row["samples"] = [sample(player, counters)]
                    for _ in range(args.seconds):
                        time.sleep(1)
                        row["samples"].append(sample(player, counters))
                    player.request("pause", paused=True)
                    player.wait(
                        lambda packet: packet.get("event") == "state" and packet.get("paused")
                    )
                    row["steps"] = [
                        player.request("step", forward=forward) for forward in [True, True, False]
                    ]
                    row["new_preview_ms"] = []
                    row["cached_preview_ms"] = []
                    generation = 0
                    for at in [2, 15, 30, 45, 60]:
                        for cached in [False, True]:
                            generation += 1
                            began = time.perf_counter()
                            player.request("preview", seconds=at, generation=generation)
                            packet = player.wait(
                                lambda p, expected=generation: (
                                    p.get("event") == "previewReady"
                                    and p.get("generation") == expected
                                )
                            )
                            row["cached_preview_ms" if cached else "new_preview_ms"].append(
                                (time.perf_counter() - began) * 1000
                            )
                            if not cached:
                                (EVIDENCE / f"{args.label}-preview-{at}.png").write_bytes(
                                    base64.b64decode(packet["image"].split(",", 1)[1])
                                )
                    row["last_state"] = player.state
            except Exception as error:
                row["error"] = repr(error)
                result["errors"].append(repr(error))
            finally:
                if player:
                    try:
                        player.close()
                        row["exit_code"] = player.process.returncode
                        row["remaining_child_pids"] = player.remaining_children
                    except Exception as error:
                        row["close_error"] = repr(error)
                        result["errors"].append(repr(error))
                cycles += 1
                (EVIDENCE / f"{args.label}.json").write_text(
                    json.dumps(result, indent=2), encoding="utf-8"
                )
                print(args.label, cycles, "errors", len(result["errors"]), flush=True)
            if result["errors"]:
                break
    finally:
        counters.close()
    values = [row["cold_ms"] for row in result["runs"] if "cold_ms" in row]
    print("cold median", statistics.median(values) if values else None, "errors", result["errors"])
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
