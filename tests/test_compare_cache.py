"""Decoded-range ownership, invalidation and conservative RAM reservations."""

import torch

from videoenhancer.service.compare_cache import DecodedRanges


def test_decoded_cache_owns_frames_and_keeps_backends_separate():
    cache = DecodedRanges(limit=100)
    source = torch.ones(4, dtype=torch.float16)
    calls = []

    def decode():
        calls.append(1)
        yield source

    key = ("synthetic", 1, 1, 0, 1)
    list(cache.frames(key, ("cpu", (0,)), 8, decode, "cpu"))
    source.zero_()
    reused = list(cache.frames(key, ("cpu", (0,)), 8, decode, "cpu"))
    assert torch.equal(reused[0], torch.ones_like(source))
    assert len(calls) == 1
    list(cache.frames(key, ("cuda", (0,)), 8, decode, "cpu"))
    assert len(calls) == 2
    assert cache.hits == 1 and cache.misses == 2
    assert cache.bytes == 16 and cache.reserved == 0


def test_decoded_cache_limits_ranges_and_invalidates_changed_source():
    cache = DecodedRanges(limit=16)
    frame = torch.ones(4, dtype=torch.float16)
    variant = ("cpu", (0,))

    def fill(key):
        return list(cache.frames(key, variant, 8, lambda: iter([frame]), "cpu"))

    a, b, c = [("synthetic", 1, 1, i, i + 1) for i in range(3)]
    fill(a)
    fill(b)
    fill(a)  # The recently used range survives.
    fill(c)
    assert set(cache.ranges) == {a, c}
    assert cache.bytes == 16
    changed = ("synthetic", 2, 2, 0, 1)
    fill(changed)
    assert list(cache.ranges) == [changed]
    assert cache.bytes == 8
    cache.clear()
    assert cache.bytes == 0 and not cache.ranges


def test_decoded_cache_bypasses_oversized_and_interrupted_ranges():
    cache = DecodedRanges(limit=8)
    frame = torch.ones(4, dtype=torch.float16)
    key = ("synthetic", 1, 1, 0, 2)
    list(cache.frames(key, ("cpu", (0, 1)), 16, lambda: iter([frame, frame]), "cpu"))
    assert not cache.ranges and cache.bytes == 0
    interrupted = cache.frames(key, ("cpu", (0, 1)), 8, lambda: iter([frame, frame]), "cpu")
    next(interrupted)
    assert cache.reserved == 8
    interrupted.close()
    assert cache.reserved == 0 and not cache.ranges
    # An inaccurate caller estimate must never cause retention beyond its reservation.
    list(cache.frames(key, ("cpu", (0, 1)), 8, lambda: iter([frame, frame]), "cpu"))
    assert cache.reserved == 0 and not cache.ranges


def test_inflight_reservation_blocks_another_retained_range():
    cache = DecodedRanges(limit=8)
    frame = torch.ones(4, dtype=torch.float16)
    first = cache.frames(("a", 1, 1, 0, 1), ("cpu", (0,)), 8, lambda: iter([frame]), "cpu")
    next(first)
    list(cache.frames(("b", 1, 1, 0, 1), ("cpu", (0,)), 8, lambda: iter([frame]), "cpu"))
    assert cache.reserved == 8 and not cache.ranges
    list(first)
    assert cache.reserved == 0 and cache.bytes == 8
    assert len(cache.ranges) == 1


def test_another_model_can_reuse_a_smaller_context_from_the_same_range():
    cache = DecodedRanges(limit=64)
    frames = [torch.full((2,), float(i), dtype=torch.float16) for i in range(5)]
    key = ("synthetic", 1, 1, 0, 3)
    list(cache.frames(key, ("cuda", (0, 1, 2, 3, 4)), 20, lambda: iter(frames), "cpu"))

    def unexpected_decode():
        raise AssertionError("The covered decoded context must be reused")

    reused = list(cache.frames(key, ("cuda", (1, 2, 3)), 12, unexpected_decode, "cpu"))
    assert [float(frame[0]) for frame in reused] == [1, 2, 3]
    assert cache.hits == 1 and cache.misses == 1
    assert cache.bytes == 20 and cache.reserved == 0
