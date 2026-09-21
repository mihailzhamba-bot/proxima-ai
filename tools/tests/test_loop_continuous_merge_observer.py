import os,tempfile,time,uuid
from pathlib import Path
import pytest
from tools.loop.continuous_merge_observer import MergeObserver,ObserveError,checked,pull_number,pinned_github_origin

REPO="mihailzhamba-bot/proxima-ai";BRANCH="feat/loop-pilot";HEAD="a"*40;MERGE="b"*40
def config(**changes):
 value={"repository":REPO,"target_branch":BRANCH,"max_polls":4,"timeout_seconds":10,
   "cursor_file":str(Path(tempfile.gettempdir())/("observer-"+uuid.uuid4().hex+".json"))}
 value.update(changes);return value
def candidate(item_id="task-one",number=7):
 return {"id":item_id,"requirement_id":"req","state":"ready_pr","depends_on":[],
   "pr_url":f"https://github.com/{REPO}/pull/{number}","evidence":{"head_sha":HEAD},
   "execution_policy":{"repository":REPO}}
def remote(number=7,**changes):
 value={"number":number,"html_url":f"https://github.com/{REPO}/pull/{number}","merged":True,"state":"closed",
   "head":{"sha":HEAD},"base":{"ref":BRANCH},"merge_commit_sha":MERGE};value.update(changes);return value
class Fixture:
 def __init__(self,detail=None,lost=False):
  self.detail=detail or candidate();self.status={"items":[self.detail]};self.posts=[];self.lost=lost
 def bridge(self,method,path,payload=None):
  if path=="/v1/queue":return self.status
  if method=="GET" and path=="/v1/queue/"+self.detail["id"]:return self.detail
  if method=="POST" and path.endswith("/merge"):
   self.posts.append(payload);self.detail={**self.detail,"state":"merged","merge_receipt":payload}
   self.status={"items":[self.detail]}
   if self.lost:raise TimeoutError("secret transport detail")
   return self.detail
  raise AssertionError((method,path))
def test_exact_merged_pr_records_existing_operator_receipt_and_repeat_is_idle():
 fixture=Fixture();observer=MergeObserver(config(),fixture.bridge,lambda method,path:remote())
 first=observer.run_once();assert first["merged"]==1
 assert fixture.posts==[{"repository":REPO,"head_sha":HEAD,"merge_commit_sha":MERGE,
   "pr_url":f"https://github.com/{REPO}/pull/7","merged":True}]
 assert observer.run_once()=={"status":"idle","polled":0,"merged":0,"results":[]}
def test_lost_bridge_merge_response_reconciles_same_receipt_without_repeat():
 fixture=Fixture(lost=True);observer=MergeObserver(config(),fixture.bridge,lambda method,path:remote())
 result=observer.run_once();assert result["merged"]==1 and len(fixture.posts)==1
 assert observer.run_once()["polled"]==0
@pytest.mark.parametrize("url",[
 "https://github.com/other/repo/pull/7","https://github.com/mihailzhamba-bot/proxima-ai/issues/7",
 "http://github.com/mihailzhamba-bot/proxima-ai/pull/7","https://github.com/mihailzhamba-bot/proxima-ai/pull/07",
 "https://github.com/mihailzhamba-bot/proxima-ai/pull/7?token=x"])
def test_pr_url_must_be_exact_pinned_owner_repo_number(url):
 fixture=Fixture({**candidate(),"pr_url":url});result=MergeObserver(config(),fixture.bridge,lambda *_:remote()).run_once()
 assert result["results"][0]["blocker"]=="pr_url_mismatch" and fixture.posts==[]
@pytest.mark.parametrize("change,blocker",[
 ({"head":{"sha":"c"*40}},"github_head_mismatch"),
 ({"base":{"ref":"main"}},"github_base_mismatch"),
 ({"merge_commit_sha":None},"github_merge_identity_missing"),
 ({"html_url":"https://github.com/other/repo/pull/7"},"github_response_invalid")])
