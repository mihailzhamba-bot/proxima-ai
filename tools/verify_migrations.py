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
LINE_COMMENT_START = "--"
BLOCK_COMMENT_START = "/*"
BLOCK_COMMENT_END = "*/"
STATEMENT_HEAD_PATTERN = re.compile(r"[A-Za-z]+")
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_.]*"
PAREN_PATTERN = re.compile(r"\([^)]*\)")
CREATE_OR_REPLACE_PATTERN = re.compile(r"\bCREATE\s+OR\s+REPLACE\b", re.IGNORECASE)
CREATE_RULE_PATTERN = re.compile(
    r"\bCREATE\s+(OR\s+REPLACE\s+)?(RULE|EVENT\s+TRIGGER|FUNCTION|PROCEDURE|EXTENSION|SUBSCRIPTION|PUBLICATION|FOREIGN\s+DATA\s+WRAPPER|FOREIGN\s+TABLE|DATABASE|USER|GROUP|LANGUAGE|ACCESS\s+METHOD|AGGREGATE|CAST|SERVER|TYPE|DOMAIN|OPERATOR|COLLATION|CONVERSION|TRANSFORM|PROCEDURAL|TEXT\s+SEARCH)\b",
    re.IGNORECASE,
)
BLANKET_BANNED_PATTERN = re.compile(
    r"\b(DROP|TRUNCATE|EXECUTE|SET_CONFIG)\b"
    r"|\bDO\s+UPDATE\b"
    r"|\b(SET|RESET)\s+(LOCAL\s+|SESSION\s+)?(ROLE|SESSION\s+AUTHORIZATION)\b",
    re.IGNORECASE,
)
# Fail-closed allowlist (B6): every statement head NOT in this set is banned,
# and ALTER TABLE is additionally restricted to purely additive/RLS-enabling forms.
ALLOWED_HEADS = frozenset({"BEGIN", "COMMIT", "CREATE", "GRANT", "INSERT"})
GRANT_ALLOWED_FORM = re.compile(
    r"^GRANT (SELECT|INSERT|UPDATE|USAGE)(, (SELECT|INSERT|UPDATE|USAGE))*"
    r" ON (SEQUENCE )?[A-Za-z_][A-Za-z0-9_.]* TO proxima_[a-z_]+$",
    re.IGNORECASE,
)
CREATE_ROLE_ALLOWED_FORM = re.compile(r"^CREATE ROLE proxima_[a-z_]+ NOLOGIN$", re.IGNORECASE)
CREATE_ALLOWED_OBJECTS = re.compile(
    r"^CREATE ((UNIQUE )?INDEX|TABLE|MATERIALIZED VIEW|SEQUENCE|POLICY)\b",
    re.IGNORECASE,
)
CREATE_VIEW_ALLOWED_FORM = re.compile(
    rf"^CREATE VIEW {IDENTIFIER} WITH \(security_invoker = true\) AS .*$",
    re.IGNORECASE | re.DOTALL,
)
CREATE_SCHEMA_ALLOWED_FORM = re.compile(r"^CREATE SCHEMA [A-Za-z_][A-Za-z0-9_]*$", re.IGNORECASE)
PAREN_PATTERN = re.compile(r"\([^)]*\)")
ALTER_TABLE_ALLOWED_FORM = re.compile(
    rf"^ALTER TABLE {IDENTIFIER} ADD COLUMN {IDENTIFIER} .*$"
    rf"|^ALTER TABLE {IDENTIFIER} ADD CONSTRAINT {IDENTIFIER}"
    r" (CHECK|UNIQUE|PRIMARY KEY|FOREIGN KEY|EXCLUDE)\b.*$"
    rf"|^ALTER TABLE {IDENTIFIER} ENABLE ROW LEVEL SECURITY$",
    re.IGNORECASE | re.DOTALL,
)


ALTER_ACTION_ALLOWED = re.compile(
    r"^(ADD COLUMN \S+ .*$"
    r"|ADD CONSTRAINT \S+ (CHECK|UNIQUE|PRIMARY KEY|FOREIGN KEY|EXCLUDE)\b.*$"
    r"|ENABLE ROW LEVEL SECURITY)$",
    re.IGNORECASE | re.DOTALL,
)


