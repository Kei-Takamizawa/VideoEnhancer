"""Measure a prepared segment on Windows with one-second per-PID PDH samples."""

import argparse
import ctypes
import json
import os
import threading
import time
from ctypes import wintypes
from pathlib import Path

from videoenhancer.pipeline.runner import process_segment


class ProcessGpuSampler:
    def __init__(self):
        self.samples = []
        self.error = None
        self.stop = threading.Event()
        self.pdh = ctypes.WinDLL("pdh")
        self.query = ctypes.c_void_p()
        self.pdh.PdhOpenQueryW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.pdh.PdhAddEnglishCounterW.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
        self.pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
        self.pdh.PdhGetFormattedCounterArrayW.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        if self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.query)):
            raise RuntimeError("Could not open the GPU memory PDH query.")
        self.counters = []
        for name in ("Dedicated Usage", "Shared Usage"):
            counter = ctypes.c_void_p()
            if self.pdh.PdhAddEnglishCounterW(
                self.query, f"\\GPU Process Memory(*)\\{name}", 0, ctypes.byref(counter)
            ):
                raise RuntimeError("Could not add the GPU memory PDH counter.")
            self.counters.append(counter)
        self.thread = threading.Thread(target=self._run, daemon=True)

    def sample(self):
        class Value(ctypes.Structure):
            _fields_ = [("status", wintypes.DWORD), ("number", ctypes.c_longlong)]

        class Item(ctypes.Structure):
            _fields_ = [("name", wintypes.LPWSTR), ("value", Value)]

        if self.pdh.PdhCollectQueryData(self.query):
            raise RuntimeError("Could not collect GPU memory PDH counters.")
        numbers = []
        for counter in self.counters:
            size, count = wintypes.DWORD(), wintypes.DWORD()
            self.pdh.PdhGetFormattedCounterArrayW(
                counter, 0x400, ctypes.byref(size), ctypes.byref(count), None
            )
            if not size.value:
                raise RuntimeError("GPU process memory PDH counter has no instances.")
            buffer = ctypes.create_string_buffer(size.value)
            if self.pdh.PdhGetFormattedCounterArrayW(
                counter, 0x400, ctypes.byref(size), ctypes.byref(count), buffer
            ):
                raise RuntimeError("Could not read GPU process memory PDH instances.")
            items = ctypes.cast(buffer, ctypes.POINTER(Item))
            values = [
                items[i].value.number
                for i in range(count.value)
                if items[i].name.lower().startswith(f"pid_{os.getpid()}_")
                and items[i].value.status in (0, 1)
            ]
            numbers.append(sum(values) if values else None)
        self.samples.append(
            dict(
                time=time.time(),
                monotonic=time.monotonic(),
                pid=os.getpid(),
                dedicated_bytes=numbers[0],
                shared_bytes=numbers[1],
            )
        )

    def _run(self):
        deadline = time.monotonic()
        while not self.stop.is_set():
            try:
                self.sample()
            except Exception as error:
                self.error = error
                return
            deadline += 1
            self.stop.wait(max(0, deadline - time.monotonic()))

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        try:
            if self.error is not None:
                raise RuntimeError("One-second GPU memory sampling failed.") from self.error
            self.sample()
        finally:
            self.pdh.PdhCloseQuery(self.query)


def measure(job, output):
    with ProcessGpuSampler() as sampler:
        stats = process_segment(
            job, dict(index=0, start=0, end=150), output, lambda: False, reference_measurement=True
        )
    observed = [
        s["dedicated_bytes"] + s["shared_bytes"]
        for s in sampler.samples
        if s["dedicated_bytes"] is not None and s["shared_bytes"] is not None
    ]
    if not observed:
        raise RuntimeError("No per-PID GPU memory samples; this model cannot be qualified.")
    peak = max(observed)
    return dict(
        fps=stats["fps_without_model_loading"],
        torch_allocated_bytes=stats["peak_torch_allocated_bytes"],
        torch_reserved_bytes=stats["peak_torch_vram_bytes"],
        process_peak_bytes=peak,
        budget_pass=peak <= 5_000_000_000,
        samples=sampler.samples,
        pipeline=stats,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = measure(json.loads(args.manifest.read_text(encoding="utf-8")), args.output)
    args.output.with_suffix(".measurement.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
