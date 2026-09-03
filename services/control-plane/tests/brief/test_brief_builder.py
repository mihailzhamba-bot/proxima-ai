"""Юнит-тесты арифметики сводки: отклонение, статусы дня, payload (AD-9, D27).

Чистые функции без ввода-вывода; валидность payload по контракту дополнительно
доказывается гейтом `tools/verify_brief.py`, а на стороне БД - `test_brief_db.py`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from proxima_control_plane.brief.assembler import build_day, day_from_rows
from proxima_control_plane.brief.builder import (
    DataStatus,
    MetricActual,
    MetricNorm,
    deviation_pct,
)

DAY = date(2026, 8, 29)
STATUS = DataStatus(date(2026, 8, 29), "2026-08-30T02:41:12+00:00", False)


def ok_norms() -> list[MetricNorm]:
    return [
        MetricNorm("orders", Decimal("34.50"), 14, 14, "ok"),
        MetricNorm("revenue", Decimal("34595.00"), 14, 14, "ok"),
    ]


def insufficient_norms() -> list[MetricNorm]:
    return [
        MetricNorm("orders", Decimal("30.00"), 14, 9, "insufficient"),
        MetricNorm("revenue", Decimal("30000.00"), 14, 9, "insufficient"),
    ]


def test_deviation_matches_the_synthetic_acceptance_scenario() -> None:
    # Вчера 27 заказов и 41 141 ₽ против нормы 34.5 и 34 595 (AC Story 2.4).
    assert deviation_pct(Decimal(27), Decimal("34.5")) == -21.7
    assert deviation_pct(Decimal("41141.00"), Decimal("34595")) == 18.9


def test_deviation_rounds_once_at_the_last_step() -> None:
    # Отклонение = (actual - norm) / norm: 1 против 3 -> -66.666...% (D27).
    assert deviation_pct(Decimal(1), Decimal(3)) == -66.7
    assert deviation_pct(Decimal(2), Decimal(3)) == -33.3
    assert deviation_pct(Decimal(4), Decimal(3)) == 33.3


def test_deviation_refuses_a_non_positive_norm_instead_of_dividing() -> None:
    with pytest.raises(ValueError):
        deviation_pct(Decimal(5), Decimal(0))
    with pytest.raises(ValueError):
        deviation_pct(Decimal(5), Decimal("-10"))


def test_ok_day_carries_expected_payload_fields_and_empty_signals() -> None:
    day = day_from_rows(DAY, 27, Decimal("41141.00"), ok_norms(), STATUS, ["a1b2c3d4"])
    assert day.status == "ok"
    payload = day.payload
    assert payload["schema_version"] == 1
    assert payload["evaluation_day"] == "2026-08-29"
    assert payload["data_status"] == {
        "last_full_day": "2026-08-29",
        "collected_at": "2026-08-30T02:41:12+00:00",
        "stale": False,
    }
    assert payload["actual"] == {"orders": 27, "revenue": "41141.00"}
    assert payload["norm"] == {
        "orders": "34.50",
        "revenue": "34595.00",
        "window_days": 14,
        "sample_days": 14,
    }
    assert payload["deviation_pct"] == {"orders": -21.7, "revenue": 18.9}
    assert payload["signals"] == []  # пусто до M-04 (AD-9)
    assert payload["source_refs"]


def test_money_strings_carry_exactly_two_decimals() -> None:
    day = day_from_rows(DAY, 27, Decimal("41141"), ok_norms(), STATUS, [])
    assert day.payload["actual"]["revenue"] == "41141.00"
    assert day.payload["norm"]["orders"] == "34.50"  # дробная часть медианы законна (AD-10)


def test_insufficient_norms_give_an_insufficient_day_without_payload_numbers() -> None:
    day = day_from_rows(DAY, 27, Decimal("41141.00"), insufficient_norms(), STATUS, [])
    assert day.status == "insufficient"
    assert day.payload["sample_days"] == 9
    assert "deviation_pct" not in day.payload
    assert "actual" not in day.payload


def test_missing_norm_versions_give_a_blocked_day() -> None:
    day = build_day(DAY, [], None, STATUS, [])
    assert day.status == "blocked"
    assert day.payload["reason"]


def test_one_metric_only_is_blocked_not_half_a_summary() -> None:
    only_orders = [MetricNorm("orders", Decimal("34.50"), 14, 14, "ok")]
    day = build_day(DAY, only_orders, MetricActual(27, Decimal("41141.00")), STATUS, [])
    assert day.status == "blocked"


def test_full_norm_without_a_fact_version_is_blocked() -> None:
    day = build_day(DAY, ok_norms(), None, STATUS, [])
    assert day.status == "blocked"


def test_source_refs_point_at_fact_norm_and_status_versions() -> None:
    day = day_from_rows(DAY, 27, Decimal("41141.00"), ok_norms(), STATUS, ["a1b2c3d4"])
    refs = "\n".join(day.payload["source_refs"])
    assert "fact_cabinet_daily/2026-08-29/run/a1b2c3d4" in refs
    assert "norm_daily/2026-08-29/orders" in refs
    assert "norm_daily/2026-08-29/revenue" in refs
    assert "data_status_current/2026-08-29" in refs


def test_stale_status_is_copied_into_the_payload_as_is() -> None:
    stale = DataStatus(date(2026, 8, 28), "2026-08-29T02:00:00+00:00", True)
    day = day_from_rows(DAY, 27, Decimal("41141.00"), ok_norms(), stale, [])
    assert day.payload["data_status"]["stale"] is True
    assert day.status == "ok"  # stale виден webapp-у, а не скрывается билдером
