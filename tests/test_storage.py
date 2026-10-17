"""Storage migration and cleanup use synthetic isolated homes only."""

import json
import os
import shutil
import time
from datetime import UTC, datetime, timedelta

import pytest
from test_controller import _job

from videoenhancer.jobs.store import JobStore, require_disk_space
from videoenhancer.models.registry import ModelRegistry
from videoenhancer.service.engine import Engine
from videoenhancer.service.settings import read_settings, save_settings
from videoenhancer.service.storage import (
    cleanup_expired,
    cleanup_job,
    copy_home,
    digest,
    storage_status,
)


def test_move_every_record_and_resume_undo(tmp_path):
    source, target = tmp_path / "old", tmp_path / "new"
    source.mkdir()
    store = JobStore(source)
    job = _job(store, tmp_path)
    job.update(state="paused", progress={}, models={})
    job["segments"][0]["state"] = "done"
    store.save(job)
    (store.job_dir(job["id"]) / "seg_00000.mp4").write_bytes(b"part")
    done = dict(
        job,
        id="finished",
        state="done",
        history_hidden_until=time.time() + 600,
        history_undo_remaining=9,
    )
    store.save(done)
    save_settings(source, {"theme": "light", "cleanup_working_files": False})
    schedule = {"timezone": "UTC", "windows": [], "log_path": str(source / "logs/run.log")}
    (source / "schedule.json").write_text(json.dumps(schedule))
    (source / "logs").mkdir()
    (source / "logs/run.log").write_text("synthetic log")
    (source / "deletions.jsonl").write_text(
        json.dumps(
            {
                "path": str(tmp_path / "external.mp4"),
                "guard": str(tmp_path / ".external.mp4.ve-guard-test"),
                "phase": "resolved",
                "result": "Kept",
                "job_id": job["id"],
                "id": "record",
            }
        )
        + "\n"
    )
    registry = ModelRegistry(source)
    model = registry.manifest("rife-4.25")
    weight = registry.folder(model["id"]) / model["weights"]["filename"]
    weight.write_bytes(b"synthetic model bytes")
    model["weights"]["sha256"] = digest(weight)
    (registry.folder(model["id"]) / "model.json").write_text(json.dumps(model))
    before = {p.relative_to(source): digest(p) for p in source.rglob("*") if p.is_file()}
    result = copy_home(source, target)
    assert result["files"] == len(before)
    assert {p.relative_to(source): digest(p) for p in source.rglob("*") if p.is_file()} == before
    assert read_settings(target)["theme"] == "light"
    moved_registry = ModelRegistry(target)
    assert moved_registry.weights(moved_registry.manifest(model["id"]), download=False).is_file()
    assert json.loads((target / "schedule.json").read_text())["log_path"] == str(
        target / "logs/run.log"
    )
    assert (target / "logs/run.log").read_text() == "synthetic log"
    assert json.loads((target / "deletions.jsonl").read_text())["path"] == str(
        tmp_path / "external.mp4"
    )
    engine = Engine(target)
    try:
        engine._recover()
        assert engine.store.load(job["id"])["state"] == "paused"
        engine.dispatch("POST", ["queue", job["id"], "resume"], {})
        assert engine.store.load(job["id"])["state"] == "queued"
        assert engine.store.load(job["id"])["segments"][0]["state"] == "done"
        assert engine.store.load("finished")["history_undo_remaining"] == 9
        engine.history_action("undo", {"ids": ["finished"]})
        assert engine.store.load("finished")["history_hidden_until"] == 0
    finally:
        engine.close()


def test_interrupted_copy_keeps_old_bytes(tmp_path):
    source = tmp_path / "old"
    source.mkdir()
    (source / "settings.json").write_text('{"theme":"dark"}')
    (source / "payload").write_bytes(b"unchanged")
    before = {p.name: p.read_bytes() for p in source.iterdir()}

    def interrupted(_value):
        raise InterruptedError("simulated killed copy")

    with pytest.raises(InterruptedError):
        copy_home(source, tmp_path / "new", interrupted)
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    # Publishing the active location is not part of copy_home.
    assert not (tmp_path / "storage-location.json").exists()


