"""Byte-based download/checking progress and fixed predicted phase weights."""

import re
import time
from collections import deque
from typing import Any


def gpu_test_prediction(model: dict[str, Any], profile: dict[str, Any] | None) -> float:
    """Predict fresh-worker startup plus the small qualification inference."""
    if not profile:
        return 15.0
    mode = "fast" if model["task"] == "interpolate" else "standard"
    startup = profile.get("startup_by_preset", {}).get(
        mode, profile.get("segment_overhead_seconds", 2)
    )
    coefficient = (
        profile.get("models", {}).get(model["id"], {}).get("seconds_per_pixel_frame", 0) or 0
    )
    frames = 1 if model["task"] == "size" else 3
    return max(1.0, float(startup) + 256 * 256 * frames * float(coefficient))


class DownloadProgress:
    def __init__(
        self, sizes: dict[str, int], gpu_seconds: float, check_sizes: dict[str, int] | None = None
    ):
        self.sizes = sizes
        self.check_sizes = dict(check_sizes or sizes)
        self.downloaded: dict[str, int] = {}
        self.checked: dict[str, int] = {}
        self.samples: deque[tuple[float, int]] = deque()
        self.started: float | None = None
        self.percent = 0.0
        self.gpu_seconds = max(1, gpu_seconds)
        total = max(1, sum(sizes.values()))
        self.expected = dict(
            download=total / (2 * 1024**2),
            checking=max(1, sum(self.check_sizes.values())) / (512 * 1024**2),
            gpu=self.gpu_seconds,
        )

    def feed(self, phase: str, _percent: float) -> dict[str, Any]:
        match = re.search(
            r"(Downloading|Checking|Verifying|Present) (.+?): ([\d,]+) / ([\d,]+) bytes", phase
        )
        now = time.monotonic()
        if match:
            kind, name, done, total = match.groups()
            name = name.removesuffix(".download").removesuffix(".extracting")
            done, total = int(done.replace(",", "")), int(total.replace(",", ""))
            self.check_sizes.setdefault(name, total)
            if kind in {"Downloading", "Present"}:
                if kind == "Downloading" or name in self.sizes:
                    self.sizes.setdefault(name, total)
                    self.downloaded[name] = done
            else:
                self.checked[name] = done
                if name in self.sizes:
                    self.downloaded[name] = total
        received = sum(self.downloaded.values())
        total = max(1, sum(self.sizes.values()))
        if match and match[1] == "Downloading":
            self.started = self.started if self.started is not None else now
            self.samples.append((now, received))
            while len(self.samples) > 2 and now - self.samples[1][0] >= 3:
                self.samples.popleft()
        speed = None
        if self.started is not None and now - self.started >= 2 and len(self.samples) > 1:
            elapsed = self.samples[-1][0] - self.samples[0][0]
            speed = (self.samples[-1][1] - self.samples[0][1]) / elapsed if elapsed else None
        download_fraction = min(1, received / total)
        checking_fraction = min(
            1, sum(self.checked.values()) / max(1, sum(self.check_sizes.values()))
        )
        completed = (
            self.expected["download"] * download_fraction
            + self.expected["checking"] * checking_fraction
        )
        self.percent = max(self.percent, min(99, completed / sum(self.expected.values()) * 100))
        remaining = (
            (total - received) / speed
            + self.expected["checking"] * (1 - checking_fraction)
            + self.gpu_seconds
            if speed
            else None
        )
        return dict(
            phase="Downloading" if match and match[1] == "Downloading" else "Checking",
            percent=self.percent,
            bytes_received=received,
            bytes_total=total,
            bytes_per_second=speed,
            remaining_seconds=remaining,
            progress_detail=phase,
            expected_phase_seconds=dict(self.expected),
        )
