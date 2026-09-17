"""Persistent LOOP bridge. Paperclip schedules; this process never schedules Director.

stdlib-only, Python 3.12+. Model-facing credentials cannot wake/cancel other runs
or publish. Gateway operations use the official Paperclip hermes_gateway wire API.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import os
import re
import sqlite3
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

TERMINAL = {"completed", "failed", "error", "cancelled", "canceled", "stopped", "interrupted"}
JOB_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9:_-]{1,160}$")
PUBLICATION_PERMIT = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
class BridgeError(Exception):
    def __init__(self, status, message, uncertain=None, revoked=False):
        self.status, self.message = status, message
        self.revoked = revoked
        self.uncertain = status >= 500 if uncertain is None else uncertain

def publication_staging_ref(job_id, permit):
    if not isinstance(job_id,str) or not JOB_ID.fullmatch(job_id) or not isinstance(permit,str) or not PUBLICATION_PERMIT.fullmatch(permit):
        raise BridgeError(400,"invalid publication staging identity")
    return f"refs/heads/loop-staging/{job_id}/{hashlib.sha256(permit.encode()).hexdigest()}"

def template_fingerprint(name,definition):
    if not isinstance(name,str) or not isinstance(definition,dict):raise BridgeError(400,"invalid job template contract")
    profile=definition.get("profile","fedor");profile_id=definition.get("profile_id");profile_revision=definition.get("profile_revision")
    try:canonical_profile_id=str(uuid.UUID(profile_id))
    except (ValueError,TypeError,AttributeError):raise BridgeError(400,"job template needs stable Agent Profile identity") from None
    if profile!="fedor" or canonical_profile_id!=profile_id or not isinstance(profile_revision,int) or isinstance(profile_revision,bool) or profile_revision<0:raise BridgeError(400,"job template needs stable Agent Profile identity")
    portable={key:definition.get(key) for key in ("base_sha","prompt_sha256","allowed_paths","contract_files","profile","profile_id","profile_revision")}
    for key in ("allowed_paths","contract_files"):
        if isinstance(portable[key],list):portable[key]=sorted(portable[key])
    return hashlib.sha256(json.dumps({"name":name,"contract":portable},sort_keys=True,separators=(",",":")).encode()).hexdigest()

def secret(path):
    p = Path(path)
    if p.stat().st_mode & 0o077: raise ValueError("secret file must have mode 0600")
    value = p.read_text().strip()
    if not value: raise ValueError("empty secret file")
    return value

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "redirect denied", headers, fp)

class JsonHTTP:
    def __init__(self, base, token, timeout=30, header="Authorization", trusted_bridge=False):
        self.header=header
        self.trusted_bridge=trusted_bridge
        parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.query or parsed.fragment: raise ValueError("invalid upstream URL")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "hermes", "paperclip", "bridge"}: raise ValueError("remote upstream requires HTTPS")
        self.base, self.token, self.timeout = base.rstrip("/"), token, timeout
    def call(self, method, path, payload=None, headers=None):
        req = Request(self.base + path, data=None if payload is None else json.dumps(payload).encode(), method=method,
            headers={self.header: ("Bearer " + self.token) if self.header=="Authorization" else self.token, "Content-Type": "application/json", "User-Agent": "LOOP-Bridge/1", **(headers or {})})
        try:
            with build_opener(NoRedirect()).open(req, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000: raise BridgeError(502, "upstream response too large")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            try: body=json.loads(exc.read(4096))
            except Exception: body={}
            if self.trusted_bridge and isinstance(body,dict) and isinstance(body.get("uncertain"),bool):
                uncertain=body["uncertain"]
                raise BridgeError(exc.code, f"Bridge rejected request (HTTP {exc.code})" if not uncertain else "Bridge result uncertain", uncertain) from None
            if 400 <= exc.code < 500:
                uncertain=isinstance(body,dict) and body.get("uncertain") is True
                raise BridgeError(exc.code, f"upstream rejected request (HTTP {exc.code})", uncertain) from None
            raise BridgeError(502, "upstream response uncertain", True) from None
        except (URLError, TimeoutError, OSError, ValueError):
            # Never expose transport errors: urllib exceptions may carry secrets or body.
            raise BridgeError(502, "upstream unavailable; reconcile intent") from None

class Bridge:
    def __init__(self, database, hermes, paperclip, director_id, openhands=None, publisher=None, context_reader=None,
                 continuous_policy=None):
        self.publisher = publisher
        self.context_reader = context_reader
        self.approved_templates = {}
        self.database, self.hermes, self.paperclip, self.director_id, self.openhands = str(database), hermes, paperclip, director_id, openhands
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.continuous = None
        if continuous_policy is not None:
            try:
                from .continuous_queue import ContinuousQueue
            except ImportError:
                from continuous_queue import ContinuousQueue
            self.continuous = ContinuousQueue(database, continuous_policy)
        self.guard = threading.RLock()
        # Remote publication is split into independently fenced mutations so a
        # cancellation can revoke an attempt while read-only destination checks
        # are blocked. Only one finisher may materialize a job at a time.
        self.publication_gate = threading.RLock()
        self.publication_finish_gate = threading.Lock()
        self.cancel_request_guard = threading.Lock()
        self.cancel_requests = set()
        with self.tx() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, key TEXT NOT NULL,
                    request_hash TEXT NOT NULL, request TEXT NOT NULL, external_id TEXT,
                    state TEXT NOT NULL, generation INTEGER NOT NULL DEFAULT 1,
                    cursor INTEGER NOT NULL DEFAULT 0, response TEXT,
                    stop_confirmed INTEGER NOT NULL DEFAULT 0,
                    created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(kind,key));
                CREATE TABLE IF NOT EXISTS events (
                    operation_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(operation_id,sequence));
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                INSERT OR IGNORE INTO settings VALUES ('paused','false');
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, director_run TEXT NOT NULL, generation INTEGER NOT NULL,
                    template TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
                    external_id TEXT, candidate_sha TEXT, verification TEXT, pr_url TEXT);
            """)
            operation_columns={r[1] for r in db.execute("PRAGMA table_info(operations)")}
            if "execution_stop_confirmed" not in operation_columns:
                db.execute("ALTER TABLE operations ADD COLUMN execution_stop_confirmed INTEGER NOT NULL DEFAULT 0")
            columns={r[1] for r in db.execute("PRAGMA table_info(jobs)")}
            for name,definition in (("publication_permit","TEXT"),("publication_active","INTEGER NOT NULL DEFAULT 0"),("recovery_receipt","TEXT"),("push_outcome","TEXT"),("push_publisher_id","TEXT"),("push_process_stopped","INTEGER NOT NULL DEFAULT 0"),("push_receipt","TEXT"),("publication_settlement","TEXT")):
                if name not in columns: db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
            if "template_fingerprint" not in columns:db.execute("ALTER TABLE jobs ADD COLUMN template_fingerprint TEXT")
            db.execute("UPDATE jobs SET state='unknown' WHERE state='publishing'")
            # The local process cannot infer whether an interrupted create reached upstream.
            db.execute("UPDATE operations SET state='unknown',updated=? WHERE state='dispatching'", (time.time(),))
        os.chmod(database, 0o600)
    @contextmanager
    def tx(self):
        with self.guard:
            db = sqlite3.connect(self.database, timeout=20)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally: db.close()
    def context(self, offset=0):
        if not isinstance(offset,int) or offset<0 or offset>10000:raise BridgeError(400,"invalid context offset")
        if not self.context_reader:raise BridgeError(503,"context reader not configured",False)
        return self.context_reader.call("GET","/api/loop/context?offset="+str(offset))
    def get(self, op_id):
        with self.tx() as db:
            row = db.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone()
        if not row: raise BridgeError(404, "run unavailable")
        return dict(row)
    def intent(self, kind, key, payload):
        if not isinstance(key, str) or not SAFE_ID.fullmatch(key): raise BridgeError(400, "invalid idempotency key")
        if shutil.disk_usage(Path(self.database).parent).free < 536870912: raise BridgeError(503,"disk reserve low; dispatch paused",False)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.tx() as db:
            old = db.execute("SELECT * FROM operations WHERE kind=? AND key=?", (kind, key)).fetchone()
            if old:
                if old["request_hash"] != digest: raise BridgeError(409, "idempotency payload conflict")
                return dict(old), False
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == "true": raise BridgeError(409, "dispatch paused")
            if kind == "hermes":
                parent = db.execute("SELECT id,key,state,request FROM operations WHERE kind='paperclip' AND external_id=?", (key,)).fetchone()
                if parent and json.loads(parent["request"]).get("source") == "operator_batch":
                    if self.operator_execution(json.loads(parent["request"])) != json.loads(parent["request"]):
                        raise BridgeError(409, "operator parent contract changed", False)
                if hasattr(self, "native_control"):
                    self.validate_native_parent(db, parent)
                if parent and parent["state"] in {"cancelling", "cancelled", "interrupted", "failed", "error"}: raise BridgeError(409, "parent run revoked")
            if kind == "paperclip" and payload.get("source") == "native_telegram" and hasattr(self, "native_control"):
                row = db.execute("SELECT * FROM native_drafts WHERE id=?", (payload.get("draft_id"),)).fetchone()
                if not row or self.native_control.approved_execution(dict(row)) != payload:
                    raise BridgeError(409, "persisted owner approval unavailable", False)
            # One active management run; queued events remain owned by Paperclip.
            if kind == "hermes" and db.execute("SELECT 1 FROM operations WHERE kind='hermes' AND state IN ('dispatching','running','unknown','cancelling')").fetchone(): raise BridgeError(409, "Director lease busy or uncertain")
            op_id, now = str(uuid.uuid4()), time.time()
            db.execute("INSERT INTO operations (id,kind,key,request_hash,request,state,created,updated) VALUES (?,?,?,?,?,'dispatching',?,?)", (op_id,kind,key,digest,encoded,now,now))
        return self.get(op_id), True
    def operator_execution(self, payload):
        required = {"source", "job_id", "template", "template_fingerprint"}
        if not required <= set(payload) or set(payload) - required - {"goal"} or payload.get("source") != "operator_batch":
            raise BridgeError(400, "exact operator batch envelope required", False)
        name = payload.get("template")
        job_id = payload.get("job_id")
        if not isinstance(name, str) or name not in self.approved_templates or not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
            raise BridgeError(400, "admitted operator job template required", False)
        if payload["template_fingerprint"] != template_fingerprint(name, self.approved_templates[name]):
            raise BridgeError(409, "operator template fingerprint changed", False)
        return {key: payload[key] for key in required} | {"goal": "Execute only the operator-authorized fixed template. Propose exactly this job_id and template using your trusted run_id and generation. Stop after proposal; the runner owns verification and PR publication."}

    def continuous_execution(self,payload):
        queue=self.continuous_required()
        if not isinstance(payload,dict) or set(payload)!={"source","policy_fingerprint","planning_snapshot","requirements","queue","goal"} or payload.get("source")!="continuous_planning" or payload.get("policy_fingerprint")!=queue.policy_fingerprint:
            raise BridgeError(409,"continuous planning envelope changed",False)
        expected={key:{**{field:value[field] for field in ("objective","acceptance","max_slices","depends_on","source_evidence")},
            "path_sets":{name:scope["description"] for name,scope in value["path_sets"].items()}}
            for key,value in queue.policy["requirements"].items()}
        if (payload.get("requirements")!=expected or not isinstance(payload.get("queue"),dict)
                or not re.fullmatch(r"[0-9a-f]{64}",str(payload.get("planning_snapshot","")))):
            raise BridgeError(409,"continuous planning policy changed",False)
        return payload

    def execution_envelope(self, key):
        native = self.native_control.execution_envelope(key) if hasattr(self, "native_control") else None
        if native is not None:
            return native
        with self.tx() as db:
            parent = db.execute("SELECT * FROM operations WHERE kind='paperclip' AND external_id=?", (key,)).fetchone()
        if parent is None:
            return None  # Preserve standalone Hermes fixtures without native control.
        approved = json.loads(parent["request"])
        if approved.get("source") == "continuous_planning":
            return self.continuous_execution(approved)
        if approved.get("source") != "operator_batch":
            return None
        expected = self.operator_execution(approved)
        if approved != expected or parent["state"] in {"cancelling", "cancelled", "failed", "error", "interrupted", "unknown", "rejected"}:
            raise BridgeError(409, "operator parent contract revoked", False)
        return expected

    def validate_native_parent(self, db, parent):
        if parent is None:
            raise BridgeError(409, "acknowledged parent binding required", False)
        approved = json.loads(parent["request"])
        if approved.get("source") != "native_telegram":
            if parent["key"].startswith(("native-telegram-", "native-retry-")):
                raise BridgeError(409, "persisted native envelope missing", False)
            return
        row = db.execute("SELECT * FROM native_drafts WHERE id=?", (approved.get("draft_id"),)).fetchone()
        if not row or self.native_control.approved_execution(dict(row)) != approved:
            raise BridgeError(409, "persisted owner-approved parent required", False)
        if row["run_id"] and row["run_id"] != parent["id"] and parent["key"] != "native-retry-" + row["run_id"]:
            raise BridgeError(409, "native attempt superseded", False)
        if parent["state"] in {"cancelling", "cancelled", "failed", "error", "interrupted", "unknown", "rejected"}:
            raise BridgeError(409, "parent run revoked", False)

    def create(self, kind, key, payload):
        if kind == "paperclip" and payload.get("source") == "operator_batch":
            payload = self.operator_execution(payload)
        envelope = self.execution_envelope(key) if kind == "hermes" else None
        op, new = self.intent(kind, key, payload)
        if not new:
            if op["state"] in {"dispatching", "unknown"}: raise BridgeError(409, "dispatch uncertain; operator reconciliation required",True)
            if op["state"]=="rejected": raise BridgeError(json.loads(op["response"])["status"],"upstream rejected this intent; no dispatch performed",False)
            return {"run_id": op["id"], "status": op["state"]}
        try:
            if kind == "hermes":
                bound_payload={**payload,"input":f"LOOP trusted attempt identity: run_id={op['id']}; generation={op['generation']}. Use this identity for Bridge job proposals.\n\n"+payload["input"]}
                if envelope is not None:
                    label = ("owner-approved native" if envelope["source"] == "native_telegram"
                             else "continuous planning" if envelope["source"] == "continuous_planning"
                             else "operator-authorized batch")
                    bound_payload["instructions"] = ("Use only the trusted LOOP envelope in input. For continuous planning, propose bounded slices through loop_propose_continuous; "
                        "for execution propose the exact fixed job. Never select paths, profiles, commands or credentials. Stop after proposals.")
                    bound_payload["input"] = bound_payload["input"].split("\n\n", 1)[0] + "\n\nLOOP trusted " + label + " task: " + json.dumps(envelope, sort_keys=True)
                response = self.hermes.call("POST", "/v1/runs", bound_payload, {"Idempotency-Key": key, "X-Hermes-Session-Key": payload["session_id"]})
            else:
                response = self.paperclip.call("POST", "/api/agents/"+quote(self.director_id,safe="")+"/wakeup", {"source":"on_demand", "triggerDetail":"manual", "reason":"LOOP event", "payload":payload, "idempotencyKey":key, "forceFreshSession":False})
            external_id = response.get("run_id") or response.get("runId") or response.get("id")
            if not external_id or not isinstance(external_id, str) or not SAFE_ID.fullmatch(external_id): raise BridgeError(502,"upstream did not confirm run identity")
        except Exception as exc:
            known=isinstance(exc,BridgeError) and not exc.uncertain
            with self.tx() as db:
                db.execute("UPDATE operations SET state=CASE WHEN state='dispatching' THEN ? ELSE state END,response=?,updated=? WHERE id=?",("rejected" if known else "unknown",json.dumps({"status":exc.status}) if known else None,time.time(),op["id"]))
            if known: raise BridgeError(exc.status,"upstream rejected dispatch; no run acknowledged",False) from None
            raise BridgeError(502,"dispatch uncertain; do not retry upstream",True) from None
        with self.tx() as db:
            db.execute("UPDATE operations SET external_id=?,state=CASE WHEN state='dispatching' THEN 'running' ELSE state END,updated=? WHERE id=?", (external_id,time.time(),op["id"]))
        result = self.get(op["id"])
        if result["state"] == "cancelling": self.cancel(op["id"])
        return {"run_id": op["id"], "status": self.get(op["id"])["state"]}
    def reconcile(self, op_id):
        op = self.get(op_id)
        if not op["external_id"]: return {"run_id": op_id,"status":op["state"],"reason":"external identity unknown; no redispatch"}
        if op["state"] in {"cancelling", "cancelled"}: return self.cancel(op_id)
        client = self.hermes if op["kind"] == "hermes" else self.paperclip
        route = "/v1/runs/" if op["kind"] == "hermes" else "/api/heartbeat-runs/"
        response = client.call("GET",route+quote(op["external_id"],safe=""))
        status = response.get("status")
        if op["kind"] == "paperclip": status = {"succeeded":"completed", "scheduled_retry":"interrupted", "timed_out":"failed"}.get(status,status)
        if status not in TERMINAL | {"running", "queued"}: raise BridgeError(502,"unknown upstream status")
        with self.tx() as db:
            current = db.execute("SELECT state,generation FROM operations WHERE id=?",(op_id,)).fetchone()
            if current["generation"] != op["generation"] or current["state"] in {"cancelling","cancelled"}: return {"run_id":op_id,"status":current["state"]}
            db.execute("UPDATE operations SET state=?,response=?,updated=? WHERE id=?",(status,json.dumps(response),time.time(),op_id))
        return {**response,"run_id":op_id,"status":status}
    def adopt(self, op_id, external_id):
        # Operator-only recovery after an independently checked upstream lookup.
        if not SAFE_ID.fullmatch(external_id): raise BridgeError(400,"invalid external identity")
        with self.tx() as db:
            db.execute("UPDATE operations SET external_id=? WHERE id=? AND external_id IS NULL AND state IN ('unknown','cancelling')",(external_id,op_id))
        return self.reconcile(op_id)
    def cancel(self, op_id):
        if hasattr(self, "native_control"):
            return self.native_control.cancel_run(op_id)
        return self._cancel(op_id)

    def _cancel(self, op_id):
        # Fence and revoke queued/active jobs BEFORE any network call.
        with self.cancel_request_guard: self.cancel_requests.add(op_id)
        with self.publication_gate:
            with self.tx() as db:
                op = db.execute("SELECT * FROM operations WHERE id=?",(op_id,)).fetchone()
                if not op:
                    with self.cancel_request_guard: self.cancel_requests.discard(op_id)
                    raise BridgeError(404,"run unavailable")
                ready = db.execute("""
                    SELECT 1 FROM jobs j JOIN operations d ON d.id=j.director_run
                    WHERE j.state='ready_pr' AND (
                        d.id=? OR (?='paperclip' AND d.kind='hermes' AND d.key=?)
                    ) LIMIT 1
                """,(op_id,op["kind"],op["external_id"])).fetchone()
                if ready and op["state"]=="completed" and op["stop_confirmed"]:
                    with self.cancel_request_guard:self.cancel_requests.discard(op_id)
                    return {"run_id":op_id,"status":"completed","reason":"ready_pr_exists"}
                if op["state"] == "cancelled" and op["stop_confirmed"]: return {"run_id":op_id,"status":"cancelled"}
                db.execute("UPDATE operations SET state='cancelling',generation=generation+1,updated=? WHERE id=? AND state!='cancelling'",(time.time(),op_id))
                db.execute("UPDATE jobs SET state='cancelled' WHERE director_run=? AND state!='ready_pr'",(op_id,))
        stop_ok = False
        if op["external_id"]:
            try:
                if op["kind"] == "hermes":
                    self.hermes.call("POST","/v1/runs/"+quote(op["external_id"],safe="")+"/stop",{})
                    result = self.hermes.call("GET","/v1/runs/"+quote(op["external_id"],safe=""))
                    stop_ok = result.get("status") in TERMINAL
                else:
                    # Board token, no implicit authority for the Director agent token.
                    self.paperclip.call("POST","/api/heartbeat-runs/"+quote(op["external_id"],safe="")+"/cancel",{})
            except BridgeError: pass
            if op["kind"] == "paperclip":
                # Even a failed Paperclip cancellation cannot skip stopping Hermes.
                with self.tx() as db: child = db.execute("SELECT id FROM operations WHERE kind='hermes' AND key=?",(op["external_id"],)).fetchone()
                if child: stop_ok = self.cancel(child["id"])["status"] in {"cancelled","completed"}
                # Without gateway binding, cancellation remains unconfirmed.
        with self.tx() as db:
            publication_open = bool(db.execute("SELECT 1 FROM jobs WHERE director_run=? AND publication_active=1",(op_id,)).fetchone())
            jobs = db.execute("SELECT external_id FROM jobs WHERE director_run=? AND external_id IS NOT NULL",(op_id,)).fetchall()
        for job in jobs:
            try:
                if not self.openhands: stop_ok = False
                else:
                    self.openhands.call("POST","/api/conversations/"+quote(job["external_id"],safe="")+"/pause")
                    observed=self.openhands.call("GET","/api/conversations/"+quote(job["external_id"],safe=""))
                    if observed.get("execution_status") not in {"paused","stopped","finished","error"}: stop_ok=False
            except BridgeError: stop_ok = False
        with self.tx() as db:
            ready = db.execute("""
                SELECT 1 FROM jobs j JOIN operations d ON d.id=j.director_run
                WHERE j.state='ready_pr' AND (d.id=? OR (?='paperclip' AND d.kind='hermes' AND d.key=?)) LIMIT 1
            """,(op_id,op["kind"],op["external_id"])).fetchone()
            if stop_ok and ready:
                final_state="completed"
            elif stop_ok and not publication_open:
                final_state="cancelled"
            else:
                final_state="cancelling"
            db.execute("UPDATE operations SET state=?,stop_confirmed=?,execution_stop_confirmed=?,updated=? WHERE id=?",(final_state,int(final_state in {"cancelled","completed"}),int(stop_ok),time.time(),op_id))
        result={"run_id":op_id,"status":final_state}
        if ready:result["reason"]="ready_pr_exists"
        return result
    def paperclip_events(self, op_id):
        op = self.get(op_id)
        if op["kind"] != "paperclip" or not op["external_id"]: raise BridgeError(409,"Paperclip identity unavailable")
        response = self.paperclip.call("GET",f"/api/heartbeat-runs/{quote(op['external_id'],safe='')}/events?afterSeq={op['cursor']}&limit=200")
        events = response if isinstance(response,list) else response.get("events",[])
        with self.tx() as db:
            for event in events:
                seq = event.get("seq")
                if not isinstance(seq,int) or seq <= op["cursor"]: continue
                db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?)",(op_id,seq,json.dumps(event)))
                db.execute("UPDATE operations SET cursor=max(cursor,?) WHERE id=?",(seq,op_id))
        return {"cursor":self.get(op_id)["cursor"],"count":len(events)}
    def pause(self, paused):
        with self.tx() as db: db.execute("UPDATE settings SET value=? WHERE key='paused'",("true" if paused else "false",))
        return {"paused":paused}
    def continuous_required(self):
        if self.continuous is None: raise BridgeError(503,"continuous queue not configured",False)
        return self.continuous
    def plan_continuous(self, key):
        queue=self.continuous_required()
        status=queue.status()
        requirements={key:{**{field:value[field] for field in ("objective","acceptance","max_slices","depends_on","source_evidence")},
            "path_sets":{name:scope["description"] for name,scope in value["path_sets"].items()}}
            for key,value in queue.policy["requirements"].items()}
        payload={"source":"continuous_planning","policy_fingerprint":queue.policy_fingerprint,
            "planning_snapshot":status["planning_snapshot"],"requirements":requirements,
            "queue":{"pending":[{key:item[key] for key in ("id","requirement_id","slice_key","state")} for item in status["items"] if item["state"] not in {"merged","cancelled"}],
                     "completed":[{key:item[key] for key in ("id","requirement_id","slice_key","state")} for item in status["items"] if item["state"]=="merged"],
                     "eligible_requirements":status["eligible_requirements"],"plan_exhausted":status["plan_exhausted"]},
            "goal":"Propose bounded WB tasks only from the pinned operator policy. Submit proposals with this trusted planning run identity. Do not choose paths, profiles, commands, credentials or execution settings."}
        return self.create("paperclip",key,payload)
    def propose_continuous(self,payload):
        try:
            planner=self.get(payload.get("planner_run_id"))
            with self.tx() as db:
                parent=db.execute("SELECT * FROM operations WHERE kind='paperclip' AND external_id=?",(planner["key"],)).fetchone()
            return self.continuous_required().propose(payload,planner,dict(parent) if parent else None)
        except (ValueError,TypeError) as error:raise BridgeError(400,str(error),False) from None
    def review_continuous(self,item_id,payload):
        try:return self.continuous_required().review(item_id,payload)
        except ValueError as error:raise BridgeError(409,str(error),False) from None
    def reject_continuous(self,item_id,payload):
        try:return self.continuous_required().reject(item_id,payload)
        except ValueError as error:raise BridgeError(409,str(error),False) from None
    def receipt_continuous(self,item_id,payload):
        try:
            if payload.get("target")=="bridge":
                registration=self.continuous_required().registration(item_id)
                name,definition=registration["template_name"],registration["template"]
                existing=self.approved_templates.get(name)
                if existing is not None and template_fingerprint(name,existing)!=registration["template_fingerprint"]:raise BridgeError(409,"bridge template conflict",False)
                if existing is None:self.approved_templates[name]=definition
            return self.continuous_required().receipt(item_id,payload)
        except ValueError as error:raise BridgeError(409,str(error),False) from None
    def merge_continuous(self,item_id,payload):
        try:return self.continuous_required().merge(item_id,payload)
        except ValueError as error:raise BridgeError(409,str(error),False) from None
    def settle_continuous(self,item_id,payload):
        try:return self.continuous_required().settle(item_id,payload)
        except ValueError as error:raise BridgeError(409,str(error),False) from None
    def retry_continuous(self,item_id,payload):
        with self.tx() as db:
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]=="true":raise BridgeError(409,"continuous queue paused",False)
        try:return self.continuous_required().retry(item_id,payload)
        except ValueError as error:raise BridgeError(409,str(error),False) from None
    def update_continuous(self,item_id,payload):
        if set(payload)-{"lease_id","state","run_id","job_id","head_sha","pr_url","blocker","evidence_ref"} or not {"lease_id","state"}<=set(payload):raise BridgeError(400,"invalid continuous update fields",False)
        evidence={k:v for k,v in payload.items() if k not in {"lease_id","state"}}
        try:return self.continuous_required().update(item_id,payload["lease_id"],payload["state"],**evidence)
        except ValueError as error:raise BridgeError(409,str(error),False) from None
    def claim_continuous(self):
        with self.tx() as db:
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]=="true":return None
        return self.continuous_required().claim()
    def continuous_status(self):
        result=self.continuous_required().status()
        with self.tx() as db:
            result["observed_at"]=time.time()
            result["shared_executor_busy"]=db.execute("SELECT 1 FROM jobs WHERE state IN ('queued','dispatching','publishing','unknown','recoverable') LIMIT 1").fetchone() is not None
            result["queue_paused"]=db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]=="true"
            rows=db.execute("SELECT id,key,state,request,updated FROM operations WHERE kind='paperclip' ORDER BY created DESC LIMIT 20").fetchall()
        matching=[];latest=None;active=None
        terminal={"completed","failed","error","cancelled","interrupted","rejected"}
        active_states={"dispatching","running","unknown","cancelling"}
        for row in rows:
            try:request=json.loads(row["request"])
            except Exception:continue
            if request.get("source")!="continuous_planning":continue
            if active is None and row["state"] in active_states:active=row
            if request.get("planning_snapshot")!=result["planning_snapshot"]:continue
            if latest is None:latest=row
            if row["state"] in terminal:matching.append(row)
        result["planning_generation"]=len(matching)
        result["planning_retry_exhausted"]=len(matching)>=3
        observed=active or latest
        if observed is not None:result["planning"]={key:observed[key] for key in ("id","key","state","updated")}
        return result

    def propose_job(self, payload, templates):
        if set(payload) != {"job_id","run_id","generation","template"}: raise BridgeError(400,"invalid job fields")
        job_id = payload["job_id"]
        if not isinstance(job_id,str) or not JOB_ID.fullmatch(job_id) or payload["template"] not in templates: raise BridgeError(400,"unknown job template")
        fingerprint=template_fingerprint(payload["template"],templates[payload["template"]])
        with self.tx() as db:
            op = db.execute("SELECT state,generation,key FROM operations WHERE id=? AND kind='hermes'",(payload["run_id"],)).fetchone()
            if not op or op["state"] != "running" or op["generation"] != payload["generation"]: raise BridgeError(409,"Director attempt no longer owns the lease")
            parent = db.execute("SELECT id,key,state,request FROM operations WHERE kind='paperclip' AND external_id=?",(op["key"],)).fetchone()
            if hasattr(self, "native_control"):
                self.validate_native_parent(db, parent)
            if getattr(self,"require_parent_for_jobs",False) and parent is None:
                raise BridgeError(409,"Paperclip parent binding not yet acknowledged",False)
            approved = json.loads(parent["request"]) if parent else {}
            if approved.get("source") == "operator_batch" and self.operator_execution(approved) != approved:
                raise BridgeError(409, "operator parent contract changed", False)
            if approved.get("source") in {"native_telegram", "operator_batch"} and (
                approved.get("job_id") != job_id or approved.get("template") != payload["template"]
                or approved.get("template_fingerprint") != fingerprint
            ): raise BridgeError(403,"job differs from owner-confirmed template",False)
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == "true": raise BridgeError(409,"dispatch paused")
            old = db.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
            if old:
                if (old["director_run"],old["generation"],old["template"],old["template_fingerprint"]) != (payload["run_id"],payload["generation"],payload["template"],fingerprint): raise BridgeError(409,"job key conflict")
            else: db.execute("INSERT INTO jobs (id,director_run,generation,template,template_fingerprint) VALUES (?,?,?,?,?)",(job_id,payload["run_id"],payload["generation"],payload["template"],fingerprint))
        return {"job_id":job_id,"state":old["state"] if old else "queued"}
    def job(self, job_id):
        with self.tx() as db:
            row=db.execute("SELECT j.*,o.generation AS current_generation,o.state AS director_state,p.id AS parent_run_id FROM jobs j JOIN operations o ON o.id=j.director_run LEFT JOIN operations p ON p.kind='paperclip' AND p.external_id=o.key WHERE j.id=?",(job_id,)).fetchone()
        if not row: raise BridgeError(404,"job unavailable")
        return dict(row)
    def native_publication_fence(self, job):
        if not hasattr(self, "native_control"):
            return
        with self.tx() as db:
            parent = db.execute("SELECT p.request FROM operations h JOIN operations p ON p.kind='paperclip' AND p.external_id=h.key WHERE h.id=?", (job["director_run"],)).fetchone()
            approved = json.loads(parent["request"]) if parent else {}
            if approved.get("source") == "native_telegram":
                draft = db.execute("SELECT state FROM native_drafts WHERE id=?", (approved.get("draft_id"),)).fetchone()
                if not draft or draft["state"] == "cancelled":
                    raise BridgeError(409, "native publication revoked", False, True)

    def fence(self, job_id):
        j=self.job(job_id)
        self.native_publication_fence(j)
        self.reconcile(j["director_run"])
        j=self.job(job_id)
        op=self.get(j["director_run"])
        with self.tx() as db: parent=db.execute("SELECT id,state FROM operations WHERE kind='paperclip' AND external_id=?",(op["key"],)).fetchone()
        if parent:
            self.reconcile(parent["id"])
            parent=self.get(parent["id"])
        if parent:
            parent_state=parent["state"]
        else:
            observed=self.paperclip.call("GET","/api/heartbeat-runs/"+quote(op["key"],safe=""))
            parent_state={"succeeded":"completed","scheduled_retry":"interrupted","timed_out":"failed"}.get(observed.get("status"),observed.get("status"))
        if parent_state not in {"running","completed"}: raise BridgeError(409,"parent publication fenced",revoked=parent_state in TERMINAL | {"cancelling"})
        if j["generation"]!=j["current_generation"] or j["director_state"] not in {"running","completed"} or j["state"] in {"cancelled","unknown"}: raise BridgeError(409,"publication fenced",revoked=j["generation"]!=j["current_generation"] or j["director_state"] in TERMINAL - {"completed"} or j["director_state"]=="cancelling")
        with self.tx() as db:
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]=="true": raise BridgeError(409,"publication paused")
        self.native_publication_fence(j)
        return j


    def next_job(self):
        with self.tx() as db:
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]=="true":return {"job_id":None}
        with self.tx() as db: rows=db.execute("SELECT id FROM jobs WHERE state IN ('queued','recoverable') ORDER BY rowid").fetchall()
        for row in rows:
            try:
                self.fence(row["id"])
                return {"job_id":row["id"]}
            except BridgeError as exc:
                if exc.status != 409 or not exc.revoked: continue
                j=self.job(row["id"])
                # Only never-dispatched jobs can be discarded automatically. An
                # existing CID remains quarantined until operator reconciliation.
                with self.tx() as db:
                    db.execute("UPDATE jobs SET state='quarantined' WHERE id=? AND external_id IS NULL",(row["id"],))
        return {"job_id":None}
    def recover_job(self, job_id, receipt):
        # Operator resumes COLLECTION of a known finished CID; no new dispatch.
        with self.guard:
            job=self.job(job_id)
            if job["state"] not in {"unknown","dispatching"} or job["publication_active"] or job["candidate_sha"]: raise BridgeError(409,"job is not a recoverable worker handoff")
            if not self.openhands or not job["external_id"]: raise BridgeError(409,"worker identity unavailable")
            observed=self.openhands.call("GET","/api/conversations/"+quote(job["external_id"],safe=""))
            if observed.get("execution_status") not in {"finished","idle","paused","stopped"}: raise BridgeError(409,"worker has not stopped")
            if receipt.get("conversation_id")!=job["external_id"] or receipt.get("branch")!="feat/loop-"+job_id or receipt.get("ok") is not True or not re.fullmatch(r"[0-9a-f]{40}",receipt.get("head_sha","")) or not re.fullmatch(r"[0-9a-f]{40}",receipt.get("base_sha","")): raise BridgeError(400,"existing handoff receipt required")
            # Temporarily move to a state that fence can authorize, then rollback
            # the state if this Director/parent no longer owns the attempt.
            with self.tx() as db: db.execute("UPDATE jobs SET state='recoverable' WHERE id=?",(job_id,))
            try: self.fence(job_id)
            except Exception:
                with self.tx() as db: db.execute("UPDATE jobs SET state='unknown' WHERE id=?",(job_id,))
                raise
            with self.tx() as db: db.execute("UPDATE jobs SET recovery_receipt=? WHERE id=?",(json.dumps(receipt),job_id))
            return {"job_id":job_id,"state":"recoverable","dispatch":False}
    def fail_job(self, job_id):
        with self.tx() as db: db.execute("UPDATE jobs SET state='unknown' WHERE id=? AND state='dispatching'",(job_id,))
        return {"state":self.job(job_id)["state"]}
    def claim_job(self, job_id):
        with self.guard:
            job=self.fence(job_id)
            with self.tx() as db:
                if db.execute("SELECT 1 FROM jobs WHERE state IN ('dispatching','publishing','unknown') AND id!=?",(job_id,)).fetchone(): raise BridgeError(409,"heavy runner slot busy or uncertain")
                if job["state"] not in {"queued","recoverable"}: raise BridgeError(409,"job already claimed; reconcile, never redispatch")
                # Existing handoff uses this exact deterministic conversation identity.
                namespace=uuid.uuid5(uuid.NAMESPACE_URL,"https://proxima.local/bad-dev-story")
                cid=str(uuid.uuid5(namespace,job_id+"/1"))
                db.execute("UPDATE jobs SET state='dispatching',external_id=? WHERE id=?",(cid,job_id))
            return {**job,"state":"dispatching","external_id":cid,"recover_only":job["state"]=="recoverable"}
    def recover_pr(self, job_id):
        # Operator-only; reconcile an already-created PR, never repeat create.
        with self.guard:
            job=self.job(job_id)
            if job["state"]!="unknown" or not job["candidate_sha"]: raise BridgeError(409,"no uncertain publication to reconcile")
            if job["publication_active"] and not job["push_process_stopped"]:raise BridgeError(409,"publisher may still run; obtain stopped receipt first")
            op=self.get(job["director_run"])
            if op["generation"]!=job["generation"] or op["state"] not in {"running","completed"}: raise BridgeError(409,"attempt revoked")
            if not self.publisher or not hasattr(self.publisher,"lookup"): raise BridgeError(503,"publisher lookup unavailable")
            url=self.publisher.lookup(job_id,job["candidate_sha"])
            if not url: return {"state":"unknown","reason":"no matching PR confirmed; no create repeated"}
            with self.tx() as db: db.execute("UPDATE jobs SET state='ready_pr',pr_url=?,publication_active=0 WHERE id=?",(url,job_id))
            return {"state":"ready_pr","pr_url":url}
    def begin_publication(self, job_id, report):
        with self.publication_gate,self.guard:
            job=self.fence(job_id)
            if job["publication_active"]: raise BridgeError(409,"publication already admitted; reconcile its receipt")
            if job["state"]!="dispatching": raise BridgeError(409,"job not awaiting verification")
            sha=report.get("sha")
            if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{40}",sha): raise BridgeError(400,"invalid candidate SHA")
            if report.get("producer")!="harper" or set(report.get("checks",{}))!={"verify","build","review"} or any(v!={"sha":sha,"status":"pass","skipped":0} for v in report["checks"].values()): raise BridgeError(409,"independent exact-SHA checks required")
            permit=str(uuid.uuid4())
            with self.tx() as db: db.execute("UPDATE jobs SET state='publishing',candidate_sha=?,verification=?,publication_permit=?,publication_active=1,push_outcome='not_started',push_process_stopped=0 WHERE id=?",(sha,json.dumps(report),permit,job_id))
            return {"permit":permit,"generation":job["generation"],"sha":sha,"staging_ref":publication_staging_ref(job_id,permit)}
    def publication_job(self, job_id, permit):
        job=self.job(job_id)
        if not isinstance(permit,str) or not hmac.compare_digest(job["publication_permit"] or "",permit):raise BridgeError(403,"invalid publication permit")
        if not job["publication_active"]:raise BridgeError(409,"publication permit closed")
        return job
    def publication_window(self, job_id, permit, action):
        """Run one publication mutation at the current durable generation."""
        with self.publication_gate:
            job=self.publication_job(job_id,permit)
            with self.cancel_request_guard: cancelled=job["director_run"] in self.cancel_requests
            if cancelled: raise BridgeError(409,"publication permit revoked",False,True)
            self.fence(job_id)
            job=self.publication_job(job_id,permit)
            with self.cancel_request_guard: cancelled=job["director_run"] in self.cancel_requests
            if cancelled: raise BridgeError(409,"publication permit revoked",False,True)
            return action(job)
    def start_push(self, job_id, payload):
        def start(job):
            publisher_id=payload.get("publisher_id")
            if not isinstance(publisher_id,str) or not SAFE_ID.fullmatch(publisher_id):raise BridgeError(400,"publisher identity required")
            if job["push_outcome"]!="not_started":raise BridgeError(409,"push already started; recover receipt instead")
            with self.tx() as db:db.execute("UPDATE jobs SET push_outcome='running',push_publisher_id=?,push_process_stopped=0 WHERE id=?",(publisher_id,job_id))
            return {"started":True}
        return self.publication_window(job_id,payload.get("permit"),start)
    def record_push(self, job_id, payload):
        with self.publication_gate,self.guard:
            job=self.publication_job(job_id,payload.get("permit"))
            if not isinstance(payload.get("publisher_id"),str) or payload.get("publisher_id")!=job["push_publisher_id"]:raise BridgeError(403,"publisher identity mismatch")
            if payload.get("outcome") not in {"succeeded","failed","unknown"} or payload.get("process_stopped") is not True or not isinstance(payload.get("evidence_ref"),str) or not payload["evidence_ref"]:raise BridgeError(400,"stopped publisher receipt required")
            if payload["outcome"]=="succeeded" and payload.get("returncode")!=0:raise BridgeError(400,"successful push needs exit zero")
            if payload["outcome"]=="failed" and (not isinstance(payload.get("returncode"),int) or payload["returncode"]==0):raise BridgeError(400,"failed push needs nonzero exit")
            if job["push_process_stopped"] and json.loads(job["push_receipt"])!=payload:raise BridgeError(409,"push receipt already recorded")
            with self.tx() as db:db.execute("UPDATE jobs SET push_outcome=?,push_process_stopped=1,push_receipt=? WHERE id=?",(payload["outcome"],json.dumps(payload),job_id))
            return {"outcome":payload["outcome"],"process_stopped":True}
    def settle_publication(self, job_id, evidence_ref):
        # Operator-only settlement observes destinations; it creates/deletes nothing.
        with self.publication_gate:
            job=self.job(job_id)
            if not job["publication_active"] or not job["candidate_sha"]:raise BridgeError(409,"no active publication to settle")
            if job["push_outcome"]!="not_started" and not job["push_process_stopped"]:raise BridgeError(409,"publisher may still run; obtain stopped receipt from Harper")
            if not isinstance(evidence_ref,str) or not evidence_ref.strip():raise BridgeError(400,"operator evidence reference required")
            if not self.publisher or not hasattr(self.publisher,"inspect"):raise BridgeError(503,"destination inspector unavailable")
            observed=self.publisher.inspect(job_id,job["candidate_sha"])
            settlement={"at":time.time(),"evidence_ref":evidence_ref,"push_outcome":job["push_outcome"],"destination":observed}
            current=self.job(job_id)
            if not current["publication_active"] or current["publication_permit"]!=job["publication_permit"]:raise BridgeError(409,"publication changed during settlement")
            with self.tx() as db:db.execute("UPDATE jobs SET state='settled',publication_active=0,publication_settlement=? WHERE id=?",(json.dumps(settlement),job_id))
            return {"state":"settled","destination":observed,"created_pr":False,"deleted_ref":False}
    def finish_publication(self, job_id, permit):
        with self.publication_finish_gate:
            job=self.job(job_id)
            if not isinstance(permit,str) or not hmac.compare_digest(job["publication_permit"] or "",permit): raise BridgeError(403,"invalid publication permit")
            if job["state"]=="ready_pr": return {"state":"ready_pr","pr_url":job["pr_url"]}
            if not job["publication_active"]: raise BridgeError(409,"publication permit closed")
            if job["push_outcome"]!="succeeded" or not job["push_process_stopped"]:raise BridgeError(409,"successful stopped push receipt required")
            if not self.publisher: raise BridgeError(503,"publisher not configured")
            url=None
            try:
                job=self.publication_window(job_id,permit,lambda current:current)
                if hasattr(self.publisher,"prepare"):
                    self.publisher.prepare(
                        job_id,job["candidate_sha"],publication_staging_ref(job_id,permit),
                        lambda mutation:self.publication_window(job_id,permit,lambda _job:mutation()),
                    )
                if hasattr(self.publisher,"lookup"):
                    url=self.publisher.lookup(job_id,job["candidate_sha"])
                else:
                    url=None
                if url is None and hasattr(self.publisher,"verify_final"):
                    self.publisher.verify_final(job_id,job["candidate_sha"])
                def create_and_commit(current):
                    final_url=url if url is not None else (
                        self.publisher.create(job_id,current["candidate_sha"])
                        if hasattr(self.publisher,"create") else self.publisher(job_id,current["candidate_sha"])
                    )
                    try:
                        if hasattr(self.publisher,"verify_final"):
                            self.publisher.verify_final(job_id,current["candidate_sha"])
                        if hasattr(self.publisher,"lookup"):
                            confirmed=self.publisher.lookup(job_id,current["candidate_sha"])
                            if confirmed!=final_url:raise BridgeError(502,"ready PR readback differs from creation receipt",True)
                    except BridgeError:
                        # A PR mutation may already exist. Any post-create
                        # disagreement is an uncertain destination, never a
                        # clean rejection that can be retried.
                        raise BridgeError(502,"publication readback uncertain",True) from None
                    with self.tx() as db:
                        db.execute("UPDATE jobs SET state='ready_pr',pr_url=?,publication_active=0 WHERE id=?",(final_url,job_id))
                    return {"state":"ready_pr","pr_url":final_url,"sha":current["candidate_sha"]}
                return self.publication_window(job_id,permit,create_and_commit)
            except BridgeError as exc:
                if exc.status==409 and exc.revoked:
                    if url is not None:
                        # Read-only lookup proved the PR existed before this
                        # cancelled attempt could issue another mutation. Keep
                        # the external truth instead of claiming it was revoked.
                        with self.publication_gate:
                            if hasattr(self.publisher,"verify_final"):self.publisher.verify_final(job_id,job["candidate_sha"])
                            confirmed=self.publisher.lookup(job_id,job["candidate_sha"])
                            if confirmed!=url:raise BridgeError(502,"existing PR changed during cancellation",True)
                            with self.tx() as db:
                                db.execute("UPDATE jobs SET state='ready_pr',pr_url=?,publication_active=0 WHERE id=?",(url,job_id))
                                director=db.execute("SELECT director_run FROM jobs WHERE id=?",(job_id,)).fetchone()[0]
                                db.execute("UPDATE operations SET state='completed',stop_confirmed=1 WHERE id=? AND state='cancelling' AND execution_stop_confirmed=1",(director,))
                                key=db.execute("SELECT key FROM operations WHERE id=?",(director,)).fetchone()[0]
                                db.execute("UPDATE operations SET state='completed',stop_confirmed=1 WHERE kind='paperclip' AND external_id=? AND state='cancelling' AND execution_stop_confirmed=1",(key,))
                        return {"state":"ready_pr","pr_url":url,"sha":job["candidate_sha"]}
                    # The admitted push has returned, and this generation was revoked.
                    # No new PR request can now be issued by this attempt.
                    with self.tx() as db: db.execute("UPDATE jobs SET state='cancelled',publication_active=0 WHERE id=? AND state!='ready_pr'",(job_id,))
                    return {"state":"cancelled","pr_url":None}
                if not exc.uncertain:raise
                with self.tx() as db: db.execute("UPDATE jobs SET state='unknown' WHERE id=?",(job_id,))
                raise BridgeError(502,"publication receipt uncertain; active permit requires reconciliation") from None
            except Exception:
                with self.tx() as db: db.execute("UPDATE jobs SET state='unknown' WHERE id=?",(job_id,))
                raise BridgeError(502,"publication receipt uncertain; active permit requires reconciliation") from None

