#!/usr/bin/python3 -I
"""Closed worker registrar for immutable per-attempt feedback sidecars."""
from __future__ import annotations
import grp,hashlib,json,os,stat,tempfile
from pathlib import Path
try:
 from .continuous_register import regular,atomic_owned
 from .worker_prompt import canonical,digest,validate_sidecar
except ImportError:
 from continuous_register import regular,atomic_owned
 from worker_prompt import canonical,digest,validate_sidecar
ROOT=Path("/etc/loop-worker/attempt-feedback");ROOT_UID=0
def register_feedback(payload,policy_file="/etc/loop-continuous/policy.json",config_file="/etc/loop-worker/templates.json"):
 if not isinstance(payload,dict) or set(payload)!={"action","target","sidecar"} or payload.get("action")!="register_feedback" or payload.get("target")!="worker":raise ValueError("invalid feedback registration request")
 policy_path,config_path=Path(policy_file),Path(config_file);regular(policy_path,ROOT_UID);regular(config_path,ROOT_UID)
 policy=json.loads(policy_path.read_text());config=json.loads(config_path.read_text());sidecar=payload["sidecar"]
 template=config.get("templates",{}).get(sidecar.get("template_name") if isinstance(sidecar,dict) else None)
 if not isinstance(template,dict):raise ValueError("feedback template unavailable")
 validate_sidecar(sidecar,sidecar.get("job_id"),sidecar.get("template_name"),template,policy)
 prompt=Path(str(template.get("prompt_file","")));info=regular(prompt,ROOT_UID)
 if hashlib.sha256(prompt.read_bytes()).hexdigest()!=template.get("prompt_sha256"):raise ValueError("feedback raw prompt changed")
 group=grp.getgrnam("loop-worker-shared").gr_gid
 try:ROOT.mkdir(mode=0o750)
 except FileExistsError:
  before=ROOT.lstat()
  if ROOT.is_symlink() or not stat.S_ISDIR(before.st_mode) or before.st_uid!=ROOT_UID:raise ValueError("feedback root untrusted")
 os.chown(ROOT,ROOT_UID,group);os.chmod(ROOT,0o750);observed=ROOT.lstat()
 if observed.st_uid!=ROOT_UID or observed.st_gid!=group or stat.S_IMODE(observed.st_mode)!=0o750:raise ValueError("feedback root ownership mismatch")
 encoded=(canonical(sidecar)+"\n").encode();target=ROOT/(sidecar["job_id"]+".json")
 if target.exists() or target.is_symlink():
  if target.is_symlink() or target.read_bytes()!=encoded:raise ValueError("feedback sidecar conflict")
  info=target.stat()
  if info.st_uid!=ROOT_UID or info.st_gid!=group or stat.S_IMODE(info.st_mode)!=0o640 or info.st_nlink!=1:raise ValueError("feedback sidecar ownership mismatch")
 else:atomic_owned(target,encoded,ROOT_UID,0o640,group)
 return {"target":"worker","job_id":sidecar["job_id"],"policy_fingerprint":sidecar["policy_fingerprint"],"sidecar_sha256":digest(sidecar)}
