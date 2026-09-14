import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import urllib.error

import pytest


ROOT=Path(__file__).resolve().parents[2]
INSTALL=ROOT/"infra/loop-control/install.py"


def load():
    spec=importlib.util.spec_from_file_location("loop_install",INSTALL)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_installer_declares_all_three_roles_and_critical_runtime_files() -> None:
    result=subprocess.run([sys.executable,"-I",str(INSTALL),"--help"],capture_output=True,text=True,check=True)
    assert "control" in result.stdout and "worker" in result.stdout and "runner" in result.stdout
    module=load()
    targets={str(target) for target,_mode in [*module.CONTROL_FILES.values(),*module.WORKER_FILES.values(),*module.RUNNER_FILES.values()]}
    for required in ["/usr/local/sbin/loop-network-preflight","/usr/local/sbin/loop-worker-volume","/usr/local/sbin/loop-worker-verify","/usr/local/sbin/loop-worker-seal","/opt/loop/worker_root.py","/opt/loop/worker_collect.py","/opt/loop/history_gate.py","/opt/loop/secret_scan.py","/opt/loop/loopctl.py"]:
        assert required in targets


def test_public_file_install_is_idempotent_and_detects_drift(tmp_path: Path,monkeypatch) -> None:
    module=load();monkeypatch.setattr(module,"INSTALL_UID",os.getuid());monkeypatch.setattr(module,"INSTALL_GID",os.getgid())
    source=tmp_path/"source";source.write_text("v1\n");target=tmp_path/"installed";mapping={source:(target,0o640)}
    drift=[];module.install_map(mapping,True,drift)
    assert drift==[str(target)] and target.read_text()=="v1\n"
    drift=[];module.install_map(mapping,False,drift);assert drift==[]
    source.write_text("v2\n");drift=[];module.install_map(mapping,False,drift);assert drift==[str(target)]
    module.install_map(mapping,True,drift);assert target.read_text()=="v2\n"


def test_digest_pin_check_fails_closed(tmp_path: Path) -> None:
    module=load();path=tmp_path/"images.env";path.write_text("LOOP_POSTGRES_IMAGE=postgres:16\n")
    missing=[];module.validate_images(path,missing);assert missing==[str(path)+":digest-pins"]
    path.write_text("\n".join(f"{name}=fixture@sha256:abc" for name in ["LOOP_POSTGRES_IMAGE","LOOP_PAPERCLIP_IMAGE","LOOP_HERMES_IMAGE","LOOP_BRIDGE_IMAGE"]))
    missing=[];module.validate_images(path,missing);assert missing==[str(path)+":digest-pins"]
    digest="a"*64
    path.write_text("\n".join(f"{name}=fixture@sha256:{digest}" for name in ["LOOP_POSTGRES_IMAGE","LOOP_PAPERCLIP_IMAGE","LOOP_HERMES_IMAGE","LOOP_BRIDGE_IMAGE"]))
    missing=[];module.validate_images(path,missing);assert missing==[]


def test_mode_600_snapshot_restores_previous_public_file(tmp_path: Path,monkeypatch) -> None:
    module=load();monkeypatch.setattr(module,"INSTALL_UID",os.getuid());monkeypatch.setattr(module,"INSTALL_GID",os.getgid());monkeypatch.setattr(module,"ROLLBACK_ROOT",tmp_path/"rollback");monkeypatch.setattr(module.os,"chown",lambda *_args:None)
    source=tmp_path/"source";source.write_text("new\n");target=tmp_path/"target";target.write_text("old\n");target.chmod(0o640)
    root,manifest=module.snapshot({source:(target,0o640)})
    backups=[path for path in root.iterdir() if path.suffix==".bak"]
    assert len(backups)==1 and backups[0].stat().st_mode&0o777==0o600
    module.install_map({source:(target,0o640)},True,[]);assert target.read_text()=="new\n"
    module.restore_snapshot(manifest);assert target.read_text()=="old\n" and target.stat().st_mode&0o777==0o640


