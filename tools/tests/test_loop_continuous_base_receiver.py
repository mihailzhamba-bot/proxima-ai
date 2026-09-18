import base64,hashlib,json,os,pwd,stat,subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
import tools.loop.continuous_base_refresh as refresh
from tools.loop.continuous_base_refresh import RefreshError,receiver_advance,recover_pair,regenerate_policy,verify_authority
from tools.loop.continuous_queue import digest
from tools.loop.bridge import template_fingerprint
from tools.tests.test_loop_continuous_queue import policy
from tools.tests.test_loop_continuous_base_refresh import refreshed

def git(repo,*args):
 return subprocess.check_output(["git","-C",str(repo),*args],stderr=subprocess.DEVNULL,text=True).strip()
def repository(tmp_path,non_ff=False):
 source=tmp_path/"source";source.mkdir();git(source,"init","-q");git(source,"config","user.name","Fixture");git(source,"config","user.email","fixture@invalid")
 (source/"db/migrations").mkdir(parents=True);(source/"db/migrations/001_init.sql").write_text("SELECT 1;\n")
 (source/"services/collector/src/wb").mkdir(parents=True);(source/"services/collector/src/wb/observations.ts").write_text("old\n")
 git(source,"add",".");git(source,"commit","-qm","old");old=git(source,"rev-parse","HEAD")
 if non_ff:git(source,"checkout","--orphan","other");subprocess.run(["git","-C",str(source),"rm","-rf","."],capture_output=True);(source/"db/migrations").mkdir(parents=True);(source/"db/migrations/001_init.sql").write_text("SELECT 1;\n");git(source,"add",".")
 else:(source/"services/collector/src/wb/observations.ts").write_text("new\n");git(source,"add",".")
 git(source,"commit","-qm","new");new=git(source,"rev-parse","HEAD");ref="refs/loop/base-refresh/"+new;git(source,"update-ref",ref,new)
 bundle=tmp_path/"refresh.bundle";subprocess.run(["git","-C",str(source),"bundle","create",str(bundle),ref,"^"+old],check=True,capture_output=True)
 receiver=tmp_path/"receiver";receiver.mkdir();git(receiver,"init","-q");subprocess.run(["git","-C",str(receiver),"fetch",str(source),old],check=True,capture_output=True)
 return source,receiver,old,new,bundle
def pair_files(tmp_path,old_policy):
 policy_path=tmp_path/"policy.json";policy_path.write_text(json.dumps(old_policy));policy_path.chmod(0o600)
 config=tmp_path/"runner.json";prompt_root=tmp_path/"prompts";prompt_root.mkdir()
 template={"base_sha":next(iter(old_policy["requirements"].values()))["base_sha"],"prompt_sha256":"1"*64,"allowed_paths":["x"],"contract_files":[],"profile":"fedor","profile_id":"73bf9c3a-ab69-4b2e-a7f0-e808df8f2614","profile_revision":0,"prompt_file":str(prompt_root/"continuous-fixture.json")}
 (prompt_root/"continuous-fixture.json").write_text("old prompt");(prompt_root/"continuous-fixture.json").chmod(0o600)
 config.write_text(json.dumps({"templates":{"continuous-fixture":template}}));config.chmod(0o600)
 receiver=tmp_path/"receiver.json";receiver.write_text(json.dumps({"role":"harper","policy_fingerprint":digest(old_policy),"policy_file":str(policy_path),"lock_file":"/etc/loop-continuous/receiver.lock"}));receiver.chmod(0o600)
 return {"config":str(config),"owner":os.getuid(),"prompts":str(prompt_root),"policy":str(policy_path),"receiver":str(receiver),"journal":str(tmp_path/"journal.json"),"manifest_root":str(tmp_path/"manifests"),"reload_receipt":str(tmp_path/"reload.json"),"reload_ack":str(tmp_path/"ack.json")}
