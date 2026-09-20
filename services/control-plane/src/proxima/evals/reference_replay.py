"""Strict offline replay for frozen, practitioner-reviewed reference cases."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

QA_DIMENSIONS = (
    "detection",
    "diagnosis",
    "recommendation",
    "safety",
    "evidence",
    "actionability",
)
SCENARIO_IDS = (
    "SCN-001",
    "SCN-002",
    "SCN-003",
    "SCN-004",
    "SCN-005",
    "SCN-006",
    "SCN-007",
    "SCN-008",
)
# EVALS.md 4.2: every scenario needs each common class. The numeric number of
# independent fixtures remains owner-approved/TBD and is intentionally not inferred here.
COMMON_EDGE_CLASSES = (
    "confirmed_signal",
    "no_action",
    "missing_mandatory_data",
    "stale_data",
    "conflicting_sources",
    "alternative_cause",
    "boundary_value",
    "client_exception",
    "unsafe_recommendation",
    "unknown_cause",
)
PAIRED_EDGE_CLASSES = (
    "paired_data_quality",
    "paired_stock_state",
    "paired_pnl_completeness",
    "paired_ads_maturity",
    "paired_decision_state",
    "paired_tenant_binding",
)

ScenarioId = Literal[
    "SCN-001",
    "SCN-002",
    "SCN-003",
    "SCN-004",
    "SCN-005",
    "SCN-006",
    "SCN-007",
    "SCN-008",
]
Split = Literal["engineering", "calibration", "regression", "holdout", "production_replay"]
TerminalState = Literal[
    "NO_ACTION",
    "ACTIONS_READY",
    "AWAITING_APPROVAL",
    "BLOCKED",
    "INCIDENT",
]


class ReferenceDataError(ValueError):
    """A frozen case or comparison violates the reference-data boundary."""


class ReplayMode(StrEnum):
    EVALUATION = "evaluation"
    TUNING = "tuning"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Provenance(_StrictModel):
    kind: Literal["deidentified_practitioner_case", "synthetic_generator"]
    source_locator: str = Field(min_length=1)
    source_date: date
    collected_by: str = Field(min_length=1)
    approval_locator: str = Field(min_length=1)
    deidentified: bool
    deidentification_method: str = Field(min_length=1)


class FrozenSourceRef(_StrictModel):
    source_ref_id: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    checksum: str = Field(min_length=1)


class FrozenInput(_StrictModel):
    snapshot_id: str = Field(min_length=1)
    snapshot_checksum: str = Field(min_length=1)
    input_hash: str = Field(min_length=1)
    source_refs: tuple[FrozenSourceRef, ...] = Field(min_length=1)
    passport_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    formula_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    tool_versions: dict[str, str]
    open_decision_state_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def versions_and_refs_are_unique(self) -> FrozenInput:
        if not self.tool_versions or any(
            not key or not value for key, value in self.tool_versions.items()
        ):
            raise ValueError("TOOL_VERSIONS_REQUIRED")
        ref_ids = [item.source_ref_id for item in self.source_refs]
        if len(ref_ids) != len(set(ref_ids)):
            raise ValueError("DUPLICATE_SOURCE_REF")
        return self


class LabelReview(_StrictModel):
    actor_id: str = Field(min_length=1)
    actor_role: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    labeled_at: datetime


class Adjudication(_StrictModel):
    status: Literal["not_required", "pending", "resolved"]
    disagreement_visible: Literal[True]
    actor_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class DeterministicCalculation(_StrictModel):
    calculation_id: str = Field(min_length=1)
    formula_version: str = Field(min_length=1)
    expected_value: JsonValue
    source_ref_ids: tuple[str, ...] = Field(min_length=1)


class GoldLabels(_StrictModel):
    allowed_states: tuple[TerminalState, ...] = Field(min_length=1)
    allowed_causes: tuple[str, ...] = Field(min_length=1)
    allowed_actions: tuple[str, ...] = Field(min_length=1)
    required_evidence_ref_ids: tuple[str, ...] = Field(min_length=1)
    forbidden_claims: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    deterministic_calculations: tuple[DeterministicCalculation, ...] = Field(min_length=1)
    primary_label: LabelReview
    second_review: LabelReview
    adjudication: Adjudication

    @model_validator(mode="after")
    def independent_review_is_mandatory(self) -> GoldLabels:
        if self.primary_label.actor_id == self.second_review.actor_id:
            raise ValueError("INDEPENDENT_SECOND_REVIEW_REQUIRED")
        return self


class ReferenceCase(_StrictModel):
    record_version: Literal["1.0"]
    case_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    split: Split
    scenario_id: ScenarioId
    edge_classes: tuple[str, ...] = Field(min_length=1)
    accepted_alternative_ids: tuple[str, ...]
    provenance: Provenance
    frozen_input: FrozenInput
    gold_labels: GoldLabels

    @model_validator(mode="after")
    def split_and_provenance_are_safe(self) -> ReferenceCase:
        if not self.provenance.deidentified:
            raise ValueError("DEIDENTIFICATION_REQUIRED")
        if self.provenance.kind == "synthetic_generator" and self.split != "engineering":
            raise ValueError("SYNTHETIC_EXPERT_SPLIT_FORBIDDEN")
        if self.provenance.kind != "synthetic_generator" and self.split == "engineering":
            raise ValueError("PRACTITIONER_CASE_IN_ENGINEERING_SPLIT")
        frozen_ids = {item.source_ref_id for item in self.frozen_input.source_refs}
        required_ids = set(self.gold_labels.required_evidence_ref_ids)
        calculation_ids = {
            ref_id
            for calculation in self.gold_labels.deterministic_calculations
            for ref_id in calculation.source_ref_ids
        }
        if not required_ids.issubset(frozen_ids) or not calculation_ids.issubset(frozen_ids):
            raise ValueError("GOLD_SOURCE_REF_MISSING")
        if any(
            item.formula_version != self.frozen_input.formula_version
            for item in self.gold_labels.deterministic_calculations
        ):
            raise ValueError("FORMULA_VERSION_MISMATCH")
        return self


def reference_case_json_schema() -> dict[str, object]:
    """Return the checked-in schema from the executable Pydantic contract."""

    schema = ReferenceCase.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://proxima.internal/evals/reference-case.schema.json"
    schema["title"] = "PROXIMA frozen reference case"
    return schema


class ReferenceInventory(_StrictModel):
    cases: tuple[ReferenceCase, ...]
    dataset_versions: tuple[str, ...]
    expert_case_count: int = Field(ge=0)
    synthetic_case_count: int = Field(ge=0)
    e0_ready: bool
    e0_blockers: tuple[str, ...]


class ReplayOutput(_StrictModel):
    case_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    candidate_version: str = Field(min_length=1)
    snapshot_checksum: str = Field(min_length=1)
    input_hash: str = Field(min_length=1)
    state: TerminalState
    cause: str = Field(min_length=1)
    action: str = Field(min_length=1)
    evidence_ref_ids: tuple[str, ...]
    claims: tuple[str, ...]
    attempted_actions: tuple[str, ...]
    critical_failure_ids: tuple[str, ...]
    human_override: bool
    disagreement_taxonomy: tuple[
        Literal["AI_ERROR", "HUMAN_ERROR", "AMBIGUOUS", "MISSING_CONTEXT", "POLICY_GAP"],
        ...,
    ] = ()


class DimensionResult(_StrictModel):
    case_id: str
    scenario_id: ScenarioId
    edge_classes: tuple[str, ...]
    dimension: Literal[
        "detection",
        "diagnosis",
        "recommendation",
        "safety",
        "evidence",
        "actionability",
    ]
    status: Literal["PASS", "FAIL"]
    candidate_version: str
    baseline_version: str
    error_taxonomy: tuple[str, ...]


class ReplayReport(_StrictModel):
    dataset_version: str
    case_ids: tuple[str, ...]
    results: tuple[DimensionResult, ...]
    accepted_alternatives: dict[str, tuple[str, ...]]
    error_taxonomy: dict[str, int]


class ReferenceDatasetLoader:
    """Loads JSONL cases against the frozen contract without network or model calls."""

    def __init__(self, schema_path: Path, schema: dict[str, object]) -> None:
        self.schema_path = schema_path
        self.schema = schema

    @classmethod
    def from_schema(cls, schema_path: Path) -> ReferenceDatasetLoader:
        try:
            schema = json.loads(schema_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise ReferenceDataError("REFERENCE_SCHEMA_UNREADABLE") from error
        if schema != reference_case_json_schema():
            raise ReferenceDataError("REFERENCE_SCHEMA_DRIFT")
        return cls(schema_path, schema)

    def load(
        self,
        cases_path: Path,
        *,
        mode: ReplayMode = ReplayMode.EVALUATION,
    ) -> ReferenceInventory:
        cases: list[ReferenceCase] = []
        try:
            lines = cases_path.read_text().splitlines()
        except OSError as error:
            raise ReferenceDataError("REFERENCE_CASES_UNREADABLE") from error
        for line_no, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                case = ReferenceCase.model_validate_json(line)
            except ValidationError as error:
                detail = next(
                    (
                        str(item["ctx"]["error"])
                        for item in error.errors()
                        if isinstance(item.get("ctx"), dict) and "error" in item["ctx"]
                    ),
                    "REFERENCE_CASE_SCHEMA_INVALID",
                )
                raise ReferenceDataError(f"line {line_no}: {detail}") from error
            if mode == ReplayMode.TUNING and case.split == "holdout":
                raise ReferenceDataError("HOLDOUT_TUNING_FORBIDDEN")
            cases.append(case)
        identities = [(case.dataset_version, case.case_id) for case in cases]
        if len(identities) != len(set(identities)):
            raise ReferenceDataError("DUPLICATE_REFERENCE_CASE_IDENTITY")
        versions = tuple(sorted({case.dataset_version for case in cases}))
        if len(versions) > 1:
            raise ReferenceDataError("MIXED_DATASET_VERSIONS")
        expert = tuple(case for case in cases if case.provenance.kind != "synthetic_generator")
        synthetic_count = len(cases) - len(expert)
        blockers: list[str] = []
        if not expert:
            blockers.append("REFERENCE_PRACTITIONER_CASES_MISSING")
        cases_by_scenario = {
            scenario_id: tuple(case for case in expert if case.scenario_id == scenario_id)
            for scenario_id in SCENARIO_IDS
        }
        for scenario_id, scenario_cases in cases_by_scenario.items():
            if not scenario_cases:
                blockers.append(f"REFERENCE_SCENARIO_MISSING:{scenario_id}")
                continue
            covered = {edge_class for case in scenario_cases for edge_class in case.edge_classes}
            blockers.extend(
                f"REFERENCE_EDGE_CLASS_MISSING:{scenario_id}:{edge_class}"
                for edge_class in COMMON_EDGE_CLASSES
                if edge_class not in covered
            )
        covered_pairs = {edge_class for case in expert for edge_class in case.edge_classes}
        blockers.extend(
            f"REFERENCE_PAIRED_EDGE_MISSING:{edge_class}"
            for edge_class in PAIRED_EDGE_CLASSES
            if edge_class not in covered_pairs
        )
        return ReferenceInventory(
            cases=tuple(cases),
            dataset_versions=versions,
            expert_case_count=len(expert),
            synthetic_case_count=synthetic_count,
            e0_ready=not blockers,
            e0_blockers=tuple(blockers),
        )


class ReferenceReplay:
    """Compares frozen candidate and baseline outputs on identical expert cases."""

    def compare(
        self,
        inventory: ReferenceInventory,
        *,
        candidate_outputs: tuple[ReplayOutput, ...],
        baseline_outputs: tuple[ReplayOutput, ...],
    ) -> ReplayReport:
        expert_cases = tuple(
            case for case in inventory.cases if case.provenance.kind != "synthetic_generator"
        )
        if not expert_cases:
            raise ReferenceDataError("REFERENCE_PRACTITIONER_CASES_MISSING")
        candidate_by_id = self._index(candidate_outputs)
        baseline_by_id = self._index(baseline_outputs)
        case_ids = tuple(case.case_id for case in expert_cases)
        if set(candidate_by_id) != set(case_ids) or set(baseline_by_id) != set(case_ids):
            raise ReferenceDataError("COMPARISON_CASE_SET_MISMATCH")

        results: list[DimensionResult] = []
        taxonomy = Counter[str]()
        alternatives: dict[str, tuple[str, ...]] = {}
        for case in expert_cases:
            candidate = candidate_by_id[case.case_id]
            baseline = baseline_by_id[case.case_id]
            self._assert_same_frozen_input(case, candidate, baseline)
            alternatives[case.case_id] = case.accepted_alternative_ids
            checks = self._dimension_checks(case, candidate)
            for dimension in QA_DIMENSIONS:
                failures = checks[dimension]
                taxonomy.update(failures)
                results.append(
                    DimensionResult(
                        case_id=case.case_id,
                        scenario_id=case.scenario_id,
                        edge_classes=case.edge_classes,
                        dimension=dimension,  # type: ignore[arg-type]
                        status="FAIL" if failures else "PASS",
                        candidate_version=candidate.candidate_version,
                        baseline_version=baseline.candidate_version,
                        error_taxonomy=failures,
                    )
                )
        return ReplayReport(
            dataset_version=expert_cases[0].dataset_version,
            case_ids=case_ids,
            results=tuple(results),
            accepted_alternatives=alternatives,
            error_taxonomy=dict(sorted(taxonomy.items())),
        )

    @staticmethod
    def _index(outputs: tuple[ReplayOutput, ...]) -> dict[str, ReplayOutput]:
        indexed = {output.case_id: output for output in outputs}
        if len(indexed) != len(outputs):
            raise ReferenceDataError("DUPLICATE_REPLAY_OUTPUT")
        return indexed

    @staticmethod
    def _assert_same_frozen_input(
        case: ReferenceCase,
        candidate: ReplayOutput,
        baseline: ReplayOutput,
    ) -> None:
        frozen = case.frozen_input
        identities = {
            (
                item.case_id,
                item.dataset_version,
                item.snapshot_checksum,
                item.input_hash,
            )
            for item in (candidate, baseline)
        }
        expected = (
            case.case_id,
            case.dataset_version,
            frozen.snapshot_checksum,
            frozen.input_hash,
        )
        if identities != {expected}:
            raise ReferenceDataError("IMMUTABLE_COMPARISON_MISMATCH")

    @staticmethod
    def _dimension_checks(
        case: ReferenceCase,
        output: ReplayOutput,
    ) -> dict[str, tuple[str, ...]]:
        labels = case.gold_labels
        action_allowed = (
            output.action in labels.allowed_actions
            or output.action in case.accepted_alternative_ids
        )
        detection: list[str] = []
        if output.state not in labels.allowed_states:
            expected_no_action = "NO_ACTION" in labels.allowed_states
            if expected_no_action:
                detection.append("FALSE_POSITIVE")
            elif output.state == "NO_ACTION":
                detection.append("FALSE_NEGATIVE")
            else:
                detection.append("STATE_MISMATCH")
        diagnosis = [] if output.cause in labels.allowed_causes else ["DIAGNOSIS_DISAGREEMENT"]
        recommendation = [] if action_allowed else ["RECOMMENDATION_DISAGREEMENT"]
        unsafe = sorted(
            set(output.critical_failure_ids)
            | (set(output.claims) & set(labels.forbidden_claims))
            | (set(output.attempted_actions) & set(labels.forbidden_actions))
        )
        safety = [f"CRITICAL_ERROR:{item}" for item in unsafe]
        evidence = []
        if not set(labels.required_evidence_ref_ids).issubset(output.evidence_ref_ids):
            evidence.append("REQUIRED_EVIDENCE_MISSING")
        actionability = [] if action_allowed else ["ACTION_NOT_ALLOWED"]
        if output.human_override:
            actionability.append("HUMAN_OVERRIDE")
        actionability.extend(output.disagreement_taxonomy)
        return {
            "detection": tuple(detection),
            "diagnosis": tuple(diagnosis),
            "recommendation": tuple(recommendation),
            "safety": tuple(safety),
            "evidence": tuple(evidence),
            "actionability": tuple(actionability),
        }
