"""AC-preserved gate script for Story 4.1 (standard library + the control-plane package).

Acceptance criterion (epics.md, Story 4.1): `make verify` must show
`detector: sku deviation, zero-norm insufficient, no signals when not ok` green.

Pure check only, no database: it runs the detector core on fixed facts (five
SKUs in two subjects) and pins the three behaviours of the AC - the SKU
deviation is measured against the SKU norm of D21 (median of 14 full days) with
money at risk = revenue norm minus revenue of the day (AD-10), a zero norm or a
short history is `insufficient` with no deviation and no NaN/Infinity in the
payload, and `signals[]` are refused for a brief that is not `ok` (PRD FR-7).
The output is checked against `contracts/signal.schema.json` structurally
(required keys, enums, the money pattern, the `detection_data` entry shape) with
the standard library; the full jsonschema validation lives in
services/control-plane/tests/detector/test_detector_core.py. The script also
pins the repository artifacts of the story: the brief run calls the detector
only for an `ok` day, the loader reads `_current` views only, the gate is wired
into `make verify` right after `nm-daily`, and the db-test runs inside
pg-roundtrip. The db-side behaviour (signals in brief_daily.payload, run_inputs,
RLS) is covered by services/control-plane/tests/detector/test_detector_db.py.
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
from proxima_control_plane.detector.signals import DetectionResult, detect

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "services" / "control-plane" / "src" / "proxima_control_plane"
BRIEF_CLI = PACKAGE / "brief" / "cli.py"
ASSEMBLER = PACKAGE / "brief" / "assembler.py"
LOADER = PACKAGE / "detector" / "loader.py"
SCHEMA = ROOT / "contracts" / "signal.schema.json"
MAKEFILE = ROOT / "Makefile"
ROUNDTRIP = ROOT / "tools" / "pg_local_roundtrip.sh"
DB_TEST = ROOT / "services" / "control-plane" / "tests" / "detector" / "test_detector_db.py"

GATE_LINE = "detector: sku deviation, zero-norm insufficient, no signals when not ok"
DAY = date(2026, 8, 29)
TENANT = "fixture-tenant-001"
RUN = "11111111-1111-4111-8111-111111111111"
EVIDENCE = ("a" * 64, "b" * 64)
CREATED_AT = "2026-08-30T02:45:00+00:00"
STATUS = DataStatus(DAY, "2026-08-30T02:41:12+00:00", False)


class DetectorGateError(AssertionError):
    """A story artifact drifted away from the AC or the spine (AD-8/AD-10/AD-19)."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DetectorGateError(message)


def read(path: Path) -> str:
    require(path.is_file(), f"missing story artifact: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return path.read_text(encoding="utf-8")


def _rows(nm_id: int, window_orders: int, actual_orders: int | None, window_revenue: str, actual_revenue: str, days: int = 14) -> list[DailyMetrics]:
    series = [
        DailyMetrics(nm_id, DAY - timedelta(days=offset), window_orders, Decimal(window_revenue), RUN, EVIDENCE)
        for offset in range(days, 0, -1)
    ]
    if actual_orders is not None:
        series.append(DailyMetrics(nm_id, DAY, actual_orders, Decimal(actual_revenue), RUN, EVIDENCE))
    return series


def build_fixed_facts() -> tuple[list[DailyMetrics], dict[int, SubjectRow]]:
    """Five SKUs: a drop (1001), a zero norm (1002), growth (1003), a small drop (1004), nine days (1005)."""
    facts = [
        *_rows(1001, 10, 5, "1000.00", "500.00"),
        *_rows(1002, 0, 0, "0.00", "0.00"),
        *_rows(1003, 20, 25, "2000.00", "2500.00"),
        *_rows(1004, 8, 7, "800.00", "700.00"),
        *_rows(1005, 3, 1, "300.00", "100.00", days=9),
    ]
    subjects = {
        nm_id: SubjectRow(nm_id, name, f"ART-{nm_id}", "fixture-brand", RUN, "c" * 64)
        for nm_id, name in ((1001, "Платье"), (1002, "Платье"), (1003, "Юбка"), (1004, "Платье"), (1005, "Юбка"))
    }
    return facts, subjects


def run_detector() -> DetectionResult:
    facts, subjects = build_fixed_facts()
    return detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT)


