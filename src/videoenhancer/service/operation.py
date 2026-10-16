"""Isolated desktop auxiliary work; shares the controller's between-segment lease."""

import json
import sys
from pathlib import Path

from videoenhancer.models.registry import ModelRegistry
from videoenhancer.service.settings import write_json


def main() -> None:
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    value, kind = request["request"], request["kind"]
    if kind == "trial" and sys.argv[2:] == ["--test-stuck-trial"]:
        import os
        import time

        (Path(request["folder"]) / "test-stuck.pid").write_text(str(os.getpid()), encoding="ascii")
        time.sleep(3600)
    if kind in {"verify", "download"}:
        registry = ModelRegistry()
        model = registry.manifest(value["model_id"])
        tracker = None
        if kind == "download" and value.get("_network_only", True):
            from videoenhancer.service.downloads import DownloadProgress

            sizes = model.get("catalog", {}).get("download_sizes", {})
            if not sizes:
                sizes = {model["weights"]["filename"]: model["weights"].get("bytes", 0)}
            tracker = DownloadProgress(
                dict(sizes),
                float(value.get("_gpu_test_seconds", 15)),
                {model["weights"]["filename"]: model["weights"].get("bytes", 0), **sizes},
            )

        def weights_progress(phase: str, percent: float) -> None:
            write_json(
                Path(request["folder"]) / "progress.json",
                tracker.feed(phase, percent) if tracker else dict(phase=phase, percent=percent),
            )

        verified = value.get("_verified_weight")
        if (
            kind == "download"
            and not value.get("_network_only", True)
            and isinstance(verified, dict)
            and verified.get("sha256") == model["weights"]["sha256"]
        ):
            from videoenhancer.models.registry import remember_verified_hash

            expected_path = registry.folder(model["id"]) / model["weights"]["filename"]
            remember_verified_hash(
                expected_path, verified["sha256"], (verified["bytes"], verified["mtime_ns"])
            )
        path = registry.weights(
            model,
            download=kind == "download" and value.get("_network_only", True),
            progress=weights_progress if kind == "verify" or tracker else None,
            force_verify=kind == "verify",
        )
        result = {
            "weights_verified": True,
            "bytes": path.stat().st_size,
            "sha256": model["weights"]["sha256"],
        }
        if kind == "download" and value.get("_network_only", True):
            info = path.stat()
            result["verified_weight"] = dict(
                bytes=info.st_size, mtime_ns=info.st_mtime_ns, sha256=model["weights"]["sha256"]
            )
            if model["architecture"] == "basicvsrpp":
                from videoenhancer.bench.basicvsr import _source_files
                from videoenhancer.models.sources import source_cache

                _source_files(source_cache(("mmagic-code.zip",)), weights_progress)
            elif model["architecture"] == "rife":
                from videoenhancer.bench.rife import _prepare_files

                _prepare_files(prepare_weights=False, progress=weights_progress)
        elif kind == "download":
            import threading
            import time
            from fractions import Fraction

            import torch

            from videoenhancer.pipeline.stages import FrameBatch

            if not torch.cuda.is_available():
                raise RuntimeError(
                    "Couldn't test this model on the GPU. Check the GPU driver and retry Install."
                )
            started = time.monotonic()
            done = threading.Event()

            def gpu_progress() -> None:
                while not done.wait(0.25):
                    elapsed = time.monotonic() - started
                    phases = value.get("_phase_seconds") or {
                        "download": 0,
                        "checking": 0,
                        "gpu": 15,
                    }
                    expected = float(phases["gpu"])
                    completed = float(phases["download"]) + float(phases["checking"])
                    percent = (completed + min(expected, elapsed)) / (completed + expected) * 100
                    write_json(
                        Path(request["folder"]) / "progress.json",
                        dict(
                            phase="Testing on the GPU",
                            percent=min(99, max(value.get("_network_percent", 0), percent)),
                            remaining_seconds=max(0, expected - elapsed),
                        ),
                    )

            reporter = threading.Thread(target=gpu_progress, daemon=True)
            stage = registry.create_stage(
                model["id"],
                model["task"],
                {"backend": "cuda", "short_side": 1080},
                Fraction(30),
                set(),
            )
            reporter.start()
            try:
                count = 3 if model["task"] != "size" else 1
                frames = torch.zeros((count, 3, 256, 256), device="cuda", dtype=torch.float16)
                stage.load()
                with torch.inference_mode():
                    output = stage.process(
                        FrameBatch(
                            frames,
                            tuple(Fraction(i, 30) for i in range(count)),
                            tuple(range(count)),
                        )
                    )
                torch.cuda.synchronize()
                if not torch.isfinite(output.frames).all():
                    raise RuntimeError("The model produced invalid pictures during its GPU test.")
                result["gpu_tested"] = True
            finally:
                stage.release()
                done.set()
                reporter.join(timeout=1)
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
