import hashlib,json,os,subprocess,threading
import pytest
from pathlib import Path
from tools.loop.continuous_queue import ContinuousQueue,QueueError,digest
from tools.loop.continuous_base_refresh import BaseRefresher,RefreshError,regenerate_policy,checked,trusted_fetch_env,validate_source_repo
from tools.tests.test_loop_continuous_queue import policy,planner,proposal,register

NEW="9"*40
def refreshed(original,head=NEW):
 value=json.loads(json.dumps(original))
 for key,item in value["requirements"].items():
  item["base_sha"]=head
  item["source_evidence"]=[{"ref":f"git:{head}:fixture","sha256":"8"*64,"summary":"trusted refreshed evidence"}]
 return value
def refresh_receipt(target,old_fp,new_fp,bundle="7"*64):
 return {"target":target,"old_policy_fingerprint":old_fp,"new_policy_fingerprint":new_fp,
  "new_head":NEW,"bundle_sha256":bundle,"installed_sha256":hashlib.sha256(target.encode()).hexdigest()}
def prepare(q,new_policy=None,key="base-refresh-999999999999"):
 new_policy=new_policy or refreshed(q.policy);bundle="7"*64
 q.begin_refresh(key,NEW);state=q.prepare_refresh(key,new_policy,bundle)
 for target in ("bridge","harper","worker"):q.refresh_receipt(key,refresh_receipt(target,state["old_policy_fingerprint"],state["new_policy_fingerprint"],bundle))
 return key,state
def test_refresh_rebases_only_never_started_and_preserves_published_history(tmp_path):
 old=policy();q=ContinuousQueue(tmp_path/"q.db",old)
 q.propose(proposal(),*planner(q));register(q);published=q.claim()
 q.update(published["id"],published["lease_id"],"ready_pr",head_sha="a"*40,pr_url="https://github.com/acme/repo/pull/1")
 safe=proposal(proposal_id="safe-slice",slice_key="slice-two");q.propose(safe,*planner(q));register(q,"safe-slice")
 old_safe=q.get("safe-slice");old_published=q.get("wb-small-task");new_policy=refreshed(old)
 key,state=prepare(q,new_policy);result=q.commit_refresh(key)
 assert result["state"]=="complete" and result["rebased"]==["safe-slice"]
 rebased=q.get("safe-slice");kept=q.get("wb-small-task")
 assert rebased["state"]=="proposed" and rebased["base_sha"]==NEW and rebased["review_fingerprint"] is None
 assert rebased["receipts"]=={} and rebased["proposal_fingerprint"]!=old_safe["proposal_fingerprint"]
 assert kept["state"]=="ready_pr" and kept["base_sha"]==old_published["base_sha"] and kept["policy_fingerprint"]==old_published["policy_fingerprint"]
 with q.db() as db:
  history=db.execute("SELECT snapshot FROM continuous_queue_history WHERE item_id='safe-slice'").fetchall()
 assert len(history)==1 and json.loads(history[0][0])["row"]["proposal_fingerprint"]==old_safe["proposal_fingerprint"] and len(json.loads(history[0][0])["receipts"])==3
 assert q.commit_refresh(key)["state"]=="complete"
def test_authority_change_and_mismatched_head_are_rejected(tmp_path):
 q=ContinuousQueue(tmp_path/"q.db",policy());q.begin_refresh("base-refresh-999999999999",NEW)
 changed=refreshed(q.policy);changed["requirements"]["wb-task"]["objective"]="expanded authority"
 with pytest.raises(QueueError,match="authority"):q.prepare_refresh("base-refresh-999999999999",changed,"7"*64)
 wrong=refreshed(q.policy,"6"*40)
 with pytest.raises(QueueError,match="head"):q.prepare_refresh("base-refresh-999999999999",wrong,"7"*64)
def test_active_attempt_legacy_job_and_planner_block_maintenance(tmp_path):
 for blocker in ("attempt","job","planning"):
  q=ContinuousQueue(tmp_path/(blocker+".db"),policy());q.propose(proposal(),*planner(q));register(q)
  if blocker=="attempt":q.claim()
  elif blocker=="job":
   with q.db() as db:
    db.execute("CREATE TABLE jobs(id TEXT,state TEXT,publication_active INTEGER)")
    db.execute("INSERT INTO jobs VALUES('legacy','queued',0)")
  else:
   with q.db() as db:
    db.execute("CREATE TABLE operations(id TEXT,state TEXT)")
    db.execute("INSERT INTO operations VALUES('plan','unknown')")
  with pytest.raises(QueueError,match="blocked"):q.begin_refresh("base-refresh-999999999999",NEW)
