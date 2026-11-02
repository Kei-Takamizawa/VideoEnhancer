"""Create synthetic faststart MP4s; all generated files stay in scratch."""

import argparse
import json
import math
import subprocess
import time
from pathlib import Path

from server import WORK


def generate(home, ffmpeg):
    home = home.resolve()
    if not home.is_relative_to(WORK / "scratch"):
        raise ValueError("Media must be under work/scratch")
    media = home / "media"
    media.mkdir(parents=True, exist_ok=True)
    recipes = {
        "h264": ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20"],
        "hevc": [
            "-c:v",
            "libx265",
            "-preset",
            "ultrafast",
            "-crf",
            "25",
            "-tag:v",
            "hvc1",
            "-x265-params",
            "pools=2:frame-threads=2:log-level=error",
        ],
        "av1": [
            "-c:v",
            "libaom-av1",
            "-usage",
            "realtime",
            "-cpu-used",
            "8",
            "-crf",
            "35",
            "-row-mt",
            "1",
        ],
    }
    measurements = []
    for codec, options in recipes.items():
        path = media / f"{codec}.mp4"
        start = time.perf_counter()
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=1920x1080:rate=60",
            "-t",
            "6",
            "-an",
            "-threads",
            "2",
            *options,
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path),
        ]
        subprocess.run(command, check=True)
        measurements.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "generation_s": time.perf_counter() - start,
                "dimensions": "1920x1080",
                "fps": 60,
                "duration_s": 6,
                "command": command[:-1] + [path.name],
            }
        )
    source = media / "h264.mp4"
    for name, size in [("50MB", 50_000_000), ("500MB", 500_000_000), ("1GB", 1_000_000_000)]:
        path = media / (name + ".mp4")
        duration = math.ceil(size / source.stat().st_size * 6)
        start = time.perf_counter()
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-stream_loop",
                "-1",
                "-i",
                str(source),
                "-t",
                str(duration),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(path),
            ],
            check=True,
        )
        measurements.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "duration_s": duration,
                "generation_s": time.perf_counter() - start,
            }
        )
    (home / "sample-metadata.json").write_text(json.dumps(measurements, indent=2))
    print(json.dumps(measurements, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=WORK / "scratch" / "ipad-spike")
    parser.add_argument(
        "--ffmpeg", help="Installed FFmpeg, otherwise use spike-only imageio-ffmpeg"
    )
    args = parser.parse_args()
    if not args.ffmpeg:
        import imageio_ffmpeg

        args.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    generate(args.home, args.ffmpeg)
