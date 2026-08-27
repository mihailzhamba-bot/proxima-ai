"""Seasonal weekday baseline for SCN-001."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping

Series = Mapping[date, Decimal]

WEEKDAY_WINDOW_DAYS = 28


def _window_pairs(series: Series, d: date, window_days: int) -> list[tuple[date, Decimal]]:
    lo = d - timedelta(days=window_days)
    return [(day, v) for day, v in series.items() if lo <= day < d]


def history_status(series: Series, d: date, window_days: int = WEEKDAY_WINDOW_DAYS) -> int:
    return len(_window_pairs(series, d, window_days))


def weekday_index(series: Series, d: date, window_days: int = WEEKDAY_WINDOW_DAYS) -> Decimal:
    pairs = _window_pairs(series, d, window_days)
    if not pairs:
        return Decimal("0")
    total = sum((v for _, v in pairs), Decimal("0"))
    if total == 0:
        return Decimal("0")
    weekday_values = [v for day, v in pairs if day.weekday() == d.weekday()]
    if not weekday_values:
        return Decimal("1")
    mean_all = total / Decimal(len(pairs))
    mean_weekday = sum(weekday_values, Decimal("0")) / Decimal(len(weekday_values))
    return mean_weekday / mean_all


def moving_average(series: Series, d: date, window_days: int) -> Decimal:
    values = [v for _, v in _window_pairs(series, d, window_days)]
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def expected(
    series: Series,
    d: date,
    window_days: int,
    weekday_window_days: int = WEEKDAY_WINDOW_DAYS,
) -> Decimal:
    return moving_average(series, d, window_days) * weekday_index(series, d, weekday_window_days)
