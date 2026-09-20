#!/usr/bin/env python3
"""Transitive run rollback (Story 1.7, AD-3).

Deletes one collector run together with everything that transitively depends
on it through `collector_run_inputs`, in a single transaction, as the
`proxima_run_janitor` role. Deleting a backfill walk therefore removes the
whole closure down to the `collect` inputs; deleting a FAILED run removes only
the run row and its `wb_raw_artifacts` rows (a failed run has no dependants).
Content-addressed artifact files on disk are never touched.

Contract (AD-3 / Story 1.7):
  * both --tenant and --run are mandatory;
  * the first statement on the connection is `set_config('proxima.tenant_id',
    $1, false)` (AD-13 session GUC); without it RLS hides the run and the
    tool must fail loudly with "0 строк для run_id" instead of deleting zero
    rows silently;
  * the whole deletion is one transaction: closure rows, artifacts and the
    run row, with row counts printed as a machine-readable JSON line.

Connection: JANITOR_DATABASE_URI_FILE (production) or JANITOR_DATABASE_URI
(harness: tools/pg_local_roundtrip.sh exports PROXIMA_TEST_DSN_JANITOR for the
db tests, while the tool itself always reads one of the variables above).

A missing --tenant means the session GUC is never set, so RLS hides every row
and the run ends with the contract error "0 строк для run_id" - an error, never
a zero-row success (Story 1.7 AC).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import uuid
from collections import deque
from pathlib import Path

import psycopg

GUC = "proxima.tenant_id"


class DeleteRunError(RuntimeError):
    """Any contract violation or refused deletion."""


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete a collector run and its transitive dependants (AD-3)",
        allow_abbrev=False,
    )
    # Not argparse-required on purpose: a missing --tenant must reach the
    # closure guard and die with the "0 строк для run_id" wording (the GUC is
    # never set, so RLS hides the run), instead of a usage error.
    parser.add_argument("--tenant", help="tenant ID, e.g. pilot-tenant")
    parser.add_argument("--run", required=True, help="run UUID (collector_runs.run_id)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the transitive closure counts without deleting anything",
    )
    return parser.parse_args(argv if argv is not None else sys.argv[1:])


def read_uri_file(path: Path) -> str:
    """Private regular file with exactly one DSN; the value never goes to output."""
    if path.is_symlink() or not path.is_file():
        raise DeleteRunError(f"janitor URI file must be a regular file: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise DeleteRunError(f"janitor URI file has unsafe permissions: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value or any(character.isspace() for character in value):
        raise DeleteRunError(f"janitor URI file must contain exactly one non-empty value: {path}")
    return value


def janitor_dsn(env: dict[str, str] | None = None) -> str:
    environment = env if env is not None else os.environ
    uri_file = environment.get("JANITOR_DATABASE_URI_FILE")
    if uri_file:
        return read_uri_file(Path(uri_file))
    uri = environment.get("JANITOR_DATABASE_URI")
    if uri:
        return uri
    raise DeleteRunError("JANITOR_DATABASE_URI_FILE (or JANITOR_DATABASE_URI) is required")


def parse_run_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as error:
        raise DeleteRunError("--run must be a UUID") from error


def closure_run_ids(inputs: dict[uuid.UUID, list[uuid.UUID]], root: uuid.UUID) -> list[uuid.UUID]:
    """Transitive closure of AD-3 in both directions.

    `collector_run_inputs` stores run -> input_run_id edges. From the root the
    closure walks the inputs upward (deleting a backfill removes every collect
    that fed it - the documented "полная переборка") and then eliminates every
    downstream dependant of everything in the set, so no orphaned consumer of a
    deleted run survives.
    """
    upward: set[uuid.UUID] = {root}
    queue: deque[uuid.UUID] = deque([root])
    while queue:
        run_id = queue.popleft()
        for input_run_id in inputs.get(run_id, ()):
            if input_run_id not in upward:
                upward.add(input_run_id)
                queue.append(input_run_id)
    dependants: dict[uuid.UUID, list[uuid.UUID]] = {}
    for run_id, consumed in inputs.items():
        for input_run_id in consumed:
            dependants.setdefault(input_run_id, []).append(run_id)
    seen: set[uuid.UUID] = set(upward)
    queue = deque(upward)
    while queue:
        run_id = queue.popleft()
        for dependent in dependants.get(run_id, ()):
            if dependent not in seen:
                seen.add(dependent)
                queue.append(dependent)
    return sorted(seen, key=lambda item: item.bytes)


def fetch_inputs(connection: psycopg.Connection, tenant_id: str, root: uuid.UUID) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Edges of the closure around `root`, expanded until the frontier is empty.

    One query around the root is not enough: it returns a single hop, and the
    closure is transitive by definition (AD-3). In the daily chain
    `collect -> norm -> brief` the edges are (norm, collect) and (brief, norm),
    so a one-hop fetch around `collect` never sees `brief` - and because
    `collector_run_inputs.input_run_id` is ON DELETE RESTRICT, the deletion then
    fails on a live referencing row instead of quietly dropping fewer rows.

    So the frontier is expanded instead: every newly discovered run is queried in
    the next round, until a round adds nothing. Bounded by the size of the actual
    closure, not by the size of the table.
    """
    if tenant_id is None:
        return {}
    inputs: dict[uuid.UUID, list[uuid.UUID]] = {}
    seen: set[uuid.UUID] = set()
    frontier: set[uuid.UUID] = {root}
    while frontier:
        rows = connection.execute(
            """
            SELECT i.run_id, i.input_run_id
            FROM collector_run_inputs i
            JOIN collector_runs r ON r.run_id = i.run_id AND r.tenant_id = i.tenant_id
            WHERE i.tenant_id = %s AND (i.run_id = ANY(%s) OR i.input_run_id = ANY(%s))
            """,
            (tenant_id, list(frontier), list(frontier)),
        ).fetchall()
        seen |= frontier
        discovered: set[uuid.UUID] = set()
        for run_id, input_run_id in rows:
            if input_run_id not in inputs.setdefault(run_id, []):
                inputs[run_id].append(input_run_id)
            discovered.update({run_id, input_run_id})
        frontier = discovered - seen
    return inputs