def assert_single_action_alter(candidate: str, name: str) -> None:
    """After removing parenthesized expressions, split the action list on
    commas; every action must be purely additive (ADD COLUMN / ADD
    CONSTRAINT), or the sole action ENABLE ROW LEVEL SECURITY."""
    head = re.match(rf"^(ALTER TABLE {IDENTIFIER}) (.*)$", candidate, re.IGNORECASE | re.DOTALL)
    if head is None:
        raise ValueError(f"migration contains banned ALTER statement: {name}")
    actions = [part.strip() for part in PAREN_PATTERN.sub(" ", head.group(2)).split(",") if part.strip()]
    if not actions:
        raise ValueError(f"migration contains banned ALTER statement: {name}")
    for action in actions:
        if not ALTER_ACTION_ALLOWED.match(action):
            raise ValueError(f"migration contains banned ALTER action ({' '.join(action.split()[:3])}): {name}")


def strip_sql_literals_and_comments(sql: str) -> str:
    """Single-pass scanner: emits SQL code, replaces comments (line/block)
    and string/dollar-quoted literals with spaces. Order-of-stripping
    bypasses (quotes inside comments, comment markers inside strings) are
    impossible by construction."""
    out: list[str] = []
    index = 0
    length = len(sql)
    while index < length:
        if sql.startswith(LINE_COMMENT_START, index):
            end = sql.find("\n", index)
            index = length if end == -1 else end
            out.append(" ")
            continue
        if sql.startswith(BLOCK_COMMENT_START, index):
            end = sql.find(BLOCK_COMMENT_END, index + 2)
            index = length if end == -1 else end + 2
            out.append(" ")
            continue
        char = sql[index]
        if char == "'":
            next_index = index + 1
            while next_index < length:
                if sql[next_index] == "'":
                    if next_index + 1 < length and sql[next_index + 1] == "'":
                        next_index += 2
                        continue
                    next_index += 1
                    break
                next_index += 1
            index = next_index
            out.append(" '?' ")
            continue
        if char == '"':
            next_index = index + 1
            while next_index < length:
                if sql[next_index] == '"':
                    if next_index + 1 < length and sql[next_index + 1] == '"':
                        next_index += 2
                        continue
                    next_index += 1
                    break
                next_index += 1
            index = next_index
            out.append(' "id" ')
            continue
        # Dollar-quoted bodies ($$...$$) are deliberately NOT stripped:
        # DO/plpgsql bodies are executable code and must stay scannable.
        out.append(char)
        index += 1
    return "".join(out)


def assert_additive_only(sql: str, name: str) -> None:
    """Additive-only doctrine (B6, Phase 3 CONTEXT 2026-08-25): migrations may
    create and extend objects but never destroy or rewrite them. Fail-closed:
    only the statement forms in ALLOWED_HEADS (plus the ALTER TABLE allowlist
    below) are accepted; everything else is rejected."""
    stripped = strip_sql_literals_and_comments(sql)
    if CREATE_OR_REPLACE_PATTERN.search(stripped):
        raise ValueError(f"migration uses banned CREATE OR REPLACE: {name}")
    if CREATE_RULE_PATTERN.search(stripped):
        raise ValueError(f"migration uses banned CREATE RULE/EVENT TRIGGER: {name}")
    if BLANKET_BANNED_PATTERN.search(stripped):
        raise ValueError(f"migration contains DROP/TRUNCATE/EXECUTE (dynamic SQL): {name}")
    for statement in stripped.split(";"):
        candidate = " ".join(statement.split())
        if not candidate:
            continue
        head = STATEMENT_HEAD_PATTERN.match(candidate)
        if head is None:
            raise ValueError(f"migration statement is not recognizable SQL: {name}")
        keyword = head.group(0).upper()
        if keyword == "ALTER":
            assert_single_action_alter(candidate, name)
            continue
        if keyword == "GRANT":
            if not GRANT_ALLOWED_FORM.match(candidate):
                raise ValueError(f"migration contains banned GRANT form: {name}")
            continue
        if candidate.upper().startswith("CREATE ROLE "):
            if not CREATE_ROLE_ALLOWED_FORM.match(candidate):
                raise ValueError(f"migration contains banned CREATE ROLE form: {name}")
            continue
        if candidate.upper().startswith("CREATE SCHEMA "):
            if not CREATE_SCHEMA_ALLOWED_FORM.match(candidate):
                raise ValueError(f"migration contains banned CREATE SCHEMA form: {name}")
            continue
        if keyword == "CREATE":
            if candidate.upper().startswith("CREATE VIEW "):
                if not CREATE_VIEW_ALLOWED_FORM.match(candidate):
                    raise ValueError(f"migration contains banned CREATE VIEW form (security_invoker = true required): {name}")
                continue
            if not CREATE_ALLOWED_OBJECTS.match(candidate):
                raise ValueError(f"migration contains banned CREATE object form: {name}")
            continue
        if keyword not in ALLOWED_HEADS:
            raise ValueError(f"migration contains non-additive statement ({keyword}): {name}")


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
