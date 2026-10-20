"""Real verified yt-dlp against synthetic media on local servers only."""

import functools
import http.server
import os
import shutil
import ssl
import subprocess
import threading
import time
import uuid
from pathlib import Path

import psutil
import pytest

from videoenhancer.media.probe import probe
from videoenhancer.service.engine import Engine
from videoenhancer.service.link_tools import ToolManager
from videoenhancer.service.settings import save_settings
from videoenhancer.service.video_links import ENCRYPTION_ERROR, VideoLinks, header_probe


@pytest.fixture
def tls_server(tmp_path):
    folder = tmp_path / "tls"
    folder.mkdir()
    cert, key = folder / "cert.pem", folder / "key.pem"
    supplied_cert = os.environ.get("VE_LINK_TEST_TLS_CERT")
    supplied_key = os.environ.get("VE_LINK_TEST_TLS_KEY")
    if supplied_cert and supplied_key:
        shutil.copyfile(supplied_cert, cert)
        shutil.copyfile(supplied_key, key)
    else:
        openssl = shutil.which("openssl") or str(
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/usr/bin/openssl.exe"
        )
        if not Path(openssl).is_file():
            pytest.skip("Local TLS fixture requires OpenSSL or explicit fixture certificate/key")
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
                "/CN=127.0.0.1",
                "-addext",
                "subjectAltName=IP:127.0.0.1",
            ],
            check=True,
            capture_output=True,
        )
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder)),
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield folder, f"https://127.0.0.1:{server.server_port}", cert
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_b3_real_aes_hls_tls_never_claims_plain_http(tls_server, ffmpeg_run, monkeypatch):
    from videoenhancer.service import video_links

    folder, base, cert = tls_server
    (folder / "aes.key").write_bytes(bytes(range(16)))
    info = folder / "key-info.txt"
    info.write_text(f"{base}/aes.key\n{folder / 'aes.key'}\n")
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x180:rate=30",
        "-t",
        "2",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-g",
        "30",
        "-hls_time",
        "1",
        "-hls_list_size",
        "0",
        "-hls_key_info_file",
        str(info),
        str(folder / "encrypted.m3u8"),
    )
    original = video_links.run_tool
    monkeypatch.setattr(
        video_links,
        "run_tool",
        lambda command, *a, **k: original(
            [*command[:-1], "-ca_file", str(cert), command[-1]], *a, **k
        ),
    )
    result = header_probe(
        base + "/encrypted.m3u8", {"url": base + "/encrypted.m3u8"}, lambda: False, lambda _: None
    )
    assert result is None or result["width"] == 320


def test_b4_real_mpd_absolute_http_segments_refused(tls_server, tmp_path, monkeypatch):
    tools = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not tools:
        pytest.skip("Verified standalone tools must be explicitly supplied")
    folder, base, _ = tls_server
    (folder / "video.mpd").write_text("""<?xml version="1.0"?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static"
 mediaPresentationDuration="PT2S"
 minBufferTime="PT1S"
 profiles="urn:mpeg:dash:profile:isoff-on-demand:2011">
<Period>
<AdaptationSet mimeType="video/mp4" contentType="video">
<Representation id="video" codecs="avc1.64000d" width="320" height="180"
 frameRate="30" bandwidth="100000">
<SegmentList timescale="1" duration="1">
<Initialization sourceURL="http://127.0.0.1:9/init.mp4"/>
<SegmentURL media="http://127.0.0.1:9/one.m4s"/>
<SegmentURL media="http://127.0.0.1:9/two.m4s"/>
</SegmentList>
</Representation>
</AdaptationSet>
</Period>
</MPD>""")
    client = VideoLinks(tmp_path / "home", ToolManager(Path(tools)))
    original = client.arguments

    def trusted():
        args, env = original()
        return [*args, "--no-check-certificates"], env

    monkeypatch.setattr(client, "arguments", trusted)
    result = client.check(
        base + "/video.mpd",
        dict(backend="cpu", preset="fast", short_side=1080, fps="off", codec="hevc"),
        lambda: False,
        lambda _: None,
        lambda _: None,
    )
    assert result["entries"][0]["error"] == ENCRYPTION_ERROR
    entry = result["raw_entries"][0]["info"]
    with pytest.raises(ValueError, match="without encryption"):
        client.selected(result["url"], entry, str(entry["formats"][0]["format_id"]))
    engine = Engine(client.home)
    engine.video_links = client
    try:
        client.save_check("a" * 32, result)
        format_id = str(entry["formats"][0]["format_id"])
        with pytest.raises(ValueError, match="without encryption"):
            engine.link_jobs.queue(dict(check_id="a" * 32, entry_key="0", format_id=format_id))
        job = dict(
            id="b" * 32,
            input={"path": str(tmp_path / "downloads/refused.mkv")},
            source=dict(
                url=result["url"],
                request_url=result["url"],
                id=str(entry["id"]),
                extractor=entry.get("extractor") or "generic",
                extractor_key=entry.get("extractor_key") or "Generic",
                format=format_id,
            ),
            settings=dict(backend="cpu", preset="fast", fps="off", short_side="keep", codec="hevc"),
        )
        with pytest.raises(ValueError, match="without encryption"):
            client.download(job, lambda: False, lambda _: None, lambda _: None)
        assert not engine.store.list_jobs()
        assert not (tmp_path / "downloads").exists()
    finally:
        engine.close()


