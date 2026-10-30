"""A session-scoped Compare child, released before a processing part uses the GPU."""

import contextlib
import multiprocessing
import os
from pathlib import Path
from typing import Any

from videoenhancer.schedule.controller import (
    _attach_windows_job,
    _close_windows_job,
    _kill_process_tree,
    _set_linux_parent_death,
)


def _serve(receiver: Any, sender: Any, parent: int, home: str) -> None:
    _set_linux_parent_death(parent)
    os.environ["VE_HOME"] = home
    state = None
    try:
        while True:
            request = receiver.recv()
            if request is None:
                break
            value, folder = request
            with (Path(folder) / "operation.log").open("a", encoding="utf-8") as log:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    os.dup2(log.fileno(), 1)
                    os.dup2(log.fileno(), 2)
                    try:
                        from videoenhancer.service.compare import render_compare
                        from videoenhancer.service.compare_cache import CompareState

                        if state is None:
                            state = CompareState()
                        result = render_compare(value, Path(folder), state)
                        sender.send((True, result, state.retire))
                        if state.retire:
                            break
                    except Exception as error:
                        import traceback

                        traceback.print_exc()
                        sender.send((False, f"{type(error).__name__}: {error}", True))
                        break
    except (EOFError, OSError):
        pass
    finally:
        if state is not None:
            state.close()
        receiver.close()
        sender.close()


class CompareWorker:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.process: Any = None
        self.requests: Any = None
        self.results: Any = None
        self.job: int | None = None

    def begin(self, value: dict[str, Any], folder: Path) -> None:
        if self.process is not None and not self.process.is_alive():
            self.close()
        if self.process is None:
            context = multiprocessing.get_context("spawn")
            requests, self.requests = context.Pipe(duplex=False)
            self.results, results = context.Pipe(duplex=False)
            self.process = context.Process(
                target=_serve, args=(requests, results, os.getpid(), str(self.home))
            )
            self.process.start()
            requests.close()
            results.close()
            try:
                if os.name == "nt":
                    self.job = _attach_windows_job(self.process.pid)
            except Exception:
                self.close(force=True)
                raise
        self.requests.send((value, str(folder)))

    def close(self, force: bool = False) -> None:
        if self.process is None:
            return
        try:
            if self.process.is_alive() and not force:
                with contextlib.suppress(OSError, EOFError):
                    self.requests.send(None)
                self.process.join(timeout=2)
            if self.process.is_alive():
                _close_windows_job(self.job)
                self.job = None
                if self.process.is_alive():
                    _kill_process_tree(self.process.pid)
                if self.process.is_alive():
                    self.process.terminate()
                self.process.join(timeout=0.5)
        finally:
            _close_windows_job(self.job)
            self.job = None
            self.requests.close()
            self.results.close()
            self.process = None
