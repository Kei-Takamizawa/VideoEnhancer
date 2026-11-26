"""Linux service and forwarded-host identity; never touches the real systemd manager."""

import http.client
import socket
import ssl
import subprocess
from argparse import Namespace
from pathlib import Path, PurePosixPath

import pytest

from videoenhancer.remote import install
from videoenhancer.remote.certificates import advertised_identity
from videoenhancer.service.settings import read_settings, save_settings


class FakeSystemctl:
    """Records commands and answers like systemctl and loginctl would."""

    def __init__(self, active=("inactive",), linger="no", enable_linger=False):
        self.calls: list[list[str]] = []
        self.active = list(active)
        self.linger = linger
        self.can_enable_linger = enable_linger

    def __call__(self, arguments):
        self.calls.append(arguments)
        output, code = "", 0
        if arguments[:3] == ["systemctl", "--user", "is-active"]:
            output = self.active.pop(0) if len(self.active) > 1 else self.active[0]
            code = 0 if output == "active" else 3
        elif arguments[:3] == ["systemctl", "--user", "is-enabled"]:
            output = "enabled"
        elif arguments[:2] == ["loginctl", "show-user"]:
            output = self.linger
        elif arguments[:2] == ["loginctl", "enable-linger"]:
            if self.can_enable_linger:
                self.linger = "yes"
            else:
                code = 1
        return subprocess.CompletedProcess(arguments, code, output + "\n", "")

    def systemctl(self):
        return [call[2:] for call in self.calls if call[:2] == ["systemctl", "--user"]]


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "engine root"
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    return root


def test_unit_matches_windows_task_policy_and_quotes_paths(tmp_path):
    # Unit paths are POSIX paths; PurePosixPath keeps this check the same on Windows CI.
    root = PurePosixPath("/srv/ve 100%/engine")
    unit = install.unit_text(root / ".venv/bin/python", PurePosixPath('/data/home "$X"'), root)
    exec_line = next(line for line in unit.splitlines() if line.startswith("ExecStart="))
    assert exec_line == (
        'ExecStart="/srv/ve 100%%/engine/.venv/bin/python" "-m" '
        '"videoenhancer.remote.launcher" "--home" "/data/home \\"$$X\\""'
    )
    assert "WorkingDirectory=/srv/ve 100%%/engine\n" in unit
    for line in (
        "Restart=on-failure",
        "RestartSec=60",
        "StartLimitBurst=4",
        "UMask=0077",
        "NoNewPrivileges=yes",
        "WantedBy=default.target",
    ):
        assert line in unit.splitlines()
    # A user manager has no system network targets; depending on them only logs errors.
    assert "network-online.target" not in unit
    with pytest.raises(ValueError):
        install.unit_text(
            PurePosixPath("/a\n[Service]"), PurePosixPath("/home"), PurePosixPath("/root")
        )


def test_register_writes_user_unit_then_reloads_and_enables(tmp_path):
    fake = FakeSystemctl()
    unit = tmp_path / "units" / install.UNIT_NAME
    service = install.Systemd(run=fake, unit_path=unit)
    root = make_root(tmp_path)
    service.register(tmp_path / "home", root)
    expected = install.unit_text(root / ".venv/bin/python", tmp_path / "home", root)
    assert unit.read_text(encoding="utf-8") == expected
    assert fake.systemctl() == [["daemon-reload"], ["enable", install.UNIT_NAME]]
    assert not list(unit.parent.glob(".*.tmp"))
    with pytest.raises(FileNotFoundError):
        service.register(tmp_path / "home", tmp_path / "no-venv")


def test_failed_systemctl_reports_the_reason(tmp_path):
    def failing(arguments):
        return subprocess.CompletedProcess(arguments, 1, "", "Failed to connect to bus")

    service = install.Systemd(run=failing, unit_path=tmp_path / install.UNIT_NAME)
    with pytest.raises(RuntimeError, match="Failed to connect to bus"):
        service.register(tmp_path / "home", make_root(tmp_path))


def test_start_waits_for_a_stopping_unit_before_starting(tmp_path, monkeypatch):
    monkeypatch.setattr(install.time, "sleep", lambda _: None)
    fake = FakeSystemctl(active=["deactivating", "active", "inactive"])
    install.Systemd(run=fake, unit_path=tmp_path / install.UNIT_NAME).start()
    commands = fake.systemctl()
    assert commands[-1] == ["start", install.UNIT_NAME]
    assert sum(command[0] == "is-active" for command in commands) == 3


