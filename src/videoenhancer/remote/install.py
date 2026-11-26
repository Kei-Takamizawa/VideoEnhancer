"""Per-user service startup (Windows task or systemd user unit) and local management."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path, PurePath
from typing import Any
from xml.sax.saxutils import escape

from videoenhancer import proc
from videoenhancer.service.settings import read_settings, save_settings

TASK_NAME = "VideoEnhancer"
SHORTCUT_NAME = "VideoEnhancer - Redo pairing.lnk"
UNIT_NAME = "videoenhancer.service"


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

    def firewall_status(self, settings: dict) -> dict:
        from videoenhancer.remote import firewall

        return firewall.status(
            firewall.program(engine_root()),
            settings["remote_https_port"],
            settings["remote_setup_port"],
        )

    def start(self) -> None:
        # Discovery disappears just before the task process exits. IgnoreNew would
        # discard a start request while that process is still finishing.
        _powershell(
            "$ErrorActionPreference='Stop'; $deadline=[DateTime]::UtcNow.AddSeconds(25); "
            "while ((Get-ScheduledTask -TaskName 'VideoEnhancer').State -eq 'Running') { "
            "if ([DateTime]::UtcNow -ge $deadline) { throw 'The service task did not stop.' }; "
            "Start-Sleep -Milliseconds 200 }; Start-ScheduledTask -TaskName 'VideoEnhancer'"
        )

    def describe(self) -> dict:
        return {"manager": "Windows Task Scheduler", "task": TASK_NAME}


def _unit_value(value: str | PurePath) -> str:
    text = str(value)
    if any(character in text for character in "\n\r\0"):
        raise ValueError("Service paths cannot contain line breaks.")
    return text.replace("%", "%%")


def _unit_argument(value: str | PurePath) -> str:
    text = _unit_value(value).replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")
    return f'"{text}"'


def unit_text(python: PurePath, home: PurePath, root: PurePath) -> str:
    """A systemd user unit equivalent to the Windows sign-in task."""
    command = " ".join(
        _unit_argument(part)
        for part in (python, "-m", "videoenhancer.remote.launcher", "--home", home)
    )
    return (
        "[Unit]\n"
        "Description=VideoEnhancer headless service\n"
        # Like the Windows task: a failed start is retried three times, one minute apart.
        "StartLimitIntervalSec=900\n"
        "StartLimitBurst=4\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={_unit_value(root)}\n"
        f"ExecStart={command}\n"
        "Restart=on-failure\n"
        "RestartSec=60\n"
        "UMask=0077\n"
        "NoNewPrivileges=yes\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


class Systemd:
    """Per-user systemd service; it changes nothing outside the user's own manager."""

    def __init__(self, run=None, unit_path: Path | None = None):
        self.run = run or self._run
        config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self.unit_path = unit_path or config / "systemd/user" / UNIT_NAME
        if run is None:
            # An injected runner (tests) never reaches a real service manager.
            if os.name == "nt":
                raise RuntimeError("Use the Windows task on Windows.")
            if shutil.which("systemctl") is None:
                raise RuntimeError("Remote startup installation needs systemd (systemctl).")

    @staticmethod
    def _run(arguments: list[str]) -> subprocess.CompletedProcess:
        return proc.run(
            arguments,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

    def _systemctl(self, *arguments: str, check: bool = True) -> str:
        result = self.run(["systemctl", "--user", *arguments])
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"systemctl --user {' '.join(arguments)} failed: {detail or result.returncode}"
            )
        return (result.stdout or "").strip()

    def register(self, home: Path, root: Path) -> None:
        python = root / ".venv/bin/python"
        if not python.is_file():
            raise FileNotFoundError("This checkout needs .venv/bin/python.")
        self.unit_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.unit_path.with_name(f".{UNIT_NAME}.tmp")
        temporary.write_text(unit_text(python, home, root), encoding="utf-8")
        temporary.replace(self.unit_path)
        self._systemctl("daemon-reload")
        self._systemctl("enable", UNIT_NAME)

    def shortcut(self, home: Path, root: Path) -> None:
        # A headless server has no Start menu; pairing opens with 've remote pair'.
        return None

    def remove(self) -> None:
        if self.unit_path.exists():
            self._systemctl("disable", UNIT_NAME, check=False)
            self.unit_path.unlink()
            self._systemctl("daemon-reload")

    def firewall(self, settings: dict) -> dict:
        return {**self.firewall_status(settings), "setup": "not_managed"}

    def remove_firewall(self) -> None:
        return None

    def firewall_status(self, settings: dict) -> dict:
        return {
            "managed": False,
            "message": (
                "VideoEnhancer does not change the Linux firewall. If one is active, "
                f"allow TCP {settings['remote_https_port']} and "
                f"{settings['remote_setup_port']} from the home network only."
            ),
        }

    def start(self) -> None:
        # A gracefully stopped service may still be exiting; starting an active
        # unit would be a no-op, so wait until systemd reports it inactive.
        deadline = time.monotonic() + 25
        while self._systemctl("is-active", UNIT_NAME, check=False) in {
            "active",
            "activating",
            "deactivating",
            "reloading",
        }:
            if time.monotonic() >= deadline:
                raise RuntimeError("The service unit did not stop.")
            time.sleep(0.2)
        self._systemctl("reset-failed", UNIT_NAME, check=False)
        self._systemctl("start", UNIT_NAME)

    def linger(self) -> bool | None:
        user = os.environ.get("USER") or Path.home().name
        result = self.run(["loginctl", "show-user", user, "--property=Linger", "--value"])
        if result.returncode != 0:
            return None
        return (result.stdout or "").strip() == "yes"

    def enable_linger(self) -> bool:
        """Ask logind, without a password prompt, to start this user's services at boot."""
        if self.linger():
            return True
        self.run(["loginctl", "enable-linger", "--no-ask-password"])
        return bool(self.linger())

    def describe(self) -> dict:
        result: dict[str, Any] = {
            "manager": "systemd user service",
            "unit": str(self.unit_path),
            "installed": self.unit_path.exists(),
        }
        if result["installed"]:
            result["enabled"] = self._systemctl("is-enabled", UNIT_NAME, check=False)
            result["active"] = self._systemctl("is-active", UNIT_NAME, check=False)
            result["starts_at_boot"] = self.linger()
        return result


