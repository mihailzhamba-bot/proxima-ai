from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "openai-key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "telegram-token": re.compile(rb"\b[0-9]{8,10}:[A-Za-z0-9_-]{35}\b"),
}
FORBIDDEN_NAMES = re.compile(r"(^|/)(?:\.env(?:\..+)?|id_rsa|id_ed25519|.+\.(?:pem|key))$", re.IGNORECASE)


def git_paths(root: Path, *arguments: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", *arguments, "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [item.decode() for item in result.stdout.split(b"\0") if item]


def index_bytes(root: Path, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f":{relative}"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return result.stdout


def inspect(scope: str, relative: str, content: bytes) -> list[str]:
    found: list[str] = []
    location = f"{scope}:{relative}"
    if FORBIDDEN_NAMES.search(relative):
        return [f"{location}: forbidden secret filename"]
    if len(content) > 5_000_000 or b"\0" in content:
        return []
    for line_number, line in enumerate(content.splitlines(), start=1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                found.append(f"{location}:{line_number}: {label}")
    return found


def findings(root: Path = ROOT) -> list[str]:
    found: list[str] = []
    for relative in git_paths(root, "--cached"):
        found.extend(inspect("index", relative, index_bytes(root, relative)))
    for relative in git_paths(root, "--cached", "--others", "--exclude-standard"):
        path = root / relative
        if path.is_file():
            found.extend(inspect("worktree", relative, path.read_bytes()))
    return sorted(set(found))


def self_test() -> None:
    samples = {
        "private-key": b"-----BEGIN " + b"PRIVATE KEY-----",
        "aws-access-key": b"AKIA" + b"A" * 16,
        "github-token": b"ghp_" + b"a" * 36,
        "openai-key": b"sk-proj-" + b"a" * 36,
        "telegram-token": b"123456789:" + b"a" * 35,
    }
    for label, sample in samples.items():
        if not PATTERNS[label].search(sample):
            raise ValueError(f"secret scanner self-test failed: {label}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("secret scanner self-test passed")
        return
    result = findings()
    if result:
        raise ValueError("secret scan failed:\n" + "\n".join(result))
    print("secret scan passed")


if __name__ == "__main__":
    main()
