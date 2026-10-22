"""Owner-check regressions, using only isolated synthetic state."""

import ast
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import save_settings


def test_a3_post_download_real_dimensions_still_refuse(tmp_path, video_factory):
    from videoenhancer.jobs.store import add_job

    with pytest.raises(OSError, match="Insufficient disk space"):
        add_job(
            video_factory(frames=2),
            dict(backend="cpu", preset="fast", fps="off", short_side=1080, codec="h264"),
            tmp_path / "output.mp4",
            tmp_path / "home",
            disk_free=0,
        )


def test_a1_japanese_above_1080_refusal(tmp_path, ffmpeg_run, monkeypatch):
    import locale

    from videoenhancer.jobs.checks import source_warning
    from videoenhancer.media.probe import probe

    source = tmp_path / "日本語・大きい動画.mp4"
    ffmpeg_run(
        "-f",
        "lavfi",
        "-i",
        "color=s=2200x1100:r=1",
        "-frames:v",
        "1",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-threads",
        "2",
        "-metadata",
        "title=日本語",
        str(source),
    )
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1252")
    assert "larger than 1080p" in source_warning(probe(source).to_dict())


def test_a1_japanese_tool_output_and_history(tmp_path, video_factory, ffmpeg_run, monkeypatch):
    import locale

    from videoenhancer.jobs.store import JobStore, add_job
    from videoenhancer.logging import get_logger
    from videoenhancer.media.mux import assemble
    from videoenhancer.media.probe import probe
    from videoenhancer.pipeline.runner import process_segment

    folder = tmp_path / "日本語フォルダ"
    folder.mkdir()
    source = folder / "サンプル「夏」の動画.mp4"
    ffmpeg_run(
        "-i",
        str(video_factory(frames=4)),
        "-c",
        "copy",
        "-metadata",
        "title=日本語の題名",
        "-metadata",
        "comment=夏の動画",
        str(source),
    )
    monkeypatch.setattr(locale, "getencoding", lambda: "cp1252")
    assert probe(source).width == 96
    home = tmp_path / "home"
    job = add_job(
        source,
        dict(backend="cpu", preset="fast", fps="off", short_side="keep", codec="h264"),
        tmp_path / "output.mp4",
        home,
    )
    store = JobStore(home)
    for part in job["segments"]:
        destination = store.job_dir(job["id"]) / f"seg_{part['index']:05d}.mp4"
        process_segment(job, part, destination, lambda: False)
        part.update(file=destination.name, state="done")
    assemble(job, store.job_dir(job["id"]))
    job.update(state="done", finished_at=job["updated_at"])
    store.save(job)
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(home)
    try:
        row = next(row for row in engine.queue()["jobs"] if row["id"] == job["id"])
        assert row["input"] == str(source)
        details = engine.dispatch("GET", ["queue", job["id"], "details"], {})["text"]
        assert json.loads(details.split("\nSegment log")[0])["input"]["path"] == str(source)
        get_logger(home).warning("Synthetic path: %s", source)
        records = (home / "videoenhancer.jsonl").read_text(encoding="utf-8").splitlines()
        assert str(source) in json.loads(records[-1])["event"]
        engine.history_action("remove", dict(ids=[job["id"]]))
        engine.history_action("undo", dict(ids=[job["id"]]))
        assert source.exists()
    finally:
        engine.close()


def test_a2_local_preparation_has_unknown_media(tmp_path, monkeypatch):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    source = tmp_path / "synthetic.mp4"
    source.write_bytes(b"synthetic")
    monkeypatch.setattr(
        engine,
        "estimate",
        lambda _: dict(warnings=[], presets={"fast": dict(seconds=1, finish=None)}),
    )
    monkeypatch.setattr(
        "videoenhancer.service.engine.threading.Thread",
        lambda **k: SimpleNamespace(start=lambda: None, is_alive=lambda: False),
    )
    try:
        result = engine.add(dict(file=str(source), settings=dict(preset="fast", codec="h264")))
        assert all(
            result["media"][key] is None
            for key in ("display_width", "display_height", "frame_count", "duration")
        )
        row = next(row for row in engine.queue()["jobs"] if row["id"] == result["id"])
        assert row["state"] == "preparing"
        assert not row.get("record_error")
        assert engine.last_error is None
    finally:
        engine.close()


