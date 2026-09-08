"""Юнит-тесты детектора на фиксированных фактах (Story 4.1, D21, D27, AD-10, AD-19).

Чистые функции без БД: норма SKU и категории, `insufficient` при нулевой норме,
короткой истории и отсутствии версии дня, сигналы по `signal.schema.json` v1,
порядок по деньгам, детерминизм снимка входа, отказ сводки не `ok`.
"""

from __future__ import annotations

import json
import math
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
from proxima_control_plane.detector.decomposition import decompose
from proxima_control_plane.detector.evaluate import (
    LEVEL_SKU,
    LEVEL_SUBJECT,
    REASON_NO_DAY,
    REASON_SHORT_WINDOW,
    REASON_ZERO_NORM,
    evaluate_all,
)
from proxima_control_plane.detector.funnel import FUNNEL_MIN_DAYS
from proxima_control_plane.detector.metrics import DailyMetrics, FunnelMetrics, SubjectRow, to_decimal
from proxima_control_plane.detector.signals import DetectionResult, detect

ROOT = Path(__file__).resolve().parents[4]
DAY = date(2026, 8, 29)
TENANT = "fixture-tenant-001"
RUN = "11111111-1111-4111-8111-111111111111"
EVIDENCE = ("a" * 64, "b" * 64)
DICTIONARY_EVIDENCE = "c" * 64
CREATED_AT = "2026-08-30T02:45:00+00:00"
STATUS = DataStatus(DAY, "2026-08-30T02:41:12+00:00", False)


def rows(
    nm_id: int,
    window_orders: int,
    actual_orders: int | None,
    window_revenue: str,
    actual_revenue: str,
    days: int = 14,
    run_id: str = RUN,
) -> list[DailyMetrics]:
    """Ряд SKU: `days` одинаковых дней перед DAY и (если задан) сам DAY."""
    series = [
        DailyMetrics(nm_id, DAY - timedelta(days=offset), window_orders, Decimal(window_revenue), run_id, EVIDENCE)
        for offset in range(days, 0, -1)
    ]
    if actual_orders is not None:
        series.append(DailyMetrics(nm_id, DAY, actual_orders, Decimal(actual_revenue), run_id, EVIDENCE))
    return series


def subject(nm_id: int, name: str) -> SubjectRow:
    return SubjectRow(nm_id, name, f"ART-{nm_id}", "fixture-brand", RUN, DICTIONARY_EVIDENCE)


def scenario() -> tuple[list[DailyMetrics], dict[int, SubjectRow]]:
    """Пять SKU в двух предметах: падение, нулевая норма, рост, малое падение, короткая история."""
    facts = [
        *rows(1001, 10, 5, "1000.00", "500.00"),
        *rows(1002, 0, 0, "0.00", "0.00"),
        *rows(1003, 20, 25, "2000.00", "2500.00"),
        *rows(1004, 8, 7, "800.00", "700.00"),
        *rows(1005, 3, 1, "300.00", "100.00", days=9),
    ]
    subjects = {
        1001: subject(1001, "Платье"),
        1002: subject(1002, "Платье"),
        1003: subject(1003, "Юбка"),
        1004: subject(1004, "Платье"),
        1005: subject(1005, "Юбка"),
    }
    return facts, subjects


def run(facts: list[DailyMetrics], subjects: dict[int, SubjectRow], history: dict[int, int] | None = None, funnel: list[FunnelMetrics] | None = None) -> DetectionResult:
    return detect(TENANT, DAY, facts, subjects, history or {}, funnel or [], CREATED_AT)


def evaluations_by_key(result: DetectionResult) -> dict[tuple[str, str], object]:
    return {(evaluation.level, evaluation.key): evaluation for evaluation in result.evaluations}


def registry() -> Registry:
    """Как `tools/verify_contracts.py`: схема доступна по `$id` и по URL, в который
    разворачивается соседняя ссылка `signal.schema.json` из `brief`."""
    schemas = [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in sorted((ROOT / "contracts").glob("*.schema.json"))]
    bases = [schema["$id"] for _, schema in schemas]
    resources = []
    for file_name, schema in schemas:
        for key in (schema["$id"], *(urljoin(base, file_name) for base in bases)):
            resources.append((key, DRAFT202012.create_resource(schema)))
    return Registry().with_resources(resources)


