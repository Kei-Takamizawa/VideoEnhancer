"""Lazily loaded, pinned neural pipeline stages."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import torch
import torch.nn.functional as F

from videoenhancer.pipeline.stages import FrameBatch, Stage


class BasicVSRRestoreStage(Stage):
    name = "restore"

    def __init__(self, settings: dict[str, Any]):
        self.settings = settings
        self.model: Any | None = None
        self.clip_frames = int(settings.get("restore_clip_frames", 15))
        self.overlap = int(settings.get("restore_overlap", 2))

    def setup(self) -> None:
        from videoenhancer.bench.basicvsr import load_basicvsr_model

        model: Any = load_basicvsr_model().eval()
        if torch.cuda.is_available():
            model = model.cuda().half()
        self.model = model

    def teardown(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None

    def process(self, batch: FrameBatch) -> FrameBatch:
        if self.model is None:
            raise RuntimeError("BasicVSR++ was not initialized. Retry the job after model setup.")
        if not batch.indices:
            return batch
        outputs: list[torch.Tensor] = []
        stride = max(1, self.clip_frames - self.overlap)
        for start in range(0, len(batch.indices), stride):
            end = min(len(batch.indices), start + self.clip_frames)
            clip = batch.frames[start:end].unsqueeze(0)
            model_input = clip.to(dtype=torch.float16 if clip.is_cuda else torch.float32)
            result = self.model(model_input)
            result = result.squeeze(0)
            if not torch.isfinite(result).all():
                result = self.model(clip.float())
                result = result.squeeze(0)
                if not torch.isfinite(result).all():
                    raise RuntimeError("BasicVSR++ returned NaN or Inf twice. Retry this segment.")
            keep_start = 0 if start == 0 else self.overlap // 2
            keep_end = (
                len(result)
                if end == len(batch.indices)
                else len(result) - (self.overlap - keep_start)
            )
            outputs.append(result[keep_start:keep_end].to(batch.frames.dtype))
            if end == len(batch.indices):
                break
        restored = torch.cat(outputs)
        return FrameBatch(
            restored, batch.timestamps[: len(restored)], batch.indices[: len(restored)]
        )


class RifeInterpolateStage(Stage):
    name = "interpolate"
    context_after = 1

    def __init__(self, rate: Fraction, scene_cuts: set[int], settings: dict[str, Any]):
        self.rate = rate
        self.scene_cuts = scene_cuts
        self.settings = settings
        self.model: Any | None = None
        self.fallback_count = 0

    def setup(self) -> None:
        from videoenhancer.bench.rife import load_rife_model

        model: Any = load_rife_model()
        if torch.cuda.is_available():
            model = model.cuda().half()
        self.model = model

    def teardown(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None

    def process(self, batch: FrameBatch) -> FrameBatch:
        outputs: list[torch.Tensor] = []
        timestamps: list[Fraction] = []
        indices: list[int] = []
        threshold = float(self.settings.get("interpolation_safety_threshold", 0.20))
        for pos, (timestamp, index) in enumerate(zip(batch.timestamps, batch.indices, strict=True)):
            current = batch.frames[pos]
            following = batch.frames[pos + 1] if pos + 1 < len(batch.indices) else current
            if index + 1 in self.scene_cuts or self.model is None:
                inserted = current if index + 1 in self.scene_cuts else (current + following) * 0.5
                if self.model is None and index + 1 not in self.scene_cuts:
                    self.fallback_count += 1
            else:
                h, w = current.shape[-2:]
                ph, pw = (-h) % 32, (-w) % 32
                pair = torch.cat((current, following), 0).unsqueeze(0)
                pair = F.pad(pair, (0, pw, 0, ph), mode="replicate")
                image0, image1 = pair[:, :3], pair[:, 3:]
                try:
                    outputs_from_model = self.model(
                        image0.to(dtype=torch.float16 if pair.is_cuda else torch.float32),
                        image1.to(dtype=torch.float16 if pair.is_cuda else torch.float32),
                        scale=1.0,
                    )
                    middle = (
                        outputs_from_model[1]
                        if isinstance(outputs_from_model, (tuple, list))
                        else outputs_from_model
                    )
                    inserted = middle[0, :, :h, :w]
                    blend = (current + following) * 0.5
                    if (
                        not torch.isfinite(inserted).all()
                        or (inserted - blend).abs().mean().item() > threshold
                    ):
                        inserted = blend
                        self.fallback_count += 1
                except Exception:
                    inserted = (current + following) * 0.5
                    self.fallback_count += 1
            outputs.extend((current, inserted))
            timestamps.extend((timestamp, timestamp + 1 / (self.rate * 2)))
            indices.extend((2 * index, 2 * index + 1))
        return FrameBatch(torch.stack(outputs), tuple(timestamps), tuple(indices))
