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
        candidate=next((v for v in status.get("items",[]) if v.get("state") in {"proposed","registering"}),None)
        if candidate is None:return {"status":"idle"}
        item=self.call("GET","/v1/queue/"+candidate["id"])
        if item["state"]=="proposed":
            existing=[self.call("GET","/v1/queue/"+value["id"]) for value in status["items"]
                      if value["id"]!=item["id"] and value["requirement_id"]==item["requirement_id"]]
            dependencies=[self.call("GET","/v1/queue/"+dependency_id) for dependency_id in item["depends_on"]]
            receipt=command(self.config["reviewer_command"],{"proposal":item,"existing":existing,"dependencies":dependencies},self.execute)
            if receipt.get("verdict")=="block":
                item=self.call("POST","/v1/queue/"+item["id"]+"/reject",payload=receipt)
                return {"status":"rejected","item_id":item["id"],"blocker":item.get("blocker")}
            item=self.call("POST","/v1/queue/"+item["id"]+"/review",payload=receipt)
        registration=self.call("GET","/v1/queue/"+item["id"]+"/registration")
        completed=set(registration.get("receipts",{}));receipts=[]
        for target in ("bridge","harper","worker"):
            if target in completed:continue
            idle={"observed_at":status["observed_at"],"queue_current":None,
                  "shared_executor_busy":False,"policy_fingerprint":status["policy_fingerprint"]}
            receipt=command(self.config["registrars"][target],{"action":"register","target":target,
                "registration":registration,"idle_receipt":idle},self.execute)
            if receipt.get("target")!=target:raise AdmissionError("registration target mismatch")
            registration=self.call("POST","/v1/queue/"+item["id"]+"/receipt",payload=receipt);receipts.append(target)
        return {"status":registration["state"],"item_id":item["id"],"registered":receipts}



class CommandDispatcher:
    def __init__(self,argv,execute=subprocess.run):self.argv,self.execute=argv,execute
    def run_once(self):return command(self.argv,{"action":"dispatch"},self.execute,timeout=3600)
