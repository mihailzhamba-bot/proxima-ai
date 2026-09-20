from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from proxima.evals.gate_validator import (
    CRITICAL_FAILURE_IDS,
    REQUIRED_GATE_CHECKS,
    TEST_EXECUTION_CHECKS,
    GateValidationError,
    GateValidator,
    compute_test_run_attestation_checksum,
    sign_test_run_attestation,
)

ROOT = Path(__file__).parents[3]
SCHEMA_PATH = ROOT / "evals/evidence/e0-e3.schema.json"
EVIDENCE_PATH = ROOT / "evals/evidence/e0-e3.json"
CANDIDATE_COMMIT = "a" * 40
ATTESTATION_KEY = "unit-test-attestation-key"
ATTESTATION_PRODUCER = "proxima-ci"


def _ready_payload(
    evidence_locator: str = "repo:src/proxima/evals/gate_validator.py",
    *,
    execution_locators: dict[str, str] | None = None,
) -> dict[str, object]:
    gates = []
    for gate_id in ("E0", "E1", "E2", "E3"):
        gates.append(
            {
                "gate_id": gate_id,
                "status": "READY",
                "checks": [
                    {
                        "check_id": check_id,
                        "status": "PASS",
                        "evidence_locators": [
                            evidence_locator,
                            *(
                                [execution_locators[check_id]]
                                if execution_locators and check_id in execution_locators
                                else []
                            ),
                        ],
                    }
                    for check_id in REQUIRED_GATE_CHECKS[gate_id]
                ],
                "blockers": [],
                "evaluated_at": "2026-08-11T12:00:00Z",
                "evaluator": "deterministic-gate-validator",
                "validator_version": "03-03.v1",
            }
        )
    return {
        "record_version": "1.0",
        "generated_at": "2026-08-11T12:00:00Z",
        "phase": "03",
        "candidate_version": CANDIDATE_COMMIT,
        "candidate_tree_hash": "b" * 40,
        "preflight_evidence": {
            "g0_decision_locator": evidence_locator,
            "g0_evidence_locator": evidence_locator,
            "phase2_release_locator": evidence_locator,
            "client_passport_locator": evidence_locator,
            "validated_at": "2026-08-11T11:00:00Z",
        },
        "gates": gates,
        "thresholds": [],
        "critical_failures": [
            {
                "failure_id": failure_id,
                "occurrences": 0,
                "evidence_locators": [evidence_locator],
            }
            for failure_id in CRITICAL_FAILURE_IDS
        ],
        "incident_readiness": {
            "incident_owner": "Mike",
            "owner_source_ref": evidence_locator,
            "runbook_version": "03-03.v1",
            "runbook_locator": evidence_locator,
        },
        "phase3_exit": "E3_READY_G1_CANDIDATE",
        "g1_owner": "Mike",
        "g1_decision_locator": None,
    }


def _approved_test_run() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    nodeids = {
        check_id: f"tests/attested/test_phase3.py::test_{check_id.casefold().replace('-', '_')}"
        for check_id in TEST_EXECUTION_CHECKS
    }
    payload: dict[str, object] = {
        "attestation_version": "1.0",
        "attestation_id": "phase3-unit-run",
        "candidate_commit": CANDIDATE_COMMIT,
        "candidate_tree_hash": "b" * 40,
        "environment": {"python": "3.14", "profile": "offline-test"},
        "generated_at": "2026-08-11T11:30:00Z",
        "suite_exit_code": 0,
        "producer": ATTESTATION_PRODUCER,
        "tests": [
            {"nodeid": nodeid, "outcome": "passed", "skipped": False} for nodeid in nodeids.values()
        ],
    }
    checksum = compute_test_run_attestation_checksum(payload)
    payload["artifact_checksum"] = checksum
    payload["signature"] = sign_test_run_attestation(checksum, ATTESTATION_KEY)
    record_locator = "attestation:phase3-unit-run"
    locators = {check_id: f"{record_locator}#{nodeid}" for check_id, nodeid in nodeids.items()}
    return (
        locators,
        {record_locator: json.dumps(payload, sort_keys=True)},
        {ATTESTATION_PRODUCER: ATTESTATION_KEY},
    )


