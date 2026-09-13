"""Private publisher journal and Linux process identity for lost push recovery."""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path

def process_identity(pid):
    if not Path("/proc/self/stat").is_file():raise RuntimeError("publication recovery requires the Harper Linux host")
    boot=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    try:
        stat=Path(f"/proc/{int(pid)}/stat").read_text()
        start=stat.rsplit(")",1)[1].split()[19]
        return boot+":"+start
    except FileNotFoundError:return None

def write_journal(path,value):
    path=Path(path);temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as stream:
        json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)

def recover_push(client,path,evidence_root,identity_reader=process_identity):
    path=Path(path).resolve();path.relative_to(Path(evidence_root).resolve())
    if path.stat().st_mode & 0o077:raise ValueError("publisher journal must be private")
    journal=json.loads(path.read_text())
    if journal.get("state")!="finished":
        for name in ("parent","child"):
            pid=journal.get(name+"_pid")
            if pid is None:continue
            actual=identity_reader(pid);expected=journal.get(name+"_identity")
            if actual is not None and (expected is None or actual==expected):raise ValueError("publisher may still run; refuse settlement")
        journal["receipt"]={"permit":journal["permit"],"publisher_id":journal["publisher_id"],"outcome":"unknown","process_stopped":True,"returncode":None,"evidence_ref":str(path)}
        journal["state"]="finished";write_journal(path,journal)
    return client.call("POST",f"/v1/runner/jobs/{journal['job_id']}/record-push",journal["receipt"])
