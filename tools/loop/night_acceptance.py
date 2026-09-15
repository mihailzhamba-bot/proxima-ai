#!/usr/bin/python3 -I
"""Run fixed overnight assertions only inside the pinned offline verifier."""
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import signal
import tempfile
import time

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
            'timeout', '--kill-after=5s', '80s', 'node', '--import', '/work/node_modules/tsx/dist/loader.mjs', '/acceptance/check.ts', job]

def validate_output(raw, job):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result: raise ValueError('duplicate output key')
            result[k] = v
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    if set(value) != {'version', 'job_id', 'results'} or type(value['version']) is not int or value['version'] != 1 or value['job_id'] != job:
        raise ValueError('incomplete evaluator output')
    results = value['results']
    if type(results) is not list: raise ValueError('invalid output')
    if job.startswith('tg-'):
        if results != ['paperclip-hermes-openhands-harper']: raise ValueError('route assertion')
    elif job == 'night-20260915-observation':
        if len(results) != 16 or results[-1] is not None or not all(type(x) is str and x.strip() for x in results[:-1]):
            raise ValueError('observation assertions')
    elif job == 'night-20260915-diagnosis':
        if len(results) != 23 or any(type(x) is not dict for x in results): raise ValueError('diagnosis output')
        for i in [*range(9), *range(14,18), *range(19,23)]:
            if results[i].get('facts') != [] or not results[i].get('unknowns'): raise ValueError('unverified fact')
        for i, expected in [(9,0),(10,12),(11,'0.00'),(12,'12345678901234567890.12'),(13,'-30.00'),(18,12)]:
            facts = results[i].get('facts', [])
            if len(facts) != 1 or type(facts[0].get('value')) is not type(expected) or facts[0]['value'] != expected or facts[0].get('sourceRefs') != ['fixture-source-exact']:
                raise ValueError('verified fact changed')
            if facts[0].get('date') != ('2024-02-29' if i == 18 else '2026-09-15'): raise ValueError('fact day changed')
    else: raise ValueError('unapproved job')

def main():
    checkout, base, head, job = sys.argv[1:]
    name = 'loop-night-accept-' + uuid.uuid4().hex
    argv = command(checkout, base, head, job, name)
    def interrupted(*_): raise RuntimeError('acceptance interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    process = None
    try:
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(argv, stdout=output, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 90
            while process.poll() is None:
                if output.tell() > 100_000 or time.monotonic() >= deadline: raise RuntimeError('evaluation bounded limit')
                time.sleep(.1)
            if process.returncode: raise ValueError('candidate evaluation failed')
            output.seek(0)
            raw = output.read(100_001)
            if len(raw) > 100_000: raise ValueError('output limit')
            validate_output(raw, job)
    finally:
        if process and process.poll() is None:
            process.kill(); process.wait(timeout=5)
        subprocess.run(['docker', 'rm', '--force', name], timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print(json.dumps({'sha': head, 'status': 'pass', 'skipped': 0}))

if __name__ == '__main__':
    try: main()
    except Exception:
        print(json.dumps({'status': 'blocked', 'reason': 'independent acceptance failed'}))
        raise SystemExit(1)
