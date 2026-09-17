import importlib.util,json,os,subprocess,sys
from pathlib import Path
from unittest.mock import patch
import pytest
P=Path(__file__).parents[1]/'loop'/'continuous_acceptance.py'
s=importlib.util.spec_from_file_location('trusted_acceptance',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
@pytest.fixture
def candidate(tmp_path,monkeypatch):
 root=tmp_path/'work';p=root/'loop-fixture-job-1-x'/'candidate';p.mkdir(parents=True)
 for dep in ['dep-0','dep-2']:(p.parent/'writable'/dep).mkdir(parents=True)
 def git(*a):return subprocess.check_output(['git','-C',str(p),*a],stderr=subprocess.DEVNULL,text=True).strip()
 git('init');git('config','user.email','fixture@invalid');git('config','user.name','Fixture')
 (p/'x.py').write_text('old\n');git('add','x.py');git('commit','-m','base');base=git('rev-parse','HEAD')
 (p/'x.py').write_text('new\n');git('commit','-am','head');head=git('rev-parse','HEAD')
 admissions=tmp_path/'admissions';admissions.mkdir()
 proof={'job_id':'fixture-job-1','base_sha':base,'allowed_paths':['x.py'],'acceptance_profile':'wb-daily-status'}
 f=admissions/'fixture-job-1.json';f.write_text(json.dumps(proof));f.chmod(0o600)
 monkeypatch.setattr(m,'OWNER_UID',os.getuid());monkeypatch.setattr(m,'ROOT',root);monkeypatch.setattr(m,'ADMISSIONS',admissions)
 monkeypatch.setattr(sys,'argv',['accept',str(p),base,head,'fixture-job-1'])
 return p,f,proof,head
def invoke(result):
 original=subprocess.run;original_popen=subprocess.Popen
 def fake_run(cmd,**kw):
  if cmd[0]=='docker':return subprocess.CompletedProcess(cmd,0,b'',b'')
  return original(cmd,**kw)
 def fake_popen(cmd,**kw):
  if cmd[0]!='docker':return original_popen(cmd,**kw)
  assert '--network'in cmd and cmd[cmd.index('--network')+1]=='none'
  assert '--read-only'in cmd and '--cap-drop'in cmd
  assert m.IMAGE in cmd
  kw['stdout'].write(result.encode());kw['stdout'].flush()
  class Done:
   returncode=0
   def poll(self):return 0
  return Done()
 with patch('subprocess.run',side_effect=fake_run),patch('subprocess.Popen',side_effect=fake_popen):
  m.main()
@pytest.mark.parametrize('change',[{'base_sha':'0'*40},{'job_id':'other-job'},{'allowed_paths':['wrong.py']},{'acceptance_profile':'arbitrary-shell'}])
def test_reject_changed_admission(candidate,change):
 _,f,proof,_=candidate;proof.update(change);f.write_text(json.dumps(proof))
 with pytest.raises(ValueError):m.main()
def test_reject_group_writable_receipt(candidate):
 _,f,_,_=candidate;f.chmod(0o660)
 with pytest.raises(ValueError):m.main()
def test_reject_skipped_and_duplicate_output(candidate):
 result={'profile':'wb-daily-status','passed':23,'skipped':1,'cases':[str(i) for i in range(23)]}
 with pytest.raises(ValueError):invoke(json.dumps(result)+'\n')
 result['skipped']=0
 with pytest.raises(ValueError):invoke(json.dumps(result)+'\n'+json.dumps(result)+'\n')
def test_exact_receipt_protocol(candidate,capsys):
 _,_,_,head=candidate
 invoke(json.dumps({'profile':'wb-daily-status','passed':23,'skipped':0,'cases':[str(i) for i in range(23)]})+'\n')
 assert json.loads(capsys.readouterr().out)=={'sha':head,'status':'pass','skipped':0}
