import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from videoenhancer.schedule.windows import Schedule, resolve_wall

ZONE = ZoneInfo("America/New_York")


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=ZONE)


def schedule(weekly=(), exceptions=(), **extra):
    return Schedule.from_dict(
        {"enabled": True, "weekly": list(weekly), "exceptions": list(exceptions), **extra}, ZONE
    )


def test_disabled_allows_processing_and_roundtrip():
    value = Schedule.from_dict({}, ZONE)
    now = at("2026-10-05T12:00")
    assert value.current_interval(now) is not None
    assert value.next_interval(now).start == now
    assert Schedule.from_dict(value.to_dict()).to_dict() == value.to_dict()


def test_overnight_union_and_half_open_end():
    value = schedule(
        [
            {"days": ["mon"], "start": "22:00", "end": "08:00"},
            {"days": ["tue"], "start": "07:00", "end": "09:00"},
            {"days": ["tue"], "start": "12:00", "end": "13:00"},
        ]
    )
    interval = value.current_interval(at("2026-10-06T06:00"))
    assert interval.start == at("2026-10-05T22:00")
    assert interval.end == at("2026-10-06T09:00")
    assert value.current_interval(at("2026-10-06T09:00")) is None
    assert value.next_interval(at("2026-10-06T09:00")).start == at("2026-10-06T12:00")


def test_off_exception_removes_previous_day_spillover():
    value = schedule(
        [{"days": ["mon"], "start": "22:00", "end": "08:00"}],
        [{"date": "2026-10-06", "windows": "off"}],
    )
    assert value.current_interval(at("2026-10-05T23:00")).end == at("2026-10-06T00:00")
    assert value.current_interval(at("2026-10-06T01:00")) is None


def test_custom_overnight_exception_and_following_exception():
    value = schedule(
        exceptions=[
            {"date": "2026-10-05", "windows": [{"start": "23:00", "end": "02:00"}]},
        ]
    )
    assert value.current_interval(at("2026-10-06T01:00")).end == at("2026-10-06T02:00")
    value = schedule(
        exceptions=[
            {"date": "2026-10-05", "windows": [{"start": "23:00", "end": "02:00"}]},
            {"date": "2026-10-06", "windows": [{"start": "04:00", "end": "05:00"}]},
        ]
    )
    assert value.current_interval(at("2026-10-06T01:00")) is None
    assert value.current_interval(at("2026-10-06T04:30")) is not None


def test_override_is_union_and_expires():
    value = schedule(override_until="2026-10-05T12:00:00-04:00")
    assert value.current_interval(at("2026-10-05T11:00")).end == at("2026-10-05T12:00")
    assert value.current_interval(at("2026-10-05T12:00")) is None
    assert schedule(override_until="job-complete").current_interval(at("2026-10-05T12:00"))


def test_spring_gap_resolves_first_valid_instant():
    value = schedule([{"days": ["sun"], "start": "02:15", "end": "04:00"}])
    interval = value.current_interval(at("2026-03-08T03:15"))
    assert interval.start == at("2026-03-08T03:00")
    assert interval.seconds == 3600
    assert resolve_wall(datetime(2026, 3, 8, 2, 45), ZONE) == at("2026-03-08T03:00")


def test_fall_fold_uses_earliest_occurrence_and_elapsed_hours():
    value = schedule([{"days": ["sun"], "start": "01:15", "end": "02:15"}])
    interval = value.current_interval(at("2026-11-01T01:30").replace(fold=1))
    assert interval.start.fold == 0
    assert interval.seconds == 7200
    assert interval.end.astimezone(UTC) - interval.start.astimezone(UTC) == timedelta(hours=2)


@pytest.mark.parametrize("clock", ["09:01", "09:59", "9:00", "24:00", "-1:00"])
def test_clock_validation(clock):
    with pytest.raises(ValueError):
        schedule([{"days": ["mon"], "start": clock, "end": "10:00"}])


def test_equal_times_mean_full_day_and_minimum_quarter_hour():
    value = schedule([{"days": ["mon"], "start": "08:00", "end": "08:00"}])
    assert value.current_interval(at("2026-10-05T09:00")).seconds == 86400
    assert schedule([{"days": ["mon"], "start": "08:00", "end": "08:15"}]).current_interval(
        at("2026-10-05T08:00")
    )


def test_duplicate_exception_and_invalid_days():
    with pytest.raises(ValueError, match="Duplicate"):
        schedule(exceptions=[{"date": "2026-10-05", "windows": "off"}] * 2)
    with pytest.raises(ValueError, match="Weekly days"):
        schedule([{"days": ["Monday"], "start": "08:00", "end": "09:00"}])


def test_connected_weekly_windows_wait_for_future_exception():
    value = schedule(
        [
            {
                "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "start": "00:00",
                "end": "00:00",
            }
        ],
        [{"date": "2026-11-01", "windows": "off"}],
    )
    assert value.current_interval(at("2026-10-05T12:00")).end == at("2026-11-01T00:00")


def test_fold_clipping_uses_elapsed_instants():
    value = schedule([{"days": ["sun"], "start": "01:00", "end": "02:00"}])
    left = at("2026-11-01T01:30").replace(fold=0)
    right = at("2026-11-01T01:45").replace(fold=1)
    interval = value.available_intervals(left, right)[0]
    assert interval.seconds == 75 * 60


def test_job_complete_override_cleared_without_losing_settings(tmp_path):
    source = tmp_path / "schedule.json"
    config = {"enabled": True, "weekly": [], "override_until": "job-complete"}
    source.write_text(json.dumps(config), encoding="utf-8")
    assert Schedule.clear_job_complete_override(source)
    assert json.loads(source.read_text(encoding="utf-8")) == {**config, "override_until": None}
    assert list(tmp_path.glob("*.tmp")) == []
    assert not Schedule.clear_job_complete_override(source)
    source.write_text(json.dumps({**config, "override_until": "2026-10-05T12:00:00Z"}))
    assert not Schedule.clear_job_complete_override(source)
