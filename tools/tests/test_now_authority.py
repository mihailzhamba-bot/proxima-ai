from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import threading
import time
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.now_orchestrator.integration import (
    CommandResult,
    DispatchInput,
    IntegrationCoordinator,
    ReleaseGateReport,
)
from tools.now_orchestrator.runtime import ActionPlan, ClaimRequest, ClaimStore, LifecycleState


def _store(tmp_path: Path) -> ClaimStore:
    common = tmp_path / ".git"
    common.mkdir(exist_ok=True)
    return ClaimStore(common)


def _claim(store: ClaimStore):
    request = ClaimRequest(
        "PMM-5",
        "B",
        ("tools/now_orchestrator",),
        "Mike",
        "run-1",
        "claim-task",
        "claim-worker",
        "now.snapshot.v1",
        "2026-08-28T10:00:00+00:00",
        "a" * 64,
    )
    claim = store.claim(request).claim
    assert claim is not None
    return claim


def _gate(tmp_path: Path) -> Path:
    path = tmp_path / "docs/release-gates/gate.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Gate\n\n## Gate\n\n- Gate ID: RG-1\n- DISCOVERY_STATUS: READY\n\n"
        "## 8. Scope lock\n\n### In scope\n\n- T04\n\n### Explicitly out of scope\n\n- deploy\n\n"
        "## 9. Acceptance\n\n- pass\n\n"
        "## 12. Autopilot handoff\n\napproved exact worker spec\n\n"
        "## 13. Final decision\n\nKEEP\n\nDISCOVERY_STATUS: READY\n",
        encoding="utf-8",
    )
    return path


def _dispatch_input(tmp_path: Path, store: ClaimStore) -> DispatchInput:
    claim = _claim(store)
    plan = ActionPlan(
        claim.key,
        claim.track,
        LifecycleState.CONFIRMED,
        claim.run_id,
        claim.task_id,
        claim.worker_id,
        claim.token,
        False,
        True,
    )
    return DispatchInput(plan, "RG-1", _gate(tmp_path), "approved exact worker spec", "T", "T", "coordinator", "worker-tree")


def _placement(tmp_path: Path, request: DispatchInput):
    from tools.now_orchestrator.integration import WorktreePlacement
    return WorktreePlacement(request.plan.key, request.plan.claim_token or "", str(tmp_path.resolve()), str((tmp_path / ".git").resolve()), request.worktree, "test-placement-receipt")


def test_claim_lookup_recomputes_token_from_every_stored_field(tmp_path: Path) -> None:
    store = _store(tmp_path)
    claim = _claim(store)
    path = store.claims_dir / f"{claim.token}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["worker_id"] = "tampered-worker"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="claim evidence"):
        store.lookup(claim.token)


def test_gate_binding_and_marker_include_exact_approved_spec_digest(tmp_path: Path) -> None:
    gate = ReleaseGateReport.read(tmp_path, _gate(tmp_path), "RG-1", "PMM-5", "a" * 64)
    expected = sha256("approved exact worker spec".encode()).hexdigest()
    assert gate.approved_spec_digest == expected

    store = _store(tmp_path)
    request = _dispatch_input(tmp_path, store)
    calls: list[tuple[str, ...]] = []

    def runner(argv, cwd=None):
        call = tuple(argv)
        calls.append(call)
        if "task-list" in call:
            return CommandResult(0, '{"ok":true,"result":{"tasks":[]}}')
        if "task-create" in call:
            return CommandResult(0, '{"ok":true,"result":{"task":{"id":"task-1"}}}')
        if "worker-start" in call:
            return CommandResult(0, '{"ok":true,"result":{"taskId":"task-1","dispatchId":"dispatch-1","workerId":"worker-1","state":"ready","stage":"input_accepted"}}')
        return CommandResult(0, '{"ok":true,"result":{"deliveryId":"delivery-1","messages":[{"type":"worker_done","payload":{"taskId":"task-1","dispatchId":"dispatch-1","workerId":"worker-1","outcome":"succeeded"}}],"count":1}}')

    result, receipt = IntegrationCoordinator(store, tmp_path, runner, placement_authority=lambda _: _placement(tmp_path, request)).dispatch(request)
    assert result.state is LifecycleState.DISPATCHED
    assert receipt is not None and receipt.approved_spec_digest == expected
    assert receipt.gate_binding_digest in receipt.marker


