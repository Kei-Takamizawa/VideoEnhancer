"""Overlap the unchanged NVENC-to-H.264 preview transcode with model work."""

import subprocess
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.media.encode import color_bsf, color_flags


class PreviewTranscode:
    def __init__(self, target: Path, rate: Fraction, media: dict[str, Any]) -> None:
        self.started = time.perf_counter()
        self.packet_write_seconds = 0.0
        self.mux_log = target.with_suffix(".mux.log").open("wb")
        self.encode_log = target.with_suffix(".encode.log").open("wb")
        self.mux: Any = None
        self.encoder: Any = None
        try:
            self.mux = proc.Popen(
                [
                    executable("ffmpeg"),
                    "-v",
                    "error",
                    "-nostdin",
                    "-f",
                    "h264",
                    "-probesize",
                    "32",
                    "-analyzeduration",
                    "1",
                    "-r",
                    str(rate),
                    "-i",
                    "pipe:0",
                    "-map",
                    "0:v:0",
                    "-c:v",
                    "copy",
                    "-bsf:v",
                    color_bsf(media, "h264"),
                    *color_flags(media),
                    "-video_track_timescale",
                    str(rate.numerator),
                    "-movflags",
                    "+frag_every_frame+empty_moov",
                    "-f",
                    "mp4",
                    "pipe:1",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.mux_log,
            )
            self.encoder = proc.Popen(
                [
                    executable("ffmpeg"),
                    "-v",
                    "error",
                    "-nostdin",
                    "-probesize",
                    "32",
                    "-analyzeduration",
                    "1",
                    "-r",
                    str(rate),
                    "-i",
                    "pipe:0",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "16",
                    "-pix_fmt",
                    "yuv420p",
                    "-threads",
                    "2",
                    str(target),
                ],
                stdin=self.mux.stdout,
                stdout=subprocess.PIPE,
                stderr=self.encode_log,
            )
            self.mux.stdout.close()
            self.mux.stdout = None
        except BaseException:
            self.abort()
            raise

    def __call__(self, packet: bytes | None) -> None:
        began = time.perf_counter()
        if self.mux.stdin is None:
            if packet is None:
                return
            raise RuntimeError("The preview packet stream has already ended")
        if packet is None:
            self.mux.stdin.close()
            self.mux.stdin = None
        elif packet:
            self.mux.stdin.write(packet)
        self.packet_write_seconds += time.perf_counter() - began

    def finish(self) -> float:
        self(None)
        self.mux.communicate(timeout=120)
        self.encoder.communicate(timeout=120)
        if self.mux.returncode or self.encoder.returncode:
            raise RuntimeError("The streamed preview transcode failed; see its isolated logs")
        return time.perf_counter() - self.started

    def abort(self) -> None:
        for process in (self.mux, self.encoder):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=2)
        self.mux_log.close()
        self.encode_log.close()
