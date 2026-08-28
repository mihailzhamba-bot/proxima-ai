from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Callable, Sequence

from ..runtime import ActionPlan, ClaimRequest, ClaimStore, LifecycleState
from .provenance import ProvenanceJournal
from .authority import AuthorityJournal

_SHA256 = __import__("re").compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ReleaseGateReport:
    gate_id: str
    discovery_status: str
    report_ref: str
    report_digest: str
    scope_digest: str
    approved_spec: str
    approved_spec_digest: str
    binding_digest: str

    @classmethod
    def read(
        cls,
        repo_root: Path,
        report_path: Path,
        expected_gate_id: str,
        task_key: str,
        snapshot_digest: str,
    ) -> ReleaseGateReport:
        root = repo_root.resolve()
        allowed = (root / "docs" / "release-gates").resolve()
        candidate = report_path.absolute()
        if candidate.is_symlink():
            raise ValueError("release gate report must not be a symlink")
        try:
            resolved = candidate.resolve(strict=True)
            relative = resolved.relative_to(allowed)
        except (OSError, ValueError) as error:
            raise ValueError("release gate report must remain in docs/release-gates") from error
        if relative.suffix != ".md" or not isinstance(expected_gate_id, str) or not expected_gate_id:
            raise ValueError("release gate identity is invalid")
        if not isinstance(task_key, str) or not task_key or not isinstance(snapshot_digest, str) or not _SHA256.fullmatch(snapshot_digest):
            raise ValueError("release gate task/snapshot binding is invalid")
        text = resolved.read_text(encoding="utf-8")
        gate_lines = [line.removeprefix("- Gate ID: ") for line in text.splitlines() if line.startswith("- Gate ID: ")]
        statuses = [line.removeprefix("- DISCOVERY_STATUS: ") for line in text.splitlines() if line.startswith("- DISCOVERY_STATUS: ")]
        if gate_lines != [expected_gate_id] or statuses != ["READY"]:
            raise ValueError("release gate must have one exact Gate ID and one READY header status")
        if not text.endswith("DISCOVERY_STATUS: READY\n"):
            raise ValueError("release gate must end with DISCOVERY_STATUS: READY")
        scope_start = text.find("## 8. Scope lock\n")
        scope_end = text.find("\n## 9. ", scope_start + 1)
        if scope_start < 0 or scope_end < 0:
            raise ValueError("release gate Scope lock is absent")
        scope = text[scope_start:scope_end]
        if "### In scope\n" not in scope or "### Explicitly out of scope\n" not in scope:
            raise ValueError("release gate Scope lock is incomplete")
        scope_digest = sha256(scope.encode()).hexdigest()
        spec_start = text.find("## 12. Autopilot handoff\n")
        spec_end = text.find("\n## 13. ", spec_start + 1)
        if spec_start < 0 or spec_end < 0:
            raise ValueError("release gate approved Autopilot handoff is absent")
        approved_spec = text[spec_start + len("## 12. Autopilot handoff\n"):spec_end].strip()
        if not approved_spec:
            raise ValueError("release gate approved Autopilot handoff is empty")
        report_digest = sha256(text.encode()).hexdigest()
        approved_spec_digest = sha256(approved_spec.encode()).hexdigest()
        return cls(
            expected_gate_id,
            "READY",
            str(resolved.relative_to(root)),
            report_digest,
            scope_digest,
            approved_spec,
            approved_spec_digest,
            sha256("\0".join((expected_gate_id, report_digest, scope_digest, approved_spec_digest, task_key, snapshot_digest)).encode()).hexdigest(),
        )


@dataclass(frozen=True)
class OrcaTerminalEvent:
    kind: str
    outcome: str | None
    delivery_id: str
    task_id: str
    dispatch_id: str
    worker_id: str


