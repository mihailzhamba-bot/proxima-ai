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
    r"^CREATE ((UNIQUE )?INDEX|TABLE|SEQUENCE|POLICY)\b",
    re.IGNORECASE,
)
TENANT_GUARD = r"tenant_id\s*=\s*current_setting\s*\(\s*<GUC>\s*,\s*true\s*\)"
CREATE_POLICY_ALLOWED_FORM = re.compile(
    rf"^CREATE\ POLICY\ [A-Za-z_][A-Za-z0-9_]*\ ON\ {IDENTIFIER}"
    r"\ FOR\ (SELECT|ALL|INSERT|UPDATE)\ TO\ proxima_[a-z_]+"
    rf"\ USING\ \(\s*{TENANT_GUARD}\s*\)"
    rf"(\ WITH\ CHECK\ \(\s*{TENANT_GUARD}\s*\))?$"
    r"|^CREATE\ POLICY\ [A-Za-z_][A-Za-z0-9_]*\ ON\ [A-Za-z_][A-Za-z0-9_.]*"
    r"\ FOR\ SELECT\ TO\ proxima_[a-z_]+"
    r"\ USING\ \(\s*EXISTS\ \(\s*SELECT\ 1\ FROM\ wb_analytics_report_tasks\ t"
    r"\ WHERE\ t\.task_id\s*=\s*[A-Za-z_][A-Za-z0-9_]*\.task_id"
    rf"\ AND\ t\.tenant_id\s*=\s*current_setting\s*\(\s*<GUC>\s*,\s*true\s*\)\s*\)\s*\)\s*$",
    re.IGNORECASE,
)
VALUE_TOKEN = r"(\s*'\?'\s*|\s*NULL\s*|\s*TRUE\s*|\s*FALSE\s*|\s*-?[0-9]+(\.[0-9]+)?\s*)"
INSERT_ALLOWED_FORM = re.compile(
    rf"^INSERT INTO {IDENTIFIER}\s*(\(\s*[A-Za-z_][A-Za-z0-9_]*(\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*\s*\))?\s*"
    rf"VALUES\s*\({VALUE_TOKEN}(\s*,\s*{VALUE_TOKEN})*\s*\)"
    rf"(\s*,\s*\({VALUE_TOKEN}(\s*,\s*{VALUE_TOKEN})*\s*\)\s*)*"
    r"(\s+ON CONFLICT\s*\(\s*[A-Za-z_][A-Za-z0-9_]*(\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*\s*\)\s+DO NOTHING\s*)?\s*$",
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
    if len(actions) > 1 and any(action.upper() == "ENABLE ROW LEVEL SECURITY" for action in actions):
        raise ValueError(f"migration combines ENABLE ROW LEVEL SECURITY with other actions: {name}")


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


QUOTED_SET_CONFIG_PATTERN = re.compile(r"[\"']\s*set_config\s*[\"']", re.IGNORECASE)
GRANT_PARSED_PATTERN = re.compile(
    r"^GRANT ((?:SELECT|INSERT|UPDATE|USAGE)(?:, (?:SELECT|INSERT|UPDATE|USAGE))*)"
    r" ON (SEQUENCE )?([A-Za-z_][A-Za-z0-9_.]*) TO (proxima_[a-z_]+)$",
    re.IGNORECASE,
)


def assert_single_transaction(statements: list[str], name: str) -> None:
    heads = [STATEMENT_HEAD_PATTERN.match(x).group(0).upper() for x in statements if x]
    if heads.count("BEGIN") != 1 or heads.count("COMMIT") != 1:
        raise ValueError(f"migration must be exactly one BEGIN..COMMIT transaction: {name}")
    if heads[0] != "BEGIN" or heads[-1] != "COMMIT":
        raise ValueError(f"migration transaction markers misplaced: {name}")


def assert_grant_matrix(candidate: str, name: str) -> None:
    match = GRANT_PARSED_PATTERN.match(candidate)
    if match is None:
        raise ValueError(f"migration contains banned GRANT form: {name}")
    privileges = {part.strip().upper() for part in match.group(1).split(",")}
    obj = match.group(3).lower().split(".")[-1]
    role = match.group(4).lower()
    if role == "proxima_data_health_read" and privileges - {"SELECT"}:
        raise ValueError(f"migration grants write privileges to the read-only role: {name}")
    if obj == "schema_migrations":
        if role != "proxima_migration_owner" or privileges - {"SELECT", "INSERT", "UPDATE"}:
            raise ValueError(f"migration grants schema_migrations outside the migration owner: {name}")


def assert_additive_only(sql: str, name: str) -> None:
    """Additive-only doctrine (B6, Phase 3 CONTEXT 2026-08-25): migrations may
    create and extend objects but never destroy or rewrite them. Fail-closed:
    only the statement forms in ALLOWED_HEADS (plus the ALTER TABLE allowlist
    below) are accepted; everything else is rejected."""
    if QUOTED_SET_CONFIG_PATTERN.search(sql):
        raise ValueError(f"migration references set_config (quoted or not): {name}")
    marked = sql.replace("'proxima.tenant_id'", "<GUC>")
    stripped = strip_sql_literals_and_comments(marked)
    if CREATE_OR_REPLACE_PATTERN.search(stripped):
        raise ValueError(f"migration uses banned CREATE OR REPLACE: {name}")
    if CREATE_RULE_PATTERN.search(stripped):
        raise ValueError(f"migration uses banned CREATE RULE/EVENT TRIGGER: {name}")
    if BLANKET_BANNED_PATTERN.search(stripped):
        raise ValueError(f"migration contains DROP/TRUNCATE/EXECUTE (dynamic SQL): {name}")
    candidates = [" ".join(statement.split()) for statement in stripped.split(";")]
    candidates = [c for c in candidates if c]
    assert_single_transaction(candidates, name)
    for candidate in candidates:
        head = STATEMENT_HEAD_PATTERN.match(candidate)
        if head is None:
            raise ValueError(f"migration statement is not recognizable SQL: {name}")
        keyword = head.group(0).upper()
        if keyword == "ALTER":
            assert_single_action_alter(candidate, name)
            continue
        if keyword == "GRANT":
            assert_grant_matrix(candidate, name)
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
            if candidate.upper().startswith("CREATE POLICY "):
                if not CREATE_POLICY_ALLOWED_FORM.match(candidate):
                    raise ValueError(f"migration creates a policy outside the canonical tenant-isolation template: {name}")
                continue
            if not CREATE_ALLOWED_OBJECTS.match(candidate):
                raise ValueError(f"migration contains banned CREATE object form: {name}")
            if re.search(r"\bCONCURRENTLY\b", candidate, re.IGNORECASE):
                raise ValueError(f"migration uses CONCURRENTLY (invalid inside a transaction): {name}")
            if candidate.upper().startswith("CREATE TABLE "):
                if not re.search(rf"^CREATE TABLE (IF NOT EXISTS )?{IDENTIFIER} \(", candidate, re.IGNORECASE):
                    raise ValueError(f"migration uses CREATE TABLE AS (data-copy) form: {name}")
                if re.search(r"\bAS\s+SELECT\b", candidate, re.IGNORECASE):
                    raise ValueError(f"migration uses CREATE TABLE AS SELECT (data-copy) form: {name}")
            continue
        if keyword == "INSERT":
            if not INSERT_ALLOWED_FORM.match(candidate):
                raise ValueError(f"migration uses INSERT outside the plain literal-VALUES form: {name}")
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
