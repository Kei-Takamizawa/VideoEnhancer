"""Inventory and remove only a measurement's newly created cycle home."""

import json
import logging
import shutil
from pathlib import Path


def remove_cycle_home(home: Path, evidence: Path) -> dict:
    work = Path(__file__).resolve().parents[3]
    root = (work / "scratch/p1e3d1").resolve(strict=True)
    target = home.resolve(strict=True)
    if target == root or not target.is_relative_to(root):
        raise ValueError(f"Refusing cleanup outside the cycle: {target}")
    loggers = [logging.getLogger(), *logging.Logger.manager.loggerDict.values()]
    for logger in loggers:
        if isinstance(logger, logging.Logger):
            for handler in list(logger.handlers):
                if isinstance(handler, logging.FileHandler) and Path(
                    handler.baseFilename
                ).is_relative_to(target):
                    logger.removeHandler(handler)
                    handler.close()
    rows = [p.stat() for p in target.rglob("*") if p.is_file()]
    inventory = dict(
        path=str(target),
        files=len(rows),
        logical_file_lengths=sum(s.st_size for s in rows),
        nonshared_file_lengths=sum(s.st_size for s in rows if s.st_nlink == 1),
        shared_hardlink_lengths=sum(s.st_size for s in rows if s.st_nlink > 1),
        note="File lengths, not allocated disk space; shared hardlink data remains in cache.",
    )
    record = evidence / f"{target.name}-cleanup.json"
    record.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    try:
        shutil.rmtree(target)
        inventory["removed"] = True
    except OSError as error:
        inventory.update(removed=False, error=repr(error))
        raise
    finally:
        record.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return inventory
