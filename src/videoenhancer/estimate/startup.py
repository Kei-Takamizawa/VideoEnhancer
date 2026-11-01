"""Worker startup costs and the shared 50-successful-part lifecycle rule."""

from typing import Any

ESTIMATE_REVISION = "p1e3d2-warm1"


def startup_seconds(profile: dict[str, Any], preset: str, cold: bool = True) -> float:
    value = profile.get("startup_by_preset", {}).get(
        preset, profile.get("segment_overhead_seconds", 2.0)
    )
    if isinstance(value, dict):
        value = value.get(
            "cold" if cold else "warm",
            value.get("cold", profile.get("segment_overhead_seconds", 2.0)),
        )
    return float(value)


def cold_parts(manifest: dict[str, Any]) -> dict[int, bool]:
    """Plan replacements; runtime worker counts override the initial job plan."""
    used = 0
    result = {}
    runtime = manifest.get("timing", {}).get("worker_parts")
    first_pending = True
    for position, part in enumerate(manifest.get("segments", [])):
        index = int(part.get("index", position))
        if part.get("state") != "done" and first_pending:
            first_pending = False
            if runtime is not None:
                used = int(runtime)
            if manifest.get("state") in {"paused", "failed", "interrupted"}:
                used = 0
        kind = part.get("stats", {}).get("startup_kind")
        if part.get("state") == "failed" or part.get("startup_kind") == "cold":
            used = 0
        cold = used % 50 == 0
        if kind in {"cold", "warm"}:
            cold = kind == "cold"
        result[index] = cold
        used = 1 if cold else used + 1
        if part.get("stats", {}).get("spilled"):
            used = 0
    return result