def portable_owners(monkeypatch,tmp_path):
 monkeypatch.setattr(refresh,"ROOT_UID",os.getuid());monkeypatch.setattr(refresh,"RECEIVER_STATE_ROOT",tmp_path/"receiver-state")
 original_regular=refresh.regular;original_atomic=refresh.atomic_owned
 monkeypatch.setattr(refresh,"regular",lambda path,owner,*args:original_regular(path,os.getuid() if owner==0 else owner,*args))
 monkeypatch.setattr(refresh,"atomic_owned",lambda path,data,owner,*args:original_atomic(path,data,os.getuid() if owner==0 else owner,*args))
 monkeypatch.setattr(refresh.pwd,"getpwnam",lambda _name:SimpleNamespace(pw_uid=os.getuid(),pw_gid=os.getgid()))
 monkeypatch.setattr(refresh,"wait_reload_ack",lambda settings,expected:refresh.atomic_owned(settings["reload_ack"],(json.dumps(expected)+"\n").encode(),os.getuid()))
def execute_as_current(seen):
 def execute(argv,**kwargs):
  if argv[:3]==["/usr/sbin/runuser","-u","verifier"]:
   command=argv[4:]
   if "bundle" in command and "verify" in command:
    info=Path(command[-1]).stat();seen.append((info.st_uid,stat.S_IMODE(info.st_mode)))
   return subprocess.run(command,**kwargs)
  return subprocess.run(argv,**kwargs)
 return execute
def request(old_policy,new_policy,new,bundle,merge_commits=None):
 raw=bundle.read_bytes();manifest={"001_init.sql":hashlib.sha256(b"SELECT 1;\n").hexdigest()}
 return {"action":"advance_base","target":"harper","maintenance_key":"base-refresh-"+new[:12],
  "expected_old_policy_fingerprint":digest(old_policy),"new_policy":new_policy,"new_head":new,
  "bundle_sha256":hashlib.sha256(raw).hexdigest(),"bundle_b64":base64.b64encode(raw).decode(),
  "merge_commits":merge_commits or [],"migration_manifest":manifest,"rebase_templates":["continuous-fixture"]}
def test_receiver_imports_bundle_as_fixed_user_updates_pair_and_is_idempotent(tmp_path,monkeypatch):
 source,repo,old,new,bundle=repository(tmp_path);old_policy=policy();old_policy["requirements"]["wb-task"]["base_sha"]=old
 new_policy=regenerate_policy(old_policy,new,source);settings=pair_files(tmp_path,old_policy);portable_owners(monkeypatch,tmp_path)
 monkeypatch.setattr(refresh,"RECEIVER_GIT",{"harper":("verifier",str(repo))});monkeypatch.setattr(refresh,"receiver_settings",lambda role,policy_file,receiver_config:settings)
 seen=[];payload=request(old_policy,new_policy,new,bundle,[old])
 config_before=Path(settings["config"]).stat()
 receipt=receiver_advance("harper",payload,settings["policy"],settings["receiver"],execute_as_current(seen))
 assert receipt["new_policy_fingerprint"]==digest(new_policy) and seen==[(os.getuid(),0o600)]
 assert json.loads(Path(settings["policy"]).read_text())==new_policy
 assert json.loads(Path(settings["config"]).read_text())["templates"]=={}
 config_after=Path(settings["config"]).stat()
 assert (config_after.st_ino,config_after.st_uid,config_after.st_gid,stat.S_IMODE(config_after.st_mode))==(config_before.st_ino,config_before.st_uid,config_before.st_gid,stat.S_IMODE(config_before.st_mode))
 assert json.loads(Path(settings["receiver"]).read_text())["policy_fingerprint"]==digest(new_policy)
 assert not (Path(settings["prompts"])/"continuous-fixture.json").exists()
 assert (Path(settings["prompts"])/("continuous-fixture.json."+digest(old_policy)+".history")).exists()
 assert (Path(settings["manifest_root"])/(new+".json")).is_file()
 assert json.loads(Path(settings["reload_receipt"]).read_text())["new_policy_fingerprint"]==digest(new_policy)
 assert receiver_advance("harper",payload,settings["policy"],settings["receiver"],execute_as_current(seen))==receipt
