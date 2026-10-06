"""Plan bounded segments using CFR frame indices and scene cuts."""

from __future__ import annotations

from fractions import Fraction
from typing import Any


def _fps(media: dict[str, Any]) -> Fraction:
    return Fraction(str(media.get("cfr_fps") or media.get("average_fps") or "30"))


def output_multiplier(manifest: dict[str, Any]) -> int:
    """Return the placeholder pipeline's exact output-frame multiplier."""
    from videoenhancer.media.timing import output_rate

    fps = _fps(manifest["media"])
    return int(output_rate(manifest["settings"], manifest["media"]) / fps)


def expected_frames(manifest: dict[str, Any], segment: dict[str, Any]) -> int:
    return (int(segment["end"]) - int(segment["start"])) * output_multiplier(manifest)


def expected_duration(manifest: dict[str, Any], segment: dict[str, Any]) -> float:
    return float(Fraction(int(segment["end"]) - int(segment["start"]), 1) / _fps(manifest["media"]))


def plan_segments(
    media: dict[str, Any],
    scene_cuts: list[int],
    *,
    predicted_seconds_per_frame: float = 0.4,
    target_seconds: float = 180.0,
) -> list[dict[str, Any]]:
    """Split normalized frames into roughly three-minute work units.

    A hard cut is preferred when it is near the desired boundary. A single
    short segment is unavoidable for clips shorter than two seconds.
    """
    count = int(media["frame_count"])
    if count <= 0:
        raise ValueError("Cannot plan segments: frame count must be positive")
    fps = _fps(media)
    if fps <= 0:
        raise ValueError("Cannot plan segments: frame rate must be positive")
    per_frame = max(float(predicted_seconds_per_frame), 0.000001)
    min_frames = max(1, int(float(fps) * 2 + 0.999999))
    max_frames = max(min_frames, int(float(fps) * 60))
    goal_frames = max(min_frames, min(max_frames, round(target_seconds / per_frame)))
    cuts = sorted({int(c) for c in scene_cuts if 0 < int(c) < count})
    boundaries = [0]
    start = 0
    while start < count:
        remaining = count - start
        if remaining <= max_frames and remaining <= goal_frames + min_frames:
            end = count
        else:
            low = start + min_frames
            high = min(start + max_frames, count - min_frames)
            if high < low:
                high = start + max_frames
            wanted = min(start + goal_frames, high)
            candidates = [cut for cut in cuts if low <= cut <= high]
            # A cut within 40% of the target is preferable to an arbitrary
            # boundary. Distant cuts may create very uneven work units.
            nearby = [
                cut for cut in candidates if abs(cut - wanted) <= max(min_frames, goal_frames * 0.4)
            ]
            end = min(nearby, key=lambda cut: abs(cut - wanted)) if nearby else wanted
        boundaries.append(end)
        start = end
    return [
        {
            "index": index,
            "start": start,
            "end": end,
            "state": "pending",
            "predicted_seconds": (end - start) * per_frame,
        }
        for index, (start, end) in enumerate(zip(boundaries[:-1], boundaries[1:], strict=True))
    ]
