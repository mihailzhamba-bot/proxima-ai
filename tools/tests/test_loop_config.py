import importlib.util
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sqlite3
ROOT=Path(__file__).resolve().parents[2]
CONF=ROOT/"infra/loop-control"

def test_pinned_adapter_uses_native_api_base_url_and_distinct_secret_mounts():
    adapter=json.loads((CONF/"paperclip-director.example.json").read_text())["adapterConfig"]
    assert adapter["apiBaseUrl"]=="http://bridge:18770/hermes";assert "baseUrl" not in adapter
    compose=json.loads(subprocess.check_output(["node","--input-type=module","-e","import fs from 'node:fs'; import {load} from 'js-yaml'; process.stdout.write(JSON.stringify(load(fs.readFileSync(process.argv[1],'utf8'))));",str(CONF/"compose.yaml")],cwd=ROOT,text=True))
    bridge=compose["services"]["bridge"]["volumes"]
    assert not any("secrets:/run/secrets" in mount for mount in bridge)
    assert not any("telegram_bot" in mount or "postgres_admin" in mount for mount in bridge)
    assert any("webapp_context" in mount for mount in bridge)
    assert any("openhands_relay.py:/opt/loop/openhands_relay.py:ro" in mount for mount in bridge)
    assert set(compose["services"]["bridge"]["networks"])=={"control","hermes_private","openhands_private"}
    assert compose["services"]["hermes"]["networks"]["hermes_private"]["ipv4_address"]=="172.30.240.2"
    assert compose["services"]["hermes"]["environment"]["HTTPS_PROXY"]=="http://172.30.240.1:18180"
    assert "bridge" in compose["services"]["hermes"]["environment"]["NO_PROXY"]
    assert compose["services"]["postgres"]["networks"]==["control"]
    assert compose["networks"]["hermes_private"]["external"] is True
    assert compose["networks"]["openhands_private"]["external"] is True
    hermes=compose["services"]["hermes"]["volumes"]
    assert any("hermes_bridge_director:/run/secrets/bridge_director" in mount for mount in hermes)
    assert compose["services"]["paperclip"]["environment"]["PAPERCLIP_CONFIG"].startswith("/paperclip/")

def test_dedicated_hermes_has_python312_and_no_inherited_root_entrypoint():
    docker=(CONF/"Dockerfile.hermes-overlay").read_text()
    assert "python:3.12.12" in docker and "USER 10000:10000" in docker and "ENTRYPOINT []" in docker
    assert "--extra sms --extra mcp" in docker
    assert "s6-setuidgid" not in docker
    assert "USER 1000:1000" in (CONF/"Dockerfile.paperclip").read_text()

def test_readiness_rejects_existing_hosts_and_missing_approval():
    spec=importlib.util.spec_from_file_location("loop_ready",CONF/"check_ready.py");module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for ip in ["153.56.134.240","135.106.186.210","135.106.211.64"]:
        result=module.check({"control_vps_ip":ip,"control_vps_approved":True,"approval_ref":"fixture approval"})
        assert "dedicated_control_vps_required" in result["missing"] and result["live_ready"] is False
    assert "explicit_control_vps_approval" in module.check({"control_vps_ip":"192.0.2.1"})["missing"]


def test_dedicated_docker_context_includes_pinned_sources_and_excludes_private_state():
    for name,dockerfile in [("paperclip","Dockerfile.paperclip"),("hermes","Dockerfile.hermes-overlay")]:
        prefix=f"build/upstream/{name}/"
        required=[prefix+name+".py",prefix+"README.md",prefix+"build/generated/source.js",prefix+".loop-source-pin.json",prefix+".env.example"]
        private=[prefix+".git/config",prefix+".env",prefix+".env.local",prefix+"secrets/live.token","infra/jobs.env",".git/config","tools/unrelated.py"]
        if name=="hermes":required += ["tools/loop/bridge.py","tools/loop/director_tool.py"]
        ignore=CONF/(dockerfile+".dockerignore")
        program="import fs from 'node:fs';import ignore from 'ignore';const filter=ignore().add(fs.readFileSync(process.argv[1],'utf8'));const paths=JSON.parse(process.argv[2]);process.stdout.write(JSON.stringify(paths.map(p=>filter.ignores(p))));"
        results=json.loads(subprocess.check_output(["node","--input-type=module","-e",program,str(ignore),json.dumps(required+private)],cwd=ROOT,text=True))
        assert results[:len(required)]==[False]*len(required)
        assert results[len(required):]==[True]*len(private)


