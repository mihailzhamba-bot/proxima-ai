#!/usr/bin/python3
"""Safe, read-only projection of the daily WB collector status file."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo


MAX_STATUS_BYTES = 64 * 1024
MOSCOW = ZoneInfo("Europe/Moscow")
_TENANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_OUTPUT_KEYS = (
    "tenant_id",
    "state",
    "analyzed_day",
    "collected_at",
    "last_attempt_at",
    "reason_code",
)


def _result(
    *,
    tenant_id: str | None = None,
    state: str = "unavailable",
    analyzed_day: str | None = None,
    collected_at: str | None = None,
    last_attempt_at: str | None = None,
    reason_code: str | None,
) -> dict[str, str | None]:
    values = {
        "tenant_id": tenant_id,
        "state": state,
        "analyzed_day": analyzed_day,
        "collected_at": collected_at,
        "last_attempt_at": last_attempt_at,
        "reason_code": reason_code,
    }
    return {key: values[key] for key in _OUTPUT_KEYS}


def _now(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _timestamp(value: Any, now: datetime) -> datetime | None:
    if type(value) is not str or not value or len(value) > 64:
        return None
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    try:
        parsed = parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None
    if parsed > now:
        return None
    return parsed


def _tenant(snapshot: dict[str, Any]) -> str | None:
    value = snapshot.get("tenant")
    if type(value) is str and _TENANT.fullmatch(value):
        return value
    return None


def _day(value: Any) -> str | None:
    if type(value) is not str or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return value if parsed.isoformat() == value else None


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def project_daily_status(snapshot: Any, now_utc: datetime) -> dict[str, str | None]:
    """Return the six-field fail-closed Director view of a collector snapshot."""
    now = _now(now_utc)
    if now is None:
        return _result(reason_code="invalid_now")
    if type(snapshot) is not dict:
        return _result(reason_code="snapshot_missing" if snapshot is None else "snapshot_invalid")

    tenant = _tenant(snapshot)
    state = snapshot.get("state")
    started_raw = snapshot.get("started_at")
    started = _timestamp(started_raw, now)
    if tenant is None or started is None or type(state) is not str:
        return _result(reason_code="snapshot_invalid")

    if state == "running":
        return _result(
            tenant_id=tenant,
            state="running",
            last_attempt_at=started_raw,
            reason_code="collector_running",
        )

    finished_raw = snapshot.get("finished_at")
    finished = _timestamp(finished_raw, now)
    if finished is None or finished < started:
        return _result(tenant_id=tenant, reason_code="timestamp_invalid")

    if state == "failed":
        return _result(
            tenant_id=tenant,
            state="failed",
            last_attempt_at=finished_raw,
            reason_code="collector_failed",
        )
    if state != "success":
        return _result(tenant_id=tenant, reason_code="snapshot_invalid")

    verified = snapshot.get("verified")
    if type(verified) is not dict:
        return _result(
            tenant_id=tenant,
            last_attempt_at=finished_raw,
            reason_code="snapshot_incomplete",
        )

    collected_raw = verified.get("collected_at")
    collected = _timestamp(collected_raw, now)
    if collected is None or not (started <= collected <= finished):
        return _result(
            tenant_id=tenant,
            last_attempt_at=finished_raw,
            reason_code="timestamp_invalid",
        )

    today_moscow = now.astimezone(MOSCOW).date()
    expected_day = (today_moscow - timedelta(days=1)).isoformat()
    if finished.astimezone(MOSCOW).date() != today_moscow:
        return _result(
            tenant_id=tenant,
            collected_at=collected_raw,
            last_attempt_at=finished_raw,
            reason_code="snapshot_old",
        )

    analyzed_day = _day(verified.get("last_full_day"))
    brief_day = _day(verified.get("brief_day"))
    if analyzed_day is None or brief_day is None:
        return _result(
            tenant_id=tenant,
            collected_at=collected_raw,
            last_attempt_at=finished_raw,
            reason_code="snapshot_incomplete",
        )
    if analyzed_day != expected_day or brief_day != expected_day:
        return _result(
            tenant_id=tenant,
            analyzed_day=analyzed_day,
            collected_at=collected_raw,
            last_attempt_at=finished_raw,
            reason_code="day_mismatch",
        )
    if verified.get("stale") is not False:
        return _result(
            tenant_id=tenant,
            analyzed_day=analyzed_day,
            collected_at=collected_raw,
            last_attempt_at=finished_raw,
            reason_code="data_stale",
        )
    if verified.get("brief_status") != "ok":
        return _result(
            tenant_id=tenant,
            analyzed_day=analyzed_day,
            collected_at=collected_raw,
            last_attempt_at=finished_raw,
            reason_code="brief_not_ready",
        )

    norm = verified.get("norm")
    if (type(norm) is not dict
            or type(norm.get("sample_days")) is not int
            or type(norm.get("window_days")) is not int
            or norm["sample_days"] != 14
            or norm["window_days"] != 14):
        return _result(
            tenant_id=tenant,
            analyzed_day=analyzed_day,
            collected_at=collected_raw,
            last_attempt_at=finished_raw,
            reason_code="norm_incomplete",
        )
    if "actual" not in verified:
        return _result(
            tenant_id=tenant,
            analyzed_day=analyzed_day,
            collected_at=collected_raw,
            last_attempt_at=finished_raw,
            reason_code="snapshot_incomplete",
        )

    return _result(
        tenant_id=tenant,
        state="success",
        analyzed_day=analyzed_day,
        collected_at=collected_raw,
        last_attempt_at=finished_raw,
        reason_code=None,
    )


def read_daily_status(path: str | os.PathLike[str], now_utc: datetime) -> dict[str, str | None]:
    """Read at most 64 KiB from ``path`` and return its safe projection."""
    try:
        with Path(path).open("rb") as status_file:
            if os.fstat(status_file.fileno()).st_size > MAX_STATUS_BYTES:
                return _result(reason_code="snapshot_invalid")
            raw = status_file.read(MAX_STATUS_BYTES)
            if os.fstat(status_file.fileno()).st_size > MAX_STATUS_BYTES:
                return _result(reason_code="snapshot_invalid")
        snapshot = json.loads(raw, object_pairs_hook=_json_object)
    except FileNotFoundError:
        return _result(reason_code="snapshot_missing")
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return _result(reason_code="snapshot_invalid")
    return project_daily_status(snapshot, now_utc)


__all__ = ["project_daily_status", "read_daily_status"]
