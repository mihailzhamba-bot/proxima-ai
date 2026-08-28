from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TRACK_ORDER = ("B", "C", "A")
MANDATORY_SOURCES = ("jira", "git", "orca", "handoff", "tasks", "exec_plans")


@dataclass(frozen=True)
class SourceSection:
    name: str
    fresh: bool
    payload: dict[str, Any]


@dataclass(frozen=True)
class JiraIssue:
    key: str
    track: str
    lifecycle: str
    owner: str
    owned: bool
    ready: bool
    dependency_critical_path: int
    jira_priority: int
    safe_slice: int
    outcome: str
    blockers: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    definition_of_done: tuple[str, ...]
    zones: tuple[str, ...]
    sources: tuple[str, ...]

    def get(self, name: str, default: Any = None) -> Any:
        return getattr(self, name, default)


@dataclass(frozen=True)
class JiraSection:
    fresh: bool
    issues: tuple[JiraIssue, ...]


@dataclass(frozen=True)
class GitSection:
    fresh: bool
    branches: tuple[Any, ...]
    pull_requests: tuple[Any, ...]
    worktrees: tuple[Any, ...]


@dataclass(frozen=True)
class OrcaSection:
    fresh: bool
    runs: tuple[Any, ...]
    tasks: tuple[Any, ...]
    workers: tuple[Any, ...]
    gates: tuple[Any, ...]


@dataclass(frozen=True)
class HandoffSection:
    fresh: bool
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class TasksSection:
    fresh: bool
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class ExecPlansSection:
    fresh: bool
    plans: tuple[Any, ...]


@dataclass(frozen=True)
class Snapshot:
    version: str
    captured_at: str
    sections: dict[str, SourceSection]
    issues: tuple[JiraIssue, ...]
    diagnostics: tuple[str, ...]
    jira: JiraSection | None
    git: GitSection | None
    orca: OrcaSection | None
    handoff: HandoffSection | None
    tasks: TasksSection | None
    exec_plans: ExecPlansSection | None


@dataclass(frozen=True)
class Card:
    track: str
    action: str
    key: str | None
    outcome: str | None
    owner: str | None
    blockers: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    definition_of_done: tuple[str, ...]
    zones: tuple[str, ...]
    sources: tuple[str, ...]
    captured_at: str | None
    rule: str | None
    reason: str | None = None
    current_state: str | None = None
    next_gate: str | None = None
    recovery_action: str | None = None


@dataclass(frozen=True)
class NowDecision:
    snapshot_version: str
    captured_at: str
    cards: tuple[Card, ...]
    recommendation_key: str | None
    diagnostics: tuple[str, ...]
    mutation_intent: None = None
