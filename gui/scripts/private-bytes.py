"""Sample an isolated desktop instance's Windows Private Bytes once per second."""

import json
import sys
import time
from pathlib import Path

import psutil

root = psutil.Process(int(sys.argv[1]))
destination = Path(sys.argv[2])
deadline = time.monotonic()
with destination.open("w", encoding="utf-8", buffering=1) as sink:
    while root.is_running():
        processes = []
        errors = []
        try:
            candidates = [root, *root.children(recursive=True)]
        except psutil.NoSuchProcess:
            break
        for process in candidates:
            try:
                arguments = process.cmdline()
                role = "shell" if process.pid == root.pid else "browser-helper"
                for argument in arguments:
                    if argument.startswith("--type="):
                        role = argument.removeprefix("--type=")
                    if argument.startswith("--utility-sub-type="):
                        role += ":" + argument.removeprefix("--utility-sub-type=")
                processes.append(
                    dict(
                        pid=process.pid,
                        parent=process.ppid(),
                        name=process.name(),
                        role=role,
                        private_bytes=process.memory_info().private,
                    )
                )
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                errors.append(process.pid)
        sink.write(
            json.dumps(
                dict(
                    time_ms=time.time_ns() // 1_000_000,
                    processes=processes,
                    total_private_bytes=sum(p["private_bytes"] for p in processes),
                    access_errors=errors,
                )
            )
            + "\n"
        )
        deadline += 1
        time.sleep(max(0, deadline - time.monotonic()))