def test_corrupt_copy_not_published(tmp_path, monkeypatch):
    source = tmp_path / "old"
    source.mkdir()
    (source / "settings.json").write_text("{}")

    def corrupt(_source, dest):
        dest.write_bytes(b"X")

    monkeypatch.setattr(shutil, "copy2", corrupt)
    with pytest.raises(OSError, match="verification failed"):
        copy_home(source, tmp_path / "new")
    assert (source / "settings.json").read_text() == "{}"


@pytest.mark.parametrize("kind", ["nonempty", "nested", "parent"])
def test_refuse_unsafe_target(tmp_path, kind):
    source = tmp_path / "old"
    source.mkdir()
    (source / "settings.json").write_text("{}")
    target = tmp_path / "new"
    if kind == "nonempty":
        target.mkdir()
        (target / "keep").write_text("owner")
    elif kind == "nested":
        target = source / "nested"
    else:
        target = tmp_path
    with pytest.raises(ValueError):
        copy_home(source, target)
    assert (source / "settings.json").exists()


def test_internal_hardlink_guard_survives_copy(tmp_path):
    source = tmp_path / "old"
    source.mkdir()
    video = source / "synthetic.mp4"
    video.write_bytes(b"synthetic")
    guard = source / ".synthetic.mp4.ve-guard-test"
    os.link(video, guard)
    info = guard.stat()
    (source / "deletions.jsonl").write_text(
        json.dumps(
            {
                "id": "test",
                "path": str(video),
                "guard": str(guard),
                "guard_dev": info.st_dev,
                "guard_ino": info.st_ino,
            }
        )
        + "\n"
    )
    target = tmp_path / "new"
    copy_home(source, target)
    journal = json.loads((target / "deletions.jsonl").read_text())
    assert os.path.samefile(journal["path"], journal["guard"])
    moved = (target / guard.name).stat()
    assert (journal["guard_dev"], journal["guard_ino"]) == (moved.st_dev, moved.st_ino)
    assert os.path.samefile(video, guard)
    from test_deletion import FakeFiles

    from videoenhancer.service.deletion import VideoDeletion, fingerprint

    replay = {
        **journal,
        **fingerprint(target / video.name),
        "phase": "guarded",
        "owner_pid": 99999999,
        "owner_started": 0,
        "job_id": "synthetic",
    }
    (target / "deletions.jsonl").write_text(json.dumps(replay) + "\n")
    result = VideoDeletion(target, FakeFiles()).recover()
    assert len(result) == 1 and result[0]["result"].startswith("Kept:")
    assert (target / video.name).read_bytes() == b"synthetic"
    assert not (target / guard.name).exists()
    assert os.path.samefile(video, guard)


@pytest.mark.parametrize("state", ["failed", "cancelled"])
def test_cleanup_only_parts_and_joined_and_retry(tmp_path, state):
    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    job["state"] = state
    job["segments"][0]["state"] = "done"
    store.save(job)
    directory = store.job_dir(job["id"])
    for name in ["seg_00000.mp4", "seg_00001.tmp.mp4", "assembled.tmp.mp4"]:
        (directory / name).write_bytes(b"own")
    protected = ["finished.mp4", "seg_owner.mp4", "other.txt", "assembly-checkpoint.json"]
    for name in protected:
        (directory / name).write_bytes(b"keep")
    assert cleanup_job(store, job["id"]) == 9
    assert all((directory / name).read_bytes() == b"keep" for name in protected)
    assert store.load(job["id"])["state"] == state
    assert store.load(job["id"])["working_files_cleaned"]
    retried = store.set_state(job["id"], "queued")
    assert all(s["state"] == "pending" for s in retried["segments"])
    assert not retried.get("working_files_cleaned")


def test_cleanup_age_setting_and_sizes(tmp_path):
    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    job.update(state="failed", finished_at=(datetime.now(UTC) - timedelta(days=8)).isoformat())
    store.save(job)
    part = store.job_dir(job["id"]) / "seg_00000.mp4"
    part.write_bytes(b"1234")
    status = storage_status(store.home, store)
    assert status["working_bytes"] == 4 and status["cleanup"][0]["bytes"] == 4
    save_settings(store.home, {"cleanup_working_files": False})
    cleanup_expired(store)
    assert part.exists()
    save_settings(store.home, {"cleanup_working_files": True})
    cleanup_expired(store)
    assert not part.exists()
    assert store.load(job["id"])["state"] == "failed"


