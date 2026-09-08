#!/usr/bin/env python3
"""Offline acceptance gate for Story 3.3 (standard library only)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOB = ROOT / "services/collector/src/jobs/funnel-csv-promote.ts"
FACTS = ROOT / "services/collector/src/facts/funnel-daily.ts"
PACKAGE = ROOT / "services/collector/package.json"
FIXTURE = ROOT / "services/collector/tests/fixtures/wb-api/analytics/nm_report_downloads/funnel_csv_promote.json"
DB_TEST = ROOT / "services/collector/tests/funnel-csv-promote.db.test.ts"
RUNNER = ROOT / "tools/funnel_csv_run.sh"
SERVICE = ROOT / "infra/systemd/proxima-funnel-csv@.service"
TIMER = ROOT / "infra/systemd/proxima-funnel-csv@.timer"
MAKEFILE = ROOT / "Makefile"
GATE_LINE = "funnel_csv: promote + replay after delete"
EXPECTED_COLUMNS = (
    "nmID", "dt", "openCardCount", "addToCartCount", "ordersCount", "ordersSumRub",
    "buyoutsCount", "buyoutsSumRub", "cancelCount", "cancelSumRub",
    "addToCartConversion", "cartToOrderConversion", "buyoutPercent", "addToWishlist", "currency",
)


class GateError(AssertionError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise GateError(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing artifact: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def check_fixture() -> list[dict[str, str]]:
    payload = json.loads(read(FIXTURE))
    require(isinstance(payload, list) and len(payload) == 21, "fixture must contain 21 rows")
    require(len({row["nmID"] for row in payload}) == 3, "fixture must contain 3 nmID")
    require(len({row["dt"] for row in payload}) == 7, "fixture must contain 7 calendar days")
    for row in payload:
        require(tuple(row) == EXPECTED_COLUMNS, "fixture columns must exactly follow CSV_COLUMN_MAP")
        require(all(isinstance(value, str) and value for value in row.values()), "loader payload values must be non-empty strings")
    return payload


def check_job() -> None:
    job = read(JOB)
    for marker in (
        'Confirmed by API-FACTS "async CSV depth" (Story 3.0 probe, 08.09.2026)',
        "export const CSV_COLUMN_MAP",
        "nmId: 'nmID'",
        "calendarDay: 'dt'",
        "openCard: 'openCardCount'",
        "cart: 'addToCartCount'",
        "orders: 'ordersCount'",
        "ordersSumRub: 'ordersSumRub'",
        "buyouts: 'buyoutsCount'",
        "buyoutsSumRub: 'buyoutsSumRub'",
        "text(payload, 'currency', context) !== 'RUB'",
        "const RUN_KIND = 'funnel_csv_promote'",
        "const FUNNEL_SOURCE = 'csv'",
        "FROM wb_analytics_report_tasks t",
        "JOIN stg_wb_nm_report_rows r",
        "t.downloaded_sha256 IS NOT NULL",
        "insertFunnelObservations(client",
        "versionFunnelDaily(client",
        "await ledger.succeed",
        "await ledger.fail",
    ):
        require(marker in job, f"job lost contract marker {marker!r}")
    require("lifecycle_status" not in job, "promotion must not depend on task lifecycle state")
    require("source: FUNNEL_SOURCE" in job, "facts must be versioned as csv")
    facts = read(FACTS)
    require("readonly source?: FunnelSource" in facts and "const source = input.source ?? FUNNEL_SOURCE" in facts,
            "shared fact writer must accept csv while preserving the v3 default")
    package = json.loads(read(PACKAGE))
    require(package["scripts"].get("funnel-csv-promote") == "node dist/jobs/funnel-csv-promote.js",
            "collector package must expose the promotion job")


def check_replay_contract(rows: list[dict[str, str]]) -> None:
    store: set[tuple[str, str, str]] = set()

    def promote() -> int:
        before = len(store)
        for row in rows:
            store.add((row["nmID"], row["dt"], "csv"))
        return len(store) - before

    require(promote() == 21, "first promotion must build 21 product-days")
    store.clear()  # delete_run.py cascades observations/facts of the promote run
    require(promote() == 21, "replay after delete must restore all product-days from durable task rows")
    db_test = read(DB_TEST)
    for marker in ("delete_run.py", "lifecycle FAILED does not suppress durable rows", "source: 'csv'", "report task survives promote deletion"):
        require(marker in db_test, f"PostgreSQL test lost {marker!r}")


def check_units() -> None:
    runner = read(RUNNER)
    require("control-plane-admin python tools/wb_async_report.py" in runner, "phase 1 must use control-plane-admin")
    require("collector" in runner and "npm run funnel-csv-promote" in runner, "phase 2 must use collector")
    require(runner.index("control-plane-admin python") < runner.rindex("npm run funnel-csv-promote"), "download must precede promotion")
    service = read(SERVICE)
    require("OnFailure=proxima-alert@%n.service" in service, "service needs its own alert")
    require("ExecStart=/usr/bin/env bash /srv/proxima-ai/repo/tools/funnel_csv_run.sh %i" in service, "service must use the two-phase runner")
    timer = read(TIMER)
    require("OnCalendar=Mon *-*-* 06:30:00 Europe/Moscow" in timer, "timer must run Mondays at 06:30 Moscow")
    require("Persistent=true" in timer and "Unit=proxima-funnel-csv@%i.service" in timer, "timer must be persistent and target the instance service")


def check_makefile() -> None:
    makefile = read(MAKEFILE)
    verify = next((line for line in makefile.splitlines() if line.startswith("verify:")), "")
    require("funnel-csv" in verify.split(), "make verify must include funnel-csv")
    require(re.search(r"^funnel-csv:\n\tuv run --python 3\.14 python tools/verify_funnel_csv\.py$", makefile, re.MULTILINE) is not None,
            "funnel-csv target must invoke tools/verify_funnel_csv.py")


def main() -> None:
    rows = check_fixture()
    check_job()
    check_replay_contract(rows)
    check_units()
    check_makefile()
    print(GATE_LINE)


if __name__ == "__main__":
    try:
        main()
    except (GateError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"funnel_csv gate failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
