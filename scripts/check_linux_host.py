"""Report whether a Linux host can run the VideoEnhancer engine and remote service.

This script only reads. It installs nothing, changes nothing and contacts no
network service. Run it with any Python 3.9 or newer that the host already has:

    python3 scripts/check_linux_host.py
    python3 scripts/check_linux_host.py --library /srv/videoenhancer/library --json

Each check prints its own measured value, or the reason it could not be
measured. "unknown" never means "fine". Only private IPv4 addresses are listed,
so the report does not disclose a public address.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

# The published PyNvVideoCodec and PyTorch Linux wheels are manylinux_2_28.
REQUIRED_GLIBC = (2, 28)
ENCODERS = ("hevc_nvenc", "h264_nvenc", "av1_nvenc")
DECODERS = ("hevc_cuvid", "h264_cuvid")
PRIVATE = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16")
)


def run(command: list[str], timeout: int = 20) -> tuple[int, str, str]:
    """Run a command without a shell; a missing program is an exit code, not a crash."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return 127, "", f"{command[0]} was not found."
    except (OSError, subprocess.SubprocessError) as error:
        return 1, "", str(error)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def operating_system() -> dict[str, Any]:
    name = "unknown"
    release = Path("/etc/os-release")
    if release.is_file():
        for line in release.read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, value = line.partition("=")
            if key == "PRETTY_NAME":
                name = value.strip().strip('"')
    library, version = platform.libc_ver()
    parts = tuple(int(part) for part in re.findall(r"\d+", version)[:2]) if version else ()
    return {
        "distribution": name,
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "libc": f"{library} {version}" if version else "unknown",
        "libc_supports_published_wheels": (
            bool(parts) and parts >= REQUIRED_GLIBC and platform.machine() == "x86_64"
        ),
        "hostname": socket.gethostname().split(".")[0],
    }


def hardware(library: Path) -> dict[str, Any]:
    memory_bytes = None
    info = Path("/proc/meminfo")
    if info.is_file():
        for line in info.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("MemTotal:"):
                memory_bytes = int(line.split()[1]) * 1024
    disks = {}
    for label, path in (("home", Path.home()), ("library", library)):
        target = path
        while not target.exists() and target != target.parent:
            target = target.parent
        try:
            usage = shutil.disk_usage(target)
            disks[label] = {
                "measured_path": str(target),
                "requested_path": str(path),
                "free_gb": round(usage.free / 1e9, 1),
                "total_gb": round(usage.total / 1e9, 1),
            }
        except OSError as error:
            disks[label] = {"requested_path": str(path), "error": str(error)}
    return {
        "logical_cpus": os.cpu_count(),
        "memory_gb": round(memory_bytes / 1e9, 1) if memory_bytes else None,
        "disks": disks,
    }


def gpus() -> dict[str, Any]:
    """Read the NVIDIA driver's own report; never infer a CUDA version ourselves."""
    if shutil.which("nvidia-smi") is None:
        return {
            "nvidia_present": False,
            "reason": "nvidia-smi was not found, so no usable NVIDIA driver is installed.",
        }
    code, output, error = run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,compute_cap",
            "--format=csv,noheader",
        ]
    )
    if code != 0:
        return {"nvidia_present": False, "reason": error or output or "nvidia-smi failed."}
    devices = []
    for line in output.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) == 4:
            devices.append(
                {
                    "name": fields[0],
                    "memory": fields[1],
                    "driver_version": fields[2],
                    "compute_capability": fields[3],
                }
            )
    driver_cuda = None
    _, banner, _ = run(["nvidia-smi"])
    match = re.search(r"CUDA Version:\s*([0-9.]+)", banner)
    if match:
        driver_cuda = match.group(1)
    return {
        "nvidia_present": bool(devices),
        "devices": devices,
        # The driver's maximum supported CUDA runtime decides which PyTorch
        # wheel index (cu126, cu128, cu130, ...) this host can install.
        "driver_maximum_cuda": driver_cuda,
        "persistence_mode_available": shutil.which("nvidia-persistenced") is not None,
        "container_toolkit": shutil.which("nvidia-ctk") is not None,
    }


