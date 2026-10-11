"""Shared step admission for forecasts and the live controller."""

from datetime import datetime, timedelta
from typing import Any

from .windows import instant


def admit_step(
    predicted: float, finalizing: bool, now: datetime, interval: Any
) -> tuple[bool, bool]:
    if interval is None:
        return False, False
    reserve = predicted if finalizing else predicted * 1.1 + 30
    beginning = getattr(interval, "start", None)
    overrun = (
        beginning is not None
        and predicted > (instant(interval.end) - instant(beginning)).total_seconds()
        and 0 <= (instant(now) - instant(beginning)).total_seconds() < 30
    )
    return overrun or instant(now) + timedelta(seconds=reserve) <= instant(interval.end), overrun
