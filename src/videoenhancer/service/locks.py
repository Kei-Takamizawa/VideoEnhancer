"""Service lock order: mutation (10), published events (20), memory state (30)."""

import threading
import time
import traceback
from typing import Any

_held = threading.local()


class OrderedLock:
    def __init__(self, name: str, rank: int, check: bool = False):
        self.name, self.rank, self.check = name, rank, check
        self._lock = threading.RLock()
        self.owner: int | None = None
        self.depth = 0
        self.since = 0.0
        self.stack = ""
        self.warned = False

    def __enter__(self) -> "OrderedLock":
        held = getattr(_held, "locks", [])
        if self.check and self not in held and any(lock.rank > self.rank for lock in held):
            raise RuntimeError(f"Lock order inversion: {held[-1].name} -> {self.name}")
        self._lock.acquire()
        if self.depth == 0:
            self.owner, self.since = threading.get_ident(), time.monotonic()
            self.stack = "".join(traceback.format_stack(limit=20))
            self.warned = False
        self.depth += 1
        _held.locks = [*held, self]
        return self

    def __exit__(self, *_: Any) -> None:
        held = getattr(_held, "locks", [])
        if not held or held[-1] is not self:
            raise RuntimeError(f"Unbalanced lock release: {self.name}")
        _held.locks = held[:-1]
        self.depth -= 1
        if not self.depth:
            self.owner = None
        self._lock.release()


def assert_io_unlocked() -> None:
    forbidden = [lock.name for lock in getattr(_held, "locks", []) if lock.rank >= 20]
    if forbidden:
        raise RuntimeError(f"File operation while holding state locks: {forbidden}")
