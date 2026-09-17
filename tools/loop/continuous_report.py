"""Deduplicated 08:00 Moscow continuous queue report."""
from __future__ import annotations
import hashlib,json,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
try:
 from .continuous_admission import command
 from .night_batch import atomic_json,json_file
except ImportError:
 from continuous_admission import command
 from night_batch import atomic_json,json_file
MSK=timezone(timedelta(hours=3))
def render(status):
 current=status.get("current");upcoming=status.get("next");items=status.get("items",[])
 lines=["LOOP очередь WB."]
 if current:
  lines.append("Текущая: "+str(current.get("id"))+" ("+str(current.get("state"))+").")
  lines.append("Последний прогресс: "+datetime.fromtimestamp(current.get("updated",0),MSK).strftime("%d.%m %H:%M МСК")+".")
 else:lines.append("Текущая: нет.")
 lines.append("Следующая: "+(str(upcoming.get("id"))+" ("+str(upcoming.get("state"))+")." if upcoming else "нет."))
 last_pr=next((item for item in sorted(items,key=lambda v:v.get("updated",0),reverse=True) if item.get("pr_url")),None)
 lines.append("Последний PR: "+(str(last_pr["pr_url"]) if last_pr else "нет."))
 final_blockers=[item for item in items if item.get("state") in {"blocked","rejected","cancelled"} and not item.get("lease_id")]
 if final_blockers:
  lines.append("Финальные блокеры: "+"; ".join(str(item.get("id"))+": "+str(item.get("blocker") or item.get("state"))[:120] for item in final_blockers[:3])+".")
 else:lines.append("Финальные блокеры: нет.")
 return "\n".join(lines)
class Reporter:
 def __init__(self,config,execute=None):
  if not isinstance(config,dict) or set(config)!={"state_file","command"} or not Path(config["state_file"]).is_absolute():raise ValueError("invalid report config")
  self.config=config;self.execute=execute
 def run(self,status,now=time.time):
  moment=datetime.fromtimestamp(now,MSK);day=moment.date().isoformat()
  if moment.hour!=8:return {"status":"not_due"}
  path=Path(self.config["state_file"]);path.parent.mkdir(parents=True,exist_ok=True)
  if path.is_symlink():raise ValueError("untrusted report state")
  if path.exists():
   saved=json_file(path)
   if saved.get("day")==day:return {"status":"deduplicated"}
  text=render(status);digest=hashlib.sha256(text.encode()).hexdigest()
  atomic_json(path,{"day":day,"digest":digest,"state":"sending"})
  try:
   result=command(self.config["command"],{"text":text,"day":day,"digest":digest},self.execute) if self.execute else command(self.config["command"],{"text":text,"day":day,"digest":digest})
  except Exception:
   atomic_json(path,{"day":day,"digest":digest,"state":"unknown"});return {"status":"unknown"}
  atomic_json(path,{"day":day,"digest":digest,"state":"sent","receipt":result})
  return {"status":"sent"}
