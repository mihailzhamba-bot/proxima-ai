"""Порог тревоги как значение конфигурации (решение 6а, D25; PRD FR-34; Story 4.2).

Чтение TOML, правила тройки «значение + источник + дата», правило прохождения
порога и его след в `brief_daily.payload.threshold`, `detection_data` и снимке
входа. Без БД и без сети.
"""

from __future__ import annotations

import json
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
from proxima_control_plane.detector.signals import detect
from proxima_control_plane.detector.threshold import (
    CONFIG_FILE_ENV,
    DEFAULT_CONFIG_PATH,
    NOT_APPLIED,
    AlertThreshold,
    load_alert_threshold,
    parse_alert_threshold,
    resolve_config_path,
)

ROOT = Path(__file__).resolve().parents[4]
DAY = date(2026, 8, 29)
TENANT = "fixture-tenant-001"
RUN = "11111111-1111-4111-8111-111111111111"
EVIDENCE = ("a" * 64,)
CREATED_AT = "2026-08-30T02:45:00+00:00"
STATUS = DataStatus(DAY, "2026-08-30T02:41:12+00:00", False)
SOURCE = "DECISIONS.md D25 decision 6a: retro run of 184 fixture days"
DECIDED = date(2026, 9, 2)
MINUS_30 = AlertThreshold(Decimal(-30), SOURCE, DECIDED)


