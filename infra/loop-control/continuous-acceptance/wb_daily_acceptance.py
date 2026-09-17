"""Trusted behavior probe for the daily wrapper, run in an offline container."""
import importlib.util, pathlib, tempfile, subprocess, datetime, json
from zoneinfo import ZoneInfo
p=pathlib.Path('/work/tools/wb/daily.py')
spec=importlib.util.spec_from_file_location('candidate_daily_wrapper',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
day=(datetime.datetime.now(ZoneInfo('Europe/Moscow')).date()-datetime.timedelta(days=1)).isoformat()
base={'last_full_day':day,'brief_day':day,'stale':False,'brief_status':'ok','norm':{'sample_days':14,'window_days':14},'actual':{'orders':46}}
results=[]
for scenario in ['success','collect','norm','brief','collect_timeout','norm_timeout','brief_timeout','stale','partial_norm','wrong_day','missing_result']:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);runtime=root/'runtime';(runtime/'secrets').mkdir(parents=True);(runtime/'raw').mkdir()
  for name in ['fixture-tenant_wb_statistics_token','proxima_collector_uri','proxima_norm_uri']:
   (runtime/'secrets'/name).write_text('fixture-not-a-real-secret\n')
  cfg={'tenant_id':'fixture-tenant','runtime_root':str(runtime),'state_root':str(root/'state'),
       'collector_image':'sha256:'+'a'*64,'control_image':'sha256:'+'b'*64,'git_sha':'c'*40,
       'network':'fixture-isolated','database_container':'fixture-postgres'}
  stages=[];stops=[];commands=[]
  def execute(cmd,**kw):
   assert kw.get('shell') is not True,'shell invocation forbidden'
   assert kw.get('timeout') and kw['timeout']<=900,'subprocess deadline missing'
   commands.append(cmd)
   if cmd[:2]==['docker','inspect']:return subprocess.CompletedProcess(cmd,0,'healthy\n','')
   if cmd[:2]==['docker','run']:
    stage='collect' if 'collect'in cmd else ('norm' if 'proxima_control_plane.norm'in cmd else 'brief')
    stages.append(stage)
    assert cmd[cmd.index('--network')+1]=='fixture-isolated'
    assert '--memory'in cmd and '--cpus'in cmd and '--pids-limit'in cmd
    assert '--date-from'not in cmd,'increment floor must remain collector-owned'
    for i,x in enumerate(cmd):
     if x=='--mount' and '/secrets/'in cmd[i+1]:assert 'readonly'in cmd[i+1]
    if scenario==stage+'_timeout':raise subprocess.TimeoutExpired(cmd,900)
    return subprocess.CompletedProcess(cmd,1 if scenario==stage else 0,'fixture-output','')
   if cmd[:2]==['docker','stop']:
    stops.append(cmd[-1]);return subprocess.CompletedProcess(cmd,0,'','')
   if cmd[:2]==['docker','exec']:
    assert cmd[cmd.index('-i')+1]=='fixture-postgres'
    assert 'READ ONLY'in kw.get('input','')
    record=json.loads(json.dumps(base))
    if scenario=='stale':record['stale']=True
    if scenario=='partial_norm':record['norm']['sample_days']=13
    if scenario=='wrong_day':record['brief_day']='2026-01-01'
    return subprocess.CompletedProcess(cmd,0,'' if scenario=='missing_result' else json.dumps(record)+'\n','')
   raise AssertionError('unexpected command')
  out=m.run_daily(cfg,execute=execute)
  assert isinstance(out,dict),scenario
  assert (out.get('state')=='success')==(scenario=='success'),scenario
  if scenario.startswith('collect'):assert stages==['collect'],scenario
  elif scenario.startswith('norm'):assert stages==['collect','norm'],scenario
  else:assert stages==['collect','norm','brief'],scenario
  assert len(stops)==len(stages),scenario
  assert len(set(stops))==len(stops),scenario
  results.append(scenario)
print(json.dumps({'profile':'wb-daily-packaging','cases':results,'passed':len(results),'skipped':0}))
