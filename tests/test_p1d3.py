import json
import os

import pytest
from test_service import api as api

from videoenhancer.jobs.store import load_machine_profile


def test_profile_selection_exact_newest_builtin_defaults(tmp_path):
    directory = tmp_path / "profiles"
    directory.mkdir()
    base = dict(
        schema_version=1, backend="cuda", gpu_name="NVIDIA GeForce RTX 4060 Ti", components={}
    )
    for driver, timestamp in [("old", 100), ("new", 200)]:
        path = directory / f"{driver}.json"
        path.write_text(json.dumps({**base, "driver": driver}), encoding="utf-8")
        os.utime(path, (timestamp, timestamp))
    exact = load_machine_profile(tmp_path, gpu_name=base["gpu_name"], driver="old")
    assert exact["driver"] == "old" and exact["source"] == "measured"
    newest = load_machine_profile(tmp_path, gpu_name=base["gpu_name"], driver="different")
    assert newest["driver"] == "new" and newest["source"] == "measured"
    assert (
        newest["driver_note"] == "Speed measured with driver new. This PC now has driver different."
    )
    builtin = load_machine_profile(
        tmp_path / "fresh", gpu_name=base["gpu_name"], driver="different"
    )
    assert builtin["source"] == "builtin"
    assert (
        load_machine_profile(tmp_path / "fresh", gpu_name="Unmeasured GPU", driver="different")
        is None
    )


def test_driver_change_preserves_first_estimate(tmp_path):
    from videoenhancer.estimate import estimate_job

    gpu = "NVIDIA GeForce RTX 4060 Ti"
    profile = load_machine_profile(tmp_path, gpu_name=gpu, driver="617.42")
    folder = tmp_path / "profiles"
    folder.mkdir()
    (folder / "measurement.json").write_text(json.dumps(profile), encoding="utf-8")
    current = load_machine_profile(tmp_path, gpu_name=gpu, driver="new-driver")
    job = dict(
        settings=dict(preset="standard", backend="cuda", fps="2x", short_side=1080),
        media=dict(
            width=720,
            height=1280,
            display_width=720,
            display_height=1280,
            cfr_fps="30",
            frame_count=900,
        ),
        segments=[dict(start=0, end=900, state="pending")],
    )
    first, changed = estimate_job(job, profile), estimate_job(job, current)
    assert changed.seconds == pytest.approx(first.seconds, rel=0.001)
    assert changed.calibrated
    assert current["driver_note"].endswith("driver new-driver.")


def test_unknown_model_has_distinct_status(tmp_path, monkeypatch):
    from videoenhancer.estimate import estimate_job

    profile = load_machine_profile(tmp_path, gpu_name="NVIDIA GeForce RTX 4060 Ti", driver="617.42")
    monkeypatch.setattr("videoenhancer.estimate.model._reference_speed", lambda *_: {})
    job = dict(
        settings=dict(
            preset="standard",
            backend="cuda",
            fps="2x",
            short_side=1080,
            restore_model="fixture-without-reference",
        ),
        media=dict(
            width=720,
            height=1280,
            display_width=720,
            display_height=1280,
            cfr_fps="30",
            frame_count=900,
        ),
        segments=[dict(start=0, end=900, state="pending")],
    )
    result = estimate_job(job, profile)
    assert result.unknown_models == ("fixture-without-reference",)
    assert result.profile_source == "builtin"
    assert not result.calibrated


def test_builtin_finalization_observation_does_not_write_package_data(tmp_path):
    from videoenhancer.estimate.model import observe_finalization

    profile = load_machine_profile(tmp_path, gpu_name="NVIDIA GeForce RTX 4060 Ti", driver="617.42")
    from pathlib import Path

    path = Path(profile["profile_path"])
    before = path.read_bytes()
    job = {"machine_profile": profile}
    observe_finalization(job, 2, 1, tmp_path)
    assert path.read_bytes() == before
    assert job["timing"]["finalization_observation"] == {"predicted": 2, "actual": 1}


def test_multifile_totals_preserve_unknown_model_status(api, video_factory, monkeypatch):
    from videoenhancer.estimate.model import Estimate

    monkeypatch.setattr(
        "videoenhancer.service.engine.estimate_job",
        lambda *_: Estimate(10, 8, 12, False, ("fixture-without-reference",)),
    )
    _, _, request = api
    source = video_factory(frames=12)
    with request(
        "estimate", "POST", {"files": [str(source)], "settings": {"backend": "cpu"}}
    ) as response:
        result = json.load(response)
    assert result["presets"]["standard"]["unknown_models"] == ["fixture-without-reference"]


