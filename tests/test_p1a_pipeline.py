from fractions import Fraction

import pytest
import torch

from videoenhancer.media.timing import output_rate
from videoenhancer.models.basicvsr import BasicVSRRestoreStage
from videoenhancer.models.rife import RifeInterpolateStage
from videoenhancer.pipeline import runner as pipeline_runner
from videoenhancer.pipeline.clips import StreamingClipBuffer, plan_restore_clips
from videoenhancer.pipeline.outliers import detect_frame_outliers, invalid_frame_positions
from videoenhancer.pipeline.stages import FrameBatch


def _batch(start: int, end: int) -> FrameBatch:
    frames = torch.arange(start, end, dtype=torch.float16)[:, None, None, None].expand(
        end - start, 3, 2, 2
    )
    return FrameBatch(
        frames,
        tuple(Fraction(index, 30) for index in range(start, end)),
        tuple(range(start, end)),
    )


def test_frame_outlier_detector_flags_isolated_flash_but_not_source_cut():
    reference = torch.full((6, 3, 16, 16), 0.25)
    reference[4:] = 0.75  # A real cut is present in both the source and output.
    output = reference.clone()
    output[2] = 1.0  # One white flash absent from the source.
    assert detect_frame_outliers(output, reference) == [2]
    assert detect_frame_outliers(reference, reference) == []


def test_frame_outlier_detector_rejects_a_source_flash():
    source_flash = torch.full((5, 3, 16, 16), 0.25)
    source_flash[2] = 1.0
    assert detect_frame_outliers(source_flash, source_flash) == []


def test_frame_outlier_detector_flags_edge_only_flash_but_not_natural_cut():
    reference = torch.full((5, 3, 40, 40), 0.25)
    reference[4:] = 0.75
    output = reference.clone()
    output[2, :, :, :4] = 1.0
    output[2, :, :, -4:] = 1.0
    assert detect_frame_outliers(output, reference) == [2]
    assert detect_frame_outliers(reference, reference) == []


def test_frame_outlier_detector_flags_chroma_glitch_with_stable_mean_luma():
    reference = torch.full((5, 3, 16, 16), 0.5)
    output = reference.clone()
    output[2, 0] = 1.0
    output[2, 1] = 0.352
    assert detect_frame_outliers(output, reference) == [2]
    assert detect_frame_outliers(reference, reference) == []


def test_invalid_frame_check_flags_nonfinite_and_unexpected_range_values():
    frames = torch.full((3, 3, 8, 8), 0.5)
    frames[1, 0, 0, 0] = float("nan")
    frames[2, 0, 0, 0] = 1.1
    assert invalid_frame_positions(frames) == [1, 2]
    assert invalid_frame_positions(frames, [False, False, True]) == [1]


def test_clip_ownership_is_center_most_and_covers_each_frame_once():
    clips = plan_restore_clips(3, 103, clip_length=15, clip_overlap=3)
    assert clips[0].owned_start == 3
    assert clips[-1].owned_end == 103
    assert all(clip.end - clip.start <= 15 for clip in clips)
    owners = []
    for frame in range(3, 103):
        matches = [clip for clip in clips if clip.owned_start <= frame < clip.owned_end]
        assert len(matches) == 1
        owners.append(matches[0])
        contenders = [clip for clip in clips if clip.start <= frame < clip.end]
        center_scores = [min(frame - c.start, c.end - 1 - frame) for c in contenders]
        chosen = max(range(len(contenders)), key=lambda index: (center_scores[index], index))
        assert matches[0] is contenders[chosen]
    assert len(owners) == 100


@pytest.mark.parametrize("preset", ["fast", "standard"])
def test_real_presets_double_supported_frame_rates(preset: str):
    media = {"cfr_fps": "30000/1001"}
    assert output_rate({"preset": preset, "fps": "2x"}, media) == Fraction(60000, 1001)