def service_platform():
    return Windows() if os.name == "nt" else Systemd()


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


def ensure_running(home: Path, service=None) -> None:
    health = running(home)
    if health and health.get("remote", {}).get("gateway_running"):
        return
    if health:
        stop_service(home)
    (service or service_platform()).start()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        health = running(home)
        if health and health.get("remote", {}).get("gateway_running"):
            return
        time.sleep(0.2)
    raise RuntimeError("The remote service did not start. Check the engine log.")


def prepare_certificates(home: Path) -> None:
    from videoenhancer.remote.certificates import advertised_identity, ensure_certificates

    name, addresses = advertised_identity(read_settings(home))
    ensure_certificates(home / "remote", name, addresses)


def install(
    home: Path,
    service=None,
    *,
    name: str | None = None,
    addresses: list[str] | None = None,
) -> dict:
    service = service or service_platform()
    identity: dict[str, Any] = {}
    if name is not None:
        identity["remote_name"] = name
    if addresses is not None:
        identity["remote_addresses"] = addresses
    if identity:
        # Validate before touching the service, so a typo changes nothing.
        save_settings(home, identity)
    prepare_certificates(home)
    save_settings(home, {"remote_enabled": True})
    service.register(home, engine_root())
    service.shortcut(home, engine_root())
    firewall_status = service.firewall(read_settings(home))
    result: dict[str, Any] = {}
    enable_linger = getattr(service, "enable_linger", None)
    if enable_linger is not None and not enable_linger():
        user = os.environ.get("USER") or Path.home().name
        result["starts_at_boot"] = False
        result["message"] = (
            f"The service runs now but will not start at boot until lingering is on: "
            f"run 'sudo loginctl enable-linger {user}' once."
        )
    ensure_running(home, service)
    return {**request(home, "remote/pairing", "POST"), "firewall": firewall_status, **result}


def uninstall(home: Path, forget_devices: bool = False, service=None) -> dict:
    service = service or service_platform()
    service.remove()
    service.remove_firewall()
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
        return install(
            home,
            name=getattr(args, "name", None),
            addresses=getattr(args, "addresses", None),
        )
    if args.remote_command == "uninstall":
        return uninstall(home, args.forget_devices)
    if args.remote_command in {"stop", "restart"}:
        stop_service(home)
        if args.remote_command == "restart":
            ensure_running(home)
        return {"service_running": args.remote_command == "restart"}
    if args.remote_command == "pair":
        result = request(home, "remote/pairing", "POST")
        if args.message_box:
            message_box(
                f"{result['setup_address']}\nPairing closes at {result['closes_at']}.",
                closes_at=result["closes_at"],
                home=home,
            )
        return result
    health = running(home)
    from videoenhancer.remote.certificates import advertised_identity

    settings = read_settings(home)
    pc_name, _ = advertised_identity(settings)
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
    try:
        service = service_platform()
    except RuntimeError as error:
        result["service"] = {"error": str(error)}
        result["firewall"] = {"managed": False}
        return result
    result["service"] = service.describe()
    result["firewall"] = service.firewall_status(settings)
    if result["firewall"].get("warning"):
        print(result["firewall"]["warning"], file=sys.stderr)
    return result


def message_box(
    message: str, *, closes_at: str | float | None = None, home: Path | None = None
) -> None:
    if isinstance(closes_at, str):
        closes_at = datetime.fromisoformat(closes_at).timestamp()
    seconds = math.ceil(closes_at - time.time()) if closes_at is not None else 30
    if seconds <= 0:
        return
    if os.name != "nt":
        raise RuntimeError("The pairing message box requires Windows.")
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        f"(New-Object -ComObject WScript.Shell).Popup({_literal(message)}, "
        f"{seconds}, 'VideoEnhancer - Redo pairing', 0) | Out-Null",
    ]
    streams: dict[str, Any] = dict(
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if home is None:
        proc.run(command, timeout=seconds + 5, check=True, **streams)
        return
    # Pairing can close early after a claim. Only this owned popup process is terminated.
    child = proc.Popen(command, **streams)
    try:
        deadline = time.time() + seconds
        while child.poll() is None and time.time() < deadline:
            try:
                pairing = json.loads((home / "remote/pairing.json").read_text(encoding="utf-8"))
                if pairing.get("closes_at", 0) <= time.time():
                    break
            except (OSError, ValueError):
                break
            time.sleep(0.25)
    finally:
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
