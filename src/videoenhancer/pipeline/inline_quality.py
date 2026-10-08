"""Sampled pre-encode fidelity and every-frame summary diagnostics.

The development replay uses these same primitives; encoded replay additionally
includes codec loss. Temporal summaries reuse the detector's 16x16 RGB frames.
"""

from __future__ import annotations

import math
from typing import Any

import torch
import torch.nn.functional as F

STRIDE = 10  # Global output positions, restricted to source-aligned frames.


def luma(rgb: torch.Tensor) -> torch.Tensor:
    rgb = rgb.float().clamp(0, 1)
    return (rgb * rgb.new_tensor([0.2126, 0.7152, 0.0722]).view(3, 1, 1)).sum(-3)


def fidelity(reference: torch.Tensor, enhanced: torch.Tensor) -> tuple[float, float]:
    """Native-source resolution normalized BT.709 Y, 8x8 SSIM windows/stride 4."""
    if enhanced.shape[-2:] != reference.shape[-2:]:
        enhanced = F.interpolate(enhanced[None].float(), size=reference.shape[-2:], mode="area")[0]
    x, y = luma(reference)[None, None], luma(enhanced)[None, None]
    mse = (x - y).square().mean()

    kernel = min(8, *x.shape[-2:])

    def pool(value: torch.Tensor) -> torch.Tensor:
        return F.avg_pool2d(value, kernel, min(4, kernel))

    mx, my = pool(x), pool(y)
    vx, vy = (pool(x * x) - mx * mx).clamp_min(0), (pool(y * y) - my * my).clamp_min(0)
    bound = (vx * vy).sqrt()
    covariance = (pool(x * y) - mx * my).clamp(-bound, bound)
    ssim = ((2 * mx * my + 0.01**2) * (2 * covariance + 0.03**2)) / (
        (mx.square() + my.square() + 0.01**2) * (vx + vy + 0.03**2)
    )
    error, similarity = torch.stack((mse, ssim.mean())).cpu().tolist()
    return (-10 * math.log10(error) if error > 0 else math.inf), similarity


class FidelityAccumulator:
    def __init__(self) -> None:
        self.count = self.finite_count = 0
        self.psnr_sum = self.ssim_sum = 0.0
        self.psnr_min = math.inf
        self.ssim_min = 1.0

    def add(self, reference: torch.Tensor, enhanced: torch.Tensor) -> None:
        psnr, ssim = fidelity(reference, enhanced)
        self.count += 1
        if math.isfinite(psnr):
            self.finite_count += 1
            self.psnr_sum += psnr
        self.psnr_min = min(self.psnr_min, psnr)
        self.ssim_sum += ssim
        self.ssim_min = min(self.ssim_min, ssim)

    def partial(self) -> dict[str, Any]:
        return dict(
            count=self.count,
            finite_count=self.finite_count,
            psnr_sum=self.psnr_sum,
            psnr_min=self.psnr_min if math.isfinite(self.psnr_min) else None,
            ssim_sum=self.ssim_sum,
            ssim_min=self.ssim_min,
        )


def temporal_partial(
    summaries: dict[int, torch.Tensor], joints: set[int], excluded: set[int]
) -> dict[str, Any]:
    indices = sorted(summaries)
    if not indices:
        return {}
    images = luma(torch.stack([summaries[i] for i in indices]))
    differences = (images[1:] - images[:-1]).abs().flatten(1).mean(1).tolist()
    regular = [
        d
        for i, d in zip(indices[1:], differences, strict=True)
        if i not in joints and i not in excluded
    ]
    return dict(
        first_index=indices[0],
        last_index=indices[-1],
        first=images[0].tolist(),
        last=images[-1].tolist(),
        sum=sum(differences),
        count=len(differences),
        regular_sum=sum(regular),
        regular_count=len(regular),
        joints=[
            dict(frame_index=i, difference=d, excluded=i in excluded)
            for i, d in zip(indices[1:], differences, strict=True)
            if i in joints
        ],
    )


