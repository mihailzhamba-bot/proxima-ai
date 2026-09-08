"""AC-preserved gate script for Story 3.1 (standard library only).

Acceptance criterion (epics.md, Story 3.1): `make verify` must show
`funnel_v3: 21 obs, replay 0, changed payload versions` green.

Pure check only, no database: it replays the observation-store semantics of
migration 017 on the committed fixture (3 nmIds x 7 days) - the canonical hash
is part of the key, so an identical replay adds nothing and a changed payload
is a new observation - and pins the repository artifacts of the story: the
migration (key, `_latest`, `_current` with csv preference, RLS matrix), the
job (run ledger, window, batch cap, active nmIds), the separate systemd unit
(06:15 Europe/Moscow, own OnFailure, never a morning_run.sh step) and the
cross-language canonical digest the collector tests pin as well. The db-side
behaviour (RLS, versions, run status) is covered by
services/collector/tests/funnel-v3.db.test.ts inside pg-roundtrip.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "017_funnel.sql"
PARSER = ROOT / "services" / "collector" / "src" / "wb" / "funnel-v3.ts"
FACTS = ROOT / "services" / "collector" / "src" / "facts" / "funnel-daily.ts"
JOB = ROOT / "services" / "collector" / "src" / "jobs" / "funnel-v3.ts"
SERVICE = ROOT / "infra" / "systemd" / "proxima-funnel-v3@.service"
TIMER = ROOT / "infra" / "systemd" / "proxima-funnel-v3@.timer"
RUNNER = ROOT / "tools" / "funnel_v3_run.sh"
MORNING = ROOT / "tools" / "morning_run.sh"
FIXTURE = ROOT / "services" / "collector" / "tests" / "fixtures" / "wb-api" / "analytics" / "sales_funnel_v3_history" / "sample.json"

FIXTURE_NM_IDS = 3
FIXTURE_DAYS = 7
DICTIONARY = ("open_card", "cart", "orders", "orders_sum_rub", "buyouts", "buyouts_sum_rub")
# sha256(canonicalJson(first history record)) - services/collector/tests/funnel-v3.test.ts pins the same digest.
FIRST_RECORD_CANONICAL_SHA256 = "6bc1aa356e207f20df1958aeb5d0930599f6c10025ab19869f785114870abb71"

TENANT_GUARD = "USING (tenant_id = current_setting('proxima.tenant_id', true))"
WITH_CHECK = "WITH CHECK (tenant_id = current_setting('proxima.tenant_id', true))"


class FunnelGateError(AssertionError):
    """A story artifact drifted away from the AC or the spine (AD-5/AD-6/AD-11)."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FunnelGateError(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing story artifact: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def canonical_sha256(record: dict) -> str:
    """Same canonical form as services/collector/src/intake/manifest.ts: sorted keys, no whitespace."""
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_migration() -> None:
    sql = read(MIGRATION)
    require("PRIMARY KEY (tenant_id, nm_id, calendar_day, source, canonical_sha256)" in sql, "017: observation key must be (tenant_id, nm_id, calendar_day, source, canonical_sha256) (AD-5)")
    require("PRIMARY KEY (tenant_id, nm_id, calendar_day, source, run_id)" in sql, "017: fact versions are keyed by run_id (AD-3)")
    require("source text NOT NULL CHECK (source IN ('v3', 'csv'))" in sql, "017: source is v3|csv (AD-5)")
    require(sql.count("run_id uuid NOT NULL REFERENCES collector_runs(run_id) ON DELETE CASCADE") == 2, "017: both tables cascade from collector_runs (AD-3)")
    require(sql.count("evidence_sha256 char(64) NOT NULL") == 2, "017: observations and versions carry evidence_sha256")
    for column in DICTIONARY:
        require(sql.count(f"    {column} ") == 2, f"017: COLUMN_MAP scn001 column {column} must exist in both tables (AD-5)")
    require("observed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP" in sql, "017: observations carry observed_at (AD-5)")
    require("CREATE VIEW stg_wb_funnel_latest WITH (security_invoker = true) AS\nSELECT DISTINCT ON (tenant_id, nm_id, calendar_day, source) *" in sql, "017: _latest is DISTINCT ON the key without the hash (AD-5)")
    require("ORDER BY tenant_id, nm_id, calendar_day, source, observed_at DESC" in sql, "017: _latest orders by observed_at DESC (AD-5)")
    require("CREATE VIEW fact_funnel_daily_current WITH (security_invoker = true) AS" in sql, "017: _current view with security_invoker (AD-13)")
    require("WHERE r.status = 'SUCCEEDED'" in sql, "017: _current reads SUCCEEDED runs only (AD-3)")
    require("CASE f.source WHEN 'csv' THEN 0 ELSE 1 END, r.finished_at DESC, f.run_id DESC" in sql, "017: _current prefers csv, then the latest finished run (AD-5/AD-3)")
    require(sql.count("ENABLE ROW LEVEL SECURITY") == 2, "017: RLS on both tables (AD-13)")
    for table, roles in (("stg_wb_funnel_obs", ("collector", "janitor")), ("fact_funnel_daily", ("collector", "norm", "janitor"))):
        for role in roles:
            policy = f"CREATE POLICY tenant_isolation_{role} ON {table} FOR "
            require(policy in sql and TENANT_GUARD in sql.split(policy, 1)[1].split("\n", 1)[0], f"017: {table} needs the tenant policy for {role} (AD-11)")
        require(f"CREATE POLICY tenant_isolation_janitor ON {table} FOR ALL TO proxima_run_janitor {TENANT_GUARD} {WITH_CHECK};" in sql, f"017: janitor FOR ALL on {table} (AD-11)")
    require("GRANT SELECT, INSERT ON stg_wb_funnel_obs TO proxima_job_collector;" in sql, "017: collector writes observations")
    require("GRANT SELECT, INSERT ON fact_funnel_daily TO proxima_job_collector;" in sql, "017: collector writes versions")
    require("GRANT SELECT ON fact_funnel_daily_current TO proxima_job_norm;" in sql, "017: norm reads _current (AC)")
    require("proxima_webapp_readonly" not in sql, "017: the webapp has no funnel grant in this story")
    require("VALUES (17, 'funnel', '" in sql, "017: ledger identity must be (17, funnel)")


