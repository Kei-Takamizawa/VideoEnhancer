"""Collect bounded failure evidence from synthetic Playwright output only."""

import argparse
import json
import shutil
from pathlib import Path


def collect(source: Path, target: Path, limit: int = 99_000_000) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    used = 0
    omitted = []
    paths = sorted(source.rglob("*"), key=lambda p: (p.suffix == ".zip", str(p)))
    for path in paths:
        if not path.is_file() or path.is_symlink() or path.suffix not in {".zip", ".log", ".md"}:
            continue
        size = path.stat().st_size
        relative = path.relative_to(source)
        if used + size > limit:
            omitted.append(str(relative))
            continue
        output = target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, output)
        used += size
    summary = dict(
        bytes=used,
        limit=limit,
        omitted=omitted,
        note="Oversize files are listed rather than producing invalid truncated traces.",
    )
    (target / "collection.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args.source, args.target)))
