#!/usr/bin/python3 -I
"""Fixed UTC+8 weekday tariff guard for every LOOP GLM request."""
from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta, timezone
import json
import math

TARIFF_TIMEZONE = timezone(timedelta(hours=8))
PEAK_START = time(14, 0)
PEAK_END = time(18, 0)
MAX_REQUEST_SECONDS = 120
SAFETY_BUFFER_SECONDS = 5
DEFERRED_EXIT = 75


class TariffDeferred(RuntimeError):
    """A request must wait until the fixed tariff peak has ended."""

    def __init__(self, reason: str, resume_at: int):
        super().__init__(reason)
        self.reason = reason
        self.resume_at = resume_at

    def as_dict(self):
        return {'reason': self.reason, 'resume_at': self.resume_at}


def _request_seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('invalid_request_seconds')
    if not 0 < value <= MAX_REQUEST_SECONDS:
        raise ValueError('invalid_request_seconds')
    return float(value)


def _epoch(value):
    return int(value.astimezone(timezone.utc).timestamp())


def _next_peak_start(local_now):
    candidate_date = local_now.date()
    for offset in range(8):
        day = candidate_date + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        candidate = datetime.combine(day, PEAK_START, tzinfo=TARIFF_TIMEZONE)
        if candidate > local_now:
            return candidate
    raise RuntimeError('next_peak_unavailable')


def tariff_status(now=None, request_seconds=MAX_REQUEST_SECONDS):
    """Return whether a bounded request can finish outside weekday peak tariff."""
    seconds = _request_seconds(request_seconds)
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('aware_datetime_required')

    local_now = now.astimezone(TARIFF_TIMEZONE)
    peak_start = datetime.combine(local_now.date(), PEAK_START, tzinfo=TARIFF_TIMEZONE)
    peak_end = datetime.combine(local_now.date(), PEAK_END, tzinfo=TARIFF_TIMEZONE)

    if local_now.weekday() < 5 and peak_start <= local_now < peak_end:
        return {'allowed': False, 'reason': 'weekday_peak',
                'resume_at': _epoch(peak_end)}

    next_peak = _next_peak_start(local_now)
    if (next_peak - local_now).total_seconds() < seconds + SAFETY_BUFFER_SECONDS:
        next_end = datetime.combine(next_peak.date(), PEAK_END, tzinfo=TARIFF_TIMEZONE)
        return {'allowed': False, 'reason': 'pre_peak_guard_band',
                'resume_at': _epoch(next_end)}

    return {'allowed': True, 'reason': 'off_peak', 'resume_at': None}


def require_offpeak(request_seconds=MAX_REQUEST_SECONDS):
    status = tariff_status(request_seconds=request_seconds)
    if not status['allowed']:
        raise TariffDeferred(status['reason'], status['resume_at'])
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True)
    args = parser.parse_args()
    del args
    status = tariff_status()
    print(json.dumps(status, sort_keys=True))
    return 0 if status['allowed'] else DEFERRED_EXIT


if __name__ == '__main__':
    raise SystemExit(main())
