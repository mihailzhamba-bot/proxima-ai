"""Failure tests hit the same persistent intent, cancellation and publication paths as HTTP."""
from __future__ import annotations
import json
import threading
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop.bridge import Bridge, BridgeError, JsonHTTP, server, template_fingerprint

PROFILE_ID="11111111-1111-4111-8111-111111111111"
TEMPLATE={"profile":"fedor","profile_id":PROFILE_ID,"profile_revision":3}

class Remote:
    def __init__(self): self.calls=[]; self.status="running"; self.fail_create=False; self.fail_stop=False
    def call(self,method,path,payload=None,headers=None):
        self.calls.append((method,path,payload,headers))
        if method=="POST" and path.endswith("/stop"):
            if self.fail_stop: raise BridgeError(502,"offline")
            self.status="stopped";return {}
        if path.endswith("/pause"):return {"success":True}
        if "/api/conversations/" in path:return {"execution_status":"paused"}
        if method=="POST":
            if self.fail_create: raise BridgeError(502,"response lost")
            return {"run_id":"remote-1","status":"running"}
        if "/events?" in path:return [{"seq":1,"type":"event"}]
        return {"run_id":"remote-1","status":self.status}

def publish_verified(b,job_id,report):
    old=b.job(job_id)
    if old["state"]=="ready_pr":return {"state":"ready_pr","pr_url":old["pr_url"]}
    permit=b.begin_publication(job_id,report)["permit"]
    b.start_push(job_id,{"permit":permit,"publisher_id":"fixture-publisher"})
    b.record_push(job_id,{"permit":permit,"publisher_id":"fixture-publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture-push"})
    return b.finish_publication(job_id,permit)

def setup(tmp_path,publisher=None):
    h,p,o=Remote(),Remote(),Remote()
    b=Bridge(tmp_path/"bridge.sqlite",h,p,"fixture-director",o,publisher)
    return b,h,p,o

def run(b,key="run-1"):
    return b.create("hermes",key,{"input":"fixture task","instructions":"fixture instructions","session_id":"fixture-session"})["run_id"]

def job(b,r):return b.propose_job({"job_id":"job-1","run_id":r,"generation":1,"template":"fixture"},{"fixture":TEMPLATE})


def test_template_requires_stable_profile_identity_and_revision(tmp_path):
    b,_,_,_=setup(tmp_path);r=run(b)
    with pytest.raises(BridgeError,match="stable Agent Profile identity"):
        b.propose_job({"job_id":"job-1","run_id":r,"generation":1,"template":"fixture"},{"fixture":{"profile":"fedor"}})
    changed={**TEMPLATE,"profile_revision":TEMPLATE["profile_revision"]+1}
    assert template_fingerprint("fixture",TEMPLATE)!=template_fingerprint("fixture",changed)

def test_repeated_create_is_durable_and_payload_conflict_rejected(tmp_path):
    b,h,p,o=setup(tmp_path);r=run(b)
    assert run(b)==r
    b=Bridge(tmp_path/"bridge.sqlite",h,p,"fixture-director",o)
    assert run(b)==r
    assert len([c for c in h.calls if c[0]=="POST"])==1
    with pytest.raises(BridgeError):b.create("hermes","run-1",{"input":"changed"})

def test_lost_reply_never_redispatches_even_after_24h_restart(tmp_path):
    b,h,p,o=setup(tmp_path);h.fail_create=True
    with pytest.raises(BridgeError):run(b)
    b=Bridge(tmp_path/"bridge.sqlite",h,p,"fixture-director",o)
    with pytest.raises(BridgeError):run(b)
    assert len(h.calls)==1
    with b.tx() as db: assert db.execute("SELECT state FROM operations").fetchone()[0]=="unknown"

def test_restart_during_dispatch_quarantines_before_retry(tmp_path):
    b,h,p,o=setup(tmp_path)
    b.intent("paperclip","wake-1",{"reason":"fixture"})
    b=Bridge(tmp_path/"bridge.sqlite",h,p,"fixture-director",o)
    with pytest.raises(BridgeError): b.create("paperclip","wake-1",{"reason":"fixture"})
    assert p.calls==[]

