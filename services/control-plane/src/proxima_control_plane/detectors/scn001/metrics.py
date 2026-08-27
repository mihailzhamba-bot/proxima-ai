"""Canonical daily input types for the SCN-001 detector core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

CABINET_SKU = "__cabinet__"

METRIC_FIELDS = ("orders", "open_card", "orders_sum_rub", "buyouts")


def to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or value is None or isinstance(value, float):
        raise TypeError(f"metric value must be Decimal, int or str, got {type(value).__name__}")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return Decimal(value)
    raise TypeError(f"metric value must be Decimal, int or str, got {type(value).__name__}")


@dataclass(frozen=True)
class DailyMetrics:
    sku: str
    date: date
    orders: Decimal
    open_card: Decimal
    orders_sum_rub: Decimal
    buyouts: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for name in METRIC_FIELDS:
            object.__setattr__(self, name, to_decimal(getattr(self, name)))


@dataclass(frozen=True)
class MetricBundle:
    rows_by_sku: Mapping[str, tuple[DailyMetrics, ...]]
    panel: tuple[str, ...]
    excluded: tuple[str, ...]

    @classmethod
    def build(
        cls,
        rows: Sequence[DailyMetrics],
        maturity_min_days: int = 21,
        maturity_window_days: int = 28,
    ) -> MetricBundle:
        grouped: dict[str, dict[date, DailyMetrics]] = {}
        for row in rows:
            days = grouped.setdefault(row.sku, {})
            if row.date in days:
                raise ValueError(f"duplicate daily row: sku={row.sku} date={row.date}")
            days[row.date] = row
        rows_by_sku = {
            sku: tuple(sorted(days.values(), key=lambda r: r.date))
            for sku, days in grouped.items()
        }
        reference = max((r.date for r in rows), default=None)
        window_start = (
            reference - timedelta(days=maturity_window_days) if reference is not None else None
        )
        panel: list[str] = []
        excluded: list[str] = []
        for sku in sorted(rows_by_sku):
            recent = sum(
                1 for r in rows_by_sku[sku] if window_start is None or r.date > window_start
            )
            (panel if recent >= maturity_min_days else excluded).append(sku)
        return cls(rows_by_sku=rows_by_sku, panel=tuple(panel), excluded=tuple(excluded))

    def metric_series(self, sku: str, field_name: str) -> dict[date, Decimal]:
        return {r.date: getattr(r, field_name) for r in self.rows_by_sku.get(sku, ())}

    def panel_daily(self) -> dict[date, DailyMetrics]:
        agg: dict[date, dict[str, Decimal]] = {}
        for sku in self.panel:
            for r in self.rows_by_sku.get(sku, ()):
                cell = agg.setdefault(r.date, {f: Decimal("0") for f in METRIC_FIELDS})
                for f in METRIC_FIELDS:
                    cell[f] = cell[f] + getattr(r, f)
        return {
            day: DailyMetrics(sku=CABINET_SKU, date=day, **cells)
            for day, cells in sorted(agg.items())
        }
