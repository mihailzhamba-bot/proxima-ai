#!/usr/bin/python3 -I
"""Create raw worker transport bytes inside a credential-free sandbox."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import uuid


WORKSPACES = Path("/srv/loop-worker/workspaces")
TRANSFER = Path("/srv/loop-worker/transfer")
JOB = re.compile(r"[a-z0-9][a-z0-9-]{2,40}")
TEMPLATE = re.compile(r"[a-z0-9][a-z0-9-]{2,63}")
SHA = re.compile(r"[a-f0-9]{40}")


def atomic_json(path: Path, value: dict) -> None:
    encoded = json.dumps(value, sort_keys=True).encode()
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def run_git(repository: Path, *arguments: str) -> str:
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/srv/loop-worker/collector-home",
        "TMPDIR": "/srv/loop-worker/collector-home/tmp",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    result = subprocess.run(
        [
            "/usr/bin/git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "safe.directory=*",
            "-C",
            str(repository),
            *arguments,
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError("untrusted workspace did not produce a bundle")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args()
    if not JOB.fullmatch(args.job) or not TEMPLATE.fullmatch(args.template) or not SHA.fullmatch(args.base_sha):
        raise SystemExit("invalid fixed collector identity")
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, "https://proxima.local/bad-dev-story")
    conversation_id = str(uuid.uuid5(namespace, args.job + "/1"))
    repository = WORKSPACES / conversation_id.replace("-", "") / "proxima-ai"
    output = TRANSFER / args.job
    if repository.is_symlink() or not (repository / ".git").is_dir():
        raise RuntimeError("deterministic workspace unavailable")
    if output.is_symlink() or not output.is_dir():
        raise RuntimeError("root-prepared transfer directory unavailable")
    branch = "feat/loop-" + args.job
    head = run_git(repository, "rev-parse", "--verify", "refs/heads/" + branch + "^{commit}")
    if not SHA.fullmatch(head):
        raise RuntimeError("worker head unavailable")
    commits = int(run_git(repository, "rev-list", "--count", args.base_sha + ".." + head))
    if commits <= 0:
        raise RuntimeError("worker produced no commits")
    bundle = output / "result.bundle"
    if bundle.exists() or bundle.is_symlink():
        raise RuntimeError("collector output already exists")
    run_git(repository, "bundle", "create", str(bundle), args.base_sha + "..refs/heads/" + branch)
    bundle.chmod(0o600)
    receipt = {
        "ok": True,
        "transport_only": True,
        "job": args.job,
        "template": args.template,
        "conversation_id": conversation_id,
        "branch": branch,
        "base_sha": args.base_sha,
        "head_sha": head,
        "commits": commits,
    }
    atomic_json(output / "receipt.json", receipt)
    print(json.dumps({"status": "collected", "transport_only": True}))


if __name__ == "__main__":
    main()
