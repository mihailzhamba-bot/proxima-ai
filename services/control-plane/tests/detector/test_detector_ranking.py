"""Story 4.2 на синтетике с пятью SKU и известными потерями (CAP-7, решение 6а, PRD FR-34, FR-7).

AC: `signals[]` отсортированы по `rub_assessment` по убыванию, большая потеря
выше при прочих равных; `brief.status` и правило показа цифр не меняются;
`signals[]` пусто при `status != ok`; рост показывается числом и в `signals[]`
не попадает; порог из конфигурации - `null` держит всех кандидатов, `-30`
отсекает меньшие падения, тройка записана в payload. Без БД и без сети.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin

import jsonschema
import pytest
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from proxima_control_plane.brief.assembler import build_day, with_signals
from proxima_control_plane.brief.builder import DataStatus, MetricActual, MetricNorm
from proxima_control_plane.detector.metrics import DailyMetrics, SubjectRow
from proxima_control_plane.detector.signals import DetectionResult, detect, rank
from proxima_control_plane.detector.threshold import NOT_APPLIED, AlertThreshold

ROOT = Path(__file__).resolve().parents[4]
DAY = date(2026, 8, 29)
TENANT = "fixture-tenant-001"
RUN = "11111111-1111-4111-8111-111111111111"
EVIDENCE = ("a" * 64, "b" * 64)
CREATED_AT = "2026-08-30T02:45:00+00:00"
STATUS = DataStatus(DAY, "2026-08-30T02:41:12+00:00", False)
MINUS_30 = AlertThreshold(Decimal(-30), "DECISIONS.md D25 decision 6a: retro run of 184 fixture days", date(2026, 9, 2))
NULL_TRIPLE = {"value": None, "source": None, "date": None}

# nm_id -> (заказы окна, заказы дня, выручка окна, выручка дня, предмет). Потери известны заранее:
#   2001: 10 -> 5, 1000 -> 500      : -50 % / -50 %,   500.00   (Платье)
#   2002: 20 -> 12, 2000 -> 1200    : -40 % / -40 %,   800.00   (Платье)
#   2003: 8 -> 7,   800 -> 900      : -12.5 % / +12.5 %, -100.00 (Юбка; заказы упали, выручка выросла)
#   2004: 20 -> 15, 2000 -> 1500    : -25 % / -25 %,   500.00   (Юбка; те же деньги, что у 2001)
#   2005: 20 -> 25, 2000 -> 2500    : +25 % / +25 %,  -500.00   (Юбка; рост - не кандидат)
#   Платье = 2001 + 2002: 30 -> 17 (-43.3 %), 3000 -> 1700: 1300.00
#   Юбка = 2003 + 2004 + 2005: 48 -> 47 (-2.1 %), 4800 -> 4900 (+2.1 %): -100.00 (те же деньги, что у 2003)
SKUS = {
    2001: (10, 5, "1000.00", "500.00", "Платье"),
    2002: (20, 12, "2000.00", "1200.00", "Платье"),
    2003: (8, 7, "800.00", "900.00", "Юбка"),
    2004: (20, 15, "2000.00", "1500.00", "Юбка"),
    2005: (20, 25, "2000.00", "2500.00", "Юбка"),
}
# Кабинетный ряд = сумма SKU: окно 78 / 7800.00, день 64 / 6600.00 -> -17.9 % / -15.4 %.
CABINET_NORMS = [MetricNorm("orders", Decimal("78.00"), 14, 14, "ok"), MetricNorm("revenue", Decimal("7800.00"), 14, 14, "ok")]
CABINET_ACTUAL = MetricActual(64, Decimal("6600.00"))
EXPECTED_UNFILTERED = ["1300.00", "800.00", "500.00", "500.00", "-100.00", "-100.00"]
EXPECTED_MINUS_30 = ["1300.00", "800.00", "500.00"]


def rows(nm_id: int, window_orders: int, actual_orders: int, window_revenue: str, actual_revenue: str) -> list[DailyMetrics]:
    series = [DailyMetrics(nm_id, DAY - timedelta(days=offset), window_orders, Decimal(window_revenue), RUN, EVIDENCE) for offset in range(14, 0, -1)]
    series.append(DailyMetrics(nm_id, DAY, actual_orders, Decimal(actual_revenue), RUN, EVIDENCE))
    return series


def scenario() -> tuple[list[DailyMetrics], dict[int, SubjectRow]]:
    facts = [row for nm_id, (wo, ao, wr, ar, _) in SKUS.items() for row in rows(nm_id, wo, ao, wr, ar)]
    subjects = {nm_id: SubjectRow(nm_id, name, f"ART-{nm_id}", "fixture-brand", RUN, "c" * 64) for nm_id, (*_, name) in SKUS.items()}
    return facts, subjects


def run(threshold: AlertThreshold = NOT_APPLIED) -> DetectionResult:
    facts, subjects = scenario()
    return detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT, threshold=threshold)


def label(signal: dict) -> str:
    data = signal["detection_data"]
    return str(data["nm_id"]["value"]) if data["level"]["value"] == "sku" else data["subject_name"]["value"]


def money(result: DetectionResult) -> list[str]:
    return [s["rub_assessment"]["value_rub"] for s in result.signals]


def ok_day(threshold: AlertThreshold = NOT_APPLIED):
    return build_day(DAY, CABINET_NORMS, CABINET_ACTUAL, STATUS, [RUN], threshold=threshold)


def validator(name: str) -> jsonschema.Draft202012Validator:
    schemas = [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in sorted((ROOT / "contracts").glob("*.schema.json"))]
    bases = [schema["$id"] for _, schema in schemas]
    resources = []
    for file_name, schema in schemas:
        for key in (schema["$id"], *(urljoin(base, file_name) for base in bases)):
            resources.append((key, DRAFT202012.create_resource(schema)))
    schema = json.loads((ROOT / "contracts" / f"{name}.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, registry=Registry().with_resources(resources), format_checker=jsonschema.FormatChecker())


def test_signals_are_sorted_by_rub_assessment_descending() -> None:
    result = run()
    assert money(result) == EXPECTED_UNFILTERED
    assert [label(s) for s in result.signals] == ["Платье", "2002", "2001", "2004", "2003", "Юбка"]
    values = [Decimal(value) for value in money(result)]
    assert values == sorted(values, reverse=True)  # большая потеря первой (CAP-7)


def test_ties_in_money_are_broken_deterministically() -> None:
    result = run()
    by_label = {label(s): s for s in result.signals}
    # 2001 и 2004 - по 500.00: глубже падение (-50 % против -25 %) выше.
    assert by_label["2001"]["rub_assessment"] == by_label["2004"]["rub_assessment"]
    assert [label(s) for s in result.signals].index("2001") < [label(s) for s in result.signals].index("2004")
    # 2003 и Юбка - по -100.00: -12.5 % глубже -2.1 %, и SKU раньше предмета.
    assert by_label["2003"]["rub_assessment"] == by_label["Юбка"]["rub_assessment"]
    assert [label(s) for s in result.signals].index("2003") < [label(s) for s in result.signals].index("Юбка")
    shuffled = list(result.signals)
    random.Random(42).shuffle(shuffled)
    assert rank(shuffled) == list(result.signals)
    assert run().signals == result.signals  # тот же вход - тот же порядок


def test_growth_is_shown_as_a_number_and_never_enters_signals() -> None:
    result = run()
    growth = next(e for e in result.evaluations if e.key == "2005")
    assert growth.status == "ok" and growth.is_candidate is False
    assert growth.orders_deviation_pct == 25.0 and growth.revenue_deviation_pct == 25.0
    assert "2005" not in {label(s) for s in result.signals}
    # Рост одной метрики внутри кандидата - число со знаком в detection_data, порог односторонний (PRD FR-34).
    partial = next(s for s in result.signals if label(s) == "2003")
    assert partial["detection_data"]["orders_deviation_pct"] == {"value": -12.5, "is_unknown": False}
    assert partial["detection_data"]["revenue_deviation_pct"] == {"value": 12.5, "is_unknown": False}
    assert partial["detection_data"]["triggered_by"] == {"value": ["orders"], "is_unknown": False}
    assert partial["rub_assessment"] == {"value_rub": "-100.00", "method": "revenue"}


def test_brief_status_and_the_numbers_rule_are_unchanged_and_signals_are_empty_when_not_ok() -> None:
    result = run()
    bare = ok_day()
    day = with_signals(bare, result.signals)
    assert day.status == "ok" == bare.status
    assert day.payload["deviation_pct"] == {"orders": -17.9, "revenue": -15.4} == bare.payload["deviation_pct"]
    assert day.payload["actual"] == bare.payload["actual"] and day.payload["norm"] == bare.payload["norm"]
    assert {key: value for key, value in day.payload.items() if key != "signals"} == {key: value for key, value in bare.payload.items() if key != "signals"}
    assert len(day.payload["signals"]) == 6
    validator("brief").validate(day.payload)
    insufficient = build_day(
        DAY,
        [MetricNorm("orders", Decimal("78.00"), 14, 9, "insufficient"), MetricNorm("revenue", Decimal("7800.00"), 14, 9, "insufficient")],
        CABINET_ACTUAL,
        STATUS,
        [RUN],
    )
    blocked = build_day(DAY, [], None, STATUS, [])
    for other in (insufficient, blocked):
        assert other.payload["signals"] == []
        validator("brief").validate(other.payload)
        with pytest.raises(ValueError, match="only for an ok day"):
            with_signals(other, result.signals)


def test_threshold_null_keeps_every_candidate_and_minus_30_drops_the_smaller_deviations() -> None:
    unfiltered = run()
    assert unfiltered.suppressed_by_threshold == 0
    assert money(unfiltered) == EXPECTED_UNFILTERED
    day = with_signals(ok_day(), unfiltered.signals)
    assert day.payload["threshold"] == NULL_TRIPLE
    for signal in unfiltered.signals:
        assert signal["detection_data"]["threshold_pct"] == {"value": None, "is_unknown": True}
        validator("signal").validate(signal)

    filtered = run(MINUS_30)
    assert money(filtered) == EXPECTED_MINUS_30
    assert [label(s) for s in filtered.signals] == ["Платье", "2002", "2001"]  # -43.3 %, -40 %, -50 % проходят
    assert filtered.suppressed_by_threshold == 3  # 2004 (-25 %), 2003 (-12.5 %), Юбка (-2.1 %) - в пределах шума
    assert [s["signal_id"] for s in filtered.signals] == [s["signal_id"] for s in unfiltered.signals][:3]  # правило порядка то же
    day = with_signals(ok_day(MINUS_30), filtered.signals)
    assert day.payload["threshold"] == {"value": -30, "source": MINUS_30.threshold_source, "date": "2026-09-02"}
    assert day.payload["deviation_pct"] == {"orders": -17.9, "revenue": -15.4}  # цифры сводки от порога не зависят
    validator("brief").validate(day.payload)
    for signal in filtered.signals:
        assert signal["detection_data"]["threshold_pct"] == {"value": -30, "is_unknown": False}
        assert signal["detection_data"]["threshold_source"] == {"value": MINUS_30.threshold_source, "is_unknown": False}
        assert signal["detection_data"]["threshold_date"] == {"value": "2026-09-02", "is_unknown": False}
        validator("signal").validate(signal)


def test_story_4_4_boundary_minus_31_alerts_minus_29_stays_silent_minus_30_alerts() -> None:
    facts = [
        *rows(2101, 100, 69, "10000.00", "6900.00"),  # -31.0 %
        *rows(2102, 100, 71, "10000.00", "7100.00"),  # -29.0 %
        *rows(2103, 100, 70, "10000.00", "7000.00"),  # -30.0 % - ровно порог
    ]
    subjects = {nm_id: SubjectRow(nm_id, f"subject-{nm_id}", f"ART-{nm_id}", "fixture-brand", RUN, "c" * 64) for nm_id in (2101, 2102, 2103)}
    result = detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT, threshold=MINUS_30)
    skus = {label(s) for s in result.signals if s["detection_data"]["level"]["value"] == "sku"}
    assert skus == {"2101", "2103"}
    unfiltered = detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT)
    assert {label(s) for s in unfiltered.signals if s["detection_data"]["level"]["value"] == "sku"} == {"2101", "2102", "2103"}
