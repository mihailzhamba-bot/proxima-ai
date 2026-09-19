import json
from pathlib import Path
from types import SimpleNamespace
from tools.loop.continuous_dispatch import Dispatcher,render
from tools.loop.continuous_tick import tick,planning_key

def config(tmp_path):
    for name in ("evidence","work","receipts","state","admission"): (tmp_path/name).mkdir()
    return {"state_root":str(tmp_path/"state"),"admission_root":str(tmp_path/"admission"),
      "start_disk_floor_bytes":3*1024**3,"night_batch_script":"/opt/loop/night_batch.py","manifest_defaults":{
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
    result=Dispatcher(config(tmp_path),call,execute,clock=lambda:1000,disk_free=lambda _path:4*1024**3).run_once()
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
    result=Dispatcher(settings,call,execute,clock=lambda:2000,disk_free=lambda _path:4*1024**3).run_once()
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


def test_unknown_monitoring_resumes_same_manifest_and_adopts_run_identity(tmp_path):
    settings=config(tmp_path);claimed=item();claimed.update(state="unknown",external_run_id=None,external_job_id=None)
    manifest,admission,root=render({**claimed,"state":"running"},settings,1000);root.mkdir(parents=True)
    from tools.loop.night_batch import atomic_json
    atomic_json(root/"manifest.json",manifest);atomic_json(Path(settings["admission_root"])/(claimed["id"]+"-a1.json"),admission)
    atomic_json(Path(manifest["state_file"]),{"status":"running","tasks":[{"phase":"monitoring","run_id":"run-1"}]})
    calls=[]
    def call(method,path,payload=None):
        calls.append((path,payload))
        if path=="/v1/queue":return {"current":{"id":claimed["id"],"state":"unknown"}}
        if path=="/v1/queue/"+claimed["id"]:return claimed
        if path.endswith("/update") and payload["state"]=="running":
            claimed.update(state="running",external_run_id="run-1",external_job_id=payload["job_id"]);return claimed
        if path.endswith("/update"):return {"state":payload["state"]}
        raise AssertionError(path)
    def execute(argv,**kwargs):
        atomic_json(Path(manifest["state_file"]),{"status":"completed","tasks":[{"phase":"ready_pr","run_id":"run-1","head_sha":"3"*40,"pr_url":"https://github.com/acme/repo/pull/3"}]})
        return SimpleNamespace(returncode=0)
    assert Dispatcher(settings,call,execute,clock=lambda:2000,disk_free=lambda _path:4*1024**3).run_once()["state"]=="ready_pr"
    assert "/v1/queue/claim" not in [path for path,_ in calls]

def test_blocked_unavailable_run_remains_quarantined(tmp_path):
    settings=config(tmp_path);claimed=item();claimed.update(state="blocked",external_run_id="run-1",external_job_id="job-1")
    _manifest,_admission,root=render({**claimed,"state":"running"},settings,1000);root.mkdir(parents=True)
    from tools.loop.night_batch import atomic_json
    atomic_json(root/"batch-state.json",{"status":"blocked","reason":"job_timeout","tasks":[{"phase":"monitoring","run_id":"run-1"}]})
    def call(method,path,payload=None):
        if path=="/v1/queue":return {"current":{"id":claimed["id"],"state":"blocked"}}
        if path=="/v1/queue/"+claimed["id"]:return claimed
        if path=="/v1/runs/run-1":raise RuntimeError("offline")
        raise AssertionError(path)
    result=Dispatcher(settings,call,clock=lambda:2000,disk_free=lambda _path:4*1024**3).run_once()
    assert result["status"]=="unknown" and result["reason"]=="stop_reconcile_failed"

def test_nonretryable_stopped_block_is_settled_once(tmp_path):
    settings=config(tmp_path);claimed=item();claimed.update(state="blocked",external_run_id="run-1",external_job_id="job-1")
    _manifest,_admission,root=render({**claimed,"state":"running"},settings,1000);root.mkdir(parents=True)
    from tools.loop.night_batch import atomic_json
    atomic_json(root/"batch-state.json",{"status":"blocked","reason":"run_terminal_or_unknown","tasks":[{"phase":"monitoring","run_id":"run-1"}]})
    settled=[]
    def call(method,path,payload=None):
        if path=="/v1/queue":return {"current":{"id":claimed["id"],"state":"blocked"}}
        if path=="/v1/queue/"+claimed["id"]:return claimed
        if path=="/v1/runs/run-1":return {"status":"cancelled"}
        if path.endswith("/settle"):settled.append(payload);return {"state":"blocked","lease_id":None}
        raise AssertionError(path)
    result=Dispatcher(settings,call,clock=lambda:2000,disk_free=lambda _path:4*1024**3).run_once()
    assert result["lease_id"] is None and len(settled)==1 and settled[0]["reason"]=="nonretryable"

def test_tick_reconciles_saved_planning_before_new_generation():
    status={"policy_fingerprint":"a"*64,"planning_snapshot":"b"*64,"planning_generation":0,
      "plan_exhausted":False,"items":[],"planning":{"id":"plan-local","state":"unknown"}}
    calls=[]
    def client(method,path,payload=None,headers=None):
        calls.append((method,path))
        if path=="/v1/queue":return status
        if path=="/v1/runs/plan-local":return {"status":"unknown"}
        raise AssertionError(path)
    class Idle:
        def run_once(self):return {"status":"idle"}
    result=tick(client,Idle(),now=lambda:1000)
    assert result["planning"] is None
    assert not any(path=="/v1/queue/plan" for _method,path in calls)

def test_planning_generation_changes_key_only_after_terminal_attempt():
    base={"policy_fingerprint":"a"*64,"planning_snapshot":"b"*64,"items":[]}
    first=planning_key({**base,"planning_generation":0},1000)
    assert planning_key({**base,"planning_generation":0},999999)==first
    assert planning_key({**base,"planning_generation":1},1000)!=first


def test_tick_refreshes_report_before_dispatch():
 status={"policy_fingerprint":"a"*64,"plan_exhausted":True,"items":[],"current":None}
 order=[]
 def client(method,path,payload=None,headers=None):
  assert path=="/v1/queue";return status
 class Stage:
  def run_once(self):return {"status":"idle"}
 class Report:
  def run(self,value,now):order.append("report");return {"status":"not_due"}
 class Dispatch:
  def run_once(self):order.append("dispatch");return {"status":"idle"}
 tick(client,Dispatch(),Stage(),Report(),now=lambda:1000)
 assert order==["report","dispatch"]


def test_tick_does_not_replace_cancelling_cross_snapshot_planner():
    status={"policy_fingerprint":"a"*64,"planning_snapshot":"new","planning_generation":0,
      "plan_exhausted":False,"items":[],"planning":{"id":"old-plan","state":"cancelling"}}
    calls=[]
    def client(method,path,payload=None,headers=None):
        calls.append(path)
        if path=="/v1/queue":return status
        if path=="/v1/runs/old-plan":return {"status":"cancelling"}
        raise AssertionError(path)
    class Idle:
        def run_once(self):return {"status":"idle"}
    assert tick(client,Idle(),now=lambda:1000)["planning"] is None
    assert "/v1/queue/plan" not in calls


def test_tick_runs_merge_observer_before_planning_and_admission():
    status={"policy_fingerprint":"a"*64,"plan_exhausted":True,"items":[],"current":None}
    order=[]
    def client(method,path,payload=None,headers=None):
        assert path=="/v1/queue";return status
    class Observer:
        def run_once(self,value):order.append("observer");return {"status":"idle","merged":0}
    class Admission:
        def run_once(self):order.append("admission");return {"status":"idle"}
    class Report:
        def run(self,value,now):order.append("report");return {"status":"not_due"}
    class Dispatch:
        def run_once(self):order.append("dispatch");return {"status":"idle"}
    result=tick(client,Dispatch(),Admission(),Report(),Observer(),now=lambda:1000)
    assert order==["observer","admission","report","dispatch"]
    assert result["merges"]["status"]=="idle"

def test_tick_merge_observer_failure_does_not_block_ready_dispatch():
    status={"policy_fingerprint":"a"*64,"plan_exhausted":True,"items":[{"id":"ready","state":"ready"}],"current":None}
    def client(method,path,payload=None,headers=None):return status
    class Observer:
        def run_once(self,value):raise TimeoutError("secret")
    class Idle:
        def run_once(self):return {"status":"idle"}
    class Dispatch:
        def run_once(self):return {"status":"dispatched"}
    result=tick(client,Dispatch(),Idle(),observer=Observer(),now=lambda:1000)
    assert result["merges"]=={"status":"unknown","blocker":"merge_observer_failed"}
    assert result["dispatch"]=={"status":"dispatched"}


def test_tick_base_refresh_completes_before_admission():
 status={"policy_fingerprint":"a"*64,"plan_exhausted":True,"items":[],"current":None,"maintenance":None}
 order=[]
 def client(method,path,payload=None,headers=None):
  assert path=="/v1/queue";return status
 class Observer:
  def run_once(self,value):order.append("merge");return {"status":"idle","merged":0}
 class Refresher:
  def run_once(self,value):order.append("refresh");return {"status":"complete","rebased":[]}
 class Admission:
  def run_once(self):order.append("admission");return {"status":"idle"}
 class Dispatch:
  def run_once(self):order.append("dispatch");return {"status":"idle"}
 tick(client,Dispatch(),Admission(),observer=Observer(),refresher=Refresher(),now=lambda:1000)
 assert order==["merge","refresh","admission","dispatch"]

def test_tick_maintenance_blocker_prevents_planning_admission_and_dispatch():
 status={"policy_fingerprint":"a"*64,"plan_exhausted":False,"items":[{"id":"one","state":"ready"}],"current":None,
   "maintenance":{"state":"fetching"}}
 calls=[]
 def client(method,path,payload=None,headers=None):calls.append(path);return status
 class Refresher:
  def run_once(self,value):return {"status":"blocked","blocker":"non_fast_forward"}
 class Never:
  def run_once(self):raise AssertionError("maintenance leaked work")
 result=tick(client,Never(),Never(),refresher=Refresher(),now=lambda:1000)
 assert result["status"]=="maintenance" and result["dispatch"]=={"status":"maintenance"}
 assert "/v1/queue/plan" not in calls


def test_active_attempt_defers_refresh_but_still_reconciles_dispatcher():
 status={"policy_fingerprint":"a"*64,"items":[{"id":"active","state":"unknown"}],"current":{"id":"active","state":"unknown"},"maintenance":None}
 order=[]
 def client(method,path,payload=None,headers=None):return status
 class Refresher:
  def run_once(self,value):raise AssertionError("refresh must defer")
 class Admission:
  def run_once(self):return {"status":"active"}
 class Dispatch:
  def run_once(self):order.append("dispatch");return {"status":"reconciled"}
 result=tick(client,Dispatch(),Admission(),refresher=Refresher(),now=lambda:1000)
 assert result["base_refresh"]=={"status":"deferred","reason":"active_attempt"}
 assert result["dispatch"]=={"status":"reconciled"} and order==["dispatch"]


def test_unverified_legacy_work_blocks_planning_but_preserves_dispatch_reconcile():
 calls=[]
 status={"queue_paused":False,"current":None,"shared_executor_busy":False,"items":[],"plan_exhausted":False,
         "legacy_ready_pr_candidates":[{"job_id":"legacy","pr_url":"https://github.com/mihailzhamba-bot/proxima-ai/pull/143","head_sha":"a"*40}],"existing_work":[]}
 def client(method,path,payload=None,headers=None):
  calls.append((method,path));return status
 class Catalog:
  def run_once(self,_status):raise TimeoutError("github unavailable")
 class Dispatch:
  def run_once(self):return {"status":"idle"}
 result=tick(client,Dispatch(),existing_observer=Catalog(),now=lambda:1000)
 assert result["status"]=="existing_work_unknown" and result["planning"] is None and result["dispatch"]=={"status":"idle"}
 assert not any(path=="/v1/queue/plan" for _,path in calls)


def test_tick_starting_planning_never_admits_or_dispatches_ready_work():
 status={"policy_fingerprint":"a"*64,"plan_exhausted":False,"shared_executor_busy":False,"current":None,
         "items":[{"id":"ready-task","state":"ready"}],"legacy_ready_pr_candidates":[],"existing_work":[]}
 calls=[]
 def client(method,path,payload=None,headers=None):
  calls.append((method,path));return {"run_id":"planner-new","status":"running"} if path=="/v1/queue/plan" else status
 class Never:
  def run_once(self):raise AssertionError("execution raced planning")
 result=tick(client,Never(),Never(),now=lambda:1000)
 assert result["status"]=="planning_started" and result["planning"]["run_id"]=="planner-new"
 assert result["admission"]["reason"]=="planning_active" and result["dispatch"]["reason"]=="planning_active"
 assert calls.count(("POST","/v1/queue/plan"))==1


def test_tick_active_planning_never_admits_or_dispatches():
 status={"policy_fingerprint":"a"*64,"plan_exhausted":False,"shared_executor_busy":False,"current":None,
         "items":[{"id":"ready-task","state":"ready"}],"planning":{"id":"planner-active","state":"running"}}
 def client(method,path,payload=None,headers=None):
  if path.startswith("/v1/runs/"):raise TimeoutError("planning observation unknown")
  return status
 class Never:
  def run_once(self):raise AssertionError("execution raced active planning")
 result=tick(client,Never(),Never(),now=lambda:1000)
 assert result["status"]=="planning_active" and result["planning"] is None and result["planning_active"]["id"]=="planner-active" and result["dispatch"]["reason"]=="active_planning"


def test_active_planning_with_legacy_current_runs_reconciliation_only():
 status={"items":[{"id":"old-attempt","state":"unknown"}],"current":{"id":"old-attempt","state":"unknown"},
         "planning":{"id":"planner-active","state":"unknown"}}
 def client(method,path,payload=None,headers=None):
  if path.startswith("/v1/runs/"):raise TimeoutError("planner unknown")
  return status
 class ReconcileOnly:
  def run_once(self):raise AssertionError("generic dispatcher may claim or resume")
  def reconcile_only(self):return {"status":"settled","item_id":"old-attempt"}
 class NeverAdmission:
  def run_once(self):raise AssertionError("admission raced planning")
 result=tick(client,ReconcileOnly(),NeverAdmission(),now=lambda:1000)
 assert result["status"]=="planning_active" and result["dispatch"]=={"status":"settled","item_id":"old-attempt"}


def test_dispatcher_reconcile_only_never_claims_or_executes(tmp_path):
 settings=config(tmp_path);current=item();current.update(state="unknown",attempts=1)
 state=Path(settings["state_root"])/current["id"]/"attempt-1"/"batch-state.json";state.parent.mkdir(parents=True)
 state.write_text(json.dumps({"status":"completed","tasks":[{"phase":"ready_pr","run_id":"run-old","head_sha":"a"*40,"pr_url":"https://github.com/acme/repo/pull/1"}]}))
 calls=[]
 def call(method,path,payload=None):
  calls.append(path)
  if path=="/v1/queue":return {"current":{"id":current["id"],"state":"unknown"}}
  if path=="/v1/queue/"+current["id"]:return current
  if path.endswith("/update"):return {"state":payload["state"]}
  raise AssertionError(path)
 def execute(*args,**kwargs):raise AssertionError("reconciliation executed batch")
 result=Dispatcher(settings,call,execute,disk_free=lambda _path:0).reconcile_only()
 assert result=={"state":"ready_pr"} and "/v1/queue/claim" not in calls


def test_dispatcher_low_disk_blocks_before_claim_without_attempt(tmp_path):
 settings=config(tmp_path);calls=[]
 def call(method,path,payload=None):calls.append(path);return {"current":None}
 floor=settings["start_disk_floor_bytes"];result=Dispatcher(settings,call,disk_free=lambda _path:floor-1).run_once()
 assert result=={"status":"blocked","reason":"disk_start_floor","free_bytes":floor-1,"required_bytes":floor}
 assert calls==["/v1/queue"] and "/v1/queue/claim" not in calls


def test_dispatcher_high_disk_reaches_claim(tmp_path):
 settings=config(tmp_path);calls=[]
 def call(method,path,payload=None):
  calls.append(path)
  if path=="/v1/queue":return {"current":None}
  if path=="/v1/queue/claim":return {"id":None}
  raise AssertionError(path)
 assert Dispatcher(settings,call,disk_free=lambda _path:settings["start_disk_floor_bytes"]).run_once()=={"status":"idle"}
 assert calls==["/v1/queue","/v1/queue/claim"]


def test_existing_unknown_reconciles_despite_low_disk(tmp_path):
 settings=config(tmp_path);current=item();current.update(state="unknown",attempts=1)
 state=Path(settings["state_root"])/current["id"]/"attempt-1"/"batch-state.json";state.parent.mkdir(parents=True)
 state.write_text(json.dumps({"status":"completed","tasks":[{"phase":"ready_pr","head_sha":"a"*40,"pr_url":"https://github.com/acme/repo/pull/1"}]}))
 calls=[]
 def call(method,path,payload=None):
  calls.append(path)
  if path=="/v1/queue":return {"current":{"id":current["id"],"state":"unknown"}}
  if path=="/v1/queue/"+current["id"]:return current
  if path.endswith("/update"):return {"state":payload["state"]}
  raise AssertionError(path)
 result=Dispatcher(settings,call,disk_free=lambda _path:0).run_once()
 assert result=={"state":"ready_pr"} and "/v1/queue/claim" not in calls


def test_legacy_dispatch_config_keeps_three_gib_floor_and_reconciliation(tmp_path):
 settings=config(tmp_path);settings.pop("start_disk_floor_bytes")
 calls=[]
 def idle(method,path,payload=None):calls.append(path);return {"current":None}
 result=Dispatcher(settings,idle,disk_free=lambda _path:3*1024**3-1).run_once()
 assert result["reason"]=="disk_start_floor" and result["required_bytes"]==3*1024**3 and calls==["/v1/queue"]
 # reconcile-only must remain constructible before the operator atomically updates the config.
 assert Dispatcher(settings,lambda *_args,**_kwargs:{"current":None},disk_free=lambda _path:0).reconcile_only()=={"status":"idle","reason":"reconciliation_only"}


def test_resumed_same_attempt_uses_fresh_subdirectory_and_keeps_original_artifacts(tmp_path):
 settings=config(tmp_path);resumed=item();resumed.update(id="wb-daily-status-slice",state="dispatching",attempts=2,external_job_id="wb-daily-status-slice-a2",evidence={"resume_sequence":1,"resume_proof":{"state_sha256":"b"*64}})
 original=Path(settings["state_root"])/resumed["id"]/"attempt-2";original.mkdir(parents=True);old_manifest=original/"manifest.json";old_state=original/"batch-state.json";old_manifest.write_text("immutable-manifest");old_state.write_text("immutable-state")
 calls=[];observed={}
 def call(method,path,payload=None):
  calls.append((path,payload))
  if path=="/v1/queue":return {"current":{"id":resumed["id"],"state":"dispatching"}}
  if path=="/v1/queue/"+resumed["id"]:return resumed
  if path.endswith("/update"):return {"state":payload["state"]}
  raise AssertionError(path)
 def execute(argv,**kwargs):
  manifest_path=Path(argv[-1]);observed["path"]=manifest_path;manifest=json.loads(manifest_path.read_text());observed["manifest"]=manifest
  state=Path(manifest["state_file"]);state.write_text(json.dumps({"status":"completed","tasks":[{"phase":"ready_pr","head_sha":"1"*40,"pr_url":"https://github.com/acme/repo/pull/1"}]}));return SimpleNamespace(returncode=0)
 result=Dispatcher(settings,call,execute,clock=lambda:5000,disk_free=lambda _path:0).run_once()
 assert result=={"state":"ready_pr"} and observed["path"].parent.name=="resume-1"
 assert observed["manifest"]["tasks"][0]["job_id"]=="wb-daily-status-slice-a2" and observed["manifest"]["end_at"]==5000+120+300
 assert old_manifest.read_text()=="immutable-manifest" and old_state.read_text()=="immutable-state"
 running=next(payload for path,payload in calls if path.endswith("/update") and payload["state"]=="running")
 assert running["resume_sequence"]==1 and "/v1/queue/claim" not in [path for path,_ in calls]


def test_resumed_unknown_monitoring_preserves_sequence_when_adopting_running(tmp_path):
 settings=config(tmp_path);current=item();current.update(id="wb-daily-status-slice",state="unknown",attempts=2,external_run_id=None,external_job_id="wb-daily-status-slice-a2",evidence={"resume_sequence":1})
 root=Path(settings["state_root"])/current["id"]/"attempt-2"/"resume-1";root.mkdir(parents=True)
 manifest,admission,_=render({**current,"state":"running"},settings,2000);Path(settings["admission_root"]).mkdir(exist_ok=True);from tools.loop.night_batch import atomic_json
 atomic_json(root/"manifest.json",manifest);atomic_json(Path(settings["admission_root"])/"wb-daily-status-slice-a2.json",admission);atomic_json(Path(manifest["state_file"]),{"status":"running","tasks":[{"phase":"monitoring","run_id":"run-resumed"}]})
 updates=[]
 def call(method,path,payload=None):
  if path=="/v1/queue":return {"current":{"id":current["id"],"state":"unknown"}}
  if path=="/v1/queue/"+current["id"]:return current
  if path.endswith("/update"):updates.append(payload);return {**current,"state":payload["state"],"external_run_id":payload.get("run_id"),"evidence":{"resume_sequence":payload.get("resume_sequence")}}
  raise AssertionError(path)
 def execute(argv,**kwargs):return SimpleNamespace(returncode=1)
 Dispatcher(settings,call,execute,clock=lambda:2000,disk_free=lambda _path:0).run_once()
 assert updates[0]["state"]=="running" and updates[0]["resume_sequence"]==1 and updates[0]["run_id"]=="run-resumed"


def test_resumed_reconcile_preserves_sequence_when_adopting_run_identity(tmp_path):
 settings=config(tmp_path);current=item();current.update(id="wb-daily-status-slice",state="blocked",attempts=2,external_run_id=None,external_job_id="wb-daily-status-slice-a2",evidence={"resume_sequence":1})
 state=Path(settings["state_root"])/current["id"]/"attempt-2"/"resume-1"/"batch-state.json";state.parent.mkdir(parents=True);state.write_text(json.dumps({"status":"blocked","reason":"job_timeout","tasks":[{"phase":"monitoring","run_id":"run-resumed"}]}))
 updates=[]
 def call(method,path,payload=None):
  if path.endswith("/update"):updates.append(payload);return {**current,"external_run_id":payload["run_id"],"evidence":{"resume_sequence":payload.get("resume_sequence")}}
  if path=="/v1/runs/run-resumed":return {"status":"running"}
  raise AssertionError(path)
 result=Dispatcher(settings,call,disk_free=lambda _path:0).reconcile(current)
 assert result["status"]=="active" and updates[0]["resume_sequence"]==1 and updates[0]["run_id"]=="run-resumed"