def parse_orca_terminal_event(text: str, task_id: str, dispatch_id: str, worker_id: str) -> OrcaTerminalEvent:
    raw = _object(text)
    result = raw.get("result") if raw and raw.get("ok") is True else None
    if not isinstance(result, dict) or type(result.get("count")) is not int or result.get("count") != 1:
        raise ValueError("Orca check must return one exact message")
    delivery_id, messages = result.get("deliveryId"), result.get("messages")
    if not isinstance(delivery_id, str) or not delivery_id or not isinstance(messages, list) or len(messages) != 1:
        raise ValueError("Orca Delivery evidence is malformed")
    message = messages[0]
    if not isinstance(message, dict) or message.get("type") not in {"worker_done", "escalation"} or not isinstance(message.get("payload"), dict):
        raise ValueError("Orca terminal message is unsupported")
    payload = message["payload"]
    if (payload.get("taskId"), payload.get("dispatchId"), payload.get("workerId")) != (task_id, dispatch_id, worker_id):
        raise ValueError("Orca terminal message provenance mismatch")
    outcome = payload.get("outcome")
    if message["type"] == "worker_done" and outcome not in {"succeeded", "failed"}:
        raise ValueError("Orca worker_done outcome is invalid")
    if message["type"] == "escalation" and outcome is not None:
        raise ValueError("Orca escalation must not carry a worker outcome")
    return OrcaTerminalEvent(message["type"], outcome, delivery_id, task_id, dispatch_id, worker_id)

@dataclass(frozen=True)
class CommandResult:
    returncode: int; stdout: str; stderr: str = ""
Runner = Callable[[Sequence[str], Path | None], CommandResult]
def subprocess_runner(argv: Sequence[str], cwd: Path | None = None) -> CommandResult:
    done = subprocess.run(list(argv), cwd=cwd, check=False, text=True, capture_output=True, shell=False)
    return CommandResult(done.returncode, done.stdout, done.stderr)

@dataclass(frozen=True)
class DispatchInput:
    plan: ActionPlan; gate_id: str; gate_report: Path; spec: str; task_title: str; display_name: str; coordinator_handle: str; worktree: str
    def valid(self) -> bool:
        p = self.plan
        return p.state is LifecycleState.CONFIRMED and p.should_dispatch and isinstance(p.claim_token, str) and bool(p.claim_token) and isinstance(self.gate_id, str) and bool(self.gate_id) and isinstance(self.gate_report, Path) and all(isinstance(x, str) and x for x in (self.spec, self.task_title, self.display_name, self.coordinator_handle, self.worktree))

@dataclass(frozen=True)
class DispatchProvenance:
    marker: str; operation_id: str; claim_token: str; task_key: str; track: str; snapshot_digest: str; run_id: str; task_id: str; dispatch_id: str; worker_id: str; check_outcome: str; gate_id: str; gate_report_digest: str; scope_digest: str; approved_spec_digest: str; gate_binding_digest: str

@dataclass(frozen=True)
class WorktreePlacement:
    task_key: str
    claim_token: str
    repo_root: str
    git_common_dir: str
    selector: str
    source_ref: str

PlacementAuthority = Callable[[str], WorktreePlacement]

def _object(text: str) -> dict[str, object] | None:
    try: data = json.loads(text)
    except json.JSONDecodeError: return None
    return data if isinstance(data, dict) else None
def _result(text: str) -> dict[str, object] | None:
    raw = _object(text); value = raw.get("result") if raw and raw.get("ok") is True else None
    return value if isinstance(value, dict) else None
def _marker(claim, gate: ReleaseGateReport) -> str:
    identity = sha256("\0".join((claim.token, claim.key, claim.track, claim.run_id, claim.task_id, claim.worker_id, claim.snapshot_digest, gate.binding_digest)).encode()).hexdigest()
    return f"now-spec:{identity};gate-binding={gate.binding_digest};spec={gate.approved_spec_digest};scope={gate.scope_digest}"

