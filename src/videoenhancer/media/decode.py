"""Indexed NVDEC and deterministic FFmpeg CPU decoding."""

import importlib
import itertools
import subprocess
from collections.abc import Callable, Iterator
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

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


class TimestampMismatch(ValueError):
    """A decoded presentation label disagrees with the analysed timeline."""


class TimestampSequence:
    def __init__(self, pts: list[str]):
        self.pts = [Fraction(value) for value in pts]
        self.positions = {stamp: index for index, stamp in enumerate(self.pts)}
        self.next_index: int | None = None

    def accept(self, stamp: Fraction) -> int:
        index = self.positions.get(stamp) if self.next_index is None else self.next_index
        if index is None or index >= len(self.pts) or self.pts[index] != stamp:
            expected = (
                self.pts[index]
                if index is not None and index < len(self.pts)
                else "a known timestamp"
            )
            raise TimestampMismatch(
                f"Decoded timestamp {stamp} at frame {self.next_index or 0} "
                f"does not match {expected}."
            )
        self.next_index = index + 1
        return index


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


def software_decoder_support() -> dict[str, bool]:
    result = proc.run(
        [executable("ffmpeg"), "-hide_banner", "-decoders"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    names = {
        fields[1]
        for line in result.stdout.splitlines()
        if len(fields := line.split()) >= 2 and fields[0].startswith("V")
    }
    return {
        "vp9": bool(names & {"vp9", "libvpx-vp9"}),
        "av1": bool(names & {"av1", "libdav1d", "libaom-av1"}),
    }


def read_exact(stream: Any, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


def validate_pixel_format(media: dict[str, Any]) -> None:
    from videoenhancer.media.admission import color_warning

    if reason := color_warning(media):
        raise ValueError(reason)
    if media.get("pixel_format", "yuv420p") not in {
        "yuv420p",
        "yuvj420p",
        "yuv420p10le",
        "nv12",
        "p010le",
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
        self.demuxer: Any = None
        self._cuda_used = False
        if backend == "cuda" and self.manifest.get("decoder", "nvdec") == "nvdec":
            self._open_cuda()

    def _open_cuda(self) -> None:
        nvc: Any = _load_pynvcodec()
        self.demuxer = nvc.CreateDemuxer(filename=self.path)
        self.decoder = nvc.CreateDecoder(
            gpuid=0,
            codec=self.demuxer.GetNvCodecId(),
            usedevicememory=True,
            outputColorType=nvc.OutputColorType.NATIVE,
        )

    def _decoded_packets(self, packets: Iterator[Any], abort: Callable[[], bool]) -> Iterator[Any]:
        for compressed in packets:
            if abort():
                raise InterruptedError("The segment was interrupted.")
            yield from self.decoder.Decode(compressed)
        flush: Any = getattr(self.decoder, "Flush", None)
        if callable(flush):
            yield from cast(Any, flush)()

    def verify_timestamps(
        self,
        pts: list[str],
        observer: Callable[[Any], None] | None = None,
        abort: Callable[[], bool] | None = None,
    ) -> None:
        """Scan the entire native stream, including the EOF packet and final frame."""
        base = Fraction(self.demuxer.GetTimebaseNum(), self.demuxer.GetTimebaseDen())
        sequence = TimestampSequence(pts)
        count = 0
        for frame in self._decoded_packets(iter(self.demuxer), abort or (lambda: False)):
            stamp = Fraction(frame.getPTS()) * base
            if sequence.accept(stamp) != count:
                raise TimestampMismatch(
                    f"NVDEC starts at frame {(sequence.next_index or 1) - 1}, expected 0."
                )
            if observer is not None:
                observer(frame)
            count += 1
        if count != len(pts):
            raise TimestampMismatch(f"NVDEC ended after {count} frames; expected {len(pts)}.")

    def _cuda_frames(self, indices: list[int], abort: Callable[[], bool]) -> Iterator[torch.Tensor]:
        if not indices:
            return
        if any(second < first for first, second in zip(indices, indices[1:], strict=False)):
            for index in indices:
                yield from self._cuda_frames([index], abort)
            return
        if self._cuda_used:
            self.decoder = self.demuxer = None
            self._open_cuda()
        self._cuda_used = True
        pts = self.manifest.get("source_pts", [])
        if not pts:
            raise TimestampMismatch("Analysed source timestamps are missing.")
        anchor = (
            max(
                (
                    key["index"]
                    for key in self.manifest.get("keyframes", [])
                    if key["index"] <= indices[0]
                ),
                default=0,
            )
            if pts
            else 0
        )
        packet = None
        while anchor > 0:
            try:
                packet = self.demuxer.Seek(anchor)
                base = Fraction(self.demuxer.GetTimebaseNum(), self.demuxer.GetTimebaseDen())
                if Fraction(packet.pts) * base <= Fraction(pts[indices[0]]):
                    break
            except Exception as error:
                if "seek" not in str(error).lower():
                    raise
            # Some containers have no usable frame-count/seek index. Decode from
            # an earlier keyframe rather than trusting an approximate index.
            self.decoder = self.demuxer = None
            self._open_cuda()
            anchor //= 2
            packet = None
        packets = (
            itertools.chain([packet], self.demuxer) if packet is not None else iter(self.demuxer)
        )
        base = Fraction(self.demuxer.GetTimebaseNum(), self.demuxer.GetTimebaseDen())

        sequence = TimestampSequence(pts)
        wanted = iter(indices)
        target = next(wanted)
        self._active_cuda_index = target
        for frame in self._decoded_packets(packets, abort):
            if abort():
                raise InterruptedError("The segment was interrupted.")
            stamp = Fraction(frame.getPTS()) * base
            decoded_index = sequence.accept(stamp)
            if decoded_index < target:
                continue
            if decoded_index != target:
                raise TimestampMismatch(
                    f"Decoder skipped analysed frame {target}; received frame {decoded_index}."
                )
            picture = self._convert(torch.from_dlpack(frame))
            # Core decode surfaces may be reused on the next Decode call.
            torch.cuda.current_stream().synchronize()
            while True:
                yield picture
                previous = target
                target = next(wanted, -1)
                if target == -1:
                    return
                if target != previous:
                    self._active_cuda_index = target
                    break
        raise TimestampMismatch(f"Decoder ended before analysed frame {target}.")

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
        if self.backend == "cuda" and self.manifest.get("decoder", "nvdec") == "nvdec":
            try:
                yield from self._cuda_frames(indices, abort)
            except (torch.OutOfMemoryError, InterruptedError, TimestampMismatch):
                raise
            except Exception as error:
                raise RuntimeError(
                    f"Couldn't read frame {getattr(self, '_active_cuda_index', 0) + 1:,} "
                    "of this video. "
                    "Try adding it again, or remux it to MP4. Use Copy details for the error."
                ) from error
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
                    native = torch.from_numpy(
                        np.frombuffer(raw, dtype=np.uint16 if depth > 8 else np.uint8)
                        .copy()
                        .reshape(height * 3 // 2, width)
                    )
                    if self.backend == "cuda":
                        native = native.to("cuda")
                    current = self._convert(native)
                assert current is not None
                yield current
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)

    def close(self) -> None:
        self.decoder = None
        self.demuxer = None
