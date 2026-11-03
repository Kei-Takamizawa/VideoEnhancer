"""Explicit isolated R1b GPU acceptance; synthetic loopback media only."""

import functools
import hashlib
import http.server
import io
import json
import os
import shutil
import threading
import time
from pathlib import Path

import pytest

from videoenhancer.estimate import estimate_job
from videoenhancer.estimate.live import live_job
from videoenhancer.remote.gateway import Gateway
from videoenhancer.service.engine import Engine
from videoenhancer.service.link_tools import ToolManager
from videoenhancer.service.settings import save_settings
from videoenhancer.service.video_links import VideoLinks


@pytest.mark.gpu
def test_remote_gpu_link_and_upload(tmp_path, ffmpeg_run, monkeypatch):
    import torch

    assert torch.cuda.is_available(), "This explicit acceptance run requires CUDA."
    evidence = Path(os.environ["VE_R1B_GPU_EVIDENCE"]).resolve()
    work = Path(__file__).resolve().parents[2]
    assert evidence.is_relative_to(work / "evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    home, library = tmp_path / "home", tmp_path / "library"
    monkeypatch.setenv("VE_HOME", str(home))
    models = Path(os.environ["VE_GPU_TEST_MODEL_HOME"])
    for name in ("models/basicvsrpp-ntire21-decompress", "adapter-sources"):
        shutil.copytree(models / name, home / name, copy_function=os.link)
    save_settings(
        home,
        {
            "preset": "standard",
            "codec": "h264",
            "short_side": "keep",
            "fps": "off",
            "library_folder": str(library),
        },
    )
    media = tmp_path / "media"
    media.mkdir()
    for name, size in (("link.mp4", "1920x1080"), ("upload.mp4", "1920x1080")):
        ffmpeg_run(
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate=30",
            "-frames:v",
            "60",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(media / name),
        )

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(media))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    engine = Engine(home)
    tools = ToolManager(Path(os.environ["VE_LINK_TEST_TOOLS_HOME"]))
    engine.link_tools = tools
    engine.video_links = VideoLinks(home, tools)
    gateway = Gateway(engine, home, {"library_folder": str(library)})
    failures = {}
    finish_job = gateway.jobs._finish

    def observe_finish(identifier):
        saved = gateway.jobs.records[identifier]["job"]
        if saved.get("error"):
            failures[identifier] = saved["error"]
        return finish_job(identifier)

    monkeypatch.setattr(gateway.jobs, "_finish", observe_finish)
    measurements = []
    result_path = evidence / "gpu-acceptance.json"
    try:
        engine.start()
        for mode in ("link", "upload"):
            if mode == "link":
                checked = gateway.adapter.check_link(
                    "test-device", {"url": f"http://127.0.0.1:{server.server_port}/link.mp4"}
                )
                deadline = time.monotonic() + 90
                while True:
                    checked = gateway.adapter.check_result("test-device", checked["id"])
                    if checked["state"] in {"done", "failed"}:
                        break
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
                assert checked["state"] == "done", checked
                value = {"check_id": checked["id"], "entry_keys": [checked["entries"][0]["key"]]}
            else:
                data = (media / "upload.mp4").read_bytes()
                upload = gateway.adapter.uploads.create(
                    "test-device", "Uploaded clip.mp4", len(data)
                )
                gateway.adapter.uploads.chunk(
                    "test-device", upload["id"], 0, io.BytesIO(data), len(data)
                )
                gateway.adapter.uploads.finish(
                    "test-device", upload["id"], hashlib.sha256(data).hexdigest()
                )
                value = {"upload_id": upload["id"]}
            estimate = gateway.adapter.estimate("test-device", value)["entries"][0]["estimate"]
            started = time.monotonic()
            job_id = gateway.adapter.add("test-device", value)["added"][0]["id"]
            job = engine.store.load(job_id)
            deleted = [str(Path(job["input"]["path"]).relative_to(home)), f"jobs/{job_id}"]
            deadline = time.monotonic() + 600
            queued_prediction = None
            predicted_at = started
            while engine.store.load_existing(job_id) or gateway.jobs.records:
                assert time.monotonic() < deadline, engine.store.load_existing(job_id)
                current = engine.store.load_existing(job_id)
                if (
                    mode == "link"
                    and queued_prediction is None
                    and current
                    and current.get("segments")
                ):
                    queued_prediction = estimate_job(
                        live_job(current, engine.live_progress.get(job_id, {}))
                    ).to_dict()
                    predicted_at = time.monotonic()
                time.sleep(0.2)
            actual = time.monotonic() - started
            gate_estimate = queued_prediction or estimate
            gate_actual = time.monotonic() - predicted_at
            row = {
                "mode": mode,
                "estimate": estimate,
                "actual_seconds": actual,
                "processing_prediction": queued_prediction,
                "seconds_after_prediction": gate_actual,
                "deleted": deleted,
                "error": failures.get(job_id),
                "outcome": json.loads((home / "remote/activity.log").read_text().splitlines()[-1]),
            }
            low, high = gate_estimate.get("low"), gate_estimate.get("high")
            row["within_range"] = low is not None and low <= gate_actual <= high
            measurements.append(row)
            result_path.write_text(json.dumps(measurements, indent=2), encoding="utf-8")
            assert not Path(job["input"]["path"]).exists()
            assert not engine.store.job_dir(job_id).exists()
        assert all(row["outcome"]["outcome"] == "done" for row in measurements), measurements
        assert len(list(library.glob("*.mp4"))) == 2
        assert not list((home / "remote/incoming").iterdir())
        lines = (home / "remote/activity.log").read_text()
        assert len(lines.splitlines()) == 2
        assert "Uploaded clip" not in lines and "link.mp4" not in lines and "http" not in lines
        assert all(row["within_range"] for row in measurements), measurements
    finally:
        engine.close()
        gateway.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
