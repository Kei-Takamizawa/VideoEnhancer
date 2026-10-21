"""Explicit CI setup; media tests use only local synthetic servers."""

import argparse
import json
from pathlib import Path

from videoenhancer.service.link_tools import ToolManager


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("home", type=Path)
    args = parser.parse_args()
    manager = ToolManager(args.home)
    plan = manager.check("stable")
    manager.install("stable", plan["id"], lambda _: None, lambda: False)
    for tool in ("yt-dlp", "deno"):
        manager.executable(tool)
    print(json.dumps(manager.status()))


if __name__ == "__main__":
    main()
