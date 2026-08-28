from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.now_orchestrator.core import load_snapshot, render, select


def source(payload: object, *, fresh: bool = True) -> dict[str, object]:
    return {"fresh": fresh, "payload": payload}


def issue(
    key: str,
    track: str,
    *,
    lifecycle: str = "READY",
    priority: int = 3,
    safe_slice: int = 1,
    owned: bool = True,
    critical_path: int = 99,
) -> dict[str, object]:
    return {
        "key": key,
        "track": track,
        "outcome": f"Outcome {key}",
        "owner": "Mike",
        "blockers": [],
        "acceptance_criteria": ["AC complete"],
        "definition_of_done": ["DoD complete"],
        "zones": [f"tools/{key.lower()}"],
        "sources": ["jira", "git"],
        "lifecycle": lifecycle,
        "owned": owned,
        "ready": True,
        "dependency_critical_path": critical_path,
        "jira_priority": priority,
        "safe_slice": safe_slice,
    }


def snapshot_data(issues: list[dict[str, object]]) -> dict[str, object]:
    return {
        "version": "now.snapshot.v1",
        "captured_at": "2026-08-28T10:00:00+00:00",
        "jira": source({"issues": issues}),
        "git": source({"branches": [], "pull_requests": [], "worktrees": []}),
        "orca": source({"runs": [], "tasks": [], "workers": [], "gates": []}),
        "handoff": source({"conflicts": []}),
        "tasks": source({"conflicts": []}),
        "exec_plans": source({"plans": []}),
    }


def test_golden_fixture_renders_stable_b_c_a_then_frozen_d() -> None:
    snapshot = load_snapshot(
        snapshot_data([issue("PA-3", "A"), issue("PMM-2", "B"), issue("PA-1", "C")])
    )

    assert render(select(snapshot)) == """SNAPSHOT: now.snapshot.v1 captured_at=2026-08-28T10:00:00+00:00
RECOMMENDATION: PMM-2

[B] START PMM-2
outcome: Outcome PMM-2
owner: Mike
current_state: READY
next_gate: CONFIRM_EXACT_KEY
blockers: none
AC: AC complete
DoD: DoD complete
zones: tools/pmm-2
sources: jira, git
captured_at: 2026-08-28T10:00:00+00:00
rule: START > dependency critical path > Jira priority > smallest safe slice > stable key

[C] START PA-1
outcome: Outcome PA-1
owner: Mike
current_state: READY
next_gate: CONFIRM_EXACT_KEY
blockers: none
AC: AC complete
DoD: DoD complete
zones: tools/pa-1
sources: jira, git
captured_at: 2026-08-28T10:00:00+00:00
rule: START > dependency critical path > Jira priority > smallest safe slice > stable key

[A] START PA-3
outcome: Outcome PA-3
owner: Mike
current_state: READY
next_gate: CONFIRM_EXACT_KEY
blockers: none
AC: AC complete
DoD: DoD complete
zones: tools/pa-3
sources: jira, git
captured_at: 2026-08-28T10:00:00+00:00
rule: START > dependency critical path > Jira priority > smallest safe slice > stable key

[D] FROZEN
reason: Track D requires an explicit Mike decision
"""


