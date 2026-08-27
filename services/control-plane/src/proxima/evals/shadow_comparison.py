"""Blind, immutable comparison of independently frozen human and AI answers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from proxima.application.scenario_engine import canonical_hash

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
TerminalState = Literal[
    "NO_ACTION",
    "ACTIONS_READY",
    "AWAITING_APPROVAL",
    "BLOCKED",
    "INCIDENT",
]
AdjudicationTaxonomy = Literal[
    "AI_ERROR",
    "HUMAN_ERROR",
    "AMBIGUOUS",
    "MISSING_CONTEXT",
    "POLICY_GAP",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ShadowAnswerSubmission(_StrictModel):
    answer_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    actor_kind: Literal["human", "ai"]
    case_or_run_id: str = Field(min_length=1)
    scenario_id: ScenarioId
    snapshot_id: str = Field(min_length=1)
    snapshot_checksum: str = Field(min_length=1)
    passport_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    open_actions_hash: str = Field(min_length=1)
    signals: tuple[str, ...]
    cause_status: Literal["proven", "hypothesis", "unknown"]
    cause: str = Field(min_length=1)
    evidence_ref_ids: tuple[str, ...]
    state: TerminalState
    action: str = Field(min_length=1)
    owner: str | None
    dependency: str | None
    risk: Literal["R0", "R1", "R2", "R3"]
    review_at: datetime | None


class ShadowSubmissionReceipt(_StrictModel):
    submission_id: str = Field(min_length=1)
    locator: str = Field(pattern=r"^shadow://submissions/[0-9a-f-]+$")
    commitment: str = Field(pattern=r"^[0-9a-f]{64}$")
    submission_order: int = Field(gt=0)
    artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor_kind: Literal["human", "ai"]


class FrozenShadowAnswer(ShadowAnswerSubmission):
    submission_id: str = Field(min_length=1)
    answer_locator: str = Field(pattern=r"^shadow://submissions/[0-9a-f-]+$")
    submission_order: int = Field(gt=0)
    frozen_at: datetime
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    answer_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    freeze_provenance_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_verified_artifact(
        cls,
        submission: ShadowAnswerSubmission,
        receipt: ShadowSubmissionReceipt,
        frozen_at: datetime,
        artifact_bytes: bytes,
    ) -> FrozenShadowAnswer:
        """Build a frozen value only after a repository byte-verifies its artifact."""

        artifact_checksum = hashlib.sha256(artifact_bytes).hexdigest()
        if artifact_checksum != receipt.artifact_checksum:
            raise ValueError("SHADOW_ARTIFACT_CHECKSUM_MISMATCH")
        canonical_bytes = canonical_submission_bytes(submission)
        if artifact_bytes != canonical_bytes:
            raise ValueError("SHADOW_ARTIFACT_BYTES_MISMATCH")
        if receipt.actor_kind != submission.actor_kind:
            raise ValueError("SHADOW_SUBMISSION_ACTOR_MISMATCH")
        expected_commitment = shadow_commitment(
            receipt.submission_id,
            receipt.locator,
            receipt.submission_order,
            receipt.actor_kind,
            receipt.artifact_checksum,
            frozen_at,
        )
        if receipt.commitment != expected_commitment:
            raise ValueError("SHADOW_SUBMISSION_COMMITMENT_MISMATCH")
        values = submission.model_dump(mode="python")
        values.update(
            submission_id=receipt.submission_id,
            answer_locator=receipt.locator,
            submission_order=receipt.submission_order,
            frozen_at=frozen_at,
            input_hash=_input_hash(submission),
            output_hash=_output_hash(submission),
            answer_checksum=receipt.artifact_checksum,
            freeze_provenance_hash=receipt.commitment,
        )
        return cls.model_validate(values)

    @model_validator(mode="after")
    def hashes_match_frozen_content(self) -> FrozenShadowAnswer:
        submission = ShadowAnswerSubmission.model_validate(
            self.model_dump(mode="python", include=set(ShadowAnswerSubmission.model_fields))
        )
        if self.input_hash != _input_hash(submission):
            raise ValueError("SHADOW_INPUT_HASH_MISMATCH")
        if self.output_hash != _output_hash(submission):
            raise ValueError("SHADOW_OUTPUT_HASH_MISMATCH")
        if (
            self.answer_checksum
            != hashlib.sha256(canonical_submission_bytes(submission)).hexdigest()
        ):
            raise ValueError("SHADOW_ANSWER_CHECKSUM_MISMATCH")
        if self.freeze_provenance_hash != shadow_commitment(
            self.submission_id,
            self.answer_locator,
            self.submission_order,
            self.actor_kind,
            self.answer_checksum,
            self.frozen_at,
        ):
            raise ValueError("SHADOW_FREEZE_PROVENANCE_MISMATCH")
        return self


def canonical_submission_bytes(submission: ShadowAnswerSubmission) -> bytes:
    return json.dumps(
        submission.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _input_hash(submission: ShadowAnswerSubmission) -> str:
    return canonical_hash(
        submission.model_dump(
            mode="json",
            include={
                "case_or_run_id",
                "scenario_id",
                "snapshot_id",
                "snapshot_checksum",
                "passport_version",
                "policy_version",
                "open_actions_hash",
            },
        )
    )


def _output_hash(submission: ShadowAnswerSubmission) -> str:
    return canonical_hash(
        submission.model_dump(
            mode="json",
            include={
                "answer_id",
                "actor_id",
                "actor_kind",
                "case_or_run_id",
                "scenario_id",
                "signals",
                "cause_status",
                "cause",
                "evidence_ref_ids",
                "state",
                "action",
                "owner",
                "dependency",
                "risk",
                "review_at",
            },
        )
    )


def shadow_commitment(
    submission_id: str,
    locator: str,
    submission_order: int,
    actor_kind: str,
    artifact_checksum: str,
    frozen_at: datetime,
) -> str:
    return canonical_hash(
        {
            "submission_id": submission_id,
            "locator": locator,
            "submission_order": submission_order,
            "actor_kind": actor_kind,
            "artifact_checksum": artifact_checksum,
            "frozen_at": frozen_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        }
    )


class ShadowSubmissionRepository(Protocol):
    def submit(self, submission: ShadowAnswerSubmission) -> ShadowSubmissionReceipt: ...

    def resolve_pair(
        self,
        human: ShadowSubmissionReceipt,
        ai: ShadowSubmissionReceipt,
    ) -> tuple[FrozenShadowAnswer, FrozenShadowAnswer]: ...


_SHADOW_IDENTITY_FIELDS = (
    "case_or_run_id",
    "scenario_id",
    "snapshot_id",
    "snapshot_checksum",
    "passport_version",
    "policy_version",
    "open_actions_hash",
    "input_hash",
)


def validate_reveal_pair(human: FrozenShadowAnswer, ai: FrozenShadowAnswer) -> None:
    if human.actor_kind != "human" or ai.actor_kind != "ai":
        raise ValueError("SHADOW_ACTOR_KIND_MISMATCH")
    if human.actor_id == ai.actor_id:
        raise ValueError("SHADOW_ACTOR_SEPARATION_REQUIRED")
    if any(getattr(human, field) != getattr(ai, field) for field in _SHADOW_IDENTITY_FIELDS):
        raise ValueError("SHADOW_FROZEN_INPUT_MISMATCH")
    if human.answer_locator == ai.answer_locator:
        raise ValueError("SHADOW_ANSWER_LOCATOR_COLLISION")


class InMemoryShadowSubmissionRepository:
    """Offline test profile with the same opaque receipt boundary as PostgreSQL."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._records: dict[str, tuple[ShadowSubmissionReceipt, datetime, bytes]] = {}
        self._next_order = 1
        self.revealed_pairs: list[tuple[str, str]] = []

    def submit(self, submission: ShadowAnswerSubmission) -> ShadowSubmissionReceipt:
        artifact_bytes = canonical_submission_bytes(submission)
        artifact_checksum = hashlib.sha256(artifact_bytes).hexdigest()
        submission_id = str(uuid4())
        locator = f"shadow://submissions/{submission_id}"
        order = self._next_order
        self._next_order += 1
        frozen_at = self._clock()
        receipt = ShadowSubmissionReceipt(
            submission_id=submission_id,
            locator=locator,
            commitment=shadow_commitment(
                submission_id,
                locator,
                order,
                submission.actor_kind,
                artifact_checksum,
                frozen_at,
            ),
            submission_order=order,
            artifact_checksum=artifact_checksum,
            actor_kind=submission.actor_kind,
        )
        self._records[submission_id] = (receipt, frozen_at, artifact_bytes)
        return receipt

    def resolve_pair(
        self,
        human: ShadowSubmissionReceipt,
        ai: ShadowSubmissionReceipt,
    ) -> tuple[FrozenShadowAnswer, FrozenShadowAnswer]:
        human_answer = self._resolve(human)
        ai_answer = self._resolve(ai)
        validate_reveal_pair(human_answer, ai_answer)
        pair = (human.submission_id, ai.submission_id)
        if pair not in self.revealed_pairs:
            self.revealed_pairs.append(pair)
        return human_answer, ai_answer

    def _resolve(self, receipt: ShadowSubmissionReceipt) -> FrozenShadowAnswer:
        record = self._records.get(receipt.submission_id)
        if record is None or record[0] != receipt:
            raise ValueError("SHADOW_SUBMISSION_RECEIPT_INVALID")
        persisted_receipt, frozen_at, artifact_bytes = record
        if hashlib.sha256(artifact_bytes).hexdigest() != persisted_receipt.artifact_checksum:
            raise ValueError("SHADOW_ARTIFACT_CHECKSUM_MISMATCH")
        submission = ShadowAnswerSubmission.model_validate_json(artifact_bytes)
        return FrozenShadowAnswer.from_verified_artifact(
            submission,
            persisted_receipt,
            frozen_at,
            artifact_bytes,
        )


