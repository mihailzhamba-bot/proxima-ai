"""Запись нормы: две строки на день (заказы и выручка) плюс входы прогона."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg

from proxima_control_plane.norm.median import WINDOW_DAYS


@dataclass(frozen=True)
class NormRow:
    """Строка нормы, готовая к записи. `value` уже округлён по D27."""

    metric: str
    value: Decimal
    sample_days: int
    status: str
    source_sha256: tuple[str, ...]


def write_norm(
    connection: psycopg.Connection,
    tenant_id: str,
    run_id: str,
    evaluation_day: date,
    rows: list[NormRow],
    input_run_ids: list[str],
) -> None:
    """Вызывается внутри транзакции прогона (AD-3): частичной нормы не бывает."""
    for row in rows:
        connection.execute(
            """
            INSERT INTO norm_daily
                (tenant_id, evaluation_day, metric, run_id, window_days, sample_days, value, status, source_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                evaluation_day,
                row.metric,
                run_id,
                WINDOW_DAYS,
                row.sample_days,
                row.value,
                row.status,
                list(row.source_sha256),
            ),
        )
    if input_run_ids:
        connection.execute(
            """
            INSERT INTO collector_run_inputs (tenant_id, run_id, input_run_id)
            SELECT %s, %s, unnest(%s::uuid[])
            ON CONFLICT (tenant_id, run_id, input_run_id) DO NOTHING
            """,
            (tenant_id, run_id, input_run_ids),
        )
