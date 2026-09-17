#!/usr/bin/python3 -I
"""Idempotent public-file installer and fail-closed role verifier for LOOP hosts."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / "infra/loop-control"
INSTALL_UID = 0
INSTALL_GID = 0
ROLLBACK_ROOT = Path("/var/backups/loop-install")
WORKER_ROOT = Path("/srv/loop-worker")
WORKER_PROFILE_NAME = "loop-codex"

CONTROL_RUNTIME_FILES = {
    ROOT / "tools/loop/bridge.py": (Path("/opt/loop/bridge.py"), 0o644),
    ROOT / "tools/loop/continuous_queue.py": (Path("/opt/loop/continuous_queue.py"), 0o644),
    ROOT / "tools/loop/continuous_dispatch.py": (Path("/opt/loop/continuous_dispatch.py"), 0o755),
    ROOT / "tools/loop/continuous_admission.py": (Path("/opt/loop/continuous_admission.py"), 0o644),
    ROOT / "tools/loop/continuous_report.py": (Path("/opt/loop/continuous_report.py"), 0o644),
    ROOT / "tools/loop/continuous_report_sender.py": (Path("/opt/loop/continuous_report_sender.py"), 0o755),
    ROOT / "tools/loop/telegram.py": (Path("/opt/loop/telegram.py"), 0o644),
    ROOT / "tools/loop/continuous_tick.py": (Path("/opt/loop/continuous_tick.py"), 0o755),
    ROOT / "tools/loop/continuous_register.py": (Path("/opt/loop/continuous_register.py"), 0o755),
    ROOT / "tools/loop/night_batch.py": (Path("/opt/loop/night_batch.py"), 0o755),
    ROOT / "tools/loop/glm_review.py": (Path("/opt/loop/glm_review.py"), 0o644),
    ROOT / "tools/loop/model_router.py": (Path("/opt/loop/model_router.py"), 0o644),
    ROOT / "tools/loop/director_tool.py": (Path("/etc/loop/native/director_tool.py"), 0o644),
    ROOT / "tools/loop/continuous_receiver.py": (Path("/usr/local/sbin/loop-continuous-register"), 0o755),
    ROOT / "tools/loop/continuous_proposal_review.py": (Path("/opt/loop/continuous-proposal-review"), 0o755),
    CONF / "continuous.policy.example.json": (Path("/etc/loop-continuous/policy.json"), 0o600),
}
CONTROL_FILES = {
    CONF / "compose.yaml": (Path("/opt/loop-control/compose.yaml"), 0o644),
    CONF / "10-paperclip-role.sh": (Path("/etc/loop/10-paperclip-role.sh"), 0o755),
    CONF / "backup.py": (Path("/usr/local/sbin/loop-backup"), 0o755),
    CONF / "health.py": (Path("/usr/local/sbin/loop-health"), 0o755),
    CONF / "network_preflight.py": (Path("/usr/local/sbin/loop-network-preflight"), 0o755),
    CONF / "openhands_relay.py": (Path("/etc/loop/openhands_relay.py"), 0o644),
    CONF / "openhands_relay_control.py": (Path("/usr/local/sbin/loop-openhands-relay-control"), 0o755),
    CONF / "tinyproxy.conf": (Path("/etc/loop-proxy/tinyproxy.conf"), 0o644),
    CONF / "loop-logrotate.conf": (Path("/etc/logrotate.d/loop-bootstrap"), 0o644),
    **CONTROL_RUNTIME_FILES,
}
CONTROL_UNITS = [
    "loop-egress-tunnel.service", "loop-egress-proxy.service", "loop-openhands-tunnel.service",
    "loop-openhands-relay.service", "loop-network-preflight.service", "loop-control.service",
    "loop-backup.service", "loop-backup.timer", "loop-health.service", "loop-health.timer",
    "loop-continuous.service", "loop-continuous.timer",
]
WORKER_FILES = {
    ROOT / "tools/loop/continuous_receiver.py": (Path("/usr/local/sbin/loop-continuous-register"), 0o755),
    ROOT / "tools/loop/continuous_register.py": (Path("/opt/loop/continuous_register.py"), 0o644),
    ROOT / "tools/loop/continuous_queue.py": (Path("/opt/loop/continuous_queue.py"), 0o644),
    ROOT / "tools/loop/bridge.py": (Path("/opt/loop/bridge.py"), 0o644),
    CONF / "loop-continuous-worker-sudoers": (Path("/etc/sudoers.d/loop-continuous-registrar"), 0o440),
    CONF / "continuous.policy.example.json": (Path("/etc/loop-continuous/policy.json"), 0o600),
    ROOT / "tools/loop/worker_dispatch.py": (Path("/opt/loop/worker_dispatch.py"), 0o755),
    ROOT / "tools/loop/worker_collect.py": (Path("/opt/loop/worker_collect.py"), 0o755),
    ROOT / "tools/loop/worker_root.py": (Path("/opt/loop/worker_root.py"), 0o755),
    ROOT / "tools/loop/worker_ssh.py": (Path("/opt/loop/worker_ssh.py"), 0o755),
    CONF / "openhands_agent_server_launcher.py": (Path("/opt/loop-openhands-agent/agent_server_launcher.py"), 0o755),
    CONF / "codex_acp_clean.py": (Path("/opt/loop-openhands-agent/bin/codex-acp"), 0o755),
    CONF / "worker_volume.py": (Path("/usr/local/sbin/loop-worker-volume"), 0o755),
    CONF / "verify_worker_host.py": (Path("/usr/local/sbin/loop-worker-verify"), 0o755),
    CONF / "seal_worker_integrity.py": (Path("/usr/local/sbin/loop-worker-seal"), 0o755),
    CONF / "openhands-agent.gitconfig": (Path("/etc/loop-openhands-agent/gitconfig"), 0o644),
    CONF / "codex-worker.config.toml": (Path("/etc/loop-openhands-agent/config.toml"), 0o444),
    CONF / "97-loop-worker-sshd.conf": (Path("/etc/ssh/sshd_config.d/97-loop-worker.conf"), 0o644),
    CONF / "loop-worker-sudoers": (Path("/etc/sudoers.d/loop-worker"), 0o440),
}
WORKER_UNITS = ["loop-worker-volume.service", "loop-openhands-directories.service", "loop-openhands-agent-server.service"]
RUNNER_UNITS = ["loop-runner-bridge-tunnel.service", "loop-runner.service"]
RUNNER_FILES = {
    ROOT / "tools/loop/continuous_receiver.py": (Path("/usr/local/sbin/loop-continuous-register"), 0o755),
    ROOT / "tools/loop/continuous_dispatch.py": (Path("/opt/loop/continuous_dispatch.py"), 0o755),
    ROOT / "tools/loop/continuous_admission.py": (Path("/opt/loop/continuous_admission.py"), 0o644),
    ROOT / "tools/loop/night_batch.py": (Path("/opt/loop/night_batch.py"), 0o755),
    ROOT / "tools/loop/glm_review.py": (Path("/opt/loop/glm_review.py"), 0o644),
    ROOT / "tools/loop/model_router.py": (Path("/opt/loop/model_router.py"), 0o644),
    ROOT / "tools/loop/continuous_register.py": (Path("/opt/loop/continuous_register.py"), 0o644),
    ROOT / "tools/loop/continuous_queue.py": (Path("/opt/loop/continuous_queue.py"), 0o644),
    CONF / "loop-continuous-runner-sudoers": (Path("/etc/sudoers.d/loop-continuous-registrar"), 0o440),
    CONF / "continuous.policy.example.json": (Path("/etc/loop-continuous/policy.json"), 0o600),
    ROOT / "tools/loop/continuous_acceptance.py": (Path("/opt/loop-review/continuous-acceptance"), 0o755),
    CONF / "continuous-acceptance/migrations.json": (Path("/opt/loop-review/continuous/migrations.json"), 0o644),
    CONF / "continuous-acceptance/daily_candidate.py": (Path("/opt/loop-review/continuous/daily_candidate.py"), 0o644),
    CONF / "continuous-acceptance/status_candidate.py": (Path("/opt/loop-review/continuous/status_candidate.py"), 0o644),
    CONF / "continuous-acceptance/warehouse_candidate.mts": (Path("/opt/loop-review/continuous/warehouse_candidate.mts"), 0o644),
    CONF / "continuous-acceptance/warehouse-check.mts": (Path("/opt/loop-review/continuous/warehouse-check.mts"), 0o644),
    CONF / "continuous-acceptance/warehouse-pg-acceptance.py": (Path("/opt/loop-review/continuous/warehouse-pg-acceptance.py"), 0o644),
    CONF / "continuous-acceptance/wb_daily_acceptance.py": (Path("/opt/loop-review/continuous/wb_daily_acceptance.py"), 0o644),
    CONF / "continuous-acceptance/wb_daily_status_acceptance.py": (Path("/opt/loop-review/continuous/wb_daily_status_acceptance.py"), 0o644),
    ROOT / "tools/loop/review_candidate.py": (Path("/opt/loop-review/review-candidate"), 0o755),
    ROOT / "tools/loop/runner.py": (Path("/opt/loop/runner.py"), 0o755),
    ROOT / "tools/loop/bridge.py": (Path("/opt/loop/bridge.py"), 0o644),
    ROOT / "tools/loop/publication.py": (Path("/opt/loop/publication.py"), 0o644),
    ROOT / "tools/loop/push_gate.py": (Path("/opt/loop/push_gate.py"), 0o644),
    ROOT / "tools/loop/verify_candidate.py": (Path("/opt/loop/verify_candidate.py"), 0o644),
    ROOT / "tools/loop/history_gate.py": (Path("/opt/loop/history_gate.py"), 0o755),
    ROOT / "tools/loop/loopctl.py": (Path("/opt/loop/loopctl.py"), 0o755),
    ROOT / "tools/secret_scan.py": (Path("/opt/loop/secret_scan.py"), 0o644),
}


def run(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, check=check)


def digest(path: Path) -> str:
    value=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):value.update(chunk)
    return value.hexdigest()


def group(name: str, apply: bool) -> None:
    try:grp.getgrnam(name);return
    except KeyError:
        if not apply:raise RuntimeError("missing group: "+name)
    run(["/usr/sbin/groupadd","--system",name])


def user(name: str, primary: str, home: str, apply: bool, shell: str = "/usr/sbin/nologin") -> None:
    try:
        account=pwd.getpwnam(name);expected_gid=grp.getgrnam(primary).gr_gid
        if account.pw_gid!=expected_gid or account.pw_dir!=home or account.pw_shell!=shell:raise RuntimeError("account contract drift: "+name)
        return
    except KeyError:
        if not apply:raise RuntimeError("missing user: "+name)
    run(["/usr/sbin/useradd","--system","--home-dir",home,"--create-home","--shell",shell,"--gid",primary,name])


def supplementary_groups(name: str) -> set[str]:
    account=pwd.getpwnam(name)
    primary=grp.getgrgid(account.pw_gid).gr_name
    return {grp.getgrgid(gid).gr_name for gid in os.getgrouplist(name,account.pw_gid)}-{primary}


def account_contract(names: list[str], expected_supplementary: dict[str,set[str]] | None = None) -> None:
    expected_supplementary=expected_supplementary or {}
    accounts=[pwd.getpwnam(name) for name in names]
    if any(account.pw_uid==0 for account in accounts) or len({account.pw_uid for account in accounts})!=len(accounts):
        raise RuntimeError("service account UID contract drift")
    for name in names:
        if supplementary_groups(name)!=expected_supplementary.get(name,set()):
            raise RuntimeError("service account group contract drift: "+name)


def install_file(source: Path, target: Path, mode: int) -> None:
    info=source.lstat()
    if not stat.S_ISREG(info.st_mode) or source.is_symlink():raise RuntimeError("invalid installer source")
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
    with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as output:
        temporary=Path(output.name)
        with source.open("rb") as input_handle:shutil.copyfileobj(input_handle,output)
        output.flush();os.fsync(output.fileno())
    os.chown(temporary,INSTALL_UID,INSTALL_GID);os.chmod(temporary,mode);os.replace(temporary,target)


def install_map(files: dict[Path,tuple[Path,int]], apply: bool, drift: list[str]) -> None:
    for source,(target,mode) in files.items():
        same=target.is_file() and not target.is_symlink() and digest(source)==digest(target) and stat.S_IMODE(target.stat().st_mode)==mode and target.stat().st_uid==INSTALL_UID
        if not same:
            drift.append(str(target))
            if apply:install_file(source,target,mode)


def install_units(names: list[str], apply: bool, drift: list[str]) -> list[Path]:
    mapping={CONF/name:(Path("/etc/systemd/system")/name,0o644) for name in names}
    install_map(mapping,apply,drift)
    return [Path("/etc/systemd/system")/name for name in names]


def role_mapping(role: str) -> dict[Path,tuple[Path,int]]:
    files={"control":CONTROL_FILES,"worker":WORKER_FILES,"runner":RUNNER_FILES}[role].copy()
    units={"control":CONTROL_UNITS,"worker":WORKER_UNITS,"runner":RUNNER_UNITS}[role]
    files.update({CONF/name:(Path("/etc/systemd/system")/name,0o644) for name in units})
    if role=="worker":
        files[CONF/"worker.templates.example.json"]=(Path("/etc/loop-worker/templates.json"),0o640)
        files[CONF/"source-integrity.example.json"]=(Path("/etc/loop-worker/source-integrity.json"),0o640)
    return files


def validate_sources(role: str) -> None:
    mapping=role_mapping(role)
    for source in mapping:
        if source.suffix==".py":ast.parse(source.read_text(),filename=str(source))
    if role=="worker" and Path("/usr/sbin/visudo").exists():
        if run(["/usr/sbin/visudo","-cf",str(CONF/"loop-worker-sudoers")],check=False).returncode:raise RuntimeError("invalid source sudoers")


def snapshot(mapping: dict[Path,tuple[Path,int]]) -> tuple[Path,dict]:
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+str(os.getpid())
    root=ROLLBACK_ROOT/stamp;root.mkdir(parents=True,mode=0o700);os.chown(root,INSTALL_UID,INSTALL_GID);os.chmod(root,0o700)
    manifest={}
    for _source,(target,_mode) in mapping.items():
        key=str(target);entry={"existed":target.exists()}
        if target.exists():
            info=target.lstat()
            if not stat.S_ISREG(info.st_mode) or target.is_symlink():raise RuntimeError("cannot snapshot non-regular install target")
            backup=root/(hashlib.sha256(key.encode()).hexdigest()+".bak");shutil.copy2(target,backup);os.chown(backup,INSTALL_UID,INSTALL_GID);os.chmod(backup,0o600)
            entry.update(backup=str(backup),mode=stat.S_IMODE(info.st_mode),uid=info.st_uid,gid=info.st_gid)
        manifest[key]=entry
    record=root/"manifest.json";record.write_text(json.dumps(manifest,sort_keys=True));os.chown(record,INSTALL_UID,INSTALL_GID);os.chmod(record,0o600)
    return root,manifest


def restore_snapshot(manifest: dict) -> None:
    for raw,entry in manifest.items():
        target=Path(raw)
        if entry["existed"]:
            backup=Path(entry["backup"]);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(backup,target);os.chown(target,entry["uid"],entry["gid"]);os.chmod(target,entry["mode"])
        elif target.exists() and target.is_file() and not target.is_symlink():target.unlink()


def snapshot_units(names: list[str]) -> dict[str,dict[str,bool]]:
    return {name:{
        "enabled":run(["/usr/bin/systemctl","is-enabled","--quiet",name],check=False).returncode==0,
        "active":run(["/usr/bin/systemctl","is-active","--quiet",name],check=False).returncode==0,
    } for name in names}


def restore_units(states: dict[str,dict[str,bool]]) -> None:
    for name,state in states.items():run(["/usr/bin/systemctl","enable" if state["enabled"] else "disable",name],check=False)
    for name,state in states.items():run(["/usr/bin/systemctl","restart" if state["active"] else "stop",name],check=False)
    for name,state in states.items():
        enabled=run(["/usr/bin/systemctl","is-enabled","--quiet",name],check=False).returncode==0
        active=run(["/usr/bin/systemctl","is-active","--quiet",name],check=False).returncode==0
        if enabled!=state["enabled"] or active!=state["active"]:raise RuntimeError("rollback could not restore service state")


def private_file(path: str, mode: int, missing: list[str], owner: str = "root", group_name: str | None = None) -> None:
    value=Path(path)
    try:info=value.lstat();expected=pwd.getpwnam(owner).pw_uid
    except (FileNotFoundError,KeyError):missing.append(path);return
    expected_group=grp.getgrnam(group_name).gr_gid if group_name else info.st_gid
    if not stat.S_ISREG(info.st_mode) or value.is_symlink() or stat.S_IMODE(info.st_mode)!=mode or info.st_uid!=expected or info.st_gid!=expected_group:missing.append(path)


def private_numeric(path: str, mode: int, missing: list[str], owner_uid: int) -> None:
    value=Path(path)
    try:info=value.lstat()
    except FileNotFoundError:missing.append(path);return
    if not stat.S_ISREG(info.st_mode) or value.is_symlink() or stat.S_IMODE(info.st_mode)!=mode or info.st_uid!=owner_uid:missing.append(path)


def private_same_numeric_owner(paths: list[str], mode: int, missing: list[str]) -> None:
    owners=[]
    for raw in paths:
        path=Path(raw)
        try:info=path.lstat()
        except FileNotFoundError:missing.append(raw);continue
        if not stat.S_ISREG(info.st_mode) or path.is_symlink() or stat.S_IMODE(info.st_mode)!=mode:missing.append(raw)
        else:owners.append(info.st_uid)
    if owners and (len(owners)!=len(paths) or len(set(owners))!=1 or owners[0] in {0,10000,10001}):missing.append("postgres-secret-owner")


def private_directory(path: str, mode: int, missing: list[str], owner: str) -> None:
    value=Path(path)
    try:info=value.lstat();expected=pwd.getpwnam(owner).pw_uid
    except (FileNotFoundError,KeyError):missing.append(path);return
    if not stat.S_ISDIR(info.st_mode) or value.is_symlink() or stat.S_IMODE(info.st_mode)!=mode or info.st_uid!=expected:missing.append(path)


def validate_images(path: Path, missing: list[str]) -> None:
    if not path.is_file():return
    values={}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name,value=line.split("=",1);values[name.strip()]=value.strip()
    required={"LOOP_POSTGRES_IMAGE","LOOP_PAPERCLIP_IMAGE","LOOP_HERMES_IMAGE","LOOP_BRIDGE_IMAGE"}
    digest_pin=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}$")
    if not required.issubset(values) or any(not digest_pin.fullmatch(values[name]) for name in required):missing.append(str(path)+":digest-pins")
    telegram_config=Path("/etc/loop/telegram.json").is_file();profiles={value.strip() for value in values.get("COMPOSE_PROFILES","").split(",") if value.strip()}
    if telegram_config != ("telegram" in profiles):missing.append(str(path)+":telegram-profile")


def verify_units(paths: list[Path], errors: list[str]) -> None:
    result=run(["/usr/bin/systemd-analyze","verify",*[str(path) for path in paths]],check=False)
    if result.returncode:errors.append("systemd-analyze")


def ensure_worker_volume(apply: bool, missing: list[str]) -> None:
    image=Path("/var/lib/loop-worker-volume.img");target=WORKER_ROOT;size=8*1024**3
    if apply:
        target.mkdir(parents=True,exist_ok=True,mode=0o755);os.chown(target,0,0);os.chmod(target,0o755)
        if not image.exists():
            if shutil.disk_usage("/var/lib").free<size+2*1024**3:raise RuntimeError("insufficient disk for bounded worker volume")
            for child in target.iterdir():
                if child.is_symlink() or not child.is_dir() or any(child.iterdir()):raise RuntimeError("refuse to hide non-empty existing worker path")
            temporary=image.with_suffix(".tmp")
            run(["/usr/bin/fallocate","-l",str(size),str(temporary)]);run(["/usr/sbin/mkfs.ext4","-q","-F",str(temporary)]);os.chown(temporary,0,0);os.chmod(temporary,0o600);os.replace(temporary,image)
    try:info=image.lstat()
    except FileNotFoundError:missing.append(str(image));return
    if not stat.S_ISREG(info.st_mode) or image.is_symlink() or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size!=size:missing.append(str(image)+":invalid")


def verify_worker_tool_versions(errors: list[str]) -> None:
    pins=json.loads((CONF/"versions.lock.json").read_text())["openhands"]
    expected=[("/opt/loop-openhands-agent/node_modules/.bin/codex-acp","@agentclientprotocol/codex-acp "+pins["codex_acp"]),("/opt/loop-openhands-agent/node_modules/.bin/codex","codex-cli "+pins["codex_cli"])]
    environment={"PATH":"/opt/loop-openhands-agent/node_modules/.bin:/usr/local/bin:/usr/bin:/bin","HOME":"/srv/loop-worker/agent-home","CODEX_HOME":"/srv/loop-worker/codex-home","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    for binary,version in expected:
        result=subprocess.run([binary,"--version"],capture_output=True,text=True,timeout=10,env=environment) if Path(binary).is_file() else None
        if result is None or result.returncode or result.stdout.strip()!=version or result.stderr.strip():errors.append("worker-tool-version:"+Path(binary).name)
    distributions={"openhands-agent-server":pins["agent_server"],"openhands-sdk":pins["sdk"],"openhands-tools":pins["tools"],"openhands-workspace":pins["workspace"]}
    code="import importlib.metadata as m,json; names="+repr(sorted(distributions))+"; print(json.dumps({name:m.version(name) for name in names},sort_keys=True))"
    python=Path("/opt/loop-openhands-agent/venv/bin/python");result=subprocess.run([str(python),"-I","-c",code],capture_output=True,text=True,timeout=10,env=environment) if python.is_file() else None
    try:observed=json.loads(result.stdout) if result is not None and result.returncode==0 and not result.stderr.strip() else None
    except json.JSONDecodeError:observed=None
    if observed!=distributions:errors.append("worker-tool-version:openhands")


def validate_codex_auth(path: Path,missing: list[str]) -> None:
    try:payload=json.loads(path.read_text())
    except Exception:missing.append(str(path)+":invalid-chatgpt-auth");return
    tokens=payload.get("tokens")
    required={"access_token","account_id","id_token","refresh_token"}
    if payload.get("auth_mode")!="chatgpt" or payload.get("OPENAI_API_KEY") is not None or not isinstance(payload.get("last_refresh"),str) or not payload["last_refresh"] or not isinstance(tokens,dict) or not required.issubset(tokens) or any(not isinstance(tokens[name],str) or len(tokens[name])<16 for name in required):missing.append(str(path)+":invalid-chatgpt-auth")


def verify_codex_login(errors: list[str]) -> None:
    environment={"PATH":"/opt/loop-openhands-agent/node_modules/.bin:/usr/local/bin:/usr/bin:/bin","HOME":"/srv/loop-worker/agent-home","CODEX_HOME":"/srv/loop-worker/codex-home","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    result=subprocess.run(["/usr/sbin/runuser","-u","loop-oh-agent","--","/usr/bin/env",*[f"{key}={value}" for key,value in environment.items()],"/opt/loop-openhands-agent/node_modules/.bin/codex","login","status"],capture_output=True,text=True,timeout=15)
    if not valid_codex_login(result):errors.append("codex-chatgpt-login")


def valid_codex_login(result) -> bool:
    lines=[line for line in (result.stdout+"\n"+result.stderr).splitlines() if line]
    allowed=lambda line:line=="Logged in using ChatGPT" or line.startswith("WARNING: proceeding, even though we could not create PATH aliases:")
    return result.returncode==0 and "Logged in using ChatGPT" in lines and all(allowed(line) for line in lines)


def validate_worker_integrity(missing: list[str],config_path: Path = Path("/etc/loop-worker/templates.json"),manifest_path: Path = Path("/etc/loop-worker/source-integrity.json"),required_override: dict[Path,int] | None = None,prompt_owner: int = 0) -> None:
    if not config_path.is_file() or not manifest_path.is_file():return
    try:config=json.loads(config_path.read_text());manifest=json.loads(manifest_path.read_text())
    except Exception:missing.append(str(manifest_path)+":invalid");return
    required=dict(required_override) if required_override is not None else {
        Path("/opt/loop/worker_dispatch.py"):0,Path("/opt/loop/worker_collect.py"):0,Path("/opt/loop/worker_root.py"):0,Path("/opt/loop/worker_ssh.py"):0,
        Path("/opt/loop-openhands-agent/agent_server_launcher.py"):0,Path("/opt/loop-openhands-agent/bin/codex-acp"):0,Path("/etc/loop-openhands-agent/config.toml"):0,Path("/usr/local/sbin/loop-worker-volume"):0,
        Path("/srv/loop-worker/trusted-source/proxima-ai/tools/orchestrator/bad_dev_story.sh"):pwd.getpwnam("loop-worker-runner").pw_uid,
        Path("/srv/loop-worker/trusted-source/proxima-ai/tools/orchestrator/lib.sh"):pwd.getpwnam("loop-worker-runner").pw_uid,
    }
    templates=config.get("templates")
    if not isinstance(templates,dict):missing.append(str(manifest_path)+":invalid");return
    for template in templates.values():
        if not isinstance(template,dict) or not isinstance(template.get("prompt_file"),str):missing.append(str(manifest_path)+":invalid");return
        required[Path(template["prompt_file"])]=prompt_owner
    files=manifest.get("files")
    if manifest.get("status")!="ready" or not isinstance(files,dict) or set(files)!={str(path) for path in required}:missing.append(str(manifest_path)+":unsealed");return
    for path,owner in required.items():
        try:info=path.lstat();expected=files[str(path)]
        except (FileNotFoundError,KeyError):missing.append(str(manifest_path)+":unsealed");return
        if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=owner or info.st_mode&0o022 or not isinstance(expected,str) or not re.fullmatch(r"[0-9a-f]{64}",expected) or digest(path)!=expected:
            missing.append(str(manifest_path)+":unsealed");return


def validate_runner_inputs(config: dict,missing: list[str],trusted_uid: int = 0) -> None:
    if config.get("bridge_url")!="http://127.0.0.1:18771" or config.get("worker_host")!="loop-worker@135.106.186.210" or config.get("publish_remote")!="git@github.com:mihailzhamba-bot/proxima-ai.git":missing.append("runner-endpoint-contract")
    public_keys=[]
    for name in ["worker_identity_file","github_publish_identity_file"]:
        path=Path(str(config.get(name,"")))
        # An empty passphrase is explicit: encrypted keys must never leave a
        # headless systemd service looking ready while waiting for a prompt.
        result=subprocess.run(["/usr/bin/ssh-keygen","-y","-P","","-f",str(path)],capture_output=True,text=True,timeout=10) if path.is_file() else None
        if result is None or result.returncode or not result.stdout.startswith("ssh-") or result.stderr.strip():missing.append(str(path)+":invalid-private-key")
        else:public_keys.append(result.stdout.strip())
    if len(public_keys)==2 and public_keys[0]==public_keys[1]:missing.append("runner-identities-must-be-distinct")
    known=Path(str(config.get("known_hosts_file","")))
    for host in ["135.106.186.210","github.com"]:
        result=subprocess.run(["/usr/bin/ssh-keygen","-F",host,"-f",str(known)],capture_output=True,text=True,timeout=10) if known.is_file() else None
        if result is None or result.returncode or not result.stdout.strip():missing.append(str(known)+":missing:"+host)
    reviewer=config.get("reviewer_command")
    executable=Path(str(reviewer[0])) if isinstance(reviewer,list) and reviewer else Path()
    try:info=executable.lstat()
    except FileNotFoundError:missing.append("reviewer-executable")
    else:
        if not executable.is_absolute() or executable.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=trusted_uid or info.st_mode&0o022 or not info.st_mode&0o111:missing.append("reviewer-executable")

    templates=config.get("templates")
    if not isinstance(templates,dict) or not templates:
        missing.append("runner-templates")
    else:
        for name,template in templates.items():
            if not isinstance(template,dict):
                missing.append("runner-template:"+str(name));continue
            try:profile_id=str(uuid.UUID(template.get("profile_id")))
            except (ValueError,TypeError,AttributeError):profile_id=""
            allowed=template.get("allowed_paths");contracts=template.get("contract_files")
            safe=lambda value:isinstance(value,str) and value and bool(Path(value).parts) and not value.startswith("/") and ".." not in Path(value).parts and Path(value).parts[0]!=".git" and "\x00" not in value
            paths_valid=isinstance(allowed,list) and bool(allowed) and all(safe(value) for value in allowed) and len(set(allowed))==len(allowed)
            contracts_valid=isinstance(contracts,list) and all(safe(value) for value in contracts) and len(set(contracts))==len(contracts)
            if not isinstance(name,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}",name) or not re.fullmatch(r"[0-9a-f]{40}",str(template.get("base_sha",""))) or not re.fullmatch(r"[0-9a-f]{64}",str(template.get("prompt_sha256",""))) or not paths_valid or not contracts_valid or template.get("profile","fedor")!="fedor" or profile_id!=template.get("profile_id") or not isinstance(template.get("profile_revision"),int) or isinstance(template.get("profile_revision"),bool) or template["profile_revision"]<0:
                missing.append("runner-template:"+str(name))


def runner_runtime_checks(config: dict,missing: list[str]) -> None:
    """Prove Harper's external capabilities without mutating remote state."""
    def verifier_command(argv: list[str],extra_environment: dict[str,str] | None = None) -> list[str]:
        environment={"PATH":"/usr/bin:/bin","HOME":str(config.get("trusted_home","")),**(extra_environment or {})}
        return ["/usr/sbin/runuser","-u","verifier","--","/usr/bin/env","-i",*[key+"="+value for key,value in environment.items()],*argv]
    docker=verifier_command(["/usr/bin/docker"])
    try:daemon=subprocess.run([*docker,"info"],capture_output=True,text=True,timeout=15)
    except (FileNotFoundError,subprocess.TimeoutExpired):daemon=None
    if daemon is None or daemon.returncode:missing.append("docker-daemon")
    image=config.get("verification_image")
    valid_image=isinstance(image,str) and re.fullmatch(r"[A-Za-z0-9._:/-]+@sha256:[0-9a-f]{64}",image)
    if not valid_image:
        missing.append("verification-image-ref")
    elif daemon is not None and daemon.returncode==0:
        try:inspection=subprocess.run([*docker,"image","inspect","--format","{{json .RepoDigests}}",image],capture_output=True,text=True,timeout=15)
        except (FileNotFoundError,subprocess.TimeoutExpired):inspection=None
        try:repo_digests=json.loads(inspection.stdout) if inspection is not None and inspection.returncode==0 else []
        except json.JSONDecodeError:repo_digests=[]
        if not isinstance(repo_digests,list) or image not in repo_digests:
            missing.append("verification-image-local")
        else:
            try:offline=subprocess.run([*docker,"run","--rm","--network","none","--entrypoint","/bin/sh",image,"-ceu","test -d /opt/offline/npm && test -d /opt/offline/uv && test -x /usr/bin/python3 && test -x /usr/bin/ssh-keygen"],capture_output=True,text=True,timeout=30)
            except (FileNotFoundError,subprocess.TimeoutExpired):offline=None
            if offline is None or offline.returncode:missing.append("verification-image-offline-inputs")

    work_root=Path(str(config.get("work_root","")))
    try:free=shutil.disk_usage(work_root).free
    except OSError:free=0
    floor=config.get("disk_floor_bytes",8*1024**3)
    if type(floor) is not int or floor<6*1024**3 or free<floor:missing.append("runner-disk-reserve")

    token_path=Path(str(config.get("runner_token_file","")))
    try:
        token=token_path.read_text().strip()
        if len(token)<32:raise ValueError
        request=urllib.request.Request("http://127.0.0.1:18771/v1/runner/jobs/next",headers={"Authorization":"Bearer "+token})
        with urllib.request.urlopen(request,timeout=10) as response:bridge=json.load(response)
        if not isinstance(bridge,dict) or set(bridge)!={"job_id"}:raise ValueError
    except Exception:missing.append("bridge-runner-auth")

    known=str(config.get("known_hosts_file",""));worker_key=str(config.get("worker_identity_file",""));worker=str(config.get("worker_host",""))
    ssh_options=["-F","/dev/null","-oBatchMode=yes","-oIdentityAgent=none","-oGlobalKnownHostsFile=/dev/null","-oUpdateHostKeys=no","-oPasswordAuthentication=no","-oKbdInteractiveAuthentication=no","-oConnectTimeout=10","-oControlMaster=no","-oControlPath=none","-oForwardAgent=no","-oIdentitiesOnly=yes","-oStrictHostKeyChecking=yes","-oUserKnownHostsFile="+known]
    ssh=verifier_command(["/usr/bin/ssh",*ssh_options,"-i",worker_key,worker,"/opt/loop/worker_fetch","--job","installer-probe"])
    try:worker_probe=subprocess.run(ssh,capture_output=True,text=True,timeout=15)
    except (FileNotFoundError,subprocess.TimeoutExpired):worker_probe=None
    if worker_probe is None or worker_probe.returncode==0 or worker_probe.stdout or not re.fullmatch(r"LOOP worker denied: [A-Za-z]+\n?",worker_probe.stderr):missing.append("worker-forced-ssh-auth")

    git_key=str(config.get("github_publish_identity_file",""));source=str(config.get("source_repo",""));remote=str(config.get("publish_remote",""))
    git_ssh=shlex.join(["/usr/bin/ssh",*ssh_options,"-i",git_key])
    environment={"GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_SYSTEM":"/dev/null","GIT_CONFIG_NOSYSTEM":"1","GIT_TERMINAL_PROMPT":"0","GIT_SSH_COMMAND":git_ssh}
    try:github_probe=subprocess.run(verifier_command(["/usr/bin/git","-c","core.hooksPath=/dev/null","-C",source,"push","--dry-run",remote,"HEAD:refs/heads/loop-installer-auth-probe"],environment),capture_output=True,text=True,timeout=30)
    except (FileNotFoundError,subprocess.TimeoutExpired):github_probe=None
    if github_probe is None or github_probe.returncode:missing.append("github-publication-auth")