def test_cut_bounded_clips_and_segment_context_preserve_identity():
    frames = _batch(0, 60)
    cuts = {11, 33, 48}
    whole_clips = plan_restore_clips(0, 60, 15, 3, cuts)
    assert all(not any(c.start < cut < c.end for cut in cuts) for c in whole_clips)
    whole_output = []
    for clip in whole_clips:
        positions = [i for i, index in enumerate(frames.indices) if clip.start <= index < clip.end]
        whole_output.extend(
            frames.frames[i]
            for i, index in zip(positions, (frames.indices[p] for p in positions), strict=True)
            if clip.owned_start <= index < clip.owned_end
        )
    assert torch.equal(torch.stack(whole_output), frames.frames)

    segment_output = []
    for start, end in ((0, 17), (17, 39), (39, 60)):
        context_start, context_end = max(0, start - 3), min(60, end + 3)
        segment = []
        for clip in plan_restore_clips(context_start, context_end, 15, 3, cuts):
            positions = [
                i for i, index in enumerate(frames.indices) if clip.start <= index < clip.end
            ]
            segment.extend(
                frames.frames[i]
                for i in positions
                if start <= frames.indices[i] < end
                and clip.owned_start <= frames.indices[i] < clip.owned_end
            )
        segment_output.extend(segment)
    assert torch.equal(torch.stack(segment_output), frames.frames)


def test_streaming_clip_buffer_live_frames_stay_bounded_with_identity_model():
    source = _batch(0, 120)
    clip_length, clip_overlap, decode_batch, queue_slots = 15, 3, 2, 2
    clips = plan_restore_clips(0, len(source.indices), clip_length, clip_overlap)
    buffer = StreamingClipBuffer()
    cursor = 0
    outputs = []
    high_water = 0
    for clip_index, clip in enumerate(clips):
        while cursor < clip.end:
            batch_end = min(len(source.indices), cursor + decode_batch)
            buffer.add(
                FrameBatch(
                    source.frames[cursor:batch_end],
                    source.timestamps[cursor:batch_end],
                    source.indices[cursor:batch_end],
                )
            )
            cursor = batch_end
        batch = buffer.build(clip)
        # Fake identity model retains its input and returns it unchanged.
        high_water = max(
            high_water,
            buffer.live_frames + len(batch.indices) + decode_batch * queue_slots,
        )
        assert torch.equal(batch.frames, source.frames[clip.start : clip.end])
        outputs.extend(
            batch.frames[position]
            for position, index in enumerate(batch.indices)
            if clip.owned_start <= index < clip.owned_end
        )
        next_start = (
            clips[clip_index + 1].start if clip_index + 1 < len(clips) else len(source.indices)
        )
        buffer.release_before(next_start)
    assert torch.equal(torch.stack(outputs), source.frames)
    assert high_water <= 2 * (clip_length + decode_batch) + decode_batch * queue_slots


class _FakeRife:
    def __init__(self, flow: float = 0.0) -> None:
        self.flow = flow
        self.seen_shape: tuple[int, ...] | None = None

    def __call__(self, pair: torch.Tensor, **_kwargs):
        self.seen_shape = tuple(pair.shape)
        left, right = pair[:, :3], pair[:, 3:]
        middle = (left + right) / 2
        flow = torch.full((1, 4, *pair.shape[-2:]), self.flow, dtype=pair.dtype)
        return [flow], torch.zeros((1, 1, *pair.shape[-2:])), [middle]


class _NanOnceBasicVSR(torch.nn.Module):
    def __init__(self, always_nan: bool = False) -> None:
        super().__init__()
        self.calls = 0
        self.always_nan = always_nan

    def forward(self, frames: torch.Tensor) -> torch.Tensor:
        self.calls += 1
        if self.always_nan or self.calls == 1:
            return frames * float("nan")
        return frames


