import json
import sys
import threading
from pathlib import Path
from urllib.parse import unquote
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.bridge import Bridge,BridgeError,GitHubPublisher
from tools.loop.publication import recover_push,write_journal
from tools.loop.runner import DeliveryRunner
from tools.tests.test_loop_bridge import TEMPLATE,setup,run,job
from tools.tests.test_loop_runner import Client

class GitHub:
    def __init__(self,state="absent",pr=False):self.state=state;self.pr=pr;self.calls=[]
    def call(self,method,path,payload=None):
        self.calls.append((method,path))
        assert method=="GET","settlement must not create a PR or alter refs"
        if "/git/ref/" in path:
            if self.state=="absent":raise BridgeError(404,"missing",False)
            return {"object":{"sha":("b" if self.state=="different" else "a")*40}}
        return [{"head":{"sha":"a"*40},"base":{"ref":"main"},"html_url":"https://github.com/fixture/repo/pull/1","state":"open","merged_at":None}] if self.pr else []

class MaterializingGitHub:
    def __init__(self):self.refs={};self.prs=[];self.calls=[]
    def call(self,method,path,payload=None):
        self.calls.append((method,path,payload))
        if method=="GET" and "/git/ref/" in path:
            ref="refs/"+unquote(path.split("/git/ref/",1)[1])
            if ref not in self.refs:raise BridgeError(404,"missing",False)
            return {"ref":ref,"object":{"sha":self.refs[ref]}}
        if method=="POST" and path.endswith("/git/refs"):
            self.refs[payload["ref"]]=payload["sha"]
            return {"ref":payload["ref"],"object":{"sha":payload["sha"]}}
        if method=="PATCH" and "/git/refs/" in path:
            ref="refs/"+unquote(path.split("/git/refs/",1)[1])
            self.refs[ref]=payload["sha"]
            return {"ref":ref,"object":{"sha":payload["sha"]}}
        if method=="GET" and "/pulls?" in path:return list(self.prs)
        if method=="POST" and path.endswith("/pulls"):
            pr={"head":{"sha":self.refs["refs/heads/"+payload["head"]]},"base":{"ref":payload["base"]},"html_url":"https://github.com/fixture/repo/pull/7","state":"open","merged_at":None}
            self.prs.append(pr);return pr
        raise AssertionError((method,path,payload))

class BlockingStagingGitHub(MaterializingGitHub):
    def __init__(self):
        super().__init__()
        self.staging_read = threading.Event()
        self.release_staging = threading.Event()
    def call(self,method,path,payload=None):
        if method=="GET" and "/git/ref/heads/loop-staging/" in path:
            self.staging_read.set()
            if not self.release_staging.wait(5):raise RuntimeError("test staging barrier timed out")
        return super().call(method,path,payload)

class BlockingPullLookupGitHub(MaterializingGitHub):
    def __init__(self):
        super().__init__();self.lookup_started=threading.Event();self.release_lookup=threading.Event()
    def call(self,method,path,payload=None):
        if method=="GET" and "/pulls?" in path:
            self.lookup_started.set()
            if not self.release_lookup.wait(5):raise RuntimeError("test pull lookup barrier timed out")
        return super().call(method,path,payload)

class MovingBranchGitHub(MaterializingGitHub):
    def call(self,method,path,payload=None):
        if method=="POST" and path.endswith("/pulls"):
            self.refs["refs/heads/"+payload["head"]]="b"*40
        return super().call(method,path,payload)

class MovingAfterResponseGitHub(MaterializingGitHub):
    def call(self,method,path,payload=None):
        result=super().call(method,path,payload)
        if method=="POST" and path.endswith("/pulls"):
            self.refs["refs/heads/"+payload["head"]]="b"*40
        return result

def admitted(tmp_path,github=None):
    github=github or GitHub()
    b,h,p,o=setup(tmp_path,GitHubPublisher(github,"fixture/repo"));r=run(b);job(b,r);b.claim_job("job-1")
    sha="a"*40;report={"producer":"harper","sha":sha,"checks":{name:{"sha":sha,"status":"pass","skipped":0} for name in ["verify","build","review"]}}
    permit=b.begin_publication("job-1",report)
    return b,h,p,o,r,permit,github

def test_operator_settles_never_started_push_without_dispatch_or_pr(tmp_path):
    b,_,_,_,_,permit,gh=admitted(tmp_path)
    result=b.settle_publication("job-1","operator checked no push")
    assert result["state"]=="settled" and result["created_pr"] is False and result["deleted_ref"] is False
    assert result["destination"]["branch_state"]=="absent"
    with pytest.raises(BridgeError):b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"late"})
    assert len(gh.calls)==2

@pytest.mark.parametrize("restart",[False,True])
def test_failed_push_has_durable_outcome_and_can_settle_after_process_exit(tmp_path,restart):
    b,h,p,o,r,permit,gh=admitted(tmp_path)
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"failed","process_stopped":True,"returncode":128,"evidence_ref":"fixture failed git log"})
    if restart:b=Bridge(tmp_path/"bridge.sqlite",h,p,"fixture-director",o,GitHubPublisher(gh,"fixture/repo"))
    assert b.job("job-1")["push_outcome"]=="failed"
    assert b.cancel(r)["status"]=="cancelling"
    b.settle_publication("job-1","operator reviewed failed push and destination")
    assert b.cancel(r)["status"]=="cancelled"
    with pytest.raises(BridgeError):b.finish_publication("job-1",permit["permit"])


