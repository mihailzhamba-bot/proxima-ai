"""Trusted Harper runner: fixed template -> existing OpenHands handoff -> checks -> PR.
Run outside the candidate checkout. No model/worker receives Bridge runner or Git credentials.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import tempfile
import time
import uuid
import sys
from pathlib import Path
if not __package__:
    # -I deliberately omits the script directory; import only our explicitly
    # installed sibling modules, never the candidate working directory.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from .bridge import BridgeError, JsonHTTP, secret, template_fingerprint
    from .verify_candidate import sanitize
    from .publication import process_identity, process_scope_running, terminate_gated_process, write_journal, recover_push
except ImportError:
    from bridge import BridgeError, JsonHTTP, secret, template_fingerprint
    from verify_candidate import sanitize
    from publication import process_identity, process_scope_running, terminate_gated_process, write_journal, recover_push

ID=re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
SHA=re.compile(r"^[a-f0-9]{40}$")
def restore_tracked_modes(checkout, records):
    root=Path(checkout).resolve()
    for record in records.split("\0"):
        if not record:continue
        metadata,name=record.split("\t",1);mode,kind,_blob=metadata.split()
        path=root/name
        if kind!="blob" or Path(name).is_absolute() or ".." in Path(name).parts:raise ValueError("invalid tracked mode entry")
        if path.parent.resolve()!=path.parent:raise ValueError("symlinked tracked parent")
        if mode=="120000" and path.is_symlink():continue
        if path.is_symlink() or not path.is_file() or mode not in {"100644","100755"}:raise ValueError("invalid tracked file mode")
        path.chmod(0o755 if mode=="100755" else 0o644)

def prepare_mountpoints(checkout,directories,files,tracked_paths):
    root=Path(checkout)
    if root.is_symlink() or not root.is_dir():raise ValueError("invalid checkout root")
    root=root.resolve();tracked=set(tracked_paths)
    for relative,is_file in [(value,False) for value in directories]+[(value,True) for value in files]:
        path=Path(relative)
        if path.is_absolute() or not path.parts or any(part in {".",".."} for part in path.parts):raise ValueError("mountpoint escapes checkout")
        normalized=path.as_posix()
        if any(item==normalized or item.startswith(normalized+"/") for item in tracked):raise ValueError("mountpoint covers tracked source")
        current=root
        for index,part in enumerate(path.parts):
            current=current/part
            if current.is_symlink():raise ValueError("symlink mountpoint or parent")
            current.resolve().relative_to(root)
            last=index==len(path.parts)-1
            if last and is_file:
                if current.exists():
                    if not current.is_file() or current.stat().st_nlink!=1 or current.stat().st_size:raise ValueError("unexpected mountpoint file")
                else:current.touch(mode=0o600,exist_ok=False)
            else:
                if current.exists() and not current.is_dir():raise ValueError("mountpoint parent is not a directory")
                if last and current.exists() and any(current.iterdir()):raise ValueError("unexpected mountpoint directory content")
                current.mkdir(mode=0o755,exist_ok=True)

class DeliveryRunner:
    def __init__(self, config, bridge, execute=None, identity_reader=process_identity, scope_reader=process_scope_running, fetch_execute=None):
        self.config,self.bridge=config,bridge
        self.execute=execute or self._execute
        self.identity_reader=identity_reader
        self.scope_reader=scope_reader
        self.fetch_execute=fetch_execute
        self.push_context=None
        self.stage_number=0
        self.evidence=None
        publish_identity=Path(config.get("github_publish_identity_file",Path(config["trusted_home"])/".ssh/github_ed25519"));known_hosts=Path(config.get("known_hosts_file",Path(config["trusted_home"])/".ssh/known_hosts"))
        if not publish_identity.is_absolute() or not known_hosts.is_absolute():raise ValueError("runner SSH trust paths must be absolute")
        git_ssh=shlex.join(["ssh","-oBatchMode=yes","-oControlMaster=no","-oControlPersist=no","-oControlPath=none","-oForwardAgent=no","-oIdentitiesOnly=yes","-oStrictHostKeyChecking=yes","-oUserKnownHostsFile="+str(known_hosts),"-i",str(publish_identity)])
        self.env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"HOME":config["trusted_home"],"GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_SYSTEM":"/dev/null","GIT_CONFIG_NOSYSTEM":"1","GIT_TERMINAL_PROMPT":"0","GIT_NO_REPLACE_OBJECTS":"1","GIT_SSH_COMMAND":git_ssh}
    def _execute(self,argv,cwd=None):
        self.stage_number+=1
        process=None
        gate_read=gate_write=None
        try:
            if self.push_context:
                # Child cannot execute git until its identity is durable. The
                # write fd is non-inheritable and is never passed to the child.
                gate_read,gate_write=os.pipe()
                gate=[sys.executable,"-I","-S",str(Path(__file__).with_name("push_gate.py")),str(gate_read),*argv]
                process=subprocess.Popen(gate,cwd=cwd,env=self.env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,pass_fds=(gate_read,),start_new_session=True)
                os.close(gate_read);gate_read=None
                journal=self.push_context["journal"]
                journal["child_pid"]=process.pid;journal["child_identity"]=self.identity_reader(process.pid)
                if not journal["child_identity"]:raise RuntimeError("gated child identity unavailable")
                journal["child_pgid"]=os.getpgid(process.pid);journal["child_sid"]=os.getsid(process.pid)
                if journal["child_pgid"]!=process.pid or journal["child_sid"]!=process.pid:raise RuntimeError("publisher did not start a dedicated session")
                journal["child_boot_id"]=journal["child_identity"].split(":",1)[0]
                journal["process_scope"]="session-v1"
                # True means permission may have been sent, never proof of exec.
                # It is committed before writing the permission byte.
                journal["exec_released"]=True
                write_journal(self.push_context["path"],journal)
                os.write(gate_write,b"R");os.close(gate_write);gate_write=None
                try:stdout,stderr=process.communicate(timeout=self.config.get("command_timeout",7200));code=process.returncode
                except subprocess.TimeoutExpired:terminate_gated_process(process,journal,self.identity_reader);stdout,stderr=process.communicate();code=124
                result=subprocess.CompletedProcess(argv,code,stdout,stderr)
            else:
                result=subprocess.run(argv,cwd=cwd,env=self.env,capture_output=True,text=True,timeout=self.config.get("command_timeout",7200),check=False)
        except subprocess.TimeoutExpired as exc:
            stdout=exc.stdout.decode(errors="replace") if isinstance(exc.stdout,bytes) else exc.stdout or ""
            stderr=exc.stderr.decode(errors="replace") if isinstance(exc.stderr,bytes) else exc.stderr or ""
            result=subprocess.CompletedProcess(argv,124,stdout,stderr)
        except Exception:
            if process is not None:
                try:terminate_gated_process(process,self.push_context["journal"],self.identity_reader)
                except (ProcessLookupError,RuntimeError):pass
                try:process.communicate(timeout=1)
                except subprocess.TimeoutExpired:pass
            result=subprocess.CompletedProcess(argv,127,"","publisher subprocess could not complete")
        finally:
            for descriptor in (gate_read,gate_write):
                if descriptor is not None:os.close(descriptor)
        stopped=True
        if self.push_context and self.push_context["journal"].get("exec_released") is True:
            try:stopped=not self.scope_reader(self.push_context["journal"])
            except Exception:stopped=False
        if self.evidence:
            log=sanitize(result.stdout+result.stderr)
            token=getattr(self.bridge,"token","")
            if token:log=log.replace(token,"[redacted]")
            (self.evidence/f"stage-{self.stage_number:02d}.log").write_text(log)
            (self.evidence/f"stage-{self.stage_number:02d}.json").write_text(json.dumps({"program":Path(argv[0]).name,"returncode":result.returncode}))
        if result.returncode or not stopped:
            error=BridgeError(502,"trusted runner command failed; sanitized stage logs retained")
            error.process_stopped=stopped;error.returncode=result.returncode
            raise error
        return result.stdout
    def fetch_bundle(self,argv,destination):
        self.stage_number+=1
        destination=Path(destination);temporary=destination.with_name(destination.name+"."+uuid.uuid4().hex+".tmp")
        try:
            if self.fetch_execute:
                self.fetch_execute(argv,temporary)
                result=subprocess.CompletedProcess(argv,0,b"",b"")
            else:
                with temporary.open("xb") as output:
                    result=subprocess.run(argv,env=self.env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.PIPE,timeout=self.config.get("command_timeout",7200),check=False)
            if result.returncode:
                if self.evidence:
                    log=sanitize((result.stderr or b"").decode(errors="replace") if isinstance(result.stderr,bytes) else result.stderr or "")
                    (self.evidence/f"stage-{self.stage_number:02d}.log").write_text(log)
                raise BridgeError(502,"trusted bundle fetch failed; no candidate accepted")
            os.chmod(temporary,0o600);os.replace(temporary,destination)
        finally:
            if temporary.exists():temporary.unlink()
    def push(self,job_id,admitted,argv):
        publisher_id=str(uuid.uuid4());path=self.evidence/"publisher.json"
        journal={"job_id":job_id,"permit":admitted["permit"],"publisher_id":publisher_id,"sha":admitted["sha"],"state":"starting","parent_pid":os.getpid(),"parent_identity":self.identity_reader(os.getpid()),"child_pid":None,"child_identity":None,"exec_gate":"pipe-v1","exec_released":False}
        write_journal(path,journal)
        self.bridge.call("POST",f"/v1/runner/jobs/{job_id}/start-push",{"permit":admitted["permit"],"publisher_id":publisher_id})
        journal["state"]="running";write_journal(path,journal)
        self.push_context={"path":path,"journal":journal}
        try:self.execute(argv)
        except Exception as exc:
            stopped=getattr(exc,"process_stopped",False)
            if stopped:
                journal["state"]="finished";journal["receipt"]={"permit":admitted["permit"],"publisher_id":publisher_id,"outcome":"failed","process_stopped":True,"returncode":exc.returncode,"evidence_ref":str(path)}
                write_journal(path,journal)
                try:self.bridge.call("POST",f"/v1/runner/jobs/{job_id}/record-push",journal["receipt"])
                except Exception:pass
            raise
        else:
            journal["state"]="finished";journal["receipt"]={"permit":admitted["permit"],"publisher_id":publisher_id,"outcome":"succeeded","process_stopped":True,"returncode":0,"evidence_ref":str(path)}
            write_journal(path,journal)
            self.bridge.call("POST",f"/v1/runner/jobs/{job_id}/record-push",journal["receipt"])
        finally:self.push_context=None
    def fence(self,job_id): return self.bridge.call("GET",f"/v1/runner/jobs/{job_id}/fence")
    def run(self,job_id):
        if not ID.fullmatch(job_id): raise ValueError("invalid job ID")
        self.evidence=Path(self.config["evidence_root"])/job_id/str(time.time_ns())
        self.evidence.mkdir(parents=True,mode=0o700);self.evidence.chmod(0o700)
        job=self.bridge.call("POST",f"/v1/runner/jobs/{job_id}/claim",{})
        template=self.config["templates"].get(job["template"])
        if not template: raise ValueError("template is not installed on Harper")
        fingerprint=template_fingerprint(job["template"],template)
        if job.get("template_fingerprint")!=fingerprint:raise BridgeError(409,"Harper template contract differs from Bridge")
        base=template["base_sha"]
        if not SHA.fullmatch(base): raise ValueError("template needs immutable base SHA")
        image=self.config["verification_image"]
        if not re.fullmatch(r"[A-Za-z0-9.:/_-]+@sha256:[a-f0-9]{64}",image): raise ValueError("verification image must be pinned by digest")
        ssh=["ssh","-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","StrictHostKeyChecking=yes","-o","ForwardAgent=no","-o","UserKnownHostsFile="+self.config["known_hosts_file"],"-i",self.config["worker_identity_file"],self.config["worker_host"]]
        remote=shlex.join([self.config["worker_python"],self.config["worker_dispatcher"],"--config",self.config["worker_config"],"--template",job["template"],"--job",job_id])
        self.fence(job_id)
        receipt=json.loads(job["recovery_receipt"]) if job.get("recover_only") else json.loads(self.execute([*ssh,remote]))
        # Handoff receipt checks ancestry and paths; never treated as verification PASS.
        sha=receipt.get("head_sha","")
        if receipt.get("ok") is not True or receipt.get("template")!=job["template"] or receipt.get("template_fingerprint")!=fingerprint or receipt.get("base_sha")!=base or not SHA.fullmatch(sha) or receipt.get("conversation_id")!=job["external_id"]: raise BridgeError(409,"OpenHands handoff integrity mismatch")
        if receipt.get("branch")!="feat/loop-"+job_id: raise BridgeError(409,"unexpected worker branch")
        bundle_sha=receipt.get("bundle_sha256","")
        if not re.fullmatch(r"[a-f0-9]{64}",bundle_sha):raise BridgeError(409,"worker bundle digest missing")
        self.fence(job_id)
        work=Path(tempfile.mkdtemp(prefix="loop-"+job_id+"-",dir=self.config["work_root"]))
        os.chmod(work,0o755)
        bundle=work/"candidate.bundle"
        remote_fetch=shlex.join([self.config["worker_fetcher"],"--job",job_id])
        self.fetch_bundle([*ssh,remote_fetch],bundle)
        with bundle.open("rb") as stream:observed_bundle_sha=hashlib.file_digest(stream,"sha256").hexdigest()
        if observed_bundle_sha!=bundle_sha:raise BridgeError(409,"worker bundle digest mismatch")
        checkout=work/"candidate"
        git=["git","-c","core.hooksPath=/dev/null","-c","protocol.file.allow=always"]
        self.execute([*git,"clone","--no-hardlinks","--no-checkout",self.config["source_repo"],str(checkout)])
        self.execute([*git,"-C",str(checkout),"fetch",str(bundle),f"refs/heads/feat/loop-{job_id}"])
        self.execute([*git,"-C",str(checkout),"checkout","--detach",sha])
        if self.execute([*git,"-C",str(checkout),"rev-parse","HEAD"]).strip()!=sha: raise BridgeError(409,"candidate SHA mismatch")
        self.execute([*git,"-C",str(checkout),"merge-base","--is-ancestor",base,sha])
        paths=self.execute([*git,"-C",str(checkout),"diff","--name-only",base,sha]).splitlines()
        allowed=template.get("allowed_paths",[])
        protected=re.compile(r"(^Makefile$|^tools/|^\.github/|(^|/)(package(-lock)?\.json|pyproject\.toml|uv\.lock)$|(^|/)[^/]*config[^/]*$|/tests/|^db/)")
        policy_exceptions={"tools/wb/daily.py","tools/tests/test_wb_daily.py","infra/systemd/proxima-wb-daily.service","infra/systemd/proxima-wb-daily.timer","services/collector/tests/collect.db.test.ts","tools/loop/wb_daily_status.py","tools/tests/test_wb_daily_status.py"}
        if not paths or any((protected.search(p) and p not in policy_exceptions) or not any(p==a or (a.endswith("/") and p.startswith(a)) for a in allowed) for p in paths): raise BridgeError(409,"candidate changes protected or unapproved paths")
        history=json.loads(self.execute([sys.executable,"-I",self.config.get("history_gate","/opt/loop/history_gate.py"),str(checkout),base,sha,*[item for value in allowed for item in ("--allowed",value)]]))
        if history.get("status")!="pass" or history.get("base_sha")!=base or history.get("head_sha")!=sha:raise BridgeError(409,"candidate history gate incomplete")
        (self.evidence/"history-receipt.json").write_text(json.dumps(history,indent=2)+"\n")
        modes=self.execute([*git,"-C",str(checkout),"ls-tree","-r","-z",sha])
        restore_tracked_modes(checkout,modes)
        # The candidate tree (including verifier/control files and .git) is RO.
        # Only dependency/build caches are separate writable mounts.
        cache=work/"writable";cache.mkdir()
        dependencies=["node_modules","services/webapp/node_modules","services/collector/node_modules","services/control-plane/.venv"]
        outputs=["services/collector/dist","services/webapp/.next","build"]
        tracked=self.execute([*git,"-C",str(checkout),"ls-tree","-r","--name-only","-z",sha]).split("\0")
        prepare_mountpoints(checkout,[*dependencies,*outputs,"fixtures/wb-api"],["services/webapp/tsconfig.tsbuildinfo"],[name for name in tracked if name])
        base_mounts=["-v",str(checkout)+":/work:ro","-v",self.config["fixture_root"]+":/work/fixtures/wb-api:ro"]
        dependency_dirs={}
        for i,relative in enumerate(dependencies):
            directory=cache/("dep-"+str(i));directory.mkdir();dependency_dirs[relative]=directory
        output_mounts=[]
        for i,relative in enumerate(outputs):
            directory=cache/("output-"+str(i));directory.mkdir();output_mounts.extend(["-v",str(directory)+":/work/"+relative+":rw"])
        tsinfo=cache/"tsconfig.tsbuildinfo";tsinfo.touch();output_mounts.extend(["-v",str(tsinfo)+":/work/services/webapp/tsconfig.tsbuildinfo:rw"])
        docker=["docker","run","--rm","--network","none","--memory",self.config.get("memory","6g"),"--cpus",str(self.config.get("cpus",3)),"--pids-limit","512","--cap-drop","ALL","--security-opt","no-new-privileges","--read-only","--tmpfs","/tmp:rw,exec,size=2g","--user","1000:1000",*base_mounts,*output_mounts,"-w","/work"]
        checks={}
        vite_mounts=[]
        for stage in ("prepare","verify","build"):
            extra=[]
            for relative,directory in dependency_dirs.items():
                extra.extend(["-v",str(directory)+":/work/"+relative+(":rw" if stage=="prepare" else ":ro")])
            if stage!="prepare":extra.extend(vite_mounts)
            if stage=="build":
                declaration=cache/"next-env.d.ts"
                # Tests may fake command execution; production always has this checkout.
                declaration.write_bytes((checkout/"services/webapp/next-env.d.ts").read_bytes())
                extra.extend(["-v",str(declaration)+":/work/services/webapp/next-env.d.ts:rw"])
            stage_docker=[arg for arg in docker if arg!="--read-only"] if stage=="prepare" else docker
            receipt=json.loads(self.execute([*stage_docker,*extra,image,"python3","/opt/loop/verify_candidate.py",sha,"--stage",stage]))
            if receipt.get("status")!="pass" or (stage!="prepare" and receipt.get("checks")!={stage:{"sha":sha,"status":"pass","skipped":0}}):raise BridgeError(409,"verification incomplete")
            (self.evidence/(stage+"-receipt.json")).write_text(json.dumps(receipt,indent=2))
            if stage!="prepare":checks.update(receipt["checks"])
            else:
                # Vite-generated config/transform caches are writable overlays,
                # never a writable node_modules package tree.
                for number,relative in enumerate(("node_modules","services/webapp/node_modules")):
                    prepare_mountpoints(dependency_dirs[relative],[".vite-temp",".vite"],[],[])
                    for name in (".vite-temp",".vite"):
                        directory=cache/("vite-"+str(number)+name);directory.mkdir()
                        vite_mounts.extend(["-v",str(directory)+":/work/"+relative+"/"+name+":rw"])
        self.fence(job_id)
        reviewer=self.config["reviewer_command"]
        if not isinstance(reviewer,list) or not reviewer or not Path(reviewer[0]).is_absolute(): raise ValueError("reviewer must be a trusted absolute executable")
        review=json.loads(self.execute([*reviewer,str(checkout),base,sha]))
        if review!={"sha":sha,"status":"pass","skipped":0}: raise BridgeError(409,"independent review blocked")
        report={"producer":"harper","sha":sha,"checks":{**checks,"review":review}}
        (self.evidence/"verification.json").write_text(json.dumps(report,indent=2)+"\n")
        self.fence(job_id)
        # Publish from a new bare repository never mounted in the candidate sandbox.
        publish=work/"publish.git"
        self.execute([*git,"init","--bare",str(publish)])
        # Worker bundles contain base..head and require the trusted base objects.
        self.execute([*git,"-C",str(publish),"fetch","--no-tags",self.config["source_repo"],base])
        self.execute([*git,"-C",str(publish),"fetch",str(bundle),f"refs/heads/feat/loop-{job_id}:refs/heads/feat/loop-{job_id}"])
        admitted=self.bridge.call("POST",f"/v1/runner/jobs/{job_id}/begin-publication",report)
        permit=admitted.get("permit","")
        expected_staging=f"refs/heads/loop-staging/{job_id}/{hashlib.sha256(permit.encode()).hexdigest()}" if isinstance(permit,str) else ""
        if admitted.get("staging_ref")!=expected_staging:raise BridgeError(409,"Bridge returned invalid publication staging ref")
        self.push(job_id,admitted,[*git,"-C",str(publish),"push",self.config["publish_remote"],f"refs/heads/feat/loop-{job_id}:{expected_staging}"])
        # Bridge holds its publication fence while checking GitHub's actual ref
        # and creating/recovering the PR. No merge/deploy path exists.
        return self.bridge.call("POST",f"/v1/runner/jobs/{job_id}/finish-publication",{"permit":admitted["permit"]})

def trusted_reload_receipt(path):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1 or info.st_size>100_000:raise ValueError("untrusted runner reload receipt")
        return json.loads(os.read(fd,100_001))
    finally:os.close(fd)
def write_reload_ack(path,receipt):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",dir=path.parent,delete=False) as output:
        temporary=Path(output.name);json.dump(receipt,output,sort_keys=True,separators=(",",":"));output.write("\n");output.flush();os.fsync(output.fileno())
    os.chmod(temporary,0o600);os.replace(temporary,path)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(directory);os.close(directory)
def trusted_template_binding(name,definition,policy,receipt_root="/etc/loop-runner/template-receipts"):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}",str(name)) or not isinstance(definition,dict):raise ValueError("invalid runner template binding")
    receipt=trusted_reload_receipt(Path(receipt_root)/(name+".json"))
    required={"template_name","template_fingerprint","policy_fingerprint","base_sha","installed_sha256"}
    prompt_path=Path(str(definition.get("prompt_file","")))
    try:fd=os.open(prompt_path,os.O_RDONLY|os.O_NOFOLLOW)
    except (OSError,TypeError):raise ValueError("untrusted runner template prompt") from None
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o022
                or info.st_nlink!=1 or info.st_size>1_000_000):raise ValueError("untrusted runner template prompt")
        chunks=[];total=0
        while True:
            chunk=os.read(fd,min(65536,1_000_001-total))
            if not chunk:break
            chunks.append(chunk);total+=len(chunk)
            if total>1_000_000:raise ValueError("untrusted runner template prompt")
        prompt=b"".join(chunks)
    finally:os.close(fd)
    installed_sha=hashlib.sha256(json.dumps({"name":name,"template":definition,"prompt_sha256":hashlib.sha256(prompt).hexdigest()},
        sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    if (not isinstance(receipt,dict) or set(receipt)!=required or receipt["template_name"]!=name
            or receipt["template_fingerprint"]!=template_fingerprint(name,definition)
            or receipt["policy_fingerprint"]!=policy or receipt["base_sha"]!=definition.get("base_sha")
            or receipt["installed_sha256"]!=installed_sha):raise ValueError("runner template binding mismatch")
    return True
def validate_continuous_additions(templates,retained,policy,receipt_root):
    if not isinstance(templates,dict) or not isinstance(retained,dict):raise ValueError("invalid retained runner templates")
    for name,fingerprint in retained.items():
        if name not in templates or template_fingerprint(name,templates[name])!=fingerprint:raise ValueError("retained runner authority changed")
    for name in sorted(set(templates)-set(retained)):
        trusted_template_binding(name,templates[name],policy,receipt_root)
def acknowledge_installed_refresh(config_raw,config,receipt_path="/etc/loop-runner/base-refresh-receipt.json",ack_path="/var/lib/loop-runner/base-refresh-ack.json",template_receipt_root="/etc/loop-runner/template-receipts"):
    path=Path(receipt_path)
    if not path.exists():return False
    receipt=trusted_reload_receipt(path);policy=config.get("continuous_policy_fingerprint")
    if receipt.get("new_policy_fingerprint")!=policy:return False
    expected={"new_policy_fingerprint":policy,"config_sha256":receipt.get("config_sha256"),
              "removed_templates":receipt.get("removed_templates"),"new_head":receipt.get("new_head"),
              "bundle_sha256":receipt.get("bundle_sha256"),"retained_templates":receipt.get("retained_templates")}
    required={"new_policy_fingerprint","config_sha256","removed_templates","new_head","bundle_sha256","retained_templates"}
    if (set(expected)!=required or not isinstance(expected["removed_templates"],list)
            or not isinstance(expected["retained_templates"],dict)):raise ValueError("invalid startup reload receipt")
    validate_continuous_additions(config.get("templates",{}),expected["retained_templates"],policy,template_receipt_root)
    ack_file=Path(ack_path)
    acknowledged=ack_file.exists() and trusted_reload_receipt(ack_file)==expected
    observed=hashlib.sha256(config_raw).hexdigest()
    if expected["config_sha256"]!=observed:
        baseline=dict(config);baseline["templates"]={name:config["templates"][name] for name in expected["retained_templates"]}
        baseline_raw=(json.dumps(baseline,sort_keys=True,indent=2)+"\n").encode()
        if hashlib.sha256(baseline_raw).hexdigest()!=expected["config_sha256"]:
            raise ValueError("installed runner config differs from reload receipt")
    if not acknowledged:write_reload_ack(ack_path,expected)
    return True
def reload_templates(pinned,fresh,pinned_policy,fresh_policy,config_sha256,receipt_path="/etc/loop-runner/base-refresh-receipt.json",ack_path="/var/lib/loop-runner/base-refresh-ack.json",template_receipt_root="/etc/loop-runner/template-receipts"):
    if not isinstance(fresh,dict):raise ValueError("runner templates unavailable")
    changed={name for name in set(pinned)&set(fresh) if pinned[name]!=fresh[name]}
    if changed:raise ValueError("runner template registry changed existing authority")
    removed=sorted(set(pinned)-set(fresh))
    if pinned_policy is None and fresh_policy is None:
        if removed:raise ValueError("runner template registry removed finite authority")
        return dict(fresh),None
    if pinned_policy is None or fresh_policy is None:raise ValueError("runner policy mode changed without restart")
    for name in sorted(set(fresh)-set(pinned)):trusted_template_binding(name,fresh[name],fresh_policy,template_receipt_root)
    if removed or fresh_policy!=pinned_policy:
        receipt=trusted_reload_receipt(receipt_path)
        required={"old_policy_fingerprint","new_policy_fingerprint","new_head","bundle_sha256","removed_templates","retained_templates","config_sha256"}
        if (not isinstance(receipt,dict) or set(receipt)!=required or receipt["old_policy_fingerprint"]!=pinned_policy
                or receipt["new_policy_fingerprint"]!=fresh_policy or receipt["removed_templates"]!=removed
                or not isinstance(receipt["retained_templates"],dict)
                or not re.fullmatch(r"[0-9a-f]{40}",str(receipt["new_head"]))
                or not re.fullmatch(r"[0-9a-f]{64}",str(receipt["bundle_sha256"]))
                or receipt["config_sha256"]!=config_sha256 or not re.fullmatch(r"[0-9a-f]{64}",str(config_sha256))):
            raise ValueError("runner base reload receipt mismatch")
        validate_continuous_additions(fresh,receipt["retained_templates"],fresh_policy,template_receipt_root)
        ack={"new_policy_fingerprint":fresh_policy,"config_sha256":config_sha256,
             "removed_templates":removed,"retained_templates":receipt["retained_templates"],
             "new_head":receipt["new_head"],"bundle_sha256":receipt["bundle_sha256"]}
        write_reload_ack(ack_path,ack)
    return dict(fresh),fresh_policy
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True);parser.add_argument("--job");parser.add_argument("--serve",action="store_true");parser.add_argument("--recover-push");args=parser.parse_args()
    config_raw=Path(args.config).read_bytes();config=json.loads(config_raw); bridge=JsonHTTP(config["bridge_url"],secret(config["runner_token_file"]),trusted_bridge=True)
    if args.recover_push:
        print(json.dumps(recover_push(bridge,args.recover_push,config["evidence_root"])));return
    if args.serve:
        # Consumer only: Paperclip remains the Director scheduler.
        pinned_templates=dict(config.get("templates",{}))
        pinned_policy=config.get("continuous_policy_fingerprint")
        if pinned_policy is not None and not re.fullmatch(r"[0-9a-f]{64}",str(pinned_policy)):raise ValueError("runner policy fingerprint invalid")
        if pinned_policy is not None:acknowledge_installed_refresh(config_raw,config)
        while True:
            job_id=None
            try:
                fresh_raw=Path(args.config).read_bytes();fresh=json.loads(fresh_raw)
                fresh_templates=fresh.get("templates")
                pinned_templates,pinned_policy=reload_templates(pinned_templates,fresh_templates,pinned_policy,
                    fresh.get("continuous_policy_fingerprint"),hashlib.sha256(fresh_raw).hexdigest())
                config=fresh
                job_id=bridge.call("GET","/v1/runner/jobs/next").get("job_id")
                if job_id: DeliveryRunner(config,bridge).run(job_id)
            except Exception:
                if job_id:
                    try: bridge.call("POST",f"/v1/runner/jobs/{job_id}/fail",{})
                    except Exception: pass
            time.sleep(10)
    if not args.job: parser.error("--job or --serve is required")
    try: print(json.dumps(DeliveryRunner(config,bridge).run(args.job)))
    except Exception: raise SystemExit("runner stopped; no success claimed; reconcile existing job before retry") from None
if __name__=="__main__": main()
