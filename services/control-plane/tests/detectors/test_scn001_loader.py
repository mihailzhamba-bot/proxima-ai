"""Loader tests: SYNTH payloads + fake DB connection, no real database (R09/R11/R16/R18)."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from proxima_control_plane.detectors.scn001.config import GlobalThresholdSource, default_config
from proxima_control_plane.detectors.scn001.loader import (
    PayloadParseError,
    attach_source_refs,
    load_bundle,
    parse_payload_row,
)
from proxima_control_plane.detectors.scn001.signal import LEVEL_CABINET, canonical_hash, detect

# SYNTH payload uses the same keys as the COLUMN_MAP registry (verified via smoke R16).
SYNTH_PAYLOAD = {
    "nmID": 777001,
    "dt": "2026-08-01",
    "ordersCount": "12",
    "openCardCount": 200,
    "ordersSumRub": "12000.50",
    "buyoutsCount": 3,
}


def test_parse_valid_synth_payload_to_daily_metrics():
    row = parse_payload_row(SYNTH_PAYLOAD)
    assert row.sku == "777001"
    assert row.orders == Decimal("12")
    assert row.open_card == Decimal("200")
    assert row.orders_sum_rub == Decimal("12000.50")
    assert row.buyouts == Decimal("3")


def test_missing_column_fails_closed_with_column_name():
    payload = {k: v for k, v in SYNTH_PAYLOAD.items() if k != "openCardCount"}
    with pytest.raises(PayloadParseError) as exc:
        parse_payload_row(payload)
    assert "openCardCount" in str(exc.value)


def test_non_numeric_value_fails_closed_not_nan():
    payload = {**SYNTH_PAYLOAD, "ordersCount": None}
    with pytest.raises(PayloadParseError) as exc:
        parse_payload_row(payload)
    assert "ordersCount" in str(exc.value)
    payload = {**SYNTH_PAYLOAD, "ordersSumRub": "12,000.50"}
    with pytest.raises(PayloadParseError) as exc:
        parse_payload_row(payload)
    assert "ordersSumRub" in str(exc.value)


def test_non_finite_decimal_fails_closed_with_column_name():
    payload = {**SYNTH_PAYLOAD, "ordersCount": "NaN"}
    with pytest.raises(PayloadParseError) as exc:
        parse_payload_row(payload)
    assert "ordersCount" in str(exc.value)
    payload = {**SYNTH_PAYLOAD, "buyoutsCount": "Infinity"}
    with pytest.raises(PayloadParseError) as exc:
        parse_payload_row(payload)
    assert "buyoutsCount" in str(exc.value)


EVAL_DAY = date(2026, 8, 1)
NM = 777001


def synth_payload(nm_id, day, orders, open_card=200, orders_sum_rub=None, buyouts=0):
    return {
        "nmID": nm_id,
        "dt": day.isoformat(),
        "ordersCount": str(orders),
        "openCardCount": open_card,
        "ordersSumRub": str(orders_sum_rub if orders_sum_rub is not None else orders * 1000),
        "buyoutsCount": buyouts,
    }


def db_row(task_id, downloaded_at, day, nm_id, payload):
    return (task_id, downloaded_at, day, nm_id, payload)


class FakeDb:
    def __init__(self, rows):
        self._rows = rows
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))
        return self

    def fetchall(self):
        return list(self._rows)


def task_rows(task_id, downloaded_at, day_from, day_to, nm_id, orders):
    return [
        db_row(task_id, downloaded_at, day_from + timedelta(days=o), nm_id, synth_payload(nm_id, day_from + timedelta(days=o), orders))
        for o in range((day_to - day_from).days + 1)
    ]


def test_load_bundle_fake_db_builds_bundle_and_resolved_refs():
    rows = task_rows("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=28), EVAL_DAY, NM, 100)
    bundle, refs = load_bundle(FakeDb(rows), EVAL_DAY, tenant_id=TENANT_A)
    assert refs == ("task-a",)
    assert len(bundle.panel) == 1
    assert bundle.panel[0] == str(NM)
    series = bundle.metric_series(str(NM), "orders")
    assert len(series) == len(set(series)) == 29
    assert series[EVAL_DAY] == Decimal("100")


def test_overlapping_tasks_resolved_by_latest_downloaded_at():
    rows = [
        *task_rows("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=28), EVAL_DAY, NM, 100),
        db_row("task-b", datetime(2026, 8, 3, tzinfo=timezone.utc), EVAL_DAY, NM, synth_payload(NM, EVAL_DAY, 40)),
    ]
    bundle, refs = load_bundle(FakeDb(rows), EVAL_DAY, tenant_id=TENANT_A)
    assert refs == ("task-a", "task-b")
    assert bundle.metric_series(str(NM), "orders")[EVAL_DAY] == Decimal("40")


def test_overlapping_tasks_tie_break_by_greatest_task_id():
    rows = [
        db_row("task-b", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY, NM, synth_payload(NM, EVAL_DAY, 7)),
        db_row("task-c", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY, NM, synth_payload(NM, EVAL_DAY, 40)),
    ]
    bundle, refs = load_bundle(FakeDb(rows), EVAL_DAY, tenant_id=TENANT_A)
    assert refs == ("task-c",)
    assert bundle.metric_series(str(NM), "orders")[EVAL_DAY] == Decimal("40")


def test_load_bundle_window_bounds_excludes_rows_outside_d_minus_window():
    rows = [
        db_row("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=29), NM, synth_payload(NM, EVAL_DAY - timedelta(days=29), 5)),
        *task_rows("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=28), EVAL_DAY, NM, 100),
    ]
    bundle, _refs = load_bundle(FakeDb(rows), EVAL_DAY, tenant_id=TENANT_A)
    series = bundle.metric_series(str(NM), "orders")
    assert EVAL_DAY - timedelta(days=29) not in series
    assert EVAL_DAY - timedelta(days=28) in series


def test_load_bundle_skips_null_row_date_and_nm_id_without_error():
    rows = [
        *task_rows("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=28), EVAL_DAY, NM, 100),
        db_row("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), None, None, synth_payload(NM, EVAL_DAY, 99)),
    ]
    bundle, refs = load_bundle(FakeDb(rows), EVAL_DAY, tenant_id=TENANT_A)
    assert refs == ("task-a",)
    assert bundle.metric_series(str(NM), "orders")[EVAL_DAY] == Decimal("100")


TENANT_A = "tenant-a"
TENANT_B = "tenant-b"


class TenantFilteringDb:
    """Fake DB that honors the SQL tenant filter: rows are stored per tenant."""

    def __init__(self, rows_by_tenant):
        self._rows_by_tenant = rows_by_tenant
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))
        self.last_rows = None
        if "t.tenant_id = %s" in query:
            assert params, "tenant filter present but no tenant param passed"
            tenant = params[0]
            assert isinstance(tenant, str) and tenant
            self.last_rows = list(self._rows_by_tenant.get(tenant, []))
        return self

    def fetchall(self):
        return self.last_rows if self.last_rows is not None else []


def test_load_bundle_filters_rows_by_tenant_sql_side():
    rows_a = task_rows("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=28), EVAL_DAY, NM, 100)
    rows_b = task_rows("task-b", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=28), EVAL_DAY, NM, 77)
    db = TenantFilteringDb({TENANT_A: rows_a, TENANT_B: rows_b})

    bundle, refs = load_bundle(db, EVAL_DAY, tenant_id=TENANT_A)

    query, params = db.queries[0]
    assert "t.tenant_id = %s" in query
    assert params[0] == TENANT_A
    assert refs == ("task-a",)
    assert bundle.metric_series(str(NM), "orders")[EVAL_DAY] == Decimal("100")

    bundle_b, refs_b = load_bundle(db, EVAL_DAY, tenant_id=TENANT_B)
    assert refs_b == ("task-b",)
    assert bundle_b.metric_series(str(NM), "orders")[EVAL_DAY] == Decimal("77")


def test_load_bundle_without_tenant_fails_closed_before_any_query():
    db = TenantFilteringDb({TENANT_A: []})
    with pytest.raises(ValueError) as exc:
        load_bundle(db, EVAL_DAY, tenant_id="")
    assert "tenant" in str(exc.value).lower()
    with pytest.raises(ValueError):
        load_bundle(db, EVAL_DAY, tenant_id=None)
    with pytest.raises(TypeError):
        load_bundle(db, EVAL_DAY)
    assert db.queries == [], "no SQL may run without an explicit tenant"


def test_loader_to_detect_signal_with_resolved_source_refs():
    rows = task_rows("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=28), EVAL_DAY - timedelta(days=1), NM, 100)
    rows.append(db_row("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY, NM, synth_payload(NM, EVAL_DAY, 40)))
    bundle, refs = load_bundle(FakeDb(rows), EVAL_DAY, tenant_id=TENANT_A)
    config = default_config()
    result = detect(bundle, config, GlobalThresholdSource(config), evaluation_date=EVAL_DAY)
    result = attach_source_refs(result, refs)
    assert result.signals, "expected a drop signal on the injected SYNTH drop"
    cabinet = next(s for s in result.signals if s.level == LEVEL_CABINET)
    assert cabinet.source_refs == refs
    assert cabinet.trust_marking == "unreleased"
    assert cabinet.snapshot_id == result.snapshot_id


def test_attach_source_refs_fills_blocked_entries_with_task_ids():
    from proxima_control_plane.detectors.scn001.metrics import DailyMetrics, MetricBundle

    eval_date = date(2026, 8, 27)
    short_history = [
        DailyMetrics(
            sku="SYNTH-SHORT",
            date=eval_date - timedelta(days=o),
            orders=100,
            open_card=200,
            orders_sum_rub=100000,
            buyouts=0,
        )
        for o in range(3, 0, -1)
    ]
    result = detect(
        MetricBundle.build(short_history),
        default_config(),
        GlobalThresholdSource(default_config()),
        evaluation_date=eval_date,
    )
    assert result.blocked, "expected a BLOCKED entry on the short-history fixture"

    final = attach_source_refs(result, ("task-a",))
    assert final.blocked
    assert all(entry.source_refs == ("task-a",) for entry in final.blocked)
    assert final.run_fingerprint == canonical_hash(replace(final, run_fingerprint=""))


def test_attach_source_refs_recomputes_run_fingerprint():
    rows = task_rows("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY - timedelta(days=28), EVAL_DAY - timedelta(days=1), NM, 100)
    rows.append(db_row("task-a", datetime(2026, 8, 2, tzinfo=timezone.utc), EVAL_DAY, NM, synth_payload(NM, EVAL_DAY, 40)))
    bundle, refs = load_bundle(FakeDb(rows), EVAL_DAY, tenant_id=TENANT_A)
    config = default_config()
    result = detect(bundle, config, GlobalThresholdSource(config), evaluation_date=EVAL_DAY)
    final = attach_source_refs(result, refs)
    assert final.run_fingerprint != result.run_fingerprint
    assert final.run_fingerprint == canonical_hash(replace(final, run_fingerprint=""))
    assert all(s.source_refs == refs for s in final.signals)


def test_smoke_without_database_uri_prints_unknown_and_exits_zero(capsys):
    from proxima_control_plane.detectors.scn001.smoke import main

    exit_code = main(uri="")
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "UNKNOWN" in captured.out


def test_smoke_mismatch_exits_two_and_lists_missing_columns(monkeypatch, capsys):
    from proxima_control_plane.detectors.scn001 import smoke
    from proxima_control_plane.detectors.scn001.loader import COLUMN_MAP

    incomplete_payload = {k: 1 for k in COLUMN_MAP.values() if k != "ordersSumRub"}

    class FakeDbOk:
        def execute(self, query, params=None):
            return self

        def fetchall(self):
            return [("task-x", 1, incomplete_payload)]

        def close(self):
            pass

    monkeypatch.setattr(smoke, "db_from_env", lambda uri=None: FakeDbOk())
    exit_code = smoke.main(uri="postgresql://synth")
    out = capsys.readouterr().out
    assert exit_code == 2
    assert "MISMATCH" in out
    assert "ordersSumRub" in out


def test_smoke_connection_failure_prints_unknown_and_exits_zero(monkeypatch, capsys):
    from proxima_control_plane.detectors.scn001 import smoke

    def unreachable(uri=None):
        raise OSError("connection refused")

    monkeypatch.setattr(smoke, "db_from_env", unreachable)
    exit_code = smoke.main(uri="postgresql://synth")
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "UNKNOWN" in out
    assert "OSError" in out


def test_smoke_db_error_after_connect_exits_three_with_error_name_only(monkeypatch, capsys):
    from proxima_control_plane.detectors.scn001 import smoke

    class FakeDbBroken:
        def execute(self, query, params=None):
            raise OSError("query failed")

    monkeypatch.setattr(smoke, "db_from_env", lambda uri=None: FakeDbBroken())
    exit_code = smoke.main(uri="postgresql://synth")
    out = capsys.readouterr().out
    assert exit_code == 3
    assert "DB_ERROR" in out
    assert "OSError" in out
    assert "query failed" not in out, "no error details/env values may leak"
