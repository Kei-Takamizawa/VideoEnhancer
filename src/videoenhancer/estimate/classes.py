"""Classes used to keep local observations within measured job ranges."""

from fractions import Fraction
from typing import Any

from videoenhancer.media.timing import output_size


def output_class(media: dict[str, Any], settings: dict[str, Any]) -> str:
    normalized = {
        "width": 720,
        "height": 1280,
        **media,
        "display_width": media.get("display_width") or media.get("width", 720),
        "display_height": media.get("display_height") or media.get("height", 1280),
    }
    short = min(output_size(settings, normalized))
    return next((str(size) for size in (1080, 1440, 2160) if short <= size), "above2160")


def length_class(job: dict[str, Any]) -> str:
    media = job.get("media", {})
    frames = media.get("frame_count") or sum(
        part["end"] - part["start"] for part in job.get("segments", [])
    )
    seconds = float(Fraction(frames) / Fraction(str(media.get("cfr_fps", "30"))))
    return next((str(minutes) for minutes in (5, 30, 120) if seconds <= minutes * 60), "above120")