def test_b1_local_three_entry_playlist_rechecks_each_video_once(
    tmp_path, video_factory, monkeypatch
):
    from videoenhancer.service import video_links

    tools = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not tools:
        pytest.skip("Verified standalone tools must be explicitly supplied")
    source = video_factory(width=320, height=180, frames=60)
    for index in range(3):
        shutil.copyfile(source, source.parent / f"video{index}.mp4")
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(source.parent)),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    engine = Engine(tmp_path / "home")
    engine.video_links = VideoLinks(engine.home, ToolManager(Path(tools)))
    save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    commands = []
    original = video_links.run_tool

    def recorded(command, *a, **k):
        commands.append(command)
        return original(command, *a, **k)

    monkeypatch.setattr(video_links, "run_tool", recorded)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        settings = dict(backend="cpu", preset="fast", fps="off", short_side="keep", codec="hevc")
        urls = [f"{base}/video{index}.mp4" for index in range(3)]
        checked = [
            engine.video_links.check(url, settings, lambda: False, lambda _: None, lambda _: None)
            for url in urls
        ]
        # A playlist metadata fixture whose entries each have their own real local link.
        result = dict(
            url=base + "/playlist",
            entries=[
                dict(value["entries"][0], key=str(index)) for index, value in enumerate(checked)
            ],
            raw_entries=[
                dict(value["raw_entries"][0], key=str(index)) for index, value in enumerate(checked)
            ],
        )
        engine.video_links.save_check("a" * 32, result)
        jobs = [
            engine.link_jobs.queue(
                dict(
                    check_id="a" * 32,
                    entry_key=str(index),
                    format_id=checked[index]["entries"][0]["selected"],
                    settings=settings,
                )
            )
            for index in range(3)
        ]
        commands.clear()
        for job in jobs:
            engine.link_jobs.download(job["id"])
            assert engine.store.load(job["id"])["state"] == "queued"
        checks = [command for command in commands if "-J" in command]
        assert [command[-1] for command in checks] == urls
        assert all("--no-playlist" in command for command in checks)
        assert len([command for command in commands if "--load-info-json" in command]) == 3
    finally:
        engine.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_a3_real_remux_interruption_then_resume(tmp_path, ffmpeg_run):
    tools = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not tools:
        pytest.skip("Verified standalone tools must be explicitly supplied")
    source = tmp_path / "source"
    source.mkdir()
    video = source / "video.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1920x1080:rate=30",
        "-frames:v",
        "240",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-preset",
        "ultrafast",
        "-crf",
        "0",
        "-movflags",
        "+faststart",
        str(video),
        timeout=120,
    )
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(source)),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = VideoLinks(tmp_path / "home", ToolManager(Path(tools)))
    stopped = threading.Event()
    monitors = []
    job_id = uuid.uuid4().hex
    partial = tmp_path / f".ve-{job_id}.mkv"
    final = tmp_path / "download.mkv"
    try:
        url = f"http://127.0.0.1:{server.server_port}/video.mp4"
        settings = dict(backend="cpu", preset="fast", short_side="keep", fps="off", codec="hevc")
        checked = client.check(url, settings, lambda: False, lambda _: None, lambda _: None)
        entry = checked["raw_entries"][0]["info"]
        job = dict(
            id=job_id,
            source=dict(
                url=url,
                request_url=url,
                id=str(entry["id"]),
                extractor=entry.get("extractor") or "generic",
                extractor_key=entry.get("extractor_key") or "Generic",
                format=checked["entries"][0]["selected"],
            ),
            input={"path": str(final)},
            settings=settings,
        )

        def changed(child):
            if child is None:
                return

            def watch():
                while child.poll() is None and not stopped.is_set():
                    try:
                        if (
                            partial.is_file()
                            and 0 < partial.stat().st_size < video.stat().st_size * 0.98
                        ):
                            for process in psutil.Process(child.pid).children(recursive=True):
                                if process.name().lower() == "ffmpeg.exe":
                                    process.suspend()
                                    stopped.set()
                                    return
                    except (psutil.Error, OSError):
                        pass
                    time.sleep(0.001)

            monitor = threading.Thread(target=watch, daemon=True)
            monitors.append(monitor)
            monitor.start()

        with pytest.raises(InterruptedError):
            client.download(job, stopped.is_set, changed, lambda _: None)
        assert stopped.is_set(), "The fixture must interrupt an actual in-progress remux"
        assert partial.is_file() and partial.stat().st_size > 0
        for monitor in monitors:
            monitor.join(timeout=5)
        client.download(job, lambda: False, lambda _: None, lambda _: None)
        assert probe(final).frame_count == 240
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        video.unlink(missing_ok=True)
        final.unlink(missing_ok=True)
        for path in tmp_path.glob(f".ve-{job_id}.*"):
            path.unlink(missing_ok=True)


