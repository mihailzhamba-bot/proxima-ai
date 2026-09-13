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
class BridgeError(Exception):
    def __init__(self, status, message): self.status, self.message = status, message

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
    def __init__(self, base, token, timeout=30, header="Authorization"):
        self.header=header
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
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            # Never expose transport errors: urllib exceptions may carry secrets or body.
            raise BridgeError(502, "upstream unavailable; reconcile intent") from None

class Bridge:
    def __init__(self, database, hermes, paperclip, director_id, openhands=None, publisher=None):
        self.publisher = publisher
        self.database, self.hermes, self.paperclip, self.director_id, self.openhands = str(database), hermes, paperclip, director_id, openhands
        Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.guard = threading.RLock()
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
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally: db.close()
    def get(self, op_id):
        with self.tx() as db:
            row = db.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone()
        if not row: raise BridgeError(404, "run unavailable")
        return dict(row)
    def intent(self, kind, key, payload):
        if not isinstance(key, str) or not SAFE_ID.fullmatch(key): raise BridgeError(400, "invalid idempotency key")
        if shutil.disk_usage(Path(self.database).parent).free < 536870912: raise BridgeError(503,"disk reserve low; dispatch paused")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.tx() as db:
            old = db.execute("SELECT * FROM operations WHERE kind=? AND key=?", (kind, key)).fetchone()
            if old:
                if old["request_hash"] != digest: raise BridgeError(409, "idempotency payload conflict")
                return dict(old), False
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == "true": raise BridgeError(409, "dispatch paused")
            if kind == "hermes":
                parent = db.execute("SELECT state FROM operations WHERE kind='paperclip' AND external_id=?", (key,)).fetchone()
                if parent and parent["state"] in {"cancelling", "cancelled", "interrupted", "failed", "error"}: raise BridgeError(409, "parent run revoked")
            # One active management run; queued events remain owned by Paperclip.
            if kind == "hermes" and db.execute("SELECT 1 FROM operations WHERE kind='hermes' AND state IN ('dispatching','running','unknown','cancelling')").fetchone(): raise BridgeError(409, "Director lease busy or uncertain")
            op_id, now = str(uuid.uuid4()), time.time()
            db.execute("INSERT INTO operations (id,kind,key,request_hash,request,state,created,updated) VALUES (?,?,?,?,?,'dispatching',?,?)", (op_id,kind,key,digest,encoded,now,now))
        return self.get(op_id), True
    def create(self, kind, key, payload):
        op, new = self.intent(kind, key, payload)
        if not new:
            if op["state"] in {"dispatching", "unknown"}: raise BridgeError(409, "dispatch uncertain; operator reconciliation required")
            return {"run_id": op["id"], "status": op["state"]}
        try:
            if kind == "hermes":
                bound_payload={**payload,"input":f"LOOP trusted attempt identity: run_id={op['id']}; generation={op['generation']}. Use this identity for Bridge job proposals.\n\n"+payload["input"]}
                response = self.hermes.call("POST", "/v1/runs", bound_payload, {"Idempotency-Key": key, "X-Hermes-Session-Key": payload["session_id"]})
            else:
                response = self.paperclip.call("POST", "/api/agents/"+quote(self.director_id,safe="")+"/wakeup", {"source":"on_demand", "triggerDetail":"manual", "reason":"LOOP event", "payload":payload, "idempotencyKey":key, "forceFreshSession":False})
            external_id = response.get("run_id") or response.get("runId") or response.get("id")
            if not external_id or not isinstance(external_id, str) or not SAFE_ID.fullmatch(external_id): raise BridgeError(502,"upstream did not confirm run identity")
        except Exception:
            with self.tx() as db: db.execute("UPDATE operations SET state=CASE WHEN state='dispatching' THEN 'unknown' ELSE state END,updated=? WHERE id=?", (time.time(),op["id"]))
            raise BridgeError(502,"dispatch uncertain; do not retry upstream") from None
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
        # Fence and revoke queued/active jobs BEFORE any network call.
        with self.tx() as db:
            op = db.execute("SELECT * FROM operations WHERE id=?",(op_id,)).fetchone()
            if not op: raise BridgeError(404,"run unavailable")
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
                if child: stop_ok = self.cancel(child["id"])["status"] == "cancelled"
                # Without gateway binding, cancellation remains unconfirmed.
        with self.tx() as db:
            jobs = db.execute("SELECT external_id FROM jobs WHERE director_run=? AND external_id IS NOT NULL",(op_id,)).fetchall()
        for job in jobs:
            try:
                if not self.openhands: stop_ok = False
                else:
                    self.openhands.call("POST","/api/conversations/"+quote(job["external_id"],safe="")+"/pause")
                    observed=self.openhands.call("GET","/api/conversations/"+quote(job["external_id"],safe=""))
                    if observed.get("execution_status") not in {"paused","stopped","finished","error"}: stop_ok=False
            except BridgeError: stop_ok = False
        with self.tx() as db: db.execute("UPDATE operations SET state=?,stop_confirmed=?,updated=? WHERE id=?",("cancelled" if stop_ok else "cancelling",int(stop_ok),time.time(),op_id))
        return {"run_id":op_id,"status":"cancelled" if stop_ok else "cancelling"}
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
    def propose_job(self, payload, templates):
        if set(payload) != {"job_id","run_id","generation","template"}: raise BridgeError(400,"invalid job fields")
        job_id = payload["job_id"]
        if not isinstance(job_id,str) or not JOB_ID.fullmatch(job_id) or payload["template"] not in templates: raise BridgeError(400,"unknown job template")
        with self.tx() as db:
            op = db.execute("SELECT state,generation FROM operations WHERE id=? AND kind='hermes'",(payload["run_id"],)).fetchone()
            if not op or op["state"] != "running" or op["generation"] != payload["generation"]: raise BridgeError(409,"Director attempt no longer owns the lease")
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0] == "true": raise BridgeError(409,"dispatch paused")
            old = db.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
            if old:
                if (old["director_run"],old["generation"],old["template"]) != (payload["run_id"],payload["generation"],payload["template"]): raise BridgeError(409,"job key conflict")
            else: db.execute("INSERT INTO jobs (id,director_run,generation,template) VALUES (?,?,?,?)",(job_id,payload["run_id"],payload["generation"],payload["template"]))
        return {"job_id":job_id,"state":old["state"] if old else "queued"}
    def job(self, job_id):
        with self.tx() as db:
            row=db.execute("SELECT j.*,o.generation AS current_generation,o.state AS director_state FROM jobs j JOIN operations o ON o.id=j.director_run WHERE j.id=?",(job_id,)).fetchone()
        if not row: raise BridgeError(404,"job unavailable")
        return dict(row)
    def fence(self, job_id):
        j=self.job(job_id)
        self.reconcile(j["director_run"])
        j=self.job(job_id)
        op=self.get(j["director_run"])
        with self.tx() as db: parent=db.execute("SELECT state FROM operations WHERE kind='paperclip' AND external_id=?",(op["key"],)).fetchone()
        if parent and parent["state"] in {"cancelling","cancelled","interrupted","failed","error"}: raise BridgeError(409,"parent publication fenced")
        if j["generation"]!=j["current_generation"] or j["director_state"] not in {"running","completed"} or j["state"] in {"cancelled","unknown"}: raise BridgeError(409,"publication fenced")
        with self.tx() as db:
            if db.execute("SELECT value FROM settings WHERE key='paused'").fetchone()[0]=="true": raise BridgeError(409,"publication paused")
        return j


    def next_job(self):
        with self.tx() as db:
            row=db.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY rowid LIMIT 1").fetchone()
        return {"job_id":row["id"] if row else None}
    def fail_job(self, job_id):
        with self.tx() as db: db.execute("UPDATE jobs SET state='unknown' WHERE id=? AND state='dispatching'",(job_id,))
        return {"state":self.job(job_id)["state"]}
    def claim_job(self, job_id):
        with self.guard:
            job=self.fence(job_id)
            with self.tx() as db:
                if db.execute("SELECT 1 FROM jobs WHERE state IN ('dispatching','publishing','unknown') AND id!=?",(job_id,)).fetchone(): raise BridgeError(409,"heavy runner slot busy or uncertain")
                if job["state"]!="queued": raise BridgeError(409,"job already claimed; reconcile, never redispatch")
                # Existing handoff uses this exact deterministic conversation identity.
                namespace=uuid.uuid5(uuid.NAMESPACE_URL,"https://proxima.local/bad-dev-story")
                cid=str(uuid.uuid5(namespace,job_id+"/1"))
                db.execute("UPDATE jobs SET state='dispatching',external_id=? WHERE id=?",(cid,job_id))
            return {**job,"state":"dispatching","external_id":cid}
    def recover_pr(self, job_id):
        # Operator-only; reconcile an already-created PR, never repeat create.
        with self.guard:
            job=self.job(job_id)
            if job["state"]!="unknown" or not job["candidate_sha"]: raise BridgeError(409,"no uncertain publication to reconcile")
            op=self.get(job["director_run"])
            if op["generation"]!=job["generation"] or op["state"] not in {"running","completed"}: raise BridgeError(409,"attempt revoked")
            if not self.publisher or not hasattr(self.publisher,"lookup"): raise BridgeError(503,"publisher lookup unavailable")
            url=self.publisher.lookup(job_id,job["candidate_sha"])
            if not url: return {"state":"unknown","reason":"no matching PR confirmed; no create repeated"}
            with self.tx() as db: db.execute("UPDATE jobs SET state='ready_pr',pr_url=? WHERE id=?",(url,job_id))
            return {"state":"ready_pr","pr_url":url}
    def publish(self, job_id, report):
        # Only the runner credential can reach this method over HTTP. Worker/model
        # credentials never enter verification containers or this route.
        with self.guard:
            job=self.fence(job_id)
            if job["state"]=="ready_pr": return {"state":"ready_pr","pr_url":job["pr_url"]}
            if job["state"]!="dispatching": raise BridgeError(409,"job not awaiting verification")
            sha=report.get("sha")
            if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{40}",sha): raise BridgeError(400,"invalid candidate SHA")
            if report.get("producer")!="harper" or set(report.get("checks",{}))!={"verify","build","review"} or any(v!={"sha":sha,"status":"pass","skipped":0} for v in report["checks"].values()): raise BridgeError(409,"independent exact-SHA checks required")
            if not self.publisher: raise BridgeError(503,"publisher not configured")
            with self.tx() as db: db.execute("UPDATE jobs SET state='publishing',candidate_sha=?,verification=? WHERE id=?",(sha,json.dumps(report),job_id))
            try: url=self.publisher(job_id,sha)
            except Exception:
                with self.tx() as db: db.execute("UPDATE jobs SET state='unknown' WHERE id=?",(job_id,))
                raise BridgeError(502,"PR publication uncertain; reconcile by branch") from None
            with self.tx() as db: db.execute("UPDATE jobs SET state='ready_pr',pr_url=? WHERE id=?",(url,job_id))
            return {"state":"ready_pr","pr_url":url,"sha":sha}

