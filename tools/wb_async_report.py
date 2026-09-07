"""Crash-safe WB Analytics async CSV collector: phase 1 of the `funnel_csv` job.

Story 3.2 (AD-3, AD-5, AD-11): every invocation is one `collector_runs` row of
kind `funnel_csv_download`, opened RUNNING before any work and closed
SUCCEEDED/FAILED with `finished_at` (the FAILED flip is a separate autocommit,
so a failed run never hides behind RUNNING). The session GUC
`proxima.tenant_id` is the first statement on the connection (AD-13). The
tenant must already exist: this tool never creates `tenants` rows. A report is
created at most once per Moscow day: before the first create the tool lists
`nm-report/downloads` and, when a report was already created today, closes the
run SUCCEEDED with a `daily-report-guard` note instead of creating another.

The tool runs under the owner URI (POSTGRES_USER_FILE/POSTGRES_PASSWORD_FILE):
the single exception to AD-11 until the phase moves to TypeScript (M-04).

stdout carries exactly one JSON summary line; run-ledger and step events are
JSON lines on stderr. No line ever carries a token, a URL body or a payload.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import stat
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping, Protocol
from zoneinfo import ZoneInfo

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[1]
MOSCOW = ZoneInfo("Europe/Moscow")
UTC = ZoneInfo("UTC")
API_ROOT = "https://seller-analytics-api.wildberries.ru/api/v2/nm-report/downloads"
REPORT_TYPE = "DETAIL_HISTORY_REPORT"
# AD-3/AD-5: phase 1 of funnel_csv is its own ledger run; the row is created by
# this tool. Kinds and statuses mirror the CHECK constraints of migration 011.
RUN_KIND = "funnel_csv_download"
RUN_KINDS = frozenset({"collect", "backfill", "funnel_v3", "funnel_csv_download", "funnel_csv_promote", "norm", "brief"})
RUN_CLOSED_STATUSES = frozenset({"SUCCEEDED", "FAILED"})
# AD-13: session GUC every RLS policy reads; set as the first statement.
TENANT_GUC = "proxima.tenant_id"
POLL_INTERVAL_SECONDS = 21
DAILY_REPORT_QUOTA = 20
MAX_CREATE_REPLAYS = 2
MAX_REGENERATIONS = 2
NOT_FOUND_BEFORE_REPLAY = 3
# Daily-report guard: attempts on the unfiltered downloads list before the
# first create (429 waits on the retry header in between).
MAX_LIST_ATTEMPTS = 3
PERIOD_LATEST_CLOSED_WEEK = "latest-closed-week"
PERIOD_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})")
SAFE_ENV_KEYS = frozenset(
    {
        "WB_STATISTICS_TOKEN_FILE",
        "PROXIMA_RAW_DIR",
        "WB_ANALYTICS_TOKEN_FILE",
        "WB_FINANCE_TOKEN_FILE",
        "WB_PRICES_TOKEN_FILE",
        "WB_PROMOTION_TOKEN_FILE",
        "PROXIMA_SPOOL_DIR",
        # Set on the VPS at release time (Conventions): compose `secrets:` source dir and
        # the raw-artifacts spool root. Non-secret path parameters, safe for jobs.env.
        "PROXIMA_SECRETS_DIR",
        "PROXIMA_RAW_DIR",
        "POSTGRES_USER_FILE",
        "POSTGRES_PASSWORD_FILE",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
    }
)
SAFE_RESPONSE_HEADERS = frozenset(
    {
        "content-type",
        "content-length",
        "content-disposition",
        "date",
        "retry-after",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "x-ratelimit-retry",
    }
)


class WbAsyncReportError(RuntimeError):
    pass


class RowCountMismatch(WbAsyncReportError):
    pass


class QuotaExhausted(WbAsyncReportError):
    pass


@dataclass(frozen=True)
class TaskRecord:
    task_id: uuid.UUID
    tenant_id: str
    period_from: date
    period_to: date
    request_body: dict[str, object]
    lifecycle_status: str
    api_status: str | None
    consecutive_not_found: int
    create_replay_count: int
    regenerate_count: int
    downloaded_sha256: str | None = None
    downloaded_size: int | None = None
    parsed_row_count: int | None = None
    staged_row_count: int | None = None
    # AD-3 audit link (migration 011, no CASCADE): the ledger run that produced
    # or is producing the download.
    collector_run_id: uuid.UUID | None = None

    @classmethod
    def from_row(cls, row: Mapping[str, object]) -> TaskRecord:
        request_body = row["request_body"]
        if not isinstance(request_body, dict):
            raise WbAsyncReportError("stored request body is not a JSON object")
        return cls(
            task_id=uuid.UUID(str(row["task_id"])),
            tenant_id=str(row["tenant_id"]),
            period_from=row["period_from"],  # type: ignore[arg-type]
            period_to=row["period_to"],  # type: ignore[arg-type]
            request_body=request_body,
            lifecycle_status=str(row["lifecycle_status"]),
            api_status=str(row["api_status"]) if row.get("api_status") is not None else None,
            consecutive_not_found=int(row["consecutive_not_found"]),
            create_replay_count=int(row["create_replay_count"]),
            regenerate_count=int(row["regenerate_count"]),
            downloaded_sha256=str(row["downloaded_sha256"]) if row.get("downloaded_sha256") is not None else None,
            downloaded_size=int(row["downloaded_size"]) if row.get("downloaded_size") is not None else None,
            parsed_row_count=int(row["parsed_row_count"]) if row.get("parsed_row_count") is not None else None,
            staged_row_count=int(row["staged_row_count"]) if row.get("staged_row_count") is not None else None,
            collector_run_id=uuid.UUID(str(row["collector_run_id"])) if row.get("collector_run_id") is not None else None,
        )


@dataclass(frozen=True)
class RawEnvelope:
    response_id: uuid.UUID
    task_id: uuid.UUID
    stage: str
    http_status: int
    response_headers: dict[str, str]
    payload: dict[str, str]
    content_sha256: str
    byte_size: int
    retrieved_at: datetime

    def as_json(self) -> dict[str, object]:
        return {
            "response_id": str(self.response_id),
            "task_id": str(self.task_id),
            "stage": self.stage,
            "http_status": self.http_status,
            "response_headers": self.response_headers,
            "payload": self.payload,
            "content_sha256": self.content_sha256,
            "byte_size": self.byte_size,
            "retrieved_at": self.retrieved_at.isoformat(),
        }

    @classmethod
    def from_json(cls, value: object) -> RawEnvelope:
        if not isinstance(value, dict):
            raise WbAsyncReportError("spooled response envelope is not an object")
        headers = value.get("response_headers")
        payload = value.get("payload")
        if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
            raise WbAsyncReportError("spooled response headers are invalid")
        if not isinstance(payload, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in payload.items()):
            raise WbAsyncReportError("spooled response payload is invalid")
        return cls(
            response_id=uuid.UUID(str(value["response_id"])),
            task_id=uuid.UUID(str(value["task_id"])),
            stage=str(value["stage"]),
            http_status=int(value["http_status"]),
            response_headers=dict(headers),
            payload=dict(payload),
            content_sha256=str(value["content_sha256"]),
            byte_size=int(value["byte_size"]),
            retrieved_at=datetime.fromisoformat(str(value["retrieved_at"])),
        )


class ReportRepository(Protocol):
    def open_run(self, tenant_id: str, kind: str, *, git_sha: str | None = None, image_id: str | None = None) -> uuid.UUID: ...
    def close_run(self, run_id: uuid.UUID, status: str) -> None: ...
    def reserve_task(self, tenant_id: str, period_from: date, period_to: date, quota_date: date, collector_run_id: uuid.UUID) -> tuple[TaskRecord, bool]: ...
    def get_task(self, task_id: uuid.UUID) -> TaskRecord: ...
    def mark_initial_create_sent(self, task_id: uuid.UUID) -> TaskRecord: ...
    def reserve_followup_post(self, task_id: uuid.UUID, action: str, quota_date: date) -> TaskRecord: ...
    def persist_raw(self, envelope: RawEnvelope) -> None: ...
    def set_status(self, task_id: uuid.UUID, lifecycle_status: str, *, api_status: str | None = None, error_code: str | None = None) -> TaskRecord: ...
    def increment_not_found(self, task_id: uuid.UUID) -> TaskRecord: ...
    def complete_download(self, task_id: uuid.UUID, sha256: str, byte_size: int, downloaded_at: datetime, rows: list[dict[str, str]]) -> TaskRecord: ...
    def record_error(self, task_id: uuid.UUID, error_code: str) -> None: ...


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if not path.is_file() or path.is_symlink():
        raise WbAsyncReportError("env file must be a regular file")
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if match is None:
            raise WbAsyncReportError(f"invalid env syntax at line {line_number}")
        key, value = match.groups()
        if key not in SAFE_ENV_KEYS:
            raise WbAsyncReportError(f"unsupported env key at line {line_number}: {key}")
        values[key] = value.strip().strip("'\"")
    return values


def read_secret(path: Path, *, private_only: bool, label: str) -> str:
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise WbAsyncReportError(f"{label} must be a regular file")
    mode = stat.S_IMODE(path.stat().st_mode)
    forbidden = 0o077 if private_only else 0o007
    if mode & forbidden:
        raise WbAsyncReportError(f"{label} has unsafe permissions")
    value = path.read_text(encoding="utf-8").strip()
    if not value or any(character.isspace() for character in value):
        raise WbAsyncReportError(f"{label} must contain exactly one non-empty value")
    return value


def validate_analytics_token(token: str, *, now: datetime, allow_read_write: bool = False) -> None:
    parts = token.split(".")
    if len(parts) != 3:
        raise WbAsyncReportError("WB Analytics token must use JWT compact format")
    try:
        payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        payload = json.loads(payload_bytes)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise WbAsyncReportError("WB Analytics token has an invalid JWT payload") from error
    if not isinstance(payload, dict):
        raise WbAsyncReportError("WB Analytics token JWT payload must be an object")
    mask = payload.get("s")
    if not isinstance(mask, int) or isinstance(mask, bool) or mask < 0:
        raise WbAsyncReportError("WB Analytics token has no valid scope mask")
    if (payload.get("acc"), payload.get("for"), payload.get("t")) != (3, "self", False):
        raise WbAsyncReportError("async report requires a personal WB token")
    if not mask & (1 << 2):
        raise WbAsyncReportError("WB token is missing Analytics scope")
    if mask & ~((1 << 2) | (1 << 30)):
        raise WbAsyncReportError("WB Analytics token must grant only the Analytics category")
    if not mask & (1 << 30) and not allow_read_write:
        raise WbAsyncReportError("WB token must be read-only")
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or isinstance(expires_at, bool) or expires_at <= int(now.timestamp()):
        raise WbAsyncReportError("WB Analytics token is expired or has no valid expiry")


def latest_closed_week(now: datetime) -> tuple[date, date]:
    if now.tzinfo is None:
        raise WbAsyncReportError("now must be timezone-aware")
    today = now.astimezone(MOSCOW).date()
    current_monday = today - timedelta(days=today.weekday())
    return current_monday - timedelta(days=7), current_monday - timedelta(days=1)


def parse_period(value: str, now: datetime) -> tuple[date, date]:
    """`latest-closed-week` (default) or an explicit `YYYY-MM-DD..YYYY-MM-DD`.

    The explicit form exists for manual replays (AD-5). Both ends are Moscow
    calendar days and the range must be closed: it ends before today (AD-7,
    a day is a fact only once it is full).
    """
    if value == PERIOD_LATEST_CLOSED_WEEK:
        return latest_closed_week(now)
    match = PERIOD_RANGE_RE.fullmatch(value)
    if match is None:
        raise WbAsyncReportError(f"--period must be {PERIOD_LATEST_CLOSED_WEEK} or YYYY-MM-DD..YYYY-MM-DD")
    try:
        period_from, period_to = (date.fromisoformat(part) for part in match.groups())
    except ValueError as error:
        raise WbAsyncReportError("--period dates must be valid ISO calendar dates") from error
    if period_from > period_to:
        raise WbAsyncReportError("--period start must not be after its end")
    if now.tzinfo is None:
        raise WbAsyncReportError("now must be timezone-aware")
    if period_to >= now.astimezone(MOSCOW).date():
        raise WbAsyncReportError("--period must end on a closed day (before today, Europe/Moscow)")
    return period_from, period_to


def parse_created_at(value: object) -> datetime | None:
    """`createdAt` of the downloads list, e.g. `2026-08-30 04:17:23`.

    A naive timestamp is read as UTC (D20 dates the external consumer's reports
    by this field in UTC); an offset, when present, wins. Unparseable or absent
    values yield None so the caller can decide whether that is drift.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def reports_created_on(body: object, day: date) -> int:
    """Reports in a `GET nm-report/downloads` body created on the Moscow `day`.

    Fail-closed on shape: a body without a `data` list, or a non-empty list
    where no entry carries a readable `createdAt`, is schema drift, because a
    silent zero would let the daily guard create a second report.
    """
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        raise WbAsyncReportError("downloads list schema drift")
    readable = 0
    created_today = 0
    for item in data:
        created_at = parse_created_at(item.get("createdAt")) if isinstance(item, dict) else None
        if created_at is None:
            continue
        readable += 1
        if created_at.astimezone(MOSCOW).date() == day:
            created_today += 1
    if data and readable == 0:
        raise WbAsyncReportError("downloads list schema drift: no readable createdAt")
    return created_today


