"""Real process crash regression for the spawn -> durable child identity window."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.loop.publication import recover_push,write_journal,process_identity,process_scope_running
from tools.loop.runner import DeliveryRunner
from tools.tests.test_loop_publication import admitted
from tools.tests.test_loop_runner import Client

class ReceiptClient:
    def __init__(self):self.calls=[]
    def call(self,*args):self.calls.append(args);return {"process_stopped":True}

def alive(pid):
    try:os.kill(pid,0)
    except ProcessLookupError:return False
    except PermissionError:
        result=subprocess.run(["ps","-p",str(pid),"-o","stat="],capture_output=True,text=True)
        return bool(result.stdout.strip()) and not result.stdout.strip().startswith("Z")
    stat=Path(f"/proc/{pid}/stat")
    if stat.is_file():
        try:return stat.read_text().rsplit(")",1)[1].split()[0]!="Z"
        except FileNotFoundError:return False
    return True


def test_parent_crash_before_child_journal_cannot_release_delayed_command(tmp_path):
    evidence=tmp_path/"evidence";evidence.mkdir(mode=0o700)
    witness=tmp_path/"child-pid";effect=tmp_path/"late-effect"
    command="import time;from pathlib import Path;time.sleep(0.2);Path("+repr(str(effect))+").write_text('unsafe late effect')"
    source=f"""
import os,sys
from pathlib import Path
sys.path.insert(0,{str(ROOT)!r})
from tools.loop.runner import DeliveryRunner
parent=os.getpid()
def identity(pid):
    if pid!=parent:
        Path({str(witness)!r}).write_text(str(pid))
        os._exit(77)
    return 'fixture-parent'
class Client:
    def call(self,*args):return {{}}
runner=DeliveryRunner({{'trusted_home':{str(tmp_path)!r}}},Client(),identity_reader=identity)
runner.evidence=Path({str(evidence)!r})
runner.push('fixture-job',{{'permit':'fixture-permit','sha':'a'*40}},[sys.executable,'-c',{command!r}])
"""
    parent=subprocess.Popen([sys.executable,"-c",source],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    stdout,stderr=parent.communicate(timeout=10)
    assert parent.returncode==77,(stdout,stderr)
    child=int(witness.read_text())
    try:
        journal=json.loads((evidence/"publisher.json").read_text())
        assert journal["child_pid"] is None and journal["exec_gate"]=="pipe-v1" and journal["exec_released"] is False
        client=ReceiptClient()
        recover_push(client,evidence/"publisher.json",evidence,lambda pid:'fixture-parent' if alive(pid) else None)
        assert client.calls[0][-1]["process_stopped"] is True
        deadline=time.monotonic()+4
        while alive(child) and time.monotonic()<deadline:time.sleep(0.01)
        assert not alive(child),"gated child must exit on parent pipe EOF"
        assert not effect.exists(),"no target exec or delayed side effect is allowed"
    finally:
        if alive(child):os.kill(child,signal.SIGKILL)

@pytest.mark.parametrize("extra",[{}, {"exec_gate":"pipe-v1","exec_released":True}])
def test_missing_child_identity_without_no_exec_proof_stays_unknown(tmp_path,extra):
    path=tmp_path/"publisher.json"
    write_journal(path,{"job_id":"fixture-job","permit":"fixture-permit","publisher_id":"fixture-publisher","state":"running","parent_pid":123,"parent_identity":"fixture-parent","child_pid":None,"child_identity":None,**extra})
    client=ReceiptClient()
    with pytest.raises(ValueError,match="no-exec guarantee"):recover_push(client,path,tmp_path,lambda pid:None)
    assert client.calls==[]


def test_real_command_observes_durable_identity_before_exec(tmp_path):
    b,_,_,_,_,permit,_=admitted(tmp_path)
    runner=DeliveryRunner({"trusted_home":str(tmp_path)},Client(b),identity_reader=lambda pid:"fixture-identity",scope_reader=lambda journal:False)
    runner.evidence=tmp_path/"evidence";runner.evidence.mkdir(mode=0o700)
    observed=tmp_path/"observed.json";journal=runner.evidence/"publisher.json"
    command="import json,os;from pathlib import Path;j=json.loads(Path("+repr(str(journal))+").read_text());Path("+repr(str(observed))+").write_text(json.dumps({'pid':os.getpid(),'child_pid':j['child_pid'],'released':j['exec_released']}))"
    runner.push("job-1",permit,[sys.executable,"-c",command])
    value=json.loads(observed.read_text())
    assert value["pid"]==value["child_pid"] and value["released"] is True
    assert b.job("job-1")["push_outcome"]=="succeeded"


def group_alive(journal):
    return process_scope_running(journal)


@pytest.mark.skipif(not Path("/proc/self/stat").is_file(),reason="native Linux publication-session proof runs on Harper")
@pytest.mark.parametrize("separate_group",[False,True])
def test_live_descendant_blocks_recovery_after_runner_and_leader_die(tmp_path,separate_group):
    evidence=tmp_path/"evidence";evidence.mkdir(mode=0o700)
    descendant_file=tmp_path/"descendant";effect=tmp_path/"late-effect"
    descendant="import time,os;from pathlib import Path;"+("os.setpgid(0,0);" if separate_group else "")+"time.sleep(10);Path("+repr(str(effect))+").write_text('late effect')"
    leader="import os,sys,subprocess;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c',"+repr(descendant)+"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);Path("+repr(str(descendant_file))+").write_text(str(p.pid));os._exit(0)"
    source=f"""
import os,sys,subprocess
from pathlib import Path
sys.path.insert(0,{str(ROOT)!r})
from tools.loop.runner import DeliveryRunner
from tools.loop.publication import process_identity,process_scope_running
identity=process_identity
scope=process_scope_running
class Client:
    def call(self,*args):return {{}}
runner=DeliveryRunner({{'trusted_home':{str(tmp_path)!r}}},Client(),identity_reader=identity,scope_reader=scope)
runner.evidence=Path({str(evidence)!r})
try:runner.push('fixture-job',{{'permit':'fixture-permit','sha':'a'*40}},[sys.executable,'-c',{leader!r}])
except Exception:os._exit(79)
os._exit(80)
"""
    parent=subprocess.Popen([sys.executable,"-c",source],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    stdout,stderr=parent.communicate(timeout=10)
    assert parent.returncode==79,(stdout,stderr)
    journal_path=evidence/"publisher.json";journal=json.loads(journal_path.read_text());child=int(descendant_file.read_text())
    identity=process_identity
    try:
        assert journal["state"]=="running" and journal["exec_released"] is True
        assert journal["child_pgid"]==journal["child_sid"]==journal["child_pid"]
        assert alive(child) and group_alive(journal)
        client=ReceiptClient()
        with pytest.raises(ValueError,match="descendant"):recover_push(client,journal_path,evidence,identity,group_alive)
        assert client.calls==[]
    finally:
        if alive(child):os.kill(child,signal.SIGKILL)
    deadline=time.monotonic()+4
    while group_alive(journal) and time.monotonic()<deadline:time.sleep(0.01)
    assert not group_alive(journal)
    assert not effect.exists()
    recover_push(client,journal_path,evidence,identity,group_alive)
    assert client.calls[0][-1]["process_stopped"] is True
