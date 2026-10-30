"""Early pixel-gate probe of a middle part; this is not a full-job G5 result."""

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
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use an alphanumeric label")
    work = Path(__file__).resolve().parents[3]
    repo = args.repo.resolve(strict=True)
    root = work / "scratch/p1e3d1"
    home = root / args.label
    evidence = work / "evidence/VE-P1e-3d1"
    if not repo.is_relative_to(work):
        raise ValueError("Source checkout must stay inside work")
    home.mkdir(parents=True, exist_ok=False)
    os.environ["VE_HOME"] = str(home)
    configuration = os.environ.get(
        "PYTORCH_ALLOC_CONF", os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "")
    )
    if "expandable_segments:" not in configuration:
        os.environ["PYTORCH_ALLOC_CONF"] = ",".join(
            filter(None, [configuration, "expandable_segments:True"])
        )
    sys.path.insert(0, str(repo / "src"))
    cache = Path(os.environ["VE_GPU_TEST_MODEL_HOME"])

    def copy(source, destination):
        if Path(source).suffix.lower() in {".pth", ".pkl", ".pt", ".zip"}:
            os.link(source, destination)
        else:
            shutil.copy2(source, destination)
        return destination

    for name in ("models", "adapter-sources"):
        shutil.copytree(cache / name, home / name, copy_function=copy)
    from videoenhancer.jobs.gpu_budget import run_with_budget
    from videoenhancer.media.analyze import analyze
    from videoenhancer.models.registry import record_models
    from videoenhancer.pipeline.runner import process_segment

    source = root / "synthetic-512x288-30.mp4"
    settings = dict(preset="standard", backend="cuda", short_side=1080, fps="2x", codec="h264")
    job = dict(**analyze(source, backend="cuda"), settings=settings)
    job["input"] = dict(path=str(source))
    job["models"] = record_models(settings, home, job["media"])
    session = None
    extras = {}
    if (repo / "src/videoenhancer/pipeline/session.py").exists():
        from videoenhancer.pipeline.session import PipelineSession

        session = PipelineSession()
        extras["session"] = session
    report = dict(
        label=args.label,
        repo=str(repo),
        pid=os.getpid(),
        scope="middle-part probe, not full-job G5",
    )
    try:
        for index, (first, last) in enumerate(((0, 30), (30, 120))):
            output = home / f"part-{index}.mp4"
            segment = dict(index=index, start=first, end=last)
            began = time.perf_counter()
            stats = run_with_budget(
                lambda progress, segment=segment, output=output: process_segment(
                    job,
                    segment,
                    output,
                    lambda: False,
                    progress=progress,
                    **extras,
                ),
                enabled=True,
            )
            report[f"part_{index}"] = dict(
                seconds=time.perf_counter() - began,
                stats=stats,
                sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
            )
            if index == 0:
                import torch

                torch.cuda.empty_cache()
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        if session is not None:
            session.close()
        (evidence / f"{args.label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        from profile_cleanup import remove_cycle_home

        remove_cycle_home(home, evidence)
    print(args.label, report["part_1"]["seconds"], report["part_1"]["sha256"], flush=True)


if __name__ == "__main__":
    main()
