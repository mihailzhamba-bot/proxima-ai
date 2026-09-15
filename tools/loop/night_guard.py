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
    if state.get('status') == 'running':
        state.update(status='blocked', reason='supervisor_stopped', updated_at=time.time())
        atomic_json(path, state)
        atomic_json(path.parent/'status.json', state)
    api = BridgeClient(manifest)
    results = []
    paths = ['/v1/pause']
    for task in state.get('tasks', []):
        if task.get('run_id') and task.get('phase') != 'ready_pr':
            paths.append('/v1/runs/'+task['run_id']+'/stop')
    for route in paths:
        try: api('POST', route, payload={}, timeout=5); results.append({'path':route, 'ok':True})
        except Exception: results.append({'path':route, 'ok':False})
    atomic_json(path.parent/'stop-receipt.json', {'observed_at':time.time(), 'actions':results})
    return all(item['ok'] for item in results)

def watch(manifest):
    path = Path(manifest['state_file'])
    if not path.exists(): return
    state = json_file(path)
    if state.get('status') != 'running': return
    now = time.time()
    expired = now >= manifest['end_at'] or now - state.get('updated_at',0) > 300
    active = next((task for task in state.get('tasks', []) if task.get('phase') != 'ready_pr'), None)
    if active and active.get('started_at'):
        expired |= now >= active['started_at'] + manifest['job_timeout_seconds']
    if expired:
        subprocess.run(['systemctl','stop','loop-night.service'], timeout=30, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Also covers a dead service whose ExecStopPost did not run.
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
