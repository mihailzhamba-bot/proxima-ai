"""Envelope DiagnosisInput, Diagnosis, BatchItem, BatchResult: parse/serialize."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ALLOWED_SCENARIOS = ("SCN-001", "SCN-005", "SCN-008")
SCHEMA_VERSION = "diagnosis.draft.v1"


@dataclass(frozen=True)
class DiagnosisInput:
    signal_id: str
    scenario_id: str
    generated_at: str
    trust: str
    payload: dict[str, Any]
    context_extracts: list[Any]
    source_refs: list[str]


@dataclass(frozen=True)
class Diagnosis:
    signal_id: str
    scenario_id: str
    trust: str
    primary_cause: dict[str, Any]
    alternatives: list[dict[str, Any]]
    unknowns: list[dict[str, Any]]
    confidence_note: str
    model: str
    prompt_version: str
    generated_at: str
    schema_version: str = SCHEMA_VERSION

    def diagnosis_to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "signal_id": self.signal_id,
            "scenario_id": self.scenario_id,
            "trust": self.trust,
            "primary_cause": self.primary_cause,
            "alternatives": self.alternatives,
            "unknowns": self.unknowns,
            "confidence_note": self.confidence_note,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class BatchItem:
    signal_id: str
    status: str
    diagnosis: Diagnosis | None = None
    error: str | None = None


@dataclass(frozen=True)
class BatchResult:
    generated_at: str
    items: list[BatchItem] = field(default_factory=list)

    def batch_to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "items": [
                {
                    "signal_id": item.signal_id,
                    "status": item.status,
                    **({"diagnosis": item.diagnosis.diagnosis_to_dict()} if item.diagnosis is not None else {}),
                    **({"error": item.error} if item.error is not None else {}),
                }
                for item in self.items
            ],
        }


def parse_signal(raw: Any) -> DiagnosisInput:
    if not isinstance(raw, dict):
        raise ValueError("signal must be a JSON object")
    signal_id = raw.get("signal_id")
    scenario_id = raw.get("scenario_id")
    generated_at = raw.get("generated_at")
    trust = raw.get("trust")
    payload = raw.get("payload")
    context_extracts = raw.get("context_extracts")
    source_refs = raw.get("source_refs")
    if not isinstance(signal_id, str) or not signal_id:
        raise ValueError("signal_id must be a non-empty string")
    if scenario_id not in ALLOWED_SCENARIOS:
        raise ValueError(f"scenario_id must be one of {ALLOWED_SCENARIOS}, got {scenario_id!r}")
    if not isinstance(generated_at, str) or not generated_at:
        raise ValueError("generated_at must be a non-empty string")
    if trust != "unreleased":
        raise ValueError("trust must be 'unreleased'")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if not isinstance(context_extracts, list):
        raise ValueError("context_extracts must be a list")
    if (
        not isinstance(source_refs, list)
        or not source_refs
        or not all(isinstance(ref, str) and ref for ref in source_refs)
    ):
        raise ValueError("source_refs must be a non-empty list of strings")
    return DiagnosisInput(
        signal_id=signal_id,
        scenario_id=scenario_id,
        generated_at=generated_at,
        trust=trust,
        payload=payload,
        context_extracts=context_extracts,
        source_refs=source_refs,
    )
