"""Measure a real isolated job from a chosen source checkout using synthetic input."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--preset", choices=("fast", "standard"), default="standard")
    parser.add_argument("--codec", choices=("h264", "hevc"), default="h264")
    parser.add_argument("--fps", choices=("off", "2x"), default="2x")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--resume-g5", action="store_true")
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use an alphanumeric label")
    work = Path(__file__).resolve().parents[3]
    repo = (args.repo or work / "repo").resolve()
    source = args.source.resolve(strict=True)
    root = work / "scratch/p1e3d1"
    home = root / args.label
    evidence = work / "evidence/VE-P1e-3d1"
    for path in (repo, source, home, evidence):
        if not path.is_relative_to(work):
            raise ValueError(f"Path must stay inside work: {path}")
    resuming = args.resume_g5 and home.exists()
    home.mkdir(parents=True, exist_ok=resuming)
    evidence.mkdir(parents=True, exist_ok=True)
    os.environ["VE_HOME"] = str(home)
    os.environ["PYTHONPATH"] = str(repo / "src")
    sys.path.insert(0, str(repo / "src"))
    cache = Path(os.environ["VE_GPU_TEST_MODEL_HOME"])

    def copy(source, target):
        if Path(source).suffix.lower() in {".pth", ".pkl", ".pt", ".zip"}:
            os.link(source, target)
        else:
            shutil.copy2(source, target)
        return target

    if not resuming:
        for name in ("models", "adapter-sources"):
            shutil.copytree(cache / name, home / name, copy_function=copy)
    from videoenhancer.service.engine import Engine

    engine = Engine(home)
    report = {"label": args.label, "repo": str(repo), "pid": os.getpid()}
    previous = engine.store.list_jobs() if resuming else []
    if resuming:
        assert len(previous) == 1, "Resume requires exactly one existing synthetic job"
        assert Path(previous[0]["input"]["path"]).resolve() == source
        expected = dict(preset=args.preset, codec=args.codec, fps=args.fps)
        assert all(previous[0]["settings"][k] == v for k, v in expected.items())
        report["resumed"] = True
        report["completed_parts_before_resume"] = [
            s["index"] for s in previous[0]["segments"] if s["state"] == "done"
        ]
        report["elapsed_scope"] = "Post-resume only; quality evidence, not a speed repetition"
    began = time.perf_counter()
    try:
        engine.start()
        job = (
            previous[0]
            if resuming
            else engine.add(
                dict(
                    file=str(source),
                    output_folder=str(home / "output"),
                    settings=dict(
                        preset=args.preset,
                        backend="cuda",
                        short_side=1080,
                        fps=args.fps,
                        codec=args.codec,
                        output_folder=str(home / "output"),
                    ),
                )
            )
        )
        deadline = time.monotonic() + 14400
        while time.monotonic() < deadline:
            if (evidence / "stop-benchmarks").exists():
                raise InterruptedError("Measurement stopped by the operator")
            current = engine.store.load(job["id"])
            if current["state"] in {"done", "failed", "cancelled"}:
                report["job"] = current
                report["elapsed_seconds"] = time.perf_counter() - began
                if current["state"] != "done":
                    raise RuntimeError(current.get("error", current["state"]))
                output = Path(current["output"])
                digest = hashlib.sha256()
                with output.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                report["sha256"] = digest.hexdigest()
                report["output_bytes"] = output.stat().st_size
                break
            time.sleep(0.2)
        else:
            raise TimeoutError("Job did not complete within four hours")
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        children = psutil.Process().children(recursive=True)
        report["pids_before_close"] = [p.pid for p in children]
        closing = time.perf_counter()
        engine.close()
        _, alive = psutil.wait_procs(children, timeout=5)
        report["shutdown_seconds"] = time.perf_counter() - closing
        report["remaining_pids"] = [p.pid for p in alive]
        (evidence / f"{args.label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.cleanup and not report["remaining_pids"]:
            from profile_cleanup import remove_cycle_home

            remove_cycle_home(home, evidence)
    print(args.label, report["elapsed_seconds"], report.get("sha256"), flush=True)


if __name__ == "__main__":
    main()