def _attested_ready() -> tuple[GateValidator, dict[str, object]]:
    locators, records, producers = _approved_test_run()
    validator = GateValidator.from_schema(
        SCHEMA_PATH,
        approved_test_run_attestations=records,
        approved_attestation_producers=producers,
    )
    return validator, _ready_payload(execution_locators=locators)


def test_checked_in_evidence_is_schema_valid_derived_and_blocked() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    phase3_exit = schema["$defs"]["Phase3ExitStatus"]
    assert phase3_exit["enum"] == [
        "BLOCKED",
        "E3_READY_G1_CANDIDATE",
    ]
    payload = json.loads(EVIDENCE_PATH.read_text())

    record = GateValidator.from_schema(SCHEMA_PATH).validate(payload)

    assert record.phase3_exit == "BLOCKED"
    assert record.g1_decision_locator is None
    assert {gate.gate_id: gate.status for gate in record.gates} == {
        "E0": "BLOCKED",
        "E1": "BLOCKED",
        "E2": "BLOCKED",
        "E3": "BLOCKED",
    }
    assert any(
        blocker.code == "REFERENCE_PRACTITIONER_CASES_MISSING"
        for blocker in record.gates[0].blockers
    )


def test_validator_derives_maximum_phase3_exit_but_never_g1() -> None:
    validator, payload = _attested_ready()
    record = validator.validate(payload)

    assert record.phase3_exit == "E3_READY_G1_CANDIDATE"
    assert "G1_PASS" not in record.model_dump_json()


def test_hand_edited_ready_with_missing_check_is_rejected() -> None:
    payload = _ready_payload()
    payload["gates"][0]["checks"][0]["status"] = "MISSING"  # type: ignore[index]
    payload["gates"][0]["checks"][0]["evidence_locators"] = []  # type: ignore[index]

    with pytest.raises(GateValidationError, match="UNSUPPORTED_GATE_STATUS:E0"):
        GateValidator.from_schema(SCHEMA_PATH).validate(payload)


def test_pass_check_without_exact_evidence_is_rejected() -> None:
    payload = _ready_payload()
    payload["gates"][1]["checks"][0]["evidence_locators"] = []  # type: ignore[index]

    with pytest.raises(GateValidationError, match="PASS_EVIDENCE_MISSING"):
        GateValidator.from_schema(SCHEMA_PATH).validate(payload)


@pytest.mark.parametrize(
    "locator",
    [
        "missing://definitely-not-an-artifact",
        "repo:does/not/exist.py",
        "pytest://tests/evals/contracts/test_critical_failures.py#not_a_real_test",
        "pytest://tests/evals/contracts/test_critical_failures.py#test_validator_derives_maximum_phase3_exit_but_never_g1[not-collected]",
        f"sha256:{'0' * 64}:src/proxima/evals/gate_validator.py",
    ],
)
def test_nonexistent_or_wrong_artifact_locator_cannot_mark_any_gate_ready(
    locator: str,
) -> None:
    payload = _ready_payload()
    payload["gates"][1]["checks"][0]["evidence_locators"] = [locator]  # type: ignore[index]

    with pytest.raises(
        GateValidationError,
        match="EVIDENCE_LOCATOR_UNRESOLVED:CONTRACT_TESTS",
    ):
        GateValidator.from_schema(SCHEMA_PATH).validate(payload)


def test_verified_content_hash_locator_cannot_replace_execution_attestation() -> None:
    artifact = ROOT / "src/proxima/evals/gate_validator.py"
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()

    with pytest.raises(GateValidationError, match="UNSUPPORTED_GATE_STATUS:E1"):
        GateValidator.from_schema(SCHEMA_PATH).validate(
            _ready_payload(f"sha256:{digest}:src/proxima/evals/gate_validator.py")
        )


def test_attestation_must_bind_exact_candidate_tree_hash() -> None:
    validator, payload = _attested_ready()
    payload["candidate_tree_hash"] = "c" * 40

    with pytest.raises(GateValidationError, match="UNSUPPORTED_GATE_STATUS:E1"):
        validator.validate(payload)