def test_backup_fails_closed_and_uses_online_sqlite_backup(tmp_path):
    spec=importlib.util.spec_from_file_location("loop_backup",CONF/"backup.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    try:
        module.copy_component_state("bridge",tmp_path/"missing",tmp_path/"out",{})
    except RuntimeError:
        pass
    else:
        raise AssertionError("mandatory Bridge state must not be optional")
    source=tmp_path/"source";source.mkdir();database=source/"bridge.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE receipt (value TEXT)")
        connection.execute("INSERT INTO receipt VALUES ('ok')")
    inventory={};destination=tmp_path/"destination"
    module.copy_component_state("bridge",source,destination,inventory)
    assert inventory["bridge"]["sqlite_backups"]==["bridge.sqlite"]
    with sqlite3.connect(destination/"bridge.sqlite") as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()==("ok",)
        assert connection.execute("SELECT value FROM receipt").fetchone()==("ok",)
    hostile=tmp_path/"hostile";hostile.mkdir();(hostile/"escape").symlink_to(database)
    try:
        module.copy_component_state("bridge",hostile,tmp_path/"hostile-out",{})
    except RuntimeError as error:
        assert "Symlink" in str(error)
    else:
        raise AssertionError("backup must reject symlinked state")
    source_text=(CONF/"backup.py").read_text()
    assert "postgres_restore_test" in source_text and "--exit-on-error" in source_text
    assert "validate_recovery_sources" in source_text and "recovery_manifest" in source_text


def test_private_tunnel_units_and_health_check_are_fail_closed():
    health=(CONF/"health.py").read_text()
    assert "loop-openhands-tunnel.service" in health
    assert "loop-openhands-relay.service" in health
    assert "X-Session-API-Key" in health
    assert "loop-control-telegram-1" in health and "/getMe" in health and "not_configured" in health
    tunnel=(CONF/"loop-openhands-tunnel.service").read_text()
    assert "-L 172.30.241.1:18001:127.0.0.1:18002" in tunnel
    assert "Restart=always" in tunnel and "StrictHostKeyChecking=yes" in tunnel
    relay=(CONF/"loop-openhands-relay.service").read_text()
    assert "loop-openhands-relay-control stop" in relay
    assert "docker exec loop-control-bridge-1" in relay
    egress_tunnel=(CONF/"loop-egress-tunnel.service").read_text()
    assert "-N -T" in egress_tunnel and "IdentityAgent=none" in egress_tunnel
    assert "loop-egress@153.56.134.240" in egress_tunnel
    egress_proxy=(CONF/"loop-egress-proxy.service").read_text()
    assert "Requires=loop-egress-tunnel.service docker.service" in egress_proxy
    proxy=(CONF/"tinyproxy.conf").read_text()
    assert "Listen 172.30.240.1" in proxy and "Allow 172.30.240.2" in proxy


def test_private_networks_are_exact_and_checked_before_compose():
    spec=importlib.util.spec_from_file_location("loop_networks",CONF/"network_preflight.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.NETWORKS=={
        "loop-hermes-private":{"subnet":"172.30.240.0/24","gateway":"172.30.240.1"},
        "loop-openhands-private":{"subnet":"172.30.241.0/24","gateway":"172.30.241.1"},
    }
    assert module.valid({"Driver":"bridge","Internal":True,"IPAM":{"Config":[{"Subnet":"172.30.241.0/24","Gateway":"172.30.241.1"}]}},module.NETWORKS["loop-openhands-private"])
    assert not module.valid({"Driver":"bridge","Internal":False,"IPAM":{"Config":[{"Subnet":"172.30.241.0/24","Gateway":"172.30.241.1"}]}},module.NETWORKS["loop-openhands-private"])
    control=(CONF/"loop-control.service").read_text()
    compose=json.loads(subprocess.check_output(["node","--input-type=module","-e","import fs from 'node:fs'; import {load} from 'js-yaml'; process.stdout.write(JSON.stringify(load(fs.readFileSync(process.argv[1],'utf8'))));",str(CONF/"compose.yaml")],cwd=ROOT,text=True))
    assert "ExecStartPre=/usr/local/sbin/loop-network-preflight --ensure" in control
    assert "--abort-on-container-exit" in control and "Restart=always" in control
    assert all(service["restart"]=="no" for service in compose["services"].values())
    assert compose["services"]["telegram"]["profiles"]==["telegram"]


