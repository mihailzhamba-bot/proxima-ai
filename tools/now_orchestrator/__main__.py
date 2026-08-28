from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import load_snapshot, render, select
from .core.snapshot import first_run_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a deterministic read-only /now snapshot", allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command")
    render_parser = subparsers.add_parser("render", help="render a normalized snapshot JSON")
    render_parser.add_argument("snapshot", type=Path, nargs="?", help="path to normalized snapshot JSON")
    render_parser.add_argument("--stdin", action="store_true", help="read normalized snapshot JSON from stdin")
    args = parser.parse_args()
    if args.command is None:
        print(render(select(first_run_snapshot())), end="")
        return 0
    if args.command == "render":
        try:
            if args.stdin == (args.snapshot is not None):
                parser.error("provide exactly one snapshot path or --stdin")
            raw = sys.stdin.read() if args.stdin else args.snapshot.read_text(encoding="utf-8")
            data = json.loads(raw)
            print(render(select(load_snapshot(data))), end="")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
