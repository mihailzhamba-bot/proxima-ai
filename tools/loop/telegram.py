"""Dedicated LOOP Telegram ingress. No live bot credentials are bundled.
Only explicitly allowed sender AND chat IDs can invoke deterministic Bridge commands.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.request import Request, build_opener
try:
    from .bridge import JsonHTTP, NoRedirect, secret, BridgeError
except ImportError:
    from bridge import JsonHTTP, NoRedirect, secret, BridgeError

class Telegram:
    def __init__(self,token):self.token=token
    def call(self,method,payload):
        if method not in {"getUpdates","sendMessage"}:raise ValueError("method denied")
        request=Request("https://api.telegram.org/bot"+self.token+"/"+method,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
        try:
            with build_opener(NoRedirect()).open(request,timeout=45) as response:
                result=json.loads(response.read(1_000_000))
                if result.get("ok") is not True:raise ValueError()
                return result["result"]
        except Exception:raise RuntimeError("Telegram unavailable; reply state preserved") from None

class Ingress:
    def __init__(self,path,telegram,bridge,users,chats,webapp_url=None):
        self.path,self.telegram,self.bridge=str(path),telegram,bridge
        self.users,self.chats=set(users),set(chats);self.webapp_url=webapp_url
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.executescript("CREATE TABLE IF NOT EXISTS cursor (id INTEGER PRIMARY KEY CHECK(id=1), offset INTEGER NOT NULL); INSERT OR IGNORE INTO cursor VALUES(1,0); CREATE TABLE IF NOT EXISTS updates (id INTEGER PRIMARY KEY, chat INTEGER NOT NULL, text TEXT NOT NULL,state TEXT NOT NULL,reply TEXT);")
            db.execute("UPDATE updates SET state='execution_unknown' WHERE state='executing'")
            db.execute("UPDATE updates SET state='delivery_unknown' WHERE state='replying'")
        os.chmod(path,0o600)
    def db(self):return sqlite3.connect(self.path)
    def ingest(self,updates):
        with self.db() as db:
            for update in updates:
                uid=update.get("update_id")
                if not isinstance(uid,int):continue
                message=update.get("message",{});sender=message.get("from",{}).get("id");chat=message.get("chat",{}).get("id");text=message.get("text","")
                if sender in self.users and chat in self.chats and isinstance(text,str) and 0<len(text)<=4000:
                    db.execute("INSERT OR IGNORE INTO updates VALUES(?,?,?,'queued',NULL)",(uid,chat,text))
                db.execute("UPDATE cursor SET offset=max(offset,?) WHERE id=1",(uid+1,))
    def command(self,uid,text):
        text=text.strip()
        if text=="/status":
            result=self.bridge.call("GET","/v1/status")
            return "Режим LOOP: "+result.get("mode","UNKNOWN")+". Работа стенда "+("подтверждена." if result.get("live_ready") else "ещё не подтверждена.")
        if text in {"/pause","/resume"}:
            result=self.bridge.call("POST","/v1"+text,{})
            return "Новые запуски приостановлены." if result.get("paused") else "Приём новых запусков включён."
        if text=="/brief" and self.webapp_url:return "Решения и задачи кабинета: "+self.webapp_url.rstrip("/")+"/brief"
        if text.startswith("/wake "):
            result=self.bridge.call("POST","/v1/wake",{"source":"telegram","source_id":str(uid),"text":text[6:]},{"Idempotency-Key":"telegram-"+str(uid)})
            return "Событие принято Paperclip. Запуск: "+result["run_id"]+". Статус: "+result["status"]+"."
        if match:=re.fullmatch(r"/stop ([a-f0-9-]{36})",text):
            result=self.bridge.call("POST","/v1/runs/"+match[1]+"/stop",{})
            return "Остановка подтверждена." if result.get("status")=="cancelled" else "Остановка запрошена. Подтверждение ещё ожидается."
        return "Команды: /status, /brief, /wake текст, /pause, /resume, /stop ID. Решение по товару подтверждается в личном кабинете."
    def retry_rejected(self,uid):
        with self.db() as db: changed=db.execute("UPDATE updates SET state='queued' WHERE id=? AND state='rejected'",(uid,)).rowcount
        return bool(changed)
    def process(self):
        with self.db() as db:rows=db.execute("SELECT id,chat,text FROM updates WHERE state='queued' ORDER BY id").fetchall()
        for uid,chat,text in rows:
            with self.db() as db:changed=db.execute("UPDATE updates SET state='executing' WHERE id=? AND state='queued'",(uid,)).rowcount
            if not changed:continue
            outcome="replied"
            try:reply=self.command(uid,text)
            except BridgeError as exc:
                if exc.uncertain:
                    with self.db() as db:db.execute("UPDATE updates SET state='execution_unknown' WHERE id=?",(uid,))
                    continue
                outcome="rejected"
                reply=f"Команда отклонена (HTTP {exc.status}). Запуск не подтверждён. Проверьте паузу, доступ и данные команды."
            except Exception:
                with self.db() as db:db.execute("UPDATE updates SET state='execution_unknown' WHERE id=?",(uid,))
                continue
            with self.db() as db:db.execute("UPDATE updates SET state='replying',reply=? WHERE id=?",(reply,uid))
            try:
                self.telegram.call("sendMessage",{"chat_id":chat,"text":reply})
                with self.db() as db:db.execute("UPDATE updates SET state=? WHERE id=?",(outcome,uid))
            except Exception:
                with self.db() as db:db.execute("UPDATE updates SET state='delivery_unknown' WHERE id=?",(uid,))
    def poll_once(self):
        with self.db() as db:offset=db.execute("SELECT offset FROM cursor WHERE id=1").fetchone()[0]
        updates=self.telegram.call("getUpdates",{"offset":offset,"timeout":30,"limit":100,"allowed_updates":["message"]})
        self.ingest(updates);self.process()

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--config",required=True);parser.add_argument("--retry-update",type=int);args=parser.parse_args()
    config=json.loads(Path(args.config).read_text())
    if not config["allowed_user_ids"] or not config["allowed_chat_ids"]:raise SystemExit("explicit Telegram allowlists required")
    bridge=JsonHTTP(config["bridge_url"],secret(config["operator_token_file"]),trusted_bridge=True)
    bot=Ingress(config["database"],Telegram(secret(config["bot_token_file"])),bridge,config["allowed_user_ids"],config["allowed_chat_ids"],config.get("webapp_url"))
    if args.retry_update is not None:
        if not bot.retry_rejected(args.retry_update):raise SystemExit("only a definitely rejected command can be retried")
        bot.process();return
    while True:
        try:bot.poll_once()
        except Exception:time.sleep(10)
if __name__=="__main__":main()