class ShadowSamplingPolicy(_StrictModel):
    mandatory_categories: tuple[
        Literal["critical", "BLOCKED", "INCIDENT", "override", "disagreement"],
        ...,
    ]
    accepted_no_action_sample_rate: float | None = Field(default=None, ge=0, le=1)
    rate_source: str | None
    rate_source_date: date | None
    approved_by: str | None
    approved_at: date | None

    @model_validator(mode="after")
    def numeric_rate_requires_source_and_approval(self) -> ShadowSamplingPolicy:
        required = {"critical", "BLOCKED", "INCIDENT", "override", "disagreement"}
        if set(self.mandatory_categories) != required:
            raise ValueError("MANDATORY_SHADOW_SAMPLE_CATEGORIES_REQUIRED")
        if self.accepted_no_action_sample_rate is not None and not (
            self.rate_source
            and self.rate_source_date
            and self.approved_by == "Mike"
            and self.approved_at
        ):
            raise ValueError("UNAPPROVED_SHADOW_SAMPLE_RATE")
        return self

    @classmethod
    def unapproved(cls) -> ShadowSamplingPolicy:
        return cls(
            mandatory_categories=(
                "critical",
                "BLOCKED",
                "INCIDENT",
                "override",
                "disagreement",
            ),
            accepted_no_action_sample_rate=None,
            rate_source=None,
            rate_source_date=None,
            approved_by=None,
            approved_at=None,
        )