def test_explicit_pause_is_preserved_while_maintenance_blocks_claims(tmp_path):
 q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
 with q.db() as db:
  db.execute("CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT)")
  db.execute("INSERT INTO settings VALUES('paused','true')")
 q.begin_refresh("base-refresh-999999999999",NEW)
 assert q.claim() is None
 with q.db() as db:assert db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]=="true"
def test_partial_receipts_and_restart_resume_same_intent(tmp_path):
 db=tmp_path/"q.db";old=policy();new=refreshed(old);q=ContinuousQueue(db,old)
 q.propose(proposal(),*planner(q));state=q.begin_refresh("base-refresh-999999999999",NEW)
 prepared=q.prepare_refresh(state["key"],new,"7"*64)
 first=refresh_receipt("bridge",prepared["old_policy_fingerprint"],prepared["new_policy_fingerprint"]);q.refresh_receipt(state["key"],first)
 restarted=ContinuousQueue(db,new)
 assert set(restarted.maintenance()["receipts"])=={"bridge"}
 assert restarted.refresh_receipt(state["key"],first)["receipts"]["bridge"]==first
 for target in ("harper","worker"):restarted.refresh_receipt(state["key"],refresh_receipt(target,prepared["old_policy_fingerprint"],prepared["new_policy_fingerprint"]))
 assert restarted.commit_refresh(state["key"])["state"]=="complete"
def test_parallel_refresh_receipts_are_not_lost(tmp_path,monkeypatch):
 q=ContinuousQueue(tmp_path/"q.db",policy());state=q.begin_refresh("base-refresh-999999999999",NEW)
 prepared=q.prepare_refresh(state["key"],refreshed(q.policy),"7"*64)
 original=q.maintenance;barrier=threading.Barrier(2);counter=[0];lock=threading.Lock()
 def synchronized_read():
  value=original()
  with lock:counter[0]+=1;number=counter[0]
  if number<=2:barrier.wait(timeout=5)
  return value
 monkeypatch.setattr(q,"maintenance",synchronized_read)
 errors=[]
 def submit(target):
  try:q.refresh_receipt(state["key"],refresh_receipt(target,prepared["old_policy_fingerprint"],prepared["new_policy_fingerprint"]))
  except Exception as error:errors.append(error)
 threads=[threading.Thread(target=submit,args=(target,)) for target in ("bridge","harper")]
 for thread in threads:thread.start()
 for thread in threads:thread.join(timeout=10)
 assert not errors and set(original()["receipts"])=={"bridge","harper"}


def test_old_review_completion_cannot_land_after_refresh(tmp_path):
 q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));old=q.get("wb-small-task")
 key,_=prepare(q);q.commit_refresh(key)
 with pytest.raises(QueueError):q.review("wb-small-task",{"proposal_fingerprint":old["proposal_fingerprint"],"verdict":"approve","reviewer":"old","checks":{"policy":"pass","scope":"pass","dependencies":{},"duplicates":{"status":"pass","compared":[],"duplicate_of":None}}})
 with pytest.raises(QueueError):q.update("wb-small-task","old-lease","ready_pr",head_sha="a"*40,pr_url="https://github.com/acme/repo/pull/1")
 with pytest.raises(QueueError):q.retry("wb-small-task",{"stopped":True,"previous_lease_id":"old-lease","external_run_id":"old","external_job_id":"old","evidence_ref":"old.json","reason":"transport_unknown"})



def refresher_config(tmp_path):
 token=tmp_path/"github-token";token.write_text("fixture-token");token.chmod(0o600)
 return {"repository":"mihailzhamba-bot/proxima-ai","target_branch":"feat/loop-pilot",
  "source_repo":str(tmp_path/"repo"),"policy_file":str(tmp_path/"policy.json"),
  "github_token_file":str(tmp_path/"github-token"),
  "state_root":str(tmp_path/"state"),"max_bundle_bytes":33554432,"github_timeout_seconds":10,
  "receivers":{target:["/trusted/"+target] for target in ("bridge","harper","worker")}}

def test_unmerged_branch_head_equal_to_pinned_base_is_idle(tmp_path):
 old=policy();base=old["requirements"]["wb-task"]["base_sha"]
 status={"policy_fingerprint":digest(old),"items":[{"id":"safe","state":"proposed","base_sha":base}],"maintenance":None}
 def bridge(method,path,payload=None):
  if path=="/v1/queue/safe":return {"base_sha":base}
  raise AssertionError(path)
 github=lambda *_:{"ref":"refs/heads/feat/loop-pilot","object":{"type":"commit","sha":base}}
 assert BaseRefresher(refresher_config(tmp_path),bridge,github).run_once(status)=={"status":"idle","reason":"base_current"}

