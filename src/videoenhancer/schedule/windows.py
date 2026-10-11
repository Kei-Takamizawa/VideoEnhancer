"""Local calendar schedules with explicit daylight-saving resolution."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from videoenhancer.files import retry_permission

UTC = UTC
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def local_zone() -> ZoneInfo:
    """Detect the OS IANA zone, including Windows zone-name mapping."""
    if os.environ.get("TZ"):
        return ZoneInfo(os.environ["TZ"])
    from tzlocal import get_localzone_name

    return ZoneInfo(get_localzone_name())


def instant(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Schedule datetimes must include a timezone.")
    return value.astimezone(UTC)


def resolve_wall(value: datetime, zone: ZoneInfo) -> datetime:
    """Choose the first occurrence of a fold or first valid minute after a gap."""
    wall = value.replace(tzinfo=None)
    for _ in range(24 * 60 + 1):
        candidates = []
        for fold in (0, 1):
            candidate = wall.replace(tzinfo=zone, fold=fold)
            roundtrip = candidate.astimezone(UTC).astimezone(zone)
            if roundtrip.replace(tzinfo=None) == wall:
                candidates.append(candidate)
        if candidates:
            return min(candidates, key=instant)
        wall += timedelta(minutes=1)
    raise ValueError(f"Cannot resolve local time {value} in {zone.key}.")


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    @property
    def seconds(self) -> float:
        return (instant(self.end) - instant(self.start)).total_seconds()

    def to_dict(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


def _clock(text: str) -> time:
    try:
        if len(text) != 5 or text[2] != ":":
            raise ValueError
        hour, minute = map(int, text.split(":"))
        result = time(hour, minute)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid time {text!r}; use HH:MM.") from None
    if result.minute % 15:
        raise ValueError("Schedule times must use 15-minute granularity.")
    return result


def _validate_window(window: dict[str, Any]) -> None:
    start, end = _clock(window["start"]), _clock(window["end"])
    minutes = ((end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)) % 1440
    if minutes and minutes < 15:
        raise ValueError("Schedule windows must last at least 15 minutes.")


class Schedule:
    def __init__(self, config: dict[str, Any], zone: ZoneInfo | None = None):
        if config.get("schema_version", 1) != 1:
            raise ValueError("Unsupported schedule schema version.")
        self.zone = zone or (
            ZoneInfo(config["timezone"]) if config.get("timezone") else local_zone()
        )
        self.enabled = bool(config.get("enabled", False))
        self.weekly = list(config.get("weekly", []))
        self.exceptions: dict[date, Any] = {}
        for window in self.weekly:
            _validate_window(window)
            if not window.get("days") or any(day not in DAY_NAMES for day in window["days"]):
                raise ValueError("Weekly days must be mon, tue, wed, thu, fri, sat or sun.")
        for entry in config.get("exceptions", []):
            day = date.fromisoformat(entry["date"])
            if day in self.exceptions:
                raise ValueError(f"Duplicate schedule exception for {day}.")
            windows = entry["windows"]
            if windows != "off":
                if not isinstance(windows, list):
                    raise ValueError("Exception windows must be a list or 'off'.")
                for window in windows:
                    _validate_window(window)
            self.exceptions[day] = windows
        self.override_until = config.get("override_until")
        self._cached_current: Interval | None = None
        self._override: datetime | None = None
        if self.override_until and self.override_until not in {"job-complete", "queue-complete"}:
            parsed = datetime.fromisoformat(self.override_until)
            self._override = resolve_wall(parsed, self.zone) if parsed.tzinfo is None else parsed

    @classmethod
    def from_dict(cls, config: dict[str, Any], zone: ZoneInfo | None = None) -> Schedule:
        return cls(config, zone)

    @classmethod
    def from_file(cls, path: str | Path, zone: ZoneInfo | None = None) -> Schedule:
        source = Path(path)
        config = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
        return cls.from_dict(config, zone)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "timezone": self.zone.key,
            "enabled": self.enabled,
            "weekly": self.weekly,
            "exceptions": [
                {"date": day.isoformat(), "windows": windows}
                for day, windows in sorted(self.exceptions.items())
            ],
            "override_until": self.override_until,
        }

    @staticmethod
    def clear_job_complete_override(path: str | Path, *, queue_complete: bool = False) -> bool:
        """Clear only a job-complete override, preserving the latest disk settings."""
        source = Path(path)
        if not source.exists():
            return False
        config = json.loads(source.read_text(encoding="utf-8"))
        if config.get("override_until") != "job-complete" and not (
            queue_complete and config.get("override_until") == "queue-complete"
        ):
            return False
        config["override_until"] = None
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=source.parent,
                prefix=source.name + ".",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(config, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            retry_permission(os.replace, temporary, source)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return True

    def _window(self, day: date, window: dict[str, Any]) -> Interval:
        start_time, end_time = _clock(window["start"]), _clock(window["end"])
        end_day = day + timedelta(days=1) if end_time <= start_time else day
        return Interval(
            resolve_wall(datetime.combine(day, start_time), self.zone),
            resolve_wall(datetime.combine(end_day, end_time), self.zone),
        )

    def _day_intervals(self, day: date) -> list[Interval]:
        lower = resolve_wall(datetime.combine(day, time.min), self.zone)
        upper = resolve_wall(datetime.combine(day + timedelta(days=1), time.min), self.zone)
        candidates = []
        # An exception replaces its entire date, including yesterday's windows.
        origins = (day,) if day in self.exceptions else (day - timedelta(days=1), day)
        for origin in origins:
            if origin in self.exceptions:
                windows = self.exceptions[origin]
                if windows == "off":
                    continue
            else:
                windows = [w for w in self.weekly if DAY_NAMES[origin.weekday()] in w["days"]]
            for window in windows:
                interval = self._window(origin, window)
                left = max(instant(lower), instant(interval.start))
                right = min(instant(upper), instant(interval.end))
                if left < right:
                    candidates.append(
                        Interval(left.astimezone(self.zone), right.astimezone(self.zone))
                    )
        return candidates

    def available_intervals(self, start: datetime, end: datetime) -> list[Interval]:
        lower, upper = instant(start), instant(end)
        if upper <= lower:
            return []
        if not self.enabled or self.override_until in {"job-complete", "queue-complete"}:
            return [Interval(start.astimezone(self.zone), end.astimezone(self.zone))]
        raw = []
        day = lower.astimezone(self.zone).date()
        last = upper.astimezone(self.zone).date()
        while day <= last:
            raw.extend(self._day_intervals(day))
            day += timedelta(days=1)
        if self._override and instant(self._override) > lower:
            raw.append(Interval(lower, min(upper, instant(self._override))))
        clipped = sorted(
            (max(lower, instant(i.start)), min(upper, instant(i.end)))
            for i in raw
            if instant(i.end) > lower and instant(i.start) < upper
        )
        merged: list[tuple[datetime, datetime]] = []
        for left, right in clipped:
            if right <= left:
                continue
            if merged and left <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
            else:
                merged.append((left, right))
        return [Interval(a.astimezone(self.zone), b.astimezone(self.zone)) for a, b in merged]

    def current_interval(self, now: datetime) -> Interval | None:
        if self._cached_current and instant(self._cached_current.start) <= instant(now) < instant(
            self._cached_current.end
        ):
            return self._cached_current
        if not self.enabled or self.override_until in {"job-complete", "queue-complete"}:
            return Interval(
                now.astimezone(self.zone), datetime(9998, 1, 1, tzinfo=UTC).astimezone(self.zone)
            )
        # Most queries examine just three dates. Extend only for connected windows.
        local_day = now.astimezone(self.zone).date()
        begin = resolve_wall(datetime.combine(local_day - timedelta(days=1), time.min), self.zone)
        lookahead = 2
        while True:
            end = resolve_wall(
                datetime.combine(local_day + timedelta(days=lookahead), time.min), self.zone
            )
            current = next(
                (
                    i
                    for i in self.available_intervals(begin, end)
                    if instant(i.start) <= instant(now) < instant(i.end)
                ),
                None,
            )
            if current is None:
                return None
            if instant(current.end) < instant(end):
                self._cached_current = current
                return current
            if lookahead >= 8:
                # A complete weekly cycle remains connected. Only a future
                # exception or override expiry can make its first break.
                future = sorted(
                    d for d in self.exceptions if d >= local_day + timedelta(days=lookahead - 1)
                )
                if not future and (not self._override or instant(self._override) <= instant(end)):
                    current = Interval(
                        current.start, datetime(9998, 1, 1, tzinfo=UTC).astimezone(self.zone)
                    )
                    self._cached_current = current
                    return current
                if future:
                    lookahead = max(lookahead * 2, (future[0] - local_day).days + 2)
                elif self._override:
                    lookahead = max(
                        lookahead * 2,
                        (self._override.astimezone(self.zone).date() - local_day).days + 2,
                    )
            else:
                lookahead *= 2

    def next_interval(self, now: datetime) -> Interval | None:
        intervals = self.available_intervals(now, instant(now) + timedelta(days=370))
        return intervals[0] if intervals else None
