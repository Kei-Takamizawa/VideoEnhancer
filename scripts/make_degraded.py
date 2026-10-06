"""Create private, reproducible compressed inputs outside the repository."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def _bitrate(path: Path, ffprobe: str) -> int:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "format=bit_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip())


def make_degraded(input_dir: Path, output_dir: Path, ffmpeg: str, ffprobe: str) -> dict:
    sources = sorted(path for path in input_dir.iterdir() if path.suffix.lower() == ".mp4")
    if len(sources) != 5:
        raise ValueError(f"Expected exactly five MP4 inputs in {input_dir}, found {len(sources)}.")
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for number, source in enumerate(sources, start=1):
        sample_id = f"sample-{number:02d}"
        for degradation, options in (
            ("D1", ["-crf", "30"]),
            ("D2", ["-crf", "36"]),
            ("D4", ["-b:v", "400k", "-maxrate", "400k", "-bufsize", "800k"]),
        ):
            target = output_dir / f"{sample_id}_{degradation}.mp4"
            _run(
                [
                    ffmpeg,
                    "-v",
                    "error",
                    "-nostdin",
                    "-y",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    *options,
                    "-pix_fmt",
                    "yuv420p",
                    str(target),
                ]
            )
            records.append(
                {
                    "sample": sample_id,
                    "degradation": degradation,
                    "path": str(target),
                    "size_bytes": target.stat().st_size,
                    "video_bitrate_bits_per_second": _bitrate(target, ffprobe),
                }
            )

        target = output_dir / f"{sample_id}_D3.mp4"
        _run(
            [
                ffmpeg,
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-an",
                "-vf",
                "scale=480:854:flags=lanczos,scale=720:1280:flags=bicubic",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                "-pix_fmt",
                "yuv420p",
                str(target),
            ]
        )
        records.append(
            {
                "sample": sample_id,
                "degradation": "D3",
                "path": str(target),
                "size_bytes": target.stat().st_size,
                "video_bitrate_bits_per_second": _bitrate(target, ffprobe),
            }
        )
    report = {"schema_version": 1, "outputs": records}
    (output_dir / "degraded_manifest.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    report = make_degraded(args.input_dir, args.output_dir, args.ffmpeg, args.ffprobe)
    print(f"Created {len(report['outputs'])} degraded videos in {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
