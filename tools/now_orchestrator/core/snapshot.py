from __future__ import annotations

from typing import Any

from .models import ExecPlansSection, GitSection, HandoffSection, JiraIssue, JiraSection, OrcaSection, Snapshot, SourceSection, TasksSection


_LIFECYCLES = {"READY", "SELECTED", "CONFIRMED", "DISPATCHED", "VERIFYING", "REVIEWING", "MERGE_GATE", "MERGED", "SYNCING", "IMPLEMENTED", "VERIFY_PASSED", "REVIEW_PASSED", "JIRA_DOC_TAIL", "BLOCKED_GATE", "NEEDS_UNBLOCK"}
_ISSUE_TEXT_LISTS = ("blockers", "acceptance_criteria", "definition_of_done", "zones", "sources")


def _mapping(value: object) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _string_list(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return None
    return tuple(value)


def _issue(value: object, index: int) -> tuple[JiraIssue | None, str | None]:
    raw = _mapping(value)
    if raw is None:
        return None, f"malformed Jira issue {index}: not an object"
    key, track, lifecycle, owner = (raw.get(name) for name in ("key", "track", "lifecycle", "owner"))
    if not isinstance(key, str) or not key:
        return None, f"malformed Jira issue {index}: key"
    if track not in {"A", "B", "C", "D"}:
        return None, f"malformed Jira issue {index}: track"
    if lifecycle not in _LIFECYCLES:
        return None, f"malformed Jira issue {index}: lifecycle"
    if not isinstance(owner, str) or not owner:
        return None, f"malformed Jira issue {index}: owner"
    if type(raw.get("owned")) is not bool or type(raw.get("ready")) is not bool:
        return None, f"malformed Jira issue {index}: readiness"
    rankings = tuple(raw.get(name) for name in ("dependency_critical_path", "jira_priority", "safe_slice"))
    if any(type(item) is not int or item < 0 for item in rankings):
        return None, f"malformed Jira issue {index}: ranking"
    outcome = raw.get("outcome")
    if not isinstance(outcome, str) or not outcome:
        return None, f"malformed Jira issue {index}: outcome evidence"
    lists = {name: _string_list(raw.get(name)) for name in _ISSUE_TEXT_LISTS}
    if any(items is None for items in lists.values()) or not lists["sources"]:
        return None, f"malformed Jira issue {index}: evidence"
    return JiraIssue(key, track, lifecycle, owner, raw["owned"], raw["ready"], rankings[0], rankings[1], rankings[2], outcome, lists["blockers"] or (), lists["acceptance_criteria"] or (), lists["definition_of_done"] or (), lists["zones"] or (), lists["sources"] or ()), None


def _payload(raw: object, name: str, diagnostics: list[str]) -> tuple[bool, dict[str, Any]] | None:
    envelope = _mapping(raw)
    if envelope is None:
        diagnostics.append(f"missing source: {name}")
        return None
    payload = _mapping(envelope.get("payload"))
    if payload is None:
        diagnostics.append(f"missing source payload: {name}")
        return None
    fresh = envelope.get("fresh") is True
    if not fresh:
        diagnostics.append(f"stale source: {name}")
    return fresh, payload


def _load_jira(raw: object, diagnostics: list[str]) -> JiraSection | None:
    parsed = _payload(raw, "jira", diagnostics)
    if parsed is None:
        return None
    fresh, payload = parsed
    values = payload.get("issues")
    if not isinstance(values, list):
        diagnostics.append("malformed source payload: jira")
        return None
    issues: list[JiraIssue] = []
    for index, value in enumerate(values):
        item, error = _issue(value, index)
        if error:
            diagnostics.append(error)
        elif item:
            issues.append(item)
    return JiraSection(fresh, tuple(issues))


def _load_git(raw: object, diagnostics: list[str]) -> GitSection | None:
    parsed = _payload(raw, "git", diagnostics)
    if parsed is None:
        return None
    fresh, payload = parsed
    fields = tuple(payload.get(name) for name in ("branches", "pull_requests", "worktrees"))
    if not all(isinstance(field, list) for field in fields):
        diagnostics.append("malformed source payload: git")
        return None
    return GitSection(fresh, *(tuple(field) for field in fields))


def _load_orca(raw: object, diagnostics: list[str]) -> OrcaSection | None:
    parsed = _payload(raw, "orca", diagnostics)
    if parsed is None:
        return None
    fresh, payload = parsed
    fields = tuple(payload.get(name) for name in ("runs", "tasks", "workers", "gates"))
    if not all(isinstance(field, list) for field in fields):
        diagnostics.append("malformed source payload: orca")
        return None
    return OrcaSection(fresh, *(tuple(field) for field in fields))


def _load_conflicts(raw: object, name: str, section_type: type[HandoffSection] | type[TasksSection], diagnostics: list[str]) -> HandoffSection | TasksSection | None:
    parsed = _payload(raw, name, diagnostics)
    if parsed is None:
        return None
    fresh, payload = parsed
    conflicts = _string_list(payload.get("conflicts", []))
    if conflicts is None:
        diagnostics.append(f"malformed source payload: {name}")
        return None
    for conflict in conflicts:
        diagnostics.append(f"conflicting source: {conflict}")
    return section_type(fresh, conflicts)


def _load_exec_plans(raw: object, diagnostics: list[str]) -> ExecPlansSection | None:
    parsed = _payload(raw, "exec_plans", diagnostics)
    if parsed is None:
        return None
    fresh, payload = parsed
    plans = payload.get("plans")
    if not isinstance(plans, list):
        diagnostics.append("malformed source payload: exec_plans")
        return None
    return ExecPlansSection(fresh, tuple(plans))


def load_snapshot(input: object) -> Snapshot:
    """Load and validate a versioned normalized snapshot without live side effects."""
    data = _mapping(input)
    if data is None:
        raise ValueError("snapshot must be a JSON object")
    version, captured_at = data.get("version"), data.get("captured_at")
    if not isinstance(version, str) or not version:
        raise ValueError("snapshot version is required")
    if not isinstance(captured_at, str) or not captured_at:
        raise ValueError("snapshot captured_at is required")
    diagnostics: list[str] = []
    if version != "now.snapshot.v1":
        diagnostics.append(f"unsupported snapshot version: {version}")
    jira = _load_jira(data.get("jira"), diagnostics)
    git = _load_git(data.get("git"), diagnostics)
    orca = _load_orca(data.get("orca"), diagnostics)
    handoff = _load_conflicts(data.get("handoff"), "handoff", HandoffSection, diagnostics)
    tasks = _load_conflicts(data.get("tasks"), "tasks", TasksSection, diagnostics)
    exec_plans = _load_exec_plans(data.get("exec_plans"), diagnostics)
    typed = {"jira": jira, "git": git, "orca": orca, "handoff": handoff, "tasks": tasks, "exec_plans": exec_plans}
    sections = {name: SourceSection(name, section.fresh, {}) for name, section in typed.items() if section is not None}
    return Snapshot(version, captured_at, sections, jira.issues if jira else (), tuple(diagnostics), jira, git, orca, handoff, tasks, exec_plans)


def first_run_snapshot() -> Snapshot:
    return load_snapshot({"version": "now.snapshot.v1", "captured_at": "UNKNOWN"})