def test_cancel_fences_late_worker_and_explicitly_stops_remote(tmp_path):
    b,h,p,o=setup(tmp_path);r=run(b);job(b,r);b.claim_job("job-1")
    assert b.cancel(r)["status"]=="cancelled"
    with pytest.raises(BridgeError):b.fence("job-1")
    assert any(c[1].endswith("/stop") for c in h.calls)
    assert any(c[1].endswith("/pause") for c in o.calls)
    assert b.job("job-1")["state"]=="cancelled"

def test_stop_network_failure_keeps_cancelling_not_claimed_stopped(tmp_path):
    b,h,_,_=setup(tmp_path);r=run(b);h.fail_stop=True
    assert b.cancel(r)["status"]=="cancelling"
    h.fail_stop=False
    assert b.cancel(r)["status"]=="cancelled"

def test_interrupted_hermes_invalidates_publication_on_reconcile(tmp_path):
    b,h,_,_=setup(tmp_path);r=run(b);job(b,r);h.status="interrupted"
    with pytest.raises(BridgeError):b.fence("job-1")

def test_pause_and_one_director_lease(tmp_path):
    b,_,_,_=setup(tmp_path);run(b)
    with pytest.raises(BridgeError):run(b,"run-2")
    b.pause(True)
    with pytest.raises(BridgeError):b.create("paperclip","wake-1",{})

def test_paperclip_wakeup_is_not_assumed_globally_idempotent_and_cursor_persists(tmp_path):
    b,_,p,_=setup(tmp_path)
    r=b.create("paperclip","wake-1",{})["run_id"]
    assert b.paperclip_events(r)=={"cursor":1,"count":1}
    assert b.paperclip_events(r)=={"cursor":1,"count":1}
    with b.tx() as db: assert db.execute("SELECT count(*) FROM events").fetchone()[0]==1
    assert p.calls[0][1]=="/api/agents/fixture-director/wakeup"
    assert p.calls[0][2]["forceFreshSession"] is False

def test_only_exact_independent_receipts_can_reach_pr_and_no_auto_merge(tmp_path):
    published=[]
    b,_,_,_=setup(tmp_path,lambda job,sha:published.append((job,sha)) or "https://github.com/fixture/repo/pull/1")
    r=run(b);job(b,r);b.claim_job("job-1")
    with pytest.raises(BridgeError):publish_verified(b,"job-1",{"worker_says":"PASS"})
    assert published==[]
    sha="a"*40
    report={"producer":"harper","sha":sha,"checks":{name:{"sha":sha,"status":"pass","skipped":0} for name in ["verify","build","review"]}}
    assert publish_verified(b,"job-1",report)["state"]=="ready_pr"
    assert len(published)==1
    assert publish_verified(b,"job-1",report)["state"]=="ready_pr"
    assert len(published)==1

def test_http_identity_separates_gateway_director_and_runner(tmp_path):
    b,_,_,_=setup(tmp_path)
    credentials={}
    for role in ["gateway","operator","director","runner"]:
        path=tmp_path/(role+".key");path.write_text("fixture-"+role);path.chmod(0o600);credentials[role]=str(path)
    http=server(b,{"port":0,"credential_files":credentials,"templates":{"fixture":TEMPLATE}})
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    url=f"http://127.0.0.1:{http.server_port}"
    try:
        gateway=JsonHTTP(url,"fixture-gateway")
        result=gateway.call("POST","/hermes/v1/runs",{"input":"fixture","instructions":"fixture","session_id":"fixture-session"},{"Idempotency-Key":"paperclip-run","X-Hermes-Session-Key":"fixture-session"})
        assert result["status"]=="running"
        with pytest.raises(BridgeError):gateway.call("POST","/v1/wake",{})
        director=JsonHTTP(url,"fixture-director")
        director.call("POST","/v1/jobs",{"job_id":"job-1","run_id":result["run_id"],"generation":1,"template":"fixture"})
        with pytest.raises(BridgeError):director.call("POST","/v1/runner/jobs/job-1/publish",{"worker_says":"PASS"})
    finally:http.shutdown();http.server_close();thread.join()


def test_cancelled_paperclip_parent_rejects_delayed_hermes_dispatch(tmp_path):
    b,h,p,o=setup(tmp_path)
    parent=b.create("paperclip","wake-1",{})["run_id"]
    b.cancel(parent)
    with pytest.raises(BridgeError):run(b,"remote-1")
    assert h.calls==[]

