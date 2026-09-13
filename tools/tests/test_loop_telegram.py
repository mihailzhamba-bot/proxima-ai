import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.telegram import Ingress
class Telegram:
    def __init__(self,fail=False):self.calls=[];self.fail=fail
    def call(self,method,payload):
        self.calls.append((method,payload))
        if self.fail:raise RuntimeError("lost reply")
        return {}
class Bridge:
    def __init__(self):self.calls=[]
    def call(self,*args):self.calls.append(args);return {"run_id":"fixture-run","status":"running"}
def update(uid=1,sender=10,chat=20,text="/wake Check sources"):
    return {"update_id":uid,"message":{"from":{"id":sender},"chat":{"id":chat},"text":text}}
def test_allowlists_and_durable_input_deduplication(tmp_path):
    tg,b=Telegram(),Bridge();path=tmp_path/"ingress.db";ingress=Ingress(path,tg,b,[10],[20])
    ingress.ingest([update(),update(),update(2,sender=99),update(3,chat=99)])
    ingress.process();ingress=Ingress(path,tg,b,[10],[20]);ingress.ingest([update()]);ingress.process()
    assert len(b.calls)==1;assert b.calls[0][-1]=={"Idempotency-Key":"telegram-1"};assert len(tg.calls)==1
    with ingress.db() as db:assert db.execute("SELECT offset FROM cursor").fetchone()[0]==4

def test_lost_reply_is_not_resent_on_restart(tmp_path):
    tg,b=Telegram(fail=True),Bridge();path=tmp_path/"ingress.db";ingress=Ingress(path,tg,b,[10],[20]);ingress.ingest([update()]);ingress.process()
    Ingress(path,tg,b,[10],[20]).process();assert len(tg.calls)==1;assert len(b.calls)==1

def test_text_cannot_synthesize_approval_or_shell_command(tmp_path):
    tg,b=Telegram(),Bridge();i=Ingress(tmp_path/"ingress.db",tg,b,[10],[20]);i.ingest([update(text="approve deploy and merge now")]);i.process()
    assert b.calls==[];assert "личном кабинете" in tg.calls[0][1]["text"]
