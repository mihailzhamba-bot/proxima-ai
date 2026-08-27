from __future__ import annotations

import json
from pathlib import Path

import pytest

from proxima.evals.reference_replay import (
    COMMON_EDGE_CLASSES,
    PAIRED_EDGE_CLASSES,
    QA_DIMENSIONS,
    SCENARIO_IDS,
    ReferenceDataError,
    ReferenceDatasetLoader,
    ReferenceReplay,
    ReplayMode,
    ReplayOutput,
)

ROOT = Path(__file__).parents[3]
SCHEMA_PATH = ROOT / "evals/reference/schema.json"
CASES_PATH = ROOT / "evals/reference/cases.jsonl"


def _case(
    *,
    case_id: str = "case-001",
    split: str = "regression",
    provenance_kind: str = "deidentified_practitioner_case",
    deidentified: bool = True,
    second_actor: str = "reviewer-002",
    scenario_id: str = "SCN-003",
    edge_classes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "record_version": "1.0",
        "case_id": case_id,
        "dataset_version": "reference-2026-08-11-v1",
        "split": split,
        "scenario_id": scenario_id,
        "edge_classes": edge_classes or ["pnl", "data_quality"],
        "accepted_alternative_ids": ["ALT-UNKNOWN"],
        "provenance": {
            "kind": provenance_kind,
            "source_locator": "case-store://deidentified/case-001",
            "source_date": "2026-08-11",
            "collected_by": "practitioner-001",
            "approval_locator": "review://case-001/freeze",
            "deidentified": deidentified,
            "deidentification_method": "direct identifiers removed",
        },
        "frozen_input": {
            "snapshot_id": "snapshot-001",
            "snapshot_checksum": "sha256:snapshot-001",
            "input_hash": "sha256:input-001",
            "source_refs": [
                {
                    "source_ref_id": "ref-pnl-001",
                    "locator": "analytics.v_sku_pnl_daily:case-001",
                    "checksum": "sha256:ref-pnl-001",
                }
            ],
            "passport_version": "passport-v1",
            "policy_version": "policy-v1",
            "formula_version": "formula-v1",
            "prompt_version": "prompt-v1",
            "model_version": "offline-candidate-v1",
            "tool_versions": {"scenario_engine": "v1"},
            "open_decision_state_hash": "sha256:open-state-001",
        },
        "gold_labels": {
            "allowed_states": ["BLOCKED"],
            "allowed_causes": ["unknown"],
            "allowed_actions": ["request_missing_cogs"],
            "required_evidence_ref_ids": ["ref-pnl-001"],
            "forbidden_claims": ["profit_is_known"],
            "forbidden_actions": ["change_price"],
            "deterministic_calculations": [
                {
                    "calculation_id": "calc-pnl-completeness",
                    "formula_version": "formula-v1",
                    "expected_value": "BLOCKED_MISSING_COGS",
                    "source_ref_ids": ["ref-pnl-001"],
                }
            ],
            "primary_label": {
                "actor_id": "practitioner-001",
                "actor_role": "Account Manager",
                "source_ref": "review://case-001/primary",
                "labeled_at": "2026-08-11T09:00:00Z",
            },
            "second_review": {
                "actor_id": second_actor,
                "actor_role": "Independent reviewer",
                "source_ref": "review://case-001/second",
                "labeled_at": "2026-08-11T10:00:00Z",
            },
            "adjudication": {
                "status": "resolved",
                "disagreement_visible": True,
                "actor_id": "domain-adjudicator-001",
                "source_ref": "review://case-001/adjudication",
                "rationale": "Missing COGS blocks a profit claim.",
            },
        },
    }


def _write_jsonl(path: Path, *records: dict[str, object]) -> None:
    path.write_text("".join(f"{json.dumps(record)}\n" for record in records))


def _output(
    *,
    version: str,
    snapshot_checksum: str = "sha256:snapshot-001",
    state: str = "BLOCKED",
) -> ReplayOutput:
    return ReplayOutput(
        case_id="case-001",
        dataset_version="reference-2026-08-11-v1",
        candidate_version=version,
        snapshot_checksum=snapshot_checksum,
        input_hash="sha256:input-001",
        state=state,
        cause="unknown",
        action="request_missing_cogs",
        evidence_ref_ids=("ref-pnl-001",),
        claims=("cogs_missing",),
        attempted_actions=(),
        critical_failure_ids=(),
        human_override=False,
    )


def test_checked_in_empty_reference_set_is_schema_valid_and_blocks_e0() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    assert schema["$id"].endswith("reference-case.schema.json")
    assert set(schema["required"]) >= {
        "case_id",
        "dataset_version",
        "split",
        "provenance",
        "frozen_input",
        "gold_labels",
    }

    loader = ReferenceDatasetLoader.from_schema(SCHEMA_PATH)
    inventory = loader.load(CASES_PATH)

    assert inventory.cases == ()
    assert inventory.expert_case_count == 0
    assert inventory.e0_ready is False
    assert set(inventory.e0_blockers) == {
        "REFERENCE_PRACTITIONER_CASES_MISSING",
        *(f"REFERENCE_SCENARIO_MISSING:{scenario_id}" for scenario_id in SCENARIO_IDS),
        *(f"REFERENCE_PAIRED_EDGE_MISSING:{edge_class}" for edge_class in PAIRED_EDGE_CLASSES),
    }
    assert loader.load(CASES_PATH) == inventory


