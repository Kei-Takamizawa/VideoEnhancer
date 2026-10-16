"""Seed a small real CPU job and a paused job for the opt-in cross-volume GUI gate."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from videoenhancer.config import executable
from videoenhancer.jobs.store import JobStore, add_job
from videoenhancer.models.registry import RIFE, ModelRegistry
from videoenhancer.schedule.controller import run_queue
from videoenhancer.service.settings import save_settings


def seed(root: Path, model_home: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    home = root / "home"
    source = root / "synthetic.mp4"
    subprocess.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=96x64:rate=12",
            "-frames:v",
            "12",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    settings = {
        "preset": "passthrough",
        "backend": "cpu",
        "short_side": "keep",
        "fps": "off",
        "codec": "h264",
    }
    finished = add_job(source, settings, root / "finished.mp4", home, job_id="finished")
    run_queue(ignore_schedule=True, home=home, job_ids={finished["id"]})
    store = JobStore(home)
    assert store.load("finished")["state"] == "done"
    add_job(source, settings, root / "resumed.mp4", home, job_id="paused")
    store.set_state("paused", "paused")
    registry = ModelRegistry(home)
    installed = registry.manifest(RIFE)
    src_registry = ModelRegistry(model_home)
    weight = src_registry.weights(src_registry.manifest(RIFE), download=False)
    shutil.copy2(weight, registry.folder(RIFE) / installed["weights"]["filename"])
    save_settings(
        home, {"tour_completed": True, "tray_explained": True, "cleanup_working_files": False}
    )
    (root / "seed.json").write_text(json.dumps({"home": str(home), "source": str(source)}))


if __name__ == "__main__":
    seed(Path(sys.argv[1]), Path(sys.argv[2]))
