"""Assertions execute in a different process from the untrusted candidate."""
import datetime,copy,json,pathlib,subprocess,tempfile,hashlib,os
now=datetime.datetime(2026,9,17,7,0,tzinfo=datetime.timezone.utc)
base={'started_at':'2026-09-17T02:30:00+00:00','finished_at':'2026-09-17T02:30:06+00:00','state':'success','tenant':'fixture-tenant','scope':'isolated rehearsal','stage':'brief','verified':{'stale':False,'last_full_day':'2026-09-16','brief_day':'2026-09-16','brief_status':'ok','collected_at':'2026-09-17T02:30:01+00:00','actual':{'orders':46},'norm':{'sample_days':14,'window_days':14}}}
results=[]
def invoke(request):
 r=subprocess.run(['python3','-I','/acceptance/status_candidate.py'],input=json.dumps(request).encode(),capture_output=True,timeout=5)
 assert r.returncode==0 and len(r.stdout)<=65536,'candidate call failed'
 out=json.loads(r.stdout)
 assert isinstance(out,dict) and set(out)=={'tenant_id','state','analyzed_day','collected_at','last_attempt_at','reason_code'}
 return out
def check(name,snapshot,ready=False,when=now):
 out=invoke({'op':'project','snapshot':snapshot,'now':when.isoformat()})
 assert (out['state'] in {'ready','success'})==ready,name
 assert 'never-emit-this'not in json.dumps(out),name
 if ready:
  assert out['tenant_id']=='fixture-tenant' and out['analyzed_day']=='2026-09-16',name
  assert out['collected_at'] and out['last_attempt_at'],name
 results.append(name)
check('valid',copy.deepcopy(base),True)
for name,key,value in [('stale','stale',True),('stale-null','stale',None),('old-fact-day','last_full_day','2026-09-15'),('old-brief-day','brief_day','2026-09-15'),('blocked','brief_status','blocked'),('future-collection','collected_at','2026-09-18T02:30:00Z'),('malformed-collection','collected_at','not-a-timestamp')]:
 x=copy.deepcopy(base);x['verified'][key]=value;check(name,x)
x=copy.deepcopy(base);x['verified']['norm']['sample_days']=13;check('partial-norm',x)
x=copy.deepcopy(base);del x['verified']['norm'];check('missing-norm',x)
x=copy.deepcopy(base);x['state']='failed';x['error']='never-emit-this';check('failed-redaction',x)
x=copy.deepcopy(base);x['state']='running';check('running',x)
check('empty',{})
x=copy.deepcopy(base);x['token']='never-emit-this';check('extra-fields-redacted',x,True)
check('moscow-new-day',copy.deepcopy(base),False,datetime.datetime(2026,9,17,21,1,tzinfo=datetime.timezone.utc))
for key in ['started_at','finished_at']:
 for value in ['bad','2026-09-18T00:00:00Z']:
  x=copy.deepcopy(base);x[key]=value;check(key+'-'+value,x)
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'snapshot.json'
 for label,body,ready in [('valid-file',json.dumps(base),True),('bad-json','{',False),('oversize',json.dumps(base)+' '*65536,False)]:
  p.write_text(body);before=hashlib.sha256(p.read_bytes()).hexdigest();names=sorted(os.listdir(td))
  out=invoke({'op':'read','path':str(p),'now':now.isoformat()})
  assert (out['state']in {'ready','success'})==ready,label
  assert hashlib.sha256(p.read_bytes()).hexdigest()==before and sorted(os.listdir(td))==names,'adapter wrote files'
  results.append(label)
 out=invoke({'op':'read','path':str(pathlib.Path(td)/'missing'),'now':now.isoformat()});assert out['state']not in {'ready','success'};results.append('missing-file')
print(json.dumps({'profile':'wb-daily-status','cases':results,'passed':len(results),'skipped':0}))
