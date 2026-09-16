import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/loop'))
spec=importlib.util.spec_from_file_location('night_guard',ROOT/'tools/loop/night_guard.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)

def test_stop_fences_only_unfinished_runs_and_records_result(tmp_path,monkeypatch):
    path=tmp_path/'state.json';path.write_text(json.dumps({'status':'running','tasks':[{'phase':'ready_pr','run_id':'done'},{'phase':'reviewing','run_id':'live'}]}))
    calls=[]
    def call(method,path,**kwargs):
        calls.append(path);return {'paused':True} if path=='/v1/pause' else {'status':'cancelled'}
    monkeypatch.setattr(guard,'BridgeClient',lambda _:call)
    monkeypatch.setattr(guard.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout='active\n'))
    assert guard.stop({'state_file':str(path)})
    assert calls==['/v1/pause','/v1/runs/live/stop']
    assert json.loads(path.read_text())['status']=='blocked'

def test_stale_heartbeat_stops_service_and_pauses_even_if_service_dead(tmp_path,monkeypatch):
    path=tmp_path/'state.json';path.write_text(json.dumps({'status':'running','updated_at':0,'tasks':[]}))
    calls=[];monkeypatch.setattr(guard.time,'time',lambda:400)
    monkeypatch.setattr(guard.subprocess,'run',lambda args,**kw:calls.append(args))
    monkeypatch.setattr(guard,'stop',lambda m:calls.append('stop'))
    guard.watch({'state_file':str(path),'end_at':500,'job_timeout_seconds':100})
    assert calls==[['systemctl','stop','loop-night.service'],'stop']

def test_completed_batch_watchdog_does_not_pause_later_work(tmp_path,monkeypatch):
    path=tmp_path/'state.json';path.write_text(json.dumps({'status':'completed','updated_at':0,
        'tasks':[{'phase':'ready_pr','run_id':'done'}]}))
    monkeypatch.setattr(guard,'stop',lambda _:(_ for _ in ()).throw(AssertionError('must not stop')))
    guard.watch({'state_file':str(path),'end_at':1,'job_timeout_seconds':100})

def test_cancelling_is_unconfirmed_and_watch_retries(tmp_path,monkeypatch):
    path=tmp_path/'state.json';path.write_text(json.dumps({'status':'running','tasks':[{'phase':'monitoring','run_id':'live'}]}))
    monkeypatch.setattr(guard,'BridgeClient',lambda _:lambda method,path,**kw:{'paused':False} if path=='/v1/pause' else {'status':'cancelling'})
    assert not guard.stop({'state_file':str(path)})
    receipt=json.loads((tmp_path/'stop-receipt.json').read_text());assert not receipt['confirmed']
    calls=[];monkeypatch.setattr(guard,'stop',lambda m:calls.append('retry'))
    guard.watch({'state_file':str(path),'end_at':1,'job_timeout_seconds':100})
    assert calls==['retry']

def test_lost_dispatch_identity_is_not_confirmed_by_pause(tmp_path,monkeypatch):
    path=tmp_path/'state.json';path.write_text(json.dumps({'status':'running','tasks':[{'phase':'dispatching','job_id':'fixture'}]}))
    monkeypatch.setattr(guard,'BridgeClient',lambda _:lambda method,path,**kw:{'paused':True})
    assert not guard.stop({'state_file':str(path),'tasks':[]})
    receipt=json.loads((tmp_path/'stop-receipt.json').read_text())
    assert any(x.get('reason')=='identity_unknown' for x in receipt['actions'])


def test_exec_stoppost_is_noop_for_normal_completed_batch(tmp_path,monkeypatch):
    path=tmp_path/'state.json'
    path.write_text(json.dumps({'status':'completed',
        'tasks':[{'phase':'ready_pr','run_id':'done'}]}))
    monkeypatch.setattr(guard,'BridgeClient',
        lambda _:(_ for _ in ()).throw(AssertionError('must not contact Bridge')))
    assert guard.stop({'state_file':str(path)})
    receipt=json.loads((tmp_path/'stop-receipt.json').read_text())
    assert receipt['confirmed'] is True
    assert receipt['normal_completion'] is True
    assert receipt['actions']==[]


def test_malformed_completed_batch_still_fails_closed(tmp_path,monkeypatch):
    path=tmp_path/'state.json'
    path.write_text(json.dumps({'status':'completed',
        'tasks':[{'phase':'monitoring','run_id':'live'}]}))
    calls=[]
    monkeypatch.setattr(guard,'stop',lambda manifest:calls.append('stop'))
    guard.watch({'state_file':str(path),'end_at':500,'job_timeout_seconds':100})
    assert calls==['stop']
