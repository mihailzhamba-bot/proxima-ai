from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"
SELF_MARKER = b"<SELF_SHA256>"
SELF_PATTERN = re.compile(
    rb"(VALUES \(1, 'bootstrap', ')[0-9a-f]{64}('\);)",
)


def normalized_sha256(content: bytes) -> str:
    normalized, replacements = SELF_PATTERN.subn(rb"\1" + SELF_MARKER + rb"\2", content)
    if replacements != 1:
        raise ValueError("bootstrap migration must contain exactly one self checksum")
    return hashlib.sha256(normalized).hexdigest()


def verify() -> None:
    paths = sorted(MIGRATIONS.glob("*.sql"))
    expected = [f"{number:03d}_" for number in range(1, len(paths) + 1)]
    for path, prefix in zip(paths, expected, strict=True):
        if not path.name.startswith(prefix):
            raise ValueError(f"migration order gap at {path.name}")
        content = path.read_bytes()
        if not content.startswith(b"BEGIN;\n") or not content.endswith(b"COMMIT;\n"):
            raise ValueError(f"migration is not transaction bounded: {path.name}")

    bootstrap = MIGRATIONS / "001_bootstrap.sql"
    content = bootstrap.read_bytes()
    match = SELF_PATTERN.search(content)
    if match is None:
        raise ValueError("bootstrap self checksum missing")
    recorded = content[match.start(0) : match.end(0)].split(b"'")[-2].decode()
    if recorded != normalized_sha256(content):
        raise ValueError("bootstrap self checksum mismatch")


if __name__ == "__main__":
    verify()
    print("migration verification passed")