def test_unit_enablement_and_runtime_state_are_restored(monkeypatch) -> None:
    module=load();state={"old.service":{"enabled":True,"active":True},"new.service":{"enabled":False,"active":False}}
    def fake(argv,check=True):
        action=argv[1];name=argv[-1];item=state[name]
        if action=="is-enabled":return SimpleNamespace(returncode=0 if item["enabled"] else 1,stdout="",stderr="")
        if action=="is-active":return SimpleNamespace(returncode=0 if item["active"] else 1,stdout="",stderr="")
        if action in {"enable","disable"}:item["enabled"]=action=="enable"
        if action in {"restart","stop"}:item["active"]=action=="restart"
        return SimpleNamespace(returncode=0,stdout="",stderr="")
    monkeypatch.setattr(module,"run",fake)
    before=module.snapshot_units(list(state));state["old.service"]={"enabled":False,"active":False};state["new.service"]={"enabled":True,"active":True}
    module.restore_units(before);assert state==before


def test_unit_rollback_detects_enablement_restore_failure(monkeypatch) -> None:
    module=load();state={"fixture.service":{"enabled":False,"active":False}}
    def fake(argv,check=True):
        action=argv[1]
        if action=="is-enabled":return SimpleNamespace(returncode=1,stdout="",stderr="")
        if action=="is-active":return SimpleNamespace(returncode=1,stdout="",stderr="")
        return SimpleNamespace(returncode=0,stdout="",stderr="")
    monkeypatch.setattr(module,"run",fake)
    with pytest.raises(RuntimeError,match="restore service state"):
        module.restore_units({"fixture.service":{"enabled":True,"active":False}})


