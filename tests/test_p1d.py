"""P1d regressions using isolated homes and synthetic inputs only."""

import json
from types import SimpleNamespace

import pytest
from test_model_registry import fake_model as fake_model

from videoenhancer.service.compare import render_compare, suggested_range
from videoenhancer.service.engine import Engine


def test_batch_estimate_uses_all_files_and_two_shared_plans(tmp_path, video_factory, monkeypatch):
    engine = Engine(tmp_path / "home")
    first, second = (
        video_factory(width=512, height=288, frames=30),
        video_factory(width=512, height=288, frames=60),
    )
    builds = []

    def plan(jobs, *_a, **_kw):
        builds.append(jobs)
        return {
            "jobs": [
                {"job_id": job["id"], "completion": f"2026-10-11T0{index}:00:00Z"}
                for index, job in enumerate(jobs)
            ]
        }

    monkeypatch.setattr("videoenhancer.service.engine._jobs_plan", plan)
    result = engine.estimate(
        {"files": [str(first), str(second)], "settings": {"backend": "cpu", "short_side": "keep"}}
    )
    assert len(builds) == 2
    assert all([job["id"] for job in jobs] == ["preview-0", "preview-1"] for jobs in builds)
    for preset in ("standard", "fast"):
        assert result["presets"][preset]["seconds"] == pytest.approx(
            sum(item["presets"][preset]["seconds"] for item in result["files"].values())
        )
        assert result["presets"][preset]["finish"] == "2026-10-11T01:00:00Z"
    assert not engine.store.list_jobs()
    engine.close()


def test_cancel_unstarted_removes_record_without_touching_original(tmp_path):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original")
    job["input"]["path"] = str(source)
    engine.store.save(job)
    result = engine.dispatch("POST", ["queue", job["id"], "cancel"], {})
    assert result["removed"] == job["id"]
    assert not engine.store.list_jobs()
    assert source.read_bytes() == b"original"
    engine.close()


def test_cancel_started_cleans_work_and_cannot_resume(tmp_path):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    job["segments"][0]["state"] = "done"
    engine.store.save(job)
    work = engine.store.job_dir(job["id"]) / "seg_0.mp4"
    work.write_bytes(b"work")
    output = tmp_path / "output.mp4"
    output.write_bytes(b"finished output")
    engine.dispatch("POST", ["queue", job["id"], "cancel"], {})
    assert not work.exists()
    assert output.read_bytes() == b"finished output"
    assert engine.store.load(job["id"])["state"] == "cancelled"
    with pytest.raises(ValueError, match="unfinished"):
        engine.dispatch("POST", ["queue", job["id"], "resume"], {})
    engine.close()


def test_history_undo_expiry_and_clear_keep_video_files(tmp_path, monkeypatch):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    engine.store.set_state(job["id"], "done")
    tick = [1000.0]
    monkeypatch.setattr("videoenhancer.service.engine.time.time", lambda: tick[0])
    callbacks = []

    class Timer:
        def __init__(self, seconds, callback):
            assert seconds == pytest.approx(10)
            callbacks.append(callback)

        def start(self):
            pass

        def cancel(self):
            pass

    monkeypatch.setattr("videoenhancer.service.engine.threading.Timer", Timer)
    request = {"ids": [job["id"]]}
    engine.dispatch("POST", ["history", "remove"], request)
    assert not engine.queue()["jobs"]
    tick[0] += 9.9
    engine.dispatch("POST", ["history", "undo"], request)
    assert len(engine.queue()["jobs"]) == 1
    callbacks[0]()
    assert len(engine.store.list_jobs()) == 1
    engine.dispatch("POST", ["history", "remove"], request)
    tick[0] += 10
    callbacks[-1]()
    assert not engine.store.list_jobs()
    _job(engine.store, tmp_path)
    engine.store.set_state(job["id"], "failed")
    result = engine.dispatch("POST", ["history", "clear"], {})
    assert result["undo_seconds"] == 10
    assert not engine.queue()["jobs"]
    tick[0] += 10
    callbacks[-1]()
    assert not engine.store.list_jobs()
    engine.close()