def test_a2_empty_nvdec_thumbnail_pass_falls_back(video_factory, monkeypatch):
    from videoenhancer.media import analyze as module

    source = video_factory(frames=4)
    monkeypatch.setattr(module, "choose_backend", lambda _: "cuda")
    monkeypatch.setattr(
        module,
        "IndexedDecoder",
        lambda *a: SimpleNamespace(verify_timestamps=lambda *a: None, close=lambda: None),
    )
    original = module._thumbnails
    monkeypatch.setattr(
        module, "_thumbnails", lambda p, m, b: iter(()) if b == "cuda" else original(p, m, b)
    )
    result = module.analyze(source, "cuda")
    assert result["decoder"] == "ffmpeg"
    assert "0" in result["decoder_reason"]
    assert result["media"]["source_frame_count"] == 4


@pytest.mark.parametrize("unreadable", [True, False])
def test_a6_early_timer_reschedules(tmp_path, monkeypatch, unreadable):
    from videoenhancer.service import engine as module

    callbacks = []

    class Timer:
        def __init__(self, delay, callback):
            self.delay = delay
            callbacks.append(callback)

        def start(self):
            pass

    monkeypatch.setattr(module.threading, "Timer", Timer)
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: 99.999))
    job = dict(id="a" * 32, unreadable_record=unreadable, history_hidden_until=100)
    directory = tmp_path / job["id"]
    directory.mkdir()
    (directory / "manifest.json").write_text("{}", encoding="utf-8")
    engine = Engine.__new__(Engine)
    engine._mutation_lock = threading.RLock()
    engine._unreadable_removals = {job["id"]: job}
    engine._history_timers = []
    engine.store = SimpleNamespace(
        jobs_dir=tmp_path, job_dir=lambda _: directory, load=lambda _: job
    )
    engine._schedule_history_removal(job)
    callbacks[0]()
    assert len(callbacks) == 2


def test_a6_transient_delete_retries_without_touching_other_files(tmp_path, monkeypatch):
    from videoenhancer.service import engine as module

    callbacks = []

    class Timer:
        def __init__(self, delay, callback):
            callbacks.append(callback)

        def start(self):
            pass

    monkeypatch.setattr(module.threading, "Timer", Timer)
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: 101))
    job = dict(id="a" * 32, unreadable_record=True, history_hidden_until=100)
    directory = tmp_path / ".removing" / job["id"]
    directory.mkdir(parents=True)
    (directory / "record").write_bytes(b"staged")
    other = tmp_path / "untouched"
    other.write_bytes(b"keep")
    engine = Engine.__new__(Engine)
    engine.home = tmp_path / "home"
    engine._mutation_lock = threading.RLock()
    engine._unreadable_removals = {job["id"]: job}
    engine._history_timers = []
    engine.store = SimpleNamespace(jobs_dir=tmp_path)
    original = module.shutil.rmtree
    attempts = []

    def delete(path):
        attempts.append(path)
        if len(attempts) < 3:
            raise PermissionError("Synthetic busy record")
        original(path)

    monkeypatch.setattr(module.shutil, "rmtree", delete)
    engine._schedule_history_removal(job)
    for index in range(3):
        callbacks[index]()
    assert attempts == [directory] * 3
    assert not directory.exists()
    assert other.read_bytes() == b"keep"


