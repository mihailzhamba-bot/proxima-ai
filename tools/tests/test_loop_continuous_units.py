import importlib.util
from pathlib import Path
import pytest
from types import SimpleNamespace
P=Path(__file__).parents[1]/"loop/continuous_acceptance.py"
spec=importlib.util.spec_from_file_location("continuous_acceptance_units",P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_exact_offline_uv_launcher_is_approved():
 assert m.approved_unit_exec(m.UV_EXEC)
 assert m.approved_unit_exec(m.ENV_UV_EXEC)
 assert m.approved_unit_exec(m.MANAGED_ENV_UV_EXEC)
 assert m.MANAGED_ENV_UV_EXEC==["/usr/bin/env","uv","run","--offline","--no-python-downloads","--managed-python","--no-project","--python","3.14","/srv/proxima-ai/repo/tools/wb/daily.py","--config","/etc/proxima-ai/wb-daily.json"]
 assert m.uv_environment_allowed({"Environment":"UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never"})
 assert not m.uv_environment_allowed(["UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never","UV_OFFLINE=0"])
 assert not m.uv_environment_allowed(["UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never",""])
 assert m.uv_environment_allowed(["UV_OFFLINE=1","UV_PYTHON_DOWNLOADS=never","UV_MANAGED_PYTHON=1"],True)
 assert not m.uv_environment_allowed(["UV_OFFLINE=1","UV_PYTHON_DOWNLOADS=never"],True)
 assert not m.uv_environment_allowed(["UV_OFFLINE=1","UV_PYTHON_DOWNLOADS=never","UV_MANAGED_PYTHON=0"],True)
@pytest.mark.parametrize("index,value",[(1,"sync"),(2,"--online"),(3,"--allow-python-downloads"),(4,"--project"),(6,"3.13"),(7,"/tmp/evil.py"),(9,"/tmp/config.json")])
def test_uv_launcher_variants_are_denied(index,value):
 command=list(m.UV_EXEC);command[index]=value;assert not m.approved_unit_exec(command)
@pytest.mark.parametrize("environment",["","UV_OFFLINE=1","UV_PYTHON_DOWNLOADS=never","UV_OFFLINE=0 UV_PYTHON_DOWNLOADS=never","UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=automatic"])
def test_uv_launcher_requires_both_offline_environment_guards(environment):
 assert not m.uv_environment_allowed({"Environment":environment})
def test_existing_direct_python_launcher_remains_allowed():
 assert m.approved_unit_exec(["/usr/bin/python3","/srv/proxima-ai/repo/tools/wb/daily.py","--config","/etc/proxima-ai/wb-daily.json"])


def write_units(tmp_path,exec_start,environment="Environment=UV_OFFLINE=1\nEnvironment=UV_PYTHON_DOWNLOADS=never"):
 root=tmp_path/"checkout";units=root/"infra/systemd";units.mkdir(parents=True)
 (units/"proxima-wb-daily.service").write_text(f"[Unit]\nDescription=fixture\n[Service]\n{environment}\nExecStart={exec_start}\n")
 (units/"proxima-wb-daily.timer").write_text("[Unit]\nDescription=fixture timer\n[Timer]\nOnCalendar=*-*-* 05:30:00 Europe/Moscow\n")
 return root

def test_verify_units_accepts_only_exact_uv_form(monkeypatch,tmp_path):
 monkeypatch.setattr(m.subprocess,"run",lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout=b"",stderr=b""))
 root=write_units(tmp_path," ".join(m.UV_EXEC));m.verify_units(root)
 bad=write_units(tmp_path/"bad"," ".join([*m.UV_EXEC,"--extra"]))
 with pytest.raises(ValueError,match="executable"):m.verify_units(bad)
 env_form=write_units(tmp_path/"env"," ".join(m.ENV_UV_EXEC),"Environment=UV_OFFLINE=1\nEnvironment=UV_PYTHON_DOWNLOADS=never\nEnvironment=UV_MANAGED_PYTHON=1")
 m.verify_units(env_form)
 managed=write_units(tmp_path/"managed"," ".join(m.MANAGED_ENV_UV_EXEC),"Environment=UV_OFFLINE=1\nEnvironment=UV_PYTHON_DOWNLOADS=never\nEnvironment=UV_MANAGED_PYTHON=1")
 m.verify_units(managed)
 managed_missing=write_units(tmp_path/"managed-missing"," ".join(m.MANAGED_ENV_UV_EXEC))
 with pytest.raises(ValueError,match="offline environment"):m.verify_units(managed_missing)
 missing=write_units(tmp_path/"missing"," ".join(m.UV_EXEC),"Environment=UV_OFFLINE=1")
 with pytest.raises(ValueError,match="offline environment"):m.verify_units(missing)
