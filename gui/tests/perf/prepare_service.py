"""Create a private synthetic fixture and measure a real running Standard job."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from service import measure

from videoenhancer.config import executable
from videoenhancer.jobs.store import JobStore, add_job
from videoenhancer.proc import run


def prepare(root: Path, model_home: Path) -> dict:
    if root.exists():
        raise ValueError("Use a fresh evidence directory.")
    home = root / "home"
    for model in ("basicvsrpp-ntire21-decompress", "rife-4.25"):
        shutil.copytree(model_home / "models" / model, home / "models" / model)
    shutil.copytree(model_home / "adapter-sources", home / "adapter-sources")
    os.environ["VE_HOME"] = str(home)
    source = root / "synthetic-8s.mp4"
    run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=720x1280:rate=30",
            "-t",
            "8",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-threads",
            "2",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    job = add_job(
        source,
        dict(preset="standard", backend="cuda", short_side=1080, fps="2x", codec="hevc"),
        home=home,
        output=root / "output.mp4",
    )
    store = JobStore(home)
    for index in range(1010):
        clone = copy.deepcopy(job)
        clone.update(
            id=f"perf-{index}",
            state="queued" if index < 10 else "done",
            output=str(root / f"output-{index}.mp4"),
            position=index + 2,
        )
        for segment in clone["segments"]:
            segment["state"] = "pending" if index < 10 else "done"
        store.save(clone)
    command = [
        sys.executable,
        "-c",
        "from videoenhancer.schedule.controller import run_queue; "
        f"run_queue(home={str(home)!r},ignore_schedule=True,job_ids={{{job['id']!r}}})",
    ]
    with (root / "controller.log").open("w", encoding="utf-8") as log:
        worker = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            while store.load(job["id"])["state"] != "running":
                if worker.poll() is not None:
                    raise RuntimeError("The real controller stopped before measurement.")
                time.sleep(0.25)
            result = measure(home, root / "results.json")
            while store.load(job["id"])["state"] != "done":
                if worker.poll() is not None or store.load(job["id"])["state"] == "failed":
                    raise RuntimeError("The fixture job did not finish.")
                time.sleep(0.25)
            return result
        finally:
            worker.terminate()
            worker.wait(timeout=30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--model-home", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root.resolve(), args.model_home.resolve())), flush=True)
