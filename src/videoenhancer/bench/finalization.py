"""Short generated concat/mux + exact validation calibration, without model inference."""

from __future__ import annotations

import itertools
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.media.mux import assemble
from videoenhancer.media.probe import probe


def fit_finalization(samples: list[dict[str, Any]]) -> dict[str, Any]:
    # Enumerate active sets for a three-variable nonnegative least-squares fit.
    matrix = np.array([[1, s["output_bytes"], s["output_frames"]] for s in samples], dtype=float)
    observed = np.array([s["seconds"] for s in samples])
    scale = np.maximum(matrix.max(axis=0), 1)
    normalized = matrix / scale
    best = np.zeros(3)
    error = float("inf")
    for count in range(1, 4):
        for columns in itertools.combinations(range(3), count):
            values = np.linalg.lstsq(normalized[:, columns], observed, rcond=None)[0]
            if (values < 0).any():
                continue
            coefficients = np.zeros(3)
            coefficients[list(columns)] = values
            residual = float(((normalized @ coefficients - observed) ** 2).sum())
            if residual < error:
                best, error = coefficients, residual
    a, b, c = (best / scale).tolist()
    return dict(
        status="measured",
        a=a,
        b=b,
        c=c,
        samples=samples,
        rms_seconds=float(np.sqrt(error / len(samples))),
        method="Nonnegative least squares: startup + output bytes + packet-count frames.",
    )


def calibrate_finalization(directory: Path) -> dict[str, Any]:
    samples = []
    with tempfile.TemporaryDirectory(prefix="finalize-", dir=directory) as temporary:
        root = Path(temporary)
        for count, width, height in (
            (30, 96, 64),
            (300, 96, 64),
            (30, 720, 1280),
            (300, 720, 1280),
        ):
            clip = root / "clip.mp4"
            proc.run(
                [
                    executable("ffmpeg"),
                    "-v",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"testsrc2=size={width}x{height}:rate=30",
                    "-frames:v",
                    str(count),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-threads",
                    "2",
                    "-pix_fmt",
                    "yuv420p",
                    str(clip),
                ],
                check=True,
                capture_output=True,
            )
            info = probe(clip).to_dict()
            for index in range(3):
                shutil.copyfile(clip, root / f"seg_{index:05d}.mp4")
            for repeat in range(2):
                output = root / "out.mp4"
                output.unlink(missing_ok=True)
                job = dict(
                    input={"path": str(clip)},
                    media=info,
                    output=str(output),
                    cfr_map=list(range(count * 3)),
                    settings=dict(preset="passthrough", fps="off", codec="h264", short_side="keep"),
                    segments=[
                        dict(index=i, start=i * count, end=(i + 1) * count) for i in range(3)
                    ],
                )
                started = time.perf_counter()
                boundaries = []
                assemble(
                    job,
                    root,
                    validation_started=lambda boundaries=boundaries: boundaries.append(
                        time.perf_counter()
                    ),
                )
                ended = time.perf_counter()
                samples.append(
                    dict(
                        output_bytes=output.stat().st_size,
                        output_frames=count * 3,
                        seconds=ended - started,
                        assembling_seconds=boundaries[0] - started,
                        validating_seconds=ended - boundaries[0],
                        repeat=repeat,
                    )
                )
    return fit_finalization(samples)
