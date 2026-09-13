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


def test_known_rejection_is_explained_and_safe_retry_keeps_same_intent(tmp_path):
    from tools.loop.bridge import BridgeError
    class RejectOnce(Bridge):
        def call(self,*args):
            self.calls.append(args)
            if len(self.calls)==1:raise BridgeError(409,"dispatch paused",False)
            return {"run_id":"fixture-run","status":"running"}
    tg,b=Telegram(),RejectOnce();i=Ingress(tmp_path/"i.db",tg,b,[10],[20]);i.ingest([update()]);i.process()
    assert "отклонена" in tg.calls[0][1]["text"]
    assert i.retry_rejected(1);i.process()
    assert b.calls[0][-1]==b.calls[1][-1]=={"Idempotency-Key":"telegram-1"}
    assert not i.retry_rejected(1)


def test_actual_http_known_bridge_503_is_rejected_and_retryable_but_vendor_503_is_uncertain(tmp_path,monkeypatch):
    import threading
    from collections import namedtuple
    from tools.loop.bridge import JsonHTTP,BridgeError,server
    from tools.tests.test_loop_bridge import setup
    import tools.loop.bridge as module
    b,h,p,o=setup(tmp_path)
    keys={}
    for role in ["operator","gateway","director","runner"]:
        path=tmp_path/(role+".key");path.write_text("fixture-"+role);path.chmod(0o600);keys[role]=str(path)
    http=server(b,{"port":0,"credential_files":keys});thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    url=f"http://127.0.0.1:{http.server_port}";Usage=namedtuple("Usage","total used free")
    monkeypatch.setattr(module.shutil,"disk_usage",lambda path:Usage(1000,1000,0))
    tg=Telegram();client=JsonHTTP(url,"fixture-operator",trusted_bridge=True);i=Ingress(tmp_path/"ingress.db",tg,client,[10],[20])
    try:
        i.ingest([update()]);i.process()
        with i.db() as db:assert db.execute("SELECT state FROM updates").fetchone()[0]=="rejected"
        assert "503" in tg.calls[0][1]["text"] and p.calls==[]
        try:JsonHTTP(url,"fixture-operator").call("POST","/v1/wake",{}, {"Idempotency-Key":"vendor-1"})
        except BridgeError as error:assert error.uncertain is True
        else:raise AssertionError("vendor503 must be uncertain")
        monkeypatch.setattr(module.shutil,"disk_usage",lambda path:Usage(10**12,0,10**12))
        assert i.retry_rejected(1);i.process()
        assert p.calls[0][2]["idempotencyKey"]=="telegram-1"
    finally:http.shutdown();http.server_close();thread.join()
