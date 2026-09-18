import sys,json,datetime,importlib.util,subprocess
from pathlib import Path
req=json.loads(sys.stdin.buffer.read(65537))
def forbidden(*args,**kwargs):raise RuntimeError('subprocess forbidden for read-only projection')
subprocess.run=forbidden;subprocess.Popen=forbidden;subprocess.call=forbidden;subprocess.check_output=forbidden;subprocess.check_call=forbidden
spec=importlib.util.spec_from_file_location('candidate_status','/work/tools/loop/wb_daily_status.py')
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
now=datetime.datetime.fromisoformat(req['now'])
if req['op']=='project':result=module.project_daily_status(req['snapshot'],now)
elif req['op']=='read':result=module.read_daily_status(Path(req['path']),now)
else:raise ValueError('invalid operation')
print(json.dumps(result))
