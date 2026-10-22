"""Synthetic, isolated P1f-3 GUI states; no owner data."""

import json
import subprocess
import sys
from pathlib import Path

from videoenhancer.config import executable
from videoenhancer.jobs.store import JobStore, add_job
from videoenhancer.logging import environment_info
from videoenhancer.service.settings import save_settings


def prepare(root: Path, state: str) -> None:
    root.mkdir(parents=True)
    home = root / "home"
    subprocess.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            str(root / "synthetic.mp4"),
        ],
        check=True,
        capture_output=True,
    )
    folder = root / "日本語フォルダ"
    folder.mkdir()
    source = folder / "サンプル「夏」の動画.mp4"
    subprocess.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(root / "synthetic.mp4"),
            "-c",
            "copy",
            "-metadata",
            "title=日本語の題名",
            "-metadata",
            "comment=夏の動画",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    refusal = folder / "日本語・大きい動画.mp4"
    subprocess.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "color=s=2200x1100:r=1",
            "-frames:v",
            "1",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-threads",
            "2",
            str(refusal),
        ],
        check=True,
        capture_output=True,
    )
    store = JobStore(home)
    job = add_job(
        source,
        dict(backend="cpu", preset="fast", short_side="keep", fps="off", codec="h264"),
        root / "output.mp4",
        home,
        job_id="a" * 32,
    )
    job.update(output=str(source), state="done", finished_at=job["updated_at"])
    store.save(job)
    save_settings(
        home,
        dict(
            preset="fast",
            short_side="keep",
            fps="off",
            codec="h264",
            tour_completed=True,
            tray_explained=True,
            cleanup_working_files=False,
        ),
    )
    if state == "failed":
        folder = home / "previews" / ("d" * 32)
        folder.mkdir(parents=True)
        (folder / "state.json").write_text(
            json.dumps(
                dict(
                    id="d" * 32,
                    kind="calibrate",
                    state="failed",
                    created_at="2020-01-01T00:00:00Z",
                    phase="Synthetic old failure",
                    error="Synthetic old failure",
                )
            ),
            encoding="utf-8",
        )
    if state == "driver":
        folder = home / "profiles"
        folder.mkdir()
        (folder / "synthetic.json").write_text(
            json.dumps(
                dict(
                    schema_version=1,
                    backend="cuda",
                    gpu_name=environment_info().get("gpu"),
                    driver="synthetic-old-driver",
                    components={},
                )
            ),
            encoding="utf-8",
        )
    print(json.dumps(dict(source=str(source), refusal=str(refusal)), ensure_ascii=True))


if __name__ == "__main__":
    prepare(Path(sys.argv[1]), sys.argv[2])
