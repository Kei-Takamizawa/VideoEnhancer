"""Only placeholder presets are registered during P0."""

from collections.abc import Callable
from fractions import Fraction
from typing import Any

from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.pipeline.stages import Blend2xStage, ResizeStage, Stage

PresetFactory = Callable[[dict[str, Any], dict[str, Any], set[int]], list[Stage]]


def _placeholder(settings: dict[str, Any], media: dict[str, Any], cuts: set[int]) -> list[Stage]:
    stages: list[Stage] = []
    if settings["preset"] != "passthrough":
        stages.append(ResizeStage(*output_size(settings, media)))
    if output_rate(settings, media) == Fraction(media["cfr_fps"]) * 2:
        stages.append(Blend2xStage(Fraction(media["cfr_fps"]), cuts))
    return stages


PRESETS: dict[str, PresetFactory] = {
    name: _placeholder for name in ("passthrough", "resize", "p0-test")
}


def create_stages(settings: dict[str, Any], media: dict[str, Any], cuts: set[int]) -> list[Stage]:
    return PRESETS[settings["preset"]](settings, media, cuts)
