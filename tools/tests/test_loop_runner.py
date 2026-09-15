from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.bridge import Bridge, BridgeError
from tools.loop.runner import DeliveryRunner,prepare_mountpoints,restore_tracked_modes

class Remote:
    def call(self,method,path,payload=None,headers=None):return {"id":"remote-run","status":"running"}
class Client:
    def __init__(self,b):self.b=b
    def call(self,method,path,payload=None,headers=None):
        job=path.split("/")[4]
        if path.endswith("/claim"):return self.b.claim_job(job)
        if path.endswith("/begin-publication"):return self.b.begin_publication(job,payload)
        if path.endswith("/start-push"):return self.b.start_push(job,payload)
        if path.endswith("/record-push"):return self.b.record_push(job,payload)
        if path.endswith("/finish-publication"):return self.b.finish_publication(job,payload["permit"])
        return self.b.fence(job)

def setup(tmp_path,fail_checks=False,changed="services/webapp/src/lib/rub.ts",cancel_before_publish=False,cancel_after_start_push=False):
    published=[];remote=Remote();b=Bridge(tmp_path/"bridge.sqlite",remote,remote,"director",publisher=lambda job,sha:published.append(sha) or "https://github.com/fixture/repo/pull/1")
    sha="a"*40;base="b"*40;template={"base_sha":base,"allowed_paths":["services/webapp/src/lib/"],"profile":"fedor","profile_id":"11111111-1111-4111-8111-111111111111","profile_revision":3}
    r=b.create("hermes","pc-run",{"input":"task","instructions":"scope","session_id":"session"})["run_id"]
    b.propose_job({"job_id":"job-1","run_id":r,"generation":1,"template":"fixture"},{"fixture":template})
    bundle_bytes=b"fixture candidate bundle";bundle_sha=__import__("hashlib").sha256(bundle_bytes).hexdigest()
    config={"trusted_home":str(tmp_path),"worker_identity_file":"/fixture/key","github_publish_identity_file":"/fixture/github-key","known_hosts_file":"/fixture/known-hosts","worker_host":"worker","worker_python":"python3","worker_dispatcher":"/opt/loop/worker_dispatch.py","worker_fetcher":"/opt/loop/worker_fetch","worker_config":"/etc/loop/templates.json","worker_source":"/srv/loop/source","work_root":str(tmp_path),"source_repo":"/fixture/source","fixture_root":"/fixture/data","evidence_root":str(tmp_path/"evidence"),"verification_image":"fixture/verify@sha256:"+"1"*64,"reviewer_command":["/opt/reviewer"],"publish_remote":"git@fixture:repo","templates":{"fixture":template}}
    calls=[]
    def execute(argv,cwd=None):
        calls.append(argv)
        if argv[0]=="ssh":return json.dumps({"ok":True,"template":"fixture","template_fingerprint":b.job("job-1")["template_fingerprint"],"head_sha":sha,"base_sha":base,"conversation_id":b.job("job-1")["external_id"],"branch":"feat/loop-job-1","bundle_sha256":bundle_sha,"worker_says":"PASS"})
        if "clone" in argv:
            checkout=Path(argv[-1]);(checkout/"services/webapp").mkdir(parents=True);(checkout/"services/webapp/next-env.d.ts").write_text("fixture declaration")
        if "rev-parse" in argv:return sha+"\n"
        if "--name-only" in argv:return changed+"\n"
        if "ls-tree" in argv:return "100644 blob "+"a"*40+"\tservices/webapp/next-env.d.ts\0"
        if len(argv)>2 and str(argv[2]).endswith("history_gate.py"):
            return json.dumps({"status":"pass","base_sha":base,"head_sha":sha,"commits":1,"changed_paths":1,"scanned_blobs":1,"objects":3})
        if argv[0]=="docker":
            assert "--network" in argv and argv[argv.index("--network")+1]=="none"
            assert not any("docker.sock" in value for value in argv)
            if fail_checks:raise BridgeError(409,"independent verifier failed")
            return json.dumps({"status":"pass","checks":{argv[-1]:{"sha":sha,"status":"pass","skipped":0}},"logs":{argv[-1]:"fixture log"}})
        if argv[0]=="/opt/reviewer":
            if cancel_before_publish:
                with b.tx() as db:db.execute("UPDATE operations SET generation=2,state='cancelled' WHERE id=?",(r,))
            return json.dumps({"sha":sha,"status":"pass","skipped":0})
        if argv[0]=="git" and "push" in argv and cancel_after_start_push:
            b.cancel(r)
        return ""
    def fetch(argv,destination):
        calls.append(argv);Path(destination).write_bytes(bundle_bytes)
    return DeliveryRunner(config,Client(b),execute,identity_reader=lambda pid:"fixture-process",fetch_execute=fetch),b,calls,published

def test_same_delivery_path_reaches_ready_pr_after_real_runner_receipts(tmp_path):
    runner,b,calls,published=setup(tmp_path)
    assert runner.run("job-1")["state"]=="ready_pr"
    assert len(published)==1
    assert any(c[0]=="docker" for c in calls)
    assert any(c[0]=="/opt/reviewer" for c in calls)
    assert any(c[0]=="ssh" and "/opt/loop/worker_fetch" in c[-1] for c in calls)
    assert not any(c[0]=="scp" for c in calls)
    assert any("push" in c for c in calls)
    publication_fetches=[c for c in calls if "fetch" in c and any(str(a).endswith("publish.git") for a in c)]
    assert publication_fetches[0][-2:]==["/fixture/source","b"*40]
    assert "--no-tags" in publication_fetches[0]
    assert publication_fetches[1][-1]=="refs/heads/feat/loop-job-1:refs/heads/feat/loop-job-1"
    with pytest.raises(BridgeError):runner.run("job-1")