def test_operation_retries_transient_progress_file_sharing(tmp_path, monkeypatch):
    import subprocess
    from pathlib import Path

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path)
    op = {"id": "sharing", "kind": "verify", "request": {}}
    folder = tmp_path / "previews" / op["id"]
    folder.mkdir(parents=True)
    (folder / "progress.json").write_text('{"percent":25}')
    (folder / "result.json").write_text('{"verified":true}')
    original = Path.read_text
    reads = []

    def read(path, *args, **kwargs):
        if path.name == "progress.json":
            reads.append(path)
            if len(reads) == 1:
                raise PermissionError("synthetic atomic publication sharing violation")
        return original(path, *args, **kwargs)

    class Child:
        returncode = 0

        def __init__(self, *args, **kwargs):
            self.calls = 0

        def communicate(self, timeout):
            self.calls += 1
            if self.calls < 3:
                raise subprocess.TimeoutExpired("synthetic", timeout)

        def poll(self):
            return 0

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr("videoenhancer.service.engine.proc.Popen", Child)
    engine._run_operation(op)
    assert len(reads) == 2 and op["percent"] == 25 and op["result"]["verified"]
    engine.close()


def test_failed_operation_stops_child_before_forgetting_it(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path)
    op = {"id": "failed-child", "kind": "verify", "state": "waiting", "request": {}}
    engine.operations[op["id"]] = op
    killed = []

    def fail(operation):
        engine.processes[operation["id"]] = SimpleNamespace(pid=12345, poll=lambda: None)
        raise PermissionError("synthetic operation failure")

    monkeypatch.setattr(engine, "_run_operation", fail)
    monkeypatch.setattr("videoenhancer.service.engine._kill_process_tree", killed.append)
    engine._auxiliary()
    assert op["state"] == "failed" and killed == [12345]
    assert not engine.processes
    engine.close()


@pytest.mark.parametrize("transfer", ["smpte2084", "arib-std-b67"])
def test_mixed_hdr_request_is_per_file_and_add_is_blocked(api, video_factory, transfer):
    import urllib.error

    _engine, _, request = api
    ordinary = video_factory(frames=12)
    hdr = video_factory(frames=12, transfer=transfer)
    settings = dict(preset="passthrough", backend="cpu", codec="h264", short_side="keep", fps="off")
    with request(
        "estimate", "POST", {"files": [str(ordinary), str(hdr)], "settings": settings}
    ) as response:
        result = json.load(response)
    assert not any("HDR" in warning for warning in result["files"][str(ordinary)]["warnings"])
    assert any("HDR" in warning for warning in result["files"][str(hdr)]["warnings"])
    assert result["files"][str(ordinary)]["presets"]["standard"]["seconds"] > 0
    with pytest.raises(urllib.error.HTTPError) as error:
        request("queue", "POST", {"file": str(hdr), "settings": settings})
    assert error.value.code == 400
    assert "HDR" in json.loads(error.value.read())["error"]


def test_api_cleanup_and_smart_app_control_are_blocking(api, video_factory):
    import urllib.error

    engine, _, request = api
    source = video_factory(width=96, height=64)
    settings = dict(preset="standard", backend="cpu", codec="h264", short_side="keep", fps="off")
    with pytest.raises(urllib.error.HTTPError) as error:
        request("queue", "POST", {"file": str(source), "settings": settings})
    assert "cleanup" in json.loads(error.value.read())["error"]
    engine.last_error = dict(
        message="Smart App Control is blocking FFmpeg", job_id=None, time="fixture"
    )
    with pytest.raises(urllib.error.HTTPError) as error:
        request(
            "queue",
            "POST",
            {"file": str(source), "settings": {**settings, "preset": "passthrough"}},
        )
    assert "Smart App Control" in json.loads(error.value.read())["error"]


def test_cli_add_cannot_bypass_cleanup_check(tmp_path, video_factory):
    from videoenhancer.jobs.store import add_job

    source = video_factory(width=96, height=64)
    with pytest.raises(ValueError, match="cleanup"):
        add_job(
            source,
            dict(preset="standard", backend="cpu", codec="h264", short_side="keep", fps="off"),
            home=tmp_path / "home",
            output=tmp_path / "output.mp4",
        )