WORKER_DIRECTORIES = [
    ("agent-home","loop-oh-agent","loop-oh-agent",0o700),
    ("agent-state","loop-oh-agent","loop-worker-shared",0o750),
    ("agent-state/openhands","loop-oh-agent","loop-oh-agent",0o700),
    ("agent-state/conversations","loop-oh-agent","loop-worker-shared",0o2750),
    ("agent-state/bash-events","loop-oh-agent","loop-oh-agent",0o700),
    ("agent-state/tmp","loop-oh-agent","loop-oh-agent",0o700),
    ("codex-home","loop-oh-agent","loop-oh-agent",0o700),
    ("runner-state","loop-worker-runner","loop-worker-runner",0o700),
    ("runner-state/tmp","loop-worker-runner","loop-worker-runner",0o700),
    ("trusted-source","loop-worker-runner","loop-worker-runner",0o700),
    ("collector-home","loop-bundle-collector","loop-bundle-collector",0o700),
    ("collector-home/tmp","loop-bundle-collector","loop-bundle-collector",0o700),
    ("gateway","root","root",0o700),
    ("gateway/outbox","root","root",0o700),
    ("gateway/receipts","root","root",0o700),
    ("transfer","root","root",0o711),
    ("workspaces","loop-worker-runner","loop-worker-shared",0o2770),
    ("worktrees","loop-oh-agent","loop-worker-shared",0o2770),
]


