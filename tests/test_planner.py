from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from videoenhancer.schedule.planner import build_plan
from videoenhancer.schedule.windows import Schedule

ZONE = ZoneInfo("UTC")
PROFILE = {
    "finalization": {"a": 0, "b": 0, "c": 0},
    "components": {"decode": 1, "color": 0, "encode": 0},
    "segment_overhead_seconds": 0,
}


def job(identity, frames, count=1, state="queued"):
    return {
        "job_id": identity,
        "state": state,
        "media": {"width": 1, "height": 1},
        "settings": {"preset": "passthrough", "fps": "off"},
        "segments": [
            {"index": i, "start": i * frames, "end": (i + 1) * frames, "state": "pending"}
            for i in range(count)
        ],
    }


def schedule(start="22:00", end="00:00"):
    return Schedule.from_dict(
        {"enabled": True, "weekly": [{"days": ["mon", "tue", "wed"], "start": start, "end": end}]},
        ZONE,
    )


def test_multi_day_queue_and_midnight_summary():
    now = datetime(2026, 10, 5, 21, tzinfo=ZONE)
    plan = build_plan([job("A", 3600, 2), job("B", 1800)], schedule(), now, 3, PROFILE)
    assert [s["job_id"] for s in plan["timeline"]] == ["A", "A", "B"]
    assert plan["jobs"][0]["completion"] == "2026-10-06T23:00:00+00:00"
    assert plan["jobs"][1]["completion"] == "2026-10-06T23:30:00+00:00"
    assert plan["days"][0]["run_hours"] == 1
    assert plan["days"][0]["jobs"][0]["end_percent"] == 50
    assert plan["days"][1]["run_hours"] == 1.5


def test_admission_reserves_safety_margin_and_overhead():
    now = datetime(2026, 10, 5, 8, tzinfo=ZONE)
    plan = build_plan([job("A", 830)], schedule("08:00", "08:15"), now, 1, PROFILE)
    assert plan["timeline"] == []  # 913 + 30 > the 900-second window.
    assert plan["jobs"][0]["completion"] is None


def test_overnight_runs_split_at_local_midnight():
    now = datetime(2026, 10, 5, 23, 30, tzinfo=ZONE)
    plan = build_plan([job("A", 3600)], schedule("22:00", "08:00"), now, 2, PROFILE)
    assert plan["days"][0]["run_hours"] == 0.5
    assert plan["days"][1]["run_hours"] == 0.5
    assert plan["days"][0]["jobs"][0]["end_percent"] == 50
    assert plan["days"][1]["jobs"][0]["start_percent"] == 50
    assert plan["days"][1]["jobs"][0]["completion"] == "2026-10-06T00:30:00+00:00"


def test_reordering_changes_completion_and_paused_jobs_are_skipped():
    now = datetime(2026, 10, 5, 8, tzinfo=ZONE)
    value = Schedule.from_dict({}, ZONE)
    first = build_plan([job("A", 600), job("B", 300)], value, now, profile=PROFILE)
    second = build_plan(
        [job("B", 300), job("A", 600), job("C", 600, state="paused")], value, now, profile=PROFILE
    )
    assert first["jobs"][0]["completion"] == "2026-10-05T08:10:00+00:00"
    assert second["jobs"][0]["completion"] == "2026-10-05T08:05:00+00:00"
    assert len(second["jobs"]) == 2


def test_invalid_horizon():
    with pytest.raises(ValueError):
        build_plan([], schedule(), datetime(2026, 10, 5, tzinfo=ZONE), 0)


def test_schedule_edit_and_live_correction_change_plan():
    now = datetime(2026, 10, 5, 8, tzinfo=ZONE)
    queued = job("A", 300)
    first = build_plan([queued], schedule("09:00", "10:00"), now, profile=PROFILE)
    second = build_plan([queued], schedule("10:00", "11:00"), now, profile=PROFILE)
    assert first["jobs"][0]["completion"] == "2026-10-05T09:05:00+00:00"
    assert second["jobs"][0]["completion"] == "2026-10-05T10:05:00+00:00"
    queued["correction_factor"] = 2
    corrected = build_plan([queued], schedule("09:00", "10:00"), now, profile=PROFILE)
    assert corrected["jobs"][0]["completion"] == "2026-10-05T09:10:00+00:00"


def test_preset_edit_recomputes_predictions_instead_of_using_stale_segment_cost():
    now = datetime(2026, 10, 5, 8, tzinfo=ZONE)
    queued = job("A", 10)
    queued["media"] = {"width": 720, "height": 1280}
    queued["segments"][0]["predicted_seconds"] = 1
    available = Schedule.from_dict({}, ZONE)
    first = build_plan([queued], available, now)
    queued["settings"] = {"preset": "p0-test", "short_side": 1080, "fps": "2x"}
    second = build_plan([queued], available, now)
    assert second["timeline"][0]["seconds"] > first["timeline"][0]["seconds"]


def test_each_job_uses_its_stored_profile():
    now = datetime(2026, 10, 5, 8, tzinfo=ZONE)
    queued = job("A", 300)
    queued["machine_profile"] = PROFILE
    plan = build_plan([queued], Schedule.from_dict({}, ZONE), now)
    assert plan["jobs"][0]["completion"] == "2026-10-05T08:05:00+00:00"
