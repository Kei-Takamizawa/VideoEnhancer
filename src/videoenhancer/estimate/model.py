"""Pixel/frame cost estimates; defaults are conservative, not measurements."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any

from videoenhancer.media.timing import output_rate, output_size

# Seconds per megapixel-frame. Calibration replaces these provisional values.
DEFAULT_COMPONENTS = {
    "cpu": {
        "decode": 0.018,
        "color": 0.025,
        "resize": 0.04,
        "blend2x": 0.025,
        "restore": 0.32,
        "interpolate": 0.046,
        "encode": 0.15,
    },
    "cuda": {
        "decode": 0.004,
        "color": 0.004,
        "resize": 0.005,
        "blend2x": 0.003,
        "restore": 0.32,
        "interpolate": 0.046,
        "encode": 0.008,
    },
}


@dataclass(frozen=True)
class Estimate:
    seconds: float
    low: float
    high: float
    calibrated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _geometry(media: dict[str, Any], settings: dict[str, Any]) -> tuple[int, int, float]:
    width = int(media.get("display_width") or media.get("width", 720))
    height = int(media.get("display_height") or media.get("height", 1280))
    if width <= 0 or height <= 0:
        raise ValueError("Media dimensions must be positive.")
    normalized = {
        **media,
        "display_width": width,
        "display_height": height,
        "cfr_fps": str(media.get("cfr_fps") or media.get("average_fps") or "30"),
    }
    output_width, output_height = output_size(settings, normalized)
    rate = Fraction(normalized["cfr_fps"])
    if rate <= 0:
        raise ValueError("Media frame rate must be positive.")
    multiplier = float(output_rate(settings, normalized) / rate)
    coded_pixels = int(media.get("width", width)) * int(media.get("height", height))
    return coded_pixels, output_width * output_height, multiplier


def _coefficient(name: str, backend: str, profile: dict[str, Any] | None) -> float:
    default = DEFAULT_COMPONENTS.get(backend, DEFAULT_COMPONENTS["cpu"])[name] / 1_000_000
    if not profile:
        return default
    component = profile.get("components", {}).get(name)
    if isinstance(component, dict):
        value = component.get("seconds_per_pixel_frame", default)
    elif isinstance(component, (float, int)):
        value = component
    else:
        value = default
    if value is None:
        return default
    value = float(value)
    if value < 0 or not math.isfinite(value):
        raise ValueError(f"Invalid calibrated cost for {name}.")
    return value


def predict_segment(
    media: dict[str, Any],
    settings: dict[str, Any],
    frames: int,
    profile: dict[str, Any] | None = None,
    correction: float = 1.0,
) -> float:
    if frames < 0 or correction <= 0 or not math.isfinite(correction):
        raise ValueError("Frame count must be nonnegative and correction must be positive.")
    if frames == 0:
        return 0.0
    input_pixels, output_pixels, multiplier = _geometry(media, settings)
    backend = settings.get("backend", "cuda")
    costs = [
        _coefficient("decode", backend, profile) * input_pixels,
        _coefficient("color", backend, profile) * (input_pixels + output_pixels * multiplier),
        _coefficient("encode", backend, profile) * output_pixels * multiplier,
    ]
    preset = settings.get("preset", "standard")
    if preset in ("resize", "p0-test", "fast", "standard"):
        costs.append(_coefficient("resize", backend, profile) * output_pixels)
    normalized_pixels = int(media.get("display_width", media.get("width", 720))) * int(
        media.get("display_height", media.get("height", 1280))
    )
    if normalized_pixels != input_pixels:
        costs.append(_coefficient("resize", backend, profile) * normalized_pixels)
    if preset == "standard":
        costs.append(_coefficient("restore", backend, profile) * input_pixels)
    if multiplier > 1:
        component = "interpolate" if preset in ("fast", "standard") else "blend2x"
        costs.append(_coefficient(component, backend, profile) * output_pixels)
    # Sum is deliberately conservative before end-to-end overlap is calibrated.
    overhead = float((profile or {}).get("segment_overhead_seconds", 2.0))
    if overhead < 0 or not math.isfinite(overhead):
        raise ValueError("Segment overhead must be finite and nonnegative.")
    return (sum(costs) * frames + overhead) * correction


def _ratios(manifest: dict[str, Any]) -> list[float]:
    ratios = []
    for value in manifest.get("timing", {}).get("observations", []):
        if isinstance(value, dict):
            predicted = float(value.get("predicted", 0))
            actual = float(value.get("actual", 0))
            ratio = actual / predicted if predicted > 0 else 0
        else:
            ratio = float(value)
        if ratio > 0 and math.isfinite(ratio):
            ratios.append(ratio)
    return ratios


def estimate_job(manifest: dict[str, Any], profile: dict[str, Any] | None = None) -> Estimate:
    if profile is None:
        profile = manifest.get("machine_profile")
    correction = float(manifest.get("correction_factor", 1.0))
    media, settings = manifest.get("media", {}), manifest.get("settings", {})
    seconds = sum(
        predict_segment(media, settings, int(s["end"]) - int(s["start"]), profile, correction)
        for s in manifest.get("segments", [])
        if s.get("state", "pending") != "done"
    )
    ratios = _ratios(manifest)
    uncertainty = 0.25
    if len(ratios) >= 2:
        relative_std = statistics.stdev(ratios) / statistics.mean(ratios)
        # Keep a small uncertainty floor and avoid a falsely precise first observation.
        uncertainty = min(0.25, max(0.05, relative_std * 1.96, 0.25 / math.sqrt(len(ratios))))
    components = (profile or {}).get("components", {})
    needed = {"decode", "color", "encode"}
    preset = settings.get("preset", "standard")
    if preset in ("resize", "p0-test", "fast", "standard"):
        needed.add("resize")
    if preset == "standard":
        needed.add("restore")
    if (
        int(media.get("display_width", media.get("width", 720)))
        * int(media.get("display_height", media.get("height", 1280)))
        != _geometry(media, settings)[0]
    ):
        needed.add("resize")
    if _geometry(media, settings)[2] > 1:
        needed.add("interpolate" if preset in ("fast", "standard") else "blend2x")

    def measured(name: str) -> bool:
        value = components.get(name)
        if isinstance(value, dict):
            value = value.get("seconds_per_pixel_frame")
        return isinstance(value, (int, float)) and math.isfinite(value) and value >= 0

    calibrated = bool(profile) and all(measured(name) for name in needed)
    return Estimate(seconds, seconds * (1 - uncertainty), seconds * (1 + uncertainty), calibrated)


def update_correction(manifest: dict[str, Any], predicted: float, actual: float) -> None:
    """Update EMA from the corrected prediction used when admitting this segment."""
    if predicted <= 0 or actual < 0 or not all(map(math.isfinite, (predicted, actual))):
        raise ValueError("Observed timing needs a positive prediction and nonnegative actual time.")
    current = float(manifest.get("correction_factor", 1.0))
    ratio = actual / predicted
    baseline_ratio = current * ratio
    manifest["correction_factor"] = 0.7 * current + 0.3 * baseline_ratio
    manifest.setdefault("timing", {}).setdefault("observations", []).append(
        {"predicted": predicted / current, "actual": actual}
    )
