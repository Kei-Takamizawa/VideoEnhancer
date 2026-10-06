"""Practical-RIFE 4.25 interpolation stage using the pinned benchmark loader."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import torch
import torch.nn.functional as F

from videoenhancer.bench.rife import load_rife_model
from videoenhancer.pipeline.stages import FrameBatch, Stage


class RifeInterpolateStage(Stage):
    name = "rife"
    context_after = 1

    def __init__(self, rate: Fraction, scene_cuts: set[int], settings: dict[str, Any]) -> None:
        self.rate = rate
        self.scene_cuts = scene_cuts
        self.settings = settings
        self.backend = settings.get("backend", "cuda")
        self.mean_flow_limit = float(settings.get("rife_mean_flow_limit", 48.0))
        self.average_difference_limit = float(settings.get("rife_average_difference_limit", 0.25))
        self.fallback_count = 0
        self.nan_fallback_count = 0
        self.model: Any = None
        self.last_padding = (0, 0)

    def setup(self) -> None:
        self.model = load_rife_model().eval()
        if self.backend == "cuda":
            self.model = self.model.cuda().half()
        else:
            self.model = self.model.float()

    def teardown(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _interpolate(self, left: torch.Tensor, right: torch.Tensor) -> torch.Tensor:
        if self.model is None:
            raise RuntimeError("Practical-RIFE stage was not set up.")
        if not torch.isfinite(left).all() or not torch.isfinite(right).all():
            self.nan_fallback_count += 1
            self.fallback_count += 1
            return torch.nan_to_num(left, nan=0.0, posinf=1.0, neginf=0.0)
        height, width = left.shape[-2:]
        pad_h, pad_w = (-height) % 32, (-width) % 32
        self.last_padding = (pad_h, pad_w)
        pair = torch.cat((left, right), dim=0).unsqueeze(0)
        pair = F.pad(pair, (0, pad_w, 0, pad_h), mode="replicate")
        flows, _mask, merged = self.model(pair, scale_list=[8, 4, 2, 1, 1], fastmode=True)
        interpolated = merged[-1][0, :, :height, :width]
        flow = flows[-1]
        mean_flow = flow.abs().mean().item()
        average = (left + right) * 0.5
        average_difference = (interpolated - average).abs().mean().item()
        if not torch.isfinite(interpolated).all() or not torch.isfinite(flow).all():
            self.nan_fallback_count += 1
            self.fallback_count += 1
            return average
        if mean_flow > self.mean_flow_limit or average_difference > self.average_difference_limit:
            self.fallback_count += 1
            return average
        return interpolated

    def process(self, batch: FrameBatch) -> FrameBatch:
        outputs: list[torch.Tensor] = []
        timestamps: list[Fraction] = []
        indices: list[int] = []
        half_frame = Fraction(1, 1) / (self.rate * 2)
        for position, (timestamp, index) in enumerate(
            zip(batch.timestamps, batch.indices, strict=True)
        ):
            current = batch.frames[position]
            following = batch.frames[position + 1] if position + 1 < len(batch.indices) else current
            if position + 1 == len(batch.indices) or index + 1 in self.scene_cuts:
                inserted = current
            else:
                try:
                    inserted = self._interpolate(current, following)
                except (FloatingPointError, RuntimeError) as exc:
                    if "out of memory" in str(exc).lower():
                        raise
                    self.fallback_count += 1
                    self.nan_fallback_count += int(not torch.isfinite(current).all())
                    inserted = (current + following) * 0.5
            outputs.extend((current, inserted))
            timestamps.extend((timestamp, timestamp + half_frame))
            indices.extend((2 * index, 2 * index + 1))
        return FrameBatch(torch.stack(outputs), tuple(timestamps), tuple(indices))
