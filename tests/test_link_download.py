"""Real verified downloader against local synthetic media only."""

import functools
import http.server
import json
import os
import shutil
import ssl
import subprocess
import threading
import time
import uuid
from pathlib import Path

import pytest

from videoenhancer.config import executable
from videoenhancer.media.probe import probe
from videoenhancer.service.engine import Engine
from videoenhancer.service.link_tools import ToolManager
from videoenhancer.service.settings import DEFAULTS, save_settings
from videoenhancer.service.video_links import ENCRYPTION_ERROR, VideoLinks, header_probe


@pytest.mark.parametrize("kind", ["playlist", "sign-in", "live", "hdr", "rotated"])
def test_local_metadata_policy(tmp_path, video_factory, ffmpeg_run, monkeypatch, kind):
    installed = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not installed:
        pytest.skip("Explicit verified standalone link tools are required")
    monkeypatch.chdir(tmp_path)
    source = video_factory(
        width=320,
        height=180,
        frames=60,
        transfer="smpte2084" if kind == "hdr" else "bt709",
    )
    served = source
    if kind == "hdr":
        served = tmp_path / "hdr-faststart.mp4"
        ffmpeg_run("-i", str(source), "-c", "copy", "-movflags", "+faststart", str(served))
    if kind == "rotated":
        served = tmp_path / "portrait.mp4"
        ffmpeg_run("-display_rotation", "90", "-i", str(source), "-c", "copy", str(served))
    if kind == "playlist":
        served = tmp_path / "playlist.html"
        videos = [source, video_factory(), video_factory()]
        served.write_text(
            "<html><title>Three videos</title>"
            + "".join(f'<video controls src="{p.name}"></video>' for p in videos)
            + "</html>",
            encoding="utf-8",
        )
    if kind == "live":
        served = tmp_path / "live.m3u8"
        served.write_text(
            "#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:2,\nsegment.ts\n",
            encoding="utf-8",
        )

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if kind == "sign-in":
                self.send_error(403, "Sign in required")
            else:
                super().do_GET()

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(tmp_path))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        links = VideoLinks(tmp_path / "home", ToolManager(Path(installed)))

        def check():
            return links.check(
                f"http://127.0.0.1:{server.server_port}/{served.name}",
                {**DEFAULTS, "backend": "cpu"},
                lambda: False,
                lambda _: None,
                lambda _: None,
            )

        if kind == "sign-in":
            with pytest.raises(ValueError, match="Sign-in"):
                check()
            return
        result = check()
        if kind == "playlist":
            assert len(result["entries"]) == 3
        elif kind == "live":
            assert "Live streams" in result["entries"][0]["error"]
        elif kind == "hdr":
            assert "HDR" in result["entries"][0].get("error", ""), json.dumps(result)
        else:
            card = result["entries"][0]
            assert not card.get("error"), card
            assert (card["formats"][0]["width"], card["formats"][0]["height"]) == (180, 320)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("interruption", ["cancel", "disconnect"])
