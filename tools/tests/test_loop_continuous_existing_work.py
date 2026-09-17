import pytest
from tools.loop.continuous_existing_work import ExistingWorkObserver,ExistingWorkError,REPOSITORY,BASE
from tools.loop.continuous_queue import ContinuousQueue,QueueError
from tools.loop.bridge import Bridge
from tools.tests.test_loop_continuous_queue import policy,planner,proposal
HEAD="a"*40

def config():return {"repository":REPOSITORY,"base":BASE,"max_per_tick":4,"timeout_seconds":10}
def candidate(url=None,head=HEAD):return {"job_id":"night-real-job","template":"night-observation-v1","pr_url":url or f"https://github.com/{REPOSITORY}/pull/143","head_sha":head}
def detail(**changes):
 value={"html_url":f"https://github.com/{REPOSITORY}/pull/143","number":143,"state":"open","merged":False,"head":{"sha":HEAD,"repo":{"full_name":REPOSITORY}},"base":{"ref":BASE,"repo":{"full_name":REPOSITORY}},"changed_files":1,"title":"Preserve WB raw observations","body":"Keeps raw evidence while normalizing observations."};value.update(changes);return value

def test_observer_verifies_actual_candidate_and_is_idempotent():
 posts=[]
 def bridge(method,path,payload=None):posts.append(payload);return payload
 def github(method,path):return [{"filename":"services/collector/src/wb/observations.ts"}] if path.endswith("files?per_page=100") else detail()
 observer=ExistingWorkObserver(config(),bridge,github);status={"legacy_ready_pr_candidates":[candidate()],"existing_work":[]}
 assert observer.run_once(status)["verified_jobs"]==["night-real-job"]
 receipt=posts[0];assert receipt["pr_number"]==143 and receipt["head_sha"]==HEAD and receipt["github_state"]=="open" and receipt["files"]==["services/collector/src/wb/observations.ts"]
 assert observer.run_once({**status,"existing_work":[{**receipt,"fingerprint":"f"*64}]})=={"status":"complete","verified":1}

@pytest.mark.parametrize("change",[
 {"html_url":"https://github.com/other/repo/pull/143"},{"head":{"sha":"b"*40}},{"base":{"ref":"main"}},{"merged":True}])
def test_observer_rejects_wrong_repository_head_base_or_closed(change):
 def github(method,path):return [{"filename":"x"}] if path.endswith("files?per_page=100") else detail(**change)
 with pytest.raises(ExistingWorkError,match="mismatch"):ExistingWorkObserver(config(),lambda *_:None,github).run_once({"legacy_ready_pr_candidates":[candidate()],"existing_work":[]})

def test_github_unknown_leaves_bridge_unchanged():
 posts=[]
 def github(*_):raise TimeoutError("offline")
 with pytest.raises(TimeoutError):ExistingWorkObserver(config(),lambda *args,**kwargs:posts.append(args),github).run_once({"legacy_ready_pr_candidates":[candidate()],"existing_work":[]})
 assert posts==[]

def queue_with_job(tmp_path):
 q=ContinuousQueue(tmp_path/"q.db",policy());repo=next(iter(q.policy["requirements"].values()))["repository"]
 with q.db() as db:
  db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,template TEXT,state TEXT,pr_url TEXT,candidate_sha TEXT)")
  db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)",("night-real-job","night-observation-v1","ready_pr",f"https://github.com/{repo}/pull/143",HEAD))
 return q,repo

def test_queue_binds_receipt_to_live_ready_pr_job_and_exposes_catalog(tmp_path):
 q,repo=queue_with_job(tmp_path);receipt={"job_id":"night-real-job","template":"night-observation-v1","pr_url":f"https://github.com/{repo}/pull/143","pr_number":143,"head_sha":HEAD,"base_ref":BASE,"github_state":"open","merge_commit_sha":None,"title":"WB observation","body":"accepted scope","files":["services/x.ts"]}
 saved=q.existing_work_receipt(receipt);status=q.status()
 assert status["legacy_ready_pr_candidates"][0]["job_id"]=="night-real-job" and status["existing_work"][0]["fingerprint"]==saved["fingerprint"]
 with q.db() as db:db.execute("UPDATE jobs SET candidate_sha=? WHERE id=?",("b"*40,"night-real-job"))
 assert q.status()["existing_work"]==[]
 with pytest.raises(QueueError,match="job changed"):q.existing_work_receipt(receipt)


def test_queue_requires_legacy_fingerprint_in_semantic_review(tmp_path):
 q,repo=queue_with_job(tmp_path);receipt={"job_id":"night-real-job","template":"night-observation-v1","pr_url":f"https://github.com/{repo}/pull/143","pr_number":143,"head_sha":HEAD,"base_ref":BASE,"github_state":"open","merge_commit_sha":None,"title":"WB observation","body":"accepted scope","files":["services/x.ts"]}
 fingerprint=q.existing_work_receipt(receipt)["fingerprint"];row=q.propose(proposal(),*planner(q))
 approval={"proposal_fingerprint":row["proposal_fingerprint"],"verdict":"approve","reviewer":"independent",
  "checks":{"policy":"pass","scope":"pass","dependencies":{},"duplicates":{"status":"pass","compared":[fingerprint],"duplicate_of":None}}}
 assert q.review(row["id"],approval)["state"]=="registering"


def test_observer_preserves_verified_merged_and_closed_work():
 for state,merged,expected in (("closed",True,"merged"),("closed",False,"closed_unmerged")):
  posts=[]
  def github(method,path):
   if path.endswith("files?per_page=100"):return [{"filename":"services/x.ts"}]
   return detail(state=state,merged=merged,merge_commit_sha="c"*40 if merged else None)
  result=ExistingWorkObserver(config(),lambda method,path,payload=None:posts.append(payload),github).run_once({"legacy_ready_pr_candidates":[candidate()],"existing_work":[]})
  assert result["status"]=="complete" and posts[0]["github_state"]==expected

def test_observer_rejects_candidate_overflow_without_github_call():
 calls=[]
 with pytest.raises(ExistingWorkError,match="exceeds bound"):
  ExistingWorkObserver(config(),lambda *_:None,lambda *args:calls.append(args)).run_once({"legacy_ready_pr_overflow":True,"legacy_ready_pr_candidates":[],"existing_work":[]})
 assert calls==[]


def test_planner_envelope_contains_verified_existing_work():
 existing={"job_id":"legacy","title":"Existing WB change","body":"criteria","files":["services/x.ts"],"github_state":"open","fingerprint":"f"*64,"pr_url":f"https://github.com/{REPOSITORY}/pull/143"}
 class Queue:
  policy=policy();policy_fingerprint="a"*64
  def maintenance_active(self):return False
  def status(self):return {"planning_snapshot":"b"*64,"items":[],"existing_work":[existing],"eligible_requirements":["wb-task"],"plan_exhausted":False}
 bridge=Bridge.__new__(Bridge);bridge.continuous=Queue();seen=[]
 bridge.create=lambda kind,key,payload:seen.append(payload) or {"run_id":"planner"}
 assert bridge.plan_continuous("plan-key")=={"run_id":"planner"}
 assert seen[0]["queue"]["existing_work"]==[existing]