def test_untrusted_or_missing_ref_is_explicit_blocker(tmp_path):
 refresher=BaseRefresher(refresher_config(tmp_path),lambda *_:{},lambda *_:{"ref":"refs/heads/main","object":{"type":"commit","sha":"a"*40}})
 with pytest.raises(RefreshError,match="branch head"):refresher.observed_head()

def test_trusted_source_evidence_is_regenerated_from_new_head(tmp_path):
 repo=tmp_path/"repo";repo.mkdir();os.system(f"git -C {repo} init -q")
 os.system(f"git -C {repo} config user.name Fixture");os.system(f"git -C {repo} config user.email fixture@invalid")
 path=repo/"services/collector/src/wb";path.mkdir(parents=True);(path/"observations.ts").write_text("trusted new source\n")
 os.system(f"git -C {repo} add .");os.system(f"git -C {repo} commit -qm base");head=os.popen(f"git -C {repo} rev-parse HEAD").read().strip()
 old=policy();new=regenerate_policy(old,head,repo);evidence=new["requirements"]["wb-task"]["source_evidence"]
 assert all(item["ref"].startswith("git:"+head+":") for item in evidence)
 assert any("trusted new source" in item["summary"] for item in evidence)

def test_toolchain_change_blocks_before_bundle_or_receivers(tmp_path,monkeypatch):
 monkeypatch.setattr("tools.loop.continuous_base_refresh.ROOT_UID",os.getuid());monkeypatch.setattr("tools.loop.continuous_base_refresh.validate_source_repo",lambda _repo:None)
 old=policy();new_head="9"*40;cfg=refresher_config(tmp_path)
 Path(cfg["policy_file"]).write_text(json.dumps(old));(Path(cfg["source_repo"])/".git").mkdir(parents=True)
 status={"policy_fingerprint":digest(old),"items":[{"id":"safe","state":"proposed","base_sha":"a"*40}],"maintenance":None}
 class Fixture(BaseRefresher):
  def observed_head(self):return new_head
  def git(self,args,**kwargs):
   if args[0]=="rev-parse":return new_head
   if args[0]=="diff":return "package-lock.json"
   return ""
 calls=[]
 def bridge(method,path,payload=None):
  calls.append(path)
  if path=="/v1/queue/safe":return {"base_sha":"a"*40}
  if path.endswith("/begin"):return {"key":"base-refresh-"+new_head[:12],"new_head":new_head,"old_policy_fingerprint":digest(old),"state":"fetching"}
  raise AssertionError(path)
 with pytest.raises(RefreshError,match="toolchain"):Fixture(cfg,bridge,lambda *_:{}).run_once(status)
 assert not any(path.endswith("/prepare") for path in calls)
def test_base_refresh_config_is_closed():
 with pytest.raises(RefreshError):checked({"repository":"other/repo"})


def test_bridge_restart_with_new_policy_resumes_old_safe_template_projection(tmp_path):
 db=tmp_path/"q.db";old=policy();new=refreshed(old);q=ContinuousQueue(db,old)
 q.propose(proposal(),*planner(q));register(q)
 intent=q.begin_refresh("base-refresh-999999999999",NEW)
 q.prepare_refresh(intent["key"],new,"7"*64)
 restarted=ContinuousQueue(db,new)
 prepared=restarted.prepare_refresh(intent["key"],new,"7"*64)
 assert prepared["rebase_templates"]==["continuous-wb-small-task"]


def test_refresh_resume_keeps_recorded_head_when_branch_advances(tmp_path,monkeypatch):
 monkeypatch.setattr("tools.loop.continuous_base_refresh.ROOT_UID",os.getuid());monkeypatch.setattr("tools.loop.continuous_base_refresh.validate_source_repo",lambda _repo:None)
 old=policy();head="9"*40;tip="8"*40;cfg=refresher_config(tmp_path)
 Path(cfg["policy_file"]).write_text(json.dumps(old));(Path(cfg["source_repo"])/".git").mkdir(parents=True)
 status={"policy_fingerprint":digest(old),"items":[],"maintenance":{"state":"fetching","key":"base-refresh-"+head[:12],
  "new_head":head,"old_policy_fingerprint":digest(old)}}
 calls=[]
 class Fixture(BaseRefresher):
  def git(self,args,**kwargs):
   calls.append(args)
   if args[0]=="rev-parse":return tip if "base-refresh-tip" in args[1] else head
   if args[0]=="diff":return "package-lock.json"
   return ""
 with pytest.raises(RefreshError,match="toolchain"):Fixture(cfg,lambda *_:{},lambda *_:{}).run_once(status)
 assert ["merge-base","--is-ancestor",head,tip] in calls
 assert ["update-ref","refs/loop/base-refresh/"+head,head] in calls