def test_worker_pass_never_overrides_failed_independent_checks(tmp_path):
    runner,b,calls,published=setup(tmp_path,fail_checks=True)
    with pytest.raises(BridgeError):runner.run("job-1")
    assert published==[];assert not any("push" in c for c in calls)

def test_cancelled_old_attempt_cannot_publish_late_success(tmp_path):
    runner,b,calls,published=setup(tmp_path,cancel_before_publish=True)
    with pytest.raises(BridgeError):runner.run("job-1")
    assert published==[];assert not any("push" in c for c in calls)

def test_cancel_after_start_push_can_only_write_staging_ref(tmp_path):
    runner,b,calls,published=setup(tmp_path,cancel_after_start_push=True)
    assert runner.run("job-1")["state"]=="cancelled"
    pushes=[args for args in calls if args[0]=="git" and "push" in args]
    assert len(pushes)==1
    source,destination=pushes[0][-1].split(":",1)
    assert source=="refs/heads/feat/loop-job-1"
    assert destination.startswith("refs/heads/loop-staging/job-1/")
    assert len(destination.rsplit("/",1)[-1])==64
    assert b.job("job-1")["publication_permit"] not in destination
    assert destination!="refs/heads/feat/loop-job-1"
    assert published==[]
    assert b.job("job-1")["state"]=="cancelled"

def test_candidate_cannot_rewrite_its_own_verifier(tmp_path):
    runner,b,calls,published=setup(tmp_path,changed="Makefile")
    with pytest.raises(BridgeError):runner.run("job-1")
    assert published==[];assert not any(c[0]=="docker" for c in calls)


def test_all_stages_preserve_dependency_mounts_and_build_adds_only_declaration_overlay(tmp_path):
    runner,b,calls,_=setup(tmp_path);runner.run("job-1")
    stages={argv[-1]:argv for argv in calls if argv[0]=="docker"}
    for stage,args in stages.items():
        expected=":rw" if stage=="prepare" else ":ro"
        for name in ["node_modules","services/webapp/node_modules","services/collector/node_modules","services/control-plane/.venv"]:
            assert any(value.endswith(":/work/"+name+expected) for value in args)
        assert any(value.endswith(":/work:ro") for value in args)
    assert any(value.endswith(":/work/services/webapp/next-env.d.ts:rw") for value in stages["build"])


def test_fresh_git_mountpoints_are_precreated_without_covering_source(tmp_path):
    import subprocess
    root=tmp_path/"checkout";root.mkdir();(root/"source.txt").write_text("source")
    subprocess.run(["git","init","-q",str(root)],check=True);subprocess.run(["git","-C",str(root),"add","source.txt"],check=True)
    tracked=subprocess.check_output(["git","-C",str(root),"ls-files","-z"],text=True).split("\0")
    targets=["build","node_modules","services/webapp/node_modules","services/webapp/.next","services/collector/dist","services/control-plane/.venv","fixtures/wb-api"]
    prepare_mountpoints(root,targets,["services/webapp/tsconfig.tsbuildinfo"],tracked)
    assert all((root/value).is_dir() for value in targets)
    assert (root/"services/webapp/tsconfig.tsbuildinfo").is_file()
    assert (root/"source.txt").read_text()=="source"
    assert subprocess.check_output(["git","-C",str(root),"ls-files","-z"],text=True).split("\0")==tracked

@pytest.mark.parametrize("kind",["tracked","symlink","escape","parent_file","nonempty"])
def test_mountpoint_preparation_rejects_unexpected_targets(tmp_path,kind):
    root=tmp_path/"checkout";root.mkdir();tracked=[];target="build"
    if kind=="tracked":tracked=["build/source.js"]
    elif kind=="symlink":(root/"build").symlink_to(tmp_path,target_is_directory=True)
    elif kind=="escape":target="../outside"
    elif kind=="parent_file":(root/"services").write_text("source");target="services/webapp/node_modules"
    elif kind=="nonempty":(root/"build").mkdir();(root/"build/private").write_text("retain")
    with pytest.raises(ValueError):prepare_mountpoints(root,[target],[],tracked)


def test_vite_overlays_are_bounded_and_created_only_after_prepare(tmp_path):
    runner,b,calls,_=setup(tmp_path);runner.run("job-1")
    stages={args[-1]:args for args in calls if args[0]=="docker"}
    for stage in ("verify","build"):
        for dependency in ("node_modules","services/webapp/node_modules"):
            assert any(arg.endswith(":/work/"+dependency+":ro") for arg in stages[stage])
            for name in (".vite-temp",".vite"):
                suffix=":/work/"+dependency+"/"+name+":rw"
                assert any(arg.endswith(suffix) for arg in stages[stage])
                assert not any(arg.endswith(suffix) for arg in stages["prepare"])


def test_checkout_exec_modes_are_restored_without_changing_bytes(tmp_path):
    script=tmp_path/'script';script.write_text('fixture');script.chmod(0o700)
    restore_tracked_modes(tmp_path,'100755 blob '+'a'*40+'\tscript\0')
    assert script.stat().st_mode & 0o777 == 0o755
    assert script.read_text()=='fixture'
    target=tmp_path/'outside';target.mkdir();(target/'file').write_text('preserve')
    (tmp_path/'redirect').symlink_to(target,target_is_directory=True)
    with pytest.raises(ValueError):restore_tracked_modes(tmp_path,'100644 blob '+'a'*40+'\tredirect/file\0')
