import hashlib,json,threading
import pytest
from tools.loop.continuous_queue import ContinuousQueue,QueueError,digest,validate_policy
from tools.loop.bridge import Bridge,BridgeError,JsonHTTP,server

BASE="a"*40
PROFILE="73bf9c3a-ab69-4b2e-a7f0-e808df8f2614"
def policy(paths=None,depends=None):
    return {"policy_id":"wb-plan-v1","plan_fingerprint":"b"*64,"requirements":{"wb-task":{
        "repository":"acme/repo","max_slices":2,"objective":"Approved WB work","acceptance":["must pass"],"acceptance_profile":"wb-daily-packaging","path_sets":{"default":{"description":"fixture set","allowed_paths":paths or ["services/collector/src/wb/observations.ts"],"contract_files":["AGENTS.md"],"acceptance_profile":"wb-daily-packaging"}},"source_evidence":[{"ref":"git:fixture","sha256":"8"*64,"summary":"Bounded source facts."}],"base_sha":BASE,"allowed_paths":paths or ["services/collector/src/wb/observations.ts"],
        "contract_files":["AGENTS.md"],"profile":"fedor","profile_id":PROFILE,"profile_revision":0,
        "depends_on":depends or []}}}
def planner(q,state="running"):
    run={"id":"planner-local","kind":"hermes","key":"paperclip-external","generation":1,"state":state,"request":"{}"}
    parent={"id":"paperclip-local","kind":"paperclip","external_id":"paperclip-external","generation":1,"state":"running",
        "request":json.dumps({"source":"continuous_planning","policy_fingerprint":q.policy_fingerprint})}
    return run,parent
def proposal(**values):
    return {"proposal_id":"wb-small-task","requirement_id":"wb-task","slice_key":"slice-one","path_set_id":"default","planner_run_id":"planner-local",
        "planner_generation":1,"goal":"Implement one bounded WB improvement","acceptance":["fixture verification passes"],
        "depends_on":[],**values}
def approve(q,item="wb-small-task",dependencies=None):
    row=q.get(item)
    with q.db() as db:
        compared=sorted(r[0] for r in db.execute("SELECT proposal_fingerprint FROM continuous_queue WHERE requirement_id=? AND id!=?",(row["requirement_id"],item)))
    return q.review(item,{"proposal_fingerprint":row["proposal_fingerprint"],"verdict":"approve",
        "reviewer":"independent-reviewer","checks":{"policy":"pass","scope":"pass","dependencies":dependencies or {},
        "duplicates":{"status":"pass","compared":compared,"duplicate_of":None}}})
def register(q,item="wb-small-task",dependencies=None):
    reviewed=approve(q,item,dependencies)
    for target in ("bridge","harper","worker"):
        q.receipt(item,{"target":target,"template_fingerprint":reviewed["template_fingerprint"],
            "policy_fingerprint":q.policy_fingerprint,"installed_sha256":hashlib.sha256(target.encode()).hexdigest()})
    return q.get(item)

def test_policy_rejects_broad_control_authority_but_allows_exact_seed_paths(tmp_path):
    with pytest.raises(QueueError,match="path sets|control authority"):validate_policy(policy(["tools/"]))
    validate_policy(policy(["tools/loop/wb_daily_status.py","tools/tests/test_wb_daily_status.py"]))

def test_proposal_requires_real_persisted_paperclip_identity(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy())
    with pytest.raises(QueueError,match="Paperclip"):q.propose(proposal(),*planner(q,state="unknown"))
    bad=proposal(planner_run_id="invented")
    with pytest.raises(QueueError,match="Paperclip"):q.propose(bad,*planner(q))
    row=q.propose(proposal(),*planner(q))
    assert row["state"]=="proposed" and row["base_sha"]==BASE
    assert row["allowed_paths"]==["services/collector/src/wb/observations.ts"]

