import json
from pathlib import Path
from types import SimpleNamespace
from tools.loop.continuous_dispatch import Dispatcher,render
from tools.loop.continuous_tick import tick

def config(tmp_path):
    for name in ("evidence","work","receipts","state","admission"): (tmp_path/name).mkdir()
    return {"state_root":str(tmp_path/"state"),"admission_root":str(tmp_path/"admission"),
      "night_batch_script":"/opt/loop/night_batch.py","manifest_defaults":{
      "template_bases":{},"job_timeout_seconds":120,"poll_seconds":10,"disk_floor_bytes":2*1024**3,
      "evidence_root":str(tmp_path/"evidence"),"work_root":str(tmp_path/"work"),
      "glm_config":"/etc/loop/glm.json","glm_script":"/opt/loop/glm_review.py",
      "review_receipts":str(tmp_path/"receipts"),"operator_key_file":"/etc/loop/operator.key",
      "runner_key_file":"/etc/loop/runner.key","acceptance_command":["/opt/loop/continuous-accept"]}}
def item():
    return {"id":"wb-daily-packaging","state":"dispatching","attempts":1,"lease_id":"a"*64,
      "requirement_id":"wb-daily-packaging","base_sha":"b"*40,"policy_fingerprint":"c"*64,
      "proposal_fingerprint":"d"*64,"review_fingerprint":"e"*64,
      "template_name":"continuous-wb-daily-packaging","template_fingerprint":"f"*64,
      "allowed_paths":["tools/wb/daily.py"],"goal":"Package daily WB runtime","acceptance":["passes"],"execution_policy":{"acceptance_profile":"wb-daily-packaging"}}

def test_render_creates_one_task_manifest_and_attempt_receipt(tmp_path):
    manifest,receipt,root=render(item(),config(tmp_path),1000)
    assert manifest["halt_mode"]=="local" and manifest["pause_on_completion"] is False
    assert len(manifest["tasks"])==1 and manifest["tasks"][0]["job_id"]=="wb-daily-packaging-a1"
    assert receipt["allowed_paths"]==["tools/wb/daily.py"] and receipt["policy_fingerprint"]=="c"*64
    assert receipt["acceptance_profile"]=="wb-daily-packaging"
    assert root.name=="attempt-1"

def test_dispatcher_projects_completed_batch_to_exact_pr(tmp_path):
    calls=[];claimed=item()
    def call(method,path,payload=None):
        calls.append((method,path,payload))
        if path=="/v1/queue":return {"current":None}
        if path=="/v1/queue/claim":return claimed
        return {"state":payload["state"]}
    def execute(argv,**kwargs):
        manifest=json.loads(Path(argv[-1]).read_text());state=Path(manifest["state_file"]);state.parent.mkdir(parents=True,exist_ok=True)
        state.write_text(json.dumps({"status":"completed","tasks":[{"phase":"ready_pr","head_sha":"1"*40,"pr_url":"https://github.com/acme/repo/pull/1"}]}))
        return SimpleNamespace(returncode=0)
    result=Dispatcher(config(tmp_path),call,execute,clock=lambda:1000).run_once()
    assert result["state"]=="ready_pr"
    updates=[payload for _method,path,payload in calls if path.endswith("/update")]
    assert [u["state"] for u in updates]==["running","ready_pr"]
    admission=tmp_path/"admission"/"wb-daily-packaging-a1.json"
    assert admission.stat().st_mode&0o777==0o600



def test_tick_replenishes_below_three_with_stable_paperclip_key():
    calls=[]
    status={"policy_fingerprint":"a"*64,"plan_exhausted":False,"items":[{"id":"one","state":"ready"}]}
    def client(method,path,payload=None,headers=None):
        calls.append((method,path,headers))
        if path=="/v1/queue":return status
        return {"run_id":"planner-one"}
    class Idle:
        def run_once(self):return {"status":"idle"}
    result=tick(client,Idle(),now=lambda:1000)
    assert result["queue_depth"]==1 and result["planning"]["run_id"]=="planner-one"
    plan=[call for call in calls if call[1]=="/v1/queue/plan"][0]
    assert plan[2]["Idempotency-Key"].startswith("continuous-plan-")

def test_tick_does_not_wake_planner_when_three_items_are_in_pipeline():
    status={"policy_fingerprint":"a"*64,"plan_exhausted":False,"items":[{"id":str(i),"state":"ready"} for i in range(3)]}
    def client(method,path,payload=None,headers=None):
        assert path=="/v1/queue";return status
    class Idle:
        def run_once(self):return {"status":"idle"}
    assert tick(client,Idle(),now=lambda:1000)["planning"] is None


def test_tick_does_not_replan_exhausted_policy():
    status={"policy_fingerprint":"a"*64,"plan_exhausted":True,"items":[]}
    def client(method,path,payload=None,headers=None):
        assert path=="/v1/queue";return status
    class Idle:
        def run_once(self):return {"status":"idle"}
    result=tick(client,Idle(),now=lambda:1000)
    assert result["planning"] is None and result["queue_depth"]==0


def test_dispatcher_recovers_existing_running_manifest_without_second_claim(tmp_path):
    settings=config(tmp_path);claimed=item();claimed["state"]="running";calls=[];runs=[]
    manifest,admission,root=render(claimed,settings,1000);root.mkdir(parents=True)
    from tools.loop.night_batch import atomic_json
    atomic_json(root/"manifest.json",manifest)
    admission_path=Path(settings["admission_root"])/(claimed["id"]+"-a1.json");atomic_json(admission_path,admission)
    def call(method,path,payload=None):
        calls.append(path)
        if path=="/v1/queue":return {"current":{"id":claimed["id"],"state":"running"}}
        if path=="/v1/queue/"+claimed["id"]:return claimed
        return {"state":payload["state"]}
    def execute(argv,**kwargs):
        runs.append(argv);state=Path(manifest["state_file"])
        state.write_text(json.dumps({"status":"completed","tasks":[{"phase":"ready_pr","head_sha":"2"*40,"pr_url":"https://github.com/acme/repo/pull/2"}]}))
        return SimpleNamespace(returncode=0)
    result=Dispatcher(settings,call,execute,clock=lambda:2000).run_once()
    assert result["state"]=="ready_pr" and len(runs)==1 and "/v1/queue/claim" not in calls


def test_tick_authoritative_pause_blocks_plan_admission_and_dispatch():
    status={"queue_paused":True,"items":[{"id":"one","state":"ready"}]}
    def client(method,path,payload=None,headers=None):
        assert path=="/v1/queue";return status
    class Never:
        def run_once(self):raise AssertionError("paused work invoked")
    result=tick(client,Never(),Never(),now=lambda:1000)
    assert result["status"]=="paused" and result["planning"] is None
    assert result["dispatch"]=={"status":"paused"}
