from __future__ import annotations
from hashlib import sha256
import json
import multiprocessing
import os
import subprocess
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def _dispatch_process(common_dir, repo_root, request, barrier, queue):
    from tools.now_orchestrator.integration import CommandResult, IntegrationCoordinator, WorktreePlacement
    from tools.now_orchestrator.runtime import ClaimStore

    log = Path(repo_root) / "process-calls.log"
    def runner(argv, cwd=None):
        call = tuple(argv)
        descriptor = os.open(log, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, (json.dumps(call) + "\n").encode())
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if "task-list" in call:return CommandResult(0,'{"ok":true,"result":{"tasks":[]}}')
        if "task-create" in call:return CommandResult(0,'{"ok":true,"result":{"task":{"id":"orca-task-1"}}}')
        if "worker-start" in call:return CommandResult(0,'{"ok":true,"result":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","state":"ready","stage":"input_accepted"}}')
        return CommandResult(0,'{"ok":true,"result":{"deliveryId":"delivery-1","messages":[{"type":"worker_done","payload":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","outcome":"succeeded"}}],"count":1}}')
    barrier.wait()
    placement = WorktreePlacement(request.plan.key, request.plan.claim_token, str(Path(repo_root).resolve()), str(Path(common_dir).resolve()), request.worktree, "test-placement-receipt")
    plan, receipt = IntegrationCoordinator(ClaimStore(Path(common_dir)), Path(repo_root), runner, placement_authority=lambda _: placement).dispatch(request)
    queue.put((plan.state.value, receipt is not None))
def store(tmp_path):
    common=tmp_path/'.git'; common.mkdir(exist_ok=True); return __import__('tools.now_orchestrator.runtime',fromlist=['ClaimStore']).ClaimStore(common)
def dispatch_receipt():
    from tools.now_orchestrator.integration import DispatchProvenance
    return DispatchProvenance('now-spec:'+'a'*64,'1'*64,'c'*64,'PMM-5','B','a'*64,'run-1','orca-task-1','d-1','w-1','succeeded','RG-20260828-now-orchestrator','2'*64,'b'*64,'3'*64,'4'*64)
def input_for(tmp_path):
    from tools.now_orchestrator.integration import DispatchInput
    from tools.now_orchestrator.runtime import ActionPlan, ClaimRequest, LifecycleState
    digest='a'*64; claim=ClaimRequest('PMM-5','B',('tools/now_orchestrator/integration',),'Mike','run-1','claim-task','claim-worker','now.snapshot.v1','2026-08-28T10:00:00+00:00',digest)
    persisted=store(tmp_path).claim(claim).claim
    assert persisted is not None
    plan=ActionPlan('PMM-5','B',LifecycleState.CONFIRMED,'run-1','claim-task','claim-worker',persisted.token,False,True)
    return DispatchInput(plan,'RG-20260828-now-orchestrator',_gate_report(tmp_path),'do work','T','T','term-coordinator','current')
def placement_for(tmp_path, request):
    from tools.now_orchestrator.integration import WorktreePlacement
    return WorktreePlacement(request.plan.key,request.plan.claim_token,str(tmp_path.resolve()),str((tmp_path/'.git').resolve()),request.worktree,'test-placement-receipt')
def test_import_hashes_and_three_facade_golden_contract():
    expected={'.opencode/skills/release-cutter/SKILL.md':'6a97d0238c3675a9b0c5e7b977dab48ceb64541036ad09cea8c324a6a00dfc98','.opencode/agents/release-critic.md':'e76fa380998e272ac4b0bcb35c15f9fa86e14a98cb39c4451aca3393e145253f','.opencode/commands/release-gate.md':'f59ed9157528af83fd7cf0b47265ca4ae660585ff91b5e18efa46ae12e33d2fa','.opencode/commands/release-task.md':'349e5b3adb5346a21734f7aabbc6f9325b2d978256e32ed7ffb06c7d420a50cb','docs/release-gates/README.md':'55611117357914bdb5a26d7ae9bc0243e9820287af6bfa87ee88af899b772016'}
    assert {p:sha256((ROOT/p).read_bytes()).hexdigest() for p in expected}==expected
    from tools.now_orchestrator.core import load_snapshot
    from tools.now_orchestrator.facades import claude_entry,codex_entry,opencode_entry
    source=lambda payload:{'fresh':True,'payload':payload}
    snapshot=load_snapshot({'version':'now.snapshot.v1','captured_at':'2026-08-28T10:00:00+00:00','jira':source({'issues':[]}),'git':source({'branches':[],'pull_requests':[],'worktrees':[]}),'orca':source({'runs':[],'tasks':[],'workers':[],'gates':[]}),'handoff':source({'conflicts':[]}),'tasks':source({'conflicts':[]}),'exec_plans':source({'plans':[]})})
    outputs=(claude_entry(snapshot),codex_entry(snapshot),opencode_entry(snapshot))
    assert outputs[0]==outputs[1]==outputs[2]
    assert all(output.endswith('\n') and output==outputs[0] for output in outputs)


def test_three_real_cli_facades_return_byte_identical_entire_stdout():
    source=lambda payload:{'fresh':True,'payload':payload}
    raw={'version':'now.snapshot.v1','captured_at':'2026-08-28T10:00:00+00:00','jira':source({'issues':[]}),'git':source({'branches':[],'pull_requests':[],'worktrees':[]}),'orca':source({'runs':[],'tasks':[],'workers':[],'gates':[]}),'handoff':source({'conflicts':[]}),'tasks':source({'conflicts':[]}),'exec_plans':source({'plans':[]})}
    payload=json.dumps(raw,separators=(',',':'))
    outputs=[]
    for client in ('claude','codex','opencode'):
        completed=subprocess.run([str(ROOT/'scripts/agent/now'),'facade',client,'--stdin'],cwd=ROOT,input=payload,text=True,capture_output=True,check=True)
        outputs.append(completed.stdout.encode())
    assert outputs[0]==outputs[1]==outputs[2]
