"""Synthetic admission, recovery and bounded diagnostic regressions."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from videoenhancer.jobs.store import input_identity
from videoenhancer.service.video_links import VideoLinks, best_format


@pytest.mark.parametrize("depth", [8, 10, 12])
def test_real_hevc_depth_admission(tmp_path, ffmpeg_run, depth):
    from videoenhancer.media.analyze import analyze

    source = tmp_path / "synthetic.mkv"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=96x64:rate=30",
        "-frames:v",
        "3",
        "-c:v",
        "libx265",
        "-preset",
        "ultrafast",
        "-x265-params",
        "log-level=error:pools=1",
        "-pix_fmt",
        f"yuv420p{depth}le" if depth > 8 else "yuv420p",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        str(source),
    )
    if depth > 10:
        with pytest.raises(ValueError) as refused:
            analyze(source, backend="cpu")
        assert str(refused.value) == (
            "This video uses 12-bit color. VideoEnhancer accepts 8-bit and 10-bit videos only."
        )
        from videoenhancer.service.engine import Engine

        engine = Engine(tmp_path / "admission-home")
        request = dict(file=str(source), settings=dict(backend="cpu", preset="fast", codec="h264"))
        try:
            assert engine.estimate(request)["warnings"][0] == str(refused.value)
            with pytest.raises(ValueError) as api_refused:
                engine.dispatch("POST", ["queue"], request)
            assert str(api_refused.value) == str(refused.value)
            assert engine.store.list_jobs() == []
        finally:
            engine.close()
    else:
        assert analyze(source, backend="cpu")["media"]["bit_depth"] == depth


def test_links_never_choose_high_depth_even_without_geometry():
    from videoenhancer.media.admission import color_warning

    invalid = dict(format_id="12", bit_depth=12)
    valid = dict(format_id="10", bit_depth=10, width=1920, height=1080)
    assert best_format([invalid, valid], 1080) == valid
    assert best_format([invalid], 1080) is None
    assert color_warning({"pix_fmt": "p016le"}) == (
        "This video uses 16-bit color. VideoEnhancer accepts 8-bit and 10-bit videos only."
    )


def test_download_recovery_uses_recorded_bytes_and_case_insensitive_name(tmp_path):
    home = tmp_path / "home"
    job_id = "a" * 32
    work = home / "jobs" / job_id
    work.mkdir(parents=True)
    target = tmp_path / "Video.mkv"
    target.write_bytes(b"finished synthetic download")
    expected = input_identity(target)
    expected["path"] = str(tmp_path / "video.mkv")
    (work / "download-commit.json").write_text(json.dumps(dict(identity=expected, timestamp=123)))
    links = VideoLinks(home, SimpleNamespace())
    job = dict(id=job_id, input={"path": expected["path"]}, source={})
    assert links.download(job, lambda: False, lambda _: None, lambda _: None) == target
    assert job["source"]["timestamp"] == 123


def test_odd_width_reuse_compares_projection_width(tmp_path):
    target = tmp_path / "video.mkv"
    target.write_bytes(b"synthetic")
    job = dict(
        id="a",
        input=input_identity(target),
        media=dict(display_width=320, display_height=180, duration=10),
        source=dict(extractor_key="Generic", id="v", url="http://localhost/v", timestamp=1),
    )
    entry = dict(
        extractor_key="Generic",
        id="v",
        webpage_url="http://localhost/v",
        timestamp=1,
        width=321,
        height=180,
        duration=10,
    )
    links = VideoLinks.__new__(VideoLinks)
    assert links.reusable(entry, SimpleNamespace(queue_jobs=lambda: [job]))["job_id"] == "a"


def test_bounded_failure_collector_keeps_logs_and_never_truncates_trace(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "collector", Path(__file__).parents[1] / "scripts/collect_e2e_failure.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.log").write_bytes(b"event")
    (source / "trace.zip").write_bytes(b"x" * 20)
    (source / "serve.json").write_text("not a log; do not collect")
    target = tmp_path / "collected"
    result = module.collect(source, target, limit=10)
    assert result["bytes"] == 5
    assert (target / "app.log").read_bytes() == b"event"
    assert not (target / "trace.zip").exists()
    assert not (target / "serve.json").exists()


def test_quit_interrupts_downloaded_analysis_and_keeps_it_resumable(tmp_path, monkeypatch):
    import threading

    from videoenhancer.service.link_jobs import LinkJobs

    final = tmp_path / "download.mkv"
    final.write_bytes(b"synthetic finished download")
    job = dict(
        id="a" * 32, state="downloading", settings={}, source={}, download={}, output="out.mp4"
    )
    store = SimpleNamespace(load=lambda _: job, load_existing=lambda _: job)
    store.patch_existing = lambda _, patch: job.update(patch)
    engine = SimpleNamespace(
        store=store,
        stop=threading.Event(),
        paused=False,
        processes={},
        _preparations=[],
        _mutation_lock=threading.RLock(),
        home=tmp_path,
        video_links=SimpleNamespace(download=lambda *args: final),
    )
    monkeypatch.setattr(
        "videoenhancer.service.link_jobs.probe", lambda *a, **k: SimpleNamespace(to_dict=lambda: {})
    )

    def prepare(*args, cancelled, **kwargs):
        assert job["state"] == "preparing"
        engine.stop.set()
        assert cancelled()
        raise InterruptedError("Analysis paused.")

    monkeypatch.setattr("videoenhancer.service.link_jobs.add_job", prepare)
    coordinator = LinkJobs(engine)
    coordinator.pending[job["id"]] = None
    coordinator.download(job["id"])
    assert job["state"] == "downloading"
    assert job["download"]["phase"] == "Paused"
    assert job["id"] in coordinator.pending
    assert final.read_bytes() == b"synthetic finished download"
    assert not coordinator.active


def test_link_tool_changes_are_refused_during_downloads(tmp_path):
    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path)
    engine.link_jobs.active["synthetic"] = SimpleNamespace()
    try:
        for action in ("install", "uninstall"):
            with pytest.raises(ValueError, match="download"):
                engine.link_tools_operation(action, {})
    finally:
        engine.link_jobs.active.clear()
        engine.close()


@pytest.mark.gpu
@pytest.mark.parametrize("depth", [8, 10])
def test_native_analysis_reuses_first_decode_with_identical_metrics(
    tmp_path, ffmpeg_run, gpu_available, depth, monkeypatch
):
    from videoenhancer.media import analyze as module

    source = tmp_path / "native.mkv"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=256x144:rate=30",
        "-frames:v",
        "24",
        "-c:v",
        "libx265",
        "-preset",
        "ultrafast",
        "-x265-params",
        "log-level=error:pools=1",
        "-pix_fmt",
        f"yuv420p{depth}le" if depth > 8 else "yuv420p",
        str(source),
    )
    original = module._thumbnails

    def no_second_native_pass(path, media, backend):
        assert backend != "cuda", "Analysis decoded the native source twice."
        return original(path, media, backend)

    monkeypatch.setattr(module, "_thumbnails", no_second_native_pass)
    result = module.analyze(source, "cuda")
    assert result["decoder"] == "nvdec"
    frames = list(original(source, result["media"], "cuda"))
    expected = [
        dict(frame=i, delta=round(module._cut_score(frames[i - 1], frames[i])[0], 3))
        for i in range(1, len(frames))
    ]
    assert result["motion_scores"] == expected
    assert len(frames) == result["media"]["source_frame_count"] == 24


def test_legacy_high_depth_fails_next_start_without_changing_finished_history(tmp_path):
    from videoenhancer.jobs.store import JobStore
    from videoenhancer.schedule.controller import run_queue

    source = tmp_path / "synthetic-placeholder.mkv"
    source.write_bytes(b"metadata-only fixture")
    store = JobStore(tmp_path / "home")
    for job_id, state in [("queued-depth", "queued"), ("finished-depth", "done")]:
        store.save(
            dict(
                schema_version=1,
                id=job_id,
                input={"path": str(source)},
                output=str(tmp_path / f"{job_id}.mp4"),
                state=state,
                settings=dict(
                    preset="fast", backend="cuda", short_side=1080, fps="off", codec="hevc"
                ),
                media=dict(
                    width=1920,
                    height=1080,
                    display_width=1920,
                    display_height=1080,
                    cfr_fps="30",
                    duration=1,
                    frame_count=30,
                    bit_depth=12,
                    pixel_format="yuv420p12le",
                ),
                segments=[dict(index=0, start=0, end=30, state="pending", predicted_seconds=1)],
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
    finished = store.job_dir("finished-depth") / "manifest.json"
    before = finished.read_bytes()
    run_queue(home=store.home, ignore_schedule=True)
    queued = store.load("queued-depth")
    assert queued["state"] == "failed"
    assert (
        queued["error"]
        == "This video uses 12-bit color. VideoEnhancer accepts 8-bit and 10-bit videos only."
    )
    assert queued["media"]["bit_depth"] == 12
    assert finished.read_bytes() == before
    assert source.read_bytes() == b"metadata-only fixture"
