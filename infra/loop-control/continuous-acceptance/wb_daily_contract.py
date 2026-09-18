"""Trusted semantic helpers for WB daily acceptance; no candidate imports."""
import re,shlex,subprocess

def flag(cmd,key):
 for i,value in enumerate(cmd):
  if value==key:
   if i+1>=len(cmd):raise AssertionError("missing flag value")
   return cmd[i+1]
  if value.startswith(key+'='):return value.split('=',1)[1]
 return None

def execute_reply(cmd,kwargs,reply):
 text_mode=kwargs.get('text') is True or kwargs.get('universal_newlines') is True or kwargs.get('encoding') is not None or kwargs.get('errors') is not None
 def stream(name):
  value=reply.get(name,'')
  return value if text_mode or isinstance(value,bytes) else value.encode()
 stdout,stderr=stream('stdout'),stream('stderr')
 if reply.get('error')=='timeout':raise subprocess.TimeoutExpired(cmd,kwargs.get('timeout',1),output=stdout,stderr=stderr)
 completed=subprocess.CompletedProcess(cmd,reply['returncode'],stdout,stderr)
 if kwargs.get('check') and completed.returncode:raise subprocess.CalledProcessError(completed.returncode,cmd,output=completed.stdout,stderr=completed.stderr)
 return completed

def exec_parts(cmd):
 assert len(cmd)>=4 and cmd[1]=='exec','not docker exec'
 tail=cmd[2:]
 if tail and tail[0]=='-i':tail=tail[1:]
 assert len(tail)>=2 and not tail[0].startswith('-'),'unsupported docker exec options'
 return tail[0],tail[1:]
def exec_container(cmd):return exec_parts(cmd)[0]
def direct_psql_command(cmd):
 _container,argv=exec_parts(cmd);program=argv[0].rsplit('/',1)[-1]
 if program=='psql':return argv
 if program in {'sh','bash'}:
  expected_prefix='read -r dbuser < "$POSTGRES_USER_FILE"; exec psql '
  assert len(argv)==3 and argv[1]=='-c' and argv[2].startswith(expected_prefix),'unapproved SQL wrapper'
  inner=shlex.split(argv[2][len(expected_prefix):]);expected=['-X','-A','-t','-U','$dbuser','-d','$POSTGRES_DB','-v','ON_ERROR_STOP=1']
  assert inner==expected,'unapproved SQL wrapper'
  return None
 raise AssertionError('unapproved SQL executable')
def sql_from(cmd,kwargs):
 stdin=kwargs.get('input');psql=direct_psql_command(cmd);cvalue=(flag(psql,'-c') or flag(psql,'--command')) if psql else None
 assert not (stdin and cvalue),'ambiguous SQL transport'
 sql=stdin or cvalue
 assert isinstance(sql,str) and sql.strip(),'missing SQL probe'
 normalized=' '.join(sql.split());upper=normalized.upper()
 assert 'BEGIN READ ONLY' in upper and re.search(r"SET LOCAL PROXIMA\.TENANT_ID\s*=\s*'FIXTURE-TENANT'",upper),'tenant read-only transaction required'
 assert 'BRIEF_CURRENT' in upper and ('DATA_STATUS_CURRENT' in upper or ('FACT_CABINET_DAILY' in upper and 'COLLECTOR_RUNS' in upper and 'NORM_DAILY_CURRENT' in upper)),'daily readiness sources required'
 assert not re.search(r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|COPY)\b',upper),'mutating SQL forbidden'
 return sql
