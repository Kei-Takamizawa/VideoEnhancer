"""The optional installer never executes unverified release assets."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from videoenhancer.service.link_tools import ASSETS, ToolManager, official_url


class Response(io.BytesIO):
    def __init__(self, body, url):
        super().__init__(body)
        self.url = url


@pytest.fixture
def publisher(tmp_path):
    files = {}
    calls = []
    binaries = {"yt-dlp": b"MZ verified test fixture", "deno": b"MZ deno test fixture"}
    for tool, repo, tag in (
        ("yt-dlp", "yt-dlp/yt-dlp", "2026.08.19"),
        ("deno", "denoland/deno", "v2.9.7"),
    ):
        asset = ASSETS[tool]
        if tool == "deno":
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as zip_file:
                zip_file.writestr("deno.exe", binaries[tool])
            body = archive.getvalue()
        else:
            body = binaries[tool]
        checksum = "SHA2-256SUMS" if tool == "yt-dlp" else asset + ".sha256sum"
        prefix = f"https://github.com/{repo}/releases/download/{tag}/"
        digest = hashlib.sha256(body).hexdigest()
        files[prefix + asset] = body
        files[prefix + checksum] = (
            f"{digest}  {asset}\n"
            if tool == "yt-dlp"
            else f"Algorithm : SHA256\nHash : {digest.upper()}\nPath : C:\\a\\target\\{asset}\n"
        ).encode()
        files[f"https://api.github.com/repos/{repo}/releases/latest"] = json.dumps(
            dict(
                tag_name=tag,
                published_at="2026-08-19T00:00:00Z",
                assets=[
                    dict(name=asset, size=len(body), browser_download_url=prefix + asset),
                    dict(name=checksum, size=100, browser_download_url=prefix + checksum),
                ],
            )
        ).encode()
    manager = ToolManager(tmp_path)

    class Publisher:
        def open(self, request, timeout):
            assert timeout == 5
            calls.append(request.full_url)
            return Response(files[request.full_url], request.full_url)

    manager.opener = Publisher()
    return manager, files, calls, binaries


def test_verified_install_tamper_guard_and_uninstall(publisher, tmp_path):
    manager, _, calls, binaries = publisher
    assert manager.status()["available"] is False
    assert not calls
    plan = manager.check("stable")
    packets = []
    result = manager.install("stable", plan["id"], packets.append, lambda: False)
    assert result["available"] is True
    assert packets[-1]["percent"] == 100
    assert all(packet["remaining_seconds"] >= 0 for packet in packets)
    for tool in ASSETS:
        assert manager.executable(tool).read_bytes() == binaries[tool]
    target = manager.executable("yt-dlp")
    target.write_bytes(b"!" * len(binaries["yt-dlp"]))
    with pytest.raises(ValueError, match="changed"):
        manager.executable("yt-dlp")
    downloaded = tmp_path / "downloaded.mp4"
    downloaded.write_bytes(b"user original")
    assert manager.uninstall()["available"] is False
    assert downloaded.read_bytes() == b"user original"


def test_installed_bytes_are_the_bytes_verified_during_download(publisher, monkeypatch):
    manager, _, _, binaries = publisher
    plan = manager.check("stable")
    original_read = Path.read_bytes

    def replaced_read(path):
        if path.suffix == ".download":
            return b"MZ substituted unverified file"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", replaced_read)
    manager.install("stable", plan["id"], lambda _: None, lambda: False)
    assert manager.executable("yt-dlp").read_bytes() == binaries["yt-dlp"]


def test_bad_checksum_does_not_replace_binary(publisher):
    manager, files, _, _ = publisher
    plan = manager.check("stable")
    manager.install("stable", plan["id"], lambda _: None, lambda: False)
    old = manager.executable("yt-dlp").read_bytes()
    files[plan["tools"][0]["url"]] = b"!" * len(old)
    with pytest.raises(ValueError, match="SHA-256 verification failed"):
        manager.install("stable", plan["id"], lambda _: None, lambda: False)
    assert manager.executable("yt-dlp").read_bytes() == old
    assert not list(manager.root.rglob("*.tmp"))


def test_cancel_does_not_leave_executable_or_partial(publisher):
    manager, _, _, _ = publisher
    plan = manager.check("stable")
    with pytest.raises(InterruptedError):
        manager.install("stable", plan["id"], lambda _: None, lambda: True)
    assert not list(manager.root.rglob("*.exe"))
    assert not list(manager.root.rglob("*.tmp"))


def test_plan_requires_consent_snapshot_and_publisher(publisher):
    manager, _, calls, _ = publisher
    plan = manager.check("stable")
    count = len(calls)
    with pytest.raises(ValueError, match="changed"):
        manager.install("stable", "stale", lambda _: None, lambda: False)
    assert len(calls) == count
    plan["tools"][0]["url"] = "https://github.com/other/project/releases/download/tag/payload.exe"
    (manager.root / "releases.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="publisher"):
        manager.install("stable", plan["id"], lambda _: None, lambda: False)


def test_missing_published_checksum_refuses(publisher):
    manager, files, _, _ = publisher
    key = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
    release = json.loads(files[key])
    release["assets"] = release["assets"][:1]
    files[key] = json.dumps(release).encode()
    with pytest.raises(ValueError, match="no published SHA-256"):
        manager.check("stable")
    assert not list(manager.root.rglob("*.exe"))


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a",
        "https://evil.test/a",
        "https://github.com@evil.test/a",
        "https://github.com:444/a",
        "file:///tool.exe",
    ],
)
def test_only_official_https_release_transports(url):
    with pytest.raises(ValueError, match="official HTTPS"):
        official_url(url)


def test_ambiguous_checksum_and_archive_path_are_refused(publisher):
    manager, files, _, _ = publisher
    plan = manager.check("stable")
    item = plan["tools"][0]
    files[item["checksum_url"]] *= 2
    with pytest.raises(ValueError, match="unambiguous"):
        manager.install("stable", plan["id"], lambda _: None, lambda: False)
    files[item["checksum_url"]] = files[item["checksum_url"]].splitlines(keepends=True)[0]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../deno.exe", b"bad")
    item = plan["tools"][1]
    body = archive.getvalue()
    item["bytes"] = len(body)
    files[item["url"]] = body
    files[item["checksum_url"]] = (
        f"{hashlib.sha256(body).hexdigest()}  {item['filename']}\n".encode()
    )
    (manager.root / "releases.json").write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="archive contents"):
        manager.install("stable", plan["id"], lambda _: None, lambda: False)
    assert not (manager.root / "deno/deno.exe").exists()