def write_toml(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "threshold.toml"
    path.write_text(body, encoding="utf-8")
    return path


def rows(nm_id: int, window_orders: int, actual_orders: int, window_revenue: str, actual_revenue: str) -> list[DailyMetrics]:
    series = [DailyMetrics(nm_id, DAY - timedelta(days=offset), window_orders, Decimal(window_revenue), RUN, EVIDENCE) for offset in range(14, 0, -1)]
    series.append(DailyMetrics(nm_id, DAY, actual_orders, Decimal(actual_revenue), RUN, EVIDENCE))
    return series


def subject(nm_id: int, name: str) -> SubjectRow:
    return SubjectRow(nm_id, name, f"ART-{nm_id}", "fixture-brand", RUN, "c" * 64)


def ok_day(threshold: AlertThreshold = NOT_APPLIED):
    norms = [MetricNorm("orders", Decimal("38.00"), 14, 14, "ok"), MetricNorm("revenue", Decimal("3800.00"), 14, 14, "ok")]
    return build_day(DAY, norms, MetricActual(37, Decimal("3700.00")), STATUS, [RUN], threshold=threshold)


def brief_validator() -> jsonschema.Draft202012Validator:
    schemas = [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in sorted((ROOT / "contracts").glob("*.schema.json"))]
    bases = [schema["$id"] for _, schema in schemas]
    resources = []
    for file_name, schema in schemas:
        for key in (schema["$id"], *(urljoin(base, file_name) for base in bases)):
            resources.append((key, DRAFT202012.create_resource(schema)))
    schema = json.loads((ROOT / "contracts" / "brief.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema, registry=Registry().with_resources(resources), format_checker=jsonschema.FormatChecker())


# --- конфигурация -------------------------------------------------------------


def test_packaged_config_loads_and_is_consistent() -> None:
    assert DEFAULT_CONFIG_PATH.is_file()
    loaded = load_alert_threshold()
    # Значение задаёт Story 4.4; здесь проверяется только форма: либо всё, либо ничего.
    assert loaded.applied == (loaded.threshold_source is not None) == (loaded.threshold_date is not None)


def test_empty_table_means_threshold_not_applied(tmp_path: Path) -> None:
    loaded = load_alert_threshold(write_toml(tmp_path, "[threshold]\n"))
    assert loaded == NOT_APPLIED
    assert loaded.applied is False
    assert loaded.payload() == {"value": None, "source": None, "date": None}
    assert loaded.detection_data() == {
        "threshold_pct": {"value": None, "is_unknown": True},
        "threshold_source": {"value": None, "is_unknown": True},
        "threshold_date": {"value": None, "is_unknown": True},
    }


def test_full_triple_is_read_with_decimal_value_and_toml_date(tmp_path: Path) -> None:
    body = f'[threshold]\nalert_threshold_pct = -30\nthreshold_source = "{SOURCE}"\nthreshold_date = 2026-09-02\n'
    loaded = load_alert_threshold(write_toml(tmp_path, body))
    assert loaded == MINUS_30
    assert isinstance(loaded.alert_threshold_pct, Decimal)
    assert loaded.payload() == {"value": -30, "source": SOURCE, "date": "2026-09-02"}
    assert loaded.detection_data()["threshold_pct"] == {"value": -30, "is_unknown": False}
    assert loaded.detection_data()["threshold_date"] == {"value": "2026-09-02", "is_unknown": False}


def test_iso_string_date_and_fractional_value_are_accepted(tmp_path: Path) -> None:
    body = '[threshold]\nalert_threshold_pct = -37.6\nthreshold_source = "p90 of noise"\nthreshold_date = "2026-09-02"\n'
    loaded = load_alert_threshold(write_toml(tmp_path, body))
    assert loaded.alert_threshold_pct == Decimal("-37.6")
    assert loaded.threshold_date == DECIDED
    assert loaded.payload()["value"] == -37.6


@pytest.mark.parametrize(
    "body, message",
    [
        ('[threshold]\nalert_threshold_pct = -30\n', "together"),
        ('[threshold]\nthreshold_source = "x"\nthreshold_date = 2026-09-02\n', "together"),
        (f'[threshold]\nalert_threshold_pct = 30\nthreshold_source = "{SOURCE}"\nthreshold_date = 2026-09-02\n', "negative"),
        (f'[threshold]\nalert_threshold_pct = 0\nthreshold_source = "{SOURCE}"\nthreshold_date = 2026-09-02\n', "negative"),
        (f'[threshold]\nalert_threshold_pct = -30\nthreshold_source = "  "\nthreshold_date = 2026-09-02\n', "non-empty"),
        ('[threshold]\nalert_threshold_pct = -30\nthreshold_source = "x"\nthreshold_date = "yesterday"\n', "ISO date"),
        ('[threshold]\nalert_threshold_pct = "thirty"\nthreshold_source = "x"\nthreshold_date = 2026-09-02\n', "valid decimal"),
        ('[threshold]\nsales_drop_threshold_pct = -30\n', "unknown threshold config keys"),
        ('[detector]\nalert_threshold_pct = -30\n', "must carry a \\[threshold\\] table"),
        ("alert_threshold_pct = -30\n", "must carry a \\[threshold\\] table"),
    ],
)
def test_invalid_config_is_refused(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_alert_threshold(write_toml(tmp_path, body))


@pytest.mark.parametrize(
    "body, message",
    [
        ('[threshold]\nalert_threshold_pct = true\nthreshold_source = "x"\nthreshold_date = 2026-09-02\n', "must be a number"),
        ('[threshold]\nalert_threshold_pct = -30\nthreshold_source = 5\nthreshold_date = 2026-09-02\n', "must be a string"),
        ('[threshold]\nalert_threshold_pct = -30\nthreshold_source = "x"\nthreshold_date = 2026-09-02T00:00:00\n', "not a datetime"),
    ],
)
def test_wrong_types_are_refused(tmp_path: Path, body: str, message: str) -> None:
    with pytest.raises(TypeError, match=message):
        load_alert_threshold(write_toml(tmp_path, body))


def test_missing_file_and_broken_toml_are_errors(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="missing"):
        load_alert_threshold(tmp_path / "absent.toml")
    with pytest.raises(ValueError, match="not valid TOML"):
        load_alert_threshold(write_toml(tmp_path, "[threshold\n"))


def test_config_path_resolution_explicit_then_env_then_packaged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CONFIG_FILE_ENV, raising=False)
    assert resolve_config_path() == DEFAULT_CONFIG_PATH
    from_env = write_toml(tmp_path, f'[threshold]\nalert_threshold_pct = -30\nthreshold_source = "{SOURCE}"\nthreshold_date = 2026-09-02\n')
    monkeypatch.setenv(CONFIG_FILE_ENV, str(from_env))
    assert resolve_config_path() == from_env
    assert load_alert_threshold() == MINUS_30
    explicit = tmp_path / "explicit.toml"
    explicit.write_text("[threshold]\n", encoding="utf-8")
    assert resolve_config_path(explicit) == explicit
    assert load_alert_threshold(explicit) == NOT_APPLIED


def test_dataclass_refuses_a_partial_triple_and_a_non_negative_value() -> None:
    with pytest.raises(ValueError, match="together"):
        AlertThreshold(Decimal(-30))
    with pytest.raises(ValueError, match="negative"):
        AlertThreshold(Decimal(0), SOURCE, DECIDED)
    with pytest.raises(TypeError, match="Decimal"):
        AlertThreshold(-30, SOURCE, DECIDED)  # type: ignore[arg-type]
    assert parse_alert_threshold({"threshold": {}}) == NOT_APPLIED


# --- правило прохождения ------------------------------------------------------


def test_admits_everything_without_a_threshold_and_at_or_beyond_it_with_one() -> None:
    assert NOT_APPLIED.admits((-0.1, None)) is True
    assert NOT_APPLIED.admits((None, None)) is True
    assert MINUS_30.admits((-31.0, None)) is True
    assert MINUS_30.admits((-30.0, 5.0)) is True  # ровно порог - тревога
    assert MINUS_30.admits((-29.9, -29.9)) is False
    assert MINUS_30.admits((-10.0, -35.0)) is True  # достаточно одной метрики
    assert MINUS_30.admits((None, None)) is False
    assert MINUS_30.admits((25.0, 25.0)) is False  # рост через порог не проходит


def test_null_threshold_keeps_every_candidate_and_minus_30_drops_the_smaller_drops() -> None:
    facts = [
        *rows(3001, 100, 69, "10000.00", "6900.00"),  # -31.0 %
        *rows(3002, 100, 70, "10000.00", "7000.00"),  # -30.0 % (ровно порог)
        *rows(3003, 100, 71, "10000.00", "7100.00"),  # -29.0 %
        *rows(3004, 100, 90, "10000.00", "6500.00"),  # заказы -10 %, выручка -35 %
        *rows(3005, 100, 125, "10000.00", "12500.00"),  # рост +25 %
    ]
    subjects = {nm_id: subject(nm_id, f"subject-{nm_id}") for nm_id in (3001, 3002, 3003, 3004, 3005)}

    unfiltered = detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT)
    assert unfiltered.threshold == NOT_APPLIED
    assert unfiltered.suppressed_by_threshold == 0
    assert {s["detection_data"]["nm_id"]["value"] for s in unfiltered.signals if s["detection_data"]["level"]["value"] == "sku"} == {3001, 3002, 3003, 3004}

    filtered = detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT, threshold=MINUS_30)
    skus = {s["detection_data"]["nm_id"]["value"] for s in filtered.signals if s["detection_data"]["level"]["value"] == "sku"}
    assert skus == {3001, 3002, 3004}  # -29 % и рост не тревога; -30 % и выручка -35 % - тревога
    assert filtered.suppressed_by_threshold == 2  # 3003 (-29 %) и его предмет с одним SKU
    for signal in filtered.signals:
        data = signal["detection_data"]
        assert data["threshold_pct"] == {"value": -30, "is_unknown": False}
        assert data["threshold_source"] == {"value": SOURCE, "is_unknown": False}
        assert data["threshold_date"] == {"value": "2026-09-02", "is_unknown": False}
    # Рост остаётся числом в оценке, но не в сигналах (PRD FR-34).
    growth = next(e for e in filtered.evaluations if e.key == "3005")
    assert growth.orders_deviation_pct == 25.0
    assert not any(s["detection_data"]["nm_id"]["value"] == 3005 for s in filtered.signals)
    # Порог - часть снимка входа: другой порог, другой снимок; сами факты те же.
    assert filtered.snapshot_id != unfiltered.snapshot_id
    assert detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT, threshold=MINUS_30).snapshot_id == filtered.snapshot_id