def test_dispatch_exact_argv_typed_provenance_and_no_preclaim_side_effect(tmp_path):
    from tools.now_orchestrator.integration import CommandResult, IntegrationCoordinator
    calls=[]
    def runner(argv,cwd=None):
        call=tuple(argv); calls.append(call)
        if 'task-list' in call:return CommandResult(0,'{"ok":true,"result":{"tasks":[]}}')
        if 'task-create' in call:return CommandResult(0,'{"ok":true,"result":{"task":{"id":"orca-task-1"}}}')
        if 'worker-start' in call:return CommandResult(0,'{"ok":true,"result":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","state":"ready","stage":"input_accepted"}}')
        return CommandResult(0,'{"ok":true,"result":{"deliveryId":"delivery-1","messages":[{"type":"worker_done","payload":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","outcome":"succeeded"}}],"count":1}}')
    request=input_for(tmp_path); out,receipt=IntegrationCoordinator(store(tmp_path),tmp_path,runner,placement_authority=lambda _:placement_for(tmp_path,request)).dispatch(request); assert out.state.value=='DISPATCHED' and receipt and receipt.task_id=='orca-task-1'
    assert calls[0]==('orca','orchestration','task-list','--run','run-1','--json')
    assert calls[1][0:5]==('orca','orchestration','task-create','--spec','do work\n\n'+receipt.marker) and '--task-title' in calls[1] and '--display-name' in calls[1]
    assert calls[2]==('orca','orchestration','worker-start','--task','orca-task-1','--worktree','current','--agent','codex','--run','run-1','--from','term-coordinator','--json')
    assert calls[3]==('orca','orchestration','check','--run','run-1','--wait','--types','worker_done,escalation','--timeout-ms','600000','--json')
def test_dispatch_fail_closed_and_race_reuses_global_lease(tmp_path):
    from tools.now_orchestrator.integration import CommandResult, IntegrationCoordinator
    request=input_for(tmp_path); calls=[]; placement=lambda _:placement_for(tmp_path,request); bad=IntegrationCoordinator(store(tmp_path),tmp_path,lambda a,cwd=None:calls.append(tuple(a)) or CommandResult(0,'{}'),placement_authority=placement)
    result,_=bad.dispatch(request); assert result.blocked and calls[-1][2]=='task-list'
    second=IntegrationCoordinator(store(tmp_path),tmp_path,lambda a,cwd=None:CommandResult(0,'{"ok":true,"result":{"tasks":[]}}'),placement_authority=placement)
    result,_=second.dispatch(request); assert result.blocked and 'task-create' in (result.reason or '')
def test_verify_and_reviewer_are_runner_evidence_not_caller_booleans(tmp_path):
    from tools.now_orchestrator.integration import CommandResult, ReviewInput, ReviewerCoordinator, ReviewReceiptStore
    from tools.now_orchestrator.runtime import ActionPlan,LifecycleState
    common=tmp_path/'.git'; common.mkdir()
    receipt=dispatch_receipt(); plan=ActionPlan('PMM-5','B',LifecycleState.DISPATCHED,'run-1','orca-task-1','w-1','c'*64,False,False)
    outputs=iter((json.dumps({'ok':True,'result':{'worker':{'taskId':'orca-task-1','dispatchId':'d-1','workerId':'w-1','worktree':str(tmp_path.resolve())}}}),str(tmp_path.resolve())+'\n',str(common.resolve())+'\n',str(common.resolve())+'\n','d'*40+'\n','PASS\n','findings\nVERDICT: 0 blockers, 0 warnings\n'))
    calls=[]
    def runner(a,cwd=None): calls.append((tuple(a),cwd)); return CommandResult(0,next(outputs))
    result,evidence=ReviewerCoordinator(runner,ReviewReceiptStore(common)).verify_and_review(ReviewInput(plan,receipt,tmp_path,tmp_path)); assert result.state.value=='MERGE_GATE' and evidence and calls[4][0]==('git','rev-parse','HEAD') and calls[5][0]==('make','verify') and calls[6][0][0:4]==('opencode','run','--agent','reviewer')
    assert evidence.receipt_id==evidence.receipt_digest


def test_reviewer_substring_is_not_a_structured_verdict(tmp_path):
    from tools.now_orchestrator.integration import CommandResult, ReviewInput, ReviewerCoordinator, ReviewReceiptStore
    from tools.now_orchestrator.runtime import ActionPlan,LifecycleState
    common=tmp_path/'.git'; common.mkdir()
    receipt=dispatch_receipt(); plan=ActionPlan('PMM-5','B',LifecycleState.DISPATCHED,'run-1','orca-task-1','w-1','c'*64,False,False)
    outputs=iter((json.dumps({'ok':True,'result':{'worker':{'taskId':'orca-task-1','dispatchId':'d-1','workerId':'w-1','worktree':str(tmp_path.resolve())}}}),str(tmp_path.resolve())+'\n',str(common.resolve())+'\n',str(common.resolve())+'\n','d'*40+'\n','PASS\n','note contains VERDICT: 0 blockers, 0 warnings but is not final structured output\n'))
    result,evidence=ReviewerCoordinator(lambda a,cwd=None:CommandResult(0,next(outputs)),ReviewReceiptStore(common)).verify_and_review(ReviewInput(plan,receipt,tmp_path,tmp_path))
    assert result.blocked and evidence is None


def _gate_report(tmp_path: Path, status: str = "READY") -> Path:
    path = tmp_path / "docs/release-gates/2026-08-28-now-orchestrator.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Release Gate: `/now`\n\n## Gate\n\n"
        "- Gate ID: RG-20260828-now-orchestrator\n"
        "- Handoff status: READY_AUTO\n"
        f"- DISCOVERY_STATUS: {status}\n\n"
        "## 8. Scope lock\n\n### In scope\n\n- T04\n\n"
        "### Explicitly out of scope\n\n- deploy\n\n"
        "## 9. Acceptance criteria\n\n- [ ] pass\n\n"
        "## 12. Autopilot handoff\n\ndo work\n\n"
        "## 13. Final decision\n\nKEEP\n\n"
        f"DISCOVERY_STATUS: {status}\n",
        encoding="utf-8",
    )
    return path


