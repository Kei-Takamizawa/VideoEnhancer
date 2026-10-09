"""Isolated desktop auxiliary work; shares the controller's between-segment lease."""

import json
import sys
from pathlib import Path

from videoenhancer.models.registry import ModelRegistry


def main() -> None:
    request = json.loads(Path(sys.argv[1]).read_text())
    value, kind = request["request"], request["kind"]
    if kind in {"verify", "download"}:
        registry = ModelRegistry()
        model = registry.manifest(value["model_id"])
        path = registry.weights(model, download=kind == "download")
        result = {
            "weights_verified": True,
            "bytes": path.stat().st_size,
            "sha256": model["weights"]["sha256"],
        }
    elif kind == "trial":
        from videoenhancer.trial import run_trial

        settings = value["settings"]
        result = run_trial(
            Path(value["file"]),
            start=value.get("start"),
            seconds=value.get("seconds", 5),
            preset=settings["preset"],
            out=Path(request["folder"]),
            backend=settings["backend"],
            short_side=settings["short_side"],
            settings_patch={**settings, "lossless": False},
        )
    else:
        from videoenhancer.bench.runner import run_bench

        result = run_bench(True, None, Path(request["folder"]))
    from videoenhancer.service.settings import write_json

    write_json(Path(request["folder"]) / "result.json", result)


if __name__ == "__main__":
    main()
