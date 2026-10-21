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
    "cleanup_working_files": True,
    "output_folder": "",
    "preset": "standard",
    "codec": "hevc",
    "short_side": 1080,
    "fps": "2x",
    "start_with_windows": False,
    "theme": "system",
    "zoom": 100,
    "tray_explained": False,
    "tour_completed": False,
    "delete_original_after": False,
    "log_folder": "",
    "advanced": {},
    "seen_failures": [],
    "restore_model": "",
    "interp_model": "",
    "size_model": "",
    "restore_strength": "medium",
    "size_strength": 0.2,
    "video_download_folder": "",
    "video_download_limit": 2,
}


def read_settings(home: Path) -> dict[str, Any]:
    path = home / "settings.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if saved.get("short_side") == 2160:
        saved["short_side"] = 1440
        write_json(path, saved)
        from videoenhancer.logging import get_logger

        get_logger(home).info("Changed the saved default output size from 2160p to 1440p.")
    return {**DEFAULTS, **saved}


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
    if "cleanup_working_files" in value and not isinstance(value["cleanup_working_files"], bool):
        raise ValueError("Automatic cleanup must be on or off.")
    previous = read_settings(home)
    value = {**previous, **value}
    if type(value["video_download_limit"]) is not int or value["video_download_limit"] not in {
        1,
        2,
        3,
    }:
        raise ValueError("Simultaneous video downloads must be 1, 2 or 3.")
    download_folder = value["video_download_folder"]
    if (
        not isinstance(download_folder, str)
        or download_folder
        and not Path(download_folder).is_absolute()
    ):
        raise ValueError("Choose an absolute video-download folder.")
    choices = {
        "preset": {"standard", "fast"},
        "codec": {"h264", "hevc", "av1"},
        "short_side": {"keep", 1080, 1440},
        "fps": {"off", "2x"},
        "theme": {"system", "dark", "light"},
        "zoom": {80, 90, 100, 110, 125, 150},
        "restore_strength": {"light", "medium", "strong"},
        "size_strength": {0.2, 0.6},
    }
    for key, allowed in choices.items():
        if value[key] not in allowed:
            raise ValueError(f"Invalid {key}.")
    if not isinstance(value["start_with_windows"], bool):
        raise ValueError("Start with Windows must be on or off.")
    if not isinstance(value["tray_explained"], bool):
        raise ValueError("Tray explanation must be on or off.")
    if not isinstance(value["tour_completed"], bool):
        raise ValueError("Tour completion must be on or off.")
    if not isinstance(value["delete_original_after"], bool):
        raise ValueError("Delete original after processing must be on or off.")
    if not isinstance(value["seen_failures"], list) or any(
        not isinstance(item, str) or len(item) > 80 for item in value["seen_failures"]
    ):
        raise ValueError("Seen failures must be a list of job ids.")
    value["seen_failures"] = list(
        dict.fromkeys([*previous["seen_failures"], *value["seen_failures"]])
    )
    for key in ("output_folder", "log_folder"):
        if not isinstance(value[key], str) or (value[key] and not Path(value[key]).is_absolute()):
            raise ValueError(f"{key} must be an absolute folder path.")
    from videoenhancer.models.registry import ModelRegistry

    for key, task in (
        ("restore_model", "restore"),
        ("interp_model", "interpolate"),
        ("size_model", "size"),
    ):
        if not isinstance(value[key], str):
            raise ValueError(f"{key} must be a model id.")
        if value[key]:
            registry = ModelRegistry(home)
            registry.weights(registry.manifest(value[key], task), download=False)
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