def test_start_refuses_when_the_unit_never_stops(tmp_path, monkeypatch):
    clock = iter(range(0, 1000, 5))
    monkeypatch.setattr(install.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(install.time, "sleep", lambda _: None)
    fake = FakeSystemctl(active=["active"])
    with pytest.raises(RuntimeError, match="did not stop"):
        install.Systemd(run=fake, unit_path=tmp_path / install.UNIT_NAME).start()
    assert ["start", install.UNIT_NAME] not in fake.systemctl()


def test_remove_only_touches_an_installed_unit(tmp_path):
    fake = FakeSystemctl()
    unit = tmp_path / install.UNIT_NAME
    service = install.Systemd(run=fake, unit_path=unit)
    service.remove()
    assert fake.calls == []
    unit.write_text("[Unit]\n", encoding="utf-8")
    service.remove()
    assert not unit.exists()
    assert fake.systemctl() == [["disable", install.UNIT_NAME], ["daemon-reload"]]


def test_linux_firewall_is_reported_as_not_managed(tmp_path):
    service = install.Systemd(run=FakeSystemctl(), unit_path=tmp_path / install.UNIT_NAME)
    settings = read_settings(tmp_path)
    status = service.firewall(settings)
    assert status["managed"] is False and status["setup"] == "not_managed"
    assert "8443" in status["message"] and "8080" in status["message"]
    assert "warning" not in status


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("homeserver", True),
        ("Pro-2", True),
        ("homeserver.local", False),
        ("-pro", False),
        ("pro-", False),
        ("a b", False),
        ("x" * 64, False),
        (3, False),
    ],
)
def test_remote_name_is_one_host_label(tmp_path, value, valid):
    if valid:
        assert save_settings(tmp_path, {"remote_name": value})["remote_name"] == value
    else:
        with pytest.raises(ValueError):
            save_settings(tmp_path, {"remote_name": value})


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        (["192.168.1.20"], True),
        (["10.0.0.2", "172.16.5.4"], True),
        ([], True),
        (["127.0.0.1"], False),
        (["169.254.1.1"], False),
        (["100.64.0.1"], False),
        (["8.8.8.8"], False),
        (["192.168.001.040"], False),
        (["192.168.1.20", "192.168.1.20"], False),
        ([f"10.0.0.{index}" for index in range(1, 10)], False),
        ("192.168.1.20", False),
        ([1], False),
    ],
)
def test_remote_addresses_are_lan_ipv4_only(tmp_path, value, valid):
    if valid:
        assert save_settings(tmp_path, {"remote_addresses": value})["remote_addresses"] == value
    else:
        with pytest.raises(ValueError):
            save_settings(tmp_path, {"remote_addresses": value})


def test_advertised_identity_prefers_saved_values(monkeypatch):
    monkeypatch.delenv("COMPUTERNAME", raising=False)
    monkeypatch.setattr("socket.gethostname", lambda: "videoenhancer.incus")
    assert advertised_identity({}, lambda: ["10.0.3.15"]) == ("videoenhancer", ["10.0.3.15"])
    assert advertised_identity(
        {"remote_name": "homeserver", "remote_addresses": ["192.168.1.20"]},
        lambda: pytest.fail("discovery is not needed"),
    ) == ("homeserver", ["192.168.1.20"])


def test_linux_install_saves_identity_and_reports_linger(tmp_path, monkeypatch):
    from cryptography import x509

    fake = FakeSystemctl(linger="no", enable_linger=False)
    unit = tmp_path / "units" / install.UNIT_NAME
    service = install.Systemd(run=fake, unit_path=unit)
    started = []
    root = make_root(tmp_path)
    monkeypatch.setattr(install, "engine_root", lambda: root)
    monkeypatch.setattr(install, "ensure_running", lambda home, service=None: started.append(home))
    monkeypatch.setattr(install, "request", lambda *a, **k: {"setup_address": "x"})
    monkeypatch.setenv("USER", "dev")
    home = tmp_path / "home"
    result = install.install(home, service, name="homeserver", addresses=["192.168.1.20"])
    assert started == [home]
    assert result["firewall"]["setup"] == "not_managed"
    assert result["starts_at_boot"] is False
    assert "sudo loginctl enable-linger dev" in result["message"]
    settings = read_settings(home)
    assert settings["remote_enabled"] is True
    assert settings["remote_name"] == "homeserver"
    assert settings["remote_addresses"] == ["192.168.1.20"]
    cert = x509.load_pem_x509_certificate((home / "remote/server.crt").read_bytes())
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert set(san.get_values_for_type(x509.DNSName)) == {"homeserver.local", "homeserver"}
    assert [str(value) for value in san.get_values_for_type(x509.IPAddress)] == ["192.168.1.20"]
    assert unit.exists()


