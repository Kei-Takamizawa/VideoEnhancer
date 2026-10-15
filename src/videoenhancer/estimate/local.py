"""Bounded local timing observations; no media names or paths are stored here."""

import json
import math
import statistics
from pathlib import Path
from typing import Any

from videoenhancer.estimate.classes import length_class, output_class
from videoenhancer.service.settings import write_json


def _key(profile: dict[str, Any]) -> list[Any]:
    key = [
        profile.get("backend"),
        profile.get("gpu_name"),
        profile.get("current_driver", profile.get("driver")),
    ]
    return [*key, profile["estimate_revision"]] if profile.get("estimate_revision") else key


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
    result.pop("finalization_correction", None)
    corrections = dict(result.get("finalization_corrections", {}))
    for bucket in ("5", "30", "120", "above120"):
        values = [
            row["finalization_correction"]
            for row in observations
            if row.get("finalization_length_class") == bucket
            and isinstance(row.get("finalization_correction"), (int, float))
            and math.isfinite(row["finalization_correction"])
            and row["finalization_correction"] > 0
        ]
        if values:
            corrections[bucket] = statistics.median(values[-5:])
    result["finalization_corrections"] = corrections
    for field in ("analysis_seconds_per_frame",):
        values = [
            row[field]
            for row in observations
            if isinstance(row.get(field), (int, float))
            and math.isfinite(row[field])
            and row[field] > 0
        ]
        if values:
            result[field] = statistics.median(values[-5:])
    startups = [
        float(sample)
        for row in observations
        for sample in row.get("startup_samples", [])
        if isinstance(sample, (int, float)) and math.isfinite(sample) and sample > 0
    ]
    if startups:
        result["segment_overhead_seconds"] = statistics.median(startups[-20:])
        result["startup_includes_model_loading"] = True
    startup_by_preset = dict(result.get("startup_by_preset", {}))
    for mode in {row.get("mode") for row in observations}:
        samples = [
            float(sample)
            for row in observations
            if row.get("mode") == mode
            for sample in row.get("startup_samples", [])
            if isinstance(sample, (int, float)) and math.isfinite(sample) and sample > 0
        ]
        if mode and samples:
            startup_by_preset[mode] = statistics.median(samples[-20:])
    result["startup_by_preset"] = startup_by_preset
    return result


def recent_correction(
    store: Any,
    mode: str,
    profile: dict[str, Any] | None,
    media: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
) -> float:
    size = output_class(media or {}, settings or {})
    values = [
        row["correction"]
        for row in read_local(store.home, profile).get("jobs", [])
        if row.get("mode") == mode and row.get("output_class") == size
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
            and output_class(job.get("media", {}), job["settings"]) == size
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
        "output_class": output_class(manifest["media"], manifest["settings"]),
        "correction": manifest.get("correction_factor", 1),
    }
    frames = max(1, manifest["media"].get("frame_count", 1))
    if manifest.get("analysis_seconds"):
        row["analysis_seconds_per_frame"] = manifest["analysis_seconds"] / frames
    overheads = [
        segment.get("stats", {}).get("per_part_startup_seconds", 0)
        for segment in manifest["segments"]
    ]
    measured_overheads = [value for value in overheads if value > 0]
    if measured_overheads:
        row["startup_samples"] = measured_overheads[-20:]
        row["segment_overhead_seconds"] = statistics.median(measured_overheads[-20:])
    final = manifest.get("timing", {}).get("finalization_observation", {})
    if final.get("predicted", 0) > 0:
        bucket = length_class(manifest)
        row["finalization_length_class"] = bucket
        row["finalization_correction"] = max(
            0.1,
            final["actual"]
            / final["predicted"]
            * profile.get("finalization_corrections", {}).get(bucket, 1),
        )
    rows.append(row)
    write_json(home / "timing-observations.json", {"machine": _key(profile), "jobs": rows[-20:]})
