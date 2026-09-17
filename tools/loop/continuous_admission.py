"""Trusted proposal admission: independent review then idempotent three-target registration."""
from __future__ import annotations
import json,subprocess
class AdmissionError(ValueError):pass
def command(argv,payload,execute=subprocess.run,timeout=300):
    if not isinstance(argv,list) or not argv or any(not isinstance(v,str) or not v or (i==0 and not v.startswith("/")) for i,v in enumerate(argv)):raise AdmissionError("invalid trusted command")
    result=execute(argv,input=json.dumps(payload).encode(),capture_output=True,timeout=timeout,check=False)
    if result.returncode or len(result.stdout)>1_000_000:raise AdmissionError("trusted admission command failed")
    try:value=json.loads(result.stdout)
    except Exception:raise AdmissionError("invalid admission receipt") from None
    if not isinstance(value,dict):raise AdmissionError("invalid admission receipt")
    return value
class Admission:
    def __init__(self,config,call,execute=subprocess.run):
        if not isinstance(config,dict) or set(config)!={"reviewer_command","registrars"} or set(config["registrars"])!={"bridge","harper","worker"}:raise AdmissionError("invalid admission config")
        self.config,self.call,self.execute=config,call,execute
    def run_once(self):
        status=self.call("GET","/v1/queue")
        if status.get("current") is not None:return {"status":"active","item_id":status["current"]["id"]}
        if status.get("shared_executor_busy"):return {"status":"active","reason":"shared_executor_busy"}
        states={value.get("id"):value.get("state") for value in status.get("items",[])}
        candidate=None
        for value in status.get("items",[]):
            if value.get("state") not in {"proposed","registering"}:continue
            detail=self.call("GET","/v1/queue/"+value["id"])
            if all(states.get(dependency)=="merged" for dependency in detail.get("depends_on",[])):
                candidate=value;break
        if candidate is None:return {"status":"idle"}
        item=self.call("GET","/v1/queue/"+candidate["id"])
        if item["state"]=="proposed":
            existing=[self.call("GET","/v1/queue/"+value["id"]) for value in status["items"]
                      if value["id"]!=item["id"] and value["requirement_id"]==item["requirement_id"]]
            dependencies=[self.call("GET","/v1/queue/"+dependency_id) for dependency_id in item["depends_on"]]
            receipt=command(self.config["reviewer_command"],{"proposal":item,"existing":existing,
                "legacy_existing":status.get("existing_work",[]),"dependencies":dependencies},self.execute)
            if receipt.get("verdict")=="block":
                item=self.call("POST","/v1/queue/"+item["id"]+"/reject",payload=receipt)
                return {"status":"rejected","item_id":item["id"],"blocker":item.get("blocker")}
            item=self.call("POST","/v1/queue/"+item["id"]+"/review",payload=receipt)
        registration=self.call("GET","/v1/queue/"+item["id"]+"/registration")
        completed=set(registration.get("receipts",{}));receipts=[]
        for target in ("bridge","harper","worker"):
            if target in completed:continue
            fresh=self.call("GET","/v1/queue")
            if fresh.get("current") is not None or fresh.get("shared_executor_busy") or fresh.get("policy_fingerprint")!=registration["policy_fingerprint"]:
                raise AdmissionError("registration idle fence changed")
            idle={"observed_at":fresh["observed_at"],"queue_current":None,
                  "shared_executor_busy":False,"policy_fingerprint":fresh["policy_fingerprint"]}
            receipt=command(self.config["registrars"][target],{"action":"register","target":target,
                "registration":registration,"idle_receipt":idle},self.execute)
            if receipt.get("target")!=target:raise AdmissionError("registration target mismatch")
            self.call("POST","/v1/queue/"+item["id"]+"/receipt",payload=receipt);receipts.append(target)
            registration=self.call("GET","/v1/queue/"+item["id"]+"/registration")
        return {"status":registration["state"],"item_id":item["id"],"registered":receipts}



class CommandDispatcher:
    def __init__(self,argv,execute=subprocess.run):self.argv,self.execute=argv,execute
    def run_once(self):return command(self.argv,{"action":"dispatch"},self.execute,timeout=3600)
