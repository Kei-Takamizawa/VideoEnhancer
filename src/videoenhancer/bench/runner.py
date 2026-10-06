"""Local I/O, placeholder-stage, and optional model benchmarks."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import tempfile
import threading
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

MODEL_CATALOG: dict[str, dict[str, str]] = {
    "rife": {
        "name": "Practical-RIFE 4.25",
        "license": "MIT",
        "source": "https://github.com/hzwer/Practical-RIFE",
        "weights": "https://drive.google.com/file/d/1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg/view",
        "sha256": "6615790efd627772917205db291f51cd392528a157ecbb2ecaeec3bff8eb6de2",
    },
    "realesrgan": {
        "name": "Real-ESRGAN realesr-general-x4v3",
        "license": "BSD-3-Clause",
        "source": "https://github.com/xinntao/Real-ESRGAN",
        "weights": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
        "sha256": "8dc7edb9ac80ccdc30c3a5dca6616509367f05fbc184ad95b731f05bece96292",
    },
    "basicvsrpp": {
        "name": "BasicVSR++ NTIRE 2021 compressed-video enhancement",
        "license": "Apache-2.0",
        "source": "https://github.com/ckkelvinchan/BasicVSR_PlusPlus",
        "weights": "https://download.openmmlab.com/mmediting/restorers/basicvsr_plusplus/basicvsr_plusplus_c128n25_ntire_decompress_track3_20210304-6daf4a40.pth",
        "sha256": "6daf4a405b0ff7221e3ac39b0a5c788468ae17661c577a3353b9fd477d0c983a",
    },
    "codeformer": {
        "name": "CodeFormer",
        "license": "NTU S-Lab License 1.0 (non-commercial)",
        "source": "https://github.com/sczhou/CodeFormer",
        "weights": "https://github.com/sczhou/CodeFormer/releases/download/v0.1.0/codeformer.pth",
        "sha256": "1009e537e0c2a07d4cabce6355f53cb66767cd4b4297ec7a4a64ca4b8a5684b7",
    },
    "keep": {
        "name": "KEEP",
        "license": "NTU S-Lab License 1.0 (non-commercial)",
        "source": "https://github.com/jnjaby/KEEP",
        "weights": "https://github.com/jnjaby/KEEP/releases",
    },
    "scrfd": {
        "name": "SCRFD (InsightFace model zoo)",
        "license": "Weights: non-commercial research only; code: MIT",
        "source": "https://github.com/deepinsight/insightface",
        "weights": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip",
        "sha256": "5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a",
    },
    "bisenet": {
        "name": "CelebAMask-HQ face parsing (BiSeNet)",
        "license": "Dataset/model terms must be confirmed for the selected checkpoint",
        "source": "https://github.com/zllrunning/face-parsing.PyTorch",
        "weights": "https://github.com/zllrunning/face-parsing.PyTorch",
    },
}


class _ResourceSampler:
    def __init__(self) -> None:
        self.nvml_peak_bytes: int | None = None
        self.rss_peak_bytes: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pynvml: Any = None
        self._handle: Any = None
        self._process: Any = None

    def start(self) -> None:
        try:
            import psutil

            self._process = psutil.Process()
            self._sample_rss()
        except ImportError:
            self._process = None
        try:
            import pynvml

            pynvml.nvmlInit()
            self._pynvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._sample()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        except Exception:
            self._pynvml = None

    def _sample(self) -> None:
        if self._pynvml is None:
            return
        try:
            used = self._pynvml.nvmlDeviceGetMemoryInfo(self._handle).used
            self.nvml_peak_bytes = max(self.nvml_peak_bytes or 0, int(used))
        except Exception:
            pass

    def _sample_rss(self) -> None:
        if getattr(self, "_process", None) is None:
            return
        try:
            value = int(self._process.memory_info().rss)
            self.rss_peak_bytes = max(self.rss_peak_bytes or 0, value)
        except Exception:
            pass

    def _loop(self) -> None:
        while not self._stop.wait(0.1):
            self._sample()
            self._sample_rss()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        self._sample()
        self._sample_rss()


def _get_home() -> Path:
    try:
        from videoenhancer.config import get_home

        return Path(get_home())
    except (ImportError, AttributeError):
        return Path(os.environ.get("VE_HOME", Path.home() / "AppData/Local/VideoEnhancer"))


def _ffmpeg() -> str | None:
    try:
        from videoenhancer.config import executable

        return executable("ffmpeg")
    except (ImportError, AttributeError, FileNotFoundError):
        found = shutil.which("ffmpeg")
        if found:
            return found
        tools = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        candidates = list((tools / "VideoEnhancerTools" / "ffmpeg").glob("*/bin/ffmpeg.exe"))
        if candidates:
            return str(sorted(candidates, key=lambda item: item.parent.parent.name)[-1])
        return None


def _generate_hevc_clip(ffmpeg: str | None, directory: Path) -> Path | None:
    if not ffmpeg:
        return None
    output = directory / "synthetic_hevc_1080x1920.mp4"
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1080x1920:rate=30",
        "-frames:v",
        "48",
        "-an",
        "-c:v",
        "libx265",
        "-preset",
        "ultrafast",
        "-threads",
        "2",
        "-x265-params",
        "pools=2:frame-threads=1:log-level=error",
        "-pix_fmt",
        "yuv420p10le",
        "-y",
        str(output),
    ]
    okay, _, _ = _run(command, timeout=100)
    return output if okay and output.is_file() else None


def _run(command: list[str], timeout: float = 90) -> tuple[bool, str, float]:
    begin = time.perf_counter()
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc), time.perf_counter() - begin
    elapsed = time.perf_counter() - begin
    return result.returncode == 0, (result.stderr or result.stdout)[-2500:], elapsed


def _gpu_info(torch: Any | None) -> dict[str, Any]:
    info: dict[str, Any] = {"available": False, "name": None, "driver": None, "vram_bytes": None}
    if torch is None or not torch.cuda.is_available():
        return info
    info["available"] = True
    try:
        props = torch.cuda.get_device_properties(0)
        info["name"] = props.name
        info["vram_bytes"] = int(props.total_memory)
    except Exception as exc:
        info["device_query_error"] = str(exc)
    try:
        import pynvml

        pynvml.nvmlInit()
        info["driver"] = pynvml.nvmlSystemGetDriverVersion()
        info["nvml_name"] = pynvml.nvmlDeviceGetName(pynvml.nvmlDeviceGetHandleByIndex(0))
    except Exception:
        pass
    return info


def _bench_tensor_stages(torch: Any, device: str) -> dict[str, Any]:
    """Measure CUDA/CPU placeholder operators without claiming video I/O."""
    result: dict[str, Any] = {}
    dtype = torch.float16 if device == "cuda" else torch.float32
    # Match the 720x1280 portrait source and 1080x1920 portrait output used by P0.
    sample = torch.rand((2, 3, 1280, 720), device=device, dtype=dtype)

    def measure(name: str, operation: Any) -> None:
        try:
            for _ in range(8):
                operation()
            if device == "cuda":
                torch.cuda.synchronize()
            timings = []
            for _ in range(50):
                start = time.perf_counter()
                operation()
                if device == "cuda":
                    torch.cuda.synchronize()
                timings.append((time.perf_counter() - start) * 1000)
            ordered = sorted(timings)
            result[name] = {
                "status": "measured",
                "median_ms": statistics.median(timings),
                "p90_ms": ordered[max(0, math.ceil(0.9 * len(ordered)) - 1)],
                "iterations": len(timings),
                "device": device,
            }
        except Exception as exc:
            result[name] = {"status": "skipped", "reason": f"operator failed: {exc}"}

    def resize() -> Any:
        return torch.nn.functional.interpolate(
            sample, size=(1920, 1080), mode="bicubic", align_corners=False, antialias=True
        )

    measure("resize", resize)

    try:
        from videoenhancer.media.color import nv12_to_rgb, rgb_to_nv12

        yuv = torch.randint(16, 240, (3 * 1280 // 2, 720), device=device, dtype=torch.uint8)
        measure("color_nv12_to_rgb", lambda: nv12_to_rgb(yuv, 720, 1280))
        rgb = torch.rand(
            (3, 1280, 720),
            device=device,
            dtype=torch.float16 if device == "cuda" else torch.float32,
        )
        measure("color_rgb_to_nv12", lambda: rgb_to_nv12(rgb))
        rgb_1080 = torch.rand(
            (3, 1920, 1080),
            device=device,
            dtype=torch.float16 if device == "cuda" else torch.float32,
        )
        measure("color_rgb_to_nv12_1080p", lambda: rgb_to_nv12(rgb_1080))
    except Exception as exc:
        result["color_conversion"] = {
            "status": "skipped",
            "reason": f"color API unavailable: {exc}",
        }

    try:
        from videoenhancer.pipeline.stages import Blend2xStage, FrameBatch, ResizeStage

        stage = ResizeStage(1080, 1920)
        frames = FrameBatch(sample, (Fraction(0), Fraction(1, 30)), (0, 1))
        blend = Blend2xStage(Fraction(30, 1))
        if hasattr(stage, "setup"):
            stage.setup()
        measure("resize_stage", lambda: stage.process(frames))
        resized_frames = stage.process(frames)
        measure("blend2x", lambda: blend.process(resized_frames))

        def end_to_end() -> Any:
            return blend.process(stage.process(frames))

        measure("p0_test_end_to_end", end_to_end)
        result["p0_test_end_to_end"]["output_frames_per_second"] = (
            2 * len(frames.frames) * 1000 / result["p0_test_end_to_end"]["median_ms"]
        )
        if hasattr(stage, "teardown"):
            stage.teardown()
    except Exception as exc:
        result["resize_stage"] = {
            "status": "skipped",
            "reason": f"ResizeStage API unavailable: {exc}",
        }
    return result


def _bench_pynvc_samples(extra_files: list[Path] | None = None) -> dict[str, Any]:
    """Decode eligible local samples directly to device memory with NVDEC."""
    try:
        import PyNvVideoCodec as nvc
    except ImportError:
        return {}
    configured = os.environ.get("VE_SAMPLES_DIR")
    directory = Path(configured).expanduser() if configured else Path.cwd() / "Videos"
    candidates = list(extra_files or []) + [
        p
        for p in (directory.iterdir() if directory.is_dir() else [])
        if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".mov", ".webm"}
    ]
    result: dict[str, Any] = {}
    targets = {
        "h264_720x1280": ("h264", 720, 1280),
        "hevc_1080x1920": ("hevc", 1080, 1920),
    }
    metadata_records = []
    for path in candidates:
        try:
            decoder = nvc.SimpleDecoder(str(path.resolve()), gpu_id=0, use_device_memory=True)
            meta = decoder.get_stream_metadata()
            metadata_records.append((path, meta))
            del decoder
        except Exception:
            continue
    for key, (codec, width, height) in targets.items():
        chosen = next(
            (
                row
                for row in metadata_records
                if str(row[1].codec_name).lower() in {codec, "h265" if codec == "hevc" else codec}
                and int(row[1].width) == width
                and int(row[1].height) == height
            ),
            None,
        )
        if chosen is None:
            result[key] = {
                "status": "skipped",
                "reason": f"No local {width}x{height} {codec.upper()} sample was found for NVDEC.",
            }
            continue
        path, meta = chosen
        durations: list[float] = []
        try:
            # One pass warms up the NVDEC session; two fresh decoder passes are timed.
            for repeat in range(3):
                decoder = nvc.SimpleDecoder(str(path.resolve()), gpu_id=0, use_device_memory=True)
                count = 0
                begin = time.perf_counter()
                total = int(meta.num_frames)
                while count < total:
                    frames = decoder.get_batch_frames(min(32, total - count))
                    if not frames:
                        break
                    count += len(frames)
                elapsed = time.perf_counter() - begin
                if repeat:
                    durations.append(elapsed)
            median = statistics.median(durations)
            result[key] = {
                "status": "measured",
                "backend": "PyNvVideoCodec SimpleDecoder (device memory)",
                "frames": count,
                "median_elapsed_seconds": median,
                "fps": count / median,
                "repeats": 2,
                "source_class": "local sample",
                "codec": str(meta.codec_name),
                "width": int(meta.width),
                "height": int(meta.height),
            }
        except Exception as exc:
            result[key] = {"status": "skipped", "reason": f"PyNvVideoCodec NVDEC failed: {exc}"}
    return result


def _bench_nvenc(torch: Any) -> dict[str, Any]:
    """Measure direct PyNvVideoCodec encode throughput without FFmpeg remux."""
    try:
        import PyNvVideoCodec as nvc

        from videoenhancer.media.color import rgb_to_nv12
        from videoenhancer.media.encode import NVENC_SETTINGS, DeviceSurface, packet_bytes
    except Exception as exc:
        return {
            name: {
                "status": "skipped",
                "reason": f"NVENC benchmark dependencies unavailable: {exc}",
            }
            for name in ("hevc_main10", "h264", "av1")
        }
    output: dict[str, Any] = {}
    rgb = torch.rand((3, 1920, 1080), device="cuda", dtype=torch.float16)
    for name, codec, color_format, matrix, depth in (
        ("hevc_main10", "hevc", "P010", "bt709", 10),
        ("h264", "h264", "NV12", "bt709", 8),
        ("av1", "av1", "P010", "bt709", 10),
    ):
        encoder = None
        try:
            settings = dict(NVENC_SETTINGS)
            settings.update(
                codec=codec,
                fps="30",
                gop="60",
                profile="high" if codec == "h264" else "main10" if codec == "hevc" else "main",
                cudastream=torch.cuda.current_stream().cuda_stream,
            )
            encoder = nvc.CreateEncoder(1080, 1920, color_format, False, **settings)
            packed = rgb_to_nv12(rgb, matrix, depth)
            surface = DeviceSurface(packed)
            with torch.inference_mode():
                for _ in range(8):
                    encoder.Encode(surface)
                torch.cuda.synchronize()
                timed_bytes = 0
                started = time.perf_counter()
                for _ in range(60):
                    timed_bytes += len(packet_bytes(encoder.Encode(surface)))
                torch.cuda.synchronize()
                elapsed = time.perf_counter() - started
                tail = packet_bytes(encoder.EndEncode())
                timed_bytes += len(tail)
                torch.cuda.synchronize()
            output[name] = {
                "status": "measured",
                "backend": "PyNvVideoCodec NVENC",
                "encoder": codec,
                "preset": "P7",
                "tuning": "high_quality",
                "rate_control": "constqp 18",
                "bit_depth": depth,
                "frames": 60,
                "elapsed_seconds": elapsed,
                "fps": 60 / elapsed,
                "encoded_bytes_including_flush": timed_bytes,
                "approx_bitrate_bits_per_second": timed_bytes * 8 / (60 / 30),
                "peak_vram_bytes": int(torch.cuda.max_memory_allocated()),
            }
        except Exception as exc:
            output[name] = {"status": "skipped", "reason": f"NVENC {codec} failed: {exc}"}
        finally:
            encoder = None
    return output


def _bench_pipeline_end_to_end(torch: Any, directory: Path) -> dict[str, Any]:
    """Process synthetic portrait frames through the actual segment worker."""
    if not torch.cuda.is_available():
        return {
            "status": "skipped",
            "reason": "CUDA is unavailable; end-to-end target is the CUDA engine.",
        }
    ffmpeg = _ffmpeg()
    if ffmpeg is None:
        return {
            "status": "skipped",
            "reason": "FFmpeg and ffprobe are required for a complete encoded segment.",
        }
    input_path = directory / "p0_end_to_end_input.mp4"
    output_path = directory / "p0_end_to_end_output.mp4"
    okay, detail, _ = _run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=720x1280:rate=30",
            "-frames:v",
            "150",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(input_path),
        ],
        timeout=60,
    )
    if not okay:
        return {"status": "skipped", "reason": f"Could not create the temporary P0 input: {detail}"}
    old_dir = os.environ.get("VE_FFMPEG_DIR")
    os.environ["VE_FFMPEG_DIR"] = str(Path(ffmpeg).parent)
    try:
        from videoenhancer.media.analyze import analyze
        from videoenhancer.pipeline.runner import process_segment

        analyzed = analyze(input_path, backend="cuda")
        manifest = {
            "input": {"path": str(input_path.resolve())},
            "settings": {
                "preset": "p0-test",
                "short_side": 1080,
                "fps": "2x",
                "codec": "hevc",
                "backend": "cuda",
                "batch_size": 2,
            },
            "media": analyzed["media"],
            "cfr_map": analyzed["cfr_map"],
            "scene_cuts": analyzed["scene_cuts"],
        }
        segment_stats = process_segment(
            manifest,
            {"index": 0, "start": 0, "end": min(150, len(analyzed["cfr_map"]))},
            output_path,
            lambda: False,
            batch_size=2,
        )
        output_frames = int(segment_stats["output_frames"])
        input_frames = int(segment_stats["input_frames"])
        return {
            "status": "measured",
            "backend": "pipeline.runner.process_segment",
            "input_resolution": "720x1280",
            "output_resolution": "1080x1920",
            "preset": "p0-test",
            "input_frames": input_frames,
            "output_frames": output_frames,
            "analysis_seconds": float(analyzed["analysis_seconds"]),
            "pipeline_seconds": float(segment_stats["seconds"]),
            "input_fps": float(segment_stats["fps"]),
            "output_fps": output_frames / float(segment_stats["seconds"]),
            "peak_torch_reserved_bytes": int(segment_stats["peak_torch_vram_bytes"]),
            "peak_rss_bytes": int(segment_stats["peak_rss_bytes"]),
            "output_file_size_bytes": output_path.stat().st_size,
            "includes_decode_stages_encode_mux": True,
        }
    except Exception as exc:
        return {"status": "skipped", "reason": f"P0 end-to-end segment failed: {exc}"}
    finally:
        if old_dir is None:
            os.environ.pop("VE_FFMPEG_DIR", None)
        else:
            os.environ["VE_FFMPEG_DIR"] = old_dir


def _bench_ffmpeg(ffmpeg: str | None, directory: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"decode": {}, "encode": {}}
    if ffmpeg is None:
        reason = "FFmpeg was not found through VE_FFMPEG_DIR or PATH."
        result["decode"] = {
            k: {"status": "skipped", "reason": reason} for k in ("h264_720x1280", "hevc_1080x1920")
        }
        result["encode"] = {
            k: {"status": "skipped", "reason": reason} for k in ("hevc_main10", "h264", "av1")
        }
        return result
    sources = [("h264_720x1280", 720, 1280, "libx264"), ("hevc_1080x1920", 1080, 1920, "libx265")]
    for key, height, width, encoder in sources:
        target = directory / f"{key}.mp4"
        ok, detail, _ = _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={width}x{height}:rate=30",
                "-frames:v",
                "45",
                "-c:v",
                encoder,
                "-preset",
                "ultrafast",
                "-y",
                str(target),
            ],
            timeout=120,
        )
        if not ok:
            result["decode"][key] = {
                "status": "skipped",
                "reason": f"Could not create local benchmark clip: {detail}",
            }
            continue
        ok, detail, elapsed = _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-hwaccel",
                "cuda",
                "-hwaccel_output_format",
                "cuda",
                "-i",
                str(target),
                "-f",
                "null",
                "-",
            ],
            timeout=90,
        )
        result["decode"][key] = (
            {
                "status": "measured",
                "frames": 45,
                "elapsed_seconds": elapsed,
                "fps": 45 / elapsed,
                "backend": "FFmpeg CUDA hwaccel",
            }
            if ok
            else {"status": "skipped", "reason": f"FFmpeg CUDA decode failed: {detail}"}
        )

    encoders = [
        ("hevc_main10", "hevc_nvenc", "p010le"),
        ("h264", "h264_nvenc", "nv12"),
        ("av1", "av1_nvenc", "p010le"),
    ]
    for key, encoder, pix_fmt in encoders:
        ok, detail, elapsed = _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=1920x1080:rate=30",
                "-frames:v",
                "60",
                "-pix_fmt",
                pix_fmt,
                "-c:v",
                encoder,
                "-preset",
                "p5",
                "-tune",
                "hq",
                "-f",
                "null",
                "-",
            ],
            timeout=120,
        )
        result["encode"][key] = (
            {
                "status": "measured",
                "frames": 60,
                "elapsed_seconds": elapsed,
                "fps": 60 / elapsed,
                "encoder": encoder,
            }
            if ok
            else {
                "status": "skipped",
                "reason": f"FFmpeg {encoder} encode unavailable/failed: {detail}",
            }
        )
    return result


def _bench_models(models: str | list[str] | None, gpu_available: bool) -> dict[str, Any]:
    selected = (
        set(MODEL_CATALOG)
        if models == "all"
        else set()
        if models is None
        else set(models.split(",") if isinstance(models, str) else models)
    )
    output: dict[str, Any] = {}
    for key in sorted(selected):
        if key not in MODEL_CATALOG:
            output[key] = {"status": "skipped", "reason": "Unknown model key."}
            continue
        model = MODEL_CATALOG[key]
        if models is None:
            reason = "Model benchmark was not requested; pass --models all or this model key."
        elif not gpu_available:
            reason = "CUDA device is unavailable; model benchmarks require CUDA FP16."
        elif key in {"keep", "bisenet"}:
            reason = (
                "No compatible, rights-reviewed benchmark adapter is implemented for this model; "
                "no checkpoint download or inference was attempted."
            )
        else:
            reason = "No trusted expected SHA-256 digest is pinned for the selected weights."
        output[key] = {
            "status": "skipped",
            "name": model["name"],
            "license": model["license"],
            "source_url": model["source"],
            "weights_url": model["weights"],
            "sha256": model.get("sha256"),
            "reason": reason,
        }
    return output


def _verified_weight(model_key: str) -> tuple[Path, str]:
    model = MODEL_CATALOG[model_key]
    expected = model.get("sha256")
    if not expected:
        raise RuntimeError("No trusted expected SHA-256 digest is pinned for this checkpoint.")
    directory = _get_home() / "models"
    directory.mkdir(parents=True, exist_ok=True)
    filename = "realesr-general-x4v3.pth"
    path = directory / filename
    if not path.exists():
        import urllib.request

        temporary = path.with_suffix(path.suffix + ".download")
        try:
            urllib.request.urlretrieve(model["weights"], temporary)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest.lower() != expected.lower():
        path.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-256 mismatch for {filename}: expected {expected}, got {digest}; "
            "the file was removed. Re-run the explicitly requested model benchmark."
        )
    return path, digest


def _bench_realesrgan(torch: Any) -> dict[str, Any]:
    entry = MODEL_CATALOG["realesrgan"]
    common = {
        "name": entry["name"],
        "license": entry["license"],
        "source_url": entry["source"],
        "weights_url": entry["weights"],
        "expected_sha256": entry["sha256"],
    }
    try:
        weight, digest = _verified_weight("realesrgan")
        from spandrel import ModelLoader
    except Exception as exc:
        return {**common, "status": "skipped", "sha256": entry["sha256"], "reason": str(exc)}
    try:
        descriptor = ModelLoader(device="cuda").load_from_file(weight)
        network = descriptor.model.eval().half()
        torch.cuda.reset_peak_memory_stats()
        working_batch = 1
        # Probe batch sizes with one warm-up call; release each probe before growing.
        for candidate in (1, 2, 4, 8, 16):
            sample = None
            try:
                sample = torch.rand((candidate, 3, 1280, 720), device="cuda", dtype=torch.float16)
                with torch.inference_mode():
                    network(sample)
                torch.cuda.synchronize()
                working_batch = candidate
                del sample
                torch.cuda.empty_cache()
            except torch.cuda.OutOfMemoryError:
                sample = None
                torch.cuda.empty_cache()
                break
        sample = torch.rand((working_batch, 3, 1280, 720), device="cuda", dtype=torch.float16)
        with torch.inference_mode():
            for _ in range(10):
                network(sample)
            torch.cuda.synchronize()
            timings: list[float] = []
            for _ in range(50):
                start = time.perf_counter()
                network(sample)
                torch.cuda.synchronize()
                timings.append((time.perf_counter() - start) * 1000)
        ordered = sorted(timings)
        return {
            **common,
            "status": "measured",
            "sha256": digest,
            "median_ms": statistics.median(timings),
            "p90_ms": ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))],
            "iterations": 50,
            "batch_size": working_batch,
            "input_shape": [working_batch, 3, 1280, 720],
            "output_shape": [working_batch, 3, 5120, 2880],
            "precision": "float16",
            "torch_inference_mode": True,
            "peak_vram_bytes": int(torch.cuda.max_memory_allocated()),
            "loader": "spandrel ModelLoader",
            "tile": "whole frame",
        }
    except Exception as exc:
        return {
            **common,
            "status": "skipped",
            "sha256": digest,
            "reason": f"verified weights were available but inference failed: {exc}",
        }


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# VideoEnhancer benchmark report",
        "",
        f"Created: {report['created_at']}",
        "",
        f"GPU: {report['environment']['gpu'].get('name') or 'not available'}; "
        f"driver: {report['environment']['gpu'].get('driver') or 'unknown'}; "
        f"VRAM: {report['environment']['gpu'].get('vram_bytes') or 'unknown'} bytes.",
        f"OS: {report['environment']['os']}; Python: {report['environment']['python']}; "
        f"PyTorch: {report['environment']['torch']}; CUDA: {report['environment']['cuda']}; "
        f"TensorRT: {report['environment']['tensorrt']}.",
        "",
        "## Part A: I/O and placeholder stages",
        "",
        "Timings marked skipped were not measured. Tensor-only timings exclude video I/O.",
        "",
        "| Component | Status | Result |",
        "|---|---|---|",
    ]
    components = report["part_a"]
    for group_name, group in (
        ("NVDEC", components["decode"]),
        ("NVENC", components["encode"]),
        ("Tensor stages", components["stages"]),
    ):
        for name, item in group.items():
            status = item.get("status", "not measured")
            value = (
                f"{item.get('fps', 0):.2f} fps"
                if "fps" in item
                else f"median {item.get('median_ms', 0):.3f} ms; p90 {item.get('p90_ms', 0):.3f} ms"
                if "median_ms" in item
                else item.get("reason", "not available")
            )
            lines.append(f"| {group_name}: {name} | {status} | {value} |")
    lines += [
        "",
        "## Part B: candidate models",
        "",
        "No weights are downloaded unless a trusted expected SHA-256 is configured.",
        "",
        "| Model | License | Source / weights | SHA-256 | Result | Peak VRAM | "
        "Input / batch / tile | Precision / loader |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for key, item in report["part_b"].items():
        name = item.get("name", key)
        license_name = item.get("license", "unknown")
        source_url = item.get("source_url", "not recorded")
        weights_url = item.get("weights_url", "not recorded")
        source_and_weights = f"Source: {source_url}<br>Weights: {weights_url}"
        digests = []
        for label, field in (
            ("expected", "expected_sha256"),
            ("actual", "sha256"),
            ("source", "source_sha256"),
            ("archive", "archive_sha256"),
        ):
            value = item.get(field)
            if field == "archive_sha256":
                value = value or item.get("weights_archive_sha256")
            if value:
                digests.append(f"{label}: {value}")
        digest = "<br>".join(digests) if digests else "not published"
        status = item.get("status", "not measured")
        result = status
        if item.get("median_ms") is not None:
            result += f"; median {item['median_ms']:.3f} ms"
        if item.get("p90_ms") is not None:
            result += f"; p90 {item['p90_ms']:.3f} ms"
        if item.get("reason"):
            result += f"; {item['reason']}"
        variants = item.get("variants")
        if variants:
            variant_results = [
                f"batch {variant.get('batch_size')}: {variant.get('status')}"
                + (
                    f", median {variant['median_ms']:.3f} ms"
                    if variant.get("median_ms") is not None
                    else f", {variant.get('reason', '')}"
                )
                for variant in variants
            ]
            result += "; " + " / ".join(variant_results)
        peak = item.get("peak_vram_bytes")
        peak_vram = f"{peak} bytes" if peak is not None else "not reported"
        shape_fields = (
            "input_shape",
            "input_source_resolution",
            "inference_resolution",
            "output_shape",
            "batch_size",
            "largest_tested_working_batch",
            "clip_frames",
            "tile",
        )
        input_info = (
            "; ".join(
                f"{field}: {json.dumps(item[field], ensure_ascii=False)}"
                for field in shape_fields
                if field in item
            )
            or "not recorded"
        )
        precision_loader = (
            "; ".join(
                f"{field}: {item[field]}"
                for field in (
                    "precision",
                    "loader",
                    "backend",
                    "adapter",
                    "provider_placement_note",
                )
                if item.get(field) is not None
            )
            or "not recorded"
        )
        values = (
            name,
            license_name,
            source_and_weights,
            digest,
            result,
            peak_vram,
            input_info,
            precision_loader,
        )
        escaped = [
            str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ") for value in values
        ]
        lines.append("| " + " | ".join(escaped) + " |")
    lines += [
        "",
        f"Peak NVML VRAM: {report['resources'].get('nvml_peak_bytes') or 'unavailable'} bytes; "
        f"peak torch VRAM: {report['resources'].get('torch_peak_bytes') or 'unavailable'} bytes; "
        f"peak RSS: {report['resources'].get('peak_rss_bytes') or 'unavailable'} bytes.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_bench(
    calibrate: bool = False,
    models: str | list[str] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run local benchmarks and return the report as a JSON-compatible dict.

    ``models`` accepts ``"all"`` or a comma-separated list: rife, realesrgan,
    basicvsrpp, codeformer, keep, scrfd, bisenet. Model downloads remain disabled
    unless a trusted expected hash and a loader adapter are available.
    """
    try:
        import torch
    except ImportError:
        torch = None
    try:
        import psutil

        process = psutil.Process()
        peak_rss = process.memory_info().rss
    except ImportError:
        process = None
        peak_rss = None

    gpu = _gpu_info(torch)
    sampler = _ResourceSampler()
    sampler.start()
    if torch is not None and gpu["available"]:
        torch.cuda.reset_peak_memory_stats()
    target = Path(output_dir) if output_dir else Path.cwd()
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ve-bench-") as temporary:
        ffmpeg = _ffmpeg()
        try:
            has_pynvc = importlib.util.find_spec("PyNvVideoCodec") is not None
        except (ImportError, ValueError):
            has_pynvc = False
        if gpu["available"] and has_pynvc:
            generated_hevc = _generate_hevc_clip(ffmpeg, Path(temporary))
            extras = [generated_hevc] if generated_hevc else []
            io_results = {
                "decode": _bench_pynvc_samples(extras),
                "encode": {},
            }
        else:
            io_results = _bench_ffmpeg(ffmpeg, Path(temporary))
    if torch is not None and gpu["available"]:
        io_results["encode"] = _bench_nvenc(torch)
    device = "cuda" if gpu["available"] else "cpu"
    stages = (
        _bench_tensor_stages(torch, device)
        if torch is not None
        else {"unavailable": {"status": "skipped", "reason": "PyTorch is not installed."}}
    )
    if torch is not None and gpu["available"] and has_pynvc:
        with tempfile.TemporaryDirectory(prefix="ve-bench-e2e-") as e2e_dir:
            end_to_end = _bench_pipeline_end_to_end(torch, Path(e2e_dir))
    else:
        end_to_end = {
            "status": "skipped",
            "reason": "CUDA PyTorch and PyNvVideoCodec are required for a full pipeline segment.",
        }
    if process is not None:
        try:
            peak_rss = max(peak_rss or 0, process.memory_info().rss)
        except Exception:
            pass
    torch_peak = None
    if torch is not None and gpu["available"]:
        torch.cuda.synchronize()
        torch_peak = int(torch.cuda.max_memory_allocated())
    version_tensorrt = None
    try:
        from importlib import import_module

        tensorrt = import_module("tensorrt")
        version_tensorrt = tensorrt.__version__
    except ImportError:
        pass
    try:
        import torch as torch_module

        cuda_version = torch_module.version.cuda
        torch_version = torch_module.__version__
    except ImportError:
        cuda_version = torch_version = None
    model_results = _bench_models(models, bool(gpu["available"]))
    selected_models = (
        set(MODEL_CATALOG)
        if models == "all"
        else set(models.split(",") if isinstance(models, str) else models or [])
    )
    if torch is not None and gpu["available"] and "realesrgan" in selected_models:
        model_results["realesrgan"] = _bench_realesrgan(torch)
    if torch is not None and gpu["available"]:
        from importlib import import_module

        adapters = {
            "basicvsrpp": ("videoenhancer.bench.basicvsr", "bench_basicvsr"),
            "codeformer": ("videoenhancer.bench.codeformer", "bench_codeformer"),
            "rife": ("videoenhancer.bench.rife", "bench_rife"),
            "scrfd": ("videoenhancer.bench.scrfd", "bench_scrfd"),
        }
        for key, (module_name, function_name) in adapters.items():
            if key not in selected_models:
                continue
            try:
                adapter = getattr(import_module(module_name), function_name)
                model_results[key] = adapter(torch)
            except Exception as exc:
                model_results[key] = {
                    **model_results.get(key, {}),
                    "status": "skipped",
                    "reason": f"Adapter could not be initialized: {exc}",
                }
    if torch is not None and gpu["available"]:
        model_peaks = [
            int(item["peak_vram_bytes"])
            for item in model_results.values()
            if item.get("peak_vram_bytes")
        ]
        torch_peak = max([torch_peak or 0, *model_peaks]) or None
    sampler.stop()
    report: dict[str, Any] = {
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "calibrate": calibrate,
        "environment": {
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "python": platform.python_version(),
            "torch": torch_version,
            "cuda": cuda_version,
            "tensorrt": version_tensorrt,
            "gpu": gpu,
        },
        "part_a": {
            "decode": io_results["decode"],
            "encode": io_results["encode"],
            "stages": stages,
            "end_to_end": end_to_end,
        },
        "part_b": model_results,
        "resources": {
            "nvml_peak_bytes": sampler.nvml_peak_bytes,
            "torch_peak_bytes": torch_peak,
            "peak_rss_bytes": sampler.rss_peak_bytes or peak_rss,
        },
        "profile": {
            "schema_version": 1,
            "gpu_name": gpu["name"],
            "driver": gpu["driver"],
            "components": {},
        },
    }
    profile_components = report["profile"]["components"]
    component_sizes = {
        "decode": (720 * 1280, "h264_720x1280"),
        "encode": (1080 * 1920, "hevc_main10"),
    }
    for component, (pixels, key) in component_sizes.items():
        item = report["part_a"]["decode" if component == "decode" else "encode"].get(key, {})
        if item.get("fps"):
            profile_components[component] = {
                "seconds_per_pixel_frame": 1.0 / (float(item["fps"]) * pixels)
            }
    input_pixels = 720 * 1280
    output_pixels = 1080 * 1920
    color_in = stages.get("color_nv12_to_rgb", {}).get("median_ms")
    color_out = stages.get("color_rgb_to_nv12_1080p", {}).get("median_ms")
    if color_in and color_out:
        profile_components["color"] = {
            "seconds_per_pixel_frame": (
                (float(color_in) + 2 * float(color_out)) / 1000 / (input_pixels + 2 * output_pixels)
            )
        }
    for name, item in stages.items():
        if name in ("resize_stage", "resize") and item.get("median_ms"):
            profile_components["resize"] = {
                "seconds_per_pixel_frame": float(item["median_ms"]) / 1000 / (2 * output_pixels)
            }
        elif name == "blend2x" and item.get("median_ms"):
            profile_components["blend2x"] = {
                "seconds_per_pixel_frame": float(item["median_ms"]) / 1000 / (2 * 1080 * 1920)
            }
        elif name == "p0_test_end_to_end" and item.get("median_ms"):
            item["fps"] = item["output_frames_per_second"]
    report["profile"]["segment_overhead_seconds"] = 2.0
    # Keep all estimator component keys present. Null timings stay visibly uncalibrated.
    for component in ("decode", "color", "resize", "blend2x", "encode"):
        profile_components.setdefault(component, {"seconds_per_pixel_frame": None})
    if end_to_end.get("status") == "measured":
        report["profile"]["end_to_end_validation"] = {
            "input_fps": end_to_end["input_fps"],
            "output_fps": end_to_end["output_fps"],
            "pipeline_seconds": end_to_end["pipeline_seconds"],
            "analysis_seconds_excluded": end_to_end["analysis_seconds"],
        }
    json_path, markdown_path = target / "bench_report.json", target / "bench_report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(report, markdown_path)
    if calibrate:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", gpu["name"] or "uncalibrated")
        safe_driver = re.sub(r"[^A-Za-z0-9._-]+", "_", gpu["driver"] or "unknown-driver")
        profile_dir = _get_home() / "profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / f"{safe_name}_{safe_driver}.json").write_text(
            json.dumps(report["profile"], indent=2), encoding="utf-8"
        )
    return report
