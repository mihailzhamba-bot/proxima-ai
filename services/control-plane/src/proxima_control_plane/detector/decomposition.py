"""Shapley decomposition of a revenue delta across U x CVR x AOV.

Перенесено из списанной ветки `pmm-20-scn-001` без изменений (D32): чистая
функция, ни ввода-вывода, ни float. Используется только для этапа воронки при
истории воронки от 8 недель (Story 4.1); иначе этап остаётся UNKNOWN.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import permutations

_FACTOR_NAMES = ("u", "cvr", "aov")


@dataclass(frozen=True)
class Contributions:
    u: Decimal
    cvr: Decimal
    aov: Decimal

    def total(self) -> Decimal:
        return self.u + self.cvr + self.aov

    def dominant(self) -> str | None:
        values = {"u": self.u, "cvr": self.cvr, "aov": self.aov}
        lead = max(values, key=lambda name: values[name])
        return lead if values[lead] > 0 else None


def decompose(
    u0: Decimal,
    cvr0: Decimal,
    aov0: Decimal,
    u1: Decimal,
    cvr1: Decimal,
    aov1: Decimal,
) -> Contributions:
    base = {"u": u0, "cvr": cvr0, "aov": aov0}
    actual = {"u": u1, "cvr": cvr1, "aov": aov1}

    def product(state: dict[str, Decimal]) -> Decimal:
        return state["u"] * state["cvr"] * state["aov"]

    delta = product(actual) - product(base)
    if delta == 0:
        return Contributions(u=Decimal("0"), cvr=Decimal("0"), aov=Decimal("0"))
    collapsed = [n for n in _FACTOR_NAMES if base[n] == 0 or actual[n] == 0]
    if collapsed:
        lead = collapsed[0]
        return Contributions(
            **{n: (delta if n == lead else Decimal("0")) for n in _FACTOR_NAMES}
        )
    orders = list(permutations(_FACTOR_NAMES))
    totals = {n: Decimal("0") for n in _FACTOR_NAMES}
    for order in orders:
        value = product(base)
        seen: frozenset[str] = frozenset()
        for n in order:
            seen = seen | {n}
            next_value = product({**base, **{m: actual[m] for m in seen}})
            totals[n] = totals[n] + next_value - value
            value = next_value
    count = Decimal(len(orders))
    phi_u = totals["u"] / count
    phi_cvr = totals["cvr"] / count
    phi_aov = delta - phi_u - phi_cvr
    return Contributions(u=phi_u, cvr=phi_cvr, aov=phi_aov)
