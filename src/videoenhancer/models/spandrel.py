"""Single-frame restoration with trusted, installed Spandrel architectures."""

import importlib
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from videoenhancer.pipeline.stages import FrameBatch, Stage


class SpandrelRestoreStage(Stage):
    name = "restore"
    single_frame = True
    clip_length = 1
    clip_overlap = 0

    def __init__(self, manifest: dict[str, Any], weights: Path, settings: dict[str, Any]) -> None:
        self.manifest, self.weights = manifest, weights
        self.settings = settings
        self.backend = settings.get("backend", "cuda")
        self.model: Any = None
        self.nan_retries = 0

    def setup(self) -> None:
        spandrel: Any = importlib.import_module("spandrel")
        blend = self.manifest["weights"].get("blend")
        if blend:
            main = torch.load(self.weights, map_location="cpu", weights_only=True)
            other = torch.load(
                self.weights.parent / blend["filename"], map_location="cpu", weights_only=True
            )
            main = main.get("params_ema", main.get("params", main))
            other = other.get("params_ema", other.get("params", other))
            if main.keys() != other.keys():
                raise ValueError("Real-ESRGAN blend checkpoints have different parameters.")
            strength = self.settings.get("size_strength", 0.2)
            state = {key: strength * main[key] + (1 - strength) * other[key] for key in main}
            model = spandrel.ModelLoader().load_from_state_dict(state)
        else:
            if self.weights.suffix == ".safetensors":
                safe = importlib.import_module("safetensors.torch")
                state = safe.load_file(str(self.weights), device="cpu")
            else:
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
                result = self._frame(frame.unsqueeze(0).to(self.dtype)).squeeze(0)
                if result.shape != frame.shape or not torch.isfinite(result).all():
                    raise RuntimeError("Spandrel returned invalid geometry or non-finite values.")
                outputs.append(result.to(batch.frames.dtype))
        return FrameBatch(torch.stack(outputs), batch.timestamps, batch.indices)

    def _tile(self, image: torch.Tensor) -> torch.Tensor:
        if self.manifest["architecture"] == "drunet":
            height, width = image.shape[-2:]
            padded = F.pad(image, (0, (-width) % 8, 0, (-height) % 8), mode="replicate")
            quality = self.manifest["architecture_params"]["quality_factor"]
            if self.settings.get("restore_strength"):
                quality = {"light": 50, "medium": 30, "strong": 10}[
                    self.settings["restore_strength"]
                ]
            strength = torch.full_like(padded[:, :1], (100 - quality) / 100)
            return self.model.model(torch.cat((padded, strength), dim=1))[:, :, :height, :width]
        return self.model(image)

    def _frame(self, image: torch.Tensor) -> torch.Tensor:
        params = self.manifest["architecture_params"]
        tile = params.get("tile_size", 0)
        if not tile:
            return self._tile(image)
        overlap = params.get("tile_overlap", 32)
        height, width = image.shape[-2:]
        result = torch.empty_like(image)
        for top in range(0, height, tile):
            for left in range(0, width, tile):
                bottom, right = min(top + tile, height), min(left + tile, width)
                y, x = max(0, top - overlap), max(0, left - overlap)
                patch = image[
                    :, :, y : min(bottom + overlap, height), x : min(right + overlap, width)
                ]
                output = self._tile(patch)
                result[:, :, top:bottom, left:right] = output[
                    :, :, top - y : bottom - y, left - x : right - x
                ]
        return result


class SpandrelSizeStage(SpandrelRestoreStage):
    name = "size"

    def process(self, batch: FrameBatch) -> FrameBatch:
        outputs = []
        with torch.inference_mode():
            for frame in batch.frames:
                result = self._frame(frame.unsqueeze(0).to(self.dtype)).squeeze(0)
                expected = (
                    3,
                    frame.shape[-2] * self.manifest["scale"],
                    frame.shape[-1] * self.manifest["scale"],
                )
                if tuple(result.shape) != expected or not torch.isfinite(result).all():
                    raise RuntimeError(
                        "The enlarger returned invalid geometry or non-finite values."
                    )
                outputs.append(result.to(batch.frames.dtype))
        return FrameBatch(torch.stack(outputs), batch.timestamps, batch.indices)

    def _frame(self, image: torch.Tensor) -> torch.Tensor:
        scale = self.manifest["scale"]
        tile = self.manifest["architecture_params"].get("tile_size", 256)
        overlap = self.manifest["architecture_params"].get("tile_overlap", 32)
        height, width = image.shape[-2:]
        result = image.new_empty((1, 3, height * scale, width * scale))
        for top in range(0, height, tile):
            for left in range(0, width, tile):
                bottom, right = min(top + tile, height), min(left + tile, width)
                y, x = max(0, top - overlap), max(0, left - overlap)
                patch = image[
                    :, :, y : min(bottom + overlap, height), x : min(right + overlap, width)
                ]
                output = self.model(patch)
                result[:, :, top * scale : bottom * scale, left * scale : right * scale] = output[
                    :,
                    :,
                    (top - y) * scale : (bottom - y) * scale,
                    (left - x) * scale : (right - x) * scale,
                ]
        return result

    def teardown(self) -> None:
        self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
