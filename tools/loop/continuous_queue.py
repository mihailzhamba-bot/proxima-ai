"""Persistent operator-pinned queue for continuous LOOP admission."""
from __future__ import annotations
import hashlib, json, re, sqlite3, time
from pathlib import PurePosixPath
ID=re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$"); SHA=re.compile(r"^[0-9a-f]{40}$"); DIGEST=re.compile(r"^[0-9a-f]{64}$")
PROFILE_ID="73bf9c3a-ab69-4b2e-a7f0-e808df8f2614"; TARGETS={"bridge","harper","worker"}
CONTROL=("tools/","infra/loop-control/",".github/","db/")
POLICY_EXCEPTIONS=frozenset({"tools/wb/daily.py","tools/tests/test_wb_daily.py","infra/systemd/proxima-wb-daily.service","infra/systemd/proxima-wb-daily.timer","services/collector/tests/collect.db.test.ts","tools/loop/wb_daily_status.py","tools/tests/test_wb_daily_status.py"})
class QueueError(ValueError): pass
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def product_path(v):
    if not isinstance(v,str) or not v or (v.startswith(CONTROL) and v not in POLICY_EXCEPTIONS):return False
    p=PurePosixPath(v);return not p.is_absolute() and ".." not in p.parts and p.parts[0]!=".git"