def build_request(task_id: uuid.UUID, tenant_id: str, period_from: date, period_to: date) -> dict[str, object]:
    return {
        "id": str(task_id),
        "reportType": REPORT_TYPE,
        "userReportName": f"proxima-{tenant_id}-{period_from.isoformat()}-{period_to.isoformat()}",
        "params": {
            "nmIDs": [],
            "subjectIds": [],
            "brandNames": [],
            "tagIds": [],
            "startDate": period_from.isoformat(),
            "endDate": period_to.isoformat(),
            "timezone": "Europe/Moscow",
            "aggregationLevel": "day",
            "skipDeletedNm": False,
        },
    }


class PostgresReportRepository:
    def __init__(self, connection: psycopg.Connection[dict[str, object]]) -> None:
        self.connection = connection

    @staticmethod
    def _lock_key(tenant_id: str, quota_date: date) -> str:
        return f"wb-analytics:{tenant_id}:{quota_date.isoformat()}"

    def _daily_quota_used(self, tenant_id: str, quota_date: date) -> int:
        row = self.connection.execute(
            "SELECT count(*) AS count FROM wb_analytics_quota_events WHERE tenant_id = %s AND quota_date = %s",
            (tenant_id, quota_date),
        ).fetchone()
        assert row is not None
        return int(row["count"])

    def _row(self, task_id: uuid.UUID) -> TaskRecord:
        row = self.connection.execute("SELECT * FROM wb_analytics_report_tasks WHERE task_id = %s", (task_id,)).fetchone()
        if row is None:
            raise WbAsyncReportError("report task is missing")
        return TaskRecord.from_row(row)

    def get_task(self, task_id: uuid.UUID) -> TaskRecord:
        return self._row(task_id)

    def bind_tenant(self, tenant_id: str) -> None:
        """AD-13: the session GUC, first statement on the connection.

        The owner URI bypasses RLS, but the convention is the same for every
        job (AD-3: "Python-jobs - та же схема"), so the autocommit steps and
        the transactions of one run share one tenant on the session.
        """
        self.connection.execute("SELECT set_config(%s, %s, false)", (TENANT_GUC, tenant_id))

    def _require_tenant(self, tenant_id: str) -> None:
        """AD-5: the tenant must exist; this tool never creates `tenants` rows."""
        row = self.connection.execute("SELECT 1 AS present FROM tenants WHERE tenant_id = %s", (tenant_id,)).fetchone()
        if row is None:
            raise WbAsyncReportError(
                f"tenant {tenant_id} does not exist: the collector never creates tenants (AD-5); add the tenants row first"
            )

    def open_run(self, tenant_id: str, kind: str, *, git_sha: str | None = None, image_id: str | None = None) -> uuid.UUID:
        """AD-3 step (1): `INSERT collector_runs … RUNNING` as its own autocommit."""
        if kind not in RUN_KINDS:
            raise WbAsyncReportError(f"invalid collector run kind: {kind}")
        with self.connection.transaction():
            self._require_tenant(tenant_id)
            run_id = uuid.uuid4()
            self.connection.execute(
                """
                INSERT INTO collector_runs (run_id, tenant_id, kind, status, git_sha, image_id)
                VALUES (%s, %s, %s, 'RUNNING', %s, %s)
                """,
                (run_id, tenant_id, kind, git_sha, image_id),
            )
            return run_id

    def close_run(self, run_id: uuid.UUID, status: str) -> None:
        """Closes the run: only `status` and `finished_at` change (AD-11 convention).

        Exactly one RUNNING row must flip; zero rows means the run is already
        closed or invisible, and that is an error, never a silent success.
        """
        if status not in RUN_CLOSED_STATUSES:
            raise WbAsyncReportError(f"invalid collector run status: {status}")
        with self.connection.transaction():
            cursor = self.connection.execute(
                """
                UPDATE collector_runs SET status = %s, finished_at = CURRENT_TIMESTAMP
                WHERE run_id = %s AND status = 'RUNNING'
                """,
                (status, run_id),
            )
            if cursor.rowcount != 1:
                raise WbAsyncReportError(f"cannot mark run {run_id} {status}: expected one RUNNING row, updated {cursor.rowcount}")

    def reserve_task(self, tenant_id: str, period_from: date, period_to: date, quota_date: date, collector_run_id: uuid.UUID) -> tuple[TaskRecord, bool]:
        with self.connection.transaction():
            self._require_tenant(tenant_id)
            self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (self._lock_key(tenant_id, quota_date),))
            existing = self.connection.execute(
                """
                SELECT * FROM wb_analytics_report_tasks
                WHERE tenant_id = %s AND report_type = %s AND period_from = %s AND period_to = %s
                """,
                (tenant_id, REPORT_TYPE, period_from, period_to),
            ).fetchone()
            if existing is not None:
                # The audit link follows the run that produces the download: a
                # run resuming an unfinished task takes it over, a run that only
                # finds the task already DOWNLOADED leaves the producer in place.
                self.connection.execute(
                    """
                    UPDATE wb_analytics_report_tasks
                    SET collector_run_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE task_id = %s AND lifecycle_status <> 'DOWNLOADED'
                    """,
                    (collector_run_id, existing["task_id"]),
                )
                return self._row(uuid.UUID(str(existing["task_id"]))), False
            if self._daily_quota_used(tenant_id, quota_date) >= DAILY_REPORT_QUOTA:
                raise QuotaExhausted(f"daily report quota exhausted for {tenant_id} on {quota_date.isoformat()}")
            task_id = uuid.uuid4()
            request_body = build_request(task_id, tenant_id, period_from, period_to)
            self.connection.execute(
                """
                INSERT INTO wb_analytics_report_tasks (
                    task_id, tenant_id, report_type, period_from, period_to, timezone,
                    aggregation_level, request_body, lifecycle_status, collector_run_id
                ) VALUES (%s, %s, %s, %s, %s, 'Europe/Moscow', 'day', %s, 'RESERVED', %s)
                """,
                (task_id, tenant_id, REPORT_TYPE, period_from, period_to, Jsonb(request_body), collector_run_id),
            )
            self.connection.execute(
                """
                INSERT INTO wb_analytics_quota_events (task_id, tenant_id, quota_date, action, action_sequence)
                VALUES (%s, %s, %s, 'create', 1)
                """,
                (task_id, tenant_id, quota_date),
            )
            return self._row(task_id), True

    def mark_initial_create_sent(self, task_id: uuid.UUID) -> TaskRecord:
        with self.connection.transaction():
            updated = self.connection.execute(
                """
                UPDATE wb_analytics_quota_events
                SET sent_at = CURRENT_TIMESTAMP
                WHERE task_id = %s AND action = 'create' AND action_sequence = 1 AND sent_at IS NULL
                RETURNING event_id
                """,
                (task_id,),
            ).fetchone()
            if updated is None:
                raise WbAsyncReportError("initial create was already marked as sent")
            self.connection.execute(
                """
                UPDATE wb_analytics_report_tasks
                SET lifecycle_status = 'CREATE_IN_FLIGHT', updated_at = CURRENT_TIMESTAMP, last_error_code = NULL
                WHERE task_id = %s
                """,
                (task_id,),
            )
            return self._row(task_id)

    def reserve_followup_post(self, task_id: uuid.UUID, action: str, quota_date: date) -> TaskRecord:
        if action not in {"create_replay", "regenerate"}:
            raise WbAsyncReportError("invalid follow-up quota action")
        with self.connection.transaction():
            task = self._row(task_id)
            self.connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (self._lock_key(task.tenant_id, quota_date),),
            )
            if self._daily_quota_used(task.tenant_id, quota_date) >= DAILY_REPORT_QUOTA:
                raise QuotaExhausted(f"daily report quota exhausted for {task.tenant_id} on {quota_date.isoformat()}")
            if action == "create_replay":
                if task.create_replay_count >= MAX_CREATE_REPLAYS:
                    raise WbAsyncReportError("create replay budget exhausted")
                sequence = task.create_replay_count + 1
                self.connection.execute(
                    """
                    UPDATE wb_analytics_report_tasks
                    SET create_replay_count = create_replay_count + 1,
                        consecutive_not_found = 0,
                        lifecycle_status = 'CREATE_IN_FLIGHT',
                        updated_at = CURRENT_TIMESTAMP,
                        last_error_code = NULL
                    WHERE task_id = %s
                    """,
                    (task_id,),
                )
            else:
                if task.regenerate_count >= MAX_REGENERATIONS:
                    raise WbAsyncReportError("regeneration budget exhausted")
                sequence = task.regenerate_count + 1
                self.connection.execute(
                    """
                    UPDATE wb_analytics_report_tasks
                    SET regenerate_count = regenerate_count + 1,
                        consecutive_not_found = 0,
                        lifecycle_status = 'REGENERATE_IN_FLIGHT',
                        updated_at = CURRENT_TIMESTAMP,
                        last_error_code = NULL
                    WHERE task_id = %s
                    """,
                    (task_id,),
                )
            self.connection.execute(
                """
                INSERT INTO wb_analytics_quota_events (
                    task_id, tenant_id, quota_date, action, action_sequence, sent_at
                ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (task_id, task.tenant_id, quota_date, action, sequence),
            )
            return self._row(task_id)

    def persist_raw(self, envelope: RawEnvelope) -> None:
        with self.connection.transaction():
            self.connection.execute(
                """
                INSERT INTO raw_wb_analytics_responses (
                    response_id, task_id, stage, http_status, response_headers, payload,
                    content_sha256, byte_size, retrieved_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (response_id) DO NOTHING
                """,
                (
                    envelope.response_id,
                    envelope.task_id,
                    envelope.stage,
                    envelope.http_status,
                    Jsonb(envelope.response_headers),
                    Jsonb(envelope.payload),
                    envelope.content_sha256,
                    envelope.byte_size,
                    envelope.retrieved_at,
                ),
            )

    def set_status(
        self,
        task_id: uuid.UUID,
        lifecycle_status: str,
        *,
        api_status: str | None = None,
        error_code: str | None = None,
    ) -> TaskRecord:
        with self.connection.transaction():
            self.connection.execute(
                """
                UPDATE wb_analytics_report_tasks
                SET lifecycle_status = %s,
                    api_status = COALESCE(%s, api_status),
                    consecutive_not_found = 0,
                    last_error_code = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE task_id = %s
                """,
                (lifecycle_status, api_status, error_code, task_id),
            )
            return self._row(task_id)

    def increment_not_found(self, task_id: uuid.UUID) -> TaskRecord:
        with self.connection.transaction():
            self.connection.execute(
                """
                UPDATE wb_analytics_report_tasks
                SET consecutive_not_found = consecutive_not_found + 1,
                    last_error_code = 'STATUS_NOT_FOUND',
                    updated_at = CURRENT_TIMESTAMP
                WHERE task_id = %s
                """,
                (task_id,),
            )
            return self._row(task_id)

    def complete_download(self, task_id: uuid.UUID, sha256: str, byte_size: int, downloaded_at: datetime, rows: list[dict[str, str]]) -> TaskRecord:
        with self.connection.transaction():
            self.connection.execute("DELETE FROM stg_wb_nm_report_rows WHERE task_id = %s", (task_id,))
            for row_number, row in enumerate(rows, start=1):
                nm_value = row.get("nmID", "")
                raw_date = row.get("dt", "")
                try:
                    row_date = date.fromisoformat(raw_date) if raw_date else None
                except ValueError:
                    row_date = None
                self.connection.execute(
                    """
                    INSERT INTO stg_wb_nm_report_rows (task_id, row_number, nm_id, row_date, payload)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (task_id, row_number, int(nm_value) if nm_value.isdigit() else None, row_date, Jsonb(row)),
                )
            staged_row = self.connection.execute(
                "SELECT count(*) AS count FROM stg_wb_nm_report_rows WHERE task_id = %s",
                (task_id,),
            ).fetchone()
            assert staged_row is not None
            staged = int(staged_row["count"])
            if staged != len(rows):
                raise RowCountMismatch(f"parsed {len(rows)} report rows but staged {staged} for task {task_id}")
            self.connection.execute(
                """
                UPDATE wb_analytics_report_tasks
                SET lifecycle_status = 'DOWNLOADED', api_status = 'SUCCESS',
                    downloaded_sha256 = %s, downloaded_size = %s, downloaded_at = %s,
                    parsed_row_count = %s, staged_row_count = %s,
                    last_error_code = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = %s
                """,
                (sha256, byte_size, downloaded_at, len(rows), staged, task_id),
            )
            return self._row(task_id)

    def record_error(self, task_id: uuid.UUID, error_code: str) -> None:
        with self.connection.transaction():
            self.connection.execute(
                "UPDATE wb_analytics_report_tasks SET last_error_code = %s, updated_at = CURRENT_TIMESTAMP WHERE task_id = %s",
                (error_code, task_id),
            )


class DurableRawRecorder:
    def __init__(self, spool_dir: Path, repository: ReportRepository) -> None:
        self.spool_dir = validate_spool_dir(spool_dir)
        self.repository = repository

    def recover(self) -> int:
        recovered = 0
        for path in sorted(self.spool_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                raise WbAsyncReportError("spool contains an unsafe entry")
            envelope = RawEnvelope.from_json(json.loads(path.read_text(encoding="utf-8")))
            self._validate_envelope(envelope)
            self.repository.persist_raw(envelope)
            self._remove(path)
            recovered += 1
        return recovered

    def capture(self, task_id: uuid.UUID, stage: str, response: httpx.Response, retrieved_at: datetime) -> RawEnvelope:
        body = response.content
        envelope = RawEnvelope(
            response_id=uuid.uuid4(),
            task_id=task_id,
            stage=stage,
            http_status=response.status_code,
            response_headers={key.lower(): value for key, value in response.headers.items() if key.lower() in SAFE_RESPONSE_HEADERS},
            payload={
                "encoding": "base64",
                "media_type": response.headers.get("Content-Type", "application/octet-stream"),
                "body_base64": base64.b64encode(body).decode("ascii"),
            },
            content_sha256=hashlib.sha256(body).hexdigest(),
            byte_size=len(body),
            retrieved_at=retrieved_at,
        )
        self._validate_envelope(envelope)
        path = self._write(envelope)
        self.repository.persist_raw(envelope)
        self._remove(path)
        return envelope

    @staticmethod
    def _validate_envelope(envelope: RawEnvelope) -> None:
        body = base64.b64decode(envelope.payload.get("body_base64", ""), validate=True)
        if hashlib.sha256(body).hexdigest() != envelope.content_sha256 or len(body) != envelope.byte_size:
            raise WbAsyncReportError("raw response envelope integrity check failed")

    def _write(self, envelope: RawEnvelope) -> Path:
        final_path = self.spool_dir / f"{envelope.response_id}.json"
        temporary = self.spool_dir / f".{envelope.response_id}.{uuid.uuid4().hex}.tmp"
        data = json.dumps(envelope.as_json(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, final_path)
            fsync_directory(self.spool_dir)
        finally:
            temporary.unlink(missing_ok=True)
        return final_path

    def _remove(self, path: Path) -> None:
        path.unlink(missing_ok=True)
        fsync_directory(self.spool_dir)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_spool_dir(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise WbAsyncReportError("spool directory must be outside the repository")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise WbAsyncReportError("spool directory must be a real directory")
    os.chmod(path, 0o700)
    return path.resolve()


def log_run_event(event: str, run_id: uuid.UUID, tenant_id: str) -> None:
    """Run-ledger lifecycle line (`running`/`succeeded`/`failed`) on stderr, the
    same shape as the TypeScript jobs; ids and the tenant only."""
    line = {"event": f"run-ledger:{event}", "run_id": str(run_id), "tenant_id": tenant_id, "kind": RUN_KIND, "at": datetime.now(UTC).isoformat()}
    print(json.dumps(line, ensure_ascii=False, sort_keys=True), file=sys.stderr)


def log_run_step(run_id: uuid.UUID, tenant_id: str, step: str, msg: str, *, level: str = "info", **extra: object) -> None:
    """One JSON line per job step: `{ts, level, run_id, tenant_id, kind, step, msg, …}`.
    Extra fields are counts, codes and ids only - never payloads, URLs or secrets."""
    line = {"ts": datetime.now(UTC).isoformat(), "level": level, "run_id": str(run_id), "tenant_id": tenant_id, "kind": RUN_KIND, "step": step, "msg": msg, **extra}
    print(json.dumps(line, ensure_ascii=False, sort_keys=True), file=sys.stderr)


def json_body(response: httpx.Response, stage: str) -> object:
    try:
        return json.loads(response.content)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WbAsyncReportError(f"{stage}: response is not valid JSON") from error


def retry_delay(response: httpx.Response) -> float:
    for header in ("X-RateLimit-Retry", "Retry-After"):
        value = response.headers.get(header, "")
        try:
            parsed = float(value)
            if math.isfinite(parsed):
                return max(parsed, POLL_INTERVAL_SECONDS)
        except ValueError:
            continue
    return float(POLL_INTERVAL_SECONDS)


def parse_report_rows(content: bytes) -> list[dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise WbAsyncReportError("report archive must contain exactly one CSV file")
        raw = archive.read(csv_names[0])
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise WbAsyncReportError("report CSV is not valid UTF-8") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames or any(not name for name in reader.fieldnames):
        raise WbAsyncReportError("report CSV has no valid header")
    rows: list[dict[str, str]] = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise WbAsyncReportError("report CSV row does not match the header")
        rows.append(dict(row))
    return rows


def assert_valid_zip(content: bytes) -> None:
    if not content.startswith(b"PK"):
        raise WbAsyncReportError("download response has no ZIP signature")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if not archive.namelist() or archive.testzip() is not None:
                raise WbAsyncReportError("download response is not an intact non-empty ZIP archive")
    except zipfile.BadZipFile as error:
        raise WbAsyncReportError("download response is not a valid ZIP archive") from error


class AsyncReportCollector:
    def __init__(
        self,
        repository: ReportRepository,
        recorder: DurableRawRecorder,
        client: httpx.Client,
        token: str,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        max_wait_seconds: float = 3600,
    ) -> None:
        self.repository = repository
        self.recorder = recorder
        self.client = client
        self.token = token
        self.now = now
        self.monotonic = monotonic
        self.sleep = sleep
        self.max_wait_seconds = max_wait_seconds
        # The ledger run of the last collect(); the summary line reports it.
        self.run_id: uuid.UUID | None = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self.token}

    def _quota_date(self) -> date:
        return self.now().astimezone(MOSCOW).date()

    def _capture(self, task_id: uuid.UUID, stage: str, response: httpx.Response) -> None:
        self.recorder.capture(task_id, stage, response, self.now())

    def collect(self, tenant_id: str, period_from: date, period_to: date, *, git_sha: str | None = None, image_id: str | None = None) -> TaskRecord:
        """One ledger run (AD-3): RUNNING before any work, SUCCEEDED after it,
        FAILED as a separate autocommit when anything raises. A missing tenant
        fails here, before the run row, the task row or any network request."""
        run_id = self.repository.open_run(tenant_id, RUN_KIND, git_sha=git_sha, image_id=image_id)
        self.run_id = run_id
        log_run_event("running", run_id, tenant_id)
        try:
            task = self._collect(run_id, tenant_id, period_from, period_to)
        except Exception as error:
            log_run_step(run_id, tenant_id, "failed", "run failed; marking FAILED", level="error", error=type(error).__name__)
            # If the FAILED flip itself fails the run stays RUNNING; the original
            # error still surfaces and Story 1.7's run tooling reconciles the ledger.
            try:
                self.repository.close_run(run_id, "FAILED")
            except Exception as close_error:
                log_run_step(run_id, tenant_id, "failed", "could not mark run FAILED", level="error", detail=str(close_error))
            else:
                log_run_event("failed", run_id, tenant_id)
            raise
        self.repository.close_run(run_id, "SUCCEEDED")
        log_run_event("succeeded", run_id, tenant_id)
        return task

    def _collect(self, run_id: uuid.UUID, tenant_id: str, period_from: date, period_to: date) -> TaskRecord:
        self.recorder.recover()
        task, created = self.repository.reserve_task(tenant_id, period_from, period_to, self._quota_date(), run_id)
        if task.lifecycle_status == "DOWNLOADED":
            return task
        if task.lifecycle_status == "BLOCKED":
            raise WbAsyncReportError(f"task {task.task_id} is blocked: inspect raw responses and last_error_code")
        deadline = self.monotonic() + self.max_wait_seconds
        if created or task.lifecycle_status == "RESERVED":
            # AD-5: at most one created report per Moscow day, checked against
            # the live downloads list, not only against this database.
            created_today = self._reports_created_today(task)
            if created_today:
                log_run_step(
                    run_id,
                    tenant_id,
                    "daily-report-guard",
                    "a report was already created today (Europe/Moscow); not creating another, task stays RESERVED",
                    task_id=str(task.task_id),
                    quota_date=self._quota_date().isoformat(),
                    reports_created_today=created_today,
                )
                return task
            task = self.repository.mark_initial_create_sent(task.task_id)
            self._post_create(task)
        return self._poll_until_downloaded(task.task_id, deadline)

    def _reports_created_today(self, task: TaskRecord) -> int:
        """`GET nm-report/downloads` (unfiltered list) before the first create.

        Fail-closed: when the list cannot be read the report is not created and
        the run fails; a rerun resumes the same RESERVED task. The response is
        captured like every other WB answer (stage `status`: same endpoint,
        same GET, no filter).
        """
        for attempt in range(1, MAX_LIST_ATTEMPTS + 1):
            try:
                response = self.client.get(API_ROOT, headers=self._headers())
            except httpx.HTTPError:
                self.repository.record_error(task.task_id, "LIST_NETWORK_FAILURE")
                raise WbAsyncReportError("downloads list request failed; no report is created until the list is checked")
            self._capture(task.task_id, "status", response)
            if response.status_code == 429 and attempt < MAX_LIST_ATTEMPTS:
                self.sleep(retry_delay(response))
                continue
            if response.status_code != 200:
                code = "LIST_ACCESS_DENIED" if response.status_code in {401, 402, 403} else f"LIST_HTTP_{response.status_code}"
                self.repository.record_error(task.task_id, code)
                raise WbAsyncReportError(f"downloads list failed with HTTP {response.status_code}")
            try:
                return reports_created_on(json_body(response, "list"), self._quota_date())
            except WbAsyncReportError:
                self.repository.record_error(task.task_id, "LIST_SCHEMA_DRIFT")
                raise
        raise WbAsyncReportError("downloads list attempts exhausted")

    def _post_create(self, task: TaskRecord) -> None:
        try:
            response = self.client.post(API_ROOT, json=task.request_body, headers=self._headers())
        except httpx.HTTPError:
            self.repository.record_error(task.task_id, "CREATE_NETWORK_UNCERTAIN")
            return
        self._capture(task.task_id, "create", response)
        if response.status_code == 200:
            body = json_body(response, "create")
            if not isinstance(body, dict):
                self.repository.set_status(task.task_id, "BLOCKED", error_code="CREATE_SCHEMA_DRIFT")
                raise WbAsyncReportError("create response schema drift")
            self.repository.set_status(task.task_id, "WAITING", api_status="WAITING")
            self.sleep(POLL_INTERVAL_SECONDS)
            return
        if response.status_code == 429:
            self.sleep(retry_delay(response))
            fresh = self.repository.get_task(task.task_id)
            if fresh.create_replay_count >= MAX_CREATE_REPLAYS:
                self.repository.set_status(task.task_id, "BLOCKED", error_code="CREATE_RATE_LIMIT_EXHAUSTED")
                raise WbAsyncReportError("create rate-limit retry budget exhausted")
            replay = self.repository.reserve_followup_post(task.task_id, "create_replay", self._quota_date())
            self._post_create(replay)
            return
        code = "CREATE_ACCESS_DENIED" if response.status_code in {401, 402, 403} else f"CREATE_HTTP_{response.status_code}"
        self.repository.set_status(task.task_id, "BLOCKED", error_code=code)
        raise WbAsyncReportError(f"create failed with HTTP {response.status_code}")

    def _poll_until_downloaded(self, task_id: uuid.UUID, deadline: float) -> TaskRecord:
        while self.monotonic() <= deadline:
            task = self.repository.get_task(task_id)
            if task.lifecycle_status == "DOWNLOADED":
                return task
            if task.lifecycle_status == "SUCCESS":
                downloaded = self._download(task_id, deadline)
                if downloaded is not None:
                    return downloaded
                continue
            try:
                response = self.client.get(
                    API_ROOT,
                    params={"filter[downloadIds]": str(task_id)},
                    headers=self._headers(),
                )
            except httpx.HTTPError:
                self.repository.record_error(task_id, "STATUS_NETWORK_FAILURE")
                self.sleep(POLL_INTERVAL_SECONDS)
                continue
            self._capture(task_id, "status", response)
            if response.status_code == 429:
                self.sleep(retry_delay(response))
                continue
            if response.status_code == 404:
                task = self.repository.increment_not_found(task_id)
                if task.consecutive_not_found >= NOT_FOUND_BEFORE_REPLAY:
                    if task.create_replay_count >= MAX_CREATE_REPLAYS:
                        self.repository.set_status(task_id, "BLOCKED", error_code="TASK_NOT_FOUND_AFTER_CREATE_REPLAYS")
                        raise WbAsyncReportError("task not found after create replay budget exhausted")
                    replay = self.repository.reserve_followup_post(task_id, "create_replay", self._quota_date())
                    self._post_create(replay)
                else:
                    self.sleep(POLL_INTERVAL_SECONDS)
                continue
            if response.status_code != 200:
                if response.status_code >= 500:
                    self.repository.record_error(task_id, f"STATUS_HTTP_{response.status_code}")
                    self.sleep(POLL_INTERVAL_SECONDS)
                    continue
                code = "STATUS_ACCESS_DENIED" if response.status_code in {401, 402, 403} else f"STATUS_HTTP_{response.status_code}"
                self.repository.set_status(task_id, "BLOCKED", error_code=code)
                raise WbAsyncReportError(f"status failed with HTTP {response.status_code}")
            try:
                status = self._extract_status(response, task_id)
            except WbAsyncReportError:
                self.repository.set_status(task_id, "BLOCKED", error_code="STATUS_SCHEMA_DRIFT")
                raise
            if status is None:
                task = self.repository.increment_not_found(task_id)
                if task.consecutive_not_found >= NOT_FOUND_BEFORE_REPLAY:
                    if task.create_replay_count >= MAX_CREATE_REPLAYS:
                        self.repository.set_status(task_id, "BLOCKED", error_code="TASK_ABSENT_AFTER_CREATE_REPLAYS")
                        raise WbAsyncReportError("task absent after create replay budget exhausted")
                    replay = self.repository.reserve_followup_post(task_id, "create_replay", self._quota_date())
                    self._post_create(replay)
                else:
                    self.sleep(POLL_INTERVAL_SECONDS)
                continue
            if status in {"WAITING", "PROCESSING", "RETRY"}:
                self.repository.set_status(task_id, status, api_status=status)
                self.sleep(POLL_INTERVAL_SECONDS)
                continue
            if status == "SUCCESS":
                self.repository.set_status(task_id, "SUCCESS", api_status=status)
                downloaded = self._download(task_id, deadline)
                if downloaded is not None:
                    return downloaded
                continue
            if status == "FAILED":
                task = self.repository.get_task(task_id)
                if task.regenerate_count >= MAX_REGENERATIONS:
                    self.repository.set_status(task_id, "FAILED", api_status=status, error_code="REGENERATE_BUDGET_EXHAUSTED")
                    raise WbAsyncReportError("report regeneration budget exhausted")
                regenerate = self.repository.reserve_followup_post(task_id, "regenerate", self._quota_date())
                self._post_regenerate(regenerate)
                continue
            self.repository.set_status(task_id, "BLOCKED", api_status=status, error_code="UNKNOWN_API_STATUS")
            raise WbAsyncReportError(f"unknown report status: {status}")
        self.repository.record_error(task_id, "POLL_TIMEOUT")
        raise WbAsyncReportError(f"poll timeout for task {task_id}; rerun resumes the same UUID")

    @staticmethod
    def _extract_status(response: httpx.Response, task_id: uuid.UUID) -> str | None:
        body = json_body(response, "status")
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            raise WbAsyncReportError("status response schema drift")
        for item in data:
            if isinstance(item, dict) and str(item.get("id")) == str(task_id):
                status = item.get("status")
                if isinstance(status, str) and status:
                    return status.upper()
        return None

    def _post_regenerate(self, task: TaskRecord) -> None:
        try:
            response = self.client.post(
                f"{API_ROOT}/retry",
                json={"downloadId": str(task.task_id)},
                headers=self._headers(),
            )
        except httpx.HTTPError:
            self.repository.record_error(task.task_id, "REGENERATE_NETWORK_UNCERTAIN")
            return
        self._capture(task.task_id, "regenerate", response)
        if response.status_code == 200:
            body = json_body(response, "regenerate")
            if not isinstance(body, dict):
                self.repository.set_status(task.task_id, "BLOCKED", error_code="REGENERATE_SCHEMA_DRIFT")
                raise WbAsyncReportError("regenerate response schema drift")
            self.repository.set_status(task.task_id, "RETRY", api_status="RETRY")
            self.sleep(POLL_INTERVAL_SECONDS)
            return
        if response.status_code == 429 and task.regenerate_count < MAX_REGENERATIONS:
            self.sleep(retry_delay(response))
            followup = self.repository.reserve_followup_post(task.task_id, "regenerate", self._quota_date())
            self._post_regenerate(followup)
            return
        code = "REGENERATE_ACCESS_DENIED" if response.status_code in {401, 402, 403} else f"REGENERATE_HTTP_{response.status_code}"
        self.repository.set_status(task.task_id, "BLOCKED", error_code=code)
        raise WbAsyncReportError(f"regenerate failed with HTTP {response.status_code}")

    def _download(self, task_id: uuid.UUID, deadline: float) -> TaskRecord | None:
        if self.monotonic() > deadline:
            return None
        try:
            response = self.client.get(f"{API_ROOT}/file/{task_id}", headers=self._headers())
        except httpx.HTTPError:
            self.repository.record_error(task_id, "DOWNLOAD_NETWORK_FAILURE")
            self.sleep(POLL_INTERVAL_SECONDS)
            return None
        self._capture(task_id, "download", response)
        if response.status_code == 429:
            self.sleep(retry_delay(response))
            return None
        if response.status_code >= 500:
            self.repository.record_error(task_id, f"DOWNLOAD_HTTP_{response.status_code}")
            self.sleep(POLL_INTERVAL_SECONDS)
            return None
        if response.status_code != 200:
            code = "DOWNLOAD_ACCESS_DENIED" if response.status_code in {401, 402, 403} else f"DOWNLOAD_HTTP_{response.status_code}"
            self.repository.set_status(task_id, "BLOCKED", error_code=code)
            raise WbAsyncReportError(f"download failed with HTTP {response.status_code}")
        try:
            assert_valid_zip(response.content)
        except WbAsyncReportError:
            self.repository.record_error(task_id, "DOWNLOAD_INVALID_ZIP")
            raise
        try:
            report_rows = parse_report_rows(response.content)
        except WbAsyncReportError:
            self.repository.set_status(task_id, "BLOCKED", error_code="REPORT_PARSE_FAILED")
            raise
        try:
            return self.repository.complete_download(
                task_id,
                hashlib.sha256(response.content).hexdigest(),
                len(response.content),
                self.now(),
                report_rows,
            )
        except RowCountMismatch:
            self.repository.set_status(task_id, "BLOCKED", error_code="ROW_COUNT_MISMATCH")
            raise


def connect_repository(env: Mapping[str, str], tenant_id: str | None = None) -> PostgresReportRepository:
    """Owner-URI connection (AD-11 exception for phase 1). With `tenant_id` the
    session GUC is the first statement on the connection (AD-3/AD-13);
    `apply_migrations` connects without a tenant."""
    required = ("POSTGRES_USER_FILE", "POSTGRES_PASSWORD_FILE")
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise WbAsyncReportError(f"missing PostgreSQL path references: {','.join(missing)}")
    user = read_secret(Path(env["POSTGRES_USER_FILE"]), private_only=False, label="PostgreSQL user file")
    password = read_secret(Path(env["POSTGRES_PASSWORD_FILE"]), private_only=False, label="PostgreSQL password file")
    connection = psycopg.connect(
        host=env.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(env.get("POSTGRES_PORT", "5432")),
        dbname=env.get("POSTGRES_DB", "proxima"),
        user=user,
        password=password,
        connect_timeout=10,
        autocommit=True,
        row_factory=dict_row,
    )
    repository = PostgresReportRepository(connection)
    if tenant_id is not None:
        repository.bind_tenant(tenant_id)
    return repository


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crash-safe WB Analytics CSV collector", allow_abbrev=False)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument(
        "--period",
        default=PERIOD_LATEST_CLOSED_WEEK,
        help=f"{PERIOD_LATEST_CLOSED_WEEK} (default) or an explicit closed range YYYY-MM-DD..YYYY-MM-DD in the Moscow calendar",
    )
    parser.add_argument("--max-wait-seconds", type=float, default=3600)
    parser.add_argument(
        "--allow-analytics-read-write",
        action="store_true",
        help="temporary staging exception: accept an exact-category Analytics token without the READ-only bit; remove after the READ-only token is issued",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", args.tenant_id):
        raise WbAsyncReportError("tenant ID is invalid")
    if args.max_wait_seconds <= 0:
        raise WbAsyncReportError("max wait must be positive")
    env = read_env_file(args.env_file)
    token_path = env.get("WB_ANALYTICS_TOKEN_FILE")
    spool_path = env.get("PROXIMA_SPOOL_DIR")
    if token_path is None or spool_path is None:
        raise WbAsyncReportError("WB_ANALYTICS_TOKEN_FILE and PROXIMA_SPOOL_DIR are required")
    now = datetime.now(MOSCOW)
    token = read_secret(Path(token_path), private_only=True, label="WB Analytics token file")
    validate_analytics_token(token, now=now, allow_read_write=args.allow_analytics_read_write)
    period_from, period_to = parse_period(args.period, now)
    repository = connect_repository(env, tenant_id=args.tenant_id)
    recorder = DurableRawRecorder(Path(spool_path), repository)
    with httpx.Client(
        timeout=httpx.Timeout(60),
        follow_redirects=False,
        headers={"User-Agent": "proxima-ai-wb-async-report/1"},
    ) as client:
        collector = AsyncReportCollector(
            repository,
            recorder,
            client,
            token,
            max_wait_seconds=args.max_wait_seconds,
        )
        # Same labels as the TypeScript jobs (morning_run.sh exports them).
        result = collector.collect(
            args.tenant_id,
            period_from,
            period_to,
            git_sha=os.environ.get("PROXIMA_GIT_SHA") or None,
            image_id=os.environ.get("PROXIMA_IMAGE_ID") or None,
        )
    print(
        json.dumps(
            {
                "status": result.lifecycle_status,
                "task_id": str(result.task_id),
                "tenant_id": result.tenant_id,
                "run_id": str(collector.run_id),
                "run_kind": RUN_KIND,
                "collector_run_id": str(result.collector_run_id) if result.collector_run_id is not None else None,
                "report_type": REPORT_TYPE,
                "period_from": result.period_from.isoformat(),
                "period_to": result.period_to.isoformat(),
                "sha256": result.downloaded_sha256,
                "byte_size": result.downloaded_size,
                "parsed_row_count": result.parsed_row_count,
                "staged_row_count": result.staged_row_count,
                "raw_payload_printed": False,
                "analytics_access": "read-write-temporary" if args.allow_analytics_read_write else "read-only",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (WbAsyncReportError, psycopg.Error) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from error
