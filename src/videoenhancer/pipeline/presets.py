"""Register placeholder P0 and model-backed P1a presets."""

from collections.abc import Callable
from fractions import Fraction
from typing import Any

from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.pipeline.stages import Blend2xStage, ResizeStage, Stage

PresetFactory = Callable[[dict[str, Any], dict[str, Any], set[int]], list[Stage]]


def _placeholder(settings: dict[str, Any], media: dict[str, Any], cuts: set[int]) -> list[Stage]:
    if settings.get("restore_model"):
        return _real(settings, media, cuts)
    stages: list[Stage] = []
    if settings["preset"] != "passthrough":
        stages.append(ResizeStage(*output_size(settings, media)))
    if output_rate(settings, media) == Fraction(media["cfr_fps"]) * 2:
        stages.append(Blend2xStage(Fraction(media["cfr_fps"]), cuts))
    return stages


def _real(settings: dict[str, Any], media: dict[str, Any], cuts: set[int]) -> list[Stage]:
    """Build the real preset stages; model-backed stages load lazily at setup."""
    from videoenhancer.models.registry import ModelRegistry, selected_models

    preset = settings["preset"]
    selected = selected_models(settings, media)
    registry = ModelRegistry()
    rate = Fraction(media["cfr_fps"])
    stages: list[Stage] = []
    if "restore" in selected:
        stages.append(registry.create_stage(selected["restore"], "restore", settings, rate, cuts))
    if preset != "passthrough":
        stages.append(ResizeStage(*output_size(settings, media)))
    if output_rate(settings, media) == Fraction(media["cfr_fps"]) * 2:
        if preset in {"fast", "standard"}:
            stages.append(
                registry.create_stage(selected["interpolate"], "interpolate", settings, rate, cuts)
            )
        else:
            stages.append(Blend2xStage(Fraction(media["cfr_fps"]), cuts))
    return stages


PRESETS: dict[str, PresetFactory] = {
    **{name: _placeholder for name in ("passthrough", "resize", "p0-test")},
    "fast": _real,
    "standard": _real,
}


def create_stages(settings: dict[str, Any], media: dict[str, Any], cuts: set[int]) -> list[Stage]:
    return PRESETS[settings["preset"]](settings, media, cuts)
