"""Shared blocking geometry checks for API and CLI additions."""

from fractions import Fraction
from pathlib import Path
from typing import Any

from videoenhancer.media.admission import color_warning
from videoenhancer.media.timing import output_size
from videoenhancer.models.registry import ModelRegistry, selected_models


def source_warning(media: dict[str, Any]) -> str | None:
    if reason := color_warning(media):
        return reason
    width = int(media.get("display_width") or media.get("width") or 0)
    height = int(media.get("display_height") or media.get("height") or 0)
    short = min(width, height)
    # The processing projection rounds square pixels to even widths. Admission
    # must still reject an actual 1081-pixel source rounded down to 1080 there.
    if (
        Fraction(
            str(media.get("sample_aspect_ratio") or media.get("sar") or "1:1").replace(":", "/")
        )
        == 1
    ):
        short = max(short, min(int(media.get("width") or 0), int(media.get("height") or 0)))
    if short > 1080:
        return (
            f"This video is larger than 1080p (short side {short} px). "
            "VideoEnhancer processes videos up to 1080p."
        )
    return None


def job_support_reason(job: dict[str, Any]) -> str | None:
    source = source_warning(job.get("media", {}))
    if source:
        return source
    target = job.get("settings", {}).get("short_side", 1080)
    if target != "keep" and int(target) > 1440:
        return (
            f"{target}p output is no longer available. Choose Keep, 1080p or 1440p for a new video."
        )
    return None


def geometry_warning(
    home: Path, media: dict[str, Any], settings: dict[str, Any], capabilities: dict[str, Any]
) -> str | None:
    unsupported = job_support_reason({"media": media, "settings": settings})
    if unsupported:
        return unsupported
    if settings.get("codec") == "av1":
        if settings.get("backend") != "cuda":
            return "AV1 requires CUDA hardware encoding. Choose HEVC instead."
        if not capabilities.get("av1_min_width") or not capabilities.get("av1_min_height"):
            return "AV1 output limits are not available yet. Try again after the hardware check."
        width, height = output_size(settings, media)
        if width < capabilities["av1_min_width"] or height < capabilities["av1_min_height"]:
            return "Output too small for AV1. Choose HEVC or a larger size."
    restore = selected_models(settings).get("restore")
    if restore and ModelRegistry(home).manifest(restore, "restore")["architecture"] == "basicvsrpp":
        width, height = output_size(settings, media)
        if min(width, height) < 256:
            return (
                f"Output too small for cleanup: {width} x {height}. "
                "This restoration model requires at least 256 pixels on both sides. "
                "Choose 1080 instead of Keep."
            )
    return None