def test_maintenance_fence_is_rechecked_inside_queue_mutations(tmp_path):
 q=ContinuousQueue(tmp_path/"q.db",policy());row=q.propose(proposal(),*planner(q))
 q.begin_refresh("base-refresh-999999999999",NEW)
 receipt={"proposal_fingerprint":row["proposal_fingerprint"],"verdict":"approve","reviewer":"reviewer",
  "checks":{"policy":"pass","scope":"pass","dependencies":{},"duplicates":{"status":"pass","compared":[],"duplicate_of":None}}}
 with pytest.raises(QueueError,match="maintenance"):q.review(row["id"],receipt)
 with pytest.raises(QueueError,match="maintenance"):q.propose(proposal(proposal_id="other",slice_key="slice-two"),*planner(q))


def test_git_credentials_use_temporary_askpass_without_secret_in_environment(tmp_path,monkeypatch):
 monkeypatch.setattr("tools.loop.continuous_base_refresh.ROOT_UID",os.getuid())
 token=tmp_path/"token";token.write_text("private-value");token.chmod(0o600);state=tmp_path/"state";state.mkdir()
 with trusted_fetch_env(str(token),state) as env:
  script=Path(env["GIT_ASKPASS"]);assert script.is_file() and script.stat().st_mode&0o777==0o700
  assert "private-value" not in json.dumps(env) and "private-value" not in script.read_text()
  assert subprocess.check_output([str(script),"Username for github"],text=True).strip()=="x-access-token"
 assert not script.exists()
 token.chmod(0o644)
 with pytest.raises(RefreshError,match="credential"):
  with trusted_fetch_env(str(token),state):pass


def test_stale_registration_receipt_cannot_cross_maintenance_boundary(tmp_path):
 q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
 row=q.get("wb-small-task");q.begin_refresh("base-refresh-999999999999",NEW)
 receipt={"target":"bridge","template_fingerprint":row["template_fingerprint"],
  "policy_fingerprint":row["policy_fingerprint"],"installed_sha256":hashlib.sha256(b"bridge").hexdigest()}
 with pytest.raises(QueueError,match="maintenance"):q.receipt(row["id"],receipt)


def test_control_source_accepts_only_pinned_linked_worktree_common_dir(tmp_path,monkeypatch):
 bare=tmp_path/"common.git";main=tmp_path/"main";linked=tmp_path/"linked"
 subprocess.run(["git","init","--bare","-q",str(bare)],check=True)
 subprocess.run(["git","clone","-q",str(bare),str(main)],check=True)
 subprocess.run(["git","-C",str(main),"config","user.name","Fixture"],check=True)
 subprocess.run(["git","-C",str(main),"config","user.email","fixture@invalid"],check=True)
 (main/"tracked").write_text("x");subprocess.run(["git","-C",str(main),"add","tracked"],check=True);subprocess.run(["git","-C",str(main),"commit","-qm","base"],check=True)
 subprocess.run(["git","-C",str(main),"push","-q","origin","HEAD:master"],check=True)
 subprocess.run(["git","--git-dir",str(bare),"worktree","add","-q",str(linked),"master"],check=True)
 assert (linked/".git").is_file()
 monkeypatch.setattr("tools.loop.continuous_base_refresh.ROOT_UID",os.getuid());monkeypatch.setattr("tools.loop.continuous_base_refresh.CONTROL_GIT_COMMON_DIR",bare)
 assert validate_source_repo(linked)==bare.resolve()
 monkeypatch.setattr("tools.loop.continuous_base_refresh.CONTROL_GIT_COMMON_DIR",tmp_path/"other.git")
 with pytest.raises(RefreshError,match="common directory"):validate_source_repo(linked)


def test_first_refresh_creates_private_state_root_before_askpass(tmp_path,monkeypatch):
 cfg=refresher_config(tmp_path);state=Path(cfg["state_root"]);assert not state.exists()
 old=policy();base=old["requirements"]["wb-task"]["base_sha"]
 result=BaseRefresher(cfg,lambda *_: {},lambda *_:{"ref":"refs/heads/feat/loop-pilot","object":{"type":"commit","sha":base}}).run_once(
  {"policy_fingerprint":digest(old),"items":[{"id":"safe","state":"proposed","base_sha":base}],"maintenance":None})
 assert result=={"status":"idle","reason":"base_current"} and state.is_dir() and state.stat().st_mode&0o777==0o700
