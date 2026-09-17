import hashlib,json,os,stat,threading
import pytest
from pathlib import Path
from tools.loop.bridge import template_fingerprint
from tools.loop.continuous_queue import digest
from tools.loop.continuous_register import RegisterError,install,prompt_permissions

def item():
    prompt={"goal":"fixture","acceptance":["pass"]}
    template={"base_sha":"a"*40,"prompt_sha256":hashlib.sha256((json.dumps(prompt,sort_keys=True,separators=(",",":"))+"\n").encode()).hexdigest(),"allowed_paths":["services/collector/src/wb/observations.ts"],
      "contract_files":["AGENTS.md"],"profile":"fedor","profile_id":"73bf9c3a-ab69-4b2e-a7f0-e808df8f2614","profile_revision":0}
    name="continuous-fixture"
    return {"id":"fixture","template_name":name,"template_fingerprint":template_fingerprint(name,template),
      "policy_fingerprint":"b"*64,"proposal_fingerprint":"c"*64,"review_fingerprint":"d"*64,
      "template":template,"prompt_contract":prompt}
def files(tmp_path):
    config=tmp_path/"config.json";config.write_text('{"templates":{}}');config.chmod(0o600)
    idle=tmp_path/"idle.json";idle.write_text('{"idle":true}');idle.chmod(0o600)
    prompts=tmp_path/"prompts";prompts.mkdir()
    return config,idle,prompts

def test_register_preserves_inode_and_emits_api_receipt(tmp_path):
    config,idle,prompts=files(tmp_path);inode=config.stat().st_ino
    receipt=install(item(),"bridge",config,prompts,idle,os.getuid())
    assert set(receipt)=={"target","template_fingerprint","policy_fingerprint","installed_sha256"}
    assert config.stat().st_ino==inode and config.stat().st_mode&0o777==0o600
    stored=json.loads(config.read_text())["templates"]["continuous-fixture"]
    assert stored["prompt_file"]==str(prompts/"continuous-fixture.json")
    assert (prompts/"continuous-fixture.json").stat().st_mode&0o777==0o600

def test_register_requires_exact_idle_and_never_overwrites_prompt(tmp_path):
    config,idle,prompts=files(tmp_path);idle.write_text('{"idle":false}')
    with pytest.raises(RegisterError,match="idle"):install(item(),"bridge",config,prompts,idle,os.getuid())
    idle.write_text('{"idle":true}');first=install(item(),"bridge",config,prompts,idle,os.getuid())
    assert install(item(),"bridge",config,prompts,idle,os.getuid())==first
    (prompts/"continuous-fixture.json").write_text("changed")
    with pytest.raises(RegisterError,match="prompt"):install(item(),"bridge",config,prompts,idle,os.getuid())



def test_register_rejects_template_name_path_escape_before_write(tmp_path):
    config,idle,prompts=files(tmp_path);bad=item();bad["template_name"]="../../escape"
    with pytest.raises(RegisterError,match="template name"):install(bad,"bridge",config,prompts,idle,os.getuid())
    assert list(prompts.iterdir())==[]


def test_register_rejects_unfingerprinted_template_authority(tmp_path):
    config,idle,prompts=files(tmp_path);bad=item();bad["template"]["command"]=["/bin/sh"]
    with pytest.raises(RegisterError,match="unapproved fields"):install(bad,"bridge",config,prompts,idle,os.getuid())
    assert list(prompts.iterdir())==[]


def test_prepared_recovery_restores_backup_before_idempotent_retry(tmp_path):
    config,idle,prompts=files(tmp_path);install(item(),"bridge",config,prompts,idle,os.getuid())
    marker=Path(str(config)+".continuous-recovery.json")
    state=json.loads(marker.read_text());state["state"]="prepared";marker.write_text(json.dumps(state));marker.chmod(0o600)
    config.write_text('{"truncated":');config.chmod(0o600)
    receipt=install(item(),"bridge",config,prompts,idle,os.getuid())
    assert receipt["target"]=="bridge"
    assert json.loads(config.read_text())["templates"]["continuous-fixture"]["base_sha"]=="a"*40
    assert json.loads(marker.read_text())["state"]=="committed"


def test_concurrent_additive_registrars_preserve_both_templates(tmp_path):
    config,idle,prompts=files(tmp_path);first=item();second=item();second["id"]="fixture-two";second["template_name"]="continuous-fixture-two"
    second["prompt_contract"]={"goal":"fixture two","acceptance":["pass"]}
    second["template"]={**second["template"],"prompt_sha256":hashlib.sha256((json.dumps(second["prompt_contract"],sort_keys=True,separators=(",",":"))+"\n").encode()).hexdigest()}
    second["template_fingerprint"]=template_fingerprint(second["template_name"],second["template"])
    errors=[]
    def worker(value):
        try:install(value,"bridge",config,prompts,idle,os.getuid())
        except Exception as error:errors.append(error)
    threads=[threading.Thread(target=worker,args=(value,)) for value in (first,second)]
    for thread in threads:thread.start()
    for thread in threads:thread.join()
    assert errors==[]
    assert set(json.loads(config.read_text())["templates"])=={"continuous-fixture","continuous-fixture-two"}


def test_worker_prompt_permissions_are_fixed_to_shared_group(monkeypatch):
    class Group:gr_gid=4321
    monkeypatch.setattr("tools.loop.continuous_register.grp.getgrnam",lambda name: Group() if name=="loop-worker-shared" else None)
    assert prompt_permissions("worker",9999)==(0,4321,0o640)
    assert prompt_permissions("harper",1000)==(1000,-1,0o600)

@pytest.mark.skipif(os.geteuid()!=0,reason="requires root chown to fixed worker identity")
def test_worker_prompt_is_group_readable_and_seal_compatible(tmp_path,monkeypatch):
    config,idle,prompts=files(tmp_path)
    class Group:gr_gid=os.getgid()
    monkeypatch.setattr("tools.loop.continuous_register.grp.getgrnam",lambda name: Group())
    install(item(),"worker",config,prompts,idle,0)
    prompt=prompts/"continuous-fixture.json";info=prompt.stat()
    assert info.st_uid==0 and info.st_gid==os.getgid() and info.st_mode&0o777==0o640
    assert info.st_mode&stat.S_IRGRP and not info.st_mode&stat.S_IWGRP
