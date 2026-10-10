"""Forecast the same between-step admission and owner order as the controller."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from videoenhancer.estimate import predict_segment
from videoenhancer.estimate.model import predict_finalization, remaining_fraction

from .admission import admit_step
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
    limit = instant(
        resolve_wall(datetime.combine(start_date + timedelta(days=days), time.min), schedule.zone)
    )
    calendar: list[dict[str, Any]] = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        lower = resolve_wall(datetime.combine(day, time.min), schedule.zone)
        upper = resolve_wall(datetime.combine(day + timedelta(days=1), time.min), schedule.zone)
        calendar.append(
            dict(
                date=day.isoformat(),
                windows=[
                    i.to_dict()
                    for i in schedule.available_intervals(max(instant(now), instant(lower)), upper)
                ],
                run_hours=0.0,
                jobs=[],
            )
        )
    windows = schedule.available_intervals(now, limit)
    current = schedule.current_interval(now)
    if windows and current is not None:
        windows[0] = current
    forecasts: list[dict[str, Any]] = []
    for ordinal, job in enumerate(jobs):
        if job.get("state") in {
            "preparing",
            "paused",
            "cancelled",
            "canceled",
            "done",
            "completed",
            "failed",
        }:
            continue
        effective = profile if profile is not None else job.get("machine_profile")
        segments = job.get("segments", [])
        units = []
        total, completed, frames_left = 0.0, 0.0, 0.0
        for segment in segments:
            frames = int(segment["end"]) - int(segment["start"])
            prediction = predict_segment(
                job.get("media", {}),
                job.get("settings", {}),
                frames,
                effective,
                float(job.get("correction_factor", 1)),
            )
            total += prediction
            if segment.get("state") == "done":
                completed += prediction
                continue
            fraction = remaining_fraction(job, segment)
            completed += prediction * (1 - fraction)
            frames_left += frames * fraction
            units.append(
                dict(
                    index=segment.get("index", 0),
                    seconds=prediction * fraction,
                    frames=frames * fraction,
                    finalizing=False,
                    active=segment.get("state") == "running",
                )
            )
        finalization = predict_finalization(job, effective)
        total += finalization
        fraction = min(
            1.0, max(0.0, float(job.get("progress", {}).get("finalization_fraction", 0)))
        )
        completed += finalization * fraction
        if finalization > 0:
            units.append(
                dict(
                    index=None,
                    seconds=finalization * (1 - fraction),
                    frames=0,
                    finalizing=True,
                    active=job.get("progress", {}).get("phase") == "finalizing",
                )
            )
        forecasts.append(
            dict(
                identity=str(job.get("job_id", job.get("id", ordinal))),
                units=units,
                total=total,
                completed=completed,
                frames_left=frames_left,
                completion=instant(now) if not units else None,
                window_end=job.get("admitted_window_end"),
            )
        )
    timeline: list[dict[str, Any]] = []
    cursor, window_index = instant(now), 0
    while any(f["units"] for f in forecasts):
        while window_index < len(windows) and instant(windows[window_index].end) <= cursor:
            window_index += 1
        active = next((f for f in forecasts if f["units"] and f["units"][0]["active"]), None)
        if active is not None:
            selected = active
            boundary = (
                datetime.fromisoformat(active["window_end"]) if active["window_end"] else None
            )
        else:
            if window_index >= len(windows):
                break
            interval = windows[window_index]
            cursor = max(cursor, instant(interval.start))
            selected = next(
                (
                    f
                    for f in forecasts
                    if f["units"]
                    and admit_step(
                        f["units"][0]["seconds"], f["units"][0]["finalizing"], cursor, interval
                    )[0]
                ),
                None,
            )
            if selected is None:
                window_index += 1
                continue
            boundary = interval.end
        unit = selected["units"].pop(0)
        predicted = unit["seconds"]
        finish = cursor + timedelta(seconds=predicted)
        timeline.append(
            dict(
                job_id=selected["identity"],
                segment_index=unit["index"],
                phase="finalizing" if unit["finalizing"] else "processing",
                start=cursor.astimezone(schedule.zone).isoformat(),
                end=finish.astimezone(schedule.zone).isoformat(),
                seconds=predicted,
                overrun_seconds=max(0.0, (finish - instant(boundary)).total_seconds())
                if boundary
                else 0.0,
            )
        )
        before = 100 * selected["completed"] / selected["total"] if selected["total"] else 100.0
        after = (
            100 * (selected["completed"] + predicted) / selected["total"]
            if selected["total"]
            else 100.0
        )
        timeline[-1].update(start_percent=before, end_percent=after)
        split = cursor
        while split < finish:
            day = split.astimezone(schedule.zone).date()
            day_index = (day - start_date).days
            if not 0 <= day_index < days:
                break
            midnight = instant(
                resolve_wall(datetime.combine(day + timedelta(days=1), time.min), schedule.zone)
            )
            stop = min(finish, midnight)
            entry = calendar[day_index]
            entry["run_hours"] += (stop - split).total_seconds() / 3600
            left = before + (after - before) * (split - cursor).total_seconds() / predicted
            right = before + (after - before) * (stop - cursor).total_seconds() / predicted
            progress = next((p for p in entry["jobs"] if p["job_id"] == selected["identity"]), None)
            if progress is None:
                entry["jobs"].append(
                    dict(
                        job_id=selected["identity"],
                        start_percent=left,
                        end_percent=right,
                        completion=None,
                    )
                )
            else:
                progress["end_percent"] = right
            split = stop
        selected["completed"] += predicted
        selected["frames_left"] -= unit["frames"]
        if not selected["units"]:
            selected["completion"] = finish
        cursor = finish
    completions = []
    for forecast in forecasts:
        completion = forecast["completion"]
        if completion is not None:
            day_index = (completion.astimezone(schedule.zone).date() - start_date).days
            if 0 <= day_index < days:
                entry = calendar[day_index]
                progress = next(
                    (p for p in entry["jobs"] if p["job_id"] == forecast["identity"]), None
                )
                if progress is None:
                    progress = dict(
                        job_id=forecast["identity"],
                        start_percent=100.0,
                        end_percent=100.0,
                        completion=None,
                    )
                    entry["jobs"].append(progress)
                progress["completion"] = completion.astimezone(schedule.zone).isoformat()
        completions.append(
            dict(
                job_id=forecast["identity"],
                completion=completion.astimezone(schedule.zone).isoformat() if completion else None,
                remaining_frames=max(0, round(forecast["frames_left"])),
            )
        )
    return dict(
        generated_at=now.isoformat(),
        timezone=schedule.zone.key,
        days=calendar,
        timeline=timeline,
        jobs=completions,
    )
