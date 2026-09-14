#!/usr/bin/python3 -I
"""Root gateway for isolated dispatch, credential-free collection and exact fetch."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid

SOURCE = Path("/srv/loop-worker/trusted-source/proxima-ai")
CONFIG = Path("/etc/loop-worker/templates.json")
INTEGRITY = Path("/etc/loop-worker/source-integrity.json")
RUN_ROOT = Path("/srv/loop-worker/runner-state")
WORKSPACES = Path("/srv/loop-worker/workspaces")
TRANSFER = Path("/srv/loop-worker/transfer")
COLLECTOR_HOME = Path("/srv/loop-worker/collector-home")
GATEWAY_ROOT = Path("/srv/loop-worker/gateway")
OUTBOX = GATEWAY_ROOT / "outbox"
RECEIPTS = GATEWAY_ROOT / "receipts"
DISPATCHER = Path("/opt/loop/worker_dispatch.py")
COLLECTOR = Path("/opt/loop/worker_collect.py")
ROOT_HELPER = Path("/opt/loop/worker_root.py")
SSH_HELPER = Path("/opt/loop/worker_ssh.py")
AGENT_LAUNCHER = Path("/opt/loop-openhands-agent/agent_server_launcher.py")
ACP_WRAPPER = Path("/opt/loop-openhands-agent/bin/codex-acp")
CODEX_CONFIG = Path("/etc/loop-openhands-agent/config.toml")
VOLUME_HELPER = Path("/usr/local/sbin/loop-worker-volume")
REAL_ACP = Path("/opt/loop-openhands-agent/node_modules/.bin/codex-acp")
REAL_CODEX = Path("/opt/loop-openhands-agent/node_modules/.bin/codex")
PINNED_TOOL_VERSIONS = {str(REAL_ACP):"@agentclientprotocol/codex-acp 1.1.7",str(REAL_CODEX):"codex-cli 0.151.0"}
OPENHANDS_PYTHON="/opt/loop-openhands-agent/venv/bin/python"
OPENHANDS_DISTRIBUTIONS={"openhands-agent-server":"1.44.0","openhands-sdk":"1.44.0","openhands-tools":"1.44.0","openhands-workspace":"1.44.0"}
AGENT_SERVICE = "loop-openhands-agent-server.service"
JOB = re.compile(r"[a-z0-9][a-z0-9-]{2,40}")
TEMPLATE = re.compile(r"[a-z0-9][a-z0-9-]{2,63}")
SHA1 = re.compile(r"[a-f0-9]{40}")
SHA256 = re.compile(r"[a-f0-9]{64}")
MAX_BUNDLE = 512 * 1024 * 1024
PRIVILEGED_UID = 0
LOCK_PATH = Path("/run/loop-worker-gateway.lock")


def uid(name: str) -> int:
    return pwd.getpwnam(name).pw_uid


def directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def file_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def validate_directory(info: os.stat_result, owners: set[int]) -> None:
    if not stat.S_ISDIR(info.st_mode) or info.st_uid not in owners or info.st_mode & 0o022:
        raise ValueError("untrusted directory")


def open_beneath(root: Path, components: tuple[str, ...], *, directory_owners: set[int], file_owners: set[int], file_mode: int | None = None, max_size: int = 2_000_000) -> int:
    if not root.is_absolute() or not components or any(not value or value in {".", ".."} or "/" in value for value in components):
        raise ValueError("invalid anchored path")
    descriptor = os.open(root, directory_flags())
    try:
        validate_directory(os.fstat(descriptor), directory_owners)
        for component in components[:-1]:
            next_descriptor = os.open(component, directory_flags(), dir_fd=descriptor)
            try: validate_directory(os.fstat(next_descriptor), directory_owners)
            except Exception:
                os.close(next_descriptor);raise
            os.close(descriptor);descriptor = next_descriptor
        result = os.open(components[-1], file_flags(), dir_fd=descriptor)
        info = os.fstat(result)
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in file_owners or info.st_nlink != 1 or info.st_size <= 0 or info.st_size > max_size or (file_mode is not None and stat.S_IMODE(info.st_mode) != file_mode):
            os.close(result);raise ValueError("untrusted regular file")
        return result
    finally: os.close(descriptor)


def read_fd(descriptor: int, limit: int = 2_000_000) -> bytes:
    chunks=[];total=0
    while True:
        chunk=os.read(descriptor,min(1024*1024,limit+1-total))
        if not chunk:return b"".join(chunks)
        chunks.append(chunk);total+=len(chunk)
        if total>limit:raise ValueError("trusted file is too large")


def read_json_beneath(root: Path, parts: tuple[str, ...], owners: set[int], mode: int = 0o600) -> dict:
    descriptor=open_beneath(root,parts,directory_owners=owners,file_owners=owners,file_mode=mode)
    try:value=json.loads(read_fd(descriptor))
    finally:os.close(descriptor)
    if not isinstance(value,dict):raise ValueError("invalid JSON receipt")
    return value


def root_json(path: Path) -> dict:
    descriptor=open_beneath(path.parent,(path.name,),directory_owners={PRIVILEGED_UID},file_owners={PRIVILEGED_UID})
    try:
        if os.fstat(descriptor).st_mode & 0o022:raise ValueError("trusted config is writable by group or world")
        value=json.loads(read_fd(descriptor))
    finally:os.close(descriptor)
    if not isinstance(value,dict):raise ValueError("invalid trusted config")
    return value


def hash_regular(path: Path, expected_owner: int) -> str:
    descriptor=os.open(path,file_flags())
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=expected_owner or info.st_mode&0o022:raise ValueError("integrity path is not trusted")
        digest=hashlib.sha256()
        while chunk:=os.read(descriptor,1024*1024):digest.update(chunk)
        return digest.hexdigest()
    finally:os.close(descriptor)


def verify_pinned_tool_versions(execute=subprocess.run) -> None:
    environment={"PATH":"/opt/loop-openhands-agent/node_modules/.bin:/usr/local/bin:/usr/bin:/bin","HOME":"/srv/loop-worker/agent-home","CODEX_HOME":"/srv/loop-worker/codex-home","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    for binary,expected in PINNED_TOOL_VERSIONS.items():
        result=execute([binary,"--version"],capture_output=True,text=True,timeout=10,env=environment)
        if result.returncode or result.stdout.strip()!=expected or result.stderr.strip():raise ValueError("pinned worker tool version drift")
    code="import importlib.metadata as m,json; names="+repr(sorted(OPENHANDS_DISTRIBUTIONS))+"; print(json.dumps({name:m.version(name) for name in names},sort_keys=True))"
    result=execute([OPENHANDS_PYTHON,"-I","-c",code],capture_output=True,text=True,timeout=10,env=environment)
    if result.returncode or result.stderr.strip():raise ValueError("pinned OpenHands distribution drift")
    try:observed=json.loads(result.stdout)
    except json.JSONDecodeError:raise ValueError("pinned OpenHands distribution drift") from None
    if observed!=OPENHANDS_DISTRIBUTIONS:raise ValueError("pinned OpenHands distribution drift")


def request_config(template_name: str) -> dict:
    verify_pinned_tool_versions();config=root_json(CONFIG);integrity=root_json(INTEGRITY)
    if config.get("source_repo")!=str(SOURCE) or config.get("run_root")!=str(RUN_ROOT) or config.get("workspace_root")!=str(WORKSPACES) or config.get("runtime_user")!="loop-worker-runner" or config.get("prompt_root")!="/etc/loop-worker/prompts":raise ValueError("unexpected worker roots or identities")
    template=config.get("templates",{}).get(template_name)
    if not isinstance(template,dict) or not SHA1.fullmatch(str(template.get("base_sha",""))):raise ValueError("template not admitted")
    profile_id=config.get("profile_fedor");profile_revision=config.get("profile_fedor_revision")
    if template.get("profile","fedor")!="fedor" or not isinstance(profile_id,str) or not re.fullmatch(r"[0-9a-f-]{36}",profile_id) or not isinstance(profile_revision,int) or isinstance(profile_revision,bool) or profile_revision<0 or template.get("profile_id")!=profile_id or template.get("profile_revision")!=profile_revision:raise ValueError("template Agent Profile binding is invalid")
    prompt=Path(str(template.get("prompt_file","")))
    if prompt.parent!=Path(config["prompt_root"]):raise ValueError("unexpected trusted prompt path")
    required={str(DISPATCHER):PRIVILEGED_UID,str(COLLECTOR):PRIVILEGED_UID,str(ROOT_HELPER):PRIVILEGED_UID,str(SSH_HELPER):PRIVILEGED_UID,str(AGENT_LAUNCHER):PRIVILEGED_UID,str(ACP_WRAPPER):PRIVILEGED_UID,str(CODEX_CONFIG):PRIVILEGED_UID,str(VOLUME_HELPER):PRIVILEGED_UID,str(SOURCE/"tools/orchestrator/bad_dev_story.sh"):uid("loop-worker-runner"),str(SOURCE/"tools/orchestrator/lib.sh"):uid("loop-worker-runner")}
    for candidate in config.get("templates",{}).values():
        if not isinstance(candidate,dict):raise ValueError("invalid template collection")
        candidate_prompt=Path(str(candidate.get("prompt_file","")))
        if candidate_prompt.parent!=Path(config["prompt_root"]):raise ValueError("unexpected trusted prompt path")
        required[str(candidate_prompt)]=PRIVILEGED_UID
    files=integrity.get("files")
    if integrity.get("status")!="ready" or not isinstance(files,dict) or set(files)!=set(required):raise ValueError("source integrity manifest is incomplete")
    for absolute,owner in required.items():
        expected=files[absolute]
        if not isinstance(expected,str) or not SHA256.fullmatch(expected) or hash_regular(Path(absolute),owner)!=expected:raise ValueError("trusted runtime changed")
    return template


def deterministic_conversation(job: str) -> str:
    return str(uuid.uuid5(uuid.uuid5(uuid.NAMESPACE_URL,"https://proxima.local/bad-dev-story"),job+"/1"))


def template_fingerprint(name: str,definition: dict) -> str:
    portable={key:definition.get(key) for key in ("base_sha","prompt_sha256","allowed_paths","contract_files","profile","profile_id","profile_revision")}
    for key in ("allowed_paths","contract_files"):
        if isinstance(portable[key],list):portable[key]=sorted(portable[key])
    return hashlib.sha256(json.dumps({"name":name,"contract":portable},sort_keys=True,separators=(",",":")).encode()).hexdigest()


def workspace_path(job: str) -> Path:return WORKSPACES/deterministic_conversation(job).replace("-","")
def dispatch_unit(job: str) -> str:return "loop-worker-dispatch-"+job
def collect_unit(job: str) -> str:return "loop-worker-collect-"+job


def dispatch_command(template_name: str,job: str) -> list[str]:
    return ["/usr/bin/systemd-run","--quiet","--wait","--pipe","--collect","--unit",dispatch_unit(job),"--property=Type=oneshot","--property=User=loop-worker-runner","--property=Group=loop-worker-shared",f"--property=WorkingDirectory={SOURCE}","--property=UMask=0007","--property=NoNewPrivileges=yes","--property=PrivateTmp=yes","--property=PrivateDevices=yes","--property=PrivateIPC=yes","--property=ProtectSystem=strict","--property=ProtectHome=yes","--property=ProtectHostname=yes","--property=ProtectKernelTunables=yes","--property=ProtectKernelModules=yes","--property=ProtectKernelLogs=yes","--property=ProtectControlGroups=yes","--property=ProtectClock=yes","--property=ProtectProc=invisible","--property=ProcSubset=pid","--property=RestrictNamespaces=yes","--property=RestrictSUIDSGID=yes","--property=RestrictRealtime=yes","--property=LockPersonality=yes","--property=CapabilityBoundingSet=","--property=AmbientCapabilities=","--property=RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX","--property=IPAddressDeny=any","--property=IPAddressAllow=localhost",f"--property=ReadWritePaths={SOURCE} {RUN_ROOT} {WORKSPACES}","--property=ReadOnlyPaths=/etc/loop-worker /opt/loop /srv/loop-worker/agent-state/conversations","--property=InaccessiblePaths=/srv/openhands /srv/proxima-ai /etc/proxima-ai /home/openhands-agent /srv/loop-worker/codex-home /srv/loop-worker/gateway /srv/loop-worker/transfer","--property=MemoryMax=4G","--property=CPUQuota=200%","--property=TasksMax=512","--property=TimeoutStartSec=95min","--property=RuntimeMaxSec=95min","--property=KillMode=control-group","--property=SendSIGKILL=yes","/usr/bin/python3","-I",str(DISPATCHER),"--config",str(CONFIG),"--template",template_name,"--job",job]


def collector_command(template_name: str,job: str,base_sha: str) -> list[str]:
    workspace=workspace_path(job);transfer=TRANSFER/job
    return ["/usr/bin/systemd-run","--quiet","--wait","--pipe","--collect","--unit",collect_unit(job),"--property=Type=oneshot","--property=User=loop-bundle-collector","--property=Group=loop-worker-shared",f"--property=WorkingDirectory={workspace}","--property=UMask=0077","--property=NoNewPrivileges=yes","--property=PrivateTmp=yes","--property=PrivateDevices=yes","--property=PrivateIPC=yes","--property=PrivateNetwork=yes","--property=ProtectSystem=strict","--property=ProtectHome=yes","--property=ProtectHostname=yes","--property=ProtectKernelTunables=yes","--property=ProtectKernelModules=yes","--property=ProtectKernelLogs=yes","--property=ProtectControlGroups=yes","--property=ProtectClock=yes","--property=ProtectProc=invisible","--property=ProcSubset=pid","--property=RestrictNamespaces=yes","--property=RestrictSUIDSGID=yes","--property=RestrictRealtime=yes","--property=LockPersonality=yes","--property=CapabilityBoundingSet=","--property=AmbientCapabilities=","--property=RestrictAddressFamilies=AF_UNIX","--property=IPAddressDeny=any",f"--property=ReadOnlyPaths={workspace} /opt/loop",f"--property=ReadWritePaths={transfer} {COLLECTOR_HOME}","--property=InaccessiblePaths=/srv/loop-worker/trusted-source /srv/loop-worker/runner-state /srv/loop-worker/gateway /srv/loop-worker/agent-state /srv/loop-worker/codex-home /etc/loop-worker /etc/loop-openhands-agent /srv/openhands /srv/proxima-ai /etc/proxima-ai /home/openhands-agent","--property=MemoryMax=1G","--property=CPUQuota=100%","--property=TasksMax=128","--property=TimeoutStartSec=5min","--property=RuntimeMaxSec=5min","--property=KillMode=control-group","/usr/bin/python3","-I",str(COLLECTOR),"--job",job,"--template",template_name,"--base-sha",base_sha]

sandbox_command=dispatch_command


def ensure_base(path: Path,owner: int,mode: int) -> None:
    parent=os.open(path.parent,directory_flags())
    try:
        validate_directory(os.fstat(parent),{PRIVILEGED_UID})
        try:os.mkdir(path.name,mode,dir_fd=parent)
        except FileExistsError:pass
        descriptor=os.open(path.name,directory_flags(),dir_fd=parent)
        try:
            info=os.fstat(descriptor)
            if info.st_uid==PRIVILEGED_UID and owner!=PRIVILEGED_UID:os.fchown(descriptor,owner,-1)
            os.fchmod(descriptor,mode);info=os.fstat(descriptor)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=owner or stat.S_IMODE(info.st_mode)!=mode:raise ValueError("worker directory ownership mismatch")
        finally:os.close(descriptor)
    finally:os.close(parent)


def ensure_beneath(root: Path,parts: tuple[str,...],owner: int,mode: int,root_owners: set[int]) -> None:
    descriptor=os.open(root,directory_flags())
    try:
        validate_directory(os.fstat(descriptor),root_owners)
        for index,component in enumerate(parts):
            if not component or component in {".",".."} or "/" in component:raise ValueError("invalid worker directory component")
            final=index==len(parts)-1
            try:os.mkdir(component,mode if final else 0o700,dir_fd=descriptor)
            except FileExistsError:pass
            next_descriptor=os.open(component,directory_flags(),dir_fd=descriptor)
            info=os.fstat(next_descriptor);expected=owner
            if info.st_uid==PRIVILEGED_UID and owner!=PRIVILEGED_UID:os.fchown(next_descriptor,owner,-1)
            os.fchmod(next_descriptor,mode if final else 0o700);info=os.fstat(next_descriptor)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=expected or info.st_mode&0o022:os.close(next_descriptor);raise ValueError("worker directory ownership mismatch")
            os.close(descriptor);descriptor=next_descriptor
    finally:os.close(descriptor)


def prepare_paths(job: str) -> None:
    runner=uid("loop-worker-runner")
    ensure_base(RUN_ROOT,runner,0o700);ensure_beneath(RUN_ROOT,("receipts",),runner,0o700,{runner});ensure_beneath(RUN_ROOT,("logs",),runner,0o700,{runner});ensure_beneath(RUN_ROOT,("logs","openhands-bridge"),runner,0o700,{runner});ensure_beneath(RUN_ROOT,("logs","openhands-bridge",job),runner,0o700,{runner});ensure_beneath(RUN_ROOT,("logs","openhands-bridge",job,"attempt-1"),runner,0o700,{runner})
    ensure_base(GATEWAY_ROOT,PRIVILEGED_UID,0o700);ensure_beneath(GATEWAY_ROOT,("outbox",),PRIVILEGED_UID,0o700,{PRIVILEGED_UID});ensure_beneath(GATEWAY_ROOT,("receipts",),PRIVILEGED_UID,0o700,{PRIVILEGED_UID})
    ensure_base(TRANSFER,PRIVILEGED_UID,0o711);ensure_base(COLLECTOR_HOME,uid("loop-bundle-collector"),0o700)


def prepare_transfer(job: str) -> None:ensure_beneath(TRANSFER,(job,),uid("loop-bundle-collector"),0o700,{PRIVILEGED_UID})


def dispatch_receipt(job: str,template_name: str,base_sha: str,fingerprint: str) -> dict:
    receipt=read_json_beneath(RUN_ROOT,("receipts",job+".json"),{uid("loop-worker-runner")})
    if receipt.get("ok") is not True or receipt.get("exit_code")!=0 or receipt.get("run_id")!=job or receipt.get("template")!=template_name or receipt.get("template_fingerprint")!=fingerprint or receipt.get("attempt")!=1 or receipt.get("conversation_id")!=deterministic_conversation(job) or receipt.get("branch")!="feat/loop-"+job or receipt.get("base_sha")!=base_sha or receipt.get("status")!="finished":raise ValueError("dispatch receipt invalid")
    return receipt


def collector_receipt(job: str,template_name: str,base_sha: str) -> dict:
    receipt=read_json_beneath(TRANSFER,(job,"receipt.json"),{PRIVILEGED_UID,uid("loop-bundle-collector")})
    if receipt.get("ok") is not True or receipt.get("transport_only") is not True or receipt.get("job")!=job or receipt.get("template")!=template_name or receipt.get("conversation_id")!=deterministic_conversation(job) or receipt.get("branch")!="feat/loop-"+job or receipt.get("base_sha")!=base_sha or not SHA1.fullmatch(str(receipt.get("head_sha",""))) or not isinstance(receipt.get("commits"),int) or receipt["commits"]<=0:raise ValueError("collector transport receipt invalid")
    return receipt


def root_receipt(job: str) -> dict|None:
    try:return read_json_beneath(RECEIPTS,(job+".json",),{PRIVILEGED_UID})
    except FileNotFoundError:return None


def validate_root_receipt(receipt: dict,job: str,template_name: str,base_sha: str,fingerprint: str) -> dict:
    if receipt.get("ok") is not True or receipt.get("job")!=job or receipt.get("template")!=template_name or receipt.get("template_fingerprint")!=fingerprint or receipt.get("base_sha")!=base_sha or receipt.get("conversation_id")!=deterministic_conversation(job) or receipt.get("branch")!="feat/loop-"+job or not SHA1.fullmatch(str(receipt.get("head_sha",""))) or not SHA256.fullmatch(str(receipt.get("bundle_sha256",""))):raise ValueError("stored gateway receipt invalid")
    return receipt


def atomic_root_json(path: Path,value: dict) -> None:
    encoded=json.dumps(value,sort_keys=True,ensure_ascii=False).encode();directory=os.open(path.parent,directory_flags());temporary=path.name+"."+uuid.uuid4().hex+".tmp"
    try:
        output=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600,dir_fd=directory)
        try:
            view=memoryview(encoded)
            while view:written=os.write(output,view);view=view[written:]
            os.fsync(output)
        finally:os.close(output)
        os.replace(temporary,path.name,src_dir_fd=directory,dst_dir_fd=directory);os.fsync(directory)
    finally:os.close(directory)


def copy_bundle(job: str) -> str:
    collector=uid("loop-bundle-collector");source=open_beneath(TRANSFER,(job,"result.bundle"),directory_owners={PRIVILEGED_UID,collector},file_owners={collector},file_mode=0o600,max_size=MAX_BUNDLE);directory=os.open(OUTBOX,directory_flags());temporary=job+"."+uuid.uuid4().hex+".tmp";digest=hashlib.sha256()
    try:
        output=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600,dir_fd=directory)
        try:
            while chunk:=os.read(source,1024*1024):
                digest.update(chunk);view=memoryview(chunk)
                while view:written=os.write(output,view);view=view[written:]
            os.fsync(output)
        finally:os.close(output)
        os.replace(temporary,job+".bundle",src_dir_fd=directory,dst_dir_fd=directory);os.fsync(directory)
    finally:os.close(source);os.close(directory)
    return digest.hexdigest()


def service_active(name: str) -> bool:return subprocess.run(["/usr/bin/systemctl","is-active","--quiet",name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
def run_unit(command: list[str]) -> None:
    if subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5800).returncode:raise RuntimeError("isolated worker unit failed")


def wait_for(reader,unit: str,timeout: int=5700):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:return reader()
        except FileNotFoundError:
            if not service_active(unit+".service"):break
            time.sleep(2)
    raise ValueError("existing worker unit needs operator reconciliation")


def quiesce_agent_server() -> None:
    if not service_active(AGENT_SERVICE):return
    show=subprocess.run(["/usr/bin/systemctl","show",AGENT_SERVICE,"--property=ControlGroup","--value"],capture_output=True,text=True,check=True);group=show.stdout.strip()
    if not group or group=="/" or not group.startswith("/"):raise RuntimeError("Agent Server cgroup identity unavailable")
    subprocess.run(["/usr/bin/systemctl","stop",AGENT_SERVICE],check=True,timeout=60)
    if service_active(AGENT_SERVICE):raise RuntimeError("Agent Server did not stop before collection")
    root=Path("/sys/fs/cgroup")/group.lstrip("/")
    if root.exists():
        for processes in root.rglob("cgroup.procs"):
            if processes.read_text().strip():raise RuntimeError("Agent Server cgroup still has live processes")


def restart_agent_server() -> None:
    subprocess.run(["/usr/bin/systemctl","start",AGENT_SERVICE],check=True,timeout=60)
    if not service_active(AGENT_SERVICE):raise RuntimeError("Agent Server did not restart after collection")


def finalize(job: str,template_name: str,base_sha: str,fingerprint: str) -> dict:
    prior=root_receipt(job)
    if prior is not None:
        return validate_root_receipt(prior,job,template_name,base_sha,fingerprint)
    dispatched=dispatch_receipt(job,template_name,base_sha,fingerprint);collected=collector_receipt(job,template_name,base_sha);bundle_sha=copy_bundle(job)
    receipt={"ok":True,"transport_only":True,"job":job,"template":template_name,"template_fingerprint":fingerprint,"conversation_id":dispatched["conversation_id"],"branch":collected["branch"],"base_sha":base_sha,"head_sha":collected["head_sha"],"commits":collected["commits"],"bundle_sha256":bundle_sha,"gates":{"transport":"untrusted","harper_verification_required":True}}
    atomic_root_json(RECEIPTS/(job+".json"),receipt);return receipt


def dispatch(template_name: str,job: str) -> None:
    template=request_config(template_name);base_sha=template["base_sha"];fingerprint=template_fingerprint(template_name,template);prepare_paths(job);prior=root_receipt(job)
    usage=shutil.disk_usage(WORKSPACES)
    if usage.total>8*1024**3+128*1024**2 or usage.free<512*1024**2:raise ValueError("bounded worker filesystem reserve is unavailable")
    if prior is not None:
        prior=validate_root_receipt(prior,job,template_name,base_sha,fingerprint)
        if not service_active(AGENT_SERVICE):restart_agent_server()
        print(json.dumps(prior,ensure_ascii=False));return
    try:dispatch_receipt(job,template_name,base_sha,fingerprint)
    except FileNotFoundError:
        if service_active(dispatch_unit(job)+".service"):wait_for(lambda:dispatch_receipt(job,template_name,base_sha,fingerprint),dispatch_unit(job))
        else:
            if workspace_path(job).exists():raise ValueError("workspace exists without a dispatch receipt")
            run_unit(dispatch_command(template_name,job));dispatch_receipt(job,template_name,base_sha,fingerprint)
    try:collector_receipt(job,template_name,base_sha)
    except FileNotFoundError:
        prepare_transfer(job);restart_needed=service_active(AGENT_SERVICE)
        try:
            quiesce_agent_server()
            if service_active(collect_unit(job)+".service"):wait_for(lambda:collector_receipt(job,template_name,base_sha),collect_unit(job),300)
            else:run_unit(collector_command(template_name,job,base_sha));collector_receipt(job,template_name,base_sha)
        finally:
            if restart_needed and not service_active(AGENT_SERVICE):restart_agent_server()
    receipt=finalize(job,template_name,base_sha,fingerprint)
    if not service_active(AGENT_SERVICE):restart_agent_server()
    print(json.dumps(receipt,ensure_ascii=False))


def fetch(job: str) -> None:
    receipt=root_receipt(job)
    if receipt is None or not SHA256.fullmatch(str(receipt.get("bundle_sha256",""))):raise ValueError("trusted gateway receipt unavailable")
    descriptor=open_beneath(OUTBOX,(job+".bundle",),directory_owners={PRIVILEGED_UID},file_owners={PRIVILEGED_UID},file_mode=0o600,max_size=MAX_BUNDLE);digest=hashlib.sha256()
    try:
        while chunk:=os.read(descriptor,1024*1024):digest.update(chunk)
        if not hmac.compare_digest(digest.hexdigest(),receipt["bundle_sha256"]):raise ValueError("outbox bundle differs from trusted receipt")
        os.lseek(descriptor,0,os.SEEK_SET)
        while chunk:=os.read(descriptor,1024*1024):sys.stdout.buffer.write(chunk)
    finally:os.close(descriptor)


def main() -> None:
    parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest="command",required=True);run=commands.add_parser("dispatch");run.add_argument("--template",required=True);run.add_argument("--job",required=True);get=commands.add_parser("fetch");get.add_argument("--job",required=True);args=parser.parse_args()
    if not JOB.fullmatch(args.job):raise ValueError("invalid job")
    if args.command=="dispatch":
        if not TEMPLATE.fullmatch(args.template):raise ValueError("invalid template")
        descriptor=os.open(LOCK_PATH,os.O_WRONLY|os.O_CREAT|getattr(os,"O_CLOEXEC",0)|getattr(os,"O_NOFOLLOW",0),0o600)
        try:
            info=os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=PRIVILEGED_UID:raise ValueError("worker gateway lock is untrusted")
            os.fchmod(descriptor,0o600)
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            dispatch(args.template,args.job)
        except BlockingIOError:
            raise ValueError("another worker gateway operation is active") from None
        finally:os.close(descriptor)
    else:fetch(args.job)


if __name__=="__main__":
    try:main()
    except Exception as error:raise SystemExit("LOOP worker denied: "+type(error).__name__) from None
