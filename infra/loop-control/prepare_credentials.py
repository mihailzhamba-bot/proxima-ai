"""Initial new-VPS local capability keys. Does not read/copy existing Hermes profiles."""
import argparse
import os
import secrets
from pathlib import Path

def write_new(path,value,uid):
    with open(path,"xb") as f:f.write(value)
    os.chmod(path,0o600);os.chown(path,uid,uid)

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--directory",required=True);parser.add_argument("--postgres-uid",type=int,required=True);args=parser.parse_args()
    if os.getuid()!=0:raise SystemExit("run as operator root on the approved new VPS")
    path=Path(args.directory);path.mkdir(parents=True,exist_ok=True);path.chmod(0o700)
    names={"bridge_operator":10001,"bridge_gateway":10001,"bridge_director":10001,"bridge_runner":10001,"hermes_api":10001,"webapp_context":10001,"postgres_admin":args.postgres_uid,"paperclip_postgres":args.postgres_uid}
    if any((path/n).exists() for n in [*names,"hermes_bridge_director"]):raise SystemExit("credentials exist; refusing overwrite")
    for name,uid in names.items():write_new(path/name,secrets.token_urlsafe(48).encode(),uid)
    write_new(path/"hermes_bridge_director",(path/"bridge_director").read_bytes(),10000)
    print("New private capability files prepared. Supply Board/GitHub/OpenHands/Telegram/model credentials separately.")
if __name__=="__main__":main()