def _merge_temporal(
    parts: list[dict[str, Any]], joints: set[int], excluded: set[int]
) -> dict[str, Any]:
    total = count = regular_sum = regular_count = 0
    details: list[dict[str, Any]] = []
    previous = None
    for part in parts:
        if not part:
            continue
        total += part["sum"]
        count += part["count"]
        regular_sum += part["regular_sum"]
        regular_count += part["regular_count"]
        details.extend(part["joints"])
        if previous is not None:
            if previous["last_index"] + 1 != part["first_index"]:
                raise ValueError("Inline temporal summaries are not contiguous.")
            difference = float(
                (torch.tensor(part["first"]) - torch.tensor(previous["last"])).abs().mean()
            )
            index = part["first_index"]
            total += difference
            count += 1
            if index in joints:
                details.append(
                    dict(frame_index=index, difference=difference, excluded=index in excluded)
                )
            elif index not in excluded:
                regular_sum += difference
                regular_count += 1
        previous = part
    baseline = regular_sum / regular_count if regular_count else 0.0
    return dict(
        mean_difference=total / count if count else 0.0,
        baseline=baseline,
        regular_count=regular_count,
        details=details,
        count=count,
    )


def aggregate_quality(job: dict[str, Any]) -> dict[str, Any]:
    from fractions import Fraction

    from videoenhancer.media.timing import output_rate
    from videoenhancer.pipeline.quality import _ratio

    factor = int(output_rate(job["settings"], job["media"]) / Fraction(job["media"]["cfr_fps"]))
    segments = job["segments"]
    parts = [s.get("stats", {}).get("inline_quality") for s in segments]
    if any(p is None for p in parts):
        return {
            "available": False,
            "reason": "Segments predate inline quality; use report --full-quality.",
        }
    clips = {factor * i for s in segments for i in s.get("stats", {}).get("clip_joints", [])}
    boundaries = {factor * s["start"] for s in segments[1:]}
    joints = clips | boundaries
    source_excluded = {
        i for cut in job.get("scene_cuts", []) for i in (cut - 1, cut, cut + 1) if i >= 0
    }
    excluded = {i * factor + phase for i in source_excluded for phase in range(factor)}
    source = _merge_temporal(
        [p["source"] for p in parts if p], {i // factor for i in joints}, source_excluded
    )
    output = _merge_temporal([p["output"] for p in parts if p], joints, excluded)
    fps = [p["fidelity"] for p in parts if p]
    count = sum(p["count"] for p in fps)
    finite = sum(p["finite_count"] for p in fps)
    psnr_min = min((p["psnr_min"] for p in fps if p["psnr_min"] is not None), default=None)

    def seam(selected: set[int]) -> float | None:
        values = [
            d["difference"] for d in output["details"] if d["frame_index"] in selected - excluded
        ]
        return (
            _ratio(sum(values) / len(values), output["baseline"])
            if values and output["regular_count"]
            else None
        )

    originals = {d["frame_index"]: d for d in source["details"]}
    diagnostics = []
    for detail in output["details"]:
        index = detail["frame_index"]
        source_ratio = _ratio(
            originals.get(index // factor, {}).get("difference", 0), source["baseline"]
        )
        out_ratio = _ratio(detail["difference"], output["baseline"])
        diagnostics.append(
            {
                **detail,
                "source_frame_index": index // factor,
                "joint_ratio": out_ratio,
                "source_joint_ratio": source_ratio,
                "relative_seam": _ratio(out_ratio, source_ratio)
                if out_ratio is not None and source_ratio is not None
                else None,
                "excluded_for_scene_cut": index in excluded,
                "clip_joint": index in clips,
                "segment_joint": index in boundaries,
            }
        )
    return dict(
        available=True,
        fidelity_frames=count,
        fidelity_stride_output_frames=STRIDE,
        psnr_y_mean_db=sum(p["psnr_sum"] for p in fps) / count
        if count and finite == count
        else None,
        psnr_y_min_db=psnr_min,
        ssim_y_mean=sum(p["ssim_sum"] for p in fps) / count if count else None,
        ssim_y_min=min((p["ssim_min"] for p in fps if p["count"]), default=None),
        flicker_ratio=_ratio(output["mean_difference"], source["mean_difference"]),
        seam_ratio=seam(joints),
        clip_seam_ratio=seam(clips),
        segment_seam_ratio=seam(boundaries),
        clip_joint_count=len(clips),
        segment_joint_count=len(boundaries),
        excluded_joint_count=len(joints & excluded),
        noncut_joint_count=len(joints - excluded),
        joint_diagnostics=diagnostics,
        method="Pre-encode normalized BT.709 Y; area resize to source for PSNR/SSIM; "
        "8x8 SSIM windows, stride 4; fidelity every 10th global output frame "
        "that is source-aligned; temporal every frame on existing 16x16 detector summaries; "
        "cut exclusion +/-1 source frame; codec loss excluded.",
    )
