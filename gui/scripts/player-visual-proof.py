"""WGC pixel checks; every command targets the spawned helper's own IPC/window."""

import importlib.util
import json
import os
import shutil
import statistics
import time
from pathlib import Path

import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location(
    "review", Path(__file__).with_name("player-review.py")
)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
EVIDENCE = review.EVIDENCE


def capture(player, name):
    _, packet = player.request("selfCapture", name=name)
    player.capture_qpc = packet["result"].get("frame_qpc_seconds")
    target = EVIDENCE / f"{name}.png"
    shutil.copyfile(player.profile / f"{name}.png", target)
    return np.array(Image.open(target).convert("RGB"))


def number(image, original=False):
    # WGC includes this window's 37px caption, 1px top/bottom client border.
    width = image.shape[1] - 2
    height = image.shape[0] - 39
    video_h = width * 9 / 16
    top = 38 + (height - video_h) / 2
    x = 1 + width * (0.1 if original else 0.7)
    y = round(top + video_h * (0.3 if original else 0.4) + video_h / 180)
    unit = width / 160
    values = [image[y, round(x + (i + 0.5) * unit)].mean() > 180 for i in range(12)]
    return sum(int(value) * 2**bit for bit, value in enumerate(values))


def main():
    player = review.native.Player(
        "review-output-1080.mp4",
        os.environ.get("VE_VISUAL_LABEL", "visual-proof-two"),
        1920,
        1080,
        "review-original-720.mp4",
    )
    result = {"steps": [], "drift": [], "divider_ms": [], "errors": []}
    try:
        player.wait(lambda p: p.get("event") == "startupProfile")
        player.request("pause", paused=True)
        player.wait(lambda p: p.get("event") == "state" and p.get("paused"))
        time.sleep(0.3)
        visible = capture(player, "controls-paused")
        player.request("testUi", action="clean")
        time.sleep(0.2)
        clean = capture(player, "controls-clean-reference")
        result["transparent_padding_max_delta"] = int(
            np.abs(
                visible[510:520, 350:500].astype(int) - clean[510:520, 350:500].astype(int)
            ).max()
        )
        result["header_changed_pixels"] = int(
            np.any(visible[68:98, 25:225] != clean[68:98, 25:225], axis=2).sum()
        )
        player.request("testUi", action="show")
        time.sleep(0.2)
        player.request("testUi", action="preview")
        time.sleep(0.5)
        capture(player, "preview-above")
        player.request("testUi", action="help")
        time.sleep(0.2)
        capture(player, "shortcut-sheet")
        player.request("testUi", action="help")
        player.request("testUi", action="speed")
        time.sleep(0.2)
        capture(player, "speed-menu")
        player.request("testUi", action="speed")
        player.request("testUi", action="letterbox")
        time.sleep(0.2)
        boxed = capture(player, "black-letterbox")
        result["letterbox_rgb_max"] = int(boxed[40:60, 350:600].max())
        player.request("testUi", action="letterbox")
        time.sleep(0.2)
        player.request("beforeAfter", enabled=True)
        player.request("seek", seconds=5)
        time.sleep(0.2)
        image = capture(player, "step-start")
        frame = number(image)
        for index, forward in enumerate([True] * 24 + [False] * 12):
            expected = frame + (1 if forward else -1)
            began = time.perf_counter()
            _, step_reply = player.request("step", forward=forward)
            values = []
            while True:
                image = capture(player, f"step-{index:02}")
                value = number(image)
                values.append(value)
                if (
                    value == expected and number(image, True) == (expected + 1) // 2
                ) or time.perf_counter() - began > 1:
                    break
            result["steps"].append(
                dict(
                    before=frame,
                    expected=expected,
                    captured=value,
                    observed=values,
                    original_captured=number(image, True),
                    target=step_reply.get("target_seconds"),
                    original_target=step_reply.get("original_target_seconds"),
                    pass_exact=value == expected and number(image, True) == (expected + 1) // 2,
                )
            )
            frame = value
        # Enable the alternative and sample burned-in digits, independently of properties.
        player.request("beforeAfter", enabled=True)
        player.request("seek", seconds=1)
        player.request("pause", paused=False)
        time.sleep(1)
        began = time.perf_counter()
        for index in range(61):
            delay = began + index - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            image = capture(player, f"drift-{index:02}")
            source, output = number(image, True), number(image)
            result["drift"].append(
                dict(
                    at=time.perf_counter() - began,
                    source=source,
                    output=output,
                    output_frame_error=output - source * 2,
                )
            )
        player.request("pause", paused=True)
        player.wait(lambda p: p.get("event") == "state" and p.get("paused"))
        time.sleep(0.3)
        player.request("divider", fraction=1)
        time.sleep(0.1)
        original = capture(player, "divider-original")
        player.request("divider", fraction=0)
        time.sleep(0.1)
        enhanced = capture(player, "divider-enhanced")
        point = (round(38 + 540 * 0.4 + 3), round(1 + 960 * 0.7 + 3))
        for index in range(20):
            fraction = 0.75 if index % 2 == 0 else 0.25
            expected = (original if fraction > 0.5 else enhanced)[point]
            began = time.perf_counter()
            player.request("divider", fraction=fraction)
            while True:
                image = capture(player, f"divider-{index:02}")
                if np.abs(image[point].astype(float) - expected.astype(float)).max() < 15:
                    break
                if time.perf_counter() - began > 0.5:
                    result["errors"].append(f"Divider pixel timeout {index}")
                    break
            result["divider_ms"].append((player.capture_qpc - began) * 1000)
            result.setdefault("divider_observation_ms", []).append(
                (time.perf_counter() - began) * 1000
            )
        player.request("beforeAfter", enabled=False)
        player.request("pause", paused=False)
        player.request("testUi", action="blur")
        player.request("testUi", action="show")
        time.sleep(0.15)
        visible = capture(player, "playing-visible")
        time.sleep(2.5)
        hidden = capture(player, "playing-autohidden")
        player.request("pause", paused=True)
        time.sleep(0.7)
        paused = capture(player, "paused-visible-again")
        for name, image in [("visible", visible), ("hidden", hidden), ("paused", paused)]:
            result[f"{name}_button_white_pixels"] = int(
                (image[-50:-28, 40:62].min(axis=2) > 220).sum()
            )
        errors = [abs(x["output_frame_error"]) for x in result["drift"]]
        result["drift_median_frames"] = statistics.median(errors)
        result["drift_worst_frames"] = max(errors)
    finally:
        (EVIDENCE / "visual-proof.json").write_text(json.dumps(result, indent=2))
        player.close()
    print(json.dumps({k: v for k, v in result.items() if k not in ["steps", "drift"]}, indent=2))


if __name__ == "__main__":
    os.environ.setdefault(
        "VE_PLAYER_EXE", str(review.WORK / "cache/tauri-target/release/VideoEnhancer-Player.exe")
    )
    main()
