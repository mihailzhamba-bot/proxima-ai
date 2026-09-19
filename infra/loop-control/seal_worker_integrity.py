#!/usr/bin/python3 -I
"""Seal the operator-reviewed LOOP worker runtime into an exact hash manifest."""

from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import tempfile


CONFIG=Path("/etc/loop-worker/templates.json")
MANIFEST=Path("/etc/loop-worker/source-integrity.json")
PROMPT_ROOT=Path("/etc/loop-worker/prompts")


def runtime_files(runner_uid: int) -> dict[Path,int]:
    source=Path("/srv/loop-worker/trusted-source/proxima-ai")
    return {
        Path("/opt/loop/worker_dispatch.py"):0,Path("/opt/loop/worker_collect.py"):0,Path("/opt/loop/worker_root.py"):0,Path("/opt/loop/worker_ssh.py"):0,Path("/opt/loop/worker_prompt.py"):0,
        Path("/opt/loop-openhands-agent/agent_server_launcher.py"):0,Path("/opt/loop-openhands-agent/bin/codex-acp"):0,Path("/etc/loop-openhands-agent/config.toml"):0,Path("/usr/local/sbin/loop-worker-volume"):0,
        source/"tools/orchestrator/bad_dev_story.sh":runner_uid,source/"tools/orchestrator/lib.sh":runner_uid,
    }


def trusted_digest(path: Path,owner: int) -> str:
    descriptor=os.open(path,os.O_RDONLY|getattr(os,"O_CLOEXEC",0)|getattr(os,"O_NOFOLLOW",0))
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=owner or info.st_nlink!=1 or info.st_mode&0o022:raise RuntimeError("integrity input is not a trusted regular file")
        value=hashlib.sha256()
        while chunk:=os.read(descriptor,1024*1024):value.update(chunk)
        return value.hexdigest()
    finally:os.close(descriptor)


def trusted_json(path: Path,owner: int) -> dict:
    descriptor=os.open(path,os.O_RDONLY|getattr(os,"O_CLOEXEC",0)|getattr(os,"O_NOFOLLOW",0))
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=owner or info.st_nlink!=1 or info.st_mode&0o022 or info.st_size>2_000_000:raise RuntimeError("worker config is not trusted")
        raw=b""
        while chunk:=os.read(descriptor,65536):raw+=chunk
    finally:os.close(descriptor)
    value=json.loads(raw)
    if not isinstance(value,dict):raise RuntimeError("worker config is invalid")
    return value


def seal(config_path: Path,manifest_path: Path,required: dict[Path,int],prompt_root: Path,shared_gid: int,manifest_uid: int = 0,prompt_owner: int = 0,config_owner: int = 0) -> dict:
    config=trusted_json(config_path,config_owner);templates=config.get("templates")
    if not isinstance(templates,dict):raise RuntimeError("worker templates are invalid")
    admitted=dict(required)
    for template in templates.values():
        if not isinstance(template,dict):raise RuntimeError("worker template is invalid")
        raw=template.get("prompt_file");prompt=Path(raw) if isinstance(raw,str) else Path()
        try:prompt.relative_to(prompt_root)
        except ValueError:raise RuntimeError("worker prompt is outside the trusted prompt root") from None
        if prompt.parent!=prompt_root or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",prompt.name):raise RuntimeError("worker prompt path is not admitted")
        admitted[prompt]=prompt_owner
    files={str(path):trusted_digest(path,owner) for path,owner in sorted(admitted.items(),key=lambda item:str(item[0]))}
    payload={"files":files,"status":"ready"};manifest_path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",dir=manifest_path.parent,delete=False) as output:
        temporary=Path(output.name);json.dump(payload,output,sort_keys=True,separators=(",",":"));output.write("\n");output.flush();os.fsync(output.fileno())
    os.chown(temporary,manifest_uid,shared_gid);os.chmod(temporary,0o640);os.replace(temporary,manifest_path)
    return payload


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--config",default=str(CONFIG));parser.add_argument("--manifest",default=str(MANIFEST));args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit("loop-worker-seal requires root")
    runner_uid=pwd.getpwnam("loop-worker-runner").pw_uid;shared_gid=grp.getgrnam("loop-worker-shared").gr_gid
    result=seal(Path(args.config),Path(args.manifest),runtime_files(runner_uid),PROMPT_ROOT,shared_gid)
    print(json.dumps({"status":"sealed","files":len(result["files"])},sort_keys=True))


if __name__=="__main__":main()
