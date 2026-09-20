from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from proxima.ai.contracts import (
    ActionContractDraft,
    ClientContext,
    ContextEnvelope,
    CycleRequest,
    DecisionMemoryRef,
    ScenarioInput,
    ScenarioPolicy,
    SnapshotRef,
    SourceRef,
    VersionedKnowledge,
)

NOW = datetime(2026, 8, 9, 20, 59, 59, tzinfo=UTC)


def _source(**overrides: object) -> SourceRef:
    values: dict[str, object] = {
        "source_ref_id": "ref-sales",
        "client_id": "SYNTH-LAB-01",
        "cabinet_id": "SYNTH-CAB-WB-01",
        "snapshot_id": "SYNTH-SNAP-0001",
        "source": "sales_current",
        "retrieved_at": NOW,
        "period": "2026-08-09",
        "locator": "analytics.v_sku_daily:metric_date=2026-08-09",
        "value": 80,
        "quality": "fresh",
        "run_id": "SYNTH-RUN-0001",
    }
    values.update(overrides)
    return SourceRef(**values)


def _snapshot(**overrides: object) -> SnapshotRef:
    values: dict[str, object] = {
        "snapshot_id": "SYNTH-SNAP-0001",
        "client_id": "SYNTH-LAB-01",
        "cabinet_id": "SYNTH-CAB-WB-01",
        "marketplace": "WB",
        "data_as_of": NOW,
        "status": "ready",
        "passport_version": "SYNTH-PASSPORT-0.1",
        "data_contract_version": "SYNTH-CONTRACT-0.1",
        "schema_version": "SYNTH-SCHEMA-0.1",
        "checksum": "abc123",
        "source_permission_ref": "SYNTH://no-external-source",
        "data_mode": "synthetic",
    }
    values.update(overrides)
    return SnapshotRef(**values)


def _context(**client_values: object) -> ContextEnvelope:
    return ContextEnvelope(
        snapshot_id="SYNTH-SNAP-0001",
        global_knowledge=VersionedKnowledge(
            version="SYNTH-METHODOLOGY-0.1", values={"scope": "engineering_only"}
        ),
        client_context=ClientContext(
            version="SYNTH-PASSPORT-0.1",
            passport_version="SYNTH-PASSPORT-0.1",
            client_id="SYNTH-LAB-01",
            cabinet_id="SYNTH-CAB-WB-01",
            values={"scope": ["shadow_read_only_analytics"], **client_values},
        ),
        operational_data=(_source(),),
        decision_memory=(
            DecisionMemoryRef(
                event_id="event-1",
                client_id="SYNTH-LAB-01",
                cabinet_id="SYNTH-CAB-WB-01",
                scenario_id="SCN-001",
                version="1",
                locator="proxima.ai_decision_memory:event-1",
                decision_state="closed",
                content_hash="hash-1",
            ),
        ),
        methodology_version="SYNTH-METHODOLOGY-0.1",
        kpi_formula_version="SYNTH-FORMULA-0.1",
        permission_version="SYNTH-PERMISSION-0.1",
    )


def _policy() -> ScenarioPolicy:
    return ScenarioPolicy(
        scenario_id="SCN-001",
        version="SYNTH-POLICY-0.1",
        formula_version="SYNTH-FORMULA-0.1",
        permission_version="SYNTH-PERMISSION-0.1",
        source_ref_ids=("ref-sales",),
        required_sources=("sales_current",),
        parameters={"trigger_ratio_lte": -0.1},
        risk_level="R0",
        owner="account-manager",
        review_at=NOW,
        recommendation_code="REVIEW_SALES_DROP",
        expected_result="Validate the bounded sales observation",
        do_nothing="Keep the frozen baseline unchanged",
    )


def test_source_ref_requires_complete_tenant_scope_utc_and_forbids_extras() -> None:
    assert _source().retrieved_at.tzinfo == UTC
    with pytest.raises(ValidationError, match="timezone"):
        _source(retrieved_at=datetime(2026, 8, 9, 20, 59, 59))
    with pytest.raises(ValidationError):
        _source(extra=True)
    with pytest.raises(ValidationError, match="secret"):
        _source(value={"api_token": "not-a-real-secret"})


@pytest.mark.parametrize(
    "transient", ["signals", "incidents", "tasks", "recommendations", "outcomes"]
)
def test_client_context_rejects_transient_operational_records(transient: str) -> None:
    with pytest.raises(ValidationError, match="transient"):
        _context(**{transient: []})


def test_context_keeps_four_versioned_namespaces_and_rejects_cross_tenant_memory() -> None:
    envelope = _context()
    assert envelope.global_knowledge.version == envelope.methodology_version
    assert envelope.client_context.passport_version == "SYNTH-PASSPORT-0.1"
    assert envelope.operational_data[0].source_ref_id == "ref-sales"
    assert envelope.decision_memory[0].event_id == "event-1"

    bad_memory = envelope.decision_memory[0].model_copy(update={"client_id": "SYNTH-OTHER"})
    with pytest.raises(ValidationError, match="Decision Memory"):
        ContextEnvelope(**{**envelope.model_dump(), "decision_memory": (bad_memory,)})