def test_selector_prefers_continue_then_closure_and_uses_stable_tie_break() -> None:
    snapshot = load_snapshot(
        snapshot_data(
            [
                issue("PMM-9", "B", lifecycle="READY", priority=1),
                issue("PMM-3", "B", lifecycle="IMPLEMENTED", priority=5),
                issue("PMM-2", "B", lifecycle="DISPATCHED", priority=5),
                issue("PMM-1", "B", lifecycle="DISPATCHED", priority=5),
            ]
        )
    )

    decision = select(snapshot)

    assert decision.cards[0].key == "PMM-1"
    assert decision.cards[0].action == "CONTINUE"
    assert decision.recommendation_key == "PMM-1"


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda data: data.pop("git"), "missing source: git"),
        (lambda data: data["orca"].update({"fresh": False}), "stale source: orca"),
        (lambda data: data["tasks"].update({"payload": {"conflicts": ["TASKS conflicts with Jira"]}}), "conflicting source: TASKS conflicts with Jira"),
    ],
)
def test_missing_stale_or_conflicting_mandatory_source_blocks_without_intent(mutate, expected: str) -> None:
    data = snapshot_data([issue("PMM-2", "B")])
    mutate(data)

    decision = select(load_snapshot(data))

    assert decision.recommendation_key is None
    assert decision.mutation_intent is None
    assert decision.cards[0].action == "BLOCKED"
    assert expected in decision.diagnostics


def test_cli_fixture_smoke(tmp_path: Path) -> None:
    fixture = tmp_path / "snapshot.json"
    fixture.write_text(json.dumps(snapshot_data([issue("PMM-2", "B")])), encoding="utf-8")

    completed = subprocess.run(
        [str(ROOT / "scripts/agent/now"), "render", str(fixture)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "RECOMMENDATION: PMM-2" in completed.stdout
    assert completed.stdout.index("[B]") < completed.stdout.index("[C]") < completed.stdout.index("[A]")


def test_supported_adapters_gather_and_reconcile_live_sources_before_delegating() -> None:
    adapter_paths = (
        ROOT / ".claude/commands/now.md",
        ROOT / ".codex/skills/now/SKILL.md",
        ROOT / ".opencode/commands/now.md",
    )

    for path in adapter_paths:
        text = path.read_text(encoding="utf-8")
        assert "Jira MCP" in text
        assert "Git/PR/worktrees" in text
        assert "Orca" in text
        assert "HANDOFF" in text
        assert "TASKS" in text
        assert "ExecPlans" in text
        assert "scripts/agent/now render --stdin" in text
        assert "read-only" in text.lower()
        assert "Jira priority" not in text
        assert "select(" not in text


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda data: data.update({"version": "now.snapshot.v2"}), "unsupported snapshot version: now.snapshot.v2"),
        (lambda data: data["git"].update({"payload": {"branches": "invalid"}}), "malformed source payload: git"),
    ],
)
def test_unsupported_version_or_malformed_section_returns_blocked(mutate, expected: str) -> None:
    data = snapshot_data([issue("PMM-2", "B")])
    mutate(data)

    decision = select(load_snapshot(data))

    assert decision.recommendation_key is None
    assert expected in decision.diagnostics
    assert all(card.action == "BLOCKED" for card in decision.cards)


def test_track_lifecycle_and_critical_path_order_ignore_unowned_work() -> None:
    snapshot = load_snapshot(
        snapshot_data(
            [
                issue("PMM-1", "B", lifecycle="READY", priority=1, critical_path=2),
                issue("PMM-2", "B", lifecycle="READY", priority=5, critical_path=1),
                issue("PA-3", "A", lifecycle="DISPATCHED", priority=99, owned=True),
                issue("PA-4", "A", lifecycle="DISPATCHED", priority=1, owned=False),
            ]
        )
    )

    decision = select(snapshot)

    assert decision.cards[0].key == "PMM-2"
    assert decision.cards[0].action == "START"
    assert decision.recommendation_key == "PMM-2"
    assert all(card.key != "PA-4" for card in decision.cards)


def test_blocked_card_exposes_state_next_gate_and_first_run_recovery() -> None:
    data = snapshot_data([issue("PMM-2", "B")])
    data.pop("git")

    decision = select(load_snapshot(data))
    rendered = render(decision)

    assert decision.cards[0].current_state == "BLOCKED_EXTERNAL"
    assert decision.cards[0].next_gate == "RECOVER_SNAPSHOT"
    assert decision.cards[0].recovery_action == "Restore mandatory source git, then rerun /now"
    assert "current_state: BLOCKED_EXTERNAL" in rendered
    assert "next_gate: RECOVER_SNAPSHOT" in rendered
    assert "recovery: Restore mandatory source git, then rerun /now" in rendered


