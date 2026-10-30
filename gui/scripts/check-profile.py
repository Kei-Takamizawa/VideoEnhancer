"""Record a final check's exit code and owned process tree inside cycle evidence."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil


def live(pid: int, created: float):
    try:
        process = psutil.Process(pid)
        return process if process.create_time() == created and process.is_running() else None
    except psutil.Error:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.label.replace("-", "").isalnum():
        parser.error("Use an alphanumeric label")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Supply a check command after --")
    work = Path(__file__).resolve().parents[3]
    directory = (args.cwd or Path.cwd()).resolve(strict=True)
    if not directory.is_relative_to(work):
        parser.error("The check working directory must stay inside work")
    command[0] = str(Path(shutil.which(command[0]) or command[0]).resolve(strict=True))
    evidence = (work / "evidence/VE-P1e-3d1").resolve(strict=True)
    temporary = (work / "scratch/p1e3d1/checks/tmp").resolve()
    for target in (evidence, temporary):
        if not target.is_relative_to(work):
            raise ValueError(f"Path must stay inside work: {target}")
    temporary.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "TEMP": str(temporary), "TMP": str(temporary)}
    record = evidence / f"check-{args.label}-processes.json"
    if record.exists():
        parser.error("Use a new label; preserve earlier check evidence")
    report = dict(label=args.label, state="running", processes=[], remaining_pids=None)
    owned = {}
    began = time.perf_counter()

    def save():
        report["processes"] = list(owned.values())
        record.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def observe(root):
        try:
            children = root.children(recursive=True)
        except psutil.Error:
            children = []
        for process in [root, *children]:
            try:
                key = (process.pid, process.create_time())
                if key not in owned:
                    owned[key] = dict(pid=key[0], created=key[1], name=process.name())
                    save()
            except psutil.Error:
                pass

    with (evidence / f"check-{args.label}.log").open("wb") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=directory,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        root = psutil.Process(process.pid)
        report["root_pid"] = process.pid
        observe(root)
        try:
            while process.poll() is None:
                observe(root)
                time.sleep(0.1)
        finally:
            report["exit_code"] = process.poll()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and any(live(*key) for key in owned):
                time.sleep(0.1)
            remaining = [key for key in owned if live(*key)]
            report["remaining_before_cleanup"] = [pid for pid, _ in remaining]
            # A leaked child fails the check even if cleanup succeeds. Verify
            # creation times again before touching an owned PID that may be reused.
            for key in remaining:
                child = live(*key)
                if child is not None:
                    try:
                        child.terminate()
                        child.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        child = live(*key)
                        if child is not None:
                            try:
                                child.kill()
                                child.wait(timeout=2)
                            except psutil.NoSuchProcess:
                                pass
                            except psutil.Error as error:
                                report.setdefault("cleanup_errors", []).append(str(error))
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.Error as error:
                        report.setdefault("cleanup_errors", []).append(str(error))
            report.update(
                state="finished",
                elapsed_seconds=time.perf_counter() - began,
                remaining_pids=[pid for pid, created in owned if live(pid, created)],
            )
            save()
    print(json.dumps(report), flush=True)
    sys.exit(process.returncode or int(bool(remaining or report["remaining_pids"])))


if __name__ == "__main__":
    main()
