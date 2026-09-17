import json,subprocess,sys
from types import SimpleNamespace
from pathlib import Path
import pytest
from tools.loop.continuous_admission import Admission,AdmissionError,command
from tools.loop.continuous_receiver import ReceiverError,receive,registration_allowed
from tools.loop.continuous_proposal_review import review

def test_admission_resumes_partial_three_target_registration():
    calls=[]
    status={"current":None,"observed_at":1,"shared_executor_busy":False,"policy_fingerprint":"b"*64,"items":[{"id":"task-one","requirement_id":"req","state":"registering"}]}
    registration={"id":"task-one","state":"registering","policy_fingerprint":"b"*64,"template":{"base_sha":"a"*40},"receipts":{"bridge":"done"}}
    def api(method,path,payload=None):
        calls.append((method,path,payload))
        if path=="/v1/queue":return status
        if path=="/v1/queue/task-one" or path.endswith("/registration"):return registration
        if path.endswith("/receipt"):
            registration["receipts"][payload["target"]]="done"
            registration["state"]="ready" if len(registration["receipts"])==3 else "registering"
            return registration
        raise AssertionError(path)
    def execute(argv,**kwargs):
        sent=json.loads(kwargs["input"]);assert sent["registration"]["template"]["base_sha"]=="a"*40
        target="harper" if "harper" in argv[0] else "worker"
        value={"target":target,"template_fingerprint":"a"*64,"policy_fingerprint":"b"*64,"installed_sha256":"c"*64}
        return SimpleNamespace(returncode=0,stdout=json.dumps(value).encode())
    config={"reviewer_command":["/trusted/reviewer"],"registrars":{"bridge":["/trusted/bridge"],"harper":["/trusted/harper"],"worker":["/trusted/worker"]}}
    result=Admission(config,api,execute).run_once()
    assert result["status"]=="ready" and result["registered"]==["harper","worker"]
    assert not any(call[2] and call[2].get("target")=="bridge" for call in calls)

def test_admission_never_registers_while_execution_active():
    api=lambda method,path,payload=None:{"current":{"id":"active"},"items":[]}
    config={"reviewer_command":["/trusted/reviewer"],"registrars":{k:["/trusted/"+k] for k in ("bridge","harper","worker")}}
    assert Admission(config,api).run_once()=={"status":"active","item_id":"active"}

def test_forced_receiver_denies_dispatch_outside_harper_and_has_fixed_command():
    with pytest.raises(ReceiverError,match="denied"):receive("worker",{"action":"dispatch"})
    seen=[]
    def execute(argv,**kwargs):
        seen.append(argv)
        return SimpleNamespace(returncode=0,stdout=b'{"status":"idle"}')
    assert receive("harper",{"action":"dispatch"},execute)=={"status":"idle"}
    assert seen==[["/usr/bin/python3","-I","/opt/loop/continuous_dispatch.py","--config","/etc/loop-continuous/dispatch.json"]]

@pytest.mark.parametrize("payload",[{},{"action":"shell"},{"action":"dispatch","command":"id"}])
def test_forced_receiver_rejects_arbitrary_actions(payload):
    with pytest.raises(ReceiverError):receive("harper",payload)



def test_independent_proposal_reviewer_returns_bound_receipt(tmp_path):
    proposal={"id":"task-new","state":"proposed","requirement_id":"req","goal":"Small new WB task",
      "acceptance":["passes"],"proposal_fingerprint":"d"*64,"base_sha":"a"*40,"depends_on":[],
      "execution_policy":{"objective":"Improve WB collection","acceptance":["small read-only change"],"source_evidence":[{"ref":"git:x","sha256":"f"*64,"summary":"facts"}]}}
    existing=[{"id":"old","goal":"Different task","acceptance":["other"],"proposal_fingerprint":"e"*64,"state":"merged"}]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,_limit):
            verdict={"verdict":"approve","scope":"pass","duplicate_of":None,"summary":"Distinct and bounded."}
            return json.dumps({"ok":True,"model":"gpt-5.6-terra","provider":"openai-codex","response":json.dumps(verdict)}).encode()
    class Opener:
        def open(self,request,timeout):return Response()
    receipt=review({"proposal":proposal,"existing":existing,"dependencies":[]},"http://127.0.0.1:1","x"*32,tmp_path,Opener())
    assert receipt["verdict"]=="approve"
    assert receipt["checks"]["duplicates"]["compared"]==["e"*64]


def test_command_real_subprocess_roundtrip_has_single_stdin_owner():
    argv=["/usr/bin/python3","-c","import json,sys; value=json.load(sys.stdin); print(json.dumps({'seen':value['value']}))"]
    assert command(argv,{"value":"ok"})=={"seen":"ok"}