def test_processing_refuses_move_and_mutations_are_frozen(tmp_path):
    engine = Engine(tmp_path / "home")
    job = _job(engine.store, tmp_path)
    try:
        with pytest.raises(ValueError, match="Pause processing first"):
            engine.dispatch("POST", ["storage", "prepare"], {})
        engine.paused = True
        assert engine.dispatch("POST", ["storage", "prepare"], {})["ready"]
        with pytest.raises(ValueError, match="App data is moving"):
            engine.dispatch("PUT", ["settings"], {"theme": "light"})
        assert engine.store.load(job["id"])["state"] == "queued"
    finally:
        engine.close()


def test_space_error_names_drive_and_free_amount(tmp_path):
    with pytest.raises(OSError) as raised:
        require_disk_space(tmp_path, 100_000_000, disk_free=0)
    assert (tmp_path.anchor or str(tmp_path)) in str(raised.value)
    assert "0.00 GB free" in str(raised.value)


def test_move_preserves_damaged_records_and_line_endings(tmp_path):
    source, target = tmp_path / "old", tmp_path / "new"
    source.mkdir()
    broken = b'{"torn":\xff\r\n'
    (source / "broken.json").write_bytes(broken)
    valid = json.dumps({"path": str(source / "payload.bin")}).encode()
    (source / "journal.jsonl").write_bytes(valid + b"\r\n\r\n" + broken + b"not-json")
    (source / "payload.bin").write_bytes(b"unchanged")
    result = copy_home(source, target)
    assert (target / "broken.json").read_bytes() == broken
    lines = (target / "journal.jsonl").read_bytes().splitlines(keepends=True)
    assert json.loads(lines[0])["path"] == str(target / "payload.bin")
    assert lines[1:] == [b"\r\n", broken, b"not-json"]
    assert result["damaged"] == {"broken.json": 1, "journal.jsonl": 2}
    for entry in result["manifest"]:
        assert entry["size"] == (source / entry["path"]).stat().st_size
        assert entry["active_size"] == (target / entry["path"]).stat().st_size


def test_prepare_failure_restores_normal_operation(tmp_path, monkeypatch):
    from videoenhancer.service import events

    engine = Engine(tmp_path / "home")
    original = events.changed

    def fail(_home):
        raise OSError("Synthetic preparation publication failure")

    try:
        monkeypatch.setattr(events, "changed", fail)
        with pytest.raises(OSError, match="Synthetic preparation"):
            engine.dispatch("POST", ["storage", "prepare"], {})
        assert not engine.storage_moving
        assert not engine.paused
        monkeypatch.setattr(events, "changed", original)
        engine.dispatch("PUT", ["settings"], {"theme": "light"})
    finally:
        engine.close()


def test_prepare_rejects_damaged_startup_record_without_changing_current_home(tmp_path):
    engine = Engine(tmp_path / "home")
    save_settings(engine.home, {})
    path = engine.home / "previews" / "damaged" / "state.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{torn startup record")
    settings = (engine.home / "settings.json").read_bytes()
    try:
        with pytest.raises(ValueError) as rejected:
            engine.dispatch("POST", ["storage", "prepare"], {})
        assert str(rejected.value) == (
            "Move stopped. A file the app needs at start is damaged: "
            "previews/damaged/state.json. Your data stays in the current folder."
        )
        assert path.read_bytes() == b"{torn startup record"
        assert (engine.home / "settings.json").read_bytes() == settings
        assert not engine.storage_moving
        assert not engine.paused
    finally:
        engine.close()


