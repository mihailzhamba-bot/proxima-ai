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
import subprocess
import tempfile
from pathlib import Path
try:
    from .bridge import BridgeError, JsonHTTP, secret
except ImportError:
    from bridge import BridgeError, JsonHTTP, secret

ID=re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")
SHA=re.compile(r"^[a-f0-9]{40}$")
class DeliveryRunner:
    def __init__(self, config, bridge, execute=None):
        self.config,self.bridge=config,bridge
        self.execute=execute or self._execute
        self.env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"HOME":config["trusted_home"],"GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_SYSTEM":"/dev/null","GIT_TERMINAL_PROMPT":"0"}
    def _execute(self,argv,cwd=None):
        result=subprocess.run(argv,cwd=cwd,env=self.env,capture_output=True,text=True,timeout=self.config.get("command_timeout",7200),check=False)
        if result.returncode: raise BridgeError(502,"trusted runner command failed; inspect protected runner log")
        return result.stdout
    def fence(self,job_id): return self.bridge.call("GET",f"/v1/runner/jobs/{job_id}/fence")
    def run(self,job_id):
        if not ID.fullmatch(job_id): raise ValueError("invalid job ID")
        job=self.bridge.call("POST",f"/v1/runner/jobs/{job_id}/claim",{})
        template=self.config["templates"].get(job["template"])
        if not template: raise ValueError("template is not installed on Harper")
        base=template["base_sha"]
        if not SHA.fullmatch(base): raise ValueError("template needs immutable base SHA")
        image=self.config["verification_image"]
        if not re.fullmatch(r"[A-Za-z0-9.:/_-]+@sha256:[a-f0-9]{64}",image): raise ValueError("verification image must be pinned by digest")
        ssh=["ssh","-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","StrictHostKeyChecking=yes","-o","ForwardAgent=no","-i",self.config["worker_identity_file"],self.config["worker_host"]]
        remote=shlex.join([self.config["worker_python"],self.config["worker_dispatcher"],"--config",self.config["worker_config"],"--template",job["template"],"--job",job_id])
        self.fence(job_id)
        receipt=json.loads(self.execute([*ssh,remote]))
        # Handoff receipt checks ancestry and paths; never treated as verification PASS.
        sha=receipt.get("head_sha","")
        if receipt.get("ok") is not True or receipt.get("base_sha")!=base or not SHA.fullmatch(sha) or receipt.get("conversation_id")!=job["external_id"]: raise BridgeError(409,"OpenHands handoff integrity mismatch")
        if receipt.get("branch")!="feat/loop-"+job_id: raise BridgeError(409,"unexpected worker branch")
        self.fence(job_id)
        work=Path(tempfile.mkdtemp(prefix="loop-"+job_id+"-",dir=self.config["work_root"]))
        os.chmod(work,0o755)
        bundle=work/"candidate.bundle"
        remote_bundle=self.config["worker_source"]+f"/logs/openhands-bridge/{job_id}/attempt-1/result.bundle"
        scp=["scp","-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","StrictHostKeyChecking=yes","-o","ForwardAgent=no","-i",self.config["worker_identity_file"],self.config["worker_host"]+":"+shlex.quote(remote_bundle),str(bundle)]
        self.execute(scp)
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
        if not paths or any(protected.search(p) or not any(p==a or (a.endswith("/") and p.startswith(a)) for a in allowed) for p in paths): raise BridgeError(409,"candidate changes protected or unapproved paths")
        # The trusted harness controls command and image. Candidate has no host
        # credentials, Docker socket, network or privileged mount; all checks use
        # disposable writable checkout and preloaded dependencies/fixtures.
        self.execute(["chmod","-R","a+rwX",str(checkout)])
        docker=["docker","run","--rm","--network","none","--memory",self.config.get("memory","6g"),"--cpus",str(self.config.get("cpus",3)),"--pids-limit","512","--cap-drop","ALL","--security-opt","no-new-privileges","--read-only","--tmpfs","/tmp:rw,exec,size=2g","--user","1000:1000","-v",str(checkout)+":/work:rw","-v",self.config["fixture_root"]+":/work/fixtures/wb-api:ro","-w","/work",image]
        # This entrypoint is baked into the trusted verification image, NOT read
        # from the candidate. It executes make verify/build and validates PG PASS
        # and no unacknowledged skips, then emits the actual command receipts.
        checks=json.loads(self.execute([*docker,"python3","/opt/loop/verify_candidate.py",sha]))
        if checks!={"verify":{"sha":sha,"status":"pass","skipped":0},"build":{"sha":sha,"status":"pass","skipped":0}}: raise BridgeError(409,"verification incomplete")
        self.fence(job_id)
        reviewer=self.config["reviewer_command"]
        if not isinstance(reviewer,list) or not reviewer or not Path(reviewer[0]).is_absolute(): raise ValueError("reviewer must be a trusted absolute executable")
        review=json.loads(self.execute([*reviewer,str(checkout),base,sha]))
        if review!={"sha":sha,"status":"pass","skipped":0}: raise BridgeError(409,"independent review blocked")
        report={"producer":"harper","sha":sha,"checks":{**checks,"review":review}}
        evidence=Path(self.config["evidence_root"])/job_id
        evidence.mkdir(parents=True,exist_ok=True)
        (evidence/"verification.json").write_text(json.dumps(report,indent=2)+"\n")
        self.fence(job_id)
        # Publish from a new bare repository never mounted in the candidate sandbox.
        publish=work/"publish.git"
        self.execute([*git,"init","--bare",str(publish)])
        self.execute([*git,"-C",str(publish),"fetch",str(bundle),f"refs/heads/feat/loop-{job_id}:refs/heads/feat/loop-{job_id}"])
        self.execute([*git,"-C",str(publish),"push",self.config["publish_remote"],f"refs/heads/feat/loop-{job_id}:refs/heads/feat/loop-{job_id}"])
        # Bridge holds its publication fence while checking GitHub's actual ref
        # and creating/recovering the PR. No merge/deploy path exists.
        return self.bridge.call("POST",f"/v1/runner/jobs/{job_id}/publish",report)

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True);parser.add_argument("--job",required=True);args=parser.parse_args()
    config=json.loads(Path(args.config).read_text()); bridge=JsonHTTP(config["bridge_url"],secret(config["runner_token_file"]))
    try: print(json.dumps(DeliveryRunner(config,bridge).run(args.job)))
    except Exception: raise SystemExit("runner stopped; no success claimed; reconcile existing job before retry") from None
if __name__=="__main__": main()
