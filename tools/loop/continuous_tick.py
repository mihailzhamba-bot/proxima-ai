#!/usr/bin/python3 -I
"""Five-minute continuous LOOP tick: replenish with Paperclip, then dispatch one task."""
from __future__ import annotations
import argparse,hashlib,json,sys,time
from datetime import datetime,timezone
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parent))
try:
    from .bridge import JsonHTTP,secret
    from .continuous_dispatch import Dispatcher
    from .continuous_admission import Admission,CommandDispatcher
    from .continuous_report import Reporter
    from .night_batch import json_file
except ImportError:
    from bridge import JsonHTTP,secret
    from continuous_dispatch import Dispatcher
    from continuous_admission import Admission,CommandDispatcher
    from continuous_report import Reporter
    from night_batch import json_file
PIPELINE={"proposed","registering","ready","dispatching","running","unknown"}
def planning_key(status,now):
    snapshot=[(item.get("id"),item.get("state")) for item in status.get("items",[]) if item.get("state") in PIPELINE]
    value=json.dumps({"policy":status.get("policy_fingerprint"),"queue":snapshot,
                      "snapshot":status.get("planning_snapshot"),"generation":status.get("planning_generation",0)},sort_keys=True)
    return "continuous-plan-"+hashlib.sha256(value.encode()).hexdigest()[:32]
def tick(client,dispatcher,admission=None,reporter=None,now=time.time):
    status=client("GET","/v1/queue")
    if status.get("queue_paused"):
        reported=reporter.run(status,now()) if reporter is not None else {"status":"disabled"}
        return {"status":"paused","queue_depth":len(status.get("items",[])),"planning":None,
                "admission":{"status":"paused"},"dispatch":{"status":"paused"},"report":reported}
    pending=[item for item in status.get("items",[]) if item.get("state") in PIPELINE]
    plan=None
    planning=(status.get("planning") or {});planning_state=planning.get("state")
    if planning_state in {"dispatching","running","unknown","cancelling"} and planning.get("id"):
        try:
            observed=client("GET","/v1/runs/"+planning["id"])
            planning_state=observed.get("status",planning_state)
        except Exception:planning_state="unknown"
    if (status.get("current") is None and not status.get("shared_executor_busy",False)
            and len(pending)<3 and not status.get("plan_exhausted",False)
            and not status.get("planning_retry_exhausted",False)
            and planning_state not in {"dispatching","running","unknown","cancelling"}):
        try:plan=client("POST","/v1/queue/plan",payload={},headers={"Idempotency-Key":planning_key(status,now())})
        except Exception:plan={"status":"unknown","reason":"planning_reconcile_required"}
    try:admitted=admission.run_once() if admission is not None else {"status":"disabled"}
    except Exception:admitted={"status":"blocked","reason":"admission_failed"}
    try:report_status=client("GET","/v1/queue")
    except Exception:report_status=status
    try:reported=reporter.run(report_status,now()) if reporter is not None else {"status":"disabled"}
    except Exception:reported={"status":"unknown"}
    try:dispatched=dispatcher.run_once()
    except Exception:dispatched={"status":"unknown","reason":"dispatch_reconcile_required"}
    return {"status":"ok","queue_depth":len(pending),"planning":plan,"admission":admitted,"dispatch":dispatched,"report":reported}
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True,type=Path);args=parser.parse_args()
    config=json_file(args.config);key_file=config["bridge_key_file"]
    client=JsonHTTP(config["bridge_url"],secret(key_file),trusted_bridge=True)
    print(json.dumps(tick(client.call,CommandDispatcher(config["dispatch_command"]),Admission(config["admission"],client.call),Reporter(config["report"]))));return 0
if __name__=="__main__":raise SystemExit(main())