def ffmpeg() -> dict[str, Any]:
    path = shutil.which("ffmpeg")
    if path is None:
        return {"present": False, "reason": "ffmpeg was not found on PATH."}
    code, output, _ = run([path, "-version"])
    version = output.splitlines()[0] if code == 0 and output else "unknown"
    found = {}
    for flag, names in (("-encoders", ENCODERS), ("-decoders", DECODERS)):
        code, listing, _ = run([path, "-hide_banner", flag])
        for name in names:
            found[name] = bool(code == 0 and re.search(rf"\b{re.escape(name)}\b", listing))
    return {
        "present": True,
        "path": path,
        "version": version,
        "ffprobe": shutil.which("ffprobe"),
        "hardware_codecs": found,
    }


def service_platform() -> dict[str, Any]:
    code, output, _ = run(["systemctl", "--version"])
    systemd = output.splitlines()[0] if code == 0 and output else None
    code, user_state, _ = run(["systemctl", "--user", "is-system-running"])
    sudo_code, _, _ = run(["sudo", "-n", "true"], timeout=10)
    avahi_code, avahi_state, _ = run(["systemctl", "is-active", "avahi-daemon"])
    return {
        "systemd": systemd,
        "user_manager": user_state or "unavailable",
        "passwordless_sudo": sudo_code == 0,
        "avahi_installed": shutil.which("avahi-daemon") is not None
        or Path("/usr/sbin/avahi-daemon").exists(),
        # Without Avahi the certificate's <hostname>.local name does not resolve
        # for an iPad, even though the HTTPS service itself works.
        "avahi_active": avahi_state == "active",
        "python": {
            name: shutil.which(name)
            for name in ("python3", "python3.12", "python3.13")
            if shutil.which(name)
        },
        "running_python": platform.python_version(),
        "uv": shutil.which("uv"),
        "git": shutil.which("git"),
    }


def addresses() -> dict[str, Any]:
    """List private IPv4 addresses only; a public address is counted, not printed."""
    private: list[str] = []
    public = 0
    code, output, _ = run(["ip", "-4", "-o", "addr"])
    candidates = re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", output) if code == 0 else []
    if not candidates:
        code, output, _ = run(["hostname", "-I"])
        candidates = re.findall(r"\d+\.\d+\.\d+\.\d+", output) if code == 0 else []
    if not candidates:
        try:
            candidates = [
                item[4][0]
                for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
            ]
        except OSError:
            candidates = []
    for value in sorted(set(candidates)):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.is_loopback:
            continue
        if any(address in network for network in PRIVATE):
            private.append(value)
        else:
            public += 1
    return {
        "private_ipv4": private,
        "public_ipv4_count": public,
        # The remote gateway refuses every client outside the private ranges, so
        # an iPad can only reach this host over the home LAN or a private VPN.
        "reachable_by_ipad_as_built": bool(private),
    }


def report(library: Path) -> dict[str, Any]:
    return {
        "operating_system": operating_system(),
        "hardware": hardware(library),
        "gpu": gpus(),
        "ffmpeg": ffmpeg(),
        "service_platform": service_platform(),
        "network": addresses(),
    }


