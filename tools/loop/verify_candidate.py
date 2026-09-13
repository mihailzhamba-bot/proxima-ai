"""Bake at /opt/loop/verify-candidate in Harper's trusted image (never bind from candidate)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

def main():
    sha=sys.argv[1]
    if not re.fullmatch(r"[0-9a-f]{40}",sha): raise SystemExit(2)
    env={**os.environ,"PUPPETEER_SKIP_DOWNLOAD":"1","USER":"ubuntu"}
    results={}
    for name,cmd in [("verify",["make","verify"]),("build",["npm","--workspace","@proxima/webapp","run","build"])]:
        process=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=5400)
        log=process.stdout+process.stderr
        Path("/tmp/loop-"+name+".log").write_text(log)
        if process.returncode or (name=="verify" and "pg-roundtrip: PASS" not in log): raise SystemExit("check failed: "+name)
        # Unit suites intentionally skip DB cases without their DSNs; the later
        # pg-roundtrip must execute these cases. Its own skip gate is mandatory.
        if name=="verify" and ("pg-roundtrip: SKIP" in log or "pg-roundtrip: FAIL" in log): raise SystemExit("DB checks incomplete")
        results[name]={"sha":sha,"status":"pass","skipped":0}
    actual=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
    if actual!=sha:raise SystemExit("candidate SHA changed")
    print(json.dumps(results))
if __name__=="__main__":main()
