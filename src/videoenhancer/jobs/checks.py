"""Shared blocking geometry checks for API and CLI additions."""

from pathlib import Path
from typing import Any

from videoenhancer.media.timing import output_size
from videoenhancer.models.registry import ModelRegistry, selected_models


def geometry_warning(
    home: Path, media: dict[str, Any], settings: dict[str, Any], capabilities: dict[str, Any]
) -> str | None:
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
        source_short = min(
            media.get("display_width", media["width"]), media.get("display_height", media["height"])
        )
        memory = capabilities.get("vram_bytes")
        if (
            settings.get("preset") == "standard"
            and source_short >= 2160
            and memory
            and memory <= 8 * 1024**3
        ):
            return "Standard can't run at this size on this GPU yet. Fast works."
        width, height = output_size(settings, media)
        if min(width, height) < 256:
            return (
                f"Output too small for cleanup: {width} x {height}. "
                "This restoration model requires at least 256 pixels on both sides. "
                "Choose 1080 instead of Keep."
            )
    return None