def check_job() -> None:
    parser = read(PARSER)
    require("FUNNEL_WINDOW_START_OFFSET = 6" in parser and "end: runDay" in parser, "window must be WB [run_day-6, run_day] (Mike 08.09, API-FACTS)")
    require("maxPerPage ?? 20" in parser and "FUNNEL_BATCH_SIZE" in parser, "batches must be capped at 20 nmIds (AD-4)")
    require("ACTIVE_NM_ID_DAYS = 30" in parser, "active nmIds come from the last 30 days (AC)")
    require("ON CONFLICT (tenant_id, nm_id, calendar_day, source, canonical_sha256) DO NOTHING" in parser, "replay of the same canonical payload is a no-op (AD-5)")
    require("if (day > window.end) return;" in parser, "records after run_day are never observed")
    facts = read(FACTS)
    require("JOIN stg_wb_funnel_latest l" in facts and "INSERT INTO fact_funnel_daily" in facts, "versions are built from stg_wb_funnel_latest (AD-5)")
    require("INSERT INTO collector_run_inputs" in facts, "versions record their input runs (AD-3)")
    job = read(JOB)
    require("const RUN_KIND = 'funnel_v3';" in job and "ledger.open({ tenantId, kind: RUN_KIND" in job, "the job is a collector_runs run of kind funnel_v3 (AD-3)")
    require("ledger.succeed(tenantId, runId, async (session) => {" in job and "versionFunnelDaily(session" in job, "versions and SUCCEEDED share one transaction (AD-3)")
    require("FROM stg_wb_orders_latest" in job, "active nmIds are read from stg_wb_orders_latest (AC)")
    require("new WbArtifactSink(" in job and "new WbClient(" in job, "every response is recorded through the single WB client (AD-1/AD-4)")
    require("assertBatchCoverage(parsed.rows, nmIds, window)" in job, "a day counts as collected only with full coverage (AC)")
    require("'--analytics-token-file'" in job and "readPrivateSecret" in job, "the analytics token arrives as a private file path (Conventions)")
    require("'x-ratelimit-limit'" in job, "the live rate limit must be logged from the response headers (PRD 4.0)")
    require("class FunnelCoverageError" in job and "error.notes" in job, "an incomplete run is FAILED with its coverage summary in notes")


