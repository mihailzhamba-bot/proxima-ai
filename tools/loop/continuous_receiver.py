#!/usr/bin/python3 -I
"""Forced-command receiver for one closed continuous-template registration target."""
from __future__ import annotations
import fcntl,json,os,stat,subprocess,tempfile
from pathlib import Path
if not __package__:
 import sys
 sys.path.insert(0,"/opt/loop")
 sys.path.insert(0,str(Path(__file__).resolve().parent))
try:
 from .continuous_register import install
 from .continuous_queue import digest,validate_policy
 from .continuous_base_refresh import receiver_advance
except ImportError:
 from continuous_register import install
 from continuous_queue import digest,validate_policy
 from continuous_base_refresh import receiver_advance
CONFIG=Path("/etc/loop-continuous/receiver.json")
ROLES={
 "bridge":{"config":"/etc/loop/bridge.json","prompts":"/etc/loop/continuous/prompts","owner":10001,
   "activate":None,"seal":None},
 "harper":{"config":"/etc/loop-runner/config.json","prompts":"/etc/loop-review/continuous/prompts","owner":1000,
   "activate":None,"seal":None},
 "worker":{"config":"/etc/loop-worker/templates.json","prompts":"/etc/loop-worker/prompts","owner":0,
   "activate":None,"seal":["/usr/local/sbin/loop-worker-seal"]}}
class ReceiverError(ValueError):pass
def read_bounded(fd=0,limit=45*1024*1024):
 chunks=[];total=0
 while True:
  chunk=os.read(fd,min(65536,limit+1-total))
  if not chunk:break
  chunks.append(chunk);total+=len(chunk)
  if total>limit:raise ReceiverError("request too large")
 return b"".join(chunks)
def run(command,execute=subprocess.run):
 result=execute(command,stdin=subprocess.DEVNULL,capture_output=True,timeout=120,check=False)
 if result.returncode:raise ReceiverError("fixed receiver action failed")
def registration_allowed(registration,policy):
 execution=registration.get("execution_policy");matched=None
 for requirement in policy["requirements"].values():
  for name,scope in requirement["path_sets"].items():
   expected={**requirement,"selected_path_set_id":name,"allowed_paths":scope["allowed_paths"],
             "contract_files":scope["contract_files"],"acceptance_profile":scope["acceptance_profile"]}
   if execution==expected:matched=expected
 if matched is None:return False
 template=registration.get("template",{})
 fixed=("base_sha","allowed_paths","contract_files","profile","profile_id","profile_revision")
 return isinstance(template,dict) and all(template.get(key)==matched.get(key) for key in fixed)
def _receive_unlocked(role,payload,execute=subprocess.run):
 if role not in ROLES or not isinstance(payload,dict) or payload.get("action") not in {"register","dispatch","advance_base"}:raise ReceiverError("invalid closed request")
 if payload["action"]=="advance_base":
  receipt=receiver_advance(role,payload,receive.policy_file,CONFIG,execute)
  if role=="worker":run(["/usr/local/sbin/loop-worker-seal"],execute)
  return receipt
 if payload["action"]=="dispatch":
  if role!="harper" or set(payload)!={"action"}:raise ReceiverError("dispatch denied")
  result=execute(["/usr/bin/python3","-I","/opt/loop/continuous_dispatch.py","--config","/etc/loop-continuous/dispatch.json"],stdin=subprocess.DEVNULL,capture_output=True,timeout=3600,check=False)
  if result.returncode or len(result.stdout)>100_000:raise ReceiverError("fixed dispatch failed")
  value=json.loads(result.stdout)
  if not isinstance(value,dict):raise ReceiverError("invalid dispatch receipt")
  return value
 if set(payload)!={"action","target","registration","idle_receipt"} or payload["target"]!=role or not isinstance(payload["registration"],dict):raise ReceiverError("invalid closed registration request")
 settings=ROLES[role];idle_receipt=payload["idle_receipt"];now=__import__("time").time()
 if (not isinstance(idle_receipt,dict) or set(idle_receipt)!={"observed_at","queue_current","shared_executor_busy","policy_fingerprint"}
     or idle_receipt["queue_current"] is not None or idle_receipt["shared_executor_busy"] is not False
     or not isinstance(idle_receipt["observed_at"],(int,float)) or not 0<=now-idle_receipt["observed_at"]<=60
     or idle_receipt["policy_fingerprint"]!=payload["registration"].get("policy_fingerprint")):raise ReceiverError("trusted fresh idle receipt required")
 if payload["registration"].get("policy_fingerprint")!=receive.policy_fingerprint:raise ReceiverError("receiver policy mismatch")
 policy_path=Path(receive.policy_file);info=policy_path.lstat()
 if policy_path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600:raise ReceiverError("untrusted receiver policy")
 policy=validate_policy(json.loads(policy_path.read_text()))
 if digest(policy)!=receive.policy_fingerprint:raise ReceiverError("receiver policy content mismatch")
 if not registration_allowed(payload["registration"],policy):raise ReceiverError("registration outside pinned policy")
 receipt=install(payload["registration"],role,settings["config"],settings["prompts"],None,settings["owner"])
 if settings["seal"]:run(settings["seal"],execute)
 return receipt
def receive(role,payload,execute=subprocess.run):
 lock=Path(receive.lock_file);lock.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
 try:
  fcntl.flock(fd,fcntl.LOCK_EX)
  return _receive_unlocked(role,payload,execute)
 finally:os.close(fd)
def main():
 info=CONFIG.lstat()
 if CONFIG.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1:raise ReceiverError("untrusted receiver config")
 config=json.loads(CONFIG.read_text())
 if not isinstance(config,dict) or set(config)!={"role","policy_fingerprint","policy_file","lock_file"} or config["role"] not in ROLES or not __import__("re").fullmatch(r"[0-9a-f]{64}",str(config["policy_fingerprint"])):raise ReceiverError("invalid receiver config")
 if config["lock_file"]!="/etc/loop-continuous/receiver.lock":raise ReceiverError("invalid receiver lock")
 receive.policy_fingerprint=config["policy_fingerprint"];receive.policy_file=config["policy_file"];receive.lock_file=config["lock_file"]
 print(json.dumps(receive(config["role"],json.loads(read_bounded()))));return 0
if __name__=="__main__":raise SystemExit(main())


receive.policy_fingerprint=getattr(receive,"policy_fingerprint",None)

receive.policy_file=getattr(receive,"policy_file",None)

receive.lock_file=getattr(receive,"lock_file","/tmp/loop-continuous-receiver-"+str(os.getpid())+".lock")
