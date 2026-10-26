"""P1e-3b numbered fixture recipes, plus a 30-to-60 fps Before/After pair."""

import os
import subprocess
from pathlib import Path


def main():
    work = Path(__file__).resolve().parents[3]
    folder = work / "scratch/p1e3c2-native"
    folder.mkdir(parents=True, exist_ok=True)
    ffmpeg = work / "cache/mpv-lgpl/ffmpeg/ffmpeg.exe"
    recipes = [
        ("h264-1080p30", "1920x1080", 30, ["-c:v", "h264_nvenc", "-preset", "p1", "-b:v", "3M"]),
        (
            "hevc-main10-1440p60",
            "2560x1440",
            60,
            [
                "-c:v",
                "hevc_nvenc",
                "-preset",
                "p1",
                "-pix_fmt",
                "p010le",
                "-profile:v",
                "main10",
                "-b:v",
                "5M",
            ],
        ),
        (
            "av1-10bit-1440p60",
            "2560x1440",
            60,
            ["-c:v", "av1_nvenc", "-preset", "p1", "-pix_fmt", "p010le", "-b:v", "5M"],
        ),
        (
            "vp9-1080p60",
            "1920x1080",
            60,
            [
                "-c:v",
                "libvpx-vp9",
                "-deadline",
                "realtime",
                "-cpu-used",
                "8",
                "-row-mt",
                "1",
                "-b:v",
                "3M",
            ],
        ),
        ("hevc-rotation", "1920x1080", 30, ["-c:v", "hevc_nvenc", "-preset", "p1", "-b:v", "3M"]),
        ("pair-original", "640x360", 30, ["-c:v", "h264_nvenc", "-preset", "p1", "-b:v", "1M"]),
    ]
    evidence = work / "evidence/VE-P1e-3c2"
    evidence.mkdir(parents=True, exist_ok=True)

    def run(name, arguments):
        target = folder / (name + ".mp4")
        if target.exists():
            return
        with (evidence / (name + "-generate.log")).open("w", encoding="utf-8") as log:
            subprocess.run(
                [
                    str(ffmpeg),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-y",
                    *arguments,
                    str(target),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        print(name, target.stat().st_size, flush=True)

    for name, size, rate, encoding in recipes:
        run(
            name,
            [
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={size}:rate={rate}:duration=65",
                "-vf",
                "drawtext=fontfile='C\\:/Windows/Fonts/consola.ttf':text='frame %{n}':"
                "x=40:y=40:fontsize=60:fontcolor=white:box=1:boxcolor=black",
                *encoding,
                "-an",
            ],
        )
    run(
        "hevc-rotation-display",
        ["-i", str(folder / "hevc-rotation.mp4"), "-c", "copy", "-metadata:s:v:0", "rotate=90"],
    )
    run(
        "pair-enhanced",
        [
            "-i",
            str(folder / "pair-original.mp4"),
            "-vf",
            "fps=60,scale=1280:720,drawtext=fontfile='C\\:/Windows/Fonts/consola.ttf':"
            "text='output %{n}':x=40:y=h-80:fontsize=60:fontcolor=white",
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p1",
            "-b:v",
            "2M",
            "-an",
        ],
    )


if __name__ == "__main__":
    main()
