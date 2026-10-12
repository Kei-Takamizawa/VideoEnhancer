import hashlib
import os
from pathlib import Path

import pytest

from videoenhancer.jobs.store import input_identity
from videoenhancer.service.deletion import VideoDeletion


class FakeFiles:
    def __init__(self, outcome="recycled", reject=""):
        self.outcome, self.reject = outcome, reject

    def preflight(self, path):
        if self.reject:
            raise OSError(self.reject)
        return 128

    def attributes(self, path, value):
        pass

    def restore(self, guard, path):
        os.link(guard, path)  # Fails without overwriting if another path appeared.
        guard.unlink()

    def recycle(self, path, post):
        if self.outcome == "recycled":
            path.rename(path.with_suffix(".bin"))
        elif self.outcome == "deleted":
            path.unlink()
        post(
            self.outcome == "recycled",
            str(path.with_suffix(".bin")) if self.outcome == "recycled" else None,
        )
        return "refused" if self.outcome == "refused" else ""


def fixture(tmp_path):
    source = tmp_path / "synthetic.mp4"
    source.write_bytes(bytes(range(256)) * 20000)
    job = dict(
        id="synthetic",
        state="done",
        input=input_identity(source),
        output=str(tmp_path / "output.mp4"),
    )
    return source, job


@pytest.mark.parametrize("outcome", ["recycled", "deleted", "refused"])
def test_guard_keeps_bytes_for_every_shell_outcome(tmp_path, outcome):
    source, job = fixture(tmp_path)
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    delete = VideoDeletion(tmp_path / "home", FakeFiles(outcome))
    result = delete.delete(source, job, [job])
    if outcome == "recycled":
        assert result == "Moved to the Recycle Bin"
        assert not source.exists()
        assert hashlib.sha256(source.with_suffix(".bin").read_bytes()).hexdigest() == expected
    else:
        assert result.startswith("Kept:")
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    assert not list(tmp_path.glob(".*.ve-guard-*"))
    assert delete.recover() == []


@pytest.mark.parametrize("phase", ["planned", "guarded", "shell", "confirmed"])
@pytest.mark.parametrize("outcome", ["recycled", "deleted"])
def test_crash_at_each_phase_recovers_without_data_loss(tmp_path, phase, outcome, monkeypatch):
    source, job = fixture(tmp_path)
    expected = source.read_bytes()
    files = FakeFiles(outcome)
    delete = VideoDeletion(tmp_path / "home", files)
    append = delete._append

    class Crash(BaseException):
        pass

    def crash(entry, state, **extra):
        append(entry, state, **extra)
        if state == phase:
            raise Crash()

    monkeypatch.setattr(delete, "_append", crash)
    if phase == "confirmed" and outcome == "deleted":
        delete.delete(source, job, [job])
    else:
        with pytest.raises(Crash):
            delete.delete(source, job, [job])
    monkeypatch.setattr("videoenhancer.service.deletion.owner_alive", lambda _entry: False)
    recovered = VideoDeletion(tmp_path / "home", files)
    recovered.recover()
    kept = source if source.exists() else source.with_suffix(".bin")
    assert kept.read_bytes() == expected
    assert not list(tmp_path.glob(".*.ve-guard-*"))
    assert recovered.recover() == []


@pytest.mark.parametrize(
    "reason", ["non-fixed drive", "FAT32", "exFAT", "file in use", "reparse point"]
)
def test_preflight_refusal_never_changes_file(tmp_path, reason):
    source, job = fixture(tmp_path)
    expected = source.read_bytes()
    result = VideoDeletion(tmp_path / "home", FakeFiles(reject=reason)).delete(source, job, [job])
    assert result == f"Kept: {reason}"
    assert source.read_bytes() == expected
    assert not (tmp_path / "home/deletions.jsonl").exists()


def test_unrecorded_path_and_shared_unfinished_original_are_kept(tmp_path):
    source, job = fixture(tmp_path)
    delete = VideoDeletion(tmp_path / "home", FakeFiles())
    other = {**job, "state": "queued", "id": "other"}
    assert "unfinished" in delete.delete(source, job, [job, other])
    assert "not recorded" in delete.delete(Path(__file__), job, [job])
    assert source.exists()


