"""P1e-2 contracts; every fixture uses its own home and synthetic data."""

import copy
import json
from datetime import UTC, datetime

import pytest

from videoenhancer.estimate.live import live_job


@pytest.mark.parametrize("indices", [[0, 1, 1, 4], [4, 2, 0]])
def test_core_decoder_matches_display_timestamps_and_requested_order(monkeypatch, indices):
    from types import SimpleNamespace

    import torch

    from videoenhancer.media.decode import IndexedDecoder

    class Demuxer:
        cursor = 0

        def GetNvCodecId(self):
            return "fixture"

        def GetTimebaseNum(self):
            return 1

        def GetTimebaseDen(self):
            return 30000

        def Seek(self, index):
            self.cursor = index + 1
            return SimpleNamespace(pts=index * 1001)

        def __iter__(self):
            while self.cursor < 5:
                index = self.cursor
                self.cursor += 1
                yield SimpleNamespace(pts=index * 1001)

    class Decoder:
        def Decode(self, packet):
            frame = torch.full((2, 2), packet.pts // 1001)
            frame.getPTS = lambda: packet.pts
            return [frame]

        def Flush(self):
            return []

    api = SimpleNamespace(
        CreateDemuxer=lambda **_options: Demuxer(),
        CreateDecoder=lambda **_options: Decoder(),
        OutputColorType=SimpleNamespace(NATIVE=0),
    )
    monkeypatch.setattr("videoenhancer.media.decode._load_pynvcodec", lambda: api)
    monkeypatch.setattr(
        torch.cuda, "current_stream", lambda: SimpleNamespace(synchronize=lambda: None)
    )
    decoder = IndexedDecoder(
        "synthetic.mp4",
        {"pixel_format": "yuv420p", "bit_depth": 8},
        "cuda",
        {
            "source_pts": [str(i * 1001) + "/30000" for i in range(5)],
            "keyframes": [{"index": i} for i in (0, 2, 4)],
        },
    )
    decoder._convert = lambda frame: frame.clone()
    try:
        assert [int(frame[0, 0]) for frame in decoder.frames(indices, lambda: False)] == indices
    finally:
        decoder.close()


def test_download_progress_uses_bytes_and_three_second_speed(monkeypatch):
    from videoenhancer.service.downloads import DownloadProgress

    clock = [0.0]
    monkeypatch.setattr("videoenhancer.service.downloads.time.monotonic", lambda: clock[0])
    tracker = DownloadProgress({"model.zip": 100 * 1024**2}, 1)
    percents = []
    for second in range(51):
        clock[0] = float(second)
        snapshot = tracker.feed(
            f"Downloading model.zip: {second * 2 * 1024**2} / {100 * 1024**2} bytes", 0
        )
        percents.append(snapshot["percent"])
        if second < 2:
            assert snapshot["remaining_seconds"] is None
        if second == 10:
            assert snapshot["bytes_per_second"] == 2 * 1024**2
            assert snapshot["remaining_seconds"] == pytest.approx(41.1953125)
    assert percents == sorted(percents)
    assert percents[1] > 0
    checked = tracker.feed(
        f"Checking model.zip.download: {100 * 1024**2} / {100 * 1024**2} bytes", 99
    )
    assert checked["percent"] < 100


def test_gpu_qualification_prediction_uses_measured_startup_and_small_input():
    from videoenhancer.service.downloads import gpu_test_prediction

    model = {"id": "fixture", "task": "restore"}
    profile = {
        "startup_by_preset": {"standard": 4.0},
        "models": {"fixture": {"seconds_per_pixel_frame": 0.000001}},
    }
    assert gpu_test_prediction(model, profile) == pytest.approx(4.196608)
    assert gpu_test_prediction(model, None) == 15


@pytest.mark.parametrize("changed", [False, True])
def test_gpu_phase_reuses_hash_only_for_unchanged_verified_weights(tmp_path, monkeypatch, changed):
    import hashlib
    import sys

    import torch

    from videoenhancer.models.registry import ModelRegistry
    from videoenhancer.service import operation

    registry = ModelRegistry(tmp_path)
    folder = registry.folder("fixture")
    folder.mkdir(parents=True)
    path = folder / "weights.bin"
    path.write_bytes(b"synthetic")
    info = path.stat()
    digest = hashlib.sha256(b"synthetic").hexdigest()
    verified = dict(bytes=info.st_size, mtime_ns=info.st_mtime_ns, sha256=digest)
    model = dict(id="fixture", weights=dict(filename=path.name, sha256=digest))
    monkeypatch.setattr(registry, "manifest", lambda _id: model)
    monkeypatch.setattr(operation, "ModelRegistry", lambda: registry)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    reads = []
    file_digest = hashlib.file_digest

    def counted(stream, algorithm):
        reads.append(True)
        return file_digest(stream, algorithm)

    monkeypatch.setattr(hashlib, "file_digest", counted)
    if changed:
        path.write_bytes(b"changed synthetic")
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            dict(
                kind="download",
                folder=str(tmp_path),
                request={
                    "model_id": "fixture",
                    "_network_only": False,
                    "_verified_weight": verified,
                },
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["operation", str(request)])
    with pytest.raises(
        ValueError if changed else RuntimeError,
        match="SHA-256 mismatch" if changed else "Couldn't test this model",
    ):
        operation.main()
    assert len(reads) == int(changed)


def test_download_starts_before_gpu_lease(tmp_path, monkeypatch):
    import threading

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    started, release = threading.Event(), threading.Event()

    def work(op):
        assert op["request"]["_network_only"]
        started.set()
        assert release.wait(3)

    monkeypatch.setattr(engine, "_run_operation", work)
    try:
        op = engine.operation("download", {"model_id": "synthetic-model"})
        assert started.wait(1)
        assert op["state"] == "running"
        release.set()
        engine.download_threads[op["id"]].join(2)
        assert op["state"] == "waiting"
        assert op["request"]["_network_only"] is False
    finally:
        release.set()
        engine.close()


def test_gpu_install_does_not_republish_network_percentage(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace

    import torch

    from videoenhancer.service import operation

    weights = tmp_path / "weights.bin"
    weights.write_bytes(b"synthetic")

    def verified_weights(_model, **options):
        assert options["download"] is False
        assert options["progress"] is None
        return weights

    registry = SimpleNamespace(
        manifest=lambda _id: {"weights": {"sha256": "fixture"}}, weights=verified_weights
    )
    monkeypatch.setattr(operation, "ModelRegistry", lambda: registry)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            dict(
                kind="download",
                folder=str(tmp_path),
                request={
                    "model_id": "fixture",
                    "_network_only": False,
                },
            )
        ),
        encoding="utf-8",
    )
    progress = tmp_path / "progress.json"
    progress.write_text('{"phase":"Testing on the GPU","percent":85}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["operation", str(request)])
    with pytest.raises(RuntimeError, match="Couldn't test this model"):
        operation.main()
    assert json.loads(progress.read_text(encoding="utf-8"))["percent"] == 85


def test_mixed_file_modes_and_folders_use_selected_plan(tmp_path, video_factory, monkeypatch):
    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    first = video_factory(width=512, height=288, frames=30)
    second = video_factory(width=512, height=288, frames=60)
    plans = []

    def plan(jobs, *_args, **_kwargs):
        plans.append(copy.deepcopy(jobs))
        return {
            "jobs": [dict(job_id=job["id"], completion=f"finish-{i}") for i, job in enumerate(jobs)]
        }

    monkeypatch.setattr("videoenhancer.service.engine._jobs_plan", plan)
    try:
        result = engine.estimate(
            dict(
                files=[str(first), str(second)],
                settings=dict(preset="standard", backend="cpu", short_side="keep"),
                file_settings={
                    str(second): dict(preset="fast", output_folder=str(tmp_path / "other"))
                },
            )
        )
        assert len(plans) == 3
        assert [job["settings"]["preset"] for job in plans[-1]] == ["standard", "fast"]
        assert result["files"][str(second)]["output"].startswith(str(tmp_path / "other"))
        assert result["selected_seconds"] == pytest.approx(
            result["files"][str(first)]["presets"]["standard"]["seconds"]
            + result["files"][str(second)]["presets"]["fast"]["seconds"]
        )
        assert result["selected_finish"] == "finish-1"
        assert not engine.store.list_jobs()
    finally:
        engine.close()


def test_lock_order_rejects_inversion_and_io_under_state_lock():
    from videoenhancer.service.locks import OrderedLock, assert_io_unlocked

    mutation = OrderedLock("mutation", 10, True)
    state = OrderedLock("state", 30, True)
    with mutation, state:
        with pytest.raises(RuntimeError, match="File operation"):
            assert_io_unlocked()
    with state:
        with pytest.raises(RuntimeError, match="inversion"):
            with mutation:
                pytest.fail("Inversion was accepted")


def test_watchdog_reports_holder_before_lock_is_released(tmp_path, monkeypatch):
    import threading

    from videoenhancer.service.engine import Engine

    reported = threading.Event()
    entries = []

    class Logger:
        def warning(self, *args):
            entries.append(args)
            reported.set()

    monkeypatch.setattr("videoenhancer.service.engine.get_logger", lambda home: Logger())
    engine = Engine(tmp_path / "home")
    try:
        with engine.lock:
            engine.lock.since -= 6
            engine._lock_watchdog.start()
            assert reported.wait(2)
            assert engine.lock.owner == threading.get_ident()
            assert "test_watchdog_reports_holder" in str(entries[0])
    finally:
        engine.close()


def test_missing_analysis_keeps_finished_details_and_reanalyses_queue(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from test_controller import _job

    from videoenhancer.jobs.store import ANALYSIS_FIELDS, JobStore

    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    sidecar = store.job_dir(job["id"]) / "analysis.json"
    sidecar.unlink()
    missing = store.load(job["id"])
    assert missing["analysis_missing"]
    calls = []

    def analyse(path, backend):
        calls.append((path, backend))
        return {key: job.get(key, []) for key in ANALYSIS_FIELDS}

    monkeypatch.setattr("videoenhancer.media.analyze.analyze", analyse)
    monkeypatch.setattr(
        "videoenhancer.jobs.store.probe",
        lambda *_args, **_kwargs: SimpleNamespace(to_dict=lambda: job["media"]),
    )
    restored = store.ensure_analysis(missing)
    assert restored["cfr_map"] == job["cfr_map"] and len(calls) == 1
    restored["state"] = "done"
    store.save(restored)
    sidecar.unlink()
    finished = store.load(job["id"])
    assert finished["state"] == "done"
    assert store.ensure_analysis(finished) is finished and len(calls) == 1


def test_restart_finishes_paused_history_removal_without_touching_video(tmp_path):
    from test_controller import _job

    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    job.update(state="done", history_hidden_until=31536000000, history_undo_remaining=9)
    engine.store.save(job)
    source = tmp_path / "input.mp4"
    before = source.read_bytes()
    try:
        engine._recover()
        assert engine.store.load_existing(job["id"]) is None
        assert source.read_bytes() == before
    finally:
        engine.close()


def test_startup_replays_completed_recycle_journal_without_restoring_file(tmp_path):
    from test_controller import _job
    from test_deletion import FakeFiles

    from videoenhancer.jobs.store import input_identity
    from videoenhancer.service.deletion import VideoDeletion
    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home", test_lock_order=True)
    try:
        job = _job(engine.store, engine.home)
        output = engine.home / "output.mp4"
        output.write_bytes(b"synthetic output")
        job.update(state="done", output_identity=input_identity(output))
        engine.store.save(job)
        engine.deletion = VideoDeletion(engine.home, FakeFiles())
        assert engine.deletion.delete(output, job, [job]) == "Moved to the Recycle Bin"
        assert "video_deletions" not in engine.store.load(job["id"])
        engine._recover()
        engine.refresh_terminal_files()
        assert engine.queue()["jobs"][0]["output_state"] == "recycled"
        assert not output.exists()
        assert output.with_suffix(".bin").exists()
    finally:
        engine.close()


def test_finalization_admission_reserves_margin_and_never_uses_overrun():
    from datetime import timedelta
    from types import SimpleNamespace

    from videoenhancer.schedule.admission import admit_step

    now = datetime(2026, 10, 14, tzinfo=UTC)
    assert not admit_step(
        100, True, now, SimpleNamespace(start=now, end=now + timedelta(seconds=209))
    )[0]
    assert admit_step(100, True, now, SimpleNamespace(start=now, end=now + timedelta(seconds=210)))[
        0
    ]
    assert not admit_step(
        100, True, now, SimpleNamespace(start=now, end=now + timedelta(seconds=10))
    )[0]


def test_oversized_source_is_refused_in_both_modes_on_any_gpu(tmp_path):
    from videoenhancer.jobs.checks import geometry_warning

    media = dict(width=3840, height=2160, display_width=3840, display_height=2160)
    settings = dict(preset="standard", short_side=1080, fps="2x", codec="hevc")
    capabilities = dict(vram_bytes=8 * 1024**3)
    expected = (
        "This video is larger than 1080p (short side 2160 px). "
        "VideoEnhancer processes videos up to 1080p."
    )
    assert geometry_warning(tmp_path, media, settings, capabilities) == expected
    assert (
        geometry_warning(tmp_path, media, {**settings, "preset": "fast"}, capabilities) == expected
    )


def test_saved_interpolation_model_is_ignored_for_sixty_fps():
    from videoenhancer.models.registry import selected_models

    assert "interpolate" not in selected_models(
        dict(preset="fast", fps="2x", interp_model="saved-choice"), dict(cfr_fps="60")
    )


def test_recorded_media_http_ranges_and_non_job_refusal(tmp_path):
    import threading
    import urllib.error
    import urllib.request

    from test_controller import _job

    from videoenhancer.jobs.store import input_identity
    from videoenhancer.service.engine import Engine
    from videoenhancer.service.server import APP_ORIGIN, LocalServer

    engine = Engine(tmp_path / "home")
    job = _job(engine.store, engine.home)
    output = engine.home / "output.mp4"
    payload = bytes(range(256)) * 4
    output.write_bytes(payload)
    job.update(state="done", output_identity=input_identity(output))
    engine.store.save(job)
    server = LocalServer(engine)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(range_value, path=None):
        headers = {"Origin": APP_ORIGIN, "Authorization": f"Bearer {server.token}"}
        if range_value is not None:
            headers["Range"] = range_value
        return urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/v1/{path or f'queue/{job["id"]}/video'}",
                headers=headers,
            ),
            timeout=5,
        )

    try:
        for header, start, end in [
            ("bytes=0-15", 0, 15),
            ("bytes=1000-", 1000, 1023),
            ("bytes=-10", 1014, 1023),
            ("bytes=1000-2000", 1000, 1023),
        ]:
            with request(header) as response:
                assert response.status == 206
                assert response.headers["Content-Range"] == f"bytes {start}-{end}/1024"
                assert response.read() == payload[start : end + 1]
        with request(None) as response:
            assert response.status == 200 and response.read() == payload
        for header in ("bytes=1024-", "bytes=5-4", "bytes=-0", "bytes=0-1,3-4"):
            with pytest.raises(urllib.error.HTTPError) as error:
                request(header)
            assert error.value.code == 416
            assert error.value.headers["Content-Range"] == "bytes */1024"
        with pytest.raises(urllib.error.HTTPError) as error:
            request("bytes=0-15", "queue/unrecorded/video")
        assert error.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as error:
            request("bytes=0-15", "queue/../../unrecorded.mp4/video")
        assert error.value.code in {400, 404}
    finally:
        engine.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("action", ["remove", "clear"])
