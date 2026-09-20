from __future__ import annotations

from datetime import UTC, datetime

import pytest

from proxima.ai.contracts import (
    ClientContext,
    ContextEnvelope,
    DecisionMemoryRef,
    OpenActionContractRef,
    ScenarioInput,
    ScenarioPolicy,
    SnapshotRef,
    SourceRef,
    VersionedKnowledge,
)
from proxima.application.scenario_engine import ScenarioEngine

NOW = datetime(2026, 8, 9, 20, 59, 59, tzinfo=UTC)
CLIENT_ID = "SYNTH-LAB-01"
CABINET_ID = "SYNTH-CAB-WB-01"
SNAPSHOT_ID = "SYNTH-SNAP-0001"
POLICY_VERSION = "SYNTH-POLICY-0.1"
FORMULA_VERSION = "SYNTH-FORMULA-0.1"
PERMISSION_VERSION = "SYNTH-PERMISSION-0.1"


def _ref(name: str, value: object, quality: str = "fresh") -> SourceRef:
    return SourceRef(
        source_ref_id=f"ref-{name}",
        client_id=CLIENT_ID,
        cabinet_id=CABINET_ID,
        snapshot_id=SNAPSHOT_ID,
        source=name,
        trust_class="policy" if name == "policy" else "analytics",
        retrieved_at=NOW,
        period="2026-08-09",
        locator=(
            f"policy:{POLICY_VERSION}" if name == "policy" else f"analytics.v_sku_daily:{name}"
        ),
        value=value,
        quality=quality,
        run_id="SYNTH-RUN-0001",
    )


def _policy(
    scenario_id: str,
    required_sources: tuple[str, ...],
    parameters: dict[str, object],
) -> ScenarioPolicy:
    return ScenarioPolicy(
        scenario_id=scenario_id,
        version=POLICY_VERSION,
        formula_version=FORMULA_VERSION,
        permission_version=PERMISSION_VERSION,
        source_ref_ids=("ref-policy",),
        required_sources=required_sources,
        parameters=parameters,
        risk_level="R0",
        owner="account-manager",
        review_at=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        recommendation_code=f"REVIEW_{scenario_id}",
        expected_result=f"Validate {scenario_id} against the frozen snapshot",
        do_nothing="Keep the frozen baseline unchanged",
    )


def _input(
    scenario_id: str,
    refs: tuple[SourceRef, ...],
    *,
    policy: ScenarioPolicy | None,
    snapshot_status: str = "ready",
    open_contracts: tuple[OpenActionContractRef, ...] = (),
    memory: tuple[DecisionMemoryRef, ...] = (),
) -> ScenarioInput:
    snapshot = SnapshotRef(
        snapshot_id=SNAPSHOT_ID,
        client_id=CLIENT_ID,
        cabinet_id=CABINET_ID,
        marketplace="WB",
        data_as_of=NOW,
        status=snapshot_status,
        passport_version="SYNTH-PASSPORT-0.1",
        data_contract_version="SYNTH-CONTRACT-0.1",
        schema_version="SYNTH-SCHEMA-0.1",
        checksum="snapshot-checksum",
        source_permission_ref="SYNTH://no-external-source",
        data_mode="synthetic",
    )
    context = ContextEnvelope(
        snapshot_id=SNAPSHOT_ID,
        global_knowledge=VersionedKnowledge(
            version="SYNTH-METHODOLOGY-0.1", values={"scope": "engineering_only"}
        ),
        client_context=ClientContext(
            version="SYNTH-PASSPORT-0.1",
            passport_version="SYNTH-PASSPORT-0.1",
            client_id=CLIENT_ID,
            cabinet_id=CABINET_ID,
            values={"scope": ["shadow_read_only_analytics"]},
        ),
        operational_data=refs,
        decision_memory=memory,
        methodology_version="SYNTH-METHODOLOGY-0.1",
        kpi_formula_version=FORMULA_VERSION,
        permission_version=PERMISSION_VERSION,
    )
    return ScenarioInput(
        scenario_id=scenario_id,
        snapshot=snapshot,
        context=context,
        policy_version=policy.version if policy else POLICY_VERSION,
        policy=policy,
        open_contracts=open_contracts,
    )


def _full_pnl() -> tuple[SourceRef, ...]:
    return (
        _ref("policy", {"version": POLICY_VERSION}),
        _ref("revenue", 1000),
        _ref("cogs", 400),
        _ref("marketplace_commission", 100),
        _ref("logistics", 50),
        _ref("paid_storage", 20),
        _ref("advertising_spend", 80),
        _ref("returns_cost", 50),
        _ref("contribution_profit_baseline", 400),
        _ref("margin_baseline", 0.4),
    )