@pytest.mark.parametrize("upstream,normalized",[("succeeded","completed"),("scheduled_retry","interrupted"),("timed_out","failed")])
def test_paperclip_terminal_mapping(tmp_path,upstream,normalized):
    b,_,p,_=setup(tmp_path)
    parent=b.create("paperclip","wake-1",{})["run_id"]
    p.status=upstream
    assert b.reconcile(parent)["status"]==normalized


def test_restart_recovers_existing_pr_without_repeating_create(tmp_path):
    class Publisher:
        def __init__(self):self.lookups=0
        def __call__(self,job,sha):raise OSError("lost receipt")
        def lookup(self,job,sha):
            self.lookups+=1
            return None if self.lookups==1 else "https://github.com/fixture/repo/pull/9"
    publisher=Publisher();b,h,p,o=setup(tmp_path,publisher);r=run(b);job(b,r);b.claim_job("job-1")
    sha="a"*40;report={"producer":"harper","sha":sha,"checks":{name:{"sha":sha,"status":"pass","skipped":0} for name in ["verify","build","review"]}}
    with pytest.raises(BridgeError):publish_verified(b,"job-1",report)
    b=Bridge(tmp_path/"bridge.sqlite",h,p,"fixture-director",o,publisher)
    assert b.recover_pr("job-1")["state"]=="ready_pr"

def test_unrouteable_job_ids_are_rejected(tmp_path):
    b,_,_,_=setup(tmp_path);r=run(b)
    with pytest.raises(BridgeError):b.propose_job({"job_id":"Colon:Job_1","run_id":r,"generation":1,"template":"fixture"},{"fixture":TEMPLATE})


def test_cancel_during_admitted_push_is_not_confirmed_and_late_finish_cannot_create_pr(tmp_path):
    published=[]
    b,h,p,o=setup(tmp_path,lambda job,sha:published.append(sha) or "https://github.com/fixture/repo/pull/1")
    r=run(b);job(b,r);b.claim_job("job-1");sha="a"*40
    report={"producer":"harper","sha":sha,"checks":{name:{"sha":sha,"status":"pass","skipped":0} for name in ["verify","build","review"]}}
    permit=b.begin_publication("job-1",report)["permit"]
    b.start_push("job-1",{"permit":permit,"publisher_id":"fixture-publisher"})
    # Exact race: cancellation is requested after final admission, before push returns.
    assert b.cancel(r)["status"]=="cancelling"
    assert b.get(r)["stop_confirmed"]==0
    b.record_push("job-1",{"permit":permit,"publisher_id":"fixture-publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture-push"})
    assert b.finish_publication("job-1",permit)["state"]=="cancelled"
    assert published==[]
    assert b.cancel(r)["status"]=="cancelled"

def test_direct_upstream_parent_cancel_is_seen_before_publish(tmp_path):
    b,h,p,o=setup(tmp_path)
    parent=b.create("paperclip","wake-1",{})["run_id"]
    r=run(b,"remote-1");job(b,r);b.claim_job("job-1")
    p.status="cancelled"
    with pytest.raises(BridgeError,match="parent"):b.fence("job-1")

def test_interrupted_never_dispatched_job_is_quarantined_without_poisoning_queue(tmp_path):
    b,h,p,o=setup(tmp_path);r=run(b);job(b,r);h.status="interrupted"
    assert b.next_job()=={"job_id":None}
    assert b.job("job-1")["state"]=="quarantined"
    assert b.job("job-1")["external_id"] is None

def test_operator_recovers_existing_cid_and_bundle_without_second_dispatch(tmp_path):
    b,h,p,o=setup(tmp_path);r=run(b);job(b,r);claimed=b.claim_job("job-1");b.fail_job("job-1")
    receipt={"ok":True,"conversation_id":claimed["external_id"],"branch":"feat/loop-job-1","head_sha":"a"*40,"base_sha":"b"*40}
    b.recover_job("job-1",receipt)
    recovered=b.claim_job("job-1")
    assert recovered["recover_only"] is True
    assert recovered["external_id"]==claimed["external_id"]
    assert json.loads(recovered["recovery_receipt"])==receipt


