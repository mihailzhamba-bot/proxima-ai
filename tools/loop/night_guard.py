#!/usr/bin/python3 -I
"""Independent systemd watchdog and stop hook for the finite overnight batch."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from night_batch import BridgeClient, atomic_json, checked, json_file

def stop(manifest):
    path = Path(manifest['state_file'])
    state = json_file(path) if path.exists() else {}
    normal_completion = (state.get('status') == 'completed'
        and type(state.get('tasks')) is list
        and all(task.get('phase') == 'ready_pr' for task in state['tasks']))
    if normal_completion:
        atomic_json(path.parent/'stop-receipt.json', {
            'observed_at': time.time(), 'attempts': 0, 'confirmed': True,
            'normal_completion': True, 'actions': []})
        return True
    if state.get('status') == 'running':
        state.update(status='blocked', reason='supervisor_stopped', updated_at=time.time())
        atomic_json(path, state)
        atomic_json(path.parent/'status.json', state)
    receipt_path = path.parent/'stop-receipt.json'
    previous = json_file(receipt_path) if receipt_path.exists() else {}
    attempts = previous.get('attempts', 0) + 1
    api = BridgeClient(manifest)
    results = []
    paths = ['/v1/pause']
    for task in state.get('tasks', []):
        if task.get('phase') in {'dispatching','monitoring','reviewing'} and not task.get('run_id'):
            expected = next((item for item in manifest.get('tasks',[]) if item['job_id']==task.get('job_id')),None)
            try:
                job=api('GET','/v1/runner/jobs/'+task['job_id'],role='runner',timeout=5)
                if not expected or job.get('template')!=expected['template'] or job.get('template_fingerprint')!=expected['template_fingerprint'] or not isinstance(job.get('parent_run_id'),str):
                    raise ValueError('identity not verified')
                import uuid
                if str(uuid.UUID(job['parent_run_id']))!=job['parent_run_id']:raise ValueError('invalid parent')
                task['run_id']=job['parent_run_id']
                atomic_json(path,state)
            except Exception:results.append({'path':'job-parent-lookup','ok':False,'reason':'identity_unknown'})
        if task.get('run_id') and task.get('phase') != 'ready_pr':
            paths.append('/v1/runs/'+task['run_id']+'/stop')
    for route in paths:
        try:
            response = api('POST', route, payload={}, timeout=5)
            confirmed = response.get('paused') is True if route == '/v1/pause' else response.get('status') == 'cancelled'
            results.append({'path':route, 'ok':confirmed})
        except Exception: results.append({'path':route, 'ok':False})
    confirmed = all(item['ok'] for item in results)
    receipt = {'observed_at':time.time(), 'attempts':attempts, 'confirmed':confirmed, 'actions':results}
    if confirmed and len(paths) > 1:
        # A cancelled model job can leave the local receipt reader waiting.
        # The queue is confirmed paused and publications fenced before restart.
        restarted = subprocess.run(['systemctl','restart','loop-runner.service'],timeout=10,check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        receipt['cancelled_wait_released'] = restarted.returncode == 0
    if not confirmed and attempts >= 6:
        # Stop the dedicated publisher on Harper even when Bridge is unreachable.
        subprocess.run(['systemctl','stop','loop-runner.service'], timeout=10, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        observed = subprocess.run(['systemctl','is-active','loop-runner.service'],timeout=5,capture_output=True,text=True,check=False)
        receipt['publisher_stopped'] = observed.stdout.strip() == 'inactive'
        receipt['retry_exhausted'] = True
    atomic_json(receipt_path, receipt)
    return confirmed

def watch(manifest):
    path = Path(manifest['state_file'])
    if not path.exists(): return
    state = json_file(path)
    receipt_path=path.parent/'stop-receipt.json'
    if state.get('status') == 'completed':
        normal_completion = (type(state.get('tasks')) is list
            and all(task.get('phase') == 'ready_pr' for task in state['tasks']))
        if normal_completion:
            # Normal completion is terminal for this finite manifest.
            return
        stop(manifest)
        return
    if state.get('status') == 'blocked':
        receipt=json_file(receipt_path) if receipt_path.exists() else {}
        if receipt.get('confirmed') is not True and receipt.get('retry_exhausted') is not True:
            stop(manifest)
        return
    now = time.time()
    expired = now >= manifest['end_at'] or now - state.get('updated_at',0) > 300
    active = next((task for task in state.get('tasks', []) if task.get('phase') != 'ready_pr'), None)
    if active and active.get('started_at'):
        expired |= now >= active['started_at'] + manifest['job_timeout_seconds']
    if expired:
        subprocess.run(['systemctl','stop','loop-night.service'], timeout=30, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Also covers a dead service whose ExecStopPost did not run.
        receipt=json_file(receipt_path) if receipt_path.exists() else {}
        if receipt.get('confirmed') is not True:
            stop(manifest)

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--stop',action='store_true');args=parser.parse_args()
    try:
        m=checked(json_file(args.manifest))
        if args.stop:
            if not stop(m): raise RuntimeError('stop unconfirmed')
        else: watch(m)
    except Exception:
        print(json.dumps({'status':'blocked','reason':'night guard could not confirm stop'}))
        raise SystemExit(1)
