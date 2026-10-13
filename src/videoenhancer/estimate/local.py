"""Bounded local timing observations; no media names or paths are stored here."""

import json
import math
import statistics
from pathlib import Path
from typing import Any

from videoenhancer.service.settings import write_json


def _key(profile: dict[str, Any]) -> list[Any]:
    return [
        profile.get("backend"),
        profile.get("gpu_name"),
        profile.get("current_driver", profile.get("driver")),
    ]


def read_local(home: Path, profile: dict[str, Any] | None) -> dict[str, Any]:
    try:
        value = json.loads((home / "timing-observations.json").read_text(encoding="utf-8"))
        return (
            value
            if isinstance(value, dict)
            and value.get("machine") == _key(profile or {})
            and isinstance(value.get("jobs"), list)
            and all(isinstance(row, dict) for row in value["jobs"])
            else {}
        )
    except (OSError, ValueError):
        return {}


def apply_local(home: Path, profile: dict[str, Any]) -> dict[str, Any]:
    observations = read_local(home, profile).get("jobs", [])
    if not observations:
        return profile
    result = dict(profile)
    for field in (
        "analysis_seconds_per_frame",
        "segment_overhead_seconds",
        "finalization_correction",
    ):
        values = [
            row[field]
            for row in observations
            if isinstance(row.get(field), (int, float))
            and math.isfinite(row[field])
            and row[field] > 0
        ]
        if values:
            result[field] = statistics.median(values[-5:])
    return result


def recent_correction(store: Any, mode: str, profile: dict[str, Any] | None) -> float:
    values = [
        row["correction"]
        for row in read_local(store.home, profile).get("jobs", [])
        if row.get("mode") == mode
    ]
    if not values:
        values = [
            job.get("correction_factor", 1)
            for job in sorted(
                store.list_jobs(include_analysis=False),
                key=lambda job: job.get("finished_at", job.get("updated_at", "")),
            )
            if job["state"] == "done"
            and job["settings"].get("preset") == mode
            and _key(job.get("machine_profile") or {}) == _key(profile or {})
        ]
    valid = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(value) and value > 0
    ]
    return statistics.median(valid[-5:]) if valid else 1.0


def record_completed(manifest: dict[str, Any], home: Path) -> None:
    profile = manifest.get("machine_profile") or {}
    value = read_local(home, profile)
    rows = [row for row in value.get("jobs", []) if row.get("id") != manifest["id"]]
    row: dict[str, Any] = {
        "id": manifest["id"],
        "mode": manifest["settings"].get("preset"),
        "correction": manifest.get("correction_factor", 1),
    }
    frames = max(1, manifest["media"].get("frame_count", 1))
    if manifest.get("analysis_seconds"):
        row["analysis_seconds_per_frame"] = manifest["analysis_seconds"] / frames
    overheads = [
        segment.get("stats", {}).get("child_startup_seconds", 0)
        + segment.get("stats", {}).get("decoder_open_seconds", 0)
        for segment in manifest["segments"]
    ]
    if any(overheads):
        row["segment_overhead_seconds"] = statistics.median(overheads)
    final = manifest.get("timing", {}).get("finalization_observation", {})
    if final.get("predicted", 0) > 0:
        row["finalization_correction"] = max(
            0.1, final["actual"] / final["predicted"] * profile.get("finalization_correction", 1)
        )
    rows.append(row)
    write_json(home / "timing-observations.json", {"machine": _key(profile), "jobs": rows[-20:]})
