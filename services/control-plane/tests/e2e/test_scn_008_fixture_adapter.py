from __future__ import annotations

from pathlib import Path

from proxima.ai.contracts import (
    ContextEnvelope,
    CycleInputBundle,
    ScenarioInput,
    SnapshotRef,
)
from proxima.application.scenario_engine import ScenarioEngine


FIXTURE = Path(__file__).parents[1] / "fixtures/scenario_engine/scn_008_partial.json"


def _scenario_input(bundle: CycleInputBundle, scenario_id: str) -> ScenarioInput:
    request = bundle.request
    quality_not_ready = any(ref.quality != "fresh" for ref in bundle.operational_data)
    snapshot = SnapshotRef(
        snapshot_id=request.snapshot_id,
        client_id=request.client_id,
        cabinet_id=request.cabinet_id,
        marketplace="WB",
        data_as_of=max(ref.retrieved_at for ref in bundle.operational_data),
        status="partial" if quality_not_ready else "ready",
        passport_version=bundle.client_context.passport_version,
        data_contract_version="fixture-data-contract-0.1",
        schema_version="fixture-schema-0.1",
        checksum=f"fixture:{request.snapshot_id}",
        source_permission_ref="fixture://scenario-engine",
        data_mode="synthetic",
    )
    context = ContextEnvelope(
        snapshot_id=request.snapshot_id,
        global_knowledge=bundle.global_knowledge,
        client_context=bundle.client_context,
        operational_data=bundle.operational_data,
        decision_memory=(),
        methodology_version=bundle.methodology_version,
        kpi_formula_version=bundle.kpi_formula_version,
        permission_version=bundle.permission_version,
    )
    policy = next(item for item in bundle.scenario_policies if item.scenario_id == scenario_id)
    return ScenarioInput(
        scenario_id=scenario_id,
        snapshot=snapshot,
        context=context,
        policy_version=policy.version,
        policy=policy,
    )


def test_scn_008_partial_fixture_adapter_preserves_incident_boundary() -> None:
    bundle = CycleInputBundle.model_validate_json(FIXTURE.read_text())
    scenario = _scenario_input(bundle, "SCN-008")

    first = ScenarioEngine().run(scenario)
    second = ScenarioEngine().run(scenario)

    assert first == second
    assert first.status == "INCIDENT"
    assert first.reason_codes == ("DATA_QUALITY_NOT_READY",)
    assert first.deterministic_outputs["quality_status"] == "partial"
    assert first.deterministic_outputs["model_called"] is False
    assert first.evidence_ref_ids == ()
