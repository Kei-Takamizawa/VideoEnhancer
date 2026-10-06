"""Small deterministic media fixtures; external media never enters source control."""

from __future__ import annotations

import subprocess
import uuid
from fractions import Fraction
from pathlib import Path

import pytest

from videoenhancer.config import executable


@pytest.fixture
def ffmpeg_run():
    try:
        ffmpeg = executable("ffmpeg")
        executable("ffprobe")
    except FileNotFoundError as error:
        pytest.skip(str(error))

    def run(*arguments: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *arguments],
            capture_output=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        return result

    return run


@pytest.fixture
def video_factory(tmp_path, ffmpeg_run):
    counter = 0

    def create(
        width: int = 96,
        height: int = 64,
        frames: int = 12,
        rate: str = "30",
        audio: bool = False,
        audio_offset: float = 0.0,
        audio_extra: float = 0.0,
        transfer: str = "bt709",
    ) -> Path:
        nonlocal counter
        target = tmp_path / f"input_{counter}.mp4"
        counter += 1
        arguments = [
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={width}x{height}:rate={rate}",
        ]
        if audio:
            duration = max(0.1, frames / float(Fraction(rate)) - audio_offset + audio_extra)
            arguments += [
                "-itsoffset",
                str(audio_offset),
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:sample_rate=48000:duration={duration}",
            ]
        arguments += [
            "-map",
            "0:v:0",
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "18",
            "-g",
            "4",
            "-bf",
            "0",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-colorspace",
            "bt709",
            "-color_range",
            "tv",
            "-color_primaries",
            "bt709",
            "-color_trc",
            transfer,
            "-bsf:v",
            "h264_metadata=colour_primaries=1:transfer_characteristics="
            + str({"bt709": 1, "smpte2084": 16, "arib-std-b67": 18}[transfer])
            + ":matrix_coefficients=1",
            "-video_track_timescale",
            str(Fraction(rate).numerator),
        ]
        if audio:
            arguments += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "128k"]
        ffmpeg_run(*arguments, str(target))
        return target

    return create


@pytest.fixture
def vfr_video(tmp_path, ffmpeg_run):
    target = tmp_path / "mixed_rate.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=256x144:rate=60",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=0.6",
        "-vf",
        "setpts=if(lt(N\\,12)\\,N/(30*TB)\\,(0.4+(N-12)/60)/TB)",
        "-fps_mode",
        "vfr",
        "-frames:v",
        "24",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-bf",
        "0",
        "-threads",
        "2",
        "-video_track_timescale",
        "60000",
        "-c:a",
        "aac",
        str(target),
    )
    return target


@pytest.fixture
def gpu_available():
    import torch

    if not torch.cuda.is_available():
        pytest.skip("An NVIDIA CUDA GPU is required.")
    pytest.importorskip("PyNvVideoCodec")


@pytest.fixture
def build_manifest():
    from videoenhancer.media.analyze import analyze

    def create(path, backend="cpu", preset="p0-test", short_side="keep", fps="2x", **extra):
        analysis = analyze(path, backend=backend)
        return {
            **analysis,
            "id": uuid.uuid4().hex,
            "input": {"path": str(path)},
            "settings": {
                "backend": backend,
                "preset": preset,
                "short_side": short_side,
                "fps": fps,
                "codec": "h264",
                "lossless": True,
                **extra,
            },
            "segments": [],
        }

    return create
