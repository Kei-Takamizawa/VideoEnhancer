"""Conservative, low-resolution detector for isolated luminance flashes."""

from __future__ import annotations

import torch


def detect_frame_outliers(
    output: torch.Tensor,
    reference: torch.Tensor,
    *,
    luma_threshold: float = 0.20,
    difference_threshold: float = 0.12,
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
    if output.shape[0] < 3:
        return []

    out = output.detach().to(device="cpu", dtype=torch.float32).clamp(0, 1)
    ref = reference.detach().to(device="cpu", dtype=torch.float32).clamp(0, 1)
    weights = out.new_tensor((0.2126, 0.7152, 0.0722)).view(1, 3, 1, 1)
    out_luma = (out * weights).sum(1).mean((1, 2))
    ref_luma = (ref * weights).sum(1).mean((1, 2))
    out_diff = (out[1:-1] - (out[:-2] + out[2:]) * 0.5).abs().mean((1, 2, 3))
    ref_diff = (ref[1:-1] - (ref[:-2] + ref[2:]) * 0.5).abs().mean((1, 2, 3))
    out_jump = (out_luma[1:-1] - (out_luma[:-2] + out_luma[2:]) * 0.5).abs()
    ref_jump = (ref_luma[1:-1] - (ref_luma[:-2] + ref_luma[2:]) * 0.5).abs()
    out_vs_ref = (out[1:-1] - ref[1:-1]).abs().mean((1, 2, 3))
    flagged = (
        (out_jump >= luma_threshold)
        & (ref_jump < luma_threshold)
        & (out_diff >= difference_threshold)
        & (out_vs_ref >= difference_threshold)
        & (ref_diff < difference_threshold)
    )
    return (flagged.nonzero().flatten() + 1).tolist()
