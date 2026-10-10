"""CPU-only previews of durable results; never acquires the GPU work lease."""

from fractions import Fraction
from pathlib import Path
from typing import Any

import torch

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.media.decode import IndexedDecoder
from videoenhancer.media.encode import Encoder
from videoenhancer.media.timing import output_rate, output_size
from videoenhancer.pipeline.stages import FrameBatch, ResizeStage


def render_result_preview(job: dict[str, Any], job_dir: Path, folder: Path) -> dict[str, Any]:
    segment = next((s for s in job["segments"] if s["state"] == "done"), None)
    if segment is None:
        raise ValueError("The first completed step is not ready yet.")
    rate = Fraction(job["media"]["cfr_fps"])
    output_fps = output_rate(job["settings"], job["media"])
    factor = int(output_fps / rate)
    first = segment["start"]
    last = min(segment["end"], first + max(1, round(5 * float(rate))))
    width, height = output_size(job["settings"], job["media"])
    decoder = IndexedDecoder(Path(job["input"]["path"]), job["media"], "cpu", job)
    encoder = Encoder(
        folder / "original-preview.mp4", width, height, output_fps, "h264", "cpu", job["media"]
    )
    resize = ResizeStage(width, height)
    try:
        for position, frame in zip(
            range(first, last),
            decoder.frames(job["cfr_map"][first:last], lambda: False),
            strict=True,
        ):
            batch = FrameBatch(torch.stack([frame]), (Fraction(position) / rate,), (position,))
            image = resize.process(batch).frames[0]
            for _ in range(factor):
                encoder.write(image)
        encoder.finish()
    except BaseException:
        encoder.abort()
        raise
    finally:
        decoder.close()
    processed = job_dir / f"seg_{segment['index']:05d}.mp4"
    seek = 0.0
    if not processed.exists():
        if job["state"] != "done":
            raise ValueError("This step's result is unavailable. Wait for the next completed step.")
        processed = Path(job["output"])
        seek = first / float(rate)
    proc.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            "-ss",
            str(seek),
            "-i",
            str(processed),
            "-an",
            "-vf",
            f"fps={output_fps}",
            "-frames:v",
            str((last - first) * factor),
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "2",
            str(folder / "enhanced-preview.mp4"),
        ],
        capture_output=True,
        check=True,
        timeout=60,
    )
    return dict(
        output_fps=float(output_fps),
        input_frames=last - first,
        pipeline=dict(fps=segment.get("stats", {}).get("fps", 0)),
        uses_gpu=False,
        reuses_processed_segment=segment["index"],
    )
