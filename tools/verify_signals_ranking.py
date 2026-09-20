"""AC-preserved gate script for Story 4.2 (standard library + the control-plane package).

Acceptance criterion (epics.md, Story 4.2): `make verify` must show
`brief: signals sorted by rub_assessment` green.

Pure check only, no database: it runs the detector core on fixed facts (five
SKUs in two subjects with known losses) and pins the AC - `signals[]` is
sorted by `rub_assessment.value_rub` descending with the larger loss first
(CAP-7) and a deterministic tie-break (deepest deviation, then SKU before
subject, then nm_id); `brief.status`, the cabinet numbers and the
"numbers only when ok" rule are unchanged by the signals; `signals[]` is empty
and refused when the brief is not ok (PRD FR-7); growth is reported as a
number and never becomes a signal (PRD FR-34, one-sided threshold). The
threshold comes from the control-plane configuration (decision 6a, D25): the
null triple keeps every candidate below the norm, `-30` (Story 4.4) drops the
smaller deviations without changing the ranking rule, and the triple travels
in `brief_daily.payload.threshold` and in each signal's `detection_data`. The
script also pins the repository artifacts: the packaged configuration file
loads, `brief/cli.py` reads it once and hands the same value to the payload
and to the detector, `contracts/brief.schema.json` requires `threshold`, and
the gate is wired into `make verify` right after `detector`. The full
jsonschema validation lives in
services/control-plane/tests/detector/test_detector_ranking.py; the db-side
behaviour is covered by tests/detector/test_detector_db.py inside pg-roundtrip.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from proxima_control_plane.brief.assembler import build_day, with_signals
from proxima_control_plane.brief.builder import DataStatus, MetricActual, MetricNorm
from proxima_control_plane.detector.metrics import DailyMetrics, SubjectRow
from proxima_control_plane.detector.signals import DetectionResult, detect, rank
from proxima_control_plane.detector.threshold import DEFAULT_CONFIG_PATH, NOT_APPLIED, AlertThreshold, load_alert_threshold

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "services" / "control-plane" / "src" / "proxima_control_plane"
BRIEF_CLI = PACKAGE / "brief" / "cli.py"
SCHEMA = ROOT / "contracts" / "brief.schema.json"
MAKEFILE = ROOT / "Makefile"
RANKING_TEST = ROOT / "services" / "control-plane" / "tests" / "detector" / "test_detector_ranking.py"

GATE_LINE = "brief: signals sorted by rub_assessment"
DAY = date(2026, 8, 29)
TENANT = "fixture-tenant-001"
RUN = "11111111-1111-4111-8111-111111111111"
EVIDENCE = ("a" * 64, "b" * 64)
CREATED_AT = "2026-08-30T02:45:00+00:00"
STATUS = DataStatus(DAY, "2026-08-30T02:41:12+00:00", False)
MINUS_30 = AlertThreshold(Decimal(-30), "DECISIONS.md D25 decision 6a: retro run of 184 fixture days", date(2026, 9, 2))
NULL_TRIPLE = {"value": None, "source": None, "date": None}

# Five SKUs with known losses (see the same table in test_detector_ranking.py):
# 2001 500.00 (-50 %), 2002 800.00 (-40 %), 2003 -100.00 (orders -12.5 %, revenue +12.5 %),
# 2004 500.00 (-25 %), 2005 growth (+25 %, not a candidate); subjects Платье 1300.00 (-43.3 %)
# and Юбка -100.00 (orders -2.1 %). Cabinet = the sum: 78 / 7800.00 -> 64 / 6600.00.
SKUS = {
    2001: (10, 5, "1000.00", "500.00", "Платье"),
    2002: (20, 12, "2000.00", "1200.00", "Платье"),
    2003: (8, 7, "800.00", "900.00", "Юбка"),
    2004: (20, 15, "2000.00", "1500.00", "Юбка"),
    2005: (20, 25, "2000.00", "2500.00", "Юбка"),
}
CABINET_NORMS = [MetricNorm("orders", Decimal("78.00"), 14, 14, "ok"), MetricNorm("revenue", Decimal("7800.00"), 14, 14, "ok")]
CABINET_ACTUAL = MetricActual(64, Decimal("6600.00"))
EXPECTED_ORDER = ["Платье", "2002", "2001", "2004", "2003", "Юбка"]
EXPECTED_MONEY = ["1300.00", "800.00", "500.00", "500.00", "-100.00", "-100.00"]
EXPECTED_MINUS_30 = ["Платье", "2002", "2001"]


class RankingGateError(AssertionError):
    """A story artifact drifted away from the AC or the spine (AD-9/AD-10/CAP-7)."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RankingGateError(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing story artifact: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return path.read_text(encoding="utf-8")


