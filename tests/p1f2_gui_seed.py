"""Isolated synthetic GUI records for the P1f-2 acceptance checks."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from videoenhancer.config import executable
from videoenhancer.jobs.store import JobStore, add_job
from videoenhancer.models.registry import ModelRegistry
from videoenhancer.service.settings import save_settings


def seed(root: Path, large: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    home = root / "home"
    source = root / "synthetic.mp4"
    subprocess.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30",
            "-t",
            "4",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-movflags",
            "+faststart",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    settings = dict(backend="cpu", preset="fast", short_side="keep", fps="off", codec="h264")
    store = JobStore(home)
    done = add_job(source, settings, root / "output.mp4", home, job_id="a" * 32)
    done.update(state="done", output=str(source), finished_at=done["updated_at"])
    store.save(done)
    save_settings(home, dict(tour_completed=True, tray_explained=True, cleanup_working_files=False))
    ModelRegistry(home)
    if not large:
        for job_id, bad in [("b" * 32, False), ("c" * 32, True)]:
            job = dict(
                done,
                id=job_id,
                state="failed",
                input={"path": str(root / ("damaged-record.mkv" if bad else "unknown-fps.mkv"))},
                output=str(root / f"{job_id}.mp4"),
                error="Synthetic download failed",
                segments=[],
                source=None
                if bad
                else dict(url="http://localhost/video", id="v", extractor="generic", format="v"),
                download=dict(phase="Download failed"),
            )
            for key in [
                "analysis_file",
                "cfr_map",
                "source_pts",
                "keyframes",
                "scene_cuts",
                "motion_scores",
            ]:
                job.pop(key, None)
            job["media"] = dict(
                display_width=-1 if bad else 0,
                display_height=180 if bad else 0,
                width=-1 if bad else 0,
                height=180 if bad else 0,
                cfr_fps="30" if bad else "0",
                duration=2,
                frame_count=60,
            )
            store.save(job)
        return
    old = root / "old"
    old.mkdir()
    filler = home / "cache/synthetic-storage"
    filler.mkdir(parents=True)
    entries = []
    block = b"x" * 16384
    digest = hashlib.sha256(block).hexdigest()
    for index in range(10000):
        name = f"fixture-{index:05}.bin"
        (old / name).write_bytes(block)
        entries.append(dict(path=name, size=len(block), sha256=digest))
    for index in range(2000):
        (filler / f"small-{index:05}.bin").write_bytes(b"synthetic")
    (root / "pointer.json").write_text(
        json.dumps(dict(active=str(home), previous=str(old), manifest=entries))
    )


if __name__ == "__main__":
    seed(Path(sys.argv[1]), len(sys.argv) > 2 and sys.argv[2] == "large")
