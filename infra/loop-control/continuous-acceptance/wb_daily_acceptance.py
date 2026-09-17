"""Trusted parent observes subprocess requests; candidate code runs in a child."""
import pathlib,tempfile,subprocess,datetime,json,os,time,select,configparser,re,atexit
from zoneinfo import ZoneInfo
day=(datetime.datetime.now(ZoneInfo('Europe/Moscow')).date()-datetime.timedelta(days=1)).isoformat()
base={'last_full_day':day,'brief_day':day,'stale':False,'collected_at':day+'T05:00:00+00:00','brief_status':'ok','norm':{'sample_days':14,'window_days':14},'actual':{'orders':46}}
results=[]
import sys
sys.path.insert(0,"/acceptance")
from wb_daily_contract import flag,exec_container,sql_from
from wb_daily_pg import DailyPostgres
pg=DailyPostgres();pg.start();atexit.register(pg.stop)
def invoke(cfg,scenario,limit=10):
 stages=[];stops=[];created={};timed_out=None;buffer=b'';result=None
 p=subprocess.Popen(['python3','-I','/acceptance/daily_candidate.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 p.stdin.write((json.dumps({'config':cfg})+'\n').encode());p.stdin.flush()
 deadline=time.monotonic()+limit
 try:
  while result is None:
   assert time.monotonic()<deadline,'candidate response deadline'
   ready,_,_=select.select([p.stdout],[],[],.1)
   if not ready:continue
   chunk=os.read(p.stdout.fileno(),65536)
   assert chunk,'candidate ended before observed result'
   buffer+=chunk;assert len(buffer)<=131072
   while b'\n'in buffer:
    line,buffer=buffer.split(b'\n',1);msg=json.loads(line)
    if msg.get('kind')=='result':result=msg['value'];break
    if msg.get('kind')=='error':result={'state':'failed','error_class':msg.get('error_class')};break
    assert msg.get('kind')=='execute','candidate tried to print an acceptance result'
    cmd=msg['cmd'];kw=msg['kwargs']
    assert not kw.get('shell') and isinstance(kw.get('timeout'),(int,float)) and kw.get('timeout')>0
    assert os.path.basename(cmd[0])=='docker'
    answer={'returncode':0,'stdout':'','stderr':''}
    if cmd[1]=='inspect':answer['stdout']='healthy\n'
    elif cmd[1]=='run':
     stage='collect' if 'collect'in cmd else ('norm' if 'proxima_control_plane.norm'in cmd else 'brief')
     stages.append(stage);name=flag(cmd,'--name');assert name and re.fullmatch(r'[a-zA-Z0-9_.-]+',name);created[stage]=name
     assert '--rm'in cmd and flag(cmd,'--network')=='fixture-isolated'
     assert flag(cmd,'--memory') and flag(cmd,'--cpus') and flag(cmd,'--pids-limit')
     assert flag(cmd,'--cap-drop')=='ALL' and flag(cmd,'--security-opt')=='no-new-privileges'
     assert '--date-from'not in cmd
     for i,x in enumerate(cmd):
      if x=='--mount' and '/secrets/'in cmd[i+1]:assert 'readonly'in cmd[i+1]
     if scenario=='lock-second':raise AssertionError('second process executed a job')
     if scenario=='lock-first' and stage=='collect':
      second,other,_=invoke(cfg,'lock-second',3);assert second.get('state')!='success' and not other,'concurrent duplicate'
     if scenario==stage+'_timeout':answer={'error':'timeout'};timed_out=stage
     elif scenario==stage:answer['returncode']=1
    elif cmd[1]=='stop':
     assert cmd[-1] in created.values(),'foreign container stop';stops.append(cmd[-1])
    elif cmd[1]=='exec':
     assert exec_container(cmd)=='fixture-postgres','wrong database container'
     sql=sql_from(cmd,kw);record=json.loads(json.dumps(base))
     if scenario=='stale':record['stale']=True
     if scenario=='partial_norm':record['norm']['sample_days']=13
     if scenario=='wrong_day':record['brief_day']='2026-01-01'
     observed=pg.run(sql,cmd,day,scenario);answer={'returncode':observed.returncode,'stdout':observed.stdout,'stderr':observed.stderr}
    else:raise AssertionError('unexpected docker action')
    p.stdin.write((json.dumps(answer)+'\n').encode());p.stdin.flush()
  p.stdin.close();assert p.wait(timeout=2)==0
  assert isinstance(result,dict)
  assert len(stops)==len(set(stops)) and all(name in created.values() for name in stops)
  if timed_out is not None:assert created[timed_out] in stops,'timed out owned container was not stopped'
  return result,stages,stops
 finally:
  if p.poll() is None:p.kill();p.wait(timeout=2)
for scenario in ['success','collect','norm','brief','collect_timeout','norm_timeout','brief_timeout','stale','partial_norm','wrong_day','missing_result','lock-first']:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);runtime=root/'runtime';(runtime/'secrets').mkdir(parents=True);(runtime/'raw').mkdir()
  for name in ['fixture-tenant_wb_statistics_token','proxima_collector_uri','proxima_norm_uri']:(runtime/'secrets'/name).write_text('fixture-not-a-real-secret\n')
  cfg={'tenant_id':'fixture-tenant','runtime_root':str(runtime),'state_root':str(root/'state'),'collector_image':'sha256:'+'a'*64,'control_image':'sha256:'+'b'*64,'git_sha':'c'*40,'network':'fixture-isolated','database_container':'fixture-postgres'}
  out,stages,stops=invoke(cfg,scenario)
  assert (out.get('state')=='success')==(scenario in {'success','lock-first'}),scenario
  expected=['collect'] if scenario.startswith('collect') else (['collect','norm'] if scenario.startswith('norm') else ['collect','norm','brief'])
  assert stages==expected,scenario
  results.append(scenario)
with tempfile.TemporaryDirectory() as td:
 bad=pathlib.Path(td)/'bad.json';bad.write_text('{}')
 r=subprocess.run(['python3','-I','/work/tools/wb/daily.py','--config',str(bad)],capture_output=True,timeout=5)
 assert r.returncode!=0,'CLI failure must not report success'
 results.append('cli-failure-exit')
root=pathlib.Path('/work/infra/systemd')
service=root/'proxima-wb-daily.service';timer=root/'proxima-wb-daily.timer'
s=configparser.ConfigParser(interpolation=None);s.read(service)
t=configparser.ConfigParser(interpolation=None);t.read(timer)
assert t['Timer']['OnCalendar'].strip()=='*-*-* 05:30:00 Europe/Moscow'
assert t['Timer'].getboolean('Persistent')
assert s['Service']['Restart']=='on-failure' and s['Service']['RestartSec']in {'15min','15m','900','900s'}
assert s['Unit']['StartLimitBurst']=='3'
limit=re.fullmatch(r'([0-9]+)(h|min|m|s)?',s['Unit'].get('StartLimitIntervalSec',''))
assert limit,'missing bounded retry interval'
seconds=int(limit[1])*{'h':3600,'min':60,'m':60,'s':1,None:1}[limit[2]]
assert 43200<=seconds<86400,'retry interval must cover attempts and reset before next morning'
results.append('schedule-and-bounded-retry')
print(json.dumps({'profile':'wb-daily-packaging','cases':results,'passed':len(results),'skipped':0}))
