"""Contained synthetic G5 fixtures; recipes are recorded outside the checkout."""

import hashlib
import json
import subprocess
from pathlib import Path

from videoenhancer.config import executable


def main():
    work = Path(__file__).resolve().parents[3]
    scratch = work / "scratch/p1e3d1"
    evidence = work / "evidence/VE-P1e-3d1"
    recipes = []
    for name, size in (("landscape-30", "1920x1080"), ("portrait-30", "1080x1920")):
        recipes.append(
            (
                name,
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc2=size={size}:rate=30:duration=30",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:sample_rate=48000:duration=30",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-shortest",
                ],
            )
        )
    recipes.extend(
        [
            (
                "hard-cut-6",
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "color=black:size=512x288:rate=30:duration=3",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=white:size=512x288:rate=30:duration=3",
                    "-filter_complex",
                    "[0:v][1:v]concat=n=2:v=1:a=0[v]",
                    "-map",
                    "[v]",
                ],
            ),
            (
                "vfr-6",
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=512x288:rate=30:duration=6",
                    "-vf",
                    "select=not(eq(mod(n\\,5)\\,1))",
                    "-fps_mode",
                    "vfr",
                ],
            ),
        ]
    )
    rows = []
    for name, arguments in recipes:
        target = scratch / f"{name}.mp4"
        command = [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            *arguments,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-b:v",
            "4M",
            "-maxrate",
            "4M",
            "-bufsize",
            "8M",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ]
        if target.exists():
            raise FileExistsError(f"Refusing to replace fixture: {target}")
        subprocess.run(
            command, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        rows.append(
            dict(
                name=name,
                command=command,
                bytes=target.stat().st_size,
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            )
        )
        (evidence / "g5-fixtures.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(name, rows[-1]["bytes"], flush=True)


if __name__ == "__main__":
    main()