class GitHubPublisher:
    def __init__(self, client, repository, base="main"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repository): raise ValueError("invalid repository")
        self.client,self.repository,self.base=client,repository,base
    def inspect(self, job_id, sha):
        branch="feat/loop-"+job_id
        try:
            ref=self.client.call("GET",f"/repos/{self.repository}/git/ref/heads/{branch}")
            if ref.get("object",{}).get("sha")!=sha:raise BridgeError(409,"destination branch differs from verified SHA")
            branch_state="matches"
        except BridgeError as exc:
            if exc.status!=404 or exc.uncertain:raise
            branch_state="absent"
        prs=self.client.call("GET",f"/repos/{self.repository}/pulls?head={self.repository.split('/')[0]}:{quote(branch,safe='')}&state=all&per_page=100")
        if not isinstance(prs,list):raise BridgeError(502,"invalid PR inspection response")
        receipts=[]
        for pr in prs:
            if pr.get("head",{}).get("sha")!=sha or pr.get("base",{}).get("ref")!=self.base:raise BridgeError(409,"destination PR differs from verified candidate")
            url=pr.get("html_url","")
            if not url.startswith("https://github.com/"+self.repository+"/pull/"):raise BridgeError(502,"invalid PR receipt")
            receipts.append({"url":url,"state":pr.get("state"),"merged":pr.get("merged_at") is not None})
        return {"branch":branch,"branch_state":branch_state,"sha":sha if branch_state=="matches" else None,"pull_requests":receipts}
    def lookup(self, job_id, sha):
        branch="feat/loop-"+job_id
        existing=self.client.call("GET",f"/repos/{self.repository}/pulls?head={self.repository.split('/')[0]}:{quote(branch,safe='')}&state=open")
        if not existing:return None
        pr=existing[0]
        if pr.get("head",{}).get("sha")!=sha or pr.get("base",{}).get("ref")!=self.base: raise BridgeError(409,"existing PR differs")
        url=pr.get("html_url","")
        if not url.startswith("https://github.com/"+self.repository+"/pull/"): raise BridgeError(502,"invalid PR receipt")
        return url
    def verify_final(self, job_id, sha):
        branch="feat/loop-"+job_id
        ref=self.client.call("GET",f"/repos/{self.repository}/git/ref/heads/{quote(branch,safe='/')}")
        if ref.get("object",{}).get("sha")!=sha:raise BridgeError(409,"remote branch differs from verified SHA")
        return True
    def create(self, job_id, sha):
        branch="feat/loop-"+job_id
        pr=self.client.call("POST",f"/repos/{self.repository}/pulls",{"title":"LOOP: verified candidate "+job_id,"head":branch,"base":self.base,"body":"Candidate `"+sha+"` passed independent Harper verify, build and review. Stop at ready PR; merge and deployment require Mike.","draft":False})
        if pr.get("head",{}).get("sha")!=sha or pr.get("base",{}).get("ref")!=self.base:raise BridgeError(502,"created PR differs from verified candidate",True)
        url=pr.get("html_url","")
        if not url.startswith("https://github.com/"+self.repository+"/pull/"): raise BridgeError(502,"invalid PR receipt")
        return url
    def prepare(self, job_id, sha, staging_ref, mutate):
        expected_prefix=f"refs/heads/loop-staging/{job_id}/"
        if not isinstance(staging_ref,str) or not staging_ref.startswith(expected_prefix) or not re.fullmatch(r"[0-9a-f]{64}",staging_ref.removeprefix(expected_prefix)):raise BridgeError(400,"invalid publication staging ref")
        staging_branch=staging_ref.removeprefix("refs/heads/")
        try: staging=self.client.call("GET",f"/repos/{self.repository}/git/ref/heads/{quote(staging_branch,safe='/')}")
        except BridgeError as exc:
            if exc.status==404 and not exc.uncertain:raise BridgeError(409,"verified staging ref is absent") from None
            raise
        if staging.get("object",{}).get("sha")!=sha:raise BridgeError(409,"staging ref differs from verified SHA")
        branch="feat/loop-"+job_id
        try: final=self.client.call("GET",f"/repos/{self.repository}/git/ref/heads/{quote(branch,safe='/')}")
        except BridgeError as exc:
            if exc.status!=404 or exc.uncertain:raise
            final=mutate(lambda:self.client.call("POST",f"/repos/{self.repository}/git/refs",{"ref":"refs/heads/"+branch,"sha":sha}))
        else:
            if final.get("object",{}).get("sha")!=sha:
                final=mutate(lambda:self.client.call("PATCH",f"/repos/{self.repository}/git/refs/heads/{quote(branch,safe='/')}",{"sha":sha,"force":False}))
        if final.get("object",{}).get("sha")!=sha:raise BridgeError(502,"final ref update was not confirmed")
        return {"branch":branch,"sha":sha}
    def __call__(self, job_id, sha):
        branch="feat/loop-"+job_id
        ref=self.client.call("GET",f"/repos/{self.repository}/git/ref/heads/{branch}")
        if ref.get("object",{}).get("sha")!=sha: raise BridgeError(409,"remote branch differs from verified SHA")
        existing=self.client.call("GET",f"/repos/{self.repository}/pulls?head={self.repository.split('/')[0]}:{quote(branch,safe='')}&state=open")
        if existing:
            pr=existing[0]
            if pr.get("head",{}).get("sha")!=sha or pr.get("base",{}).get("ref")!=self.base: raise BridgeError(409,"existing PR differs")
        else:
            return self.create(job_id,sha)
        url=pr.get("html_url","")
        if not url.startswith("https://github.com/"+self.repository+"/pull/"): raise BridgeError(502,"invalid PR receipt")
        return url

