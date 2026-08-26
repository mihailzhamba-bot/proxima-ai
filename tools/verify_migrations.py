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
LINE_COMMENT_PATTERN = re.compile(r"--[^\n]*")
BLOCK_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
STRING_LITERAL_PATTERN = re.compile(r"'(?:[^']|'')*'")
DOLLAR_STRING_PATTERN = re.compile(r"\$[A-Za-z_]*\$.*?\$[A-Za-z_]*\$", re.DOTALL)
BANNED_STATEMENT_PREFIXES = ("DROP", "TRUNCATE")
BANNED_PREFIX_PATTERN = re.compile(r"^[A-Z]+")
ALTER_TABLE_FORBIDDEN = re.compile(r"\b(DROP|TYPE|RENAME)\b")
CREATE_OR_REPLACE_PATTERN = re.compile(r"\bCREATE\s+OR\s+REPLACE\b")


def strip_sql_literals_and_comments(sql: str) -> str:
    stripped = BLOCK_COMMENT_PATTERN.sub(" ", sql)
    stripped = DOLLAR_STRING_PATTERN.sub(" '$' ", stripped)
    stripped = STRING_LITERAL_PATTERN.sub(" '?' ", stripped)
    stripped = LINE_COMMENT_PATTERN.sub(" ", stripped)
    return stripped


def assert_additive_only(sql: str, name: str) -> None:
    """Additive-only doctrine (B6, Phase 3 CONTEXT 2026-08-25): migrations may
    create and extend objects but never destroy or rewrite them."""
    stripped = strip_sql_literals_and_comments(sql)
    if CREATE_OR_REPLACE_PATTERN.search(stripped):
        raise ValueError(f"migration uses banned CREATE OR REPLACE: {name}")
    for statement in stripped.split(";"):
        candidate = statement.strip()
        if not candidate:
            continue
        keyword = BANNED_PREFIX_PATTERN.match(candidate.upper())
        if keyword is None:
            continue
        head = candidate.upper().split(None, 1)[0]
        if head in BANNED_STATEMENT_PREFIXES or candidate.upper().startswith("DROP "):
            raise ValueError(f"migration contains destructive statement ({head}): {name}")
        if re.match(r"ALTER\s+TABLE\b", candidate.upper()) and ALTER_TABLE_FORBIDDEN.search(candidate.upper()):
            raise ValueError(f"migration contains banned ALTER TABLE rewrite: {name}")


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
        assert_additive_only(content.decode("utf-8"), path.name)


if __name__ == "__main__":
    verify()
    print("migration verification passed")
