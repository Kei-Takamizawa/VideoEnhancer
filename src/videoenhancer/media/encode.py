"""NVENC device input and FFmpeg CPU encoding; no silent GPU fallback."""

import importlib
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

import torch

from videoenhancer.config import executable
from videoenhancer.media.color import rgb_to_nv12

NVENC_SETTINGS = {
    "preset": "P7",
    "tuning_info": "high_quality",
    "rc": "constqp",
    "constqp": "18",
    "bf": "0",
}


def packet_bytes(packets: Any) -> bytes:
    if isinstance(packets, dict):
        return bytes(packets["data"])
    if isinstance(packets, list) and (not packets or isinstance(packets[0], dict)):
        return b"".join(bytes(packet["data"]) for packet in packets)
    return bytes(packets)


def color_flags(media: dict[str, Any]) -> list[str]:
    matrix = "smpte170m" if media["color_matrix"] == "bt601" else "bt709"
    primaries = media.get("color_primaries", "bt709")
    transfer = media.get("color_transfer", "bt709")
    return [
        "-colorspace",
        matrix,
        "-color_range",
        "tv",
        "-color_primaries",
        "bt709" if primaries == "unknown" else primaries,
        "-color_trc",
        "bt709" if transfer == "unknown" else transfer,
    ]


def color_bsf(media: dict[str, Any], codec: str) -> str:
    primaries = {
        "bt709": 1,
        "bt470m": 4,
        "bt470bg": 5,
        "smpte170m": 6,
        "smpte240m": 7,
        "film": 8,
        "bt2020": 9,
        "smpte428": 10,
        "smpte431": 11,
        "smpte432": 12,
    }
    transfers = {
        "bt709": 1,
        "gamma22": 4,
        "gamma28": 5,
        "smpte170m": 6,
        "smpte240m": 7,
        "linear": 8,
        "log": 9,
        "log_sqrt": 10,
        "iec61966-2-4": 11,
        "bt1361e": 12,
        "iec61966-2-1": 13,
        "bt2020-10": 14,
        "bt2020-12": 15,
    }
    matrix = 6 if media["color_matrix"] == "bt601" else 1
    p = primaries.get(media.get("color_primaries", "unknown"), 2)
    t = transfers.get(media.get("color_transfer", "unknown"), 2)
    name = {"hevc": "hevc_metadata", "h264": "h264_metadata", "av1": "av1_metadata"}[codec]
    spelling = "color_primaries" if codec == "av1" else "colour_primaries"
    result = f"{name}={spelling}={p}:transfer_characteristics={t}:matrix_coefficients={matrix}"
    if codec != "av1":
        result += ":video_full_range_flag=0"
    else:
        result += ":color_range=tv"
    return result


class Encoder:
    def __init__(
        self,
        path: Path,
        width: int,
        height: int,
        rate: Fraction,
        codec: str,
        backend: str,
        media: dict[str, Any],
        lossless: bool = False,
    ):
        self.path, self.codec, self.backend, self.media, self.rate = (
            path,
            codec,
            backend,
            media,
            rate,
        )
        self.bit_depth = 8 if codec == "h264" else 10
        self.process: subprocess.Popen | None = None
        self.encoder: Any = None
        self.stream: Any = None
        self.raw_path = path.with_suffix(
            ".raw." + {"hevc": "hevc", "h264": "h264", "av1": "ivf"}[codec]
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if backend == "cuda":
            nvc: Any = importlib.import_module("PyNvVideoCodec")

            options: dict[str, Any] = dict(NVENC_SETTINGS)
            if lossless:
                options.update(tuning_info="lossless", constqp="0")
            options.update(
                codec=codec,
                fps=str(round(float(rate))),
                gop=str(max(1, round(float(rate) * 2))),
                profile="high" if codec == "h264" else "main10" if codec == "hevc" else "main",
            )
            self.encoder = nvc.CreateEncoder(
                width, height, "NV12" if self.bit_depth == 8 else "P010", True, **options
            )
            self.stream = self.raw_path.open("wb")
        else:
            implementation = {"hevc": "libx265", "h264": "libx264", "av1": "libaom-av1"}[codec]
            command = [
                executable("ffmpeg"),
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "nv12" if self.bit_depth == 8 else "p010le",
                "-s:v",
                f"{width}x{height}",
                "-r",
                str(rate),
                "-i",
                "pipe:0",
                "-an",
                "-c:v",
                implementation,
                "-threads",
                "2",
                "-pix_fmt",
                "yuv420p" if self.bit_depth == 8 else "yuv420p10le",
            ]
            if codec == "hevc":
                command += [
                    "-preset",
                    "fast",
                    "-x265-params",
                    "pools=2:frame-threads=1:log-level=error:"
                    + ("lossless=1" if lossless else "crf=18"),
                ]
            elif codec == "h264":
                command += [
                    "-preset",
                    "fast",
                    "-crf",
                    "0" if lossless else "18",
                    "-x264-params",
                    "threads=1:lookahead-threads=1",
                ]
            else:
                command += ["-cpu-used", "6", "-crf", "0" if lossless else "18", "-b:v", "0"]
            command += [
                *color_flags(media),
                "-bsf:v",
                color_bsf(media, codec),
                "-video_track_timescale",
                str(rate.numerator),
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(path),
            ]
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, frame: torch.Tensor) -> None:
        surface = rgb_to_nv12(frame, self.media["color_matrix"], self.bit_depth)
        if self.backend == "cuda":
            stream = torch.cuda.current_stream()
            stream.synchronize()
            # Keep model/color work on CUDA, then hand NVENC an owned host
            # buffer. PyNvVideoCodec does not document when its encoder stops
            # reading CUDA Array Interface input surfaces, and rare post-encode
            # artifacts were observed with that path.
            host_surface = surface.cpu().contiguous()
            if host_surface.dtype == torch.uint16:
                host_surface = host_surface.view(torch.uint8).reshape(-1)
            packets = self.encoder.Encode(host_surface.numpy())
            self.stream.write(packet_bytes(packets))
        else:
            assert self.process is not None and self.process.stdin is not None
            try:
                self.process.stdin.write(surface.numpy().tobytes())
            except BrokenPipeError:
                stderr = (
                    self.process.stderr.read().decode(errors="replace")
                    if self.process.stderr
                    else ""
                )
                raise RuntimeError(
                    f"CPU encode failed: {stderr}. Check FFmpeg codec support."
                ) from None

    def finish(self) -> None:
        if self.backend == "cuda":
            self.stream.write(packet_bytes(self.encoder.EndEncode()))
            self.stream.close()
            self.encoder = None
            metadata = color_bsf(self.media, self.codec)
            command = [
                executable("ffmpeg"),
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-r",
                str(self.rate),
                "-i",
                str(self.raw_path),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-bsf:v",
                metadata,
                *color_flags(self.media),
                "-video_track_timescale",
                str(self.rate.numerator),
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(self.path),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(
                    f"GPU segment mux failed: {result.stderr}. "
                    "Check FFmpeg bitstream-filter support."
                )
            self.raw_path.unlink(missing_ok=True)
        elif self.process:
            assert self.process.stdin is not None
            self.process.stdin.close()
            self.process.stdin = None
            _, stderr = self.process.communicate(timeout=60)
            if self.process.returncode:
                raise RuntimeError(
                    f"CPU encode failed: {stderr.decode(errors='replace')}. "
                    "Check FFmpeg codec support."
                )

    def abort(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.communicate(timeout=10)
        if self.stream and not self.stream.closed:
            self.stream.close()
        self.encoder = None
        self.path.unlink(missing_ok=True)
        self.raw_path.unlink(missing_ok=True)
