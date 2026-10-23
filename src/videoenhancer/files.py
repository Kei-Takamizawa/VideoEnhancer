"""Retry short-lived Windows sharing violations without changing publication semantics."""

from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


@contextmanager
def temporary_folder(prefix: str) -> Iterator[Path]:
    """Use inherited directory ACLs; Windows treats mode 0o700 specially."""
    folder = Path(tempfile.gettempdir()) / f"{prefix}{uuid.uuid4().hex}"
    folder.mkdir(mode=0o777)
    try:
        yield folder
    finally:
        shutil.rmtree(folder)


def retry_permission(operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    for delay in (0.2, 0.5, 1, 2, 4):
        try:
            return operation(*args, **kwargs)
        except PermissionError:
            time.sleep(delay)
    return operation(*args, **kwargs)