def test_schedule_preview_builds_only_expected_unless_range_requested(tmp_path, monkeypatch):
    engine = Engine(tmp_path / "home")
    builds = []
    monkeypatch.setattr(
        "videoenhancer.service.engine.build_plan",
        lambda *_: builds.append(True) or {"jobs": [], "timeline": []},
    )
    request = {"enabled": False}
    expected = engine.dispatch("POST", ["schedule", "preview"], request)
    assert len(builds) == 1
    assert "best" not in expected and "worst" not in expected
    bounds = engine.dispatch("POST", ["schedule", "preview"], {**request, "include_range": True})
    assert len(builds) == 4
    assert "best" in bounds and "worst" in bounds
    engine.close()


def test_event_clients_share_plan_without_timer_only_rebuilds(tmp_path, monkeypatch):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    builds = []
    monkeypatch.setattr(
        "videoenhancer.service.engine._jobs_plan",
        lambda *_a, **_k: builds.append(True) or {"jobs": [], "timeline": []},
    )
    tick = [0.0]
    monkeypatch.setattr("videoenhancer.service.engine.time.monotonic", lambda: tick[0])
    engine.event_snapshot()
    engine.event_snapshot()
    assert len(builds) == 1
    job["progress"] = {"frames_done": 10}
    engine.store.save(job)
    tick[0] = 4.9
    engine.event_snapshot()
    assert len(builds) == 1
    tick[0] = 5.0
    engine.event_snapshot()
    assert len(builds) == 1
    tick[0] = 60.0
    engine.event_snapshot()
    assert len(builds) == 1
    engine.store.set_state(job["id"], "paused")
    engine.event_snapshot()
    assert len(builds) == 2
    engine.dispatch("PUT", ["schedule"], {"enabled": False})
    engine.event_snapshot()
    assert len(builds) == 3
    engine.close()


def test_resume_all_preserves_individually_paused_jobs(tmp_path):
    from test_controller import _job

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    engine.dispatch("POST", ["queue", job["id"], "pause"], {})
    engine.dispatch("POST", ["processing"], {"paused": True})
    assert engine.health()["paused_all"]
    assert engine.store.load(job["id"])["state"] == "paused"
    engine.dispatch("POST", ["processing"], {"paused": False})
    assert not engine.health()["paused_all"]
    assert engine.store.load(job["id"])["state"] == "paused"
    engine.close()


