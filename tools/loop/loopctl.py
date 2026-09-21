"""Operator CLI. Credentials are read from private files, never command arguments."""
import argparse
import json
import sys
from pathlib import Path
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from .bridge import JsonHTTP, secret, BridgeError
except ImportError:
    from bridge import JsonHTTP, secret, BridgeError

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True)
    parser.add_argument("command",choices=["status","wake","pause","resume","stop","events","adopt","recover-pr","recover-worker","settle-publication"])
    parser.add_argument("--id");parser.add_argument("--key");parser.add_argument("--input-file");parser.add_argument("--external-id");parser.add_argument("--evidence-ref");args=parser.parse_args()
    config=json.loads(Path(args.config).read_text());client=JsonHTTP(config["bridge_url"],secret(config["operator_token_file"]),trusted_bridge=True)
    if args.command=="status": method,path,payload="GET","/v1/status",None
    elif args.command in {"pause","resume"}:method,path,payload="POST","/v1/"+args.command,{}
    elif args.command=="wake":
        if not args.key or not args.input_file:parser.error("wake needs stable --key and --input-file")
        method,path,payload="POST","/v1/wake",json.loads(Path(args.input_file).read_text())
    else:
        if not args.id:parser.error("command needs --id")
        if args.command=="settle-publication":
            if not args.evidence_ref:parser.error("settlement requires an operator evidence reference")
            method,path,payload="POST",f"/v1/jobs/{args.id}/settle-publication",{"evidence_ref":args.evidence_ref}
        elif args.command=="recover-worker":
            if not args.input_file:parser.error("recover-worker needs an independently checked existing handoff receipt")
            method,path,payload="POST",f"/v1/jobs/{args.id}/recover-worker",json.loads(Path(args.input_file).read_text())
        elif args.command=="recover-pr":method,path,payload="POST",f"/v1/jobs/{args.id}/recover-pr",{}
        elif args.command=="adopt":
            if not args.external_id:parser.error("adopt needs independently verified --external-id")
            method,path,payload="POST",f"/v1/runs/{args.id}/adopt",{"external_id":args.external_id}
        else:method,path,payload=("GET" if args.command=="events" else "POST"),f"/v1/runs/{args.id}/"+("events" if args.command=="events" else "stop"),{}
    try: print(json.dumps(client.call(method,path,payload,{"Idempotency-Key":args.key} if args.key else None)))
    except BridgeError as e:raise SystemExit(e.message) from None
if __name__=="__main__":main()