def test_cancelled_transfer_resumes_partial_file(
    tmp_path, video_factory, ffmpeg_run, monkeypatch, interruption
):
    installed = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not installed:
        pytest.skip("Explicit verified standalone link tools are required")
    original = video_factory(width=640, height=360, frames=180)
    source = tmp_path / "faststart.mp4"
    ffmpeg_run("-i", str(original), "-c", "copy", "-movflags", "+faststart", str(source))
    data = source.read_bytes()
    requests = []
    disconnected = threading.Event()
    from videoenhancer.service import video_links

    original_run = video_links.run_tool

    def mark_transfer(command, *args, **kwargs):
        if "--load-info-json" in command:
            command = [*command, "--add-header", "X-Transfer-Fixture: yes"]
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(video_links, "run_tool", mark_transfer)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            field = self.headers.get("Range", "")
            start = int(field.split("=")[1].split("-")[0]) if field else 0
            requests.append(start)
            self.send_response(206 if field else 200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(data) - start))
            if field:
                self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
            self.end_headers()
            try:
                if (
                    interruption == "disconnect"
                    and self.headers.get("X-Transfer-Fixture")
                    and not disconnected.is_set()
                ):
                    disconnected.set()
                    self.wfile.write(data[: len(data) // 2])
                    self.wfile.flush()
                    self.close_connection = True
                    return
                for offset in range(start, len(data), 8192):
                    self.wfile.write(data[offset : offset + 8192])
                    self.wfile.flush()
                    time.sleep(0.02)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        links = VideoLinks(tmp_path / "home", ToolManager(Path(installed)))
        settings = {**DEFAULTS, "backend": "cpu"}
        result = links.check(
            f"http://127.0.0.1:{server.server_port}/video.mp4",
            settings,
            lambda: False,
            lambda _: None,
            lambda _: None,
        )
        entry = result["raw_entries"][0]["info"]
        final = tmp_path / "resumed.mkv"
        job = dict(
            id=uuid.uuid4().hex,
            input={"path": str(final)},
            settings=settings,
            source=dict(
                request_url=result["url"],
                url=result["url"],
                id=str(entry["id"]),
                extractor=entry["extractor"],
                format=result["entries"][0]["selected"],
            ),
        )
        cancel = threading.Event()

        def progress(value):
            if interruption == "cancel" and value.get("bytes", 0) > 100000:
                cancel.set()

        with pytest.raises(InterruptedError if interruption == "cancel" else ValueError):
            links.download(job, cancel.is_set, lambda _: None, progress)
        assert not final.exists()
        partials = list(tmp_path.glob(".ve-*.part"))
        assert partials and partials[0].stat().st_size > 0
        before = len(requests)
        links.download(job, lambda: False, lambda _: None, lambda _: None)
        assert final.is_file()
        assert any(offset > 0 for offset in requests[before:])
        assert probe(final).frame_count == 180
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.skipif(
    os.name != "nt",
    reason="Real Windows FFmpeg TLS integration; portable transport policy has separate unit tests",
)
def test_https_header_redirect_to_http_is_refused(tmp_path, monkeypatch):
    openssl = shutil.which("openssl")
    if not openssl and os.name == "nt":
        candidate = (
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/usr/bin/openssl.exe"
        )
        if candidate.is_file():
            openssl = str(candidate)
    supplied_cert = os.environ.get("VE_LINK_TEST_TLS_CERT")
    supplied_key = os.environ.get("VE_LINK_TEST_TLS_KEY")
    if not openssl and not (supplied_cert and supplied_key):
        pytest.skip("Local TLS fixture requires OpenSSL")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    if supplied_cert and supplied_key:
        cert, key = Path(supplied_cert), Path(supplied_key)
    else:
        subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(cert),
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
            ],
            check=True,
            capture_output=True,
        )

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/video.mp4")
            self.end_headers()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    from videoenhancer.service import video_links

    original_run = video_links.run_tool

    def trusted_local_server(command, *args, **kwargs):
        # Trust only this ephemeral fixture CA; production checks remain unchanged.
        return original_run([*command[:-1], "-ca_file", str(cert), command[-1]], *args, **kwargs)

    monkeypatch.setattr(video_links, "run_tool", trusted_local_server)
    url = f"https://127.0.0.1:{server.server_port}/video.mp4"
    try:
        with pytest.raises(ValueError, match="without encryption") as failure:
            header_probe(url, {"url": url}, lambda: False, lambda _: None)
        assert str(failure.value) == ENCRYPTION_ERROR
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_unreadable_no_range_header_falls_back_then_download_is_probed(tmp_path, video_factory):
    installed = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not installed:
        pytest.skip("Explicit verified standalone link tools are required")
    original = video_factory(width=320, height=180, frames=60)
    data = original.read_bytes()
    assert data.rfind(b"moov") > data.find(b"mdat")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                if self.headers.get("Range"):
                    self.wfile.write(data[:1024])
                    self.wfile.flush()
                    time.sleep(25)
                    self.wfile.write(data[1024:])
                else:
                    self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        links = VideoLinks(tmp_path / "home", ToolManager(Path(installed)))
        settings = {**DEFAULTS, "backend": "cpu"}
        result = links.check(
            f"http://127.0.0.1:{server.server_port}/video.mp4",
            settings,
            lambda: False,
            lambda _: None,
            lambda _: None,
        )
        card = result["entries"][0]
        assert not card.get("error"), card
        assert card["unknown_size"]
        assert card["formats"][0]["estimate"] is None
        entry = result["raw_entries"][0]["info"]
        final = tmp_path / "fallback.mkv"
        job = dict(
            id=uuid.uuid4().hex,
            input={"path": str(final)},
            settings=settings,
            source=dict(
                request_url=result["url"],
                url=result["url"],
                id=str(entry["id"]),
                extractor=entry["extractor"],
                format=card["selected"],
            ),
        )
        links.download(job, lambda: False, lambda _: None, lambda _: None)
        media = probe(final)
        assert (media.width, media.height) == (320, 180)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("kind", ["direct", "hls", "dash"])
