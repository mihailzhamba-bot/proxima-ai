from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Callable

from ..jira import AuditBeforeWriteAdapter, JiraIntent, JiraReadback, JiraReconciliation, JiraResult
from ..runtime import ActionPlan, ConvergenceEvidence, LifecycleState
from .coordinator import DispatchProvenance, ReviewEvidence, Runner, subprocess_runner
from .ops_sync import OpsSyncReadback
from .authority import AuthorityJournal

_COMMIT = re.compile(r"[0-9a-f]{40,64}\Z")


def _blocked(plan: ActionPlan, reason: str) -> ActionPlan:
    return ActionPlan(plan.key, plan.track, LifecycleState.BLOCKED_EXTERNAL, plan.run_id, plan.task_id, plan.worker_id, plan.claim_token, False, False, True, reason)


@dataclass(frozen=True)
class MergeApprovalEvidence:
    approval_id: str; approver: str; approver_identity: str; repo: str; base_ref: str; task_id: str; dispatch_id: str; worker_id: str; issue_key: str; pr_number: int; head: str; scope_digest: str; approval_digest: str; source_ref: str


def approval_digest(value: MergeApprovalEvidence) -> str:
    payload = asdict(value); payload["approval_digest"] = ""; payload["source_ref"] = ""
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


ReviewAuthority = Callable[[str], ReviewEvidence]
ApprovalAuthority = Callable[[str], MergeApprovalEvidence]
OpsAuthority = Callable[[str], OpsSyncReadback]
DispatchAuthority = Callable[[str], DispatchProvenance]


@dataclass(frozen=True)
class MergeReadback:
    pr_number: int; state: str; repo: str; base_ref: str; head: str; merge_commit: str; source_ref: str


@dataclass(frozen=True)
class OrcaSettlement:
    task_id: str; dispatch_id: str; worker_id: str; task_status: str; worker_outcome: str; release_state: str; source_ref: str


@dataclass(frozen=True)
class MirrorRequirement:
    path: str; required_tokens: tuple[str, ...]


@dataclass(frozen=True)
class RepoConvergence:
    commit: str; handoff_ref: str; tasks_ref: str; exec_plan_ref: str


@dataclass(frozen=True)
class JiraRemoteEvidence:
    intent_id: str; issue_key: str; status: str; transition_id: str; payload_digest: str; remote_evidence_id: str


WriteJira = Callable[[str], JiraResult]
ReadJira = Callable[[], JiraRemoteEvidence]


