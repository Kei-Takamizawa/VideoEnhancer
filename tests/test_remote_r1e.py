"""Reliability regressions using only synthetic data and isolated homes."""

import http.client
import json
import logging
import os
import ssl
import threading
import time

import pytest
from test_remote_gateway import gateway as gateway_fixture
from test_remote_gateway import pair, request


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    yield from gateway_fixture.__wrapped__(tmp_path, monkeypatch)


def test_ranges_reuse_connection_and_cache_validators(gateway):
    cookie = pair(gateway)
    library = gateway.adapter.library
    library.folder.mkdir(exist_ok=True)
    path = library.folder / "synthetic.mp4"
    path.write_bytes(b"0123456789")
    route = f"/api/library/{library._identifier(path)}/video"
    context = ssl.create_default_context(cafile=str(gateway.home / "remote/ca.crt"))
    conn = http.client.HTTPSConnection("127.0.0.1", gateway.https_port, context=context)
    try:
        headers = {"Cookie": cookie, "Range": "bytes=1-3"}
        conn.request("GET", route, headers=headers)
        response = conn.getresponse()
        assert response.read() == b"123"
        assert response.getheader("Cache-Control") == "private, max-age=86400"
        assert response.getheader("Connection") != "close"
        etag = response.getheader("ETag")
        modified = response.getheader("Last-Modified")
        assert etag and not etag.startswith("W/") and modified
        sock = conn.sock
        for validator, expected, body in [
            (etag, 206, b"123"),
            (modified, 206, b"123"),
            ('"old"', 200, b"0123456789"),
            ("W/" + etag, 200, b"0123456789"),
        ]:
            conn.request("GET", route, headers={**headers, "If-Range": validator})
            response = conn.getresponse()
            assert response.status == expected
            assert response.read() == body
            assert conn.sock is sock
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1000000000))
        conn.request("GET", route, headers={**headers, "If-Range": etag})
        response = conn.getresponse()
        assert response.status == 200
        assert response.getheader("ETag") != etag
        response.read()
    finally:
        conn.close()
    status, headers, _ = request(gateway, route.rsplit("/", 1)[0], "DELETE", cookie=cookie)
    assert status == 200
    assert headers["Clear-Site-Data"] == '"cache"'
    assert headers["Cache-Control"] == "no-store"


def test_second_upload_start_is_conflict(gateway):
    cookie = pair(gateway)
    body = json.dumps({"name": "synthetic.mp4", "size": 2})
    assert request(gateway, "/api/uploads", "POST", cookie=cookie, body=body)[0] == 200
    status, headers, result = request(gateway, "/api/uploads", "POST", cookie=cookie, body=body)
    assert status == 409
    assert "one upload at a time" in json.loads(result)["error"].lower()
    assert headers["Cache-Control"] == "no-store"


def test_lost_upload_start_recovery_and_cancel(gateway):
    cookie = pair(gateway)
    other = pair(gateway)
    body = json.dumps({"name": "synthetic.mp4", "size": 2})
    first = json.loads(request(gateway, "/api/uploads", "POST", cookie=cookie, body=body)[2])
    route = f"/api/uploads/{first['id']}"
    assert request(gateway, route + "/chunk?offset=0", "PUT", cookie=cookie, body=b"x")[0] == 200
    for name in ["synthetic.mp4", "different.mp4"]:
        status, _, raw = request(
            gateway,
            "/api/uploads",
            "POST",
            cookie=cookie,
            body=json.dumps({"name": name, "size": 2}),
        )
        assert status == 409
        assert json.loads(raw)["upload"] == {
            "id": first["id"],
            "name": "synthetic.mp4",
            "size": 2,
            "offset": 1,
        }
    assert request(gateway, route, "DELETE", cookie=other)[0] == 404
    assert request(gateway, route, "DELETE", cookie=cookie)[0] == 204
    assert not (gateway.adapter.uploads.folder / first["id"]).exists()
    assert request(gateway, route, "DELETE", cookie=cookie)[0] == 404
    assert request(gateway, "/api/uploads", "POST", cookie=cookie, body=body)[0] == 200


