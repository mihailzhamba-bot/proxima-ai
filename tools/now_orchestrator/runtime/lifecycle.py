from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
import json
from typing import Callable

from ..core import Snapshot, select
from .claims import ClaimRequest, ClaimStore, normalize_zones

class LifecycleState(StrEnum):
    SELECTED = "SELECTED"; CONFIRMED = "CONFIRMED"; DISPATCHED = "DISPATCHED"; VERIFYING = "VERIFYING"; REVIEWING = "REVIEWING"; MERGE_GATE = "MERGE_GATE"; MERGED = "MERGED"; SYNCING = "SYNCING"; DONE = "DONE"; BLOCKED_CONFLICT = "BLOCKED_CONFLICT"; BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"

_NEXT = {LifecycleState.CONFIRMED: LifecycleState.DISPATCHED, LifecycleState.DISPATCHED: LifecycleState.VERIFYING, LifecycleState.VERIFYING: LifecycleState.REVIEWING, LifecycleState.REVIEWING: LifecycleState.MERGE_GATE, LifecycleState.MERGE_GATE: LifecycleState.MERGED, LifecycleState.MERGED: LifecycleState.SYNCING, LifecycleState.SYNCING: LifecycleState.DONE}

@dataclass(frozen=True)
class GoCommand:
    key: str; owner: str

@dataclass(frozen=True)
class ConvergenceEvidence:
    merge_commit: str; jira: bool; orca: bool; git: bool; handoff: bool; tasks: bool; exec_plan: bool; jira_ref: str; orca_ref: str; git_ref: str; handoff_ref: str; tasks_ref: str; exec_plan_ref: str
    def valid(self) -> bool:
        return all(value is True for value in (self.jira, self.orca, self.git, self.handoff, self.tasks, self.exec_plan)) and all(isinstance(value, str) and value for value in (self.merge_commit, self.jira_ref, self.orca_ref, self.git_ref, self.handoff_ref, self.tasks_ref, self.exec_plan_ref))

@dataclass(frozen=True)
class ActionPlan:
    key: str | None; track: str | None; state: LifecycleState; run_id: str | None; task_id: str | None; worker_id: str | None; claim_token: str | None; dispatch: bool; should_dispatch: bool; blocked: bool = False; reason: str | None = None
    def as_dict(self) -> dict[str, object]:
        return {"blocked": self.blocked, "claim_token": self.claim_token, "dispatch": self.dispatch, "key": self.key, "reason": self.reason, "run_id": self.run_id, "should_dispatch": self.should_dispatch, "state": self.state, "task_id": self.task_id, "track": self.track, "worker_id": self.worker_id}
    def transition(self, target: LifecycleState, evidence: ConvergenceEvidence | None = None) -> ActionPlan:
        if _NEXT.get(self.state) is not target: raise ValueError("invalid lifecycle transition")
        if target is LifecycleState.DONE and (evidence is None or not evidence.valid()):
            return ActionPlan(self.key, self.track, LifecycleState.BLOCKED_EXTERNAL, self.run_id, self.task_id, self.worker_id, self.claim_token, False, False, True, "missing typed close convergence")
        return ActionPlan(self.key, self.track, target, self.run_id, self.task_id, self.worker_id, self.claim_token, False, target is LifecycleState.CONFIRMED)

def _blocked(reason: str) -> ActionPlan:
    return ActionPlan(None, None, LifecycleState.BLOCKED_EXTERNAL, None, None, None, None, False, False, True, reason)

def _captured_at(value: str, clock: Callable[[], datetime], max_age: timedelta) -> bool:
    try: captured = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: return False
    if captured.tzinfo is None: return False
    now = clock()
    if now.tzinfo is None: raise ValueError("clock must be timezone-aware")
    age = now.astimezone(UTC) - captured.astimezone(UTC)
    return timedelta(0) <= age <= max_age

def _snapshot_digest(snapshot: Snapshot) -> str:
    return sha256(json.dumps(asdict(snapshot), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def advance(command: GoCommand, snapshot: Snapshot, claims: ClaimStore, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC), max_age: timedelta = timedelta(minutes=5)) -> ActionPlan:
    if not isinstance(command.key, str) or not command.key or not isinstance(command.owner, str) or not command.owner: return _blocked("exact key and owner are required")
    if snapshot.diagnostics or not _captured_at(snapshot.captured_at, clock, max_age): return _blocked("fresh complete timestamped snapshot is required")
    decision = select(snapshot); card = next((item for item in decision.cards if item.key == command.key), None)
    if decision.recommendation_key != command.key or card is None or card.track not in {"A", "B", "C"}: return _blocked("key does not match the fresh selected snapshot")
    if card.owner != "Mike" or command.owner != card.owner: return _blocked("command owner does not match selected Mike owner")
    try: zones = normalize_zones(card.zones)
    except ValueError as error: return _blocked(str(error))
    provenance = sha256(f"{snapshot.version}\0{snapshot.captured_at}\0{command.key}\0{card.track}\0{','.join(zones)}".encode()).hexdigest()[:32]
    result = claims.claim(ClaimRequest(command.key, card.track, zones, command.owner, f"now-{provenance}", f"task-{provenance}", f"worker-{provenance}", snapshot.version, snapshot.captured_at, _snapshot_digest(snapshot)))
    if result.claim is None: return _blocked(result.reason or "claim rejected")
    claim = result.claim
    return ActionPlan(claim.key, claim.track, LifecycleState.CONFIRMED, claim.run_id, claim.task_id, claim.worker_id, claim.token, False, True, False, "T04 dispatch is intentionally not executed")