def test_crash_after_guard_removal_finishes_confirmed_recycle(tmp_path, monkeypatch):
    source, job = fixture(tmp_path)
    deletion = VideoDeletion(tmp_path / "home", FakeFiles())
    append = deletion._append

    class Crash(BaseException):
        pass

    def crash(entry, phase, **extra):
        if phase == "resolved":
            raise Crash()
        append(entry, phase, **extra)

    monkeypatch.setattr(deletion, "_append", crash)
    with pytest.raises(Crash):
        deletion.delete(source, job, [job])
    assert not source.exists() and not list(tmp_path.glob(".*.ve-guard-*"))
    monkeypatch.setattr("videoenhancer.service.deletion.owner_alive", lambda _entry: False)
    recovered = VideoDeletion(tmp_path / "home", FakeFiles()).recover()
    assert recovered[0]["result"] == "Moved to the Recycle Bin"
    assert source.with_suffix(".bin").read_bytes() == bytes(range(256)) * 20000


def test_path_replaced_at_shell_keeps_original_bytes(tmp_path):
    source, job = fixture(tmp_path)
    expected = source.read_bytes()

    class Replacement(FakeFiles):
        def recycle(self, path, post):
            path.unlink()
            path.write_bytes(b"different replacement")
            return super().recycle(path, post)

    result = VideoDeletion(tmp_path / "home", Replacement()).delete(source, job, [job])
    assert result.startswith("Kept:")
    assert source.read_bytes() == expected
    assert source.with_suffix(".bin").read_bytes() == b"different replacement"


def test_replacement_that_stays_reports_full_retained_guard(tmp_path):
    source, job = fixture(tmp_path)
    expected = source.read_bytes()

    class Replacement(FakeFiles):
        def recycle(self, path, post):
            path.unlink()
            path.write_bytes(b"new file at original path")
            raise RuntimeError("synthetic shell exception")

    deletion = VideoDeletion(tmp_path / "home", Replacement())
    result = deletion.delete(source, job, [job])
    guard = next(tmp_path.glob(".*.ve-guard-*"))
    assert str(guard) in result
    assert guard.read_bytes() == expected
    assert deletion.notices[0]["guard"] == str(guard)


def test_changed_identity_is_kept_before_shell(tmp_path):
    source, job = fixture(tmp_path)
    source.write_bytes(b"changed input")
    result = VideoDeletion(tmp_path / "home", FakeFiles()).delete(source, job, [job])
    assert result == "Kept: the file changed after this job used it"
    assert source.read_bytes() == b"changed input"
    assert not (tmp_path / "home/deletions.jsonl").exists()


@pytest.mark.parametrize(
    "reason",
    ["the file is too big for the Recycle Bin", "the Recycle Bin is turned off for this drive"],
)
def test_bin_limits_skip_shell(tmp_path, reason):
    source, job = fixture(tmp_path)

    class Limit(FakeFiles):
        def bin_refusal(self, path):
            return reason

        def recycle(self, path, post):
            pytest.fail("the shell must not be called")

    assert VideoDeletion(tmp_path / "home", Limit()).delete(source, job, [job]) == f"Kept: {reason}"
    assert source.exists()


def test_non_oserror_after_guard_restores_bytes(tmp_path):
    source, job = fixture(tmp_path)
    expected = source.read_bytes()

    class Failure(FakeFiles):
        def recycle(self, path, post):
            path.unlink()
            raise RuntimeError("synthetic error after guard")

    result = VideoDeletion(tmp_path / "home", Failure()).delete(source, job, [job])
    assert "synthetic error" in result
    assert source.read_bytes() == expected


def test_readonly_guard_removal_never_changes_file_attributes(tmp_path):
    source, job = fixture(tmp_path)
    calls = []

    class ReadOnly(FakeFiles):
        def preflight(self, path):
            return 1

        def attributes(self, path, value):
            pytest.fail("hard links must not change shared file attributes")

        def unlink_guard(self, path):
            calls.append(path)
            path.unlink()

    assert (
        VideoDeletion(tmp_path / "home", ReadOnly()).delete(source, job, [job])
        == "Moved to the Recycle Bin"
    )
    assert len(calls) == 1