def test_cancel_ready_upload_protects_queued_source(gateway):
    from types import SimpleNamespace

    from videoenhancer.service.settings import write_json

    cookie = pair(gateway)
    first = json.loads(
        request(
            gateway,
            "/api/uploads",
            "POST",
            cookie=cookie,
            body=json.dumps({"name": "synthetic.mp4", "size": 1}),
        )[2]
    )
    directory = gateway.adapter.uploads.folder / first["id"]
    metadata = json.loads((directory / "upload.json").read_text())
    metadata["ready"] = True
    write_json(directory / "upload.json", metadata)
    jobs = [{"source": {"remote": {"folder": str(directory), "device": metadata["device"]}}}]
    gateway.adapter.engine = SimpleNamespace(store=SimpleNamespace(list_jobs=lambda: jobs))
    route = f"/api/uploads/{first['id']}"
    assert request(gateway, route, "DELETE", cookie=cookie)[0] == 409
    assert directory.exists()
    jobs.clear()
    assert request(gateway, route, "DELETE", cookie=cookie)[0] == 204


@pytest.mark.parametrize("branch", ["segment", "controller", "assembly", "storage", "input"])
def test_controller_failure_logs_are_private(tmp_path, monkeypatch, branch):
    from datetime import UTC, datetime

    from test_controller import FakeClock, _job

    from videoenhancer.jobs.store import JobStore
    from videoenhancer.schedule import controller

    secret = "Private Name C:\\secret\\private-clip.mp4 https://private.invalid/video"
    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=UTC))
    monkeypatch.setattr(controller, "log_job_header", lambda *a: None)
    monkeypatch.setattr(controller, "validate_done_segments", lambda *a: False)

    def broken(*args, **kwargs):
        raise RuntimeError(secret)

    class Executor:
        def run(self, *args, **kwargs):
            return controller.SegmentResult("failed", error=secret)

    if branch == "controller":
        monkeypatch.setattr(controller, "validate_done_segments", broken)
    elif branch == "assembly":
        job["segments"][0]["state"] = "done"
        store.save(job)
        monkeypatch.setattr("videoenhancer.media.mux.assemble", broken)
    elif branch == "storage":

        def full(*args, **kwargs):
            raise OSError(secret)

        monkeypatch.setattr(controller, "require_disk_space", full)
    elif branch == "input":

        def invalid(*args, **kwargs):
            raise ValueError(secret)

        monkeypatch.setattr(controller, "validate_input", invalid)
    controller.run_queue(
        home=store.home, clock=clock, executor=Executor(), ignore_schedule=True, disk_free=1_000_000
    )
    assert store.load(job["id"])["state"] == "failed"
    output = (store.home / "videoenhancer.jsonl").read_text()
    assert all(
        value not in output
        for value in ["Private Name", "secret", "private-clip", "private.invalid"]
    )
    assert "stage=" in output and "type=" in output
    if branch == "controller":
        assert "type=RuntimeError" in output and "test_remote_r1e.py:" in output


def test_preparation_failure_preserves_detail(tmp_path, monkeypatch):
    from videoenhancer.service.engine import Engine

    engine = Engine(tmp_path / "home")
    engine.remote_jobs = object()
    source = tmp_path / "invalid.mp4"
    source.write_bytes(b"not a video")
    monkeypatch.setattr(
        engine,
        "estimate",
        lambda *a: {
            "warnings": [],
            "presets": {"fast": {"seconds": 1, "finish": None}},
        },
    )
    monkeypatch.setattr(
        engine,
        "chosen",
        lambda *a: {
            "preset": "passthrough",
            "fps": "off",
            "backend": "cpu",
        },
    )
    try:
        job = engine.add(
            {"file": str(source), "settings": {"codec": "hevc", "preset": "fast"}},
            remote={"device": "synthetic", "folder": str(tmp_path / "incoming")},
        )
        for thread in engine._preparations:
            thread.join(15)
            assert not thread.is_alive()
        latest = engine.store.load(job["id"])
        assert latest["state"] == "failed"
        assert latest["failure"]["stage"] == "probe"
        assert latest["failure"]["reason"]
        assert latest["failure"]["type"]
    finally:
        engine.close()


