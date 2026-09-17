#!/usr/bin/python3 -I
"""Trusted monotonic base refresh coordinator and fixed-role receiver."""
from __future__ import annotations
import base64,contextlib,fcntl,hashlib,json,os,pwd,re,signal,stat,subprocess,tempfile,threading,time
from pathlib import Path
try:
    from .continuous_queue import canonical,digest,policy_authority,validate_policy
    from .continuous_register import atomic_owned,regular
    from .bridge import template_fingerprint
except ImportError:
    from continuous_queue import canonical,digest,policy_authority,validate_policy
    from continuous_register import atomic_owned,regular
    from bridge import template_fingerprint
REPOSITORY="mihailzhamba-bot/proxima-ai";BRANCH="feat/loop-pilot";SHA=re.compile(r"^[0-9a-f]{40}$");DIGEST=re.compile(r"^[0-9a-f]{64}$")
MAX_BUNDLE=32*1024*1024;MAX_EVIDENCE=12;MAX_BLOB=64*1024
ROOT_UID=0;RECEIVER_STATE_ROOT=Path("/var/lib/loop-continuous");CONTROL_GIT_COMMON_DIR=Path("/srv/loop/source/proxima-ai.git")
TOOLCHAIN={"package.json","package-lock.json","services/collector/package.json","services/webapp/package.json","services/control-plane/pyproject.toml","services/control-plane/uv.lock","infra/loop-control/Dockerfile.verification"}
RECEIVER_GIT={"harper":("verifier","/srv/loop-runner/source/proxima-ai"),"worker":("loop-worker-runner","/srv/loop-worker/trusted-source/proxima-ai")}
class RefreshError(ValueError):pass
def write_in_place(path,data,owner):
    path=Path(path);info=regular(path,owner);fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX);os.lseek(fd,0,os.SEEK_SET)
        view=memoryview(data)
        while view:
            written=os.write(fd,view)
            if written<=0:raise RefreshError("short config write")
            view=view[written:]
        os.ftruncate(fd,len(data));os.fsync(fd)
    finally:os.close(fd)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(directory);os.close(directory)
    after=path.stat()
    if after.st_ino!=info.st_ino or after.st_uid!=info.st_uid or after.st_gid!=info.st_gid or stat.S_IMODE(after.st_mode)!=stat.S_IMODE(info.st_mode):raise RefreshError("config inode or ownership changed")
def deadline_call(call,timeout,method,path):
    if threading.current_thread() is not threading.main_thread():raise RefreshError("deadline requires main thread")
    def expired(_signal,_frame):raise TimeoutError("base refresh observation deadline")
    previous=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,timeout)
    try:return call(method,path)
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
def trusted_command(argv,payload,execute=subprocess.run,timeout=600):
    if not isinstance(argv,list) or not argv or not Path(argv[0]).is_absolute():raise RefreshError("invalid base refresh receiver")
    result=execute(argv,input=json.dumps(payload).encode(),capture_output=True,timeout=timeout,check=False)
    if result.returncode or len(result.stdout)>1_000_000:raise RefreshError("base refresh receiver failed")
    try:value=json.loads(result.stdout)
    except Exception:raise RefreshError("invalid base refresh receiver receipt") from None
    if not isinstance(value,dict):raise RefreshError("invalid base refresh receiver receipt")
    return value
def checked(config):
    required={"repository","target_branch","source_repo","policy_file","github_token_file","state_root","max_bundle_bytes","github_timeout_seconds","receivers"}
    if not isinstance(config,dict) or set(config)!=required or config["repository"]!=REPOSITORY or config["target_branch"]!=BRANCH:raise RefreshError("invalid base refresh config")
    for key in ("source_repo","policy_file","github_token_file","state_root"):
        if not isinstance(config[key],str) or not Path(config[key]).is_absolute():raise RefreshError("invalid base refresh path")
    if config["max_bundle_bytes"]!=MAX_BUNDLE or config["github_timeout_seconds"]!=10 or not isinstance(config["receivers"],dict) or set(config["receivers"])!={"bridge","harper","worker"}:raise RefreshError("invalid base refresh bounds")
    for argv in config["receivers"].values():
        if not isinstance(argv,list) or not argv or not Path(argv[0]).is_absolute():raise RefreshError("invalid base refresh receiver")
    return config