@pytest.mark.parametrize("failure_count", [2, 4])
def test_a6_readable_partial_delete_keeps_retrying_after_manifest_is_gone(
    tmp_path, monkeypatch, failure_count
):
    from videoenhancer.service import engine as module

    monkeypatch.setattr(module, "choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    callbacks = []

    class Timer:
        def __init__(self, delay, callback):
            callbacks.append(callback)

        def start(self):
            pass

        def cancel(self):
            pass

    monkeypatch.setattr(module.threading, "Timer", Timer)
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: 101, monotonic=time.monotonic))
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"keep")
    job = dict(
        schema_version=1,
        id="a" * 32,
        state="failed",
        history_hidden_until=100,
        input={"path": str(outside)},
        output=str(tmp_path / "output.mp4"),
        segments=[],
    )
    engine.store.save(job)
    directory = engine.store.job_dir(job["id"])
    (directory / "data.bin").write_bytes(b"staged")
    original = module.shutil.rmtree
    attempts = []

    def delete(path):
        attempts.append(path)
        (path / "manifest.json").unlink(missing_ok=True)
        if len(attempts) <= failure_count:
            raise PermissionError("Synthetic partial deletion")
        original(path)

    monkeypatch.setattr(module.shutil, "rmtree", delete)
    try:
        engine._schedule_history_removal(job)
        count = min(failure_count + 1, 4)
        for index in range(count):
            callbacks[index]()
        staged = engine.store.jobs_dir / ".removing" / job["id"]
        assert attempts == [staged] * count
        assert len(callbacks) == count
        if failure_count == 4:
            assert staged.exists()
            monkeypatch.setattr(module.shutil, "rmtree", original)
            engine._recover()
        assert not staged.exists() and not directory.exists()
        assert outside.read_bytes() == b"keep"
    finally:
        engine.close()


def test_a1_explicit_text_encodings():
    violations = []
    root = Path(__file__).parents[1] / "src" / "videoenhancer"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            keywords = {arg.arg: arg.value for arg in node.keywords}
            needs_encoding = name in {
                "read_text",
                "write_text",
                "FileHandler",
                "RotatingFileHandler",
            }
            if name == "open":
                builtin = isinstance(node.func, ast.Name)
                receiver = "" if builtin else ast.unparse(node.func.value)
                non_file = receiver in {"archive", "bundle", "zipped", "self.opener"} or (
                    "build_opener(" in receiver
                )
                mode_index = 1 if builtin else 0
                mode = keywords.get("mode")
                if mode is None and len(node.args) > mode_index:
                    mode = node.args[mode_index]
                binary = (
                    isinstance(mode, ast.Constant)
                    and isinstance(mode.value, str)
                    and "b" in mode.value
                )
                needs_encoding = not non_file and not binary
            if name in {"run", "Popen", "check_output", "check_call"}:
                needs_encoding = any(
                    isinstance(keywords.get(key), ast.Constant) and keywords[key].value is True
                    for key in ("text", "universal_newlines")
                )
            if needs_encoding and "encoding" not in keywords:
                violations.append(f"{path.relative_to(root)}:{node.lineno}")
    assert not violations, "Implicit text encodings: " + ", ".join(violations)


@pytest.mark.parametrize("short_side", [1080, 1440])
def test_a3_unknown_link_dimensions_reserve_download_only(tmp_path, monkeypatch, short_side):
    monkeypatch.setattr("videoenhancer.service.engine.choose_backend", lambda _: "cpu")
    engine = Engine(tmp_path / "home")
    save_settings(engine.home, {"video_download_folder": str(tmp_path / "downloads")})
    video = dict(format_id="v", url="http://localhost/v", vcodec="h264", filesize=50_000_000)
    monkeypatch.setattr(
        engine.video_links, "metadata", lambda *a: (video["url"], dict(id="v", formats=[video]))
    )
    calls = []
    monkeypatch.setattr(
        "videoenhancer.jobs.store.require_working_space",
        lambda *a, **k: calls.append((a, k)),
    )
    try:
        engine.link_jobs.queue(
            dict(
                check_id="x",
                entry_key="0",
                format_id="v",
                settings={"backend": "cpu", "short_side": short_side},
            )
        )
        assert calls[0][0][2] == 0
        assert calls[0][1]["download_bytes"] == 50_000_000
    finally:
        engine.close()
