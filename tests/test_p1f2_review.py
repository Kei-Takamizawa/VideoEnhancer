"""Regression cases for the designer's P1f review, using isolated local metadata."""

import json
from types import SimpleNamespace

import pytest

from videoenhancer.service import video_links as links
from videoenhancer.service.engine import Engine
from videoenhancer.service.link_tools import ToolManager
from videoenhancer.service.settings import DEFAULTS, save_settings


@pytest.fixture
def download_case(tmp_path, monkeypatch):
    client = links.VideoLinks(tmp_path / "home", ToolManager(tmp_path))
    video = dict(
        format_id="v",
        url="http://localhost/v.mp4",
        width=320,
        height=180,
        fps=30,
        duration=2,
        vcodec="h264",
        ext="mp4",
        downloader_options={"http_chunk_size": 1048576, "evil": "ignored"},
    )
    entry = dict(id="v", extractor="generic", extractor_key="Generic", duration=2, formats=[video])
    calls = []

    def check(url, *a, **k):
        calls.append((url, k))
        return dict(url=url, raw_entries=[{"info": entry}])

    monkeypatch.setattr(client, "check", check)
    monkeypatch.setattr(client, "arguments", lambda: (["fixture"], {}))
    job = dict(
        id="a" * 32,
        source=dict(
            request_url="http://localhost/list",
            url="http://localhost/entry",
            id="v",
            extractor="generic",
            extractor_key="Generic",
            format="v",
        ),
        input={"path": str(tmp_path / "video.mkv")},
        settings=DEFAULTS,
    )
    commands = []
    temporary = tmp_path / (".ve-" + job["id"] + ".mkv")

    def run(command, *a, **k):
        commands.append(command)
        temporary.write_bytes(b"complete")
        return "", ""

    monkeypatch.setattr(links, "run_tool", run)
    monkeypatch.setattr(
        "videoenhancer.media.probe.probe",
        lambda *a, **k: SimpleNamespace(duration=2, to_dict=lambda: {"duration": 2}),
    )
    return client, job, calls, commands, temporary


def test_b1_entry_rechecked_once(download_case):
    client, job, calls, _, _ = download_case
    client.download(job, lambda: False, lambda _: None, lambda _: None)
    assert calls == [(job["source"]["url"], {"single": True})]


def test_a2_fragment_abort_flag(download_case):
    client, job, _, commands, _ = download_case
    client.download(job, lambda: False, lambda _: None, lambda _: None)
    assert "--abort-on-unavailable-fragments" in commands[0]


def test_a3_partial_remux_removed_before_attempt(download_case, monkeypatch):
    client, job, _, _, temporary = download_case
    temporary.write_bytes(b"partial")

    def run(*a, **k):
        assert not temporary.exists()
        temporary.write_bytes(b"complete")
        return "", ""

    monkeypatch.setattr(links, "run_tool", run)
    client.download(job, lambda: False, lambda _: None, lambda _: None)


def test_b10_preserves_only_positive_chunk_size(download_case):
    client, job, _, _, _ = download_case
    client.download(job, lambda: False, lambda _: None, lambda _: None)
    info = json.loads((client.home / "jobs" / job["id"] / "download-info.json").read_text())
    assert info["formats"][0]["downloader_options"] == {"http_chunk_size": 1048576}


@pytest.mark.parametrize("chunk", [0, -1, True, 1.5, "1048576"])
def test_b10_rejects_non_positive_integer_chunk_sizes(download_case, chunk):
    client, job, _, _, _ = download_case
    client.check("http://localhost/entry")["raw_entries"][0]["info"]["formats"][0][
        "downloader_options"
    ] = {"http_chunk_size": chunk}
    client.download(job, lambda: False, lambda _: None, lambda _: None)
    info = json.loads((client.home / "jobs" / job["id"] / "download-info.json").read_text())
    assert "downloader_options" not in info["formats"][0]


def test_b7_all_formats_with_default_interpolation_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    video = dict(
        format_id="v",
        url="http://localhost/v",
        width=320,
        height=180,
        fps=30,
        duration=2,
        vcodec="h264",
    )
    monkeypatch.setattr(
        engine.video_links, "metadata", lambda *a: (video["url"], dict(id="v", formats=[video]))
    )
    try:
        result = engine.dispatch(
            "POST",
            ["links", "estimate"],
            dict(
                check_id="x",
                entry_key="0",
                format_id="v",
                all_formats=True,
                settings={"backend": "cpu", "fps": "2x"},
            ),
        )
        assert result["formats"]["v"]["seconds"] > 0
    finally:
        engine.close()


