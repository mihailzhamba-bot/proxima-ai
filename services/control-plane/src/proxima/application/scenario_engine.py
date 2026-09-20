"""Pure deterministic SCN-001..008 engine without model or network calls."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast

from pydantic import BaseModel, JsonValue

from proxima.ai.contracts import (
    DeterministicScenarioResult,
    ScenarioId,
    ScenarioInput,
    ScenarioStatus,
    SourceRef,
)

_PNL_COMPONENTS = (
    "revenue",
    "cogs",
    "marketplace_commission",
    "logistics",
    "paid_storage",
    "advertising_spend",
    "returns_cost",
)
_PNL_FORMULA = (
    "revenue - cogs - marketplace_commission - logistics - paid_storage - "
    "advertising_spend - returns_cost"
)
_STOCK_STATES = ("SELLABLE", "IN_TRANSIT", "CLIENT_WAREHOUSE", "PLANNED")
MANDATORY_SOURCES: dict[ScenarioId, frozenset[str]] = {
    "SCN-001": frozenset({"sales_current", "sales_baseline"}),
    "SCN-002": frozenset({"orders_current", "orders_baseline"}),
    "SCN-003": frozenset({*_PNL_COMPONENTS, "contribution_profit_baseline"}),
    "SCN-004": frozenset({*_PNL_COMPONENTS, "margin_baseline"}),
    "SCN-005": frozenset({"stock", "demand_per_day", "lead_time_days", "moq", "client_stock"}),
    "SCN-006": frozenset(
        {"stock", "demand_per_day", "seasonality", "storage_exposure", "contribution_margin"}
    ),
    "SCN-007": frozenset(
        {"drr_current", "drr_baseline", "attribution_mature", "stock", "contribution_margin"}
    ),
    "SCN-008": frozenset({"data_quality"}),
}


class ScenarioPolicyMissing(ValueError):
    """Internal marker for a policy gap; public behavior is typed BLOCKED."""


def _json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _decimal(value: JsonValue, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    try:
        return Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{name} must be numeric") from error


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _ratio(current: Decimal, baseline: Decimal, name: str) -> Decimal:
    if baseline == 0:
        raise ValueError(f"{name} baseline cannot be zero")
    return (current - baseline) / abs(baseline)


@dataclass(frozen=True)
class _Decision:
    status: ScenarioStatus
    outputs: dict[str, JsonValue]
    missing: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()


Handler = Callable[[ScenarioInput, dict[str, JsonValue], tuple[str, ...]], _Decision]


class ScenarioEngine:
    """Application-owned registry of eight ordinary deterministic handlers."""

    def __init__(self) -> None:
        self.handlers: dict[ScenarioId, Handler] = {
            "SCN-001": self._run_scn_001,
            "SCN-002": self._run_scn_002,
            "SCN-003": self._run_scn_003,
            "SCN-004": self._run_scn_004,
            "SCN-005": self._run_scn_005,
            "SCN-006": self._run_scn_006,
            "SCN-007": self._run_scn_007,
            "SCN-008": self._run_scn_008,
        }

    def run(self, input_: ScenarioInput) -> DeterministicScenarioResult:
        material_refs = self._material_refs(input_)
        facts_fingerprint = canonical_hash([self._fingerprint_ref(ref) for ref in material_refs])
        evidence_hash = canonical_hash(
            [
                {
                    "source_ref_id": ref.source_ref_id,
                    "locator": ref.locator,
                    "period": ref.period,
                    "value": ref.value,
                    "quality": ref.quality,
                }
                for ref in material_refs
            ]
        )
        decision_state = {
            "open_contracts": [
                contract.model_dump(mode="json")
                for contract in sorted(input_.open_contracts, key=lambda item: item.contract_id)
            ],
            "decision_memory": [
                memory.model_dump(mode="json")
                for memory in sorted(
                    (
                        item
                        for item in input_.context.decision_memory
                        if item.scenario_id in {None, input_.scenario_id}
                    ),
                    key=lambda item: item.event_id,
                )
            ],
        }
        decision_state_fingerprint = canonical_hash(decision_state)
        trigger_fingerprint = canonical_hash(
            {
                "scenario_id": input_.scenario_id,
                "snapshot_id": input_.snapshot.snapshot_id,
                "snapshot_checksum": input_.snapshot.checksum,
                "policy_version": input_.policy_version,
                "policy": input_.policy.model_dump(mode="json") if input_.policy else None,
                "facts_fingerprint": facts_fingerprint,
                "decision_state_fingerprint": decision_state_fingerprint,
            }
        )

        qualities = {ref.quality for ref in input_.context.operational_data}
        if input_.snapshot.status != "ready" or qualities - {"fresh"}:
            status: ScenarioStatus = "INCIDENT" if input_.scenario_id == "SCN-008" else "BLOCKED"
            return self._result(
                input_,
                status,
                trigger_fingerprint,
                facts_fingerprint,
                evidence_hash,
                decision_state_fingerprint,
                material_refs,
                {"quality_status": input_.snapshot.status},
                (),
                ("DATA_QUALITY_NOT_READY",),
            )

        if input_.policy is None:
            return self._result(
                input_,
                "BLOCKED",
                trigger_fingerprint,
                facts_fingerprint,
                evidence_hash,
                decision_state_fingerprint,
                material_refs,
                {},
                (f"policy:{input_.policy_version}",),
                ("SCENARIO_POLICY_MISSING",),
            )

        facts, ambiguous = self._facts(input_.context.operational_data)
        required = list(MANDATORY_SOURCES[input_.scenario_id])
        required.extend(input_.policy.required_sources)
        missing = tuple(sorted(set(required) - facts.keys()))
        if ambiguous:
            missing = tuple(sorted(set(missing).union(f"ambiguous:{name}" for name in ambiguous)))
        if (
            input_.scenario_id in {"SCN-003", "SCN-004"}
            and input_.policy.parameters.get("formula") != _PNL_FORMULA
        ):
            missing = tuple(sorted(set(missing).union({"policy.parameters.formula"})))

        decision = self.handlers[input_.scenario_id](input_, facts, missing)
        if decision.status == "PROPOSED":
            action_missing = []
            if input_.policy.review_at is None:
                action_missing.append("policy.review_at")
            if not input_.policy.expected_result:
                action_missing.append("policy.expected_result")
            if action_missing:
                decision = _Decision(
                    status="BLOCKED",
                    outputs=decision.outputs,
                    missing=tuple(action_missing),
                    reason_codes=("ACTION_POLICY_INCOMPLETE",),
                )

        if decision.status == "PROPOSED" and any(
            contract.facts_fingerprint == facts_fingerprint
            and contract.evidence_hash == evidence_hash
            for contract in input_.open_contracts
        ):
            decision = _Decision(
                status="NO_ACTION",
                outputs=decision.outputs,
                reason_codes=("DUPLICATE_OPEN_CONTRACT",),
            )

        return self._result(
            input_,
            decision.status,
            trigger_fingerprint,
            facts_fingerprint,
            evidence_hash,
            decision_state_fingerprint,
            material_refs,
            decision.outputs,
            decision.missing,
            decision.reason_codes,
        )

    @staticmethod
    def _fingerprint_ref(ref: SourceRef) -> dict[str, JsonValue]:
        return {
            "source_ref_id": ref.source_ref_id,
            "client_id": ref.client_id,
            "cabinet_id": ref.cabinet_id,
            "snapshot_id": ref.snapshot_id,
            "source": ref.source,
            "trust_class": ref.trust_class,
            "retrieved_at": ref.retrieved_at.isoformat(),
            "period": ref.period,
            "locator": ref.locator,
            "value": ref.value,
            "quality": ref.quality,
            "run_id": ref.run_id,
            "lineage_checksum": ref.lineage_checksum,
        }

    @staticmethod
    def _facts(refs: tuple[SourceRef, ...]) -> tuple[dict[str, JsonValue], tuple[str, ...]]:
        facts: dict[str, JsonValue] = {}
        ambiguous: set[str] = set()
        for ref in refs:
            if ref.source in facts and facts[ref.source] != ref.value:
                ambiguous.add(ref.source)
            else:
                facts[ref.source] = ref.value
        return facts, tuple(sorted(ambiguous))

    @staticmethod
    def _material_refs(input_: ScenarioInput) -> tuple[SourceRef, ...]:
        if input_.policy is None:
            selected = input_.context.operational_data
        else:
            required = set(input_.policy.required_sources).union(
                MANDATORY_SOURCES[input_.scenario_id]
            )
            policy_refs = set(input_.policy.source_ref_ids)
            selected = tuple(
                ref
                for ref in input_.context.operational_data
                if ref.source in required
                or ref.source == "data_quality"
                or ref.source_ref_id in policy_refs
                or ref.quality != "fresh"
            )
        return tuple(sorted(selected, key=lambda ref: ref.source_ref_id))

    @staticmethod
    def _threshold(policy: ScenarioInput, key: str) -> Decimal:
        if policy.policy is None:
            raise ScenarioPolicyMissing(f"policy:{policy.policy_version}")
        value = policy.policy.parameters.get(key)
        if value is None:
            raise ScenarioPolicyMissing(f"policy.parameters.{key}")
        return _decimal(value, f"policy.parameters.{key}")

    def _drop_decision(
        self,
        input_: ScenarioInput,
        facts: dict[str, JsonValue],
        missing: tuple[str, ...],
        *,
        current_key: str,
        baseline_key: str,
        output_key: str,
    ) -> _Decision:
        local_missing = list(missing)
        try:
            threshold = self._threshold(input_, "trigger_ratio_lte")
        except ScenarioPolicyMissing, ValueError:
            threshold = Decimal(0)
            local_missing.append("policy.parameters.trigger_ratio_lte")
        if local_missing:
            return _Decision(
                "BLOCKED", {}, tuple(sorted(set(local_missing))), ("MISSING_REQUIRED_INPUT",)
            )
        try:
            current = _decimal(facts[current_key], current_key)
            baseline = _decimal(facts[baseline_key], baseline_key)
            ratio = _ratio(current, baseline, output_key)
        except ValueError:
            return _Decision(
                "BLOCKED",
                {},
                (baseline_key,),
                ("INVALID_COMPARABLE_BASELINE",),
            )
        outputs: dict[str, JsonValue] = {
            current_key: _json_number(current),
            baseline_key: _json_number(baseline),
            output_key: _json_number(ratio),
            "cause_status": "unknown",
        }
        if ratio <= threshold:
            return _Decision("PROPOSED", outputs, reason_codes=("POLICY_TRIGGER_CONFIRMED",))
        return _Decision("NO_ACTION", outputs, reason_codes=("POLICY_TRIGGER_NOT_MET",))

    def _run_scn_001(
        self, input_: ScenarioInput, facts: dict[str, JsonValue], missing: tuple[str, ...]
    ) -> _Decision:
        return self._drop_decision(
            input_,
            facts,
            missing,
            current_key="sales_current",
            baseline_key="sales_baseline",
            output_key="sales_delta_ratio",
        )

    def _run_scn_002(
        self, input_: ScenarioInput, facts: dict[str, JsonValue], missing: tuple[str, ...]
    ) -> _Decision:
        return self._drop_decision(
            input_,
            facts,
            missing,
            current_key="orders_current",
            baseline_key="orders_baseline",
            output_key="orders_delta_ratio",
        )

    @staticmethod
    def _contribution_profit(facts: dict[str, JsonValue]) -> Decimal:
        values = {key: _decimal(facts[key], key) for key in _PNL_COMPONENTS}
        return values["revenue"] - sum(
            (values[key] for key in _PNL_COMPONENTS if key != "revenue"), Decimal(0)
        )

    def _run_scn_003(
        self, input_: ScenarioInput, facts: dict[str, JsonValue], missing: tuple[str, ...]
    ) -> _Decision:
        local_missing = list(missing)
        if "policy.parameters.formula" in local_missing:
            reason = "MISSING_PNL_INPUT"
        else:
            reason = "MISSING_REQUIRED_INPUT"
        try:
            threshold = self._threshold(input_, "trigger_ratio_lte")
        except ScenarioPolicyMissing, ValueError:
            threshold = Decimal(0)
            local_missing.append("policy.parameters.trigger_ratio_lte")
        if local_missing:
            return _Decision("BLOCKED", {}, tuple(sorted(set(local_missing))), (reason,))
        try:
            current = self._contribution_profit(facts)
            baseline = _decimal(
                facts["contribution_profit_baseline"], "contribution_profit_baseline"
            )
            ratio = _ratio(current, baseline, "contribution_profit")
        except ValueError:
            return _Decision(
                "BLOCKED",
                {},
                ("contribution_profit_baseline",),
                ("INVALID_COMPARABLE_BASELINE",),
            )
        outputs: dict[str, JsonValue] = {
            "contribution_profit": _json_number(current),
            "contribution_profit_baseline": _json_number(baseline),
            "contribution_profit_delta_ratio": _json_number(ratio),
            "formula": _PNL_FORMULA,
        }
        status: ScenarioStatus = "PROPOSED" if ratio <= threshold else "NO_ACTION"
        code = "POLICY_TRIGGER_CONFIRMED" if status == "PROPOSED" else "POLICY_TRIGGER_NOT_MET"
        return _Decision(status, outputs, reason_codes=(code,))

    def _run_scn_004(
        self, input_: ScenarioInput, facts: dict[str, JsonValue], missing: tuple[str, ...]
    ) -> _Decision:
        local_missing = list(missing)
        try:
            threshold = self._threshold(input_, "trigger_ratio_lte")
        except ScenarioPolicyMissing, ValueError:
            threshold = Decimal(0)
            local_missing.append("policy.parameters.trigger_ratio_lte")
        if local_missing:
            return _Decision(
                "BLOCKED", {}, tuple(sorted(set(local_missing))), ("MISSING_PNL_INPUT",)
            )
        try:
            profit = self._contribution_profit(facts)
            revenue = _decimal(facts["revenue"], "revenue")
            baseline = _decimal(facts["margin_baseline"], "margin_baseline")
            if revenue == 0:
                raise ValueError("revenue cannot be zero")
            margin = profit / revenue
            ratio = _ratio(margin, baseline, "contribution_margin")
        except ValueError:
            return _Decision(
                "BLOCKED", {}, ("revenue|margin_baseline",), ("INVALID_COMPARABLE_BASELINE",)
            )
        outputs: dict[str, JsonValue] = {
            "contribution_profit": _json_number(profit),
            "contribution_margin": _json_number(margin),
            "margin_baseline": _json_number(baseline),
            "margin_delta_ratio": _json_number(ratio),
            "formula": _PNL_FORMULA,
            "effect_status": "potential",
        }
        status: ScenarioStatus = "PROPOSED" if ratio <= threshold else "NO_ACTION"
        code = "POLICY_TRIGGER_CONFIRMED" if status == "PROPOSED" else "POLICY_TRIGGER_NOT_MET"
        return _Decision(status, outputs, reason_codes=(code,))

    @staticmethod
    def _stock_outputs(facts: dict[str, JsonValue]) -> tuple[dict[str, JsonValue], list[str]]:
        missing: list[str] = []
        stock = facts.get("stock")
        if not isinstance(stock, dict):
            return {}, ["stock"]
        for state in _STOCK_STATES:
            value = stock.get(state)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                missing.append(f"stock.{state}")
        sellable = stock.get("SELLABLE")
        if isinstance(sellable, bool) or not isinstance(sellable, (int, float)):
            return {}, missing
        outputs: dict[str, JsonValue] = {
            "sellable_stock": sellable,
            "non_sellable_stock": {
                "IN_TRANSIT": cast(JsonValue, stock.get("IN_TRANSIT")),
                "CLIENT_WAREHOUSE": cast(JsonValue, stock.get("CLIENT_WAREHOUSE")),
                "PLANNED": cast(JsonValue, stock.get("PLANNED")),
            },
        }
        demand = facts.get("demand_per_day")
        if isinstance(demand, bool) or not isinstance(demand, (int, float)) or demand <= 0:
            missing.append("demand_per_day")
        else:
            outputs["days_cover"] = float(Decimal(str(sellable)) / Decimal(str(demand)))
        return outputs, missing

    def _run_scn_005(
        self, input_: ScenarioInput, facts: dict[str, JsonValue], missing: tuple[str, ...]
    ) -> _Decision:
        outputs, stock_missing = self._stock_outputs(facts)
        local_missing = list(missing) + stock_missing
        try:
            threshold = self._threshold(input_, "days_cover_lte")
        except ScenarioPolicyMissing, ValueError:
            threshold = Decimal(0)
            local_missing.append("policy.parameters.days_cover_lte")
        if local_missing:
            return _Decision(
                "BLOCKED",
                outputs,
                tuple(sorted(set(local_missing))),
                ("SELLABLE_STOCK_OR_SUPPLY_INPUT_MISSING",),
            )
        days_cover = _decimal(outputs["days_cover"], "days_cover")
        status: ScenarioStatus = "PROPOSED" if days_cover <= threshold else "NO_ACTION"
        code = "POLICY_TRIGGER_CONFIRMED" if status == "PROPOSED" else "POLICY_TRIGGER_NOT_MET"
        return _Decision(status, outputs, reason_codes=(code,))

    def _run_scn_006(
        self, input_: ScenarioInput, facts: dict[str, JsonValue], missing: tuple[str, ...]
    ) -> _Decision:
        outputs, stock_missing = self._stock_outputs(facts)
        local_missing = list(missing) + stock_missing
        try:
            threshold = self._threshold(input_, "days_cover_gte")
        except ScenarioPolicyMissing, ValueError:
            threshold = Decimal(0)
            local_missing.append("policy.parameters.days_cover_gte")
        if local_missing:
            return _Decision(
                "BLOCKED",
                outputs,
                tuple(sorted(set(local_missing))),
                ("OVERSTOCK_CONTEXT_MISSING",),
            )
        outputs.update(
            {
                "seasonality": facts["seasonality"],
                "storage_exposure": facts["storage_exposure"],
                "contribution_margin": facts["contribution_margin"],
                "effect_status": "potential",
            }
        )
        days_cover = _decimal(outputs["days_cover"], "days_cover")
        status: ScenarioStatus = "PROPOSED" if days_cover >= threshold else "NO_ACTION"
        code = "POLICY_TRIGGER_CONFIRMED" if status == "PROPOSED" else "POLICY_TRIGGER_NOT_MET"
        return _Decision(status, outputs, reason_codes=(code,))

    def _run_scn_007(
        self, input_: ScenarioInput, facts: dict[str, JsonValue], missing: tuple[str, ...]
    ) -> _Decision:
        local_missing = list(missing)
        if input_.policy is None:
            return _Decision(
                "BLOCKED",
                {},
                (f"policy:{input_.policy_version}",),
                ("SCENARIO_POLICY_MISSING",),
            )
        experiment = input_.policy.parameters.get("experiment")
        required_experiment = (
            "variable",
            "baseline",
            "success_criterion",
            "stop_criterion",
            "rollback_criterion",
            "exposure_limit",
        )
        if not isinstance(experiment, dict):
            local_missing.extend(f"experiment.{field}" for field in required_experiment)
            experiment_dict: dict[str, JsonValue] = {}
        else:
            experiment_dict = experiment
            local_missing.extend(
                f"experiment.{field}" for field in required_experiment if not experiment.get(field)
            )
        if facts.get("attribution_mature") is not True:
            local_missing.append("attribution_mature")
        try:
            threshold = self._threshold(input_, "trigger_ratio_gte")
        except ScenarioPolicyMissing, ValueError:
            threshold = Decimal(0)
            local_missing.append("policy.parameters.trigger_ratio_gte")
        if local_missing:
            return _Decision(
                "BLOCKED", {}, tuple(sorted(set(local_missing))), ("ADS_EXPERIMENT_NOT_READY",)
            )
        try:
            current = _decimal(facts["drr_current"], "drr_current")
            baseline = _decimal(facts["drr_baseline"], "drr_baseline")
            ratio = _ratio(current, baseline, "drr")
        except ValueError:
            return _Decision("BLOCKED", {}, ("drr_baseline",), ("INVALID_COMPARABLE_BASELINE",))
        outputs: dict[str, JsonValue] = {
            "drr_current": _json_number(current),
            "drr_baseline": _json_number(baseline),
            "drr_delta_ratio": _json_number(ratio),
            "attribution_mature": True,
            "experiment_draft": experiment_dict,
            "effect_status": "potential",
        }
        status: ScenarioStatus = "PROPOSED" if ratio >= threshold else "NO_ACTION"
        code = "POLICY_TRIGGER_CONFIRMED" if status == "PROPOSED" else "POLICY_TRIGGER_NOT_MET"
        return _Decision(status, outputs, reason_codes=(code,))

    @staticmethod
    def _run_scn_008(
        input_: ScenarioInput, facts: dict[str, JsonValue], missing: tuple[str, ...]
    ) -> _Decision:
        del input_
        if missing:
            return _Decision("BLOCKED", {}, missing, ("DATA_QUALITY_MAPPING_MISSING",))
        return _Decision(
            "NO_ACTION",
            {"quality_status": "ready", "quality_fact": facts.get("data_quality")},
            reason_codes=("DATA_QUALITY_READY",),
        )

    @staticmethod
    def _result(
        input_: ScenarioInput,
        status: ScenarioStatus,
        trigger_fingerprint: str,
        facts_fingerprint: str,
        evidence_hash: str,
        decision_state_fingerprint: str,
        material_refs: tuple[SourceRef, ...],
        outputs: dict[str, JsonValue],
        missing: tuple[str, ...],
        reason_codes: tuple[str, ...],
    ) -> DeterministicScenarioResult:
        policy = input_.policy
        counter_sources = set()
        if policy is not None:
            configured = policy.parameters.get("counterevidence_sources", [])
            if isinstance(configured, list):
                counter_sources = {item for item in configured if isinstance(item, str)}
        counter_ids = tuple(
            ref.source_ref_id for ref in material_refs if ref.source in counter_sources
        )
        evidence_ids = tuple(
            ref.source_ref_id
            for ref in material_refs
            if ref.quality == "fresh" and ref.source not in counter_sources
        )
        state_trace = (
            ("SIGNAL", "ANALYSIS", "RECOMMENDATION_DRAFT", "REVIEW_PENDING", "TERMINAL")
            if status == "PROPOSED"
            else ("SIGNAL", "ANALYSIS", "TERMINAL")
        )
        return DeterministicScenarioResult(
            scenario_id=input_.scenario_id,
            status=status,
            trigger_fingerprint=trigger_fingerprint,
            facts_fingerprint=facts_fingerprint,
            evidence_hash=evidence_hash,
            decision_state_fingerprint=decision_state_fingerprint,
            deterministic_inputs={
                "snapshot_id": input_.snapshot.snapshot_id,
                "snapshot_checksum": input_.snapshot.checksum,
                "policy_version": input_.policy_version,
                "source_ref_ids": [ref.source_ref_id for ref in material_refs],
            },
            deterministic_outputs={**outputs, "model_called": False},
            evidence_ref_ids=evidence_ids,
            counterevidence_ref_ids=counter_ids,
            missing_data=missing,
            reason_codes=reason_codes,
            state_trace=state_trace,
        )
