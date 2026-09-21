#!/usr/bin/python3 -I
"""Forced SSH command for fixed LOOP dispatch and exact bundle fetch."""

from __future__ import annotations

import os
import re
import shlex
import sys


JOB = re.compile(r"[a-z0-9][a-z0-9-]{2,40}")
TEMPLATE = re.compile(r"[a-z0-9][a-z0-9-]{2,63}")


def parse(command: str) -> list[str]:
    args = shlex.split(command)
    dispatch_prefix = [
        "/usr/bin/python3",
        "/opt/loop/worker_dispatch.py",
        "--config",
        "/etc/loop-worker/templates.json",
        "--template",
    ]
    if (
        len(args) == 8
        and args[:5] == dispatch_prefix
        and args[6] == "--job"
        and TEMPLATE.fullmatch(args[5])
        and JOB.fullmatch(args[7])
    ):
        return [
            "/usr/bin/sudo",
            "-n",
            "/opt/loop/worker_root.py",
            "dispatch",
            "--template",
            args[5],
            "--job",
            args[7],
        ]
    if (
        len(args) == 3
        and args[0] == "/opt/loop/worker_fetch"
        and args[1] == "--job"
        and JOB.fullmatch(args[2])
    ):
        return [
            "/usr/bin/sudo",
            "-n",
            "/opt/loop/worker_root.py",
            "fetch",
            "--job",
            args[2],
        ]
    raise ValueError("only fixed dispatch or exact bundle fetch is allowed")


def main() -> int:
    try:
        argv = parse(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    except (TypeError, ValueError):
        print("LOOP command denied", file=sys.stderr)
        return 126
    os.execve(argv[0], argv, {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
