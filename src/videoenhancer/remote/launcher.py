"""Windowless entry point that pins the installed task to its selected home."""

import argparse
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--pair-message", action="store_true")
    args = parser.parse_args()
    os.environ["VE_HOME"] = str(args.home.resolve())
    from videoenhancer.cli import main as cli

    if args.pair_message:
        try:
            from videoenhancer.remote.install import command

            command(
                argparse.Namespace(remote_command="pair", message_box=True), args.home.resolve()
            )
            return 0
        except (OSError, ValueError, RuntimeError):
            from videoenhancer.remote.install import message_box

            message_box("The PC service is not available. Run 've remote status' on the PC.")
            return 1
    return cli(["serve", "--remote"])


if __name__ == "__main__":
    raise SystemExit(main())
