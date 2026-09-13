import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.evaluate_director import grade,evaluate
ROOT=Path(__file__).resolve().parents[2]
def test_goal_sources_and_control_are_scored_independently():
    case=json.loads((ROOT/"infra/loop-control/director-eval-cases.json").read_text())[0]
    answer={"goal":case["goal"],"facts":case["allowed_facts"],"hypotheses":[],"unknowns":["Причина"],"executor":case["executor"],"owner_approval_required":True,"publication_allowed":False,"effect_proven":False}
    assert grade(case,answer)["score"]==6
    answer["facts"]=[{"claim":"Invented 99 sales","source_ref":"fake"}];answer["publication_allowed"]=True
    result=grade(case,answer);assert result["score"]==4;assert result["checks"]["sources"] is False;assert result["checks"]["publication_control"] is False

def test_unconfigured_comparison_makes_no_model_calls():
    with pytest.raises(ValueError,match="two authorized"):evaluate({"candidates":[]},[])


def test_duplicate_facts_and_numeric_text_cannot_bypass_grounding():
    case={"goal":"g","executor":None,"allowed_facts":[{"claim":"one","source_ref":"a"},{"claim":"two","source_ref":"b"}]}
    answer={"goal":"g","executor":None,"facts":[case["allowed_facts"][0]]*2,"hypotheses":[],"unknowns":["Unknown"],"owner_approval_required":True,"publication_allowed":False,"effect_proven":False}
    assert grade(case,answer)["checks"]["sources"] is False
    answer["facts"]=case["allowed_facts"];answer["unknowns"]=["Sales grew 99%"]
    assert grade(case,answer)["checks"]["sources"] is False

@pytest.mark.parametrize("mode",["completed","invalid_json","timeout"])
def test_two_configured_models_use_real_gateway_routes_and_preserve_identity_boundary(tmp_path,mode):
    import threading
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    calls=[];outputs={}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,value,status=200):
            raw=json.dumps(value).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(raw)
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))) or b"{}")
            if self.path.endswith("/stop"):calls.append(("stop",None));self.send({});return
            calls.append(("create",body["model"]))
            case=json.loads(body["input"]);run=str(len(outputs)+1)
            outputs[run]={"goal":case["goal"],"facts":case["facts"],"hypotheses":[],"unknowns":["Cause unverified"],"executor":case["executor"],"owner_approval_required":True,"publication_allowed":False,"effect_proven":False}
            self.send({"run_id":run},202)
        def do_GET(self):
            run=self.path.rsplit("/",1)[-1]
            self.send({"status":"completed","model":"hermes-agent","output":"bad json" if mode=="invalid_json" else json.dumps(outputs[run])})
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    key=tmp_path/"token";key.write_text("fixture-eval-key");key.chmod(0o600)
    config={"timeout_seconds":0 if mode=="timeout" else 2,"candidates":[{"name":name,"model_id":name,"gateway_url":f"http://127.0.0.1:{server.server_port}","token_file":str(key)} for name in ["fixture-model-a","fixture-model-b"]]}
    case=json.loads((ROOT/"infra/loop-control/director-eval-cases.json").read_text())[0]
    try:report=evaluate(config,[case])
    finally:server.shutdown();server.server_close();thread.join()
    assert [value for action,value in calls if action=="create"]==["fixture-model-a","fixture-model-b"]
    assert all(row["model_identity_verified"] is False and row["observed_provider_model_id"] is None for row in report["results"])
    assert all(row["score"]==(6 if mode=="completed" else 0) for row in report["results"])
    if mode=="timeout":assert len([1 for action,_ in calls if action=="stop"])==2
