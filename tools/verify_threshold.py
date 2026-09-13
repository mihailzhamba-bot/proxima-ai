"""Acceptance gate for Story 4.4 (standard library + control-plane package)."""

from __future__ import annotations

import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from proxima_control_plane.brief.assembler import build_day, with_signals
from proxima_control_plane.brief.builder import DataStatus, MetricActual, MetricNorm
from proxima_control_plane.detector.metrics import DailyMetrics, SubjectRow
from proxima_control_plane.detector.signals import detect
from proxima_control_plane.detector.threshold import load_alert_threshold

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
CONFIG = ROOT / "services/control-plane/src/proxima_control_plane/detector/threshold.toml"
WEB_COMPONENT = ROOT / "services/webapp/src/components/brief/anomalies.tsx"
GATE_LINE = "threshold: -31 signals, -29 silent, payload carries source"
DAY = date(2026, 8, 29)
RUN = "11111111-1111-4111-8111-111111111111"
SOURCE = "fixture retro-alarm labels"
DECIDED = "2026-09-09"


class ThresholdGateError(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ThresholdGateError(message)


def rows(nm_id: int, actual: int) -> list[DailyMetrics]:
    history = [
        DailyMetrics(nm_id, DAY - timedelta(days=offset), 100, Decimal("10000.00"), RUN, ("a" * 64,))
        for offset in range(14, 0, -1)
    ]
    return [*history, DailyMetrics(nm_id, DAY, actual, Decimal(actual * 100), RUN, ("a" * 64,))]


def verify() -> None:
    require(load_alert_threshold(CONFIG).payload() == {"value": -30, "source": "docs/exec-plans/active/loop-pilot.txt: план Mike 2026-09-13, порог пилота", "date": "2026-09-13"}, "packaged threshold must match the approved pilot decision")
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / "threshold.toml"
        config.write_text(
            f'[threshold]\nalert_threshold_pct = -30\nthreshold_source = "{SOURCE}"\nthreshold_date = {DECIDED}\n',
            encoding="utf-8",
        )
        threshold = load_alert_threshold(config)

    facts = [*rows(4401, 69), *rows(4402, 71)]
    subjects = {
        nm_id: SubjectRow(nm_id, f"fixture-subject-{nm_id}", f"ART-{nm_id}", "fixture-brand", RUN, "b" * 64)
        for nm_id in (4401, 4402)
    }
    result = detect("fixture-tenant-001", DAY, facts, subjects, {}, [], "2026-09-09T05:00:00+00:00", threshold)
    sku_ids = {
        signal["detection_data"]["nm_id"]["value"]
        for signal in result.signals
        if signal["detection_data"]["level"]["value"] == "sku"
    }
    require(4401 in sku_ids, "-31 percent must produce a signal")
    require(4402 not in sku_ids, "-29 percent must stay silent")

    status = DataStatus(DAY, "2026-09-09T04:59:00+00:00", False)
    norms = [MetricNorm("orders", Decimal(100), 14, 14, "ok"), MetricNorm("revenue", Decimal("10000.00"), 14, 14, "ok")]
    expected = {"value": -30, "source": SOURCE, "date": DECIDED}
    days = (
        with_signals(build_day(DAY, norms, MetricActual(69, Decimal("6900.00")), status, [RUN], threshold), result.signals),
        build_day(DAY, [MetricNorm("orders", Decimal(100), 14, 9, "insufficient"), MetricNorm("revenue", Decimal("10000.00"), 14, 9, "insufficient")], MetricActual(69, Decimal("6900.00")), status, [RUN], threshold),
        build_day(DAY, [], None, status, [], threshold),
    )
    require(all(day.payload["threshold"] == expected for day in days), "every brief status must carry value, source and date")

    makefile = MAKEFILE.read_text(encoding="utf-8")
    verify_line = next(line for line in makefile.splitlines() if line.startswith("verify:"))
    require("threshold" in verify_line.split(), "threshold target must be wired into make verify")
    component = WEB_COMPONENT.read_text(encoding="utf-8")
    require("summary.threshold" in component and "Порог тревоги не применяется" in component, "webapp caption must use payload threshold and preserve the unset text")


def main() -> None:
    verify()
    print(GATE_LINE)


if __name__ == "__main__":
    try:
        main()
    except (ThresholdGateError, KeyError, ValueError, TypeError, OSError) as exc:
        print(f"threshold gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