def test_lost_push_receipt_requires_dead_publisher_and_checks_destination_after_restart(tmp_path):
    b,h,p,o,r,permit,gh=admitted(tmp_path,GitHub("matches",pr=True))
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b=Bridge(tmp_path/"bridge.sqlite",h,p,"fixture-director",o,GitHubPublisher(gh,"fixture/repo"))
    assert b.cancel(r)["status"]=="cancelling"
    with pytest.raises(BridgeError,match="may still run"):b.settle_publication("job-1","unverified")
    journal=tmp_path/"publisher.json"
    write_journal(journal,{"job_id":"job-1","permit":permit["permit"],"publisher_id":"publisher","state":"running","parent_pid":123,"parent_identity":"fixture-parent","child_pid":124,"child_identity":"fixture-child"})
    with pytest.raises(ValueError,match="may still run"):recover_push(Client(b),journal,tmp_path,lambda pid:"fixture-parent" if pid==123 else "fixture-child")
    assert b.job("job-1")["publication_active"]==1
    recover_push(Client(b),journal,tmp_path,lambda pid:None,scope_reader=lambda journal:False)
    result=b.settle_publication("job-1","operator verified stopped process and matching destination")
    assert result["destination"]["branch_state"]=="matches"
    assert result["destination"]["pull_requests"][0]["url"].endswith("/1")
    assert all(method=="GET" for method,_ in gh.calls)
    assert b.cancel(r)["status"]=="cancelled"


def test_settlement_never_accepts_a_different_destination_sha(tmp_path):
    b,_,_,_,_,_,_=admitted(tmp_path,GitHub("different"))
    with pytest.raises(BridgeError,match="differs"):b.settle_publication("job-1","operator check")
    assert b.job("job-1")["publication_active"]==1


def test_real_failed_subprocess_is_journaled_before_recording_outcome(tmp_path):
    b,_,_,_,_,permit,_=admitted(tmp_path)
    runner=DeliveryRunner({"trusted_home":str(tmp_path)},Client(b),identity_reader=lambda pid:"fixture-process",scope_reader=lambda journal:False)
    runner.evidence=tmp_path/"evidence";runner.evidence.mkdir(mode=0o700)
    with pytest.raises(BridgeError):runner.push("job-1",permit,[sys.executable,"-c","import sys;print('push failed');sys.exit(7)"])
    journal=json.loads((runner.evidence/"publisher.json").read_text())
    assert journal["state"]=="finished" and journal["child_pid"] is not None
    assert journal["receipt"]["returncode"]==7
    assert b.job("job-1")["push_process_stopped"]==1


def test_bridge_materializes_final_ref_and_pr_only_from_exact_staging_sha(tmp_path):
    github=MaterializingGitHub()
    b,_,_,_,_,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    result=b.finish_publication("job-1",permit["permit"])
    assert result["state"]=="ready_pr" and result["pr_url"].endswith("/7")
    assert github.refs["refs/heads/feat/loop-job-1"]==permit["sha"]
    assert any(method=="POST" and path.endswith("/git/refs") for method,path,_ in github.calls)
    assert any(method=="POST" and path.endswith("/pulls") for method,path,_ in github.calls)


def test_cancelled_staging_push_never_materializes_final_ref_or_pr(tmp_path):
    github=MaterializingGitHub()
    b,_,_,_,run_id,permit,_=admitted(tmp_path,github)
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    assert b.cancel(run_id)["status"]=="cancelling"
    github.refs[permit["staging_ref"]]=permit["sha"]
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    assert b.finish_publication("job-1",permit["permit"])["state"]=="cancelled"
    assert "refs/heads/feat/loop-job-1" not in github.refs
    assert github.prs==[]
    assert github.calls==[]


def test_cancel_during_staging_lookup_blocks_later_final_ref_and_pr(tmp_path):
    github=BlockingStagingGitHub()
    b,_,_,_,run_id,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    result={}
    def finish():result.update(b.finish_publication("job-1",permit["permit"]))
    thread=threading.Thread(target=finish)
    thread.start()
    assert github.staging_read.wait(2)
    assert b.cancel(run_id)["status"]=="cancelling"
    github.release_staging.set()
    thread.join(5)
    assert not thread.is_alive()
    assert result=={"state":"cancelled","pr_url":None}
    assert "refs/heads/feat/loop-job-1" not in github.refs
    assert github.prs==[]
    assert all(method=="GET" for method,_,_ in github.calls)


def test_cancel_never_claims_to_revoke_an_existing_ready_pr(tmp_path):
    github=MaterializingGitHub()
    b,_,_,_,run_id,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    assert b.finish_publication("job-1",permit["permit"])["state"]=="ready_pr"
    assert b.cancel(run_id)=={"run_id":run_id,"status":"completed","reason":"ready_pr_exists"}
    assert b.job("job-1")["state"]=="ready_pr"