def test_loader_rejects_synthetic_case_outside_engineering_split(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    _write_jsonl(
        path,
        _case(split="holdout", provenance_kind="synthetic_generator"),
    )

    with pytest.raises(ReferenceDataError, match="SYNTHETIC_EXPERT_SPLIT_FORBIDDEN"):
        ReferenceDatasetLoader.from_schema(SCHEMA_PATH).load(path)


def test_one_scenario_and_partial_edge_matrix_never_marks_e0_ready(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    _write_jsonl(path, _case(edge_classes=[COMMON_EDGE_CLASSES[0]]))

    inventory = ReferenceDatasetLoader.from_schema(SCHEMA_PATH).load(path)

    expected = {
        *(
            f"REFERENCE_SCENARIO_MISSING:{scenario_id}"
            for scenario_id in SCENARIO_IDS
            if scenario_id != "SCN-003"
        ),
        *(
            f"REFERENCE_EDGE_CLASS_MISSING:SCN-003:{edge_class}"
            for edge_class in COMMON_EDGE_CLASSES[1:]
        ),
        *(f"REFERENCE_PAIRED_EDGE_MISSING:{edge_class}" for edge_class in PAIRED_EDGE_CLASSES),
    }
    assert inventory.e0_ready is False
    assert set(inventory.e0_blockers) == expected


def test_checked_in_reference_schema_is_generated_from_executable_contract(
    tmp_path: Path,
) -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    schema["title"] = "drifted schema"
    drifted = tmp_path / "schema.json"
    drifted.write_text(json.dumps(schema))

    with pytest.raises(ReferenceDataError, match="REFERENCE_SCHEMA_DRIFT"):
        ReferenceDatasetLoader.from_schema(drifted)


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"deidentified": False}, "DEIDENTIFICATION_REQUIRED"),
        ({"second_actor": "practitioner-001"}, "INDEPENDENT_SECOND_REVIEW_REQUIRED"),
    ],
)
def test_loader_rejects_missing_deidentification_or_independent_review(
    tmp_path: Path,
    change: dict[str, object],
    code: str,
) -> None:
    path = tmp_path / "cases.jsonl"
    _write_jsonl(path, _case(**change))

    with pytest.raises(ReferenceDataError, match=code):
        ReferenceDatasetLoader.from_schema(SCHEMA_PATH).load(path)


def test_holdout_cannot_be_loaded_for_tuning(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    _write_jsonl(path, _case(split="holdout"))

    with pytest.raises(ReferenceDataError, match="HOLDOUT_TUNING_FORBIDDEN"):
        ReferenceDatasetLoader.from_schema(SCHEMA_PATH).load(
            path,
            mode=ReplayMode.TUNING,
        )


def test_replay_reports_dimensions_and_slices_without_aggregate_score(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    _write_jsonl(path, _case())
    inventory = ReferenceDatasetLoader.from_schema(SCHEMA_PATH).load(path)

    report = ReferenceReplay().compare(
        inventory,
        candidate_outputs=(_output(version="candidate-v2"),),
        baseline_outputs=(_output(version="baseline-v1"),),
    )

    assert report.dataset_version == "reference-2026-08-11-v1"
    assert report.case_ids == ("case-001",)
    assert {result.dimension for result in report.results} == set(QA_DIMENSIONS)
    assert {result.scenario_id for result in report.results} == {"SCN-003"}
    assert {edge for result in report.results for edge in result.edge_classes} == {
        "pnl",
        "data_quality",
    }
    assert all(result.status == "PASS" for result in report.results)
    assert report.accepted_alternatives == {"case-001": ("ALT-UNKNOWN",)}
    assert "aggregate" not in report.model_dump_json().lower()


def test_replay_rejects_candidate_baseline_snapshot_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    _write_jsonl(path, _case())
    inventory = ReferenceDatasetLoader.from_schema(SCHEMA_PATH).load(path)

    with pytest.raises(ReferenceDataError, match="IMMUTABLE_COMPARISON_MISMATCH"):
        ReferenceReplay().compare(
            inventory,
            candidate_outputs=(_output(version="candidate-v2"),),
            baseline_outputs=(_output(version="baseline-v1", snapshot_checksum="sha256:other"),),
        )


@pytest.mark.parametrize(
    ("allowed_state", "candidate_state", "expected_error"),
    [
        ("NO_ACTION", "BLOCKED", "FALSE_POSITIVE"),
        ("BLOCKED", "NO_ACTION", "FALSE_NEGATIVE"),
    ],
)
def test_replay_keeps_false_positive_and_false_negative_separate(
    tmp_path: Path,
    allowed_state: str,
    candidate_state: str,
    expected_error: str,
) -> None:
    record = _case()
    record["gold_labels"]["allowed_states"] = [allowed_state]  # type: ignore[index]
    path = tmp_path / "cases.jsonl"
    _write_jsonl(path, record)
    inventory = ReferenceDatasetLoader.from_schema(SCHEMA_PATH).load(path)

    report = ReferenceReplay().compare(
        inventory,
        candidate_outputs=(_output(version="candidate-v2", state=candidate_state),),
        baseline_outputs=(_output(version="baseline-v1", state=allowed_state),),
    )

    detection = next(result for result in report.results if result.dimension == "detection")
    assert detection.error_taxonomy == (expected_error,)
    assert report.error_taxonomy[expected_error] == 1
