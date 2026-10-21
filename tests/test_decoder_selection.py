"""Decoded labels must remain consecutive, including frames before a seek target."""

from fractions import Fraction
from types import SimpleNamespace

import pytest
import torch

from videoenhancer.media.decode import IndexedDecoder, TimestampMismatch, TimestampSequence


@pytest.mark.parametrize("stamps", [[0, 0, 33], [0, 67], [1, 33]])
def test_invalid_labels_fail_at_the_first_bad_frame(stamps):
    sequence = TimestampSequence(["0", "33/1000", "67/1000"])
    with pytest.raises(TimestampMismatch, match="frame 1" if stamps[0] == 0 else "frame 0"):
        for stamp in stamps:
            sequence.accept(Fraction(stamp, 1000))


def test_seek_starts_on_known_label_then_checks_every_frame():
    sequence = TimestampSequence(["0", "33/1000", "67/1000"])
    assert sequence.accept(Fraction(33, 1000)) == 1
    assert sequence.accept(Fraction(67, 1000)) == 2


def test_duplicate_before_target_cannot_be_silently_skipped(monkeypatch):
    decoder = IndexedDecoder.__new__(IndexedDecoder)
    decoder.manifest = {"source_pts": ["0", "33/1000", "67/1000"]}
    decoder._cuda_used = False
    decoder.demuxer = SimpleNamespace(GetTimebaseNum=lambda: 1, GetTimebaseDen=lambda: 1000)
    decoder._decoded_packets = lambda *_: iter(
        [SimpleNamespace(getPTS=lambda value=value: value) for value in [0, 0, 33, 67]]
    )
    # The real packet iterator is unused by this fake native decoder.
    decoder.demuxer = type(
        "Demuxer",
        (),
        {
            "GetTimebaseNum": lambda _: 1,
            "GetTimebaseDen": lambda _: 1000,
            "__iter__": lambda _: iter([]),
        },
    )()
    decoder._convert = lambda _: torch.zeros(3, 2, 2)
    with pytest.raises(TimestampMismatch, match="frame 1"):
        list(decoder._cuda_frames([2], lambda: False))


def test_eof_without_flush_uses_the_empty_packet():
    seen = []
    decoder = IndexedDecoder.__new__(IndexedDecoder)
    decoder.decoder = SimpleNamespace(Decode=lambda packet: seen.append(packet) or [packet])
    assert list(decoder._decoded_packets(iter(["data", "empty EOF"]), lambda: False)) == [
        "data",
        "empty EOF",
    ]
    assert seen == ["data", "empty EOF"]


def test_native_decoder_requires_an_analysed_timeline():
    decoder = IndexedDecoder.__new__(IndexedDecoder)
    decoder.manifest = {}
    decoder._cuda_used = False
    with pytest.raises(TimestampMismatch, match="timestamps are missing"):
        list(decoder._cuda_frames([0], lambda: False))
