"""CLI parsing and local queue/schedule behavior without processing media."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from videoenhancer import cli


@pytest.mark.parametrize("command", ["probe", "enhance"])
def test_smart_app_control_block_is_specific_in_probe_and_enhance(
    command, video_factory, tmp_path, monkeypatch, capsys
):
    import importlib

    import torch

    from videoenhancer.media.decode import SMART_APP_CONTROL_MESSAGE

    source = video_factory(frames=2)
    monkeypatch.setenv("VE_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    original = importlib.import_module

    def blocked(name, *args, **kwargs):
        if name == "PyNvVideoCodec":
            error = OSError("Simulated blocked VersionCheck.cp312-win_amd64.pyd")
            error.winerror = 577
            raise error
        return original(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", blocked)
    args = ["--json", command, str(source)]
    if command == "enhance":
        args += ["-o", str(tmp_path / "output.mp4"), "--backend", "cuda"]
    assert cli.main(args) == 1
    assert SMART_APP_CONTROL_MESSAGE in json.loads(capsys.readouterr().err)["error"]


def test_help_lists_engine_commands(capsys: Any) -> None:
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])
    assert result.value.code == 0
    text = capsys.readouterr().out
    assert all(command in text for command in ("probe", "add", "queue", "schedule", "run", "bench"))


def test_schedule_commands_accept_json_anywhere(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setenv("VE_HOME", str(tmp_path))
    assert cli.main(["--json", "schedule", "set-weekly", "--window", "mon,tue@22:00-08:00"]) == 0
    configured = json.loads(capsys.readouterr().out)
    assert configured["weekly"] == [{"days": ["mon", "tue"], "start": "22:00", "end": "08:00"}]
    assert cli.main(["schedule", "enable", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["enabled"] is True
    assert (
        cli.main(["schedule", "add-exception", "--date", "2026-10-06", "--window", "off", "--json"])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["exceptions"][0]["windows"] == "off"
    assert cli.main(["schedule", "override", "--until", "job-complete", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["override_until"] == "job-complete"
    assert cli.main(["schedule", "remove-exception", "--date", "2026-10-06", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["exceptions"] == []


def test_schedule_rejects_non_quarter_hour(tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setenv("VE_HOME", str(tmp_path))
    result = cli.main(
        ["schedule", "set-weekly", "--days", "mon", "--start", "22:05", "--end", "08:00"]
    )
    assert result == 1
    assert "15-minute" in capsys.readouterr().err
    assert not (tmp_path / "schedule.json").exists()


def test_format_plan_shows_local_weekday_windows_and_progress() -> None:
    plan = {
        "days": [
            {
                "date": "2026-10-05",
                "windows": [
                    {"start": "2026-10-05T22:00:00-07:00", "end": "2026-10-06T00:00:00-07:00"}
                ],
                "run_hours": 2.0,
                "jobs": [
                    {
                        "job_id": "abcdef012345",
                        "start_percent": 0,
                        "end_percent": 8,
                        "completion": None,
                    }
                ],
            }
        ]
    }
    text = cli.format_plan(plan)
    assert "Mon 10/05" in text
    assert "22:00–24:00" in text
    assert "2.0h" in text
    assert "abcdef01: 0% → 8%" in text


def test_enhance_runs_only_newly_added_job(tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    from videoenhancer.estimate import Estimate
    from videoenhancer.jobs import store as jobs_store
    from videoenhancer.media import decode
    from videoenhancer.schedule import controller

    monkeypatch.setenv("VE_HOME", str(tmp_path))
    monkeypatch.setattr(decode, "choose_backend", lambda requested: "cpu")
    selected: dict[str, Any] = {}

    def add_job(_path: Any, settings: dict, **options: Any) -> dict:
        selected.update(settings)
        assert options["target_segment_seconds"] == 90
        return {
            "id": "fresh-job",
            "output": str(tmp_path / "enhanced.mp4"),
            "segments": [{"index": 0, "start": 0, "end": 30, "state": "pending"}],
            "state": "queued",
        }

    monkeypatch.setattr(jobs_store, "add_job", add_job)
    monkeypatch.setattr(cli, "_jobs_plan", lambda *_args: {"days": []})
    monkeypatch.setattr(
        "videoenhancer.estimate.estimate_job", lambda _job: Estimate(10, 8, 12, False)
    )

    def run_queue(*_args: Any, **kwargs: Any) -> None:
        assert kwargs["ignore_schedule"] is True
        assert kwargs["job_ids"] == {"fresh-job"}

    monkeypatch.setattr(controller, "run_queue", run_queue)
    monkeypatch.setattr(
        jobs_store.JobStore,
        "load",
        lambda _self, _id: {"state": "done", "result": str(tmp_path / "enhanced.mp4")},
    )
    assert (
        cli.main(
            [
                "enhance",
                "input.mp4",
                "--backend",
                "auto",
                "--batch-size",
                "9",
                "--segment-seconds",
                "90",
                "--pipeline-queue-size",
                "1",
                "--restore-model",
                "my-finetune",
                "--interp-model",
                "rife-4.25",
                "--json",
            ]
        )
        == 0
    )
    assert selected["backend"] == "cpu"
    assert selected["batch_size"] == 4
    assert selected["pipeline_queue_size"] == 1
    assert selected["restore_model"] == "my-finetune"
    assert selected["interp_model"] == "rife-4.25"
    assert json.loads(capsys.readouterr().out)["state"] == "done"


def test_probe_json_after_command(tmp_path: Path, monkeypatch: Any, capsys: Any) -> None:
    from videoenhancer.media import probe as media_probe

    monkeypatch.setenv("VE_HOME", str(tmp_path))
    data = {
        "path": str(tmp_path / "input.mp4"),
        "display_width": 720,
        "display_height": 1280,
        "width": 720,
        "height": 1280,
        "rotation": 0,
        "codec": "h264",
        "profile": "High",
        "bit_depth": 8,
        "average_fps": "30000/1001",
        "cfr_fps": "30000/1001",
        "is_vfr": False,
        "frame_count": 532,
        "frame_count_estimated": False,
        "duration": 17.75,
        "color_matrix": "bt709",
        "color_range": "tv",
        "audio_streams": [],
    }

    class Info:
        def to_dict(self) -> dict:
            return data

    monkeypatch.setattr(media_probe, "probe", lambda *_args, **_kwargs: Info())
    assert cli.main(["probe", "input.mp4", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["frame_count"] == 532
