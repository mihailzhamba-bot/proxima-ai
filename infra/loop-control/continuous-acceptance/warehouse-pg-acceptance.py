#!/usr/bin/python3
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
PG=Path('/usr/lib/postgresql/16/bin')
def call(args,**kwargs):return subprocess.run([str(x) for x in args],check=True,timeout=30,stdout=subprocess.DEVNULL,**kwargs)
manifest=json.loads(Path('/acceptance/migrations.json').read_text())
found={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/work/db/migrations').glob('*.sql')}
assert found==manifest,'migration baseline changed'
with tempfile.TemporaryDirectory(prefix='warehouse-pg-',dir='/tmp') as tmp:
 root=Path(tmp);data=root/'data';port='55432';started=False
 try:
  call([PG/'initdb','-D',data,'-U','acceptance_admin','--auth=trust','--encoding=UTF8'])
  call([PG/'pg_ctl','-D',data,'-l',root/'pg.log','-w','-t','20','-o',f'-h 127.0.0.1 -p {port} -k {root}','start']);started=True
  call([PG/'createdb','-h','127.0.0.1','-p',port,'-U','acceptance_admin','proxima'])
  psql=[PG/'psql','-X','-h','127.0.0.1','-p',port,'-U','acceptance_admin','-d','proxima','-v','ON_ERROR_STOP=1']
  for name in sorted(manifest):call(psql+['-f',Path('/work/db/migrations')/name])
  call(psql+['-c','CREATE ROLE acceptance_collector LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; GRANT proxima_job_collector TO acceptance_collector; GRANT CONNECT ON DATABASE proxima TO acceptance_collector;'])
  env=dict(os.environ,PROXIMA_TEST_POSTGRES_DSN=f'postgresql://acceptance_admin@127.0.0.1:{port}/proxima',PROXIMA_TEST_DSN_COLLECTOR=f'postgresql://acceptance_collector@127.0.0.1:{port}/proxima')
  r=subprocess.run(['node','--import','/work/node_modules/tsx/dist/loader.mjs','/acceptance/warehouse-check.mts'],env=env,timeout=120)
  if r.returncode:raise SystemExit(r.returncode)
 finally:
  if started:subprocess.run([str(PG/'pg_ctl'),'-D',str(data),'-m','immediate','-w','stop'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
