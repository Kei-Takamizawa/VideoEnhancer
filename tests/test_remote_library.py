"""Scratch-only library safety, metadata and byte-range tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from videoenhancer.remote.library import InUseError, Library, parse_range


@pytest.fixture
def library(tmp_path, monkeypatch):
    folder = tmp_path / "library"
    folder.mkdir()
    result = Library(tmp_path / "home", folder)
    monkeypatch.setattr(
        result,
        "_probe",
        lambda path: {"duration": 2.5, "width": 96, "height": 64, "codec": "h264"},
    )
    return result


def test_listing_filters_sorts_and_keeps_opaque_stable_ids(library):
    folder = library.folder
    (folder / "old.mp4").write_bytes(b"old")
    (folder / "new.MOV").write_bytes(b"newer")
    os.utime(folder / "old.mp4", (100, 100))
    os.utime(folder / "new.MOV", (200, 200))
    for name in (".hidden.mp4", "pending.mp4.tmp", "pending.part.mp4", "notes.txt"):
        (folder / name).write_bytes(b"ignored")
    (folder / "subfolder.mp4").mkdir()
    items = library.list()
    assert [item["name"] for item in items] == ["new", "old"]
    assert [item["size"] for item in items] == [5, 3]
    assert all(len(item["id"]) == 64 and "path" not in item for item in items)
    assert library.list()[0]["id"] == items[0]["id"]
    assert items[0]["codec"] == "h264"


def test_probe_cache_persists_and_invalidates_on_size_or_mtime(library, monkeypatch):
    path = library.folder / "sample.mp4"
    path.write_bytes(b"one")
    calls = []

    def probe(path):
        calls.append(path)
        return {"duration": 1.0, "width": 96, "height": 64, "codec": "hevc"}

    monkeypatch.setattr(library, "_probe", probe)
    assert library.list()[0]["codec"] == "hevc"
    library.list()
    assert len(calls) == 1
    other = Library(library.home, library.folder)
    monkeypatch.setattr(other, "_probe", probe)
    other.list()
    assert len(calls) == 1
    path.write_bytes(b"two bytes")
    other.list()
    assert len(calls) == 2
    cached = json.loads((library.home / "remote" / "library-probes.json").read_text())
    assert len(cached) == 1


def test_unreadable_video_is_listed_and_can_be_deleted(library, monkeypatch):
    path = library.folder / "broken.mp4"
    path.write_bytes(b"bad")

    def broken(path):
        raise ValueError("private filename must not be exposed")

    monkeypatch.setattr(library, "_probe", broken)
    item = library.list()[0]
    assert item["error"] == "Can't read this video"
    assert item["duration"] is None
    library.delete(item["id"])
    assert not path.exists()


def test_active_stream_refuses_delete_then_releases(library):
    (library.folder / "sample.mp4").write_bytes(b"abcdef")
    identifier = library.list()[0]["id"]
    with library.acquire(identifier) as (stream, item):
        assert stream.read() == b"abcdef"
        assert item["filename"] == "sample.mp4"
        with pytest.raises(InUseError, match="streamed or downloaded"):
            library.delete(identifier)
    library.delete(identifier)
    assert library.list() == []


@pytest.mark.parametrize("identifier", ["../outside", "x/../x", "%2e%2e", "abc", "A" * 64])
def test_invalid_id_never_resolves_to_path(library, identifier):
    with pytest.raises(ValueError):
        library.delete(identifier)
    with pytest.raises(ValueError), library.acquire(identifier):
        pass


def test_unknown_id_has_no_file(library):
    with pytest.raises(FileNotFoundError):
        library.delete("a" * 64)


@pytest.mark.parametrize("attributes", [0x400, 0x2])
def test_reparse_points_and_hidden_windows_files_are_rejected(library, monkeypatch, attributes):
    (library.folder / "outside.mp4").write_bytes(b"not really a symlink")
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path.name == "outside.mp4":
            return SimpleNamespace(st_mode=0o100644, st_file_attributes=attributes)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    assert library.list() == []


def test_symlink_to_outside_is_rejected(library, tmp_path):
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"secret")
    link = library.folder / "linked.mp4"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("This Windows account cannot create symbolic links.")
    assert library.list() == []
    assert outside.read_bytes() == b"secret"


def test_storage_is_decimal_drive_capacity_and_library_size(library, monkeypatch):
    (library.folder / "one.mp4").write_bytes(b"1234")
    (library.folder / "ignore.txt").write_bytes(b"ignored")
    monkeypatch.setattr(
        "videoenhancer.remote.library.shutil.disk_usage",
        lambda path: SimpleNamespace(total=1_000_000_000, free=400_000_000),
    )
    result = library.storage()
    assert result["total"] == 1_000_000_000
    assert result["free"] == 400_000_000
    assert result["library_bytes"] == 4


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, (0, 9)),
        ("bytes=0-0", (0, 0)),
        ("bytes=3-6", (3, 6)),
        ("bytes=-3", (7, 9)),
        ("bytes=7-", (7, 9)),
        ("bytes=0-99", (0, 9)),
        ("bytes=-99", (0, 9)),
    ],
)
def test_byte_ranges(header, expected):
    assert parse_range(header, 10) == expected


@pytest.mark.parametrize(
    "header", ["bytes=10-", "bytes=4-3", "bytes=-0", "bytes=0-1,3-4", "items=0-1", "bytes=a-2"]
)
def test_invalid_byte_ranges(header):
    with pytest.raises(ValueError):
        parse_range(header, 10)


def test_empty_file_range():
    assert parse_range(None, 0) == (0, -1)
    with pytest.raises(ValueError):
        parse_range("bytes=0-0", 0)


def test_actual_ffprobe_metadata(video_factory, tmp_path):
    source = video_factory(width=96, height=64, frames=12, rate="30")
    folder = tmp_path / "real-library"
    folder.mkdir()
    source.rename(folder / "sample.mp4")
    library = Library(tmp_path / "probe-home", folder)
    item = library.list()[0]
    assert "error" not in item
    assert item["duration"] == pytest.approx(0.4)
    assert (item["width"], item["height"], item["codec"]) == (96, 64, "h264")


def test_video_changed_during_probe_is_not_listed(library, monkeypatch):
    (library.folder / "sample.mp4").write_bytes(b"writing")

    def probe(path):
        path.write_bytes(b"still writing a longer file")
        return {"duration": 1.0, "width": 96, "height": 64, "codec": "h264"}

    monkeypatch.setattr(library, "_probe", probe)
    assert library.list() == []


def test_opened_file_identity_change_is_refused(library, monkeypatch):
    (library.folder / "first.mp4").write_bytes(b"first")
    other = library.folder / "other.mp4"
    other.write_bytes(b"other")
    identifier = next(item["id"] for item in library.list() if item["name"] == "first")
    original_open = os.open
    monkeypatch.setattr(
        "videoenhancer.remote.library.open_descriptor",
        lambda path, flags: original_open(other, flags),
    )
    with pytest.raises(FileNotFoundError, match="changed"), library.acquire(identifier):
        pytest.fail("A replaced file was exposed.")
