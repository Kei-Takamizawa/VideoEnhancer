import hashlib
import os
from pathlib import Path

import pytest

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
        post(self.outcome == "recycled")
        return "refused" if self.outcome == "refused" else ""


def fixture(tmp_path):
    source = tmp_path / "synthetic.mp4"
    source.write_bytes(bytes(range(256)) * 20000)
    job = dict(
        id="synthetic",
        state="done",
        input={"path": str(source)},
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
    recovered = VideoDeletion(tmp_path / "home", FakeFiles()).recover()
    assert recovered[0]["result"] == "Moved to the Recycle Bin"
    assert source.with_suffix(".bin").read_bytes() == bytes(range(256)) * 20000
