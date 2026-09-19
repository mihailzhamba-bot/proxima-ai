"""Read-only GitHub merge observer for verified continuous queue candidates."""
from __future__ import annotations
import re,signal,threading,time
from pathlib import Path
from urllib.parse import urlparse
try:
    from .night_batch import atomic_json,json_file
except ImportError:
    from night_batch import atomic_json,json_file
SHA=re.compile(r"^[0-9a-f]{40}$")
REPOSITORY=re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PINNED_REPOSITORY="mihailzhamba-bot/proxima-ai"
PINNED_TARGET="feat/loop-pilot"
class ObserveError(ValueError):pass
def pinned_github_origin(url):
    if url!="https://api.github.com":raise ObserveError("unpinned GitHub origin")
    return url
def deadline_call(call,timeout,method,path):
    if threading.current_thread() is not threading.main_thread():raise ObserveError("deadline requires main thread")
    def expired(_signal,_frame):raise TimeoutError("GitHub observation deadline")
    previous=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,timeout)
    try:return call(method,path)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
def checked(config):
    required={"repository","target_branch","max_polls","timeout_seconds","cursor_file"}
    if not isinstance(config,dict) or set(config)!=required:raise ObserveError("invalid merge observer config")
    if config["repository"]!=PINNED_REPOSITORY or not REPOSITORY.fullmatch(str(config["repository"])):raise ObserveError("invalid observer repository")
    if config["target_branch"]!=PINNED_TARGET or not isinstance(config["target_branch"],str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,120}",config["target_branch"]) or ".." in config["target_branch"]:raise ObserveError("invalid observer branch")
    if type(config["max_polls"]) is not int or not 1<=config["max_polls"]<=8:raise ObserveError("invalid observer poll bound")
    if type(config["timeout_seconds"]) is not int or not 1<=config["timeout_seconds"]<=30:raise ObserveError("invalid observer timeout")
    if not isinstance(config["cursor_file"],str) or not Path(config["cursor_file"]).is_absolute():raise ObserveError("invalid observer cursor")
    return config
def pull_number(url,repository):
    parsed=urlparse(url)
    expected="/"+repository+"/pull/"
    if parsed.scheme!="https" or parsed.netloc!="github.com" or parsed.query or parsed.fragment or not parsed.path.startswith(expected):raise ObserveError("PR URL outside pinned repository")
    suffix=parsed.path[len(expected):]
    if not suffix.isascii() or not suffix.isdigit() or str(int(suffix))!=suffix or int(suffix)<1:raise ObserveError("invalid PR number")
    return int(suffix)
class MergeObserver:
    def __init__(self,config,bridge_call,github_call):
        self.config,self.bridge,self.github=checked(config),bridge_call,github_call
    def candidates(self,status):
        items=status.get("items",[])
        ready=[item for item in items if item.get("state")=="ready_pr"]
        if not ready:return []
        states={item.get("id"):item.get("state") for item in items};needed=set()
        for item in items:
            if item.get("state") in {"merged","rejected","cancelled"}:continue
            needed.update(dep for dep in item.get("depends_on",[]) if states.get(dep)=="ready_pr")
        eligible=ready if len(ready)<=3 else [item for item in ready if item.get("id") in needed]
        if not eligible:return []
        cursor_path=Path(self.config["cursor_file"]);last=None
        if cursor_path.exists():
            if cursor_path.is_symlink():raise ObserveError("untrusted observer cursor")
            saved=json_file(cursor_path)
            if not isinstance(saved,dict) or set(saved)!={"last_id"} or not isinstance(saved["last_id"],str):raise ObserveError("invalid observer cursor")
            last=saved["last_id"]
        ids=[item["id"] for item in eligible];start=ids.index(last)+1 if last in ids else 0
        rotated=eligible[start:]+eligible[:start]
        return rotated[:self.config["max_polls"]]
    def observe(self,item):
        try:detail=self.bridge("GET","/v1/queue/"+item["id"])
        except Exception:return {"item_id":item.get("id"),"status":"unknown","blocker":"queue_candidate_unavailable"}
        if detail.get("state")!="ready_pr" or detail.get("execution_policy",{}).get("repository")!=self.config["repository"]:
            return {"item_id":detail.get("id"),"status":"blocked","blocker":"candidate_repository_mismatch"}
        try:number=pull_number(detail.get("pr_url",""),self.config["repository"])
        except ObserveError:return {"item_id":detail.get("id"),"status":"blocked","blocker":"pr_url_mismatch"}
        try:remote=deadline_call(self.github,self.config["timeout_seconds"],"GET",f"/repos/{self.config['repository']}/pulls/{number}")
        except Exception:return {"item_id":detail["id"],"status":"unknown","blocker":"github_observation_unavailable"}
        expected_url=f"https://github.com/{self.config['repository']}/pull/{number}"
        if (not isinstance(remote,dict) or remote.get("number")!=number or remote.get("html_url")!=expected_url
                or not isinstance(remote.get("merged"),bool) or not isinstance(remote.get("state"),str)):
            return {"item_id":detail["id"],"status":"unknown","blocker":"github_response_invalid"}
        if remote["merged"] is not True:
            blocker="github_pr_closed_unmerged" if remote.get("state")=="closed" else "github_pr_not_merged"
            return {"item_id":detail["id"],"status":"pending" if remote.get("state")=="open" else "blocked","blocker":blocker}
        if remote.get("state")!="closed":
            return {"item_id":detail["id"],"status":"unknown","blocker":"github_merged_state_invalid"}
        candidate_sha=(detail.get("evidence") or {}).get("head_sha")
        head_sha=(remote.get("head") or {}).get("sha")
        base_ref=(remote.get("base") or {}).get("ref")
        merge_sha=remote.get("merge_commit_sha")
        if not SHA.fullmatch(str(candidate_sha)) or head_sha!=candidate_sha:
            return {"item_id":detail["id"],"status":"blocked","blocker":"github_head_mismatch"}
        if base_ref!=self.config["target_branch"]:
            return {"item_id":detail["id"],"status":"blocked","blocker":"github_base_mismatch"}
        if not SHA.fullmatch(str(merge_sha)):
            return {"item_id":detail["id"],"status":"unknown","blocker":"github_merge_identity_missing"}
        receipt={"repository":self.config["repository"],"head_sha":head_sha,"merge_commit_sha":merge_sha,
                 "pr_url":expected_url,"merged":True}
        try:
            merged=self.bridge("POST",f"/v1/queue/{detail['id']}/merge",payload=receipt)
        except Exception:
            try:merged=self.bridge("GET",f"/v1/queue/{detail['id']}")
            except Exception:return {"item_id":detail["id"],"status":"unknown","blocker":"merge_receipt_unconfirmed"}
            if merged.get("state")!="merged" or merged.get("merge_receipt")!=receipt:
                return {"item_id":detail["id"],"status":"unknown","blocker":"merge_receipt_unconfirmed"}
        return {"item_id":detail["id"],"status":"merged","merge_commit_sha":merge_sha}
    def run_once(self,status=None):
        status=status or self.bridge("GET","/v1/queue")
        selected=self.candidates(status);results=[self.observe(item) for item in selected]
        if selected:
            cursor=Path(self.config["cursor_file"]);cursor.parent.mkdir(parents=True,exist_ok=True)
            atomic_json(cursor,{"last_id":selected[-1]["id"]})
        return {"status":"idle" if not selected else "observed","polled":len(selected),
                "merged":sum(item["status"]=="merged" for item in results),"results":results}
