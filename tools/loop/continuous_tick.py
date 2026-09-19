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
    from .continuous_merge_observer import MergeObserver,pinned_github_origin
    from .continuous_existing_work import ExistingWorkObserver,ExistingWorkError
    from .continuous_base_refresh import BaseRefresher,RefreshError
    from .night_batch import json_file
except ImportError:
    from bridge import JsonHTTP,secret
    from continuous_dispatch import Dispatcher
    from continuous_admission import Admission,CommandDispatcher
    from continuous_report import Reporter
    from continuous_merge_observer import MergeObserver,pinned_github_origin
    from continuous_existing_work import ExistingWorkObserver,ExistingWorkError
    from continuous_base_refresh import BaseRefresher,RefreshError
    from night_batch import json_file
PIPELINE={"proposed","registering","ready","dispatching","running","unknown"}
def planning_key(status,now):
    snapshot=[(item.get("id"),item.get("state")) for item in status.get("items",[]) if item.get("state") in PIPELINE]
    value=json.dumps({"policy":status.get("policy_fingerprint"),"queue":snapshot,
                      "snapshot":status.get("planning_snapshot"),"generation":status.get("planning_generation",0)},sort_keys=True)
    return "continuous-plan-"+hashlib.sha256(value.encode()).hexdigest()[:32]
def tick(client,dispatcher,admission=None,reporter=None,observer=None,refresher=None,existing_observer=None,now=time.time):
    status=client("GET","/v1/queue")
    if status.get("queue_paused"):
        reported=reporter.run(status,now()) if reporter is not None else {"status":"disabled"}
        return {"status":"paused","queue_depth":len(status.get("items",[])),"planning":None,
                "admission":{"status":"paused"},"dispatch":{"status":"paused"},"report":reported}
    try:merges=observer.run_once(status) if observer is not None else {"status":"disabled"}
    except Exception:merges={"status":"unknown","blocker":"merge_observer_failed"}
    if merges.get("merged"):
        try:status=client("GET","/v1/queue")
        except Exception:pass
    pre_refresh_planning=status.get("planning") or {}
    if pre_refresh_planning.get("state") in {"dispatching","running","unknown","cancelling"} and pre_refresh_planning.get("id"):
        try:
            client("GET","/v1/runs/"+pre_refresh_planning["id"])
            status=client("GET","/v1/queue")
        except Exception:pass
    active_planning=status.get("planning") or {}
    if active_planning.get("state") in {"dispatching","running","unknown","cancelling"}:
        reconciled={"status":"blocked","reason":"active_planning"}
        if status.get("current") is not None:
            try:reconciled=dispatcher.reconcile_only()
            except Exception:reconciled={"status":"unknown","reason":"attempt_reconcile_required"}
        return {"status":"planning_active","queue_depth":len(status.get("items",[])),"merges":merges,
                "base_refresh":{"status":"deferred","reason":"active_planning"},"existing_work":{"status":"deferred"},
                "planning":None,"planning_active":active_planning,"admission":{"status":"blocked","reason":"active_planning"},
                "dispatch":reconciled,"report":{"status":"disabled"}}
    if status.get("current") is not None:
        refresh={"status":"deferred","reason":"active_attempt"}
    else:
        try:refresh=refresher.run_once(status) if refresher is not None else {"status":"disabled"}
        except RefreshError as error:refresh={"status":"blocked","blocker":str(error)}
        except Exception:refresh={"status":"blocked","blocker":"base_refresh_failed"}
    if refresh.get("status")=="complete":
        try:status=client("GET","/v1/queue")
        except Exception:pass
    maintenance=(status.get("maintenance") or {}).get("state") in {"fetching","installing"}
    if refresh.get("status")=="blocked" or maintenance:
        try:reported=reporter.run(status,now()) if reporter is not None else {"status":"disabled"}
        except Exception:reported={"status":"unknown"}
        return {"status":"maintenance","queue_depth":len(status.get("items",[])),"merges":merges,
                "base_refresh":refresh,"planning":None,"admission":{"status":"maintenance"},
                "dispatch":{"status":"maintenance"},"report":reported}
    try:catalog=existing_observer.run_once(status) if existing_observer is not None else {"status":"disabled"}
    except Exception:catalog={"status":"unknown","blocker":"existing_work_github_unavailable"}
    if catalog.get("verified_jobs"):
        try:status=client("GET","/v1/queue")
        except Exception:pass
    unresolved={v.get("job_id") for v in status.get("legacy_ready_pr_candidates",[])}-{v.get("job_id") for v in status.get("existing_work",[])}
    if catalog.get("status")=="unknown" or unresolved:
        try:dispatched=dispatcher.run_once()
        except Exception:dispatched={"status":"unknown","reason":"dispatch_reconcile_required"}
        return {"status":"existing_work_unknown","queue_depth":len(status.get("items",[])),"merges":merges,
                "base_refresh":refresh,"existing_work":catalog,"planning":None,"admission":{"status":"blocked","reason":"existing_work_unknown"},
                "dispatch":dispatched,"report":{"status":"disabled"}}
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
        return {"status":"planning_started","queue_depth":len(pending),"merges":merges,"base_refresh":refresh,
                "existing_work":catalog,"planning":plan,"admission":{"status":"blocked","reason":"planning_active"},
                "dispatch":{"status":"blocked","reason":"planning_active"},"report":{"status":"disabled"}}
    try:admitted=admission.run_once() if admission is not None else {"status":"disabled"}
    except Exception:admitted={"status":"blocked","reason":"admission_failed"}
    try:report_status=client("GET","/v1/queue")
    except Exception:report_status=status
    try:reported=reporter.run(report_status,now()) if reporter is not None else {"status":"disabled"}
    except Exception:reported={"status":"unknown"}
    try:dispatched=dispatcher.run_once()
    except Exception:dispatched={"status":"unknown","reason":"dispatch_reconcile_required"}
    return {"status":"ok","queue_depth":len(pending),"merges":merges,"base_refresh":refresh,"existing_work":catalog,"planning":plan,"admission":admitted,"dispatch":dispatched,"report":reported}
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True,type=Path);args=parser.parse_args()
    config=json_file(args.config);key_file=config["bridge_key_file"]
    client=JsonHTTP(config["bridge_url"],secret(key_file),trusted_bridge=True)
    observer_config=dict(config["merge_observer"]);github_url=observer_config.pop("github_url");github_token=observer_config.pop("token_file")
    github=JsonHTTP(pinned_github_origin(github_url),secret(github_token),timeout=observer_config["timeout_seconds"])
    observer=MergeObserver(observer_config,client.call,github.call)
    catalog=ExistingWorkObserver({"repository":observer_config["repository"],"base":observer_config["target_branch"],"max_per_tick":observer_config["max_polls"],"timeout_seconds":observer_config["timeout_seconds"]},client.call,github.call)
    refresher=BaseRefresher(config["base_refresh"],client.call,github.call)
    print(json.dumps(tick(client.call,CommandDispatcher(config["dispatch_command"]),Admission(config["admission"],client.call),None,observer,refresher,catalog)));return 0
if __name__=="__main__":raise SystemExit(main())
