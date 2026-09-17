"""Independent status acceptance; executed only inside the credential-free verifier."""
import importlib.util, datetime, copy, json, pathlib
path=pathlib.Path('/work/tools/loop/wb_daily_status.py')
spec=importlib.util.spec_from_file_location('candidate_daily_status',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
now=datetime.datetime(2026,9,17,7,0,tzinfo=datetime.timezone.utc)
base={'started_at':'2026-09-17T02:30:00+00:00','finished_at':'2026-09-17T02:30:06+00:00',
 'state':'success','tenant':'fixture-tenant','scope':'isolated rehearsal','stage':'brief',
 'verified':{'stale':False,'last_full_day':'2026-09-16','brief_day':'2026-09-16','brief_status':'ok',
 'collected_at':'2026-09-17T02:30:01+00:00','actual':{'orders':46},
 'norm':{'sample_days':14,'window_days':14,'orders':'38.00','revenue':'28269.33'}}}
results=[]
def check(name,snapshot,ready=False,when=now):
 out=module.project_daily_status(snapshot,when)
 assert isinstance(out,dict),name
 assert set(out)=={'tenant_id','state','analyzed_day','collected_at','last_attempt_at','reason_code'},name
 assert (out['state'] in {'ready','success'})==ready,name
 assert 'never-emit-this' not in json.dumps(out),name
 results.append(name)
check('valid',copy.deepcopy(base),True)
for name,key,value in [('stale','stale',True),('stale-null','stale',None),('old-fact-day','last_full_day','2026-09-15'),('old-brief-day','brief_day','2026-09-15'),('blocked','brief_status','blocked'),('future-collection','collected_at','2026-09-18T02:30:00Z'),('malformed-collection','collected_at','not-a-timestamp')]:
 x=copy.deepcopy(base);x['verified'][key]=value;check(name,x)
x=copy.deepcopy(base);x['verified']['norm']['sample_days']=13;check('partial-norm',x)
x=copy.deepcopy(base);del x['verified']['norm'];check('missing-norm',x)
x=copy.deepcopy(base);x['state']='failed';x['error']='never-emit-this';check('failed-redaction',x)
x=copy.deepcopy(base);x['state']='running';check('running',x)
check('empty',{})
x=copy.deepcopy(base);x['token']='never-emit-this';x['verified']['raw']='never-emit-this';check('unexpected-fields-redacted',x,True)
check('moscow-new-day',copy.deepcopy(base),False,datetime.datetime(2026,9,17,21,1,tzinfo=datetime.timezone.utc))
print(json.dumps({'profile':'wb-daily-status','cases':results,'passed':len(results),'skipped':0}))
