#!/usr/bin/python3 -I
"""Closed Telegram sender for the continuous 08:00 report."""
import argparse,json,os,stat,sys
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parent))
from bridge import secret
from telegram import Telegram
def read_bounded(fd=0,limit=1_000_000):
 chunks=[];total=0
 while True:
  chunk=os.read(fd,min(65536,limit+1-total))
  if not chunk:break
  chunks.append(chunk);total+=len(chunk)
  if total>limit:raise ValueError("input too large")
 return b"".join(chunks)
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--config",required=True,type=Path);args=parser.parse_args()
 info=args.config.lstat()
 if args.config.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600:raise ValueError("untrusted report config")
 config=json.loads(args.config.read_text())
 if set(config)!={"bot_token_file","chat_id"} or not isinstance(config["chat_id"],int):raise ValueError("invalid report config")
 payload=json.loads(read_bounded(limit=10000))
 if set(payload)!={"text","day","digest"} or not isinstance(payload["text"],str) or len(payload["text"])>4000:raise ValueError("invalid report")
 result=Telegram(secret(config["bot_token_file"])).call("sendMessage",{"chat_id":config["chat_id"],"text":payload["text"]})
 print(json.dumps({"message_id":result.get("message_id"),"day":payload["day"],"digest":payload["digest"]}));return 0
if __name__=="__main__":raise SystemExit(main())