def trusted_git_env():
 return {"PATH":"/usr/bin:/bin","HOME":"/var/empty","LANG":"C.UTF-8","LC_ALL":"C.UTF-8","GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_SYSTEM":"/dev/null","GIT_CONFIG_NOSYSTEM":"1","GIT_TERMINAL_PROMPT":"0"}
@contextlib.contextmanager
def trusted_fetch_env(token_file,state_root):
 token=Path(token_file);info=token.lstat()
 if token.is_symlink() or not token.is_file() or info.st_uid!=ROOT_UID or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1:raise RefreshError("untrusted Git credential path")
 root=Path(state_root);directory=Path(tempfile.mkdtemp(prefix="askpass-",dir=root));script=directory/"git-askpass"
 try:
  os.chmod(directory,0o700)
  body=("#!/bin/sh\ncase \"$1\" in\n*Username*) printf '%s\\n' x-access-token;;\n"
        "*Password*) exec /bin/cat "+str(token).replace("'","'\"'\"'").join(("'","'"))+";;\n*) exit 1;;\nesac\n")
  fd=os.open(script,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700)
  try:os.write(fd,body.encode());os.fsync(fd)
  finally:os.close(fd)
  yield {**trusted_git_env(),"GIT_ASKPASS":str(script),"GIT_ASKPASS_REQUIRE":"force"}
 finally:
  try:script.unlink()
  except FileNotFoundError:pass
  directory.rmdir()
def run_git(repo,args,env=None,binary=False,check=True,limit=1_000_000):
    result=subprocess.run(["/usr/bin/git","-c","core.hooksPath=/dev/null","-c","safe.directory=*","-C",str(repo),*args],
        env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=120,check=False)
    if check and result.returncode:raise RefreshError("trusted Git operation failed")
    if len(result.stdout)>limit:raise RefreshError("trusted Git output exceeds bound")
    return result.stdout if binary else result.stdout.decode().strip()
def validate_source_repo(repo):
 source=Path(repo);info=source.lstat()
 if source.is_symlink() or not source.is_dir() or info.st_uid!=ROOT_UID or info.st_mode&0o022:raise RefreshError("untrusted Control source repo")
 if run_git(source,["rev-parse","--is-inside-work-tree"])!="true":raise RefreshError("Control source is not a worktree")
 common=Path(run_git(source,["rev-parse","--path-format=absolute","--git-common-dir"])).resolve()
 git_dir=Path(run_git(source,["rev-parse","--path-format=absolute","--absolute-git-dir"])).resolve()
 expected=CONTROL_GIT_COMMON_DIR.resolve()
 if common!=expected or not (git_dir==expected or expected in git_dir.parents):raise RefreshError("untrusted Control Git common directory")
 return common
def evidence_for(repo,head,paths):
    result=[]
    for path in sorted(set(paths)):
        entry=run_git(repo,["ls-tree",head,"--",path],check=True)
        if not entry:
            raw=b"";summary="Tracked path is absent at the approved base; the bounded task may create it."
            value=hashlib.sha256(b"ABSENT\0"+path.encode()).hexdigest()
        else:
            size=int(run_git(repo,["cat-file","-s",head+":"+path]))
            if size>MAX_BLOB:raise RefreshError("source evidence blob exceeds bound")
            raw=run_git(repo,["show",head+":"+path],binary=True,limit=MAX_BLOB)
            if b"\0" in raw:raise RefreshError("binary source evidence is unsupported")
            try:text=raw.decode("utf-8")
            except UnicodeDecodeError:raise RefreshError("non-UTF8 source evidence is unsupported") from None
            summary=text[:5500] or "Tracked file is empty at the approved base."
            value=hashlib.sha256(raw).hexdigest()
        result.append({"ref":"git:"+head+":"+path,"sha256":value,"summary":summary})
        if len(result)>MAX_EVIDENCE:raise RefreshError("source evidence path bound exceeded")
    return result
