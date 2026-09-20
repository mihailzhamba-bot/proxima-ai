"""Вход детектора: версии `_current` под ролью `proxima_job_norm` (AD-19).

Соединение и GUC арендатора приходят от прогона `brief` (детектор - его шаг), для
сухого прогона из CLI используется `brief.loader.connect`. Читаются только view
`_current`: `fact_nm_daily_current` за 28 дней перед оцениваемым плюс сам день
(самое широкое окно адаптера), `dim_nm_subject_current` целиком,
`fact_funnel_daily_current` - число дней истории по nmId и строки окна только для
SKU с историей от 8 недель. `stg_*` детектор не читает; соединения делает адаптер,
третьего view в БД нет.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import psycopg

from proxima_control_plane.detector.evaluate import READ_BACK_DAYS
from proxima_control_plane.detector.funnel import FUNNEL_MIN_DAYS
from proxima_control_plane.detector.metrics import DailyMetrics, FunnelMetrics, SubjectRow
from proxima_control_plane.norm.median import WINDOW_DAYS


def read_nm_facts(connection: psycopg.Connection, tenant_id: str, evaluation_day: date) -> list[DailyMetrics]:
    """Версии дней по nmId за `[evaluation_day-28, evaluation_day]`; пропуск дня - пропуск."""
    first_day = evaluation_day - timedelta(days=READ_BACK_DAYS)
    rows = connection.execute(
        """
        SELECT nm_id, calendar_day, orders_count, revenue_rub, run_id::text, evidence_sha256
        FROM fact_nm_daily_current
        WHERE tenant_id = %s AND calendar_day >= %s AND calendar_day <= %s
        ORDER BY nm_id, calendar_day
        """,
        (tenant_id, first_day, evaluation_day),
    ).fetchall()
    return [
        DailyMetrics(
            nm_id=int(row[0]),
            calendar_day=row[1],
            orders=int(row[2]),
            revenue_rub=Decimal(row[3]),
            run_id=row[4],
            evidence_sha256=tuple(str(item).strip() for item in (row[5] or [])),
        )
        for row in rows
    ]


def read_subjects(connection: psycopg.Connection, tenant_id: str) -> dict[int, SubjectRow]:
    """Предмет каждого nmId по последнему SUCCEEDED прогону (AD-19: атрибут SKU, не дня)."""
    rows = connection.execute(
        """
        SELECT nm_id, subject_name, supplier_article, brand, run_id::text, evidence_sha256
        FROM dim_nm_subject_current
        WHERE tenant_id = %s
        ORDER BY nm_id
        """,
        (tenant_id,),
    ).fetchall()
    return {
        int(row[0]): SubjectRow(
            nm_id=int(row[0]),
            subject_name=row[1],
            supplier_article=row[2],
            brand=row[3],
            run_id=row[4],
            evidence_sha256=str(row[5]).strip(),
        )
        for row in rows
    }


def read_funnel_history_days(connection: psycopg.Connection, tenant_id: str, evaluation_day: date) -> dict[int, int]:
    """Сколько дней воронки с версией есть у nmId до оцениваемого дня включительно."""
    rows = connection.execute(
        """
        SELECT nm_id, count(DISTINCT calendar_day)
        FROM fact_funnel_daily_current
        WHERE tenant_id = %s AND calendar_day <= %s
        GROUP BY nm_id
        ORDER BY nm_id
        """,
        (tenant_id, evaluation_day),
    ).fetchall()
    return {int(row[0]): int(row[1]) for row in rows}


def read_funnel_window(
    connection: psycopg.Connection,
    tenant_id: str,
    nm_ids: list[int],
    evaluation_day: date,
) -> list[FunnelMetrics]:
    """Строки воронки окна нормы и оцениваемого дня - только для перечисленных nmId."""
    if not nm_ids:
        return []
    first_day = evaluation_day - timedelta(days=WINDOW_DAYS)
    rows = connection.execute(
        """
        SELECT nm_id, calendar_day, open_card, orders, orders_sum_rub, run_id::text, evidence_sha256
        FROM fact_funnel_daily_current
        WHERE tenant_id = %s AND nm_id = ANY(%s) AND calendar_day >= %s AND calendar_day <= %s
        ORDER BY nm_id, calendar_day
        """,
        (tenant_id, nm_ids, first_day, evaluation_day),
    ).fetchall()
    return [
        FunnelMetrics(
            nm_id=int(row[0]),
            calendar_day=row[1],
            open_card=int(row[2]),
            orders=int(row[3]),
            orders_sum_rub=Decimal(row[4]),
            run_id=row[5],
            evidence_sha256=str(row[6]).strip(),
        )
        for row in rows
    ]


def funnel_eligible(history_days: dict[int, int]) -> list[int]:
    """nmId с историей воронки от 8 недель - только им читается окно (Story 4.1)."""
    return sorted(nm_id for nm_id, days in history_days.items() if days >= FUNNEL_MIN_DAYS)


__all__ = [
    "funnel_eligible",
    "read_funnel_history_days",
    "read_funnel_window",
    "read_nm_facts",
    "read_subjects",
]
