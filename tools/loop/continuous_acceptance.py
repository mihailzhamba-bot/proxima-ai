#!/usr/bin/python3 -I
"""Operator-owned acceptance for bounded continuous pilot tasks."""
import hashlib,json,os,re,stat,subprocess,sys,tempfile,uuid,time
from pathlib import Path
ROOT=Path('/srv/loop-runner/work')
ADMISSIONS=Path('/etc/loop-review/continuous/admissions')
TESTS=Path('/opt/loop-review/continuous')
IMAGE='localhost:5000/loop-verification/producer@sha256:cf2053695d05fc3ee894def2eee3b25f1e2c1aff252fef7e0b1038937327dd31'
PROFILES={'wb-daily-packaging':('wb_daily_acceptance.py',11),'wb-daily-status':('wb_daily_status_acceptance.py',15),'wb-warehouse-metadata':('warehouse-pg-acceptance.py',7),'wb-generic':('generic_acceptance.py',1)}
def trusted_json(path):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd)
  if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022 or st.st_nlink!=1 or st.st_size>65536:raise ValueError('untrusted admission')
  return json.loads(os.read(fd,65537))
 finally:os.close(fd)
def git(path,*args):
 env={'PATH':'/usr/bin:/bin','HOME':'/var/empty','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_NOSYSTEM':'1','GIT_NO_REPLACE_OBJECTS':'1','GIT_OPTIONAL_LOCKS':'0'}
 r=subprocess.run(['/usr/bin/git','-c','safe.directory='+str(path),'-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-C',str(path),*args],env=env,capture_output=True,timeout=20,check=True)
 if len(r.stdout)>4194304:raise ValueError('git output bound')
 return r.stdout.decode()
def main():
 checkout,base,head,job=sys.argv[1:]
 if not re.fullmatch('[a-z0-9][a-z0-9-]{2,80}',job) or not all(re.fullmatch('[0-9a-f]{40}',v) for v in [base,head]):raise ValueError('invalid identity')
 proof=trusted_json(ADMISSIONS/(job+'.json'))
 if proof.get('job_id')!=job or proof.get('base_sha')!=base or proof.get('acceptance_profile')not in PROFILES:raise ValueError('admission binding')
 path=Path(checkout)
 if path.resolve()!=path or path.name!='candidate' or path.parent.parent!=ROOT or not path.parent.name.startswith('loop-'+job+'-'):raise ValueError('candidate location')
 if git(path,'rev-parse','HEAD').strip()!=head or head==base:raise ValueError('candidate head')
 git(path,'merge-base','--is-ancestor',base,head)
 if git(path,'rev-list','--count',base+'..'+head).strip()!='1' or git(path,'status','--porcelain','--untracked-files=all').strip():raise ValueError('candidate history/dirty')
 changed=git(path,'diff','--name-only',base,head,'--').splitlines()
 if not changed or set(changed)!=set(proof['allowed_paths']):raise ValueError('candidate paths')
 for rev in [base,head]:
  if any(l.startswith('160000 ') or l.startswith('120000 ') and l.split('\t',1)[-1] in changed for l in git(path,'ls-tree','-r',rev).splitlines()):raise ValueError('candidate link')
 profile=proof['acceptance_profile']
 if profile=='wb-generic' and (not isinstance(proof.get('goal'),str) or not isinstance(proof.get('acceptance'),list) or not proof['acceptance'] or not all(re.fullmatch('[0-9a-f]{64}',str(proof.get(k,''))) for k in ('proposal_fingerprint','review_fingerprint'))):raise ValueError('generic acceptance binding')
 script,count=PROFILES[profile]
 mounts=['-v',str(path)+':/work:ro','-v',str(TESTS)+':/acceptance:ro']
 for i,target in [(0,'node_modules'),(2,'services/collector/node_modules')]:
  dep=path.parent/'writable'/('dep-'+str(i))
  if dep.resolve()!=dep or not dep.is_dir():raise ValueError('dependency missing')
  mounts+=['-v',str(dep)+':/work/'+target+':ro']
 name='loop-continuous-accept-'+uuid.uuid4().hex
 cmd=['docker','run','--rm','--name',name,'--network','none','--user','1000:1000','--read-only','--memory','1g','--cpus','1','--pids-limit','128','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,noexec,size=384m,mode=1777',*mounts,'-w','/work',IMAGE,'timeout','--kill-after=5s','180s','python3','-I','/acceptance/'+script]
 try:
  with tempfile.TemporaryFile() as output:
   proc=subprocess.Popen(cmd,stdout=output,stderr=output,stdin=subprocess.DEVNULL)
   deadline=time.monotonic()+195
   try:
    while proc.poll() is None:
     if output.tell()>2000000 or time.monotonic()>deadline:raise ValueError('acceptance bounded limit')
     time.sleep(.1)
    if output.tell()>2000000:raise ValueError('acceptance output bound')
    output.seek(0);raw=output.read().decode()
    if proc.returncode:raise ValueError('independent acceptance failed')
   finally:
    if proc.poll() is None:proc.kill();proc.wait(timeout=5)
  lines=[l.removeprefix('ACCEPTANCE_RESULT ') for l in raw.splitlines() if l.startswith('ACCEPTANCE_RESULT ') or l.startswith('{"profile":')]
  if len(lines)!=1:raise ValueError('acceptance result missing/duplicate')
  result=json.loads(lines[0])
  if result.get('profile')!=profile or result.get('passed')!=count or result.get('skipped')!=0 or len(result.get('cases',[]))!=count or len(set(result['cases']))!=count:raise ValueError('acceptance case count')
 finally:
  subprocess.run(['docker','stop','--time','5',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
 print(json.dumps({'sha':head,'status':'pass','skipped':0}))
if __name__=='__main__':
 try:main()
 except Exception as e:
  print(json.dumps({'status':'blocked','reason':str(e) if isinstance(e,ValueError) else type(e).__name__}))
  raise SystemExit(1)
