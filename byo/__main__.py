"""Entrypoint — bare 'byo' chats; subcommands open the other surfaces."""

from __future__ import annotations

import sys

from byo import __version__

USAGE = """byo — a small local agent you can read.

  byo                 chat in the terminal
  byo dashboard       the local dashboard at http://127.0.0.1:7777
  byo trajectory      render the newest recorded trajectory
  byo --version       print the version
  byo --help          this text
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        from byo.gateway.cli import main as chat

        return chat()
    command = args[0]
    if command in ("--version", "-V"):
        print(__version__)
        return 0
    if command in ("--help", "-h", "help"):
        print(USAGE, end="")
        return 0
    if command == "dashboard":
        try:
            from byo.ops.dashboard import main as dashboard
        except ImportError:
            print("dashboard is not available in this build", file=sys.stderr)
            return 2
        return dashboard()
    if command == "trajectory":
        try:
            from byo.ops.show_trajectory import main as show
        except ImportError:
            print("the trajectory view is not available in this build", file=sys.stderr)
            return 2
        return show(args[1:])
    print(f"byo: unknown command {command!r}\n", file=sys.stderr)
    print(USAGE, end="", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
