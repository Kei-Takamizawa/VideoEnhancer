"""Bounded restoration clip planning with deterministic overlap ownership."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import torch

from videoenhancer.pipeline.stages import FrameBatch


@dataclass(frozen=True)
class RestoreClip:
    start: int
    end: int
    owned_start: int
    owned_end: int


class StreamingClipBuffer:
    """Retain only frames required by the current and next restoration window."""

    def __init__(self) -> None:
        self._frames: dict[int, tuple[torch.Tensor, Fraction]] = {}

    def add(self, batch: FrameBatch) -> None:
        for frame, index, timestamp in zip(
            batch.frames, batch.indices, batch.timestamps, strict=True
        ):
            self._frames[index] = (frame, timestamp)

    def build(self, clip: RestoreClip) -> FrameBatch:
        indices = range(clip.start, clip.end)
        if any(index not in self._frames for index in indices):
            raise KeyError(f"Frames for restoration clip [{clip.start}, {clip.end}) are missing.")
        indices = range(clip.start, clip.end)
        return FrameBatch(
            torch.stack([self._frames[index][0] for index in indices]),
            tuple(self._frames[index][1] for index in indices),
            tuple(indices),
        )

    def release_before(self, index: int) -> None:
        for frame_index in [key for key in self._frames if key < index]:
            del self._frames[frame_index]

    @property
    def live_frames(self) -> int:
        return len(self._frames)


def plan_restore_clips(
    start: int,
    end: int,
    clip_length: int,
    clip_overlap: int,
    scene_cuts: set[int] | None = None,
) -> list[RestoreClip]:
    """Plan clips that never span cuts; overlap frames belong to the most central clip."""
    if start < 0 or end < start:
        raise ValueError("Clip range must be a non-negative half-open interval.")
    if clip_length < 1 or clip_overlap < 0 or 2 * clip_overlap >= clip_length:
        raise ValueError("clip_length must be positive and exceed twice clip_overlap.")
    if start == end:
        return []

    cuts = sorted(cut for cut in (scene_cuts or set()) if start < cut < end)
    scene_edges = [start, *cuts, end]
    result: list[RestoreClip] = []
    stride = clip_length - 2 * clip_overlap

    for scene_start, scene_end in zip(scene_edges[:-1], scene_edges[1:], strict=True):
        starts = [scene_start]
        while starts[-1] + clip_length < scene_end:
            next_start = starts[-1] + stride
            if next_start <= starts[-1]:
                break
            starts.append(next_start)

        windows = [(clip_start, min(scene_end, clip_start + clip_length)) for clip_start in starts]
        ownership_edges = [scene_start]
        for previous, following in zip(windows[:-1], windows[1:], strict=True):
            overlap_start, overlap_end = following[0], previous[1]
            if overlap_start > overlap_end:
                raise RuntimeError("Restoration clip plan contains a gap.")
            # At the midpoint, both windows are equally far from their nearest edge;
            # ties belong to the later clip, making ownership stable across runs.
            ownership_edges.append((overlap_start + overlap_end + 1) // 2)
        ownership_edges.append(scene_end)
        for index, (clip_start, clip_end) in enumerate(windows):
            owned_start, owned_end = ownership_edges[index : index + 2]
            result.append(RestoreClip(clip_start, clip_end, owned_start, owned_end))

    if result[0].owned_start != start or result[-1].owned_end != end:
        raise RuntimeError("Restoration clip plan does not cover the requested range.")
    if any(
        left.owned_end != right.owned_start for left, right in zip(result, result[1:], strict=False)
    ):
        raise RuntimeError("Restoration clip ownership is not contiguous.")
    return result
