import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


ROOT=Path(__file__).resolve().parents[2]
LAUNCHER=ROOT/"infra/loop-control/openhands_agent_server_launcher.py"
CLEAN=ROOT/"infra/loop-control/codex_acp_clean.py"


def load(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_acp_environment_is_allowlisted() -> None:
    module=load(CLEAN,"loop_acp_clean")
    environment=module.clean_environment({
        "HOME":"/fixture/home","CODEX_HOME":"/fixture/codex","HTTPS_PROXY":"http://127.0.0.1:1081",
        "OH_SESSION_API_KEYS_0":"must-not-pass","OH_SECRET_KEY":"must-not-pass","SESSION_API_KEY":"must-not-pass",
        "OPENAI_API_KEY":"must-not-pass","UNRELATED":"must-not-pass",
    })
    assert environment["HOME"]=="/fixture/home" and environment["CODEX_HOME"]=="/fixture/codex"
    assert environment["HTTPS_PROXY"]=="http://127.0.0.1:1081"
    for name in ["OH_SESSION_API_KEYS_0","OH_SECRET_KEY","SESSION_API_KEY","OPENAI_API_KEY","UNRELATED"]:
        assert name not in environment
    assert environment["GIT_CONFIG_GLOBAL"]=="/etc/loop-openhands-agent/gitconfig"


@pytest.mark.skipif(sys.platform!="linux",reason="Linux prctl acceptance runs on Harper")
def test_launcher_reads_bounded_private_fd_closes_stdin_and_disables_dumping(tmp_path: Path) -> None:
    private=tmp_path/"private.json";private.write_text(json.dumps({"fixture":True}));private.chmod(0o600)
    program=f"""
import ctypes,importlib.util,json,os
spec=importlib.util.spec_from_file_location('launcher',{str(LAUNCHER)!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.disable_process_inspection()
raw=m.read_private_config(expected_uid=os.getuid())
print(json.dumps({{'payload':json.loads(raw),'dumpable':ctypes.CDLL(None).prctl(m.PR_GET_DUMPABLE,0,0,0,0),'stdin_size':os.fstat(0).st_size}}))
"""
    with private.open("rb") as source:
        result=subprocess.run([sys.executable,"-I","-c",program],stdin=source,capture_output=True,text=True,check=True)
    observed=json.loads(result.stdout)
    assert observed=={"payload":{"fixture":True},"dumpable":0,"stdin_size":0}


def test_unit_uses_root_opened_stdin_and_isolated_launcher() -> None:
    unit=(ROOT/"infra/loop-control/loop-openhands-agent-server.service").read_text()
    assert "StandardInput=file:/etc/loop-openhands-agent/server-config.private.json" in unit
    assert "venv/bin/python -I /opt/loop-openhands-agent/agent_server_launcher.py" in unit
    assert "LimitCORE=0" in unit
    assert "EnvironmentFile=" not in unit and "ExecStartPre=" not in unit
