import json
from pathlib import Path
import importlib.util
import pytest

def module():
    spec=importlib.util.spec_from_file_location('night_acceptance',Path(__file__).resolve().parents[2]/'tools/loop/night_acceptance.py')
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

@pytest.mark.parametrize('raw',[b'',b'null',b'{}',b'{"version":1,"version":1}',b'PASS'])
def test_exit_zero_without_complete_evaluation_is_blocked(raw):
    with pytest.raises((ValueError,TypeError,KeyError)): module().validate_output(raw,'tg-'+'a'*32)

def test_observation_requires_every_invalid_input_blocked_and_valid_deadline_ready():
    m=module();job='night-20260915-observation'
    payload={'version':1,'job_id':job,'results':['blocked']*15+[None]}
    m.validate_output(json.dumps(payload),job)
    payload['results'][0]=None
    with pytest.raises(ValueError):m.validate_output(json.dumps(payload),job)

def test_different_job_cannot_supply_a_pass_result():
    job='tg-'+'a'*32
    with pytest.raises(ValueError):module().validate_output(json.dumps({'version':1,'job_id':'tg-'+'b'*32,'results':['paperclip-hermes-openhands-harper']}),job)

def test_candidate_location_cannot_escape_trusted_job_tree():
    with pytest.raises(ValueError):module().command('/tmp/candidate','a'*40,'b'*40,'night-20260915-observation','fixture')