def _rows(nm_id: int, window_orders: int, actual_orders: int, window_revenue: str, actual_revenue: str) -> list[DailyMetrics]:
    series = [DailyMetrics(nm_id, DAY - timedelta(days=offset), window_orders, Decimal(window_revenue), RUN, EVIDENCE) for offset in range(14, 0, -1)]
    series.append(DailyMetrics(nm_id, DAY, actual_orders, Decimal(actual_revenue), RUN, EVIDENCE))
    return series


def build_fixed_facts() -> tuple[list[DailyMetrics], dict[int, SubjectRow]]:
    facts = [row for nm_id, (wo, ao, wr, ar, _) in SKUS.items() for row in _rows(nm_id, wo, ao, wr, ar)]
    subjects = {nm_id: SubjectRow(nm_id, name, f"ART-{nm_id}", "fixture-brand", RUN, "c" * 64) for nm_id, (*_, name) in SKUS.items()}
    return facts, subjects


def run_detector(threshold: AlertThreshold = NOT_APPLIED) -> DetectionResult:
    facts, subjects = build_fixed_facts()
    return detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT, threshold=threshold)


def label(signal: dict) -> str:
    data = signal["detection_data"]
    return str(data["nm_id"]["value"]) if data["level"]["value"] == "sku" else data["subject_name"]["value"]


def money(result: DetectionResult) -> list[str]:
    return [s["rub_assessment"]["value_rub"] for s in result.signals]


def ok_day(threshold: AlertThreshold = NOT_APPLIED):
    return build_day(DAY, CABINET_NORMS, CABINET_ACTUAL, STATUS, [RUN], threshold=threshold)


