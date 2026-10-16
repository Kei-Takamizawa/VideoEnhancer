"""Repeat event-stream CPU measurements with one separate idle client."""

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


def measure(
    engine: Engine, server: LocalServer, output: Path, history: int, seconds: int = 31
) -> dict:
    client = subprocess.Popen(
        [
            sys.executable,
            "-c",
            """
import sys,time,urllib.request
request=urllib.request.Request(sys.argv[1],headers={'Authorization':'Bearer '+sys.argv[2]})
with urllib.request.urlopen(request,timeout=45) as response:
 print('ready',flush=True)
 for line in response:
  if line.startswith(b'data: '): print('event '+str(time.monotonic()),flush=True)
""",
            f"http://127.0.0.1:{server.server_port}/v1/events",
            server.token,
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert client.stdout is not None
    assert client.stdout.readline().strip() == "ready"
    assert client.stdout.readline().startswith("event ")
    data = []
    reader = threading.Thread(target=lambda: data.extend(client.stdout or []), daemon=True)
    reader.start()
    time.sleep(2)
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    time.sleep(seconds)
    wall, cpu = time.perf_counter() - wall_start, time.process_time() - cpu_start
    result = dict(
        wall_seconds=wall,
        cpu_seconds=cpu,
        one_core_cpu_percent=100 * cpu / wall,
        events=len(data),
        history=history,
        queued=10,
        actual_standard_running=any(j["state"] == "running" for j in engine._event_running_jobs),
        method=(
            "All service threads including real controller and HTTP/SSE; "
            "idle client and CUDA renderer child are separate processes; "
            "complete initial snapshot and two seconds warm-up excluded."
        ),
    )
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    client.terminate()
    client.wait(timeout=5)
    reader.join(timeout=3)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    engine = Engine(args.home)
    engine._environment()
    engine._home_watcher.start()
    server = LocalServer(engine)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    try:
        print(json.dumps(measure(engine, server, args.output, history=1000)), flush=True)
    finally:
        engine.close()
        server.shutdown()
        server.server_close()
