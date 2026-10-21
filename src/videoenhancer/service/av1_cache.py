"""Persist encoder probes for the exact GPU and driver pair."""

import json
from pathlib import Path
from typing import Any

from videoenhancer.service.settings import write_json


def capabilities(home: Path, gpu: str, driver: str) -> dict[str, Any]:
    from videoenhancer.media.encode import av1_minimum_size, probe_av1

    path = home / "av1-capabilities.json"
    key = {"gpu": gpu, "driver": driver, "schema": 1}
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if (
            cached["key"] == key
            and isinstance(cached["value"]["av1_supported"], bool)
            and (
                not cached["value"]["av1_supported"]
                or all(
                    isinstance(cached["value"].get(k), int) and cached["value"][k] > 0
                    for k in ("av1_min_width", "av1_min_height")
                )
            )
        ):
            return cached["value"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    supported, reason = probe_av1()
    value: dict[str, Any] = dict(av1_supported=supported, av1_unavailable_reason=reason)
    if supported:
        width, height = av1_minimum_size()
        value.update(av1_min_width=width, av1_min_height=height)
    if gpu and driver:
        write_json(path, dict(key=key, value=value))
    return value
