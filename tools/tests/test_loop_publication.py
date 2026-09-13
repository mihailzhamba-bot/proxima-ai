import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.bridge import Bridge,BridgeError,GitHubPublisher
from tools.loop.publication import recover_push,write_journal
from tools.loop.runner import DeliveryRunner
from tools.tests.test_loop_bridge import setup,run,job
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
