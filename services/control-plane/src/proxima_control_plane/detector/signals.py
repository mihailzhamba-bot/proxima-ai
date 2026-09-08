"""Сигналы по `contracts/signal.schema.json` v1 из оценок детектора (AD-1, AD-10, AD-19).

Один сигнал на кандидата (SKU или категория с заказами или выручкой ниже нормы,
D32). Порог - значение конфигурации control-plane (`detector/threshold.py`,
решение 6а, Story 4.2): пока он `null`, в `signals[]` попадает каждый кандидат;
когда Story 4.4 задаст значение, остаются кандидаты, у которых хотя бы одна
упавшая метрика отклонилась на порог или глубже, - правило порядка при этом не
меняется. `rub_assessment.value_rub` - деньги под риском строкой с двумя
знаками, `method = revenue` (переход к прибыли - только для SKU с `cogs_status`,
PRD FR-9, вне этой истории). `source_refs` - версии фактов (`run_id`), их
доказательства (`evidence_sha256`), словарь и расчёт по снимку входа. `detection_data`
несёт ряд SKU/категории: `nm_id`, `supplier_article`, `subject_name` webapp берёт
отсюда, а не из фактов (AD-19), и тройку порога, с которой считался сигнал.
`signals[]` упорядочены по деньгам под риском (CAP-7).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Mapping, Sequence

from proxima_control_plane.detector.canonical import canonical_hash
from proxima_control_plane.detector.evaluate import (
    ADAPTER_WINDOWS,
    LEVEL_SKU,
    LEVEL_SUBJECT,
    STATUS_OK,
    Evaluation,
    evaluate_all,
)
from proxima_control_plane.detector.funnel import FunnelStage, funnel_stage
from proxima_control_plane.detector.metrics import DailyMetrics, FunnelMetrics, SubjectRow
from proxima_control_plane.detector.threshold import NOT_APPLIED, AlertThreshold
from proxima_control_plane.norm.median import WINDOW_DAYS, quantize_money

SCHEMA_VERSION = 1
SCENARIO_CODE = "SCN-001"
TRUST_MARKING = "unreleased"
RUB_METHOD = "revenue"
CALCULATION = "scn001/norm-median-14d/v1"
ARTIFACT_PREFIX = "artifact://business-signal/sha256/"


@dataclass(frozen=True)
class DetectionResult:
    """Итог шага детектора для одного дня сводки."""

    evaluation_day: date
    snapshot_id: str
    evaluations: tuple[Evaluation, ...]
    signals: tuple[dict, ...]
    input_run_ids: tuple[str, ...]
    unknown_subject_nm_ids: tuple[int, ...]
    threshold: AlertThreshold = NOT_APPLIED
    # Кандидаты ниже нормы, не прошедшие порог (Story 4.2); ноль, пока порог не применяется.
    suppressed_by_threshold: int = 0

    def counters(self) -> dict[str, int]:
        by_level = {LEVEL_SKU: 0, LEVEL_SUBJECT: 0}
        insufficient = {LEVEL_SKU: 0, LEVEL_SUBJECT: 0}
        for evaluation in self.evaluations:
            by_level[evaluation.level] += 1
            if evaluation.status != STATUS_OK:
                insufficient[evaluation.level] += 1
        return {
            "sku_total": by_level[LEVEL_SKU],
            "sku_insufficient": insufficient[LEVEL_SKU],
            "subject_total": by_level[LEVEL_SUBJECT],
            "subject_insufficient": insufficient[LEVEL_SUBJECT],
            "signals": len(self.signals),
        }


def known(value: Any) -> dict:
    return {"value": value, "is_unknown": False}


UNKNOWN = {"value": None, "is_unknown": True}


def _money(value: Decimal) -> str:
    return str(quantize_money(value))


def _two_decimals(value: Decimal | None) -> dict:
    return UNKNOWN if value is None else known(_money(value))


def _int(value: Decimal) -> int | str:
    """Заказы - целые; дробная сумма невозможна по CHECK, но строкой она честнее, чем float."""
    return int(value) if value == value.to_integral_value() else _money(value)


def subject_slug(subject_name: str) -> str:
    return hashlib.sha256(subject_name.encode("utf-8")).hexdigest()[:12]


def signal_id(evaluation: Evaluation, evaluation_day: date) -> str:
    key = evaluation.key if evaluation.level == LEVEL_SKU else subject_slug(evaluation.key)
    return f"scn001-{evaluation_day.isoformat()}-{evaluation.level}-{key}"


def snapshot_id(
    tenant_id: str,
    evaluation_day: date,
    facts: Sequence[DailyMetrics],
    subjects: Mapping[int, SubjectRow],
    funnel_history_days: Mapping[int, int],
    funnel_rows: Sequence[FunnelMetrics],
    threshold: AlertThreshold = NOT_APPLIED,
) -> str:
    """Хэш входа детектора: те же факты и тот же порог - тот же снимок, любое изменение - другой."""
    return canonical_hash(
        {
            "scenario_code": SCENARIO_CODE,
            "calculation": CALCULATION,
            "tenant_id": tenant_id,
            "evaluation_day": evaluation_day,
            "facts": sorted(facts, key=lambda row: (row.nm_id, row.calendar_day)),
            "subjects": [subjects[nm_id] for nm_id in sorted(subjects)],
            "funnel_history_days": {str(nm_id): funnel_history_days[nm_id] for nm_id in sorted(funnel_history_days)},
            "funnel": sorted(funnel_rows, key=lambda row: (row.nm_id, row.calendar_day)),
            "threshold": threshold.payload(),
        }
    )


def source_refs(evaluation: Evaluation, subjects: Mapping[int, SubjectRow], funnel: FunnelStage | None, snapshot: str) -> list[str]:
    refs: set[str] = set()
    for row in evaluation.rows:
        refs.add(f"table://fact_nm_daily/nm/{row.nm_id}/run/{row.run_id}")
        refs.update(f"{ARTIFACT_PREFIX}{sha}" for sha in row.evidence_sha256)
    for nm_id in evaluation.nm_ids:
        subject = subjects.get(nm_id)
        if subject is None:
            refs.add(f"table://dim_nm_subject/nm/{nm_id}/is_unknown")
        else:
            refs.add(f"table://dim_nm_subject/nm/{nm_id}/run/{subject.run_id}")
            refs.add(f"{ARTIFACT_PREFIX}{subject.evidence_sha256}")
    if funnel is not None:
        for row in funnel.rows:
            refs.add(f"table://fact_funnel_daily/nm/{row.nm_id}/run/{row.run_id}")
            refs.add(f"{ARTIFACT_PREFIX}{row.evidence_sha256}")
    refs.add(f"calc://{CALCULATION}/snapshot/{snapshot}")
    return sorted(refs)


def _funnel_data(funnel: FunnelStage | None) -> dict:
    if funnel is None:
        return {"funnel_weeks": known(0), "funnel_stage": UNKNOWN}
    data = {"funnel_weeks": known(funnel.weeks), "funnel_stage": UNKNOWN if funnel.stage is None else known(funnel.stage)}
    if funnel.contributions is not None:
        data["funnel_loss_u_rub"] = known(_money(funnel.contributions.u))
        data["funnel_loss_cvr_rub"] = known(_money(funnel.contributions.cvr))
        data["funnel_loss_aov_rub"] = known(_money(funnel.contributions.aov))
    return data


def detection_data(
    evaluation: Evaluation,
    subjects: Mapping[int, SubjectRow],
    funnel: FunnelStage | None,
    evaluation_day: date,
    threshold: AlertThreshold = NOT_APPLIED,
) -> dict:
    if evaluation.status != STATUS_OK or evaluation.actual_orders is None or evaluation.actual_revenue is None:
        raise ValueError("detection_data is built for ok evaluations only")
    if evaluation.norm_orders is None or evaluation.norm_revenue is None or not evaluation.triggered_by:
        raise ValueError("ok evaluation without a norm or a deviation")
    if evaluation.level == LEVEL_SKU:
        nm_id = evaluation.nm_ids[0]
        subject = subjects.get(nm_id)
        identity = {
            "level": known(LEVEL_SKU),
            "nm_id": known(nm_id),
            "supplier_article": UNKNOWN if subject is None else known(subject.supplier_article),
            "brand": UNKNOWN if subject is None else known(subject.brand),
            "subject_name": UNKNOWN if subject is None else known(subject.subject_name),
            "sku_count": known(1),
        }
    else:
        identity = {
            "level": known(LEVEL_SUBJECT),
            "nm_id": UNKNOWN,
            "supplier_article": UNKNOWN,
            "brand": UNKNOWN,
            "subject_name": known(evaluation.key),
            "sku_count": known(len(evaluation.nm_ids)),
        }
    data = {
        **identity,
        "evaluation_day": known(evaluation_day.isoformat()),
        "triggered_by": known(list(evaluation.triggered_by)),
        "orders_actual": known(_int(evaluation.actual_orders)),
        "orders_norm_median": known(_money(evaluation.norm_orders)),
        "orders_deviation_pct": UNKNOWN if evaluation.orders_deviation_pct is None else known(evaluation.orders_deviation_pct),
        "revenue_actual": known(_money(evaluation.actual_revenue)),
        "revenue_norm_median": known(_money(evaluation.norm_revenue)),
        "revenue_deviation_pct": UNKNOWN if evaluation.revenue_deviation_pct is None else known(evaluation.revenue_deviation_pct),
        "norm_window_days": known(WINDOW_DAYS),
        "norm_sample_days": known(evaluation.sample_days),
        "norm_status": known(evaluation.status),
        "norm_rule": known("D21 median of 14 full days before evaluation_day"),
        "history_days_28d": known(evaluation.history_days),
        # Тройка порога, с которой считался сигнал (Story 4.2): UNKNOWN, пока порог null.
        **threshold.detection_data(),
        **{f"orders_mean_{window}d": _two_decimals(evaluation.means.get(window)) for window in ADAPTER_WINDOWS},
        **_funnel_data(funnel),
    }
    return data


def build_signal(
    evaluation: Evaluation,
    subjects: Mapping[int, SubjectRow],
    funnel: FunnelStage | None,
    tenant_id: str,
    evaluation_day: date,
    created_at: str,
    snapshot: str,
    threshold: AlertThreshold = NOT_APPLIED,
) -> dict:
    if evaluation.money_at_risk is None:
        raise ValueError("a signal needs money at risk")
    # D32: знак оценки значим — рост выручки при падении заказов остаётся
    # отрицательной суммой, а не обрезается до искусственных 0.00.
    return {
        "schema_version": SCHEMA_VERSION,
        "signal_id": signal_id(evaluation, evaluation_day),
        "scenario_code": SCENARIO_CODE,
        "snapshot_id": snapshot,
        "tenant_id": tenant_id,
        "created_at": created_at,
        "trust_marking": TRUST_MARKING,
        "rub_assessment": {"value_rub": _money(evaluation.money_at_risk), "method": RUB_METHOD},
        "source_refs": source_refs(evaluation, subjects, funnel, snapshot),
        "detection_data": detection_data(evaluation, subjects, funnel, evaluation_day, threshold),
    }


def _rank_key(signal: dict) -> tuple:
    data = signal["detection_data"]
    level = data["level"]["value"]
    key = f"{data['nm_id']['value']:020d}" if level == LEVEL_SKU else data["subject_name"]["value"]
    return (-Decimal(signal["rub_assessment"]["value_rub"]), level, key)


def rank(signals: Sequence[dict]) -> list[dict]:
    """По убыванию денег под риском; при равенстве - SKU раньше категории, затем ключ."""
    return sorted(signals, key=_rank_key)


def detect(
    tenant_id: str,
    evaluation_day: date,
    facts: Sequence[DailyMetrics],
    subjects: Mapping[int, SubjectRow],
    funnel_history_days: Mapping[int, int],
    funnel_rows: Sequence[FunnelMetrics],
    created_at: str,
    threshold: AlertThreshold = NOT_APPLIED,
) -> DetectionResult:
    """Чистый прогон детектора на уже прочитанных версиях (тестируемо без БД).

    `threshold` - конфигурация control-plane (Story 4.2): `NOT_APPLIED` пропускает
    каждого кандидата ниже нормы; заданный порог оставляет тех, у кого хотя бы одна
    упавшая метрика отклонилась на порог или глубже. Рост кандидатом не бывает.
    """
    snapshot = snapshot_id(tenant_id, evaluation_day, facts, subjects, funnel_history_days, funnel_rows, threshold)
    evaluations = evaluate_all(facts, subjects, evaluation_day)
    funnel_by_nm: dict[int, list[FunnelMetrics]] = {}
    for row in funnel_rows:
        funnel_by_nm.setdefault(row.nm_id, []).append(row)
    signals: list[dict] = []
    suppressed = 0
    for evaluation in evaluations:
        if not evaluation.is_candidate:
            continue
        if not threshold.admits((evaluation.orders_deviation_pct, evaluation.revenue_deviation_pct)):
            suppressed += 1
            continue
        funnel: FunnelStage | None = None
        if evaluation.level == LEVEL_SKU:
            # Этап воронки - только у SKU; у категории он остаётся UNKNOWN.
            nm_id = evaluation.nm_ids[0]
            funnel = funnel_stage(funnel_history_days.get(nm_id, 0), funnel_by_nm.get(nm_id, []), evaluation_day)
        signals.append(build_signal(evaluation, subjects, funnel, tenant_id, evaluation_day, created_at, snapshot, threshold))
    input_run_ids = {row.run_id for row in facts}
    input_run_ids.update(subject.run_id for subject in subjects.values())
    input_run_ids.update(row.run_id for row in funnel_rows)
    return DetectionResult(
        evaluation_day=evaluation_day,
        snapshot_id=snapshot,
        evaluations=tuple(evaluations),
        signals=tuple(rank(signals)),
        input_run_ids=tuple(sorted(input_run_ids)),
        unknown_subject_nm_ids=tuple(sorted({row.nm_id for row in facts} - set(subjects))),
        threshold=threshold,
        suppressed_by_threshold=suppressed,
    )


__all__ = [
    "CALCULATION",
    "RUB_METHOD",
    "SCENARIO_CODE",
    "TRUST_MARKING",
    "DetectionResult",
    "build_signal",
    "detect",
    "rank",
    "signal_id",
    "snapshot_id",
    "source_refs",
]