def prepare_worker_directories() -> None:
    for relative,owner,group_name,mode in WORKER_DIRECTORIES:
        path=WORKER_ROOT/relative
        path.mkdir(parents=True,exist_ok=True)
        if path.is_symlink() or not path.is_dir():raise RuntimeError("invalid worker state directory")
        os.chown(path,pwd.getpwnam(owner).pw_uid,grp.getgrnam(group_name).gr_gid);os.chmod(path,mode)
    target=WORKER_ROOT/"codex-home/config.toml"
    if target.exists() and (target.is_symlink() or not target.is_file()):raise RuntimeError("invalid Codex config bind target")
    if not target.exists():
        descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o444);os.close(descriptor)
    os.chown(target,0,0);os.chmod(target,0o444)


def migrate_worker_auth() -> None:
    source=Path("/var/lib/loop-oh-agent/.codex/auth.json")
    target=WORKER_ROOT/"codex-home/auth.json"
    if target.exists():return
    if not source.exists():return
    account=pwd.getpwnam("loop-oh-agent")
    temporary=target.with_name(".auth.json."+str(os.getpid())+".tmp")
    try:
        source_fd=os.open(source,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0));info=os.fstat(source_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=account.pw_uid or stat.S_IMODE(info.st_mode)!=0o600:
            os.close(source_fd);raise RuntimeError("legacy LOOP auth file is untrusted")
        target_fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(source_fd,"rb") as input_handle,os.fdopen(target_fd,"wb") as output:
            shutil.copyfileobj(input_handle,output);output.flush();os.fsync(output.fileno())
        os.chown(temporary,account.pw_uid,account.pw_gid);os.chmod(temporary,0o600);os.replace(temporary,target)
    finally:
        if temporary.exists():temporary.unlink()


def worker_session_key() -> str:
    values={}
    for line in Path("/etc/loop-worker/secrets/openhands.env").read_text().splitlines():
        if "=" in line:
            name,value=line.split("=",1);values[name]=value
    key=values.get("LOCAL_BACKEND_API_KEY","")
    if len(key)<32 or key.strip()!=key:raise RuntimeError("dedicated client key is malformed")
    server=json.loads(Path("/etc/loop-openhands-agent/server-config.private.json").read_text())
    keys=server.get("session_api_keys")
    if not isinstance(keys,list) or len(keys)!=1 or keys[0]!=key:raise RuntimeError("dedicated client/server key contract mismatch")
    return key


def worker_api(method: str,path: str,key: str,body: dict | None = None) -> dict:
    payload=None if body is None else json.dumps(body,separators=(",",":")).encode()
    request=urllib.request.Request("http://127.0.0.1:18002"+path,data=payload,method=method,headers={"X-Session-API-Key":key,"Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)


def wait_worker_api(timeout: float = 30.0) -> None:
    key=worker_session_key();deadline=time.monotonic()+timeout
    while True:
        try:worker_api("GET","/api/agent-profiles",key);return
        except (urllib.error.URLError,ConnectionError,TimeoutError):
            if time.monotonic()>=deadline:raise RuntimeError("dedicated Agent Server API did not become ready") from None
            time.sleep(0.5)


def ensure_worker_profile(*, create: bool) -> dict:
    key=worker_session_key();expected=json.loads((CONF/"openhands-profile.example.json").read_text());name=expected["name"]
    listing=worker_api("GET","/api/agent-profiles",key);previous=listing.get("active_agent_profile_id")
    if create and not isinstance(previous,str):raise RuntimeError("existing active Agent Profile pointer is required for rollback")
    state={"key":key,"created":False,"creation_attempted":False,"previous_active":previous,"profile_id":None,"profile_revision":None}
    try:
        try:detail=worker_api("GET","/api/agent-profiles/"+urllib.parse.quote(name,safe=""),key)
        except urllib.error.HTTPError as error:
            if error.code!=404 or not create:raise RuntimeError("dedicated Agent Profile missing") from error
            state["creation_attempted"]=True
            worker_api("POST","/api/agent-profiles/"+urllib.parse.quote(name,safe=""),key,expected["profile"]);state["created"]=True
            detail=worker_api("GET","/api/agent-profiles/"+urllib.parse.quote(name,safe=""),key)
        profile=detail.get("profile",{})
        if any(profile.get(field)!=value for field,value in expected["profile"].items()):raise RuntimeError("dedicated Agent Profile drift")
        profile_id=profile.get("id")
        if not isinstance(profile_id,str) or not profile_id:raise RuntimeError("dedicated Agent Profile has no stable id")
        revision=profile.get("revision")
        if not isinstance(revision,int) or isinstance(revision,bool) or revision<0:raise RuntimeError("dedicated Agent Profile has no revision")
        state["profile_id"]=profile_id;state["profile_revision"]=revision
        if create and previous!=profile_id:worker_api("POST","/api/agent-profiles/"+urllib.parse.quote(profile_id,safe="")+"/activate",key)
        active=worker_api("GET","/api/agent-profiles",key).get("active_agent_profile_id")
        if active!=profile_id:raise RuntimeError("dedicated Agent Profile is not active")
        return state
    except Exception:
        if create and (state["creation_attempted"] or state.get("profile_id")!=previous):rollback_worker_profile(state)
        raise


def bind_worker_profile(state: dict, *, apply: bool, path: Path = Path("/etc/loop-worker/templates.json")) -> None:
    config=json.loads(path.read_text())
    expected_id=state["profile_id"];expected_revision=state["profile_revision"]
    templates=config.get("templates")
    if not isinstance(templates,dict):raise RuntimeError("worker templates are invalid")
    for template in templates.values():
        if not isinstance(template,dict):raise RuntimeError("worker template is invalid")
        if ("profile_id" in template and template["profile_id"]!=expected_id) or ("profile_revision" in template and template["profile_revision"]!=expected_revision):raise RuntimeError("approved worker template conflicts with live Agent Profile")
        if not apply and (template.get("profile_id")!=expected_id or template.get("profile_revision")!=expected_revision):raise RuntimeError("worker template profile binding drift")
    if not apply:
        if config.get("profile_fedor")!=expected_id or config.get("profile_fedor_revision")!=expected_revision:
            raise RuntimeError("worker template profile binding drift")
        return
    config["profile_fedor"]=expected_id;config["profile_fedor_revision"]=expected_revision
    for template in templates.values():template["profile_id"]=expected_id;template["profile_revision"]=expected_revision
    shared=grp.getgrnam("loop-worker-shared").gr_gid
    with tempfile.NamedTemporaryFile("w",dir=path.parent,delete=False) as output:
        temporary=Path(output.name);json.dump(config,output,sort_keys=True,separators=(",",":"));output.write("\n");output.flush();os.fsync(output.fileno())
    os.chown(temporary,0,shared);os.chmod(temporary,0o640);os.replace(temporary,path)


def rollback_worker_profile(state: dict | None) -> None:
    if not state:return
    key=state["key"]
    if state.get("creation_attempted"):
        try:worker_api("DELETE","/api/agent-profiles/"+WORKER_PROFILE_NAME,key)
        except Exception:pass
    previous=state.get("previous_active")
    if isinstance(previous,str) and previous:
        worker_api("POST","/api/agent-profiles/"+urllib.parse.quote(previous,safe="")+"/activate",key)


def control(apply: bool, drift: list[str], missing: list[str], errors: list[str]) -> list[str]:
    group("loop-tunnel",apply);group("loop-proxy",apply);group("loop-openhands-tunnel",apply)
    user("loop-tunnel","loop-tunnel","/var/lib/loop-tunnel",apply);user("loop-proxy","loop-proxy","/var/lib/loop-proxy",apply);user("loop-openhands-tunnel","loop-openhands-tunnel","/var/lib/loop-openhands-tunnel",apply)
    account_contract(["loop-tunnel","loop-proxy","loop-openhands-tunnel"])
    install_map(CONTROL_FILES,apply,drift);units=install_units(CONTROL_UNITS,apply,drift)
    for path,mode in [("/etc/loop/images.env",0o600),("/etc/loop/paperclip.env",0o600),("/etc/loop/director.env",0o600),("/etc/loop/secrets/backup_encryption",0o600),("/etc/loop-tunnel/known_hosts",0o644),("/etc/loop-openhands-tunnel/known_hosts",0o644)]:private_file(path,mode,missing)
    private_numeric("/etc/loop/bridge.json",0o600,missing,10001);private_numeric("/etc/loop/hermes.yaml",0o600,missing,10000)
    for name in ["bridge_operator","bridge_gateway","bridge_director","bridge_runner","hermes_api","paperclip_board","openhands_api","github_pr","webapp_context"]:private_numeric("/etc/loop/secrets/"+name,0o600,missing,10001)
    private_numeric("/etc/loop/secrets/hermes_bridge_director",0o600,missing,10000)
    private_same_numeric_owner(["/etc/loop/secrets/postgres_admin","/etc/loop/secrets/paperclip_postgres"],0o600,missing)
    if Path("/etc/loop/telegram.json").exists():
        private_numeric("/etc/loop/telegram.json",0o600,missing,10001);private_numeric("/etc/loop/secrets/telegram_bot",0o600,missing,10001)
    private_file("/var/lib/loop-tunnel/id_ed25519",0o600,missing,"loop-tunnel")
    private_file("/var/lib/loop-openhands-tunnel/id_ed25519",0o600,missing,"loop-openhands-tunnel")
    validate_images(Path("/etc/loop/images.env"),missing)
    for program in ["/usr/bin/docker","/usr/bin/tinyproxy","/usr/bin/ssh"]:
        if not Path(program).is_file():missing.append(program)
    if apply:
        for path in [Path("/var/backups/loop"),Path("/var/lib/loop/backups"),Path("/var/lib/loop/health")]:path.mkdir(parents=True,exist_ok=True,mode=0o700);os.chown(path,0,0);os.chmod(path,0o700)
    for path in ["/var/backups/loop","/var/lib/loop/backups","/var/lib/loop/health"]:private_directory(path,0o700,missing,"root")
    if not missing:verify_units(units,errors)
    return ["loop-egress-tunnel.service","loop-egress-proxy.service","loop-openhands-tunnel.service","loop-openhands-relay.service","loop-network-preflight.service","loop-control.service","loop-backup.timer","loop-health.timer"]


def worker(apply: bool, drift: list[str], missing: list[str], errors: list[str]) -> list[str]:
    group("loop-worker-shared",apply);group("loop-worker-runner",apply);group("loop-bundle-collector",apply);group("loop-worker",apply)
    user("loop-worker-runner","loop-worker-runner","/var/lib/loop-worker-runner",apply)
    user("loop-bundle-collector","loop-bundle-collector","/var/lib/loop-bundle-collector",apply)
    user("loop-worker","loop-worker","/var/lib/loop-worker-ssh",apply,"/bin/sh")
    group("loop-oh-agent",apply);user("loop-oh-agent","loop-oh-agent","/var/lib/loop-oh-agent",apply)
    if apply:run(["/usr/sbin/usermod","-a","-G","loop-worker-shared","loop-oh-agent"])
    install_map(WORKER_FILES,apply,drift);units=install_units(WORKER_UNITS,apply,drift)
    ensure_worker_volume(apply,missing)
    if apply and not missing:
        run(["/usr/local/sbin/loop-worker-volume","--mount"]);prepare_worker_directories();migrate_worker_auth()
    account_contract(["loop-worker-runner","loop-bundle-collector","loop-worker","loop-oh-agent"],{"loop-oh-agent":{"loop-worker-shared"}})
    if apply:
        templates=Path("/etc/loop-worker/templates.json");integrity=Path("/etc/loop-worker/source-integrity.json")
        if not templates.exists():install_file(CONF/"worker.templates.example.json",templates,0o640)
        if not integrity.exists():install_file(CONF/"source-integrity.example.json",integrity,0o640)
        shared=grp.getgrnam("loop-worker-shared").gr_gid
        os.chown(templates,0,shared);os.chown(integrity,0,shared)
    for path in ["/etc/loop-worker/templates.json","/etc/loop-worker/source-integrity.json"]:private_file(path,0o640,missing,"root","loop-worker-shared")
    validate_worker_integrity(missing)
    for path,mode,owner in [("/etc/loop-openhands-agent/server-config.private.json",0o600,"root"),("/etc/loop-worker/secrets/openhands.env",0o600,"loop-worker-runner"),("/srv/loop-worker/codex-home/auth.json",0o600,"loop-oh-agent")]:private_file(path,mode,missing,owner)
    auth_path=Path("/srv/loop-worker/codex-home/auth.json")
    if auth_path.is_file() and not auth_path.is_symlink():validate_codex_auth(auth_path,missing)
    for relative,owner,_group_name,mode in WORKER_DIRECTORIES:private_directory(str(WORKER_ROOT/relative),mode,missing,owner)
    private_directory("/var/lib/loop-worker-ssh/.ssh",0o700,missing,"loop-worker")
    private_file("/var/lib/loop-worker-ssh/.ssh/authorized_keys",0o600,missing,"loop-worker")
    for path in ["/srv/loop-worker/trusted-source/proxima-ai/.git","/opt/loop-openhands-agent/venv/bin/python","/opt/loop-openhands-agent/node_modules/.bin/codex-acp","/opt/loop-openhands-agent/node_modules/.bin/codex"]:
        if not Path(path).exists():missing.append(path)
    verify_worker_tool_versions(errors)
    if not missing:verify_codex_login(errors)
    for argv,label in [(["/usr/sbin/visudo","-cf","/etc/sudoers.d/loop-worker"],"sudoers"),(["/usr/sbin/sshd","-t"],"sshd")]:
        if Path(argv[-1]).exists() or label=="sshd":
            if run(argv,check=False).returncode:errors.append(label)
    if not errors:
        effective=run(["/usr/sbin/sshd","-T","-C","user=loop-worker,host=claudette,addr=135.106.211.64"],check=False)
        required=["forcecommand /opt/loop/worker_ssh.py","disableforwarding yes","permittty no","authenticationmethods publickey"]
        if effective.returncode or any(value not in effective.stdout.lower() for value in required):errors.append("sshd-effective")
    if not missing:verify_units(units,errors)
    return ["loop-worker-volume.service","loop-openhands-directories.service","loop-openhands-agent-server.service"]


def runner(apply: bool, drift: list[str], missing: list[str], errors: list[str]) -> list[str]:
    group("loop-runner-tunnel",apply)
    user("loop-runner-tunnel","loop-runner-tunnel","/var/lib/loop-runner-tunnel",apply)
    account_contract(["loop-runner-tunnel"])
    try:grp.getgrnam("docker")
    except KeyError:missing.append("group:docker")
    try:
        account=pwd.getpwnam("verifier")
        # Preserve Harper's existing verifier login. The unit sets its own HOME
        # and ProtectHome blocks the historical home from the LOOP runtime.
        if account.pw_uid!=1000 or grp.getgrgid(account.pw_gid).gr_name!="verifier" or (account.pw_dir,account.pw_shell) not in {("/var/lib/loop-runner","/usr/sbin/nologin"),("/home/verifier","/bin/bash")}:errors.append("verifier-account")
    except KeyError:
        if apply:
            group("verifier",True);run(["/usr/sbin/useradd","--uid","1000","--create-home","--home-dir","/var/lib/loop-runner","--shell","/usr/sbin/nologin","--gid","verifier","verifier"])
        else:missing.append("user:verifier")
    if apply and "group:docker" not in missing:run(["/usr/sbin/usermod","-a","-G","docker","verifier"])
    if "verifier-account" not in errors and "user:verifier" not in missing and "group:docker" not in missing:account_contract(["verifier"],{"verifier":{"docker"}})
    install_map(RUNNER_FILES,apply,drift);units=install_units(RUNNER_UNITS,apply,drift)
    tunnel_missing=[]
    private_file("/var/lib/loop-runner-tunnel/id_ed25519",0o600,tunnel_missing,"loop-runner-tunnel")
    private_file("/etc/loop-runner-tunnel/known_hosts",0o644,tunnel_missing)
    missing.extend(tunnel_missing)
    if apply and not tunnel_missing and not errors:
        verify_units(units,errors)
        if not errors:
            run(["/usr/bin/systemctl","daemon-reload"])
            run(["/usr/bin/systemctl","enable","--now","loop-runner-bridge-tunnel.service"])
    if apply:
        verifier=pwd.getpwnam("verifier").pw_uid
        for path,mode in [(Path("/var/lib/loop-runner"),0o700),(Path("/srv/loop-runner"),0o700)]:
            path.mkdir(parents=True,exist_ok=True,mode=mode);os.chown(path,verifier,pwd.getpwnam("verifier").pw_gid);os.chmod(path,mode)
    for path in ["/var/lib/loop-runner","/srv/loop-runner"]:private_directory(path,0o700,missing,"verifier")
    private_file("/etc/loop-runner/config.json",0o600,missing,"verifier")
    private_directory("/var/lib/loop-runner/.ssh",0o700,missing,"verifier")
    private_file("/var/lib/loop-runner/.ssh/known_hosts",0o644,missing,"verifier")
    config_path=Path("/etc/loop-runner/config.json")
    if config_path.is_file():
        try:config=json.loads(config_path.read_text())
        except Exception:missing.append(str(config_path)+":invalid")
        else:
            for key in ["trusted_home","work_root","evidence_root"]:
                value=config.get(key);path=Path(value) if isinstance(value,str) else Path()
                if not isinstance(value,str) or not path.is_absolute():missing.append(str(config_path)+":"+key);continue
                if apply:
                    path.mkdir(parents=True,exist_ok=True,mode=0o700);account=pwd.getpwnam("verifier");os.chown(path,account.pw_uid,account.pw_gid);os.chmod(path,0o700)
                private_directory(value,0o700,missing,"verifier")
            for key in ["runner_token_file","worker_identity_file","github_publish_identity_file","known_hosts_file"]:
                value=config.get(key)
                if not isinstance(value,str):missing.append(str(config_path)+":"+key)
                elif key=="known_hosts_file":private_file(value,0o644,missing,"verifier")
                else:private_file(value,0o600,missing,"verifier")
            validate_runner_inputs(config,missing)
            runner_runtime_checks(config,missing)
    for path in ["/srv/loop-runner/source/proxima-ai/.git","/srv/loop-runner/fixtures/wb-api"]:
        if not Path(path).is_dir():missing.append(path)
    if not missing:verify_units(units,errors)
    return RUNNER_UNITS


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--role",choices=["control","worker","runner"],required=True);mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument("--check",action="store_true");mode.add_argument("--apply",action="store_true");args=parser.parse_args()
    if args.apply and os.geteuid()!=0:raise SystemExit("--apply requires root")
    validate_sources(args.role);drift=[];missing=[];errors=[];rollback=None
    unit_names={"control":CONTROL_UNITS,"worker":WORKER_UNITS,"runner":RUNNER_UNITS}[args.role]
    if args.apply:rollback=(snapshot(role_mapping(args.role)),snapshot_units(unit_names))
    profile_rollback=None
    try:
        services=globals()[args.role](args.apply,drift,missing,errors)
        if args.apply:
            run(["/usr/bin/systemctl","daemon-reload"])
            if errors:raise RuntimeError("installed public files failed validation")
            if not missing:
                run(["/usr/bin/systemctl","enable",*services]);run(["/usr/bin/systemctl","restart",*services])
                observed=[name for name in services if name!="loop-network-preflight.service" and run(["/usr/bin/systemctl","is-active","--quiet",name],check=False).returncode!=0]
                if observed:raise RuntimeError("installed service failed runtime activation")
                if args.role=="worker":
                    wait_worker_api()
                    profile_rollback=ensure_worker_profile(create=True)
                    bind_worker_profile(profile_rollback,apply=True)
                    if run(["/usr/local/sbin/loop-worker-verify"],check=False).returncode!=0:raise RuntimeError("native worker boundary verification failed")
        elif args.role=="worker" and not drift and not missing and not errors:
            try:
                wait_worker_api();state=ensure_worker_profile(create=False);bind_worker_profile(state,apply=False)
                if run(["/usr/local/sbin/loop-worker-verify"],check=False).returncode!=0:errors.append("native-worker-boundary")
            except Exception:errors.append("worker-profile")
    except Exception:
        if args.apply and rollback is not None:
            try:rollback_worker_profile(profile_rollback)
            except Exception:pass
            restore_snapshot(rollback[0][1]);run(["/usr/bin/systemctl","daemon-reload"],check=False);restore_units(rollback[1])
        raise
    status="ready" if not missing and not errors and (args.apply or not drift) else ("installed_pending_private_inputs" if args.apply and not errors else "blocked")
    print(json.dumps({"role":args.role,"mode":"apply" if args.apply else "check","status":status,"public_drift":drift,"missing_private_or_runtime":missing,"verification_errors":errors},sort_keys=True))
    if status!="ready" and not (args.apply and status=="installed_pending_private_inputs"):raise SystemExit(1)


if __name__=="__main__":main()