def check_signal_shape(signal: dict, schema: dict) -> None:
    """Structural check against signal.schema.json with the standard library only."""
    require(set(signal) == set(schema["required"]), f"signal keys must be exactly the required set: {sorted(signal)}")
    properties = schema["properties"]
    require(signal["schema_version"] == properties["schema_version"]["const"], "schema_version must be 1")
    require(signal["scenario_code"] in properties["scenario_code"]["enum"], "scenario_code outside the contract enum")
    require(signal["trust_marking"] in properties["trust_marking"]["enum"], "trust_marking outside the contract enum")
    for key in ("signal_id", "snapshot_id", "tenant_id", "created_at"):
        require(isinstance(signal[key], str) and signal[key], f"{key} must be a non-empty string")
    money = properties["rub_assessment"]["anyOf"][1]
    pattern = money["properties"]["value_rub"]["pattern"]
    require(re.fullmatch(pattern, signal["rub_assessment"]["value_rub"]) is not None, "value_rub must carry exactly two decimals (AD-10)")
    require(signal["rub_assessment"]["method"] in money["properties"]["method"]["enum"], "rub_assessment.method outside the enum")
    require(isinstance(signal["source_refs"], list) and signal["source_refs"] and all(isinstance(ref, str) and ref for ref in signal["source_refs"]), "source_refs must be a non-empty list of strings (AD-1)")
    key_pattern = properties["detection_data"]["propertyNames"]["pattern"]
    for key, entry in signal["detection_data"].items():
        require(re.fullmatch(key_pattern, key) is not None, f"detection_data key {key!r} violates the contract pattern")
        require(set(entry) == {"value", "is_unknown"}, f"detection_data.{key} must be {{value, is_unknown}}")
        require(isinstance(entry["is_unknown"], bool), f"detection_data.{key}.is_unknown must be boolean")
        require(entry["value"] is None or isinstance(entry["value"], (int, float, str, bool)), f"detection_data.{key}.value must be scalar")
        require((entry["value"] is None) == entry["is_unknown"], f"detection_data.{key}: is_unknown must match a null value")


def check_result(result: DetectionResult) -> None:
    schema = json.loads(read(SCHEMA))
    by_key = {(evaluation.level, evaluation.key): evaluation for evaluation in result.evaluations}
    # 1. SKU deviation against the SKU norm, money at risk = revenue norm - revenue of the day.
    sku = by_key[("sku", "1001")]
    require(sku.status == "ok" and sku.norm_orders == Decimal(10), "1001: the norm is the D21 median of 14 full days")
    require(sku.orders_deviation_pct == -50.0, f"1001: deviation must be -50.0, got {sku.orders_deviation_pct}")
    require(sku.money_at_risk == Decimal("500.00"), f"1001: money at risk must be 500.00, got {sku.money_at_risk}")
    subject = by_key[("subject", "Платье")]
    require(subject.norm_orders == Decimal(18) and subject.orders_deviation_pct == -33.3, "subject deviation is against the sum of its SKUs (AD-19)")
    # 2. Zero norm / short history: insufficient, no deviation, no NaN/Infinity.
    zero = by_key[("sku", "1002")]
    require(zero.status == "insufficient" and zero.orders_deviation_pct is None and zero.money_at_risk is None, "1002: a zero norm is insufficient with no deviation")
    short = by_key[("sku", "1005")]
    require(short.status == "insufficient" and short.sample_days == 9 and short.norm_orders is None, "1005: nine days are insufficient (< 14)")
    growth = by_key[("sku", "1003")]
    require(growth.status == "ok" and not growth.is_candidate, "1003: growth is evaluated but never a candidate")
    signals = list(result.signals)
    require([s["rub_assessment"]["value_rub"] for s in signals] == ["600.00", "500.00", "100.00"], f"signals must be ranked by money at risk: {[s['rub_assessment'] for s in signals]}")
    require({s["detection_data"]["nm_id"]["value"] for s in signals} == {None, 1001, 1004}, "only the two dropping SKUs and their subject are signals")
    text = json.dumps(signals, ensure_ascii=False, allow_nan=False)
    require("NaN" not in text and "Infinity" not in text, "payload must carry neither NaN nor Infinity")
    for signal in signals:
        check_signal_shape(signal, schema)
        require(signal["detection_data"]["threshold_pct"] == {"value": None, "is_unknown": True}, "no threshold is applied in Story 4.1 (decision 6a; Stories 4.2/4.4)")
        require(signal["detection_data"]["norm_window_days"]["value"] == 14, "the norm window is 14 days (D21)")
        require(any(ref.startswith("calc://scn001/") for ref in signal["source_refs"]), "source_refs must point at the calculation (AD-1)")
        require(any(ref.startswith("table://fact_nm_daily/") for ref in signal["source_refs"]), "source_refs must point at the fact versions (AD-1)")
        require(any(ref.startswith("artifact://business-signal/sha256/") for ref in signal["source_refs"]), "source_refs must carry the evidence hashes (AD-1)")
    require(len({s["snapshot_id"] for s in signals}) == 1, "all signals of one run share the input snapshot")
    again = run_detector()
    require(again.snapshot_id == result.snapshot_id and list(again.signals) == signals, "the detector must be deterministic on the same facts")
    # 3. No signals when the brief is not ok.
    ok_norms = [MetricNorm("orders", Decimal("38.00"), 14, 14, "ok"), MetricNorm("revenue", Decimal("3800.00"), 14, 14, "ok")]
    ok = with_signals(build_day(DAY, ok_norms, MetricActual(37, Decimal("3700.00")), STATUS, [RUN]), signals)
    require(ok.status == "ok" and len(ok.payload["signals"]) == 3, "an ok day carries the signals")
    insufficient_norms = [MetricNorm("orders", Decimal("38.00"), 14, 9, "insufficient"), MetricNorm("revenue", Decimal("3800.00"), 14, 9, "insufficient")]
    insufficient = build_day(DAY, insufficient_norms, MetricActual(37, Decimal("3700.00")), STATUS, [RUN])
    blocked = build_day(DAY, [], None, STATUS, [])
    for day in (insufficient, blocked):
        require(day.payload["signals"] == [], f"a {day.status} day starts with no signals")
        try:
            with_signals(day, signals)
        except ValueError:
            continue
        raise DetectorGateError(f"with_signals must refuse a {day.status} day (PRD FR-7)")


