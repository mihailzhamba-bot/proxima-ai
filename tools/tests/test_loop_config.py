import importlib.util
import json
from pathlib import Path
import subprocess
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
