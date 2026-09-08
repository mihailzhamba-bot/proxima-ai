"""Чистая арифметика детектора: норма ряда по D21/D27, отклонение, деньги под риском.

Правила, которые здесь живут:

- норма ряда = медиана окна `[evaluation_day-14, evaluation_day-1]` (D21, AD-8) -
  та же функция `median`, что у нормы кабинета; при чётном числе точек - среднее
  двух средних (D27);
- `insufficient`, если дней окна с версией меньше 14, если норма заказов равна нулю
  или если у оцениваемого дня нет версии: отклонение тогда не вычисляется, и в
  payload не появляется ни NaN, ни Infinity, ни синтетического «-100 %»;
- отклонение по SKU - против нормы SKU; по категории - против суммы рядов её SKU
  (AD-19: ряд категории = сумма рядов nmId с одним `subject_name`);
- деньги под риском = норма выручки минус выручка дня (`finishedPrice`, revenue-based),
  округление половиной вверх один раз на последнем шаге (D27, AD-10);
- `deviation_pct` округляется до 0.1 п.п. один раз после деления (D27);
- окна 7/14/28 старого детектора живут здесь как справочные средние (`means`) и
  норму D21 не подменяют (AD-8).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

from proxima_control_plane.brief.builder import deviation_pct
from proxima_control_plane.detector.metrics import DailyMetrics, SubjectRow
from proxima_control_plane.norm.median import WINDOW_DAYS, median, norm_window, quantize_money

LEVEL_SKU = "sku"
LEVEL_SUBJECT = "subject"
STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient"
ADAPTER_WINDOWS = (7, 14, 28)
READ_BACK_DAYS = max(ADAPTER_WINDOWS)

REASON_SHORT_WINDOW = "norm window has fewer than 14 day versions"
REASON_ZERO_NORM = "orders norm is zero: deviation undefined"
REASON_NO_DAY = "no fact version for evaluation_day"

DayValues = tuple[Decimal, Decimal]  # (orders, revenue_rub)


@dataclass(frozen=True)
class Evaluation:
    """Результат оценки одного ряда (SKU или категория) на оцениваемый день."""

    level: str
    key: str
    nm_ids: tuple[int, ...]
    status: str
    reason: str | None
    sample_days: int
    actual_orders: Decimal | None
    actual_revenue: Decimal | None
    norm_orders: Decimal | None
    norm_revenue: Decimal | None
    orders_deviation_pct: float | None
    revenue_deviation_pct: float | None
    money_at_risk: Decimal | None
    means: Mapping[int, Decimal | None]
    history_days: int
    rows: tuple[DailyMetrics, ...]

    @property
    def is_candidate(self) -> bool:
        """Кандидат: ниже нормы заказы или выручка; порог не применяется (D32)."""
        return self.status == STATUS_OK and bool(self.triggered_by)

    @property
    def triggered_by(self) -> tuple[str, ...]:
        """Метрики, которые отклонились вниз, в стабильном порядке контракта."""
        return tuple(
            metric
            for metric, deviation in (
                ("orders", self.orders_deviation_pct),
                ("revenue", self.revenue_deviation_pct),
            )
            if deviation is not None and deviation < 0
        )


def series_by_day(rows: Sequence[DailyMetrics]) -> dict[date, DayValues]:
    """Ряд одного nmId: день -> (заказы, выручка). Два ряда на день - ошибка входа."""
    series: dict[date, DayValues] = {}
    for row in rows:
        if row.calendar_day in series:
            raise ValueError(f"duplicate day version for nm_id={row.nm_id} day={row.calendar_day}")
        series[row.calendar_day] = (row.orders, row.revenue_rub)
    return series


def sum_series(parts: Sequence[Mapping[date, DayValues]]) -> dict[date, DayValues]:
    """Ряд категории: сумма рядов её SKU по дням, где хоть у одного SKU есть версия."""
    total: dict[date, DayValues] = {}
    for part in parts:
        for day, (orders, revenue) in part.items():
            orders_sum, revenue_sum = total.get(day, (Decimal(0), Decimal(0)))
            total[day] = (orders_sum + orders, revenue_sum + revenue)
    return total


def window_means(series: Mapping[date, DayValues], evaluation_day: date) -> dict[int, Decimal | None]:
    """Средние заказов за 7/14/28 дней перед оцениваемым - справочно, не норма."""
    means: dict[int, Decimal | None] = {}
    for window in ADAPTER_WINDOWS:
        days = [evaluation_day - timedelta(days=offset) for offset in range(window, 0, -1)]
        values = [series[day][0] for day in days if day in series]
        means[window] = None if not values else sum(values, Decimal(0)) / Decimal(len(values))
    return means


def history_days(series: Mapping[date, DayValues], evaluation_day: date) -> int:
    first = evaluation_day - timedelta(days=READ_BACK_DAYS)
    return sum(1 for day in series if first <= day < evaluation_day)


def evaluate_series(
    level: str,
    key: str,
    nm_ids: Sequence[int],
    series: Mapping[date, DayValues],
    evaluation_day: date,
    rows: Sequence[DailyMetrics],
) -> Evaluation:
    """Норма ряда и отклонение дня против неё; `insufficient` не называет отклонение."""
    window = norm_window(evaluation_day)
    present = [series[day] for day in window if day in series]
    sample_days = len(present)
    means = window_means(series, evaluation_day)
    history = history_days(series, evaluation_day)
    actual = series.get(evaluation_day)
    actual_orders = None if actual is None else actual[0]
    actual_revenue = None if actual is None else actual[1]
    base = dict(
        level=level,
        key=key,
        nm_ids=tuple(sorted(nm_ids)),
        sample_days=sample_days,
        actual_orders=actual_orders,
        actual_revenue=actual_revenue,
        orders_deviation_pct=None,
        revenue_deviation_pct=None,
        money_at_risk=None,
        means=means,
        history_days=history,
        rows=tuple(sorted(rows, key=lambda row: (row.nm_id, row.calendar_day))),
    )
    if sample_days < WINDOW_DAYS:
        return Evaluation(status=STATUS_INSUFFICIENT, reason=REASON_SHORT_WINDOW, norm_orders=None, norm_revenue=None, **base)
    norm_orders = median([orders for orders, _ in present])
    norm_revenue = median([revenue for _, revenue in present])
    if actual is None:
        return Evaluation(status=STATUS_INSUFFICIENT, reason=REASON_NO_DAY, norm_orders=norm_orders, norm_revenue=norm_revenue, **base)
    base["orders_deviation_pct"] = deviation_pct(actual[0], norm_orders) if norm_orders > 0 else None
    base["revenue_deviation_pct"] = deviation_pct(actual[1], norm_revenue) if norm_revenue > 0 else None
    if base["orders_deviation_pct"] is None and base["revenue_deviation_pct"] is None:
        return Evaluation(status=STATUS_INSUFFICIENT, reason=REASON_ZERO_NORM, norm_orders=norm_orders, norm_revenue=norm_revenue, **base)
    base["money_at_risk"] = quantize_money(norm_revenue - actual[1])
    return Evaluation(status=STATUS_OK, reason=None, norm_orders=norm_orders, norm_revenue=norm_revenue, **base)


def evaluate_all(
    facts: Sequence[DailyMetrics],
    subjects: Mapping[int, SubjectRow],
    evaluation_day: date,
) -> list[Evaluation]:
    """Оценки всех SKU с версиями и всех категорий из словаря; порядок детерминирован."""
    rows_by_nm: dict[int, list[DailyMetrics]] = {}
    for row in facts:
        rows_by_nm.setdefault(row.nm_id, []).append(row)
    evaluations: list[Evaluation] = []
    series_by_nm: dict[int, dict[date, DayValues]] = {}
    for nm_id in sorted(rows_by_nm):
        series = series_by_day(rows_by_nm[nm_id])
        series_by_nm[nm_id] = series
        evaluations.append(evaluate_series(LEVEL_SKU, str(nm_id), (nm_id,), series, evaluation_day, rows_by_nm[nm_id]))
    members_by_subject: dict[str, list[int]] = {}
    for nm_id in sorted(series_by_nm):
        # D32: SKU без текущей строки словаря оценивается сам, но не участвует
        # в предметных агрегатах — его предмет неизвестен.
        if nm_id in subjects:
            members_by_subject.setdefault(subjects[nm_id].subject_name, []).append(nm_id)
    for subject_name in sorted(members_by_subject):
        members = members_by_subject[subject_name]
        series = sum_series([series_by_nm[nm_id] for nm_id in members])
        rows = [row for nm_id in members for row in rows_by_nm[nm_id]]
        evaluations.append(evaluate_series(LEVEL_SUBJECT, subject_name, members, series, evaluation_day, rows))
    return evaluations


__all__ = [
    "ADAPTER_WINDOWS",
    "LEVEL_SKU",
    "LEVEL_SUBJECT",
    "READ_BACK_DAYS",
    "STATUS_INSUFFICIENT",
    "STATUS_OK",
    "Evaluation",
    "evaluate_all",
    "evaluate_series",
    "series_by_day",
    "sum_series",
    "window_means",
]
