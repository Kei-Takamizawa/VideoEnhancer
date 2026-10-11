"""Retry short-lived Windows sharing violations without changing publication semantics."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


def retry_permission(operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    for delay in (0.2, 0.5, 1, 2, 4):
        try:
            return operation(*args, **kwargs)
        except PermissionError:
            time.sleep(delay)
    return operation(*args, **kwargs)
