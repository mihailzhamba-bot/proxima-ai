"""SCN-001 loader: payload column registry, fail-closed parsing, staging DB resolution.

Pure parsing lives here; SQL resolution is thin and DB-agnostic (any object with
``execute(query, params)`` works). psycopg is imported lazily — the core never
touches the database.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Mapping, Protocol, Sequence

from proxima_control_plane.detectors.scn001.metrics import (
    DailyMetrics,
    MetricBundle,
    to_decimal,
)
from proxima_control_plane.detectors.scn001.signal import canonical_hash

# Registry: canonical DailyMetrics field -> WB report column name in payload jsonb.
# Verified against a real staging payload by smoke R16 on 2026-08-28: all six
# columns PRESENT (task f1b8892a, row 1) — transcript:
# .autopilot/2026-08-27-pmm20-scn001-core/evidence-r16-smoke.md
# Unmapped payload keys observed: addToCartConversion, addToCartCount,
# addToWishlist, buyoutPercent, buyoutsSumRub, cancelCount, cancelSumRub,
# cartToOrderConversion, currency.
COLUMN_MAP: Mapping[str, str] = {
    "sku": "nmID",
    "date": "dt",
    "orders": "ordersCount",
    "open_card": "openCardCount",
    "orders_sum_rub": "ordersSumRub",
    "buyouts": "buyoutsCount",
}


class PayloadParseError(ValueError):
    """Fail-closed payload parsing: missing column or non-numeric value."""


class DbExecutor(Protocol):
    """Minimal DB surface: psycopg Connection/Cursor both satisfy it."""

    def execute(self, query: str, params: Sequence[Any] = ()) -> Any: ...


def parse_payload_row(
    payload: Mapping[str, Any],
    column_registry: Mapping[str, str] = COLUMN_MAP,
) -> DailyMetrics:
    """Parse one WB report payload row into canonical DailyMetrics (fail-closed)."""
    if not isinstance(payload, Mapping):
        raise PayloadParseError(f"payload must be a JSON object, got {type(payload).__name__}")
    values: dict[str, Any] = {}
    for field, column in column_registry.items():
        if column not in payload:
            raise PayloadParseError(f"missing column: {column!r} (field={field})")
        values[field] = payload[column]
    sku = _parse_sku(values["sku"], column_registry["sku"])
    day = _parse_date(values["date"], column_registry["date"])
    return DailyMetrics(
        sku=sku,
        date=day,
        orders=_parse_metric(values["orders"], column_registry["orders"]),
        open_card=_parse_metric(values["open_card"], column_registry["open_card"]),
        orders_sum_rub=_parse_metric(values["orders_sum_rub"], column_registry["orders_sum_rub"]),
        buyouts=_parse_metric(values["buyouts"], column_registry["buyouts"]),
    )


def _parse_sku(value: Any, column: str) -> str:
    if isinstance(value, bool) or value is None or not isinstance(value, (int, str)):
        raise PayloadParseError(f"non-numeric value for column {column!r} (field=sku): {value!r}")
    return str(value)


def _parse_date(value: Any, column: str) -> date:
    if not isinstance(value, str):
        raise PayloadParseError(f"invalid date value for column {column!r} (field=date): {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PayloadParseError(
            f"invalid date value for column {column!r} (field=date): {value!r}"
        ) from exc


def _parse_metric(value: Any, column: str) -> Decimal:
    try:
        parsed = to_decimal(value)
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise PayloadParseError(
            f"non-numeric value for column {column!r}: {value!r}"
        ) from exc
    if not parsed.is_finite():
        raise PayloadParseError(f"non-numeric value for column {column!r}: {value!r}")
    return parsed


TASK_ROW_SQL = """
SELECT t.task_id::text AS task_id,
       t.downloaded_at,
       r.row_date,
       r.nm_id,
       r.payload
FROM wb_analytics_report_tasks AS t
JOIN stg_wb_nm_report_rows AS r ON r.task_id = t.task_id
WHERE t.tenant_id = %s
  AND t.lifecycle_status = 'DOWNLOADED'
  AND t.downloaded_at IS NOT NULL
  AND t.period_from <= %s
  AND t.period_to >= %s
  AND r.row_date IS NOT NULL
  AND r.nm_id IS NOT NULL
  AND r.row_date BETWEEN %s AND %s
ORDER BY r.row_date, r.nm_id, t.downloaded_at, t.task_id
"""


def load_bundle(
    db: DbExecutor,
    d: date,
    window: int = 28,
    *,
    tenant_id: str,
) -> tuple[MetricBundle, tuple[str, ...]]:
    """Resolve DOWNLOADED staging rows covering [d - window, d] into a canonical bundle.

    Fail-closed on tenant scope: tenant_id is required and non-empty; the SQL
    filters t.tenant_id = %s regardless of the connecting role's RLS policy
    (migration 003 makes tenant_id mandatory; 009 adds RLS via proxima.tenant_id).
    Overlapping tasks are resolved deterministically per (row_date, nm_id):
    latest downloaded_at wins, tie-break by greatest task_id — no duplicate days.
    Returns (bundle, task_ids): task_ids are the resolved downloads the bundle was
    actually assembled from (sorted, unique) — the source_refs for detect() output.
    Row shape (positional): (task_id, downloaded_at, row_date, nm_id, payload).
    """
    if not isinstance(tenant_id, str) or not tenant_id:
        raise ValueError(
            "tenant_id is required (non-empty string): refusing an unscoped cross-tenant read"
        )
    window_start = d - timedelta(days=window)
    cursor = db.execute(TASK_ROW_SQL, (tenant_id, d, window_start, window_start, d))
    raw_rows = cursor.fetchall()
    winners: dict[tuple[date, Any], tuple[tuple[Any, str], Mapping[str, Any]]] = {}
    for task_id, downloaded_at, row_date, _nm_id, payload in raw_rows:
        if row_date is None or _nm_id is None:
            continue
        if not (window_start <= row_date <= d):
            continue
        rank = (downloaded_at, str(task_id))
        key = (row_date, _nm_id)
        current = winners.get(key)
        if current is None or rank > current[0]:
            winners[key] = (rank, payload)
    rows = [
        parse_payload_row(payload)
        for _key, (_rank, payload) in sorted(winners.items(), key=lambda item: item[0])
    ]
    bundle = MetricBundle.build(rows, evaluation_date=d)
    task_ids = tuple(sorted({rank[1] for rank, _payload in winners.values()}))
    return bundle, task_ids


def attach_source_refs(result: Any, source_refs: Sequence[str]) -> Any:
    """Fill signal and blocked source_refs (task_ids) after detect(); recompute fingerprint.

    The fingerprint is recomputed with the same rule as detect()
    (spec «Хэши»: canonical_hash of the result with empty fingerprint),
    so it matches the returned result bit-for-bit.
    """
    refs = tuple(source_refs)
    with_refs = replace(
        result,
        signals=tuple(replace(signal, source_refs=refs) for signal in result.signals),
        blocked=tuple(replace(entry, source_refs=refs) for entry in result.blocked),
    )
    fingerprint = canonical_hash(replace(with_refs, run_fingerprint=""))
    return replace(with_refs, run_fingerprint=fingerprint)


def db_from_env(uri: str | None = None) -> Any:
    """Open a psycopg connection from DATABASE_URI (name only — never a literal value)."""
    import psycopg

    database_uri = uri if uri is not None else os.environ.get("DATABASE_URI")
    if not database_uri:
        raise RuntimeError("DATABASE_URI is not set (environment variable name: DATABASE_URI)")
    return psycopg.connect(database_uri)
