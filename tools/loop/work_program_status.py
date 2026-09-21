#!/usr/bin/python3 -I
"""Bounded research metadata projection; no model text, prompts or credentials."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

STATE_ROOT = Path("/var/lib/loop-work-program")
EVIDENCE_ROOT = Path("/srv/loop/work-program/results")
MAX_PROJECTION_BYTES = 4096
MAX_ARTIFACT_BYTES = 200_000
MAX_ARTIFACT_LOOKUPS = 8
STALE_SECONDS = 600
STATUSES = {"enabled", "running", "idle", "waiting_window", "unknown", "blocked", "unavailable"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
HASH = re.compile(r"[0-9a-f]{64}")
REASON = re.compile(r"[a-z][a-z0-9_]{0,79}")
MODELS = {"z.ai": {"glm-5.3-flash"}, "openai-codex": {
    "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-6-astra", "gpt-5.5"}}
FIELDS = {"schema_version", "projected_at_utc", "source_updated_at_utc",
          "status", "reason", "enabled", "task_id", "resume_at", "last_result"}

def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError("duplicate field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid number")))

def timestamp(value):
    if type(value) is not str or len(value) > 40: raise ValueError("invalid timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None: raise ValueError("timezone required")
    return parsed.timestamp()

def stamp(now):
    return datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")

def valid_identity(value):
    return (type(value) is dict and set(value) == {"task_id", "provider", "model", "completed_at_utc"}
        and type(value["task_id"]) is str and ID.fullmatch(value["task_id"])
        and type(value["provider"]) is str and type(value["model"]) is str
        and value["model"] in MODELS.get(value["provider"], set()))

def decode_projection(raw, now=None):
    """Validate persisted fields and calculate freshness at the moment of reading."""
    now = time.time() if now is None else now
    try:
        if type(raw) is not str or len(raw.encode("utf-8")) > MAX_PROJECTION_BYTES:
            raise ValueError("projection limit")
        value = strict_json(raw)
        if (type(value) is not dict or set(value) != FIELDS
                or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or value["status"] not in STATUSES
                or type(value["reason"]) is not str or not REASON.fullmatch(value["reason"])
                or value["enabled"] is not None and type(value["enabled"]) is not bool
                or value["task_id"] is not None and (
                    type(value["task_id"]) is not str or not ID.fullmatch(value["task_id"]))):
            raise ValueError("invalid projection")
        projected = timestamp(value["projected_at_utc"])
        updated = timestamp(value["source_updated_at_utc"]) if value["source_updated_at_utc"] is not None else None
        if projected > now + 5 or updated is not None and updated > projected + 5:
            raise ValueError("future projection")
        resume = value["resume_at"]
        if resume is not None and (type(resume) not in (int, float)
                or not math.isfinite(resume) or not 0 < resume < 10**11):
            raise ValueError("invalid resume")
        last = value["last_result"]
        if last is not None and (not valid_identity(last)
                or timestamp(last["completed_at_utc"]) > projected + 5):
            raise ValueError("invalid result")
        fresh = (updated is not None and value["status"] != "unavailable"
            and now - projected < STALE_SECONDS and now - updated < STALE_SECONDS)
        result = {**value, "fresh": fresh}
        if not fresh and value["status"] != "unavailable":
            result.update(status="stale", last_known_status=value["status"])
        return result
    except Exception:
        return {"status": "unavailable", "fresh": False}

def unavailable(now):
    return {"schema_version": 1, "projected_at_utc": stamp(now),
        "source_updated_at_utc": None, "status": "unavailable",
        "reason": "projection_unavailable", "enabled": None,
        "task_id": None, "resume_at": None, "last_result": None}

def build_projection(state, events, artifact_reader, *, now=None):
    """Copy an allowlist of metadata only; discard artifact verdict and context."""
    now = time.time() if now is None else now
    result = unavailable(now)
    try:
        if type(state) is not dict or state.get("status") not in STATUSES - {"unavailable"}:
            return result
        timestamp(state.get("updated_at_utc"))
        result.update(source_updated_at_utc=state["updated_at_utc"], status=state["status"],
            reason=state.get("reason"), enabled=state.get("enabled"),
            task_id=state.get("task_id"), resume_at=state.get("resume_at"))
        attempts = 0
        for event in reversed(events):
            if type(event) is not dict or event.get("event") != "complete": continue
            task, key = event.get("task_id"), event.get("key")
            if (type(task) is not str or not ID.fullmatch(task) or type(key) is not str
                    or not key.startswith(task + ":") or not HASH.fullmatch(key[len(task) + 1:])):
                continue
            if attempts >= MAX_ARTIFACT_LOOKUPS: break
            attempts += 1
            try:
                digest = key[len(task) + 1:]
                artifact = artifact_reader(task, digest, event.get("artifact"))
                if (artifact.get("artifact_type") != "model-research-data-not-admission"
                        or artifact.get("task_id") != task or artifact.get("content_hash") != digest):
                    continue
                last = {"task_id": task, "provider": artifact.get("provider"),
                    "model": artifact.get("model"), "completed_at_utc": artifact.get("created_at_utc")}
                if not valid_identity(last): continue
                if timestamp(last["completed_at_utc"]) > now + 5: continue
                actual = artifact.get("actual_provider_route")
                if actual is not None and (type(actual) is not dict
                        or actual.get("provider") != last["provider"] or actual.get("model") != last["model"]):
                    continue
                result["last_result"] = last
                break
            except Exception:
                continue
        if decode_projection(json.dumps(result), now).get("status") == "unavailable":
            return unavailable(now)
        return result
    except Exception:
        return unavailable(now)

def read_projection(now=None):
    now = time.time() if now is None else now
    try:
        # Host-only readers stay lazy; importing this validator in Bridge reads nothing.
        if not __package__: sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from . import work_program
        except ImportError:
            import work_program
        root = work_program._secure_dir(STATE_ROOT, "untrusted_state")
        evidence = work_program._secure_dir(EVIDENCE_ROOT, "untrusted_evidence")
        state = work_program.read_state(root)
        events = work_program.read_journal(root)
        def artifact_reader(task, digest, claimed):
            path = evidence / (task + "-" + digest + ".json")
            if claimed != str(path): raise ValueError("artifact path mismatch")
            fd = work_program._trusted_regular(path)
            with os.fdopen(fd, "rb") as handle:
                if os.fstat(handle.fileno()).st_size > MAX_ARTIFACT_BYTES: raise ValueError("artifact limit")
                raw = handle.read(MAX_ARTIFACT_BYTES + 1)
            if len(raw) > MAX_ARTIFACT_BYTES: raise ValueError("artifact limit")
            return strict_json(raw)
        return build_projection(state, events, artifact_reader, now=now)
    except Exception:
        return unavailable(now)

PUBLISH_CODE = """
import json,sqlite3,sys
raw=sys.stdin.buffer.read(4097)
if len(raw)>4096:raise SystemExit(2)
value=json.loads(raw)
if value.get('schema_version')!=1:raise SystemExit(2)
db=sqlite3.connect('file:/var/lib/loop/bridge/bridge.sqlite?mode=rw',uri=True,timeout=2)
try:
 db.execute('BEGIN IMMEDIATE')
 db.execute("INSERT INTO settings(key,value) VALUES('work_program_status',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(raw.decode('utf-8'),))
 db.commit()
finally:db.close()
"""

def publish(projection, execute=subprocess.run):
    raw = json.dumps(projection, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if (len(raw) > MAX_PROJECTION_BYTES
            or decode_projection(raw.decode("utf-8")).get("schema_version") != 1):
        raise ValueError("invalid projection")
    execute(["docker", "exec", "--user", "10001:10001", "-i", "loop-control-bridge-1",
        "python3", "-I", "-c", PUBLISH_CODE], input=raw,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    try:
        if os.geteuid() != 0: raise ValueError("root projector required")
        projection = read_projection()
        if args.preview: print(json.dumps(projection, ensure_ascii=False))
        else:
            publish(projection)
            print(json.dumps({"published": True}))
        return 0
    except Exception:
        print(json.dumps({"published": False, "reason": "projection_unavailable"}))
        return 1

if __name__ == "__main__": raise SystemExit(main())
