"""Hidden engine subprocesses with continuously drained, bounded diagnostics."""

from __future__ import annotations

import os
import subprocess
import threading
from typing import Any

STDERR_LIMIT = 64 * 1024


def _options(options: dict[str, Any]) -> dict[str, Any]:
    if os.name == "nt":
        options["creationflags"] = options.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
    return options


class Popen(subprocess.Popen):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **_options(kwargs))
        self._tail: bytes | str = "" if getattr(self, "text_mode", False) else b""
        self._tail_lock = threading.Lock()
        self._drainer: threading.Thread | None = None
        if kwargs.get("stderr") == subprocess.PIPE and self.stderr is not None:
            stream, self.stderr = self.stderr, None

            def drain() -> None:
                try:
                    while chunk := stream.read(4096):
                        with self._tail_lock:
                            self._tail = (self._tail + chunk)[-STDERR_LIMIT:]
                finally:
                    stream.close()

            self._drainer = threading.Thread(target=drain, name="ve-stderr", daemon=True)
            self._drainer.start()

    def diagnostic_tail(self) -> bytes | str:
        with self._tail_lock:
            return self._tail

    def communicate(self, *args: Any, **kwargs: Any) -> Any:
        stdout, stderr = super().communicate(*args, **kwargs)
        if self._drainer is not None:
            self._drainer.join(timeout=2)
            stderr = self.diagnostic_tail()
        return stdout, stderr


def stderr_text(process: Popen) -> str:
    tail = process.diagnostic_tail()
    return tail if isinstance(tail, str) else tail.decode(errors="replace")


def run(
    *args: Any,
    input: Any = None,
    capture_output: bool = False,
    timeout: float | None = None,
    check: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    if input is not None:
        if "stdin" in kwargs:
            raise ValueError("stdin and input arguments may not both be used")
        kwargs["stdin"] = subprocess.PIPE
    if capture_output:
        if "stdout" in kwargs or "stderr" in kwargs:
            raise ValueError("stdout and stderr arguments may not be used with capture_output")
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with Popen(*args, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            process.kill()
            stdout, stderr = process.communicate()
            error.output, error.stderr = stdout, stderr
            raise
        except BaseException:
            process.kill()
            process.wait()
            raise
        result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
