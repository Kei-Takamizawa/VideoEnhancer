"""Independent payload ablation; diagnostics only, never a curve fit input."""

import argparse
import copy
import json
import time
from pathlib import Path

from videoenhancer.jobs.store import JobStore
from videoenhancer.pipeline.inline_quality import aggregate_quality
from videoenhancer.schedule.controller import FinalizationTimer, SystemClock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_home", type=Path)
    args = parser.parse_args()
    work = Path(__file__).resolve().parents[3]
    source = args.source_home.resolve(strict=True)
    home = (work / "scratch/p1e3d2b/aggregation-ablation").resolve()
    assert source.is_relative_to(work) and home.is_relative_to(work) and not home.exists()
    original = JobStore(source).load("curve-10-0")
    store = JobStore(home)
    rows = []
    for kind in ("full", "quality-only"):
        for repeat in range(3):
            job = copy.deepcopy(original)
            job.update(id=f"aggregation-{kind}-{repeat}", state="running", timing={})
            job.pop("quality", None)
            if kind == "quality-only":
                for segment in job["segments"]:
                    segment["stats"] = {
                        key: value
                        for key, value in segment["stats"].items()
                        if key
                        in {
                            "inline_quality",
                            "clip_joints",
                            "raw_flag_count",
                            "final_flag_count",
                            "luma_outliers",
                        }
                    }
            store.save(job)
            timer = FinalizationTimer(store, job["id"], SystemClock())
            began = time.perf_counter()
            timer.begin("aggregating")
            current = store.load(job["id"])
            core = time.perf_counter()
            current["quality"] = aggregate_quality(current)
            core_seconds = time.perf_counter() - core
            assert current["quality"] == original["quality"]
            store.save(current)
            timer.end()
            total = time.perf_counter() - began
            result = store.load(job["id"])
            rows.append(
                dict(
                    kind=kind,
                    repeat=repeat,
                    core_seconds=core_seconds,
                    event_seconds=result["timing"]["events"][-1]["elapsed_seconds"],
                    total_seconds=total,
                    manifest_bytes=(store.job_dir(job["id"]) / "manifest.json").stat().st_size,
                    parts=len(job["segments"]),
                )
            )
    evidence = work / "evidence/VE-P1e-3d2b/aggregation-ablation.json"
    evidence.write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
