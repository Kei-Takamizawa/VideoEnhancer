"""Local JSONL diagnostics with readable console messages."""

from __future__ import annotations

import importlib
import json
import logging
import platform
import subprocess
import sys
import threading
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from videoenhancer import proc


def capture_runtime_errors(home: Path) -> None:
    """Keep pythonw warnings and uncaught thread failures in the service log."""
    from videoenhancer.remote.diagnostics import frames, reason

    logger = get_logger(home)
    logging.captureWarnings(True)
    warnings = logging.getLogger("py.warnings")

    class WarningLog(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logger.warning("Python warning: %s", reason(record.getMessage()))

    warnings.handlers = [WarningLog()]
    warnings.propagate = False

    def thread_error(args: threading.ExceptHookArgs) -> None:
        logger.error(
            "uncaught thread exception type=%s reason=%s traceback=%s",
            args.exc_type.__name__,
            reason(args.exc_value),
            frames(args.exc_value),
        )

    threading.excepthook = thread_error


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        for name in ("job_id", "segment", "action", "elapsed_seconds"):
            if hasattr(record, name):
                fields[name] = getattr(record, name)
        if record.exc_info:
            fields["exception"] = self.formatException(record.exc_info)
        return json.dumps(fields, ensure_ascii=False)


def _handler(path: Path) -> RotatingFileHandler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    return handler


def get_logger(home: Path, *, job_id: str | None = None, console: bool = True) -> logging.Logger:
    """Return a logger writing the global log and optionally a job log."""
    name = f"videoenhancer.{job_id}" if job_id else "videoenhancer"
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    global_path = home / "videoenhancer.jsonl"
    settings_path = home / "settings.json"
    if settings_path.exists():
        try:
            preferences = json.loads(settings_path.read_text(encoding="utf-8"))
            if not isinstance(preferences, dict):
                preferences = {}
        except (ValueError, UnicodeError):
            preferences = {}
        if preferences.get("log_folder"):
            global_path = Path(preferences["log_folder"]) / "videoenhancer.jsonl"
    job_path = home / "jobs" / job_id / "job.jsonl" if job_id else None
    existing = {getattr(handler, "baseFilename", None) for handler in logger.handlers}
    if str(global_path) not in existing:
        logger.addHandler(_handler(global_path))
    if job_path is not None and str(job_path) not in existing:
        logger.addHandler(_handler(job_path))
    if (
        console
        and sys.stderr is not None
        and not any(
            isinstance(handler, logging.StreamHandler)
            and not isinstance(handler, RotatingFileHandler)
            for handler in logger.handlers
        )
    ):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)
    return logger


def environment_info() -> dict[str, str]:
    info = {"os": platform.platform(), "python": platform.python_version()}
    try:
        torch = importlib.import_module("torch")

        info["torch"] = torch.__version__
        info["cuda_runtime"] = str(torch.version.cuda)
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
    except ImportError:
        info["torch"] = "unavailable"
    try:
        result = proc.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
        if result.returncode == 0:
            info["driver"] = result.stdout.strip().splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        pass
    try:
        from videoenhancer.config import executable

        result = proc.run(
            [executable("ffmpeg"), "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
        if result.returncode == 0:
            info["ffmpeg"] = result.stdout.splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        info["ffmpeg"] = "unavailable"
    try:
        from importlib.metadata import version

        info["pynvvideocodec"] = version("pynvvideocodec")
    except Exception:
        info["pynvvideocodec"] = "unavailable"
    return info


def log_job_header(logger: logging.Logger, job_id: str) -> None:
    logger.info(
        "Job environment: %s",
        json.dumps(environment_info(), ensure_ascii=False),
        extra={"job_id": job_id},
    )
