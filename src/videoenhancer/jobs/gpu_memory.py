"""Process-scoped GPU and RAM memory sampling for long jobs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

import psutil
import torch

from videoenhancer import proc
from videoenhancer.jobs.pdh import ProcessMemoryCounters


class SpillTracker:
    def __init__(self) -> None:
        self.baseline: int | None = None
        self.spilled: bool | None = None
        self.peak_dedicated: int | None = None
        self.peak_shared: int | None = None

    def observe(self, dedicated: int | None, shared: int | None) -> None:
        if dedicated is not None:
            self.peak_dedicated = max(self.peak_dedicated or 0, dedicated)
        if shared is not None:
            if self.baseline is None:
                self.baseline, self.spilled = shared, False
            self.peak_shared = max(self.peak_shared or 0, shared)
            if shared - self.baseline > 256_000_000:
                self.spilled = True


class JobMemorySampler:
    """Sample engine PID dedicated GPU bytes, Torch reserve, RSS, and NVML."""

    def __init__(
        self, interval_seconds: int = 1, on_sample: Callable[[dict[str, Any]], None] | None = None
    ) -> None:
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, Any]] = []
        self.on_sample = on_sample
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._nvml: Any = None
        self._handle: Any = None
        self.spill = SpillTracker()
        self._pdh: ProcessMemoryCounters | None = None
        self.counter_source = "unavailable"
        if os.name == "nt":
            try:
                self._pdh = ProcessMemoryCounters()
                self.counter_source = "PDH ctypes"
            except OSError:
                self.counter_source = "PowerShell fallback"
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            pass

    @staticmethod
    def _dedicated_bytes(pid: int) -> int | None:
        return JobMemorySampler._windows_bytes(pid, "Dedicated Usage")

    @staticmethod
    def _windows_bytes(pid: int, counter: str) -> int | None:
        if os.name != "nt":
            return None
        try:
            powershell = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
            if powershell is None:
                return None
            # Use Windows' built-in PDH query to avoid making pywin32 a runtime
            # dependency. Match only this engine PID across all GPU adapters.
            counter_path = f"\\GPU Process Memory(*)\\{counter}"
            command = (
                f"$prefix='pid_{pid}_'; "
                f"$samples=(Get-Counter '{counter_path}' -ErrorAction Stop).CounterSamples; "
                "$items=@($samples | Where-Object { $_.InstanceName.StartsWith("
                "$prefix,[StringComparison]::OrdinalIgnoreCase) }); "
                "if ($items.Count -eq 0) { exit 3 }; "
                "[Console]::Out.WriteLine([long](($items | "
                "Measure-Object -Property CookedValue -Sum).Sum))"
            )
            result = proc.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
            if result.returncode != 0:
                return None
            return int(result.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
            return None

    def sample(self) -> dict[str, Any]:
        started = time.perf_counter()
        pid = os.getpid()
        rss = int(psutil.Process(pid).memory_info().rss)
        reserved = int(torch.cuda.memory_reserved()) if torch.cuda.is_available() else 0
        dedicated = shared = None
        counter_started = time.perf_counter()
        if self._pdh is not None:
            try:
                dedicated, shared = self._pdh.read(pid)
            except OSError:
                self._pdh.close()
                self._pdh = None
                self.counter_source = "PowerShell fallback"
        if self.counter_source == "PowerShell fallback":
            dedicated = self._dedicated_bytes(pid)
            shared = self._windows_bytes(pid, "Shared Usage")
        counter_seconds = time.perf_counter() - counter_started
        self.spill.observe(dedicated, shared)
        nvml_bytes = None
        if self._nvml is not None:
            try:
                nvml_bytes = int(self._nvml.nvmlDeviceGetMemoryInfo(self._handle).used)
            except Exception:
                pass
        record = {
            "timestamp": time.time(),
            "pid": pid,
            "process_dedicated_gpu_bytes": dedicated,
            "process_shared_gpu_bytes": shared,
            "counter_source": self.counter_source if shared is not None else "unavailable",
            "counter_sample_seconds": counter_seconds,
            "spilled": self.spill.spilled,
            "cap_on": torch.cuda.get_per_process_memory_fraction() < 1
            if torch.cuda.is_initialized()
            else False,
            "torch_reserved_bytes": reserved,
            "process_rss_bytes": rss,
            "device_nvml_used_bytes": nvml_bytes,
            "sources": {
                "process_dedicated_gpu_bytes": (
                    self.counter_source + " GPU Process Memory for processing PID"
                ),
                "torch_reserved_bytes": "torch.cuda.memory_reserved",
                "process_rss_bytes": "psutil.Process(pid).memory_info().rss",
                "device_nvml_used_bytes": "NVML device-wide memory.used",
            },
        }
        record["sample_seconds"] = time.perf_counter() - started
        self.samples.append(record)
        if self.on_sample is not None:
            self.on_sample(record)
        # Emit samples as they happen so a killed child leaves memory evidence.
        if sys.stderr is not None:
            print("Memory sample: " + json.dumps(record), file=sys.stderr, flush=True)
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
        if self._pdh is not None and (self._thread is None or not self._thread.is_alive()):
            self._pdh.close()
        return self.samples