@pytest.mark.parametrize(
    "relative",
    [
        "settings.json",
        "schedule.json",
        "jobs/damaged/manifest.json",
        "previews/damaged/state.json",
        "previews/damaged/request.json",
        "models/damaged/model.json",
    ],
)
def test_move_startup_preflight_reports_relative_path_without_repair(tmp_path, relative):
    from videoenhancer.service.storage import check_startup_records

    home = tmp_path / "home"
    path = home / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{torn")
    with pytest.raises(ValueError) as rejected:
        check_startup_records(home)
    assert str(rejected.value) == (
        f"Move stopped. A file the app needs at start is damaged: {relative}. "
        "Your data stays in the current folder."
    )
    assert path.read_bytes() == b"{torn"


def test_move_startup_preflight_allows_damaged_noncore_logs(tmp_path):
    from videoenhancer.service.storage import check_startup_records

    home = tmp_path / "home"
    home.mkdir()
    (home / "events.jsonl").write_bytes(b'{"valid":1}\n{torn\n')
    (home / "diagnostics.json").write_bytes(b"{torn")
    check_startup_records(home)
    copied = copy_home(home, tmp_path / "copy")
    assert copied["damaged"] == {"events.jsonl": 1, "diagnostics.json": 1}
    assert (tmp_path / "copy" / "events.jsonl").read_bytes() == b'{"valid": 1}\n{torn\n'
    assert (tmp_path / "copy" / "diagnostics.json").read_bytes() == b"{torn"


def test_storage_status_with_concurrent_file_churn(tmp_path):
    import threading

    home = tmp_path / "home"
    home.mkdir()
    store = JobStore(home)
    stop = threading.Event()

    def churn():
        path = home / "transient.bin"
        while not stop.is_set():
            path.write_bytes(b"transient")
            path.unlink(missing_ok=True)

    worker = threading.Thread(target=churn)
    worker.start()
    try:
        for _ in range(100):
            assert storage_status(home, store)["total_bytes"] >= 0
    finally:
        stop.set()
        worker.join()


def test_killed_copy_process_preserves_source_and_location(tmp_path):
    import subprocess
    import sys

    source = tmp_path / "old"
    source.mkdir()
    for i in range(12):
        (source / f"payload-{i:02}.bin").write_bytes(b"s" * (2 * 1024 * 1024))
    pointer = tmp_path / "location.json"
    pointer.write_text(json.dumps({"active": str(source)}))
    before = {p.name: digest(p) for p in source.iterdir()}
    process = subprocess.Popen(
        [sys.executable, "-m", "videoenhancer.service.storage", str(source), str(tmp_path / "new")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert process.stdout is not None
        first = json.loads(process.stdout.readline())
        assert first["phase"] == "Copying and verifying"
        process.kill()
        process.wait(timeout=15)
        assert process.returncode != 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=15)
    assert {p.name: digest(p) for p in source.iterdir()} == before
    assert json.loads(pointer.read_text())["active"] == str(source)


def test_cli_saved_location_missing_and_override(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from videoenhancer import config

    saved = tmp_path / "roaming" / "VideoEnhancer" / "storage-location.json"
    saved.parent.mkdir(parents=True)
    target = tmp_path / "active"
    target.mkdir()
    saved.write_text(json.dumps({"active": str(target)}))
    env = {"LOCALAPPDATA": str(tmp_path / "local"), "APPDATA": str(tmp_path / "roaming")}
    monkeypatch.setattr(config, "os", SimpleNamespace(name="nt", environ=env))
    assert config.get_home() == target
    target.rmdir()
    with pytest.raises(FileNotFoundError, match="The app data folder was not found"):
        config.get_home()
    env["VE_HOME"] = str(tmp_path / "override")
    assert config.get_home() == tmp_path / "override"


def test_cleanup_preserves_recorded_input_and_finished_output_even_with_part_names(tmp_path):
    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    directory = store.job_dir(job["id"])
    source = directory / "seg_99999.mp4"
    output = directory / "assembled.tmp.mp4"
    source.write_bytes(b"owner input")
    output.write_bytes(b"owner finished output")
    job.update(state="failed", input={**job["input"], "path": str(source)}, output=str(output))
    store.save(job)
    part = directory / "seg_00000.mp4"
    part.write_bytes(b"engine part")
    assert cleanup_job(store, job["id"]) == len(b"engine part")
    assert source.read_bytes() == b"owner input"
    assert output.read_bytes() == b"owner finished output"


def test_automatic_cleanup_logs_locked_job_and_continues(tmp_path, monkeypatch):
    from videoenhancer.service import storage

    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    job.update(state="failed", finished_at=(datetime.now(UTC) - timedelta(days=8)).isoformat())
    store.save(job)
    other = {**job, "id": "other"}
    store.save(other)
    for item in (job, other):
        (store.job_dir(item["id"]) / "seg_00000.mp4").write_bytes(b"part")
    actual = storage.cleanup_job

    def locked(current, job_id, **kwargs):
        if job_id == job["id"]:
            raise PermissionError("synthetic locked part")
        return actual(current, job_id, **kwargs)

    monkeypatch.setattr(storage, "cleanup_job", locked)
    storage.cleanup_expired(store)
    assert (store.job_dir(job["id"]) / "seg_00000.mp4").exists()
    assert not (store.job_dir(other["id"]) / "seg_00000.mp4").exists()
    assert store.load(other["id"])["state"] == "failed"


def test_unreadable_subfolder_refuses_incomplete_copy(tmp_path, monkeypatch):
    from videoenhancer.service import storage

    source = tmp_path / "old"
    source.mkdir()
    (source / "settings.json").write_text("{}")

    def denied(_root, *, followlinks, onerror):
        onerror(PermissionError("synthetic unreadable directory"))
        return iter(())

    monkeypatch.setattr(storage.os, "walk", denied)
    with pytest.raises(PermissionError, match="synthetic unreadable"):
        storage.copy_home(source, tmp_path / "new")
    assert (source / "settings.json").read_text() == "{}"
    assert not (tmp_path / "new").exists()


def test_live_core_records_survive_log_append_and_history_removal(tmp_path):
    from videoenhancer.service.storage import core_records_load

    home = tmp_path / "home"
    store = JobStore(home)
    job = _job(store, tmp_path)
    save_settings(home, {})
    ModelRegistry(home)
    assert core_records_load(home, store)
    (home / "run.log").write_text("new live log data")
    import shutil

    shutil.rmtree(store.job_dir(job["id"]))
    assert core_records_load(home, store)


@pytest.mark.parametrize(
    "record", ["settings", "job", "model", "missing-model", "schedule", "preview"]
)
def test_core_records_fail_closed_without_repair(tmp_path, record):
    from videoenhancer.service.storage import core_records_load

    home = tmp_path / "home"
    store = JobStore(home)
    job = _job(store, tmp_path)
    save_settings(home, {})
    registry = ModelRegistry(home)
    model = next(registry.root.glob("*/model.json"))
    preview = home / "previews" / "fixture" / "state.json"
    preview.parent.mkdir(parents=True)
    path = {
        "settings": home / "settings.json",
        "job": store.job_dir(job["id"]) / "manifest.json",
        "model": model,
        "missing-model": model,
        "schedule": home / "schedule.json",
        "preview": preview,
    }[record]
    if record == "missing-model":
        path.unlink()
    else:
        path.write_text("{broken")
    assert not core_records_load(home, store)
    if record == "missing-model":
        assert not path.exists()


def test_move_manifest_protects_recorded_videos_and_all_videos_with_damaged_jobs(tmp_path):
    home = tmp_path / "old"
    store = JobStore(home)
    job = _job(store, tmp_path)
    source = home / "input.mp4"
    output = home / "output.mp4"
    preview = home / "preview.mp4"
    unknown = home / "extensionless"
    for path in (source, output, preview, unknown):
        path.write_bytes(b"synthetic file bytes; copy test only")
    job.update(input={**job["input"], "path": str(source)}, output=str(output))
    store.save(job)
    result = copy_home(home, tmp_path / "new")
    flags = {entry["path"]: entry["protected_video"] for entry in result["manifest"]}
    assert flags["input.mp4"] and flags["output.mp4"]
    assert not flags["preview.mp4"]
    (store.job_dir(job["id"]) / "manifest.json").write_bytes(b"{torn")
    result = copy_home(home, tmp_path / "damaged-copy")
    assert all(entry["protected_video"] for entry in result["manifest"])
