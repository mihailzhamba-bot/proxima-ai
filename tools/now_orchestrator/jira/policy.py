from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Literal


DecisionStatus = Literal["AUTO", "APPROVAL_REQUIRED", "DENY"]
_AUTO = frozenset({"create", "edit", "comment", "link", "assign", "transition"})
_APPROVAL = frozenset({"delete", "archive", "bulk"})
_SECRET_NAMES = ("secret", "token", "password", "api_key", "apikey", "authorization", "credential", "private_key")
_SECRET_VALUES = (re.compile(r"\bbearer\s+[a-z0-9._~+/-]+", re.I), re.compile(r"\beyJ[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\.[a-z0-9_-]{8,}\b", re.I), re.compile(r"\bAKIA[0-9A-Z]{16}\b"), re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"))
_KEY = re.compile(r"[A-Z][A-Z0-9]*-[1-9][0-9]*")


@dataclass(frozen=True)
class ExecutionContract:
    owner: str
    owner_account_id: str
    lane: str
    blockers: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    definition_of_done: tuple[str, ...]
    gate_id: str
    evidence_locators: tuple[str, ...]
    zones: tuple[str, ...]

    def as_payload(self) -> dict[str, object]:
        return {"owner": self.owner, "owner_account_id": self.owner_account_id, "lane": self.lane, "blockers": list(self.blockers), "acceptance_criteria": list(self.acceptance_criteria), "definition_of_done": list(self.definition_of_done), "gate_id": self.gate_id, "evidence_locators": list(self.evidence_locators), "zones": list(self.zones)}

    def valid(self) -> bool:
        collections = (self.blockers, self.acceptance_criteria, self.definition_of_done, self.evidence_locators, self.zones)
        return self.owner == "Mike" and isinstance(self.owner_account_id, str) and bool(self.owner_account_id) and self.lane in {"A", "B", "C"} and isinstance(self.gate_id, str) and bool(self.gate_id) and all(isinstance(values, tuple) and values and all(isinstance(item, str) and item for item in values) for values in collections)


@dataclass(frozen=True)
class JiraIntent:
    actor: str
    operation: str
    project: str
    issue_key: str | None
    payload: dict[str, Any]
    execution_contract: ExecutionContract | None = None
    issue_count: int = 1
    assignee: str | None = "Mike"
    assignee_account_id: str | None = None
    replaces_scope: bool = False
    def payload_digest(self) -> str:
        return sha256(json.dumps(self.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class JiraDecision:
    status: DecisionStatus
    reason: str
    payload_digest: str


@dataclass(frozen=True)
class JiraResult:
    intent_id: str
    success: bool
    remote_evidence_id: str | None


@dataclass(frozen=True)
class JiraReconciliation:
    intent_id: str
    remote_evidence_id: str
    effect_present: bool


@dataclass(frozen=True)
class JiraRepairPlan:
    action: Literal["link_current", "update_backlog", "create_backlog", "proposal"]
    reason: str
    current_issue_key: str
    intents: tuple[JiraIntent, ...]
    update_path: tuple[str, ...]


def _walk(value: object, names: tuple[str, ...] = ()) -> tuple[tuple[tuple[str, ...], object], ...]:
    if isinstance(value, dict):
        return tuple(item for key, child in value.items() for item in _walk(child, (*names, str(key))))
    if isinstance(value, list):
        return tuple(item for child in value for item in _walk(child, names))
    return ((names, value),)


def _secret(payload: object) -> bool:
    for names, value in _walk(payload):
        if any(marker in name.casefold() for name in names for marker in _SECRET_NAMES):
            return True
        if isinstance(value, str) and any(pattern.search(value) for pattern in _SECRET_VALUES):
            return True
    return False


def _deny(intent: JiraIntent, reason: str, approval: bool = False) -> JiraDecision:
    return JiraDecision("APPROVAL_REQUIRED" if approval else "DENY", reason, intent.payload_digest())


def _contract_payload(intent: JiraIntent, payload: dict[str, object]) -> JiraDecision | None:
    contract = intent.execution_contract
    embedded = payload.get("execution_contract")
    if contract is None or not contract.valid() or not isinstance(embedded, dict) or embedded != contract.as_payload():
        return _deny(intent, "payload must carry the exact complete execution contract")
    assignee = payload.get("assignee")
    if not isinstance(assignee, dict) or assignee != {"displayName": "Mike", "accountId": contract.owner_account_id}:
        return _deny(intent, "payload assignee must be Mike contract identity", True)
    if intent.actor != "Mike" or intent.assignee != "Mike" or intent.assignee_account_id != contract.owner_account_id:
        return _deny(intent, "envelope account identity does not match contract", True)
    return None


def _fields_payload(intent: JiraIntent, *, create: bool) -> JiraDecision | None:
    if set(intent.payload) != {"fields"} or not isinstance(intent.payload["fields"], dict):
        return _deny(intent, "operation payload schema is invalid")
    fields = intent.payload["fields"]
    allowed = {"execution_contract", "assignee", "summary"} if create else {"execution_contract", "assignee", "summary", "description"}
    content = tuple(fields.get(name) for name in ("summary", "description") if name in fields)
    if not set(fields).issubset(allowed) or "execution_contract" not in fields or "assignee" not in fields or not content or not all(isinstance(value, str) and value for value in content):
        return _deny(intent, "unknown or missing protected task field", True)
    return _contract_payload(intent, fields)


def _simple_schema(intent: JiraIntent) -> JiraDecision | None:
    payload = intent.payload
    contract_error = _contract_payload(intent, payload)
    if contract_error is not None:
        return contract_error
    if intent.operation == "comment":
        return None if set(payload) == {"body", "assignee", "execution_contract"} and isinstance(payload["body"], str) and payload["body"] else _deny(intent, "comment payload schema is invalid")
    if intent.operation == "link":
        target = payload.get("target")
        if set(payload) != {"target", "assignee", "execution_contract"} or not isinstance(target, str):
            return _deny(intent, "link payload schema is invalid")
        if target == intent.issue_key:
            return _deny(intent, "self-link is forbidden")
        return None if _KEY.fullmatch(target) and target.startswith(f"{intent.project}-") else _deny(intent, "link target is foreign or invalid", True)
    if intent.operation == "assign":
        account = payload.get("assignee")
        expected = intent.execution_contract.owner_account_id if intent.execution_contract else None
        return None if set(payload) == {"assignee", "execution_contract"} and account == {"displayName": "Mike", "accountId": expected} else _deny(intent, "assign payload identity is invalid", True)
    if intent.operation == "transition":
        return None if set(payload) == {"transition_id", "assignee", "execution_contract"} and isinstance(payload["transition_id"], str) and bool(payload["transition_id"]) else _deny(intent, "transition payload schema is invalid", True)
    return _deny(intent, "unsupported Jira operation")


def validate_write_intent(intent: JiraIntent) -> JiraDecision | None:
    """Return a fail-closed decision for an invalid executable write, else None."""
    if not isinstance(intent.payload, dict) or not isinstance(intent.actor, str) or not intent.actor or not isinstance(intent.project, str) or intent.project not in {"PA", "PMM"}:
        return _deny(intent, "missing or foreign Jira identity", True)
    if _secret(intent.payload):
        return _deny(intent, "payload contains a secret-shaped name or value")
    if not isinstance(intent.operation, str) or intent.operation not in _AUTO | _APPROVAL:
        return _deny(intent, "unsupported Jira operation")
    if intent.operation in _APPROVAL or type(intent.issue_count) is not int or intent.issue_count != 1 or intent.replaces_scope:
        return _deny(intent, "bulk, destructive, or scope replacement operation", True)
    if intent.operation == "create" and intent.issue_key is not None:
        return _deny(intent, "create must not name an existing issue key")
    if intent.operation != "create" and (not isinstance(intent.issue_key, str) or not _KEY.fullmatch(intent.issue_key) or not intent.issue_key.startswith(f"{intent.project}-")):
        return _deny(intent, "single issue key is invalid")
    if intent.operation == "create":
        return _fields_payload(intent, create=True)
    if intent.operation == "edit":
        return _fields_payload(intent, create=False)
    return _simple_schema(intent)


def authorize(intent: JiraIntent) -> JiraDecision:
    result = validate_write_intent(intent)
    return result or JiraDecision("AUTO", "single-issue safe write", intent.payload_digest())


def _task_fields(contract: ExecutionContract, summary: str) -> dict[str, object]:
    return {"fields": {"summary": summary, "assignee": {"displayName": "Mike", "accountId": contract.owner_account_id}, "execution_contract": contract.as_payload()}}


def _bound_payload(contract: ExecutionContract, **payload: object) -> dict[str, object]:
    return {**payload, "assignee": {"displayName": "Mike", "accountId": contract.owner_account_id}, "execution_contract": contract.as_payload()}


def classify_gap(*, project: str, current_issue_key: str, execution_contract: ExecutionContract, in_scope: bool, unambiguous: bool, blocker: bool, existing_backlog_key: str | None = None) -> JiraRepairPlan:
    if not unambiguous:
        return JiraRepairPlan("proposal", "ambiguous gap requires approval", current_issue_key, (), ("obtain explicit repair approval",))
    if not isinstance(project, str) or project not in {"PA", "PMM"} or not isinstance(current_issue_key, str) or not _KEY.fullmatch(current_issue_key) or not current_issue_key.startswith(f"{project}-"):
        return JiraRepairPlan("proposal", "current issue key is unresolved", current_issue_key, (), ("live read current key",))
    if not execution_contract.valid():
        return JiraRepairPlan("proposal", "execution contract is invalid", current_issue_key, (), ("restore complete execution contract",))
    account_id = execution_contract.owner_account_id
    if existing_backlog_key is None:
        create = JiraIntent("Mike", "create", project, None, _task_fields(execution_contract, "Safe gap backlog item"), execution_contract, assignee_account_id=account_id)
        return JiraRepairPlan("create_backlog", "safe gap needs a new backlog issue", current_issue_key, (create,), ("authorize create", "read back created key", "classify update with resolved backlog key"))
    if not isinstance(existing_backlog_key, str) or not _KEY.fullmatch(existing_backlog_key) or not existing_backlog_key.startswith(f"{project}-") or existing_backlog_key == current_issue_key:
        return JiraRepairPlan("proposal", "resolved backlog key is invalid or self-referential", current_issue_key, (), ("live read a distinct backlog key",))
    intents = (
        JiraIntent("Mike", "edit", project, existing_backlog_key, _task_fields(execution_contract, "Update safe gap backlog item"), execution_contract, assignee_account_id=account_id),
        JiraIntent("Mike", "comment", project, existing_backlog_key, _bound_payload(execution_contract, body="Record current-task relationship after live readback."), execution_contract, assignee_account_id=account_id),
        JiraIntent("Mike", "link", project, current_issue_key, _bound_payload(execution_contract, target=existing_backlog_key), execution_contract, assignee_account_id=account_id),
    )
    action: Literal["link_current", "update_backlog"] = "link_current" if in_scope and blocker else "update_backlog"
    return JiraRepairPlan(action, "safe gap updates a distinct resolved backlog issue", current_issue_key, intents, ("authorize edit/comment/link", "read back all remote evidence"))
