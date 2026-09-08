"""AC-preserved gate script for Story 4.0 (standard library only).

Acceptance criterion (epics.md, Story 4.0): `make verify` must show
`order-counts: per-nm sums vs cabinet` green.

AD-19 defines the gate as the node:test unit test on the fixtures: the
per-nmId sums of `summarizeNmDaily` equal `summarizeCabinetDaily` on every
day for each of the six columns (services/collector/tests/nm-daily.test.ts,
runs everywhere, without PostgreSQL). This script runs that test file, replays
the same arithmetic in Python on the committed 30.08 fixtures as a
cross-language pin, and pins the repository artifacts of the story: migration
018 (tables, keys, indexes, CASCADE, `_current` by the AD-3 rule, grants and
policies by the AD-11 template, no webapp grant), the writer (dictionary before
rows, one SELECT shared with the cabinet aggregator, the check as one export,
no second `collector_run_inputs`) and its wiring into `collect`/`backfill`
inside the SUCCEEDED transaction. The db-side behaviour (`_current`, replay,
transitive delete_run, RLS) is covered by
services/collector/tests/nm-daily.db.test.ts inside pg-roundtrip.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "018_nm_daily.sql"
CABINET = ROOT / "services" / "collector" / "src" / "facts" / "cabinet-daily.ts"
WRITER = ROOT / "services" / "collector" / "src" / "facts" / "nm-daily.ts"
COLLECT = ROOT / "services" / "collector" / "src" / "jobs" / "collect.ts"
BACKFILL = ROOT / "services" / "collector" / "src" / "jobs" / "backfill.ts"
UNIT_TEST = ROOT / "services" / "collector" / "tests" / "nm-daily.test.ts"
DB_TEST = ROOT / "services" / "collector" / "tests" / "nm-daily.db.test.ts"
FIXTURES = ROOT / "services" / "collector" / "tests" / "fixtures" / "wb-api" / "statistics"
UNIT_TEST_COMMAND = ["npm", "--workspace", "@proxima/collector", "exec", "--", "tsx", "--test", "tests/nm-daily.test.ts"]

GATE_LINE = "order-counts: per-nm sums vs cabinet"
FLOOR = date(2026, 8, 17)
RUN_DAY = date(2026, 8, 30)
FIXTURE_NM_IDS = 97
COLUMNS = ("orders_count", "cancelled_count", "sales_count", "returns_count", "revenue_rub", "forpay_rub")
DICTIONARY_KEYS = ("subject", "category", "brand", "supplierArticle")

TENANT_GUARD = "USING (tenant_id = current_setting('proxima.tenant_id', true))"
WITH_CHECK = "WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true))"


class NmDailyGateError(AssertionError):
    """A story artifact drifted away from the AC or the spine (AD-19/AD-3/AD-11)."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise NmDailyGateError(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing story artifact: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return path.read_text(encoding="utf-8")


