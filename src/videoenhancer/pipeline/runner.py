"""Three overlapped workers with bounded queues and rational frame ownership."""

import logging
import queue
import threading
import time
from bisect import bisect_right
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import psutil
import torch

from videoenhancer.jobs.gpu_memory import JobMemorySampler
from videoenhancer.media.decode import IndexedDecoder, choose_backend
from videoenhancer.media.encode import Encoder
from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.pipeline.clips import (
    RestoreClip,
    StreamingClipBuffer,
    plan_restore_clips,
)
from videoenhancer.pipeline.inline_quality import (
    STRIDE,
    FidelityAccumulator,
    temporal_partial,
)
from videoenhancer.pipeline.outliers import (
    detect_frame_outliers,
    invalid_frame_positions,
    reference_range_positions,
    summarize_frames,
)
from videoenhancer.pipeline.presets import create_stages
from videoenhancer.pipeline.stages import FrameBatch, ResizeStage

logger = logging.getLogger(__name__)


def process_segment(
    manifest: dict[str, Any],
    segment: dict[str, Any],
    output_path: Path,
    abort: Callable[[], bool],
    batch_size: int = 2,
) -> dict[str, Any]:
    from videoenhancer.models.registry import validate_job_models

    validate_job_models(manifest)
    started = time.perf_counter()
    settings, media = manifest["settings"], manifest["media"]
    backend = choose_backend(settings.get("backend", "auto"))
    torch.set_num_threads(2)
    if backend == "cuda":
        torch.cuda.reset_peak_memory_stats()
    stages = create_stages(settings, media, set(manifest.get("scene_cuts", [])))
    memory_sampler = JobMemorySampler()
    memory_sampler.start()
    try:
        for stage in stages:
            stage.setup()
    except BaseException:
        for stage in stages:
            stage.teardown()
        memory_sampler.stop()
        raise
    context_before = sum(s.context_before for s in stages)
    context_after = sum(s.context_after for s in stages)
    start, end = segment["start"], segment["end"]
    count = len(manifest["cfr_map"])
    source_start, source_end = max(0, start - context_before), min(count, end + context_after)
    rate = Fraction(media["cfr_fps"])
    factor = int(output_rate(settings, media) / rate)
    source_cuts = sorted(set(manifest.get("scene_cuts", [])))
    # Two queue slots, two-frame batches, and at most one context frame keep
    # full-resolution tensors bounded independently of video duration.
    queue_size = max(1, int(settings.get("pipeline_queue_size", 2)))
    decoded: queue.Queue[Any] = queue.Queue(maxsize=queue_size)
    processed: queue.Queue[Any] = queue.Queue(maxsize=queue_size)
    stopped = threading.Event()
    errors: list[BaseException] = []
    written = 0
    peak_rss = 0
    decode_seconds = 0.0
    encode_seconds = 0.0
    handoff_check_seconds = 0.0
    reference_check_seconds = 0.0
    corruption_retries = 0
    corruption_fallbacks = 0
    corruption_events: list[dict[str, Any]] = []
    raw_flag_indices: set[int] = set()
    postrepair_flag_indices: set[int] = set()
    stage_seconds: dict[str, float] = {}
    reference_summaries: dict[int, torch.Tensor] = {}
    reference_out_of_range: set[int] = set()
    output_summaries: dict[int, torch.Tensor] = {}
    quality_enabled = settings.get("preset") in {"fast", "standard"} and not settings.get(
        "development_disable_inline_quality", False
    )
    quality_fidelity = FidelityAccumulator()
    quality_references: dict[int, torch.Tensor] = {}
    quality_seconds = 0.0
    sentinel = object()
    restore_stage: Any = next((stage for stage in stages if stage.name == "restore"), None)
    restore_windows = (
        plan_restore_clips(
            source_start,
            source_end,
            restore_stage.clip_length,
            restore_stage.clip_overlap,
            set(manifest.get("scene_cuts", [])),
        )
        if restore_stage is not None
        else []
    )
    oom_retries = 0

    def check() -> bool:
        return stopped.is_set() or abort()

    def put(q: queue.Queue, item: Any) -> None:
        while not check():
            try:
                q.put(item, timeout=0.1)
                return
            except queue.Full:
                pass
        raise InterruptedError("The segment was interrupted.")

    def get(q: queue.Queue):
        while not check():
            try:
                return q.get(timeout=0.1)
            except queue.Empty:
                pass
        raise InterruptedError("The segment was interrupted.")

    def guard(fn: Callable[[], None]) -> None:
        try:
            with torch.inference_mode():
                fn()
        except BaseException as error:
            errors.append(error)
            stopped.set()

    def decode() -> None:
        nonlocal decode_seconds, reference_check_seconds
        decode_started = time.perf_counter()
        decoder = IndexedDecoder(manifest["input"]["path"], media, backend, manifest)
        try:
            indices = manifest["cfr_map"][source_start:source_end]
            iterator = decoder.frames(indices, check)
            pending: list[torch.Tensor] = []
            positions: list[int] = []
            for index, frame in zip(range(source_start, source_end), iterator, strict=True):
                if quality_enabled and start <= index < end and index * factor % STRIDE == 0:
                    quality_references[index] = frame
                pending.append(frame)
                positions.append(index)
                if len(pending) == batch_size:
                    check_started = time.perf_counter()
                    batch = FrameBatch(
                        torch.stack(pending),
                        tuple(Fraction(i) / rate for i in positions),
                        tuple(positions),
                    )
                    summaries = summarize_frames(batch.frames)
                    reference_summaries.update(zip(batch.indices, summaries.cpu(), strict=True))
                    reference_out_of_range.update(
                        batch.indices[position]
                        for position in reference_range_positions(batch.frames)
                    )
                    reference_check_seconds += time.perf_counter() - check_started
                    if backend == "cuda":
                        torch.cuda.synchronize()
                    put(decoded, batch)
                    pending, positions = [], []
            if pending:
                check_started = time.perf_counter()
                batch = FrameBatch(
                    torch.stack(pending),
                    tuple(Fraction(i) / rate for i in positions),
                    tuple(positions),
                )
                summaries = summarize_frames(batch.frames)
                reference_summaries.update(zip(batch.indices, summaries.cpu(), strict=True))
                reference_out_of_range.update(
                    batch.indices[position] for position in reference_range_positions(batch.frames)
                )
                reference_check_seconds += time.perf_counter() - check_started
                if backend == "cuda":
                    torch.cuda.synchronize()
                put(decoded, batch)
            put(decoded, sentinel)
        finally:
            decoder.close()
            decode_seconds += time.perf_counter() - decode_started

    def apply_stage(stage: Any, batch: FrameBatch) -> FrameBatch:
        stage_started = time.perf_counter()
        result = stage.process(batch)
        stage_seconds[stage.name] = stage_seconds.get(stage.name, 0.0) + (
            time.perf_counter() - stage_started
        )
        return result

    def record_quality(result: FrameBatch, owned_start: int, owned_end: int) -> FrameBatch:
        nonlocal quality_seconds
        if quality_enabled:
            metric_started = time.perf_counter()
            for position, index in enumerate(result.indices):
                if (
                    owned_start * factor <= index < owned_end * factor
                    and index % factor == 0
                    and index % STRIDE == 0
                ):
                    quality_fidelity.add(
                        quality_references.pop(index // factor), result.frames[position]
                    )
            quality_seconds += time.perf_counter() - metric_started
        return result

    def validate_handoff(
        source: FrameBatch,
        interpolation_input: FrameBatch | None,
        result: FrameBatch,
        retry_clip: Callable[[], FrameBatch],
        retry_pair: Callable[[int], FrameBatch] | None,
        owned_start: int,
        owned_end: int,
    ) -> FrameBatch:
        """Validate final compute output, retry its producing unit once, then fall back."""
        nonlocal handoff_check_seconds, corruption_retries, corruption_fallbacks, quality_seconds
        check_started = time.perf_counter()

        def flagged_positions(candidate: FrameBatch) -> list[int]:
            reference_indices = [index // factor for index in candidate.indices]
            if any(index not in reference_summaries for index in reference_indices):
                raise RuntimeError("No decoded reference summary for compute output.")
            references: list[torch.Tensor] = []
            input_range_flags: list[bool] = []
            for index, reference_index in zip(candidate.indices, reference_indices, strict=True):
                reference = reference_summaries[reference_index]
                outside = reference_index in reference_out_of_range
                if (
                    factor == 2
                    and index % 2
                    and index + 1 in candidate.indices
                    and reference_index + 1 in reference_summaries
                    and reference_index + 1 not in source_cuts
                ):
                    reference = (reference + reference_summaries[reference_index + 1]) * 0.5
                    outside |= reference_index + 1 in reference_out_of_range
                references.append(reference)
                input_range_flags.append(outside)
            reference = torch.stack(references)
            summary = summarize_frames(candidate.frames)
            # At clip/video boundaries, an output neighbor is unavailable.
            # Its aligned source summary supplies a conservative comparison
            # so an in-range flash at an endpoint cannot escape the check.
            temporal = [
                position - 1
                for position in detect_frame_outliers(
                    torch.cat(
                        (
                            reference[:1].to(summary.device),
                            summary,
                            reference[-1:].to(summary.device),
                        )
                    ),
                    torch.cat((reference[:1], reference, reference[-1:])),
                    scene_ids=[
                        bisect_right(source_cuts, index // factor)
                        for index in (
                            candidate.indices[0],
                            *candidate.indices,
                            candidate.indices[-1],
                        )
                    ],
                )
            ]
            return sorted(
                set(temporal) | set(invalid_frame_positions(candidate.frames, input_range_flags))
            )

        flagged = flagged_positions(result)
        raw_flag_indices.update(
            result.indices[position]
            for position in flagged
            if start * factor <= result.indices[position] < end * factor
        )
        if not flagged:
            handoff_check_seconds += time.perf_counter() - check_started
            return record_quality(result, owned_start, owned_end)

        even_flags = [position for position in flagged if result.indices[position] % factor == 0]
        odd_flags = [position for position in flagged if result.indices[position] % factor != 0]
        if even_flags or retry_pair is None or interpolation_input is None:
            corruption_retries += 1
            result = retry_clip()
        else:
            # RIFE's odd output positions belong to one source-frame pair.
            corruption_retries += len(odd_flags)
            frames = result.frames.clone()
            for position in odd_flags:
                output_index = result.indices[position]
                retried = retry_pair(output_index // factor)
                try:
                    retry_position = retried.indices.index(output_index)
                except ValueError:
                    continue
                frames[position] = retried.frames[retry_position]
            result = FrameBatch(frames, result.timestamps, result.indices)

        persistent = flagged_positions(result)
        # A repaired context endpoint can reveal an anomaly in its inserted
        # neighbor. Re-check and apply the same policy to that newly flagged frame.
        for _repair_pass in range(2):
            if not persistent:
                break
            frames = result.frames.clone()
            output_positions = {index: position for position, index in enumerate(result.indices)}
            # Restore source-aligned frames first, so a flagged inserted frame
            # can blend the repaired, valid endpoints rather than corrupt data.
            for position in sorted(persistent, key=lambda pos: result.indices[pos] % factor):
                output_index = result.indices[position]
                if factor == 2 and output_index % 2:
                    left = output_positions[output_index - 1]
                    right = output_positions.get(output_index + 1)
                    if right is None and output_index // factor != count - 1:
                        if not owned_start * factor <= output_index < owned_end * factor:
                            continue  # Discarded terminal context has no inserted midpoint.
                        raise RuntimeError("Flagged owned RIFE frame has no right endpoint.")
                    frames[position] = (
                        frames[left] + frames[left if right is None else right]
                    ) * 0.5
                    action = "endpoint_blend_50_50"
                else:
                    input_index = output_index // factor
                    source_position = source.indices.index(input_index)
                    faithful = FrameBatch(
                        source.frames[source_position : source_position + 1],
                        (source.timestamps[source_position],),
                        (input_index,),
                    )
                    frames[position] = (
                        ResizeStage(*output_size(settings, media))
                        .process(faithful)
                        .frames[0]
                        .to(frames.dtype)
                    )
                    action = "source_frame_resize"
                corruption_fallbacks += 1
                corruption_events.append(
                    {
                        "stage": "rife" if output_index % factor else "restore",
                        "frame_index": output_index,
                        "action": action,
                    }
                )
            result = FrameBatch(frames, result.timestamps, result.indices)
            persistent = flagged_positions(result)

        postrepair_flag_indices.update(
            result.indices[pos]
            for pos in persistent
            if owned_start * factor <= result.indices[pos] < owned_end * factor
        )
        handoff_check_seconds += time.perf_counter() - check_started
        return record_quality(result, owned_start, owned_end)

    def compute() -> None:
        nonlocal oom_retries
        if restore_stage is not None:
            active_restore: Any = restore_stage
            frame_cache = StreamingClipBuffer()
            source_cursor = source_start
            decoder_finished = False

            def fill_until(target: int) -> None:
                nonlocal source_cursor, decoder_finished
                while source_cursor < target and not decoder_finished:
                    decoded_batch = get(decoded)
                    if decoded_batch is sentinel:
                        decoder_finished = True
                        break
                    frame_cache.add(decoded_batch)
                    source_cursor = decoded_batch.indices[-1] + 1

            def restore_with_retry(batch: FrameBatch, clip: RestoreClip) -> FrameBatch:
                nonlocal oom_retries
                try:
                    return apply_stage(active_restore, batch)
                except torch.cuda.OutOfMemoryError:
                    clip_frames = len(batch.indices)
                    minimum = 2 * active_restore.clip_overlap + 1
                    retry_length = max(minimum, (clip_frames + 1) // 2)
                    if retry_length >= clip_frames:
                        raise RuntimeError(
                            f"Job {manifest.get('id')} segment {segment['index']}: "
                            f"BasicVSR++ exhausted GPU memory on a {clip_frames}-frame clip; "
                            "reduce the configured clip length or free GPU memory."
                        ) from None
                    oom_retries += 1
                    logger.warning(
                        "Job %s segment %s: CUDA OOM on %d-frame clip; retrying once with "
                        "%d-frame clips.",
                        manifest.get("id"),
                        segment["index"],
                        clip_frames,
                        retry_length,
                    )
                    torch.cuda.empty_cache()
                    retry_clips = plan_restore_clips(
                        batch.indices[0],
                        batch.indices[-1] + 1,
                        retry_length,
                        min(active_restore.clip_overlap, (retry_length - 1) // 2),
                    )
                    pieces: list[FrameBatch] = []
                    for retry_clip in retry_clips:
                        positions = [
                            pos
                            for pos, index in enumerate(batch.indices)
                            if retry_clip.start <= index < retry_clip.end
                        ]
                        part = FrameBatch(
                            batch.frames[positions],
                            tuple(batch.timestamps[pos] for pos in positions),
                            tuple(batch.indices[pos] for pos in positions),
                        )
                        restored = apply_stage(active_restore, part)
                        owners = [
                            pos
                            for pos, index in enumerate(restored.indices)
                            if retry_clip.owned_start <= index < retry_clip.owned_end
                        ]
                        pieces.append(
                            FrameBatch(
                                restored.frames[owners],
                                tuple(restored.timestamps[pos] for pos in owners),
                                tuple(restored.indices[pos] for pos in owners),
                            )
                        )
                    merged = FrameBatch(
                        torch.cat([piece.frames for piece in pieces]),
                        tuple(t for piece in pieces for t in piece.timestamps),
                        tuple(i for piece in pieces for i in piece.indices),
                    )
                    return merged

            for clip_index, clip in enumerate(restore_windows):
                if check():
                    raise InterruptedError("The segment was interrupted.")
                if (
                    getattr(active_restore, "single_frame", False)
                    and factor == 2
                    and clip.end < source_end
                    and clip.end not in source_cuts
                ):
                    # Single-frame adapters still supply RIFE's following-frame
                    # context; ownership stays with the original one-frame clip.
                    clip = RestoreClip(clip.start, clip.end + 1, clip.owned_start, clip.owned_end)
                fill_until(clip.end)
                try:
                    clip_batch = frame_cache.build(clip)
                except KeyError:
                    raise RuntimeError(
                        f"Job {manifest.get('id')} segment {segment['index']}: "
                        f"decoder ended before restoration clip [{clip.start}, {clip.end})."
                    ) from None
                transformed = restore_with_retry(clip_batch, clip)
                interpolation_input: FrameBatch | None = None
                stage_input: FrameBatch | None = None
                interpolation_stage: Any | None = next(
                    (stage for stage in stages if stage.name == "rife"), None
                )
                for stage in stages:
                    if stage is active_restore:
                        continue
                    stage_input = transformed
                    if stage is interpolation_stage:
                        interpolation_input = stage_input
                    transformed = apply_stage(stage, stage_input)

                def retry_clip(
                    clip_batch: FrameBatch = clip_batch,
                    clip: RestoreClip = clip,
                    active_restore: Any = active_restore,
                ) -> FrameBatch:
                    retried = restore_with_retry(clip_batch, clip)
                    for retry_stage in stages:
                        if retry_stage is active_restore:
                            continue
                        retried = apply_stage(retry_stage, retried)
                    return retried

                def retry_pair(
                    left_index: int,
                    interpolation_input: FrameBatch | None = interpolation_input,
                    interpolation_stage: Any | None = interpolation_stage,
                ) -> FrameBatch:
                    if interpolation_input is None or interpolation_stage is None:
                        raise RuntimeError("RIFE retry requested without an interpolation input.")
                    try:
                        left_position = interpolation_input.indices.index(left_index)
                    except ValueError:
                        raise RuntimeError("RIFE retry pair is outside the current clip.") from None
                    right_position = min(left_position + 1, len(interpolation_input.indices) - 1)
                    pair = FrameBatch(
                        interpolation_input.frames[left_position : right_position + 1],
                        interpolation_input.timestamps[left_position : right_position + 1],
                        interpolation_input.indices[left_position : right_position + 1],
                    )
                    return apply_stage(interpolation_stage, pair)

                transformed = validate_handoff(
                    clip_batch,
                    interpolation_input,
                    transformed,
                    retry_clip,
                    retry_pair if interpolation_stage is not None else None,
                    max(start, clip.owned_start),
                    min(end, clip.owned_end),
                )
                owned = [
                    pos
                    for pos, index in enumerate(transformed.indices)
                    if max(start, clip.owned_start) * factor
                    <= index
                    < min(end, clip.owned_end) * factor
                ]
                if owned:
                    owned_batch = FrameBatch(
                        transformed.frames[owned],
                        tuple(transformed.timestamps[pos] for pos in owned),
                        tuple(transformed.indices[pos] for pos in owned),
                    )
                    if backend == "cuda":
                        torch.cuda.synchronize()
                    put(processed, owned_batch)
                    del owned_batch
                next_start = (
                    restore_windows[clip_index + 1].start
                    if clip_index + 1 < len(restore_windows)
                    else source_end
                )
                frame_cache.release_before(next_start)
                # Retry defaults and stage_input otherwise retain the previous
                # full-resolution clip throughout the next restoration call.
                del retry_clip, retry_pair, interpolation_input, stage_input
                del transformed, clip_batch
            # Drain the decoder sentinel so the producer can close cleanly.
            while not decoder_finished:
                item = get(decoded)
                if item is sentinel:
                    decoder_finished = True
            put(processed, sentinel)
            return

        current = get(decoded)
        while current is not sentinel:
            following = get(decoded)
            batch = current
            own = len(batch.indices)
            if context_after and following is not sentinel:
                frames = torch.cat((batch.frames, following.frames[:context_after]))
                batch = FrameBatch(
                    frames,
                    batch.timestamps + following.timestamps[:context_after],
                    batch.indices + following.indices[:context_after],
                )
            input_batch = batch
            interpolation_input: FrameBatch | None = None
            interpolation_stage = next(
                (stage for stage in stages if stage.name in {"rife", "blend2x"}), None
            )
            for stage in stages:
                stage_input = batch
                if stage is interpolation_stage:
                    interpolation_input = stage_input
                batch = apply_stage(stage, stage_input)

            def retry_clip_without_restore(
                input_batch: FrameBatch = input_batch,
                stages: list[Any] = stages,
            ) -> FrameBatch:
                retried = input_batch
                for retry_stage in stages:
                    retried = apply_stage(retry_stage, retried)
                return retried

            def retry_pair_without_restore(
                left_index: int,
                interpolation_input: FrameBatch | None = interpolation_input,
                interpolation_stage: Any | None = interpolation_stage,
            ) -> FrameBatch:
                if interpolation_input is None or interpolation_stage is None:
                    raise RuntimeError("Interpolation retry requested without an input pair.")
                try:
                    left_position = interpolation_input.indices.index(left_index)
                except ValueError:
                    raise RuntimeError(
                        "Interpolation retry pair is outside the current batch."
                    ) from None
                right_position = min(left_position + 1, len(interpolation_input.indices) - 1)
                pair = FrameBatch(
                    interpolation_input.frames[left_position : right_position + 1],
                    interpolation_input.timestamps[left_position : right_position + 1],
                    interpolation_input.indices[left_position : right_position + 1],
                )
                return apply_stage(interpolation_stage, pair)

            batch = validate_handoff(
                input_batch,
                interpolation_input,
                batch,
                retry_clip_without_restore,
                retry_pair_without_restore if interpolation_stage is not None else None,
                max(start, input_batch.indices[0]),
                min(end, input_batch.indices[0] + own),
            )
            # Clip context output and keep interpolation owned by its left frame.
            mask = [
                position
                for position, index in enumerate(batch.indices[: own * factor])
                if start * factor <= index < end * factor
            ]
            if mask:
                batch = FrameBatch(
                    batch.frames[mask],
                    tuple(batch.timestamps[p] for p in mask),
                    tuple(batch.indices[p] for p in mask),
                )
                if backend == "cuda":
                    torch.cuda.synchronize()
                put(processed, batch)
            current = following
        put(processed, sentinel)

    def encode() -> None:
        nonlocal written, peak_rss, encode_seconds
        encoder = Encoder(
            output_path,
            *output_size(settings, media),
            output_rate(settings, media),
            settings.get("codec", "hevc"),
            backend,
            media,
            settings.get("lossless", False),
        )
        try:
            while True:
                batch = get(processed)
                if batch is sentinel:
                    break
                summaries = summarize_frames(batch.frames).cpu()
                output_indices = tuple(
                    range(start * factor + written, start * factor + written + len(batch.indices))
                )
                output_summaries.update(zip(output_indices, summaries, strict=True))
                for frame in batch.frames:
                    if check():
                        raise InterruptedError("The segment was interrupted.")
                    encode_started = time.perf_counter()
                    encoder.write(frame)
                    encode_seconds += time.perf_counter() - encode_started
                    written += 1
                peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
            encode_started = time.perf_counter()
            encoder.finish()
            encode_seconds += time.perf_counter() - encode_started
        except BaseException:
            encoder.abort()
            raise

    workers = [
        threading.Thread(target=guard, args=(fn,), daemon=True) for fn in (decode, compute, encode)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    for stage in stages:
        stage.teardown()
    memory_samples = memory_sampler.stop()
    if errors:
        primary = next((e for e in errors if not isinstance(e, InterruptedError)), errors[0])
        raise primary
    if written != (end - start) * factor:
        raise RuntimeError(
            f"Segment {segment['index']} encoded {written} frames instead of "
            f"{(end - start) * factor}. Retry the segment."
        )
    ordered_output = sorted(output_summaries)
    aligned_reference = []
    for index in ordered_output:
        source_index = index // factor
        reference = reference_summaries[source_index]
        if (
            factor == 2
            and index % 2
            and source_index + 1 in reference_summaries
            and source_index + 1 not in source_cuts
        ):
            reference = (reference + reference_summaries[source_index + 1]) * 0.5
        aligned_reference.append(reference)
    flagged_positions = detect_frame_outliers(
        torch.stack([output_summaries[index] for index in ordered_output]),
        torch.stack(aligned_reference),
        scene_ids=[bisect_right(source_cuts, index // factor) for index in ordered_output],
    )
    final_flag_indices = postrepair_flag_indices | {
        ordered_output[pos] for pos in flagged_positions
    }
    inline_quality = None
    if quality_enabled:
        metric_started = time.perf_counter()
        clip_joints = {
            clip.owned_start for clip in restore_windows if start < clip.owned_start < end
        }
        source_joints = clip_joints | {s["start"] for s in manifest.get("segments", [])[1:]}
        source_excluded = {i for cut in source_cuts for i in (cut - 1, cut, cut + 1) if i >= 0}
        inline_quality = {
            "fidelity": quality_fidelity.partial(),
            "source": temporal_partial(
                {i: v for i, v in reference_summaries.items() if start <= i < end},
                source_joints,
                source_excluded,
            ),
            "output": temporal_partial(
                output_summaries,
                {i * factor for i in source_joints},
                {i * factor + p for i in source_excluded for p in range(factor)},
            ),
        }
        quality_seconds += time.perf_counter() - metric_started
    elapsed = time.perf_counter() - started
    return {
        "inline_quality": inline_quality,
        "inline_quality_seconds": quality_seconds,
        "seconds": elapsed,
        "input_frames": end - start,
        "output_frames": written,
        "fps": (end - start) / elapsed,
        "decode_seconds": decode_seconds,
        "stage_seconds": stage_seconds,
        "clip_joints": [
            clip.owned_start for clip in restore_windows if start < clip.owned_start < end
        ],
        "encode_seconds": encode_seconds,
        "handoff_check_seconds": handoff_check_seconds + reference_check_seconds,
        "pipeline_queue_size": queue_size,
        "peak_rss_bytes": peak_rss,
        "peak_torch_vram_bytes": torch.cuda.max_memory_reserved() if backend == "cuda" else 0,
        "memory_samples": memory_samples,
        "interpolation_fallbacks": sum(
            int(getattr(stage, "fallback_count", 0)) for stage in stages
        ),
        "nan_retries": sum(int(getattr(stage, "nan_retries", 0)) for stage in stages),
        "oom_retries": oom_retries,
        "corruption_retries": corruption_retries,
        "corruption_fallbacks": corruption_fallbacks,
        "corruption_events": corruption_events,
        "raw_flag_count": len(raw_flag_indices),
        "raw_flag_scope": (
            "Unique pre-repair compute indices, including clip context within the segment."
        ),
        "final_flag_count": len(final_flag_indices),
        "raw_luma_outliers": [
            {"frame_index": index, "timestamp_seconds": index / float(output_rate(settings, media))}
            for index in sorted(raw_flag_indices)
        ],
        "luma_outliers": [
            {
                "frame_index": index,
                "timestamp_seconds": index / float(output_rate(settings, media)),
            }
            for index in sorted(final_flag_indices)
        ],
    }
