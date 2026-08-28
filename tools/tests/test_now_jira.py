from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def contract() -> object:
    from tools.now_orchestrator.jira import ExecutionContract

    return ExecutionContract(
        owner="Mike",
        owner_account_id="account-mike",
        lane="B",
        blockers=("none",),
        acceptance_criteria=("AC-1",),
        definition_of_done=("DoD-1",),
        gate_id="RG-20260828-now-orchestrator",
        evidence_locators=("jira:PMM-5",),
        zones=("tools/now_orchestrator/jira",),
    )


def intent(**changes: object) -> object:
    from tools.now_orchestrator.jira import JiraIntent

    base: dict[str, object] = {
        "actor": "Mike",
        "operation": "edit",
        "project": "PMM",
        "issue_key": "PMM-5",
        "payload": {"fields": {"summary": "safe", "assignee": {"displayName": "Mike", "accountId": "account-mike"}, "execution_contract": contract().as_payload()}},  # type: ignore[attr-defined]
        "execution_contract": contract(),
        "assignee_account_id": "account-mike",
    }
    base.update(changes)
    return JiraIntent(**base)  # type: ignore[arg-type]


def ledger(tmp_path: Path) -> object:
    from tools.now_orchestrator.jira import JiraLedger

    common_dir = tmp_path / ".git"
    return JiraLedger(common_dir / "now" / "evidence" / "test.jsonl", common_dir=common_dir)


def test_authorize_allows_complete_single_project_execution_contract() -> None:
    from tools.now_orchestrator.jira import authorize

    decision = authorize(intent())

    assert decision.status == "AUTO"
    assert decision.reason == "single-issue safe write"


@pytest.mark.parametrize(
    "payload",
    [
        {"project": "PA"},
        {"fields": {"project": "OTHER"}},
        {"links": [{"project": "PA", "key": "PA-1"}]},
        {"links": [{"key": "PA-1"}]},
        {"fields": {"assignee": "Other"}},
        {"fields": {"assignee": {"displayName": "Mike", "accountId": "wrong"}}},
        {"bulk": True},
        {"issue_count": 2},
        {"fields": {"replaces_scope": True}},
        {"scope_replacement": "epic"},
        {"fields": {"parent": "PMM-1"}},
    ],
)
def test_payload_cannot_bypass_operation_boundary(payload: dict[str, object]) -> None:
    from tools.now_orchestrator.jira import authorize

    assert authorize(intent(payload=payload)).status != "AUTO"


def test_canonical_secret_detection_rejects_names_and_values() -> None:
    from tools.now_orchestrator.jira import authorize

    payloads = (
        {"nested": {"api" + "_token": "x"}},
        {"body": "Authorization" + ": " + "Bearer" + " " + "abc.def.ghi"},
        {"body": "AK" + "IAIOSFODNN7EXAMPLE"},
    )
    assert all(authorize(intent(payload=payload)).status == "DENY" for payload in payloads)


def test_execution_contract_is_required_and_validated() -> None:
    from tools.now_orchestrator.jira import ExecutionContract, authorize

    assert authorize(intent(execution_contract=None)).status == "DENY"
    bad = ExecutionContract("Mike", "", "B", (), ("AC",), ("DoD",), "", ("jira:PMM-5",), ())
    assert authorize(intent(execution_contract=bad)).status == "DENY"


def test_payload_contract_and_envelope_identity_must_match_exactly() -> None:
    from tools.now_orchestrator.jira import authorize

    payload = {"fields": {"summary": "safe", "assignee": {"displayName": "Mike", "accountId": "other"}, "execution_contract": contract().as_payload()}}  # type: ignore[attr-defined]
    assert authorize(intent(payload=payload)).status != "AUTO"
    malformed = contract().as_payload()  # type: ignore[attr-defined]
    malformed["zones"] = "not-a-list"
    payload["fields"]["assignee"] = {"displayName": "Mike", "accountId": "account-mike"}
    payload["fields"]["execution_contract"] = malformed
    assert authorize(intent(payload=payload)).status == "DENY"


def test_assign_requires_complete_contract_and_exact_envelope_identity() -> None:
    from tools.now_orchestrator.jira import authorize

    assign_payload = {"assignee": {"displayName": "Mike", "accountId": "account-mike"}, "execution_contract": contract().as_payload()}  # type: ignore[attr-defined]
    assert authorize(intent(operation="assign", payload=assign_payload, execution_contract=None, assignee_account_id=None)).status != "AUTO"
    assert authorize(intent(operation="assign", payload=assign_payload, assignee="Not Mike")).status != "AUTO"


def test_issue_count_rejects_bool_and_transition_id_must_be_nonempty() -> None:
    from tools.now_orchestrator.jira import authorize

    transition_payload = {"transition_id": "", "assignee": {"displayName": "Mike", "accountId": "account-mike"}, "execution_contract": contract().as_payload()}  # type: ignore[attr-defined]
    assert authorize(intent(operation="transition", payload=transition_payload, issue_count=True)).status != "AUTO"
    assert authorize(intent(operation="transition", payload=transition_payload)).status != "AUTO"


@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        ("comment", {"body": "audit"}),
        ("link", {"target": "PMM-6"}),
        ("transition", {"transition_id": "31"}),
    ],
)
def test_non_field_writes_require_payload_bound_contract(operation: str, payload: dict[str, object]) -> None:
    from tools.now_orchestrator.jira import authorize

    assert authorize(intent(operation=operation, payload=payload)).status != "AUTO"