def statements_only(sql: str) -> str:
    """The SQL without `--` comment lines: comments may name the roles they exclude."""
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def check_migration(path: Path = MIGRATION) -> None:
    sql = statements_only(read(path))
    require("CREATE TABLE dim_nm_subject (" in sql and "CREATE TABLE fact_nm_daily (" in sql, "018: both tables of AD-19 live in one file (AD-14)")
    require(sql.index("CREATE TABLE dim_nm_subject (") < sql.index("CREATE TABLE fact_nm_daily ("), "018: the dictionary is created before the daily rows")
    require("PRIMARY KEY (tenant_id, nm_id, run_id)" in sql, "018: dim_nm_subject is keyed by (tenant_id, nm_id, run_id) (AD-19)")
    require("PRIMARY KEY (tenant_id, calendar_day, nm_id, run_id)" in sql, "018: fact_nm_daily is keyed by (tenant_id, calendar_day, nm_id, run_id) (AD-19)")
    require(sql.count("nm_id bigint NOT NULL CHECK (nm_id > 0)") == 2, "018: nm_id is a positive bigint in both tables")
    require(sql.count("run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE") == 2, "018: both tables cascade from collector_runs (AD-3, delete_run.py unchanged)")
    for column in ("subject_name", "category_name", "brand", "supplier_article"):
        require(f"    {column} text NOT NULL," in sql, f"018: dim_nm_subject.{column} is text NOT NULL (empty string is a literal value)")
    require("    last_change_at timestamptz NOT NULL," in sql, "018: the dictionary keeps the winning observation's last_change_at")
    require("    evidence_sha256 char(64) NOT NULL CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$')," in sql, "018: the dictionary keeps one evidence hash")
    require("    evidence_sha256 char(64)[] NOT NULL," in sql, "018: daily rows keep evidence_sha256[] like fact_cabinet_daily")
    for column in ("orders_count", "cancelled_count", "sales_count", "returns_count"):
        require(f"    {column} integer NOT NULL CHECK ({column} >= 0)," in sql, f"018: fact_nm_daily.{column} mirrors fact_cabinet_daily")
    require("    revenue_rub numeric(14,2) NOT NULL," in sql and "    forpay_rub numeric(14,2) NOT NULL," in sql, "018: money is numeric(14,2) (AD-10)")
    for index in (
        "CREATE INDEX dim_nm_subject_run_idx ON dim_nm_subject (run_id);",
        "CREATE INDEX fact_nm_daily_run_idx ON fact_nm_daily (run_id);",
        "CREATE INDEX fact_nm_daily_day_idx ON fact_nm_daily (tenant_id, calendar_day);",
        "CREATE INDEX fact_nm_daily_nm_idx ON fact_nm_daily (tenant_id, nm_id, calendar_day);",
    ):
        require(index in sql, f"018: index missing: {index} (AD-19)")
    require(
        "CREATE VIEW dim_nm_subject_current WITH (security_invoker = true) AS\nSELECT DISTINCT ON (d.tenant_id, d.nm_id) d.*" in sql
        and "ORDER BY d.tenant_id, d.nm_id, r.finished_at DESC, d.run_id DESC;" in sql,
        "018: dim_nm_subject_current follows the AD-3 rule on (tenant_id, nm_id)",
    )
    require(
        "CREATE VIEW fact_nm_daily_current WITH (security_invoker = true) AS\nSELECT DISTINCT ON (f.tenant_id, f.calendar_day, f.nm_id) f.*" in sql
        and "ORDER BY f.tenant_id, f.calendar_day, f.nm_id, r.finished_at DESC, f.run_id DESC;" in sql,
        "018: fact_nm_daily_current follows the AD-3 rule on (tenant_id, calendar_day, nm_id)",
    )
    require(sql.count("WHERE r.status = 'SUCCEEDED'") == 2, "018: both _current views read SUCCEEDED runs only (AD-3)")
    require(sql.count("ENABLE ROW LEVEL SECURITY") == 2, "018: RLS on both tables (AD-13)")
    for table in ("dim_nm_subject", "fact_nm_daily"):
        require(f"GRANT SELECT, INSERT ON {table} TO proxima_job_collector;" in sql, f"018: the collector writes {table} (AD-11)")
        require(f"GRANT SELECT ON {table}_current TO proxima_job_collector;" in sql, f"018: the collector reads {table}_current")
        require(f"GRANT SELECT ON {table} TO proxima_job_norm;" in sql and f"GRANT SELECT ON {table}_current TO proxima_job_norm;" in sql, f"018: norm reads {table} and its _current view (Story 4.1 adapter)")
        require(f"CREATE POLICY tenant_isolation_collector ON {table} FOR ALL TO proxima_job_collector {TENANT_GUARD} {WITH_CHECK};" in sql, f"018: collector FOR ALL on {table} (AD-11)")
        require(f"CREATE POLICY tenant_isolation_norm ON {table} FOR SELECT TO proxima_job_norm {TENANT_GUARD};" in sql, f"018: norm FOR SELECT on {table} (AD-11)")
        require(f"CREATE POLICY tenant_isolation_janitor ON {table} FOR ALL TO proxima_run_janitor {TENANT_GUARD} {WITH_CHECK};" in sql, f"018: janitor FOR ALL on {table} (AD-11)")
    require("proxima_webapp_readonly" not in sql, "018: the webapp gets no grant - it reads brief_current/data_status_current only (AD-9)")
    require("GRANT UPDATE" not in sql and "UPDATE ON" not in sql, "018: nobody updates versions (AD-2: a new run is a new version)")
    require("VALUES (18, 'nm_daily', '" in sql, "018: ledger identity must be (18, nm_daily)")


