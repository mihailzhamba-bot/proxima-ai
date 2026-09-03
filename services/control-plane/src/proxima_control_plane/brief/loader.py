"""Вход сводки: соединение под ролью norm, GUC арендатора, чтение версий.

Роль - `proxima_job_norm` (AD-9: пишет сводку тот же джоб, что считает норму).
Значение строки подключения нигде не печатается - ни в лог, ни в исключение:
наружу выходит только имя переменной или пути (политика секретов AGENTS.md).
"""

from __future__ import annotations

import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg

from proxima_control_plane.brief.builder import DataStatus, MetricActual, MetricNorm
from proxima_control_plane.norm.loader import validate_tenant

DSN_ENV = "PROXIMA_TEST_DSN_NORM"
DSN_FILE_ENV = "NORM_DATABASE_URI_FILE"
TENANT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


def resolve_dsn() -> str:
    """Harness даёт DSN переменной, сервер - путём к файлу. Угадывать нечего."""
    dsn = os.environ.get(DSN_ENV)
    if dsn:
        return dsn
    path = os.environ.get(DSN_FILE_ENV)
    if not path:
        raise RuntimeError(f"neither {DSN_ENV} nor {DSN_FILE_ENV} is set: refusing to guess a connection")
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError(f"{DSN_FILE_ENV} points at an empty file: {path}")
    return value


def connect(tenant_id: str) -> psycopg.Connection:
    """Соединение с GUC арендатора первым statement - иначе RLS не пустит (AD-13)."""
    connection = psycopg.connect(resolve_dsn(), autocommit=True)
    try:
        connection.execute("SELECT set_config('proxima.tenant_id', %s, false)", (tenant_id,))
    except Exception:
        connection.close()
        raise
    return connection


def read_data_status(connection: psycopg.Connection, tenant_id: str) -> DataStatus | None:
    row = connection.execute(
        """
        SELECT last_full_day, collected_at, stale
        FROM data_status_current
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    return DataStatus(last_full_day=row[0], collected_at=row[1].isoformat(), stale=bool(row[2]))


def read_actual(connection: psycopg.Connection, tenant_id: str, brief_day: date) -> MetricActual | None:
    """Версия оцениваемого дня из `fact_cabinet_daily_current` (AD-9)."""
    row = connection.execute(
        """
        SELECT orders_count, revenue_rub
        FROM fact_cabinet_daily_current
        WHERE tenant_id = %s AND calendar_day = %s
        """,
        (tenant_id, brief_day),
    ).fetchone()
    if row is None:
        return None
    return MetricActual(orders=int(row[0]), revenue=Decimal(row[1]))


def read_norms(connection: psycopg.Connection, tenant_id: str, brief_day: date) -> list[MetricNorm]:
    """Все строки нормы за день из `norm_daily_current` (пусто = blocked)."""
    rows = connection.execute(
        """
        SELECT metric, value, window_days, sample_days, status
        FROM norm_daily_current
        WHERE tenant_id = %s AND evaluation_day = %s
        ORDER BY metric
        """,
        (tenant_id, brief_day),
    ).fetchall()
    return [
        MetricNorm(
            metric=row[0],
            value=Decimal(row[1]),
            window_days=int(row[2]),
            sample_days=int(row[3]),
            status=row[4],
        )
        for row in rows
    ]


def read_norm_input_run_ids(connection: psycopg.Connection, tenant_id: str, brief_day: date) -> list[str]:
    """Прогоны-источники строк нормы за день - вход сводки в `run_inputs` (AD-9)."""
    rows = connection.execute(
        """
        SELECT DISTINCT n.run_id::text
        FROM norm_daily n
        JOIN collector_runs r ON r.run_id = n.run_id AND r.tenant_id = n.tenant_id
        WHERE n.tenant_id = %s AND n.evaluation_day = %s AND r.status = 'SUCCEEDED'
        ORDER BY 1
        """,
        (tenant_id, brief_day),
    ).fetchall()
    return [row[0] for row in rows]


def read_fact_run_ids(connection: psycopg.Connection, tenant_id: str, brief_day: date) -> list[str]:
    """Прогоны-источники версии дня из `fact_cabinet_daily_current` (AD-9)."""
    rows = connection.execute(
        """
        SELECT DISTINCT f.run_id::text
        FROM fact_cabinet_daily f
        JOIN collector_runs r ON r.run_id = f.run_id AND r.tenant_id = f.tenant_id
        WHERE f.tenant_id = %s AND f.calendar_day = %s
          AND r.status = 'SUCCEEDED'
          AND r.finished_at = (
              SELECT max(r2.finished_at)
              FROM fact_cabinet_daily f2
              JOIN collector_runs r2 ON r2.run_id = f2.run_id AND r2.tenant_id = f2.tenant_id
              WHERE f2.tenant_id = f.tenant_id AND f2.calendar_day = f.calendar_day AND r2.status = 'SUCCEEDED'
          )
        ORDER BY 1
        """,
        (tenant_id, brief_day),
    ).fetchall()
    return [row[0] for row in rows]


__all__ = [
    "connect",
    "read_actual",
    "read_data_status",
    "read_fact_run_ids",
    "read_norm_input_run_ids",
    "read_norms",
    "resolve_dsn",
    "validate_tenant",
]