def test_b14_cancel_real_transfer_removes_only_owned_partial(
    tmp_path, video_factory, ffmpeg_run, monkeypatch
):
    tools = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not tools:
        pytest.skip("Verified standalone tools must be explicitly supplied")
    source = video_factory(width=640, height=360, frames=300)
    served = source.parent / "faststart.mp4"
    ffmpeg_run("-i", str(source), "-c", "copy", "-movflags", "+faststart", str(served))

    class Handler(http.server.SimpleHTTPRequestHandler):
        def copyfile(self, source, outputfile):
            try:
                while block := source.read(8192):
                    outputfile.write(block)
                    outputfile.flush()
                    time.sleep(0.03)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(source.parent))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    engine = Engine(tmp_path / "home")
    engine.video_links = VideoLinks(engine.home, ToolManager(Path(tools)))
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    folder = tmp_path / "downloads"
    save_settings(engine.home, {"video_download_folder": str(folder)})
    worker = None
    try:
        result = engine.video_links.check(
            f"http://127.0.0.1:{server.server_port}/faststart.mp4",
            dict(backend="cpu", preset="fast", fps="off", short_side="keep", codec="hevc"),
            lambda: False,
            lambda _: None,
            lambda _: None,
        )
        engine.video_links.save_check("a" * 32, result)
        job = engine.link_jobs.queue(
            dict(
                check_id="a" * 32,
                entry_key="0",
                format_id=result["entries"][0]["selected"],
                settings=dict(
                    backend="cpu", preset="fast", fps="off", short_side="keep", codec="hevc"
                ),
            )
        )
        unrelated = folder / f".ve-{job['id']}other.mp4.part"
        unrelated.write_bytes(b"keep unrelated file")
        worker = threading.Thread(target=engine.link_jobs.download, args=(job["id"],))
        engine.link_jobs.active[job["id"]] = worker
        worker.start()
        deadline = time.monotonic() + 30
        while not any(path.stat().st_size > 0 for path in folder.glob(f".ve-{job['id']}.*.part")):
            assert worker.is_alive() and time.monotonic() < deadline
            time.sleep(0.01)
        engine.cancel_job(job["id"])
        worker.join(timeout=20)
        assert not worker.is_alive()
        assert not list(folder.glob(f".ve-{job['id']}.*"))
        assert unrelated.read_bytes() == b"keep unrelated file"
    finally:
        engine.close()
        if worker:
            worker.join(timeout=20)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("failures", [1, 100])
def test_a2_real_hls_middle_fragment_retries(tmp_path, ffmpeg_run, monkeypatch, failures):
    tools = os.environ.get("VE_LINK_TEST_TOOLS_HOME")
    if not tools:
        pytest.skip("Verified standalone tools must be explicitly supplied")
    source = tmp_path / "source"
    source.mkdir()
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x180:rate=30",
        "-t",
        "6",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-g",
        "30",
        "-sc_threshold",
        "0",
        "-hls_time",
        "1",
        "-hls_list_size",
        "0",
        str(source / "index.m3u8"),
    )
    missing = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if (
                self.path.endswith("index2.ts")
                and not self.headers.get("User-Agent", "").startswith("Lavf")
                and len(missing) < failures
            ):
                missing.append(self.path)
                self.send_error(500, "Synthetic middle fragment failure")
                return
            super().do_GET()

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(source))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    engine.video_links = VideoLinks(engine.home, ToolManager(Path(tools)))
    save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
    try:
        result = engine.video_links.check(
            f"http://127.0.0.1:{server.server_port}/index.m3u8",
            {"backend": "cpu", "preset": "fast", "short_side": 1080, "fps": "off", "codec": "hevc"},
            lambda: False,
            lambda _: None,
            lambda _: None,
        )
        engine.video_links.save_check("a" * 32, result)
        job = engine.link_jobs.queue(
            dict(
                check_id="a" * 32,
                entry_key="0",
                format_id=result["entries"][0]["selected"],
                settings={"backend": "cpu", "preset": "fast", "fps": "off", "short_side": "keep"},
            )
        )
        engine.link_jobs.download(job["id"])
        final = engine.store.load(job["id"])
        if failures == 1:
            assert final["state"] == "queued", final.get("error")
            assert probe(Path(final["input"]["path"])).frame_count == 180
            assert len(missing) == 1
        else:
            assert final["state"] == "failed"
            assert final["download"]["retries"] == 3
            assert len(missing) == 4
            assert "fragment" in final["error"].lower() or "500" in final["error"]
        assert len(engine.queue()["jobs"]) == 1
    finally:
        engine.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
