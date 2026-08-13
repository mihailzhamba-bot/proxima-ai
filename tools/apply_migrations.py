from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import psycopg

import verify_migrations
from wb_async_report import WbAsyncReportError, connect_repository, read_env_file


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "db" / "migrations"
LEDGER_PATTERN = re.compile(
    r"VALUES \(([0-9]+), '([a-z][a-z0-9_]{1,63})', '([0-9a-f]{64})'\);"
)


def migration_identity(path: Path) -> tuple[int, str, str]:
    match = LEDGER_PATTERN.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise WbAsyncReportError(f"migration ledger identity missing: {path.name}")
    version, name, checksum = match.groups()
    return int(version), name, checksum


def applied_migrations(connection: psycopg.Connection[dict[str, object]]) -> dict[int, tuple[str, str]]:
    exists = connection.execute("SELECT to_regclass('public.schema_migrations') AS table_name").fetchone()
    if exists is None or exists["table_name"] is None:
        return {}
    rows = connection.execute("SELECT version, name, sha256 FROM schema_migrations ORDER BY version").fetchall()
    return {int(row["version"]): (str(row["name"]), str(row["sha256"])) for row in rows}


def apply_pending(connection: psycopg.Connection[dict[str, object]]) -> list[str]:
    verify_migrations.verify()
    applied = applied_migrations(connection)
    completed: list[str] = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        version, name, checksum = migration_identity(path)
        current = applied.get(version)
        if current is not None:
            if current != (name, checksum):
                raise WbAsyncReportError(f"applied migration checksum mismatch: {path.name}")
            continue
        connection.execute(path.read_text(encoding="utf-8"), prepare=False)
        recorded = applied_migrations(connection).get(version)
        if recorded != (name, checksum):
            raise WbAsyncReportError(f"migration did not record its identity: {path.name}")
        applied[version] = recorded
        completed.append(path.name)
    return completed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply verified additive PROXIMA AI migrations")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repository = connect_repository(read_env_file(args.env_file))
    completed = apply_pending(repository.connection)
    print("migrations: " + (", ".join(completed) if completed else "already current"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (WbAsyncReportError, psycopg.Error) as error:
        print(f"migrations: failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