def test_a2_incomplete_duration_is_kept_and_refused(download_case, monkeypatch):
    client, job, _, _, temporary = download_case
    monkeypatch.setattr(
        "videoenhancer.media.probe.probe",
        lambda *a, **k: SimpleNamespace(to_dict=lambda: {"duration": 0.2}),
    )
    with pytest.raises(
        ValueError, match=r"The download is incomplete \(0.2 s of 2 s\). Retry the download."
    ):
        client.download(job, lambda: False, lambda _: None, lambda _: None)
    assert temporary.is_file()


def test_b13_redirect_to_loopback_refused_before_following(tmp_path, monkeypatch):
    client = links.VideoLinks(tmp_path, ToolManager(tmp_path))
    monkeypatch.setattr(
        client,
        "metadata",
        lambda *a: ("https://example.test/video", {"thumbnail": "https://example.test/image"}),
    )
    monkeypatch.setattr(
        links.socket,
        "getaddrinfo",
        lambda host, *a, **k: [
            (2, 1, 6, "", ("127.0.0.1" if host == "127.0.0.1" else "93.184.216.34", 443))
        ],
    )

    def opener(*handlers):
        handler = next(
            h for h in handlers if isinstance(h, links.urllib.request.HTTPRedirectHandler)
        )

        def open_request(*a, **k):
            handler.redirect_request(
                links.urllib.request.Request("https://example.test/image"),
                None,
                302,
                "Found",
                {},
                "https://127.0.0.1/image",
            )
            pytest.fail("Private redirect was followed")

        return SimpleNamespace(open=open_request)

    monkeypatch.setattr(links.urllib.request, "build_opener", opener)
    with pytest.raises(ValueError, match="not public"):
        client.thumbnail("check", "entry")


def test_a1_legacy_placeholders_and_bad_record_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
    video = dict(format_id="v", url="http://localhost/v", vcodec="h264")
    monkeypatch.setattr(
        engine.video_links, "metadata", lambda *a: (video["url"], dict(id="v", formats=[video]))
    )
    errors = []
    monkeypatch.setattr(engine, "_error", lambda *a: errors.append(a))
    try:
        value = dict(check_id="x", entry_key="0", format_id="v", settings={"backend": "cpu"})
        legacy = engine.link_jobs.queue(value)
        engine.store.patch_existing(
            legacy["id"],
            {
                "state": "failed",
                "finished_at": "2026-10-19T12:34:56+00:00",
                "media": dict(
                    width=0,
                    height=0,
                    display_width=0,
                    display_height=0,
                    cfr_fps="0",
                    duration=0,
                    frame_count=0,
                ),
            },
        )
        broken = engine.link_jobs.queue(value)
        engine.store.patch_existing(
            broken["id"], {"state": "failed", "source": None, "media": {"width": -1}}
        )
        for _ in range(2):
            rows = engine.queue()["jobs"]
            assert len(rows) == 2
            old = next(row for row in rows if row["id"] == legacy["id"])
            assert not old.get("record_error"), old
            assert old["finished_at"] == "2026-10-19T12:34:56+00:00"
            assert old["media"]["display_width"] is None
            bad = next(row for row in rows if row["id"] == broken["id"])
            assert bad["record_error"]
            assert bad["error"].startswith("This job's record can't be shown:")
        assert len(errors) == 1
    finally:
        engine.close()


@pytest.mark.parametrize("target", ["http://127.0.0.1/image", "https://192.168.1.1/image"])
def test_b13_private_thumbnail_never_fetched(tmp_path, monkeypatch, target):
    client = links.VideoLinks(tmp_path, ToolManager(tmp_path))
    monkeypatch.setattr(
        client, "metadata", lambda *a: ("http://site.test/video", {"thumbnail": target})
    )
    opened = []

    def opener(*a):
        opened.append(True)
        raise RuntimeError("Network must not be reached")

    monkeypatch.setattr(links.urllib.request, "build_opener", opener)
    with pytest.raises(ValueError):
        client.thumbnail("check", "entry")
    assert not opened


def test_b7_estimates_do_not_reprobe_hardware(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "videoenhancer.logging.environment_info",
        lambda: calls.append(True) or {"gpu": "Synthetic", "driver": "1"},
    )
    client = links.VideoLinks(tmp_path, ToolManager(tmp_path))
    video = dict(width=320, height=180, fps=30, duration=2)
    for _ in range(20):
        if hasattr(client, "estimate"):
            client.estimate(video, {**DEFAULTS, "backend": "cuda"})
        else:
            links.format_estimate(video, {**DEFAULTS, "backend": "cuda"}, tmp_path)
    assert len(calls) <= 2
    warmed = len(calls)
    for _ in range(20):
        client.estimate(video, {**DEFAULTS, "backend": "cuda"})
    assert len(calls) == warmed


