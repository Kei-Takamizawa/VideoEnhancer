"""Remote commands never need a real Windows task or owner home in CI."""

from pathlib import Path

import pytest

from videoenhancer.cli import _parser
from videoenhancer.service.settings import read_settings, save_settings


@pytest.fixture(autouse=True)
def fake_firewall_powershell(monkeypatch):
    monkeypatch.setattr(
        "videoenhancer.remote.install._powershell",
        lambda _: '{"interfaces":[],"allow_rule":false,"block_rules":[]}',
    )


def test_remote_cli_options():
    assert _parser().parse_args(["serve", "--remote"]).remote
    assert _parser().parse_args(["remote", "uninstall", "--forget-devices"]).forget_devices


def test_remote_settings_validation(tmp_path):
    assert read_settings(tmp_path)["remote_enabled"] is False
    for value in (
        {"remote_enabled": 1},
        {"remote_https_port": 0},
        {"remote_setup_port": True},
        {"library_folder": "relative"},
        {"share_limit_bytes": -1},
        {"share_limit_bytes": True},
        {"share_limit_bytes": "100"},
    ):
        with pytest.raises(ValueError):
            save_settings(tmp_path, value)
    assert save_settings(tmp_path, {"library_folder": str(tmp_path / "library")})[
        "library_folder"
    ] == str(tmp_path / "library")
    assert save_settings(tmp_path, {"share_limit_bytes": 100})["share_limit_bytes"] == 100


def test_install_uninstall_fake_windows(tmp_path, monkeypatch):
    from videoenhancer.remote import install

    calls = []

    class Windows:
        def firewall(self, settings):
            calls.append(("firewall", settings))
            return {"setup": "missing", "allow_rule": False}

        def remove_firewall(self):
            calls.append(("remove_firewall",))

        def register(self, home, root):
            calls.append(("register", home, root))

        def shortcut(self, home, root):
            calls.append(("shortcut", home, root))

        def remove(self):
            calls.append(("remove",))

    monkeypatch.setattr(install, "prepare_certificates", lambda home: calls.append(("cert", home)))
    monkeypatch.setattr(install, "ensure_running", lambda home: calls.append(("start", home)))
    monkeypatch.setattr(install, "stop_service", lambda home: calls.append(("stop", home)))
    monkeypatch.setattr(
        install, "request", lambda *a, **k: {"setup_address": "http://pc.local:8080/"}
    )
    home = tmp_path / "home"
    home.mkdir()
    library = tmp_path / "library"
    library.mkdir()
    keep = library / "keep.mp4"
    keep.write_bytes(b"synthetic")
    save_settings(home, {"library_folder": str(library)})
    result = install.install(home, Windows())
    assert result["firewall"]["setup"] == "missing"
    install.install(home, Windows())
    assert read_settings(home)["remote_enabled"] is True
    remote = home / "remote"
    remote.mkdir(exist_ok=True)
    devices = remote / "devices.json"
    devices.write_text("{}")
    install.uninstall(home, False, Windows())
    assert devices.exists() and keep.exists()
    install.uninstall(home, True, Windows())
    assert not devices.exists() and keep.exists()
    assert read_settings(home)["remote_enabled"] is False
    assert sum(row[0] == "register" for row in calls) == 2
    assert sum(row[0] == "firewall" for row in calls) == 2
    assert sum(row[0] == "remove_firewall" for row in calls) == 2


def test_task_xml_is_user_only_windowless_restart_policy(tmp_path):
    from videoenhancer.remote.install import task_xml

    xml = task_xml(Path("C:/engine/.venv/Scripts/pythonw.exe"), tmp_path, Path("C:/engine"), "SID")
    assert "<UserId>SID</UserId>" in xml
    assert "<LogonType>InteractiveToken</LogonType>" in xml
    assert "<RunLevel>LeastPrivilege</RunLevel>" in xml
    assert "<Interval>PT1M</Interval><Count>3</Count>" in xml
    assert "pythonw.exe" in xml and "--home" in xml
    assert f"<WorkingDirectory>{Path('C:/engine')}</WorkingDirectory>" in xml


def test_stopped_status_is_complete_without_creating_certificates(tmp_path):
    from argparse import Namespace

    from videoenhancer.remote.install import command

    result = command(Namespace(remote_command="status"), tmp_path)
    assert result["service_running"] is False
    assert result["gateway_running"] is False
    assert result["pairing_open"] is False
    assert result["paired_devices"] == 0
    assert result["addresses"] and result["setup_address"]
    assert result["cert_expires"] is None
    assert not (tmp_path / "remote").exists()


def test_plain_service_status_keeps_remote_details(tmp_path, monkeypatch):
    from argparse import Namespace

    from videoenhancer.remote import install

    monkeypatch.setattr(install, "running", lambda _: {"remote": {"gateway_running": False}})
    result = install.command(Namespace(remote_command="status"), tmp_path)
    assert result["service_running"] is True and result["gateway_running"] is False
    assert result["addresses"] and result["setup_address"]
    assert result["cert_expires"] is None and result["paired_devices"] == 0


@pytest.mark.parametrize("flag,enabled", [(True, False), (False, True), (False, False)])
def test_serve_remote_lifecycle(tmp_path, monkeypatch, flag, enabled):
    import threading

    from videoenhancer.service import server

    calls = []

    class Engine:
        def __init__(self, home):
            self.stop = threading.Event()

        def start(self):
            calls.append("engine start")

        def close(self):
            calls.append("engine close")

    class Gateway:
        def __init__(self, engine, home, settings):
            calls.append("gateway init")

        def start(self):
            calls.append("gateway start")

        def close(self):
            calls.append("gateway close")

    class Server:
        server_port = 1
        token = "test"

        def __init__(self, engine, gateway):
            assert (gateway is not None) == (flag or enabled)

        def serve_forever(self, **kwargs):
            calls.append("serve")

        def server_close(self):
            calls.append("server close")

    save_settings(tmp_path, {"remote_enabled": enabled})
    monkeypatch.setattr(server, "Engine", Engine)
    monkeypatch.setattr(server, "LocalServer", Server)
    monkeypatch.setattr(server, "discovery", lambda *args: None)
    monkeypatch.setattr(server.signal, "signal", lambda *args: None)
    monkeypatch.setattr("videoenhancer.remote.gateway.Gateway", Gateway)
    assert server.serve(tmp_path, remote=flag) == 0
    assert ("gateway start" in calls) == (flag or enabled)
    assert ("gateway close" in calls) == (flag or enabled)
    assert "engine close" in calls and "server close" in calls
