"""Own-window UI, mockup and moving-divider WGC proof; no desktop capture."""

import importlib.util
import json
import os
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "proof", Path(__file__).with_name("player-visual-proof.py")
)
assert spec is not None and spec.loader is not None
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


def main():
    player = proof.review.native.Player(
        "review-output-1080.mp4", "ui-final-two", 1920, 1080, "review-original-720.mp4"
    )
    result = {"divider": [], "errors": []}
    try:
        player.wait(lambda row: row.get("event") == "startupProfile")
        player.request("beforeAfter", enabled=True)
        player.request("seek", seconds=2)
        player.request("pause", paused=False)
        player.wait(lambda row: row.get("event") == "state" and row.get("paused") is False)
        for index in range(20):
            fraction = 0.75 if index % 2 == 0 else 0.25
            began = time.perf_counter()
            player.request("divider", fraction=fraction)
            while True:
                image = proof.capture(player, f"ui-divider-{index:02}")
                pixel = image[round(38 + 540 * 0.4 + 3), round(1 + 960 * 0.7 + 3)]
                monochrome = int(pixel.max()) - int(pixel.min()) < 20
                if monochrome == (fraction < 0.5):
                    break
                if time.perf_counter() - began > 0.5:
                    result["errors"].append(f"Pixel did not follow divider {index}")
                    break
            result["divider"].append(
                dict(
                    fraction=fraction,
                    pixel=pixel.tolist(),
                    frame_ms=(player.capture_qpc - began) * 1000,
                    observation_ms=(time.perf_counter() - began) * 1000,
                    paused=player.state.get("paused"),
                    position=player.state.get("position"),
                )
            )
        player.request("beforeAfter", enabled=False)
        player.request("pause", paused=True)
        time.sleep(0.5)
        proof.capture(player, "ui-paused")
        player.request("testUi", action="show")
        player.request("pause", paused=False)
        time.sleep(0.2)
        proof.capture(player, "ui-playing-visible")
        time.sleep(2.4)
        proof.capture(player, "ui-autohidden")
        player.request("pause", paused=True)
        time.sleep(0.7)
        proof.capture(player, "ui-paused-visible")
        result["native_exit_before_close"] = player.process.poll()
    finally:
        player.close()
        result["exit_code"] = player.process.returncode
        result["remaining_children"] = player.remaining_children
        (proof.EVIDENCE / "ui-proof.json").write_text(json.dumps(result, indent=2))
    os.environ["VE_PLAYER_TEST_MOCKUP"] = "1"
    player = proof.review.native.Player("review-output-1080.mp4", "mockup-final", 1920, 1080)
    try:
        player.wait(lambda row: row.get("event") == "startupProfile")
        time.sleep(0.7)
        player.request("testUi", action="mockup")
        time.sleep(0.3)
        proof.capture(player, "mockup-landscape")
    finally:
        player.close()
        os.environ.pop("VE_PLAYER_TEST_MOCKUP", None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    os.environ.setdefault(
        "VE_PLAYER_EXE",
        str(proof.review.WORK / "cache/tauri-target/release/VideoEnhancer-Player.exe"),
    )
    main()
