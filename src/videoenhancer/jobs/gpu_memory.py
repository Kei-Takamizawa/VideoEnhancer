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


class JobMemorySampler:
    """Sample engine PID dedicated GPU bytes, Torch reserve, RSS, and NVML."""

    def __init__(
        self, interval_seconds: int = 60, on_sample: Callable[[dict[str, Any]], None] | None = None
    ) -> None:
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, Any]] = []
        self.on_sample = on_sample
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
                timeout=8,
                check=False,
            )
            if result.returncode != 0:
                return None
            return int(result.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError):
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
            "process_shared_gpu_bytes": self._windows_bytes(pid, "Shared Usage"),
            "torch_reserved_bytes": reserved,
            "process_rss_bytes": rss,
            "device_nvml_used_bytes": nvml_bytes,
            "sources": {
                "process_dedicated_gpu_bytes": (
                    "Windows Get-Counter PDH GPU Process Memory Dedicated Usage for engine PID"
                ),
                "torch_reserved_bytes": "torch.cuda.memory_reserved",
                "process_rss_bytes": "psutil.Process(pid).memory_info().rss",
                "device_nvml_used_bytes": "NVML device-wide memory.used",
            },
        }
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
        return self.samples