def test_progress_packets_change_without_rebuilding_history(tmp_path, monkeypatch):
    from test_controller import _job

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    job["state"] = "running"
    job["segments"][0]["state"] = "running"
    engine.store.save(job)
    builds = []
    monkeypatch.setattr(
        "videoenhancer.service.engine._jobs_plan",
        lambda *_a, **_k: builds.append(1) or {"jobs": [], "timeline": []},
    )
    tick = [100.0]
    monkeypatch.setattr("videoenhancer.service.engine.time.monotonic", lambda: tick[0])
    first = engine.event_message()
    engine._progress(
        job,
        dict(
            frames_done=2,
            fps=1,
            elapsed_seconds=2,
            segment=0,
            phase="processing",
            step="Processing",
        ),
    )
    before = json.loads(engine.progress_message())["progress"][0]
    tick[0] = 101.1
    after = json.loads(engine.progress_message())["progress"][0]
    assert after["work_left"] < before["work_left"]
    assert after["percent"] > before["percent"]
    assert engine.event_message() == first
    assert len(builds) == 3  # Structural plan once; two live finish-time forecasts.
    engine.close()


def test_idle_events_do_not_stat_history_each_second(tmp_path, monkeypatch):
    from test_controller import _job

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    engine.store.set_state(job["id"], "done")
    engine.event_message()
    calls = []
    original = os.stat

    def counted(path, *args, **kwargs):
        if "manifest.json" in str(path):
            calls.append(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", counted)
    for _ in range(5):
        engine.event_message()
    assert calls == []
    engine.close()


def test_direct_health_reuses_compact_metadata_and_invalidates_on_change(tmp_path, monkeypatch):
    from test_controller import _job

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    engine.store.set_state(job["id"], "running")
    expected = engine.health(engine.store.event_state()[1])
    calls = []
    original = engine.store.event_state

    def compact():
        calls.append(True)
        return original()

    def full(*args, **kwargs):
        raise AssertionError("Health must not copy full terminal manifests.")

    monkeypatch.setattr(engine.store, "event_state", compact)
    monkeypatch.setattr(engine.store, "list_jobs", full)
    assert engine.health() == expected
    assert engine.health() == expected
    assert calls == [True]
    engine.store.set_state(job["id"], "done")
    assert engine.health()["job_id"] is None
    assert calls == [True, True]
    engine.close()


def test_api_free_space_and_av1_minimum_are_enforced(api, video_factory, monkeypatch):
    import urllib.error
    from types import SimpleNamespace

    engine, _, request = api
    source = video_factory(width=128, height=64)
    settings = dict(preset="passthrough", backend="cpu", codec="h264", short_side="keep", fps="off")
    with monkeypatch.context() as context:
        context.setattr(
            "videoenhancer.service.engine.shutil.disk_usage", lambda _path: SimpleNamespace(free=0)
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            request("queue", "POST", {"file": str(source), "settings": settings})
        assert "Insufficient space" in json.loads(error.value.read())["error"]
    engine.environment.update(av1_supported=True, av1_min_width=130, av1_min_height=66)
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda *_: "cuda")
    with pytest.raises(urllib.error.HTTPError) as error:
        request(
            "queue",
            "POST",
            {"file": str(source), "settings": {**settings, "backend": "cuda", "codec": "av1"}},
        )
    assert "AV1" in json.loads(error.value.read())["error"]


def test_cli_add_enforces_detected_av1_minimum(tmp_path, video_factory, monkeypatch):
    from videoenhancer.jobs.store import add_job
    from videoenhancer.media.probe import probe

    source = video_factory(width=128, height=64)
    media = probe(source).to_dict()
    monkeypatch.setattr(
        "videoenhancer.media.analyze.analyze", lambda *_args, **_kwargs: {"media": media}
    )
    monkeypatch.setattr(
        "videoenhancer.logging.environment_info", lambda: dict(gpu="fixture", driver="fixture")
    )
    monkeypatch.setattr(
        "videoenhancer.service.av1_cache.capabilities",
        lambda *_: dict(av1_supported=True, av1_min_width=130, av1_min_height=66),
    )
    with pytest.raises(ValueError, match="AV1"):
        add_job(
            source,
            dict(preset="passthrough", backend="cuda", codec="av1", short_side="keep", fps="off"),
            home=tmp_path / "home",
            output=tmp_path / "output.mp4",
        )