@pytest.mark.parametrize(
    "mutate",
    [
        lambda candidate: candidate.pop("key"),
        lambda candidate: candidate.update({"track": "X"}),
        lambda candidate: candidate.update({"lifecycle": "UNKNOWN"}),
        lambda candidate: candidate.update({"owner": []}),
        lambda candidate: candidate.update({"ready": "yes"}),
        lambda candidate: candidate.update({"jira_priority": "high"}),
        lambda candidate: candidate.update({"sources": []}),
    ],
)
def test_malformed_mandatory_jira_issue_field_fails_closed(mutate) -> None:
    candidate = issue("PMM-2", "B")
    mutate(candidate)

    decision = select(load_snapshot(snapshot_data([candidate])))

    assert decision.recommendation_key is None
    assert "malformed Jira issue" in decision.diagnostics[0]
    assert all(card.action == "BLOCKED" for card in decision.cards)


def test_typed_handoff_tasks_and_execplans_sections_are_loaded_separately() -> None:
    snapshot = load_snapshot(snapshot_data([issue("PMM-2", "B")]))

    assert type(snapshot.handoff).__name__ == "HandoffSection"
    assert type(snapshot.tasks).__name__ == "TasksSection"
    assert type(snapshot.exec_plans).__name__ == "ExecPlansSection"


def test_active_foreign_lane_conflicts_with_start_in_same_track() -> None:
    foreign = issue("PMM-9", "B", lifecycle="DISPATCHED", owned=False)
    snapshot = load_snapshot(snapshot_data([issue("PMM-2", "B"), foreign]))

    decision = select(snapshot)

    assert decision.cards[0].action == "BLOCKED"
    assert decision.cards[0].current_state == "BLOCKED_CONFLICT"
    assert "foreign lane PMM-9" in (decision.cards[0].reason or "")
    assert decision.recommendation_key is None


def test_git_orca_conflict_evidence_blocks_start_for_affected_track() -> None:
    data = snapshot_data([issue("PMM-2", "B")])
    data["git"] = source({"branches": [], "pull_requests": [], "worktrees": [{"track": "B", "key": "PMM-9", "conflict": True}]})

    decision = select(load_snapshot(data))

    assert decision.cards[0].action == "BLOCKED"
    assert decision.cards[0].current_state == "BLOCKED_CONFLICT"
    assert "git conflict PMM-9" in (decision.cards[0].reason or "")
    assert decision.recommendation_key is None


def test_orca_conflict_evidence_blocks_start_for_affected_track() -> None:
    data = snapshot_data([issue("PMM-2", "B")])
    data["orca"] = source({"runs": [], "tasks": [{"track": "B", "key": "PMM-9", "conflict": True}], "workers": [], "gates": []})

    decision = select(load_snapshot(data))

    assert decision.cards[0].action == "BLOCKED"
    assert decision.cards[0].current_state == "BLOCKED_CONFLICT"
    assert "orca conflict PMM-9" in (decision.cards[0].reason or "")
    assert decision.recommendation_key is None


def test_recommendation_remains_first_non_blocked_card_in_b_c_a_order() -> None:
    snapshot = load_snapshot(
        snapshot_data([issue("PMM-2", "B", lifecycle="READY"), issue("PA-3", "A", lifecycle="DISPATCHED")])
    )

    assert select(snapshot).recommendation_key == "PMM-2"


def test_cli_first_run_without_snapshot_returns_recovery_card() -> None:
    completed = subprocess.run(
        [str(ROOT / "scripts/agent/now")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert "RECOMMENDATION: BLOCKED" in completed.stdout
    assert "recovery: Restore mandatory source jira, then rerun /now" in completed.stdout
