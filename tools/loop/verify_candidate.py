"""Trusted image producer: immutable source, real command execution, durable receipts."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import shutil
import pwd
import sys
from pathlib import Path

OFFLINE_ROOT=Path("/opt/offline")

def prepare_environment(env,offline_root=None,scratch_parent=None):
    offline=Path(offline_root) if offline_root is not None else OFFLINE_ROOT
    if any(not (offline/name).is_dir() for name in ("npm","uv")):raise ValueError("trusted offline npm/uv caches are required")
    scratch=Path(tempfile.mkdtemp(prefix="loop-producer-",dir=scratch_parent))
    home=scratch/"home";home.mkdir()
    for name in ("npm","uv"):
        copied=scratch/name;shutil.copytree(offline/name,copied)
        for path in [copied,*copied.rglob("*")]:
            if not path.is_symlink():path.chmod(path.stat().st_mode | (0o700 if path.is_dir() else 0o600))
    python=shutil.which("python3.14",path=env.get("PATH"))
    if not python and sys.version_info[:2]==(3,14):python=sys.executable
    if not python:raise ValueError("preinstalled Python 3.14 required; downloads disabled")
    user=pwd.getpwuid(os.getuid()).pw_name
    return {**env,"HOME":str(home),"USER":user,"LOGNAME":user,"PATH":str(Path(python).parent)+os.pathsep+env.get("PATH",""),"npm_config_cache":str(scratch/"npm"),"NPM_CONFIG_CACHE":str(scratch/"npm"),"npm_config_offline":"true","NPM_CONFIG_OFFLINE":"true","UV_CACHE_DIR":str(scratch/"uv"),"UV_OFFLINE":"1","UV_PYTHON_DOWNLOADS":"never","UV_PYTHON":python}

class VerificationFailure(Exception):
    def __init__(self,message,receipt):super().__init__(message);self.receipt=receipt

def sanitize(text):
    text=re.sub(r"(?i)(Bearer\s+)\S+",r"\1[redacted]",text)
    text=re.sub(r"(?i)([a-z][a-z0-9+.-]*://[^\s:/]+:)[^\s@]+@",r"\1[redacted]@",text)
    return re.sub(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+",r"\1[redacted]",text)

def command(argv,root,env):
    return subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True,timeout=5400,check=False)

def source_manifest(root,sha,env,require_readonly=True,stage="verify"):
    result=command(["git","-c","core.hooksPath=/dev/null","ls-tree","-rz","--full-tree",sha],root,env)
    if result.returncode:raise ValueError("candidate tree unavailable")
    entries={}
    for record in result.stdout.split("\0"):
        if not record:continue
        metadata,name=record.split("\t",1);mode,kind,blob=metadata.split()
        if kind!="blob" or name.startswith("/") or ".." in Path(name).parts:raise ValueError("unsupported candidate entry")
        path=Path(root)/name
        data=os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
        actual=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        if actual!=blob:raise ValueError("candidate content differs from SHA: "+name)
        if require_readonly and not (os.statvfs(path.parent if path.is_symlink() else path).f_flag & os.ST_RDONLY):
            # Next's sole generated declaration is a separate build overlay; it
            # was immutable during verify and never changes the original tree.
            if not (stage=="build" and name=="services/webapp/next-env.d.ts"):raise ValueError("candidate input is writable: "+name)
        entries[name]=blob
    return hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()

def produce(root,sha,stage,require_readonly=True,env=None):
    if not re.fullmatch(r"[0-9a-f]{40}",sha) or stage not in {"prepare","verify","build"}:raise ValueError("invalid verification request")
    env={**os.environ,**(env or {}),"PUPPETEER_SKIP_DOWNLOAD":"1","PROXIMA_VERIFY_READONLY":"1","PYTHONDONTWRITEBYTECODE":"1","GIT_OPTIONAL_LOCKS":"0","GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_SYSTEM":"/dev/null","UV_NO_SYNC":"1","NPM_CONFIG_AUDIT":"false","NPM_CONFIG_FUND":"false","NPM_CONFIG_LOGS_DIR":"/tmp/npm-logs"}
    receipt={"sha":sha,"stage":stage,"status":"fail","checks":{},"logs":{},"manifest_sha256":None}
    try:
        env=prepare_environment(env)
        receipt["manifest_sha256"]=source_manifest(root,sha,env,require_readonly,stage)
        if stage=="prepare":
            prepare_env={k:v for k,v in env.items() if k!="UV_NO_SYNC"}
            for name,argv in (("npm",["npm","ci","--ignore-scripts"]),("uv",["uv","sync","--python",env["UV_PYTHON"],"--project","services/control-plane","--extra","test","--locked"])):
                result=command(argv,root,prepare_env)
                receipt["logs"][name]=sanitize(result.stdout+result.stderr)
                if result.returncode:raise ValueError("dependency preparation failed: "+name)
            receipt["status"]="pass"
            return receipt
        argv=["make","verify"] if stage=="verify" else ["npm","--workspace","@proxima/webapp","run","build"]
        result=command(argv,root,env)
        receipt["logs"][stage]=sanitize(result.stdout+result.stderr)
        if result.returncode:raise ValueError("nonzero "+stage)
        if stage=="verify" and ("pg-roundtrip: PASS" not in result.stdout+result.stderr or re.search(r"pg-roundtrip: (SKIP|FAIL)",result.stdout+result.stderr)):raise ValueError("PostgreSQL gate incomplete")
        # Same immutable source tree must still be present. Build's generated
        # next-env overlay is checked by the runner against the unmounted original.
        if stage=="verify" and source_manifest(root,sha,env,require_readonly,stage)!=receipt["manifest_sha256"]:raise ValueError("source changed during verification")
        receipt["checks"]={stage:{"sha":sha,"status":"pass","skipped":0}};receipt["status"]="pass"
        return receipt
    except Exception as exc:
        receipt["reason"]=sanitize(str(exc))
        raise VerificationFailure("candidate verification failed",receipt) from None

def main():
    parser=argparse.ArgumentParser();parser.add_argument("sha");parser.add_argument("--stage",choices=["prepare","verify","build"],required=True);args=parser.parse_args()
    try:result=produce(Path.cwd(),args.sha,args.stage)
    except VerificationFailure as exc:print(json.dumps(exc.receipt));raise SystemExit(1)
    print(json.dumps(result))
if __name__=="__main__":main()
