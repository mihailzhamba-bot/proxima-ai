from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import json
import multiprocessing
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.now_orchestrator.core import load_snapshot
from tools.now_orchestrator.runtime import ClaimRequest, ClaimStore, ConvergenceEvidence, GoCommand, LifecycleState, LivenessEvidence, advance

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)


def git_dir(tmp_path: Path) -> Path:
    path = tmp_path / ".git"
    path.mkdir(parents=True)
    return path


def source(payload: object) -> dict[str, object]:
    return {"fresh": True, "payload": payload}


def snapshot(*, owner: str = "Mike", zones: list[str] | None = None, captured_at: str = "2026-08-28T10:00:00+00:00", outcome: str = "runtime") -> object:
    return load_snapshot({"version": "now.snapshot.v1", "captured_at": captured_at, "jira": source({"issues": [{"key": "PMM-2", "track": "B", "outcome": outcome, "owner": owner, "blockers": [], "acceptance_criteria": ["AC"], "definition_of_done": ["DoD"], "zones": zones or ["tools/runtime"], "sources": ["jira"], "lifecycle": "READY", "owned": True, "ready": True, "dependency_critical_path": 1, "jira_priority": 1, "safe_slice": 1}]}), "git": source({"branches": [], "pull_requests": [], "worktrees": []}), "orca": source({"runs": [], "tasks": [], "workers": [], "gates": []}), "handoff": source({"conflicts": []}), "tasks": source({"conflicts": []}), "exec_plans": source({"plans": []})})


def request(key: str = "PMM-2", track: str = "B", zones: tuple[str, ...] = ("tools/runtime",), *, owner: str = "Mike", captured_at: str = "2026-08-28T10:00:00+00:00", snapshot_digest: str = "a" * 64) -> ClaimRequest:
    return ClaimRequest(key, track, zones, owner, "run-1", "task-1", "worker-1", "now.snapshot.v1", captured_at, snapshot_digest)


def _process_race(common: str, barrier: object, queue: object, key: str) -> None:
    barrier.wait()  # type: ignore[union-attr]
    claim = ClaimStore(Path(common)).claim(request(key=key)).claim
    lease = ClaimStore(Path(common)).acquire_integration("Mike", "run-1", key, "worker-1").lease
    queue.put((claim is not None, lease is not None))  # type: ignore[union-attr]


def test_competing_claims_are_process_safe_and_overlap_both_directions(tmp_path: Path) -> None:
    common = git_dir(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda value: ClaimStore(common).claim(request(key=value)), ("PMM-2", "PMM-3")))
    assert sum(result.claim is not None for result in results) == 1
    store = ClaimStore(common)
    assert store.claim(request(key="PA-1", track="A", zones=("tools",))).reason == "zone overlap: tools <-> tools/runtime"
    assert store.claim(request(key="PA-2", track="A", zones=("tools/runtime/deep",))).reason == "zone overlap: tools/runtime <-> tools/runtime/deep"


def test_independent_processes_have_one_claim_and_one_global_lease(tmp_path: Path) -> None:
    common = git_dir(tmp_path)
    context = multiprocessing.get_context("spawn")
    barrier, queue = context.Barrier(2), context.Queue()
    processes = [context.Process(target=_process_race, args=(str(common), barrier, queue, key)) for key in ("PMM-2", "PMM-3")]
    for process in processes: process.start()
    for process in processes: process.join(10)
    assert all(process.exitcode == 0 for process in processes)
    outcomes = [queue.get(timeout=2) for _ in processes]
    assert sum(claim for claim, _ in outcomes) == 1
    assert sum(lease for _, lease in outcomes) == 1


