#!/usr/bin/python3 -I
"""Install one reviewed immutable template locally and emit a target receipt."""
from __future__ import annotations
import argparse,fcntl,grp,hashlib,json,os,re,stat,tempfile
from pathlib import Path
try:
    from .bridge import template_fingerprint
    from .continuous_queue import canonical
except ImportError:
    from bridge import template_fingerprint
    from continuous_queue import canonical
class RegisterError(ValueError):pass
def regular(path,owner_uid,max_bytes=1_000_000):
    info=path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=owner_uid or info.st_mode&0o022 or info.st_nlink!=1 or info.st_size>max_bytes:raise RegisterError("untrusted registration file")
    return info
def read_bounded_fd(fd,limit):
    chunks=[];total=0
    while True:
        chunk=os.read(fd,min(65536,limit+1-total))
        if not chunk:break
        chunks.append(chunk);total+=len(chunk)
        if total>limit:raise RegisterError("registration config too large")
    return b"".join(chunks)
def write_all(fd,data):
    view=memoryview(data)
    while view:
        written=os.write(fd,view)
        if written<=0:raise RegisterError("short registration write")
        view=view[written:]
def fsync_dir(path):
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
def atomic_owned(path,data,owner_uid,mode=0o600,group_gid=-1):
    path=Path(path);fd,temporary=tempfile.mkstemp(prefix=path.name+".",dir=path.parent)
    try:
        os.fchmod(fd,mode);os.fchown(fd,owner_uid,group_gid);write_all(fd,data);os.fsync(fd);os.close(fd);fd=-1
        os.replace(temporary,path);fsync_dir(path)
    finally:
        if fd>=0:os.close(fd)
        if os.path.exists(temporary):os.unlink(temporary)
def restore_prepared(config_path,owner_uid,config_fd):
    backup=Path(str(config_path)+".continuous-backup");marker=Path(str(config_path)+".continuous-recovery.json")
    if not marker.exists():return
    regular(marker,owner_uid,100_000);state=json.loads(marker.read_text())
    if state.get("state")!="prepared":return
    regular(backup,owner_uid);raw=backup.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=state.get("old_sha256"):raise RegisterError("registration backup mismatch")
    os.lseek(config_fd,0,os.SEEK_SET);write_all(config_fd,raw);os.ftruncate(config_fd,len(raw));os.fsync(config_fd);fsync_dir(config_path)
    atomic_owned(marker,(json.dumps({**state,"state":"recovered"},sort_keys=True)+"\n").encode(),owner_uid)
def prompt_permissions(target,owner_uid):
    if target=="worker":return 0,grp.getgrnam("loop-worker-shared").gr_gid,0o640
    return owner_uid,-1,0o600
def render(item,prompt_dir):
    needed={"id","template_name","template_fingerprint","policy_fingerprint","proposal_fingerprint","review_fingerprint","template","prompt_contract"}
    if not isinstance(item,dict) or not needed<=set(item):raise RegisterError("reviewed queue export required")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}",str(item["template_name"])):raise RegisterError("invalid template name")
    template_keys={"base_sha","prompt_sha256","allowed_paths","contract_files","profile","profile_id","profile_revision"}
    if not isinstance(item["template"],dict) or set(item["template"])!=template_keys:raise RegisterError("template has unapproved fields")
    if template_fingerprint(item["template_name"],item["template"])!=item["template_fingerprint"]:raise RegisterError("template fingerprint mismatch")
    prompt=(canonical(item["prompt_contract"])+"\n").encode()
    if item["template"].get("prompt_sha256")!=hashlib.sha256(prompt).hexdigest():raise RegisterError("prompt fingerprint mismatch")
    prompt_root=Path(prompt_dir).resolve()
    prompt_path=prompt_root/(item["template_name"]+".json")
    if prompt_path.parent!=prompt_root:raise RegisterError("prompt path escapes root")
    installed={**item["template"],"prompt_file":str(prompt_path)}
    receipt_base={"template_name":item["template_name"],"template_fingerprint":item["template_fingerprint"],
      "policy_fingerprint":item["policy_fingerprint"],"proposal_fingerprint":item["proposal_fingerprint"],
      "review_fingerprint":item["review_fingerprint"]}
    return installed,prompt_path,prompt,receipt_base