def test_cancel_during_pr_lookup_blocks_later_pr_create(tmp_path):
    github=BlockingPullLookupGitHub()
    b,_,_,_,run_id,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    github.refs["refs/heads/feat/loop-job-1"]=permit["sha"]
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    result={}
    thread=threading.Thread(target=lambda:result.update(b.finish_publication("job-1",permit["permit"])))
    thread.start();assert github.lookup_started.wait(2)
    assert b.cancel(run_id)["status"]=="cancelling"
    github.release_lookup.set();thread.join(5)
    assert result=={"state":"cancelled","pr_url":None}
    assert github.prs==[]


def test_cancel_during_lookup_preserves_an_exact_pr_that_already_exists(tmp_path):
    github=BlockingPullLookupGitHub()
    b,_,_,_,run_id,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    github.refs["refs/heads/feat/loop-job-1"]=permit["sha"]
    github.prs.append({"head":{"sha":permit["sha"]},"base":{"ref":"main"},"html_url":"https://github.com/fixture/repo/pull/7","state":"open","merged_at":None})
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    result={}
    thread=threading.Thread(target=lambda:result.update(b.finish_publication("job-1",permit["permit"])))
    thread.start();assert github.lookup_started.wait(2)
    assert b.cancel(run_id)["status"]=="cancelling"
    github.release_lookup.set();thread.join(5)
    assert result["state"]=="ready_pr"
    assert b.job("job-1")["state"]=="ready_pr"
    assert b.cancel(run_id)=={"run_id":run_id,"status":"completed","reason":"ready_pr_exists"}


def test_settlement_serializes_against_finisher_and_late_push(tmp_path):
    github=MaterializingGitHub()
    b,_,_,_,_,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    github.refs["refs/heads/feat/loop-job-1"]=permit["sha"]
    result=b.settle_publication("job-1","operator confirmed no publisher ran")
    assert result["state"]=="settled"
    with pytest.raises(BridgeError,match="permit closed"):b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"late"})
    with pytest.raises(BridgeError,match="permit closed"):b.finish_publication("job-1",permit["permit"])
    assert github.prs==[]


def test_created_pr_must_report_the_exact_verified_head(tmp_path):
    github=MovingBranchGitHub()
    b,_,_,_,_,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    with pytest.raises(BridgeError,match="receipt uncertain"):b.finish_publication("job-1",permit["permit"])
    assert b.job("job-1")["state"]=="unknown"
    assert github.prs[0]["head"]["sha"]=="b"*40


def test_created_pr_is_read_back_before_ready_state_is_recorded(tmp_path):
    github=MovingAfterResponseGitHub()
    b,_,_,_,_,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    with pytest.raises(BridgeError,match="receipt uncertain"):b.finish_publication("job-1",permit["permit"])
    assert b.job("job-1")["state"]=="unknown"


def test_cancel_after_ready_pr_stops_and_revokes_sibling_work(tmp_path):
    github=MaterializingGitHub()
    b,_,_,_,run_id,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    b.finish_publication("job-1",permit["permit"])
    b.propose_job({"job_id":"job-2","run_id":run_id,"generation":1,"template":"fixture"},{"fixture":TEMPLATE})
    b.claim_job("job-2")
    report={"producer":"harper","sha":"c"*40,"checks":{name:{"sha":"c"*40,"status":"pass","skipped":0} for name in ["verify","build","review"]}}
    second=b.begin_publication("job-2",report)
    cancelled=b.cancel(run_id)
    assert cancelled["status"] in {"cancelling","completed"}
    assert cancelled["reason"]=="ready_pr_exists"
    with pytest.raises(BridgeError):b.start_push("job-2",{"permit":second["permit"],"publisher_id":"publisher-2"})


def test_wrong_staging_sha_never_changes_final_ref_or_creates_pr(tmp_path):
    github=MaterializingGitHub()
    b,_,_,_,_,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]="b"*40
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    with pytest.raises(BridgeError,match="staging ref differs"):b.finish_publication("job-1",permit["permit"])
    assert "refs/heads/feat/loop-job-1" not in github.refs
    assert not any(method in {"POST","PATCH"} for method,_,_ in github.calls)
    assert b.job("job-1")["state"]=="publishing"


def test_bridge_updates_existing_final_ref_without_force_after_staging_check(tmp_path):
    github=MaterializingGitHub()
    b,_,_,_,_,permit,_=admitted(tmp_path,github)
    github.refs[permit["staging_ref"]]=permit["sha"]
    github.refs["refs/heads/feat/loop-job-1"]="b"*40
    b.start_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher"})
    b.record_push("job-1",{"permit":permit["permit"],"publisher_id":"publisher","outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":"fixture staging push"})
    assert b.finish_publication("job-1",permit["permit"])["state"]=="ready_pr"
    patches=[payload for method,path,payload in github.calls if method=="PATCH" and "/git/refs/" in path]
    assert patches==[{"sha":permit["sha"],"force":False}]