def test_direct_download_remux(tmp_path, video_factory, ffmpeg_run, kind, monkeypatch):
    installed = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not installed:
        pytest.skip("Explicit verified standalone link tools are required")
    original = video_factory(width=320, height=180, frames=60, audio=True)
    monkeypatch.chdir(original.parent)
    served = original
    if kind == "hls":
        served = original.parent / "video.m3u8"
        ffmpeg_run(
            "-i",
            str(original),
            "-c",
            "copy",
            "-hls_list_size",
            "0",
            "-hls_playlist_type",
            "vod",
            str(served),
        )
    elif kind == "dash":
        served = original.parent / "video.mpd"
        ffmpeg_run("-i", str(original), "-map", "0", "-c", "copy", "-f", "dash", str(served))
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(original.parent)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        home = tmp_path / "home"
        links = VideoLinks(home, ToolManager(Path(installed)))
        packets = []
        result = links.check(
            f"http://127.0.0.1:{server.server_port}/{served.name}",
            {**DEFAULTS, "backend": "torch"},
            lambda: False,
            lambda _: None,
            packets.append,
        )
        card = result["entries"][0]
        assert not card.get("error"), card
        assert not card["unknown_size"]
        assert card["formats"][0]["width"] == 320
        entry = result["raw_entries"][0]["info"]
        job_id = uuid.uuid4().hex
        final = tmp_path / "downloaded.mkv"
        job = dict(
            id=job_id,
            input={"path": str(final)},
            settings={**DEFAULTS, "backend": "torch"},
            source=dict(
                request_url=result["url"],
                url=result["url"],
                id=str(entry["id"]),
                extractor=entry["extractor"],
                format=card["selected"],
            ),
        )
        downloaded = links.download(job, lambda: False, lambda _: None, packets.append)
        assert downloaded == final
        media = probe(final)
        assert media.width == 320 and media.height == 180
        assert any(item.get("phase") == "Downloading" for item in packets)
        if kind in {"direct", "dash"}:

            def hashes(path):
                value = json.loads(
                    subprocess.check_output(
                        [
                            executable("ffprobe"),
                            "-v",
                            "error",
                            "-show_packets",
                            "-show_data_hash",
                            "sha256",
                            "-of",
                            "json",
                            str(path),
                        ]
                    )
                )
                return {
                    index: [
                        item["data_hash"]
                        for item in value["packets"]
                        if item["stream_index"] == index
                    ]
                    for index in (0, 1)
                }

            assert hashes(final) == hashes(original)
        if kind == "direct":
            engine = Engine(tmp_path / "engine-home")
            engine.video_links = VideoLinks(engine.home, ToolManager(Path(installed)))
            check_id = uuid.uuid4().hex
            engine.video_links.save_check(check_id, result)
            save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
            try:
                job = engine.link_jobs.queue(
                    dict(
                        check_id=check_id,
                        entry_key="0",
                        format_id=card["selected"],
                        settings=dict(
                            preset="fast", short_side=1080, fps="off", backend="cpu", codec="h264"
                        ),
                    )
                )
                assert job["state"] == "downloading"
                assert engine.queue()["jobs"][0]["source"]["url"] == result["url"]
                engine.link_jobs.recover()
                deadline = time.monotonic() + 30
                while (
                    engine.store.load(job["id"])["state"] == "downloading"
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.1)
                while engine.link_jobs.active and time.monotonic() < deadline:
                    time.sleep(0.1)
                finished = engine.store.load(job["id"])
                assert finished["state"] == "queued", finished.get("error")
                assert finished["source"]["downloaded_at"]
                assert Path(finished["input"]["path"]).is_file()
                assert engine.video_links.reusable(entry, engine.store)["job_id"] == job["id"]
                Path(finished["input"]["path"]).write_bytes(b"Changed synthetic download")
                assert engine.video_links.reusable(entry, engine.store) is None
            finally:
                engine.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
