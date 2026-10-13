"""Isolated desktop auxiliary work; shares the controller's between-segment lease."""

import json
import sys
from pathlib import Path

from videoenhancer.models.registry import ModelRegistry
from videoenhancer.service.settings import write_json


def main() -> None:
    request = json.loads(Path(sys.argv[1]).read_text())
    value, kind = request["request"], request["kind"]
    if kind == "trial" and sys.argv[2:] == ["--test-stuck-trial"]:
        import os
        import time

        (Path(request["folder"]) / "test-stuck.pid").write_text(str(os.getpid()), encoding="ascii")
        time.sleep(3600)
    if kind in {"verify", "download"}:
        registry = ModelRegistry()
        model = registry.manifest(value["model_id"])

        def weights_progress(phase: str, percent: float) -> None:
            write_json(
                Path(request["folder"]) / "progress.json", dict(phase=phase, percent=percent)
            )

        path = registry.weights(
            model,
            download=kind == "download",
            progress=weights_progress,
            force_verify=kind == "verify",
        )
        result = {
            "weights_verified": True,
            "bytes": path.stat().st_size,
            "sha256": model["weights"]["sha256"],
        }
    elif kind == "compare":
        from videoenhancer.service.compare import render_compare

        result = render_compare(value, Path(request["folder"]))
    elif kind == "trial":
        from videoenhancer.trial import run_trial

        settings = value["settings"]
        from videoenhancer.jobs.store import JobStore

        manifest = JobStore().load(value["job_id"]) if value.get("job_id") else None

        def progress(phase: str, percent: float) -> None:
            write_json(
                Path(request["folder"]) / "progress.json", dict(phase=phase, percent=percent)
            )

        result = run_trial(
            Path(value["file"]),
            start=value.get("start"),
            seconds=value.get("seconds", 5),
            preset=settings["preset"],
            out=Path(request["folder"]),
            backend=settings["backend"],
            short_side=settings["short_side"],
            settings_patch={**settings, "lossless": False},
            source_manifest=manifest,
            progress=progress,
        )
    else:
        from videoenhancer.bench.runner import run_bench

        def calibration_progress(phase: str, percent: float) -> None:
            snapshot = dict(phase=phase, percent=percent)
            write_json(Path(request["folder"]) / "progress.json", snapshot)
            with (Path(request["folder"]) / "progress.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(snapshot) + "\n")

        result = run_bench(True, None, Path(request["folder"]), progress=calibration_progress)
    write_json(Path(request["folder"]) / "result.json", result)


if __name__ == "__main__":
    main()