def validate_policy(p):
    if not isinstance(p,dict) or set(p)!={"policy_id","plan_fingerprint","requirements"}:raise QueueError("invalid continuous policy")
    if not ID.fullmatch(str(p["policy_id"])) or not DIGEST.fullmatch(str(p["plan_fingerprint"])):raise QueueError("invalid continuous policy identity")
    if not isinstance(p["requirements"],dict) or not p["requirements"]:raise QueueError("continuous policy has no requirements")
    req={"base_sha","allowed_paths","contract_files","profile","profile_id","profile_revision","depends_on","repository","max_slices","objective","acceptance","acceptance_profile","source_evidence","path_sets"}
    for key,item in p["requirements"].items():
        if not ID.fullmatch(str(key)) or not isinstance(item,dict) or not req<=set(item) or set(item)-req:raise QueueError("invalid continuous requirement")
        if (type(item["max_slices"]) is not int or not 1<=item["max_slices"]<=20
                or not isinstance(item["objective"],str) or not item["objective"]
                or not isinstance(item["acceptance"],list) or not item["acceptance"] or not ID.fullmatch(str(item["acceptance_profile"]))
                or not re.fullmatch(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",str(item["repository"])) or not SHA.fullmatch(str(item["base_sha"])) or item["profile"]!="fedor" or item["profile_id"]!=PROFILE_ID or type(item["profile_revision"]) is not int or item["profile_revision"]<0):raise QueueError("invalid continuous execution identity")
        path_sets=item["path_sets"]
        if (not isinstance(path_sets,dict) or not path_sets
                or any(not ID.fullmatch(str(name)) or not isinstance(scope,dict)
                       or set(scope)!={"description","allowed_paths","contract_files","acceptance_profile"}
                       or not isinstance(scope["description"],str) or not scope["description"]
                       or not isinstance(scope["allowed_paths"],list) or not scope["allowed_paths"]
                       or any(not product_path(v) for v in scope["allowed_paths"])
                       or not isinstance(scope["contract_files"],list)
                       or not ID.fullmatch(str(scope["acceptance_profile"])) for name,scope in path_sets.items())):
            raise QueueError("invalid operator path sets")
        evidence=item["source_evidence"]
        if (not isinstance(evidence,list) or not 1<=len(evidence)<=12
                or any(not isinstance(v,dict) or set(v)!={"ref","sha256","summary"}
                       or not isinstance(v["ref"],str) or not v["ref"] or len(v["ref"])>300
                       or not DIGEST.fullmatch(str(v["sha256"])) or not isinstance(v["summary"],str)
                       or not 1<=len(v["summary"])<=6000 for v in evidence)):
            raise QueueError("invalid bounded source evidence")
        for name in ("allowed_paths","contract_files","depends_on"):
            if not isinstance(item[name],list) or any(not isinstance(v,str) for v in item[name]):raise QueueError("invalid continuous requirement list")
        if not item["allowed_paths"] or any(not product_path(v) for v in item["allowed_paths"]):raise QueueError("continuous policy exposes control authority")
        if any(not ID.fullmatch(v) for v in item["depends_on"]):raise QueueError("invalid continuous dependency")
    return p
class ContinuousQueue:
    def __init__(self,database,policy,clock=time.time):
        self.database,self.policy,self.clock=str(database),validate_policy(policy),clock;self.policy_fingerprint=digest(policy)
        with self.db() as d:
            d.executescript("""CREATE TABLE IF NOT EXISTS continuous_queue(
id TEXT PRIMARY KEY,requirement_id TEXT NOT NULL,slice_key TEXT NOT NULL,planner_run_id TEXT NOT NULL,planner_generation INTEGER NOT NULL,
goal TEXT NOT NULL,acceptance TEXT NOT NULL,base_sha TEXT NOT NULL,allowed_paths TEXT NOT NULL,contract_files TEXT NOT NULL,
depends_on TEXT NOT NULL,proposal_fingerprint TEXT NOT NULL,policy_fingerprint TEXT NOT NULL,execution_policy TEXT NOT NULL,review_fingerprint TEXT,
template_name TEXT,template_fingerprint TEXT,state TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
lease_id TEXT,lease_expires REAL,external_run_id TEXT,external_job_id TEXT,evidence TEXT,pr_url TEXT,blocker TEXT,
created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS continuous_receipts(queue_id TEXT NOT NULL,target TEXT NOT NULL,template_fingerprint TEXT NOT NULL,
receipt_fingerprint TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(queue_id,target),
FOREIGN KEY(queue_id) REFERENCES continuous_queue(id));
CREATE TABLE IF NOT EXISTS continuous_attempt_events(queue_id TEXT NOT NULL,sequence INTEGER NOT NULL,event TEXT NOT NULL,
created REAL NOT NULL,PRIMARY KEY(queue_id,sequence),FOREIGN KEY(queue_id) REFERENCES continuous_queue(id));
CREATE TABLE IF NOT EXISTS continuous_merges(queue_id TEXT PRIMARY KEY,receipt TEXT NOT NULL,receipt_fingerprint TEXT NOT NULL,
created REAL NOT NULL,FOREIGN KEY(queue_id) REFERENCES continuous_queue(id));
CREATE TABLE IF NOT EXISTS continuous_dependency_receipts(queue_id TEXT NOT NULL,dependency_id TEXT NOT NULL,receipt TEXT NOT NULL,
PRIMARY KEY(queue_id,dependency_id),FOREIGN KEY(queue_id) REFERENCES continuous_queue(id));""")
            columns={r[1] for r in d.execute("PRAGMA table_info(continuous_queue)")}
            if "slice_key" not in columns:d.execute("ALTER TABLE continuous_queue ADD COLUMN slice_key TEXT NOT NULL DEFAULT 'legacy'")
            if "execution_policy" not in columns:d.execute("ALTER TABLE continuous_queue ADD COLUMN execution_policy TEXT NOT NULL DEFAULT '{}'")
            d.execute("CREATE UNIQUE INDEX IF NOT EXISTS continuous_slice_unique ON continuous_queue(requirement_id,slice_key)")
    def db(self):
        d=sqlite3.connect(self.database,timeout=20);d.row_factory=sqlite3.Row;d.execute("PRAGMA foreign_keys=ON");return d
    def get(self,item_id):
        with self.db() as d:
            row=d.execute("SELECT * FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            receipts=d.execute("SELECT target,receipt_fingerprint FROM continuous_receipts WHERE queue_id=? ORDER BY target",(item_id,)).fetchall()
            merged=d.execute("SELECT receipt,receipt_fingerprint FROM continuous_merges WHERE queue_id=?",(item_id,)).fetchone()
        if not row:raise QueueError("queue item unavailable")
        v=dict(row)
        for k in ("acceptance","allowed_paths","contract_files","depends_on","execution_policy","evidence"):v[k]=json.loads(v[k]) if v[k] else None
        v["receipts"]={r["target"]:r["receipt_fingerprint"] for r in receipts}
        if merged:v["merge_receipt"]=json.loads(merged[0]);v["merge_receipt_fingerprint"]=merged[1]
        return v
    def propose(self,p,planner,parent):
        fields={"proposal_id","requirement_id","slice_key","path_set_id","planner_run_id","planner_generation","goal","acceptance","depends_on"}
        if not isinstance(p,dict) or set(p)!=fields:raise QueueError("invalid planning proposal fields")
        request=json.loads(parent["request"]) if parent else {}
        if (p["planner_run_id"]!=planner["id"] or p["planner_generation"]!=planner["generation"]
                or planner["kind"]!="hermes" or planner["state"] not in {"running","completed"}
                or parent is None or parent["kind"]!="paperclip" or parent["state"] not in {"running","completed"}
                or parent["external_id"]!=planner["key"] or request.get("source")!="continuous_planning"
                or request.get("policy_fingerprint")!=self.policy_fingerprint):raise QueueError("trusted Paperclip planning parent and Hermes run required")
        item_id,rid=p["proposal_id"],p["requirement_id"];slice_key=p["slice_key"];policy=self.policy["requirements"].get(rid)
        path_set=policy["path_sets"].get(p["path_set_id"]) if policy else None
        if not ID.fullmatch(str(item_id)) or len(item_id)>36 or not ID.fullmatch(str(slice_key)) or policy is None or path_set is None:raise QueueError("proposal is outside approved WB plan")
        goal,acceptance,deps=p["goal"],p["acceptance"],p["depends_on"]
        if not isinstance(goal,str) or not 10<=len(goal)<=1000 or "\n" in goal or not isinstance(acceptance,list) or not 1<=len(acceptance)<=12 or any(not isinstance(v,str) or not v or len(v)>500 for v in acceptance) or deps!=policy["depends_on"]:raise QueueError("proposal exceeds approved requirement bounds")
        execution_policy={**policy,"selected_path_set_id":p["path_set_id"],
            "allowed_paths":path_set["allowed_paths"],"contract_files":path_set["contract_files"],
            "acceptance_profile":path_set["acceptance_profile"]}
        fixed={k:execution_policy[k] for k in ("base_sha","allowed_paths","contract_files","depends_on")}
        fp=digest({"id":item_id,"requirement_id":rid,"slice_key":slice_key,"path_set_id":p["path_set_id"],"goal":goal,"acceptance":acceptance,**fixed,"policy_fingerprint":self.policy_fingerprint});now=self.clock()
        with self.db() as d:
            old=d.execute("SELECT proposal_fingerprint FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            if old and old[0]!=fp:raise QueueError("proposal id conflict")
            if not old:
                active=d.execute("SELECT count(*) FROM continuous_queue WHERE requirement_id=? AND state NOT IN ('rejected','cancelled')",(rid,)).fetchone()[0]
                total=d.execute("SELECT count(*) FROM continuous_queue WHERE requirement_id=?",(rid,)).fetchone()[0]
                if active>=policy["max_slices"] or total>=policy["max_slices"]*3:raise QueueError("requirement slice capacity exhausted")
                try:d.execute("""INSERT INTO continuous_queue(id,requirement_id,slice_key,planner_run_id,planner_generation,goal,acceptance,
base_sha,allowed_paths,contract_files,depends_on,proposal_fingerprint,policy_fingerprint,execution_policy,state,created,updated)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(item_id,rid,slice_key,planner["id"],planner["generation"],goal,canonical(acceptance),fixed["base_sha"],canonical(fixed["allowed_paths"]),canonical(fixed["contract_files"]),canonical(deps),fp,self.policy_fingerprint,canonical(execution_policy),"proposed",now,now))
                except sqlite3.IntegrityError:raise QueueError("requirement slice already proposed") from None
        return self.get(item_id)
    def review(self,item_id,receipt):
        row=self.get(item_id)
        required={"proposal_fingerprint","verdict","reviewer","checks"}
        if not isinstance(receipt,dict) or set(receipt)!=required or row["state"] not in {"proposed","registering"} or row["policy_fingerprint"]!=self.policy_fingerprint or receipt["proposal_fingerprint"]!=row["proposal_fingerprint"]:raise QueueError("exact proposal review required")
        receipt_fingerprint=digest(receipt)
        if row["state"]=="registering":
            if row["review_fingerprint"]!=receipt_fingerprint:raise QueueError("review receipt conflict")
            return self.registration(item_id)
        checks=receipt.get("checks")
        if receipt["verdict"]!="approve" or not isinstance(receipt["reviewer"],str) or not receipt["reviewer"] or not isinstance(checks,dict) or set(checks)!={"policy","scope","dependencies","duplicates"} or checks["policy"]!="pass" or checks["scope"]!="pass" or not isinstance(checks["dependencies"],dict) or not isinstance(checks["duplicates"],dict):raise QueueError("independent approval receipt required")
        policy=row["execution_policy"];dependencies={}
        with self.db() as d:
            compared=sorted(r[0] for r in d.execute("SELECT proposal_fingerprint FROM continuous_queue WHERE requirement_id=? AND id!=?",(row["requirement_id"],item_id)))
            if checks["duplicates"]!={"status":"pass","compared":compared,"duplicate_of":None}:raise QueueError("independent semantic duplicate review required")
            for dependency_id in row["depends_on"]:
                dep=d.execute("SELECT state FROM continuous_queue WHERE id=?",(dependency_id,)).fetchone()
                merged=d.execute("SELECT receipt,receipt_fingerprint FROM continuous_merges WHERE queue_id=?",(dependency_id,)).fetchone()
                proof=checks["dependencies"].get(dependency_id)
                if (not dep or dep[0]!="merged" or not isinstance(proof,dict) or not merged
                        or proof!={"dependency_queue_id":dependency_id,"merge_receipt_fingerprint":merged[1],
                                  "base_sha":row["base_sha"],"ancestor":True}):raise QueueError("verified dependency ancestry required")
                dependencies[dependency_id]=proof
            if set(checks["dependencies"])!=set(row["depends_on"]):raise QueueError("verified dependency ancestry required")
        rfp=receipt_fingerprint
        prompt={"proposal_fingerprint":row["proposal_fingerprint"],"requirement_id":row["requirement_id"],
                "requirement_objective":policy["objective"],"goal":row["goal"],"acceptance":row["acceptance"],
                "source_evidence":policy["source_evidence"]}
        template={k:policy[k] for k in ("base_sha","allowed_paths","contract_files","profile","profile_id","profile_revision")};template["prompt_sha256"]=hashlib.sha256((canonical(prompt)+"\n").encode()).hexdigest();name="continuous-"+item_id
        try:from .bridge import template_fingerprint
        except ImportError:from bridge import template_fingerprint
        tfp=template_fingerprint(name,template)
        with self.db() as d:
            d.execute("UPDATE continuous_queue SET review_fingerprint=?,template_name=?,template_fingerprint=?,state='registering',updated=? WHERE id=?",(rfp,name,tfp,self.clock(),item_id))
            for dependency_id,proof in dependencies.items():
                d.execute("INSERT OR REPLACE INTO continuous_dependency_receipts VALUES(?,?,?)",(item_id,dependency_id,canonical(proof)))
        return {**self.get(item_id),"template":template,"prompt_contract":prompt,"review_receipt":receipt}
    def registration(self,item_id):
        row=self.get(item_id)
        if row["state"] not in {"registering","ready"} or row["policy_fingerprint"]!=self.policy_fingerprint:raise QueueError("reviewed registration unavailable")
        policy=row["execution_policy"]
        prompt={"proposal_fingerprint":row["proposal_fingerprint"],"requirement_id":row["requirement_id"],
                "requirement_objective":policy["objective"],"goal":row["goal"],"acceptance":row["acceptance"],
                "source_evidence":policy["source_evidence"]}
        template={k:policy[k] for k in ("base_sha","allowed_paths","contract_files","profile","profile_id","profile_revision")}
        template["prompt_sha256"]=hashlib.sha256((canonical(prompt)+"\n").encode()).hexdigest()
        try:from .bridge import template_fingerprint
        except ImportError:from bridge import template_fingerprint
        if template_fingerprint(row["template_name"],template)!=row["template_fingerprint"]:raise QueueError("registration fingerprint drift")
        return {**row,"template":template,"prompt_contract":prompt}
    def reject(self,item_id,receipt):
        row=self.get(item_id)
        required={"proposal_fingerprint","verdict","reviewer","checks","blocker"}
        if (not isinstance(receipt,dict) or set(receipt)!=required or receipt["verdict"]!="block"
                or row["state"]!="proposed" or row["policy_fingerprint"]!=self.policy_fingerprint
                or receipt["proposal_fingerprint"]!=row["proposal_fingerprint"]
                or not isinstance(receipt["blocker"],str) or not receipt["blocker"]):raise QueueError("invalid proposal rejection")
        with self.db() as d:
            result=d.execute("UPDATE continuous_queue SET state='rejected',review_fingerprint=?,blocker=?,updated=? WHERE id=? AND state='proposed'",(digest(receipt),receipt["blocker"][:500],self.clock(),item_id))
            if result.rowcount!=1:raise QueueError("proposal rejection raced")
        return self.get(item_id)
    def receipt(self,item_id,receipt):
        row=self.get(item_id);required={"target","template_fingerprint","policy_fingerprint","installed_sha256"}
        if not isinstance(receipt,dict) or set(receipt)!=required or row["policy_fingerprint"]!=self.policy_fingerprint or receipt["target"] not in TARGETS or row["state"] not in {"registering","ready"} or receipt["template_fingerprint"]!=row["template_fingerprint"] or receipt["policy_fingerprint"]!=self.policy_fingerprint or not DIGEST.fullmatch(str(receipt["installed_sha256"])):raise QueueError("invalid immutable template receipt")
        rfp=digest(receipt);target=receipt["target"];tfp=receipt["template_fingerprint"]
        with self.db() as d:
            old=d.execute("SELECT template_fingerprint,receipt_fingerprint FROM continuous_receipts WHERE queue_id=? AND target=?",(item_id,target)).fetchone()
            if old and tuple(old)!=(tfp,rfp):raise QueueError("template receipt conflict")
            d.execute("INSERT OR IGNORE INTO continuous_receipts VALUES(?,?,?,?,?)",(item_id,target,tfp,rfp,self.clock()))
            count=d.execute("SELECT count(*) FROM continuous_receipts WHERE queue_id=?",(item_id,)).fetchone()[0]
            d.execute("UPDATE continuous_queue SET state=?,updated=? WHERE id=?",("ready" if count==3 else "registering",self.clock(),item_id))
        return self.get(item_id)
    def merge(self,item_id,receipt):
        row=self.get(item_id);required={"repository","head_sha","merge_commit_sha","pr_url","merged"}
        evidence=row.get("evidence") or {}
        if not isinstance(receipt,dict) or set(receipt)!=required or receipt["merged"] is not True or row["state"]!="ready_pr" or receipt["repository"]!=row["execution_policy"]["repository"] or receipt["head_sha"]!=evidence.get("head_sha") or not SHA.fullmatch(str(receipt["merge_commit_sha"])) or not isinstance(receipt["repository"],str) or "/" not in receipt["repository"] or receipt["pr_url"]!=row["pr_url"]:raise QueueError("verified exact-head merge receipt required")
        rfp=digest(receipt)
        with self.db() as d:
            d.execute("INSERT INTO continuous_merges VALUES(?,?,?,?)",(item_id,canonical(receipt),rfp,self.clock()))
            d.execute("UPDATE continuous_queue SET state='merged',updated=? WHERE id=?",(self.clock(),item_id))
        return self.get(item_id)
    def claim(self,lease_seconds=300):
        now=self.clock()
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            if d.execute("SELECT 1 FROM continuous_queue WHERE state IN('dispatching','running','unknown') OR(state='blocked' AND lease_id IS NOT NULL) OR(lease_id IS NOT NULL AND lease_expires>?)",(now,)).fetchone():return None
            selected=None
            for row in d.execute("SELECT id,depends_on FROM continuous_queue WHERE state='ready' AND attempts<3 AND policy_fingerprint=? ORDER BY created,id",(self.policy_fingerprint,)):
                dependencies=json.loads(row["depends_on"])
                if all((lambda x:x and x[0]=="merged")(d.execute("SELECT state FROM continuous_queue WHERE id=?",(dep,)).fetchone())
                       and d.execute("SELECT 1 FROM continuous_dependency_receipts WHERE queue_id=? AND dependency_id=?",(row["id"],dep)).fetchone()
                       for dep in dependencies):selected=row["id"];break
            if selected is None:return None
            lease=digest({"id":selected,"at":now})
            result=d.execute("UPDATE continuous_queue SET state='dispatching',attempts=attempts+1,lease_id=?,lease_expires=?,updated=? WHERE id=? AND state='ready' AND attempts<3",(lease,now+lease_seconds,now,selected))
            if result.rowcount!=1:return None
        return self.get(selected)
    def update(self,item_id,lease_id,state,**evidence):
        if state not in {"running","unknown","ready_pr","blocked","cancelled"}:raise QueueError("invalid queue transition")
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            row=d.execute("SELECT * FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            if not row or row["policy_fingerprint"]!=self.policy_fingerprint or row["lease_id"]!=lease_id or row["state"] not in {"dispatching","running","unknown","blocked"}:raise QueueError("queue lease lost")
            if state=="ready_pr" and (not SHA.fullmatch(str(evidence.get("head_sha",""))) or not str(evidence.get("pr_url","")).startswith("https://")):raise QueueError("ready PR evidence required")
            event={"state":state,"lease_id":lease_id,"evidence":evidence}
            terminal=state in {"ready_pr","cancelled"} or (state=="blocked" and row["attempts"]>=3)
            sequence=d.execute("SELECT coalesce(max(sequence),0)+1 FROM continuous_attempt_events WHERE queue_id=?",(item_id,)).fetchone()[0]
            d.execute("INSERT INTO continuous_attempt_events VALUES(?,?,?,?)",(item_id,sequence,canonical(event),self.clock()))
            result=d.execute("""UPDATE continuous_queue SET state=?,external_run_id=coalesce(?,external_run_id),
external_job_id=coalesce(?,external_job_id),evidence=?,pr_url=coalesce(?,pr_url),blocker=coalesce(?,blocker),
lease_id=?,lease_expires=?,updated=? WHERE id=? AND state=? AND lease_id=?""",(state,evidence.get("run_id"),evidence.get("job_id"),canonical(evidence),evidence.get("pr_url"),evidence.get("blocker"),None if terminal else lease_id,None if terminal else row["lease_expires"],self.clock(),item_id,row["state"],lease_id))
            if result.rowcount!=1:raise QueueError("queue transition raced")
        return self.get(item_id)
    def retry(self,item_id,receipt):
        required={"stopped","previous_lease_id","external_run_id","external_job_id","evidence_ref","reason"}
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            row=d.execute("SELECT * FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            if not row or row["policy_fingerprint"]!=self.policy_fingerprint or not isinstance(receipt,dict) or set(receipt)!=required or receipt["stopped"] is not True or receipt.get("reason") not in {"local_failure","transport_unknown"} or row["state"] not in {"unknown","blocked"} or row["attempts"]>=3 or receipt["previous_lease_id"]!=row["lease_id"] or receipt["external_run_id"]!=row["external_run_id"] or receipt["external_job_id"]!=row["external_job_id"] or not isinstance(receipt["evidence_ref"],str) or not receipt["evidence_ref"]:raise QueueError("confirmed stopped predecessor required")
            sequence=d.execute("SELECT coalesce(max(sequence),0)+1 FROM continuous_attempt_events WHERE queue_id=?",(item_id,)).fetchone()[0]
            d.execute("INSERT INTO continuous_attempt_events VALUES(?,?,?,?)",(item_id,sequence,canonical({"state":"retry_ready","stop_receipt":receipt}),self.clock()))
            result=d.execute("UPDATE continuous_queue SET state='ready',lease_id=NULL,lease_expires=NULL,external_run_id=NULL,external_job_id=NULL,updated=? WHERE id=? AND state=? AND lease_id=?",(self.clock(),item_id,row["state"],row["lease_id"]))
            if result.rowcount!=1:raise QueueError("queue retry raced")
        return self.get(item_id)
    def status(self):
        with self.db() as d:rows=[dict(r) for r in d.execute("SELECT id,requirement_id,slice_key,state,attempts,updated,pr_url,blocker,lease_id FROM continuous_queue ORDER BY created,id")]
        active_counts={key:sum(row["requirement_id"]==key and row["state"] not in {"rejected","cancelled"} for row in rows) for key in self.policy["requirements"]}
        total_counts={key:sum(row["requirement_id"]==key for row in rows) for key in self.policy["requirements"]}
        eligible=[key for key,item in self.policy["requirements"].items() if active_counts[key]<item["max_slices"] and total_counts[key]<item["max_slices"]*3]
        return {"policy_fingerprint":self.policy_fingerprint,"continuous_ready":False,
        "plan_exhausted":not eligible,"eligible_requirements":eligible,
        "current":next((r for r in rows if (r["state"] in {"dispatching","running","unknown"} or (r["state"]=="blocked" and r.get("lease_id")))),None),
        "next":next((r for r in rows if r["state"] in {"ready","registering","proposed"}),None),"items":rows}