def test_registry_contains_eight_distinct_application_owned_handlers() -> None:
    engine = ScenarioEngine()
    assert set(engine.handlers) == {f"SCN-{number:03d}" for number in range(1, 9)}
    assert len({handler.__name__ for handler in engine.handlers.values()}) == 8


@pytest.mark.parametrize(
    ("scenario_id", "refs", "required", "parameters", "expected_status", "output_key"),
    [
        (
            "SCN-001",
            (_ref("policy", {}), _ref("sales_current", 80), _ref("sales_baseline", 100)),
            ("sales_current", "sales_baseline"),
            {"trigger_ratio_lte": -0.1},
            "PROPOSED",
            "sales_delta_ratio",
        ),
        (
            "SCN-002",
            (_ref("policy", {}), _ref("orders_current", 80), _ref("orders_baseline", 100)),
            ("orders_current", "orders_baseline"),
            {"trigger_ratio_lte": -0.1},
            "PROPOSED",
            "orders_delta_ratio",
        ),
        (
            "SCN-003",
            _full_pnl(),
            tuple(ref.source for ref in _full_pnl() if ref.source != "policy"),
            {
                "trigger_ratio_lte": -0.1,
                "formula": "revenue - cogs - marketplace_commission - logistics - paid_storage - advertising_spend - returns_cost",
            },
            "PROPOSED",
            "contribution_profit",
        ),
        (
            "SCN-004",
            _full_pnl(),
            tuple(ref.source for ref in _full_pnl() if ref.source != "policy"),
            {
                "trigger_ratio_lte": -0.1,
                "formula": "revenue - cogs - marketplace_commission - logistics - paid_storage - advertising_spend - returns_cost",
            },
            "PROPOSED",
            "contribution_margin",
        ),
        (
            "SCN-005",
            (
                _ref("policy", {}),
                _ref(
                    "stock",
                    {"SELLABLE": 10, "IN_TRANSIT": 100, "CLIENT_WAREHOUSE": 50, "PLANNED": 25},
                ),
                _ref("demand_per_day", 10),
                _ref("lead_time_days", 5),
                _ref("moq", 20),
                _ref("client_stock", 50),
            ),
            ("stock", "demand_per_day", "lead_time_days", "moq", "client_stock"),
            {"days_cover_lte": 3},
            "PROPOSED",
            "sellable_stock",
        ),
        (
            "SCN-006",
            (
                _ref("policy", {}),
                _ref(
                    "stock",
                    {"SELLABLE": 1000, "IN_TRANSIT": 0, "CLIENT_WAREHOUSE": 0, "PLANNED": 0},
                ),
                _ref("demand_per_day", 10),
                _ref("seasonality", "flat"),
                _ref("storage_exposure", 100),
                _ref("contribution_margin", 0.2),
            ),
            ("stock", "demand_per_day", "seasonality", "storage_exposure", "contribution_margin"),
            {"days_cover_gte": 90},
            "PROPOSED",
            "days_cover",
        ),
        (
            "SCN-007",
            (
                _ref("policy", {}),
                _ref("drr_current", 0.25),
                _ref("drr_baseline", 0.15),
                _ref("attribution_mature", True),
                _ref("stock", {"SELLABLE": 100}),
                _ref("contribution_margin", 0.3),
            ),
            ("drr_current", "drr_baseline", "attribution_mature", "stock", "contribution_margin"),
            {
                "trigger_ratio_gte": 0.5,
                "experiment": {
                    "variable": "bid",
                    "baseline": "frozen_campaign_baseline",
                    "success_criterion": "policy-defined primary metric improves",
                    "stop_criterion": "policy-defined stop condition",
                    "rollback_criterion": "restore frozen baseline",
                    "exposure_limit": "synthetic bounded exposure",
                },
            },
            "PROPOSED",
            "experiment_draft",
        ),
        (
            "SCN-008",
            (_ref("policy", {}), _ref("data_quality", {"status": "ready"})),
            ("data_quality",),
            {},
            "NO_ACTION",
            "quality_status",
        ),
    ],
)
def test_all_scenario_handlers_make_deterministic_policy_bound_decisions(
    scenario_id: str,
    refs: tuple[SourceRef, ...],
    required: tuple[str, ...],
    parameters: dict[str, object],
    expected_status: str,
    output_key: str,
) -> None:
    policy = _policy(scenario_id, required, parameters)
    result = ScenarioEngine().run(_input(scenario_id, refs, policy=policy))
    assert result.status == expected_status
    assert output_key in result.deterministic_outputs
    assert result.deterministic_outputs["model_called"] is False


