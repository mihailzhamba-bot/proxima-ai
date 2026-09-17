"""Persistent operator-pinned queue for continuous LOOP admission."""
from __future__ import annotations
import hashlib, json, re, sqlite3, time
from pathlib import PurePosixPath
ID=re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$"); SHA=re.compile(r"^[0-9a-f]{40}$"); DIGEST=re.compile(r"^[0-9a-f]{64}$")
PROFILE_ID="73bf9c3a-ab69-4b2e-a7f0-e808df8f2614"; TARGETS={"bridge","harper","worker"}
ACCEPTANCE_PROFILES={"wb-daily-packaging","wb-warehouse-metadata","wb-daily-status"}
CONTROL=("tools/","infra/loop-control/",".github/","db/")
POLICY_EXCEPTIONS=frozenset({"tools/wb/daily.py","tools/tests/test_wb_daily.py","infra/systemd/proxima-wb-daily.service","infra/systemd/proxima-wb-daily.timer","services/collector/tests/collect.db.test.ts","tools/loop/wb_daily_status.py","tools/tests/test_wb_daily_status.py"})
class QueueError(ValueError): pass
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def policy_authority(policy):
    value=json.loads(canonical(validate_policy(policy)))
    for requirement in value["requirements"].values():
        requirement.pop("base_sha",None);requirement.pop("source_evidence",None)
    return value
