"""Process-scoped GPU and RAM memory sampling for long jobs."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import psutil
import torch


class JobMemorySampler:
    """Sample engine PID dedicated GPU bytes, Torch reserve, RSS, and NVML."""

    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._nvml: Any = None
        self._handle: Any = None
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            pass

    @staticmethod
    def _dedicated_bytes(pid: int) -> int | None:
        if os.name != "nt":
            return None
        try:
            total = 0
            matched = False
            import win32pdh  # type: ignore[import-not-found]

            query = win32pdh.OpenQuery()
            try:
                expand = win32pdh.__dict__["ExpandWildCardPath"]
                paths = expand(None, r"\\GPU Process Memory(*)\\Dedicated Usage")
                counters = []
                for path in paths:
                    if f"pid_{pid}_" in path.lower():
                        counters.append(win32pdh.AddCounter(query, path))
                        matched = True
                if not matched:
                    return None
                win32pdh.CollectQueryData(query)
                for counter in counters:
                    _, value = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_LARGE)
                    total += int(value)
                return total
            finally:
                win32pdh.CloseQuery(query)
        except Exception:
            return None

    def sample(self) -> dict[str, Any]:
        pid = os.getpid()
        rss = int(psutil.Process(pid).memory_info().rss)
        reserved = int(torch.cuda.memory_reserved()) if torch.cuda.is_available() else 0
        nvml_bytes = None
        if self._nvml is not None:
            try:
                nvml_bytes = int(self._nvml.nvmlDeviceGetMemoryInfo(self._handle).used)
            except Exception:
                pass
        record = {
            "timestamp": time.time(),
            "pid": pid,
            "process_dedicated_gpu_bytes": self._dedicated_bytes(pid),
            "torch_reserved_bytes": reserved,
            "process_rss_bytes": rss,
            "device_nvml_used_bytes": nvml_bytes,
            "sources": {
                "process_dedicated_gpu_bytes": (
                    "Windows GPU Process Memory\\Dedicated Usage summed for engine PID"
                ),
                "torch_reserved_bytes": "torch.cuda.memory_reserved",
                "process_rss_bytes": "psutil.Process(pid).memory_info().rss",
                "device_nvml_used_bytes": "NVML device-wide memory.used",
            },
        }
        self.samples.append(record)
        return record

    def start(self) -> None:
        self.sample()
        self._thread = threading.Thread(target=self._run, name="ve-memory-sampler", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.sample()

    def stop(self) -> list[dict[str, Any]]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 2)
        return self.samples
