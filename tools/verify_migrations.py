from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"
SELF_MARKER = b"<SELF_SHA256>"
SELF_PATTERN = re.compile(
    rb"(VALUES \(([0-9]+), '([a-z][a-z0-9_]{1,63})', ')[0-9a-f]{64}('\);)",
)
FILENAME_PATTERN = re.compile(r"^([0-9]{3})_([a-z][a-z0-9_]{1,63})\.sql$")


def normalized_sha256(content: bytes) -> str:
    normalized, replacements = SELF_PATTERN.subn(rb"\1" + SELF_MARKER + rb"\4", content)
    if replacements != 1:
        raise ValueError("migration must contain exactly one self checksum")
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
        filename = FILENAME_PATTERN.fullmatch(path.name)
        if filename is None:
            raise ValueError(f"migration filename is invalid: {path.name}")
        version, name = filename.groups()
        matches = list(SELF_PATTERN.finditer(content))
        if len(matches) != 1:
            raise ValueError(f"migration self checksum missing or ambiguous: {path.name}")
        match = matches[0]
        recorded_version, recorded_name = match.group(2).decode(), match.group(3).decode()
        recorded_sha256 = content[match.start(0) : match.end(0)].split(b"'")[-2].decode()
        if (recorded_version, recorded_name) != (str(int(version)), name):
            raise ValueError(f"migration ledger identity mismatch: {path.name}")
        if recorded_sha256 != normalized_sha256(content):
            raise ValueError(f"migration self checksum mismatch: {path.name}")


if __name__ == "__main__":
    verify()
    print("migration verification passed")
