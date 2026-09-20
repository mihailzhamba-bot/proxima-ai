"""Deterministic E0-E3 evidence validation; no gate status is trusted as input."""

from __future__ import annotations

import ast
import copy
import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

type GateId = Literal["E0", "E1", "E2", "E3"]
type GateStatus = Literal["NOT_EVALUATED", "BLOCKED", "READY"]
type Phase3ExitStatus = Literal["BLOCKED", "E3_READY_G1_CANDIDATE"]

CRITICAL_FAILURE_IDS = tuple(f"CF-{index:02d}" for index in range(1, 11))
REQUIRED_GATE_CHECKS: dict[str, tuple[str, ...]] = {
    "E0": (
        "REFERENCE_SCHEMA_FROZEN",
        "SCN_001_008_COVERAGE",
        "PRACTITIONER_LABELS",
        "INDEPENDENT_SECOND_REVIEW",
        "DISAGREEMENTS_VISIBLE",
        "DEIDENTIFICATION_COMPLETE",
    ),
    "E1": (
        "CONTRACT_TESTS",
        "FORMULA_TESTS",
        "TENANT_TESTS",
        "QUALITY_TESTS",
        "DEDUP_TESTS",
        "AUTONOMY_TESTS",
        "AUDIT_TESTS",
        "REFUSAL_INCOMPLETE_TESTS",
        *(f"{failure_id}_FAIL_CLOSED" for failure_id in CRITICAL_FAILURE_IDS),
    ),
    "E2": (
        "FROZEN_REGRESSION_REPORT",
        "FROZEN_HOLDOUT_REPORT",
        "CANDIDATE_BASELINE_COMPARISON",
        "HUMAN_ADJUDICATION",
        "JUDGE_CALIBRATION_NON_AUTHORITATIVE",
        "HOLDOUT_ISOLATION",
        "PROVIDER_MODEL_APPROVED",
    ),
    "E3": (
        "E0_E2_READY",
        "REAL_G0",
        "PHASE2_RELEASE",
        "OPERATIONAL_CLIENT_PASSPORT",
        "THREE_CLIENT_READINESS",
        "NO_WRITE_SURFACE",
        "ONLINE_VALIDATORS",
        "POSTGRES_AUDIT_RECONSTRUCTION",
        "METRICS_DASHBOARD",
        "INCIDENT_OWNER",
        "INCIDENT_RUNBOOK",
        "SHADOW_BASELINE_28_DAYS",
    ),
}
TEST_EXECUTION_CHECKS = frozenset(
    {
        *REQUIRED_GATE_CHECKS["E1"],
        "HOLDOUT_ISOLATION",
        "NO_WRITE_SURFACE",
        "ONLINE_VALIDATORS",
        "POSTGRES_AUDIT_RECONSTRUCTION",
        "METRICS_DASHBOARD",
    }
)


