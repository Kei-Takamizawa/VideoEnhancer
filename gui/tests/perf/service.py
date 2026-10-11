"""Measure one real SSE client while a separate controller runs Standard."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from videoenhancer.service.engine import Engine
from videoenhancer.service.server import LocalServer


def measure(home: Path, output: Path, seconds: int = 31) -> dict:
    engine = Engine(home)
    engine._environment()
    jobs = engine.store.list_jobs()
    assert sum(j["state"] == "done" for j in jobs) == 1000
    assert sum(j["state"] == "queued" for j in jobs) == 10
    running = [j for j in jobs if j["state"] == "running"]
    assert len(running) == 1 and running[0]["settings"]["preset"] == "standard"
    server = LocalServer(engine)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    # The idle client runs outside the measured service process. Its buffered
    # HTTP reads must not be counted as event-stream service CPU.
    client = subprocess.Popen(
        [
            sys.executable,
            "-c",
            """
import sys, urllib.request
request = urllib.request.Request(sys.argv[1], headers={"Authorization": "Bearer " + sys.argv[2]})
with urllib.request.urlopen(request, timeout=40) as response:
    print("ready", flush=True)
    for line in response:
        if line.startswith(b"data: "):
            print("event", flush=True)
""",
            f"http://127.0.0.1:{server.server_port}/v1/events",
            server.token,
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert client.stdout is not None
    assert client.stdout.readline().strip() == "ready"
    data = []

    def receive():
        assert client.stdout is not None
        for line in client.stdout:
            if line.strip() == "event":
                data.append(time.perf_counter())

    reader = threading.Thread(target=receive, daemon=True)
    reader.start()
    deadline = time.perf_counter() + 120
    while not data:
        if client.poll() is not None or time.perf_counter() >= deadline:
            raise RuntimeError("The initial event snapshot did not arrive.")
        time.sleep(0.1)
    # Warm manifest and snapshot caches before the idle-client interval.
    time.sleep(2)
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    for _ in range(seconds):
        assert engine.store.load(running[0]["id"])["state"] == "running"
        time.sleep(1)
    wall, cpu = time.perf_counter() - wall_start, time.process_time() - cpu_start
    result = dict(
        wall_seconds=wall,
        cpu_seconds=cpu,
        one_core_cpu_percent=cpu / wall * 100,
        events=len(data),
        history=1000,
        queued=10,
        actual_standard_running=True,
        method=(
            "service process_time includes real HTTP/SSE; "
            "idle client and GPU controller are separate processes"
        ),
    )
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    engine.close()
    client.terminate()
    client.wait(timeout=5)
    reader.join(timeout=3)
    server.shutdown()
    server.server_close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.home, args.output)))