def test_blocked_semantic_review_is_persisted_and_does_not_register():
    proposal={"id":"bad","requirement_id":"req","state":"proposed","depends_on":[]}
    status={"current":None,"shared_executor_busy":False,"observed_at":1,"policy_fingerprint":"a"*64,"items":[proposal,{"id":"next","requirement_id":"req","state":"proposed"}]}
    calls=[]
    def api(method,path,payload=None):
        calls.append((path,payload))
        if path=="/v1/queue":return status
        if path=="/v1/queue/bad":return proposal
        if path=="/v1/queue/next":return {"id":"next","proposal_fingerprint":"e"*64}
        if path.endswith("/reject"):return {"id":"bad","state":"rejected","blocker":payload["blocker"]}
        raise AssertionError(path)
    receipt={"proposal_fingerprint":"d"*64,"verdict":"block","reviewer":"terra","checks":{},"blocker":"duplicate"}
    def execute(argv,**kwargs):return SimpleNamespace(returncode=0,stdout=json.dumps(receipt).encode())
    config={"reviewer_command":["/trusted/reviewer"],"registrars":{k:["/trusted/"+k] for k in ("bridge","harper","worker")}}
    assert Admission(config,api,execute).run_once()["status"]=="rejected"
    assert any(path.endswith("/reject") for path,_ in calls)


def test_receiver_rejects_template_different_from_valid_execution_policy():
    scope={"description":"one","allowed_paths":["services/x.py"],"contract_files":["AGENTS.md"],"acceptance_profile":"wb-generic"}
    requirement={"repository":"acme/repo","max_slices":2,"objective":"WB","acceptance":["pass"],"source_evidence":[],
      "path_sets":{"one":scope},"base_sha":"a"*40,"profile":"fedor","profile_id":"73bf9c3a-ab69-4b2e-a7f0-e808df8f2614",
      "profile_revision":0,"depends_on":[],"allowed_paths":scope["allowed_paths"],"contract_files":scope["contract_files"],
      "acceptance_profile":"wb-generic"}
    execution={**requirement,"selected_path_set_id":"one","allowed_paths":scope["allowed_paths"],
      "contract_files":scope["contract_files"],"acceptance_profile":"wb-generic"}
    template={key:execution[key] for key in ("base_sha","allowed_paths","contract_files","profile","profile_id","profile_revision")}
    registration={"execution_policy":execution,"template":template}
    policy={"requirements":{"req":requirement}}
    assert registration_allowed(registration,policy)
    registration["template"]={**template,"allowed_paths":["tools/loop/bridge.py"]}
    assert not registration_allowed(registration,policy)


def test_installed_receiver_imports_opt_loop_under_isolated_python(tmp_path):
    source=Path(__file__).parents[1]/"loop";installed=tmp_path/"opt-loop";installed.mkdir()
    for name in ("continuous_receiver.py","continuous_register.py","continuous_queue.py","bridge.py"):
        text=(source/name).read_text()
        if name=="continuous_receiver.py":
            text=text.replace('"/opt/loop"',repr(str(installed)))
            text=text.replace('Path("/etc/loop-continuous/receiver.json")',f'Path({str(tmp_path/"receiver.json")!r})')
        (installed/name).write_text(text)
    (tmp_path/"receiver.json").write_text(json.dumps({"role":"harper","policy_fingerprint":"a"*64,"policy_file":str(tmp_path/"policy.json")}))
    (tmp_path/"receiver.json").chmod(0o600)
    result=subprocess.run([sys.executable,"-I",str(installed/"continuous_receiver.py")],input=b"{}",capture_output=True)
    assert result.returncode!=0
    assert b"ModuleNotFoundError" not in result.stderr
    assert b"invalid closed request" in result.stderr


def test_real_subprocess_three_target_registration_refetches_full_contract(tmp_path):
    review=tmp_path/"review.py"
    review.write_text("import json,sys\nv=json.load(sys.stdin);p=v['proposal'];print(json.dumps({'proposal_fingerprint':p['proposal_fingerprint'],'verdict':'approve','reviewer':'terra','checks':{'policy':'pass','scope':'pass','dependencies':{},'duplicates':{'status':'pass','compared':[],'duplicate_of':None}}}))\n")
    registrar=tmp_path/"register.py"
    registrar.write_text("import json,sys\nt=sys.argv[1];v=json.load(sys.stdin);r=v['registration'];assert r['template']['base_sha']=='a'*40;print(json.dumps({'target':t,'template_fingerprint':r['template_fingerprint'],'policy_fingerprint':r['policy_fingerprint'],'installed_sha256':t[0]*64}))\n")
    item={"id":"task","requirement_id":"req","state":"proposed","depends_on":[],"proposal_fingerprint":"d"*64}
    registration={**item,"state":"registering","policy_fingerprint":"b"*64,"template_fingerprint":"c"*64,
      "template":{"base_sha":"a"*40},"receipts":{}}
    status={"current":None,"shared_executor_busy":False,"observed_at":100.0,"policy_fingerprint":"b"*64,"items":[item]}
    def api(method,path,payload=None):
      if path=="/v1/queue":status["observed_at"]+=1;return status
      if path=="/v1/queue/task":return item if item["state"]=="proposed" else registration
      if path.endswith("/review"):item["state"]="registering";return registration
      if path.endswith("/registration"):return registration
      if path.endswith("/receipt"):
       registration["receipts"][payload["target"]]=payload["installed_sha256"]
       registration["state"]="ready" if len(registration["receipts"])==3 else "registering"
       return registration
      raise AssertionError(path)
    config={"reviewer_command":["/usr/bin/python3",str(review)],"registrars":{
      target:["/usr/bin/python3",str(registrar),target] for target in ("bridge","harper","worker")}}
    result=Admission(config,api).run_once()
    assert result["status"]=="ready" and result["registered"]==["bridge","harper","worker"]
    assert set(registration["receipts"])=={"bridge","harper","worker"}
    assert status["observed_at"]==104