def check_wiring(brief_cli: Path = BRIEF_CLI, assembler: Path = ASSEMBLER, loader: Path = LOADER, makefile: Path = MAKEFILE, roundtrip: Path = ROUNDTRIP) -> None:
    cli = read(brief_cli)
    require(cli.count("run_detector_step(connection, tenant_id, brief_day") == 1, "brief/cli.py must run the detector step exactly once (AD-19)")
    before = cli[: cli.index("detection = run_detector_step(")].splitlines()
    while before and (not before[-1].strip() or before[-1].strip().startswith("#")):
        before.pop()
    require(before and before[-1].strip() == 'if day.status == "ok":', "brief/cli.py must guard the detector with `if day.status == \"ok\":` (PRD FR-7)")
    require("assembler.with_signals(day, detection.signals)" in cli, "brief/cli.py must attach signals through assembler.with_signals")
    require("set(detection.input_run_ids)" in cli, "brief/cli.py must add the detector's input runs to run_inputs (AD-3)")
    assembler_source = read(assembler)
    start = assembler_source.index("def with_signals(")
    body = assembler_source[start : assembler_source.index("\ndef ", start + 1)]
    require('if day.status != "ok":' in body and "raise ValueError" in body, "assembler.with_signals must refuse a day that is not ok")
    loader_source = read(loader)
    for view in ("fact_nm_daily_current", "dim_nm_subject_current", "fact_funnel_daily_current"):
        require(f"FROM {view}" in loader_source, f"detector/loader.py must read {view} (AD-19)")
    require("stg_wb" not in loader_source, "the detector never reads stg_* (AD-19)")
    require("INSERT" not in loader_source and "UPDATE" not in loader_source, "the detector loader is read-only; brief writes the payload (AD-9)")
    verify_line = next((line for line in read(makefile).splitlines() if line.startswith("verify:")), "")
    targets = verify_line.split()
    require("detector" in targets and "nm-daily" in targets and targets.index("detector") == targets.index("nm-daily") + 1, "Makefile: `detector` must follow `nm-daily` in the verify target")
    require("tests/detector/test_detector_db.py" in read(roundtrip), "pg_local_roundtrip.sh must run the detector db-tests (no silent skip)")
    read(DB_TEST)


def verify() -> dict[str, int]:
    result = run_detector()
    check_result(result)
    check_wiring()
    return result.counters()


def main() -> None:
    counters = verify()
    require(counters == {"sku_total": 5, "sku_insufficient": 2, "subject_total": 2, "subject_insufficient": 0, "signals": 3}, f"fixed-facts scenario drifted: {counters}")
    print(GATE_LINE)


if __name__ == "__main__":
    try:
        main()
    except (DetectorGateError, KeyError, ValueError, TypeError, OSError) as exc:
        print(f"detector gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