def test_failure_activity_is_private(tmp_path, caplog):
    from videoenhancer.remote.diagnostics import failure
    from videoenhancer.remote.jobs import activity

    error = ValueError("Private Person at C:\\home\\private clip.mp4 https://secret.invalid/video")
    with caplog.at_level(logging.INFO, logger="videoenhancer.remote"):
        detail = failure("probe", error)
    job = {"settings": {"preset": "fast"}, "failure": detail}
    path = tmp_path / "activity.log"
    activity(path, job, "failed", 0, 0)
    row = json.loads(path.read_text())
    assert row["error_category"] == "probe"
    assert row["error_type"] == "ValueError"
    output = path.read_text() + caplog.text
    assert all(
        secret not in output
        for secret in ["Private Person", "C:\\home", "private clip", "secret.invalid"]
    )
    assert "[url]" in output and "[path]" in output


def test_progress_copies_outside_lock(monkeypatch):
    from videoenhancer.service.engine import Engine
    from videoenhancer.service.locks import OrderedLock

    engine = Engine.__new__(Engine)
    engine.lock = OrderedLock("engine state", 30, True)
    engine.live_progress = {}
    engine._progress_received = {}
    entered = threading.Event()
    release = threading.Event()
    import copy

    original = copy.deepcopy

    def slow(value):
        entered.set()
        assert release.wait(3)
        return original(value)

    monkeypatch.setattr("videoenhancer.service.engine.copy.deepcopy", slow)
    thread = threading.Thread(target=engine._progress, args=({"id": "j"}, {"frames_done": 1}))
    thread.start()
    assert entered.wait(3)
    began = time.monotonic()
    try:
        assert engine.lock._lock.acquire(timeout=0.5)
        engine.lock._lock.release()
        assert time.monotonic() - began < 1
    finally:
        release.set()
        thread.join(3)


def test_aborted_range_logs_bytes_and_releases_library(gateway, caplog):
    cookie = pair(gateway)
    library = gateway.adapter.library
    library.folder.mkdir(exist_ok=True)
    path = library.folder / "synthetic.mp4"
    path.write_bytes(b"x" * (16 * 1024 * 1024))
    identifier = library._identifier(path)
    context = ssl.create_default_context(cafile=str(gateway.home / "remote/ca.crt"))
    conn = http.client.HTTPSConnection("127.0.0.1", gateway.https_port, context=context, timeout=10)
    with caplog.at_level(logging.INFO, logger="videoenhancer.remote"):
        conn.request(
            "GET",
            f"/api/library/{identifier}/video",
            headers={"Cookie": cookie, "Range": "bytes=0-"},
        )
        response = conn.getresponse()
        assert response.read(1) == b"x"
        response.close()
        conn.close()
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            if "client disconnected" in caplog.text and not library._active:
                break
            time.sleep(0.02)
        assert not library._active
        assert "client disconnected route=/api/library/{id}/video bytes_sent=" in caplog.text
        assert "synthetic.mp4" not in caplog.text


def test_gateway_unhandled_exception_is_private(gateway, monkeypatch, caplog):
    cookie = pair(gateway)

    def broken():
        raise RuntimeError("Private Name C:\\secret\\clip.mp4 https://private.invalid")

    monkeypatch.setattr(gateway.adapter.library, "list", broken)
    with caplog.at_level(logging.INFO, logger="videoenhancer.remote"):
        assert request(gateway, "/api/library", cookie=cookie)[0] == 500
    assert "type=RuntimeError" in caplog.text and "test_remote_r1e.py:" in caplog.text
    assert all(
        secret not in caplog.text
        for secret in ["Private Name", "secret\\", "private.invalid", "raise RuntimeError"]
    )