def test_exact_review_and_all_three_receipts_are_required(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());row=q.propose(proposal(),*planner(q))
    with pytest.raises(QueueError,match="exact proposal"):q.review(row["id"],{"proposal_fingerprint":"0"*64,"verdict":"approve","reviewer":"reviewer","checks":{"policy":"pass","scope":"pass","dependencies":{},"duplicates":{"status":"pass","compared":[],"duplicate_of":None}}})
    reviewed=approve(q)
    assert reviewed["state"]=="registering" and reviewed["template"]["profile"]=="fedor"
    for target in ("bridge","harper"):
        assert q.receipt(row["id"],{"target":target,"template_fingerprint":reviewed["template_fingerprint"],"policy_fingerprint":q.policy_fingerprint,"installed_sha256":hashlib.sha256(target.encode()).hexdigest()})["state"]=="registering"
    ready=q.receipt(row["id"],{"target":"worker","template_fingerprint":reviewed["template_fingerprint"],"policy_fingerprint":q.policy_fingerprint,"installed_sha256":hashlib.sha256(b"worker").hexdigest()})
    assert ready["state"]=="ready" and set(ready["receipts"])=={"bridge","harper","worker"}

def test_global_lease_duplicate_claim_and_ready_pr_evidence(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
    claimed=q.claim();assert claimed["state"]=="dispatching" and claimed["attempts"]==1
    assert q.claim() is None
    with pytest.raises(QueueError,match="evidence"):q.update(claimed["id"],claimed["lease_id"],"ready_pr",pr_url="https://example.test/pr/1")
    done=q.update(claimed["id"],claimed["lease_id"],"ready_pr",head_sha="d"*40,pr_url="https://example.test/pr/1",evidence_ref="receipt.json")
    assert done["state"]=="ready_pr" and done["lease_id"] is None

def test_dependency_waits_for_ready_pr_not_ready(tmp_path):
    p=policy();p["requirements"]["dependent"]={**p["requirements"]["wb-task"],"depends_on":["wb-small-task"]}
    q=ContinuousQueue(tmp_path/"q.db",p)
    q.propose(proposal(),*planner(q));register(q)
    second=proposal(proposal_id="dependent-job",slice_key="slice-two",requirement_id="dependent",depends_on=["wb-small-task"])
    q.propose(second,*planner(q))
    first=q.claim();assert first["id"]=="wb-small-task"
    q.update(first["id"],first["lease_id"],"blocked",blocker="fixture")
    assert q.claim() is None



def test_stable_slice_key_prevents_renamed_duplicate(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q))
    with pytest.raises(QueueError,match="slice"):
        q.propose(proposal(proposal_id="renamed-job"),*planner(q))

def test_dependency_needs_exact_head_merge_receipt(tmp_path):
    p=policy();p["requirements"]["dependent"]={**p["requirements"]["wb-task"],"depends_on":["wb-small-task"]}
    q=ContinuousQueue(tmp_path/"q.db",p);q.propose(proposal(),*planner(q));register(q)
    second=proposal(proposal_id="dependent-job",slice_key="slice-two",requirement_id="dependent",depends_on=["wb-small-task"])
    q.propose(second,*planner(q))
    with pytest.raises(QueueError,match="ancestry"):approve(q,"dependent-job")
    first=q.claim();head="d"*40;url="https://github.com/acme/repo/pull/1"
    q.update(first["id"],first["lease_id"],"ready_pr",head_sha=head,pr_url=url,evidence_ref="candidate.json")
    assert q.claim() is None
    with pytest.raises(QueueError,match="merge receipt"):
        q.merge(first["id"],{"repository":"acme/repo","head_sha":"e"*40,"merge_commit_sha":"f"*40,"pr_url":url,"merged":True})
    q.merge(first["id"],{"repository":"acme/repo","head_sha":head,"merge_commit_sha":"f"*40,"pr_url":url,"merged":True})
    from tools.loop.continuous_queue import digest as receipt_digest
    merge_receipt={"repository":"acme/repo","head_sha":head,"merge_commit_sha":"f"*40,"pr_url":url,"merged":True}
    proof={"wb-small-task":{"dependency_queue_id":"wb-small-task","merge_receipt_fingerprint":receipt_digest(merge_receipt),"base_sha":BASE,"ancestor":True}}
    register(q,"dependent-job",proof)
    assert q.claim()["id"]=="dependent-job"