def test_slow_removal_returns_immediately_and_keeps_http_sse_alive(tmp_path, action):
    import threading
    import time
    import urllib.request
    from pathlib import Path

    from test_controller import _job
    from test_deletion import FakeFiles

    from videoenhancer.jobs.store import input_identity
    from videoenhancer.service.deletion import VideoDeletion
    from videoenhancer.service.engine import Engine
    from videoenhancer.service.server import APP_ORIGIN, LocalServer

    class SlowFiles(FakeFiles):
        def recycle(self, path, post):
            time.sleep(2)
            return super().recycle(path, post)

    engine = Engine(tmp_path / "home", test_lock_order=True)
    engine.deletion = VideoDeletion(engine.home, SlowFiles())
    base = _job(engine.store, engine.home)
    base["state"] = "cancelled"
    engine.store.save(base)
    engine.remove(base["id"])
    ids = []
    for index in range(3):
        source = engine.home / f"source-{index}.mp4"
        output = engine.home / f"output-{index}.mp4"
        source.write_bytes(b"synthetic source")
        output.write_bytes(b"synthetic output")
        job = copy.deepcopy(base)
        job.update(
            id=f"record-{index}",
            state="done",
            input=input_identity(source),
            output=str(output),
            output_identity=input_identity(output),
        )
        engine.store.save(job)
        ids.append(job["id"])
    server = LocalServer(engine)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(path, body=None):
        return urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/v1/{path}",
                headers={
                    "Origin": APP_ORIGIN,
                    "Authorization": f"Bearer {server.token}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(body).encode() if body is not None else None,
            ),
            timeout=20,
        )

    try:
        with request("events") as events:
            start = time.monotonic()
            with request(
                f"history/{action}", dict(ids=ids, output=True, original=True)
            ) as response:
                operation = json.load(response)
            assert time.monotonic() - start < 1
            assert operation["kind"] == "history-removal"
            activity = []
            removed = set()
            finished = False
            while time.monotonic() - start < 20:
                line = events.readline()
                if line.startswith((b"event:", b": heartbeat")):
                    activity.append(time.monotonic())
                if line.startswith(b"data:"):
                    packet = json.loads(line.removeprefix(b"data: "))
                    for op in packet.get("queue", {}).get("operations", []):
                        if op["id"] == operation["id"]:
                            removed.update(op["result"]["ids"])
                            if op["state"] == "done":
                                assert op["completed_files"] == 6
                                assert op["result"]["files"]["moved"] == 6
                                finished = True
                if finished:
                    break
            assert finished
            assert removed == set(ids)
            assert max(b - a for a, b in zip(activity, activity[1:], strict=False)) <= 2
            assert all(engine.store.load(i)["history_hidden_until"] for i in ids)
            with request("history/undo", dict(ids=ids)) as response:
                assert set(json.load(response)["ids"]) == set(ids)
            assert all(engine.store.load(i)["history_hidden_until"] == 0 for i in ids)
            assert all(not Path(engine.store.load(i)["output"]).exists() for i in ids)
    finally:
        engine.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cumulative_rate_ignores_noisy_delta_and_blends_before_maturity():
    job = dict(
        settings={"preset": "passthrough", "short_side": "keep", "fps": "off"},
        media={"width": 32, "height": 32, "cfr_fps": "30"},
        correction_factor=1,
        machine_profile={"segment_overhead_seconds": 30},
        segments=[dict(index=0, start=0, end=100, state="running")],
    )
    early = live_job(job, dict(segment=0, frames_done=5, elapsed_seconds=3, fps=999))
    assert early["progress"]["cumulative_fps"] == pytest.approx(5 / 3)
    assert 5 / 3 < early["progress"]["fps"] < 100 / 30
    mature = live_job(job, dict(segment=0, frames_done=40, elapsed_seconds=20, fps=999))
    assert mature["progress"]["fps"] == 2
    assert mature["machine_profile"]["live_seconds_per_frame"] == 0.5
    assert "live_seconds_per_frame" not in job["machine_profile"]