def _hold_deletion(root, ready, release):
    source, job = fixture(root)

    class Held(FakeFiles):
        def recycle(self, path, post):
            ready.set()
            assert release.wait(15)
            return super().recycle(path, post)

    assert (
        VideoDeletion(root / "home", Held()).delete(source, job, [job])
        == "Moved to the Recycle Bin"
    )


def test_cross_process_recovery_does_not_touch_active_guard(tmp_path):
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    worker = context.Process(target=_hold_deletion, args=(tmp_path, ready, release))
    worker.start()
    try:
        assert ready.wait(10)
        guard = next(tmp_path.glob(".*.ve-guard-*"))
        before = guard.read_bytes()
        journal = (tmp_path / "home/deletions.jsonl").read_bytes()
        assert VideoDeletion(tmp_path / "home", FakeFiles()).recover() == []
        assert guard.read_bytes() == before
        assert (tmp_path / "home/deletions.jsonl").read_bytes() == journal
    finally:
        release.set()
        worker.join(10)
        if worker.is_alive():
            worker.terminate()
            worker.join(5)
    assert worker.exitcode == 0


def test_unfinished_hardlink_alias_prevents_deletion(tmp_path):
    source, job = fixture(tmp_path)
    alias = tmp_path / "alias.mp4"
    os.link(source, alias)
    other = {**job, "id": "alias-job", "state": "queued", "input": input_identity(alias)}
    result = VideoDeletion(tmp_path / "home", FakeFiles()).delete(source, job, [job, other])
    assert "unfinished" in result and source.exists()


def test_auto_delete_merges_fresh_fields_and_skips_removed_job(tmp_path, monkeypatch):
    import shutil

    from test_controller import _job

    from videoenhancer.jobs.store import JobStore
    from videoenhancer.service.deletion import finish_original_deletions

    store = JobStore(tmp_path / "home")
    job = _job(store, tmp_path)
    job.update(state="done")
    job["settings"]["delete_original_after"] = True
    store.save(job)

    def concurrent_change(_job):
        store.patch_existing(
            job["id"], {"video_deletions": {"output": "Kept: concurrent output change"}}
        )
        raise ValueError("synthetic output verification failed")

    monkeypatch.setattr("videoenhancer.service.deletion.verify_output", concurrent_change)
    finish_original_deletions(store)
    assert store.load(job["id"])["video_deletions"]["output"] == "Kept: concurrent output change"
    store.patch_existing(job["id"], {"original_delete_result": None})
    monkeypatch.setattr(
        "videoenhancer.service.deletion.verify_output",
        lambda _job: shutil.rmtree(store.job_dir(job["id"])),
    )
    finish_original_deletions(store)
    assert not store.job_dir(job["id"]).exists()


@pytest.mark.parametrize(
    "case", ["pass", "short_frames", "wrong_duration", "missing_audio", "no_video"]
)
def test_verify_output_with_real_small_files(tmp_path, video_factory, ffmpeg_run, case):
    from videoenhancer.media.probe import probe
    from videoenhancer.service.deletion import verify_output

    source = video_factory(frames=12, audio=case == "missing_audio")
    media = probe(source, count_packets=True).to_dict()
    output = source
    if case == "short_frames":
        output = video_factory(frames=8)
    elif case == "wrong_duration":
        media["cfr_fps"] = "60"
    elif case == "missing_audio":
        output = video_factory(frames=12)
    elif case == "no_video":
        output = tmp_path / "audio.wav"
        ffmpeg_run("-f", "lavfi", "-i", "sine=frequency=440:duration=0.4", str(output))
    job = dict(
        output=str(output),
        media=media,
        settings=dict(
            preset="passthrough", fps="off", short_side="keep", codec="h264", backend="cpu"
        ),
    )
    if case == "pass":
        verify_output(job)
    else:
        with pytest.raises(Exception) as failure:
            verify_output(job)
        assert str(failure.value).strip()