class ShadowAdjudication(_StrictModel):
    taxonomy: AdjudicationTaxonomy
    rationale: str = Field(min_length=1)
    domain_owner: str = Field(min_length=1)
    policy_owner: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    resolved_at: datetime


class ShadowDifferences(_StrictModel):
    signals: tuple[tuple[str, ...], tuple[str, ...]] | None
    cause_status: tuple[str, str] | None
    cause: tuple[str, str] | None
    evidence: tuple[tuple[str, ...], tuple[str, ...]] | None
    state: tuple[str, str] | None
    action: tuple[str, str] | None
    owner: tuple[str | None, str | None] | None
    dependency: tuple[str | None, str | None] | None
    risk: tuple[str, str] | None
    review_at: tuple[datetime | None, datetime | None] | None


class ShadowComparisonRecord(_StrictModel):
    comparison_id: str = Field(min_length=1)
    created_at: datetime
    case_or_run_id: str
    scenario_id: ScenarioId
    frozen_input_hash: str
    human_answer_hash: str
    ai_answer_hash: str
    human_answer_locator: str
    ai_answer_locator: str
    human_answer_checksum: str
    ai_answer_checksum: str
    human_freeze_provenance_hash: str
    ai_freeze_provenance_hash: str
    human_frozen_at: datetime
    ai_frozen_at: datetime
    differences: ShadowDifferences
    adjudication: ShadowAdjudication | None
    sampling_policy: ShadowSamplingPolicy


class ShadowComparator:
    """Compares two frozen records only after their shared input identity matches."""

    def __init__(self, repository: ShadowSubmissionRepository) -> None:
        self._repository = repository

    def compare(
        self,
        *,
        human: ShadowSubmissionReceipt,
        ai: ShadowSubmissionReceipt,
        sampling_policy: ShadowSamplingPolicy,
        adjudication: ShadowAdjudication | None = None,
    ) -> ShadowComparisonRecord:
        human, ai = self._repository.resolve_pair(human, ai)
        validate_reveal_pair(human, ai)
        differences = ShadowDifferences(
            signals=self._pair(human.signals, ai.signals),
            cause_status=self._pair(human.cause_status, ai.cause_status),
            cause=self._pair(human.cause, ai.cause),
            evidence=self._pair(human.evidence_ref_ids, ai.evidence_ref_ids),
            state=self._pair(human.state, ai.state),
            action=self._pair(human.action, ai.action),
            owner=self._pair(human.owner, ai.owner),
            dependency=self._pair(human.dependency, ai.dependency),
            risk=self._pair(human.risk, ai.risk),
            review_at=self._pair(human.review_at, ai.review_at),
        )
        basis = {
            "case_or_run_id": human.case_or_run_id,
            "scenario_id": human.scenario_id,
            "input_hash": human.input_hash,
            "human_answer_hash": human.output_hash,
            "ai_answer_hash": ai.output_hash,
        }
        return ShadowComparisonRecord(
            comparison_id=canonical_hash(basis),
            created_at=max(human.frozen_at, ai.frozen_at),
            case_or_run_id=human.case_or_run_id,
            scenario_id=human.scenario_id,
            frozen_input_hash=human.input_hash,
            human_answer_hash=human.output_hash,
            ai_answer_hash=ai.output_hash,
            human_answer_locator=human.answer_locator,
            ai_answer_locator=ai.answer_locator,
            human_answer_checksum=human.answer_checksum,
            ai_answer_checksum=ai.answer_checksum,
            human_freeze_provenance_hash=human.freeze_provenance_hash,
            ai_freeze_provenance_hash=ai.freeze_provenance_hash,
            human_frozen_at=human.frozen_at,
            ai_frozen_at=ai.frozen_at,
            differences=differences,
            adjudication=adjudication,
            sampling_policy=sampling_policy,
        )

    @staticmethod
    def _pair[ValueT](human: ValueT, ai: ValueT) -> tuple[ValueT, ValueT] | None:
        return None if human == ai else (human, ai)
