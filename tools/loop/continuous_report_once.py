#!/usr/bin/python3 -I
"""Send the deduplicated 08:00 Moscow continuous queue report only."""
import argparse,json,sys,time
from pathlib import Path
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parent))
from bridge import JsonHTTP,secret
from continuous_report import Reporter
from night_batch import json_file
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--config",required=True,type=Path);args=parser.parse_args()
 config=json_file(args.config);client=JsonHTTP(config["bridge_url"],secret(config["bridge_key_file"]),trusted_bridge=True)
 result=Reporter(config["report"]).run(client.call("GET","/v1/queue"),time.time())
 print(json.dumps(result));return 0 if result["status"] in {"sent","deduplicated","not_due"} else 1
if __name__=="__main__":raise SystemExit(main())