def check_writer(cabinet: Path = CABINET, writer: Path = WRITER, collect: Path = COLLECT, backfill: Path = BACKFILL) -> None:
    cabinet_source = read(cabinet)
    require("export async function loadLatestObservations(" in cabinet_source, "cabinet-daily.ts must expose the one SELECT of the _latest views both writers share (AD-19)")
    require("FROM stg_wb_orders_latest WHERE tenant_id = $1" in cabinet_source and "FROM stg_wb_sales_latest WHERE tenant_id = $1" in cabinet_source, "the shared SELECT reads both _latest views (AD-2)")
    source = read(writer)
    require("export function summarizeNmSubjects(" in source and "export function summarizeNmDaily(" in source, "nm-daily.ts must export the two pure functions (AD-19)")
    require("export async function writeNmDaily(" in source, "nm-daily.ts must export the run writer")
    require(source.count("export async function checkPerNmSumsVsCabinet(") == 1 and source.count("return { check: 'per_nm_sums_vs_cabinet', status:") == 1, "the SQL check is one export named per_nm_sums_vs_cabinet (AD-19)")
    require("'PASS' : 'MISMATCH'" in source and "days_checked: days.size" in source, "the check reports PASS|MISMATCH with days_checked (AD-17)")
    require("mismatches.push({ calendar_day: row.calendar_day, column: row.column_name, cabinet: row.cabinet, per_nm_sum: row.per_nm_sum })" in source, "mismatches carry {calendar_day, column, cabinet, per_nm_sum} (AD-19)")
    require("COALESCE(n.orders_count, 0)" in source and "COALESCE(n.revenue_rub, 0.00)" in source, "a day without nm rows compares against zeros (AD-19)")
    require("INSERT INTO collector_run_inputs" not in source, "collector_run_inputs is written once, by the cabinet aggregator (AD-19)")
    require(source.index("INSERT INTO dim_nm_subject") < source.index("INSERT INTO fact_nm_daily") < source.index("checkPerNmSumsVsCabinet(client, { tenantId: input.tenantId, runId: input.runId })"), "the writer inserts the dictionary, then the rows, then runs the check (AD-19)")
    require("throw new RangeError(`${row.kind} ${row.key}: payload.nmId must be a positive integer`)" in source, "a missing or non-positive nmId is a RangeError - fail-closed like date (AD-19)")
    require("throw new WbClientError('WB_SCHEMA_DRIFT'" in source, "a dictionary key missing from the payload is WB_SCHEMA_DRIFT (AD-19)")
    require("if (candidate.kind !== incumbent.kind) return candidate.kind === 'order';" in source and "return candidate.key > incumbent.key;" in source, "dictionary ties: order before sale, then the greater key (AD-19)")
    require("if (day < floor || day >= runDay) continue;" in source, "daily rows cover [floor, run_day-1] only (AD-2)")
    require("cell.evidence.size > 0 ? cell.evidence : new Set(emptyEvidence)" in source, "a zero row carries the run's artifacts as evidence (AD-2/AD-19)")
    for job, name in ((collect, "collect"), (backfill, "backfill")):
        job_source = read(job)
        require("import { writeNmDaily, type WriteNmDailyResult } from '../facts/nm-daily.js';" in job_source, f"{name}.ts must call the nmId writer")
        start = job_source.index("await ledger.succeed(")
        end = job_source.index("\n  });", start)  # the callback closes at two-space indent
        body = job_source[start:end]
        require("loadLatestObservations(client, tenantId)" in body, f"{name}: one SELECT of the _latest views inside the run transaction (AD-19)")
        require(body.index("aggregateCabinetDaily(client, { tenantId, runId, floor, runDay, observations })") < body.index("writeNmDaily(client, { tenantId, runId, floor, runDay, observations })"), f"{name}: fact_nm_daily is written right after aggregateCabinetDaily inside transaction (3) (AD-19)")
        require("log('quality_check'," in job_source and "'info' : 'warn'" in job_source, f"{name}: the check is one AD-17 log line, PASS info / MISMATCH warn")
        require("ledger.fail(" not in body, f"{name}: the check never fails the run inside the transaction")
    require("checkPerNmSumsVsCabinet(client, { tenantId })" in read(DB_TEST), "nm-daily.db.test.ts must run the same check over the _current views (AD-19)")


def money(value: object) -> Decimal:
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(str(value))


