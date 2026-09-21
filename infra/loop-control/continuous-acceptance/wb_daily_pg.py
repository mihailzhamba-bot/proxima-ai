"""Disposable tenant-isolated PostgreSQL oracle for WB daily acceptance."""
import os,shlex,subprocess,tempfile
from pathlib import Path
PG=Path('/usr/lib/postgresql/16/bin')
class DailyPostgres:
 def __init__(self):self.temp=None;self.root=None;self.data=None;self.started=False
 def call(self,args,**kwargs):return subprocess.run([str(v) for v in args],check=True,timeout=30,**kwargs)
 def start(self):
  self.temp=tempfile.TemporaryDirectory(prefix='wb-daily-pg-',dir='/tmp');self.root=Path(self.temp.name);self.data=self.root/'data';port='55433'
  self.call([PG/'initdb','-D',self.data,'-U','acceptance_admin','--auth=trust','--encoding=UTF8'],stdout=subprocess.DEVNULL)
  self.call([PG/'pg_ctl','-D',self.data,'-l',self.root/'pg.log','-w','-t','20','-o',f"-h '' -k {self.root} -p {port}",'start'],stdout=subprocess.DEVNULL);self.started=True
  self.call([PG/'createdb','-h',self.root,'-p',port,'-U','acceptance_admin','proxima'],stdout=subprocess.DEVNULL)
  self.admin=[PG/'psql','-X','-q','-h',self.root,'-p',port,'-U','acceptance_admin','-d','proxima','-v','ON_ERROR_STOP=1']
  self.probe=[PG/'psql','-X','-q','-h',self.root,'-p',port,'-U','acceptance_probe','-d','proxima','-v','ON_ERROR_STOP=1']
  schema="""CREATE ROLE acceptance_probe LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE TABLE collector_runs(tenant_id text,run_id text,status text,finished_at timestamptz);
CREATE TABLE fact_cabinet_daily(tenant_id text,run_id text,calendar_day date);
CREATE TABLE norm_daily_current(tenant_id text,evaluation_day date,metric text,sample_days int,window_days int,status text);
CREATE TABLE brief_current(tenant_id text,brief_day date,status text,payload jsonb);
CREATE TABLE data_status_current(tenant_id text,last_full_day date,stale boolean,collected_at timestamptz);
ALTER TABLE collector_runs ENABLE ROW LEVEL SECURITY; ALTER TABLE fact_cabinet_daily ENABLE ROW LEVEL SECURITY; ALTER TABLE norm_daily_current ENABLE ROW LEVEL SECURITY; ALTER TABLE brief_current ENABLE ROW LEVEL SECURITY; ALTER TABLE data_status_current ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_runs ON collector_runs USING (tenant_id=current_setting('proxima.tenant_id',true));
CREATE POLICY tenant_fact ON fact_cabinet_daily USING (tenant_id=current_setting('proxima.tenant_id',true));
CREATE POLICY tenant_norm ON norm_daily_current USING (tenant_id=current_setting('proxima.tenant_id',true));
CREATE POLICY tenant_brief ON brief_current USING (tenant_id=current_setting('proxima.tenant_id',true));
CREATE POLICY tenant_status ON data_status_current USING (tenant_id=current_setting('proxima.tenant_id',true));
GRANT SELECT ON ALL TABLES IN SCHEMA public TO acceptance_probe;"""
  self.call(self.admin,input=schema,text=True,capture_output=True)
 def seed(self,day,scenario):
  stale='true' if scenario=='stale' else 'false';samples=13 if scenario=='partial_norm' else 14;brief='2026-01-01' if scenario=='wrong_day' else day
  fact_day='2026-01-01' if scenario=='stale' else day;finished="now()-interval '48 hours'" if scenario=='stale' else 'now()'
  if scenario=='missing_result':fixture=""
  else:fixture=f"""INSERT INTO collector_runs VALUES('fixture-tenant','run-1','SUCCEEDED',{finished}),('other-tenant','other','SUCCEEDED',now());
INSERT INTO fact_cabinet_daily VALUES('fixture-tenant','run-1','{fact_day}'),('other-tenant','other','2099-01-01');
INSERT INTO norm_daily_current VALUES('fixture-tenant','{day}','orders',{samples},14,'ok'),('fixture-tenant','{day}','sales',{samples},14,'ok'),('other-tenant','2099-01-01','orders',1,1,'failed');
INSERT INTO brief_current VALUES('fixture-tenant','{brief}','ok','{{"actual":{{"orders":46}},"norm":{{"sample_days":{samples},"window_days":14}}}}'),('other-tenant','2099-01-01','failed','{{}}');
INSERT INTO data_status_current VALUES('fixture-tenant','{day}',{stale},now()),('other-tenant','2099-01-01',false,now());"""
  sql='TRUNCATE collector_runs,fact_cabinet_daily,norm_daily_current,brief_current,data_status_current;'+fixture
  self.call(self.admin,input=sql,text=True,capture_output=True)
 def output_flags(self,cmd):
  tokens=[]
  for value in cmd:
   try:tokens.extend(shlex.split(value))
   except ValueError:tokens.append(value)
  flags=[]
  if '--csv' in tokens:flags.append('--csv')
  short=[value[1:] for value in tokens if value.startswith('-') and not value.startswith('--')]
  if '-A' in tokens or '--no-align' in tokens or any('A' in value for value in short):flags.append('-A')
  if '-t' in tokens or '--tuples-only' in tokens or any('t' in value for value in short):flags.append('-t')
  for index,value in enumerate(tokens):
   if value in {'-F','--field-separator'} and index+1<len(tokens):flags+=['-F',tokens[index+1]]
   elif value.startswith('-F') and len(value)>2:flags+=['-F',value[2:]]
   elif value.startswith('--field-separator='):flags.append(value)
  return flags
 def run(self,sql,cmd,day,scenario):
  self.seed(day,scenario)
  env=dict(os.environ,PGOPTIONS='-c default_transaction_read_only=on')
  return subprocess.run([str(v) for v in self.probe+self.output_flags(cmd)],input=sql,text=True,capture_output=True,timeout=30,env=env)
 def stop(self):
  if self.started:
   subprocess.run([str(PG/'pg_ctl'),'-D',str(self.data),'-m','immediate','-w','stop'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15);self.started=False
  if self.temp:self.temp.cleanup();self.temp=None
