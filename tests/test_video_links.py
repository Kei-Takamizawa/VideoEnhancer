"""Link metadata policy, bounded probes and cancellable child processes."""

import json
import sys
import time

import psutil
import pytest

from videoenhancer.service.link_tools import ToolManager
from videoenhancer.service.video_links import (
    ENCRYPTION_ERROR,
    VideoLinks,
    best_format,
    format_reason,
    header_probe,
    require_encrypted_format,
    run_tool,
    safe_filename,
    video_url,
)


def test_selected_format_cannot_bypass_a_probe_transport_refusal(tmp_path):
    links = VideoLinks(tmp_path, ToolManager(tmp_path))
    entry = {
        "formats": [
            dict(
                format_id="video",
                url="https://site.test/video",
                width=320,
                height=180,
                vcodec="h264",
                transport_error=ENCRYPTION_ERROR,
            )
        ]
    }
    with pytest.raises(ValueError, match="without encryption"):
        links.selected("https://site.test/watch", entry, "video")


def test_http_best_audio_is_refused_in_the_checked_card(tmp_path, monkeypatch):
    links = VideoLinks(tmp_path, ToolManager(tmp_path))
    monkeypatch.setattr(links, "arguments", lambda: (["verified-test-fixture"], {}))
    entry = dict(
        id="fixture",
        title="Synthetic",
        duration=2,
        formats=[
            dict(
                format_id="video",
                url="https://site.test/video",
                width=320,
                height=180,
                fps=30,
                vcodec="h264",
                acodec="none",
            ),
            dict(format_id="audio", url="http://site.test/audio", vcodec="none", acodec="opus"),
        ],
    )
    monkeypatch.setattr(
        "videoenhancer.service.video_links.run_tool", lambda *a, **k: (json.dumps(entry), "")
    )
    checked = links.check(
        "https://site.test/watch",
        {"short_side": 1080},
        lambda: False,
        lambda _: None,
        lambda _: None,
    )
    card = checked["entries"][0]
    assert card["selected"] is None
    assert card["error"] == ENCRYPTION_ERROR
    assert card["formats"][0]["disabled"] == ENCRYPTION_ERROR


@pytest.mark.parametrize(
    "url",
    [
        "file:///secret",
        "ftp://site.test/a",
        "https://user:password@site.test/a",
        "https://site.test:99999/a",
        "http://site.test/\r\nheader",
    ],
)
def test_reject_non_http_and_credential_links(url):
    with pytest.raises(ValueError):
        video_url(url)


@pytest.mark.parametrize("key", ["url", "manifest_url", "fragment_base_url"])
def test_https_metadata_downgrade_is_refused(key):
    with pytest.raises(ValueError, match="without encryption"):
        require_encrypted_format("https://site.test/watch", {key: "http://site.test/video"})
    require_encrypted_format("http://site.test/watch", {key: "http://site.test/video"})


