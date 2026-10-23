"""Optional, manually requested and checksum-verified standalone link tools."""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import threading
import time
import urllib.request
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import urlsplit

from videoenhancer.service.settings import write_json

MIN_DENO = (2, 3, 0)
REPOSITORIES = {
    "stable": "yt-dlp/yt-dlp",
    "nightly": "yt-dlp/yt-dlp-nightly-builds",
}
ASSETS = {"yt-dlp": "yt-dlp.exe", "deno": "deno-x86_64-pc-windows-msvc.zip"}
HOSTS = {
    "api.github.com",
    "github.com",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
}
NOTICE = (
    "Only download videos you have the right to use. Some sites' terms do not allow downloading."
)


def official_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Link tools must come from the official HTTPS release publisher.")
    return url


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ToolManager:
    def __init__(self, home: Path):
        self.root = home / "tools"
        if self.root.is_symlink() or self.root.is_junction():
            raise ValueError("The link-tools folder must not be a link.")
        self.lock = threading.Lock()
        self.opener = urllib.request.build_opener(ReleaseRedirect())

    def _folder(self, tool: str) -> Path:
        if tool not in ASSETS:
            raise ValueError("Unknown link tool.")
        folder = self.root / tool
        if (
            self.root.is_symlink()
            or self.root.is_junction()
            or folder.is_symlink()
            or folder.is_junction()
            or folder.resolve().parent != self.root.resolve()
        ):
            raise ValueError("The link-tool folder must not be a link.")
        return folder

    def _read(self, url: str, limit: int = 2_000_000) -> bytes:
        request = urllib.request.Request(
            official_url(url),
            headers={"User-Agent": "VideoEnhancer", "Accept": "application/vnd.github+json"},
        )
        with self.opener.open(request, timeout=5) as response:
            official_url(response.url)
            body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("The release information is larger than expected.")
        return body

    def status(self) -> dict[str, Any]:
        installed = {}
        for tool in ASSETS:
            folder = self._folder(tool)
            metadata = folder / "installed.json"
            if metadata.is_file():
                from videoenhancer.damaged_json import read_object

                try:
                    item = read_object(metadata, self.root.parent, ("executable_bytes",))
                except (ValueError, UnicodeError):
                    continue
                binary = folder / f"{tool}.exe"
                item["present"] = (
                    binary.is_file() and binary.stat().st_size == item["executable_bytes"]
                )
                installed[tool] = item
        return {
            "installed": installed,
            "available": all(installed.get(tool, {}).get("present") for tool in ASSETS),
            "notice": NOTICE,
        }

    def check(self, channel: str) -> dict[str, Any]:
        if channel not in REPOSITORIES:
            raise ValueError("Choose Stable or Nightly.")
        tools = []
        for tool, repository in (("yt-dlp", REPOSITORIES[channel]), ("deno", "denoland/deno")):
            release = json.loads(
                self._read(f"https://api.github.com/repos/{repository}/releases/latest")
            )
            tag = release["tag_name"]
            if not re.fullmatch(r"[A-Za-z0-9._-]+", tag):
                raise ValueError("Invalid release version.")
            if tool == "deno":
                version = tuple(int(part) for part in tag.removeprefix("v").split("."))
                if version < MIN_DENO:
                    raise ValueError("yt-dlp needs Deno 2.3.0 or later.")
            names = {asset["name"]: asset for asset in release["assets"]}
            filename = ASSETS[tool]
            checksum_name = "SHA2-256SUMS" if tool == "yt-dlp" else filename + ".sha256sum"
            if filename not in names or checksum_name not in names:
                raise ValueError(f"{tool} has no published SHA-256 checksum. Installation refused.")
            prefix = f"https://github.com/{repository}/releases/download/{tag}/"
            for name in (filename, checksum_name):
                if names[name]["browser_download_url"] != prefix + name:
                    raise ValueError("Unexpected release asset publisher.")
            size = names[filename]["size"]
            if not isinstance(size, int) or not 0 < size <= 300_000_000:
                raise ValueError("Unexpected link-tool download size.")
            tools.append(
                dict(
                    tool=tool,
                    tag=tag,
                    version=tag.removeprefix("v"),
                    released=release["published_at"],
                    bytes=size,
                    url=prefix + filename,
                    checksum_url=prefix + checksum_name,
                    filename=filename,
                    channel=channel if tool == "yt-dlp" else "stable",
                    licence="Unlicense source; GPLv3+ executable" if tool == "yt-dlp" else "MIT",
                )
            )
        plan = {"id": uuid.uuid4().hex, "channel": channel, "tools": tools, "notice": NOTICE}
        self.root.mkdir(parents=True, exist_ok=True)
        write_json(self.root / "releases.json", plan)
        return plan

    def _checksum(self, item: dict[str, Any]) -> str:
        lines = self._read(item["checksum_url"]).decode("utf-8").splitlines()
        matches = []
        for line in lines:
            fields = line.split()
            if len(fields) == 2 and fields[1].lstrip("*") == item["filename"]:
                matches.append(fields[0].lower())
        if not matches and item["tool"] == "deno":
            # Windows Deno releases publish PowerShell Get-FileHash output.
            fields = {}
            for line in lines:
                key, separator, value = line.partition(":")
                if separator:
                    fields.setdefault(key.strip(), []).append(value.strip())
            if (
                fields.get("Algorithm") == ["SHA256"]
                and len(fields.get("Hash", [])) == 1
                and len(fields.get("Path", [])) == 1
                and PureWindowsPath(fields["Path"][0]).name == item["filename"]
            ):
                matches.append(fields["Hash"][0].lower())
        if len(matches) != 1 or not re.fullmatch("[0-9a-f]{64}", matches[0]):
            raise ValueError(
                f"No unambiguous published SHA-256 for {item['tool']}. Installation refused."
            )
        return matches[0]

    def install(
        self,
        channel: str,
        plan_id: str,
        progress: Callable[[dict[str, Any]], None],
        cancelled: Callable[[], bool],
    ) -> dict[str, Any]:
        if not self.lock.acquire(blocking=False):
            raise ValueError("Link tools are already being changed.")
        try:
            # Use only the manually checked plan shown in the consent dialog.
            plan = json.loads((self.root / "releases.json").read_text(encoding="utf-8"))
            if plan["channel"] != channel or plan["id"] != plan_id:
                raise ValueError("Release information changed. Check again before installing.")
            total = sum(item["bytes"] for item in plan["tools"])
            complete = 0
            started = time.monotonic()
            for item in plan["tools"]:
                tool = item["tool"]
                repository = REPOSITORIES[channel] if tool == "yt-dlp" else "denoland/deno"
                filename = ASSETS[tool]
                checksum_name = "SHA2-256SUMS" if tool == "yt-dlp" else filename + ".sha256sum"
                if not re.fullmatch(r"[A-Za-z0-9._-]+", item["tag"]):
                    raise ValueError("Invalid cached release version.")
                prefix = f"https://github.com/{repository}/releases/download/{item['tag']}/"
                if (
                    item["filename"] != filename
                    or item["url"] != prefix + filename
                    or item["checksum_url"] != prefix + checksum_name
                ):
                    raise ValueError("Unexpected cached release publisher.")
                expected = self._checksum(item)
                folder = self._folder(item["tool"])
                folder.mkdir(parents=True, exist_ok=True)
                temporary = folder / f"download-{uuid.uuid4().hex}.tmp"
                staged = folder / f"verified-{uuid.uuid4().hex}.tmp"
                try:
                    digest = hashlib.sha256()
                    checked_bytes = bytearray()
                    received = 0
                    request = urllib.request.Request(
                        official_url(item["url"]), headers={"User-Agent": "VideoEnhancer"}
                    )
                    with (
                        self.opener.open(request, timeout=5) as response,
                        temporary.open("xb") as sink,
                    ):
                        official_url(response.url)
                        while True:
                            if cancelled():
                                raise InterruptedError("Link-tool installation cancelled.")
                            block = response.read(256 * 1024)
                            if not block:
                                break
                            received += len(block)
                            if received > item["bytes"]:
                                raise ValueError("Link-tool download exceeds its published size.")
                            sink.write(block)
                            digest.update(block)
                            checked_bytes.extend(block)
                            done = complete + received
                            speed = done / max(0.001, time.monotonic() - started)
                            progress(
                                dict(
                                    phase=f"Downloading {item['tool']}",
                                    percent=done / total * 98,
                                    remaining_seconds=(total - done) / speed,
                                    bytes=done,
                                    total_bytes=total,
                                )
                            )
                    if received != item["bytes"] or digest.hexdigest() != expected:
                        raise ValueError(
                            f"{item['tool']} SHA-256 verification failed. The file will not run."
                        )
                    if cancelled():
                        raise InterruptedError("Link-tool installation cancelled.")
                    data = bytes(checked_bytes)
                    if item["tool"] == "deno":
                        with zipfile.ZipFile(io.BytesIO(data)) as archive:
                            entries = archive.infolist()
                            if (
                                len(entries) != 1
                                or entries[0].filename != "deno.exe"
                                or entries[0].file_size > 300_000_000
                            ):
                                raise ValueError("Unexpected Deno archive contents.")
                            data = archive.read(entries[0])
                    with staged.open("xb") as stream:
                        stream.write(data)
                    executable_hash = hashlib.sha256(data).hexdigest()
                    staged.replace(folder / f"{item['tool']}.exe")
                    write_json(
                        folder / "installed.json",
                        {
                            **item,
                            "sha256": expected,
                            "executable_sha256": executable_hash,
                            "executable_bytes": len(data),
                        },
                    )
                    complete += received
                finally:
                    temporary.unlink(missing_ok=True)
                    staged.unlink(missing_ok=True)
            progress(dict(phase="Link tools installed", percent=100, remaining_seconds=0))
            return self.status()
        finally:
            self.lock.release()

    def executable(self, tool: str) -> Path:
        folder = self._folder(tool)
        item = json.loads((folder / "installed.json").read_text(encoding="utf-8"))
        binary = folder / f"{tool}.exe"
        if binary.is_symlink() or binary.is_junction():
            raise ValueError("The installed link tool must not be a link.")
        with binary.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != item["executable_sha256"]:
            raise ValueError("The installed link tool changed. Reinstall it before use.")
        return binary

    def uninstall(self) -> dict[str, Any]:
        if not self.lock.acquire(blocking=False):
            raise ValueError("Link tools are already being changed.")
        try:
            for tool in ASSETS:
                folder = self._folder(tool)
                if folder.exists():
                    shutil.rmtree(folder)
            return self.status()
        finally:
            self.lock.release()