def test_global_pause_aborts_running_step_without_pausing_the_job(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from test_controller import FakeClock, _job

    from videoenhancer.schedule import controller

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    stopped = []
    clock = FakeClock(datetime(2026, 10, 11, tzinfo=UTC), lambda: stopped.append(True))

    class Executor:
        def run(self, _job, _segment, _output, abort, **_kwargs):
            engine.dispatch("POST", ["processing"], {"paused": True})
            assert abort()
            return controller.SegmentResult("aborted")

    monkeypatch.setattr(controller, "validate_done_segments", lambda *_: False)
    controller.run_queue(
        ignore_schedule=True,
        home=engine.home,
        clock=clock,
        executor=Executor(),
        paused_all=lambda: engine.paused,
        stopped=lambda: bool(stopped),
    )
    result = engine.store.load(job["id"])
    assert result["state"] == "queued"
    assert result["segments"][0]["state"] == "pending"
    assert engine.health()["paused_all"]
    engine.close()


def test_pausing_one_video_admits_next_video(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from test_controller import FakeClock, _job

    from videoenhancer.schedule import controller

    engine = Engine(tmp_path / "home")
    first = _job(engine.store, tmp_path)
    second = {**first, "id": "second-job", "position": 2}
    engine.store.save(second)
    started = []

    class Executor:
        def run(self, job, _segment, _output, abort, **_kwargs):
            started.append(job["id"])
            if job["id"] == first["id"]:
                engine.dispatch("POST", ["queue", job["id"], "pause"], {})
                assert abort()
            return controller.SegmentResult("aborted")

    monkeypatch.setattr(controller, "validate_done_segments", lambda *_: False)
    controller.run_queue(
        ignore_schedule=True,
        home=engine.home,
        clock=FakeClock(datetime(2026, 10, 11, tzinfo=UTC)),
        executor=Executor(),
        stopped=lambda: len(started) == 2,
    )
    assert started == [first["id"], second["id"]]
    assert engine.store.load(first["id"])["state"] == "paused"
    engine.close()


def test_reference_delta_scales_whole_pipeline_and_rejects_other_gpu():
    from videoenhancer.estimate.model import model_delta
    from videoenhancer.models.registry import C1

    profile = {"gpu_name": "NVIDIA GeForce RTX 4060 Ti"}
    default = {"backend": "cuda", "preset": "standard"}
    assert model_delta(default, profile) == (0, True)
    delta, usable = model_delta({**default, "restore_model": "scunet-real-psnr"}, profile)
    assert usable
    assert delta == pytest.approx(1 / 0.5874732990888704 - 1 / 2.4727076215054278)
    assert model_delta({**default, "restore_model": C1}, profile) == (0, True)
    assert model_delta(
        {**default, "size_model": "span-liveaction-2x"}, {"gpu_name": "Other GPU"}
    ) == (0, False)


def test_cancelled_compare_keeps_completed_model_for_immediate_reuse(
    fake_model, video_factory, monkeypatch
):
    folder, model, registry = fake_model
    registry.add(folder)
    second = {**model, "id": "second-fixture"}
    (folder / "model.json").write_text(json.dumps(second))
    registry.add(folder)
    monkeypatch.setenv("VE_HOME", str(registry.home))
    engine = Engine(registry.home)
    settings = dict(
        preset="standard", restore_model=model["id"], backend="cpu", short_side="keep", fps="off"
    )
    monkeypatch.setattr(engine, "chosen", lambda _: settings)
    monkeypatch.setattr(engine, "geometry_warning", lambda *_: None)
    source = video_factory(frames=90)
    request = dict(file=str(source), seconds=3, models=[model["id"], second["id"]])
    op = engine.operation("compare", request)
    from videoenhancer.pipeline.runner import process_segment

    rendered = []

    def segment(job, *args, **kwargs):
        name = job["settings"]["restore_model"]
        rendered.append(name)
        if name == second["id"]:
            (engine.home / "previews" / op["id"] / "incomplete.mp4").write_bytes(b"unfinished")
            engine.cancel_operation(op["id"])
            raise InterruptedError("Cancelled after the first model became ready")
        return process_segment(job, *args, **kwargs)

    monkeypatch.setattr("videoenhancer.service.compare.process_segment", segment)
    monkeypatch.setattr(
        engine,
        "_run_operation",
        lambda operation: render_compare(operation["request"], engine.home / "previews" / op["id"]),
    )
    engine._auxiliary()
    assert op["state"] == "cancelled"
    old = engine.home / "previews" / op["id"]
    assert (old / f"{model['id']}-preview.mp4").is_file()
    assert not (old / "incomplete.mp4").exists()
    resumed = engine.operation("compare", {**request, "models": [model["id"]]})
    assert resumed["state"] == "done"
    assert resumed["result"]["items"][0]["reused"]
    assert resumed["result"]["original_reused"]
    assert rendered == [model["id"], second["id"]]
    assert not engine.processes
    engine.close()


def test_scene_cut_and_two_neighbours_do_not_win_motion_window(tmp_path):
    # CFR duplication makes source score indices differ from scene-cut indices.
    index = dict(media={"cfr_fps": "30"}, cfr_map=[i // 2 for i in range(450)])
    analysis = dict(
        scene_cuts=[120],
        motion_scores=[
            *[dict(frame=i, delta=255) for i in range(59, 61)],
            *[dict(frame=i, delta=1) for i in range(150, 225)],
        ],
    )
    assert suggested_range(tmp_path / "synthetic", analysis, index)["first_frame"] == 300


def test_hard_cut_in_real_calm_clip_is_excluded(tmp_path, ffmpeg_run):
    from videoenhancer.media.analyze import analyze

    source = tmp_path / "calm-cut.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "color=black:size=96x64:rate=30:duration=5",
        "-f",
        "lavfi",
        "-i",
        "color=white:size=96x64:rate=30:duration=10",
        "-filter_complex",
        "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        str(source),
    )
    analysis = analyze(source, backend="cpu")
    assert analysis["scene_cuts"] == [150]
    selection = suggested_range(source, analysis)
    assert not selection["first_frame"] <= 150 < selection["last_frame"]


def test_av1_minimum_uses_encoder_probes_not_rounded_capabilities(monkeypatch):
    from videoenhancer.media import encode

    monkeypatch.setattr(
        encode.importlib,
        "import_module",
        lambda _: SimpleNamespace(GetEncoderCaps=lambda *_: {"width_min": 192, "height_min": 128}),
    )
    tested = []

    def probe(width, height):
        tested.append((width, height))
        return (width >= 130 and height >= 66, None)

    monkeypatch.setattr(encode, "probe_av1", probe)
    assert encode.av1_minimum_size() == (130, 66)
    assert tested[-1] == (130, 66)


def test_av1_small_output_rejected_before_queue_record_created(
    tmp_path, monkeypatch, video_factory
):
    engine = Engine(tmp_path / "home")
    engine.environment.update(av1_min_width=130, av1_min_height=66)
    settings = dict(preset="passthrough", codec="av1", short_side="keep", fps="off", backend="cuda")
    source = video_factory(width=128, height=66)
    monkeypatch.setattr(engine, "chosen", lambda _: settings)
    message = "Output too small for AV1. Choose HEVC or a larger size."
    assert message in engine.estimate({"file": str(source), "settings": settings})["warnings"]
    with pytest.raises(ValueError, match="Output too small for AV1"):
        engine.dispatch("POST", ["queue"], {"file": str(source), "settings": settings})
    assert engine.store.list_jobs() == []
    engine.close()


@pytest.mark.parametrize(
    "key,valid,invalid",
    [
        ("restore_strength", ["light", "medium", "strong"], ["", "extreme", 0]),
        ("size_strength", [0.2, 0.6], [0, 1, "0.2"]),
    ],
)
def test_service_validates_strength_settings_and_job_overrides(tmp_path, key, valid, invalid):
    engine = Engine(tmp_path / "home")
    for value in valid:
        assert engine.dispatch("PUT", ["settings"], {key: value})[key] == value
        assert engine.chosen({key: value, "backend": "cpu"})[key] == value
    for value in invalid:
        with pytest.raises(ValueError):
            engine.dispatch("PUT", ["settings"], {key: value})
        with pytest.raises(ValueError):
            engine.chosen({key: value, "backend": "cpu"})
    engine.close()


def test_service_trial_percent_history_has_progress_and_terminal_sample(tmp_path, monkeypatch):
    engine = Engine(tmp_path / "home")
    op = dict(
        id="trial-fixture",
        kind="trial",
        state="running",
        request={
            "file": "synthetic.mp4",
            "seconds": 3,
            "settings": {"preset": "fast", "short_side": "keep", "fps": "off", "backend": "cpu"},
        },
    )
    folder = engine.home / "previews" / op["id"]
    folder.mkdir(parents=True)
    (folder / "progress.json").write_text(json.dumps({"percent": 40, "phase": "Processing"}))
    (folder / "result.json").write_text(json.dumps({"output_fps": 30}))
    monkeypatch.setattr(
        "videoenhancer.service.engine.probe",
        lambda *_a, **_k: SimpleNamespace(to_dict=lambda: {"cfr_fps": "30"}),
    )
    monkeypatch.setattr("videoenhancer.media.mux._run", lambda *_: None)
    monkeypatch.setattr("videoenhancer.config.executable", lambda _: "fixture")
    monkeypatch.setattr("videoenhancer.service.engine.load_machine_profile", lambda *_: None)
    import subprocess

    class Process:
        pid = 12345
        returncode = 0
        calls = 0

        def communicate(self, timeout):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("fixture", timeout)

    monkeypatch.setattr("videoenhancer.service.engine.proc.Popen", lambda *_a, **_k: Process())
    ticks = iter([0, 0, 0, 3, 3, 4, 4, 4])
    monkeypatch.setattr("videoenhancer.service.engine.time.monotonic", lambda: next(ticks))
    engine._run_operation(op)
    assert [sample["percent"] for sample in op["percent_history"]] == [0, 40, 100]
    assert op["percent_history"][-1]["terminal"]
    assert all(sample["time"] for sample in op["percent_history"])
