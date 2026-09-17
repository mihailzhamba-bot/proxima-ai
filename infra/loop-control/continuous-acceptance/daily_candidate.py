import sys,os,json,subprocess,importlib.util,contextlib,io
sys.path.insert(0,"/acceptance")
from wb_daily_contract import execute_reply
wire=os.fdopen(os.dup(1),'w',buffering=1)
request=json.loads(sys.stdin.readline(65537))
def execute(cmd,**kwargs):
 msg={'kind':'execute','cmd':[str(x) for x in cmd],'kwargs':kwargs}
 wire.write(json.dumps(msg)+'\n');wire.flush()
 reply=json.loads(sys.stdin.readline(131073))
 return execute_reply(cmd,kwargs,reply)
try:
 with contextlib.redirect_stdout(io.StringIO()):
  spec=importlib.util.spec_from_file_location('candidate_daily','/work/tools/wb/daily.py')
  m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
  result=m.run_daily(request['config'],execute=execute)
 wire.write(json.dumps({'kind':'result','value':result})+'\n')
except Exception as e:
 wire.write(json.dumps({'kind':'error','error_class':type(e).__name__})+'\n')
