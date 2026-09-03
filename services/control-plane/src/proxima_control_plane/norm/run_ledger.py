"""Реестр прогонов на Python: тот же контракт, что у `RunLedger` коллектора (AD-3).

Код коллектора не переиспользуется - он на TypeScript; переиспользуется правило:
`RUNNING` автокоммитом, работа и `SUCCEEDED` одной транзакцией, `FAILED` отдельно.
Частичных прогонов не существует.
"""

from __future__ import annotations

import os
import uuid
from typing import Callable

import psycopg

from proxima_control_plane.norm.log import log_run_event

KIND = "norm"


class RunLedgerError(RuntimeError):
    pass


def open_run(connection: psycopg.Connection, tenant_id: str, notes: str | None = None) -> str:
    run_id = str(uuid.uuid4())
    connection.execute(
        """
        INSERT INTO collector_runs (run_id, tenant_id, kind, status, git_sha, image_id, notes)
        VALUES (%s, %s, %s, 'RUNNING', %s, %s, %s)
        """,
        (run_id, tenant_id, KIND, _env("PROXIMA_GIT_SHA"), _env("PROXIMA_IMAGE_ID"), notes),
    )
    log_run_event("running", run_id, tenant_id)
    return run_id


def succeed(
    connection: psycopg.Connection,
    tenant_id: str,
    run_id: str,
    work: Callable[[psycopg.Connection], None],
) -> None:
    """Работа и перевод в `SUCCEEDED` - одна транзакция; при ошибке откат целиком."""
    with connection.transaction():
        work(connection)
        cursor = connection.execute(
            """
            UPDATE collector_runs SET status = 'SUCCEEDED', finished_at = CURRENT_TIMESTAMP
            WHERE run_id = %s AND status = 'RUNNING'
            """,
            (run_id,),
        )
        if cursor.rowcount != 1:
            raise RunLedgerError(
                f"cannot mark run {run_id} SUCCEEDED: expected one RUNNING row visible to tenant "
                f"{tenant_id}, updated {cursor.rowcount}"
            )
    log_run_event("succeeded", run_id, tenant_id)


def fail(connection: psycopg.Connection, tenant_id: str, run_id: str) -> None:
    cursor = connection.execute(
        """
        UPDATE collector_runs SET status = 'FAILED', finished_at = CURRENT_TIMESTAMP
        WHERE run_id = %s AND status = 'RUNNING'
        """,
        (run_id,),
    )
    if cursor.rowcount != 1:
        raise RunLedgerError(
            f"cannot mark run {run_id} FAILED: expected one RUNNING row visible to tenant "
            f"{tenant_id}, updated {cursor.rowcount}"
        )
    log_run_event("failed", run_id, tenant_id)


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value or None