@pytest.mark.parametrize("portrait", [False, True])
@pytest.mark.parametrize("output", [1080, "keep", 1440])
def test_default_quality_uses_short_side_fps_bitrate_and_sdr(portrait, output):
    formats = []
    for size, fps, bitrate, dynamic in (
        (720, 60, 5000, "SDR"),
        (1080, 30, 5000, "SDR"),
        (1080, 60, 4000, "SDR"),
        (1080, 60, 6000, "SDR"),
        (1080, 60, 9000, "HDR10"),
        (1440, 60, 20000, "SDR"),
    ):
        width, height = (size, size * 16 // 9) if portrait else (size * 16 // 9, size)
        formats.append(
            dict(width=width, height=height, fps=fps, tbr=bitrate, dynamic_range=dynamic)
        )
    chosen = best_format(formats, output)
    assert chosen is not None
    assert min(chosen["width"], chosen["height"]) == 1080
    assert chosen["fps"] == 60 and chosen["tbr"] == 6000
    assert format_reason(formats[-2]) == "HDR is not supported yet"


def test_header_probe_uses_required_limits_headers_and_rotated_dimensions(monkeypatch):
    calls = []
    raw = dict(
        streams=[
            dict(
                codec_type="video",
                width=1920,
                height=1080,
                avg_frame_rate="30000/1001",
                duration="10",
                codec_name="h264",
                side_data_list=[dict(rotation=90)],
                color_transfer="bt709",
            ),
            dict(codec_type="audio", codec_name="aac"),
        ]
    )

    def capture(command, cancelled, process_changed, **kwargs):
        calls.append((command, kwargs))
        return json.dumps(raw), ""

    monkeypatch.setattr("videoenhancer.service.video_links.run_tool", capture)
    item = dict(
        url="https://site.test/video.mp4", http_headers={"Referer": "https://site.test/watch"}
    )
    result = header_probe("https://site.test/watch", item, lambda: False, lambda _: None)
    assert result and (result["width"], result["height"]) == (1080, 1920)
    args, options = calls[0]
    assert args[args.index("-protocol_whitelist") + 1] == "https,tls,tcp"
    assert args[args.index("-rw_timeout") + 1] == "10000000"
    assert args[args.index("-probesize") + 1] == "1000000"
    assert args[args.index("-analyzeduration") + 1] == "1000000"
    assert args[args.index("-headers") + 1] == "Referer: https://site.test/watch\r\n"
    assert options["timeout"] == 20
    item["http_headers"] = {"Referer": "evil\r\nInjected: true"}
    with pytest.raises(ValueError, match="invalid video request headers"):
        header_probe("https://site.test/watch", item, lambda: False, lambda _: None)


def test_probe_timeout_falls_back_but_http_whitelist_failure_refuses(monkeypatch):
    def timeout(*args, **kwargs):
        raise TimeoutError("bounded")

    monkeypatch.setattr("videoenhancer.service.video_links.run_tool", timeout)
    assert (
        header_probe(
            "https://site.test/a", dict(url="https://site.test/a"), lambda: False, lambda _: None
        )
        is None
    )

    def refusal(*args, **kwargs):
        raise ValueError("Protocol 'http' not on whitelist 'https,tls,tcp'!")

    monkeypatch.setattr("videoenhancer.service.video_links.run_tool", refusal)
    with pytest.raises(ValueError, match="without encryption") as failure:
        header_probe(
            "https://site.test/a", dict(url="https://site.test/a"), lambda: False, lambda _: None
        )
    assert str(failure.value) == ENCRYPTION_ERROR


def test_filenames_are_safe_windows_names_and_preserve_video_id():
    result = safe_filename('CON/<>:"|?*' + "😀" * 200, "id/unsafe")
    assert not any(char in result for char in '<>:"/\\|?*')
    assert result.endswith("[id_unsafe]")
    assert len(result.split(" [")[0].encode("utf-16-le")) <= 240
    assert safe_filename("CON", "NUL").startswith("_CON")


@pytest.mark.parametrize("cancel", [True, False])
def test_process_tree_is_killed_on_cancel_and_timeout(tmp_path, cancel):
    child_file = tmp_path / "child.pid"
    script = tmp_path / "parent.py"
    script.write_text(
        "import subprocess,sys,time,pathlib\n"
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'])\n"
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid))\ntime.sleep(120)\n",
        encoding="utf-8",
    )
    started = time.monotonic()

    def cancelled():
        return cancel and child_file.exists()

    with pytest.raises(InterruptedError if cancel else TimeoutError):
        run_tool(
            [sys.executable, str(script), str(child_file)], cancelled, lambda _: None, timeout=2
        )
    assert time.monotonic() - started < 8
    if child_file.exists():
        pid = int(child_file.read_text())
        for _ in range(50):
            if not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                break
            time.sleep(0.05)
        assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


def test_process_diagnostics_survive_fast_failure():
    with pytest.raises(ValueError, match="fixture failure"):
        run_tool(
            [sys.executable, "-c", 'import sys;sys.stderr.write("fixture failure");sys.exit(2)'],
            lambda: False,
            lambda _: None,
        )


def test_manifest_probe_keeps_video_only_representation_and_separate_audio(tmp_path, monkeypatch):
    links = VideoLinks(tmp_path, ToolManager(tmp_path))
    monkeypatch.setattr(links, "arguments", lambda: (["synthetic-tool"], {}))
    monkeypatch.setattr(links, "estimate", lambda *args: None)
    entry = dict(
        id="synthetic",
        formats=[
            dict(format_id="v", vcodec="h264", acodec="none", url="https://site.test/video.mpd"),
            dict(format_id="a", vcodec="none", acodec="aac", url="https://site.test/audio.mpd"),
        ],
    )
    monkeypatch.setattr(
        "videoenhancer.service.video_links.run_tool", lambda *a, **k: (json.dumps(entry), "")
    )
    monkeypatch.setattr(
        "videoenhancer.service.video_links.header_probe",
        lambda *a, **k: dict(width=320, height=180, duration=2, vcodec="h264", acodec="aac"),
    )
    checked = links.check(
        "https://site.test/video.mpd",
        {"short_side": 1080},
        lambda: False,
        lambda _: None,
        lambda _: None,
    )
    enriched = checked["raw_entries"][0]["info"]
    video, audio = links.selected(checked["url"], enriched, "v")
    assert video["acodec"] == "none"
    assert audio is not None and audio["format_id"] == "a"