def test_missing_policy_is_typed_blocked_not_an_exception() -> None:
    result = ScenarioEngine().run(_input("SCN-001", (_ref("sales_current", 80),), policy=None))
    assert result.status == "BLOCKED"
    assert result.reason_codes == ("SCENARIO_POLICY_MISSING",)
    assert "policy:SYNTH-POLICY-0.1" in result.missing_data


@pytest.mark.parametrize(
    ("scenario_id", "mandatory_source", "parameters"),
    [
        ("SCN-001", "sales_current", {"trigger_ratio_lte": -0.1}),
        ("SCN-002", "orders_current", {"trigger_ratio_lte": -0.1}),
        (
            "SCN-003",
            "revenue",
            {
                "trigger_ratio_lte": -0.1,
                "formula": "revenue - cogs - marketplace_commission - logistics - paid_storage - advertising_spend - returns_cost",
            },
        ),
        (
            "SCN-004",
            "revenue",
            {
                "trigger_ratio_lte": -0.1,
                "formula": "revenue - cogs - marketplace_commission - logistics - paid_storage - advertising_spend - returns_cost",
            },
        ),
        ("SCN-005", "stock", {"days_cover_lte": 3}),
        ("SCN-006", "seasonality", {"days_cover_gte": 90}),
        (
            "SCN-007",
            "drr_current",
            {
                "trigger_ratio_gte": 0.5,
                "experiment": {
                    "variable": "bid",
                    "baseline": "frozen",
                    "success_criterion": "improves",
                    "stop_criterion": "stop",
                    "rollback_criterion": "restore",
                    "exposure_limit": "bounded",
                },
            },
        ),
        ("SCN-008", "data_quality", {}),
    ],
)
def test_each_handler_blocks_when_policy_omits_mandatory_sources(
    scenario_id: str,
    mandatory_source: str,
    parameters: dict[str, object],
) -> None:
    policy = _policy(scenario_id, ("policy",), parameters)

    result = ScenarioEngine().run(_input(scenario_id, (_ref("policy", {}),), policy=policy))

    assert result.status == "BLOCKED"
    assert mandatory_source in result.missing_data
    assert "MISSING_REQUIRED_INPUT" in result.reason_codes or scenario_id in {
        "SCN-003",
        "SCN-004",
        "SCN-005",
        "SCN-006",
        "SCN-007",
        "SCN-008",
    }


def test_fingerprint_changes_with_value_quality_and_decision_state() -> None:
    policy = _policy("SCN-001", ("sales_current", "sales_baseline"), {"trigger_ratio_lte": -0.1})
    refs = (_ref("policy", {}), _ref("sales_current", 80), _ref("sales_baseline", 100))
    baseline = ScenarioEngine().run(_input("SCN-001", refs, policy=policy))
    changed_value = ScenarioEngine().run(
        _input(
            "SCN-001",
            (_ref("policy", {}), _ref("sales_current", 79), _ref("sales_baseline", 100)),
            policy=policy,
        )
    )
    changed_quality = ScenarioEngine().run(
        _input(
            "SCN-001",
            (_ref("policy", {}), _ref("sales_current", 80, "stale"), _ref("sales_baseline", 100)),
            policy=policy,
        )
    )
    memory = DecisionMemoryRef(
        event_id="event-open",
        client_id=CLIENT_ID,
        cabinet_id=CABINET_ID,
        scenario_id="SCN-001",
        version="2",
        locator="proxima.ai_decision_memory:event-open",
        decision_state="review_pending",
        content_hash="decision-content-hash",
    )
    changed_decision = ScenarioEngine().run(
        _input("SCN-001", refs, policy=policy, memory=(memory,))
    )

    assert (
        len(
            {
                baseline.trigger_fingerprint,
                changed_value.trigger_fingerprint,
                changed_quality.trigger_fingerprint,
                changed_decision.trigger_fingerprint,
            }
        )
        == 4
    )
    assert baseline.facts_fingerprint != changed_value.facts_fingerprint
    assert baseline.facts_fingerprint != changed_quality.facts_fingerprint
    assert baseline.decision_state_fingerprint != changed_decision.decision_state_fingerprint


