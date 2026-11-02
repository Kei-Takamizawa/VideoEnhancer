"""Narrow Windows firewall management; all PowerShell calls are fakeable."""

from __future__ import annotations

import base64
import json
from pathlib import Path

NAME = "VideoEnhancer (iPad)"
PUBLIC_WARNING = (
    "Your network is set to Public. Set it to Private in Settings > Network & internet, "
    "or the iPad may not connect."
)


def program(root: Path) -> Path:
    # Windows venv launchers run the base interpreter; firewall rules must match that image.
    config = root / ".venv/pyvenv.cfg"
    if config.is_file():
        for line in config.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "home":
                candidate = Path(value.strip()) / "pythonw.exe"
                if candidate.is_file():
                    return candidate.resolve()
    return (root / ".venv/Scripts/pythonw.exe").resolve()


def status(python: Path, https_port: int, setup_port: int) -> dict:
    from videoenhancer.remote.install import _literal, _powershell

    try:
        result = json.loads(
            _powershell(
                "$ErrorActionPreference='Stop'; "
                f"$program={_literal(python)}; "
                "$rules=@(Get-NetFirewallApplicationFilter | Where-Object "
                "{ $_.Program -ieq $program } | Get-NetFirewallRule); "
                "$interfaces=@(Get-NetConnectionProfile | Where-Object "
                "{ $_.IPv4Connectivity -ne 'Disconnected' "
                "-or $_.IPv6Connectivity -ne 'Disconnected' } "
                "| ForEach-Object { @{name=$_.InterfaceAlias;"
                "profile=[string]$_.NetworkCategory} }); "
                f"$allow=@($rules | Where-Object {{ $_.DisplayName -eq {_literal(NAME)} "
                "-and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' "
                "-and $_.Enabled -eq 'True' -and [string]$_.Profile -eq 'Private' } "
                "| Where-Object { $p=$_ | Get-NetFirewallPortFilter; "
                f"$p.Protocol -eq 'TCP' -and @($p.LocalPort) -contains '{https_port}' "
                f"-and @($p.LocalPort) -contains '{setup_port}' }}); "
                "$blocks=@($rules | Where-Object { $_.Action -eq 'Block' } | ForEach-Object "
                "{ @{name=$_.Name;display_name=$_.DisplayName} }); "
                "@{interfaces=$interfaces;allow_rule=($allow.Count -gt 0);block_rules=$blocks} "
                "| ConvertTo-Json -Depth 5 -Compress"
            )
        )
    except (RuntimeError, ValueError, OSError):
        return {
            "interfaces": [],
            "allow_rule": False,
            "block_rules": [],
            "error": "Windows firewall status could not be read.",
        }
    if any(row.get("profile") == "Public" for row in result.get("interfaces", [])):
        result["warning"] = PUBLIC_WARNING
    return result


def _elevated(script: str) -> None:
    from videoenhancer.remote.install import _powershell

    encoded = base64.b64encode(
        ("$ErrorActionPreference='Stop'; " + script).encode("utf-16-le")
    ).decode()
    _powershell(
        "$ErrorActionPreference='Stop'; $p=Start-Process powershell.exe -Verb RunAs "
        "-WindowStyle Hidden -Wait -PassThru -ArgumentList "
        f"'-NoProfile','-NonInteractive','-EncodedCommand', '{encoded}'; "
        "if ($p.ExitCode -ne 0) { throw 'Firewall update failed.' }"
    )


def configure(python: Path, https_port: int, setup_port: int) -> dict:
    from videoenhancer.remote.install import _literal

    before = status(python, https_port, setup_port)
    try:
        _elevated(
            f"$program={_literal(python)}; "
            "$rules=@(Get-NetFirewallApplicationFilter | Where-Object "
            "{ $_.Program -ieq $program } | Get-NetFirewallRule); "
            "$rules | Where-Object { $_.Action -eq 'Block' "
            "-and @('Python','pythonw.exe') -contains $_.DisplayName } | Remove-NetFirewallRule; "
            f"$rules | Where-Object {{ $_.DisplayName -eq {_literal(NAME)} }} "
            "| Remove-NetFirewallRule; "
            f"New-NetFirewallRule -DisplayName {_literal(NAME)} -Direction Inbound "
            "-Action Allow -Enabled True -Profile Private -Protocol TCP "
            f"-Program $program -LocalPort {https_port},{setup_port} | Out-Null"
        )
    except (RuntimeError, OSError):
        return {
            **before,
            "setup": "missing",
            "removed_block_rules": [],
            "message": "Firewall setup was declined or failed. Run remote install to retry.",
        }
    after = status(python, https_port, setup_port)
    remaining = {rule["name"] for rule in after["block_rules"]}
    after["removed_block_rules"] = (
        [rule for rule in before["block_rules"] if rule["name"] not in remaining]
        if "error" not in after
        else []
    )
    after["setup"] = "ready" if after["allow_rule"] else "missing"
    return after


def remove() -> None:
    _elevated(
        "Get-NetFirewallRule -DisplayName 'VideoEnhancer (iPad)' -ErrorAction SilentlyContinue "
        "| Remove-NetFirewallRule"
    )
