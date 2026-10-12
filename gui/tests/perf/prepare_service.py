"""Generate diagnostic-rich synthetic History, measure repeats, and retain the fixture."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import statistics
import threading
import time
from pathlib import Path

from service import measure

from videoenhancer.config import executable
from videoenhancer.jobs.store import JobStore, add_job, input_identity
from videoenhancer.proc import run
from videoenhancer.schedule.controller import run_queue
from videoenhancer.service.engine import Engine
from videoenhancer.service.server import LocalServer, discovery


def seed_history(
    store: JobStore, template: dict, source: Path, root: Path, start: int, stop: int
) -> None:
    identity = input_identity(source)
    for index in range(start, stop):
        clone = copy.deepcopy(template)
        clone.update(
            id=f"perf-{index}",
            state="queued" if index < 10 else "done",
            input=identity,
            output=str(root / f"output-{index}.mp4"),
            position=index + 2,
        )
        clone.pop("output_identity", None)
        clone.pop("history_hidden_until", None)
        clone.pop("remove_on_cancel", None)
        clone["settings"]["delete_original_after"] = False
        for segment in clone["segments"]:
            segment["state"] = "pending" if index < 10 else "done"
        store.save(clone)


def prepare(root: Path, model_home: Path, history_template: Path, renderer: bool = False) -> dict:
    if root.exists():
        raise ValueError("Use a fresh evidence directory.")
    home = root / "home"
    for model in ("basicvsrpp-ntire21-decompress", "rife-4.25"):
        shutil.copytree(model_home / "models" / model, home / "models" / model)
    shutil.copytree(model_home / "adapter-sources", home / "adapter-sources")
    os.environ["VE_HOME"] = str(home)
    source = root / "synthetic-30s.mp4"
    run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=720x1280:rate=30",
            "-frames:v",
            "900",
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
    template = json.loads(history_template.read_text(encoding="utf-8"))
    if template["state"] != "done" or not any(s.get("stats") for s in template["segments"]):
        raise ValueError("Use a genuinely finished synthetic job with recorded diagnostics.")
    seed_history(store, template, source, root, 0, 1010)
    engine = Engine(home)
    engine._environment()
    engine._home_watcher.start()
    engine.worker = threading.Thread(
        target=lambda: run_queue(
            home=home,
            ignore_schedule=True,
            job_ids={job["id"]},
            stopped=engine.stop.is_set,
            on_progress=engine._progress,
            on_error=engine._error,
        ),
        daemon=True,
    )
    server = LocalServer(engine)
    discovery(home, server.server_port, server.token)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    engine.worker.start()
    threading.Thread(target=engine._deletion_recovery, daemon=True).start()
    try:
        while store.load(job["id"])["state"] != "running":
            if not engine.worker.is_alive():
                raise RuntimeError("The real controller stopped before measurement.")
            time.sleep(0.25)
        samples = []
        for repeat in range(3):
            value = measure(engine, server, root / f"sample-{repeat + 1}.json", history=1000)
            assert value["actual_standard_running"]
            samples.append(value)
        seed_history(store, template, source, root, 1010, 5010)
        # Scaling measures steady state, excluding the newly seeded cold projection.
        projection_started = time.perf_counter()
        engine.event_message()
        projection_seconds = time.perf_counter() - projection_started
        scale = measure(engine, server, root / "scale-5000.json", history=5000)
        values = sorted(sample["one_core_cpu_percent"] for sample in samples)
        result = dict(
            samples=samples,
            median=statistics.median(values),
            p90=values[1] + 0.8 * (values[2] - values[1]),
            scaling_5000=scale,
            scaling_initial_projection_seconds=projection_seconds,
        )
        (root / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if renderer:
            import subprocess

            env = dict(
                os.environ, VE_REAL_ENGINE_HOME=str(home), VE_GUI_EVIDENCE=str(root / "renderer")
            )
            completed = subprocess.run(
                [
                    "node",
                    "node_modules/@playwright/test/cli.js",
                    "test",
                    "tests/perf/real-progress.spec.ts",
                    "--config=playwright.perf.config.ts",
                ],
                cwd="gui",
                env=env,
                capture_output=True,
                text=True,
            )
            (root / "renderer.log").write_text(
                completed.stdout + completed.stderr, encoding="utf-8"
            )
            result["renderer_exit_code"] = completed.returncode
        engine.worker.join()
        final = store.load(job["id"])
        result["job_state"] = final["state"]
        (root / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if final["state"] != "done":
            raise RuntimeError("The real fixture job failed.")
        return result
    finally:
        engine.close()
        server.shutdown()
        server.server_close()
        (home / "serve.json").unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--model-home", required=True, type=Path)
    parser.add_argument("--history-template", required=True, type=Path)
    parser.add_argument("--renderer", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                args.root.resolve(),
                args.model_home.resolve(),
                args.history_template.resolve(),
                args.renderer,
            )
        ),
        flush=True,
    )
