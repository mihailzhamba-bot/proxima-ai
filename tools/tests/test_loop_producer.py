import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.verify_candidate import produce,VerificationFailure,prepare_environment
import tools.loop.verify_candidate as producer
from tools.loop.runner import DeliveryRunner
from tools.loop.bridge import BridgeError

@pytest.fixture
def project(tmp_path,monkeypatch):
    offline=tmp_path/"offline"
    (offline/"npm").mkdir(parents=True);(offline/"uv").mkdir()
    monkeypatch.setattr(producer,"OFFLINE_ROOT",offline)
    root=tmp_path/"repo";root.mkdir();(root/"source.txt").write_text("verified source")
    subprocess.run(["git","init","-q",str(root)],check=True)
    subprocess.run(["git","-C",str(root),"add","source.txt"],check=True)
    subprocess.run(["git","-C",str(root),"-c","user.name=Fixture","-c","user.email=fixture@example.invalid","commit","-qm","fixture"],check=True)
    sha=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    binaries=tmp_path/"bin";binaries.mkdir()
    code="#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\nassert os.environ.get('CI')=='true'\nassert os.environ.get('NEXT_TELEMETRY_DISABLED')=='1'\nif os.environ.get('MUTATE')=='1':Path('source.txt').write_text('changed')\nprint(os.environ.get('PG_MARKER','pg-roundtrip: PASS'))\nprint('Bearer fixture-sensitive-value',file=sys.stderr)\nsys.exit(int(os.environ.get('EXIT_CODE','0')))\n"
    for name in ["make","npm"]:
        path=binaries/name;path.write_text(code);path.chmod(0o755)
    if sys.version_info[:2]==(3,14):
        (binaries/"python3.14").symlink_to(sys.executable)
    env={"PATH":str(binaries)+os.pathsep+os.environ["PATH"]}
    return root,sha,env

@pytest.mark.parametrize("stage",["verify","build"])
def test_real_producer_success_has_exact_sha_receipt(project,stage):
    root,sha,env=project;r=produce(root,sha,stage,False,{**env,"CI":"false","NEXT_TELEMETRY_DISABLED":"0"})
    assert r["checks"]=={stage:{"sha":sha,"status":"pass","skipped":0}}
    assert "fixture-sensitive-value" not in json.dumps(r)

@pytest.mark.parametrize("stage,settings",[("verify",{"EXIT_CODE":"2"}),("build",{"EXIT_CODE":"3"}),("verify",{"PG_MARKER":"no database check"}),("verify",{"PG_MARKER":"pg-roundtrip: SKIP"}),("verify",{"PG_MARKER":"pg-roundtrip: PASS\npg-roundtrip: SKIP"}),("verify",{"MUTATE":"1"})])
def test_real_producer_failure_preserves_sanitized_logs(project,stage,settings):
    root,sha,env=project
    with pytest.raises(VerificationFailure) as error:produce(root,sha,stage,False,{**env,**settings})
    assert error.value.receipt["status"]=="fail";assert error.value.receipt["checks"]=={}
    assert stage in error.value.receipt["logs"]
    assert "fixture-sensitive-value" not in json.dumps(error.value.receipt)

def test_producer_rejects_wrong_sha_and_writable_production_inputs(project):
    root,sha,env=project
    with pytest.raises(VerificationFailure):produce(root,"a"*40,"verify",False,env)
    with pytest.raises(VerificationFailure,match="verification failed"):produce(root,sha,"verify",True,env)

def test_runner_retains_failed_subprocess_logs_outside_candidate(tmp_path):
    runner=DeliveryRunner({"trusted_home":str(tmp_path)},object());runner.evidence=tmp_path/"evidence";runner.evidence.mkdir()
    with pytest.raises(BridgeError):runner._execute([sys.executable,"-c","import sys;print('stage stdout');print('Bearer fixture-private',file=sys.stderr);sys.exit(7)"])
    log=(runner.evidence/"stage-01.log").read_text();assert "stage stdout" in log;assert "fixture-private" not in log
    assert json.loads((runner.evidence/"stage-01.json").read_text())["returncode"]==7


def test_cache_preparation_is_writable_local_and_strictly_offline(tmp_path):
    source=tmp_path/"offline"; (source/"npm").mkdir(parents=True);(source/"uv").mkdir()
    (source/"npm"/"fixture").write_text("npm source");(source/"uv"/"fixture").write_text("uv source")
    result=prepare_environment({"PATH":os.environ["PATH"]},source,tmp_path)
    assert result["NPM_CONFIG_OFFLINE"]=="true" and result["UV_OFFLINE"]=="1" and result["UV_PYTHON_DOWNLOADS"]=="never"
    assert Path(result["HOME"]).is_dir()
    copied=Path(result["npm_config_cache"])/"fixture";copied.write_text("changed copy")
    assert (source/"npm"/"fixture").read_text()=="npm source"
    assert Path(result["UV_CACHE_DIR"]).parent!=source
    with pytest.raises(ValueError,match="offline"):prepare_environment({"PATH":os.environ["PATH"]},tmp_path/"missing",tmp_path)