class JiraClosePort:
    def __init__(self, adapter: AuditBeforeWriteAdapter, intent: JiraIntent, write: WriteJira, readback: ReadJira) -> None:
        self.adapter, self.intent, self.write, self.readback = adapter, intent, write, readback

    def _read(self, intent_id: str, issue_key: str, status: str, transition: str, payload_digest: str) -> JiraReadback:
        remote = self.readback()
        if (remote.intent_id, remote.issue_key, remote.status, remote.transition_id, remote.payload_digest) != (intent_id, issue_key, status, transition, payload_digest) or not remote.remote_evidence_id:
            raise ValueError("Jira remote readback mismatch")
        receipt = JiraReadback(intent_id, remote.issue_key, remote.status, remote.remote_evidence_id)
        existing = [event for event in self.adapter.ledger.events_for(intent_id) if event.get("event") == "readback"]
        if existing:
            latest = existing[-1]
            if (latest.get("issue_key"), latest.get("status"), latest.get("remote_evidence_id")) != (receipt.issue_key, receipt.status, receipt.remote_evidence_id):
                raise ValueError("Jira remote readback changed during recovery")
            return receipt
        self.adapter.record_readback(receipt)
        return receipt

    def _reconcile_failed(self, intent_id: str, issue_key: str, status: str, transition: str, payload_digest: str) -> JiraReadback:
        remote = self.readback()
        if (remote.intent_id, remote.issue_key, remote.transition_id, remote.payload_digest) != (intent_id, issue_key, transition, payload_digest) or not remote.remote_evidence_id:
            raise ValueError("failed Jira write recovery readback mismatch")
        present = remote.status == status
        if present:
            self.adapter.ledger.confirm_remote_effect(intent_id, remote.remote_evidence_id)
        else:
            self.adapter.ledger.reconcile(JiraReconciliation(intent_id, remote.remote_evidence_id, False))
        if not present:
            raise ValueError("failed Jira write was read back absent; retry requires a fresh invocation")
        return self._read(intent_id, issue_key, status, transition, payload_digest)

    def _reconcile_pending(self, intent_id: str, issue_key: str, status: str, transition: str, payload_digest: str) -> JiraReadback:
        remote = self.readback()
        if (remote.intent_id, remote.issue_key, remote.transition_id, remote.payload_digest) != (intent_id, issue_key, transition, payload_digest) or not remote.remote_evidence_id or not remote.status:
            raise ValueError("pending Jira write authoritative readback mismatch")
        present = remote.status == status
        self.adapter.record(JiraResult(intent_id, present, remote.remote_evidence_id))
        if not present:
            self.adapter.ledger.reconcile(JiraReconciliation(intent_id, remote.remote_evidence_id, False))
            raise ValueError("pending Jira write was read back absent; retry requires a fresh invocation")
        receipt = JiraReadback(intent_id, issue_key, status, remote.remote_evidence_id)
        self.adapter.record_readback(receipt)
        return receipt

    @contextmanager
    def _locked_intent(self):
        intent_id = sha256("\0".join((self.intent.actor, self.intent.operation, self.intent.project, self.intent.issue_key or "", self.intent.payload_digest())).encode()).hexdigest()
        lock_root = self.adapter.ledger.common_dir / "now" / "evidence" / "jira-locks"
        lock_root.mkdir(parents=True, exist_ok=True)
        if lock_root.is_symlink():
            raise ValueError("Jira lock root must not be a symlink")
        descriptor = os.open(lock_root / f"{intent_id}.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield intent_id
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def execute(self, issue_key: str, status: str, transition: str, payload_digest: str) -> JiraReadback:
        with self._locked_intent() as expected_intent_id:
            decision, intent_id = self.adapter.prepare(self.intent)
            if decision.status != "AUTO" or intent_id is None or intent_id != expected_intent_id:
                raise ValueError(f"Jira close intent is not AUTO: {decision.reason}")
            actual_transition = self.intent.payload.get("transition_id") if isinstance(self.intent.payload, dict) else None
            if self.intent.issue_key != issue_key or self.intent.operation != "transition" or actual_transition != transition or decision.payload_digest != payload_digest:
                raise ValueError("Jira close intent identity/payload mismatch")
            events = self.adapter.ledger.events_for(intent_id)
            readbacks = [item for item in events if item.get("event") == "readback"]
            if readbacks:
                event = readbacks[-1]
                if (event.get("issue_key"), event.get("status")) != (issue_key, status):
                    raise ValueError("stored Jira readback mismatch")
                evidence_id = event.get("remote_evidence_id")
                if not isinstance(evidence_id, str) or not evidence_id:
                    raise ValueError("stored Jira readback evidence is invalid")
                return JiraReadback(intent_id, issue_key, status, evidence_id)
            write_intents = [item for item in events if item.get("event") == "write_intent"]
            outcomes = [item for item in events if item.get("event") == "outcome"]
            if len(write_intents) == len(outcomes) + 1:
                return self._reconcile_pending(intent_id, issue_key, status, transition, payload_digest)
            if outcomes and outcomes[-1].get("success") is True:
                return self._read(intent_id, issue_key, status, transition, payload_digest)
            if outcomes:
                latest = events[-1] if events else None
                if isinstance(latest, dict) and latest.get("event") == "remote_effect_confirmed":
                    return self._read(intent_id, issue_key, status, transition, payload_digest)
                if isinstance(latest, dict) and latest.get("event") == "outcome" and latest.get("success") is False:
                    return self._reconcile_failed(intent_id, issue_key, status, transition, payload_digest)
                if not isinstance(latest, dict) or latest.get("event") != "reconciliation" or latest.get("effect_present") is not False:
                    raise ValueError("failed Jira outcome requires explicit absence reconciliation before retry")
            _, pending = self.adapter.ledger.record_write_intent(intent_id)
            if pending:
                return self._reconcile_pending(intent_id, issue_key, status, transition, payload_digest)
            result = self.write(intent_id)
            if result.intent_id != intent_id:
                raise ValueError("Jira write receipt intent mismatch")
            self.adapter.record(result)
            if not result.success:
                return self._reconcile_failed(intent_id, issue_key, status, transition, payload_digest)
            return self._read(intent_id, issue_key, status, transition, payload_digest)


@dataclass(frozen=True)
class CloseInput:
    plan: ActionPlan; dispatch: DispatchProvenance; review: ReviewEvidence; approval: MergeApprovalEvidence; repo_root: Path; expected_repo: str; expected_base_ref: str; expected_mike_identity: str; issue_key: str; expected_jira_status: str; expected_jira_transition: str; expected_jira_payload_digest: str; mirrors: tuple[MirrorRequirement, ...]; ops_sync: OpsSyncReadback


@dataclass(frozen=True)
class CloseEvidence:
    merge: MergeReadback; jira: JiraReadback; orca: OrcaSettlement; repo: RepoConvergence; ops_sync: OpsSyncReadback


class CloseCoordinator:
    def __init__(self, jira: JiraClosePort | None, review_authority: ReviewAuthority | None, approval_authority: ApprovalAuthority | None, ops_authority: OpsAuthority | None, runner: Runner = subprocess_runner, *, dispatch_authority: DispatchAuthority | None = None, common_dir: Path | None = None) -> None:
        self.jira, self.review_authority, self.approval_authority, self.ops_authority, self.runner = jira, review_authority, approval_authority, ops_authority, runner
        self.dispatch_authority, self.common_dir = dispatch_authority, common_dir.resolve() if common_dir else None

    def _repository(self, request: CloseInput, approval: MergeApprovalEvidence) -> Path:
        root = request.repo_root.resolve()
        top = self.runner(("git", "rev-parse", "--show-toplevel"), root)
        if top.returncode != 0 or not top.stdout.strip() or Path(top.stdout.strip()).resolve() != root:
            raise ValueError("close repository root readback mismatch")
        common = self.runner(("git", "rev-parse", "--path-format=absolute", "--git-common-dir"), root)
        if common.returncode != 0 or not common.stdout.strip() or self.common_dir is None or Path(common.stdout.strip()).resolve() != self.common_dir:
            raise ValueError("close Git common-dir readback mismatch")
        remote = self.runner(("gh", "repo", "view", "--json", "nameWithOwner"), root)
        try:
            remote_data = json.loads(remote.stdout)
        except json.JSONDecodeError as error:
            raise ValueError("close repository remote readback is malformed") from error
        if remote.returncode != 0 or not isinstance(remote_data, dict) or set(remote_data) != {"nameWithOwner"} or remote_data.get("nameWithOwner") != approval.repo:
            raise ValueError("close repository remote identity mismatch")
        return root

    def _merge(self, request: CloseInput, approval: MergeApprovalEvidence, review: ReviewEvidence) -> MergeReadback:
        result = self.runner(("gh", "pr", "view", str(approval.pr_number), "--repo", approval.repo, "--json", "number,state,baseRefName,headRefOid,headRepository,mergeCommit,url"), request.repo_root)
        try: data = json.loads(result.stdout)
        except json.JSONDecodeError as error: raise ValueError("gh PR readback is malformed") from error
        merge_value = data.get("mergeCommit") if isinstance(data, dict) else None
        merge_commit = merge_value.get("oid") if isinstance(merge_value, dict) else merge_value
        head_repo = data.get("headRepository") if isinstance(data, dict) else None
        repo = head_repo.get("nameWithOwner") if isinstance(head_repo, dict) else None
        if result.returncode != 0 or not isinstance(data, dict) or set(data) != {"number", "state", "baseRefName", "headRefOid", "headRepository", "mergeCommit", "url"} or (data.get("number"), data.get("state"), repo, data.get("baseRefName"), data.get("headRefOid")) != (approval.pr_number, "MERGED", approval.repo, approval.base_ref, review.head) or not isinstance(merge_commit, str) or not _COMMIT.fullmatch(merge_commit) or not isinstance(data.get("url"), str):
            raise ValueError("gh PR repo/base/head/merge readback is absent or mismatched")
        commit = self.runner(("git", "--no-replace-objects", "rev-parse", f"{merge_commit}^{{commit}}"), request.repo_root)
        ancestor = self.runner(("git", "--no-replace-objects", "merge-base", "--is-ancestor", review.head, merge_commit), request.repo_root)
        if commit.returncode != 0 or commit.stdout.strip() != merge_commit or ancestor.returncode != 0:
            raise ValueError("reviewed HEAD is not proven as an ancestor of merge commit")
        return MergeReadback(data["number"], data["state"], repo, data["baseRefName"], data["headRefOid"], merge_commit, data["url"])

    def _orca(self, request: CloseInput) -> OrcaSettlement:
        shown = self.runner(("orca", "orchestration", "worker-show", "--dispatch", request.dispatch.dispatch_id, "--json"), request.repo_root)
        listed = self.runner(("orca", "orchestration", "task-list", "--run", request.dispatch.run_id, "--json"), request.repo_root)
        try: worker_raw, tasks_raw = json.loads(shown.stdout), json.loads(listed.stdout)
        except json.JSONDecodeError as error: raise ValueError("Orca settlement readback is malformed") from error
        worker_result = worker_raw.get("result") if isinstance(worker_raw, dict) and worker_raw.get("ok") is True else None
        worker = worker_result.get("worker") if isinstance(worker_result, dict) else None
        tasks_result = tasks_raw.get("result") if isinstance(tasks_raw, dict) and tasks_raw.get("ok") is True else None
        tasks = tasks_result.get("tasks") if isinstance(tasks_result, dict) else None
        task = next((item for item in tasks if isinstance(item, dict) and item.get("id") == request.dispatch.task_id), None) if isinstance(tasks, list) else None
        if shown.returncode != 0 or listed.returncode != 0 or not isinstance(worker, dict) or set(worker) not in ({"taskId", "dispatchId", "workerId", "outcome"}, {"taskId", "dispatchId", "workerId", "outcome", "releaseState"}) or (worker.get("taskId"), worker.get("dispatchId"), worker.get("workerId"), worker.get("outcome")) != (request.dispatch.task_id, request.dispatch.dispatch_id, request.dispatch.worker_id, "succeeded") or not isinstance(task, dict) or set(task) != {"id", "status"} or task.get("status") != "completed":
            raise ValueError("Orca task/dispatch/worker settlement mismatch")
        if worker.get("releaseState") == "released":
            return OrcaSettlement(request.dispatch.task_id, request.dispatch.dispatch_id, request.dispatch.worker_id, "completed", "succeeded", "released", f"orca:dispatch:{request.dispatch.dispatch_id}")
        released = self.runner(("orca", "orchestration", "worker-release", "--dispatch", request.dispatch.dispatch_id, "--json"), request.repo_root)
        try: release_raw = json.loads(released.stdout)
        except json.JSONDecodeError as error: raise ValueError("Orca worker release is malformed") from error
        release_result = release_raw.get("result") if isinstance(release_raw, dict) and release_raw.get("ok") is True else None
        if released.returncode != 0 or not isinstance(release_result, dict) or set(release_result) != {"state", "dispatchId", "workerId"} or (release_result.get("state"), release_result.get("dispatchId"), release_result.get("workerId")) != ("released", request.dispatch.dispatch_id, request.dispatch.worker_id):
            raise ValueError("Orca worker release identity/state mismatch")
        return OrcaSettlement(request.dispatch.task_id, request.dispatch.dispatch_id, request.dispatch.worker_id, "completed", "succeeded", "released", f"orca:dispatch:{request.dispatch.dispatch_id}")

    def _repo(self, request: CloseInput, ops: OpsSyncReadback) -> RepoConvergence:
        canonical = (
            ("docs/agent-system/HANDOFF.md", ops.handoff_blob),
            ("docs/agent-system/TASKS.md", ops.tasks_blob),
            (ops.exec_plan_path, ops.exec_plan_blob),
        )
        if not ops.exec_plan_path.startswith("docs/exec-plans/active/") or not ops.exec_plan_path.endswith(".md"):
            raise ValueError("exact canonical HANDOFF, TASKS and active ExecPlan mirrors are required")
        refs: list[str] = []
        for path, expected_blob in canonical:
            pure = PurePosixPath(path)
            if pure.is_absolute() or ".." in pure.parts or not _COMMIT.fullmatch(expected_blob): raise ValueError("repo mirror identity is unsafe")
            shown = self.runner(("git", "--no-replace-objects", "show", f"{ops.merge_commit}:{path}"), request.repo_root)
            blob = self.runner(("git", "--no-replace-objects", "rev-parse", f"{ops.merge_commit}:{path}"), request.repo_root)
            blob_sha = blob.stdout.strip()
            if shown.returncode != 0 or blob.returncode != 0 or blob_sha != expected_blob:
                raise ValueError(f"repo mirror did not converge in Git commit: {path}")
            refs.append(f"{ops.merge_commit}:{path}:blob:{blob_sha}")
        return RepoConvergence(ops.merge_commit or "", *refs)

    @staticmethod
    def _evidence(value: dict[str, object]) -> CloseEvidence:
        expected = set(CloseEvidence.__dataclass_fields__)
        if set(value) != expected:
            raise ValueError("authority close completion receipt is malformed")
        try:
            merge = MergeReadback(**value["merge"])  # type: ignore[arg-type]
            jira = JiraReadback(**value["jira"])  # type: ignore[arg-type]
            orca = OrcaSettlement(**value["orca"])  # type: ignore[arg-type]
            repo = RepoConvergence(**value["repo"])  # type: ignore[arg-type]
            ops = OpsSyncReadback(**value["ops_sync"])  # type: ignore[arg-type]
        except (TypeError, KeyError) as error:
            raise ValueError("authority close completion receipt is malformed") from error
        return CloseEvidence(merge, jira, orca, repo, ops)

    def close(self, request: CloseInput) -> tuple[ActionPlan, CloseEvidence | None]:
        plan = request.plan
        try:
            if plan.state is not LifecycleState.MERGE_GATE: raise ValueError("close requires MERGE_GATE")
            if self.jira is None or self.review_authority is None or self.approval_authority is None or self.ops_authority is None or self.dispatch_authority is None or self.common_dir is None: raise ValueError("trusted close authority port is unavailable; close is BLOCKED_EXTERNAL")
            dispatch = self.dispatch_authority(request.dispatch.operation_id)
            if dispatch != request.dispatch: raise ValueError("durable dispatch receipt is absent or mismatched")
            if (plan.key, plan.track, plan.run_id, plan.task_id, plan.worker_id, plan.claim_token) != (dispatch.task_key, dispatch.track, dispatch.run_id, dispatch.task_id, dispatch.worker_id, dispatch.claim_token) or request.issue_key != plan.key: raise ValueError("cross-task dispatch chain mismatch")
            review = self.review_authority(request.review.receipt_id)
            if review != request.review or review.receipt_digest != review.receipt_id or review.verify_command != "make verify" or review.verify_exit_code != 0 or not _COMMIT.fullmatch(review.verify_output_digest) or (review.task_id, review.dispatch_id, review.worker_id, review.blockers, review.warnings) != (dispatch.task_id, dispatch.dispatch_id, dispatch.worker_id, 0, 0): raise ValueError("durable reviewer receipt is absent or mismatched")
            if Path(review.repo_common_dir).resolve() != self.common_dir: raise ValueError("review receipt Git common-dir authority mismatch")
            approval = self.approval_authority(request.approval.approval_id)
            if approval != request.approval or approval.approver != "Mike" or not approval.approver_identity or approval.approver_identity != request.expected_mike_identity or approval.approval_digest != approval_digest(approval) or (approval.repo, approval.base_ref) != (request.expected_repo, request.expected_base_ref) or (approval.task_id, approval.dispatch_id, approval.worker_id, approval.issue_key, approval.head, approval.scope_digest) != (dispatch.task_id, dispatch.dispatch_id, dispatch.worker_id, request.issue_key, review.head, dispatch.scope_digest): raise ValueError("independent Mike decision-gate readback mismatch")
            ops = self.ops_authority(request.ops_sync.operation_id)
            if ops != request.ops_sync or ops.request_digest != ops.operation_id or ops.pr_state != "MERGED" or not isinstance(ops.merge_commit, str) or not _COMMIT.fullmatch(ops.merge_commit) or (ops.repo, ops.base_ref, ops.task_key, ops.dispatch_id, ops.issue_key, ops.scope_digest) != (approval.repo, approval.base_ref, plan.key, dispatch.dispatch_id, request.issue_key, dispatch.scope_digest): raise ValueError("merged ops sync durable readback mismatch")
            request = replace(request, repo_root=self._repository(request, approval))
            operation_id = sha256("\0".join((dispatch.operation_id, review.receipt_id, approval.approval_digest, ops.operation_id, request.expected_jira_payload_digest)).encode()).hexdigest()
            journal = AuthorityJournal(self.common_dir, operation_id)
            identity = {
                "version": "now.authority.v1", "operation_id": operation_id,
                "task_key": plan.key, "claim_token": dispatch.claim_token,
                "run_id": dispatch.run_id, "task_id": dispatch.task_id,
                "dispatch_id": dispatch.dispatch_id, "worker_id": dispatch.worker_id,
                "snapshot_digest": dispatch.snapshot_digest, "gate_id": dispatch.gate_id,
                "gate_report_digest": dispatch.gate_report_digest,
                "scope_digest": dispatch.scope_digest,
                "approved_spec_digest": dispatch.approved_spec_digest,
                "repo": approval.repo, "base_ref": approval.base_ref,
                "issue_key": request.issue_key, "review_receipt_id": review.receipt_id,
                "ops_operation_id": ops.operation_id,
            }
            with journal.locked():
                journal.open(identity)
                completed = journal.complete()
                if completed is not None:
                    evidence = self._evidence(completed)
                    if evidence.merge.merge_commit != ops.product_merge_commit or evidence.jira.issue_key != request.issue_key or evidence.orca.dispatch_id != dispatch.dispatch_id:
                        raise ValueError("authority close completion chain mismatch")
                    syncing = plan.transition(LifecycleState.MERGED).transition(LifecycleState.SYNCING)
                    convergence = ConvergenceEvidence(evidence.merge.merge_commit, True, True, True, True, True, True, evidence.jira.remote_evidence_id, evidence.orca.source_ref, evidence.merge.source_ref, evidence.repo.handoff_ref, evidence.repo.tasks_ref, evidence.repo.exec_plan_ref)
                    return syncing.transition(LifecycleState.DONE, convergence), evidence
                journal.intent("merge_readback", {"approval_digest": approval.approval_digest, "head": review.head})
                merge = self._merge(request, approval, review)
                journal.effect("merge_readback", asdict(merge))
                if ops.product_merge_commit != merge.merge_commit:
                    raise ValueError("ops sync product merge binding mismatch")
                journal.intent("ops_merge_readback", {"ops_operation_id": ops.operation_id, "ops_merge_commit": ops.merge_commit})
                ancestor = self.runner(("git", "--no-replace-objects", "merge-base", "--is-ancestor", merge.merge_commit, ops.merge_commit), request.repo_root)
                if ancestor.returncode != 0:
                    raise ValueError("product merge is not proven as an ancestor of ops merge")
                journal.effect("ops_merge_readback", {"merge_commit": ops.merge_commit, "product_merge_commit": ops.product_merge_commit})
                journal.intent("repo_mirrors", {"ops_merge_commit": ops.merge_commit})
                repo = self._repo(request, ops)
                journal.effect("repo_mirrors", asdict(repo))
                journal.intent("jira", {"issue_key": request.issue_key, "transition": request.expected_jira_transition, "payload_digest": request.expected_jira_payload_digest})
                jira = self.jira.execute(request.issue_key, request.expected_jira_status, request.expected_jira_transition, request.expected_jira_payload_digest)
                journal.effect("jira", asdict(jira))
                journal.intent("orca_release", {"dispatch_id": dispatch.dispatch_id, "worker_id": dispatch.worker_id})
                orca = self._orca(request)
                journal.effect("orca_release", asdict(orca))
                evidence = CloseEvidence(merge, jira, orca, repo, ops)
                journal.complete(asdict(evidence))
                syncing = plan.transition(LifecycleState.MERGED).transition(LifecycleState.SYNCING)
                convergence = ConvergenceEvidence(merge.merge_commit, True, True, True, True, True, True, jira.remote_evidence_id, orca.source_ref, merge.source_ref, repo.handoff_ref, repo.tasks_ref, repo.exec_plan_ref)
                return syncing.transition(LifecycleState.DONE, convergence), evidence
        except (OSError, TypeError, ValueError) as error:
            return _blocked(plan, str(error)), None
