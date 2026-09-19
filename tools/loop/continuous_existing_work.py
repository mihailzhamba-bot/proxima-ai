"""Verify legacy ready PR jobs as semantic duplicate context; never mutates GitHub."""
from __future__ import annotations
import re
REPOSITORY="mihailzhamba-bot/proxima-ai";BASE="feat/loop-pilot";SHA=re.compile(r"^[0-9a-f]{40}$")
try:from .continuous_base_refresh import deadline_call
except ImportError:from continuous_base_refresh import deadline_call
class ExistingWorkError(ValueError):pass
class ExistingWorkObserver:
 def __init__(self,config,bridge_call,github_call):
  if (not isinstance(config,dict) or config.get("repository")!=REPOSITORY or config.get("base")!=BASE
      or config.get("max_per_tick") not in range(1,17) or config.get("timeout_seconds")!=10):raise ExistingWorkError("invalid existing-work observer config")
  self.config,self.bridge,self.github=config,bridge_call,github_call
 def run_once(self,status):
  if status.get("legacy_ready_pr_overflow"):raise ExistingWorkError("legacy ready PR catalog exceeds bound")
  candidates=status.get("legacy_ready_pr_candidates",[]);verified={v.get("job_id") for v in status.get("existing_work",[])}
  pending=[v for v in candidates if v.get("job_id") not in verified]
  if not pending:return {"status":"complete","verified":len(verified)}
  completed=[]
  for item in pending[:self.config["max_per_tick"]]:
   match=re.fullmatch(r"https://github\.com/"+re.escape(REPOSITORY)+r"/pull/([1-9][0-9]*)",str(item.get("pr_url","")))
   if (not match or not SHA.fullmatch(str(item.get("head_sha",""))) or not isinstance(item.get("template"),str)):raise ExistingWorkError("invalid legacy ready PR candidate")
   number=int(match.group(1));detail=deadline_call(self.github,self.config["timeout_seconds"],"GET",f"/repos/{REPOSITORY}/pulls/{number}")
   if (not isinstance(detail,dict) or detail.get("html_url")!=item["pr_url"] or detail.get("number")!=number
       or detail.get("state") not in {"open","closed"} or (detail.get("head") or {}).get("sha")!=item["head_sha"]
       or ((detail.get("head") or {}).get("repo") or {}).get("full_name")!=REPOSITORY
       or (detail.get("base") or {}).get("ref")!=BASE or ((detail.get("base") or {}).get("repo") or {}).get("full_name")!=REPOSITORY):raise ExistingWorkError("legacy ready PR GitHub evidence mismatch")
   merged=detail.get("merged") is True
   if detail["state"]=="open" and merged:raise ExistingWorkError("legacy ready PR GitHub evidence mismatch")
   github_state="merged" if merged else ("open" if detail["state"]=="open" else "closed_unmerged")
   merge_sha=detail.get("merge_commit_sha") if merged else None
   if merged and not SHA.fullmatch(str(merge_sha)):raise ExistingWorkError("legacy merged PR receipt unavailable")
   if not isinstance(detail.get("changed_files"),int) or detail["changed_files"]<1 or detail["changed_files"]>100:raise ExistingWorkError("legacy ready PR file evidence exceeds bound")
   files=deadline_call(self.github,self.config["timeout_seconds"],"GET",f"/repos/{REPOSITORY}/pulls/{number}/files?per_page=100")
   if (not isinstance(files,list) or not files or len(files)>100
       or detail.get("changed_files")!=len(files)):raise ExistingWorkError("legacy ready PR file evidence unavailable")
   names=[v.get("filename") for v in files]
   if any(not isinstance(v,str) or not v or len(v)>500 for v in names):raise ExistingWorkError("invalid legacy ready PR files")
   title=detail.get("title") or "";body=detail.get("body") or ""
   if not isinstance(title,str) or len(title)>500 or not isinstance(body,str) or len(body)>10_000:raise ExistingWorkError("legacy ready PR text exceeds bound")
   receipt={"job_id":item["job_id"],"template":item["template"],"pr_url":item["pr_url"],"pr_number":number,
            "head_sha":item["head_sha"],"base_ref":BASE,"github_state":github_state,"merge_commit_sha":merge_sha,
            "title":title,"body":body,"files":names}
   self.bridge("POST","/v1/queue/existing-work",payload=receipt);completed.append(item["job_id"])
  return {"status":"complete" if len(pending)<=len(completed) else "partial","verified_jobs":completed}
