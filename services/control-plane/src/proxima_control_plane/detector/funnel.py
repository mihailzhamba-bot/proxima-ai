"""Этап воронки для сигнала SKU: разложение U x CVR x AOV по Шепли (Story 4.1).

Этап называется только при истории воронки от 8 недель (56 дней с версией по
nmId в `fact_funnel_daily_current`); иначе `stage` неизвестен - в `detection_data`
это `is_unknown: true`, а не выдуманное значение. База факторов - окно 14 дней
перед оцениваемым по строкам воронки: U0 - средние открытия в день, CVR0 -
заказы/открытия окна, AOV0 - сумма заказов/заказы окна; факт - день. Разложение
идёт от факта к базе, поэтому положительный вклад фактора = потеря от него.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from proxima_control_plane.detector.decomposition import Contributions, decompose
from proxima_control_plane.detector.metrics import FunnelMetrics
from proxima_control_plane.norm.median import norm_window

FUNNEL_MIN_WEEKS = 8
FUNNEL_MIN_DAYS = FUNNEL_MIN_WEEKS * 7
STAGES = ("u", "cvr", "aov")


@dataclass(frozen=True)
class FunnelStage:
    """Этап и вклады; `stage is None` читается как UNKNOWN."""

    weeks: int
    stage: str | None
    contributions: Contributions | None
    rows: tuple[FunnelMetrics, ...]


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return numerator / denominator if denominator > 0 else Decimal(0)


def funnel_stage(
    history_days: int,
    rows: Sequence[FunnelMetrics],
    evaluation_day: date,
) -> FunnelStage:
    """Этап падения по воронке SKU или UNKNOWN, если истории меньше 8 недель."""
    weeks = history_days // 7
    used = tuple(sorted(rows, key=lambda row: row.calendar_day))
    if weeks < FUNNEL_MIN_WEEKS:
        return FunnelStage(weeks=weeks, stage=None, contributions=None, rows=())
    by_day: Mapping[date, FunnelMetrics] = {row.calendar_day: row for row in used}
    if len(by_day) != len(used):
        raise ValueError("duplicate funnel day version for one nm_id")
    window = [by_day[day] for day in norm_window(evaluation_day) if day in by_day]
    day = by_day.get(evaluation_day)
    if not window or day is None:
        return FunnelStage(weeks=weeks, stage=None, contributions=None, rows=used)
    open_card = sum((row.open_card for row in window), Decimal(0))
    orders = sum((row.orders for row in window), Decimal(0))
    orders_sum = sum((row.orders_sum_rub for row in window), Decimal(0))
    u0 = open_card / Decimal(len(window))
    cvr0 = _ratio(orders, open_card)
    aov0 = _ratio(orders_sum, orders)
    u1 = day.open_card
    cvr1 = _ratio(day.orders, day.open_card)
    aov1 = _ratio(day.orders_sum_rub, day.orders)
    contributions = decompose(u1, cvr1, aov1, u0, cvr0, aov0)
    return FunnelStage(weeks=weeks, stage=contributions.dominant(), contributions=contributions, rows=used)


__all__ = ["FUNNEL_MIN_DAYS", "FUNNEL_MIN_WEEKS", "STAGES", "FunnelStage", "funnel_stage"]
