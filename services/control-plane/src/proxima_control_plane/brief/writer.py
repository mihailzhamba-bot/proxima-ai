"""Запись сводки: одна строка дня плюс входы прогона (AD-3, AD-9)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import psycopg


@dataclass(frozen=True)
class BriefRow:
    """Строка сводки, готовая к записи. `payload` уже валиден по контракту."""

    brief_day: date
    status: str
    payload: dict


def write_brief(
    connection: psycopg.Connection,
    tenant_id: str,
    run_id: str,
    row: BriefRow,
    input_run_ids: list[str],
) -> None:
    """Вызывается внутри транзакции прогона (AD-3): частичной сводки не бывает."""
    connection.execute(
        """
        INSERT INTO brief_daily (tenant_id, brief_day, run_id, status, payload)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (tenant_id, row.brief_day, run_id, row.status, json.dumps(row.payload, ensure_ascii=False)),
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
