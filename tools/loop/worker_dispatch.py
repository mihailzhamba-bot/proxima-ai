"""Install on Claudette as trusted code; uses existing OpenHands handoff unchanged."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True);parser.add_argument("--job",required=True);parser.add_argument("--template",required=True);args=parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}",args.job): raise SystemExit("invalid job")
    config_path=Path(args.config)
    if config_path.stat().st_mode & 0o022: raise SystemExit("templates must not be worker-writable")
    config=json.loads(config_path.read_text()); template=config["templates"].get(args.template)
    if not template: raise SystemExit("unknown template")
    if not re.fullmatch(r"[0-9a-f]{40}",template["base_sha"]): raise SystemExit("base must be immutable SHA")
    root=Path(config["source_repo"])
    if not (root/".git").is_dir(): raise SystemExit("dedicated full source checkout required")
    command=["bash",str(root/"tools/orchestrator/bad_dev_story.sh"),"--source-dir",str(root),"--run-id",args.job,"--branch","feat/loop-"+args.job,"--base-ref",template["base_sha"],"--prompt-file",template["prompt_file"],"--profile",template.get("profile","fedor"),"--attempt","1","--timeout","5400","--max-iterations","100","--keep-workspace"]
    # No incoming shell fragments, paths, flags or secrets. All task choices come
    # from operator-reviewed templates stored outside the worker checkout.
    result=subprocess.run(command,cwd=root,env={**os.environ,"REPO_ROOT":str(root)},timeout=5500)
    raise SystemExit(result.returncode)
if __name__=="__main__":main()
