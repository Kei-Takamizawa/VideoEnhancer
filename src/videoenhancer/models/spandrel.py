"""Single-frame restoration with trusted, installed Spandrel architectures."""

import importlib
from pathlib import Path
from typing import Any

import torch

from videoenhancer.pipeline.stages import FrameBatch, Stage


class SpandrelRestoreStage(Stage):
    name = "restore"
    single_frame = True
    clip_length = 1
    clip_overlap = 0

    def __init__(self, manifest: dict[str, Any], weights: Path, settings: dict[str, Any]) -> None:
        self.manifest, self.weights = manifest, weights
        self.backend = settings.get("backend", "cuda")
        self.model: Any = None
        self.nan_retries = 0

    def setup(self) -> None:
        spandrel: Any = importlib.import_module("spandrel")
        state = torch.load(self.weights, map_location="cpu", weights_only=True)
        model = spandrel.ModelLoader().load_from_state_dict(state)
        if not isinstance(model, spandrel.ImageModelDescriptor):
            raise ValueError("Spandrel adapter requires a single-image restoration model.")
        if (
            model.scale != self.manifest["scale"]
            or model.input_channels != 3
            or model.output_channels != 3
        ):
            raise ValueError("Spandrel model must restore RGB at the declared scale=1.")
        self.dtype = torch.float32
        if self.backend == "cuda" and self.manifest["precision"] == "fp16":
            if not model.supports_half:
                raise ValueError("This Spandrel model does not support declared fp16 precision.")
            self.dtype = torch.float16
        self.model = model.to(device=self.backend, dtype=self.dtype).eval()

    def process(self, batch: FrameBatch) -> FrameBatch:
        if self.model is None:
            raise RuntimeError("Spandrel stage was not set up.")
        outputs = []
        with torch.inference_mode():
            for frame in batch.frames:
                result = self.model(frame.unsqueeze(0).to(self.dtype)).squeeze(0)
                if result.shape != frame.shape or not torch.isfinite(result).all():
                    raise RuntimeError("Spandrel returned invalid geometry or non-finite values.")
                outputs.append(result.to(batch.frames.dtype))
        return FrameBatch(torch.stack(outputs), batch.timestamps, batch.indices)

    def teardown(self) -> None:
        self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