def server(bridge, config):
    keys={role:secret(path) for role,path in config["credential_files"].items()}
    bridge.approved_templates = config.get("templates", {})
    native = None
    if "native_telegram" in config:
        try:
            from .native_control import NativeControl
        except ImportError:
            from native_control import NativeControl
        native = NativeControl(bridge, config)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send_json(self,status,value):
            encoded=json.dumps(value).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
        def authenticate(self,role):
            if role not in keys or not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+keys[role]): raise BridgeError(403,"access denied")
        def handle_request(self):
            path=urlparse(self.path).path
            try:
                if path.startswith("/hermes/"): self.authenticate("gateway")
                elif path.startswith("/v1/chat/"): self.authenticate("chat")
                elif path.startswith("/v1/native/"): self.authenticate("native_ingress")
                elif path in {"/v1/jobs","/v1/context","/v1/queue/proposals"}: self.authenticate("director")
                elif path.startswith("/v1/runner/"): self.authenticate("runner")
                else: self.authenticate("operator")
                payload={}
                if self.command=="POST":
                    length=int(self.headers.get("Content-Length","0"))
                    if length<0 or length>100000: raise BridgeError(413,"payload too large")
                    payload=json.loads(self.rfile.read(length) or b"{}")
                    if not isinstance(payload,dict): raise BridgeError(400,"object required")
                if path.startswith(("/v1/chat/", "/v1/native/", "/v1/native-recovery/")):
                    if native is None: raise BridgeError(503,"native chat not configured",False)
                    result=native.route(self.command,path,payload)
                elif self.command=="GET" and path=="/hermes/health": result=bridge.hermes.call("GET","/health")
                elif self.command=="POST" and path=="/hermes/v1/runs":
                    if set(payload)-{"input","instructions","session_id"} or not all(isinstance(payload.get(k),str) and payload[k] for k in ("input","instructions","session_id")): raise BridgeError(400,"invalid gateway request")
                    if self.headers.get("X-Hermes-Session-Key")!=payload["session_id"]: raise BridgeError(400,"session binding missing")
                    result=bridge.create("hermes",self.headers.get("Idempotency-Key"),payload)
                elif self.command=="POST" and path=="/v1/wake": result=bridge.create("paperclip",self.headers.get("Idempotency-Key"),payload)
                elif self.command=="GET" and path=="/v1/context":
                    from urllib.parse import parse_qs
                    values=parse_qs(urlparse(self.path).query)
                    if set(values)-{"offset"}:raise BridgeError(400,"context scope is fixed")
                    result=bridge.context(int(values.get("offset",["0"])[0]))
                elif self.command=="POST" and path=="/v1/jobs": result=bridge.propose_job(payload,config.get("templates",{}))
                elif self.command=="POST" and path=="/v1/queue/plan":result=bridge.plan_continuous(self.headers.get("Idempotency-Key"))
                elif self.command=="POST" and path=="/v1/queue/proposals":result=bridge.propose_continuous(payload)
                elif self.command=="GET" and path=="/v1/queue":result=bridge.continuous_status()
                elif self.command=="GET" and (match:=re.fullmatch(r"/v1/queue/([a-z0-9][a-z0-9-]{2,63})(/registration)?",path)):
                    try:result=bridge.continuous_required().registration(match[1]) if match[2] else bridge.continuous_required().get(match[1])
                    except ValueError as error:raise BridgeError(409,str(error),False) from None
                elif self.command=="POST" and path=="/v1/queue/claim":result=bridge.claim_continuous() or {"item_id":None}
                elif match:=re.fullmatch(r"/v1/queue/([a-z0-9][a-z0-9-]{2,63})/(review|reject|receipt|update|merge|retry|settle)",path):
                    if self.command!="POST":raise BridgeError(404,"queue operation unavailable")
                    if match[2]=="review":result=bridge.review_continuous(match[1],payload)
                    elif match[2]=="reject":result=bridge.reject_continuous(match[1],payload)
                    elif match[2]=="receipt":result=bridge.receipt_continuous(match[1],payload)
                    elif match[2]=="merge":result=bridge.merge_continuous(match[1],payload)
                    elif match[2]=="retry":result=bridge.retry_continuous(match[1],payload)
                    elif match[2]=="settle":result=bridge.settle_continuous(match[1],payload)
                    else:result=bridge.update_continuous(match[1],payload)
                elif self.command=="GET" and path=="/v1/runner/jobs/next": result=bridge.next_job()
                elif match:=re.fullmatch(r"/v1/runner/jobs/([a-z0-9][a-z0-9-]{2,40})(/(claim|begin-publication|start-push|record-push|finish-publication|fence|fail))?",path):
                    if self.command=="POST" and match[3]=="fail": result=bridge.fail_job(match[1])
                    elif self.command=="POST" and match[3]=="claim": result=bridge.claim_job(match[1])
                    elif self.command=="POST" and match[3]=="begin-publication": result=bridge.begin_publication(match[1],payload)
                    elif self.command=="POST" and match[3]=="start-push":result=bridge.start_push(match[1],payload)
                    elif self.command=="POST" and match[3]=="record-push":result=bridge.record_push(match[1],payload)
                    elif self.command=="POST" and match[3]=="finish-publication": result=bridge.finish_publication(match[1],payload.get("permit"))
                    elif self.command=="GET" and match[3]=="fence": result=bridge.fence(match[1])
                    elif self.command=="GET" and match[3] is None: result=bridge.job(match[1])
                    else: raise BridgeError(404,"runner operation unavailable")
                elif self.command=="POST" and (match:=re.fullmatch(r"/v1/jobs/([a-z0-9][a-z0-9-]{2,40})/settle-publication",path)):result=bridge.settle_publication(match[1],payload.get("evidence_ref"))
                elif self.command=="POST" and (match:=re.fullmatch(r"/v1/jobs/([a-z0-9][a-z0-9-]{2,40})/recover-worker",path)): result=bridge.recover_job(match[1],payload)
                elif self.command=="POST" and (match:=re.fullmatch(r"/v1/jobs/([a-z0-9][a-z0-9-]{2,40})/recover-pr",path)): result=bridge.recover_pr(match[1])
                elif self.command=="POST" and path in {"/v1/pause","/v1/resume"}: result=bridge.pause(path.endswith("pause"))
                elif match:=re.fullmatch(r"/(hermes/v1|v1)/runs/([A-Za-z0-9-]+)(/(stop|events|adopt))?",path):
                    op=bridge.get(match[2])
                    if match[1]=="hermes/v1" and op["kind"]!="hermes": raise BridgeError(404,"run unavailable")
                    action=match[4]
                    if self.command=="POST" and action=="stop": result=bridge.cancel(match[2])
                    elif self.command=="POST" and action=="adopt" and match[1]=="v1": result=bridge.adopt(match[2],payload["external_id"])
                    elif self.command=="GET" and action=="events" and match[1]=="hermes/v1":
                        # Hermes SSE has no replay. This is a current status snapshot;
                        # official adapter also polls GET and owns stream reconnects.
                        result=bridge.reconcile(match[2]); data=("event: run.status\ndata: "+json.dumps(result)+"\n\n").encode()
                        self.send_response(200); self.send_header("Content-Type","text/event-stream"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
                    elif self.command=="GET" and action=="events": result=bridge.paperclip_events(match[2])
                    elif self.command=="GET" and action is None: result=bridge.reconcile(match[2])
                    else: raise BridgeError(404,"operation unavailable")
                elif self.command=="GET" and path=="/v1/status":
                    result={"mode":"pr_only","scheduler":"paperclip","live_ready":False,"reason":"operator runtime acceptance required"}
                    if bridge.continuous is not None:result["queue"]=bridge.continuous_status()
                else: raise BridgeError(404,"operation unavailable")
                self.send_json(200,result)
            except BridgeError as e: self.send_json(e.status,{"error":e.message,"uncertain":e.uncertain})
            except Exception: self.send_json(400,{"error":"invalid request"})
        do_POST=handle_request
        do_GET=handle_request
    return ThreadingHTTPServer((config.get("bind","127.0.0.1"),config.get("port",18770)),Handler)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--config",required=True); args=parser.parse_args()
    config=json.loads(Path(args.config).read_text())
    upstream=lambda name: JsonHTTP(config[name]["url"],secret(config[name]["token_file"]),header=config[name].get("header","Authorization"))
    publisher=GitHubPublisher(upstream("github"),config["github"]["repository"],base=config["github"].get("base","main")) if "github" in config else None
    bridge=Bridge(config["database"],upstream("hermes"),upstream("paperclip"),config["director_id"],upstream("openhands") if "openhands" in config else None,publisher,upstream("webapp_context") if "webapp_context" in config else None,config.get("continuous_policy"))
    server(bridge,config).serve_forever()
if __name__=="__main__":
    # Native extensions must share this process's BridgeError identity when
    # launched as a script, not import a second copy under the module name.
    import sys
    sys.modules.setdefault("bridge",sys.modules[__name__])
    main()
