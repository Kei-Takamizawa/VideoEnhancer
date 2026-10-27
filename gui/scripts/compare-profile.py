"""Isolated real-engine Compare profile, with an optional before-code overlay."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--busy", action="store_true")
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use an alphanumeric label")
    work = Path(__file__).resolve().parents[3]
    repo = work / "repo"
    scratch = work / "scratch/p1e3c2-compare"
    home = scratch / args.label
    evidence = work / "evidence/VE-P1e-3c2"
    home.mkdir(parents=True, exist_ok=False)
    os.environ["VE_HOME"] = str(home)
    if args.baseline:
        overlay = scratch / (args.label + "-overlay")
        package = overlay / "videoenhancer"
        service = package / "service"
        service.mkdir(parents=True)
        for destination, original in [
            (package, repo / "src/videoenhancer"),
            (service, repo / "src/videoenhancer/service"),
        ]:
            content = (original / "__init__.py").read_text(encoding="utf-8")
            (destination / "__init__.py").write_text(
                content + f"\n__path__.append({str(original)!r})\n", encoding="utf-8"
            )
        before = (evidence / "compare-before.py").read_text(encoding="utf-8")
        # Measurement-only addition: preserve the process_segment statistics
        # discarded by the old result. No pixel/encoding operation changes.
        before = before.replace('fps=stats["fps"],', 'fps=stats["fps"], profile=stats,')
        (service / "compare.py").write_text(before, encoding="utf-8")
        sys.path.insert(0, str(overlay))
        os.environ["PYTHONPATH"] = str(overlay) + os.pathsep + str(repo / "src")
    else:
        os.environ["PYTHONPATH"] = str(repo / "src")
    cache = Path(os.environ["VE_GPU_TEST_MODEL_HOME"])

    def copy_file(source, destination):
        if Path(source).suffix.lower() in {".pth", ".pkl", ".pt", ".zip"}:
            os.link(source, destination)
        else:
            shutil.copy2(source, destination)
        return destination

    for name in ["models", "adapter-sources"]:
        shutil.copytree(cache / name, home / name, copy_function=copy_file)
    from videoenhancer.models.registry import C1
    from videoenhancer.service.engine import Engine

    source = scratch / "synthetic-512x288-30.mp4"
    if not source.is_file():
        raise FileNotFoundError("Generate the shared six-second synthetic source first")
    settings = dict(
        preset="standard",
        backend="cuda",
        short_side=1080,
        fps="2x",
        codec="h264",
        output_folder=str(home / "output"),
    )
    engine = Engine(home)
    engine.start()
    report = dict(label=args.label, baseline=args.baseline, busy=args.busy, settings=settings)
    try:
        if args.busy:
            job = engine.add(dict(file=str(source), settings=settings))
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                current = engine.store.load(job["id"])
                if any(part["state"] == "running" for part in current["segments"]):
                    report["standard_job_at_request"] = dict(
                        state=current["state"],
                        segments=[part["state"] for part in current["segments"]],
                    )
                    break
                if current["state"] in {"failed", "done", "cancelled"}:
                    raise RuntimeError(
                        f"Standard job did not reach a running part: {current.get('error')}"
                    )
                time.sleep(0.05)
            else:
                raise TimeoutError("Standard job admission")
        began = time.perf_counter()
        operation = engine.operation(
            "compare", dict(file=str(source), settings=settings, seconds=5, start=0, models=[C1])
        )
        report["admission_seconds"] = time.perf_counter() - began
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            folder = home / "previews" / operation["id"]
            progress = folder / "progress.json"
            if progress.exists():
                try:
                    packet = json.loads(progress.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    report["progress_read_retries"] = report.get("progress_read_retries", 0) + 1
                    packet = {}
                if (
                    packet.get("result", {}).get("first_looks")
                    and "first_tile_seconds" not in report
                ):
                    report["first_tile_seconds"] = time.perf_counter() - began
            if operation["state"] in {"done", "failed", "cancelled"}:
                report["operation"] = operation
                report["elapsed_seconds"] = time.perf_counter() - began
                report["hashes"] = {
                    file.name: hashlib.sha256(file.read_bytes()).hexdigest()
                    for file in folder.glob("*-preview.mp4")
                }
                if operation["state"] != "done":
                    raise RuntimeError(operation.get("error", operation["state"]))
                break
            time.sleep(0.05)
        else:
            raise TimeoutError("Compare did not complete")
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        engine.close()
        (evidence / f"{args.label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(args.label, "seconds", report["elapsed_seconds"], "hashes", report["hashes"], flush=True)


if __name__ == "__main__":
    main()
