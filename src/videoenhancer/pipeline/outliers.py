"""Conservative, low-resolution detector for isolated luminance flashes."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def summarize_frames(frames: torch.Tensor, size: int = 16) -> torch.Tensor:
    """Return per-channel spatial summaries for each frame."""
    if frames.ndim != 4 or frames.shape[1] != 3:
        raise ValueError("Frames must have shape (frames, 3, height, width).")
    return F.interpolate(frames.float(), size=(size, size), mode="area")


def invalid_frame_positions(
    frames: torch.Tensor,
    reference_out_of_range: list[bool] | None = None,
) -> list[int]:
    """Flag non-finite frames and unexpected values outside normalized RGB range."""
    if frames.ndim != 4 or frames.shape[1] != 3:
        raise ValueError("Frames must have shape (frames, 3, height, width).")
    finite = torch.isfinite(frames).flatten(1).all(1)
    bounded = ((frames >= 0.0) & (frames <= 1.0)).flatten(1).all(1)
    if reference_out_of_range is None:
        reference_out_of_range = [False] * len(frames)
    if len(reference_out_of_range) != len(frames):
        raise ValueError("Reference range flags must match the frame count.")
    exempt_range = torch.tensor(reference_out_of_range, device=frames.device, dtype=torch.bool)
    range_violation = ~bounded & finite & ~exempt_range
    isolated_range = range_violation.clone()
    if len(frames) > 1:
        isolated_range[1:] &= ~range_violation[:-1]
        isolated_range[:-1] &= ~range_violation[1:]
    return (~finite | isolated_range).nonzero().flatten().cpu().tolist()


def reference_range_positions(frames: torch.Tensor) -> list[int]:
    """Record every input range excursion, regardless of decoder batch boundaries."""
    if frames.ndim != 4 or frames.shape[1] != 3:
        raise ValueError("Frames must have shape (frames, 3, height, width).")
    outside = ((frames < 0) | (frames > 1)).flatten(1).any(1)
    return outside.nonzero().flatten().cpu().tolist()


def detect_frame_outliers(
    output: torch.Tensor,
    reference: torch.Tensor,
    *,
    scene_ids: list[int] | None = None,
    luma_threshold: float = 0.20,
    difference_threshold: float = 0.12,
    edge_luma_threshold: float = 15 / 255,
) -> list[int]:
    """Return output positions with isolated luma and image-difference anomalies.

    Both arguments are small RGB image summaries with shape ``(frames, 3, h, w)``.
    ``reference`` is aligned to output frames (interpolated frames may reference
    their left source frame). This deliberately requires an input-side anomaly
    check so real scene cuts are not reported as white flashes.
    """
    if output.ndim != 4 or reference.ndim != 4:
        raise ValueError("Frame summaries must have shape (frames, 3, height, width).")
    if output.shape != reference.shape or output.shape[1] != 3:
        raise ValueError("Output and reference summaries must have matching RGB geometry.")
    if scene_ids is not None and len(scene_ids) != len(output):
        raise ValueError("Scene IDs must match the output frame count.")
    if output.shape[0] < 3:
        return []

    out = output.detach().to(device="cpu", dtype=torch.float32).clamp(0, 1)
    ref = reference.detach().to(device="cpu", dtype=torch.float32).clamp(0, 1)
    center = torch.arange(1, len(out) - 1)
    left, right = center - 1, center + 1
    missing_left = torch.zeros(len(center), dtype=torch.bool)
    missing_right = missing_left.clone()
    if scene_ids is not None:
        scenes = torch.tensor(scene_ids)
        same_left = scenes[left] == scenes[center]
        same_right = scenes[right] == scenes[center]
        # At a scene boundary, both comparisons use the available same-side
        # neighbor. A one-frame scene has only its aligned source reference.
        missing_left = ~same_left & ~same_right
        missing_right = missing_left.clone()
        left = torch.where(same_left, left, torch.where(same_right, right, center))
        right = torch.where(same_right, right, torch.where(same_left, left, center))
    previous, following = out[left].clone(), out[right].clone()
    previous[missing_left] = ref[center][missing_left]
    following[missing_right] = ref[center][missing_right]
    ref_previous, ref_following = ref[left], ref[right]
    weights = out.new_tensor((0.2126, 0.7152, 0.0722)).view(1, 3, 1, 1)
    out_luma = (out * weights).sum(1)
    ref_luma = (ref * weights).sum(1)

    def region_means(luma: torch.Tensor) -> dict[str, torch.Tensor]:
        height, width = luma.shape[-2:]
        edge_x = max(1, round(width * 0.08))
        edge_y = max(1, round(height * 0.08))
        return {
            "whole": luma.mean((1, 2)),
            "left": luma[:, :, :edge_x].mean((1, 2)),
            "right": luma[:, :, width - edge_x :].mean((1, 2)),
            "top": luma[:, :edge_y, :].mean((1, 2)),
            "bottom": luma[:, height - edge_y :, :].mean((1, 2)),
            "center": luma[:, edge_y : height - edge_y, edge_x : width - edge_x].mean((1, 2)),
        }

    output_regions = region_means(out_luma)
    reference_regions = region_means(ref_luma)
    previous_regions = region_means((previous * weights).sum(1))
    following_regions = region_means((following * weights).sum(1))
    ref_previous_regions = region_means((ref_previous * weights).sum(1))
    ref_following_regions = region_means((ref_following * weights).sum(1))
    flagged = torch.zeros(output.shape[0] - 2, dtype=torch.bool)
    output_difference = (out[1:-1] - (previous + following) * 0.5).abs().mean((1, 2, 3))
    reference_difference = (ref[1:-1] - (ref_previous + ref_following) * 0.5).abs().mean((1, 2, 3))
    output_reference_difference = (out[1:-1] - ref[1:-1]).abs().mean((1, 2, 3))
    # Luma alone misses chroma corruption that changes the picture but preserves
    # its weighted mean. Keep the input-side temporal guard to exclude real cuts.
    flagged |= (
        (output_difference >= difference_threshold)
        & (reference_difference < difference_threshold)
        & (output_reference_difference >= difference_threshold)
    )
    for region, threshold in (
        ("whole", luma_threshold),
        ("left", edge_luma_threshold),
        ("right", edge_luma_threshold),
        ("top", edge_luma_threshold),
        ("bottom", edge_luma_threshold),
    ):
        values = output_regions[region]
        reference_values = reference_regions[region]
        out_neighbors = (previous_regions[region] + following_regions[region]) * 0.5
        ref_neighbors = (ref_previous_regions[region] + ref_following_regions[region]) * 0.5
        jump = (values[1:-1] - out_neighbors).abs()
        reference_jump = (reference_values[1:-1] - ref_neighbors).abs()
        if region != "whole":
            regional_out_diff = (values[1:-1] - out_neighbors).abs()
            regional_ref_diff = (reference_values[1:-1] - ref_neighbors).abs()
            regional_out_vs_ref = (values[1:-1] - reference_values[1:-1]).abs()
        else:
            regional_out_diff = output_difference
            regional_ref_diff = reference_difference
            regional_out_vs_ref = output_reference_difference
        candidate = (
            (jump > threshold)
            & (reference_jump <= threshold)
            & (
                regional_out_diff
                > (edge_luma_threshold if region != "whole" else difference_threshold)
            )
            & (
                regional_out_vs_ref
                > (edge_luma_threshold if region != "whole" else difference_threshold)
            )
            & (
                regional_ref_diff
                <= (edge_luma_threshold if region != "whole" else difference_threshold)
            )
        )
        if region != "whole":
            center = output_regions["center"]
            center_jump = (
                center[1:-1] - (previous_regions["center"] + following_regions["center"]) * 0.5
            ).abs()
            candidate &= center_jump <= edge_luma_threshold
        flagged |= candidate
    return (flagged.nonzero().flatten() + 1).tolist()
