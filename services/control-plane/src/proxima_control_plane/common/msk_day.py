"""The single place that converts an instant into a Europe/Moscow calendar day.

Python twin of the collector helper ``src/wb/msk-day.ts`` (AD-7): both must agree
on every input, otherwise the norm job and the collector fold the same WB answer
into different days. WB ``date``/``lastChangeDate`` arrive as Moscow wall-clock
text without a zone, so zoneless input is read as Moscow time, never as the
runtime zone.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_ZONELESS_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$")
_ZONELESS_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FIXED_MSK_OFFSET = timezone(timedelta(hours=3))

try:
    _MSK = ZoneInfo("Europe/Moscow")
except ZoneInfoNotFoundError:  # pragma: no cover - bare container without tzdata
    _MSK = _FIXED_MSK_OFFSET


def msk_day(value: str | datetime | date) -> str:
    """Return the Moscow calendar day (``YYYY-MM-DD``) of ``value``.

    Zoneless strings and naive datetimes are Moscow wall clock; zoneless dates
    are already a Moscow day. Invalid input raises ValueError instead of guessing.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date().isoformat()
        return value.astimezone(_MSK).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise ValueError(f"msk_day: unsupported input {value!r}")
    if _ZONELESS_DATE.match(value):
        return value
    if _ZONELESS_DATETIME.match(value):
        return value[:10]
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"msk_day: invalid instant {value!r}") from exc
    if parsed.tzinfo is None:
        return parsed.date().isoformat()
    return parsed.astimezone(_MSK).date().isoformat()


def msk_today(now: datetime | None = None) -> str:
    """Moscow calendar day of ``now`` (UTC now by default)."""
    instant = datetime.now(timezone.utc) if now is None else now
    return msk_day(instant)
