"""Bounded, CPU-owned decoded ranges for one isolated Compare worker."""

import json
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from typing import Any

import torch

from videoenhancer.pipeline.session import PipelineSession


class DecodedRanges:
    def __init__(self, limit: int = 1_000_000_000) -> None:
        self.limit = limit
        self.ranges: OrderedDict[tuple, dict[tuple, tuple[torch.Tensor, ...]]] = OrderedDict()
        self.reserved = 0
        self.bytes = 0
        self.hits = 0
        self.misses = 0
        self.lock = threading.Lock()

    def _evict(self, key: tuple) -> None:
        entries = self.ranges.pop(key)
        self.bytes -= sum(t.numel() * t.element_size() for v in entries.values() for t in v)

    @staticmethod
    def _lookup(entries: dict | None, variant: tuple) -> tuple[torch.Tensor, ...] | None:
        if entries is None:
            return None
        if variant in entries:
            return entries[variant]
        backend, indices = variant
        for (other_backend, other_indices), frames in entries.items():
            if backend != other_backend or len(indices) > len(other_indices):
                continue
            for start in range(len(other_indices) - len(indices) + 1):
                if other_indices[start : start + len(indices)] == indices:
                    return frames[start : start + len(indices)]
        return None

    def frames(
        self,
        key: tuple,
        variant: tuple,
        estimated_bytes: int,
        decode: Callable[[], Iterator[torch.Tensor]],
        device: str,
    ) -> Iterator[torch.Tensor]:
        """Keep CPU and CUDA decodes separate; their conversion paths may differ."""
        with self.lock:
            # key is (path, size, mtime_ns, first, last).
            for old in list(self.ranges):
                if old[0] == key[0] and old[1:3] != key[1:3]:
                    self._evict(old)
            entries = self.ranges.get(key)
            cached = self._lookup(entries, variant)
            if cached is not None:
                self.hits += 1
                self.ranges.move_to_end(key)
                pinned = sum(t.numel() * t.element_size() for t in cached)
                self.reserved += pinned
            else:
                self.misses += 1
            retain = cached is None and estimated_bytes <= self.limit
            while (
                retain
                and self.ranges
                and (
                    self.bytes + self.reserved + estimated_bytes > self.limit
                    or (key not in self.ranges and len(self.ranges) >= 2)
                )
            ):
                self._evict(next(iter(self.ranges)))
            if self.reserved + self.bytes + estimated_bytes > self.limit:
                retain = False
            if retain:
                self.reserved += estimated_bytes
            entries = None
        if cached is not None:
            try:
                for frame in cached:
                    yield frame.to(device)
            finally:
                with self.lock:
                    self.reserved -= pinned
            return
        frames: list[torch.Tensor] = []
        complete = False
        accumulated = 0
        try:
            for frame in decode():
                if retain:
                    accumulated += frame.numel() * frame.element_size()
                    if accumulated > estimated_bytes:
                        frames.clear()
                        with self.lock:
                            self.reserved -= estimated_bytes
                        retain = False
                    else:
                        frames.append(frame.detach().to("cpu", copy=True))
                yield frame
            complete = True
        finally:
            if retain:
                if not complete:
                    frames.clear()
                with self.lock:
                    self.reserved -= estimated_bytes
                    actual = sum(t.numel() * t.element_size() for t in frames)
                    if complete and actual <= estimated_bytes:
                        while self.ranges and key not in self.ranges and len(self.ranges) >= 2:
                            self._evict(next(iter(self.ranges)))
                        entries = self.ranges.setdefault(key, {})
                        previous = entries.get(variant, ())
                        self.bytes -= sum(t.numel() * t.element_size() for t in previous)
                        entries[variant] = tuple(frames)
                        self.bytes += actual
                        self.ranges.move_to_end(key)

    def clear(self) -> None:
        with self.lock:
            self.ranges.clear()
            self.bytes = 0


class CompareState:
    def __init__(self) -> None:
        self.decoded = DecodedRanges()
        self.session = PipelineSession()
        self.key: str | None = None
        self.retire = False

    def models(self, job: dict[str, Any]) -> PipelineSession:
        key = json.dumps(
            [job.get(k) for k in ("input", "settings", "media", "scene_cuts", "models")],
            sort_keys=True,
        )
        if key != self.key:
            self.session.close()
            self.key = key
        return self.session

    def close(self) -> None:
        self.retire = True
        self.session.close()
        self.decoded.clear()