def test_b14_cancel_removes_only_own_partial_files(tmp_path, monkeypatch):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    folder = tmp_path / "downloads"
    save_settings(engine.home, {"video_download_folder": str(folder)})
    video = dict(
        format_id="v",
        url="http://localhost/v",
        width=320,
        height=180,
        fps=30,
        duration=2,
        vcodec="h264",
    )
    monkeypatch.setattr(
        engine.video_links, "metadata", lambda *a: (video["url"], dict(id="v", formats=[video]))
    )
    try:
        job = engine.link_jobs.queue(
            dict(check_id="x", entry_key="0", format_id="v", settings={"backend": "cpu"})
        )
        own = folder / f".ve-{job['id']}.mp4.part"
        other = folder / f".ve-{job['id']}other.mp4.part"
        own.write_bytes(b"partial")
        other.write_bytes(b"keep")
        engine.cancel_job(job["id"])
        assert not own.exists()
        assert other.read_bytes() == b"keep"
    finally:
        engine.close()


def test_b6_queue_checks_working_space(tmp_path, monkeypatch):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
    video = dict(
        format_id="v",
        url="http://localhost/v",
        width=320,
        height=180,
        fps=30,
        duration=2,
        vcodec="h264",
        filesize=1000000,
    )
    monkeypatch.setattr(
        engine.video_links, "metadata", lambda *a: (video["url"], dict(id="v", formats=[video]))
    )
    calls = []

    def insufficient(*a, **k):
        calls.append(True)
        raise OSError("Insufficient disk space")

    monkeypatch.setattr("videoenhancer.jobs.store.require_working_space", insufficient)
    try:
        with pytest.raises(OSError, match="Insufficient disk space"):
            engine.link_jobs.queue(
                dict(check_id="x", entry_key="0", format_id="v", settings={"backend": "cpu"})
            )
        assert calls
        assert not engine.store.list_jobs()
    finally:
        engine.close()


@pytest.mark.parametrize("protocol", ["crypto", "httpproxy"])
def test_b3_non_http_whitelist_failure_falls_back(monkeypatch, protocol):
    def fail(*a, **k):
        raise ValueError(f"Protocol '{protocol}' not on whitelist 'https,tls,tcp'")

    monkeypatch.setattr(links, "run_tool", fail)
    assert (
        links.header_probe(
            "https://site.test/v", {"url": "https://site.test/v"}, lambda: False, lambda _: None
        )
        is None
    )


def test_b4_http_fragments_refused():
    with pytest.raises(ValueError, match="without encryption"):
        links.require_encrypted_format(
            "https://site.test/watch",
            {"url": "https://site.test/v", "fragments": [{"url": "http://site.test/1"}]},
        )


def test_b13_dns_rebinding_is_refused_at_connect(monkeypatch):
    monkeypatch.setattr(
        links.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))]
    )
    monkeypatch.setattr(
        links.socket, "socket", lambda *a: pytest.fail("Private connection attempted")
    )
    with pytest.raises(ValueError, match="not public"):
        links.public_socket(("public-then-rebound.test", 443), timeout=1)


@pytest.mark.parametrize("kind", ["media", "json"])
def test_a1_bad_projection_or_json_keeps_other_rows_and_safe_removal(tmp_path, monkeypatch, kind):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
    video = dict(format_id="v", url="http://localhost/v", vcodec="h264")
    monkeypatch.setattr(
        engine.video_links, "metadata", lambda *a: (video["url"], dict(id="v", formats=[video]))
    )
    errors = []
    monkeypatch.setattr(engine, "_error", lambda *a: errors.append(a))
    try:
        value = dict(check_id="x", entry_key="0", format_id="v", settings={"backend": "cpu"})
        good = engine.link_jobs.queue(value)
        bad = engine.link_jobs.queue(value)
        directory = engine.store.job_dir(bad["id"])
        kept = directory / "unknown-data.bin"
        kept.write_bytes(b"keep unknown data")
        if kind == "json":
            (directory / "manifest.json").write_text("{torn record")
            with pytest.raises(ValueError):
                engine.store.list_jobs()  # Startup/core loading policy stays strict.
        else:
            engine.store.patch_existing(
                bad["id"], {"state": "failed", "media": None, "source": None}
            )
        for _ in range(2):
            rows = engine.queue()["jobs"]
            assert {row["id"] for row in rows} == {good["id"], bad["id"]}
            assert next(row for row in rows if row["id"] == bad["id"])["record_error"]
            assert len(engine.store.event_state()[0]) == 2
        assert len(errors) == 1
        if kind == "json":
            with pytest.raises(ValueError):
                engine.remove(bad["id"])  # Direct deletion cannot bypass the History Undo workflow.
            assert kept.read_bytes() == b"keep unknown data"
        else:
            engine.remove(bad["id"])
            assert [row["id"] for row in engine.queue()["jobs"]] == [good["id"]]
    finally:
        engine.close()