def regenerate_policy(policy,new_head,repo):
    value=json.loads(canonical(validate_policy(policy)))
    for requirement in value["requirements"].values():
        paths=[]
        for scope in requirement["path_sets"].values():paths.extend(scope["allowed_paths"])
        requirement["base_sha"]=new_head;requirement["source_evidence"]=evidence_for(repo,new_head,paths)
    validate_policy(value);return value
def migration_manifest(repo,head):
    names=run_git(repo,["ls-tree","-r","--name-only",head,"--","db/migrations"]).splitlines()
    names=[name.split("/",2)[-1] for name in names if name.endswith(".sql")]
    if not names or len(names)>100:raise RefreshError("migration manifest unavailable")
    result={}
    for name in sorted(names):
        object_name=head+":db/migrations/"+name;size=int(run_git(repo,["cat-file","-s",object_name]))
        if size>2_000_000:raise RefreshError("migration exceeds trusted bound")
        result[name]=hashlib.sha256(run_git(repo,["show",object_name],binary=True,limit=2_000_000)).hexdigest()
    return result
def bundle_payload(path):
    raw=Path(path).read_bytes()
    if not raw or len(raw)>MAX_BUNDLE:raise RefreshError("Git bundle exceeds decoded bound")
    return base64.b64encode(raw).decode(),hashlib.sha256(raw).hexdigest()
def verify_authority(old,new):
    if policy_authority(old)!=policy_authority(new):raise RefreshError("base refresh authority changed")
def receiver_settings(role,policy_file,receiver_config):
    base={"bridge":{"config":"/etc/loop/bridge.json","owner":10001,"prompts":"/etc/loop/continuous/prompts"},
          "harper":{"config":"/etc/loop-runner/config.json","owner":1000,"prompts":"/etc/loop-review/continuous/prompts","manifest_root":"/opt/loop-review/continuous/manifests","reload_receipt":"/etc/loop-runner/base-refresh-receipt.json","reload_ack":"/var/lib/loop-runner/base-refresh-ack.json"},
          "worker":{"config":"/etc/loop-worker/templates.json","owner":0,"prompts":"/etc/loop-worker/prompts"}}[role]
    return {**base,"policy":str(policy_file),"receiver":str(receiver_config),"journal":"/etc/loop-continuous/base-refresh-journal.json"}
def recover_pair(settings):
    marker=Path(settings["journal"])
    if not marker.exists():return
    regular(marker,ROOT_UID,100_000);state=json.loads(marker.read_text())
    if state.get("state")!="prepared":return
    for key,owner in (("policy",0),("config",settings["owner"]),("receiver",0)):
        target=Path(settings[key]);backup=Path(str(target)+".base-refresh-backup");regular(backup,owner)
        raw=backup.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=state[key+"_sha256"]:raise RefreshError("base refresh backup mismatch")
        if key=="config":write_in_place(target,raw,owner)
        else:atomic_owned(target,raw,owner,stat.S_IMODE(target.stat().st_mode),target.stat().st_gid)
    for record in state.get("prompts",[]):
        original=Path(record["original"]);history=Path(record["history"]);raw=history.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=record["sha256"]:raise RefreshError("prompt history hash mismatch")
        if not original.exists():atomic_owned(original,raw,record["uid"],record["mode"],record["gid"])
    atomic_owned(marker,(json.dumps({**state,"state":"recovered"},sort_keys=True)+"\n").encode(),ROOT_UID)
