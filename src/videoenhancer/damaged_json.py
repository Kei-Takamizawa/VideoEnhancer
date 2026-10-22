"""Session notices for damaged JSON; readers never modify the source file."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_errors: dict[Path, dict[str, str]] = {}


def record(home: Path, path: Path, error: Exception) -> None:
    path = path.resolve()
    with _lock:
        if path in _errors:
            return
        _errors[path] = {"home": str(home.resolve()), "path": str(path), "error": str(error)}
    from videoenhancer.logging import get_logger

    get_logger(home).warning("Skipped damaged JSON file %s: %s", path, error)


def notices(home: Path) -> list[dict[str, str]]:
    with _lock:
        return [dict(value) for value in _errors.values() if value["home"] == str(home.resolve())]


def read_object(path: Path, home: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object at the top level.")
        return value
    except (ValueError, UnicodeError) as error:
        record(home, path, error)
        raise