def test_basicvsr_retries_nonfinite_clip_once_in_fp32():
    stage = BasicVSRRestoreStage({"backend": "cpu", "clip_length": 3, "clip_overlap": 1})
    model = _NanOnceBasicVSR()
    stage.model = model
    batch = _batch(0, 3)
    result = stage.process(batch)
    assert model.calls == 2
    assert stage.nan_retries == 1
    assert torch.equal(result.frames, batch.frames)

    stage.model = _NanOnceBasicVSR(always_nan=True)
    with pytest.raises(FloatingPointError, match="FP32 retry"):
        stage.process(batch)
    stage.model = None


@pytest.mark.gpu
def test_real_basicvsr_gpu_stage_returns_cuda_clip_within_memory_limit(gpu_available):
    stage = BasicVSRRestoreStage({"backend": "cuda", "clip_length": 15, "clip_overlap": 3})
    stage.setup()
    frames = batch = result = None
    try:
        frames = torch.rand((15, 3, 1280, 720), device="cuda", dtype=torch.float16)
        batch = FrameBatch(
            frames,
            tuple(Fraction(index, 30) for index in range(15)),
            tuple(range(15)),
        )
        result = stage.process(batch)
        torch.cuda.synchronize()
        assert result.frames.device.type == "cuda"
        assert result.frames.shape == frames.shape
        assert torch.isfinite(result.frames).all()
        assert torch.cuda.max_memory_reserved() <= 5 * 1024**3
    finally:
        result = batch = frames = None
        stage.teardown()


def test_rife_passes_original_frames_exactly_and_honors_cut_and_padding():
    stage = RifeInterpolateStage(Fraction(30), {2}, {"backend": "cpu"})
    stage.model = _FakeRife()
    original = torch.rand((3, 3, 33, 35), dtype=torch.float16)
    batch = FrameBatch(original, tuple(Fraction(i, 30) for i in range(3)), (0, 1, 2))
    result = stage.process(batch)
    assert result.frames.shape == (6, 3, 33, 35)
    assert result.indices == tuple(range(6))
    assert torch.equal(result.frames[::2], original)
    assert torch.equal(result.frames[3], original[1])  # cut after frame 1: duplicate it
    assert stage.last_padding == (31, 29)
    assert stage.model.seen_shape == (1, 6, 64, 64)


def test_rife_fallbacks_for_extreme_flow_and_nonfinite_pairs():
    stage = RifeInterpolateStage(
        Fraction(30), set(), {"backend": "cpu", "rife_mean_flow_limit": 1.0}
    )
    stage.model = _FakeRife(flow=2.0)
    frames = torch.zeros((2, 3, 32, 32), dtype=torch.float32)
    frames[1].fill_(1)
    result = stage.process(FrameBatch(frames, (Fraction(0), Fraction(1, 30)), (0, 1)))
    assert torch.equal(result.frames[1], torch.full_like(frames[0], 0.5))
    assert stage.fallback_count == 1

    frames[0, 0, 0, 0] = float("nan")
    result = stage.process(FrameBatch(frames, (Fraction(0), Fraction(1, 30)), (0, 1)))
    assert stage.nan_fallback_count >= 1
    assert torch.isfinite(result.frames[1]).all()