def test_manual_poster_long_clip_fast_seek(tmp_path, ffmpeg_run, monkeypatch):
    from videoenhancer import proc
    from videoenhancer.remote.library import Library
    from videoenhancer.remote.thumbnails import Thumbnails

    # One hour at one small frame per second; seeking near its end must stay bounded.
    folder = tmp_path / "library"
    folder.mkdir()
    path = folder / "synthetic.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "color=size=32x32:rate=1:duration=3600",
        "-c:v",
        "libx264",
        "-threads",
        "1",
        "-g",
        "2",
        str(path),
    )
    library = Library(tmp_path, folder)
    images = Thumbnails(library)
    calls = []
    original = proc.run_cancellable

    def measured(command, cancelled, timeout):
        calls.append((command, timeout))
        return original(command, cancelled, timeout)

    monkeypatch.setattr(proc, "run_cancellable", measured)
    began = time.monotonic()
    images.set_poster(library._identifier(path), 3590)
    elapsed = time.monotonic() - began
    assert elapsed < 10
    assert calls[0][0].index("-ss") < calls[0][0].index("-i")
    assert 0 < calls[0][1] <= 30
    print(f"poster seek seconds={elapsed:.3f}")

    def timeout(*args, **kwargs):
        raise TimeoutError("private tool diagnostic")

    monkeypatch.setattr(proc, "run_cancellable", timeout)
    with pytest.raises(ValueError, match="within 30 seconds"):
        images.set_poster(library._identifier(path), 3590)


def test_link_failure_logged_without_source_details(tmp_path, caplog):
    from types import SimpleNamespace

    from videoenhancer.service.link_jobs import LinkJobs

    job = {"id": "synthetic", "state": "downloading", "download": {"retries": 3}}

    class Store:
        def load(self, _):
            return job.copy()

        def load_existing(self, _):
            return job.copy()

        def patch_existing(self, _, value):
            job.update(value)

    def broken(*args):
        raise OSError("Private Name https://private.invalid C:\\secret\\clip.mp4")

    engine = SimpleNamespace(
        store=Store(),
        stop=threading.Event(),
        paused=False,
        processes={},
        video_links=SimpleNamespace(download=broken),
    )
    links = LinkJobs(engine)
    with caplog.at_level(logging.INFO, logger="videoenhancer.remote"):
        links.download("synthetic")
    assert job["state"] == "failed"
    assert job["failure"]["stage"] == "download"
    assert "type=OSError" in caplog.text
    assert all(
        secret not in caplog.text for secret in ["Private Name", "private.invalid", "secret\\"]
    )


def test_notification_slow_writer_runs_outside_engine_lock(tmp_path, monkeypatch):
    from videoenhancer.service.engine import Engine
    from videoenhancer.service.settings import write_json

    engine = Engine(tmp_path / "engine-home")
    holds = []
    lock_type = type(engine.lock)
    original_exit = lock_type.__exit__

    def measured_exit(lock, *args):
        if lock is engine.lock:
            holds.append(time.monotonic() - lock.since)
        return original_exit(lock, *args)

    monkeypatch.setattr(lock_type, "__exit__", measured_exit)

    def health(_):
        assert engine.lock.owner is None
        time.sleep(1.05)
        write_json(engine.home / "slow-writer.json", {"synthetic": True})
        return {}

    monkeypatch.setattr(engine, "health", health)
    try:
        engine._progress({"id": "synthetic", "state": "running"}, {"frames_done": 1})
        engine.event_snapshot()
        assert holds and max(holds) < 1
        print(f"maximum engine lock seconds={max(holds):.6f}")
    finally:
        engine.close()


def test_pythonw_warnings_and_thread_errors_are_logged_privately(tmp_path):
    import subprocess
    import sys
    import textwrap

    # A fresh interpreter matches service startup and isolates process-wide hooks
    # from pytest's per-test warning capture and earlier service-start tests.
    script = textwrap.dedent(r"""
        import sys, threading, warnings
        from pathlib import Path
        from videoenhancer.logging import capture_runtime_errors

        sys.stdout = sys.stderr = None
        capture_runtime_errors(Path(sys.argv[1]))
        warnings.simplefilter('always')
        warnings.warn('Private Name https://private.invalid C:\\secret\\clip.mp4', RuntimeWarning)
        def broken():
            raise RuntimeError('Private Name https://private.invalid C:\\secret\\clip.mp4')
        thread = threading.Thread(target=broken)
        thread.start()
        thread.join(3)
        assert not thread.is_alive()
    """)
    subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        check=True,
        capture_output=True,
        timeout=15,
    )
    output = (tmp_path / "videoenhancer.jsonl").read_text()
    assert "Python warning:" in output and "uncaught thread exception type=RuntimeError" in output
    assert all(secret not in output for secret in ["Private Name", "private.invalid", "secret\\"])
