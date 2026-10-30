"""Real CPU Compare IPC and release before a queued processing part."""

import time

from videoenhancer.service.compare_worker import CompareWorker
from videoenhancer.service.engine import Engine


def request(source):
    return dict(
        file=str(source),
        start=0,
        seconds=3,
        models=["standard-resize"],
        settings=dict(
            preset="fast",
            backend="cpu",
            short_side="keep",
            fps="off",
            codec="h264",
        ),
    )


def test_compare_worker_reuse_error_and_shutdown(video_factory, tmp_path):
    source = video_factory(frames=180)
    worker = CompareWorker(tmp_path / "isolated")
    process = None
    try:
        for index in range(2):
            folder = tmp_path / f"preview-{index}"
            folder.mkdir()
            value = {**request(source), "start": index * 3}
            worker.begin(value, folder)
            assert worker.results.poll(30)
            success, result, retire = worker.results.recv()
            assert success, result
            assert not retire and result["items"][0]["id"] == "standard-resize"
            if process is None:
                process = worker.process
            assert worker.process.pid == process.pid
        folder = tmp_path / "failure"
        folder.mkdir()
        worker.begin({**request(source), "file": str(tmp_path / "missing.mp4")}, folder)
        assert worker.results.poll(30)
        success, error, retire = worker.results.recv()
        assert not success and retire and "FileNotFoundError" in error
    finally:
        worker.close()
    assert process is not None and not process.is_alive()
    assert worker.process is None


def test_engine_releases_compare_cache_before_processing(video_factory, tmp_path):
    source = video_factory(frames=180)
    home = tmp_path / "isolated"
    engine = Engine(home)
    engine.start()
    process = None
    try:
        operation = engine.operation("compare", request(source))
        deadline = time.monotonic() + 30
        while operation["state"] not in {"done", "failed"} and time.monotonic() < deadline:
            time.sleep(0.05)
        assert operation["state"] == "done", operation.get("error")
        process = engine.compare_worker.process
        assert process is not None and process.is_alive()
        job = engine.add(
            dict(
                file=str(source),
                output_folder=str(home / "output"),
                settings=request(source)["settings"],
            )
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            current = engine.store.load(job["id"])
            if current["state"] in {"done", "failed"}:
                assert current["state"] == "done", current.get("error")
                break
            time.sleep(0.05)
        else:
            raise AssertionError("CPU processing job did not finish")
        assert not process.is_alive()
        assert engine.compare_worker.process is None
    finally:
        engine.close()
    assert process is not None and not process.is_alive()
