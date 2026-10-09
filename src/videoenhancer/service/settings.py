"""Validated desktop preferences; engine defaults remain unchanged."""

from __future__ import annotations

import json
import math
import os
import uuid
from pathlib import Path
from typing import Any

from videoenhancer.files import retry_permission

DEFAULTS: dict[str, Any] = {
    "output_folder": "",
    "preset": "standard",
    "codec": "hevc",
    "short_side": 1080,
    "fps": "2x",
    "start_with_windows": False,
    "theme": "system",
    "log_folder": "",
    "advanced": {},
}


def read_settings(home: Path) -> dict[str, Any]:
    path = home / "settings.json"
    return {**DEFAULTS, **(json.loads(path.read_text()) if path.exists() else {})}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        retry_permission(temporary.replace, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_settings(home: Path, value: dict[str, Any]) -> dict[str, Any]:
    if set(value) - set(DEFAULTS):
        raise ValueError("Unknown setting.")
    value = {**read_settings(home), **value}
    choices = {
        "preset": {"standard", "fast"},
        "codec": {"h264", "hevc", "av1"},
        "short_side": {"keep", 1080, 1440, 2160},
        "fps": {"off", "2x"},
        "theme": {"system", "dark", "light"},
    }
    for key, allowed in choices.items():
        if value[key] not in allowed:
            raise ValueError(f"Invalid {key}.")
    if not isinstance(value["start_with_windows"], bool):
        raise ValueError("Start with Windows must be on or off.")
    for key in ("output_folder", "log_folder"):
        if not isinstance(value[key], str) or (value[key] and not Path(value[key]).is_absolute()):
            raise ValueError(f"{key} must be an absolute folder path.")
    advanced = value["advanced"]
    if not isinstance(advanced, dict) or set(advanced) - {
        "clip_length",
        "clip_overlap",
        "interpolation_safety_threshold",
    }:
        raise ValueError("Unknown advanced setting.")
    length = advanced.get("clip_length", 15)
    overlap = advanced.get("clip_overlap", 2)
    if not isinstance(length, int) or not isinstance(overlap, int) or not 3 <= length <= 100:
        raise ValueError("Clip length must be 3–100 frames; overlap must be an integer.")
    if not 0 <= 2 * overlap < length:
        raise ValueError("Overlap must be nonnegative and less than half the clip length.")
    threshold = float(advanced.get("interpolation_safety_threshold", 0.20))
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Interpolation threshold must be between 0 and 1.")
    write_json(home / "settings.json", value)
    return value
