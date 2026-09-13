"""Prepare exact upstream checkouts on Harper; never run on LOOP-control."""
import argparse
import json
import socket
import subprocess
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--destination",required=True);parser.add_argument("--harper-hostname",required=True);args=parser.parse_args()
    if socket.gethostname()!=args.harper_hostname:raise SystemExit("Harper host identity mismatch")
    lock=json.loads(Path(__file__).with_name("versions.lock.json").read_text())
    target=Path(args.destination);target.mkdir(parents=True,exist_ok=True)
    for name in ("paperclip","hermes"):
        info=lock[name];path=target/name
        if path.exists():raise SystemExit("destination exists; inspect instead of overwriting")
        subprocess.run(["git","clone","--no-checkout",info["repository"],str(path)],check=True)
        subprocess.run(["git","-C",str(path),"checkout","--detach",info["commit"]],check=True)
        actual=subprocess.check_output(["git","-C",str(path),"rev-parse","HEAD"],text=True).strip()
        if actual!=info["commit"]:raise SystemExit("pin mismatch")
        (path/".loop-source-pin.json").write_text(json.dumps({"commit":actual,"repository":info["repository"]})+"\n")
    print("Exact sources prepared. Build dedicated LOOP Dockerfiles on Harper; record image digests before deployment.")
if __name__=="__main__":main()