class GitHubPublisher:
    def __init__(self, client, repository, base="main"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repository): raise ValueError("invalid repository")
        self.client,self.repository,self.base=client,repository,base
    def lookup(self, job_id, sha):
        branch="feat/loop-"+job_id
        existing=self.client.call("GET",f"/repos/{self.repository}/pulls?head={self.repository.split('/')[0]}:{quote(branch,safe='')}&state=open")
        if not existing:return None
        pr=existing[0]
        if pr.get("head",{}).get("sha")!=sha or pr.get("base",{}).get("ref")!=self.base: raise BridgeError(409,"existing PR differs")
        url=pr.get("html_url","")
        if not url.startswith("https://github.com/"+self.repository+"/pull/"): raise BridgeError(502,"invalid PR receipt")
        return url
    def __call__(self, job_id, sha):
        branch="feat/loop-"+job_id
        ref=self.client.call("GET",f"/repos/{self.repository}/git/ref/heads/{branch}")
        if ref.get("object",{}).get("sha")!=sha: raise BridgeError(409,"remote branch differs from verified SHA")
        existing=self.client.call("GET",f"/repos/{self.repository}/pulls?head={self.repository.split('/')[0]}:{quote(branch,safe='')}&state=open")
        if existing:
            pr=existing[0]
            if pr.get("head",{}).get("sha")!=sha or pr.get("base",{}).get("ref")!=self.base: raise BridgeError(409,"existing PR differs")
        else:
            pr=self.client.call("POST",f"/repos/{self.repository}/pulls",{"title":"LOOP: verified candidate "+job_id,"head":branch,"base":self.base,"body":"Candidate `"+sha+"` passed independent Harper verify, build and review. Stop at ready PR; merge and deployment require Mike.","draft":False})
        url=pr.get("html_url","")
        if not url.startswith("https://github.com/"+self.repository+"/pull/"): raise BridgeError(502,"invalid PR receipt")
        return url