def test_unapproved_repo_or_pytest_source_never_proves_executed_pass() -> None:
    with pytest.raises(GateValidationError, match="UNSUPPORTED_GATE_STATUS:E1"):
        GateValidator.from_schema(SCHEMA_PATH).validate(_ready_payload())

    payload = _ready_payload()
    payload["gates"][1]["checks"][0]["evidence_locators"] = [  # type: ignore[index]
        "pytest://src/proxima/evals/gate_validator.py#validate"
    ]
    with pytest.raises(
        GateValidationError,
        match="EVIDENCE_LOCATOR_UNRESOLVED:CONTRACT_TESTS",
    ):
        GateValidator.from_schema(SCHEMA_PATH).validate(payload)


def test_ready_preflight_check_must_cross_link_loaded_evidence() -> None:
    payload = _ready_payload()
    e3 = payload["gates"][3]  # type: ignore[index]
    real_g0 = next(check for check in e3["checks"] if check["check_id"] == "REAL_G0")
    real_g0["evidence_locators"] = ["repo:src/proxima/application/scenario_engine.py"]

    with pytest.raises(GateValidationError, match="PREFLIGHT_EVIDENCE_MISMATCH:REAL_G0"):
        GateValidator.from_schema(SCHEMA_PATH).validate(payload)


def test_checked_in_gate_schema_is_generated_from_executable_contract(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    schema["title"] = "drifted schema"
    drifted = tmp_path / "e0-e3.schema.json"
    drifted.write_text(json.dumps(schema))

    with pytest.raises(GateValidationError, match="EVIDENCE_SCHEMA_DRIFT"):
        GateValidator.from_schema(drifted)


def test_ownerless_blocker_is_rejected() -> None:
    payload = _ready_payload()
    payload["gates"][0]["status"] = "BLOCKED"  # type: ignore[index]
    payload["gates"][0]["checks"][0]["status"] = "MISSING"  # type: ignore[index]
    payload["gates"][0]["checks"][0]["evidence_locators"] = []  # type: ignore[index]
    payload["gates"][0]["blockers"] = [  # type: ignore[index]
        {"code": "MISSING", "owner": "", "next_evidence": "Name the owner."}
    ]
    payload["phase3_exit"] = "BLOCKED"

    with pytest.raises(GateValidationError, match="RECORD_SCHEMA_INVALID"):
        GateValidator.from_schema(SCHEMA_PATH).validate(payload)


def test_unapproved_numeric_threshold_is_rejected() -> None:
    payload = _ready_payload()
    payload["thresholds"] = [{"name": "latency_seconds", "value": 3.0}]

    with pytest.raises(GateValidationError, match="UNAPPROVED_NUMERIC_THRESHOLD"):
        GateValidator.from_schema(SCHEMA_PATH).validate(payload)


@pytest.mark.parametrize("failure_id", CRITICAL_FAILURE_IDS)
def test_every_confirmed_critical_failure_blocks_ready(failure_id: str) -> None:
    payload = _ready_payload()
    failure = next(
        item
        for item in payload["critical_failures"]
        if item["failure_id"] == failure_id  # type: ignore[union-attr]
    )
    failure["occurrences"] = 1

    with pytest.raises(GateValidationError, match=f"CONFIRMED_CRITICAL_FAILURE:{failure_id}"):
        GateValidator.from_schema(SCHEMA_PATH).validate(payload)


def test_derive_replaces_claimed_statuses_in_one_code_path() -> None:
    payload = _ready_payload()
    payload["gates"][0]["checks"][0]["status"] = "MISSING"  # type: ignore[index]
    payload["gates"][0]["checks"][0]["evidence_locators"] = []  # type: ignore[index]
    payload["gates"][0]["blockers"] = [  # type: ignore[index]
        {
            "code": "REFERENCE_SCHEMA_MISSING",
            "owner": "Mike",
            "next_evidence": "Freeze the reference schema.",
        }
    ]

    record = GateValidator.from_schema(SCHEMA_PATH).derive(payload)

    assert record.gates[0].status == "BLOCKED"
    assert record.phase3_exit == "BLOCKED"


def test_incident_readiness_names_only_approved_interim_owner_and_read_only_recovery() -> None:
    readiness = json.loads(EVIDENCE_PATH.read_text())["incident_readiness"]

    assert readiness["incident_owner"] == "Mike"
    assert readiness["owner_source_ref"] == "conversation:2026-08-11#interim-technical-incident-owner"
    assert readiness["runbook_version"] == "03-03.v1"
    assert readiness["runbook_locator"] == "src/proxima/evals/gate_validator.py"