def test_claim_is_atomic_across_concurrent_dispatchers(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
    barrier=threading.Barrier(3);results=[]
    def worker():
        barrier.wait();results.append(q.claim())
    threads=[threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:thread.start()
    barrier.wait()
    for thread in threads:thread.join()
    assert sum(value is not None for value in results)==1

def test_unknown_retains_lease_and_retry_requires_stopped_receipt(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
    claimed=q.claim();lease=claimed["lease_id"]
    unknown=q.update(claimed["id"],lease,"unknown",run_id="run-one",job_id="job-one",blocker="lost-response")
    assert unknown["lease_id"]==lease and q.claim() is None
    bad={"stopped":True,"previous_lease_id":lease,"external_run_id":"run-other","external_job_id":"job-one","evidence_ref":"stop.json","reason":"transport_unknown"}
    with pytest.raises(QueueError,match="stopped predecessor"):q.retry(claimed["id"],bad)
    good={**bad,"external_run_id":"run-one"}
    assert q.retry(claimed["id"],good)["state"]=="ready"
    assert q.claim()["attempts"]==2


def test_director_can_propose_but_cannot_review_or_register_http(tmp_path):
    class Remote:
        def call(self,method,path,payload=None,headers=None):
            return {"run_id":"hermes-external" if path=="/v1/runs" else "paperclip-external","runId":"paperclip-external","status":"running"}
    qpolicy=policy();bridge=Bridge(tmp_path/"bridge.db",Remote(),Remote(),"director",continuous_policy=qpolicy)
    credentials={}
    for role in ("operator","director"):
        path=tmp_path/(role+".key");path.write_text("key-"+role);path.chmod(0o600);credentials[role]=str(path)
    http=server(bridge,{"port":0,"credential_files":credentials,"templates":{}})
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    root=f"http://127.0.0.1:{http.server_port}";operator=JsonHTTP(root,"key-operator");director=JsonHTTP(root,"key-director")
    try:
        planned=operator.call("POST","/v1/queue/plan",{},{"Idempotency-Key":"planning-one"})
        hermes=bridge.create("hermes","paperclip-external",{"input":"plan","instructions":"plan","session_id":"fixture"})
        candidate=proposal(planner_run_id=hermes["run_id"])
        proposed=director.call("POST","/v1/queue/proposals",candidate)
        assert bridge.continuous_status()["planning"]["id"]==planned["run_id"]
        receipt={"proposal_fingerprint":proposed["proposal_fingerprint"],"verdict":"approve","reviewer":"reviewer",
                 "checks":{"policy":"pass","scope":"pass","dependencies":{},"duplicates":{"status":"pass","compared":[],"duplicate_of":None}}}
        with pytest.raises(BridgeError):director.call("POST","/v1/queue/wb-small-task/review",receipt)
        assert operator.call("POST","/v1/queue/wb-small-task/review",receipt)["state"]=="registering"
    finally:
        http.shutdown();http.server_close();thread.join()


def test_policy_change_rejects_old_proposal_and_review_is_immutable(tmp_path):
    first_policy=policy();q=ContinuousQueue(tmp_path/"q.db",first_policy)
    row=q.propose(proposal(),*planner(q));reviewed=approve(q)
    conflicting={"proposal_fingerprint":row["proposal_fingerprint"],"verdict":"approve","reviewer":"other",
        "checks":{"policy":"pass","scope":"pass","dependencies":{},"duplicates":{"status":"pass","compared":[],"duplicate_of":None}}}
    with pytest.raises(QueueError,match="conflict"):q.review(row["id"],conflicting)
    changed=policy();changed["plan_fingerprint"]="9"*64
    newer=ContinuousQueue(tmp_path/"q.db",changed)
    with pytest.raises(QueueError,match="exact proposal"):newer.review(row["id"],reviewed["review_receipt"])


def test_bridge_pause_blocks_continuous_claim_with_ready_work(tmp_path):
    class Remote:
        def call(self,*args,**kwargs):return {"run_id":"remote"}
    qpolicy=policy();bridge=Bridge(tmp_path/"bridge.db",Remote(),Remote(),"director",continuous_policy=qpolicy)
    q=bridge.continuous;q.propose(proposal(),*planner(q));register(q)
    bridge.pause(True)
    assert bridge.claim_continuous() is None
    assert bridge.continuous_status()["queue_paused"] is True


def test_user_stop_cancellation_never_becomes_retry(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
    claimed=q.claim();q.update(claimed["id"],claimed["lease_id"],"unknown",run_id="run",job_id="job")
    receipt={"stopped":True,"previous_lease_id":claimed["lease_id"],"external_run_id":"run",
      "external_job_id":"job","evidence_ref":"stop.json","reason":"user_stop"}
    with pytest.raises(QueueError,match="stopped predecessor"):q.retry(claimed["id"],receipt)


def test_claim_atomically_respects_legacy_shared_executor(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
    with q.db() as db:
        db.execute("CREATE TABLE jobs(id TEXT,state TEXT)")
        db.execute("INSERT INTO jobs VALUES('legacy','dispatching')")
    assert q.claim() is None
    with q.db() as db:db.execute("UPDATE jobs SET state='ready_pr'")
    assert q.claim()["id"]=="wb-small-task"

def test_third_blocked_attempt_keeps_lease_until_confirmed_stop_settlement(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
    for attempt in (1,2,3):
        claimed=q.claim();assert claimed["attempts"]==attempt
        blocked=q.update(claimed["id"],claimed["lease_id"],"blocked",run_id=f"run-{attempt}",job_id=f"job-{attempt}",blocker="local")
        assert blocked["lease_id"]==claimed["lease_id"]
        receipt={"stopped":True,"previous_lease_id":claimed["lease_id"],"external_run_id":f"run-{attempt}",
          "external_job_id":f"job-{attempt}","evidence_ref":f"stop-{attempt}.json",
          "reason":"local_failure" if attempt<3 else "attempts_exhausted"}
        if attempt<3:q.retry(claimed["id"],receipt)
        else:
            with pytest.raises(QueueError):q.retry(claimed["id"],{**receipt,"reason":"local_failure"})
            settled=q.settle(claimed["id"],receipt);assert settled["lease_id"] is None and settled["state"]=="blocked"

def test_reject_wins_race_against_late_review(tmp_path):
    q=ContinuousQueue(tmp_path/"q.db",policy());row=q.propose(proposal(),*planner(q))
    rejection={"proposal_fingerprint":row["proposal_fingerprint"],"verdict":"block","reviewer":"terra","checks":{},"blocker":"duplicate"}
    q.reject(row["id"],rejection)
    with pytest.raises(QueueError,match="exact proposal"):approve(q)


def test_generic_acceptance_profile_is_disabled_until_real_proof_exists():
    candidate=policy();candidate["requirements"]["wb-task"]["acceptance_profile"]="wb-generic"
    candidate["requirements"]["wb-task"]["path_sets"]["default"]["acceptance_profile"]="wb-generic"
    with pytest.raises(QueueError,match="execution identity|path sets"):validate_policy(candidate)


def test_manual_claim_is_atomically_blocked_by_continuous_planning(tmp_path):
 q=ContinuousQueue(tmp_path/"q.db",policy());q.propose(proposal(),*planner(q));register(q)
 before=q.get("wb-small-task");assert before["state"]=="ready" and before["attempts"]==0
 with q.db() as db:
  db.execute("CREATE TABLE operations(id TEXT PRIMARY KEY,state TEXT,request TEXT)")
  db.execute("INSERT INTO operations VALUES(?,?,?)",("planner-active","running",json.dumps({"source":"continuous_planning","planning_snapshot":"f"*64})))
 assert q.claim() is None
 after=q.get("wb-small-task");assert after["state"]=="ready" and after["attempts"]==0 and after["lease_id"] is None
 with q.db() as db:db.execute("UPDATE operations SET state='completed'")
 assert q.claim()["attempts"]==1


def test_planning_intent_is_atomically_rejected_after_execution_claim(tmp_path):
 class Never:
  def call(self,*args,**kwargs):raise AssertionError("planning reached upstream")
 bridge=Bridge(tmp_path/"bridge.db",Never(),Never(),"director",continuous_policy=policy())
 q=bridge.continuous;q.propose(proposal(),*planner(q));register(q);assert q.claim()["state"]=="dispatching"
 with pytest.raises(BridgeError,match="execution active"):bridge.plan_continuous("planning-after-claim")