def server(bridge, config):
    keys={role:secret(path) for role,path in config["credential_files"].items()}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send_json(self,status,value):
            encoded=json.dumps(value).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
        def authenticate(self,role):
            if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+keys[role]): raise BridgeError(403,"access denied")
        def handle_request(self):
            path=urlparse(self.path).path
            try:
                if path.startswith("/hermes/"): self.authenticate("gateway")
                elif path=="/v1/jobs": self.authenticate("director")
                elif path.startswith("/v1/runner/"): self.authenticate("runner")
                else: self.authenticate("operator")
                payload={}
                if self.command=="POST":
                    length=int(self.headers.get("Content-Length","0"))
                    if length<0 or length>100000: raise BridgeError(413,"payload too large")
                    payload=json.loads(self.rfile.read(length) or b"{}")
                    if not isinstance(payload,dict): raise BridgeError(400,"object required")
                if self.command=="GET" and path=="/hermes/health": result=bridge.hermes.call("GET","/health")
                elif self.command=="POST" and path=="/hermes/v1/runs":
                    if set(payload)-{"input","instructions","session_id"} or not all(isinstance(payload.get(k),str) and payload[k] for k in ("input","instructions","session_id")): raise BridgeError(400,"invalid gateway request")
                    if self.headers.get("X-Hermes-Session-Key")!=payload["session_id"]: raise BridgeError(400,"session binding missing")
                    result=bridge.create("hermes",self.headers.get("Idempotency-Key"),payload)
                elif self.command=="POST" and path=="/v1/wake": result=bridge.create("paperclip",self.headers.get("Idempotency-Key"),payload)
                elif self.command=="POST" and path=="/v1/jobs": result=bridge.propose_job(payload,config.get("templates",{}))
                elif self.command=="GET" and path=="/v1/runner/jobs/next": result=bridge.next_job()
                elif match:=re.fullmatch(r"/v1/runner/jobs/([a-z0-9][a-z0-9-]{2,40})(/(claim|publish|fence|fail))?",path):
                    if self.command=="POST" and match[3]=="fail": result=bridge.fail_job(match[1])
                    elif self.command=="POST" and match[3]=="claim": result=bridge.claim_job(match[1])
                    elif self.command=="POST" and match[3]=="publish": result=bridge.publish(match[1],payload)
                    elif self.command=="GET" and match[3]=="fence": result=bridge.fence(match[1])
                    elif self.command=="GET" and match[3] is None: result=bridge.job(match[1])
                    else: raise BridgeError(404,"runner operation unavailable")
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
                elif self.command=="GET" and path=="/v1/status": result={"mode":"pr_only","scheduler":"paperclip","live_ready":False,"reason":"operator runtime acceptance required"}
                else: raise BridgeError(404,"operation unavailable")
                self.send_json(200,result)
            except BridgeError as e: self.send_json(e.status,{"error":e.message})
            except Exception: self.send_json(400,{"error":"invalid request"})
        do_POST=handle_request
        do_GET=handle_request
    return ThreadingHTTPServer((config.get("bind","127.0.0.1"),config.get("port",18770)),Handler)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--config",required=True); args=parser.parse_args()
    config=json.loads(Path(args.config).read_text())
    upstream=lambda name: JsonHTTP(config[name]["url"],secret(config[name]["token_file"]),header=config[name].get("header","Authorization"))
    publisher=GitHubPublisher(upstream("github"),config["github"]["repository"]) if "github" in config else None
    bridge=Bridge(config["database"],upstream("hermes"),upstream("paperclip"),config["director_id"],upstream("openhands") if "openhands" in config else None,publisher)
    server(bridge,config).serve_forever()
if __name__=="__main__": main()
