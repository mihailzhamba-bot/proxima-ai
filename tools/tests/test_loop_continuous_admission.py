import json,subprocess
from types import SimpleNamespace
import pytest
from tools.loop.continuous_admission import Admission,AdmissionError,command
from tools.loop.continuous_receiver import ReceiverError,receive,registration_allowed
from tools.loop.continuous_proposal_review import review

def test_admission_resumes_partial_three_target_registration():
    calls=[]
    status={"current":None,"observed_at":1,"shared_executor_busy":False,"policy_fingerprint":"b"*64,"items":[{"id":"task-one","requirement_id":"req","state":"registering"}]}
    registration={"id":"task-one","state":"registering","receipts":{"bridge":"done"}}
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