def test_b6_one_margin_for_same_drive_download_work_and_output(tmp_path):
    from videoenhancer.jobs.store import require_working_space

    home, output, downloads = [tmp_path / name for name in ["home", "output", "downloads"]]
    for folder in [home, output, downloads]:
        folder.mkdir()
    with pytest.raises(OSError, match="Insufficient disk space"):
        require_working_space(
            home, output, 1000, 4399, download_folder=downloads, download_bytes=500
        )
    require_working_space(home, output, 1000, 4400, download_folder=downloads, download_bytes=500)


def test_b8_cache_is_inside_engine_home(tmp_path, monkeypatch):
    tools = SimpleNamespace(executable=lambda name: tmp_path / name)
    args, _ = links.VideoLinks(tmp_path, tools).arguments()
    assert args[args.index("--cache-dir") + 1] == str(tmp_path / "tools/yt-dlp/cache")


@pytest.mark.parametrize(
    "entry",
    [{"_type": "playlist", "title": "Nested", "entries": []}, {"id": "missing", "title": "No URL"}],
)
def test_b2_nested_or_missing_url_gets_plain_reason(tmp_path, monkeypatch, entry):
    client = links.VideoLinks(tmp_path, ToolManager(tmp_path))
    monkeypatch.setattr(client, "arguments", lambda: (["fixture"], {}))
    monkeypatch.setattr(
        links,
        "run_tool",
        lambda *a, **k: (json.dumps({"_type": "playlist", "entries": [entry]}), ""),
    )
    result = client.check(
        "https://site.test/list", DEFAULTS, lambda: False, lambda _: None, lambda _: None
    )
    assert result["entries"][0]["error"]
    if entry.get("_type") == "playlist":
        assert "list of lists" in result["entries"][0]["error"]


@pytest.mark.parametrize("state", ["downloading", "preparing", "failed", "cancelled"])
@pytest.mark.parametrize("missing", ["fps", "width"])
def test_a1_unknown_media_snapshots(tmp_path, monkeypatch, state, missing):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    video = dict(
        format_id="v",
        url="http://localhost/v",
        width=320,
        height=180,
        fps=30,
        duration=2,
        vcodec="h264",
    )
    video.pop(missing)
    entry = dict(id="v", formats=[video])
    monkeypatch.setattr(engine.video_links, "metadata", lambda *a: (video["url"], entry))
    save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
    try:
        job = engine.link_jobs.queue(
            dict(check_id="x", entry_key="0", format_id="v", settings={"backend": "cpu"})
        )
        assert job["media"]["cfr_fps" if missing == "fps" else "width"] is None
        engine.store.patch_existing(job["id"], {"state": state, "error": "Synthetic failure"})
        row = engine.queue()["jobs"][0]
        assert row["state"] == state
        assert row["error"] == "Synthetic failure"
        assert row["estimate_after_download"]
    finally:
        engine.close()


@pytest.mark.parametrize("outcome", ["undo", "expire", "restart"])
@pytest.mark.parametrize("raw", [b"{torn record", b"{invalid utf8\xff"])
def test_a1_unreadable_history_folder_undo_and_cleanup(tmp_path, monkeypatch, outcome, raw):
    import hashlib
    import time

    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    directory = engine.store.job_dir("a" * 32)
    directory.mkdir()
    (directory / "manifest.json").write_bytes(raw)
    (directory / "nested").mkdir()
    (directory / "nested" / "data.bin").write_bytes(bytes(range(256)))
    outside = tmp_path / "video.mp4"
    outside.write_bytes(b"outside stays")

    def inventory(folder):
        return {
            str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*")
            if p.is_file()
        }

    try:
        row = engine.queue()["jobs"][0]
        assert row["unreadable_record"]
        details = engine.dispatch("GET", ["queue", directory.name, "details"], {})
        assert "Parse error:" in details["text"]
        assert str(directory / "manifest.json") in details["text"]
        with pytest.raises(ValueError, match="videos stay"):
            engine.history_action("remove", {"ids": [directory.name], "original": True})
        before = inventory(directory)
        result = engine.history_action("remove", {"ids": [directory.name]})
        assert result["undo_seconds"] == 10
        staged = engine.store.jobs_dir / ".removing" / directory.name
        assert not directory.exists()
        assert inventory(staged) == before
        if outcome == "undo":
            engine.history_action("pause-undo", {"ids": [directory.name], "paused": True})
            engine.history_action("pause-undo", {"ids": [directory.name], "paused": False})
            engine.history_action("undo", {"ids": [directory.name]})
            assert inventory(directory) == before
            assert not staged.exists()
        elif outcome == "expire":
            deadline = time.monotonic() + 13
            while staged.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert not staged.exists()
        else:
            engine.close()
            engine = Engine(tmp_path / "home")
            engine._recover()  # The first operation in Engine.start().
            assert not staged.exists()
        assert outside.read_bytes() == b"outside stays"
    finally:
        engine.close()
