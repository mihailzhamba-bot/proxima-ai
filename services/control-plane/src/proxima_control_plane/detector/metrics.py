"""Канонические типы входа детектора: Decimal без float, ряд по nmId (AD-19).

`to_decimal` и форма `DailyMetrics` перенесены из списанной ветки `pmm-20-scn-001`
(D32: переносятся только чистые куски, код ветки не адаптируется): принимаются
Decimal, int и str; float, bool, None, NaN и Infinity отвергаются на входе, поэтому
в payload такие значения не попадают по построению. Поля приведены к грейну
`fact_nm_daily_current` (`orders_count`, `revenue_rub`) и `fact_funnel_daily_current`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

DAILY_METRIC_FIELDS = ("orders", "revenue_rub")
FUNNEL_METRIC_FIELDS = ("open_card", "orders", "orders_sum_rub")


def to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, bool) or value is None or isinstance(value, float):
        raise TypeError(f"metric value must be Decimal, int or str, got {type(value).__name__}")
    elif isinstance(value, int):
        parsed = Decimal(value)
    elif isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"metric value is not a valid Decimal: {value!r}") from exc
    else:
        raise TypeError(f"metric value must be Decimal, int or str, got {type(value).__name__}")
    if not parsed.is_finite():
        raise ValueError(f"metric value must be a finite Decimal, got {parsed}")
    return parsed


def _validate_nm_id(nm_id: object) -> None:
    if isinstance(nm_id, bool) or not isinstance(nm_id, int) or nm_id <= 0:
        raise ValueError(f"nm_id must be a positive integer, got {nm_id!r}")


@dataclass(frozen=True)
class DailyMetrics:
    """Одна версия дня по nmId из `fact_nm_daily_current`.

    `orders` - заказы без отмен, `revenue_rub` - выручка `finishedPrice` (glossary.md);
    `run_id` и `evidence_sha256` - доказательство версии для `source_refs` (AD-1, AD-19).
    """

    nm_id: int
    calendar_day: date
    orders: Decimal
    revenue_rub: Decimal
    run_id: str
    evidence_sha256: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_nm_id(self.nm_id)
        for name in DAILY_METRIC_FIELDS:
            object.__setattr__(self, name, to_decimal(getattr(self, name)))
        object.__setattr__(self, "evidence_sha256", tuple(sorted(str(item).strip() for item in self.evidence_sha256)))


@dataclass(frozen=True)
class FunnelMetrics:
    """Одна версия дня воронки по nmId из `fact_funnel_daily_current` (AD-5)."""

    nm_id: int
    calendar_day: date
    open_card: Decimal
    orders: Decimal
    orders_sum_rub: Decimal
    run_id: str
    evidence_sha256: str

    def __post_init__(self) -> None:
        _validate_nm_id(self.nm_id)
        for name in FUNNEL_METRIC_FIELDS:
            object.__setattr__(self, name, to_decimal(getattr(self, name)))


@dataclass(frozen=True)
class SubjectRow:
    """Строка `dim_nm_subject_current`: предмет SKU на момент последнего прогона (AD-19)."""

    nm_id: int
    subject_name: str
    supplier_article: str
    brand: str
    run_id: str
    evidence_sha256: str

    def __post_init__(self) -> None:
        _validate_nm_id(self.nm_id)


__all__ = [
    "DAILY_METRIC_FIELDS",
    "FUNNEL_METRIC_FIELDS",
    "DailyMetrics",
    "FunnelMetrics",
    "SubjectRow",
    "to_decimal",
]
