"""SCN-001 trigger, threshold filtering, dedup, and run-result assembly."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Mapping, Sequence

from proxima_control_plane.detectors.scn001.baseline import expected, history_status
from proxima_control_plane.detectors.scn001.config import (
    GlobalThresholdSource,
    Scn001Config,
    ThresholdSource,
)
from proxima_control_plane.detectors.scn001.decomposition import Contributions, decompose
from proxima_control_plane.detectors.scn001.metrics import (
    CABINET_SKU,
    METRIC_FIELDS,
    DailyMetrics,
    MetricBundle,
)

SCENARIO_CODE = "SCN-001"
TRUST_MARKING = "unreleased"
REVENUE_METHOD = "revenue"
LEVEL_SKU = "sku"
LEVEL_CABINET = "cabinet"
REASON_INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
REASON_INVALID_BASELINE = "INVALID_BASELINE"
REASON_INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class MoneyDelta:
    value: Decimal
    method: str = REVENUE_METHOD


@dataclass(frozen=True)
class FactorSnapshot:
    u: Decimal
    cvr: Decimal
    aov: Decimal


@dataclass(frozen=True)
class SignalContext:
    buyouts: Decimal
    buyouts_expected: Decimal


@dataclass(frozen=True)
class Scn001Signal:
    scenario_code: str
    level: str
    key: str
    evaluation_date: date
    delta_7: Decimal | None
    delta_14: Decimal | None
    delta_28: Decimal | None
    revenue_delta_orders: MoneyDelta
    contributions: Contributions
    dominant_factor: str | None
    factors_baseline: FactorSnapshot
    factors_actual: FactorSnapshot
    snapshot_id: str
    source_refs: tuple[str, ...] = ()
    trust_marking: str = TRUST_MARKING
    context: SignalContext | None = None
    panel_size: int | None = None
    excluded_count: int | None = None


@dataclass(frozen=True)
class BlockedEntry:
    reason: str
    level: str
    key: str
    evaluation_date: date
    detail: str = ""
    trust_marking: str = TRUST_MARKING


@dataclass(frozen=True)
class DedupEntry:
    level: str
    key: str
    opened_at: date
    last_seen_date: date


@dataclass(frozen=True)
class RunCounters:
    candidates: int = 0
    filtered_by_rub: int = 0
    filtered_by_rank: int = 0
    dedup_suppressed: int = 0
    blocked_by_reason: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Scn001RunResult:
    evaluation_date: date
    snapshot_id: str
    signals: tuple[Scn001Signal, ...]
    blocked: tuple[BlockedEntry, ...]
    counters: RunCounters
    dedup_state: tuple[DedupEntry, ...]
    trust_marking: str = TRUST_MARKING
    run_fingerprint: str = ""


def _encode(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, Decimal):
        return format(obj.normalize(), "f") if obj != 0 else "0"
    if isinstance(obj, date):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _encode(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Mapping):
        return {str(k): _encode(v) for k, v in obj.items()}
    if isinstance(obj, (set, frozenset)):
        items = [_encode(item) for item in obj]
        items.sort(key=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return items
    if isinstance(obj, (list, tuple)):
        return [_encode(item) for item in obj]
    raise TypeError(f"cannot canonically encode {type(obj).__name__}")


def canonical_hash(obj: Any) -> str:
    payload = json.dumps(_encode(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot_id(bundle: MetricBundle, evaluation_date: date) -> str:
    panel_rows = [r for sku in bundle.panel for r in bundle.rows_by_sku.get(sku, ())]
    panel_rows.sort(key=lambda r: (r.sku, r.date))
    return canonical_hash(
        {
            "evaluation_date": evaluation_date,
            "panel": list(bundle.panel),
            "metrics": panel_rows,
        }
    )


@dataclass(frozen=True)
class _TriggerOutcome:
    day: DailyMetrics
    ratios: Mapping[int, Decimal | None]
    factors_baseline: FactorSnapshot
    factors_actual: FactorSnapshot
    revenue_delta: Decimal
    contributions: Contributions
    lost: Decimal
    buyouts_expected: Decimal


@dataclass(frozen=True)
class _Evaluation:
    blocked: BlockedEntry | None = None
    triggered: bool = False
    recovered: bool = False
    outcome: _TriggerOutcome | None = None


@dataclass(frozen=True)
class _Candidate:
    level: str
    key: str
    outcome: _TriggerOutcome


def _zero_day(sku: str, day: date) -> DailyMetrics:
    return DailyMetrics(
        sku=sku,
        date=day,
        orders=Decimal("0"),
        open_card=Decimal("0"),
        orders_sum_rub=Decimal("0"),
        buyouts=Decimal("0"),
    )


def _evaluate_target(
    level: str,
    key: str,
    rows_by_date: Mapping[date, DailyMetrics],
    evaluation_date: date,
    config: Scn001Config,
    drop_threshold: Decimal,
) -> _Evaluation:
    orders_series = {d: r.orders for d, r in rows_by_date.items()}
    history_days = history_status(orders_series, evaluation_date, config.maturity_window_days)
    if history_days < config.maturity_min_days:
        return _Evaluation(
            blocked=BlockedEntry(
                reason=REASON_INSUFFICIENT_HISTORY,
                level=level,
                key=key,
                evaluation_date=evaluation_date,
                detail=f"history_days={history_days} < {config.maturity_min_days}",
            )
        )
    for day_key in sorted(rows_by_date):
        row = rows_by_date[day_key]
        for name in METRIC_FIELDS:
            if getattr(row, name) < 0:
                return _Evaluation(
                    blocked=BlockedEntry(
                        reason=REASON_INVALID_INPUT,
                        level=level,
                        key=key,
                        evaluation_date=evaluation_date,
                        detail=f"negative {name}={getattr(row, name)} on {day_key}",
                    )
                )
    day = rows_by_date.get(evaluation_date)
    if day is None:
        day_sku = next(iter(rows_by_date.values())).sku if rows_by_date else CABINET_SKU
        day = _zero_day(day_sku, evaluation_date)
    if day.orders > 0 and day.open_card == 0:
        return _Evaluation(
            blocked=BlockedEntry(
                reason=REASON_INVALID_INPUT,
                level=level,
                key=key,
                evaluation_date=evaluation_date,
                detail=f"open_card=0 with orders={day.orders}",
            )
        )
    orders_series = {d: r.orders for d, r in rows_by_date.items()}
    exp_trigger = expected(orders_series, evaluation_date, config.trigger_window)
    if exp_trigger == 0:
        return _Evaluation(
            blocked=BlockedEntry(
                reason=REASON_INVALID_BASELINE,
                level=level,
                key=key,
                evaluation_date=evaluation_date,
                detail="expected orders = 0 in trigger window",
            )
        )
    corroborators = [w for w in config.windows if w != config.trigger_window]
    ratios: dict[int, Decimal | None] = {}
    drops: dict[int, bool] = {}
    for w in config.windows:
        exp_w = expected(orders_series, evaluation_date, w)
        if exp_w == 0:
            ratios[w] = None
            drops[w] = False
            continue
        ratio = day.orders / exp_w - Decimal("1")
        ratios[w] = ratio
        drops[w] = ratio <= -drop_threshold
    triggered = bool(drops.get(config.trigger_window, False)) and any(
        drops[w] for w in corroborators
    )
    ratio_trigger = ratios.get(config.trigger_window)
    recovered = ratio_trigger is not None and ratio_trigger >= -drop_threshold
    if not triggered:
        return _Evaluation(triggered=False, recovered=recovered)
    u_series = {d: r.open_card for d, r in rows_by_date.items()}
    aov_series = {
        d: (r.orders_sum_rub / r.orders if r.orders > 0 else Decimal("0"))
        for d, r in rows_by_date.items()
    }
    buyouts_series = {d: r.buyouts for d, r in rows_by_date.items()}
    u1 = day.open_card
    cvr1 = day.orders / u1 if u1 > 0 else Decimal("0")
    aov1 = day.orders_sum_rub / day.orders if day.orders > 0 else Decimal("0")
    exp_u = expected(u_series, evaluation_date, config.trigger_window)
    exp_aov = expected(aov_series, evaluation_date, config.trigger_window)
    exp_buyouts = expected(buyouts_series, evaluation_date, config.trigger_window)
    revenue0 = exp_trigger * exp_aov
    u0 = exp_u
    cvr0 = exp_trigger / exp_u if exp_u > 0 else Decimal("0")
    aov0 = exp_aov
    revenue1 = day.orders * aov1
    revenue_delta = revenue0 - revenue1
    if exp_u > 0:
        contributions = decompose(u1, cvr1, aov1, u0, cvr0, aov0)
    else:
        contributions = Contributions(u=revenue_delta, cvr=Decimal("0"), aov=Decimal("0"))
    lost = revenue_delta if revenue_delta > 0 else Decimal("0")
    outcome = _TriggerOutcome(
        day=day,
        ratios=ratios,
        factors_baseline=FactorSnapshot(u=u0, cvr=cvr0, aov=aov0),
        factors_actual=FactorSnapshot(u=u1, cvr=cvr1, aov=aov1),
        revenue_delta=revenue_delta,
        contributions=contributions,
        lost=lost,
        buyouts_expected=exp_buyouts,
    )
    return _Evaluation(triggered=True, outcome=outcome)


def _to_signal(
    candidate: _Candidate,
    snapshot_id: str,
    bundle: MetricBundle,
    evaluation_date: date,
    config: Scn001Config,
) -> Scn001Signal:
    o = candidate.outcome
    is_cabinet = candidate.level == LEVEL_CABINET
    return Scn001Signal(
        scenario_code=SCENARIO_CODE,
        level=candidate.level,
        key=candidate.key,
        evaluation_date=evaluation_date,
        delta_7=o.ratios.get(7),
        delta_14=o.ratios.get(14),
        delta_28=o.ratios.get(config.trigger_window),
        revenue_delta_orders=MoneyDelta(value=o.revenue_delta, method=REVENUE_METHOD),
        contributions=o.contributions,
        dominant_factor=o.contributions.dominant(),
        factors_baseline=o.factors_baseline,
        factors_actual=o.factors_actual,
        snapshot_id=snapshot_id,
        context=SignalContext(buyouts=o.day.buyouts, buyouts_expected=o.buyouts_expected),
        panel_size=len(bundle.panel) if is_cabinet else None,
        excluded_count=len(bundle.excluded) if is_cabinet else None,
    )


def detect(
    bundle: MetricBundle,
    config: Scn001Config,
    threshold_source: ThresholdSource | None = None,
    dedup_state: Sequence[DedupEntry] = (),
    *,
    evaluation_date: date,
) -> Scn001RunResult:
    if threshold_source is None:
        threshold_source = GlobalThresholdSource(config)
    drop_threshold = threshold_source.drop_threshold()
    rub_floor = threshold_source.rub_floor()
    snapshot_id = _snapshot_id(bundle, evaluation_date)
    dedup: dict[tuple[str, str], DedupEntry] = {(e.level, e.key): e for e in dedup_state}
    result_dedup: dict[tuple[str, str], DedupEntry] = dict(dedup)
    blocked: list[BlockedEntry] = []
    candidates: list[_Candidate] = []

    def _evaluate(level: str, key: str, rows_by_date: Mapping[date, DailyMetrics]) -> None:
        evaluation = _evaluate_target(
            level, key, rows_by_date, evaluation_date, config, drop_threshold
        )
        if evaluation.blocked is not None:
            blocked.append(evaluation.blocked)
        elif evaluation.triggered:
            candidates.append(_Candidate(level, key, evaluation.outcome))
        elif evaluation.recovered:
            result_dedup.pop((level, key), None)

    for sku in sorted(bundle.rows_by_sku):
        rows_by_date = {r.date: r for r in bundle.rows_by_sku[sku]}
        _evaluate(LEVEL_SKU, sku, rows_by_date)

    if bundle.panel:
        _evaluate(LEVEL_CABINET, CABINET_SKU, bundle.panel_daily())

    candidates_count = len(candidates)
    dedup_suppressed = 0
    accepted: list[_Candidate] = []
    for candidate in candidates:
        pair = (candidate.level, candidate.key)
        entry = dedup.get(pair)
        if entry is not None:
            if evaluation_date - entry.last_seen_date >= timedelta(days=config.cooldown_days):
                result_dedup.pop(pair)
            else:
                dedup_suppressed += 1
                result_dedup[pair] = replace(entry, last_seen_date=evaluation_date)
                continue
        accepted.append(candidate)
        result_dedup[pair] = DedupEntry(
            level=candidate.level,
            key=candidate.key,
            opened_at=evaluation_date,
            last_seen_date=evaluation_date,
        )

    filtered_by_rub = 0
    finalists: list[_Candidate] = []
    for candidate in accepted:
        if candidate.outcome.lost < rub_floor:
            filtered_by_rub += 1
        else:
            finalists.append(candidate)
    finalists.sort(key=lambda c: (-c.outcome.revenue_delta, c.level, c.key))
    emitted = finalists[: config.top_n]
    filtered_by_rank = len(finalists) - len(emitted)
    signals = tuple(
        _to_signal(c, snapshot_id, bundle, evaluation_date, config) for c in emitted
    )
    counters = RunCounters(
        candidates=candidates_count,
        filtered_by_rub=filtered_by_rub,
        filtered_by_rank=filtered_by_rank,
        dedup_suppressed=dedup_suppressed,
        blocked_by_reason=dict(Counter(b.reason for b in blocked)),
    )
    result = Scn001RunResult(
        evaluation_date=evaluation_date,
        snapshot_id=snapshot_id,
        signals=signals,
        blocked=tuple(blocked),
        counters=counters,
        dedup_state=tuple(result_dedup[k] for k in sorted(result_dedup)),
    )
    fingerprint = canonical_hash(replace(result, run_fingerprint=""))
    return replace(result, run_fingerprint=fingerprint)
