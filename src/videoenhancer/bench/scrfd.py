"""Benchmark the official InsightFace SCRFD 500m ONNX model with CUDA EP."""

from __future__ import annotations

import hashlib
import statistics
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from videoenhancer.config import get_home

ARCHIVE_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip"
ARCHIVE_SHA256 = "57d31b56b6ffa911c8a73cfc1707c73cab76efe7f13b675a05223bf42de47c72"
WEIGHT_SHA256 = "5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a"
WEIGHT_NAME = "scrfd-det_500m.onnx"


class _NvmlPeakSampler:
    """Sample device-wide VRAM use around the SCRFD inference loop."""

    def __init__(self) -> None:
        self._nvml: Any = None
        self._handle: Any = None
        self.peak_bytes: int | None = None

    def start(self) -> None:
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.sample()
        except Exception:
            self._nvml = None
            self._handle = None

    def sample(self) -> None:
        if self._nvml is None:
            return
        try:
            used = int(self._nvml.nvmlDeviceGetMemoryInfo(self._handle).used)
            self.peak_bytes = max(self.peak_bytes or 0, used)
        except Exception:
            pass

    def stop(self) -> int | None:
        self.sample()
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml = None
        return self.peak_bytes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_weight() -> Path:
    models = get_home() / "models"
    models.mkdir(parents=True, exist_ok=True)
    weight = models / WEIGHT_NAME
    if weight.is_file() and _sha256(weight) == WEIGHT_SHA256:
        return weight
    archive = models / "buffalo_sc.zip"
    if not archive.is_file() or _sha256(archive) != ARCHIVE_SHA256:
        archive.unlink(missing_ok=True)
        temporary = archive.with_suffix(".zip.download")
        try:
            with urllib.request.urlopen(ARCHIVE_URL, timeout=120) as response:
                temporary.write_bytes(response.read())
            actual = _sha256(temporary)
            if actual != ARCHIVE_SHA256:
                raise RuntimeError(f"SCRFD archive SHA-256 mismatch: {actual}")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        member = next((name for name in bundle.namelist() if name.endswith("/det_500m.onnx")), None)
        if member is None:
            raise RuntimeError("The verified buffalo_sc archive lacks det_500m.onnx.")
        temporary_weight = weight.with_suffix(".onnx.extracting")
        try:
            with bundle.open(member) as source, temporary_weight.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
            actual = _sha256(temporary_weight)
            if actual != WEIGHT_SHA256:
                raise RuntimeError(f"SCRFD checkpoint SHA-256 mismatch: {actual}")
            temporary_weight.replace(weight)
        finally:
            temporary_weight.unlink(missing_ok=True)
    return weight


def bench_scrfd(_torch: Any) -> dict[str, Any]:
    """Measure 50 warmed CUDA ORT inferences on a 640x640 full-frame input."""
    result: dict[str, Any] = {
        "name": "SCRFD 500m buffalo_sc detector",
        "license": "InsightFace public model weights: non-commercial research only",
        "source_url": "https://github.com/deepinsight/insightface",
        "weights_url": ARCHIVE_URL,
        "sha256": WEIGHT_SHA256,
        "archive_sha256": ARCHIVE_SHA256,
        "input_source_resolution": "720x1280",
        "input_shape": [1280, 720, 3],
        "inference_resolution": "640x640 letterboxed",
        "batch_size": 1,
        "tile": "whole frame",
        "precision": "float32",
        "provider_placement_note": (
            "CUDAExecutionProvider is requested and CPUExecutionProvider is enabled as fallback; "
            "per-node placement was not profiled, so some graph nodes may run on CPU."
        ),
        "peak_vram_scope": "NVML device-wide used memory; includes other processes.",
        "checksum_provenance": (
            "Pinned after first acquisition from the official HTTPS release archive."
        ),
    }
    try:
        import numpy as np
        import onnxruntime as ort

        checkpoint = _verified_weight()
        providers = ort.get_available_providers()
        if "CUDAExecutionProvider" not in providers:
            return {
                **result,
                "status": "skipped",
                "reason": f"ONNX Runtime CUDA provider unavailable; providers={providers}.",
            }
        session = ort.InferenceSession(
            str(checkpoint),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        memory = _NvmlPeakSampler()
        memory.start()
        memory.sample()
        image = np.random.default_rng(20261004).integers(0, 256, (1280, 720, 3), dtype=np.uint8)
        scale = min(640 / image.shape[1], 640 / image.shape[0])
        width, height = round(image.shape[1] * scale), round(image.shape[0] * scale)
        x_indices = np.minimum((np.arange(width) / scale).astype(np.int64), image.shape[1] - 1)
        y_indices = np.minimum((np.arange(height) / scale).astype(np.int64), image.shape[0] - 1)
        resized = image[y_indices[:, None], x_indices[None, :]]
        padded = np.zeros((640, 640, 3), dtype=np.uint8)
        left, top = (640 - width) // 2, (640 - height) // 2
        padded[top : top + height, left : left + width] = resized
        input_tensor = ((padded.astype(np.float32) - 127.5) / 128.0).transpose(2, 0, 1)[None]
        input_name = session.get_inputs()[0].name
        for _ in range(10):
            session.run(None, {input_name: input_tensor})
            memory.sample()
        timings: list[float] = []
        for _ in range(50):
            start = time.perf_counter()
            session.run(None, {input_name: input_tensor})
            timings.append((time.perf_counter() - start) * 1000)
            memory.sample()
        ordered = sorted(timings)
        outputs: Any = session.run(None, {input_name: input_tensor})
        return {
            **result,
            "status": "measured",
            "backend": "ONNX Runtime with CUDAExecutionProvider and CPUExecutionProvider",
            "median_ms": statistics.median(timings),
            "p90_ms": ordered[int(0.9 * (len(ordered) - 1))],
            "iterations": len(timings),
            "torch_inference_mode": "not applicable; ONNX Runtime",
            "providers": session.get_providers(),
            "output_shapes": [list(getattr(value, "shape", ())) for value in outputs],
            "peak_vram_bytes": memory.stop(),
        }
    except Exception as exc:
        peak_vram = memory.stop() if "memory" in locals() else None
        return {
            **result,
            "status": "skipped",
            "peak_vram_bytes": peak_vram,
            "reason": f"SCRFD benchmark unavailable or failed: {exc}",
        }
