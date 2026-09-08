"""Сбор входов и чистая сборка дня сводки без записи (AD-9, тестируемо без БД).

День считается по строкам `norm_daily_current` за `brief_day`:
- обе метрики со статусом `ok` и факт дня есть -> payload по контракту `brief`,
  `deviation_pct` по D27, `signals = []` до шага детектора, `source_refs` из
  версий факта, строк нормы и `data_status`;
- метрики есть, но `insufficient` -> `insufficient`;
- строк нормы нет (или не обе метрики) -> `blocked`.

Сигналы детектора (Story 4.1, AD-19) вкладываются отдельным шагом `with_signals`
и только в день со статусом `ok`: при `insufficient`/`blocked` `signals[]` пуст
(PRD FR-7), и это правило живёт здесь, а не в вызывающем коде.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Sequence

from proxima_control_plane.brief.builder import (
    DataStatus,
    DayDeviation,
    MetricActual,
    MetricNorm,
    blocked_day,
    build_day_payload,
    insufficient_day,
)
from proxima_control_plane.norm.log import log_run_event as log_norm_event

log_run_event = log_norm_event


def _norm_statuses(norms: list[MetricNorm]) -> set[str]:
    return {norm.status for norm in norms}


def build_day(
    brief_day: date,
    norms: list[MetricNorm],
    actual: MetricActual | None,
    data_status: DataStatus | None,
    fact_run_ids: list[str],
) -> DayDeviation:
    """Чистая сборка дня из уже прочитанных версий. Факт нужен только для `ok`."""
    if data_status is None:
        raise ValueError("data_status is required to build a brief payload: refusing to invent one")
    source_refs = _source_refs(brief_day, norms, data_status, fact_run_ids)
    if len(norms) < 2 or {"orders", "revenue"} - {norm.metric for norm in norms}:
        return blocked_day(brief_day, actual, data_status, source_refs)
    if "insufficient" in _norm_statuses(norms):
        return insufficient_day(brief_day, actual, norms, data_status, source_refs)
    if actual is None:
        # Норма полная, а дня нет: блок, а не нулевой payload - факта нет.
        return blocked_day(brief_day, None, data_status, source_refs, "no fact version for evaluation_day")
    return build_day_payload(brief_day, actual, norms, data_status, source_refs)


def with_signals(day: DayDeviation, signals: Sequence[dict]) -> DayDeviation:
    """Сигналы детектора - только в день `ok`; иначе отказ, а не тихий пустой список.

    Вызывающий код обязан проверить статус до запуска детектора: сигналы против
    неполной или отсутствующей нормы не считаются (Story 4.1, PRD FR-7).
    """
    if day.status != "ok":
        raise ValueError(f"signals are built only for an ok day, got status={day.status}")
    payload = dict(day.payload)
    payload["signals"] = [dict(signal) for signal in signals]
    return DayDeviation(brief_day=day.brief_day, status=day.status, payload=payload)


def _source_refs(brief_day: date, norms: list[MetricNorm], data_status: DataStatus, fact_run_ids: list[str]) -> list[str]:
    return [
        *(f"table://fact_cabinet_daily/{brief_day.isoformat()}/run/{run_id}" for run_id in sorted(fact_run_ids)),
        *(f"table://norm_daily/{brief_day.isoformat()}/{norm.metric}" for norm in norms),
        f"view://data_status_current/{data_status.last_full_day.isoformat()}",
    ]


def day_from_rows(
    brief_day: date,
    actual_orders: int,
    actual_revenue: Decimal,
    norms: list[MetricNorm],
    data_status: DataStatus,
    fact_run_ids: list[str],
) -> DayDeviation:
    """Обёртка для CLI: собирает `MetricActual` и вызывает `build_day`."""
    return build_day(
        brief_day,
        norms,
        MetricActual(orders=actual_orders, revenue=actual_revenue),
        data_status,
        fact_run_ids,
    )


__all__ = ["build_day", "day_from_rows", "log_run_event", "with_signals"]
