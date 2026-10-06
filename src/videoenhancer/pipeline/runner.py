"""Three overlapped workers with bounded queues and rational frame ownership."""

import queue
import threading
import time
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import psutil
import torch

from videoenhancer.media.decode import IndexedDecoder, choose_backend
from videoenhancer.media.encode import Encoder
from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.pipeline.presets import create_stages
from videoenhancer.pipeline.stages import FrameBatch


def process_segment(
    manifest: dict[str, Any],
    segment: dict[str, Any],
    output_path: Path,
    abort: Callable[[], bool],
    batch_size: int = 2,
) -> dict[str, Any]:
    started = time.perf_counter()
    settings, media = manifest["settings"], manifest["media"]
    backend = choose_backend(settings.get("backend", "auto"))
    torch.set_num_threads(2)
    if backend == "cuda":
        torch.cuda.reset_peak_memory_stats()
    stages = create_stages(settings, media, set(manifest.get("scene_cuts", [])))
    for stage in stages:
        stage.setup()
    context_before = sum(s.context_before for s in stages)
    context_after = sum(s.context_after for s in stages)
    start, end = segment["start"], segment["end"]
    count = len(manifest["cfr_map"])
    source_start, source_end = max(0, start - context_before), min(count, end + context_after)
    rate = Fraction(media["cfr_fps"])
    factor = int(output_rate(settings, media) / rate)
    # Two queue slots, two-frame batches, and at most one context frame keep
    # full-resolution tensors bounded independently of video duration.
    decoded: queue.Queue[Any] = queue.Queue(maxsize=2)
    processed: queue.Queue[Any] = queue.Queue(maxsize=2)
    stopped = threading.Event()
    errors: list[BaseException] = []
    written = 0
    peak_rss = 0
    sentinel = object()

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
        decoder = IndexedDecoder(manifest["input"]["path"], media, backend, manifest)
        try:
            indices = manifest["cfr_map"][source_start:source_end]
            iterator = decoder.frames(indices, check)
            pending: list[torch.Tensor] = []
            positions: list[int] = []
            for index, frame in zip(range(source_start, source_end), iterator, strict=True):
                pending.append(frame)
                positions.append(index)
                if len(pending) == batch_size:
                    batch = FrameBatch(
                        torch.stack(pending),
                        tuple(Fraction(i) / rate for i in positions),
                        tuple(positions),
                    )
                    if backend == "cuda":
                        torch.cuda.synchronize()
                    put(decoded, batch)
                    pending, positions = [], []
            if pending:
                batch = FrameBatch(
                    torch.stack(pending),
                    tuple(Fraction(i) / rate for i in positions),
                    tuple(positions),
                )
                if backend == "cuda":
                    torch.cuda.synchronize()
                put(decoded, batch)
            put(decoded, sentinel)
        finally:
            decoder.close()

    def compute() -> None:
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
            for stage in stages:
                batch = stage.process(batch)
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
        nonlocal written, peak_rss
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
                for frame in batch.frames:
                    if check():
                        raise InterruptedError("The segment was interrupted.")
                    encoder.write(frame)
                    written += 1
                peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
            encoder.finish()
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
    if errors:
        primary = next((e for e in errors if not isinstance(e, InterruptedError)), errors[0])
        raise primary
    if written != (end - start) * factor:
        raise RuntimeError(
            f"Segment {segment['index']} encoded {written} frames instead of "
            f"{(end - start) * factor}. Retry the segment."
        )
    elapsed = time.perf_counter() - started
    return {
        "seconds": elapsed,
        "input_frames": end - start,
        "output_frames": written,
        "fps": (end - start) / elapsed,
        "peak_rss_bytes": peak_rss,
        "peak_torch_vram_bytes": torch.cuda.max_memory_reserved() if backend == "cuda" else 0,
    }