def test_packet_and_snapshot_use_same_full_queue_data(tmp_path, monkeypatch):
    from zoneinfo import ZoneInfo

    from test_controller import _job

    from videoenhancer.schedule.planner import build_plan
    from videoenhancer.schedule.windows import Schedule
    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    try:
        running = _job(engine.store, tmp_path)
        running.update(state="running", position=1, correction_factor=2, analysis_seconds=3)
        running["segments"] = [
            dict(index=0, start=0, end=100, state="running"),
            dict(index=1, start=100, end=200, state="pending"),
        ]
        queued = copy.deepcopy(running)
        queued.update(id="aaaa", state="queued", position=2, correction_factor=1)
        for part in queued["segments"]:
            part["state"] = "pending"
        engine.store.save(running)
        engine.store.save(queued)
        now = datetime(2026, 10, 19, 8, tzinfo=UTC)
        schedule = Schedule.from_dict({"enabled": False}, ZoneInfo("UTC"))
        monkeypatch.setattr(
            "videoenhancer.service.engine._jobs_plan",
            lambda jobs, _home, days=120: build_plan(jobs, schedule, now, days),
        )
        monkeypatch.setattr("videoenhancer.service.engine.time.monotonic", lambda: 100.0)
        engine._progress(
            running,
            dict(
                phase="processing",
                step="Processing",
                segment=0,
                frames_done=40,
                elapsed_seconds=20,
                fps=999,
            ),
        )
        engine.event_snapshot()
        snapshot = engine.queue()
        packets = json.loads(engine.progress_message())["progress"]
        rows = {row["id"]: row for row in snapshot["jobs"]}
        for packet in packets:
            expected = datetime.fromisoformat(rows[packet["id"]]["eta"])
            actual = datetime.fromisoformat(packet["finish_time"])
            assert abs((actual - expected).total_seconds()) <= 1
        received = engine._progress_received[running["id"]][1]
        for key in ("correction_factor", "position", "created_at", "analysis_seconds"):
            assert received[key] == running[key]
    finally:
        engine.close()


def test_local_startup_is_median_of_named_disjoint_part_terms(tmp_path):
    from videoenhancer.estimate.local import apply_local, record_completed

    job = dict(
        id="synthetic",
        settings={"preset": "standard"},
        media={"frame_count": 300},
        machine_profile={"backend": "cuda", "gpu_name": "fixture", "driver": "fixture"},
        segments=[{"stats": {"per_part_startup_seconds": value}} for value in (5, 6, 100)],
    )
    record_completed(job, tmp_path)
    assert apply_local(tmp_path, job["machine_profile"])["segment_overhead_seconds"] == 6