def test_health_verifies_current_backup_bytes_hash_and_hmac(tmp_path):
    spec=importlib.util.spec_from_file_location("loop_health",CONF/"health.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/"daily";target=root/"attempt";target.mkdir(parents=True,mode=0o700)
    root.chmod(0o700);target.chmod(0o700)
    key=tmp_path/"backup.key";key.write_bytes(b"fixture-key");key.chmod(0o600)
    encrypted=target/"loop-backup.tar.gz.enc";encrypted.write_bytes(b"encrypted fixture");encrypted.chmod(0o600)
    module.BACKUP_ROOT=root;module.BACKUP_KEY=key
    raw=encrypted.read_bytes()
    receipt={"encrypted_file":str(encrypted),"encrypted_bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"hmac_sha256":hmac.new(key.read_bytes(),raw,hashlib.sha256).hexdigest()}
    assert module.verify_backup_artifact(receipt,os.getuid())
    encrypted.write_bytes(raw+b"corrupt");encrypted.chmod(0o600)
    assert not module.verify_backup_artifact(receipt,os.getuid())


def test_dedicated_openhands_server_cannot_read_existing_proxima_state():
    service=(CONF/"loop-openhands-agent-server.service").read_text()
    assert "User=loop-oh-agent" in service
    assert "127.0.0.1 --port 18002" in service
    assert "HOME=/srv/loop-worker/agent-home" in service
    assert "CODEX_HOME=/srv/loop-worker/codex-home" in service
    assert "OH_PERSISTENCE_DIR=/srv/loop-worker/agent-state/openhands" in service
    assert "TMPDIR=/srv/loop-worker/agent-state/tmp" in service
    assert "InaccessiblePaths=/srv/openhands /srv/proxima-ai /etc/proxima-ai /home/openhands-agent" in service
    assert "/srv/loop-worker/trusted-source" in service and "/srv/loop-worker/runner-state" in service
    assert "ReadWritePaths=/srv/loop-worker/agent-home /srv/loop-worker/agent-state /srv/loop-worker/codex-home /srv/loop-worker/workspaces /srv/loop-worker/worktrees" in service
    assert "SupplementaryGroups=loop-worker-shared" in service
    assert "Requires=dutch-tunnel.service" in service
    assert "Requires=loop-openhands-directories.service" in service
    assert "BindReadOnlyPaths=/etc/loop-openhands-agent/config.toml:/srv/loop-worker/codex-home/config.toml" in service
    assert "/etc/loop-openhands-agent/server-config.private.json" in service
    assert "IPAddressDeny=any" in service and "IPAddressAllow=localhost" in service
    assert "NO_PROXY=localhost,127.0.0.1,::1" in service
    assert "NoNewPrivileges=yes" in service and "CapabilityBoundingSet=\n" in service
    config=json.loads((CONF/"openhands-agent.config.example.json").read_text())
    assert config["max_concurrent_runs"]==1
    assert config["enable_vscode"] is False and config["enable_vnc"] is False
    assert config["preload_tools"] is False
    assert config["telemetry"]["exporter"]=="none"
    profile=json.loads((CONF/"openhands-profile.example.json").read_text())
    assert profile["profile"]["acp_command"]=="/opt/loop-openhands-agent/bin/codex-acp"
    assert profile["profile"]["mcp_server_refs"]==[]
    assert profile["profile"]["acp_model"]=="gpt-5.6-sol"
    assert profile["profile"]["acp_session_mode"]=="agent"
    assert profile["profile"]["acp_args"]==[] and profile["profile"]["acp_startup_timeout"]==90.0 and profile["profile"]["acp_prompt_timeout"]==1800.0
    directories=(CONF/"loop-openhands-directories.service").read_text()
    assert "2750 /srv/loop-worker/agent-state/conversations" in directories
    assert "0700 /srv/loop-worker/codex-home" in directories
    assert "0711 /srv/loop-worker/transfer" in directories
    assert "2770 /srv/loop-worker/workspaces" in directories
    assert "2770 /srv/loop-worker/worktrees" in directories
    assert "CAP_FSETID" in directories and "ExecStartPost=/usr/bin/python3 -I" in directories
    codex=(CONF/"codex-worker.config.toml").read_text()
    assert 'default_permissions = "loop-worker"' in codex and "[permissions.loop-worker.network]" in codex
    assert '":root" = "deny"' in codex and '":workspace_roots"' in codex
    runner=(CONF/"loop-runner.service").read_text()
    assert "ExecStart=/usr/bin/python3 -I /opt/loop/runner.py" in runner


def test_worker_gateway_sources_are_versioned_and_fail_closed():
    for path in ["../../tools/loop/worker_root.py","../../tools/loop/worker_ssh.py","../../tools/loop/worker_collect.py","worker.templates.example.json","source-integrity.example.json","loop-worker-sudoers","openhands_agent_server_launcher.py","codex_acp_clean.py","worker_volume.py","verify_worker_host.py"]:
        assert (CONF/path).is_file()
    config=json.loads((CONF/"worker.templates.example.json").read_text())
    assert config["source_repo"]=="/srv/loop-worker/trusted-source/proxima-ai"
    assert config["runtime_user"]=="loop-worker-runner"
    assert config["templates"]=={}
    integrity=json.loads((CONF/"source-integrity.example.json").read_text())
    assert integrity["files"]=={} and integrity["status"].startswith("BLOCKED_")
    sshd=(CONF/"97-loop-worker-sshd.conf").read_text()
    assert "AllowUsers loop-worker@135.106.211.64" in sshd
    assert "ForceCommand /opt/loop/worker_ssh.py" in sshd
    assert "DisableForwarding yes" in sshd and "PermitTTY no" in sshd
    assert "PermitUserEnvironment" not in sshd