def test_global_pause_keeps_same_queued_job_available_after_resume(tmp_path):
    b,h,p,o=setup(tmp_path);r=run(b);job(b,r)
    b.pause(True);assert b.next_job()=={"job_id":None};assert b.job("job-1")["state"]=="queued"
    b.pause(False);assert b.next_job()=={"job_id":"job-1"}
    p.status="queued";assert b.next_job()=={"job_id":None};assert b.job("job-1")["state"]=="queued"
    p.status="running";assert b.next_job()=={"job_id":"job-1"}


def test_publication_pause_preserves_permit_for_finish_after_resume(tmp_path):
    published=[]
    b,_,_,_=setup(tmp_path,lambda job,sha:published.append(sha) or "https://github.com/fixture/repo/pull/1")
    r=run(b);job(b,r);b.claim_job("job-1");sha="a"*40
    report={"producer":"harper","sha":sha,"checks":{name:{"sha":sha,"status":"pass","skipped":0} for name in ["verify","build","review"]}}
    permit=b.begin_publication("job-1",report)["permit"]
    b.start_push("job-1",{"permit":permit,"publisher_id":"fixture-publisher"})
    b.record_push("job-1",{"permit":permit,"publisher_id":"fixture-publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture-push"})
    b.pause(True)
    with pytest.raises(BridgeError) as error:b.finish_publication("job-1",permit)
    assert error.value.revoked is False
    assert b.job("job-1")["publication_active"]==1 and b.job("job-1")["state"]=="publishing"
    assert published==[]
    b.pause(False)
    assert b.finish_publication("job-1",permit)["state"]=="ready_pr"
    assert len(published)==1


def test_job_parent_binding_is_persisted_bridge_parent_not_remote_or_other_job(tmp_path):
    b, _, _, _ = setup(tmp_path)
    parents = []
    for index in (1, 2):
        parent = b.create("paperclip", "wake-" + str(index), {})["run_id"]
        external = "paperclip-external-" + str(index)
        with b.tx() as db:
            db.execute("UPDATE operations SET external_id=? WHERE id=?", (external, parent))
        director = run(b, external)
        job_id = "job-" + str(index)
        b.propose_job({"job_id": job_id, "run_id": director, "generation": 1, "template": "fixture"}, {"fixture": TEMPLATE})
        with b.tx() as db:
            db.execute("UPDATE operations SET state='completed' WHERE id=?", (director,))
        parents.append(parent)
    assert b.job("job-1")["parent_run_id"] == parents[0]
    assert b.job("job-2")["parent_run_id"] == parents[1]
    assert b.job("job-1")["parent_run_id"] != b.job("job-2")["parent_run_id"]


def test_standalone_job_without_persisted_parent_reports_null_binding(tmp_path):
    b, _, _, _ = setup(tmp_path)
    director = run(b, "unbound-remote-parent")
    job(b, director)
    assert b.job("job-1")["parent_run_id"] is None

def test_childless_paperclip_stop_confirms_from_upstream_and_is_idempotent(tmp_path):
    b,_,p,_=setup(tmp_path)
    parent=b.create("paperclip","wake-1",{})["run_id"]
    p.status="cancelled"
    assert b.cancel(parent)["status"]=="cancelled"
    assert b.get(parent)["stop_confirmed"]==1
    calls=len(p.calls)
    assert b.cancel(parent)["status"]=="cancelled"
    assert b.get(parent)["state"]=="cancelled"
    assert len(p.calls)==calls
    assert b.reconcile(parent)["status"]=="cancelled"
    assert len(p.calls)==calls


def test_internal_bridge_error_is_500_uncertain_not_400(tmp_path):
    b,_,_,_=setup(tmp_path)
    credentials={}
    for role in ["gateway","operator","director","runner"]:
        path=tmp_path/(role+".key");path.write_text("fixture-"+role);path.chmod(0o600);credentials[role]=str(path)
    http=server(b,{"port":0,"credential_files":credentials})
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    url=f"http://127.0.0.1:{http.server_port}"
    try:
        director=JsonHTTP(url,"fixture-director",trusted_bridge=True)
        with pytest.raises(BridgeError) as error:
            director.call("GET","/v1/context?offset=abc")
        assert error.value.status==500 and error.value.uncertain is True
    finally:
        http.shutdown();http.server_close();thread.join()