def test_release_gate_readback_binds_scope_digest_to_task_and_snapshot(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import ReleaseGateReport

    proof = ReleaseGateReport.read(
        tmp_path,
        _gate_report(tmp_path),
        "RG-20260828-now-orchestrator",
        "PMM-5",
        "a" * 64,
    )
    assert proof.discovery_status == "READY"
    assert proof.binding_digest == sha256(
        "\0".join((proof.gate_id, proof.report_digest, proof.scope_digest, proof.approved_spec_digest, "PMM-5", "a" * 64)).encode()
    ).hexdigest()


def test_release_gate_readback_rejects_non_ready_and_path_escape(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import ReleaseGateReport

    with pytest.raises(ValueError, match="READY"):
        ReleaseGateReport.read(tmp_path, _gate_report(tmp_path, "BLOCKED"), "RG-20260828-now-orchestrator", "PMM-5", "a" * 64)
    outside = tmp_path / "outside.md"
    outside.write_text(_gate_report(tmp_path).read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ValueError, match="release-gates"):
        ReleaseGateReport.read(tmp_path, outside, "RG-20260828-now-orchestrator", "PMM-5", "a" * 64)


def test_orca_terminal_event_reads_exact_result_messages_schema() -> None:
    from tools.now_orchestrator.integration import parse_orca_terminal_event

    raw = json.dumps({"ok": True, "result": {"deliveryId": "delivery-1", "messages": [{"type": "worker_done", "payload": {"taskId": "t-1", "dispatchId": "d-1", "workerId": "w-1", "outcome": "succeeded"}}], "count": 1}})
    event = parse_orca_terminal_event(raw, "t-1", "d-1", "w-1")
    assert event.kind == "worker_done"
    assert event.outcome == "succeeded"


@pytest.mark.parametrize(
    "raw",
    [
        '{"result":{"taskId":"t-1","dispatchId":"d-1","outcome":"worker_done"}}',
        '{"result":{"messages":[{"type":"worker_done","payload":{"taskId":"other","dispatchId":"d-1","workerId":"w-1","outcome":"succeeded"}}],"count":1}}',
        "not-json",
    ],
)
def test_orca_terminal_event_rejects_flat_mismatched_or_malformed_json(raw: str) -> None:
    from tools.now_orchestrator.integration import parse_orca_terminal_event

    with pytest.raises(ValueError):
        parse_orca_terminal_event(raw, "t-1", "d-1", "w-1")


@pytest.mark.parametrize("terminal", ["malformed", "escalation", "failed"])
def test_dispatch_terminal_error_always_releases_fenced_lease(tmp_path: Path, terminal: str) -> None:
    from tools.now_orchestrator.integration import CommandResult, IntegrationCoordinator

    calls = []
    def runner(argv, cwd=None):
        call = tuple(argv); calls.append(call)
        if "task-list" in call: return CommandResult(0, '{"ok":true,"result":{"tasks":[]}}')
        if "task-create" in call: return CommandResult(0, '{"ok":true,"result":{"task":{"id":"orca-task-1"}}}')
        if "worker-start" in call: return CommandResult(0, '{"ok":true,"result":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","state":"ready","stage":"input_accepted"}}')
        if terminal == "malformed": return CommandResult(0, "not-json")
        if terminal == "escalation": message = {"type":"escalation","payload":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1"}}
        else: message = {"type":"worker_done","payload":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","outcome":"failed"}}
        return CommandResult(0, json.dumps({"ok":True,"result":{"deliveryId":"delivery-1","messages":[message],"count":1}}))

    runtime = store(tmp_path)
    request=input_for(tmp_path); result, receipt = IntegrationCoordinator(runtime, tmp_path, runner, placement_authority=lambda _:placement_for(tmp_path,request)).dispatch(request)
    assert result.blocked and receipt is None
    assert not runtime.lease_path.exists()


def test_retry_after_success_reuses_append_only_receipt_without_effects(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CommandResult, IntegrationCoordinator

    calls = []
    def runner(argv, cwd=None):
        call=tuple(argv); calls.append(call)
        if "task-list" in call:return CommandResult(0,'{"ok":true,"result":{"tasks":[]}}')
        if "task-create" in call:return CommandResult(0,'{"ok":true,"result":{"task":{"id":"orca-task-1"}}}')
        if "worker-start" in call:return CommandResult(0,'{"ok":true,"result":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","state":"ready","stage":"input_accepted"}}')
        return CommandResult(0,'{"ok":true,"result":{"deliveryId":"delivery-1","messages":[{"type":"worker_done","payload":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","outcome":"succeeded"}}],"count":1}}')

    runtime = store(tmp_path); request = input_for(tmp_path); coordinator = IntegrationCoordinator(runtime, tmp_path, runner, placement_authority=lambda _:placement_for(tmp_path,request))
    first = coordinator.dispatch(request); call_count = len(calls)
    second = coordinator.dispatch(request)
    assert second == first and second[1] is not None
    assert len(calls) == call_count
    events = (runtime.root / "provenance" / f"{second[1].operation_id}.jsonl").read_text(encoding="utf-8")
    assert events.count('"event":"dispatch_intent"') == 1
    assert events.count('"event":"dispatch_succeeded"') == 1


def test_two_processes_cannot_duplicate_task_or_worker(tmp_path: Path) -> None:
    runtime = store(tmp_path)
    request = input_for(tmp_path)
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    processes = [context.Process(target=_dispatch_process, args=(str(runtime.common_dir), str(tmp_path), request, barrier, queue)) for _ in range(2)]
    for process in processes: process.start()
    results = [queue.get(timeout=10) for _ in processes]
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0
    calls = [json.loads(line) for line in (tmp_path / "process-calls.log").read_text(encoding="utf-8").splitlines()]
    assert sum("task-create" in call for call in calls) == 1
    assert sum("worker-start" in call for call in calls) == 1
    assert results.count(("DISPATCHED", True)) == 1
    assert results.count(("BLOCKED_EXTERNAL", False)) == 1


def _close_contract(tmp_path: Path, payload_digest: str = '9'*64):
    from dataclasses import replace
    from tools.now_orchestrator.integration import CloseInput, MergeApprovalEvidence, MirrorRequirement, OpsSyncReadback, ReviewEvidence, approval_digest
    from tools.now_orchestrator.runtime import ActionPlan, LifecycleState
    dispatch = dispatch_receipt()
    plan = ActionPlan('PMM-5','B',LifecycleState.MERGE_GATE,'run-1','orca-task-1','w-1','c'*64,False,False)
    review = ReviewEvidence('orca-task-1','d-1','w-1','d'*40,'verify-ref','review-ref',0,0,str(tmp_path/'.git'),str(tmp_path),'make verify',0,'7'*64,'5'*64,'5'*64)
    approval = MergeApprovalEvidence('approval-1','Mike','acct-mike','owner/repo','main','orca-task-1','d-1','w-1','PMM-5',42,'d'*40,'b'*64,'','gate:approval-1')
    approval = replace(approval,approval_digest=approval_digest(approval))
    mirrors=tuple(MirrorRequirement(relative,(token,)) for relative,token in (("docs/agent-system/HANDOFF.md","HANDOFF-DONE"),("docs/agent-system/TASKS.md","TASKS-DONE"),("docs/exec-plans/active/now.md","PLAN-DONE")))
    ops=OpsSyncReadback(str(tmp_path/'ops'),'ops/now-close','f'*40,43,'MERGED','https://example.invalid/pr/43','6'*64,'6'*64,'f'*40,'owner/repo','main','PMM-5','d-1','PMM-5','b'*64,'e'*40,'a'*40,'a'*40,'docs/exec-plans/active/now.md','a'*40)
    return CloseInput(plan,dispatch,review,approval,tmp_path,'owner/repo','main','acct-mike','PMM-5','Done','done',payload_digest,mirrors,ops)


def _close_payload(tmp_path: Path):
    from dataclasses import asdict
    request=_close_contract(tmp_path); raw=asdict(request); raw.pop('repo_root'); raw['plan']=request.plan.as_dict()
    raw['mirrors']=[{'path':item.path,'required_tokens':list(item.required_tokens)} for item in request.mirrors]
    return raw


def test_public_close_routes_never_claim_done_without_remote_ports(tmp_path: Path) -> None:
    evidence=tmp_path/'close.json'; evidence.write_text(json.dumps(_close_payload(tmp_path)),encoding='utf-8')
    for client in ('codex','claude','opencode'):
        completed=subprocess.run([str(ROOT/'scripts/agent/now'),'close','--client',client,'--evidence',str(evidence)],cwd=ROOT,text=True,capture_output=True,check=True)
        result=json.loads(completed.stdout)
        assert result['plan']['state']=='BLOCKED_EXTERNAL' and result['evidence'] is None
        if client=='codex': assert result['side_effect_plan'] is None
        else:
            side=result['side_effect_plan']; assert side['executable'] is False and side['resume']=='readback-first'
            assert side['execution_owner']==f'{client}:approved-tool-adapter' and 'operation_id' in side['receipt_binding']


def _close_runner(calls, *, merged=True):
    from tools.now_orchestrator.integration import CommandResult
    def runner(argv,cwd=None):
        call=tuple(argv); calls.append((call,cwd))
        if call==('git','rev-parse','--show-toplevel'):return CommandResult(0,str(cwd)+'\n')
        if call==('git','rev-parse','--path-format=absolute','--git-common-dir'):return CommandResult(0,str(Path(cwd)/'.git')+'\n')
        if call==('gh','repo','view','--json','nameWithOwner'):return CommandResult(0,json.dumps({'nameWithOwner':'owner/repo'}))
        if call[:3]==('gh','pr','view'):
            state='MERGED' if merged else 'OPEN'
            return CommandResult(0,json.dumps({'number':42,'state':state,'baseRefName':'main','headRefOid':'d'*40,'headRepository':{'nameWithOwner':'owner/repo'},'mergeCommit':{'oid':'e'*40},'url':'https://example.invalid/pr/42'}))
        if call[:4]==('git','--no-replace-objects','merge-base','--is-ancestor'):return CommandResult(0,'')
        if call[:3]==('git','--no-replace-objects','show'):
            if 'HANDOFF.md' in call[3]: return CommandResult(0,'HANDOFF-DONE')
            if 'TASKS.md' in call[3]: return CommandResult(0,'TASKS-DONE')
            return CommandResult(0,'PLAN-DONE')
        if call[:3]==('git','--no-replace-objects','rev-parse'):
            return CommandResult(0,('e' if '^{commit}' in call[3] else 'a')*40+'\n')
        if 'worker-show' in call:return CommandResult(0,'{"ok":true,"result":{"worker":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","outcome":"succeeded"}}}')
        if 'task-list' in call:return CommandResult(0,'{"ok":true,"result":{"tasks":[{"id":"orca-task-1","status":"completed"}]}}')
        if 'worker-release' in call:return CommandResult(0,'{"ok":true,"result":{"state":"released","dispatchId":"d-1","workerId":"w-1"}}')
        raise AssertionError(call)
    return runner


def test_close_rejects_fake_approval_before_any_readback(tmp_path: Path) -> None:
    from dataclasses import replace
    from tools.now_orchestrator.integration import CloseCoordinator
    calls=[]; request=_close_contract(tmp_path)
    authority=request.approval; request=replace(request,approval=replace(request.approval,approver='caller-boolean'))
    result,evidence=CloseCoordinator(object(),lambda _:request.review,lambda _:authority,lambda _:request.ops_sync,_close_runner(calls),dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)  # type: ignore[arg-type]
    assert result.blocked and evidence is None and calls==[]


def test_codex_without_jira_write_port_is_blocked_external_before_effects(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator
    calls=[]; result,evidence=CloseCoordinator(None,None,None,None,_close_runner(calls)).close(_close_contract(tmp_path))
    assert result.state.value=='BLOCKED_EXTERNAL' and evidence is None
    assert 'authority port' in (result.reason or '') and calls==[]


def test_close_rejects_fake_gh_merge_readback_without_jira_write(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator
    calls=[]; request=_close_contract(tmp_path)
    fake_port=object()
    result,evidence=CloseCoordinator(fake_port,lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,_close_runner(calls,merged=False),dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)  # type: ignore[arg-type]
    assert result.blocked and evidence is None
    assert calls[0][0]==('git','rev-parse','--show-toplevel')
    assert calls[1][0]==('git','rev-parse','--path-format=absolute','--git-common-dir')
    assert calls[2][0]==('gh','repo','view','--json','nameWithOwner')
    assert calls[3][0][:3]==('gh','pr','view')


def test_close_audits_before_jira_write_reads_back_and_reaches_done(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator, JiraClosePort, JiraRemoteEvidence
    from tools.now_orchestrator.jira import AuditBeforeWriteAdapter, ExecutionContract, JiraIntent, JiraLedger, JiraResult
    runtime=store(tmp_path); ledger=JiraLedger(common_dir=runtime.common_dir); calls=[]; order=[]
    contract=ExecutionContract('Mike','acct-mike','B',('none',),('AC',),('DoD',),'RG-20260828-now-orchestrator',('gh:pr-42',),('tools/now_orchestrator',))
    payload={'transition_id':'done','assignee':{'displayName':'Mike','accountId':'acct-mike'},'execution_contract':contract.as_payload()}
    intent=JiraIntent('Mike','transition','PMM','PMM-5',payload,contract,assignee_account_id='acct-mike')
    def write(intent_id):
        assert '"event":"intent"' in ledger.path.read_text(encoding='utf-8'); order.append('write'); return JiraResult(intent_id,True,'jira-write-1')
    payload_digest=intent.payload_digest()
    def readback():
        order.append('read'); intent_id=next(item['intent_id'] for item in ledger._events() if item.get('event')=='intent'); return JiraRemoteEvidence(intent_id,'PMM-5','Done','done',payload_digest,'jira-read-1')
    port=JiraClosePort(AuditBeforeWriteAdapter(ledger),intent,write,readback)
    request=_close_contract(tmp_path,payload_digest)
    result,evidence=CloseCoordinator(port,lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,_close_runner(calls),dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)
    assert result.state.value=='DONE' and evidence is not None and order==['write','read']
    ledger_text=ledger.path.read_text(encoding='utf-8')
    assert ledger_text.index('"event":"intent"') < ledger_text.index('"event":"outcome"') < ledger_text.index('"event":"readback"')
    assert any('worker-release' in call for call,_ in calls)


def test_close_rejects_cross_task_durable_dispatch_receipt_before_effects(tmp_path: Path) -> None:
    from dataclasses import replace
    from tools.now_orchestrator.integration import CloseCoordinator

    request=_close_contract(tmp_path); calls=[]
    stale=replace(request.dispatch,task_key='PMM-OTHER')
    result,evidence=CloseCoordinator(object(),lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,_close_runner(calls),dispatch_authority=lambda _:stale,common_dir=tmp_path/'.git').close(request)  # type: ignore[arg-type]
    assert result.blocked and evidence is None and calls==[]


def test_close_rejects_caller_zero_zero_review_without_durable_receipt(tmp_path: Path) -> None:
    from dataclasses import replace
    from tools.now_orchestrator.integration import CloseCoordinator

    request=_close_contract(tmp_path); calls=[]; durable=request.review
    request=replace(request,review=replace(request.review,receipt_id='9'*64,receipt_digest='9'*64))
    result,evidence=CloseCoordinator(object(),lambda _:durable,lambda _:request.approval,lambda _:request.ops_sync,_close_runner(calls),dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)  # type: ignore[arg-type]
    assert result.blocked and evidence is None and calls==[]


def test_close_rejects_caller_forged_repo_against_mike_receipt(tmp_path: Path) -> None:
    from dataclasses import replace
    from tools.now_orchestrator.integration import CloseCoordinator

    request=replace(_close_contract(tmp_path),expected_repo='attacker/repo'); calls=[]
    result,evidence=CloseCoordinator(object(),lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,_close_runner(calls),dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)  # type: ignore[arg-type]
    assert result.blocked and evidence is None and calls==[]


def test_close_rejects_cross_task_ops_receipt_replay_before_effects(tmp_path: Path) -> None:
    from dataclasses import replace
    from tools.now_orchestrator.integration import CloseCoordinator

    request=_close_contract(tmp_path); calls=[]; stale=replace(request.ops_sync,task_key='PMM-OTHER')
    result,evidence=CloseCoordinator(object(),lambda _:request.review,lambda _:request.approval,lambda _:stale,_close_runner(calls),dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)  # type: ignore[arg-type]
    assert result.blocked and evidence is None and calls==[]


def test_close_uses_trusted_ops_blobs_not_caller_mirror_tokens(tmp_path: Path) -> None:
    from dataclasses import replace
    from tools.now_orchestrator.integration import CloseCoordinator, MirrorRequirement
    from tools.now_orchestrator.jira import JiraReadback

    (tmp_path/'.git').mkdir(exist_ok=True); request=_close_contract(tmp_path); calls=[]
    request=replace(request,mirrors=(MirrorRequirement('caller/forged.md',('IMPOSSIBLE',)),))
    jira=type('Port',(),{'execute':lambda self,*args:JiraReadback('intent','PMM-5','Done','jira')})()
    result,evidence=CloseCoordinator(jira,lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,_close_runner(calls),dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)
    assert result.state.value=='DONE' and evidence is not None
    assert all('caller/forged.md' not in ' '.join(call) for call,_ in calls)


def test_close_requires_product_merge_ancestor_of_ops_merge(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator
    from tools.now_orchestrator.jira import JiraReadback

    request=_close_contract(tmp_path); calls=[]; base=_close_runner(calls)
    def runner(argv,cwd=None):
        if tuple(argv)==('git','--no-replace-objects','merge-base','--is-ancestor','e'*40,'f'*40):
            from tools.now_orchestrator.integration import CommandResult
            calls.append((tuple(argv),cwd)); return CommandResult(1,'')
        return base(argv,cwd)
    jira=type('Port',(),{'execute':lambda self,*args:JiraReadback('intent','PMM-5','Done','jira')})()
    result,evidence=CloseCoordinator(jira,lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,runner,dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)
    assert result.blocked and evidence is None and not any('worker-release' in call for call,_ in calls)


def test_close_crash_after_worker_release_resumes_without_duplicate_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator, CommandResult
    from tools.now_orchestrator.jira import JiraReadback
    import tools.now_orchestrator.integration.close as close_module

    (tmp_path/'.git').mkdir(exist_ok=True); request=_close_contract(tmp_path); calls=[]; released=False
    base=_close_runner(calls)
    def runner(argv,cwd=None):
        nonlocal released
        call=tuple(argv)
        if 'worker-show' in call and released:
            calls.append((call,cwd)); return CommandResult(0,'{"ok":true,"result":{"worker":{"taskId":"orca-task-1","dispatchId":"d-1","workerId":"w-1","outcome":"succeeded","releaseState":"released"}}}')
        result=base(argv,cwd)
        if 'worker-release' in call: released=True
        return result
    jira=type('Port',(),{'execute':lambda self,*args:JiraReadback('intent','PMM-5','Done','jira')})()
    original=close_module.AuthorityJournal.effect; crashed=False
    def append_once(self,event,payload):
        nonlocal crashed
        if event=='orca_release' and not crashed:
            crashed=True; raise OSError('crash after remote release')
        return original(self,event,payload)
    monkeypatch.setattr(close_module.AuthorityJournal,'effect',append_once)
    coordinator=CloseCoordinator(jira,lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,runner,dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git')
    first,_=coordinator.close(request); second,evidence=coordinator.close(request)
    assert first.blocked and second.state.value=='DONE' and evidence is not None
    assert crashed is True and sum('worker-release' in call for call,_ in calls)==1


def test_close_rejects_foreign_repo_root_before_gh_or_jira(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator, CommandResult
    from tools.now_orchestrator.jira import JiraReadback

    (tmp_path/'.git').mkdir(exist_ok=True); request=_close_contract(tmp_path); calls=[]
    def runner(argv,cwd=None): calls.append((tuple(argv),cwd)); return CommandResult(0,str(tmp_path/'foreign')+'\n')
    jira=type('Port',(),{'execute':lambda self,*args:JiraReadback('intent','PMM-5','Done','jira')})()
    result,evidence=CloseCoordinator(jira,lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,runner,dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)
    assert result.blocked and evidence is None
    assert calls==[(('git','rev-parse','--show-toplevel'),tmp_path)]


def test_close_rejects_foreign_git_common_dir_before_gh_or_jira(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator, CommandResult
    from tools.now_orchestrator.jira import JiraReadback

    (tmp_path/'.git').mkdir(exist_ok=True); request=_close_contract(tmp_path); calls=[]
    def runner(argv,cwd=None):
        call=tuple(argv); calls.append((call,cwd))
        if call==('git','rev-parse','--show-toplevel'): return CommandResult(0,str(tmp_path.resolve())+'\n')
        return CommandResult(0,str(tmp_path/'foreign.git')+'\n')
    jira=type('Port',(),{'execute':lambda self,*args:JiraReadback('intent','PMM-5','Done','jira')})()
    result,evidence=CloseCoordinator(jira,lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,runner,dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)
    assert result.blocked and evidence is None
    assert [call for call,_ in calls]==[('git','rev-parse','--show-toplevel'),('git','rev-parse','--path-format=absolute','--git-common-dir')]


def test_close_git_proofs_disable_replace_refs(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CloseCoordinator
    from tools.now_orchestrator.jira import JiraReadback

    (tmp_path/'.git').mkdir(exist_ok=True); request=_close_contract(tmp_path); calls=[]
    jira=type('Port',(),{'execute':lambda self,*args:JiraReadback('intent','PMM-5','Done','jira')})()
    result,evidence=CloseCoordinator(jira,lambda _:request.review,lambda _:request.approval,lambda _:request.ops_sync,_close_runner(calls),dispatch_authority=lambda _:request.dispatch,common_dir=tmp_path/'.git').close(request)
    assert result.state.value=='DONE' and evidence is not None
    proof_calls=[call for call,_ in calls if call[:2]==('git','--no-replace-objects')]
    assert any('merge-base' in call for call in proof_calls)
    assert any('show' in call for call in proof_calls)
    assert any('rev-parse' in call and '^{commit}' in call[-1] for call in proof_calls)


@pytest.mark.parametrize('crash_step',('verify','reviewer'))
def test_reviewer_pending_local_operation_reruns_safely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, crash_step: str) -> None:
    from tools.now_orchestrator.integration import CommandResult, ReviewInput, ReviewerCoordinator, ReviewReceiptStore
    from tools.now_orchestrator.runtime import ActionPlan,LifecycleState
    import tools.now_orchestrator.integration.coordinator as module

    common=tmp_path/'.git'; common.mkdir(); receipt=dispatch_receipt()
    plan=ActionPlan('PMM-5','B',LifecycleState.DISPATCHED,'run-1','orca-task-1','w-1','c'*64,False,False); calls=[]
    def runner(argv,cwd=None):
        call=tuple(argv); calls.append((call,cwd))
        if 'worker-show' in call:return CommandResult(0,json.dumps({'ok':True,'result':{'worker':{'taskId':'orca-task-1','dispatchId':'d-1','workerId':'w-1','worktree':str(tmp_path.resolve())}}}))
        if call==('git','rev-parse','--show-toplevel'):return CommandResult(0,str(tmp_path.resolve())+'\n')
        if call==('git','rev-parse','--path-format=absolute','--git-common-dir'):return CommandResult(0,str(common.resolve())+'\n')
        if call==('git','rev-parse','HEAD'):return CommandResult(0,'d'*40+'\n')
        if call==('make','verify'):return CommandResult(0,'VERIFY RAW\n','verify stderr\n')
        if call[:4]==('opencode','run','--agent','reviewer'):return CommandResult(0,'review\nVERDICT: 0 blockers, 0 warnings\n')
        raise AssertionError(call)
    original=module.AuthorityJournal.effect; crashed=False
    def crash_once(self,step,payload):
        nonlocal crashed
        if step==crash_step and not crashed: crashed=True; raise OSError(f'crash after {step}')
        return original(self,step,payload)
    monkeypatch.setattr(module.AuthorityJournal,'effect',crash_once)
    coordinator=ReviewerCoordinator(runner,ReviewReceiptStore(common)); request=ReviewInput(plan,receipt,tmp_path,tmp_path)
    first,_=coordinator.verify_and_review(request); second,evidence=coordinator.verify_and_review(request)
    assert first.blocked and second.state.value=='MERGE_GATE' and evidence is not None and crashed
    make_calls=sum(call==('make','verify') for call,_ in calls); reviewer_calls=sum(call[:4]==('opencode','run','--agent','reviewer') for call,_ in calls)
    assert (make_calls,reviewer_calls)==((2,1) if crash_step=='verify' else (1,2))


def test_review_preserves_exact_raw_verify_artifact_and_rejects_tamper(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import CommandResult, ReviewInput, ReviewerCoordinator, ReviewReceiptStore
    from tools.now_orchestrator.runtime import ActionPlan,LifecycleState

    common=tmp_path/'.git'; common.mkdir(); receipt=dispatch_receipt()
    plan=ActionPlan('PMM-5','B',LifecycleState.DISPATCHED,'run-1','orca-task-1','w-1','c'*64,False,False); calls=[]
    def runner(argv,cwd=None):
        call=tuple(argv); calls.append((call,cwd))
        outputs={
            ('git','rev-parse','--show-toplevel'):str(tmp_path.resolve())+'\n',
            ('git','rev-parse','--path-format=absolute','--git-common-dir'):str(common.resolve())+'\n',
            ('git','rev-parse','HEAD'):'d'*40+'\n',
            ('make','verify'):'RAW STDOUT\n',
        }
        if 'worker-show' in call:return CommandResult(0,json.dumps({'ok':True,'result':{'worker':{'taskId':'orca-task-1','dispatchId':'d-1','workerId':'w-1','worktree':str(tmp_path.resolve())}}}))
        if call[:4]==('opencode','run','--agent','reviewer'):return CommandResult(0,'VERDICT: 0 blockers, 0 warnings\n')
        return CommandResult(0,outputs[call],'RAW STDERR\n' if call==('make','verify') else '')
    store=ReviewReceiptStore(common); result,evidence=ReviewerCoordinator(runner,store).verify_and_review(ReviewInput(plan,receipt,tmp_path,tmp_path))
    assert result.state.value=='MERGE_GATE' and evidence is not None
    artifact=store.read_verify_output(evidence.verify_output_ref)
    assert artifact['argv']==['make','verify'] and artifact['cwd']==str(tmp_path.resolve()) and artifact['head']=='d'*40
    assert artifact['exit_code']==0 and artifact['stdout']=='RAW STDOUT\n' and artifact['stderr']=='RAW STDERR\n'
    assert evidence.verify_output_digest==sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    artifact_path=store.verify_outputs_root/f"{evidence.verify_output_ref}.json"
    artifact_path.write_text(artifact_path.read_text(encoding='utf-8')+' ',encoding='utf-8')
    with pytest.raises(ValueError,match='digest'):store.read_verify_output(evidence.verify_output_ref)


def _ops_runner(repo: Path, worktree: Path, calls: list, *, staged: str = "docs/agent-system/HANDOFF.md\ndocs/agent-system/TASKS.md\ndocs/exec-plans/active/now.md\n"):
    from tools.now_orchestrator.integration import CommandResult
    pr_reads=0
    def runner(argv,cwd=None):
        nonlocal pr_reads
        call=tuple(argv); calls.append((call,cwd))
        if call==('git','rev-parse','--show-toplevel'):return CommandResult(0,str(repo)+'\n')
        if call==('git','rev-parse','--path-format=absolute','--git-common-dir'):return CommandResult(0,str(repo/'.git')+'\n')
        if call==('gh','repo','view','--json','nameWithOwner'):return CommandResult(0,json.dumps({'nameWithOwner':'owner/repo'}))
        if call[:4]==('git','worktree','add','--detach'):worktree.mkdir(); return CommandResult(0,'ok')
        if call==('git','branch','--show-current'):return CommandResult(0,'ops/now-close\n')
        if call==('git','diff','--cached','--name-only'):return CommandResult(0,staged)
        if call==('git','rev-parse','HEAD'):return CommandResult(0,'f'*40+'\n')
        if call[:2]==('git','rev-parse') and ':' in call[2]:return CommandResult(0,'a'*40+'\n')
        if call[:3]==('gh','pr','view'):
            pr_reads+=1
            if pr_reads==1:return CommandResult(1,'')
            return CommandResult(0,json.dumps({'number':43,'state':'OPEN','baseRefName':'main','headRefName':'ops/now-close','headRefOid':'f'*40,'url':'https://example.invalid/pr/43'}))
        if call[:3]==('gh','pr','list'):return CommandResult(0,'[]')
        return CommandResult(0,'ok')
    return runner


def _ops_request(repo: Path, updates, message='docs: close now'):
    from dataclasses import replace
    from tools.now_orchestrator.integration import OpsSyncInput
    from tools.now_orchestrator.integration.ops_sync import _request_digest
    request=OpsSyncInput(repo,'owner/repo','origin/main','ops/now-close','PMM-5','d-1','PMM-5','b'*64,'e'*40,'docs/exec-plans/active/now.md',tuple(updates),message,'Close now','Evidence','approval-ops','')
    return replace(request,approval_digest=_request_digest(request))


def test_ops_sync_isolated_worktree_explicit_stage_push_pr_and_readback(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import FileUpdate, OpsApprovalReadback, OpsRepoSync
    repo=tmp_path/'repo'; repo.mkdir(); (repo/'.git').mkdir(); worktree=tmp_path/'ops-worktree'; calls=[]
    request=_ops_request(repo,(FileUpdate('docs/agent-system/HANDOFF.md','H'),FileUpdate('docs/agent-system/TASKS.md','T'),FileUpdate('docs/exec-plans/active/now.md','P')))
    approval=lambda _:OpsApprovalReadback('approval-ops',request.approval_digest,'Mike','gate:ops')
    result=OpsRepoSync(_ops_runner(repo,worktree,calls),lambda _:worktree,approval).sync(request)
    assert result.pr_number==43 and result.head=='f'*40
    argv=[call for call,_ in calls]
    assert ('git','add','--','docs/agent-system/HANDOFF.md','docs/agent-system/TASKS.md','docs/exec-plans/active/now.md') in argv
    assert any(call[:3]==('git','push','-u') for call in argv)
    assert any(call[:3]==('gh','pr','create') for call in argv)
    assert not any('add -A' in ' '.join(call) or 'merge' in call for call in argv)


def test_ops_sync_retry_reads_wal_and_does_not_duplicate_effects(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import FileUpdate, OpsApprovalReadback, OpsRepoSync
    repo=tmp_path/'repo'; repo.mkdir(); (repo/'.git').mkdir(); worktree=tmp_path/'ops-worktree'; calls=[]
    request=_ops_request(repo,(FileUpdate('docs/agent-system/HANDOFF.md','H'),FileUpdate('docs/agent-system/TASKS.md','T'),FileUpdate('docs/exec-plans/active/now.md','P')))
    approval=lambda _:OpsApprovalReadback('approval-ops',request.approval_digest,'Mike','gate:ops')
    sync=OpsRepoSync(_ops_runner(repo,worktree,calls),lambda _:worktree,approval)
    first=sync.sync(request); second=sync.sync(request)
    assert first==second
    argv=[call for call,_ in calls]
    assert sum(call[:3]==('git','worktree','add') for call in argv)==1
    assert sum(call[:2]==('git','commit') for call in argv)==1
    assert sum(call[:2]==('git','push') for call in argv)==1
    assert sum(call[:3]==('gh','pr','create') for call in argv)==1


def test_ops_sync_refuses_pr_create_when_absence_lookup_is_not_proven(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import FileUpdate, OpsApprovalReadback, OpsRepoSync

    repo = tmp_path / "repo"; repo.mkdir(); (repo / ".git").mkdir(); worktree = tmp_path / "ops-worktree"; calls = []
    base = _ops_runner(repo, worktree, calls)
    def runner(argv, cwd=None):
        if tuple(argv)[:3] == ("gh", "pr", "list"):
            calls.append((tuple(argv), cwd))
            from tools.now_orchestrator.integration import CommandResult
            return CommandResult(1, "rate limited")
        return base(argv, cwd)
    request = _ops_request(repo, (FileUpdate("docs/agent-system/HANDOFF.md", "H"), FileUpdate("docs/agent-system/TASKS.md", "T"), FileUpdate("docs/exec-plans/active/now.md", "P")))
    approval = lambda _: OpsApprovalReadback("approval-ops", request.approval_digest, "Mike", "gate:ops")
    with pytest.raises(ValueError, match="absence"):
        OpsRepoSync(runner, lambda _: worktree, approval).sync(request)
    assert not any(call[:3] == ("gh", "pr", "create") for call, _ in calls)


def test_ops_sync_default_worktree_is_deterministic_across_crash_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.now_orchestrator.integration import FileUpdate, OpsApprovalReadback, OpsRepoSync
    from tools.now_orchestrator.integration.ops_sync import _request_digest
    import tools.now_orchestrator.integration.ops_sync as ops_module

    repo=tmp_path/'repo'; repo.mkdir(); (repo/'.git').mkdir(); calls=[]
    request=_ops_request(repo,(FileUpdate('docs/agent-system/HANDOFF.md','H'),FileUpdate('docs/agent-system/TASKS.md','T'),FileUpdate('docs/exec-plans/active/now.md','P')))
    monkeypatch.setattr(ops_module.tempfile,'gettempdir',lambda:str(tmp_path))
    worktree=tmp_path/f"proxima-now-ops-{_request_digest(request)[:24]}"
    base=_ops_runner(repo,worktree,calls); failed=False
    def runner(argv,cwd=None):
        nonlocal failed
        if tuple(argv)==('git','rev-parse','--show-toplevel') and cwd==worktree:
            from tools.now_orchestrator.integration import CommandResult
            calls.append((tuple(argv),cwd)); return CommandResult(0,str(worktree)+'\n')
        if tuple(argv)==('git','switch','-c','ops/now-close') and not failed:
            failed=True
            from tools.now_orchestrator.integration import CommandResult
            calls.append((tuple(argv),cwd)); return CommandResult(1,'failed')
        return base(argv,cwd)
    approval=lambda _:OpsApprovalReadback('approval-ops',request.approval_digest,'Mike','gate:ops')
    sync=OpsRepoSync(runner,approval_authority=approval)
    with pytest.raises(ValueError): sync.sync(request)
    result=sync.sync(request)
    assert result.worktree==str(worktree.absolute())
    assert sum(call[:3]==('git','worktree','add') for call,_ in calls)==1


@pytest.mark.parametrize('unsafe',['../escape','/absolute','.','docs/*'])
def test_ops_sync_rejects_path_escape_before_effects(tmp_path: Path, unsafe: str) -> None:
    from tools.now_orchestrator.integration import FileUpdate, OpsRepoSync, OpsSyncInput
    repo=tmp_path/'repo'; repo.mkdir(); calls=[]
    request=OpsSyncInput(repo,'owner/repo','origin/main','ops/now-close','PMM-5','d-1','PMM-5','b'*64,'e'*40,'docs/exec-plans/active/now.md',(FileUpdate(unsafe,'x'),),'docs: close','Close','Evidence','approval','digest')
    with pytest.raises(ValueError,match='path'):
        OpsRepoSync(lambda argv,cwd=None:calls.append((tuple(argv),cwd))).sync(request)
    assert calls==[]


def test_ops_sync_staged_path_mismatch_stops_before_commit(tmp_path: Path) -> None:
    from tools.now_orchestrator.integration import FileUpdate, OpsApprovalReadback, OpsRepoSync
    repo=tmp_path/'repo'; repo.mkdir(); (repo/'.git').mkdir(); worktree=tmp_path/'ops-worktree'; calls=[]
    request=_ops_request(repo,(FileUpdate('docs/agent-system/HANDOFF.md','H'),FileUpdate('docs/agent-system/TASKS.md','T'),FileUpdate('docs/exec-plans/active/now.md','P')),'docs: close')
    approval=lambda _:OpsApprovalReadback('approval-ops',request.approval_digest,'Mike','gate:ops')
    with pytest.raises(ValueError,match='staged paths'):
        OpsRepoSync(_ops_runner(repo,worktree,calls,staged='docs/agent-system/HANDOFF.md\nother.txt\n'),lambda _:worktree,approval).sync(request)
    assert not any(call[:2]==('git','commit') for call,_ in calls)