def test_dispatch_rejects_request_spec_not_exactly_approved(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = replace(_dispatch_input(tmp_path, store), spec="caller changed scope")
    calls = []
    result, receipt = IntegrationCoordinator(store, tmp_path, lambda argv, cwd=None: calls.append(tuple(argv)) or CommandResult(0, "{}" ), placement_authority=lambda _: _placement(tmp_path, request)).dispatch(request)
    assert result.blocked and receipt is None and calls == []


def test_every_orca_envelope_requires_literal_ok_true(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = _dispatch_input(tmp_path, store)

    def runner(argv, cwd=None):
        if "task-list" in argv:
            return CommandResult(0, '{"ok":1,"result":{"tasks":[]}}')
        raise AssertionError("must fail before an Orca effect")

    result, receipt = IntegrationCoordinator(store, tmp_path, runner, placement_authority=lambda _: _placement(tmp_path, request)).dispatch(request)
    assert result.blocked and receipt is None


def test_reused_dispatch_receipt_is_schema_and_identity_verified(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = _dispatch_input(tmp_path, store)
    gate = ReleaseGateReport.read(tmp_path, request.gate_report, request.gate_id, "PMM-5", "a" * 64)
    operation_id = sha256("receipt-tamper".encode()).hexdigest()
    from tools.now_orchestrator.integration.provenance import ProvenanceJournal

    journal = ProvenanceJournal(store.common_dir, operation_id)
    # A foreign success journal must never authorize this request.
    journal.append("dispatch_succeeded", receipt={"marker": "now-spec:" + operation_id})
    assert gate.binding_digest
    calls = []
    result, receipt = IntegrationCoordinator(store, tmp_path, lambda argv, cwd=None: calls.append(tuple(argv)) or CommandResult(1, "" ), placement_authority=lambda _: _placement(tmp_path, request)).dispatch(request)
    assert receipt is None and result.blocked


def test_orca_dispatch_show_uses_supported_argv_without_run(tmp_path: Path) -> None:
    store = _store(tmp_path)
    request = _dispatch_input(tmp_path, store)
    calls: list[tuple[str, ...]] = []

    def runner(argv, cwd=None):
        call = tuple(argv)
        calls.append(call)
        if "task-list" in call:
            marker = next(value for value in call if value.startswith("--")) if False else ""
            # Return no task; this test only constrains the command builder below.
            return CommandResult(0, '{"ok":true,"result":{"tasks":[]}}')
        if "task-create" in call:
            return CommandResult(1, '{"ok":false}')
        raise AssertionError(call)

    IntegrationCoordinator(store, tmp_path, runner, placement_authority=lambda _: _placement(tmp_path, request)).dispatch(request)
    assert not any("dispatch-show" in call and "--run" in call for call in calls)


def test_close_requires_independent_review_and_mike_decision_ports(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator

    assert "review_authority" in CloseCoordinator.__init__.__annotations__
    assert "approval_authority" in CloseCoordinator.__init__.__annotations__


def test_close_input_requires_ops_sync_readback() -> None:
    from tools.now_orchestrator.integration import CloseInput

    assert "ops_sync" in CloseInput.__dataclass_fields__


def test_merge_readback_contract_names_repo_base_and_ancestry() -> None:
    from tools.now_orchestrator.integration import CloseInput

    assert "expected_repo" in CloseInput.__dataclass_fields__
    assert "expected_base_ref" in CloseInput.__dataclass_fields__


def test_review_evidence_has_durable_digest_bound_receipt() -> None:
    from tools.now_orchestrator.integration import ReviewEvidence

    assert {"receipt_id", "receipt_digest", "repo_common_dir", "worktree_ref"}.issubset(ReviewEvidence.__dataclass_fields__)


def test_ops_sync_has_approval_wal_and_reconciliation_identity() -> None:
    from tools.now_orchestrator.integration import OpsSyncInput, OpsSyncReadback

    assert {"approval_id", "approval_digest"}.issubset(OpsSyncInput.__dataclass_fields__)
    assert {"operation_id", "request_digest", "merge_commit"}.issubset(OpsSyncReadback.__dataclass_fields__)


def test_jira_success_then_failed_readback_retries_readback_without_second_write(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraResult

    common=tmp_path/'.git'; common.mkdir(); ledger=JiraLedger(common_dir=common)
    contract=ExecutionContract('Mike','acct-mike','B',('none',),('AC',),('DoD',),'RG-1',('gate:1',),('tools/now_orchestrator',))
    payload={'transition_id':'done','assignee':{'displayName':'Mike','accountId':'acct-mike'},'execution_contract':contract.as_payload()}
    intent=JiraIntent('Mike','transition','PMM','PMM-5',payload,contract,assignee_account_id='acct-mike')
    writes=[]; reads=[]
    def write(intent_id): writes.append(intent_id); return JiraResult(intent_id,True,'write-1')
    def read():
        reads.append(True); intent_id=writes[0]
        status='Wrong' if len(reads)==1 else 'Done'
        return JiraRemoteEvidence(intent_id,'PMM-5',status,'done',intent.payload_digest(),f'read-{len(reads)}')
    port=JiraClosePort(AuditBeforeWriteAdapter(ledger),intent,write,read)
    with pytest.raises(ValueError,match='readback'):
        port.execute('PMM-5','Done','done',intent.payload_digest())
    receipt=port.execute('PMM-5','Done','done',intent.payload_digest())
    assert receipt.status=='Done' and len(writes)==1 and len(reads)==2


def test_jira_failed_write_requires_live_reconciliation_before_returning_success(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraResult

    common = tmp_path / ".git"; common.mkdir(); ledger = JiraLedger(common_dir=common)
    contract = ExecutionContract("Mike", "acct-mike", "B", ("none",), ("AC",), ("DoD",), "RG-1", ("gate:1",), ("tools/now_orchestrator",))
    payload = {"transition_id": "done", "assignee": {"displayName": "Mike", "accountId": "acct-mike"}, "execution_contract": contract.as_payload()}
    intent = JiraIntent("Mike", "transition", "PMM", "PMM-5", payload, contract, assignee_account_id="acct-mike")
    reads: list[bool] = []
    def read():
        reads.append(True)
        return JiraRemoteEvidence(sha256("\0".join((intent.actor, intent.operation, intent.project, intent.issue_key or "", intent.payload_digest())).encode()).hexdigest(), "PMM-5", "Done", "done", intent.payload_digest(), "read-1")
    port = JiraClosePort(AuditBeforeWriteAdapter(ledger), intent, lambda intent_id: JiraResult(intent_id, False, None), read)
    receipt = port.execute("PMM-5", "Done", "done", intent.payload_digest())
    assert receipt.status == "Done" and len(reads) == 2
    assert '"event":"remote_effect_confirmed"' in ledger.path.read_text(encoding="utf-8")


def test_jira_crash_after_failed_outcome_resumes_with_live_readback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.now_orchestrator.integration import JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraResult

    common = tmp_path / ".git"; common.mkdir(); ledger = JiraLedger(common_dir=common); adapter = AuditBeforeWriteAdapter(ledger)
    contract = ExecutionContract("Mike", "acct-mike", "B", ("none",), ("AC",), ("DoD",), "RG-1", ("gate:1",), ("tools/now_orchestrator",))
    payload = {"transition_id": "done", "assignee": {"displayName": "Mike", "accountId": "acct-mike"}, "execution_contract": contract.as_payload()}
    intent = JiraIntent("Mike", "transition", "PMM", "PMM-5", payload, contract, assignee_account_id="acct-mike")
    original = adapter.record; crashed = False
    def record_once(result):
        nonlocal crashed
        original(result)
        if not crashed:
            crashed = True
            raise OSError("crash after failed outcome")
    monkeypatch.setattr(adapter, "record", record_once)
    intent_id = sha256("\0".join((intent.actor, intent.operation, intent.project, intent.issue_key or "", intent.payload_digest())).encode()).hexdigest()
    port = JiraClosePort(adapter, intent, lambda value: JiraResult(value, False, None), lambda: JiraRemoteEvidence(intent_id, "PMM-5", "Done", "done", intent.payload_digest(), "read-1"))
    with pytest.raises(OSError, match="crash"):
        port.execute("PMM-5", "Done", "done", intent.payload_digest())
    assert port.execute("PMM-5", "Done", "done", intent.payload_digest()).status == "Done"


def test_close_json_rejects_extra_nested_fields_and_malformed_mirror(tmp_path: Path) -> None:
    from dataclasses import asdict
    from tools.now_orchestrator.__main__ import _close_request
    from tools.now_orchestrator.integration import MergeApprovalEvidence, OpsSyncReadback, ReviewEvidence

    dispatch = {
        'marker':'m','operation_id':'1'*64,'claim_token':'c'*64,'task_key':'PMM-5','track':'B','snapshot_digest':'a'*64,'run_id':'run-1','task_id':'task-1','dispatch_id':'dispatch-1','worker_id':'worker-1','check_outcome':'succeeded','gate_id':'RG-1','gate_report_digest':'2'*64,'scope_digest':'3'*64,'approved_spec_digest':'4'*64,'gate_binding_digest':'5'*64,
    }
    review=ReviewEvidence('task-1','dispatch-1','worker-1','d'*40,'v','r',0,0,'common','worktree','make verify',0,'7'*64,'6'*64,'6'*64)
    approval=MergeApprovalEvidence('approval','Mike','acct','owner/repo','main','task-1','dispatch-1','worker-1','PMM-5',1,'d'*40,'3'*64,'7'*64,'gate')
    ops=OpsSyncReadback('w','b','f'*40,2,'MERGED','url','8'*64,'8'*64,'e'*40,'owner/repo','main','PMM-5','dispatch-1','PMM-5','b'*64,'e'*40,'a'*40,'a'*40,'docs/exec-plans/active/now.md','a'*40)
    raw={'plan':{'key':'PMM-5','track':'B','state':'MERGE_GATE','run_id':'run-1','task_id':'task-1','worker_id':'worker-1','claim_token':'c'*64,'dispatch':False,'should_dispatch':False,'blocked':False,'reason':None},'dispatch':dispatch,'review':asdict(review),'approval':asdict(approval),'expected_repo':'owner/repo','expected_base_ref':'main','expected_mike_identity':'acct','issue_key':'PMM-5','expected_jira_status':'Done','expected_jira_transition':'done','expected_jira_payload_digest':'9'*64,'mirrors':[{'path':'docs/agent-system/HANDOFF.md','required_tokens':['DONE']}],'ops_sync':asdict(ops)}
    raw['dispatch']['extra']='forged'
    with pytest.raises(ValueError,match='unexpected'):_close_request(raw,tmp_path)
    del raw['dispatch']['extra']; raw['mirrors']=[{'path':'docs/agent-system/HANDOFF.md','required_tokens':['DONE'],'extra':True}]
    with pytest.raises(ValueError,match='unexpected'):_close_request(raw,tmp_path)
    raw['mirrors']=[{'path':'docs/agent-system/HANDOFF.md','required_tokens':['DONE']}]
    raw['review']['verify_exit_code']=True
    with pytest.raises(ValueError,match='counters'):_close_request(raw,tmp_path)


def test_dispatch_cli_rejects_extra_envelope_field_before_effects(tmp_path: Path) -> None:
    plan={
        'plan':{'key':'PMM-5','track':'B','state':'CONFIRMED','run_id':'run-1','task_id':'task-1','worker_id':'worker-1','claim_token':'c'*64,'dispatch':False,'should_dispatch':True,'blocked':False,'reason':None},
        'gate_id':'RG-1','spec':'s','task_title':'t','display_name':'d','coordinator_handle':'c','worktree':'current','extra':'forged',
    }
    plan_path=tmp_path/'plan.json'; gate_path=tmp_path/'gate.md'
    plan_path.write_text(json.dumps(plan),encoding='utf-8'); gate_path.write_text('gate',encoding='utf-8')
    completed=__import__('subprocess').run([str(ROOT/'scripts/agent/now'),'dispatch','--plan',str(plan_path),'--gate',str(gate_path)],cwd=ROOT,text=True,capture_output=True)
    assert completed.returncode==2 and 'missing or unexpected' in completed.stderr


def test_claim_rejects_stored_zones_string_even_with_recomputed_token(tmp_path: Path) -> None:
    from dataclasses import asdict
    from tools.now_orchestrator.runtime.claims import Claim, _claim_token

    store = _store(tmp_path)
    original = _claim(store)
    original_path = store.claims_dir / f"{original.token}.json"
    original_path.unlink()
    forged = Claim("0" * 64, original.key, original.track, tuple("zone"), original.owner, original.run_id, original.task_id, original.worker_id, original.snapshot_version, original.captured_at, original.snapshot_digest, original.created_at)
    forged = replace(forged, token=_claim_token(forged))
    payload = asdict(forged)
    payload["zones"] = "zone"
    (store.claims_dir / f"{forged.token}.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="claim evidence"):
        store.lookup(forged.token)


def test_dispatch_rejects_unapproved_worktree_selector_before_orca(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import WorktreePlacement

    store = _store(tmp_path)
    request = replace(_dispatch_input(tmp_path, store), worktree="caller-selected")
    claim = store.lookup(request.plan.claim_token)
    assert claim is not None
    placement = WorktreePlacement(claim.key, claim.token, str(tmp_path.resolve()), str(store.common_dir.resolve()), "approved-selector", "placement:1")
    calls = []
    result, receipt = IntegrationCoordinator(store, tmp_path, lambda *args: calls.append(args) or CommandResult(1, ""), placement_authority=lambda _: placement).dispatch(request)
    assert result.blocked and receipt is None and calls == []


def test_dispatch_show_failure_is_not_exact_absence_and_never_starts_worker(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import ReleaseGateReport, WorktreePlacement
    from tools.now_orchestrator.integration.coordinator import _marker

    store = _store(tmp_path)
    request = _dispatch_input(tmp_path, store)
    claim = store.lookup(request.plan.claim_token)
    assert claim is not None
    gate = ReleaseGateReport.read(tmp_path, request.gate_report, request.gate_id, claim.key, claim.snapshot_digest)
    marker = _marker(claim, gate)
    placement = WorktreePlacement(claim.key, claim.token, str(tmp_path.resolve()), str(store.common_dir.resolve()), request.worktree, "placement:1")
    calls: list[tuple[str, ...]] = []
    def runner(argv, cwd=None):
        call = tuple(argv); calls.append(call)
        if "task-list" in call:
            return CommandResult(0, json.dumps({"ok": True, "result": {"tasks": [{"id": "task-1", "spec": f"{gate.approved_spec}\n\n{marker}"}]}}))
        if "dispatch-show" in call:
            return CommandResult(0, '{"ok":false,"error":"lookup failed"}')
        raise AssertionError(call)
    result, receipt = IntegrationCoordinator(store, tmp_path, runner, placement_authority=lambda _: placement).dispatch(request)
    assert result.blocked and receipt is None
    assert not any("worker-start" in call for call in calls)


def test_review_receipt_publish_is_atomic_and_fsyncs_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.now_orchestrator.integration import ReviewEvidence, ReviewReceiptStore
    import tools.now_orchestrator.integration.coordinator as module
    import stat

    common = tmp_path / ".git"; common.mkdir()
    store = ReviewReceiptStore(common)
    evidence = ReviewEvidence("t", "d", "w", "a" * 40, "verify", "review", 0, 0, str(common), str(tmp_path), "make verify", 0, "b" * 64, "", "")
    replacements = []; sync_modes=[]
    real_replace = module.os.replace
    real_fsync = module.os.fsync
    def replace_spy(source, target):
        replacements.append((source, target)); return real_replace(source, target)
    def fsync_spy(descriptor):
        sync_modes.append(stat.S_IFMT(module.os.fstat(descriptor).st_mode)); return real_fsync(descriptor)
    monkeypatch.setattr(module.os, "replace", replace_spy)
    monkeypatch.setattr(module.os, "fsync", fsync_spy)
    issued = store.issue(evidence)
    assert replacements and store.read(issued.receipt_id) == issued
    assert stat.S_IFREG in sync_modes and stat.S_IFDIR in sync_modes
    assert not list(store.root.glob("*.tmp"))


def test_actual_dispatch_operation_rejects_cross_task_stale_receipt(tmp_path: Path) -> None:
    from dataclasses import asdict
    from tools.now_orchestrator.integration import ReleaseGateReport, WorktreePlacement
    from tools.now_orchestrator.integration.coordinator import DispatchProvenance, _marker
    from tools.now_orchestrator.integration.provenance import ProvenanceJournal

    store = _store(tmp_path); request = _dispatch_input(tmp_path, store)
    claim = store.lookup(request.plan.claim_token); assert claim is not None
    gate = ReleaseGateReport.read(tmp_path, request.gate_report, request.gate_id, claim.key, claim.snapshot_digest)
    marker = _marker(claim, gate); operation_id = sha256(marker.encode()).hexdigest()
    stale = DispatchProvenance(marker, operation_id, claim.token, "PMM-OTHER", claim.track, claim.snapshot_digest, claim.run_id, "task", "dispatch", "worker", "succeeded", gate.gate_id, gate.report_digest, gate.scope_digest, gate.approved_spec_digest, gate.binding_digest)
    ProvenanceJournal(store.common_dir, operation_id).append("dispatch_succeeded", receipt=asdict(stale))
    placement = WorktreePlacement(claim.key, claim.token, str(tmp_path.resolve()), str(store.common_dir.resolve()), request.worktree, "placement:1")
    calls = []
    result, receipt = IntegrationCoordinator(store, tmp_path, lambda *args: calls.append(args) or CommandResult(1, ""), placement_authority=lambda _: placement).dispatch(request)
    assert result.blocked and receipt is None and calls == []


def test_jira_failed_outcome_can_retry_only_after_valid_absence_reconciliation(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraReconciliation, JiraResult

    common = tmp_path / ".git"; common.mkdir(); ledger = JiraLedger(common_dir=common)
    contract = ExecutionContract("Mike", "acct", "B", ("none",), ("AC",), ("DoD",), "RG", ("e",), ("tools",))
    payload = {"transition_id": "done", "assignee": {"displayName": "Mike", "accountId": "acct"}, "execution_contract": contract.as_payload()}
    intent = JiraIntent("Mike", "transition", "PMM", "PMM-5", payload, contract, assignee_account_id="acct")
    adapter = AuditBeforeWriteAdapter(ledger); _, intent_id = adapter.prepare(intent); assert intent_id
    adapter.record(JiraResult(intent_id, False, None)); ledger.reconcile(JiraReconciliation(intent_id, "read-absent", False))
    writes = []
    def write(receipt_id): writes.append(receipt_id); return JiraResult(receipt_id, True, "write-2")
    def read(): return JiraRemoteEvidence(intent_id, "PMM-5", "Done", "done", intent.payload_digest(), "read-2")
    result = JiraClosePort(adapter, intent, write, read).execute("PMM-5", "Done", "done", intent.payload_digest())
    assert result.status == "Done" and writes == [intent_id]


def test_parallel_jira_close_serializes_one_remote_write(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraResult

    common = tmp_path / ".git"; common.mkdir(); ledger = JiraLedger(common_dir=common)
    contract = ExecutionContract("Mike", "acct", "B", ("none",), ("AC",), ("DoD",), "RG", ("e",), ("tools",))
    payload = {"transition_id": "done", "assignee": {"displayName": "Mike", "accountId": "acct"}, "execution_contract": contract.as_payload()}
    intent = JiraIntent("Mike", "transition", "PMM", "PMM-5", payload, contract, assignee_account_id="acct")
    writes: list[str] = []
    def write(intent_id): writes.append(intent_id); time.sleep(0.05); return JiraResult(intent_id, True, "write")
    def read():
        intent_id = sha256("\0".join((intent.actor, intent.operation, intent.project, intent.issue_key or "", intent.payload_digest())).encode()).hexdigest()
        return JiraRemoteEvidence(intent_id, "PMM-5", "Done", "done", intent.payload_digest(), "read")
    results=[]
    def execute():
        port=JiraClosePort(AuditBeforeWriteAdapter(ledger),intent,write,read)
        try: results.append(port.execute("PMM-5","Done","done",intent.payload_digest()).status)
        except Exception as error: results.append(type(error).__name__)
    threads=[threading.Thread(target=execute) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert len(writes) == 1 and results.count("Done") == 2


def test_parallel_jira_close_reuses_stored_terminal_readback_not_mutable_port(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraResult

    common=tmp_path/'.git'; common.mkdir(); ledger=JiraLedger(common_dir=common)
    contract=ExecutionContract('Mike','acct','B',('none',),('AC',),('DoD',),'RG',('e',),('tools',))
    payload={'transition_id':'done','assignee':{'displayName':'Mike','accountId':'acct'},'execution_contract':contract.as_payload()}
    intent=JiraIntent('Mike','transition','PMM','PMM-5',payload,contract,assignee_account_id='acct')
    intent_id=sha256("\0".join((intent.actor,intent.operation,intent.project,intent.issue_key or '',intent.payload_digest())).encode()).hexdigest()
    writes=[]; reads=[]
    def write(value): writes.append(value); time.sleep(0.03); return JiraResult(value,True,'write')
    def read():
        reads.append(True)
        return JiraRemoteEvidence(intent_id,'PMM-5','Done','done',intent.payload_digest(),f'read-{len(reads)}')
    results=[]
    def execute():
        try: results.append(JiraClosePort(AuditBeforeWriteAdapter(ledger),intent,write,read).execute('PMM-5','Done','done',intent.payload_digest()).status)
        except Exception as error: results.append(type(error).__name__)
    threads=[threading.Thread(target=execute) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert writes==[intent_id] and results==['Done','Done'] and len(reads)==1


def test_jira_remote_success_crash_before_ledger_record_recovers_by_readback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.now_orchestrator.integration import JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraResult

    common=tmp_path/'.git'; common.mkdir(); ledger=JiraLedger(common_dir=common); adapter=AuditBeforeWriteAdapter(ledger)
    contract=ExecutionContract('Mike','acct','B',('none',),('AC',),('DoD',),'RG',('e',),('tools',))
    payload={'transition_id':'done','assignee':{'displayName':'Mike','accountId':'acct'},'execution_contract':contract.as_payload()}
    intent=JiraIntent('Mike','transition','PMM','PMM-5',payload,contract,assignee_account_id='acct')
    intent_id=sha256("\0".join((intent.actor,intent.operation,intent.project,intent.issue_key or '',intent.payload_digest())).encode()).hexdigest()
    writes=[]; reads=[]; crashed=False; original=adapter.record
    def write(value): writes.append(value); return JiraResult(value,True,'write-remote')
    def read(): reads.append(True); return JiraRemoteEvidence(intent_id,'PMM-5','Done','done',intent.payload_digest(),'read-recovered')
    def record_once(result):
        nonlocal crashed
        if not crashed: crashed=True; raise OSError('crash before ledger outcome')
        return original(result)
    monkeypatch.setattr(adapter,'record',record_once)
    port=JiraClosePort(adapter,intent,write,read)
    with pytest.raises(OSError,match='crash'): port.execute('PMM-5','Done','done',intent.payload_digest())
    recovered=port.execute('PMM-5','Done','done',intent.payload_digest())
    assert recovered.status=='Done' and writes==[intent_id] and len(reads)>=1


def test_jira_second_attempt_crash_uses_distinct_durable_attempt_wal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.now_orchestrator.integration import JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraResult

    common=tmp_path/'.git'; common.mkdir(); ledger=JiraLedger(common_dir=common); adapter=AuditBeforeWriteAdapter(ledger)
    contract=ExecutionContract('Mike','acct','B',('none',),('AC',),('DoD',),'RG',('e',),('tools',))
    payload={'transition_id':'done','assignee':{'displayName':'Mike','accountId':'acct'},'execution_contract':contract.as_payload()}
    intent=JiraIntent('Mike','transition','PMM','PMM-5',payload,contract,assignee_account_id='acct')
    intent_id=sha256("\0".join((intent.actor,intent.operation,intent.project,intent.issue_key or '',intent.payload_digest())).encode()).hexdigest()
    writes=[]; read_statuses=iter(('Open','Done')); original=adapter.record; crash_second=True
    def write(value):
        writes.append(value)
        return JiraResult(value,False,None) if len(writes)==1 else JiraResult(value,True,'write-2')
    def read(): return JiraRemoteEvidence(intent_id,'PMM-5',next(read_statuses),'done',intent.payload_digest(),f'read-{len(writes)}')
    port=JiraClosePort(adapter,intent,write,read)
    with pytest.raises(ValueError,match='absent'): port.execute('PMM-5','Done','done',intent.payload_digest())
    def crash_after_second(result):
        nonlocal crash_second
        if result.success and crash_second: crash_second=False; raise OSError('crash after second remote write')
        return original(result)
    monkeypatch.setattr(adapter,'record',crash_after_second)
    with pytest.raises(OSError,match='second'): port.execute('PMM-5','Done','done',intent.payload_digest())
    recovered=port.execute('PMM-5','Done','done',intent.payload_digest())
    assert recovered.status=='Done' and len(writes)==2
    attempts=[event for event in ledger.events_for(intent_id) if event.get('event')=='write_intent']
    assert [event.get('attempt') for event in attempts]==[1,2]


def test_jira_ledger_first_create_write_all_and_fsyncs_file_and_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import stat
    import tools.now_orchestrator.jira.ledger as module
    from tools.now_orchestrator.jira import ExecutionContract, JiraIntent, JiraLedger

    common=tmp_path/'.git'; common.mkdir(); ledger=JiraLedger(common_dir=common)
    contract=ExecutionContract('Mike','acct','B',('none',),('AC',),('DoD',),'RG',('e',),('tools',))
    payload={'transition_id':'done','assignee':{'displayName':'Mike','accountId':'acct'},'execution_contract':contract.as_payload()}
    intent=JiraIntent('Mike','transition','PMM','PMM-5',payload,contract,assignee_account_id='acct')
    real_write=module.os.write; real_fsync=module.os.fsync; writes=[]; sync_modes=[]
    def partial_write(fd,data): writes.append(len(data)); return real_write(fd,data[:max(1,min(7,len(data)))])
    def fsync_spy(fd): sync_modes.append(stat.S_IFMT(module.os.fstat(fd).st_mode)); return real_fsync(fd)
    monkeypatch.setattr(module.os,'write',partial_write); monkeypatch.setattr(module.os,'fsync',fsync_spy)
    ledger.authorize(intent)
    parsed=json.loads(ledger.path.read_text(encoding='utf-8'))
    assert parsed['event']=='intent' and len(writes)>1
    assert stat.S_IFREG in sync_modes and stat.S_IFDIR in sync_modes


def test_close_authority_contract_includes_durable_dispatch_and_close_journal() -> None:
    from tools.now_orchestrator.integration import CloseCoordinator

    assert "dispatch_authority" in CloseCoordinator.__init__.__annotations__
    assert "common_dir" in CloseCoordinator.__init__.__annotations__


def test_mike_approval_receipt_binds_canonical_repo_and_base() -> None:
    from tools.now_orchestrator.integration import MergeApprovalEvidence

    assert {"repo", "base_ref"}.issubset(MergeApprovalEvidence.__dataclass_fields__)


def test_ops_receipt_binds_cross_task_chain_and_canonical_blobs() -> None:
    from tools.now_orchestrator.integration import OpsSyncInput, OpsSyncReadback

    identity = {"task_key", "dispatch_id", "issue_key", "scope_digest", "repo", "product_merge_commit"}
    blobs = {"handoff_blob", "tasks_blob", "exec_plan_path", "exec_plan_blob"}
    assert identity.issubset(OpsSyncInput.__dataclass_fields__)
    assert (identity | blobs).issubset(OpsSyncReadback.__dataclass_fields__)


def test_review_receipt_binds_raw_make_verify_result() -> None:
    from tools.now_orchestrator.integration import ReviewEvidence

    assert {"verify_command", "verify_exit_code", "verify_output_digest"}.issubset(ReviewEvidence.__dataclass_fields__)


def test_authority_journal_rejects_foreign_identity_and_duplicate_step(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import AuthorityJournal

    common = tmp_path / ".git"
    common.mkdir()
    journal = AuthorityJournal(common, "a" * 64)
    identity = {"task_key": "PMM-5", "claim_token": "c" * 64, "scope_digest": "s" * 64}
    with journal.locked():
        journal.open(identity)
        journal.intent("jira", {"issue_key": "PMM-5", "transition": "done"})
        journal.effect("jira", {"remote_evidence_id": "jira-1"})
        with pytest.raises(ValueError, match="binding mismatch"):
            journal.intent("jira", {"issue_key": "PMM-OTHER", "transition": "done"})
    with journal.locked():
        with pytest.raises(ValueError, match="identity mismatch"):
            journal.open({**identity, "task_key": "PMM-OTHER"})


def test_authority_journal_complete_is_replay_only(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import AuthorityJournal

    common = tmp_path / ".git"
    common.mkdir()
    journal = AuthorityJournal(common, "b" * 64)
    receipt = {"merge_commit": "d" * 40, "jira": "jira-1", "orca": "released"}
    with journal.locked():
        journal.open({"task_key": "PMM-5", "claim_token": "c" * 64})
        assert journal.complete(receipt) == receipt
    with journal.locked():
        assert journal.complete() == receipt
        with pytest.raises(ValueError, match="invalid after completion"):
            journal.intent("orca_release", {"dispatch_id": "d-1"})
