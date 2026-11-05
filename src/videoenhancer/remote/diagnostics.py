"""Privacy-safe remote failure diagnostics; never copy arbitrary exception text."""

import logging
import re
import traceback
from pathlib import Path


def reason(error):
    text = str(error).lower()
    # Untrusted tool stderr can contain bare titles as well as paths and URLs.
    message = "Operation failed."
    for words, description in (
        (("timeout", "timed out", "too long"), "Operation timed out."),
        (("no space", "disk full"), "Insufficient disk space."),
        (("permission", "access is denied"), "Access denied."),
        (("connection", "network"), "Network operation failed."),
        (("not found", "missing"), "Required resource is unavailable."),
        (("invalid", "unsupported", "not supported"), "Unsupported or invalid media or request."),
        (("encoder", "encode"), "Encoding failed."),
        (("decode", "decoder"), "Decoding failed."),
    ):
        if any(word in text for word in words):
            message = description
            break
    if re.search(r"[a-z][a-z0-9+.-]*://", text):
        message += " [url]"
    if re.search(r"[a-z]:[\\/]|\\\\|(?:^|\s)/", text):
        message += " [path]"
    return message


def failure(stage, error):
    detail = {"stage": stage, "type": type(error).__name__, "reason": reason(error)}
    logging.getLogger("videoenhancer.remote").error(
        "job failure stage=%s type=%s reason=%s", stage, detail["type"], detail["reason"]
    )
    return detail


def frames(error):
    """Traceback locations only: no source lines, absolute paths or locals."""
    return " ".join(
        f"{Path(frame.f_code.co_filename).name}:{line}"
        for frame, line in traceback.walk_tb(error.__traceback__)
    )


def log_failure(logger, stage, error, *, extra=None, level=logging.ERROR):
    """Use only classified text and traceback locations in controller logs."""
    logger.log(
        level,
        "job failure stage=%s type=%s reason=%s traceback=%s",
        stage,
        type(error).__name__,
        reason(error),
        frames(error),
        extra=extra,
    )


def job_stage(job):
    if job.get("state") == "downloading":
        return "download"
    if job.get("state") == "preparing" or not job.get("segments"):
        return "probe"
    progress = job.get("progress") or {}
    return "encode" if progress.get("phase") == "finalizing" else "enhance"
