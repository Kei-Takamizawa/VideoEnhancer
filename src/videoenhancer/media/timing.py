"""Exact output geometry and timing rules."""

from fractions import Fraction
from typing import Any


def output_rate(settings: dict[str, Any], media: dict[str, Any]) -> Fraction:
    rate = Fraction(media["cfr_fps"])
    if (
        settings.get("fps", "2x") == "2x"
        and settings.get("preset", "p0-test") in {"p0-test", "fast", "standard"}
        and rate <= 30
    ):
        return min(rate * 2, Fraction(60))
    return rate


def output_size(settings: dict[str, Any], media: dict[str, Any]) -> tuple[int, int]:
    width, height = int(media["display_width"]), int(media["display_height"])
    target = settings.get("short_side", 1080)
    if (
        settings.get("preset") == "passthrough"
        or target == "keep"
        or min(width, height) >= int(target)
    ):
        return width + width % 2, height + height % 2
    scale = int(target) / min(width, height)
    return max(2, round(width * scale / 2) * 2), max(2, round(height * scale / 2) * 2)


def nearest_mapping(pts: list[Fraction], duration: Fraction, rate: Fraction) -> list[int]:
    if not pts:
        raise ValueError("The input has no presentation timestamps.")
    origin = pts[0]
    normalized = [p - origin for p in pts]
    count = max(1, round(duration * rate))
    cursor = 0
    mapping = []
    for index in range(count):
        target = Fraction(index, 1) / rate
        while cursor + 1 < len(pts) and abs(normalized[cursor + 1] - target) < abs(
            normalized[cursor] - target
        ):
            cursor += 1
        mapping.append(cursor)
    return mapping