class IntegrationCoordinator:
    def __init__(self, claims: ClaimStore, repo_root: Path, runner: Runner = subprocess_runner, *, placement_authority: PlacementAuthority | None = None) -> None:
        self.claims, self.repo_root, self.runner = claims, repo_root.resolve(), runner
        self.placement_authority = placement_authority
    @staticmethod
    def _blocked(plan: ActionPlan, reason: str) -> ActionPlan:
        return ActionPlan(plan.key, plan.track, LifecycleState.BLOCKED_EXTERNAL, plan.run_id, plan.task_id, plan.worker_id, plan.claim_token, False, False, True, reason)

    @staticmethod
    def _dispatched(plan: ActionPlan, receipt: DispatchProvenance) -> ActionPlan:
        return ActionPlan(plan.key, plan.track, LifecycleState.DISPATCHED, plan.run_id, receipt.task_id, receipt.worker_id, plan.claim_token, False, False)
    def _call(self, argv: Sequence[str], journal: ProvenanceJournal, operation: str) -> CommandResult:
        journal.append(f"{operation}_intent", argv=list(argv))
        result = self.runner(argv, None)
        journal.append(f"{operation}_outcome", returncode=result.returncode, stdout_digest=sha256(result.stdout.encode()).hexdigest(), stderr_digest=sha256(result.stderr.encode()).hexdigest())
        return result

    @staticmethod
    def _receipt(event: dict[str, object], claim, gate: ReleaseGateReport, marker: str, operation_id: str) -> DispatchProvenance:
        value = event.get("receipt")
        fields = set(DispatchProvenance.__dataclass_fields__)
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError("dispatch success receipt is absent")
        try:
            receipt = DispatchProvenance(**value)  # type: ignore[arg-type]
        except TypeError as error:
            raise ValueError("dispatch success receipt schema is invalid") from error
        expected = (
            marker, operation_id, claim.token, claim.key, claim.track, claim.snapshot_digest,
            claim.run_id, gate.gate_id, gate.report_digest, gate.scope_digest,
            gate.approved_spec_digest, gate.binding_digest,
        )
        actual = (
            receipt.marker, receipt.operation_id, receipt.claim_token, receipt.task_key,
            receipt.track, receipt.snapshot_digest, receipt.run_id, receipt.gate_id,
            receipt.gate_report_digest, receipt.scope_digest,
            receipt.approved_spec_digest, receipt.gate_binding_digest,
        )
        if actual != expected or receipt.check_outcome != "succeeded" or not all(isinstance(value, str) and value for value in (receipt.task_id, receipt.dispatch_id, receipt.worker_id)):
            raise ValueError("dispatch success receipt identity is mismatched")
        return receipt

    def _reconcile(self, claim, gate: ReleaseGateReport, marker: str, journal: ProvenanceJournal) -> tuple[str | None, str | None, str | None]:
        listed = self._call(("orca", "orchestration", "task-list", "--run", claim.run_id, "--json"), journal, "task_list")
        listed_result = _result(listed.stdout); tasks = listed_result.get("tasks") if listed_result else None
        if listed.returncode != 0 or not isinstance(tasks, list):
            raise ValueError("Orca task-list readback is absent or malformed")
        expected_spec = f"{gate.approved_spec}\n\n{marker}"
        matching = [item for item in tasks if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("spec") == expected_spec]
        if len(matching) > 1:
            raise ValueError("Orca task marker is not unique")
        if not matching:
            return None, None, None
        task_id = matching[0]["id"]
        shown = self._call(("orca", "orchestration", "dispatch-show", "--task", task_id, "--json"), journal, "dispatch_show")
        shown_envelope = _object(shown.stdout)
        if shown.returncode != 0 or not isinstance(shown_envelope, dict) or set(shown_envelope) != {"ok", "result"} or shown_envelope.get("ok") is not True:
            raise ValueError("Orca dispatch-show did not prove dispatch presence or exact absence")
        shown_result = shown_envelope.get("result")
        if not isinstance(shown_result, dict) or set(shown_result) != {"taskId", "dispatch"} or shown_result.get("taskId") != task_id:
            raise ValueError("Orca dispatch-show readback is malformed or mismatched")
        dispatch = shown_result.get("dispatch")
        if dispatch is None:
            return task_id, None, None
        if not isinstance(dispatch, dict) or set(dispatch) != {"id", "taskId", "workerId"} or dispatch.get("taskId") != task_id or not isinstance(dispatch.get("id"), str) or not isinstance(dispatch.get("workerId"), str):
            raise ValueError("Orca dispatch readback is malformed or mismatched")
        dispatch_id, worker_id = dispatch["id"], dispatch["workerId"]
        worker = self._call(("orca", "orchestration", "worker-show", "--dispatch", dispatch_id, "--json"), journal, "worker_show")
        worker_result = _result(worker.stdout)
        worker_data = worker_result.get("worker") if worker_result else None
        if worker.returncode != 0 or not isinstance(worker_data, dict) or (worker_data.get("taskId"), worker_data.get("dispatchId"), worker_data.get("workerId")) != (task_id, dispatch_id, worker_id):
            raise ValueError("Orca worker readback is malformed or mismatched")
        return task_id, dispatch_id, worker_id

    def dispatch(self, request: DispatchInput) -> tuple[ActionPlan, DispatchProvenance | None]:
        if not request.valid(): return self._blocked(request.plan, "strict confirmed plan, Gate report and persisted claim token are required"), None
        claim = self.claims.lookup(request.plan.claim_token)
        if claim is None or (request.plan.key, request.plan.track, request.plan.run_id, request.plan.task_id, request.plan.worker_id) != (claim.key, claim.track, claim.run_id, claim.task_id, claim.worker_id): return self._blocked(request.plan, "persisted claim authority does not match ActionPlan"), None
        try:
            gate = ReleaseGateReport.read(self.repo_root, request.gate_report, request.gate_id, claim.key, claim.snapshot_digest)
        except (OSError, ValueError) as error:
            return self._blocked(request.plan, str(error)), None
        if request.spec != gate.approved_spec:
            return self._blocked(request.plan, "dispatch spec does not exactly match approved Gate handoff"), None
        if self.placement_authority is None:
            return self._blocked(request.plan, "trusted worktree placement authority is required"), None
        try:
            placement = self.placement_authority(claim.token)
        except (OSError, TypeError, ValueError) as error:
            return self._blocked(request.plan, f"trusted worktree placement readback failed: {error}"), None
        if not isinstance(placement, WorktreePlacement) or (
            placement.task_key,
            placement.claim_token,
            Path(placement.repo_root).resolve(),
            Path(placement.git_common_dir).resolve(),
            placement.selector,
        ) != (
            claim.key,
            claim.token,
            self.repo_root,
            self.claims.common_dir.resolve(),
            request.worktree,
        ) or not placement.source_ref:
            return self._blocked(request.plan, "trusted worktree placement does not match claim/repository/selector"), None
        marker = _marker(claim, gate)
        operation_id = sha256(marker.encode()).hexdigest()
        journal = ProvenanceJournal(self.claims.common_dir, operation_id)
        try:
            with journal.locked():
                success = journal.success()
                if success:
                    receipt = self._receipt(success, claim, gate, marker, operation_id)
                    return self._dispatched(request.plan, receipt), receipt
            lease_result = self.claims.acquire_integration(claim.owner, claim.run_id, claim.task_id, claim.worker_id)
            if lease_result.lease is None: return self._blocked(request.plan, lease_result.reason or "integration lease unavailable"), None
            lease = lease_result.lease
            try:
                with journal.locked():
                    success = journal.success()
                    if success:
                        receipt = self._receipt(success, claim, gate, marker, operation_id)
                        return self._dispatched(request.plan, receipt), receipt
                    journal.append("dispatch_intent", marker=marker, claim_token=claim.token, gate=gate)
                    task_id, dispatch_id, worker_id = self._reconcile(claim, gate, marker, journal)
                    if task_id is None:
                        created = self._call(("orca", "orchestration", "task-create", "--spec", f"{gate.approved_spec}\n\n{marker}", "--task-title", request.task_title, "--display-name", request.display_name, "--run", claim.run_id, "--from", request.coordinator_handle, "--json"), journal, "task_create")
                        created_result = _result(created.stdout); task = created_result.get("task") if created_result else None
                        task_id = task.get("id") if created.returncode == 0 and isinstance(task, dict) and isinstance(task.get("id"), str) else None
                    if not task_id: raise ValueError("Orca task-create did not return result.task.id")
                    if dispatch_id is None:
                        worker = self._call(("orca", "orchestration", "worker-start", "--task", task_id, "--worktree", request.worktree, "--agent", "codex", "--run", claim.run_id, "--from", request.coordinator_handle, "--json"), journal, "worker_start")
                        result = _result(worker.stdout)
                        if worker.returncode != 0 or not result or result.get("taskId") != task_id or result.get("state") != "ready" or result.get("stage") != "input_accepted" or not isinstance(result.get("dispatchId"), str) or not isinstance(result.get("workerId"), str): raise ValueError("Orca worker-start did not prove ready input acceptance")
                        dispatch_id, worker_id = result["dispatchId"], result["workerId"]
                    assert worker_id is not None
                    checked = self._call(("orca", "orchestration", "check", "--run", claim.run_id, "--wait", "--types", "worker_done,escalation", "--timeout-ms", "600000", "--json"), journal, "check")
                    if checked.returncode != 0: raise ValueError("Orca check failed")
                    terminal = parse_orca_terminal_event(checked.stdout, task_id, dispatch_id, worker_id)
                    journal.append("terminal_event", terminal=terminal)
                    if terminal.kind == "escalation": raise ValueError("Orca worker escalated")
                    if terminal.outcome != "succeeded": raise ValueError("Orca worker reported failure")
                    receipt = DispatchProvenance(marker, operation_id, claim.token, claim.key, claim.track, claim.snapshot_digest, claim.run_id, task_id, dispatch_id, worker_id, terminal.outcome, gate.gate_id, gate.report_digest, gate.scope_digest, gate.approved_spec_digest, gate.binding_digest)
                    journal.append("dispatch_succeeded", receipt=receipt)
                    return self._dispatched(request.plan, receipt), receipt
            finally:
                if not self.claims.release_integration(lease.token, claim.owner):
                    raise ValueError("integration lease fencing release failed")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            return self._blocked(request.plan, str(error)), None