def test_receiver_rejects_non_fast_forward_and_dependency_not_in_head(tmp_path,monkeypatch):
 source,repo,old,new,bundle=repository(tmp_path,non_ff=True);old_policy=policy();old_policy["requirements"]["wb-task"]["base_sha"]=old
 new_policy=refreshed(old_policy,new);settings=pair_files(tmp_path,old_policy);portable_owners(monkeypatch,tmp_path)
 monkeypatch.setattr(refresh,"RECEIVER_GIT",{"harper":("verifier",str(repo))});monkeypatch.setattr(refresh,"receiver_settings",lambda role,policy_file,receiver_config:settings)
 with pytest.raises(RefreshError,match="ancestry"):receiver_advance("harper",request(old_policy,new_policy,new,bundle,[old]),settings["policy"],settings["receiver"],execute_as_current([]))
def test_malformed_oversize_bundle_and_authority_change_fail_closed(tmp_path,monkeypatch):
 old=policy();new=refreshed(old);changed=json.loads(json.dumps(new));changed["requirements"]["wb-task"]["objective"]="expanded"
 with pytest.raises(RefreshError,match="authority"):verify_authority(old,changed)
 payload={"action":"advance_base","target":"bridge","maintenance_key":"base-refresh-999999999999","expected_old_policy_fingerprint":digest(old),
  "new_policy":new,"new_head":"9"*40,"bundle_sha256":"0"*64,"bundle_b64":"%%%","merge_commits":[],"migration_manifest":{},"rebase_templates":[]}
 with pytest.raises(RefreshError,match="malformed"):receiver_advance("bridge",payload,tmp_path/"policy",tmp_path/"receiver")
 monkeypatch.setattr(refresh,"MAX_BUNDLE",16);raw=b"x"*17;payload.update(bundle_b64=base64.b64encode(raw).decode(),bundle_sha256=hashlib.sha256(raw).hexdigest())
 with pytest.raises(RefreshError,match="size"):receiver_advance("bridge",payload,tmp_path/"policy",tmp_path/"receiver")
def test_prepared_pair_journal_restores_policy_config_receiver_and_prompt(tmp_path,monkeypatch):
 old=policy();settings=pair_files(tmp_path,old);portable_owners(monkeypatch,tmp_path)
 originals={key:Path(settings[key]).read_bytes() for key in ("policy","config","receiver")}
 for key,owner in (("policy",0),("config",os.getuid()),("receiver",0)):
  refresh.atomic_owned(Path(settings[key]+".base-refresh-backup"),originals[key],os.getuid())
 prompt=Path(settings["prompts"])/"continuous-fixture.json";raw_prompt=prompt.read_bytes();history=prompt.with_suffix(".history")
 refresh.atomic_owned(history,raw_prompt,os.getuid(),0o640,os.getgid());prompt.unlink()
 record={"original":str(prompt),"history":str(history),"sha256":hashlib.sha256(raw_prompt).hexdigest(),"uid":os.getuid(),"gid":os.getgid(),"mode":0o640}
 state={"state":"prepared",**{key+"_sha256":hashlib.sha256(value).hexdigest() for key,value in originals.items()},"prompts":[record]}
 refresh.atomic_owned(settings["journal"],(json.dumps(state)+"\n").encode(),os.getuid())
 for key in originals:Path(settings[key]).write_text("{")
 recover_pair(settings)
 assert all(Path(settings[key]).read_bytes()==value for key,value in originals.items())
 assert prompt.read_bytes()==raw_prompt and prompt.stat().st_mode&0o777==0o640 and prompt.stat().st_gid==os.getgid()
 assert json.loads(Path(settings["journal"]).read_text())["state"]=="recovered"

def test_receiver_rejects_prerequisite_merge_not_in_new_head(tmp_path,monkeypatch):
 source,repo,old,new,bundle=repository(tmp_path);old_policy=policy();old_policy["requirements"]["wb-task"]["base_sha"]=old
 new_policy=regenerate_policy(old_policy,new,source);settings=pair_files(tmp_path,old_policy);portable_owners(monkeypatch,tmp_path)
 monkeypatch.setattr(refresh,"RECEIVER_GIT",{"harper":("verifier",str(repo))});monkeypatch.setattr(refresh,"receiver_settings",lambda role,policy_file,receiver_config:settings)
 payload=request(old_policy,new_policy,new,bundle,["c"*40])
 with pytest.raises(RefreshError,match="ancestry"):receiver_advance("harper",payload,settings["policy"],settings["receiver"],execute_as_current([]))
