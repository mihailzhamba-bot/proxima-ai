from __future__ import annotations

from typing import Any

from .models import Card, NowDecision, Snapshot, TRACK_ORDER


_CONTINUE = {"SELECTED", "CONFIRMED", "DISPATCHED", "VERIFYING", "REVIEWING", "MERGE_GATE", "MERGED", "SYNCING"}
_CLOSE = {"IMPLEMENTED", "VERIFY_PASSED", "REVIEW_PASSED", "JIRA_DOC_TAIL"}


def _text_list(value: object) -> tuple[str, ...]:
    return tuple(item for item in value if isinstance(item, str) and item) if isinstance(value, (list, tuple)) else ()


def _rank(issue: dict[str, Any]) -> tuple[int, int, int, str]:
    critical_path = issue.get("dependency_critical_path", 999999)
    priority = issue.get("jira_priority", 999999)
    safe_slice = issue.get("safe_slice", 999999)
    return (
        critical_path if isinstance(critical_path, int) else 999999,
        priority if isinstance(priority, int) else 999999,
        safe_slice if isinstance(safe_slice, int) else 999999,
        str(issue.get("key", "")),
    )


def _action(issue: dict[str, Any]) -> str | None:
    lifecycle = issue.get("lifecycle")
    if lifecycle in _CONTINUE and issue.get("owned") is True:
        return "CONTINUE"
    if lifecycle in _CLOSE:
        return "CLOSE_CURRENT"
    if lifecycle in {"BLOCKED_GATE", "NEEDS_UNBLOCK"}:
        return "UNBLOCK"
    if lifecycle == "READY" and issue.get("ready") is True:
        return "START"
    return None


def _track_conflict_evidence(snapshot: Snapshot, track: str) -> tuple[str, str] | None:
    """Return explicit Git/Orca conflict evidence for one track, if present."""
    sections = (
        ("git", snapshot.git.branches + snapshot.git.pull_requests + snapshot.git.worktrees) if snapshot.git else ("git", ()),
        ("orca", snapshot.orca.runs + snapshot.orca.tasks + snapshot.orca.workers + snapshot.orca.gates) if snapshot.orca else ("orca", ()),
    )
    for source, records in sections:
        for record in records:
            if isinstance(record, dict) and record.get("track") == track and record.get("conflict") is True:
                key = record.get("key")
                return source, key if isinstance(key, str) and key else "unknown"
    return None


def _card(track: str, action: str, issue: dict[str, Any], captured_at: str) -> Card:
    key = issue.get("key")
    if not isinstance(key, str) or not key:
        return Card(
            track, "BLOCKED", None, None, None, (), (), (), (), (), captured_at, None,
            "invalid candidate: missing key", "BLOCKED_EXTERNAL", "RECOVER_SNAPSHOT",
            "Restore a valid Jira candidate, then rerun /now",
        )
    rules = {
        "CONTINUE": "CONTINUE > dependency critical path > Jira priority > smallest safe slice > stable key",
        "CLOSE_CURRENT": "CLOSE_CURRENT > dependency critical path > Jira priority > smallest safe slice > stable key",
        "UNBLOCK": "UNBLOCK > dependency critical path > Jira priority > smallest safe slice > stable key",
        "START": "START > dependency critical path > Jira priority > smallest safe slice > stable key",
    }
    return Card(
        track=track,
        action=action,
        key=key,
        outcome=issue.get("outcome") if isinstance(issue.get("outcome"), str) else "UNKNOWN",
        owner=issue.get("owner") if isinstance(issue.get("owner"), str) else "UNKNOWN",
        blockers=_text_list(issue.get("blockers")),
        acceptance_criteria=_text_list(issue.get("acceptance_criteria")),
        definition_of_done=_text_list(issue.get("definition_of_done")),
        zones=_text_list(issue.get("zones")),
        sources=_text_list(issue.get("sources")),
        captured_at=captured_at,
        rule=rules[action],
        current_state=issue.get("lifecycle") if isinstance(issue.get("lifecycle"), str) else "UNKNOWN",
        next_gate={
            "CONTINUE": "COMPLETE_CURRENT_STATE",
            "CLOSE_CURRENT": "CLOSE_EVIDENCE",
            "UNBLOCK": "RESOLVE_NEAREST_GATE",
            "START": "CONFIRM_EXACT_KEY",
        }[action],
    )


