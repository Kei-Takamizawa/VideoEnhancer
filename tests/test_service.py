"""Real loopback HTTP, CPU jobs and local service boundary checks."""

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

import pytest

from videoenhancer.service.engine import Engine
from videoenhancer.service.server import APP_ORIGIN, LocalServer, discovery, service_lock


def wait_prepared(engine):
    deadline = time.monotonic() + 15
    while any(j["state"] == "preparing" for j in engine.store.list_jobs()):
        assert time.monotonic() < deadline, "Preparation did not finish"
        time.sleep(0.02)


@pytest.fixture
def api(tmp_path):
    engine = Engine(tmp_path / "home")
    server = LocalServer(engine)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(path, method="GET", data=None, token=True, origin=APP_ORIGIN, host=None):
        headers = {"Origin": origin}
        if token:
            headers["Authorization"] = "Bearer " + (server.token if token is True else token)
        if host:
            headers["Host"] = host
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/v1/{path}",
            data=json.dumps(data).encode() if data is not None else None,
            headers={**headers, "Content-Type": "application/json"},
            method=method,
        )
        return urllib.request.urlopen(req, timeout=20)

    yield engine, server, request
    engine.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_token_origin_host_and_user_private_discovery(api):
    engine, server, request = api
    assert server.server_address[0] == "127.0.0.1"
    for kwargs, status in (
        (dict(token=False), 401),
        (dict(token="wrong"), 401),
        (dict(token="\u00e9"), 401),
        (dict(origin="https://evil.invalid"), 403),
        (dict(host="evil.invalid"), 403),
        (dict(origin="null"), 403),
    ):
        with pytest.raises(urllib.error.HTTPError) as error:
            request("health", **kwargs)
        assert error.value.code == status
    with request("health") as response:
        assert json.load(response)["version"]
    discovery(engine.home, server.server_port, server.token)
    data = json.loads((engine.home / "serve.json").read_text())
    assert data["port"] == server.server_port and data["token"] == server.token
    import os
    import subprocess

    if os.name == "nt":
        acl = subprocess.run(
            ["icacls", str(engine.home / "serve.json")], capture_output=True, text=True, check=True
        ).stdout
        assert "(I)" not in acl
    else:
        assert (engine.home / "serve.json").stat().st_mode & 0o777 == 0o600


def test_single_instance_reports_existing_port(tmp_path):
    (tmp_path / "serve.json").write_text('{"port":12345}')
    with service_lock(tmp_path):
        with pytest.raises(RuntimeError, match="12345"):
            with service_lock(tmp_path):
                pytest.fail("Second service acquired the lock")


def test_cpu_queue_sse_controls_and_completed_output(api, video_factory):
    engine, _, request = api
    source = video_factory(frames=24)
    settings = dict(preset="passthrough", backend="cpu", codec="h264", short_side="keep", fps="off")
    with request("queue", "POST", {"file": str(source), "settings": settings}) as response:
        first = json.load(response)
    with request(
        "queue",
        "POST",
        {"file": str(source), "settings": settings, "output": str(source.parent / "second.mp4")},
    ) as response:
        second = json.load(response)
    assert first["state"] == second["state"] == "preparing"
    wait_prepared(engine)
    request(f"queue/{second['id']}/move", "POST", {"position": 1}).close()
    assert engine.store.list_jobs()[0]["id"] == second["id"]
    request(f"queue/{first['id']}/pause", "POST", {}).close()
    assert engine.store.load(first["id"])["state"] == "paused"
    request(f"queue/{first['id']}/resume", "POST", {}).close()
    with request("events") as events:
        assert events.readline() == b"event: update\n"
        payload = json.loads(events.readline().decode().removeprefix("data: "))
        assert len(payload["queue"]["jobs"]) == 2
        engine.worker.start()
        deadline = time.monotonic() + 30
        finished = False
        while time.monotonic() < deadline:
            line = events.readline()
            if line.startswith(b"data: "):
                rows = json.loads(line[6:])["queue"]["jobs"]
                if all(j["state"] == "done" for j in rows):
                    finished = True
                    assert all(j["progress_percent"] == 100 for j in rows)
                    break
        assert finished
    request(f"queue/{first['id']}", "DELETE").close()
    assert len(engine.store.list_jobs()) == 1


def test_schedule_preview_and_persisted_settings(api, video_factory):
    engine, _, request = api
    source = video_factory(frames=12)
    request(
        "queue",
        "POST",
        {
            "file": str(source),
            "settings": dict(
                preset="passthrough", backend="cpu", codec="h264", short_side="keep", fps="off"
            ),
        },
    ).close()
    schedule = dict(
        enabled=True,
        timezone="UTC",
        weekly=[
            dict(days=["mon", "tue", "wed", "thu", "fri", "sat", "sun"], start="22:00", end="08:00")
        ],
    )
    wait_prepared(engine)
    with request("schedule/preview", "POST", schedule) as response:
        preview = json.load(response)
        assert preview["next_window"] and preview["plan"]["jobs"][0]["completion"]
    request("schedule", "PUT", schedule).close()
    saved = json.loads((engine.home / "schedule.json").read_text())
    assert saved["weekly"] == schedule["weekly"]
    request("schedule/override", "POST", {"until": "job-complete"}).close()
    assert (
        json.loads((engine.home / "schedule.json").read_text())["override_until"] == "job-complete"
    )
    request("settings", "PUT", {"preset": "fast", "theme": "light"}).close()
    assert engine.chosen({"backend": "cpu"})["preset"] == "fast"
    with request("settings") as response:
        assert json.load(response)["theme"] == "light"
    with request(
        "estimate", "POST", {"file": str(source), "settings": {"backend": "cpu"}}
    ) as response:
        estimate = json.load(response)
        assert set(estimate["presets"]) == {"standard", "fast"}
        assert estimate["disk"]["required_bytes"] > 0


def test_saved_schedule_used_by_controller_with_fake_clock(api, monkeypatch, video_factory):
    from test_controller import FakeClock

    from videoenhancer.schedule import controller

    engine, _, request = api
    source = video_factory(frames=12)
    request(
        "queue",
        "POST",
        {
            "file": str(source),
            "settings": dict(
                preset="passthrough", backend="cpu", codec="h264", short_side="keep", fps="off"
            ),
        },
    ).close()
    request(
        "schedule",
        "PUT",
        dict(enabled=True, timezone="UTC", weekly=[dict(days=["mon"], start="09:00", end="10:00")]),
    ).close()
    clock = FakeClock(datetime(2026, 10, 5, 8, 59, 59, tzinfo=UTC))
    stopped = threading.Event()
    observed = []

    class Executor:
        def run(self, *_args, **_kwargs):
            observed.append(clock.now())
            stopped.set()
            return controller.SegmentResult("aborted")

    wait_prepared(engine)
    controller.run_queue(home=engine.home, clock=clock, executor=Executor(), stopped=stopped.is_set)
    assert observed and observed[0].hour == 9


def test_model_download_requires_consent(api):
    engine, _, request = api
    with request("models") as response:
        model = json.load(response)[0]
    with pytest.raises(urllib.error.HTTPError) as error:
        request(f"models/{model['id']}/download", "POST", {})
    assert error.value.code == 400
    with request(
        f"models/{model['id']}/download", "POST", {"agree": True, "licence": model["licence"]}
    ) as response:
        assert json.load(response)["state"] == "waiting"
    consent = json.loads((engine.home / "consent" / f"{model['id']}.json").read_text())
    assert consent["licence"] == model["licence"] and consent["url"]
