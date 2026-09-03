"""Вход нормы: соединение под ролью norm, GUC арендатора, дни окна из версий фактов.

Значение строки подключения нигде не печатается - ни в лог, ни в исключение:
наружу выходит только имя переменной или пути (политика секретов AGENTS.md).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg

DSN_ENV = "PROXIMA_TEST_DSN_NORM"
DSN_FILE_ENV = "NORM_DATABASE_URI_FILE"
TENANT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


@dataclass(frozen=True)
class DayFact:
    """Одна версия дня из `fact_cabinet_daily_current`."""

    calendar_day: date
    orders_count: int
    revenue_rub: Decimal
    run_id: str
    evidence_sha256: tuple[str, ...]


def validate_tenant(tenant_id: str) -> str:
    if not TENANT_PATTERN.match(tenant_id):
        raise ValueError(f"tenant_id must match {TENANT_PATTERN.pattern}, got {tenant_id!r}")
    return tenant_id


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


def read_last_full_day(connection: psycopg.Connection, tenant_id: str) -> date | None:
    row = connection.execute(
        "SELECT last_full_day FROM data_status_current WHERE tenant_id = %s",
        (tenant_id,),
    ).fetchone()
    return None if row is None else row[0]


def read_window(connection: psycopg.Connection, tenant_id: str, days: list[date]) -> list[DayFact]:
    """Версии дней окна. Отсутствующий день просто не приходит - это и есть пропуск."""
    rows = connection.execute(
        """
        SELECT calendar_day, orders_count, revenue_rub, run_id::text, evidence_sha256
        FROM fact_cabinet_daily_current
        WHERE tenant_id = %s AND calendar_day = ANY(%s)
        ORDER BY calendar_day
        """,
        (tenant_id, days),
    ).fetchall()
    return [
        DayFact(
            calendar_day=row[0],
            orders_count=int(row[1]),
            revenue_rub=Decimal(row[2]),
            run_id=row[3],
            evidence_sha256=tuple(sorted(str(item).strip() for item in (row[4] or []))),
        )
        for row in rows
    ]