def test_worker_volume_requires_ext4_and_hard_mount_options() -> None:
    path=ROOT/"infra/loop-control/worker_volume.py";spec=importlib.util.spec_from_file_location("loop_worker_volume",path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    loops="/dev/loop7: []: (/var/lib/loop-worker-volume.img)\n"
    module.validate_mount_metadata("/dev/loop7","ext4","rw,nodev,nosuid,noatime",loops)
    for filesystem,options in [("xfs","rw,nodev,nosuid,noatime"),("ext4","rw,nodev,nosuid")]:
        with pytest.raises(RuntimeError,match="filesystem or options"):
            module.validate_mount_metadata("/dev/loop7",filesystem,options,loops)


def test_fresh_worker_profile_is_created_activated_and_bound(tmp_path: Path,monkeypatch) -> None:
    module=load();expected=json.loads((module.CONF/"openhands-profile.example.json").read_text());profile={**expected["profile"],"id":"11111111-1111-4111-8111-111111111111","name":"loop-codex","revision":1}
    state={"exists":False,"active":"old-profile"};calls=[]
    def fake_api(method,path,key,body=None):
        calls.append((method,path,body))
        if method=="GET" and path=="/api/agent-profiles":return {"active_agent_profile_id":state["active"]}
        if method=="GET" and path.endswith("/loop-codex"):
            if not state["exists"]:raise urllib.error.HTTPError(path,404,"missing",{},None)
            return {"name":"loop-codex","profile":profile}
        if method=="POST" and path.endswith("/loop-codex"):
            assert body==expected["profile"];state["exists"]=True;return {"name":"loop-codex"}
        if method=="POST" and path.endswith("/activate"):
            state["active"]=profile["id"];return {"id":profile["id"]}
        raise AssertionError((method,path,body))
    monkeypatch.setattr(module,"worker_session_key",lambda:"k"*48);monkeypatch.setattr(module,"worker_api",fake_api)
    result=module.ensure_worker_profile(create=True)
    assert result["created"] is True and result["profile_id"]==profile["id"] and result["profile_revision"]==1
    config_path=tmp_path/"templates.json";config_path.write_text(json.dumps({"templates":{"kept":{"base_sha":"a"*40}}}));config_path.chmod(0o640)
    monkeypatch.setattr(module.grp,"getgrnam",lambda _name:SimpleNamespace(gr_gid=os.getgid()))
    monkeypatch.setattr(module.os,"chown",lambda *_args:None)
    module.bind_worker_profile(result,apply=True,path=config_path);bound=json.loads(config_path.read_text())
    assert bound["templates"]=={"kept":{"base_sha":"a"*40,"profile_id":profile["id"],"profile_revision":1}} and bound["profile_fedor"]==profile["id"] and bound["profile_fedor_revision"]==1
    assert any(method=="POST" and path.endswith("/activate") for method,path,_body in calls)


def test_worker_profile_binding_rejects_conflicting_approved_template(tmp_path: Path,monkeypatch) -> None:
    module=load();path=tmp_path/"templates.json";path.write_text(json.dumps({"templates":{"task":{"profile_id":"22222222-2222-4222-8222-222222222222","profile_revision":1}}}))
    state={"profile_id":"11111111-1111-4111-8111-111111111111","profile_revision":1}
    with pytest.raises(RuntimeError,match="conflicts"):
        module.bind_worker_profile(state,apply=True,path=path)


def test_shipped_worker_integrity_placeholder_never_reports_ready(tmp_path: Path,monkeypatch) -> None:
    module=load();config=tmp_path/"templates.json";manifest=tmp_path/"source-integrity.json"
    monkeypatch.setattr(module.pwd,"getpwnam",lambda _name:SimpleNamespace(pw_uid=os.getuid()))
    config.write_text(json.dumps({"templates":{}}));manifest.write_text((module.CONF/"source-integrity.example.json").read_text())
    missing=[];module.validate_worker_integrity(missing,config,manifest)
    assert missing==[str(manifest)+":unsealed"]


def test_worker_integrity_seal_transitions_placeholder_to_valid_manifest(tmp_path: Path) -> None:
    installer=load();seal_path=ROOT/"infra/loop-control/seal_worker_integrity.py";spec=importlib.util.spec_from_file_location("loop_worker_seal",seal_path);sealer=importlib.util.module_from_spec(spec);spec.loader.exec_module(sealer)
    prompt_root=tmp_path/"prompts";prompt_root.mkdir();prompt=prompt_root/"task.txt";prompt.write_text("approved prompt\n")
    runtime=tmp_path/"worker.py";runtime.write_text("print('trusted')\n")
    config=tmp_path/"templates.json";config.write_text(json.dumps({"templates":{"task":{"prompt_file":str(prompt)}}}));manifest=tmp_path/"source-integrity.json";manifest.write_text((installer.CONF/"source-integrity.example.json").read_text())
    payload=sealer.seal(config,manifest,{runtime:os.getuid()},prompt_root,os.getgid(),manifest_uid=os.getuid(),prompt_owner=os.getuid(),config_owner=os.getuid())
    assert payload["status"]=="ready" and set(payload["files"])=={str(runtime),str(prompt)}
    missing=[];installer.validate_worker_integrity(missing,config,manifest,{runtime:os.getuid()},os.getuid());assert missing==[]


def test_profile_create_failure_rolls_back_new_name_and_active_pointer(monkeypatch) -> None:
    module=load();calls=[];created=False
    def fake_api(method,path,key,body=None):
        nonlocal created;calls.append((method,path))
        if method=="GET" and path=="/api/agent-profiles":return {"active_agent_profile_id":"old-profile"}
        if method=="GET" and path.endswith("/loop-codex"):
            if not created:raise urllib.error.HTTPError(path,404,"missing",{},None)
            raise RuntimeError("readback failed")
        if method=="POST" and path.endswith("/loop-codex"):created=True;return {}
        if method=="DELETE":created=False;return {}
        if method=="POST" and path.endswith("old-profile/activate"):return {}
        raise AssertionError((method,path))
    monkeypatch.setattr(module,"worker_session_key",lambda:"k"*48);monkeypatch.setattr(module,"worker_api",fake_api)
    with pytest.raises(RuntimeError,match="readback failed"):module.ensure_worker_profile(create=True)
    assert created is False and ("DELETE","/api/agent-profiles/loop-codex") in calls and ("POST","/api/agent-profiles/old-profile/activate") in calls


def test_profile_activate_failure_restores_previous_pointer(monkeypatch) -> None:
    module=load();expected=json.loads((module.CONF/"openhands-profile.example.json").read_text())["profile"];profile={**expected,"id":"11111111-1111-4111-8111-111111111111","revision":1};active="old-profile";failed=False
    def fake_api(method,path,key,body=None):
        nonlocal active,failed
        if method=="GET" and path=="/api/agent-profiles":return {"active_agent_profile_id":active}
        if method=="GET" and path.endswith("/loop-codex"):return {"profile":profile}
        if method=="POST" and path.endswith(profile["id"]+"/activate"):
            active=profile["id"];failed=True;raise RuntimeError("activation response lost")
        if method=="POST" and path.endswith("old-profile/activate"):active="old-profile";return {}
        raise AssertionError((method,path))
    monkeypatch.setattr(module,"worker_session_key",lambda:"k"*48);monkeypatch.setattr(module,"worker_api",fake_api)
    with pytest.raises(RuntimeError,match="activation response lost"):module.ensure_worker_profile(create=True)
    assert failed is True and active=="old-profile"


def test_runner_inputs_require_two_valid_keys_hosts_and_executable_reviewer(tmp_path: Path) -> None:
    module=load();keys=[]
    for name in ["worker","github"]:
        path=tmp_path/name;subprocess.run(["/usr/bin/ssh-keygen","-q","-t","ed25519","-N","","-f",str(path)],check=True);keys.append(path)
    known=tmp_path/"known_hosts";known.write_text("135.106.186.210 "+keys[0].with_suffix(".pub").read_text()+"github.com "+keys[1].with_suffix(".pub").read_text())
    reviewer=tmp_path/"reviewer";reviewer.write_text("#!/bin/sh\nexit 0\n");reviewer.chmod(0o755)
    config={"worker_host":"loop-worker@135.106.186.210","publish_remote":"git@github.com:mihailzhamba-bot/proxima-ai.git","worker_identity_file":str(keys[0]),"github_publish_identity_file":str(keys[1]),"known_hosts_file":str(known),"reviewer_command":[str(reviewer)]}
    missing=[];module.validate_runner_inputs(config,missing,trusted_uid=os.getuid());assert missing==[]
    keys[0].write_text("");missing=[];module.validate_runner_inputs(config,missing,trusted_uid=os.getuid());assert str(keys[0])+":invalid-private-key" in missing


def test_codex_auth_requires_complete_chatgpt_token_set(tmp_path: Path) -> None:
    module=load();path=tmp_path/"auth.json";valid={"auth_mode":"chatgpt","OPENAI_API_KEY":None,"last_refresh":"2026-09-14T00:00:00Z","tokens":{name:name+"-"+"x"*32 for name in ["access_token","account_id","id_token","refresh_token"]}}
    path.write_text(json.dumps(valid));missing=[];module.validate_codex_auth(path,missing);assert missing==[]
    valid["tokens"].pop("refresh_token");path.write_text(json.dumps(valid));module.validate_codex_auth(path,missing);assert missing==[str(path)+":invalid-chatgpt-auth"]


def test_codex_login_accepts_only_exact_status_and_known_path_warning() -> None:
    module=load();warning="WARNING: proceeding, even though we could not create PATH aliases: Operation not permitted (os error 1)"
    assert module.valid_codex_login(SimpleNamespace(returncode=0,stdout="",stderr=warning+"\nLogged in using ChatGPT\n"))
    assert not module.valid_codex_login(SimpleNamespace(returncode=0,stdout="Logged in using ChatGPT\n",stderr="unexpected diagnostic\n"))