def check_threshold_shape(payload: dict, schema: dict) -> None:
    """Structural check of payload.threshold against brief.schema.json with the standard library only."""
    require("threshold" in schema["required"], "brief.schema.json must require `threshold` (Story 4.2)")
    branches = schema["properties"]["threshold"]["oneOf"]
    triple = payload["threshold"]
    require(set(triple) == {"value", "source", "date"}, f"payload.threshold must be {{value, source, date}}, got {sorted(triple)}")
    if triple["value"] is None:
        require(triple["source"] is None and triple["date"] is None, "a null threshold carries null source and date")
        return
    applied = branches[1]["properties"]
    require(isinstance(triple["value"], (int, float)) and not isinstance(triple["value"], bool), "threshold.value must be a number")
    require(triple["value"] < applied["value"]["exclusiveMaximum"], "threshold.value must be negative (one-sided drop threshold, PRD FR-34)")
    require(isinstance(triple["source"], str) and len(triple["source"]) >= applied["source"]["minLength"], "threshold.source must be a non-empty string")
    require(isinstance(triple["date"], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", triple["date"]) is not None, "threshold.date must be an ISO date")
    date.fromisoformat(triple["date"])


def check_result() -> list[str]:
    schema = json.loads(read(SCHEMA))
    result = run_detector()
    labels = [label(s) for s in result.signals]
    # 1. Sorted by rub_assessment descending, larger loss first, deterministic tie-break.
    require(money(result) == EXPECTED_MONEY, f"signals must be ranked by money at risk: {money(result)}")
    values = [Decimal(value) for value in money(result)]
    require(values == sorted(values, reverse=True), "rub_assessment must be non-increasing (CAP-7)")
    require(labels == EXPECTED_ORDER, f"ties must break by the deepest deviation, then SKU before subject: {labels}")
    require(rank(list(reversed(result.signals))) == list(result.signals), "rank() must be a pure function of the signals")
    require(run_detector().signals == result.signals, "the same facts must give the same order")
    # 2. Growth is a number, never a signal (PRD FR-34, one-sided threshold).
    growth = next(e for e in result.evaluations if e.key == "2005")
    require(growth.status == "ok" and growth.orders_deviation_pct == 25.0 and not growth.is_candidate, "2005: growth is evaluated as a number but is never a candidate")
    require("2005" not in labels, "growth must not enter signals[]")
    partial = next(s for s in result.signals if label(s) == "2003")
    require(partial["detection_data"]["revenue_deviation_pct"] == {"value": 12.5, "is_unknown": False}, "a growing metric inside a candidate is shown as a signed number")
    require(partial["detection_data"]["triggered_by"] == {"value": ["orders"], "is_unknown": False}, "only the dropping metric triggers (D32)")
    # 3. brief.status and the cabinet numbers are unchanged; signals[] empty and refused when not ok.
    bare = ok_day()
    day = with_signals(bare, result.signals)
    require(day.status == "ok" and bare.status == "ok", "attaching signals must not change brief.status")
    require(day.payload["deviation_pct"] == {"orders": -17.9, "revenue": -15.4} == bare.payload["deviation_pct"], "the cabinet deviation must not change with signals")
    require({k: v for k, v in day.payload.items() if k != "signals"} == {k: v for k, v in bare.payload.items() if k != "signals"}, "only signals[] may differ")
    require(len(day.payload["signals"]) == 6, "an ok day carries every candidate when no threshold applies")
    insufficient_norms = [MetricNorm("orders", Decimal("78.00"), 14, 9, "insufficient"), MetricNorm("revenue", Decimal("7800.00"), 14, 9, "insufficient")]
    insufficient = build_day(DAY, insufficient_norms, CABINET_ACTUAL, STATUS, [RUN])
    blocked = build_day(DAY, [], None, STATUS, [])
    for other in (insufficient, blocked):
        require(other.payload["signals"] == [], f"a {other.status} day carries no signals (PRD FR-7)")
        check_threshold_shape(other.payload, schema)
        try:
            with_signals(other, result.signals)
        except ValueError:
            continue
        raise RankingGateError(f"with_signals must refuse a {other.status} day (PRD FR-7)")
    # 4. Threshold from configuration: null keeps all, -30 drops the smaller deviations, same ranking rule.
    check_threshold_shape(day.payload, schema)
    require(day.payload["threshold"] == NULL_TRIPLE, "Story 4.2: the null triple is written while no threshold applies")
    require(result.suppressed_by_threshold == 0, "no candidate is suppressed without a threshold")
    for signal in result.signals:
        require(signal["detection_data"]["threshold_pct"] == {"value": None, "is_unknown": True}, "the null threshold is UNKNOWN in detection_data")
        require(signal["detection_data"]["threshold_source"] == {"value": None, "is_unknown": True}, "the null source is UNKNOWN in detection_data")
        require(signal["detection_data"]["threshold_date"] == {"value": None, "is_unknown": True}, "the null date is UNKNOWN in detection_data")
    filtered = run_detector(MINUS_30)
    require([label(s) for s in filtered.signals] == EXPECTED_MINUS_30, f"-30 must keep only the deviations at or beyond it: {[label(s) for s in filtered.signals]}")
    require(filtered.suppressed_by_threshold == 3, f"-30 must suppress three candidates, got {filtered.suppressed_by_threshold}")
    require([s["signal_id"] for s in filtered.signals] == [s["signal_id"] for s in result.signals][:3], "the ranking rule must not depend on the threshold")
    applied_day = with_signals(ok_day(MINUS_30), filtered.signals)
    check_threshold_shape(applied_day.payload, schema)
    require(applied_day.payload["threshold"] == {"value": -30, "source": MINUS_30.threshold_source, "date": "2026-09-02"}, "the applied triple is written to payload.threshold")
    require(applied_day.payload["deviation_pct"] == bare.payload["deviation_pct"], "the threshold must not change the cabinet numbers")
    for signal in filtered.signals:
        require(signal["detection_data"]["threshold_pct"] == {"value": -30, "is_unknown": False}, "the applied threshold is written to detection_data")
    try:
        with_signals(ok_day(), filtered.signals)
    except ValueError:
        pass
    else:
        raise RankingGateError("a brief must refuse signals built with another threshold")
    require(filtered.snapshot_id != result.snapshot_id, "the threshold is part of the input snapshot")
    return labels


def check_wiring(brief_cli: Path = BRIEF_CLI, schema: Path = SCHEMA, makefile: Path = MAKEFILE, config: Path = DEFAULT_CONFIG_PATH) -> None:
    cli = read(brief_cli)
    require(cli.count("load_alert_threshold(") == 1, "brief/cli.py must read the threshold configuration exactly once (Story 4.2)")
    require(cli.index("load_alert_threshold(") < cli.index("loader.connect("), "brief/cli.py must read the threshold before connecting: a bad configuration fails before a run is opened")
    require("fact_run_ids, threshold=threshold)" in cli, "brief/cli.py must hand the threshold to assembler.build_day")
    require("run_detector_step(connection, tenant_id, brief_day, created_at=utc_now_iso(), threshold=threshold)" in cli, "brief/cli.py must hand the same threshold to the detector step")
    contract = json.loads(read(schema))
    require("threshold" in contract["required"] and "threshold" in contract["properties"], "contracts/brief.schema.json must carry a required `threshold`")
    require(len(contract["properties"]["threshold"]["oneOf"]) == 2, "brief.schema.json: threshold is either the null triple or value+source+date")
    verify_line = next((line for line in read(makefile).splitlines() if line.startswith("verify:")), "")
    targets = verify_line.split()
    require("signals-ranking" in targets and "detector" in targets and targets.index("signals-ranking") == targets.index("detector") + 1, "Makefile: `signals-ranking` must follow `detector` in the verify target")
    read(RANKING_TEST)
    loaded = load_alert_threshold(config)
    require(loaded.applied == (loaded.threshold_source is not None) == (loaded.threshold_date is not None), "the packaged threshold configuration must carry value, source and date together")


def verify() -> list[str]:
    labels = check_result()
    check_wiring()
    return labels


def main() -> None:
    labels = verify()
    require(labels == EXPECTED_ORDER, f"fixed-facts scenario drifted: {labels}")
    print(GATE_LINE)


if __name__ == "__main__":
    try:
        main()
    except (RankingGateError, KeyError, ValueError, TypeError, OSError) as exc:
        print(f"signals ranking gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