def install(item,target,config_path,prompt_dir,idle_path,owner_uid):
    if target not in {"bridge","harper","worker"}:raise RegisterError("invalid registration target")
    config_path,prompt_dir=Path(config_path),Path(prompt_dir)
    regular(config_path,owner_uid)
    if idle_path is not None:
        idle_path=Path(idle_path);regular(idle_path,owner_uid,100_000)
        idle=json.loads(idle_path.read_text())
        if idle!={"idle":True}:raise RegisterError("target is not proven idle")
    installed,prompt_path,prompt,receipt=render(item,prompt_dir)
    prompt_uid,prompt_gid,prompt_mode=prompt_permissions(target,owner_uid)
    prompt_dir.mkdir(parents=True,exist_ok=True)
    if prompt_path.exists():
        info=regular(prompt_path,prompt_uid)
        if stat.S_IMODE(info.st_mode)!=prompt_mode or (target=="worker" and info.st_gid!=prompt_gid):raise RegisterError("immutable prompt ownership mismatch")
        if prompt_path.read_bytes()!=prompt:raise RegisterError("immutable prompt conflict")
    else:
        if prompt_path.is_symlink():raise RegisterError("immutable prompt conflict")
        fd=os.open(prompt_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,prompt_mode)
        try:
            os.fchown(fd,prompt_uid,prompt_gid);os.fchmod(fd,prompt_mode);write_all(fd,prompt);os.fsync(fd)
        finally:os.close(fd)
    fd=os.open(config_path,os.O_RDWR|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        restore_prepared(config_path,owner_uid,fd)
        os.lseek(fd,0,os.SEEK_SET)
        raw=read_bounded_fd(fd,1_000_000)
        config=json.loads(raw);templates=config.get("templates")
        if not isinstance(templates,dict):raise RegisterError("template registry unavailable")
        old=templates.get(item["template_name"])
        if old is not None and old!=installed:raise RegisterError("template registration conflict")
        templates[item["template_name"]]=installed
        encoded=(json.dumps(config,sort_keys=True,indent=2)+"\n").encode()
        if encoded!=raw:
            backup=Path(str(config_path)+".continuous-backup");marker_path=Path(str(config_path)+".continuous-recovery.json")
            atomic_owned(backup,raw,owner_uid)
            recovery={"state":"prepared","old_sha256":hashlib.sha256(raw).hexdigest(),
                      "new_sha256":hashlib.sha256(encoded).hexdigest(),"template_fingerprint":item["template_fingerprint"]}
            atomic_owned(marker_path,(json.dumps(recovery,sort_keys=True)+"\n").encode(),owner_uid)
            try:
                os.lseek(fd,0,os.SEEK_SET);write_all(fd,encoded);os.ftruncate(fd,len(encoded));os.fsync(fd);fsync_dir(config_path)
                atomic_owned(marker_path,(json.dumps({**recovery,"state":"committed"},sort_keys=True)+"\n").encode(),owner_uid)
            except Exception:
                try:
                    os.lseek(fd,0,os.SEEK_SET);write_all(fd,raw);os.ftruncate(fd,len(raw));os.fsync(fd)
                    atomic_owned(marker_path,(json.dumps({**recovery,"state":"recovered"},sort_keys=True)+"\n").encode(),owner_uid)
                finally:raise
    except Exception:
        raise
    finally:os.close(fd)
    readback=json.loads(config_path.read_text())
    if readback.get("templates",{}).get(item["template_name"])!=installed:raise RegisterError("template readback failed")
    installed_sha=hashlib.sha256(canonical({"name":item["template_name"],"template":installed,"prompt_sha256":hashlib.sha256(prompt).hexdigest()}).encode()).hexdigest()
    if target=="harper":
        receipt_root=Path("/etc/loop-runner/template-receipts");receipt_root.mkdir(parents=True,exist_ok=True)
        binding={"template_name":item["template_name"],"template_fingerprint":item["template_fingerprint"],
                 "policy_fingerprint":item["policy_fingerprint"],"base_sha":item["template"]["base_sha"],
                 "installed_sha256":installed_sha}
        atomic_owned(receipt_root/(item["template_name"]+".json"),(json.dumps(binding,sort_keys=True)+"\n").encode(),owner_uid,0o600)
    return {"target":target,"template_fingerprint":item["template_fingerprint"],
            "policy_fingerprint":item["policy_fingerprint"],"installed_sha256":installed_sha}
def main():
    parser=argparse.ArgumentParser()
    for name in ("item","config","prompt-dir","idle-state","receipt"):parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--target",required=True,choices=("bridge","harper","worker"));parser.add_argument("--owner-uid",required=True,type=int)
    args=parser.parse_args();item=json.loads(args.item.read_text())
    receipt=install(item,args.target,args.config,args.prompt_dir,args.idle_state,args.owner_uid)
    if args.receipt.exists():raise RegisterError("receipt already exists")
    fd=os.open(args.receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:os.write(fd,(json.dumps(receipt,sort_keys=True)+"\n").encode());os.fsync(fd)
    finally:os.close(fd)
    print(json.dumps(receipt));return 0
if __name__=="__main__":raise SystemExit(main())
