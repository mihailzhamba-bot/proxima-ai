#!/usr/bin/python3 -I
"""Run fixed overnight assertions only inside the pinned offline verifier."""
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import signal

IMAGE = 'localhost:5000/loop-verification/producer@sha256:cf2053695d05fc3ee894def2eee3b25f1e2c1aff252fef7e0b1038937327dd31'

def command(checkout, base, head, job, name):
    if not all(re.fullmatch(r'[0-9a-f]{40}', value) for value in (base, head)):
        raise ValueError('invalid sha')
    if job not in {'night-20260915-observation', 'night-20260915-diagnosis'} and not re.fullmatch(r'tg-[0-9a-f]{32}', job):
        raise ValueError('unapproved job')
    checkout = Path(checkout)
    if checkout.is_symlink() or checkout.name != 'candidate' or checkout.parent.parent != Path('/srv/loop-runner/work'):
        raise ValueError('untrusted checkout location')
    if not checkout.parent.name.startswith('loop-' + job + '-'):
        raise ValueError('candidate job differs')
    mounts = ['-v', str(checkout) + ':/work:ro', '-v', '/opt/loop-review/night_acceptance.ts:/acceptance/check.ts:ro']
    for i, target in enumerate(['node_modules', 'services/webapp/node_modules', 'services/collector/node_modules', 'services/control-plane/.venv']):
        source = checkout.parent/'writable'/('dep-'+str(i))
        if source.is_symlink() or not source.is_dir(): raise ValueError('prepared dependency missing')
        mounts += ['-v', str(source)+':/work/'+target+':ro']
    return ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--memory', '512m', '--cpus', '1', '--pids-limit', '64',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--read-only', '--user', '1000:1000',
            '--tmpfs', '/tmp:rw,noexec,size=64m', *mounts, '-w', '/work', IMAGE,
            'node', '--import', '/work/node_modules/tsx/dist/loader.mjs', '/acceptance/check.ts', job]

def main():
    checkout, base, head, job = sys.argv[1:]
    name = 'loop-night-accept-' + uuid.uuid4().hex
    argv = command(checkout, base, head, job, name)
    def interrupted(*_): raise RuntimeError('acceptance interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        subprocess.run(argv, check=True, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        subprocess.run(['docker', 'rm', '--force', name], timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print(json.dumps({'sha': head, 'status': 'pass', 'skipped': 0}))

if __name__ == '__main__':
    try: main()
    except Exception:
        print(json.dumps({'status': 'blocked', 'reason': 'independent acceptance failed'}))
        raise SystemExit(1)