def proposal_digest(item_id,requirement_id,slice_key,path_set_id,goal,acceptance,execution_policy,policy_fingerprint):
    fixed={key:execution_policy[key] for key in ("base_sha","allowed_paths","contract_files","depends_on")}
    return digest({"id":item_id,"requirement_id":requirement_id,"slice_key":slice_key,"path_set_id":path_set_id,
                   "goal":goal,"acceptance":acceptance,**fixed,"policy_fingerprint":policy_fingerprint})
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
                or not isinstance(item["acceptance"],list) or not item["acceptance"] or item["acceptance_profile"] not in ACCEPTANCE_PROFILES
                or not re.fullmatch(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",str(item["repository"])) or not SHA.fullmatch(str(item["base_sha"])) or item["profile"]!="fedor" or item["profile_id"]!=PROFILE_ID or type(item["profile_revision"]) is not int or item["profile_revision"]<0):raise QueueError("invalid continuous execution identity")
        path_sets=item["path_sets"]
        if (not isinstance(path_sets,dict) or not path_sets
                or any(not ID.fullmatch(str(name)) or not isinstance(scope,dict)
                       or set(scope)!={"description","allowed_paths","contract_files","acceptance_profile"}
                       or not isinstance(scope["description"],str) or not scope["description"]
                       or not isinstance(scope["allowed_paths"],list) or not scope["allowed_paths"]
                       or any(not product_path(v) for v in scope["allowed_paths"])
                       or not isinstance(scope["contract_files"],list)
                       or scope["acceptance_profile"] not in ACCEPTANCE_PROFILES for name,scope in path_sets.items())):
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
depends_on TEXT NOT NULL,proposal_fingerprint TEXT NOT NULL,policy_fingerprint TEXT NOT NULL,execution_policy TEXT NOT NULL,prompt_contract_version INTEGER NOT NULL DEFAULT 2,review_fingerprint TEXT,
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
PRIMARY KEY(queue_id,dependency_id),FOREIGN KEY(queue_id) REFERENCES continuous_queue(id));
CREATE TABLE IF NOT EXISTS continuous_maintenance(
id INTEGER PRIMARY KEY CHECK(id=1),key TEXT NOT NULL,state TEXT NOT NULL,old_policy_fingerprint TEXT NOT NULL,
new_head TEXT NOT NULL,new_policy TEXT,new_policy_fingerprint TEXT,bundle_sha256 TEXT,rebase_templates TEXT NOT NULL,
receipts TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS continuous_queue_history(
item_id TEXT NOT NULL,sequence INTEGER NOT NULL,snapshot TEXT NOT NULL,created REAL NOT NULL,
PRIMARY KEY(item_id,sequence));
CREATE TABLE IF NOT EXISTS continuous_existing_work(
job_id TEXT PRIMARY KEY,receipt TEXT NOT NULL,receipt_fingerprint TEXT NOT NULL,created REAL NOT NULL);""")
            columns={r[1] for r in d.execute("PRAGMA table_info(continuous_queue)")}
            if "slice_key" not in columns:d.execute("ALTER TABLE continuous_queue ADD COLUMN slice_key TEXT NOT NULL DEFAULT 'legacy'")
            if "execution_policy" not in columns:d.execute("ALTER TABLE continuous_queue ADD COLUMN execution_policy TEXT NOT NULL DEFAULT '{}'")
            if "prompt_contract_version" not in columns:d.execute("ALTER TABLE continuous_queue ADD COLUMN prompt_contract_version INTEGER NOT NULL DEFAULT 1")
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
        fp=proposal_digest(item_id,rid,slice_key,p["path_set_id"],goal,acceptance,execution_policy,self.policy_fingerprint);now=self.clock()
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            if self.maintenance_active(d):raise QueueError("base refresh maintenance active")
            old=d.execute("SELECT proposal_fingerprint FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            if old and old[0]!=fp:raise QueueError("proposal id conflict")
            if not old:
                active=d.execute("SELECT count(*) FROM continuous_queue WHERE requirement_id=? AND state NOT IN ('rejected','cancelled')",(rid,)).fetchone()[0]
                total=d.execute("SELECT count(*) FROM continuous_queue WHERE requirement_id=?",(rid,)).fetchone()[0]
                if active>=policy["max_slices"] or total>=policy["max_slices"]*3:raise QueueError("requirement slice capacity exhausted")
                try:d.execute("""INSERT INTO continuous_queue(id,requirement_id,slice_key,planner_run_id,planner_generation,goal,acceptance,
base_sha,allowed_paths,contract_files,depends_on,proposal_fingerprint,policy_fingerprint,execution_policy,prompt_contract_version,state,created,updated)
VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(item_id,rid,slice_key,planner["id"],planner["generation"],goal,canonical(acceptance),fixed["base_sha"],canonical(fixed["allowed_paths"]),canonical(fixed["contract_files"]),canonical(deps),fp,self.policy_fingerprint,canonical(execution_policy),2,"proposed",now,now))
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
            legacy=[]
            has_jobs=d.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone()
            if has_jobs:
                for stored in d.execute("SELECT receipt,receipt_fingerprint FROM continuous_existing_work"):
                    value=json.loads(stored[0]);job=d.execute("SELECT template,state,pr_url,candidate_sha FROM jobs WHERE id=?",(value["job_id"],)).fetchone()
                    if (job and job["state"]=="ready_pr" and job["template"]==value["template"]
                            and job["pr_url"]==value["pr_url"] and job["candidate_sha"]==value["head_sha"]):legacy.append(stored[1])
            compared=sorted([r[0] for r in d.execute("SELECT proposal_fingerprint FROM continuous_queue WHERE requirement_id=? AND id!=?",(row["requirement_id"],item_id))]+legacy)
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
        if row["prompt_contract_version"]>=2:prompt.update(checkout="proxima-ai",allowed_paths=policy["allowed_paths"],
                scoped_commit="Create exactly one scoped commit containing only changes within allowed_paths.")
        template={k:policy[k] for k in ("base_sha","allowed_paths","contract_files","profile","profile_id","profile_revision")};template["prompt_sha256"]=hashlib.sha256((canonical(prompt)+"\n").encode()).hexdigest();name="continuous-"+item_id
        try:from .bridge import template_fingerprint
        except ImportError:from bridge import template_fingerprint
        tfp=template_fingerprint(name,template)
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            if self.maintenance_active(d):raise QueueError("base refresh maintenance active")
            changed=d.execute("UPDATE continuous_queue SET review_fingerprint=?,template_name=?,template_fingerprint=?,state='registering',updated=? WHERE id=? AND state='proposed' AND proposal_fingerprint=? AND policy_fingerprint=?",(rfp,name,tfp,self.clock(),item_id,row["proposal_fingerprint"],self.policy_fingerprint))
            if changed.rowcount!=1:raise QueueError("proposal review raced")
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
        if row["prompt_contract_version"]>=2:prompt.update(checkout="proxima-ai",allowed_paths=policy["allowed_paths"],
                scoped_commit="Create exactly one scoped commit containing only changes within allowed_paths.")
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
            d.execute("BEGIN IMMEDIATE")
            if self.maintenance_active(d):raise QueueError("base refresh maintenance active")
            result=d.execute("UPDATE continuous_queue SET state='rejected',review_fingerprint=?,blocker=?,updated=? WHERE id=? AND state='proposed' AND proposal_fingerprint=? AND policy_fingerprint=?",(digest(receipt),receipt["blocker"][:500],self.clock(),item_id,row["proposal_fingerprint"],self.policy_fingerprint))
            if result.rowcount!=1:raise QueueError("proposal rejection raced")
        return self.get(item_id)
    def receipt(self,item_id,receipt):
        row=self.get(item_id);required={"target","template_fingerprint","policy_fingerprint","installed_sha256"}
        if not isinstance(receipt,dict) or set(receipt)!=required or row["policy_fingerprint"]!=self.policy_fingerprint or receipt["target"] not in TARGETS or row["state"] not in {"registering","ready"} or receipt["template_fingerprint"]!=row["template_fingerprint"] or receipt["policy_fingerprint"]!=self.policy_fingerprint or not DIGEST.fullmatch(str(receipt["installed_sha256"])):raise QueueError("invalid immutable template receipt")
        rfp=digest(receipt);target=receipt["target"];tfp=receipt["template_fingerprint"]
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            if self.maintenance_active(d):raise QueueError("base refresh maintenance active")
            current=d.execute("SELECT state,policy_fingerprint,template_fingerprint FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            if (not current or current["state"] not in {"registering","ready"}
                    or current["policy_fingerprint"]!=self.policy_fingerprint
                    or current["template_fingerprint"]!=tfp):raise QueueError("stale immutable template receipt")
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
            d.execute("BEGIN IMMEDIATE")
            if self.maintenance_active(d):raise QueueError("base refresh maintenance active")
            d.execute("INSERT INTO continuous_merges VALUES(?,?,?,?)",(item_id,canonical(receipt),rfp,self.clock()))
            d.execute("UPDATE continuous_queue SET state='merged',updated=? WHERE id=?",(self.clock(),item_id))
        return self.get(item_id)
    def maintenance(self):
        with self.db() as d:row=d.execute("SELECT * FROM continuous_maintenance WHERE id=1").fetchone()
        if not row:return None
        value=dict(row)
        for key in ("new_policy","rebase_templates","receipts"):
            value[key]=json.loads(value[key]) if value[key] else None
        return value
    def maintenance_active(self,db=None):
        if db is not None:return db.execute("SELECT 1 FROM continuous_maintenance WHERE id=1 AND state IN ('fetching','installing')").fetchone() is not None
        with self.db() as connection:return self.maintenance_active(connection)
    def begin_refresh(self,key,new_head):
        if not isinstance(key,str) or not ID.fullmatch(key) or not SHA.fullmatch(str(new_head)):raise QueueError("invalid base refresh identity")
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            old=d.execute("SELECT * FROM continuous_maintenance WHERE id=1").fetchone()
            if old and old["state"] in {"fetching","installing"}:
                if old["key"]==key and old["new_head"]==new_head and old["old_policy_fingerprint"]==self.policy_fingerprint:return dict(old)
                raise QueueError("another base refresh is active")
            jobs=d.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone()
            if jobs and d.execute("SELECT 1 FROM jobs WHERE state IN ('queued','dispatching','publishing','unknown','recoverable') OR publication_active=1 LIMIT 1").fetchone():raise QueueError("base refresh blocked by shared executor")
            operations=d.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='operations'").fetchone()
            if operations and d.execute("SELECT 1 FROM operations WHERE state IN ('dispatching','running','unknown','cancelling') LIMIT 1").fetchone():raise QueueError("base refresh blocked by active planning")
            if d.execute("SELECT 1 FROM continuous_queue WHERE state IN ('dispatching','running','unknown') OR (state='blocked' AND lease_id IS NOT NULL) LIMIT 1").fetchone():raise QueueError("base refresh blocked by active attempt")
            now=self.clock()
            d.execute("DELETE FROM continuous_maintenance WHERE id=1")
            d.execute("INSERT INTO continuous_maintenance VALUES(1,?,'fetching',?,?,NULL,NULL,NULL,'[]','{}',?,?)",
                      (key,self.policy_fingerprint,new_head,now,now))
        return self.maintenance()
    def prepare_refresh(self,key,new_policy,bundle_sha256):
        validate_policy(new_policy)
        if not DIGEST.fullmatch(str(bundle_sha256)):raise QueueError("invalid base refresh bundle")
        if policy_authority(new_policy)!=policy_authority(self.policy):raise QueueError("base refresh authority changed")
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            row=d.execute("SELECT * FROM continuous_maintenance WHERE id=1").fetchone()
            if (not row or row["key"]!=key or row["state"] not in {"fetching","installing"}
                    or self.policy_fingerprint not in {row["old_policy_fingerprint"],row["new_policy_fingerprint"]}):
                raise QueueError("base refresh intent unavailable")
            if any(item["base_sha"]!=row["new_head"] for item in new_policy["requirements"].values()):raise QueueError("base refresh head mismatch")
            new_fp=digest(new_policy)
            safe=d.execute("SELECT template_name FROM continuous_queue WHERE attempts=0 AND state IN ('proposed','registering','ready') AND policy_fingerprint=?",(row["old_policy_fingerprint"],)).fetchall()
            templates=sorted({item[0] for item in safe if item[0]})
            if row["state"]=="installing":
                if row["new_policy_fingerprint"]!=new_fp or row["bundle_sha256"]!=bundle_sha256 or json.loads(row["rebase_templates"])!=templates:raise QueueError("base refresh preparation conflict")
            else:d.execute("UPDATE continuous_maintenance SET state='installing',new_policy=?,new_policy_fingerprint=?,bundle_sha256=?,rebase_templates=?,receipts='{}',updated=? WHERE id=1",
                           (canonical(new_policy),new_fp,bundle_sha256,canonical(templates),self.clock()))
        return self.maintenance()
    def refresh_receipt(self,key,receipt):
        required={"target","old_policy_fingerprint","new_policy_fingerprint","new_head","bundle_sha256","installed_sha256"}
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            row=d.execute("SELECT * FROM continuous_maintenance WHERE id=1").fetchone()
            if (not row or row["key"]!=key or row["state"]!="installing" or not isinstance(receipt,dict) or set(receipt)!=required
                    or receipt["target"] not in TARGETS or receipt["old_policy_fingerprint"]!=row["old_policy_fingerprint"]
                    or receipt["new_policy_fingerprint"]!=row["new_policy_fingerprint"] or receipt["new_head"]!=row["new_head"]
                    or receipt["bundle_sha256"]!=row["bundle_sha256"] or not DIGEST.fullmatch(str(receipt["installed_sha256"]))):
                raise QueueError("invalid base refresh receipt")
            receipts=json.loads(row["receipts"]);old=receipts.get(receipt["target"])
            if old is not None and old!=receipt:raise QueueError("base refresh receipt conflict")
            receipts[receipt["target"]]=receipt
            changed=d.execute("UPDATE continuous_maintenance SET receipts=?,updated=? WHERE id=1 AND key=? AND state='installing'",
                              (canonical(receipts),self.clock(),key))
            if changed.rowcount!=1:raise QueueError("base refresh receipt raced")
        return self.maintenance()
    def commit_refresh(self,key):
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            row=d.execute("SELECT * FROM continuous_maintenance WHERE id=1").fetchone()
            if not row or row["key"]!=key:raise QueueError("base refresh intent unavailable")
            if row["state"]=="complete":return {"state":"complete","policy_fingerprint":row["new_policy_fingerprint"],"rebased":[]}
            if row["state"]!="installing":raise QueueError("base refresh is not installed")
            receipts=json.loads(row["receipts"])
            if set(receipts)!=TARGETS:raise QueueError("three base refresh receipts required")
            new_policy=json.loads(row["new_policy"]);new_fp=row["new_policy_fingerprint"];rebased=[]
            candidates=d.execute("SELECT * FROM continuous_queue WHERE attempts=0 AND state IN ('proposed','registering','ready') AND policy_fingerprint=?",(row["old_policy_fingerprint"],)).fetchall()
            for candidate in candidates:
                snapshot={"row":dict(candidate),
                          "receipts":[dict(value) for value in d.execute("SELECT * FROM continuous_receipts WHERE queue_id=? ORDER BY target",(candidate["id"],))],
                          "dependency_receipts":[dict(value) for value in d.execute("SELECT * FROM continuous_dependency_receipts WHERE queue_id=? ORDER BY dependency_id",(candidate["id"],))]}
                sequence=d.execute("SELECT coalesce(max(sequence),0)+1 FROM continuous_queue_history WHERE item_id=?",(candidate["id"],)).fetchone()[0]
                d.execute("INSERT INTO continuous_queue_history VALUES(?,?,?,?)",(candidate["id"],sequence,canonical(snapshot),self.clock()))
                old_execution=json.loads(candidate["execution_policy"]);requirement=new_policy["requirements"][candidate["requirement_id"]]
                selected=old_execution["selected_path_set_id"];scope=requirement["path_sets"][selected]
                execution={**requirement,"selected_path_set_id":selected,"allowed_paths":scope["allowed_paths"],
                           "contract_files":scope["contract_files"],"acceptance_profile":scope["acceptance_profile"]}
                acceptance=json.loads(candidate["acceptance"])
                proposal_fp=proposal_digest(candidate["id"],candidate["requirement_id"],candidate["slice_key"],selected,
                                            candidate["goal"],acceptance,execution,new_fp)
                d.execute("""UPDATE continuous_queue SET state='proposed',base_sha=?,allowed_paths=?,contract_files=?,
                    proposal_fingerprint=?,policy_fingerprint=?,execution_policy=?,review_fingerprint=NULL,
                    template_name=NULL,template_fingerprint=NULL,blocker=NULL,updated=? WHERE id=? AND attempts=0""",
                    (execution["base_sha"],canonical(execution["allowed_paths"]),canonical(execution["contract_files"]),
                     proposal_fp,new_fp,canonical(execution),self.clock(),candidate["id"]))
                d.execute("DELETE FROM continuous_receipts WHERE queue_id=?",(candidate["id"],))
                d.execute("DELETE FROM continuous_dependency_receipts WHERE queue_id=?",(candidate["id"],))
                rebased.append(candidate["id"])
            d.execute("UPDATE continuous_maintenance SET state='complete',updated=? WHERE id=1",(self.clock(),))
        self.policy=validate_policy(new_policy);self.policy_fingerprint=new_fp
        return {"state":"complete","policy_fingerprint":new_fp,"rebased":rebased,
                "removed_templates":json.loads(row["rebase_templates"])}
    def existing_work_receipt(self,receipt):
        required={"job_id","template","pr_url","pr_number","head_sha","base_ref","github_state","merge_commit_sha","title","body","files"}
        if (not isinstance(receipt,dict) or set(receipt)!=required or not ID.fullmatch(str(receipt.get("job_id","")))
                or not SHA.fullmatch(str(receipt.get("head_sha",""))) or receipt.get("base_ref")!="feat/loop-pilot"
                or receipt.get("github_state") not in {"open","merged","closed_unmerged"}
                or (receipt.get("merge_commit_sha") is not None and not SHA.fullmatch(str(receipt["merge_commit_sha"])))
                or (receipt.get("github_state")=="merged")!=(receipt.get("merge_commit_sha") is not None)
                or not isinstance(receipt.get("pr_number"),int) or receipt["pr_number"]<1
                or not isinstance(receipt.get("title"),str) or len(receipt["title"])>500
                or not isinstance(receipt.get("body"),str) or len(receipt["body"])>10_000
                or not isinstance(receipt.get("files"),list) or not receipt["files"] or len(receipt["files"])>100
                or any(not isinstance(v,str) or not v or len(v)>500 for v in receipt["files"])):
            raise QueueError("invalid existing-work receipt")
        repositories={value["repository"] for value in self.policy["requirements"].values()}
        if len(repositories)!=1:raise QueueError("existing-work repository unavailable")
        expected_url=f"https://github.com/{next(iter(repositories))}/pull/{receipt['pr_number']}"
        if receipt["pr_url"]!=expected_url:raise QueueError("existing-work repository mismatch")
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            has_jobs=d.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone()
            row=d.execute("SELECT id,template,state,pr_url,candidate_sha FROM jobs WHERE id=?",(receipt["job_id"],)).fetchone() if has_jobs else None
            if (not row or row["state"]!="ready_pr" or row["template"]!=receipt["template"]
                    or row["pr_url"]!=receipt["pr_url"] or row["candidate_sha"]!=receipt["head_sha"]):raise QueueError("existing-work job changed")
            fingerprint=digest(receipt);old=d.execute("SELECT receipt_fingerprint FROM continuous_existing_work WHERE job_id=?",(receipt["job_id"],)).fetchone()
            if old and old[0]!=fingerprint:raise QueueError("existing-work receipt conflict")
            d.execute("INSERT OR IGNORE INTO continuous_existing_work VALUES(?,?,?,?)",(receipt["job_id"],canonical(receipt),fingerprint,self.clock()))
        return {**receipt,"fingerprint":fingerprint}
    def claim(self,lease_seconds=300):
        now=self.clock()
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            if self.maintenance_active(d):return None
            jobs_exists=d.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone()
            if jobs_exists and d.execute("SELECT 1 FROM jobs WHERE state IN ('queued','dispatching','publishing','unknown','recoverable') LIMIT 1").fetchone():return None
            operations_exists=d.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='operations'").fetchone()
            if operations_exists:
                for operation in d.execute("SELECT request FROM operations WHERE state IN ('dispatching','running','unknown','cancelling')"):
                    try:request=json.loads(operation[0])
                    except Exception:return None
                    if request.get("source")=="continuous_planning":return None
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
            if self.maintenance_active(d):raise QueueError("base refresh maintenance active")
            row=d.execute("SELECT * FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            if not row or row["policy_fingerprint"]!=self.policy_fingerprint or row["lease_id"]!=lease_id or row["state"] not in {"dispatching","running","unknown","blocked"}:raise QueueError("queue lease lost")
            if state=="ready_pr" and (not SHA.fullmatch(str(evidence.get("head_sha",""))) or not str(evidence.get("pr_url","")).startswith("https://")):raise QueueError("ready PR evidence required")
            event={"state":state,"lease_id":lease_id,"evidence":evidence}
            terminal=state in {"ready_pr","cancelled"}
            sequence=d.execute("SELECT coalesce(max(sequence),0)+1 FROM continuous_attempt_events WHERE queue_id=?",(item_id,)).fetchone()[0]
            d.execute("INSERT INTO continuous_attempt_events VALUES(?,?,?,?)",(item_id,sequence,canonical(event),self.clock()))
            result=d.execute("""UPDATE continuous_queue SET state=?,external_run_id=coalesce(?,external_run_id),
external_job_id=coalesce(?,external_job_id),evidence=?,pr_url=coalesce(?,pr_url),blocker=coalesce(?,blocker),
lease_id=?,lease_expires=?,updated=? WHERE id=? AND state=? AND lease_id=?""",(state,evidence.get("run_id"),evidence.get("job_id"),canonical(evidence),evidence.get("pr_url"),evidence.get("blocker"),None if terminal else lease_id,None if terminal else row["lease_expires"],self.clock(),item_id,row["state"],lease_id))
            if result.rowcount!=1:raise QueueError("queue transition raced")
        return self.get(item_id)
    def settle(self,item_id,receipt):
        required={"stopped","previous_lease_id","external_run_id","external_job_id","evidence_ref","reason"}
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            if self.maintenance_active(d):raise QueueError("base refresh maintenance active")
            row=d.execute("SELECT * FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            if (not row or row["policy_fingerprint"]!=self.policy_fingerprint or not isinstance(receipt,dict)
                    or set(receipt)!=required or receipt["stopped"] is not True
                    or receipt["reason"] not in {"nonretryable","attempts_exhausted","user_stop"}
                    or row["state"] not in {"unknown","blocked"} or receipt["previous_lease_id"]!=row["lease_id"]
                    or receipt["external_run_id"]!=row["external_run_id"] or receipt["external_job_id"]!=row["external_job_id"]
                    or not isinstance(receipt["evidence_ref"],str) or not receipt["evidence_ref"]):
                raise QueueError("confirmed terminal settlement required")
            sequence=d.execute("SELECT coalesce(max(sequence),0)+1 FROM continuous_attempt_events WHERE queue_id=?",(item_id,)).fetchone()[0]
            d.execute("INSERT INTO continuous_attempt_events VALUES(?,?,?,?)",(item_id,sequence,canonical({"state":"settled","stop_receipt":receipt}),self.clock()))
            state="cancelled" if receipt["reason"]=="user_stop" else "blocked"
            changed=d.execute("UPDATE continuous_queue SET state=?,lease_id=NULL,lease_expires=NULL,updated=? WHERE id=? AND state=? AND lease_id IS ?",(state,self.clock(),item_id,row["state"],row["lease_id"]))
            if changed.rowcount!=1:raise QueueError("queue settlement raced")
        return self.get(item_id)
    def retry(self,item_id,receipt):
        required={"stopped","previous_lease_id","external_run_id","external_job_id","evidence_ref","reason"}
        with self.db() as d:
            d.execute("BEGIN IMMEDIATE")
            if self.maintenance_active(d):raise QueueError("base refresh maintenance active")
            row=d.execute("SELECT * FROM continuous_queue WHERE id=?",(item_id,)).fetchone()
            if not row or row["policy_fingerprint"]!=self.policy_fingerprint or not isinstance(receipt,dict) or set(receipt)!=required or receipt["stopped"] is not True or receipt.get("reason") not in {"local_failure","transport_unknown"} or row["state"] not in {"unknown","blocked"} or row["attempts"]>=3 or receipt["previous_lease_id"]!=row["lease_id"] or receipt["external_run_id"]!=row["external_run_id"] or receipt["external_job_id"]!=row["external_job_id"] or not isinstance(receipt["evidence_ref"],str) or not receipt["evidence_ref"]:raise QueueError("confirmed stopped predecessor required")
            sequence=d.execute("SELECT coalesce(max(sequence),0)+1 FROM continuous_attempt_events WHERE queue_id=?",(item_id,)).fetchone()[0]
            d.execute("INSERT INTO continuous_attempt_events VALUES(?,?,?,?)",(item_id,sequence,canonical({"state":"retry_ready","stop_receipt":receipt}),self.clock()))
            result=d.execute("UPDATE continuous_queue SET state='ready',lease_id=NULL,lease_expires=NULL,external_run_id=NULL,external_job_id=NULL,updated=? WHERE id=? AND state=? AND lease_id IS ?",(self.clock(),item_id,row["state"],row["lease_id"]))
            if result.rowcount!=1:raise QueueError("queue retry raced")
        return self.get(item_id)
    def status(self):
        with self.db() as d:
            rows=[dict(r) for r in d.execute("SELECT id,requirement_id,slice_key,state,attempts,updated,pr_url,blocker,lease_id,depends_on,base_sha FROM continuous_queue ORDER BY created,id")]
            merges={r["queue_id"]:json.loads(r["receipt"]).get("merge_commit_sha") for r in d.execute("SELECT queue_id,receipt FROM continuous_merges")}
        for row in rows:
            row["depends_on"]=json.loads(row["depends_on"])
            if row["id"] in merges:row["merge_commit_sha"]=merges[row["id"]]
        with self.db() as d:
            has_jobs=d.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone()
            candidate_count=d.execute("SELECT count(*) FROM jobs WHERE state='ready_pr' AND pr_url IS NOT NULL AND candidate_sha IS NOT NULL").fetchone()[0] if has_jobs else 0
            candidates=[dict(v) for v in d.execute("SELECT id AS job_id,template,pr_url,candidate_sha AS head_sha FROM jobs WHERE state='ready_pr' AND pr_url IS NOT NULL AND candidate_sha IS NOT NULL ORDER BY id LIMIT 32")] if has_jobs else []
            verified={v["job_id"]:(json.loads(v["receipt"]),v["receipt_fingerprint"]) for v in d.execute("SELECT * FROM continuous_existing_work")}
        existing=[]
        for candidate in candidates:
            stored=verified.get(candidate["job_id"])
            if stored and all(stored[0].get(key)==candidate[key] for key in ("job_id","template","pr_url","head_sha")):existing.append({**stored[0],"fingerprint":stored[1]})
        active_counts={key:sum(row["requirement_id"]==key and row["state"] not in {"rejected","cancelled"} for row in rows) for key in self.policy["requirements"]}
        total_counts={key:sum(row["requirement_id"]==key for row in rows) for key in self.policy["requirements"]}
        eligible=[key for key,item in self.policy["requirements"].items() if active_counts[key]<item["max_slices"] and total_counts[key]<item["max_slices"]*3]
        planning_snapshot=digest({"policy_fingerprint":self.policy_fingerprint,
            "items":[{key:row.get(key) for key in ("id","requirement_id","slice_key","state")} for row in rows],
            "existing_work":sorted(value["fingerprint"] for value in existing),"legacy_ready_pr_overflow":candidate_count>32,
            "eligible_requirements":eligible})
        return {"policy_fingerprint":self.policy_fingerprint,"planning_snapshot":planning_snapshot,
        "legacy_ready_pr_candidates":candidates,"legacy_ready_pr_overflow":candidate_count>32,"existing_work":existing,"maintenance":self.maintenance(),"continuous_ready":False,
        "plan_exhausted":not eligible,"eligible_requirements":eligible,
        "current":next((r for r in rows if (r["state"] in {"dispatching","running","unknown"} or (r["state"]=="blocked" and r.get("lease_id")))),None),
        "next":next((r for r in rows if r["state"] in {"ready","registering","proposed"}),None),"items":rows}