def verify_manifest(repo,head,manifest,user,execute):
    command=["/usr/sbin/runuser","-u",user,"--","/usr/bin/git","-c","safe.directory=*","-C",repo,"ls-tree","-r","--name-only",head,"--","db/migrations"]
    result=execute(command,stdin=subprocess.DEVNULL,capture_output=True,timeout=60,check=False)
    if result.returncode:raise RefreshError("receiver migration tree unavailable")
    names=[line.split("/",2)[-1] for line in result.stdout.decode().splitlines() if line.endswith(".sql")]
    if set(names)!=set(manifest):raise RefreshError("receiver migration manifest names differ")
    for name in names:
        object_name=head+":db/migrations/"+name
        size=execute(["/usr/sbin/runuser","-u",user,"--","/usr/bin/git","-c","safe.directory=*","-C",repo,"cat-file","-s",object_name],
            stdin=subprocess.DEVNULL,capture_output=True,timeout=30,check=False)
        if size.returncode:
            raise RefreshError("receiver migration object unavailable")
        try:length=int(size.stdout)
        except ValueError:raise RefreshError("receiver migration size invalid") from None
        if length>2_000_000:raise RefreshError("receiver migration exceeds bound")
        result=execute(["/usr/sbin/runuser","-u",user,"--","/usr/bin/git","-c","safe.directory=*","-C",repo,"show",object_name],
            stdin=subprocess.DEVNULL,capture_output=True,timeout=60,check=False)
        if result.returncode or len(result.stdout)>2_000_000 or hashlib.sha256(result.stdout).hexdigest()!=manifest[name]:raise RefreshError("receiver migration manifest hash differs")
def wait_reload_ack(settings,expected,timeout=45,clock=time.monotonic,sleep=time.sleep):
    path=Path(settings["reload_ack"]);deadline=clock()+timeout
    while clock()<deadline:
        try:
            info=regular(path,settings["owner"],100_000)
            if stat.S_IMODE(info.st_mode)!=0o600:raise RefreshError("runner reload acknowledgement mode invalid")
            if json.loads(path.read_text())==expected:return
        except FileNotFoundError:pass
        sleep(.25)
    raise RefreshError("runner reload acknowledgement timeout")