def select(snapshot: Snapshot) -> NowDecision:
    """Choose at most one actionable candidate per active track, deterministically."""
    if snapshot.diagnostics:
        reason = "; ".join(snapshot.diagnostics)
        first = snapshot.diagnostics[0]
        if first.startswith("conflicting source:"):
            state, gate, recovery = "BLOCKED_CONFLICT", "RECONCILE_SOURCES", "Reconcile conflicting sources, then rerun /now"
        else:
            source = first.rsplit(": ", 1)[-1]
            state, gate, recovery = "BLOCKED_EXTERNAL", "RECOVER_SNAPSHOT", f"Restore mandatory source {source}, then rerun /now"
        cards = tuple(
            Card(track, "BLOCKED", None, None, None, (), (), (), (), (), snapshot.captured_at, None, reason, state, gate, recovery)
            for track in TRACK_ORDER
        )
        return NowDecision(snapshot.version, snapshot.captured_at, cards, None, snapshot.diagnostics)

    selected_cards: list[tuple[Card, tuple[int, int, int, str], str]] = []
    for track in TRACK_ORDER:
        candidates = [issue for issue in snapshot.issues if issue.get("track") == track and _action(issue) is not None]
        foreign_active = next((issue for issue in snapshot.issues if issue.get("track") == track and issue.get("owned") is False and issue.get("lifecycle") in _CONTINUE), None)
        evidence_conflict = _track_conflict_evidence(snapshot, track)
        by_action = {action: sorted((issue for issue in candidates if _action(issue) == action), key=_rank) for action in ("CONTINUE", "CLOSE_CURRENT", "UNBLOCK", "START")}
        selected_action = next((action for action in ("CONTINUE", "CLOSE_CURRENT", "UNBLOCK", "START") if by_action[action]), None)
        if selected_action == "START" and foreign_active is not None:
            selected_cards.append((
                Card(track, "BLOCKED", None, None, None, (), (), (), (), (), snapshot.captured_at, None, f"foreign lane {foreign_active.get('key')} is active", "BLOCKED_CONFLICT", "RECONCILE_LANE", "Reconcile the foreign lane, then rerun /now"),
                (999999, 999999, 999999, ""),
                "BLOCKED",
            ))
            continue
        if selected_action == "START" and evidence_conflict is not None:
            source, key = evidence_conflict
            selected_cards.append((
                Card(track, "BLOCKED", None, None, None, (), (), (), (), (), snapshot.captured_at, None, f"{source} conflict {key} is active", "BLOCKED_CONFLICT", "RECONCILE_LANE", "Reconcile the foreign lane, then rerun /now"),
                (999999, 999999, 999999, ""),
                "BLOCKED",
            ))
            continue
        if selected_action is None:
            selected_cards.append((
                Card(track, "BLOCKED", None, None, None, (), (), (), (), (), snapshot.captured_at, None, "no ready candidate", "WAITING_FOR_DECISION", "REFRESH_BACKLOG", "Refresh ready backlog evidence, then rerun /now"),
                (999999, 999999, 999999, ""),
                "BLOCKED",
            ))
        else:
            issue = by_action[selected_action][0]
            selected_cards.append((_card(track, selected_action, issue, snapshot.captured_at), _rank(issue), selected_action))

    selected = next((item for item in selected_cards if item[2] != "BLOCKED"), None)
    recommendation = selected[0].key if selected is not None else None
    return NowDecision(snapshot.version, snapshot.captured_at, tuple(card for card, _, _ in selected_cards), recommendation, ())
