"""Firewall command construction only: never query or mutate the PC firewall."""

import base64
import json
from pathlib import Path

from videoenhancer.remote import install


def test_firewall_install_limits_program_ports_profile_and_one_elevation(tmp_path, monkeypatch):
    from videoenhancer.remote import firewall

    calls = []
    before = {
        "interfaces": [{"name": "Wi-Fi", "profile": "Public"}],
        "allow_rule": False,
        "block_rules": [{"name": "blocked-id", "display_name": "Python"}],
    }
    after = {**before, "allow_rule": True, "block_rules": []}

    def powershell(script):
        calls.append(script)
        return (
            json.dumps(before if len(calls) == 1 else after) if "-Verb RunAs" not in script else ""
        )

    monkeypatch.setattr(install, "_powershell", powershell)
    result = firewall.configure(Path("C:/python/pythonw.exe"), 8443, 8080)
    elevated = [s for s in calls if "-Verb RunAs" in s]
    assert len(elevated) == 1
    encoded = elevated[0].split("-EncodedCommand', '")[1].split("'")[0]
    script = base64.b64decode(encoded).decode("utf-16-le")
    assert "-Profile Private" in script and "-Protocol TCP" in script
    assert "-LocalPort 8443,8080" in script
    assert "C:/python/pythonw.exe" in script.replace("\\", "/")
    assert "@('Python','pythonw.exe')" in script and "-eq 'Block'" in script
    assert result["removed_block_rules"] == before["block_rules"]
    assert result["allow_rule"] is True
    assert "Public" in result["warning"]


def test_declined_uac_returns_missing_firewall_without_failing_install(monkeypatch):
    from videoenhancer.remote import firewall

    def powershell(script):
        if "-Verb RunAs" in script:
            raise RuntimeError("UAC declined")
        return '{"interfaces":[],"allow_rule":false,"block_rules":[]}'

    monkeypatch.setattr(install, "_powershell", powershell)
    result = firewall.configure(Path("C:/python/pythonw.exe"), 8443, 8080)
    assert not result["allow_rule"] and result["setup"] == "missing"


def test_uninstall_only_removes_named_videoenhancer_rule(monkeypatch):
    from videoenhancer.remote import firewall

    calls = []
    monkeypatch.setattr(install, "_powershell", lambda script: calls.append(script) or "")
    firewall.remove()
    script = base64.b64decode(calls[0].split("-EncodedCommand', '")[1].split("'")[0]).decode(
        "utf-16-le"
    )
    assert "-DisplayName 'VideoEnhancer (iPad)'" in script
    assert "Remove-NetFirewallRule" in script and "Block" not in script


def test_status_command_uses_fake_firewall_and_prints_public_warning(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from videoenhancer.remote import firewall

    monkeypatch.setattr(install, "running", lambda _: None)
    monkeypatch.setattr(
        install,
        "_powershell",
        lambda _: json.dumps(
            {
                "interfaces": [{"name": "Wi-Fi", "profile": "Public"}],
                "allow_rule": False,
                "block_rules": [{"name": "other", "display_name": "Python"}],
            }
        ),
    )
    result = install.command(Namespace(remote_command="status"), tmp_path)
    assert result["firewall"]["block_rules"][0]["name"] == "other"
    assert firewall.PUBLIC_WARNING in capsys.readouterr().err


def test_firewall_program_matches_venv_runtime(tmp_path):
    from videoenhancer.remote import firewall

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "pythonw.exe").touch()
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text(f"home = {runtime}\n")
    assert firewall.program(tmp_path) == runtime / "pythonw.exe"