@dataclass(frozen=True)
class ReviewEvidence:
    task_id: str; dispatch_id: str; worker_id: str; head: str; verify_ref: str; reviewer_ref: str; blockers: int; warnings: int; repo_common_dir: str; worktree_ref: str; verify_command: str; verify_exit_code: int; verify_output_digest: str; receipt_id: str; receipt_digest: str; verify_output_ref: str = ""


def _review_digest(evidence: ReviewEvidence) -> str:
    payload = asdict(evidence)
    payload["receipt_id"] = ""
    payload["receipt_digest"] = ""
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ReviewReceiptStore:
    """Trusted durable review receipts; callers can request validation, never synthesize authority."""

    def __init__(self, common_dir: Path) -> None:
        self.root = common_dir.resolve() / "now" / "evidence" / "reviews"
        self.verify_outputs_root = self.root / "verify-outputs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.verify_outputs_root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or self.verify_outputs_root.is_symlink():
            raise ValueError("review receipt root must not be a symlink")

    @contextmanager
    def _locked(self):
        descriptor = os.open(self.root / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def issue(self, evidence: ReviewEvidence) -> ReviewEvidence:
        with self._locked():
            digest = _review_digest(evidence)
            issued_payload = asdict(evidence)
            issued_payload["receipt_id"] = digest
            issued_payload["receipt_digest"] = digest
            issued = ReviewEvidence(**issued_payload)
            path = self.root / f"{digest}.json"
            payload = json.dumps(asdict(issued), sort_keys=True, separators=(",", ":")).encode()
            if path.exists():
                existing = self.read(digest)
                if existing != issued:
                    raise ValueError("review receipt collision")
                return existing
            temporary = self.root / f".{digest}.{os.getpid()}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                offset = 0
                while offset < len(payload):
                    written = os.write(descriptor, payload[offset:])
                    if written <= 0:
                        raise OSError("short review receipt write")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.replace(temporary, path)
                directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except BaseException:
                if temporary.exists():
                    temporary.unlink()
                raise
            return issued

    def issue_verify_output(self, *, argv: tuple[str, ...], cwd: Path, head: str, exit_code: int, stdout: str, stderr: str) -> tuple[str, str]:
        artifact = {"argv": list(argv), "cwd": str(cwd.resolve()), "head": head, "exit_code": exit_code, "stdout": stdout, "stderr": stderr}
        payload = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
        digest = sha256(payload).hexdigest()
        path = self.verify_outputs_root / f"{digest}.json"
        with self._locked():
            if path.exists():
                if self.read_verify_output(digest) != artifact:
                    raise ValueError("verify output collision")
                return digest, digest
            temporary = self.verify_outputs_root / f".{digest}.{os.getpid()}.tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                offset = 0
                while offset < len(payload):
                    written = os.write(descriptor, payload[offset:])
                    if written <= 0:
                        raise OSError("short verify output write")
                    offset += written
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.replace(temporary, path)
                directory = os.open(self.verify_outputs_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except BaseException:
                if temporary.exists():
                    temporary.unlink()
                raise
        return digest, digest

    def read_verify_output(self, output_ref: str) -> dict[str, object]:
        if not _SHA256.fullmatch(output_ref):
            raise ValueError("verify output identity is invalid")
        path = self.verify_outputs_root / f"{output_ref}.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("verify output is absent")
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                payload = os.read(descriptor, os.fstat(descriptor).st_size)
            finally:
                os.close(descriptor)
            artifact = json.loads(payload)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("verify output is invalid") from error
        if sha256(payload).hexdigest() != output_ref:
            raise ValueError("verify output digest is invalid")
        if not isinstance(artifact, dict) or set(artifact) != {"argv", "cwd", "head", "exit_code", "stdout", "stderr"} or not isinstance(artifact["argv"], list) or not artifact["argv"] or not all(isinstance(value, str) and value for value in artifact["argv"]) or type(artifact["exit_code"]) is not int or not all(isinstance(artifact[name], str) for name in ("cwd", "head", "stdout", "stderr")):
            raise ValueError("verify output schema is invalid")
        return artifact

    def read(self, receipt_id: str) -> ReviewEvidence:
        if not _SHA256.fullmatch(receipt_id):
            raise ValueError("review receipt identity is invalid")
        path = self.root / f"{receipt_id}.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("durable review receipt is absent")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or set(raw) != set(ReviewEvidence.__dataclass_fields__):
                raise ValueError("review receipt schema is invalid")
            evidence = ReviewEvidence(**raw)
        except (OSError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("review receipt schema is invalid") from error
        if evidence.receipt_id != receipt_id or evidence.receipt_digest != receipt_id or _review_digest(evidence) != receipt_id:
            raise ValueError("review receipt digest is invalid")
        return evidence

@dataclass(frozen=True)
class ReviewInput:
    plan: ActionPlan; dispatch: DispatchProvenance; worker_worktree: Path; repo_root: Path

class ReviewerCoordinator:
    def __init__(self, runner: Runner = subprocess_runner, receipt_store: ReviewReceiptStore | None = None) -> None:
        self.runner, self.receipt_store = runner, receipt_store
    def verify_and_review(self, request: ReviewInput) -> tuple[ActionPlan, ReviewEvidence | None]:
        plan, dispatch = request.plan, request.dispatch
        worktree = request.worker_worktree.resolve()
        if plan.state is not LifecycleState.DISPATCHED:
            return IntegrationCoordinator._blocked(plan, "verification requires DISPATCHED"), None
        repo_root = request.repo_root.resolve()
        if self.receipt_store is None or not worktree.is_dir() or not repo_root.is_dir() or (plan.run_id, dispatch.run_id) != (dispatch.run_id, plan.run_id) or plan.task_id is None:
            return IntegrationCoordinator._blocked(plan, "worker worktree or dispatch provenance is invalid"), None
        worker_readback = self.runner(("orca", "orchestration", "worker-show", "--dispatch", dispatch.dispatch_id, "--json"), repo_root)
        worker_result = _result(worker_readback.stdout)
        worker = worker_result.get("worker") if worker_result else None
        if worker_readback.returncode != 0 or not isinstance(worker, dict) or (worker.get("taskId"), worker.get("dispatchId"), worker.get("workerId"), worker.get("worktree")) != (dispatch.task_id, dispatch.dispatch_id, dispatch.worker_id, str(worktree)):
            return IntegrationCoordinator._blocked(plan, "Orca worker placement readback mismatch"), None
        top = self.runner(("git", "rev-parse", "--show-toplevel"), worktree)
        worker_common = self.runner(("git", "rev-parse", "--path-format=absolute", "--git-common-dir"), worktree)
        repo_common = self.runner(("git", "rev-parse", "--path-format=absolute", "--git-common-dir"), repo_root)
        common = worker_common.stdout.strip()
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != worktree or worker_common.returncode != 0 or repo_common.returncode != 0 or Path(common).resolve() != Path(repo_common.stdout.strip()).resolve():
            return IntegrationCoordinator._blocked(plan, "worker Git repository/common-dir readback mismatch"), None
        head_result = self.runner(("git", "rev-parse", "HEAD"), worktree)
        head = head_result.stdout.strip()
        if head_result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40,64}", head):
            return IntegrationCoordinator._blocked(plan, "worker git HEAD readback failed"), None
        operation_id = sha256("\0".join((dispatch.operation_id, head, str(worktree))).encode()).hexdigest()
        journal = AuthorityJournal(Path(common), operation_id)
        identity = {
            "version": "now.authority.v1", "operation_id": operation_id,
            "task_key": dispatch.task_key, "claim_token": dispatch.claim_token,
            "run_id": dispatch.run_id, "task_id": dispatch.task_id,
            "dispatch_id": dispatch.dispatch_id, "worker_id": dispatch.worker_id,
            "snapshot_digest": dispatch.snapshot_digest, "head": head,
            "worktree": str(worktree),
        }
        try:
            with journal.locked():
                journal.open(identity)
                completed = journal.effect_receipt("review_receipt")
                if completed is not None:
                    receipt_id = completed.get("receipt_id")
                    if not isinstance(receipt_id, str):
                        raise ValueError("authority review receipt is malformed")
                    evidence = self.receipt_store.read(receipt_id)
                    if (evidence.task_id, evidence.dispatch_id, evidence.worker_id, evidence.head) != (dispatch.task_id, dispatch.dispatch_id, dispatch.worker_id, head):
                        raise ValueError("authority review receipt identity mismatch")
                    return plan.transition(LifecycleState.VERIFYING).transition(LifecycleState.REVIEWING).transition(LifecycleState.MERGE_GATE), evidence
                verify_effect = journal.effect_receipt("verify")
                verify_intent = journal.intent("verify", {"head": head, "command": "make verify"})
                if verify_effect is None:
                    verify = self.runner(("make", "verify"), worktree)
                    if verify.returncode != 0:
                        raise ValueError("make verify failed in worker worktree")
                    verify_output_digest, verify_output_ref = self.receipt_store.issue_verify_output(argv=("make", "verify"), cwd=worktree, head=head, exit_code=verify.returncode, stdout=verify.stdout, stderr=verify.stderr)
                    journal.effect("verify", {"head": head, "exit_code": verify.returncode, "output_digest": verify_output_digest, "output_ref": verify_output_ref})
                else:
                    if (verify_effect.get("head"), verify_effect.get("exit_code")) != (head, 0) or not isinstance(verify_effect.get("output_digest"), str) or not _SHA256.fullmatch(verify_effect["output_digest"]) or not isinstance(verify_effect.get("output_ref"), str):
                        raise ValueError("authority verify receipt is malformed")
                    verify_output_digest = verify_effect["output_digest"]
                    verify_output_ref = verify_effect["output_ref"]
                    artifact = self.receipt_store.read_verify_output(verify_output_ref)
                    if verify_output_digest != verify_output_ref or artifact["argv"] != ["make", "verify"] or artifact["cwd"] != str(worktree) or artifact["head"] != head or artifact["exit_code"] != 0:
                        raise ValueError("authority verify output artifact binding is invalid")
                review_effect = journal.effect_receipt("reviewer")
                if review_effect is None:
                    reviewer_intent = journal.intent("reviewer", {"head": head, "verify_output_digest": verify_output_digest})
                    prompt = f"Review task {dispatch.task_id}, dispatch {dispatch.dispatch_id}, worker {dispatch.worker_id}, git HEAD {head}. Return the required exact final VERDICT line."
                    review = self.runner(("opencode", "run", "--agent", "reviewer", prompt), worktree)
                    lines = [line.strip() for line in review.stdout.splitlines() if line.strip()]
                    verdict = re.fullmatch(r"VERDICT: ([0-9]+) blockers, ([0-9]+) warnings", lines[-1]) if lines else None
                    if review.returncode != 0 or verdict is None:
                        raise ValueError("reviewer output lacks an exact structured final verdict")
                    blockers, warnings = int(verdict.group(1)), int(verdict.group(2))
                    reviewer_ref = "reviewer:" + sha256((head + "\0" + review.stdout).encode()).hexdigest()
                    journal.effect("reviewer", {"head": head, "blockers": blockers, "warnings": warnings, "reviewer_ref": reviewer_ref})
                else:
                    blockers, warnings, reviewer_ref = review_effect.get("blockers"), review_effect.get("warnings"), review_effect.get("reviewer_ref")
                    if type(blockers) is not int or type(warnings) is not int or not isinstance(reviewer_ref, str) or not reviewer_ref:
                        raise ValueError("authority reviewer receipt is malformed")
                if blockers != 0 or warnings != 0:
                    raise ValueError(f"reviewer verdict is {blockers} blockers / {warnings} warnings")
                evidence = ReviewEvidence(dispatch.task_id, dispatch.dispatch_id, dispatch.worker_id, head, "make-verify:" + sha256((head + "\0" + verify_output_digest).encode()).hexdigest(), reviewer_ref, blockers, warnings, str(Path(common).resolve()), str(worktree), "make verify", 0, verify_output_digest, "", "", verify_output_ref)
                evidence = self.receipt_store.issue(evidence)
                journal.intent("review_receipt", {"receipt_id": evidence.receipt_id})
                journal.effect("review_receipt", {"receipt_id": evidence.receipt_id})
                return plan.transition(LifecycleState.VERIFYING).transition(LifecycleState.REVIEWING).transition(LifecycleState.MERGE_GATE), evidence
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            return IntegrationCoordinator._blocked(plan, str(error)), None