def validator(name: str) -> jsonschema.Draft202012Validator:
    schema = json.loads((ROOT / "contracts" / f"{name}.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, registry=registry(), format_checker=jsonschema.FormatChecker())


def ok_day():
    norms = [MetricNorm("orders", Decimal("38.00"), 14, 14, "ok"), MetricNorm("revenue", Decimal("3800.00"), 14, 14, "ok")]
    return build_day(DAY, norms, MetricActual(37, Decimal("3700.00")), STATUS, [RUN])


def test_signals_validate_against_the_signal_and_brief_contracts() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    assert len(result.signals) == 3
    signal_validator = validator("signal")
    for signal in result.signals:
        signal_validator.validate(signal)
    day = with_signals(ok_day(), result.signals)
    validator("brief").validate(day.payload)
    assert day.status == "ok"
    assert len(day.payload["signals"]) == 3


def test_sku_deviation_is_against_the_sku_norm_and_money_is_norm_minus_actual() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    sku = evaluations_by_key(result)[(LEVEL_SKU, "1001")]
    assert sku.status == "ok"
    assert sku.norm_orders == Decimal(10)
    assert sku.orders_deviation_pct == -50.0
    assert sku.money_at_risk == Decimal("500.00")
    signal = next(s for s in result.signals if s["signal_id"] == f"scn001-{DAY.isoformat()}-sku-1001")
    data = signal["detection_data"]
    assert signal["rub_assessment"] == {"value_rub": "500.00", "method": "revenue"}
    assert signal["scenario_code"] == "SCN-001"
    assert signal["trust_marking"] == "unreleased"
    assert data["nm_id"] == {"value": 1001, "is_unknown": False}
    assert data["supplier_article"] == {"value": "ART-1001", "is_unknown": False}
    assert data["subject_name"] == {"value": "Платье", "is_unknown": False}
    assert data["orders_norm_median"] == {"value": "10.00", "is_unknown": False}
    assert data["orders_actual"] == {"value": 5, "is_unknown": False}
    assert data["revenue_norm_median"] == {"value": "1000.00", "is_unknown": False}
    assert data["revenue_actual"] == {"value": "500.00", "is_unknown": False}
    assert data["norm_window_days"] == {"value": 14, "is_unknown": False}
    assert data["norm_sample_days"] == {"value": 14, "is_unknown": False}
    assert data["threshold_pct"] == {"value": None, "is_unknown": True}  # порог - Story 4.2/4.4


def test_zero_norm_is_insufficient_and_yields_neither_signal_nor_nan() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    zero = evaluations_by_key(result)[(LEVEL_SKU, "1002")]
    assert zero.status == "insufficient"
    assert zero.reason == REASON_ZERO_NORM
    assert zero.sample_days == 14
    assert zero.orders_deviation_pct is None and zero.money_at_risk is None
    assert not any(s["detection_data"]["nm_id"]["value"] == 1002 for s in result.signals)
    text = json.dumps(list(result.signals), ensure_ascii=False, allow_nan=False)
    assert "NaN" not in text and "Infinity" not in text
    for signal in result.signals:
        for entry in signal["detection_data"].values():
            if isinstance(entry["value"], float):
                assert math.isfinite(entry["value"])


def test_short_history_is_insufficient_without_a_deviation() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    short = evaluations_by_key(result)[(LEVEL_SKU, "1005")]
    assert short.status == "insufficient"
    assert short.reason == REASON_SHORT_WINDOW
    assert short.sample_days == 9
    assert short.norm_orders is None and short.orders_deviation_pct is None
    assert not any(s["detection_data"]["nm_id"]["value"] == 1005 for s in result.signals)


def test_missing_evaluation_day_is_insufficient_not_a_synthetic_minus_100() -> None:
    facts = rows(2001, 10, None, "1000.00", "0.00")
    result = run(facts, {2001: subject(2001, "Платье")})
    sku = evaluations_by_key(result)[(LEVEL_SKU, "2001")]
    assert sku.status == "insufficient"
    assert sku.reason == REASON_NO_DAY
    assert sku.orders_deviation_pct is None
    assert result.signals == ()


def test_growth_is_evaluated_but_never_a_candidate() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    growth = evaluations_by_key(result)[(LEVEL_SKU, "1003")]
    assert growth.status == "ok"
    assert growth.orders_deviation_pct == 25.0
    assert growth.money_at_risk == Decimal("-500.00")
    assert growth.is_candidate is False
    assert not any(s["detection_data"]["nm_id"]["value"] == 1003 for s in result.signals)


def test_subject_deviation_is_against_the_sum_of_its_skus() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    dress = evaluations_by_key(result)[(LEVEL_SUBJECT, "Платье")]
    # Платье = 1001 + 1002 + 1004: окно 10+0+8 = 18, день 5+0+7 = 12 -> -33.3 %.
    assert dress.nm_ids == (1001, 1002, 1004)
    assert dress.norm_orders == Decimal(18)
    assert dress.actual_orders == Decimal(12)
    assert dress.orders_deviation_pct == -33.3
    assert dress.money_at_risk == Decimal("600.00")
    skirt = evaluations_by_key(result)[(LEVEL_SUBJECT, "Юбка")]
    # Юбка = 1003 + 1005: 1005 даёт только 9 дней, но дни окна есть у 1003 - 14/14.
    assert skirt.sample_days == 14
    assert skirt.is_candidate is False
    signal = next(s for s in result.signals if s["detection_data"]["level"]["value"] == LEVEL_SUBJECT)
    assert signal["detection_data"]["sku_count"] == {"value": 3, "is_unknown": False}
    assert signal["detection_data"]["nm_id"] == {"value": None, "is_unknown": True}
    refs = "\n".join(signal["source_refs"])
    for nm_id in (1001, 1002, 1004):
        assert f"table://fact_nm_daily/nm/{nm_id}/run/{RUN}" in refs
        assert f"table://dim_nm_subject/nm/{nm_id}/run/{RUN}" in refs


def test_signals_are_ranked_by_money_at_risk_descending() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    assert [s["rub_assessment"]["value_rub"] for s in result.signals] == ["600.00", "500.00", "100.00"]
    assert [s["detection_data"]["level"]["value"] for s in result.signals] == ["subject", "sku", "sku"]


def test_source_refs_point_at_fact_versions_evidence_dictionary_and_calculation() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    signal = next(s for s in result.signals if s["detection_data"]["nm_id"]["value"] == 1001)
    refs = signal["source_refs"]
    assert f"table://fact_nm_daily/nm/1001/run/{RUN}" in refs
    assert f"table://dim_nm_subject/nm/1001/run/{RUN}" in refs
    assert f"artifact://business-signal/sha256/{'a' * 64}" in refs
    assert f"artifact://business-signal/sha256/{DICTIONARY_EVIDENCE}" in refs
    assert f"calc://scn001/norm-median-14d/v1/snapshot/{result.snapshot_id}" in refs
    assert refs == sorted(refs) and len(refs) == len(set(refs))
    assert result.input_run_ids == (RUN,)


def test_no_signals_when_the_brief_is_not_ok() -> None:
    facts, subjects = scenario()
    result = run(facts, subjects)
    insufficient = build_day(
        DAY,
        [MetricNorm("orders", Decimal("38.00"), 14, 9, "insufficient"), MetricNorm("revenue", Decimal("3800.00"), 14, 9, "insufficient")],
        MetricActual(37, Decimal("3700.00")),
        STATUS,
        [RUN],
    )
    blocked = build_day(DAY, [], None, STATUS, [])
    for day in (insufficient, blocked):
        assert day.payload["signals"] == []
        with pytest.raises(ValueError, match="only for an ok day"):
            with_signals(day, result.signals)


def test_same_facts_give_the_same_signals_and_snapshot_and_a_changed_fact_a_new_snapshot() -> None:
    facts, subjects = scenario()
    first = run(facts, subjects)
    second = run(list(reversed(facts)), dict(reversed(list(subjects.items()))))
    assert first.snapshot_id == second.snapshot_id
    assert first.signals == second.signals
    assert len({s["snapshot_id"] for s in first.signals}) == 1
    changed = [
        DailyMetrics(row.nm_id, row.calendar_day, row.orders + 1, row.revenue_rub, row.run_id, row.evidence_sha256)
        if row.nm_id == 1004 and row.calendar_day == DAY
        else row
        for row in facts
    ]
    third = run(changed, subjects)
    assert third.snapshot_id != first.snapshot_id


def test_rounding_follows_d27_half_up_once_at_the_last_step() -> None:
    # Выручка окна: семь дней 100.00 и семь 100.01 -> медиана 100.005 (среднее двух средних).
    facts = [
        DailyMetrics(3001, DAY - timedelta(days=offset), 3, Decimal("100.00") if offset % 2 else Decimal("100.01"), RUN, EVIDENCE)
        for offset in range(14, 0, -1)
    ]
    facts.append(DailyMetrics(3001, DAY, 1, Decimal("50.00"), RUN, EVIDENCE))
    result = run(facts, {3001: subject(3001, "Платье")})
    sku = evaluations_by_key(result)[(LEVEL_SKU, "3001")]
    assert sku.norm_revenue == Decimal("100.005")  # промежуточное - полная точность
    assert sku.money_at_risk == Decimal("50.01")  # 100.005 - 50.00 = 50.005 -> половина вверх
    assert sku.orders_deviation_pct == -66.7  # (1 - 3) / 3 = -66.666... -> один раз до 0.1
    signal = result.signals[0]
    assert signal["rub_assessment"]["value_rub"] == "50.01"
    assert signal["detection_data"]["revenue_norm_median"]["value"] == "100.01"
    assert signal["detection_data"]["revenue_deviation_pct"]["value"] == -50.0


def test_adapter_means_are_reported_but_the_norm_stays_the_median() -> None:
    # Тринадцать дней по 10 и один выброс 100: медиана 10, среднее за 14 дней 16.43.
    facts = [DailyMetrics(4001, DAY - timedelta(days=offset), 100 if offset == 7 else 10, Decimal("1000.00"), RUN, EVIDENCE) for offset in range(14, 0, -1)]
    facts.append(DailyMetrics(4001, DAY, 6, Decimal("600.00"), RUN, EVIDENCE))
    result = run(facts, {4001: subject(4001, "Платье")})
    sku = evaluations_by_key(result)[(LEVEL_SKU, "4001")]
    assert sku.norm_orders == Decimal(10)
    assert sku.orders_deviation_pct == -40.0
    data = result.signals[0]["detection_data"]
    assert data["orders_mean_7d"]["value"] == "22.86"
    assert data["orders_mean_14d"]["value"] == "16.43"
    assert data["orders_mean_28d"]["value"] == "16.43"
    assert data["history_days_28d"]["value"] == 14
    assert data["norm_rule"]["value"].startswith("D21 median")


def funnel_rows(nm_id: int, window_orders: int, actual_orders: int) -> list[FunnelMetrics]:
    series = [
        FunnelMetrics(nm_id, DAY - timedelta(days=offset), 100, window_orders, Decimal(window_orders * 100), RUN, "d" * 64)
        for offset in range(14, 0, -1)
    ]
    series.append(FunnelMetrics(nm_id, DAY, 100, actual_orders, Decimal(actual_orders * 100), RUN, "d" * 64))
    return series


def test_funnel_stage_is_unknown_below_eight_weeks_and_named_from_eight() -> None:
    facts = rows(1001, 10, 5, "1000.00", "500.00")
    subjects = {1001: subject(1001, "Платье")}
    short = run(facts, subjects, {1001: FUNNEL_MIN_DAYS - 1}, funnel_rows(1001, 10, 5))
    data = short.signals[0]["detection_data"]
    assert data["funnel_weeks"] == {"value": 7, "is_unknown": False}
    assert data["funnel_stage"] == {"value": None, "is_unknown": True}
    assert "funnel_loss_cvr_rub" not in data
    long = run(facts, subjects, {1001: FUNNEL_MIN_DAYS}, funnel_rows(1001, 10, 5))
    data = long.signals[0]["detection_data"]
    assert data["funnel_weeks"] == {"value": 8, "is_unknown": False}
    # Открытия и средний чек не менялись - вся потеря на конверсии.
    assert data["funnel_stage"] == {"value": "cvr", "is_unknown": False}
    assert data["funnel_loss_cvr_rub"] == {"value": "500.00", "is_unknown": False}
    assert data["funnel_loss_u_rub"] == {"value": "0.00", "is_unknown": False}
    assert f"table://fact_funnel_daily/nm/1001/run/{RUN}" in long.signals[0]["source_refs"]
    validator("signal").validate(long.signals[0])
    without_rows = run(facts, subjects, {1001: FUNNEL_MIN_DAYS}, [])
    assert without_rows.signals[0]["detection_data"]["funnel_stage"] == {"value": None, "is_unknown": True}


def test_to_decimal_rejects_float_bool_none_and_non_finite() -> None:
    assert to_decimal(5) == Decimal(5)
    assert to_decimal("12.50") == Decimal("12.50")
    for bad in (1.5, True, None):
        with pytest.raises(TypeError):
            to_decimal(bad)
    for bad in ("NaN", "Infinity", "-Infinity", "abc"):
        with pytest.raises(ValueError):
            to_decimal(bad)
    with pytest.raises(TypeError):
        DailyMetrics(1, DAY, 1.0, Decimal(1), RUN, EVIDENCE)


def test_shapley_contributions_add_up_to_the_revenue_delta() -> None:
    contributions = decompose(Decimal(100), Decimal("0.10"), Decimal(100), Decimal(80), Decimal("0.05"), Decimal(120))
    assert contributions.total() == Decimal(80) * Decimal("0.05") * Decimal(120) - Decimal(100) * Decimal("0.10") * Decimal(100)
    assert contributions.dominant() == "aov"  # только средний чек вырос - он и есть единственный положительный вклад
    loss = decompose(Decimal(80), Decimal("0.05"), Decimal(120), Decimal(100), Decimal("0.10"), Decimal(100))
    assert loss.dominant() == "cvr"


def test_a_fact_row_without_a_dictionary_row_is_refused() -> None:
    facts = rows(5001, 10, 5, "1000.00", "500.00")
    with pytest.raises(ValueError, match="dim_nm_subject_current has no row"):
        evaluate_all(facts, {}, DAY)