def blockers(data: dict[str, Any]) -> list[str]:
    found = []
    if not data["gpu"].get("nvidia_present"):
        found.append(
            "No NVIDIA GPU is usable: "
            f"{data['gpu'].get('reason', 'unknown')} CPU-only processing is far slower."
        )
    if not data["operating_system"]["libc_supports_published_wheels"]:
        found.append(
            "This host does not match the published x86_64 manylinux_2_28 wheels "
            f"(libc {data['operating_system']['libc']}, "
            f"architecture {data['operating_system']['architecture']}); "
            "PyNvVideoCodec and PyTorch would have to be built or replaced."
        )
    if not data["ffmpeg"]["present"]:
        found.append("FFmpeg is missing; probing, muxing and CPU encoding need it.")
    elif not any(data["ffmpeg"]["hardware_codecs"].get(name) for name in ENCODERS):
        found.append("This FFmpeg build has no NVENC encoder, so hardware encoding is unavailable.")
    if not data["service_platform"]["systemd"]:
        found.append("systemd was not found, so the service needs another supervisor.")
    if not data["service_platform"]["avahi_active"]:
        found.append(
            "Avahi is not active, so the certificate's <hostname>.local name will not "
            "resolve for an iPad; a fixed private IPv4 address would be needed instead."
        )
    if not data["network"]["reachable_by_ipad_as_built"]:
        found.append(
            "This host has no private IPv4 address. The remote gateway only accepts "
            "clients in the private ranges, so an iPad cannot reach it without a VPN."
        )
    return found


def lines(data: dict[str, Any]) -> list[str]:
    system = data["operating_system"]
    machine = data["hardware"]
    gpu = data["gpu"]
    tools = data["ffmpeg"]
    service = data["service_platform"]
    text = [
        "VideoEnhancer Linux host report",
        "",
        f"Host           {system['hostname']} ({system['architecture']})",
        f"Distribution   {system['distribution']}",
        f"Kernel / libc  {system['kernel']} / {system['libc']}",
        f"CPU / memory   {machine['logical_cpus']} logical CPUs / {machine['memory_gb']} GB",
    ]
    for label, disk in machine["disks"].items():
        if "error" in disk:
            text.append(f"Disk {label:9} {disk['requested_path']}: {disk['error']}")
        else:
            text.append(
                f"Disk {label:9} {disk['measured_path']}: "
                f"{disk['free_gb']} GB free of {disk['total_gb']} GB"
            )
    if gpu.get("nvidia_present"):
        for index, device in enumerate(gpu["devices"]):
            text.append(
                f"GPU {index}          {device['name']}, {device['memory']}, "
                f"driver {device['driver_version']}, compute {device['compute_capability']}"
            )
        text.append(f"Driver CUDA    up to {gpu.get('driver_maximum_cuda') or 'unknown'}")
    else:
        text.append(f"GPU            none usable ({gpu.get('reason', 'unknown')})")
    if tools["present"]:
        codecs = ", ".join(
            f"{name}={'yes' if present else 'no'}"
            for name, present in tools["hardware_codecs"].items()
        )
        text.append(f"FFmpeg         {tools['version']}")
        text.append(f"Hardware codecs {codecs}")
    else:
        text.append(f"FFmpeg         missing ({tools['reason']})")
    text += [
        f"systemd        {service['systemd'] or 'missing'} "
        f"(user manager: {service['user_manager']})",
        f"Passwordless sudo {'yes' if service['passwordless_sudo'] else 'no'}",
        f"Avahi          installed={service['avahi_installed']} active={service['avahi_active']}",
        f"Python         running {service['running_python']}; "
        f"available {', '.join(service['python']) or 'none found'}",
        f"uv / git       {service['uv'] or 'missing'} / {service['git'] or 'missing'}",
        f"Private IPv4   {', '.join(data['network']['private_ipv4']) or 'none'} "
        f"(public addresses: {data['network']['public_ipv4_count']})",
        "",
    ]
    found = blockers(data)
    if found:
        text.append("Blocking findings:")
        text += [f"  - {item}" for item in found]
    else:
        text.append("No blocking finding was measured by this report.")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--library",
        type=Path,
        default=Path.home() / "Videos/VideoEnhancer",
        help="Planned finished-video folder; its filesystem free space is measured.",
    )
    parser.add_argument("--json", action="store_true", help="Print the raw measurements as JSON.")
    arguments = parser.parse_args(argv)
    data = report(arguments.library)
    if arguments.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print("\n".join(lines(data)))
    return 1 if blockers(data) else 0


if __name__ == "__main__":
    raise SystemExit(main())