def replay_fixture(fixtures: Path = FIXTURES) -> tuple[int, int, int]:
    """Python twin of the unit test: per-nmId sums equal the cabinet sums per day, six columns."""
    orders = json.loads(read(fixtures / "orders" / "sample.json"))
    sales = json.loads(read(fixtures / "sales" / "sample.json"))
    require(isinstance(orders, list) and isinstance(sales, list), "fixtures must be JSON arrays")
    nm_ids: set[int] = set()
    cabinet: dict[date, dict[str, Decimal]] = defaultdict(lambda: {column: Decimal(0) for column in COLUMNS})
    per_nm: dict[tuple[date, int], dict[str, Decimal]] = defaultdict(lambda: {column: Decimal(0) for column in COLUMNS})

    def add(day: date, nm_id: int, column: str, amount: Decimal) -> None:
        cabinet[day][column] += amount
        per_nm[(day, nm_id)][column] += amount

    for kind, rows in (("order", orders), (("sale"), sales)):
        for row in rows:
            nm_id = row.get("nmId")
            require(isinstance(nm_id, int) and nm_id > 0, f"{kind}: nmId must be a positive integer (AD-19 fail-closed)")
            for key in DICTIONARY_KEYS:
                require(isinstance(row.get(key), str), f"{kind}: {key} must be present as a string (missing = WB_SCHEMA_DRIFT)")
            nm_ids.add(nm_id)
            day = date.fromisoformat(row["date"][:10])
            if day < FLOOR or day >= RUN_DAY:
                continue
            if kind == "order":
                add(day, nm_id, "cancelled_count" if row.get("isCancel") is True else "orders_count", Decimal(1))
            else:
                sale_id = row["saleID"]
                if sale_id.startswith("S"):
                    add(day, nm_id, "sales_count", Decimal(1))
                    add(day, nm_id, "revenue_rub", money(row["finishedPrice"]))
                    add(day, nm_id, "forpay_rub", money(row["forPay"]))
                elif sale_id.startswith("R"):
                    add(day, nm_id, "returns_count", Decimal(1))
    require(len(nm_ids) == FIXTURE_NM_IDS, f"fixtures must hold {FIXTURE_NM_IDS} nmIds in orders UNION sales, got {len(nm_ids)}")
    days = [FLOOR + timedelta(days=offset) for offset in range((RUN_DAY - FLOOR).days)]
    rows = 0
    for day in days:
        sums = {column: Decimal(0) for column in COLUMNS}
        for nm_id in nm_ids:
            rows += 1
            for column in COLUMNS:
                sums[column] += per_nm[(day, nm_id)][column]
        for column in COLUMNS:
            require(sums[column] == cabinet[day][column], f"{day} {column}: per-nm sum {sums[column]} != cabinet {cabinet[day][column]}")
    require(rows == len(days) * len(nm_ids), "one row per versioned day x nmId, zeros included")
    return len(days), len(nm_ids), rows


def run_unit_test(command: list[str] = UNIT_TEST_COMMAND) -> int:
    """The gate of AD-19 is the node:test file itself; it must pass with zero failures and zero skips."""
    read(UNIT_TEST)
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    require(completed.returncode == 0, f"unit test failed (exit {completed.returncode}):\n{completed.stdout[-2000:]}\n{completed.stderr[-2000:]}")
    passed = 0
    for line in completed.stdout.splitlines():
        if line.startswith("# pass "):
            passed += int(line.split()[2])
        if line.startswith("# fail ") and int(line.split()[2]) != 0:
            raise NmDailyGateError(f"unit test reported failures:\n{completed.stdout[-2000:]}")
        if line.startswith("# skipped ") and int(line.split()[2]) != 0:
            raise NmDailyGateError("unit test skipped cases - the gate must run everywhere without PostgreSQL")
    require(passed >= 6, f"unit test reported {passed} passed cases, expected at least 6")
    return passed


def verify(node_test: bool = True) -> tuple[int, int, int, int]:
    check_migration()
    check_writer()
    days, nm_ids, rows = replay_fixture()
    passed = run_unit_test() if node_test else 0
    return days, nm_ids, rows, passed


def main() -> None:
    days, nm_ids, rows, passed = verify()
    require(days == 13 and nm_ids == FIXTURE_NM_IDS and rows == 13 * FIXTURE_NM_IDS, "fixture replay drifted")
    require(passed >= 6, "node:test gate drifted")
    print(GATE_LINE)


if __name__ == "__main__":
    try:
        main()
    except (NmDailyGateError, KeyError, ValueError, OSError) as exc:
        print(f"nm-daily gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
