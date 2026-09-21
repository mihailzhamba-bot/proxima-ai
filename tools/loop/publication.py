"""Private publisher journal and Linux process identity for lost push recovery."""
from __future__ import annotations
import json
import os
import uuid
import signal
from pathlib import Path

def process_identity(pid):
    if not Path("/proc/self/stat").is_file():raise RuntimeError("publication recovery requires the Harper Linux host")
    boot=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    try:
        stat=Path(f"/proc/{int(pid)}/stat").read_text()
        start=stat.rsplit(")",1)[1].split()[19]
        return boot+":"+start
    except FileNotFoundError:return None

def process_scope_running(journal):
    """Inspect the whole dedicated Linux session, not only its original leader."""
    if journal.get("process_scope")!="session-v1" or not isinstance(journal.get("child_pgid"),int) or not isinstance(journal.get("child_sid"),int) or not journal.get("child_boot_id"):
        raise ValueError("publisher process scope identity missing")
    boot=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if boot!=journal["child_boot_id"]:return False
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():continue
        try:fields=(path/"stat").read_text().rsplit(")",1)[1].split()
        except FileNotFoundError:continue
        if fields[0]!="Z" and (int(fields[2])==journal["child_pgid"] or int(fields[3])==journal["child_sid"]):return True
    return False

def terminate_gated_process(process,journal,identity_reader=process_identity):
    # Before gate release the trusted wrapper cannot have a publishing child.
    if journal.get("exec_released") is not True:
        process.kill();return
    # Never signal a recycled/unidentified process group.
    if identity_reader(process.pid)!=journal.get("child_identity"):
        raise RuntimeError("cannot prove ownership of publisher process group")
    os.killpg(journal["child_pgid"],signal.SIGKILL)

def write_journal(path,value):
    path=Path(path);temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as stream:
        json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    directory=os.open(path.parent,os.O_RDONLY | getattr(os,"O_DIRECTORY",0))
    try:os.fsync(directory)
    finally:os.close(directory)

def recover_push(client,path,evidence_root,identity_reader=process_identity,scope_reader=process_scope_running):
    path=Path(path).resolve();path.relative_to(Path(evidence_root).resolve())
    if path.stat().st_mode & 0o077:raise ValueError("publisher journal must be private")
    journal=json.loads(path.read_text())
    if journal.get("state")!="finished":
        if journal.get("parent_pid") is None or not journal.get("parent_identity"):
            raise ValueError("publisher parent identity missing; no stopped proof")
        for name in ("parent","child"):
            pid=journal.get(name+"_pid")
            if pid is None:continue
            actual=identity_reader(pid);expected=journal.get(name+"_identity")
            if actual is not None and (expected is None or actual==expected):raise ValueError("publisher may still run; refuse settlement")
        no_exec=journal.get("exec_gate")=="pipe-v1" and journal.get("exec_released") is False
        if journal.get("child_pid") is None and not no_exec:
            raise ValueError("publisher child identity missing without a no-exec guarantee")
        if not no_exec and scope_reader(journal):raise ValueError("publishing descendant may still run; refuse settlement")
        journal["receipt"]={"permit":journal["permit"],"publisher_id":journal["publisher_id"],"outcome":"unknown","process_stopped":True,"returncode":None,"evidence_ref":str(path)}
        journal["state"]="finished";write_journal(path,journal)
    return client.call("POST",f"/v1/runner/jobs/{journal['job_id']}/record-push",journal["receipt"])