def test_linux_install_with_linger_has_no_warning(tmp_path, monkeypatch):
    fake = FakeSystemctl(linger="no", enable_linger=True)
    service = install.Systemd(run=fake, unit_path=tmp_path / install.UNIT_NAME)
    root = make_root(tmp_path)
    monkeypatch.setattr(install, "engine_root", lambda: root)
    monkeypatch.setattr(install, "ensure_running", lambda home, service=None: None)
    monkeypatch.setattr(install, "request", lambda *a, **k: {})
    monkeypatch.setattr(install, "prepare_certificates", lambda home: None)
    result = install.install(tmp_path / "home", service)
    assert "message" not in result and "starts_at_boot" not in result
    assert ["loginctl", "enable-linger", "--no-ask-password"] in fake.calls


def test_invalid_identity_changes_nothing(tmp_path, monkeypatch):
    fake = FakeSystemctl()
    unit = tmp_path / install.UNIT_NAME
    service = install.Systemd(run=fake, unit_path=unit)
    root = make_root(tmp_path)
    monkeypatch.setattr(install, "engine_root", lambda: root)
    with pytest.raises(ValueError):
        install.install(tmp_path / "home", service, addresses=["8.8.8.8"])
    assert fake.calls == [] and not unit.exists()
    assert read_settings(tmp_path / "home")["remote_enabled"] is False


def test_linux_status_describes_the_user_service(tmp_path, monkeypatch):
    fake = FakeSystemctl(active=["active"], linger="yes")
    unit = tmp_path / install.UNIT_NAME
    unit.write_text("[Unit]\n", encoding="utf-8")
    monkeypatch.setattr(
        install, "service_platform", lambda: install.Systemd(run=fake, unit_path=unit)
    )
    monkeypatch.setattr(install, "running", lambda _: None)
    save_settings(tmp_path, {"remote_name": "homeserver", "remote_addresses": ["192.168.1.20"]})
    result = install.command(Namespace(remote_command="status"), tmp_path)
    assert result["pc_name"] == "homeserver"
    assert result["addresses"] == ["https://homeserver.local:8443/"]
    assert result["service"] == {
        "manager": "systemd user service",
        "unit": str(unit),
        "installed": True,
        "enabled": "enabled",
        "active": "active",
        "starts_at_boot": True,
    }
    assert result["firewall"]["managed"] is False


def test_forwarded_gateway_serves_the_host_name_not_its_own(tmp_path, monkeypatch):
    """An Incus proxy delivers iPad connections from loopback with the host's name."""
    from videoenhancer.remote.gateway import Gateway

    monkeypatch.setattr(
        "videoenhancer.remote.gateway.local_addresses",
        lambda: pytest.fail("a configured address list must be used as-is"),
    )
    gateway = Gateway(
        None,
        tmp_path,
        {
            "remote_https_port": 0,
            "remote_setup_port": 0,
            "library_folder": str(tmp_path / "library"),
            "remote_name": "homeserver",
            "remote_addresses": ["192.168.1.20"],
        },
    )
    gateway.start()
    try:
        context = ssl.create_default_context(cafile=str(tmp_path / "remote" / "ca.crt"))

        def status(host: str, server_name: str) -> int:
            raw = http.client.HTTPSConnection("127.0.0.1", gateway.https_port, timeout=10)
            raw.sock = context.wrap_socket(
                socket.create_connection(("127.0.0.1", gateway.https_port), timeout=10),
                server_hostname=server_name,
            )
            raw.request("GET", "/api/session", headers={"Host": host})
            code = raw.getresponse().status
            raw.close()
            return code

        port = gateway.https_port
        # The certificate verifies as homeserver.local, and the Host check accepts it.
        assert status(f"homeserver.local:{port}", "homeserver.local") == 200
        assert status(f"192.168.1.20:{port}", "homeserver.local") == 200
        # The container's own names are no longer valid hosts.
        assert status(f"127.0.0.1:{port}", "homeserver.local") == 421
        with pytest.raises(ssl.SSLCertVerificationError):
            status(f"videoenhancer.local:{port}", "videoenhancer.local")
    finally:
        gateway.close()
