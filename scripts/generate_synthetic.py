"""Generate small synthetic fixtures or a two-hour, looped P0 soak input."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _make_fixture(ffmpeg: str, out: Path, kind: str, backend: str) -> None:
    nvenc = backend == "nvenc"
    h264 = (
        ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "hq"]
        if nvenc
        else ["-c:v", "libx264", "-preset", "ultrafast"]
    )
    if kind == "vfr":
        source = "testsrc2=size=720x1280:rate=60,noise=alls=4:allf=t+u"
        video_options = ["-vf", "select='if(lt(t,6),not(mod(n,2)),1)'", "-fps_mode", "vfr"]
        codec = h264
        duration = "12"
    elif kind == "rotation":
        source = "testsrc2=size=1280x720:rate=30,drawbox=x=0:y=0:w=iw:h=ih:color=black:t=2"
        video_options = []
        codec = h264
        duration = "12"
    elif kind == "hdr":
        source = "testsrc2=size=720x1280:rate=30"
        video_options = [
            "-vf",
            "format=yuv420p10le",
            "-color_primaries",
            "bt2020",
            "-color_trc",
            "smpte2084",
            "-colorspace",
            "bt2020nc",
        ]
        codec = (
            ["-c:v", "hevc_nvenc", "-preset", "p1", "-profile:v", "main10"]
            if nvenc
            else [
                "-c:v",
                "libx265",
                "-preset",
                "ultrafast",
                "-threads",
                "2",
                "-x265-params",
                "pools=2:frame-threads=1",
            ]
        )
        duration = "8"
    else:
        source = (
            "testsrc2=size=720x1280:rate=30,"
            "drawbox=x=0:y=0:w=iw:h=ih:color=red:t=fill:enable='gte(t,4)*lt(t,5)'"
        )
        video_options = []
        codec = h264
        duration = "12"
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        source,
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000",
        *video_options,
        "-t",
        duration,
        *codec,
        "-pix_fmt",
        "p010le" if kind == "hdr" else "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-y",
        str(out),
    ]
    _run(command)
    if kind == "rotation":
        rotated = out.with_name(out.stem + "_rotated.mp4")
        _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-display_rotation",
                "90",
                "-i",
                str(out),
                "-map",
                "0",
                "-c",
                "copy",
                "-y",
                str(rotated),
            ]
        )
        rotated.replace(out)


def _make_soak(ffmpeg: str, out: Path, backend: str) -> None:
    base = out.with_name("soak_base_60s.mp4")
    source = (
        "testsrc2=size=720x1280:rate=30000/1001,"
        "noise=alls=4:allf=t+u,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=red:t=fill:enable='between(t,15,16)',"
        "drawbox=x=0:y=0:w=iw:h=ih:color=blue:t=fill:enable='between(t,37,38)'"
    )
    video_encoder = (
        ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "hq"]
        if backend == "nvenc"
        else ["-c:v", "libx264", "-preset", "ultrafast", "-threads", "2"]
    )
    _run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            source,
            "-frames:v",
            "1800",
            *video_encoder,
            "-pix_fmt",
            "yuv420p",
            "-an",
            "-y",
            str(base),
        ]
    )
    # 60.06s at 30000/1001 is 1800 frames. Copy 119 repeats and cap to exactly
    # 215,784 frames (7,199.9932 seconds) without re-encoding the two-hour file.
    _run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-stream_loop",
            "-1",
            "-i",
            str(base),
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-frames:v",
            "215784",
            "-t",
            "7199.9928",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-y",
            str(out),
        ]
    )
    base.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".tmp/synthetic"))
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--backend", choices=("auto", "cpu", "nvenc"), default="auto")
    parser.add_argument("--soak", action="store_true", help="also create the two-hour soak input")
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error("ffmpeg was not found; set --ffmpeg or add it to PATH")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    backend = "nvenc" if args.backend == "nvenc" else "cpu"
    if args.backend == "auto":
        probe = subprocess.run(
            [
                args.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=size=256x144",
                "-frames:v",
                "1",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        backend = "nvenc" if probe.returncode == 0 else "cpu"
    for kind in ("vfr", "rotation", "hdr", "cuts"):
        path = args.output_dir / f"synthetic_{kind}.mp4"
        _make_fixture(args.ffmpeg, path, kind, backend)
        print(path.resolve())
    if args.soak:
        path = args.output_dir / "soak_2h.mp4"
        _make_soak(args.ffmpeg, path, backend)
        print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
