#!/usr/bin/python3 -I
"""Dispatch one reviewed continuous queue item through the existing finite night batch."""
from __future__ import annotations
import argparse,fcntl,json,os,re,subprocess,sys,time
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parent))
try:
    from .night_batch import atomic_json,json_file
except ImportError:
    from night_batch import atomic_json,json_file
SHA=re.compile(r"^[0-9a-f]{40}$");DIGEST=re.compile(r"^[0-9a-f]{64}$")
class DispatchError(ValueError):pass
def checked(config):
    required={"state_root","admission_root","night_batch_script","manifest_defaults"}
    if not isinstance(config,dict) or set(config)!=required:raise DispatchError("invalid continuous dispatcher config")
    for key in required-{"manifest_defaults"}:
        if not isinstance(config[key],str) or not Path(config[key]).is_absolute():raise DispatchError("dispatcher paths must be absolute")
    defaults=config["manifest_defaults"]
    needed={"template_bases","job_timeout_seconds","poll_seconds","disk_floor_bytes","evidence_root","work_root","glm_config","glm_script","review_receipts","operator_key_file","runner_key_file","acceptance_command"}
    if not isinstance(defaults,dict) or set(defaults)!=needed:raise DispatchError("invalid manifest defaults")
    return config
def attempt_id(item):
    value=f'{item["id"]}-a{item["attempts"]}'
    if len(value)>40:raise DispatchError("attempt job id exceeds Bridge contract")
    return value
def render(item,config,now):
    if item.get("state") not in {"dispatching","running"} or not DIGEST.fullmatch(str(item.get("lease_id",""))) or not SHA.fullmatch(str(item.get("base_sha",""))) or not DIGEST.fullmatch(str(item.get("template_fingerprint",""))):raise DispatchError("invalid claimed queue item")
    defaults=config["manifest_defaults"];job=attempt_id(item);root=Path(config["state_root"])/item["id"]/f'attempt-{item["attempts"]}'
    manifest={**defaults,"template_bases":{item["template_name"]:item["base_sha"]},
      "tasks":[{"key":"continuous-"+job,"job_id":job,"template":item["template_name"],"template_fingerprint":item["template_fingerprint"]}],
      "end_at":now+item.get("job_timeout_seconds",defaults["job_timeout_seconds"])+300,
      "state_file":str(root/"batch-state.json"),"pause_on_completion":False,"halt_mode":"local"}
    acceptance={"schema_version":1,"queue_id":item["id"],"job_id":job,"attempt":item["attempts"],
      "requirement_id":item["requirement_id"],"base_sha":item["base_sha"],"policy_fingerprint":item["policy_fingerprint"],
      "proposal_fingerprint":item["proposal_fingerprint"],"review_fingerprint":item["review_fingerprint"],
      "template_name":item["template_name"],"template_fingerprint":item["template_fingerprint"],
      "allowed_paths":item["allowed_paths"],"goal":item["goal"],"acceptance":item["acceptance"],"acceptance_profile":item["execution_policy"]["acceptance_profile"]}
    return manifest,acceptance,root