def test_profit_and_margin_require_formula_cogs_and_every_pnl_component() -> None:
    policy = _policy(
        "SCN-003",
        ("revenue", "cogs", "marketplace_commission"),
        {"trigger_ratio_lte": -0.1},
    )
    result = ScenarioEngine().run(
        _input("SCN-003", (_ref("policy", {}), _ref("revenue", 1000)), policy=policy)
    )
    assert result.status == "BLOCKED"
    assert "cogs" in result.missing_data
    assert "policy.parameters.formula" in result.missing_data
    assert "MISSING_PNL_INPUT" in result.reason_codes


def test_stock_math_uses_sellable_only_and_never_counts_other_states() -> None:
    policy = _policy(
        "SCN-005",
        ("stock", "demand_per_day", "lead_time_days", "moq", "client_stock"),
        {"days_cover_lte": 3},
    )
    refs = (
        _ref("policy", {}),
        _ref("stock", {"SELLABLE": 10, "IN_TRANSIT": 100, "CLIENT_WAREHOUSE": 50, "PLANNED": 25}),
        _ref("demand_per_day", 10),
        _ref("lead_time_days", 5),
        _ref("moq", 20),
        _ref("client_stock", 50),
    )
    result = ScenarioEngine().run(_input("SCN-005", refs, policy=policy))
    assert result.deterministic_outputs["sellable_stock"] == 10
    assert result.deterministic_outputs["days_cover"] == 1.0
    assert result.deterministic_outputs["non_sellable_stock"] == {
        "IN_TRANSIT": 100,
        "CLIENT_WAREHOUSE": 50,
        "PLANNED": 25,
    }


def test_quality_failure_has_one_incident_owner_and_blocks_dependents() -> None:
    refs = (_ref("policy", {}), _ref("data_quality", {"root": "partial"}, "partial"))
    quality_policy = _policy("SCN-008", ("data_quality",), {})
    sales_policy = _policy("SCN-001", ("data_quality",), {"trigger_ratio_lte": -0.1})
    engine = ScenarioEngine()
    incident = engine.run(_input("SCN-008", refs, policy=quality_policy))
    dependent = engine.run(_input("SCN-001", refs, policy=sales_policy))
    assert incident.status == "INCIDENT"
    assert dependent.status == "BLOCKED"
    assert incident.reason_codes == dependent.reason_codes == ("DATA_QUALITY_NOT_READY",)


def test_open_contract_suppresses_same_facts_but_new_fact_creates_new_version_candidate() -> None:
    policy = _policy("SCN-001", ("sales_current", "sales_baseline"), {"trigger_ratio_lte": -0.1})
    refs = (_ref("policy", {}), _ref("sales_current", 80), _ref("sales_baseline", 100))
    engine = ScenarioEngine()
    first = engine.run(_input("SCN-001", refs, policy=policy))
    open_contract = OpenActionContractRef(
        contract_id="action-1",
        client_id=CLIENT_ID,
        cabinet_id=CABINET_ID,
        scenario_id="SCN-001",
        state="review_pending",
        version=1,
        trigger_fingerprint=first.trigger_fingerprint,
        facts_fingerprint=first.facts_fingerprint,
        evidence_hash=first.evidence_hash,
        decision_state_version="1",
    )
    duplicate = engine.run(_input("SCN-001", refs, policy=policy, open_contracts=(open_contract,)))
    new_fact = engine.run(
        _input(
            "SCN-001",
            (_ref("policy", {}), _ref("sales_current", 70), _ref("sales_baseline", 100)),
            policy=policy,
            open_contracts=(open_contract,),
        )
    )
    assert duplicate.status == "NO_ACTION"
    assert duplicate.reason_codes == ("DUPLICATE_OPEN_CONTRACT",)
    assert new_fact.status == "PROPOSED"
    assert new_fact.facts_fingerprint != open_contract.facts_fingerprint


def test_ads_requires_mature_attribution_and_complete_controlled_experiment() -> None:
    policy = _policy(
        "SCN-007",
        ("drr_current", "drr_baseline", "attribution_mature", "stock", "contribution_margin"),
        {"trigger_ratio_gte": 0.5, "experiment": {"variable": "bid"}},
    )
    refs = (
        _ref("policy", {}),
        _ref("drr_current", 0.25),
        _ref("drr_baseline", 0.15),
        _ref("attribution_mature", False),
        _ref("stock", {"SELLABLE": 100}),
        _ref("contribution_margin", 0.3),
    )
    result = ScenarioEngine().run(_input("SCN-007", refs, policy=policy))
    assert result.status == "BLOCKED"
    assert "attribution_mature" in result.missing_data
    assert "experiment.success_criterion" in result.missing_data