def test_context_rejects_duplicate_source_ref_ids_and_semantic_locators() -> None:
    duplicate_id = _source(source="sales_baseline", value=100)
    with pytest.raises(ValidationError, match="DUPLICATE_SOURCE_REF_ID"):
        ContextEnvelope(
            **{
                **_context().model_dump(),
                "operational_data": (_source(), duplicate_id),
            }
        )

    duplicate_locator = _source(
        source_ref_id="ref-sales-copy",
        value=81,
    )
    with pytest.raises(ValidationError, match="DUPLICATE_SOURCE_SEMANTIC_LOCATOR"):
        ContextEnvelope(
            **{
                **_context().model_dump(),
                "operational_data": (_source(), duplicate_locator),
            }
        )


def test_synthetic_policy_cannot_cross_into_real_snapshot() -> None:
    real_source = _source(
        client_id="REAL-CLIENT",
        cabinet_id="REAL-CABINET",
        snapshot_id="REAL-SNAPSHOT",
        locator="analytics.v_sku_daily:real",
    )
    context = ContextEnvelope(
        snapshot_id="REAL-SNAPSHOT",
        global_knowledge=VersionedKnowledge(version="method-v1", values={}),
        client_context=ClientContext(
            version="passport-v1",
            passport_version="passport-v1",
            client_id="REAL-CLIENT",
            cabinet_id="REAL-CABINET",
            values={"scope": ["shadow_read_only_analytics"]},
        ),
        operational_data=(real_source,),
        decision_memory=(),
        methodology_version="method-v1",
        kpi_formula_version="formula-v1",
        permission_version="permission-v1",
    )
    with pytest.raises(ValidationError, match="synthetic policy"):
        ScenarioInput(
            scenario_id="SCN-001",
            snapshot=_snapshot(
                snapshot_id="REAL-SNAPSHOT",
                client_id="REAL-CLIENT",
                cabinet_id="REAL-CABINET",
                passport_version="passport-v1",
                data_contract_version="contract-v1",
                schema_version="schema-v1",
                checksum="real-checksum",
                source_permission_ref="permission://real-v1",
                data_mode="real",
            ),
            context=context,
            policy_version="SYNTH-POLICY-0.1",
            policy=_policy(),
        )


def test_cycle_request_rejects_duplicate_scenarios_and_action_has_no_execution_fields() -> None:
    with pytest.raises(ValidationError, match="unique"):
        CycleRequest(
            actor="ai-operations",
            correlation_id="corr-1",
            client_id="SYNTH-LAB-01",
            cabinet_id="SYNTH-CAB-WB-01",
            snapshot_id="SYNTH-SNAP-0001",
            mode="shadow",
            scenario_ids=("SCN-001", "SCN-001"),
            workflow_version="SYNTH-WORKFLOW-0.1",
        )

    payload = {
        "action_contract_id": "action-1",
        "version": 1,
        "client_id": "SYNTH-LAB-01",
        "cabinet_id": "SYNTH-CAB-WB-01",
        "snapshot_id": "SYNTH-SNAP-0001",
        "scenario_id": "SCN-001",
        "state": "review_pending",
        "domain": "sales",
        "trigger_fingerprint": "trigger-hash",
        "facts_fingerprint": "facts-hash",
        "evidence_hash": "evidence-hash",
        "decision_state_fingerprint": "decision-hash",
        "risk_level": "R0",
        "policy_version": "SYNTH-POLICY-0.1",
        "permission_version": "SYNTH-PERMISSION-0.1",
        "evidence_ref_ids": ("ref-sales",),
        "counterevidence_ref_ids": (),
        "missing_data": (),
        "recommendation_code": "REVIEW_SALES_DROP",
        "expected_result": "Validate the bounded sales observation",
        "review_at": NOW,
        "owner": "account-manager",
        "client_dependency": None,
        "do_nothing": "Keep the frozen baseline unchanged",
        "requires_human": True,
        "reversible": False,
    }
    assert ActionContractDraft(**payload).requires_human is True
    with pytest.raises(ValidationError):
        ActionContractDraft(**{**payload, "executable_payload": {"bid": 1}})
    with pytest.raises(ValidationError, match="human"):
        ActionContractDraft(**{**payload, "requires_human": False})


def test_unversioned_policy_and_context_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ScenarioPolicy(
            scenario_id="SCN-001",
            version="",
            formula_version="",
            permission_version="",
            source_ref_ids=("ref-sales",),
            required_sources=("sales_current",),
            parameters={},
            risk_level="R0",
            owner="account-manager",
            recommendation_code="REVIEW_SALES_DROP",
            do_nothing="Wait",
        )
    with pytest.raises(ValidationError):
        VersionedKnowledge(version="", values={})
