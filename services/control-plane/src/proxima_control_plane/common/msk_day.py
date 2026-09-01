"""Calendar-day conversion at the PROXIMA business timezone boundary."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")


def msk_day(moment: datetime) -> date:
    """Return the Moscow calendar day for an aware timestamp."""
    if moment.tzinfo is None:
        raise ValueError("msk_day requires a timezone-aware datetime")
    return moment.astimezone(MOSCOW).date()
