"""BasicVSR++ restoration stage using the P0 benchmark loader and checkpoint."""

from __future__ import annotations

from typing import Any

import torch

from videoenhancer.bench.basicvsr import WEIGHTS_SHA256, load_basicvsr_model
from videoenhancer.pipeline.stages import FrameBatch, Stage


class BasicVSRRestoreStage(Stage):
    name = "restore"

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.clip_length = int(settings.get("clip_length", 21))
        self.clip_overlap = int(settings.get("clip_overlap", 3))
        self.context_before = self.clip_overlap
        self.context_after = self.clip_overlap
        self.backend = settings.get("backend", "cuda")
        self.model: Any = None
        self.nan_retries = 0
        self.weight_sha256 = WEIGHTS_SHA256

    def setup(self) -> None:
        # Keep parameters on CPU between clips so BasicVSR++ and full-resolution
        # RIFE activations do not occupy the 8 GB reference GPU at the same time.
        self.model = load_basicvsr_model(cpu_cache_length=self.clip_length).eval()
        self.model = self.model.half() if self.backend == "cuda" else self.model.float()

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
        precision = torch.float16 if self.backend == "cuda" else torch.float32
        values = frames.to(dtype=precision)
        if self.backend == "cuda":
            # Reclaim unused blocks from the preceding RIFE clip before the
            # recurrent restoration activations are allocated.
            torch.cuda.empty_cache()
            self.model = self.model.cuda().half()
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
                self.model = self.model.half()
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