def test_ranking_rule_is_the_same_with_and_without_a_threshold() -> None:
    facts = [
        *rows(3101, 10, 5, "1000.00", "500.00"),  # -50 %, 500.00
        *rows(3102, 20, 12, "2000.00", "1200.00"),  # -40 %, 800.00
        *rows(3103, 8, 7, "800.00", "700.00"),  # -12.5 %, 100.00
    ]
    subjects = {nm_id: subject(nm_id, "Платье") for nm_id in (3101, 3102, 3103)}
    unfiltered = detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT)
    filtered = detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT, threshold=MINUS_30)
    money = lambda result: [s["rub_assessment"]["value_rub"] for s in result.signals]  # noqa: E731
    assert money(unfiltered) == ["1400.00", "800.00", "500.00", "100.00"]  # предмет 38 -> 24 (-36.8 %), затем SKU
    assert money(filtered) == ["1400.00", "800.00", "500.00"]
    assert [s["signal_id"] for s in filtered.signals] == [s["signal_id"] for s in unfiltered.signals][:3]


# --- след в сводке ------------------------------------------------------------


def test_payload_threshold_object_is_written_in_every_status_and_validates() -> None:
    validator = brief_validator()
    for threshold, expected in ((NOT_APPLIED, {"value": None, "source": None, "date": None}), (MINUS_30, {"value": -30, "source": SOURCE, "date": "2026-09-02"})):
        ok = ok_day(threshold)
        insufficient = build_day(
            DAY,
            [MetricNorm("orders", Decimal("38.00"), 14, 9, "insufficient"), MetricNorm("revenue", Decimal("3800.00"), 14, 9, "insufficient")],
            MetricActual(37, Decimal("3700.00")),
            STATUS,
            [RUN],
            threshold=threshold,
        )
        blocked = build_day(DAY, [], None, STATUS, [], threshold=threshold)
        for day in (ok, insufficient, blocked):
            assert day.payload["threshold"] == expected
            assert day.payload["signals"] == []
            validator.validate(day.payload)
        assert (ok.status, insufficient.status, blocked.status) == ("ok", "insufficient", "blocked")


def test_signals_built_with_another_threshold_are_refused_by_the_brief() -> None:
    facts = rows(3201, 10, 5, "1000.00", "500.00")
    subjects = {3201: subject(3201, "Платье")}
    unfiltered = detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT)
    filtered = detect(TENANT, DAY, facts, subjects, {}, [], CREATED_AT, threshold=MINUS_30)
    validator = brief_validator()
    validator.validate(with_signals(ok_day(), unfiltered.signals).payload)
    validator.validate(with_signals(ok_day(MINUS_30), filtered.signals).payload)
    with pytest.raises(ValueError, match="built with threshold"):
        with_signals(ok_day(), filtered.signals)
    with pytest.raises(ValueError, match="built with threshold"):
        with_signals(ok_day(MINUS_30), unfiltered.signals)


def test_brief_contract_rejects_a_threshold_value_without_source_and_date() -> None:
    validator = brief_validator()
    payload = ok_day().payload
    payload["threshold"] = {"value": -30, "source": None, "date": None}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)
    payload["threshold"] = {"value": 30, "source": SOURCE, "date": "2026-09-02"}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)
    del payload["threshold"]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(payload)
