"""Deterministic whole-segment planning over local calendar windows."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from videoenhancer.estimate import predict_segment

from .windows import Schedule, instant, resolve_wall


def build_plan(
    jobs: list[dict[str, Any]],
    schedule: Schedule,
    now: datetime,
    days: int = 14,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if days < 1:
        raise ValueError("Plan days must be positive.")
    start_date = now.astimezone(schedule.zone).date()
    limit = resolve_wall(
        datetime.combine(start_date + timedelta(days=days), time.min), schedule.zone
    )
    windows = schedule.available_intervals(now, limit)
    calendar = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        lower = resolve_wall(datetime.combine(day, time.min), schedule.zone)
        upper = resolve_wall(datetime.combine(day + timedelta(days=1), time.min), schedule.zone)
        calendar.append(
            {
                "date": day.isoformat(),
                "windows": [
                    i.to_dict()
                    for i in schedule.available_intervals(max(instant(now), instant(lower)), upper)
                ],
                "run_hours": 0.0,
                "jobs": [],
            }
        )
    timeline: list[dict[str, Any]] = []
    completions: list[dict[str, Any]] = []
    window_index = 0
    cursor = instant(now)
    exhausted = False
    for ordinal, job in enumerate(jobs):
        if job.get("state") in ("paused", "cancelled", "canceled", "done", "completed", "failed"):
            continue
        identity = str(job.get("job_id", job.get("id", ordinal)))
        segments = job.get("segments", [])
        total_frames = sum(max(0, int(s["end"]) - int(s["start"])) for s in segments)
        completed_frames = sum(
            int(s["end"]) - int(s["start"]) for s in segments if s.get("state") == "done"
        )
        remaining = [s for s in segments if s.get("state", "pending") != "done"]
        completion: datetime | None = None
        for segment in remaining:
            if exhausted:
                break
            frames = int(segment["end"]) - int(segment["start"])
            predicted = predict_segment(
                job.get("media", {}),
                job.get("settings", {}),
                frames,
                profile if profile is not None else job.get("machine_profile"),
                float(job.get("correction_factor", 1.0)),
            )
            required = timedelta(seconds=1.1 * predicted + 30)
            admitted = False
            while window_index < len(windows):
                interval = windows[window_index]
                cursor = max(cursor, instant(interval.start))
                if cursor + required <= instant(interval.end):
                    admitted = True
                    break
                window_index += 1
            if not admitted:
                exhausted = True
                break
            finish = cursor + timedelta(seconds=predicted)
            timeline.append(
                {
                    "job_id": identity,
                    "segment_index": segment.get("index", 0),
                    "start": cursor.astimezone(schedule.zone).isoformat(),
                    "end": finish.astimezone(schedule.zone).isoformat(),
                    "seconds": predicted,
                }
            )
            before = 100 * completed_frames / total_frames if total_frames else 100.0
            after = 100 * (completed_frames + frames) / total_frames if total_frames else 100.0
            split = cursor
            while split < finish:
                day = split.astimezone(schedule.zone).date()
                next_midnight = instant(
                    resolve_wall(datetime.combine(day + timedelta(days=1), time.min), schedule.zone)
                )
                stop = min(finish, next_midnight)
                entry = calendar[(day - start_date).days]
                entry["run_hours"] += (stop - split).total_seconds() / 3600
                fraction_start = (split - cursor).total_seconds() / predicted if predicted else 0
                fraction_end = (stop - cursor).total_seconds() / predicted if predicted else 1
                left = before + (after - before) * fraction_start
                right = before + (after - before) * fraction_end
                progress = next((p for p in entry["jobs"] if p["job_id"] == identity), None)
                if progress is None:
                    progress = {
                        "job_id": identity,
                        "start_percent": left,
                        "end_percent": right,
                        "completion": None,
                    }
                    entry["jobs"].append(progress)
                else:
                    progress["end_percent"] = right
                split = stop
            completed_frames += frames
            cursor = finish
            completion = finish
        finished = len(remaining) == 0 or completed_frames >= total_frames
        if not finished:
            completion = None
        elif completion is None:
            completion = instant(now)
        if completion is not None:
            # A segment ending exactly at midnight completes on the new calendar date.
            index = (completion.astimezone(schedule.zone).date() - start_date).days
            if 0 <= index < days:
                entry = calendar[index]
                progress = next((p for p in entry["jobs"] if p["job_id"] == identity), None)
                if progress is None:
                    progress = {
                        "job_id": identity,
                        "start_percent": 100.0,
                        "end_percent": 100.0,
                        "completion": None,
                    }
                    entry["jobs"].append(progress)
                progress["completion"] = completion.astimezone(schedule.zone).isoformat()
        completions.append(
            {
                "job_id": identity,
                "completion": completion.astimezone(schedule.zone).isoformat()
                if completion
                else None,
                "remaining_frames": max(0, total_frames - completed_frames),
            }
        )
    return {
        "generated_at": now.isoformat(),
        "timezone": schedule.zone.key,
        "days": calendar,
        "timeline": timeline,
        "jobs": completions,
    }
