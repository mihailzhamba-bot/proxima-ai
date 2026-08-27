"""Wall-clock boundary helper for SCN-001 (package edge only, never inside detect)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def default_evaluation_date(now: datetime | None = None) -> date:
    current = now if now is not None else datetime.now(MOSCOW_TZ)
    return current.astimezone(MOSCOW_TZ).date() - timedelta(days=1)