def test_runtime_rejects_symlink_parent_and_crash_residue(tmp_path: Path) -> None:
    common = git_dir(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    os.symlink(target, common / "now")
    with pytest.raises(ValueError, match="symlink"):
        ClaimStore(common)
    clean = git_dir(tmp_path / "clean")
    (clean / "now" / "claims").mkdir(parents=True)
    (clean / "now" / "claims" / ".claim.tmp").write_text("partial", encoding="utf-8")
    with pytest.raises(ValueError, match="crash residue"):
        ClaimStore(clean)


def test_tokens_cannot_escape_or_release_wrong_record(tmp_path: Path) -> None:
    store = ClaimStore(git_dir(tmp_path))
    claim = store.claim(request()).claim
    assert claim is not None
    assert not store.release("../" + claim.token, "Mike")
    assert not store.release("z" * 64, "Mike")
    assert store.release(claim.token, "Mike")
    lease = store.acquire_integration("Mike", "run-1", "task-1", "worker-1").lease
    assert lease is not None
    assert not store.release_integration("0" * 64, "Mike")
    assert not store.release_integration("../" + lease.token, "Mike")


def test_resume_requires_exact_immutable_identity(tmp_path: Path) -> None:
    store = ClaimStore(git_dir(tmp_path))
    assert store.claim(request()).claim
    assert store.claim(request(zones=("tools/runtime/changed",))).reason == "claim provenance conflict"
    assert store.claim(request(captured_at="2026-08-28T10:00:01+00:00")).reason == "claim provenance conflict"
    assert store.claim(request(owner="Other")).reason == "claim provenance conflict"


def test_integration_lease_resumes_only_for_the_exact_same_identity(tmp_path: Path) -> None:
    store = ClaimStore(git_dir(tmp_path))
    first = store.acquire_integration("Mike", "run-1", "task-1", "worker-1")
    resumed = store.acquire_integration("Mike", "run-1", "task-1", "worker-1")
    foreign = store.acquire_integration("Mike", "run-1", "task-1", "worker-2")
    assert first.lease is not None and resumed.lease == first.lease
    assert foreign.lease is None and foreign.reason == "integration lease active"


def test_snapshot_digest_is_required_canonical_and_changes_claim_token(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        ClaimRequest("PMM-2", "B", ("tools/runtime",), "Mike", "run-1", "task-1", "worker-1", "now.snapshot.v1", "2026-08-28T10:00:00+00:00")
    for fabricated in ("", "not-a-sha", "A" * 64):
        with pytest.raises(ValueError, match="snapshot_digest"):
            request(snapshot_digest=fabricated)
    first = ClaimStore(git_dir(tmp_path / "first")).claim(request(snapshot_digest="a" * 64)).claim
    second = ClaimStore(git_dir(tmp_path / "second")).claim(request(snapshot_digest="b" * 64)).claim
    assert first is not None and second is not None and first.token != second.token


def test_go_requires_mike_fresh_timestamp_and_stays_confirmed(tmp_path: Path) -> None:
    good = snapshot()
    plan = advance(GoCommand("PMM-2", "Mike"), good, ClaimStore(git_dir(tmp_path)), clock=lambda: NOW)
    assert plan.state is LifecycleState.CONFIRMED and plan.should_dispatch and not plan.dispatch
    assert advance(GoCommand("PMM-2", "Other"), good, ClaimStore(git_dir(tmp_path / "foreign")), clock=lambda: NOW).blocked
    assert advance(GoCommand("PMM-2", "Mike"), snapshot(captured_at="2026-08-28T09:50:00+00:00"), ClaimStore(git_dir(tmp_path / "stale")), clock=lambda: NOW).blocked
    assert advance(GoCommand("PMM-2", "Mike"), snapshot(captured_at="not-a-time"), ClaimStore(git_dir(tmp_path / "bad")), clock=lambda: NOW).blocked
    assert plan.transition(LifecycleState.DISPATCHED).state is LifecycleState.DISPATCHED


def test_recovery_requires_typed_bound_not_live_evidence(tmp_path: Path) -> None:
    store = ClaimStore(git_dir(tmp_path))
    lease = store.acquire_integration("Mike", "run-1", "task-1", "worker-1").lease
    assert lease is not None
    assert not store.recover_integration(LivenessEvidence("0" * 64, False, False, False, "owner-read", "task-read", "worker-read", NOW))
    assert store.recover_integration(LivenessEvidence(lease.token, False, False, False, "owner-read", "task-read", "worker-read", NOW), clock=lambda: NOW)


def test_snapshot_content_and_recovery_time_bounds_fail_closed(tmp_path: Path) -> None:
    common = git_dir(tmp_path)
    assert not advance(GoCommand("PMM-2", "Mike"), snapshot(), ClaimStore(common), clock=lambda: NOW).blocked
    assert advance(GoCommand("PMM-2", "Mike"), snapshot(outcome="changed"), ClaimStore(common), clock=lambda: NOW).reason == "claim provenance conflict"
    store = ClaimStore(git_dir(tmp_path / "lease"))
    lease = store.acquire_integration("Mike", "run-1", "task-1", "worker-1").lease
    assert lease is not None
    for evidence in (LivenessEvidence(lease.token, False, False, False, "", "task", "worker", NOW), LivenessEvidence(lease.token, True, False, False, "owner", "task", "worker", NOW), LivenessEvidence(lease.token, False, False, False, "owner", "task", "worker", NOW - __import__("datetime").timedelta(minutes=6)), LivenessEvidence(lease.token, False, False, False, "owner", "task", "worker", NOW + __import__("datetime").timedelta(minutes=1))):
        assert not store.recover_integration(evidence, clock=lambda: NOW)
    assert store.lease_path.exists()


def test_short_write_loop_and_owner_release_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.now_orchestrator.runtime import claims
    sizes: list[int] = []
    monkeypatch.setattr(claims.os, "write", lambda _fd, data: sizes.append(len(data)) or max(1, len(data) // 2))
    claims._write_all(7, b"abcd")
    assert len(sizes) > 1
    monkeypatch.undo()
    store = ClaimStore(git_dir(tmp_path))
    claim = store.claim(request()).claim
    assert claim is not None and not store.release(claim.token, "Other") and store.release(claim.token, "Mike")


def test_integration_release_requires_exact_owner_and_preserves_lease_victim(tmp_path: Path) -> None:
    store = ClaimStore(git_dir(tmp_path))
    lease = store.acquire_integration("Mike", "run-1", "task-1", "worker-1").lease
    assert lease is not None
    assert not store.release_integration("../" + lease.token, "Mike")
    assert store.lease_path.exists()
    assert not store.release_integration(lease.token, "Other")
    assert store.lease_path.exists()
    assert store.release_integration(lease.token, "Mike")


def test_interrupted_recovery_wal_intent_is_observable_and_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    common = git_dir(tmp_path)
    store = ClaimStore(common)
    lease = store.acquire_integration("Mike", "run-1", "task-1", "worker-1").lease
    assert lease is not None
    original_audit = store._audit

    def crash_before_recovery_outcome(event: str, **payload: object) -> None:
        if event == "integration_recovered":
            raise OSError("simulated crash before recovery outcome")
        original_audit(event, **payload)

    monkeypatch.setattr(store, "_audit", crash_before_recovery_outcome)
    evidence = LivenessEvidence(lease.token, False, False, False, "owner-read", "task-read", "worker-read", NOW)
    with pytest.raises(OSError, match="simulated crash"):
        store.recover_integration(evidence, clock=lambda: NOW)
    assert "integration_recovery_intent" in store.audit_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete recovery intent"):
        ClaimStore(common)


def test_done_requires_typed_true_convergence_and_fixed_golden_json(tmp_path: Path) -> None:
    plan = advance(GoCommand("PMM-2", "Mike"), snapshot(), ClaimStore(git_dir(tmp_path)), clock=lambda: NOW).transition(LifecycleState.DISPATCHED)
    for state in (LifecycleState.VERIFYING, LifecycleState.REVIEWING, LifecycleState.MERGE_GATE, LifecycleState.MERGED, LifecycleState.SYNCING):
        plan = plan.transition(state)
    assert plan.transition(LifecycleState.DONE, ConvergenceEvidence("", True, True, True, True, True, True, "jira", "orca", "git", "handoff", "tasks", "plan")).blocked
    assert plan.transition(LifecycleState.DONE, ConvergenceEvidence("merge-1", 1, True, True, True, True, True, "jira", "orca", "git", "handoff", "tasks", "plan")).blocked
    assert plan.transition(LifecycleState.DONE, ConvergenceEvidence("merge-1", "yes", True, True, True, True, True, "jira", "orca", "git", "handoff", "tasks", "plan")).blocked
    done = plan.transition(LifecycleState.DONE, ConvergenceEvidence("merge-1", True, True, True, True, True, True, "jira", "orca", "git", "handoff", "tasks", "plan"))
    assert done.state is LifecycleState.DONE
    golden = '{"blocked":false,"claim_token":"57d541eda2037627abde60ad3d8d5af7fe395958f6c94b1cfa45467c639f7593","dispatch":false,"key":"PMM-2","reason":null,"run_id":"now-75cb99899085e6e815a01de8c233a5ac","should_dispatch":false,"state":"DONE","task_id":"task-75cb99899085e6e815a01de8c233a5ac","track":"B","worker_id":"worker-75cb99899085e6e815a01de8c233a5ac"}'
    assert json.dumps(done.as_dict(), sort_keys=True, separators=(",", ":")) == golden
    for facade in (".claude/commands/now.md", ".codex/skills/now/SKILL.md", ".opencode/commands/now.md"):
        assert "scripts/agent/now go <KEY>" in (ROOT / facade).read_text(encoding="utf-8")
