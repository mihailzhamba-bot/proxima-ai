"""AC-preserved gate script for Story 2.4.

Acceptance criterion (epics.md, Story 2.4): `make verify` must show
`brief: payload valid, orders -21.7%` green. The skeleton below (found in the
repo, untouched, gate step missing) is kept verbatim by this script.

Pure check only: it imports the builder, not the database. The db-side
behavior (RLS, statuses, run_inputs) is covered by
services/control-plane/tests/brief/test_brief_db.py inside pg-roundtrip.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import jsonschema
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from proxima_control_plane.brief.builder import DataStatus, MetricNorm
from proxima_control_plane.brief.assembler import day_from_rows

ROOT = Path(__file__).resolve().parents[1]

# == START GATE SKELETON (do not remove; make verify greps this line) ==
def main() -> None:
    day = build_synthetic_day()
    payload = day.payload
    schema = load_schema()
    jsonschema.Draft202012Validator(schema, registry=load_registry()).validate(payload)
    assert payload["deviation_pct"]["orders"] == -21.7, payload["deviation_pct"]
    assert payload["deviation_pct"]["revenue"] == 18.9, payload["deviation_pct"]
    assert payload["signals"] == []
    assert payload["source_refs"]
    assert payload["data_status"]["stale"] is False
    assert day.status == "ok"
    assert "status" not in payload  # status lives in the brief_daily column, not in the contract payload
    print(f"brief: payload valid, orders {payload['deviation_pct']['orders']}%")
# == END GATE SKELETON (do not remove; make verify greps this line) ==


def build_synthetic_day():
    """Synthetic scenario of the AC: yesterday 27 orders / 41,141 RUB against a
    norm of 34.5 / 34,595 (expected deviations -21.7% / +18.9%, D27 rounding)."""
    return day_from_rows(
        date(2026, 8, 29),
        27,
        Decimal("41141.00"),
        [
            MetricNorm("orders", Decimal("34.50"), 14, 14, "ok"),
            MetricNorm("revenue", Decimal("34595.00"), 14, 14, "ok"),
        ],
        DataStatus(date(2026, 8, 29), "2026-08-30T02:41:12+00:00", False),
        fact_run_ids=["a1b2c3d4"],
    )


def load_registry() -> Registry:
    schemas = sorted((ROOT / "contracts").glob("*.schema.json"))
    resources = []
    for path in schemas:
        schema = json.loads(path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], DRAFT202012.create_resource(schema)))
    return Registry().with_resources(resources)


def load_schema() -> dict:
    return json.loads((ROOT / "contracts" / "brief.schema.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, jsonschema.ValidationError) as exc:
        print(f"brief gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