def check_units() -> None:
    timer = read(TIMER)
    require("OnCalendar=*-*-* 06:15:00 Europe/Moscow" in timer, "timer must fire at 06:15 Europe/Moscow (AC, AD-7)")
    require("Persistent=true" in timer and "Unit=proxima-funnel-v3@%i.service" in timer, "timer must be persistent and target the funnel service")
    service = read(SERVICE)
    require("OnFailure=proxima-alert@%n.service" in service, "service needs its own OnFailure alert (AC, AD-6)")
    require("ExecStart=/usr/bin/env bash /srv/proxima-ai/repo/tools/funnel_v3_run.sh %i" in service, "service must run tools/funnel_v3_run.sh")
    require("Type=oneshot" in service and "ProtectHome=true" in service, "service is a one-shot like proxima-morning@ (AD-6)")
    runner = read(RUNNER)
    require("npm run funnel-v3 --" in runner and "_wb_analytics_token" in runner, "runner must start the funnel-v3 job with the tenant analytics token")
    require("funnel" not in read(MORNING).lower(), "funnel_v3 must not be a morning_run.sh step (CR to AD-6, decision 4a)")


def replay_fixture() -> tuple[int, int, bool, int]:
    payload = json.loads(read(FIXTURE))
    require(isinstance(payload, list) and len(payload) == FIXTURE_NM_IDS, f"fixture must hold {FIXTURE_NM_IDS} products")
    store: dict[tuple[int, str, str], dict] = {}

    def observe(products: list) -> int:
        inserted = 0
        for product in products:
            require(product.get("currency") == "RUB", "fixture money must be RUB")
            nm_id = product["product"]["nmId"]
            require(len(product["history"]) == FIXTURE_DAYS, f"nmId {nm_id} must have {FIXTURE_DAYS} days")
            for record in product["history"]:
                for field in ("openCount", "cartCount", "orderCount", "orderSum", "buyoutCount", "buyoutSum"):
                    require(isinstance(record.get(field), (int, float)) and record[field] >= 0, f"nmId {nm_id} {record.get('date')} lacks {field}")
                key = (nm_id, record["date"], canonical_sha256(record))
                if key not in store:
                    store[key] = record
                    inserted += 1
        return inserted

    observations = observe(payload)
    require(observations == FIXTURE_NM_IDS * FIXTURE_DAYS, f"expected {FIXTURE_NM_IDS * FIXTURE_DAYS} observations, got {observations}")
    require(canonical_sha256(payload[0]["history"][0]) == FIRST_RECORD_CANONICAL_SHA256, "canonical digest of the first record drifted from the collector pin")
    replay = observe(payload)

    changed = json.loads(json.dumps(payload))
    record = changed[0]["history"][0]
    record["openCount"] += 1
    before = len(store)
    require(observe(changed) == 1, "a changed payload must be exactly one new observation")
    versions = len(store) == before + 1 and (changed[0]["product"]["nmId"], record["date"], canonical_sha256(record)) in store
    latest = max((key for key in store if key[0] == changed[0]["product"]["nmId"] and key[1] == record["date"]), key=lambda key: store[key]["openCount"])
    require(store[latest]["openCount"] == record["openCount"], "the newest observation must carry the changed payload")

    # `= run_day` is observed but never versioned (AD-7).
    run_day = date.fromisoformat(payload[0]["history"][-1]["date"])
    versionable = sum(1 for product in payload for entry in product["history"] if date.fromisoformat(entry["date"]) < run_day)
    require(versionable == FIXTURE_NM_IDS * (FIXTURE_DAYS - 1), "the run day must not be versionable")
    return observations, replay, versions, versionable


def main() -> None:
    check_migration()
    check_job()
    check_units()
    observations, replay, versions, versionable = replay_fixture()
    require(replay == 0, f"replay must add nothing, added {replay}")
    require(versions, "changed payload must become a new version")
    require(versionable == 18, "run day version exclusion drifted")
    print(f"funnel_v3: {observations} obs, replay {replay}, changed payload versions")


if __name__ == "__main__":
    try:
        main()
    except (FunnelGateError, KeyError, ValueError) as exc:
        print(f"funnel gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
