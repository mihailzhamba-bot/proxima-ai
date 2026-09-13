from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.bridge import Bridge, BridgeError
from tools.loop.runner import DeliveryRunner

class Remote:
    def call(self,method,path,payload=None,headers=None):return {"id":"remote-run","status":"running"}
class Client:
    def __init__(self,b):self.b=b
    def call(self,method,path,payload=None,headers=None):
        job=path.split("/")[4]
        if path.endswith("/claim"):return self.b.claim_job(job)
        if path.endswith("/begin-publication"):return self.b.begin_publication(job,payload)
        if path.endswith("/finish-publication"):return self.b.finish_publication(job,payload["permit"])
        return self.b.fence(job)

def setup(tmp_path,fail_checks=False,changed="services/webapp/src/lib/rub.ts",cancel_before_publish=False):
    published=[];remote=Remote();b=Bridge(tmp_path/"bridge.sqlite",remote,remote,"director",publisher=lambda job,sha:published.append(sha) or "https://github.com/fixture/repo/pull/1")
    r=b.create("hermes","pc-run",{"input":"task","instructions":"scope","session_id":"session"})["run_id"]
    b.propose_job({"job_id":"job-1","run_id":r,"generation":1,"template":"fixture"},{"fixture":{}})
    sha="a"*40;base="b"*40
    config={"trusted_home":str(tmp_path),"worker_identity_file":"/fixture/key","worker_host":"worker","worker_python":"python3","worker_dispatcher":"/opt/loop/worker_dispatch.py","worker_config":"/etc/loop/templates.json","worker_source":"/srv/loop/source","work_root":str(tmp_path),"source_repo":"/fixture/source","fixture_root":"/fixture/data","evidence_root":str(tmp_path/"evidence"),"verification_image":"fixture/verify@sha256:"+"1"*64,"reviewer_command":["/opt/reviewer"],"publish_remote":"git@fixture:repo","templates":{"fixture":{"base_sha":base,"allowed_paths":["services/webapp/src/lib/"]}}}
    calls=[]
    def execute(argv,cwd=None):
        calls.append(argv)
        if argv[0]=="ssh":return json.dumps({"ok":True,"head_sha":sha,"base_sha":base,"conversation_id":b.job("job-1")["external_id"],"branch":"feat/loop-job-1","worker_says":"PASS"})
        if "clone" in argv:
            checkout=Path(argv[-1]);(checkout/"services/webapp").mkdir(parents=True);(checkout/"services/webapp/next-env.d.ts").write_text("fixture declaration")
        if "rev-parse" in argv:return sha+"\n"
        if "--name-only" in argv:return changed+"\n"
        if argv[0]=="docker":
            assert "--network" in argv and argv[argv.index("--network")+1]=="none"
            assert not any("docker.sock" in value for value in argv)
            if fail_checks:raise BridgeError(409,"independent verifier failed")
            return json.dumps({"status":"pass","checks":{argv[-1]:{"sha":sha,"status":"pass","skipped":0}},"logs":{argv[-1]:"fixture log"}})
        if argv[0]=="/opt/reviewer":
            if cancel_before_publish:
                with b.tx() as db:db.execute("UPDATE operations SET generation=2,state='cancelled' WHERE id=?",(r,))
            return json.dumps({"sha":sha,"status":"pass","skipped":0})
        return ""
    return DeliveryRunner(config,Client(b),execute),b,calls,published

def test_same_delivery_path_reaches_ready_pr_after_real_runner_receipts(tmp_path):
    runner,b,calls,published=setup(tmp_path)
    assert runner.run("job-1")["state"]=="ready_pr"
    assert len(published)==1
    assert any(c[0]=="docker" for c in calls)
    assert any(c[0]=="/opt/reviewer" for c in calls)
    assert any("push" in c for c in calls)
    with pytest.raises(BridgeError):runner.run("job-1")

def test_worker_pass_never_overrides_failed_independent_checks(tmp_path):
    runner,b,calls,published=setup(tmp_path,fail_checks=True)
    with pytest.raises(BridgeError):runner.run("job-1")
    assert published==[];assert not any("push" in c for c in calls)

def test_cancelled_old_attempt_cannot_publish_late_success(tmp_path):
    runner,b,calls,published=setup(tmp_path,cancel_before_publish=True)
    with pytest.raises(BridgeError):runner.run("job-1")
    assert published==[];assert not any("push" in c for c in calls)

def test_candidate_cannot_rewrite_its_own_verifier(tmp_path):
    runner,b,calls,published=setup(tmp_path,changed="Makefile")
    with pytest.raises(BridgeError):runner.run("job-1")
    assert published==[];assert not any(c[0]=="docker" for c in calls)
