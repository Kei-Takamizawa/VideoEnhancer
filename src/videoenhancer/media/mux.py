"""Stream-copy final assembly with original audio and atomic publication."""

import os
import subprocess
import uuid
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

from videoenhancer.config import executable
from videoenhancer.media.probe import probe
from videoenhancer.media.timing import output_rate

MP4_AUDIO_CODECS = {"aac", "mp3", "ac3", "eac3", "alac"}


def _audio_duration_matches(original: dict[str, Any], actual: dict[str, Any]) -> bool:
    delta = original["duration"] - actual["duration"]
    if abs(delta) <= 0.020:
        return True
    sample_rate = int(original.get("sample_rate", 0))
    initial_padding = int(original.get("initial_padding", 0))
    if sample_rate <= 0 or initial_padding <= 0:
        return False
    # Some AAC inputs include encoder priming in the probed track duration.
    # Stream-copy muxing preserves the packets while MP4 presents the audible
    # duration, which is shorter by exactly that priming interval.
    return abs(delta - initial_padding / sample_rate) <= 0.020


def _run(command: list[str], abort: Callable[[], bool] | None, *, cwd: Path | None = None) -> None:
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=cwd)
    try:
        while True:
            try:
                _, error = process.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if abort and abort():
                    raise InterruptedError(
                        "Final assembly was interrupted. Resume the job to retry."
                    ) from None
        if process.returncode:
            raise RuntimeError(
                f"Final assembly failed: {error.decode(errors='replace')}. "
                "Keep the job and retry after checking FFmpeg."
            )
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def assemble(
    manifest: dict[str, Any], job_dir: Path, abort: Callable[[], bool] | None = None
) -> Path:
    output = Path(manifest.get("output", manifest.get("output_path", "")))
    if not str(output) or output.resolve() == Path(manifest["input"]["path"]).resolve():
        raise ValueError("Choose an output path different from the input video.")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}. Choose another output path.")
    output.parent.mkdir(parents=True, exist_ok=True)
    listing = job_dir / "concat.txt"
    lines = []
    for segment in manifest["segments"]:
        name = segment.get("file", segment.get("output", f"seg_{segment['index']:05d}.mp4"))
        path = Path(name)
        if not path.is_absolute():
            path = job_dir / path
        if not path.is_file():
            raise FileNotFoundError(
                f"Segment {segment['index']} is missing: {path}. Resume to regenerate it."
            )
        escaped = path.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'\n")
    listing.write_text("".join(lines), encoding="utf-8")
    joined = job_dir / "assembled.tmp.mp4"
    temporary = output.with_name(output.stem + f".{uuid.uuid4().hex}.tmp.mp4")
    ffmpeg = executable("ffmpeg")
    try:
        _run(
            [
                ffmpeg,
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-map",
                "0:v:0",
                "-c",
                "copy",
                "-video_track_timescale",
                str(output_rate(manifest["settings"], manifest["media"]).numerator),
                str(joined),
            ],
            abort,
        )
        rate = output_rate(manifest["settings"], manifest["media"])
        expected_duration = float(
            Fraction(len(manifest["cfr_map"])) * rate / Fraction(manifest["media"]["cfr_fps"])
        )
        audio_end = max(
            (
                audio["start_offset"] + audio["duration"]
                for audio in manifest["media"].get("audio_streams", [])
            ),
            default=0.0,
        )
        mux_duration = max(expected_duration, audio_end)
        command = [
            ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-copyts",
            "-i",
            str(joined),
            "-itsoffset",
            str(-manifest["media"].get("start_time", 0)),
            "-i",
            manifest["input"]["path"],
            "-map",
            "0:v:0",
            "-map",
            "1:a?",
            "-map_metadata",
            "1",
            "-map_chapters",
            "1",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-t",
            f"{mux_duration:.9f}",
        ]
        for audio_index, audio in enumerate(manifest["media"].get("audio_streams", [])):
            if audio["codec"] not in MP4_AUDIO_CODECS:
                command += [f"-c:a:{audio_index}", "aac", f"-b:a:{audio_index}", "256k"]
        command += [
            "-metadata:s:v:0",
            "rotate=0",
            "-avoid_negative_ts",
            "disabled",
            "-video_track_timescale",
            str(output_rate(manifest["settings"], manifest["media"]).numerator),
            "-movflags",
            "+faststart",
            str(temporary),
        ]
        _run(command, abort)
        result = probe(temporary)
        expected = int(
            Fraction(len(manifest["cfr_map"])) * rate / Fraction(manifest["media"]["cfr_fps"])
        )
        expected_duration = float(Fraction(expected) / rate)
        if result.frame_count != expected or abs(result.duration - expected_duration) > float(
            1 / rate
        ):
            raise RuntimeError(
                f"Assembly validation failed: {result.frame_count}/{expected} frames, "
                f"{result.duration:.6f}/{expected_duration:.6f} s. "
                "Resume to regenerate invalid segments."
            )
        if result.rotation:
            raise RuntimeError(
                "Assembly retained a rotation flag. Keep segments and report this input."
            )
        for original, actual in zip(
            manifest["media"].get("audio_streams", []), result.audio_streams, strict=True
        ):
            if abs(original["start_offset"] - actual["start_offset"]) > 0.020:
                raise RuntimeError(
                    f"Audio timing mismatch: {original['start_offset']:.4f}/"
                    f"{actual['start_offset']:.4f} s offset. Keep segments and inspect "
                    "source audio."
                )
            if not _audio_duration_matches(original, actual):
                raise RuntimeError(
                    f"Audio duration changed from {original['duration']:.4f} to "
                    f"{actual['duration']:.4f} s. Keep segments and inspect source audio."
                )
        if abort and abort():
            raise InterruptedError("Final assembly was interrupted.")
        # Both operations refuse an output created while assembly was in progress.
        # Windows rename also works on external drives without hard-link support.
        if os.name == "nt":
            os.rename(temporary, output)
        else:
            os.link(temporary, output)
        return output
    finally:
        temporary.unlink(missing_ok=True)
        joined.unlink(missing_ok=True)
        listing.unlink(missing_ok=True)
