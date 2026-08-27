"""Threshold configuration for SCN-001."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class Scn001Config:
    windows: tuple[int, ...] = (7, 14, 28)
    trigger_window: int = 28
    maturity_min_days: int = 21
    maturity_window_days: int = 28
    cooldown_days: int = 7
    top_n: int = 10
    drop_threshold: Decimal = Decimal("0.20")
    rub_floor: Decimal = Decimal("3000")


def default_config() -> Scn001Config:
    return Scn001Config()


class ThresholdSource(Protocol):
    def drop_threshold(self) -> Decimal: ...

    def rub_floor(self) -> Decimal: ...


@dataclass(frozen=True)
class GlobalThresholdSource:
    config: Scn001Config

    def drop_threshold(self) -> Decimal:
        return self.config.drop_threshold

    def rub_floor(self) -> Decimal:
        return self.config.rub_floor
