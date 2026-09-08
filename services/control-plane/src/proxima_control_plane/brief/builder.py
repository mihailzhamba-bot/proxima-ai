"""Чистая арифметика сводки: отклонение к норме и материализованный payload.

Конвенция D27 (как в `norm/median.py`): отклонение считается в Decimal и
округляется до 0.1 процентного пункта ровно один раз, на последнем шаге после
деления; деньги - строки с двумя знаками (AD-10); двоичная плавающая точка в
расчёте не появляется (`deviation_pct` - единственное число в payload, и это
уже округлённый результат). Payload валиден по `contracts/brief.schema.json`
(AD-9); `signals` здесь всегда пуст - их вкладывает шаг детектора через
`assembler.with_signals` только в день `ok` (AD-19, Story 4.1), а `source_refs`
собирается из версий фактов, строк нормы и записей `data_status` - он никогда
не пуст.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from proxima_control_plane.norm.median import quantize_money

SCHEMA_VERSION = 1
NO_SIGNALS: list[dict] = []  # заполняется шагом детектора (assembler.with_signals) только при `ok`
DEVIATION_QUANTUM = Decimal("0.1")


@dataclass(frozen=True)
class MetricActual:
    """Факт одного дня: заказы в штуках, выручка деньгами AD-10."""

    orders: int
    revenue: Decimal


@dataclass(frozen=True)
class MetricNorm:
    """Строка нормы из `norm_daily_current` на оцениваемый день."""

    metric: str
    value: Decimal
    window_days: int
    sample_days: int
    status: str


@dataclass(frozen=True)
class DataStatus:
    """Строка `data_status_current` на момент записи (AD-7)."""

    last_full_day: date
    collected_at: str
    stale: bool


@dataclass(frozen=True)
class DayDeviation:
    """Готовая сводка одного дня: payload и статус материализации."""

    brief_day: date
    status: str
    payload: dict


def deviation_pct(actual: Decimal, norm: Decimal) -> float:
    """`(actual - norm) / norm * 100` с округлением до 0.1 один раз (D27).

    Норма ноль или меньше - деление не определено, а не ноль: придумывать
    отклонение нельзя.
    """
    if norm <= 0:
        raise ValueError(f"deviation is undefined for a non-positive norm: {norm}")
    quotient = (actual - norm) / norm * Decimal(100)
    return float(quotient.quantize(DEVIATION_QUANTUM, rounding=ROUND_HALF_UP))


def _money(value: Decimal) -> str:
    return str(quantize_money(value))


def _metric_payloads(actual: MetricActual, norms: Sequence[MetricNorm]) -> tuple[dict, dict, dict]:
    by_metric = {norm.metric: norm for norm in norms}
    orders_norm = by_metric["orders"]
    revenue_norm = by_metric["revenue"]
    return (
        {
            "orders": actual.orders,
            "revenue": _money(actual.revenue),
        },
        {
            "orders": _money(orders_norm.value),
            "revenue": _money(revenue_norm.value),
            "window_days": orders_norm.window_days,
            "sample_days": orders_norm.sample_days,
        },
        {
            "orders": deviation_pct(Decimal(actual.orders), orders_norm.value),
            "revenue": deviation_pct(actual.revenue, revenue_norm.value),
        },
    )


def build_day_payload(
    brief_day: date,
    actual: MetricActual,
    norms: Sequence[MetricNorm],
    data_status: DataStatus,
    source_refs: Sequence[str],
) -> DayDeviation:
    """Payload дня со статусом `ok`; вход уже собран из версий _current (AD-9)."""
    actual_payload, norm_payload, deviation = _metric_payloads(actual, norms)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "evaluation_day": brief_day.isoformat(),
        "data_status": {
            "last_full_day": data_status.last_full_day.isoformat(),
            "collected_at": data_status.collected_at,
            "stale": data_status.stale,
        },
        "actual": actual_payload,
        "norm": norm_payload,
        "deviation_pct": deviation,
        "signals": list(NO_SIGNALS),
        "source_refs": list(source_refs),
    }
    return DayDeviation(brief_day=brief_day, status="ok", payload=payload)


def _envelope(brief_day: date, actual: MetricActual | None, data_status: DataStatus, source_refs: Sequence[str]) -> dict:
    """Общая для всех трёх статусов часть payload: она известна всегда."""
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation_day": brief_day.isoformat(),
        "data_status": {
            "last_full_day": data_status.last_full_day.isoformat(),
            "collected_at": data_status.collected_at,
            "stale": data_status.stale,
        },
        "actual": None if actual is None else {"orders": actual.orders, "revenue": _money(actual.revenue)},
        "signals": list(NO_SIGNALS),
        "source_refs": list(source_refs),
    }


def insufficient_day(
    brief_day: date,
    actual: MetricActual,
    norms: Sequence[MetricNorm],
    data_status: DataStatus,
    source_refs: Sequence[str],
) -> DayDeviation:
    """Норма есть, но окно неполное: пропуск виден, отклонение не называется (AD-9).

    Норму отдаём как есть - она посчитана на имеющихся днях и это факт. Отклонение
    против неполной нормы числом не называем: `null` честнее, чем цифра, за которую
    нельзя ручаться. Какому числу верить, читатель узнаёт из `brief_daily.status`.
    """
    by_metric = {norm.metric: norm for norm in norms}
    orders_norm = by_metric["orders"]
    revenue_norm = by_metric["revenue"]
    for norm in (orders_norm, revenue_norm):
        if norm.status != "insufficient":
            raise ValueError(f"insufficient_day requires insufficient norms, got {norm.metric}={norm.status}")
    if orders_norm.sample_days != revenue_norm.sample_days:
        raise ValueError("norm metrics disagree on sample_days; refusing to hide the disagreement")
    payload = _envelope(brief_day, actual, data_status, source_refs)
    payload["norm"] = {
        "orders": _money(orders_norm.value),
        "revenue": _money(revenue_norm.value),
        "window_days": orders_norm.window_days,
        "sample_days": orders_norm.sample_days,
    }
    payload["deviation_pct"] = None
    return DayDeviation(brief_day=brief_day, status="insufficient", payload=payload)


def blocked_day(
    brief_day: date,
    actual: MetricActual | None,
    data_status: DataStatus,
    source_refs: Sequence[str],
    reason: str = "norm version missing for evaluation_day",
) -> DayDeviation:
    """Версий нормы за день нет: сводка заблокирована, а не обнулена (AD-9).

    Форма payload не меняется от статуса - меняются значения. Отсутствующая норма
    записывается как `null`, потому что пропущенный ключ и явное «нет» читаются
    по-разному, а причина называется словами.
    """
    payload = _envelope(brief_day, actual, data_status, source_refs)
    payload["norm"] = None
    payload["deviation_pct"] = None
    payload["reason"] = reason
    return DayDeviation(brief_day=brief_day, status="blocked", payload=payload)
