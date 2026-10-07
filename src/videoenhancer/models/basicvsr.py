"""BasicVSR++ restoration stage using the P0 benchmark loader and checkpoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

from videoenhancer.bench.basicvsr import WEIGHTS_SHA256, load_basicvsr_model
from videoenhancer.pipeline.stages import FrameBatch, Stage


class BasicVSRRestoreStage(Stage):
    name = "restore"

    def __init__(
        self,
        settings: dict[str, Any],
        *,
        manifest: dict[str, Any] | None = None,
        weights: Path | None = None,
    ) -> None:
        self.settings = settings
        self.manifest = manifest or {}
        self.weights = weights
        self.clip_length = int(settings.get("clip_length", self.manifest.get("clip_length", 21)))
        self.clip_overlap = int(settings.get("clip_overlap", self.manifest.get("clip_overlap", 3)))
        self.context_before = self.clip_overlap
        self.context_after = self.clip_overlap
        self.backend = settings.get("backend", "cuda")
        self.model: Any = None
        self.nan_retries = 0
        self.weight_sha256 = WEIGHTS_SHA256
        self.precision = self.manifest.get("precision", "fp16")

    def setup(self) -> None:
        # Keep parameters on CPU between clips so BasicVSR++ and full-resolution
        # RIFE activations do not occupy the 8 GB reference GPU at the same time.
        if self.weights is None:
            self.model = load_basicvsr_model(cpu_cache_length=self.clip_length).eval()
        else:
            self.model = load_basicvsr_model(
                cpu_cache_length=self.clip_length,
                weights=self.weights,
                architecture_params=self.manifest["architecture_params"],
            ).eval()
            self.weight_sha256 = self.manifest["weights"]["sha256"]
        self.model = (
            self.model.half()
            if self.backend == "cuda" and self.precision == "fp16"
            else self.model.float()
        )

    def teardown(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def process(self, batch: FrameBatch) -> FrameBatch:
        if self.model is None:
            raise RuntimeError("BasicVSR++ stage was not set up.")
        frames = batch.frames
        precision = (
            torch.float16 if self.backend == "cuda" and self.precision == "fp16" else torch.float32
        )
        values = frames.to(dtype=precision)
        if self.backend == "cuda":
            # Reclaim unused blocks from the preceding RIFE clip before the
            # recurrent restoration activations are allocated.
            torch.cuda.empty_cache()
            self.model = self.model.cuda().to(dtype=precision)
        try:
            with torch.inference_mode():
                result = self.model(values.unsqueeze(0))
            if not torch.isfinite(result).all():
                raise FloatingPointError("BasicVSR++ returned NaN or Inf.")
        except FloatingPointError:
            self.nan_retries += 1
            self.model = self.model.float()
            try:
                with torch.inference_mode():
                    result = self.model(values.float().unsqueeze(0))
                if not torch.isfinite(result).all():
                    raise FloatingPointError("BasicVSR++ returned NaN or Inf after FP32 retry.")
            finally:
                self.model = self.model.to(dtype=precision)
        finally:
            if self.backend == "cuda":
                self.model = self.model.cpu()
                torch.cuda.empty_cache()
        result = result.squeeze(0).to(dtype=frames.dtype)
        if tuple(result.shape) != tuple(frames.shape):
            raise RuntimeError(
                f"BasicVSR++ changed clip geometry from {tuple(frames.shape)} to "
                f"{tuple(result.shape)}."
            )
        return FrameBatch(result, batch.timestamps, batch.indices)
