"""Юнит-тесты арифметики нормы: окно, медиана, округление (AD-8, D27)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from proxima_control_plane.norm.median import (
    WINDOW_DAYS,
    median,
    norm_status,
    norm_window,
    quantize_money,
)


def test_window_is_fourteen_days_and_excludes_the_evaluated_day() -> None:
    window = norm_window(date(2026, 8, 29))
    assert len(window) == WINDOW_DAYS
    assert window[0] == date(2026, 8, 15)
    assert window[-1] == date(2026, 8, 28)
    assert date(2026, 8, 29) not in window


def test_window_crosses_a_month_boundary_without_arithmetic_of_its_own() -> None:
    window = norm_window(date(2026, 3, 1))
    assert window[0] == date(2026, 2, 15)
    assert window[-1] == date(2026, 2, 28)


def test_window_crosses_a_year_boundary() -> None:
    window = norm_window(date(2026, 1, 1))
    assert window[0] == date(2025, 12, 18)
    assert window[-1] == date(2025, 12, 31)
    assert len(window) == WINDOW_DAYS


def test_median_of_an_odd_sample_is_the_middle_value() -> None:
    assert median([Decimal(3), Decimal(1), Decimal(2)]) == Decimal(2)


def test_median_of_an_even_sample_is_the_mean_of_the_two_middle_values() -> None:
    # D27: не нижнее среднее и не верхнее, а их среднее арифметическое.
    assert median([Decimal(34), Decimal(35)]) == Decimal("34.5")
    assert median([Decimal(1), Decimal(2), Decimal(3), Decimal(4)]) == Decimal("2.5")


def test_median_of_a_full_window_can_carry_a_fractional_part() -> None:
    # Окно нормы всегда чётное, поэтому дробная норма заказов - норма, а не баг.
    orders = [Decimal(value) for value in (28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41)]
    assert len(orders) == WINDOW_DAYS
    assert median(orders) == Decimal("34.5")


def test_median_rejects_an_empty_sample_instead_of_returning_zero() -> None:
    with pytest.raises(ValueError):
        median([])


def test_money_rounds_half_up_not_half_even() -> None:
    # Банковское округление дало бы 34595.00 и 34595.02; D27 требует половину вверх.
    assert quantize_money(Decimal("34595.005")) == Decimal("34595.01")
    assert quantize_money(Decimal("34595.015")) == Decimal("34595.02")
    assert quantize_money(Decimal("34594.995")) == Decimal("34595.00")


def test_money_keeps_two_decimals_for_a_whole_value() -> None:
    assert str(quantize_money(Decimal(34595))) == "34595.00"


def test_status_is_ok_only_for_a_full_window() -> None:
    assert norm_status(14) == "ok"
    assert norm_status(13) == "insufficient"
    assert norm_status(9) == "insufficient"
    assert norm_status(0) == "insufficient"


def test_status_rejects_a_sample_outside_the_window() -> None:
    with pytest.raises(ValueError):
        norm_status(15)
    with pytest.raises(ValueError):
        norm_status(-1)
