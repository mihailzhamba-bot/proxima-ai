"""Чистая арифметика нормы: окно, медиана, округление. Ни ввода-вывода, ни float.

Конвенции расчёта зафиксированы решением D27 и продублированы в
`contracts/norm.schema.json`; здесь они и живут в коде:

- медиана при чётном числе точек - среднее арифметическое двух средних значений;
- деньги округляются половиной вверх до двух знаков;
- всё считается в десятичной арифметике, двоичная с плавающей точкой не появляется.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

WINDOW_DAYS = 14
MONEY_QUANTUM = Decimal("0.01")


def norm_window(evaluation_day: date) -> list[date]:
    """Фиксированное окно `[evaluation_day - 14, evaluation_day - 1]` (AD-8, D21).

    Оцениваемый день в окно не входит: он и есть то, что сравнивают с нормой.
    """
    return [evaluation_day - timedelta(days=offset) for offset in range(WINDOW_DAYS, 0, -1)]


def median(values: Sequence[Decimal]) -> Decimal:
    """Медиана выборки. При чётном числе точек - среднее двух средних (D27).

    Пустая выборка - ошибка, а не ноль: у нормы без данных нет значения, и
    придумывать его нельзя.
    """
    if not values:
        raise ValueError("median of an empty sample is undefined")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def quantize_money(value: Decimal) -> Decimal:
    """Два знака, половина вверх (D27, AD-10). Банковское округление отклонено."""
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def norm_status(sample_days: int) -> str:
    """`ok` только при полном окне: пропуск дня должен быть виден (AD-8)."""
    if sample_days < 0 or sample_days > WINDOW_DAYS:
        raise ValueError(f"sample_days out of range: {sample_days}")
    return "ok" if sample_days == WINDOW_DAYS else "insufficient"
