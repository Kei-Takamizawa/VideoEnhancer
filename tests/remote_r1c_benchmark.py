"""Measure sidecar generation for a bounded synthetic 10-minute 1080p clip."""

import argparse
import json
import time
from pathlib import Path

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.remote.library import Library
from videoenhancer.remote.thumbnails import Thumbnails


def run(work):
    root = (work / "scratch/r1c/benchmark").resolve()
    assert root.is_relative_to((work / "scratch").resolve())
    folder = root / "library"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "synthetic.mp4"
    proc.run(
        [
            executable("ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x346789:s=1920x1080:r=30:d=600,"
            "drawgrid=width=160:height=90:thickness=2:color=white",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-threads",
            "2",
            "-g",
            "60",
            "-crf",
            "28",
            str(source),
        ],
        capture_output=True,
        check=True,
        timeout=300,
    )
    assert source.stat().st_size < 100_000_000
    library = Library(root / "home", folder)
    images = Thumbnails(library)
    identifier = library._identifier(source)
    start = time.perf_counter()
    index = images.generate(identifier)
    seconds = time.perf_counter() - start
    sizes = {p.name: p.stat().st_size for p in images._folder(identifier).iterdir()}
    result = dict(
        fixture="Synthetic static grid, H.264 1920x1080, 30 fps, 600 seconds, GOP 60",
        seconds=seconds,
        source_bytes=source.stat().st_size,
        files=sizes,
        total_sidecar_bytes=sum(sizes.values()),
        index=index,
    )
    evidence = work / "evidence/VE-R1c"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().work.resolve(strict=True)), indent=2))