def compute_plan(connection: psycopg.Connection, tenant_id: str | None, root: uuid.UUID) -> dict[str, int]:
    """Row counts the deletion would remove, under the caller's RLS visibility."""
    if connection.execute(
        "SELECT count(*) FROM collector_runs WHERE run_id = %s", (root,)
    ).fetchone()[0] == 0:
        known = f" {root}" if tenant_id is not None else ""
        raise DeleteRunError(f"0 строк для run_id{known}")
    run_ids = closure_run_ids(fetch_inputs(connection, tenant_id, root), root)
    artifacts = connection.execute(
        "SELECT count(*) FROM wb_raw_artifacts WHERE run_id = ANY(%s::uuid[])", (run_ids,)
    ).fetchone()[0]
    inputs = connection.execute(
        "SELECT count(*) FROM collector_run_inputs WHERE run_id = ANY(%s::uuid[])", (run_ids,)
    ).fetchone()[0]
    return {"runs": len(run_ids), "artifacts": artifacts, "run_inputs": inputs}


def delete_in_one_transaction(
    connection: psycopg.Connection,
    root: uuid.UUID,
    run_ids: list[uuid.UUID],
) -> dict[str, int]:
    """The whole rollback is a single transaction (AD-3); any error rolls it
    all back and the run stays exactly as it was."""
    try:
        connection.execute("BEGIN")
        artifacts = connection.execute(
            "SELECT count(*) FROM wb_raw_artifacts WHERE run_id = ANY(%s::uuid[])", (run_ids,)
        ).fetchone()[0]
        inputs = connection.execute(
            "SELECT count(*) FROM collector_run_inputs WHERE run_id = ANY(%s::uuid[])", (run_ids,)
        ).fetchone()[0]
        connection.execute("DELETE FROM wb_raw_artifacts WHERE run_id = ANY(%s::uuid[])", (run_ids,))
        # input edges first: input_run_id carries ON DELETE RESTRICT (AD-3)
        connection.execute("DELETE FROM collector_run_inputs WHERE run_id = ANY(%s::uuid[])", (run_ids,))
        connection.execute("DELETE FROM collector_runs WHERE run_id = ANY(%s::uuid[])", (run_ids,))
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return {"runs": len(run_ids), "artifacts": artifacts, "run_inputs": inputs}


def run_deletion(connection: psycopg.Connection, tenant_id: str | None, root: uuid.UUID, dry_run: bool) -> dict[str, int]:
    plan = compute_plan(connection, tenant_id, root)
    if dry_run:
        return plan
    inputs = fetch_inputs(connection, tenant_id, root)
    run_ids = closure_run_ids(inputs, root)
    return delete_in_one_transaction(connection, root, run_ids)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        tenant_id = args.tenant
        if tenant_id is not None and not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", tenant_id):
            raise DeleteRunError("--tenant must be a valid tenant ID")
        root = parse_run_id(args.run)
        connection = psycopg.connect(janitor_dsn(), autocommit=True)
    except DeleteRunError as error:
        print(f"delete_run: {error}", file=sys.stderr)
        return 1
    try:
        # First statement of the session, AD-13: the tenant GUC drives every
        # RLS policy this session touches. Without --tenant the GUC never
        # exists, RLS hides the run, and the closure guard below fires the
        # contract error instead of a silent zero-row success.
        if tenant_id is not None:
            connection.execute("SELECT set_config(%s, %s, false)", (GUC, tenant_id))
        counts = run_deletion(connection, tenant_id, root, args.dry_run)
    except DeleteRunError as error:
        print(f"delete_run: {error}", file=sys.stderr)
        return 1
    finally:
        connection.close()
    mode = "dry-run" if args.dry_run else "deleted"
    print(f"delete_run: {mode} closure {json.dumps(counts, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
