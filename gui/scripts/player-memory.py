"""Read only the specified work-owned desktop process and its descendants."""

import json
import sys
from pathlib import Path

import psutil

from videoenhancer.jobs.pdh import ProcessMemoryCounters


def main():
    work = Path(__file__).resolve().parents[3]
    parent = psutil.Process(int(sys.argv[1]))
    executable = Path(parent.exe()).resolve()
    if executable.name not in {
        "VideoEnhancer.exe",
        "VideoEnhancer-Player.exe",
    } or not executable.is_relative_to(work):
        raise ValueError("Only this work folder's desktop/player test process may be sampled")
    children = parent.children(recursive=True)
    helpers = [process for process in children if process.name() == "VideoEnhancer-Player.exe"]
    excluded = {
        process.pid for helper in helpers for process in [helper, *helper.children(recursive=True)]
    }
    counters = ProcessMemoryCounters()
    rows, errors = [], []
    try:
        for process in [parent, *children]:
            if process.pid in excluded:
                continue
            try:
                dedicated, shared = counters.read(process.pid)
                rows.append(
                    dict(
                        pid=process.pid,
                        private=process.memory_info().private,
                        dedicated=dedicated,
                        shared=shared,
                        handles=process.num_handles(),
                    )
                )
            except (psutil.Error, OSError) as error:
                errors.append(str(error))
        result = dict(
            processes=rows,
            errors=errors,
            helper_pids=[helper.pid for helper in helpers],
            main_private=next(row["private"] for row in rows if row["pid"] == parent.pid),
            main_tree_private=sum(row["private"] for row in rows),
            dedicated=sum(row["dedicated"] or 0 for row in rows),
            shared=sum(row["shared"] or 0 for row in rows),
            main_has_libmpv=any("libmpv" in item.path.lower() for item in parent.memory_maps()),
        )
        print(json.dumps(result))
    finally:
        counters.close()


if __name__ == "__main__":
    main()
