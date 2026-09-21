"""Offline readiness gate; passing this does not claim a live run."""
import argparse
import ipaddress
import json
import re
from pathlib import Path

def check(config):
    missing=[]
    try: ip=ipaddress.ip_address(config.get("control_vps_ip",""))
    except ValueError:missing.append("new_control_vps_ip");ip=None
    if ip and str(ip) in {"153.56.134.240","135.106.186.210","135.106.211.64"}:missing.append("dedicated_control_vps_required")
    if config.get("control_vps_approved") is not True or not config.get("approval_ref"):missing.append("explicit_control_vps_approval")
    for name in ("paperclip","hermes","bridge","postgres","verification"):
        value=config.get("images",{}).get(name) or ""
        if not re.fullmatch(r"[A-Za-z0-9.:/_-]+@sha256:[a-f0-9]{64}",value):missing.append("image_digest:"+name)
    for role in ("operator","gateway","director","runner"):
        p=Path(config.get("credential_files",{}).get(role,"/nonexistent"))
        if not p.is_file() or p.stat().st_mode & 0o077:missing.append("private_credential:"+role)
    if config.get("mode")!="pr_only":missing.append("pr_only_required")
    return {"package_ready":not missing,"live_ready":False,"missing":missing,"live_acceptance":"separate runtime check required"}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("config");args=parser.parse_args()
    result=check(json.loads(Path(args.config).read_text()));print(json.dumps(result,indent=2));raise SystemExit(0 if result["package_ready"] else 1)
if __name__=="__main__":main()
