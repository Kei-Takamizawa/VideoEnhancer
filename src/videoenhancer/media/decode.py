"""Indexed NVDEC and deterministic FFmpeg CPU decoding."""

import importlib
import subprocess
from collections.abc import Callable, Iterator
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.media.color import nv12_to_rgb

SMART_APP_CONTROL_MESSAGE = (
    "PyNvVideoCodec could not start. Windows Smart App Control may have blocked its "
    "unsigned NVIDIA video component (VersionCheck.cp312-win_amd64.pyd). See "
    "docs/TROUBLESHOOTING.md for details and options."
)


def _load_pynvcodec() -> Any:
    try:
        return importlib.import_module("PyNvVideoCodec")
    except (ImportError, OSError) as exc:
        # Windows returns ERROR_INVALID_IMAGE_HASH (577) when policy blocks an
        # image. ImportError also covers a blocked extension reported by Python.
        winerror = getattr(exc, "winerror", None)
        missing_optional_package = (
            isinstance(exc, ModuleNotFoundError) and exc.name == "PyNvVideoCodec"
        )
        if not missing_optional_package and (winerror == 577 or isinstance(exc, ImportError)):
            raise RuntimeError(f"{SMART_APP_CONTROL_MESSAGE} Details: {exc}") from None
        raise


def choose_backend(requested: str = "auto") -> str:
    if requested == "cpu":
        return "cpu"
    if torch.cuda.is_available():
        try:
            _load_pynvcodec()
        except ModuleNotFoundError:
            if requested == "cuda":
                raise RuntimeError(
                    "Install the gpu extra (uv sync --extra gpu) for NVDEC/NVENC."
                ) from None
        else:
            return "cuda"
    if requested == "cuda":
        raise RuntimeError("CUDA is unavailable. Check the NVIDIA driver or use --backend cpu.")
    return "cpu"


def read_exact(stream: Any, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


def validate_pixel_format(media: dict[str, Any]) -> None:
    if media.get("pixel_format", "yuv420p") not in {
        "yuv420p",
        "yuvj420p",
        "yuv420p10le",
        "yuv420p12le",
        "nv12",
        "p010le",
        "p016le",
    }:
        raise ValueError(
            f"Unsupported decoded pixel format {media['pixel_format']}. "
            "Convert the source to 4:2:0 SDR before processing."
        )


class IndexedDecoder:
    def __init__(
        self,
        path: str | Path,
        media: dict[str, Any],
        backend: str,
        manifest: dict[str, Any] | None = None,
    ):
        self.path, self.media, self.backend = str(path), media, backend
        self.manifest = manifest or {}
        validate_pixel_format(media)
        self.decoder: Any = None
        if backend == "cuda":
            nvc: Any = _load_pynvcodec()

            self.decoder = nvc.SimpleDecoder(
                self.path,
                gpu_id=0,
                use_device_memory=True,
                output_color_type=nvc.OutputColorType.NATIVE,
                decoder_cache_size=1,
                need_scanned_stream_metadata=True,
            )

    def _convert(self, frame: torch.Tensor) -> torch.Tensor:
        rgb = nv12_to_rgb(
            frame,
            self.media["width"],
            self.media["height"],
            self.media["color_matrix"],
            self.media["color_range"] == "pc",
            self.media["bit_depth"],
        )
        rotation = self.media.get("rotation", 0)
        if rotation:
            # ffprobe display-matrix rotation is counterclockwise.
            rgb = torch.rot90(rgb, rotation // 90, (-2, -1))
        display_shape = (self.media["display_height"], self.media["display_width"])
        if rgb.shape[-2:] != display_shape:
            rgb = F.interpolate(
                rgb.float()[None],
                size=display_shape,
                mode="bicubic",
                align_corners=False,
                antialias=True,
            )[0].to(torch.float16)
        return rgb.contiguous()

    def frames(self, indices: list[int], abort: Callable[[], bool]) -> Iterator[torch.Tensor]:
        if self.backend == "cuda":
            for index in indices:
                if abort():
                    raise InterruptedError("The segment was interrupted.")
                yield self._convert(torch.from_dlpack(self.decoder[index]))
            return
        if not indices:
            return
        first, last = min(indices), max(indices)
        pts = self.manifest.get("source_pts", [])
        keyframes = self.manifest.get("keyframes", [])
        previous = max((k["index"] for k in keyframes if k["index"] <= first), default=0)
        seek = Fraction(pts[previous]) if pts else None
        width, height = self.media["width"], self.media["height"]
        depth = self.media["bit_depth"]
        command = [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            "-threads",
            "2",
            "-noautorotate",
        ]
        if seek is not None:
            # FFmpeg rounds -ss to microseconds. Floor the absolute keyframe
            # timestamp so accurate seeking never discards that keyframe.
            micros = seek * 1_000_000
            seek_microseconds = micros.numerator // micros.denominator
            command += [
                "-seek_timestamp",
                "1",
                "-ss",
                f"{seek_microseconds / 1_000_000:.6f}",
            ]
        command += [
            "-i",
            self.path,
            "-map",
            "0:v:0",
            "-an",
            "-sn",
            "-vf",
            f"select=between(n\\,{first - previous}\\,{last - previous})",
            "-fps_mode",
            "passthrough",
            "-frames:v",
            str(last - first + 1),
            "-pix_fmt",
            "p010le" if depth > 8 else "nv12",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
        process = proc.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdout is not None
        size = width * height * 3 // 2 * (2 if depth > 8 else 1)
        current_index = first - 1
        current: torch.Tensor | None = None
        try:
            for index in indices:
                if abort():
                    raise InterruptedError("The segment was interrupted.")
                while current_index < index:
                    raw = read_exact(process.stdout, size)
                    if len(raw) != size:
                        stderr = proc.stderr_text(process)
                        raise RuntimeError(
                            f"Decode failed at input frame {index}: {stderr}. Re-probe the input."
                        )
                    current_index += 1
                    current = self._convert(
                        torch.from_numpy(
                            np.frombuffer(raw, dtype=np.uint16 if depth > 8 else np.uint8)
                            .copy()
                            .reshape(height * 3 // 2, width)
                        )
                    )
                assert current is not None
                yield current
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)

    def close(self) -> None:
        self.decoder = None