def receiver_advance(role,payload,policy_file,receiver_config,execute=subprocess.run):
    required={"action","target","maintenance_key","expected_old_policy_fingerprint","new_policy","new_head","bundle_sha256","bundle_b64","merge_commits","migration_manifest","rebase_templates"}
    if role not in {"bridge","harper","worker"} or not isinstance(payload,dict) or set(payload)!=required or payload.get("action")!="advance_base" or payload.get("target")!=role:raise RefreshError("invalid advance-base request")
    if not SHA.fullmatch(str(payload["new_head"])) or not DIGEST.fullmatch(str(payload["bundle_sha256"])):raise RefreshError("invalid advance-base identity")
    try:bundle=base64.b64decode(payload["bundle_b64"],validate=True)
    except Exception:raise RefreshError("malformed Git bundle") from None
    if not bundle or len(bundle)>MAX_BUNDLE or hashlib.sha256(bundle).hexdigest()!=payload["bundle_sha256"]:raise RefreshError("Git bundle digest or size invalid")
    new_policy=validate_policy(payload["new_policy"]);new_fp=digest(new_policy);settings=receiver_settings(role,policy_file,receiver_config);recover_pair(settings)
    regular(Path(settings["policy"]),ROOT_UID);regular(Path(settings["config"]),settings["owner"]);regular(Path(settings["receiver"]),ROOT_UID,100_000)
    old_policy=validate_policy(json.loads(Path(policy_file).read_text()));old_fp=digest(old_policy)
    if old_fp==new_fp:
        marker=Path(settings["journal"])
        if not marker.exists():raise RefreshError("advanced policy lacks receipt journal")
        state=json.loads(marker.read_text())
        if state.get("state")!="committed" or state.get("new_policy_fingerprint")!=new_fp:raise RefreshError("advanced policy journal mismatch")
        if role=="harper":
            atomic_owned(settings["reload_receipt"],(json.dumps(state["reload_receipt"],sort_keys=True)+"\n").encode(),settings["owner"],0o600)
            wait_reload_ack(settings,state["reload_ack"])
        return state["receipt"]
    if old_fp!=payload["expected_old_policy_fingerprint"]:raise RefreshError("receiver old policy mismatch")
    verify_authority(old_policy,new_policy)
    if any(item["base_sha"]!=payload["new_head"] for item in new_policy["requirements"].values()):raise RefreshError("receiver head mismatch")
    if not isinstance(payload["merge_commits"],list) or any(not SHA.fullmatch(str(value)) for value in payload["merge_commits"]):raise RefreshError("invalid merge ancestry")
    if not isinstance(payload["migration_manifest"],dict) or any(not re.fullmatch(r"[0-9]{3}_[a-z0-9_]+\.sql",name) or not DIGEST.fullmatch(str(value)) for name,value in payload["migration_manifest"].items()):raise RefreshError("invalid migration manifest")
    if not isinstance(payload["rebase_templates"],list) or any(not re.fullmatch(r"continuous-[a-z0-9-]{3,63}",str(value)) for value in payload["rebase_templates"]):raise RefreshError("invalid rebase templates")
    if role in RECEIVER_GIT:
        user,repo=RECEIVER_GIT[role];uid=pwd.getpwnam(user).pw_uid;gid=pwd.getpwnam(user).pw_gid
        root=RECEIVER_STATE_ROOT;root.mkdir(parents=True,exist_ok=True,mode=0o711);os.chmod(root,0o711)
        user_root=root/("bundles-"+role);user_root.mkdir(exist_ok=True,mode=0o700);os.chown(user_root,uid,gid);os.chmod(user_root,0o700)
        fd,name=tempfile.mkstemp(prefix="base-refresh-",suffix=".bundle",dir=user_root)
        try:
            os.fchmod(fd,0o600);os.fchown(fd,uid,gid);view=memoryview(bundle)
            while view:
                written=os.write(fd,view)
                if written<=0:raise RefreshError("short bundle write")
                view=view[written:]
            os.fsync(fd);os.close(fd);fd=-1
            ref="refs/loop/base-refresh/"+payload["new_head"]
            commands=[
             ["/usr/sbin/runuser","-u",user,"--","/usr/bin/git","-C",repo,"bundle","verify",name],
             ["/usr/sbin/runuser","-u",user,"--","/usr/bin/git","-C",repo,"fetch","--no-tags",name,ref+":"+ref]]
            for command_line in commands:
                result=execute(command_line,stdin=subprocess.DEVNULL,capture_output=True,timeout=120,check=False)
                if result.returncode:raise RefreshError("receiver bundle import failed")
            ancestors=sorted({item["base_sha"] for item in old_policy["requirements"].values()}|set(payload["merge_commits"]))
            for ancestor in ancestors:
                result=execute(["/usr/sbin/runuser","-u",user,"--","/usr/bin/git","-C",repo,"merge-base","--is-ancestor",ancestor,payload["new_head"]],
                    stdin=subprocess.DEVNULL,capture_output=True,timeout=30,check=False)
                if result.returncode:raise RefreshError("receiver ancestry check failed")
            verify_manifest(repo,payload["new_head"],payload["migration_manifest"],user,execute)
        finally:
            if fd>=0:os.close(fd)
            try:os.unlink(name)
            except OSError:pass
    config_path=Path(settings["config"]);policy_path=Path(settings["policy"]);receiver_path=Path(settings["receiver"])
    regular(config_path,settings["owner"]);regular(policy_path,ROOT_UID);regular(receiver_path,ROOT_UID,100_000)
    config=json.loads(config_path.read_text());templates=config.get("templates")
    if not isinstance(templates,dict):raise RefreshError("receiver template registry unavailable")
    prompt_records=[]
    for name in payload["rebase_templates"]:
        templates.pop(name,None)
        prompt=Path(settings["prompts"])/(name+".json")
        if prompt.exists():
            info=prompt.stat();history=prompt.with_name(prompt.name+"."+old_fp+".history");raw=prompt.read_bytes()
            if history.exists() and history.read_bytes()!=raw:raise RefreshError("prompt history conflict")
            if not history.exists():atomic_owned(history,raw,info.st_uid,stat.S_IMODE(info.st_mode),info.st_gid)
            prompt_records.append({"original":str(prompt),"history":str(history),"sha256":hashlib.sha256(raw).hexdigest(),
                                   "uid":info.st_uid,"gid":info.st_gid,"mode":stat.S_IMODE(info.st_mode)})
    if role=="bridge":config["continuous_policy"]=new_policy
    if role=="harper":config["continuous_policy_fingerprint"]=new_fp
    receiver_config=json.loads(receiver_path.read_text())
    if (set(receiver_config)!={"role","policy_fingerprint","policy_file","lock_file"}
            or receiver_config.get("role")!=role or receiver_config.get("policy_fingerprint")!=old_fp
            or receiver_config.get("policy_file")!=str(policy_path)
            or receiver_config.get("lock_file")!="/etc/loop-continuous/receiver.lock"):
        raise RefreshError("receiver config policy mismatch")
    receiver_config["policy_fingerprint"]=new_fp
    marker=Path(settings["journal"]);marker.parent.mkdir(parents=True,exist_ok=True)
    policy_raw=policy_path.read_bytes();config_raw=config_path.read_bytes();receiver_raw=receiver_path.read_bytes()
    for path,raw,owner in ((Path(str(policy_path)+".base-refresh-backup"),policy_raw,ROOT_UID),
                           (Path(str(config_path)+".base-refresh-backup"),config_raw,settings["owner"]),
                           (Path(str(receiver_path)+".base-refresh-backup"),receiver_raw,ROOT_UID)):
        atomic_owned(path,raw,owner)
    config_encoded=(json.dumps(config,sort_keys=True,indent=2)+"\n").encode()
    reload_receipt=None;reload_ack=None
    if role=="harper":
        retained={name:template_fingerprint(name,definition) for name,definition in sorted(config["templates"].items())}
        reload_receipt={"old_policy_fingerprint":old_fp,"new_policy_fingerprint":new_fp,"new_head":payload["new_head"],
                        "bundle_sha256":payload["bundle_sha256"],"removed_templates":sorted(payload["rebase_templates"]),
                        "retained_templates":retained,"config_sha256":hashlib.sha256(config_encoded).hexdigest()}
        reload_ack={"new_policy_fingerprint":new_fp,"config_sha256":reload_receipt["config_sha256"],
                    "removed_templates":reload_receipt["removed_templates"],"retained_templates":retained,
                    "new_head":payload["new_head"],"bundle_sha256":payload["bundle_sha256"]}
    state={"state":"prepared","maintenance_key":payload["maintenance_key"],"old_policy_fingerprint":old_fp,
           "new_policy_fingerprint":new_fp,"new_head":payload["new_head"],"bundle_sha256":payload["bundle_sha256"],
           "policy_sha256":hashlib.sha256(policy_raw).hexdigest(),"config_sha256":hashlib.sha256(config_raw).hexdigest(),
           "receiver_sha256":hashlib.sha256(receiver_raw).hexdigest(),"prompts":prompt_records,
           "reload_receipt":reload_receipt,"reload_ack":reload_ack}
    atomic_owned(marker,(json.dumps(state,sort_keys=True)+"\n").encode(),ROOT_UID)
    atomic_owned(policy_path,(json.dumps(new_policy,sort_keys=True,indent=2)+"\n").encode(),ROOT_UID,0o600)
    write_in_place(config_path,config_encoded,settings["owner"])
    atomic_owned(receiver_path,(json.dumps(receiver_config,sort_keys=True,indent=2)+"\n").encode(),ROOT_UID,0o600)
    for record in prompt_records:
        original=Path(record["original"])
        if original.exists():
            original.unlink()
            directory=os.open(original.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(directory);os.close(directory)
    if role=="harper":
        manifest_root=Path(settings.get("manifest_root","/opt/loop-review/continuous/manifests"));manifest_root.mkdir(parents=True,exist_ok=True,mode=0o755)
        atomic_owned(manifest_root/(payload["new_head"]+".json"),(json.dumps(payload["migration_manifest"],sort_keys=True,indent=2)+"\n").encode(),ROOT_UID,0o644)
    installed_sha=digest({"policy":new_policy,"config_templates":config["templates"],"new_head":payload["new_head"]})
    receipt={"target":role,"old_policy_fingerprint":old_fp,"new_policy_fingerprint":new_fp,"new_head":payload["new_head"],
             "bundle_sha256":payload["bundle_sha256"],"installed_sha256":installed_sha}
    committed={**state,"state":"committed","receipt":receipt}
    atomic_owned(marker,(json.dumps(committed,sort_keys=True)+"\n").encode(),ROOT_UID)
    if role=="harper":
        atomic_owned(settings["reload_receipt"],(json.dumps(reload_receipt,sort_keys=True)+"\n").encode(),settings["owner"],0o600)
        wait_reload_ack(settings,reload_ack)
    return receipt

class BaseRefresher:
    def __init__(self,config,bridge_call,github_call,execute=subprocess.run):
        self.config,self.bridge,self.github,self.execute=checked(config),bridge_call,github_call,execute
    def git(self,args,binary=False,check=True,limit=1_000_000,env=None):
        env=env or trusted_git_env()
        return run_git(self.config["source_repo"],args,env,binary,check,limit)
    def merged_commits(self,status):
        values=[]
        for item in status.get("items",[]):
            if item.get("state")!="merged":continue
            value=item.get("merge_commit_sha")
            if not SHA.fullmatch(str(value)):raise RefreshError("merged dependency receipt unavailable")
            values.append(value)
        return sorted(set(values))
    def observed_head(self):
        from urllib.parse import quote
        response=deadline_call(self.github,self.config["github_timeout_seconds"],"GET",f"/repos/{REPOSITORY}/git/ref/heads/{quote(BRANCH,safe='')}")
        value=(response.get("object") or {}).get("sha") if isinstance(response,dict) else None
        if response.get("ref")!="refs/heads/"+BRANCH or (response.get("object") or {}).get("type")!="commit" or not SHA.fullmatch(str(value)):raise RefreshError("trusted branch head unavailable")
        return value
    def run_once(self,status=None):
        root=Path(self.config["state_root"]);root.mkdir(parents=True,exist_ok=True)
        info=root.lstat()
        if root.is_symlink() or not root.is_dir() or info.st_uid!=os.geteuid() or info.st_mode&0o022:raise RefreshError("untrusted base refresh state root")
        fd=os.open(root/"refresh.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return {"status":"busy"}
            return self._run_locked(status)
        finally:os.close(fd)
    def _run_locked(self,status=None):
        status=status or self.bridge("GET","/v1/queue");maintenance=status.get("maintenance")
        if maintenance and maintenance.get("state")=="complete":maintenance=None
        if maintenance:head=maintenance["new_head"];key=maintenance["key"]
        else:
            head=self.observed_head();bases={item.get("base_sha") for item in status.get("items",[]) if item.get("state") in {"proposed","registering","ready"}}
            if not bases:
                policy_fp=status["policy_fingerprint"];base_status=self.bridge("GET","/v1/queue/base-refresh")
                if base_status.get("state")=="idle":return {"status":"idle","reason":"no_refreshable_work"}
            if bases and bases=={head}:return {"status":"idle","reason":"base_current"}
            key="base-refresh-"+head[:12];maintenance=self.bridge("POST","/v1/queue/base-refresh/begin",payload={"key":key,"new_head":head})
        old_policy_fp=maintenance["old_policy_fingerprint"];source=Path(self.config["source_repo"])
        ref="refs/loop/base-refresh/"+head;tip_ref="refs/loop/base-refresh-tip/"+key
        with trusted_fetch_env(self.config["github_token_file"],self.config["state_root"]) as fetch_env:
            self.git(["-c","credential.helper=","-c","http.followRedirects=false","fetch","--no-tags","--force","https://github.com/"+REPOSITORY+".git","+refs/heads/"+BRANCH+":"+tip_ref],env=fetch_env)
        tip=self.git(["rev-parse",tip_ref])
        self.git(["merge-base","--is-ancestor",head,tip])
        self.git(["update-ref",ref,head])
        if self.git(["rev-parse",ref])!=head:raise RefreshError("fetched branch identity mismatch")
        policy_path=Path(self.config["policy_file"]);regular(policy_path,ROOT_UID,1_000_000)
        validate_source_repo(source)
        old_policy=json.loads(policy_path.read_text())
        if digest(old_policy)!=old_policy_fp:
            backup=Path(str(policy_path)+".base-refresh-backup")
            if not backup.exists():raise RefreshError("Control policy does not match Bridge")
            old_policy=json.loads(backup.read_text())
        if digest(old_policy)!=old_policy_fp:raise RefreshError("Control policy does not match Bridge")
        old_bases=sorted({item["base_sha"] for item in old_policy["requirements"].values()});merges=self.merged_commits(status)
        for ancestor in sorted(set(old_bases+merges)):
            self.git(["merge-base","--is-ancestor",ancestor,head])
        changed=set()
        for old in old_bases:changed.update(self.git(["diff","--name-only",old+".."+head]).splitlines())
        if changed&TOOLCHAIN:raise RefreshError("toolchain_update_requires_image_refresh")
        new_policy=regenerate_policy(old_policy,head,source);verify_authority(old_policy,new_policy)
        state_root=Path(self.config["state_root"]);state_root.mkdir(parents=True,exist_ok=True)
        bundle=state_root/(key+".bundle")
        if bundle.exists():regular(bundle,ROOT_UID,MAX_BUNDLE)
        else:
            temporary=bundle.with_suffix(".tmp");self.git(["update-ref",ref,head])
            args=["bundle","create",str(temporary),ref,*["^"+value for value in old_bases]]
            self.git(args);os.chmod(temporary,0o600)
            fd=os.open(temporary,os.O_RDONLY);os.fsync(fd);os.close(fd);os.replace(temporary,bundle)
            directory=os.open(bundle.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(directory);os.close(directory)
        self.git(["bundle","verify",str(bundle)])
        encoded,bundle_sha=bundle_payload(bundle)
        prepared=self.bridge("POST","/v1/queue/base-refresh/prepare",payload={"key":key,"new_policy":new_policy,"bundle_sha256":bundle_sha})
        manifests=migration_manifest(source,head);receipts=prepared.get("receipts",{})
        request={"action":"advance_base","maintenance_key":key,"expected_old_policy_fingerprint":old_policy_fp,
          "new_policy":new_policy,"new_head":head,"bundle_sha256":bundle_sha,"bundle_b64":encoded,
          "merge_commits":merges,"migration_manifest":manifests,"rebase_templates":prepared["rebase_templates"]}
        for target in ("bridge","harper","worker"):
            if target in receipts:continue
            receipt=trusted_command(self.config["receivers"][target],{**request,"target":target},self.execute,timeout=600)
            self.bridge("POST","/v1/queue/base-refresh/receipt",payload={"key":key,"receipt":receipt})
        committed=self.bridge("POST","/v1/queue/base-refresh/commit",payload={"key":key})
        return {"status":"complete","new_head":head,"policy_fingerprint":committed["policy_fingerprint"],"rebased":committed["rebased"]}