def test_all_six_operations_share_strict_write_contract() -> None:
    from tools.now_orchestrator.jira import authorize

    bound = {"assignee": {"displayName": "Mike", "accountId": "account-mike"}, "execution_contract": contract().as_payload()}  # type: ignore[attr-defined]
    operations = (
        intent(operation="create", issue_key=None, payload={"fields": {"summary": "safe", **bound}}),
        intent(),
        intent(operation="comment", payload={"body": "audit", **bound}),
        intent(operation="link", payload={"target": "PMM-6", **bound}),
        intent(operation="assign", payload=bound),
        intent(operation="transition", payload={"transition_id": "31", **bound}),
    )

    assert all(authorize(write).status == "AUTO" for write in operations)  # type: ignore[arg-type]


def test_ledger_recomputes_decision_and_binds_digest(tmp_path: Path) -> None:
    from tools.now_orchestrator.jira import JiraDecision

    safe_ledger = ledger(tmp_path)
    decision, intent_id = safe_ledger.authorize(intent())  # type: ignore[attr-defined]
    assert decision.status == "AUTO"
    assert intent_id
    denied, denied_id = safe_ledger.authorize(intent(payload={"bulk": True}))  # type: ignore[attr-defined]
    assert denied.status != "AUTO"
    assert denied_id
    with pytest.raises(TypeError):
        safe_ledger.authorize(intent(), JiraDecision("AUTO", "forged", "digest"))  # type: ignore[attr-defined,call-arg]


def test_outcome_requires_evidence_then_failed_reconciliation_event(tmp_path: Path) -> None:
    from tools.now_orchestrator.jira import JiraReconciliation, JiraResult

    safe_ledger = ledger(tmp_path)
    _, intent_id = safe_ledger.authorize(intent())  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="remote evidence"):
        safe_ledger.record(JiraResult(intent_id, True, None))  # type: ignore[attr-defined]
    safe_ledger.record(JiraResult(intent_id, False, "mcp-error-1"))  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="reconciliation"):
        safe_ledger.record(JiraResult(intent_id, True, "remote-1"))  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="evidence"):
        safe_ledger.reconcile(JiraReconciliation(intent_id, "", False))  # type: ignore[attr-defined]
    safe_ledger.reconcile(JiraReconciliation(intent_id, "readback-1", False))  # type: ignore[attr-defined]
    safe_ledger.record(JiraResult(intent_id, True, "remote-1"))  # type: ignore[attr-defined]


def test_reconciliation_with_existing_effect_denies_retry(tmp_path: Path) -> None:
    from tools.now_orchestrator.jira import JiraReconciliation, JiraResult

    safe_ledger = ledger(tmp_path)
    _, intent_id = safe_ledger.authorize(intent())  # type: ignore[attr-defined]
    safe_ledger.record(JiraResult(intent_id, False, "mcp-error"))  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="denied"):
        safe_ledger.reconcile(JiraReconciliation(intent_id, "readback-existing", True))  # type: ignore[attr-defined]


def test_ledger_path_cannot_escape_or_follow_symlink(tmp_path: Path) -> None:
    from tools.now_orchestrator.jira import JiraLedger

    common_dir = tmp_path / ".git"
    with pytest.raises(ValueError, match="common-dir"):
        JiraLedger(tmp_path / "outside.jsonl", common_dir=common_dir)
    evidence = common_dir / "now" / "evidence"
    evidence.mkdir(parents=True)
    (common_dir / "now" / "escape").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="symlink"):
        JiraLedger(common_dir / "now" / "escape" / "ledger.jsonl", common_dir=common_dir)


def test_safe_gap_create_defers_link_until_live_readback() -> None:
    from tools.now_orchestrator.jira import classify_gap

    plan = classify_gap(
        project="PMM",
        current_issue_key="PMM-5",
        execution_contract=contract(),
        in_scope=False,
        unambiguous=True,
        blocker=False,
    )

    assert plan.action == "create_backlog"
    assert plan.current_issue_key == "PMM-5"
    assert [repair.operation for repair in plan.intents] == ["create"]
    assert plan.update_path
    from tools.now_orchestrator.jira import authorize
    assert authorize(plan.intents[0]).status == "AUTO"
    proposal = classify_gap(project="PMM", current_issue_key="PMM-5", execution_contract=contract(), in_scope=True, unambiguous=False, blocker=True)
    assert proposal.action == "proposal"
    assert not proposal.intents


def test_safe_gap_existing_backlog_updates_distinct_valid_key() -> None:
    from tools.now_orchestrator.jira import authorize, classify_gap

    plan = classify_gap(
        project="PMM",
        current_issue_key="PMM-5",
        existing_backlog_key="PMM-6",
        execution_contract=contract(),
        in_scope=False,
        unambiguous=True,
        blocker=False,
    )

    assert plan.action == "update_backlog"
    assert [repair.operation for repair in plan.intents] == ["edit", "comment", "link"]
    assert all(authorize(repair).status == "AUTO" for repair in plan.intents)
    self_link = classify_gap(project="PMM", current_issue_key="PMM-5", existing_backlog_key="PMM-5", execution_contract=contract(), in_scope=True, unambiguous=True, blocker=True)
    assert self_link.action == "proposal"
    assert not self_link.intents
