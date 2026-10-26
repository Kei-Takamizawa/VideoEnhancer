"""Measure the alternative bounded idle policy in the test-only helper."""

import importlib.util
import json
import os
import statistics
import time
from pathlib import Path

import psutil


def main():
    work = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "player_acceptance", Path(__file__).with_name("player-acceptance.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    os.environ["VE_PLAYER_TEST_IDLE"] = "1"
    os.environ["VE_PLAYER_EXE"] = str(
        Path(os.environ["CARGO_TARGET_DIR"]) / "debug/VideoEnhancer-Player.exe"
    )
    counters = module.ProcessMemoryCounters()
    player = None
    report = {}
    try:
        player = module.Player("h264-1080p30.mp4", "idle-policy-test", 1920, 1080)
        report["cold_ms"] = player.cold_ms
        report["executable_sha256"] = player.executable_sha256
        report["playing"] = module.sample(player, counters)
        player.request("close")
        time.sleep(10)
        report["idle_at_10_seconds"] = module.sample(player, counters)
        report["warm_ms"] = []
        for _ in range(5):
            report["warm_ms"].append(player.request("open", handle="output")[0])
            player.request("close")
        report["warm_median_ms"] = statistics.median(report["warm_ms"])
        children = psutil.Process(player.process.pid).children(recursive=True)
        began = time.perf_counter()
        player.process.wait(timeout=32)
        report["auto_exit_seconds_after_last_close"] = time.perf_counter() - began
        report["exit_code"] = player.process.returncode
        _, alive = psutil.wait_procs(children, timeout=10)
        report["remaining_children"] = [process.pid for process in alive]
        if alive or player.process.returncode:
            raise RuntimeError("Idle helper did not release its process tree")
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        if player:
            player.close()
        counters.close()
        (work / "evidence/VE-P1e-3c2/idle-policy.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    print("idle policy", report["warm_ms"], report["auto_exit_seconds_after_last_close"])


if __name__ == "__main__":
    main()