class Dispatcher:
    def __init__(self,config,call,execute=subprocess.run,clock=time.time):
        self.config,self.call,self.execute,self.clock=checked(config),call,execute,clock
    def run_once(self):
        lock_path=Path(self.config["state_root"])/"dispatcher.lock";lock_path.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return {"status":"busy"}
            return self._run_locked()
        finally:os.close(fd)
    def _run_locked(self):
        status=self.call("GET","/v1/queue");current=status.get("current");resume=False
        if status.get("queue_paused"):return {"status":"paused"}
        if current is not None:
            item=self.call("GET","/v1/queue/"+current["id"])
            if current.get("state")=="unknown":
                state_path=Path(self.config["state_root"])/item["id"]/f'attempt-{item["attempts"]}'/"batch-state.json"
                try:persisted=json_file(state_path)
                except Exception:persisted={}
                task=persisted.get("tasks",[{}])[0] if isinstance(persisted.get("tasks"),list) and persisted["tasks"] else {}
                if persisted.get("status")=="running" and task.get("phase") in {"monitoring","reviewing"}:
                    item=self.call("POST",f'/v1/queue/{item["id"]}/update',payload={"lease_id":item["lease_id"],"state":"running",
                      "run_id":task.get("run_id"),"job_id":item.get("external_job_id") or attempt_id(item),"evidence_ref":str(state_path)})
                    resume=True
                else:return self.reconcile(item)
            elif current.get("state")=="blocked":return self.reconcile(item)
            elif current.get("state") not in {"dispatching","running"}:return {"status":"active","item_id":current.get("id"),"state":current.get("state")}
            else:resume=True
        else:item=self.call("POST","/v1/queue/claim",payload={})
        if item.get("id") is None:return {"status":"idle"}
        manifest,admission,root=render(item,self.config,self.clock());root.mkdir(parents=True,exist_ok=resume)
        admission_path=Path(self.config["admission_root"])/(attempt_id(item)+".json")
        admission_path.parent.mkdir(parents=True,exist_ok=True)
        if admission_path.exists():
            if admission_path.is_symlink() or json_file(admission_path)!=admission:raise DispatchError("attempt admission receipt conflict")
        else:
            atomic_json(admission_path,admission);os.chmod(admission_path,0o600)
        manifest_path=root/"manifest.json"
        if manifest_path.exists():
            persisted=json_file(manifest_path)
            expected={**manifest,"end_at":persisted.get("end_at")}
            if manifest_path.is_symlink() or persisted!=expected:raise DispatchError("attempt manifest conflict")
            manifest=persisted
        else:atomic_json(manifest_path,manifest)
        if item["state"]=="dispatching":
            self.call("POST",f'/v1/queue/{item["id"]}/update',payload={"lease_id":item["lease_id"],"state":"running","job_id":attempt_id(item),"evidence_ref":str(admission_path)})
        try:
            result=self.execute([sys.executable,"-I",self.config["night_batch_script"],"--manifest",str(manifest_path)],
                stdin=subprocess.DEVNULL,capture_output=True,timeout=manifest["job_timeout_seconds"]+360,check=False)
        except Exception:
            return self.call("POST",f'/v1/queue/{item["id"]}/update',payload={"lease_id":item["lease_id"],"state":"unknown","job_id":attempt_id(item),"evidence_ref":str(manifest_path),"blocker":"batch_process_unknown"})
        try:state=json_file(manifest["state_file"])
        except Exception:
            return self.call("POST",f'/v1/queue/{item["id"]}/update',payload={"lease_id":item["lease_id"],"state":"unknown","job_id":attempt_id(item),"evidence_ref":str(manifest_path),"blocker":"batch_state_unavailable"})
        task=state.get("tasks",[{}])[0] if isinstance(state.get("tasks"),list) and state["tasks"] else {}
        if result.returncode==0 and state.get("status")=="completed" and task.get("phase")=="ready_pr":
            return self.call("POST",f'/v1/queue/{item["id"]}/update',payload={"lease_id":item["lease_id"],"state":"ready_pr","job_id":attempt_id(item),"head_sha":task.get("head_sha"),"pr_url":task.get("pr_url"),"evidence_ref":str(manifest["state_file"])})
        return self.call("POST",f'/v1/queue/{item["id"]}/update',payload={"lease_id":item["lease_id"],"state":"blocked" if state.get("status")=="blocked" else "unknown","run_id":task.get("run_id"),"job_id":attempt_id(item),"evidence_ref":str(manifest["state_file"]),"blocker":str(state.get("reason","batch_failed"))[:120]})
    def reconcile(self,item):
        state_path=Path(self.config["state_root"])/item["id"]/f'attempt-{item["attempts"]}'/"batch-state.json"
        try:batch=json_file(state_path)
        except Exception:return {"status":"unknown","item_id":item["id"],"reason":"batch_state_unavailable"}
        task=batch.get("tasks",[{}])[0] if isinstance(batch.get("tasks"),list) and batch["tasks"] else {}
        if batch.get("status")=="completed" and task.get("phase")=="ready_pr":
            return self.call("POST",f'/v1/queue/{item["id"]}/update',payload={"lease_id":item["lease_id"],"state":"ready_pr",
              "run_id":task.get("run_id"),"job_id":attempt_id(item),"head_sha":task.get("head_sha"),
              "pr_url":task.get("pr_url"),"evidence_ref":str(state_path)})
        reason=batch.get("reason")
        retryable={"job_timeout","glm_review_blocked","batch_operation_failed","completed_without_job","review_deadline","acceptance_deadline"}
        run_id=item.get("external_run_id") or task.get("run_id")
        if run_id and not item.get("external_run_id"):
            item=self.call("POST",f'/v1/queue/{item["id"]}/update',payload={"lease_id":item["lease_id"],
              "state":item["state"],"run_id":run_id,"job_id":item.get("external_job_id") or attempt_id(item),
              "evidence_ref":str(state_path),"blocker":str(reason or "reconcile")[:120]})
        if not run_id:return {"status":"unknown","item_id":item["id"],"reason":"run_identity_unavailable"}
        try:run=self.call("GET","/v1/runs/"+run_id)
        except Exception:return {"status":"unknown","item_id":item["id"],"reason":"stop_reconcile_failed"}
        if run.get("status") not in {"cancelled","failed","error","interrupted","stopped"}:return {"status":"active","item_id":item["id"],"state":run.get("status")}
        base_receipt={"stopped":True,"previous_lease_id":item["lease_id"],"external_run_id":run_id,
          "external_job_id":item.get("external_job_id"),"evidence_ref":str(state_path)}
        if item["attempts"]<3 and reason in retryable:
            return self.call("POST",f'/v1/queue/{item["id"]}/retry',payload={**base_receipt,"reason":"local_failure"})
        settlement="attempts_exhausted" if item["attempts"]>=3 else "nonretryable"
        return self.call("POST",f'/v1/queue/{item["id"]}/settle',payload={**base_receipt,"reason":settlement})

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True,type=Path);args=parser.parse_args()
    config=json_file(args.config);bridge_url=config.pop("bridge_url")
    try:
        from .bridge import JsonHTTP,secret
    except ImportError:
        from bridge import JsonHTTP,secret
    client=JsonHTTP(bridge_url,secret(config.pop("bridge_key_file")),trusted_bridge=True)
    print(json.dumps(Dispatcher(config,client.call).run_once()));return 0
if __name__=="__main__":raise SystemExit(main())
