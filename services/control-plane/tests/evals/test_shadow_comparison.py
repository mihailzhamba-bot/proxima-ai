from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from proxima.evals.shadow_comparison import (
    InMemoryShadowSubmissionRepository,
    ShadowAnswerSubmission,
    ShadowComparator,
    ShadowSamplingPolicy,
)

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _answer(actor_kind: str, *, policy_version: str = "policy-v1") -> ShadowAnswerSubmission:
    return ShadowAnswerSubmission(
        answer_id=f"answer-{actor_kind}",
        actor_id="manager-001" if actor_kind == "human" else "candidate-001",
        actor_kind=actor_kind,
        case_or_run_id="shadow-case-001",
        scenario_id="SCN-003",
        snapshot_id="snapshot-shadow-001",
        snapshot_checksum="sha256:shadow-snapshot",
        passport_version="passport-v1",
        policy_version=policy_version,
        open_actions_hash="sha256:open-actions",
        signals=("profit_input_missing",),
        cause_status="unknown",
        cause="unknown",
        evidence_ref_ids=("ref-pnl",),
        state="BLOCKED",
        action="request_missing_cogs" if actor_kind == "human" else "request_inputs",
        owner="account-manager",
        dependency="client-cogs",
        risk="R0",
        review_at=NOW,
    )


def test_submission_rejects_caller_controlled_freeze_provenance() -> None:
    payload = _answer("human").model_dump(mode="python")
    payload.update(
        answer_locator="missing://caller-controlled",
        counterpart_visible_at_freeze=False,
        answer_checksum="0" * 64,
    )

    with pytest.raises(ValidationError):
        ShadowAnswerSubmission.model_validate(payload)


def test_comparison_uses_server_receipts_and_persists_verified_commitments() -> None:
    repository = InMemoryShadowSubmissionRepository(clock=lambda: NOW)
    human = repository.submit(_answer("human"))
    ai = repository.submit(_answer("ai"))

    record = ShadowComparator(repository).compare(
        human=human,
        ai=ai,
        sampling_policy=ShadowSamplingPolicy.unapproved(),
    )

    assert (human.submission_order, ai.submission_order) == (1, 2)
    assert human.locator.startswith("shadow://submissions/")
    assert record.human_answer_locator == human.locator
    assert record.ai_answer_locator == ai.locator
    assert record.human_answer_checksum == human.artifact_checksum
    assert record.ai_answer_checksum == ai.artifact_checksum
    assert record.human_freeze_provenance_hash == human.commitment
    assert record.ai_freeze_provenance_hash == ai.commitment
    assert repository.revealed_pairs == [(human.submission_id, ai.submission_id)]


def test_arbitrary_missing_locator_is_rejected_without_reveal() -> None:
    repository = InMemoryShadowSubmissionRepository(clock=lambda: NOW)
    human = repository.submit(_answer("human"))
    ai = repository.submit(_answer("ai"))
    forged = human.model_copy(update={"locator": "missing://caller-controlled"})

    with pytest.raises(ValueError, match="SHADOW_SUBMISSION_RECEIPT_INVALID"):
        ShadowComparator(repository).compare(
            human=forged,
            ai=ai,
            sampling_policy=ShadowSamplingPolicy.unapproved(),
        )

    assert repository.revealed_pairs == []


def test_resolver_byte_verifies_both_artifacts_before_reveal() -> None:
    repository = InMemoryShadowSubmissionRepository(clock=lambda: NOW)
    human = repository.submit(_answer("human"))
    ai = repository.submit(_answer("ai"))
    receipt, frozen_at, _ = repository._records[ai.submission_id]
    repository._records[ai.submission_id] = (receipt, frozen_at, b"{}")

    with pytest.raises(ValueError, match="SHADOW_ARTIFACT_CHECKSUM_MISMATCH"):
        ShadowComparator(repository).compare(
            human=human,
            ai=ai,
            sampling_policy=ShadowSamplingPolicy.unapproved(),
        )

    assert repository.revealed_pairs == []


def test_mismatched_frozen_inputs_are_rejected_before_reveal() -> None:
    repository = InMemoryShadowSubmissionRepository(clock=lambda: NOW)
    human = repository.submit(_answer("human"))
    ai = repository.submit(_answer("ai", policy_version="policy-v2"))

    with pytest.raises(ValueError, match="SHADOW_FROZEN_INPUT_MISMATCH"):
        ShadowComparator(repository).compare(
            human=human,
            ai=ai,
            sampling_policy=ShadowSamplingPolicy.unapproved(),
        )

    assert repository.revealed_pairs == []