class _FakeRestore:
    name = "restore"
    clip_length = 5
    clip_overlap = 1
    context_before = 1
    context_after = 1

    def __init__(self, out_of_memory_once: bool = False) -> None:
        self.calls = 0
        self.max_frames = 0
        self.out_of_memory_once = out_of_memory_once

    def setup(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def process(self, batch: FrameBatch) -> FrameBatch:
        self.calls += 1
        self.max_frames = max(self.max_frames, len(batch.indices))
        if self.out_of_memory_once and self.calls == 1:
            raise torch.cuda.OutOfMemoryError("injected CUDA out of memory")
        return batch


class _CorruptOnceRestore(_FakeRestore):
    def process(self, batch: FrameBatch) -> FrameBatch:
        self.calls += 1
        frames = batch.frames.clone()
        if self.calls == 1 and len(frames) >= 3:
            frames[2].fill_(1.0)
        return FrameBatch(frames, batch.timestamps, batch.indices)


class _CorruptEveryRestore(_FakeRestore):
    def process(self, batch: FrameBatch) -> FrameBatch:
        self.calls += 1
        frames = batch.frames.clone()
        if len(frames) >= 3:
            frames[2].fill_(1.0)
        return FrameBatch(frames, batch.timestamps, batch.indices)


@pytest.mark.parametrize("out_of_memory_once", [False, True])
def test_process_segment_uses_bounded_streaming_restore_and_retries_oom(
    video_factory, build_manifest, tmp_path, monkeypatch, out_of_memory_once
):
    source = video_factory(width=256, height=144, frames=24)
    manifest = build_manifest(
        source, backend="cpu", preset="standard", fps="off", short_side="keep"
    )
    fake_restore = _FakeRestore(out_of_memory_once)
    monkeypatch.setattr(pipeline_runner, "create_stages", lambda *_args: [fake_restore])
    output = tmp_path / "streamed_restore.mp4"
    stats = pipeline_runner.process_segment(
        manifest, {"index": 7, "start": 0, "end": 24}, output, lambda: False
    )
    assert stats["output_frames"] == 24
    assert stats["luma_outliers"] == []
    assert fake_restore.calls > 1
    assert fake_restore.max_frames <= fake_restore.clip_length
    assert stats["oom_retries"] == int(out_of_memory_once)
    result = __import__("videoenhancer.media.probe", fromlist=["probe"]).probe(
        output, count_frames=True
    )
    assert result.frame_count == 24


def test_process_segment_retries_an_injected_corrupt_clip_before_handoff(
    video_factory, build_manifest, tmp_path, monkeypatch
):
    source = video_factory(width=64, height=64, frames=12)
    manifest = build_manifest(
        source, backend="cpu", preset="standard", fps="off", short_side="keep"
    )
    fake_restore = _CorruptOnceRestore()
    monkeypatch.setattr(pipeline_runner, "create_stages", lambda *_args: [fake_restore])
    output = tmp_path / "recovered.mp4"
    stats = pipeline_runner.process_segment(
        manifest, {"index": 0, "start": 0, "end": 12}, output, lambda: False
    )
    assert stats["corruption_retries"] == 1
    assert stats["corruption_fallbacks"] == 0
    assert fake_restore.calls >= 2
    assert stats["luma_outliers"] == []


def test_process_segment_records_fallback_when_corruption_persists(
    video_factory, build_manifest, tmp_path, monkeypatch
):
    source = video_factory(width=64, height=64, frames=12)
    manifest = build_manifest(
        source, backend="cpu", preset="standard", fps="off", short_side="keep"
    )
    fake_restore = _CorruptEveryRestore()
    monkeypatch.setattr(pipeline_runner, "create_stages", lambda *_args: [fake_restore])
    output = tmp_path / "fallback.mp4"
    stats = pipeline_runner.process_segment(
        manifest, {"index": 0, "start": 0, "end": 12}, output, lambda: False
    )
    assert stats["corruption_retries"] > 0
    assert stats["corruption_fallbacks"] > 0
    assert all(event["action"] == "nearest_valid_frame" for event in stats["corruption_events"])


@pytest.mark.gpu
def test_real_rife_gpu_padding_crop_and_original_frame_passthrough(gpu_available):
    from videoenhancer.pipeline.stages import FrameBatch

    stage = RifeInterpolateStage(Fraction(30), set(), {"backend": "cuda"})
    stage.setup()
    original = batch = result = None
    try:
        original = torch.rand((2, 3, 1920, 1080), device="cuda", dtype=torch.float16)
        batch = FrameBatch(original, (Fraction(0), Fraction(1, 30)), (0, 1))
        result = stage.process(batch)
        torch.cuda.synchronize()
        assert result.frames.shape == (4, 3, 1920, 1080)
        assert result.indices == (0, 1, 2, 3)
        assert torch.equal(result.frames[::2], original)
        assert stage.last_padding == (0, 8)
    finally:
        result = batch = original = None
        torch.cuda.empty_cache()
        stage.teardown()
