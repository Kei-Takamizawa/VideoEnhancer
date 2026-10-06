"""Stages preserve rational timestamps and explicit temporal context."""

from dataclasses import dataclass
from fractions import Fraction

import torch
import torch.nn.functional as F


@dataclass
class FrameBatch:
    frames: torch.Tensor
    timestamps: tuple[Fraction, ...]
    indices: tuple[int, ...]


class Stage:
    name = "stage"
    context_before = 0
    context_after = 0

    def setup(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def estimate_cost(self, input_size: tuple[int, int], **features: float) -> dict[str, float]:
        return {"pixels": float(input_size[0] * input_size[1]), **features}

    def process(self, batch: FrameBatch) -> FrameBatch:
        return batch


class ResizeStage(Stage):
    name = "resize"

    def __init__(self, width: int, height: int):
        self.width, self.height = width, height

    def process(self, batch: FrameBatch) -> FrameBatch:
        if batch.frames.shape[-2:] == (self.height, self.width):
            return batch
        result = F.interpolate(
            batch.frames.float(),
            size=(self.height, self.width),
            mode="bicubic",
            align_corners=False,
            antialias=True,
        ).to(torch.float16)
        return FrameBatch(result, batch.timestamps, batch.indices)


class Blend2xStage(Stage):
    name = "blend2x"
    context_after = 1

    def __init__(self, rate: Fraction, scene_cuts: set[int] | None = None):
        self.rate = rate
        self.scene_cuts = scene_cuts or set()

    def process(self, batch: FrameBatch) -> FrameBatch:
        outputs = []
        timestamps = []
        indices = []
        for pos, (timestamp, index) in enumerate(zip(batch.timestamps, batch.indices, strict=True)):
            current = batch.frames[pos]
            following = batch.frames[pos + 1] if pos + 1 < len(batch.indices) else current
            inserted = current if index + 1 in self.scene_cuts else (current + following) * 0.5
            outputs.extend((current, inserted))
            timestamps.extend((timestamp, timestamp + 1 / (self.rate * 2)))
            indices.extend((2 * index, 2 * index + 1))
        return FrameBatch(torch.stack(outputs), tuple(timestamps), tuple(indices))
