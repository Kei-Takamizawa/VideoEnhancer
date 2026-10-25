"""Generate numbered synthetic clips and collect playback logs, not benchmarks.

Run with the repository's Python after dot-sourcing local-env.ps1. This script
never automates UI input or captures the desktop. Profiles and media are scratch
artifacts; the operator must close this cycle before cleaning those artifacts.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approaches", nargs="+", choices=["B1", "B2"], default=["B1", "B2"])
    parser.add_argument("--rotation-only", action="store_true")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--dll", type=Path)
    parser.add_argument("--label", default="smoke")
    parser.add_argument("--skip-generate", action="store_true")
    args = parser.parse_args()
    if not args.label.replace("-", "").replace("_", "").isalnum():
        parser.error("Label must be a safe directory name")
    work = Path(__file__).resolve().parents[3]
    cache = work / "cache/mpv-lgpl"
    scratch = work / "scratch/mpv-spike"
    evidence = work / "evidence/VE-P1e-3c1"
    if args.dll:
        evidence /= args.label
    if args.rotation_only:
        evidence /= "rotation-fixed"
    if args.generate_only:
        evidence = work / "evidence/VE-P1e-3c1/fixtures"
    scratch.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    ffmpeg = cache / "ffmpeg/ffmpeg.exe"
    executable = cache / "spike-target/debug/mpv-embedding-spike.exe"
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
    ]
    results = []
    for name, size, fps, encoding in recipes:
        if args.rotation_only and name != "hevc-rotation":
            continue
        target = scratch / f"{name}.mp4"
        command = [
            str(ffmpeg),
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate={fps}:duration=65",
            "-vf",
            "drawtext=fontfile='C\\:/Windows/Fonts/consola.ttf':text='frame %{n}':"
            "x=40:y=40:fontsize=80:fontcolor=white:box=1:boxcolor=black,"
            "drawtext=fontfile='C\\:/Windows/Fonts/consola.ttf':text='frame %{n}':"
            "x=40:y=h-110:fontsize=80:fontcolor=white:shadowcolor=black:shadowx=1:shadowy=1",
            *encoding,
            "-an",
            str(target),
        ]
        with (evidence / f"{name}-generate.log").open("w", encoding="utf-8") as log:
            run = (
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
                if not args.skip_generate
                else None
            )
        results.append(
            {
                "step": "generate",
                "clip": name,
                "command": command,
                "returncode": run.returncode if run else None,
            }
        )
        if run and run.returncode:
            continue
        if name == "hevc-rotation":
            rotated = scratch / "hevc-rotation-display.mp4"
            command = [
                str(ffmpeg),
                "-hide_banner",
                "-y",
                "-display_rotation",
                "90",
                "-i",
                str(target),
                "-c",
                "copy",
                str(rotated),
            ]
            if not args.skip_generate:
                with (evidence / "rotation-remux.log").open("w", encoding="utf-8") as log:
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            target = rotated
        if args.skip_generate and not target.is_file():
            raise FileNotFoundError(target)
        for approach in [] if args.generate_only else args.approaches:
            profile = scratch / f"profile-{approach}"
            profile.mkdir(exist_ok=True)
            env = os.environ.copy()
            env["VE_MPV_SPIKE_AUTOCLOSE_MS"] = "5000"
            command = [
                str(executable),
                approach,
                str(args.dll.resolve() if args.dll else cache / "libmpv-2.dll"),
                str(target),
                str(profile),
            ]
            with (
                (evidence / f"{name}-{approach}.jsonl").open("w", encoding="utf-8") as out,
                (evidence / f"{name}-{approach}.stderr.log").open("w", encoding="utf-8") as err,
            ):
                run = subprocess.run(command, stdout=out, stderr=err, env=env, timeout=30)
            results.append(
                {
                    "step": "playback_smoke",
                    "clip": name,
                    "approach": approach,
                    "returncode": run.returncode,
                }
            )
            rows = [
                json.loads(line)
                for line in (evidence / f"{name}-{approach}.jsonl").read_text().splitlines()
            ]
            telemetry = [r["properties"] for r in rows if r.get("event") == "telemetry"]
            results[-1]["d3d11va_playback"] = (
                bool(telemetry)
                and all(p.get("hwdec-current") == "d3d11va" for p in telemetry)
                and any(float(p.get("time-pos") or 0) > 0 for p in telemetry)
            )
            print(json.dumps(results[-1]), flush=True)
        (evidence / "smoke-results.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8"
        )
    if any(
        r.get("returncode") not in (None, 0)
        or (r["step"] == "playback_smoke" and not r["d3d11va_playback"])
        for r in results
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