def test_remote_merge_scope_mismatch_never_records_receipt(change,blocker):
 fixture=Fixture();result=MergeObserver(config(),fixture.bridge,lambda *_:remote(**change)).run_once()
 assert result["results"][0]["blocker"]==blocker and fixture.posts==[]
@pytest.mark.parametrize("state,expected_status,blocker",[("open","pending","github_pr_not_merged"),("closed","blocked","github_pr_closed_unmerged")])
def test_unmerged_open_or_closed_pr_leaves_queue_unchanged(state,expected_status,blocker):
 fixture=Fixture();result=MergeObserver(config(),fixture.bridge,lambda *_:remote(merged=False,state=state,merge_commit_sha=None)).run_once()
 assert result["results"][0]=={"item_id":"task-one","status":expected_status,"blocker":blocker}
 assert fixture.detail["state"]=="ready_pr" and fixture.posts==[]
def test_timeout_or_secret_transport_error_is_redacted_and_state_unchanged():
 fixture=Fixture()
 def unavailable(*_args):raise TimeoutError("Bearer super-secret")
 result=MergeObserver(config(),fixture.bridge,unavailable).run_once()
 assert result["results"][0]["blocker"]=="github_observation_unavailable"
 assert "secret" not in str(result) and fixture.posts==[] and fixture.detail["state"]=="ready_pr"
def test_large_ready_set_polls_only_items_needed_by_unfinished_dependencies():
 details={f"ready-{i}":candidate(f"ready-{i}",i) for i in range(1,5)}
 dependent={"id":"future","requirement_id":"req","state":"proposed","depends_on":["ready-4"]}
 status={"items":[*details.values(),dependent]}
 polled=[]
 def bridge(method,path,payload=None):
  if path=="/v1/queue":return status
  item_id=path.rsplit("/",1)[-1]
  if item_id=="future":return dependent
  if method=="GET":return details[item_id]
  raise AssertionError(path)
 def github(method,path):polled.append(path);return remote(4)
 result=MergeObserver(config(),bridge,github).run_once(status)
 assert result["polled"]==1 and polled==[f"/repos/{REPO}/pulls/4"]
def test_config_and_url_parsing_fail_closed():
 with pytest.raises(ObserveError):checked(config(repository="other/repo"))
 with pytest.raises(ObserveError):checked(config(target_branch="main"))
 with pytest.raises(ObserveError):checked(config(timeout_seconds=31))
 assert pull_number(f"https://github.com/{REPO}/pull/9",REPO)==9


def test_round_robin_cursor_prevents_early_unmerged_pr_starvation(tmp_path):
 details={f"ready-{i}":candidate(f"ready-{i}",i) for i in range(1,5)}
 status={"items":[*details.values(),{"id":"future","state":"proposed","depends_on":list(details)}]}
 polled=[]
 def bridge(method,path,payload=None):
  if path=="/v1/queue":return status
  return details[path.rsplit("/",1)[-1]]
 def github(method,path):
  polled.append(path);number=int(path.rsplit("/",1)[-1])
  return remote(number,merged=False,state="open",merge_commit_sha=None)
 observer=MergeObserver(config(max_polls=2,cursor_file=str(tmp_path/"cursor.json")),bridge,github)
 observer.run_once(status);observer.run_once(status)
 assert polled==[f"/repos/{REPO}/pulls/{i}" for i in (1,2,3,4)]

def test_absolute_deadline_bounds_trickling_or_stalled_github_call():
 fixture=Fixture()
 def stalled(*_args):time.sleep(2);return remote()
 started=time.monotonic()
 result=MergeObserver(config(timeout_seconds=1),fixture.bridge,stalled).run_once()
 assert time.monotonic()-started<1.5
 assert result["results"][0]["blocker"]=="github_observation_unavailable"

def test_github_origin_is_exactly_pinned():
 assert pinned_github_origin("https://api.github.com")=="https://api.github.com"
 for value in ("https://github.example","http://127.0.0.1:1","https://api.github.com.evil"):
  with pytest.raises(ObserveError):pinned_github_origin(value)
