"""Compare captured burned-in frame digits with independent FFmpeg references."""

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageFont

WORK = Path(__file__).resolve().parents[3]
EVIDENCE = WORK / "evidence/VE-P1e-3b/section13"
SCRATCH = WORK / "scratch/mpv-spike"
FFMPEG = WORK / "cache/mpv-lgpl/ffmpeg/ffmpeg.exe"


def binary(image):
    return image.convert("L").point(lambda value: 255 if value > 210 else 0)


def references(clip, fps, base, width, height):
    folder = SCRATCH / "references" / f"{clip}-{width}x{height}"
    folder.mkdir(parents=True, exist_ok=True)
    first, last = max(0, base - 2), base + 4
    if all((folder / f"{n}.png").is_file() for n in range(first, last + 1)):
        return {n: Image.open(folder / f"{n}.png").convert("RGB") for n in range(first, last + 1)}
    command = [
        str(FFMPEG),
        "-hide_banner",
        "-y",
        "-i",
        str(SCRATCH / clip),
        "-vf",
        f"select=between(n\\,{first}\\,{last}),scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
        "-fps_mode",
        "vfr",
        "-start_number",
        str(first),
        str(folder / "%d.png"),
    ]
    with (folder / "generate.log").open("w") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    return {n: Image.open(folder / f"{n}.png").convert("RGB") for n in range(first, last + 1)}


def digit_roi(clip, base, width, height):
    font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 80)
    source_width, source_height = (2560, 1440) if "1440" in clip else (1920, 1080)
    left = 40 + font.getlength("frame ")
    right = left + font.getlength(str(base + 4))
    top, bottom = 40, 120
    if "rotation-display" in clip:
        left, top, right, bottom = top, source_width - right, bottom, source_width - left
        source_width, source_height = source_height, source_width
    scale = min(width / source_width, height / source_height)
    offset_x = (width - source_width * scale) / 2
    offset_y = (height - source_height * scale) / 2
    return (
        round(offset_x + left * scale),
        round(offset_y + top * scale),
        round(offset_x + right * scale),
        round(offset_y + bottom * scale),
    )


def identify(actual, refs, roi, expected):
    actual = binary(actual.crop(roi))
    scores = []
    for frame, reference in refs.items():
        best = 1.0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                shifted = tuple(p + (dx if i % 2 == 0 else dy) for i, p in enumerate(roi))
                candidate = binary(reference.crop(shifted))
                difference = ImageChops.difference(actual, candidate)
                score = sum(value > 0 for value in difference.get_flattened_data()) / (
                    actual.width * actual.height
                )
                best = min(best, score)
        scores.append((best, frame))
    scores.sort()
    return {
        "expected_frame": expected,
        "observed_frame": scores[0][1],
        "best_error": scores[0][0],
        "margin": scores[1][0] - scores[0][0],
        "scores": [{"frame": n, "error": s} for s, n in scores],
        "status": ("PASS" if scores[0][1] == expected else "FAIL")
        if scores[0][0] < 0.25 and scores[1][0] - scores[0][0] > 0.003
        else "UNAVAILABLE_AMBIGUOUS",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--case")
    args = parser.parse_args()
    cache = {}
    results = []
    for file in sorted(EVIDENCE.glob("bench-*-results.json")):
        if args.case and file.name != args.case + "-results.json":
            continue
        result = json.loads(file.read_text())
        clip = result["clip"]
        fps = 60 if ("1440p60" in clip or "1080p60" in clip) else 30
        base = 6 * fps
        steps = []
        for index, sample in enumerate(result.get("steps", [])):
            capture = sample.get("capture", {})
            if capture.get("status") != "MEASURED":
                steps.append(
                    {
                        "status": "UNAVAILABLE",
                        "reason": sample.get("reason", capture.get("reason", "No valid capture")),
                    }
                )
                continue
            image = Image.open(EVIDENCE / capture["value"]["file"]).convert("RGB")
            width = image.width - 2
            height = round(width * 9 / 16)
            top = image.height - height - 1
            actual = image.crop((1, top, 1 + width, top + height))
            key = (clip, width, height)
            if key not in cache:
                cache[key] = references(clip, fps, base, width, height)
            roi = digit_roi(clip, base, width, height)
            expected = base + [1, 2, 1][index]
            steps.append(
                {
                    **identify(actual, cache[key], roi, expected),
                    "roi": roi,
                    "capture": capture["value"]["file"],
                }
            )
        results.append({"case": file.name, "clip": clip, "steps": steps})
    output = "frame-accuracy-extra.json" if args.case else "frame-accuracy.json"
    (EVIDENCE / output).write_text(json.dumps(results, indent=2) + "\n")
    if args.preview:
        checks = []
        for file in sorted(EVIDENCE.glob("preview-*-results.json")):
            result = json.loads(file.read_text())
            for sample in result.get("samples", []):
                if not sample.get("image"):
                    continue
                image = Image.open(EVIDENCE / sample["image"]).convert("RGB")
                expected = round(sample["target"] * 30)
                refs = references(result["clip"], 30, expected, image.width, image.height)
                roi = digit_roi(result["clip"], expected, image.width, image.height)
                checks.append({"image": sample["image"], **identify(image, refs, roi, expected)})
        (EVIDENCE / "preview-frame-accuracy.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(
        json.dumps(
            [
                {
                    "case": r["case"],
                    "steps": [
                        (s["status"], s.get("observed_frame"), s.get("expected_frame"))
                        for s in r["steps"]
                    ],
                }
                for r in results
            ]
        )
    )


if __name__ == "__main__":
    main()
