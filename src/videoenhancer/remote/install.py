"""Per-user Windows startup and authenticated local management commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from videoenhancer import proc
from videoenhancer.service.settings import read_settings, save_settings

TASK_NAME = "VideoEnhancer"
SHORTCUT_NAME = "VideoEnhancer - Redo pairing.lnk"


def engine_root() -> Path:
    return Path(__file__).resolve().parents[3]


def task_xml(python: Path, home: Path, root: Path, sid: str) -> str:
    arguments = subprocess.list2cmdline(
        ["-m", "videoenhancer.remote.launcher", "--home", str(home)]
    )
    return (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
        "<Triggers><LogonTrigger><Enabled>true</Enabled>"
        f"<UserId>{escape(sid)}</UserId></LogonTrigger></Triggers>"
        '<Principals><Principal id="Owner">'
        f"<UserId>{escape(sid)}</UserId><LogonType>InteractiveToken</LogonType>"
        "<RunLevel>LeastPrivilege</RunLevel></Principal></Principals>"
        "<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>"
        "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>"
        "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"
        "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>"
        "<RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure>"
        '</Settings><Actions Context="Owner"><Exec>'
        f"<Command>{escape(str(python))}</Command><Arguments>{escape(arguments)}</Arguments>"
        f"<WorkingDirectory>{escape(str(root))}</WorkingDirectory>"
        "</Exec></Actions></Task>"
    )


def _powershell(script: str) -> str:
    try:
        result = proc.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
                + script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=30,
        )
    except subprocess.SubprocessError as error:
        raise RuntimeError("Windows could not update the per-user task or shortcut.") from error
    return result.stdout.strip()


def _literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


class Windows:
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Remote startup installation requires Windows.")

    def register(self, home: Path, root: Path) -> None:
        python = root / ".venv/Scripts/pythonw.exe"
        if not python.is_file():
            raise FileNotFoundError("This checkout needs .venv/Scripts/pythonw.exe.")
        sid = _powershell("[Security.Principal.WindowsIdentity]::GetCurrent().User.Value")
        xml = task_xml(python, home, root, sid)
        _powershell(
            "$ErrorActionPreference='Stop'; Register-ScheduledTask -TaskName 'VideoEnhancer' "
            f"-Xml {_literal(xml)} -Force | Out-Null"
        )

    def shortcut(self, home: Path, root: Path) -> None:
        arguments = subprocess.list2cmdline(
            ["-m", "videoenhancer.remote.launcher", "--home", str(home), "--pair-message"]
        )
        _powershell(
            "$ErrorActionPreference='Stop'; "
            "$p=Join-Path ([Environment]::GetFolderPath('Programs')) "
            f"{_literal(SHORTCUT_NAME)}; "
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($p); "
            f"$s.TargetPath={_literal(root / '.venv/Scripts/pythonw.exe')}; "
            f"$s.Arguments={_literal(arguments)}; $s.WorkingDirectory={_literal(root)}; "
            "$s.Save()"
        )

    def remove(self) -> None:
        _powershell(
            "$ErrorActionPreference='Stop'; "
            "$task=Get-ScheduledTask -TaskName 'VideoEnhancer' -ErrorAction SilentlyContinue; "
            "if ($task) { Unregister-ScheduledTask -TaskName 'VideoEnhancer' -Confirm:$false }; "
            "$p=Join-Path ([Environment]::GetFolderPath('Programs')) "
            f"{_literal(SHORTCUT_NAME)}; if (Test-Path -LiteralPath $p) "
            "{ Remove-Item -LiteralPath $p }"
        )

    def firewall(self, settings: dict) -> dict:
        from videoenhancer.remote import firewall

        return firewall.configure(
            firewall.program(engine_root()),
            settings["remote_https_port"],
            settings["remote_setup_port"],
        )

    def remove_firewall(self) -> None:
        from videoenhancer.remote import firewall

        firewall.remove()


def request(home: Path, route: str, method: str = "GET", body=None) -> dict:
    discovery = json.loads((home / "serve.json").read_text(encoding="utf-8"))
    port = discovery["port"]
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid service discovery port.")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/{route}",
        data=json.dumps(body or {}).encode() if method != "GET" else None,
        headers={
            "Authorization": "Bearer " + discovery["token"],
            "Content-Type": "application/json",
        },
        method=method,
    )
    # Local service management must not send credentials through a configured proxy.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
        req, timeout=20
    ) as response:
        return json.load(response)


def running(home: Path) -> dict | None:
    try:
        health = request(home, "health")
        if Path(health.get("home", "")).resolve() != home.resolve():
            raise RuntimeError("The discovered service uses a different engine home.")
        return health
    except (OSError, ValueError, KeyError):
        return None


def stop_service(home: Path) -> None:
    if running(home) is None:
        return
    request(home, "shutdown", "POST", {"remote_uninstall": True})
    deadline = time.monotonic() + 30
    while (home / "serve.json").exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("The service did not stop. Close it before retrying.")
        time.sleep(0.1)


def ensure_running(home: Path) -> None:
    health = running(home)
    if health and health.get("remote", {}).get("gateway_running"):
        return
    if health:
        stop_service(home)
    root = engine_root()
    python = root / ".venv/Scripts/pythonw.exe"
    if not python.is_file():
        raise FileNotFoundError("The checkout's windowless Python is missing.")
    # Do not inherit development VE_HOME or any desktop-only startup hold.
    env = {**os.environ, "VE_HOME": str(home)}
    env.pop("VE_STORAGE_MOVE_HOLD", None)
    proc.Popen(
        [str(python), "-m", "videoenhancer.remote.launcher", "--home", str(home)],
        cwd=root,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        health = running(home)
        if health and health.get("remote", {}).get("gateway_running"):
            return
        time.sleep(0.2)
    raise RuntimeError("The remote service did not start. Check the engine log.")


def prepare_certificates(home: Path) -> None:
    import socket

    from videoenhancer.remote.certificates import ensure_certificates, local_addresses

    name = os.environ.get("COMPUTERNAME") or socket.gethostname().split(".")[0]
    ensure_certificates(home / "remote", name, local_addresses())


def install(home: Path, windows=None) -> dict:
    windows = windows or Windows()
    prepare_certificates(home)
    save_settings(home, {"remote_enabled": True})
    windows.register(home, engine_root())
    windows.shortcut(home, engine_root())
    firewall_status = windows.firewall(read_settings(home))
    ensure_running(home)
    return {**request(home, "remote/pairing", "POST"), "firewall": firewall_status}


def uninstall(home: Path, forget_devices: bool = False, windows=None) -> dict:
    windows = windows or Windows()
    windows.remove()
    windows.remove_firewall()
    stop_service(home)
    save_settings(home, {"remote_enabled": False})
    if forget_devices:
        (home / "remote/devices.json").unlink(missing_ok=True)
    return {
        "service_running": False,
        "devices_forgotten": forget_devices,
        "library_preserved": True,
    }


def command(args, home: Path) -> dict:
    if args.remote_command == "install":
        return install(home)
    if args.remote_command == "uninstall":
        return uninstall(home, args.forget_devices)
    if args.remote_command == "pair":
        result = request(home, "remote/pairing", "POST")
        if args.message_box:
            message_box(f"{result['setup_address']}\nPairing closes at {result['closes_at']}.")
        return result
    health = running(home)
    import socket

    settings = read_settings(home)
    pc_name = os.environ.get("COMPUTERNAME") or socket.gethostname().split(".")[0]
    result: dict[str, Any] = {
        "service_running": False,
        "gateway_running": False,
        "pc_name": pc_name,
        "addresses": [f"https://{pc_name}.local:{settings['remote_https_port']}/"],
        "setup_address": f"http://{pc_name}.local:{settings['remote_setup_port']}/",
        "cert_expires": None,
        "paired_devices": 0,
        "pairing_open": False,
        "closes_at": None,
    }
    remote = home / "remote"
    if (remote / "server.crt").is_file():
        from cryptography import x509

        cert = x509.load_pem_x509_certificate((remote / "server.crt").read_bytes())
        result["cert_expires"] = cert.not_valid_after_utc.isoformat()
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        hosts = [
            *san.get_values_for_type(x509.DNSName),
            *map(str, san.get_values_for_type(x509.IPAddress)),
        ]
        result["addresses"] = [f"https://{host}:{settings['remote_https_port']}/" for host in hosts]
    if (remote / "devices.json").is_file():
        result["paired_devices"] = len(
            json.loads((remote / "devices.json").read_text(encoding="utf-8"))
        )
    if health:
        result.update(health.get("remote", {}))
        result["service_running"] = True
    from videoenhancer.remote import firewall

    result["firewall"] = firewall.status(
        firewall.program(engine_root()),
        settings["remote_https_port"],
        settings["remote_setup_port"],
    )
    if result["firewall"].get("warning"):
        print(result["firewall"]["warning"], file=sys.stderr)
    return result


def message_box(message: str) -> None:
    if os.name != "nt":
        raise RuntimeError("The pairing message box requires Windows.")
    import ctypes

    ctypes.windll.user32.MessageBoxW(None, message, "VideoEnhancer - Redo pairing", 0)
