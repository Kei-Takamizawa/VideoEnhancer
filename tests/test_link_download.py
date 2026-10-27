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
from types import SimpleNamespace

import pytest

from videoenhancer.config import executable
from videoenhancer.jobs.store import input_identity
from videoenhancer.media.probe import probe
from videoenhancer.service.engine import Engine
from videoenhancer.service.link_tools import ToolManager
from videoenhancer.service.settings import DEFAULTS, save_settings
from videoenhancer.service.video_links import ENCRYPTION_ERROR, VideoLinks, header_probe


def test_generic_reuse_local_hosts_replaced_duration_and_unchanged_file(tmp_path, ffmpeg_run):
    installed = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not installed:
        pytest.skip("Explicit verified standalone link tools are required")
    folders = [tmp_path / "host-a", tmp_path / "host-b"]
    for folder, frames in zip(folders, [30, 60], strict=True):
        folder.mkdir()
        ffmpeg_run(
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30",
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-movflags",
            "+faststart",
            str(folder / "video.mp4"),
        )
    servers = [
        http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder)),
        )
        for folder in folders
    ]
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in servers]
    for thread in threads:
        thread.start()
    links = VideoLinks(tmp_path / "home", ToolManager(Path(installed)))

    def check(server):
        return links.check(
            f"http://127.0.0.1:{server.server_port}/video.mp4",
            {**DEFAULTS, "backend": "cpu"},
            lambda: False,
            lambda _: None,
            lambda _: None,
        )

    try:
        first = check(servers[0])["raw_entries"][0]["info"]
        saved = tmp_path / "downloaded.mp4"
        shutil.copyfile(folders[0] / "video.mp4", saved)
        job = dict(
            id="saved",
            input=input_identity(saved),
            media=probe(saved).to_dict(),
            source=dict(
                extractor_key=first["extractor_key"],
                id=str(first["id"]),
                url=first["webpage_url"],
                timestamp=first.get("timestamp"),
            ),
        )
        store = SimpleNamespace(queue_jobs=lambda: [job])
        assert links.reusable(check(servers[0])["raw_entries"][0]["info"], store)
        assert not links.reusable(check(servers[1])["raw_entries"][0]["info"], store)
        shutil.copyfile(folders[1] / "video.mp4", folders[0] / "video.mp4")
        replaced = check(servers[0])["raw_entries"][0]["info"]
        # Isolate the duration check from the independent Last-Modified check.
        replaced["timestamp"] = first.get("timestamp")
        assert not links.reusable(replaced, store)
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)


def test_1440p_direct_file_is_refused_by_header_without_download(tmp_path, ffmpeg_run, monkeypatch):
    """Designer-approved two-frame CPU fixture; never submit it to a processing job."""
    installed = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not installed:
        pytest.skip("Explicit verified standalone link tools are required")
    fixture = tmp_path / "refusal-1440.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "color=size=2560x1440:rate=30",
        "-frames:v",
        "2",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-threads",
        "2",
        "-movflags",
        "+faststart",
        str(fixture),
    )
    requests = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            requests.append(
                dict(agent=self.headers.get("User-Agent"), range=self.headers.get("Range"))
            )
            super().do_GET()

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(tmp_path))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    engine = Engine(tmp_path / "home")
    engine.video_links = VideoLinks(engine.home, ToolManager(Path(installed)))
    commands = []
    from videoenhancer.service import video_links as module

    real_run = module.run_tool

    def run(command, *args, **kwargs):
        commands.append(command)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(module, "run_tool", run)
    folder = tmp_path / "downloads"
    folder.mkdir()
    save_settings(engine.home, {"video_download_folder": str(folder)})
    try:
        result = engine.video_links.check(
            f"http://127.0.0.1:{server.server_port}/{fixture.name}",
            {**DEFAULTS, "backend": "cpu"},
            lambda: False,
            lambda _: None,
            lambda _: None,
        )
        card = result["entries"][0]
        assert card["error"] == (
            "This video is larger than 1080p (short side 1440 px). "
            "VideoEnhancer processes videos up to 1080p."
        )
        assert card["selected"] is None
        assert not list(folder.iterdir())
        assert not engine.store.queue_jobs()
        assert len(commands) == 2
        assert "-J" in commands[0] and "--load-info-json" not in commands[0]
        assert Path(commands[1][0]).stem == "ffprobe" and "-show_streams" in commands[1]
        # ffprobe forwards the format's User-Agent, so identify its Range probe instead.
        assert any(r["range"] == "bytes=0-" for r in requests), requests
        print(
            json.dumps(
                dict(
                    refused=card["error"],
                    commands=[Path(c[0]).name for c in commands],
                    requests=requests,
                    downloads=0,
                    jobs=0,
                )
            )
        )
    finally:
        engine.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        fixture.unlink(missing_ok=True)
    assert not fixture.exists()


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
        checkpoint_bytes = 0

        def progress(value):
            nonlocal checkpoint_bytes
            if interruption != "cancel" or cancel.is_set():
                return
            if not 100000 < value.get("bytes", 0) < len(data):
                return
            # Progress counts bytes accepted by the tool, not flushed file bytes.
            # Python 3.14's larger write buffer can still hold that entire prefix.
            # Interrupt a known resumable prefix while the transfer is unfinished.
            for partial in tmp_path.glob(".ve-*.part"):
                try:
                    written = partial.stat().st_size
                except FileNotFoundError:
                    continue  # A completed file may have been renamed concurrently.
                if 0 < written < len(data):
                    checkpoint_bytes = written
                    print(f"Cancel checkpoint: received={value['bytes']}, persisted={written}")
                    cancel.set()
                    break

        with pytest.raises(InterruptedError if interruption == "cancel" else ValueError):
            links.download(job, cancel.is_set, lambda _: None, progress)
        assert not final.exists()
        partials = list(tmp_path.glob(".ve-*.part"))
        assert partials and partials[0].stat().st_size > 0
        partial_bytes = partials[0].read_bytes()
        assert len(partial_bytes) < len(data)
        assert partial_bytes == data[: len(partial_bytes)]
        if interruption == "cancel":
            assert 0 < checkpoint_bytes <= len(partial_bytes)
        before = len(requests)
        links.download(job, lambda: False, lambda _: None, lambda _: None)
        assert final.is_file()
        assert any(offset > 0 for offset in requests[before:])
        assert len(partial_bytes) in requests[before:]
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
        previous = dict(
            id="earlier",
            input=input_identity(final),
            media=media.to_dict(),
            source=dict(
                extractor_key=entry["extractor_key"], id=str(entry["id"]), url=entry["webpage_url"]
            ),
        )
        assert links.reusable(entry, SimpleNamespace(queue_jobs=lambda: [previous])) is None
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
                assert "timestamp" in finished["source"]
                assert finished["source"]["timestamp"] == entry.get("timestamp")
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