class GateValidationError(ValueError):
    """Evidence cannot support the claimed gate state."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class PreflightEvidence(_StrictModel):
    g0_decision_locator: str | None
    g0_evidence_locator: str | None
    phase2_release_locator: str | None
    client_passport_locator: str | None
    validated_at: datetime | None


class GateCheck(_StrictModel):
    check_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL", "MISSING"]
    evidence_locators: tuple[str, ...]


class GateBlocker(_StrictModel):
    code: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    next_evidence: str = Field(min_length=1)
    due_at: datetime | None = None


class GateRecord(_StrictModel):
    gate_id: GateId
    status: GateStatus
    checks: tuple[GateCheck, ...]
    blockers: tuple[GateBlocker, ...]
    evaluated_at: datetime
    evaluator: str = Field(min_length=1)
    validator_version: str = Field(min_length=1)


class ThresholdEvidence(_StrictModel):
    name: str = Field(min_length=1)
    value: float | None = None
    baseline_source: str | None = None
    baseline_date: date | None = None
    approved_by: str | None = None
    approved_at: date | None = None

    @model_validator(mode="after")
    def numeric_value_requires_approval(self) -> ThresholdEvidence:
        if self.value is None:
            return self
        if not (
            self.baseline_source
            and self.baseline_date
            and self.approved_by == "Mike"
            and self.approved_at
        ):
            raise ValueError("UNAPPROVED_NUMERIC_THRESHOLD")
        return self


class CriticalFailureEvidence(_StrictModel):
    failure_id: Literal[
        "CF-01",
        "CF-02",
        "CF-03",
        "CF-04",
        "CF-05",
        "CF-06",
        "CF-07",
        "CF-08",
        "CF-09",
        "CF-10",
    ]
    occurrences: int = Field(ge=0)
    evidence_locators: tuple[str, ...]


class IncidentReadiness(_StrictModel):
    incident_owner: str = Field(min_length=1)
    owner_source_ref: str = Field(min_length=1)
    runbook_version: str = Field(min_length=1)
    runbook_locator: str = Field(min_length=1)


class GateEvidenceRecord(_StrictModel):
    record_version: Literal["1.0"]
    generated_at: datetime
    phase: Literal["03"]
    candidate_version: str = Field(min_length=1)
    candidate_tree_hash: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{40}$|^[0-9a-f]{64}$",
    )
    preflight_evidence: PreflightEvidence
    gates: tuple[GateRecord, ...]
    thresholds: tuple[ThresholdEvidence, ...]
    critical_failures: tuple[CriticalFailureEvidence, ...]
    incident_readiness: IncidentReadiness
    phase3_exit: Phase3ExitStatus
    g1_owner: Literal["Mike"]
    g1_decision_locator: str | None

    @model_validator(mode="after")
    def complete_unique_gate_and_failure_sets(self) -> GateEvidenceRecord:
        gate_ids = tuple(gate.gate_id for gate in self.gates)
        if gate_ids != ("E0", "E1", "E2", "E3"):
            raise ValueError("GATES_MUST_BE_ORDERED_E0_E3")
        failure_ids = tuple(item.failure_id for item in self.critical_failures)
        if failure_ids != CRITICAL_FAILURE_IDS:
            raise ValueError("CRITICAL_FAILURE_SET_INCOMPLETE")
        threshold_names = [threshold.name for threshold in self.thresholds]
        if len(threshold_names) != len(set(threshold_names)):
            raise ValueError("DUPLICATE_THRESHOLD")
        return self


class AttestedTestOutcome(_StrictModel):
    nodeid: str = Field(min_length=1)
    outcome: Literal["passed"]
    skipped: Literal[False]


class TestRunAttestation(_StrictModel):
    attestation_version: Literal["1.0"]
    attestation_id: str = Field(min_length=1)
    candidate_commit: str = Field(pattern=r"^[0-9a-f]{7,64}$")
    candidate_tree_hash: str = Field(pattern=r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
    environment: dict[str, str]
    generated_at: datetime
    suite_exit_code: Literal[0]
    producer: str = Field(min_length=1)
    tests: tuple[AttestedTestOutcome, ...]
    artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def complete_attestation(self) -> TestRunAttestation:
        nodeids = [item.nodeid for item in self.tests]
        if not self.environment or any(
            not key or not value for key, value in self.environment.items()
        ):
            raise ValueError("ATTESTATION_ENVIRONMENT_MISSING")
        if not nodeids or len(nodeids) != len(set(nodeids)):
            raise ValueError("ATTESTATION_TEST_SET_INVALID")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("ATTESTATION_TIMESTAMP_NAIVE")
        return self


def compute_test_run_attestation_checksum(payload: Mapping[str, object]) -> str:
    unsigned = {
        key: value
        for key, value in payload.items()
        if key not in {"artifact_checksum", "signature"}
    }
    raw = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def sign_test_run_attestation(checksum: str, signing_key: bytes | str) -> str:
    key = signing_key.encode() if isinstance(signing_key, str) else signing_key
    return hmac.new(key, checksum.encode(), hashlib.sha256).hexdigest()


def gate_evidence_json_schema() -> dict[str, object]:
    """Return the checked-in schema from the executable Pydantic contract."""

    schema = GateEvidenceRecord.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://proxima.internal/evals/e0-e3.schema.json"
    schema["title"] = "PROXIMA Phase 3 deterministic gate evidence"
    return schema


@dataclass(frozen=True, slots=True)
class ResolvedEvidenceLocator:
    locator: str
    kind: Literal["repo", "sha256", "external", "attestation"]
    checksum: str
    path: Path | None = None
    fragment: str | None = None
    attestation: TestRunAttestation | None = None


class EvidenceLocatorResolver:
    """Resolve only repository, pytest, content-hash and approved external evidence."""

    _SHA256 = re.compile(r"^[0-9a-f]{64}$")

    def __init__(
        self,
        repo_root: Path,
        *,
        approved_external_records: Mapping[str, bytes | str] | None = None,
        approved_test_run_attestations: Mapping[str, bytes | str] | None = None,
        approved_attestation_producers: Mapping[str, bytes | str] | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.approved_external_records = dict(approved_external_records or {})
        self.approved_test_run_attestations = dict(approved_test_run_attestations or {})
        self.approved_attestation_producers = dict(approved_attestation_producers or {})

    def resolve(self, locator: str) -> ResolvedEvidenceLocator:
        if locator.startswith("external:"):
            return self._resolve_external(locator)
        if locator.startswith("attestation:"):
            return self._resolve_attestation(locator)
        if locator.startswith("pytest://"):
            raise ValueError("PYTEST_SOURCE_IS_NOT_EXECUTION_ATTESTATION")
        if locator.startswith("sha256:"):
            _, digest, spec = locator.split(":", 2)
            if not self._SHA256.fullmatch(digest):
                raise ValueError("INVALID_SHA256")
            resolved = self._resolve_repo(spec, kind="sha256")
            if resolved.checksum != digest:
                raise ValueError("SHA256_MISMATCH")
            return resolved
        if "://" in locator:
            raise ValueError("UNAPPROVED_LOCATOR_SCHEME")
        spec = locator.removeprefix("repo:")
        return self._resolve_repo(spec, kind="repo")

    def _resolve_attestation(self, locator: str) -> ResolvedEvidenceLocator:
        record_locator, separator, nodeid = locator.partition("#")
        if not separator or not nodeid:
            raise ValueError("ATTESTATION_NODE_REQUIRED")
        raw_record = self.approved_test_run_attestations.get(record_locator)
        if raw_record is None:
            raise ValueError("ATTESTATION_RECORD_NOT_APPROVED")
        raw = raw_record.encode() if isinstance(raw_record, str) else raw_record
        try:
            parsed = json.loads(raw)
            attestation = TestRunAttestation.model_validate_json(raw)
        except (json.JSONDecodeError, ValidationError) as error:
            raise ValueError("ATTESTATION_RECORD_INVALID") from error
        if record_locator != f"attestation:{attestation.attestation_id}":
            raise ValueError("ATTESTATION_ID_MISMATCH")
        checksum = compute_test_run_attestation_checksum(parsed)
        if not hmac.compare_digest(checksum, attestation.artifact_checksum):
            raise ValueError("ATTESTATION_CHECKSUM_MISMATCH")
        signing_key = self.approved_attestation_producers.get(attestation.producer)
        if signing_key is None:
            raise ValueError("ATTESTATION_PRODUCER_NOT_APPROVED")
        expected_signature = sign_test_run_attestation(checksum, signing_key)
        if not hmac.compare_digest(expected_signature, attestation.signature):
            raise ValueError("ATTESTATION_SIGNATURE_MISMATCH")
        outcomes = {item.nodeid: item for item in attestation.tests}
        outcome = outcomes.get(nodeid)
        if outcome is None or outcome.outcome != "passed" or outcome.skipped:
            raise ValueError("ATTESTATION_NODE_NOT_PASSED")
        return ResolvedEvidenceLocator(
            locator=locator,
            kind="attestation",
            checksum=checksum,
            fragment=nodeid,
            attestation=attestation,
        )

    def _resolve_external(self, locator: str) -> ResolvedEvidenceLocator:
        content = self.approved_external_records.get(locator)
        if content is None:
            raise ValueError("EXTERNAL_RECORD_NOT_APPROVED")
        raw = content.encode() if isinstance(content, str) else content
        return ResolvedEvidenceLocator(
            locator=locator,
            kind="external",
            checksum=hashlib.sha256(raw).hexdigest(),
        )

    def _resolve_repo(
        self,
        spec: str,
        *,
        kind: Literal["repo", "sha256"],
    ) -> ResolvedEvidenceLocator:
        relative, _separator, fragment = spec.partition("#")
        if not relative or Path(relative).is_absolute():
            raise ValueError("REPOSITORY_PATH_INVALID")
        candidate = (self.repo_root / relative).resolve()
        if not candidate.is_relative_to(self.repo_root) or not candidate.is_file():
            raise ValueError("REPOSITORY_ARTIFACT_MISSING")
        if fragment:
            self._verify_fragment(candidate, fragment)
        raw = candidate.read_bytes()
        return ResolvedEvidenceLocator(
            locator=spec,
            kind=kind,
            checksum=hashlib.sha256(raw).hexdigest(),
            path=candidate,
            fragment=fragment or None,
        )

    @staticmethod
    def _verify_fragment(path: Path, fragment: str) -> None:
        if path.suffix == ".py":
            try:
                tree = ast.parse(path.read_text())
            except (OSError, SyntaxError, UnicodeDecodeError) as error:
                raise ValueError("PYTHON_ARTIFACT_UNREADABLE") from error
            if "[" in fragment or "]" in fragment:
                raise ValueError("PYTEST_PARAMETER_ANCHOR_UNVERIFIED")
            node_name = fragment.split("::")[-1]
            symbols = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            }
            if node_name not in symbols:
                raise ValueError("PYTHON_NODE_MISSING")
            return
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError) as error:
            raise ValueError("TEXT_ARTIFACT_UNREADABLE") from error
        if fragment not in content:
            raise ValueError("CONTENT_ANCHOR_MISSING")


class GateValidator:
    """Validates evidence and derives the only supported READY representation."""

    def __init__(
        self,
        schema_path: Path,
        schema: dict[str, object],
        resolver: EvidenceLocatorResolver,
    ) -> None:
        self.schema_path = schema_path
        self.schema = schema
        self.resolver = resolver

    @classmethod
    def from_schema(
        cls,
        schema_path: Path,
        *,
        repo_root: Path | None = None,
        approved_external_records: Mapping[str, bytes | str] | None = None,
        approved_test_run_attestations: Mapping[str, bytes | str] | None = None,
        approved_attestation_producers: Mapping[str, bytes | str] | None = None,
    ) -> GateValidator:
        try:
            schema = json.loads(schema_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise GateValidationError("EVIDENCE_SCHEMA_UNREADABLE") from error
        if schema != gate_evidence_json_schema():
            raise GateValidationError("EVIDENCE_SCHEMA_DRIFT")
        root = repo_root or cls._discover_repo_root(schema_path)
        return cls(
            schema_path,
            schema,
            EvidenceLocatorResolver(
                root,
                approved_external_records=approved_external_records,
                approved_test_run_attestations=approved_test_run_attestations,
                approved_attestation_producers=approved_attestation_producers,
            ),
        )

    def validate(self, payload: dict[str, object]) -> GateEvidenceRecord:
        record = self._parse(payload)
        self._validate_checks(record)
        self._validate_preflight_cross_links(record)
        expected = self._expected_statuses(record)
        confirmed = next(
            (item.failure_id for item in record.critical_failures if item.occurrences),
            None,
        )
        if confirmed and any(gate.status == "READY" for gate in record.gates[1:]):
            raise GateValidationError(f"CONFIRMED_CRITICAL_FAILURE:{confirmed}")
        for gate in record.gates:
            if gate.status != expected[gate.gate_id]:
                raise GateValidationError(f"UNSUPPORTED_GATE_STATUS:{gate.gate_id}")
            if gate.status == "READY" and gate.blockers:
                raise GateValidationError(f"READY_GATE_HAS_BLOCKERS:{gate.gate_id}")
            if gate.status == "BLOCKED" and not gate.blockers:
                raise GateValidationError(f"BLOCKED_GATE_WITHOUT_BLOCKER:{gate.gate_id}")
        expected_exit: Phase3ExitStatus = (
            "E3_READY_G1_CANDIDATE" if expected["E3"] == "READY" else "BLOCKED"
        )
        if record.phase3_exit != expected_exit:
            raise GateValidationError("UNSUPPORTED_PHASE3_EXIT")
        if record.g1_decision_locator is not None:
            raise GateValidationError("PHASE3_CANNOT_RECORD_G1_DECISION")
        return record

    def derive(self, payload: dict[str, object]) -> GateEvidenceRecord:
        normalized = copy.deepcopy(payload)
        record = self._parse(normalized)
        self._validate_checks(record)
        self._validate_preflight_cross_links(record)
        expected = self._expected_statuses(record)
        gates = normalized.get("gates")
        if not isinstance(gates, list):
            raise GateValidationError("RECORD_SCHEMA_INVALID")
        for gate in gates:
            if not isinstance(gate, dict):
                raise GateValidationError("RECORD_SCHEMA_INVALID")
            gate_id = gate.get("gate_id")
            if not isinstance(gate_id, str):
                raise GateValidationError("RECORD_SCHEMA_INVALID")
            gate["status"] = expected[gate_id]
            if expected[gate_id] == "BLOCKED" and not gate.get("blockers"):
                gate["blockers"] = [
                    {
                        "code": f"{gate_id}_PREREQUISITES_BLOCKED",
                        "owner": record.incident_readiness.incident_owner,
                        "next_evidence": f"Close all evidence prerequisites for {gate_id}.",
                    }
                ]
        normalized["phase3_exit"] = (
            "E3_READY_G1_CANDIDATE" if expected["E3"] == "READY" else "BLOCKED"
        )
        normalized["g1_decision_locator"] = None
        return self.validate(normalized)

    @staticmethod
    def _parse(payload: dict[str, object]) -> GateEvidenceRecord:
        try:
            return GateEvidenceRecord.model_validate_json(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            )
        except ValidationError as error:
            if "UNAPPROVED_NUMERIC_THRESHOLD" in str(error):
                raise GateValidationError("UNAPPROVED_NUMERIC_THRESHOLD") from error
            raise GateValidationError("RECORD_SCHEMA_INVALID") from error

    def _validate_checks(self, record: GateEvidenceRecord) -> None:
        for gate in record.gates:
            check_ids = tuple(check.check_id for check in gate.checks)
            if check_ids != REQUIRED_GATE_CHECKS[gate.gate_id]:
                raise GateValidationError(f"REQUIRED_GATE_CHECKS_MISMATCH:{gate.gate_id}")
            for check in gate.checks:
                if check.status == "PASS" and (
                    not check.evidence_locators
                    or any(not locator.strip() for locator in check.evidence_locators)
                ):
                    raise GateValidationError(f"PASS_EVIDENCE_MISSING:{check.check_id}")
                for locator in check.evidence_locators:
                    self._resolve_or_raise(locator, check.check_id)
        for failure in record.critical_failures:
            for locator in failure.evidence_locators:
                self._resolve_or_raise(locator, failure.failure_id)

    def _validate_preflight_cross_links(self, record: GateEvidenceRecord) -> None:
        checks = {check.check_id: check for gate in record.gates for check in gate.checks}
        preflight = record.preflight_evidence
        requirements = {
            "REAL_G0": tuple(
                locator
                for locator in (
                    preflight.g0_decision_locator,
                    preflight.g0_evidence_locator,
                )
                if locator is not None
            ),
            "PHASE2_RELEASE": (preflight.phase2_release_locator,),
            "OPERATIONAL_CLIENT_PASSPORT": (preflight.client_passport_locator,),
            "INCIDENT_OWNER": (record.incident_readiness.owner_source_ref,),
            "INCIDENT_RUNBOOK": (record.incident_readiness.runbook_locator,),
        }
        for check_id, required_locators in requirements.items():
            check = checks[check_id]
            if check.status != "PASS":
                continue
            if (
                not required_locators
                or any(locator is None for locator in required_locators)
                or not set(required_locators).issubset(check.evidence_locators)
            ):
                raise GateValidationError(f"PREFLIGHT_EVIDENCE_MISMATCH:{check_id}")
            for locator in required_locators:
                if locator is not None:
                    self._resolve_or_raise(locator, check_id)
        preflight_checks = ("REAL_G0", "PHASE2_RELEASE", "OPERATIONAL_CLIENT_PASSPORT")
        if any(checks[check_id].status == "PASS" for check_id in preflight_checks):
            if preflight.validated_at is None:
                raise GateValidationError("PREFLIGHT_VALIDATION_TIMESTAMP_MISSING")

    def _resolve_or_raise(self, locator: str, evidence_id: str) -> None:
        try:
            self.resolver.resolve(locator)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise GateValidationError(f"EVIDENCE_LOCATOR_UNRESOLVED:{evidence_id}") from error

    @staticmethod
    def _discover_repo_root(schema_path: Path) -> Path:
        resolved = schema_path.resolve()
        for candidate in (resolved.parent, *resolved.parents):
            if (candidate / "pyproject.toml").is_file():
                return candidate
        raise GateValidationError("REPOSITORY_ROOT_NOT_FOUND")

    def _execution_attested(self, check: GateCheck, record: GateEvidenceRecord) -> bool:
        if check.check_id not in TEST_EXECUTION_CHECKS:
            return True
        for locator in check.evidence_locators:
            try:
                resolved = self.resolver.resolve(locator)
            except OSError, UnicodeDecodeError, ValueError:
                continue
            attestation = resolved.attestation
            if (
                resolved.kind == "attestation"
                and attestation is not None
                and attestation.candidate_commit == record.candidate_version
                and record.candidate_tree_hash is not None
                and attestation.candidate_tree_hash == record.candidate_tree_hash
                and attestation.generated_at <= record.generated_at
            ):
                return True
        return False

    def _expected_statuses(self, record: GateEvidenceRecord) -> dict[str, GateStatus]:
        statuses: dict[str, GateStatus] = {}
        confirmed_failure = any(item.occurrences for item in record.critical_failures)
        for gate in record.gates:
            ready = all(
                check.status == "PASS" and self._execution_attested(check, record)
                for check in gate.checks
            )
            if gate.gate_id == "E1" and confirmed_failure:
                ready = False
            if gate.gate_id == "E2":
                ready = ready and statuses.get("E0") == "READY" and statuses.get("E1") == "READY"
                ready = ready and not confirmed_failure
            if gate.gate_id == "E3":
                ready = ready and all(statuses.get(item) == "READY" for item in ("E0", "E1", "E2"))
                ready = ready and not confirmed_failure
            statuses[gate.gate_id] = "READY" if ready else "BLOCKED"
        return statuses
