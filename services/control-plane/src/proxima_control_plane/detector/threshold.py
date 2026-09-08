"""Порог тревоги как значение конфигурации control-plane (решение 6а, D25; PRD FR-34).

Story 4.2: порог не применяется - `alert_threshold_pct`, `threshold_source` и
`threshold_date` равны `null`, каждый кандидат ниже нормы остаётся в `signals[]`,
а тройка записывается в `brief_daily.payload.threshold` и в `detection_data`
каждого сигнала. Story 4.4 задаёт значение (`-30`) вместе с источником и датой
одной записью в `DECISIONS.md`: порог без источника и даты не применяется
(fail-closed, PRD FR-20 «правило без источника не применяется»). Порог
односторонний: только падение, число строго отрицательное; рост показывается
числом и тревогой не помечается (PRD FR-34).

Где живёт: `detector/threshold.toml` рядом с этим модулем - файл уезжает в образ
вместе с пакетом, смена значения = коммит и релиз (AD-15). Путь переопределяется
переменной `PROXIMA_THRESHOLD_CONFIG_FILE` (путь к файлу, не значение) или флагом
`--threshold-config` у `brief`/`detector` - для harness и теневого пересчёта.
TOML не знает `null`: отсутствующий ключ = не задан. Правило порога: кандидат
остаётся в `signals[]`, если хотя бы одна из упавших метрик отклонилась на порог
или глубже (`deviation_pct <= alert_threshold_pct`); порядок сигналов от порога
не зависит.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

CONFIG_FILE_ENV = "PROXIMA_THRESHOLD_CONFIG_FILE"
DEFAULT_CONFIG_PATH = Path(__file__).with_name("threshold.toml")
SECTION = "threshold"
KEY_VALUE = "alert_threshold_pct"
KEY_SOURCE = "threshold_source"
KEY_DATE = "threshold_date"
KNOWN_KEYS_ORDERED = (KEY_VALUE, KEY_SOURCE, KEY_DATE)
KNOWN_KEYS = frozenset(KNOWN_KEYS_ORDERED)


@dataclass(frozen=True)
class AlertThreshold:
    """Тройка порога: значение в процентах отклонения, источник и дата решения.

    Либо все три заданы, либо ни одно: порог без источника и даты - ошибка
    конфигурации, а не «порог по умолчанию».
    """

    alert_threshold_pct: Decimal | None = None
    threshold_source: str | None = None
    threshold_date: date | None = None

    def __post_init__(self) -> None:
        given = {
            KEY_VALUE: self.alert_threshold_pct is not None,
            KEY_SOURCE: self.threshold_source is not None,
            KEY_DATE: self.threshold_date is not None,
        }
        if any(given.values()) and not all(given.values()):
            missing = sorted(key for key, present in given.items() if not present)
            raise ValueError(f"threshold config must set {', '.join(KNOWN_KEYS_ORDERED)} together; missing {missing}")
        if self.alert_threshold_pct is not None:
            if not isinstance(self.alert_threshold_pct, Decimal):
                raise TypeError(f"{KEY_VALUE} must be Decimal, got {type(self.alert_threshold_pct).__name__}")
            if not self.alert_threshold_pct.is_finite():
                raise ValueError(f"{KEY_VALUE} must be finite, got {self.alert_threshold_pct}")
            if self.alert_threshold_pct >= 0:
                raise ValueError(f"{KEY_VALUE} must be negative (one-sided drop threshold, PRD FR-34), got {self.alert_threshold_pct}")
        if self.threshold_source is not None and not self.threshold_source.strip():
            raise ValueError(f"{KEY_SOURCE} must be a non-empty string")
        if self.threshold_date is not None and (isinstance(self.threshold_date, datetime) or not isinstance(self.threshold_date, date)):
            raise TypeError(f"{KEY_DATE} must be a date, got {type(self.threshold_date).__name__}")

    @property
    def applied(self) -> bool:
        return self.alert_threshold_pct is not None

    def admits(self, deviations: Iterable[float | None]) -> bool:
        """Кандидат проходит порог, если хотя бы одна метрика упала на порог или глубже.

        Без порога проходит каждый кандидат. Отклонения - уже округлённые по D27
        числа; сравнение идёт в Decimal через их точный текст, не во float.
        """
        if self.alert_threshold_pct is None:
            return True
        return any(
            deviation is not None and Decimal(str(deviation)) <= self.alert_threshold_pct
            for deviation in deviations
        )

    def value_number(self) -> int | float | None:
        """Значение для JSON: целое, если порог целый (`-30`), иначе число с дробью."""
        if self.alert_threshold_pct is None:
            return None
        if self.alert_threshold_pct == self.alert_threshold_pct.to_integral_value():
            return int(self.alert_threshold_pct)
        return float(self.alert_threshold_pct)

    def payload(self) -> dict:
        """Объект `threshold` в `brief_daily.payload` (contracts/brief.schema.json)."""
        return {
            "value": self.value_number(),
            "source": self.threshold_source,
            "date": None if self.threshold_date is None else self.threshold_date.isoformat(),
        }

    def detection_data(self) -> dict:
        """Та же тройка в `detection_data` сигнала: `{value, is_unknown}` на ключ."""
        payload = self.payload()
        return {
            "threshold_pct": _entry(payload["value"]),
            "threshold_source": _entry(payload["source"]),
            "threshold_date": _entry(payload["date"]),
        }


NOT_APPLIED = AlertThreshold()


def _entry(value: Any) -> dict:
    return {"value": value, "is_unknown": value is None}


def _parse_value(raw: Any) -> Decimal:
    if isinstance(raw, bool) or raw is None:
        raise TypeError(f"{KEY_VALUE} must be a number, got {type(raw).__name__}")
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, float):
        # Через точный короткий текст: -30.5 остаётся -30.5, а не двоичным хвостом.
        return Decimal(repr(raw))
    if isinstance(raw, str):
        try:
            return Decimal(raw.strip())
        except InvalidOperation as exc:
            raise ValueError(f"{KEY_VALUE} is not a valid decimal: {raw!r}") from exc
    raise TypeError(f"{KEY_VALUE} must be a number, got {type(raw).__name__}")


def _parse_source(raw: Any) -> str:
    if not isinstance(raw, str):
        raise TypeError(f"{KEY_SOURCE} must be a string, got {type(raw).__name__}")
    return raw.strip()


def _parse_date(raw: Any) -> date:
    if isinstance(raw, datetime):
        raise TypeError(f"{KEY_DATE} must be a calendar date (YYYY-MM-DD), not a datetime")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw.strip())
        except ValueError as exc:
            raise ValueError(f"{KEY_DATE} is not an ISO date: {raw!r}") from exc
    raise TypeError(f"{KEY_DATE} must be a date, got {type(raw).__name__}")


def parse_alert_threshold(data: Mapping[str, Any]) -> AlertThreshold:
    """Разбор уже прочитанного TOML: секция `[threshold]` обязательна, ключи - только известные."""
    section = data.get(SECTION)
    if not isinstance(section, Mapping):
        raise ValueError(f"threshold config must carry a [{SECTION}] table")
    unknown = sorted(set(section) - KNOWN_KEYS)
    if unknown:
        raise ValueError(f"unknown threshold config keys: {unknown}")
    return AlertThreshold(
        alert_threshold_pct=_parse_value(section[KEY_VALUE]) if KEY_VALUE in section else None,
        threshold_source=_parse_source(section[KEY_SOURCE]) if KEY_SOURCE in section else None,
        threshold_date=_parse_date(section[KEY_DATE]) if KEY_DATE in section else None,
    )


def resolve_config_path(explicit: str | Path | None = None) -> Path:
    """Явный путь -> переменная окружения (путь) -> файл рядом с пакетом."""
    if explicit:
        return Path(explicit)
    from_env = os.environ.get(CONFIG_FILE_ENV)
    if from_env:
        return Path(from_env)
    return DEFAULT_CONFIG_PATH


def load_alert_threshold(path: str | Path | None = None) -> AlertThreshold:
    """Читает порог из TOML. Отсутствие файла - ошибка: угадывать порог нельзя."""
    resolved = resolve_config_path(path)
    try:
        text = resolved.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"threshold config file is missing: {resolved}") from exc
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"threshold config is not valid TOML: {resolved}: {exc}") from exc
    return parse_alert_threshold(data)


__all__ = [
    "CONFIG_FILE_ENV",
    "DEFAULT_CONFIG_PATH",
    "NOT_APPLIED",
    "AlertThreshold",
    "load_alert_threshold",
    "parse_alert_threshold",
    "resolve_config_path",
]
