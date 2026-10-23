"""Shared input color-depth admission, including link metadata."""

import re
from typing import Any


def color_depth(media: dict[str, Any]) -> int:
    values = []
    for key in ("bit_depth", "bits_per_raw_sample", "bits_per_sample", "color_depth"):
        try:
            values.append(int(media.get(key) or 0))
        except (ValueError, TypeError):
            pass
    pixel = str(media.get("pixel_format") or media.get("pix_fmt") or "")
    match = re.search(r"(?:p0|p|gray)(10|12|14|16)(?:le|be|$)", pixel)
    if match:
        values.append(int(match[1]))
    return max(values, default=0) or 8


def color_warning(media: dict[str, Any]) -> str | None:
    depth = color_depth(media)
    if depth > 10:
        return (
            f"This video uses {depth}-bit color. "
            "VideoEnhancer accepts 8-bit and 10-bit videos only."
        )
    return None
