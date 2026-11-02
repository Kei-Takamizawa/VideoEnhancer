from argparse import Namespace
from types import SimpleNamespace

import pytest

from videoenhancer.cli import _parser
from videoenhancer.remote import install


@pytest.fixture(autouse=True)
def fake_windows_platform(monkeypatch):
    monkeypatch.setattr(install, "os", SimpleNamespace(name="nt", environ=install.os.environ))


def test_start_uses_task_and_never_child_process(tmp_path, monkeypatch):
    calls = []
    health = iter([None, {"remote": {"gateway_running": True}}])
    monkeypatch.setattr(install, "running", lambda _: next(health))
    monkeypatch.setattr(install, "_powershell", calls.append)
    monkeypatch.setattr(install.proc, "Popen", lambda *a, **k: pytest.fail("child launched"))
    install.ensure_running(tmp_path)
    assert len(calls) == 1
    assert "Start-ScheduledTask -TaskName 'VideoEnhancer'" in calls[0]


@pytest.mark.parametrize("name", ["restart", "stop"])
def test_control_commands_are_graceful(tmp_path, monkeypatch, name):
    calls = []
    assert _parser().parse_args(["remote", name]).remote_command == name
    monkeypatch.setattr(install, "stop_service", lambda home: calls.append("stop"))
    monkeypatch.setattr(install, "ensure_running", lambda home: calls.append("start"))
    result = install.command(Namespace(remote_command=name), tmp_path)
    assert calls == (["stop", "start"] if name == "restart" else ["stop"])
    assert result["service_running"] == (name == "restart")


def test_stop_requests_management_bypass(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(install, "running", lambda _: {"remote": {"gateway_running": True}})
    monkeypatch.setattr(install, "request", lambda *args: calls.append(args))
    install.stop_service(tmp_path)
    assert calls == [(tmp_path, "shutdown", "POST", {"remote_uninstall": True})]


def test_pair_message_has_deadline(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        install, "request", lambda *a: {"setup_address": "http://pc/", "closes_at": 200}
    )
    monkeypatch.setattr(install, "message_box", lambda *a, **kw: calls.append((a, kw)))
    install.command(Namespace(remote_command="pair", message_box=True), tmp_path)
    assert calls[0][1] == {"closes_at": 200, "home": tmp_path}


def test_expired_message_does_not_open(monkeypatch):
    monkeypatch.setattr(install.time, "time", lambda: 200)
    monkeypatch.setattr(install.proc, "run", lambda *a, **kw: pytest.fail("popup opened"))
    install.message_box("Expired", closes_at=199)


def test_popup_is_timed_and_waited(monkeypatch):
    calls = []
    monkeypatch.setattr(install.time, "time", lambda: 100)
    monkeypatch.setattr(install.proc, "run", lambda *a, **kw: calls.append((a, kw)))
    install.message_box("Pairing", closes_at=120)
    assert ".Popup('Pairing', 20," in calls[0][0][0][-1]
    assert calls[0][1]["timeout"] == 25


@pytest.mark.parametrize("deadline", ["1970-01-01T00:02:00+00:00", 120.0])
def test_popup_accepts_gateway_timestamp(monkeypatch, deadline):
    calls = []
    monkeypatch.setattr(install.time, "time", lambda: 100)
    monkeypatch.setattr(install.proc, "run", lambda *a, **kw: calls.append(kw))
    install.message_box("Pairing", closes_at=deadline)
    assert calls[0]["timeout"] == 25


def test_pair_popup_reaps_helper_when_claim_closes_window(tmp_path, monkeypatch):
    import json

    state = tmp_path / "remote/pairing.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"closes_at": 0}), encoding="utf-8")
    calls = []

    class Child:
        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, **kwargs):
            calls.append("wait")

    monkeypatch.setattr(install.time, "time", lambda: 100)
    monkeypatch.setattr(install.proc, "Popen", lambda *a, **kw: Child())
    install.message_box("Pairing", closes_at=120, home=tmp_path)
    assert calls == ["terminate", "wait"]


def test_shutdown_bypass_keeps_desktop_refusal(tmp_path):
    import json
    import threading
    import urllib.error
    import urllib.request

    from videoenhancer.service.server import LocalServer

    class Engine:
        home = tmp_path
        stop = threading.Event()

        def start_publication(self):
            pass

        def close(self):
            self.stop.set()

    engine = Engine()
    server = LocalServer(engine, remote_gateway=object())
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        for body, authenticated, expected in [
            ({}, True, 409),
            ({"remote_uninstall": True}, False, 401),
            ({"remote_uninstall": True}, True, 200),
        ]:
            req = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/v1/shutdown",
                data=json.dumps(body).encode(),
                headers={
                    "Authorization": "Bearer " + (server.token if authenticated else "wrong"),
                    "Content-Type": "application/json",
                },
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with opener.open(req, timeout=5) as response:
                    assert response.status == expected
            except urllib.error.HTTPError as error:
                assert error.code == expected
            assert engine.stop.is_set() == (expected == 200)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert not thread.is_alive()
