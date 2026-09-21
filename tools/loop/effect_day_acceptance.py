#!/usr/bin/python3 -I
"""Independently verify effect-day selection in the pinned offline image."""
import json
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid

IMAGE = 'localhost:5000/loop-verification/producer@sha256:cf2053695d05fc3ee894def2eee3b25f1e2c1aff252fef7e0b1038937327dd31'
JOB = 'day-20260916-effect-day'
APPROVED_JOBS = frozenset({JOB, JOB + '-r2', JOB + '-r3'})
MAX_OUTPUT = 100_000
RUNNER_ROOT = Path('/srv/loop-runner/work')
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', re.I)
SHA256 = re.compile(r'[0-9a-f]{64}')
TASK_ID = '11111111-1111-4111-8111-111111111111'
FACT_RUN_ID = '33333333-3333-4333-8333-333333333333'
SOURCES = ['a' * 64, 'b' * 64]
WORKER_PROMPT = (
    'Edit only services/webapp/src/lib/loop/service.ts. In createQueueService.observe, '
    'use the computed Moscow observation end day ' + chr(96) + 'end' + chr(96) +
    ' for the fact_nm_daily_current calendar_day argument and snapshot.evaluation_day '
    'instead of row.brief_day. Make only this two-line change; do not alter SQL '
    'structure, authorization, or other functions. '
    'Create exactly one commit containing only services/webapp/src/lib/loop/service.ts. '
    'Commit: fix(loop): use observation target day. Do not push.'
)


def worker_prompt():
    return WORKER_PROMPT


def command(checkout, base, head, job, name):
    if not all(re.fullmatch(r'[0-9a-f]{40}', value) for value in (base, head)):
        raise ValueError('invalid sha')
    if job not in APPROVED_JOBS or not re.fullmatch(r'loop-effect-day-accept-[0-9a-f]{32}', name):
        raise ValueError('unapproved job')
    checkout = Path(checkout)
    expected_parent = RUNNER_ROOT
    if (checkout.is_symlink() or not checkout.is_dir() or checkout.name != 'candidate'
            or checkout.parent.parent != expected_parent
            or not checkout.parent.name.startswith('loop-' + job + '-')
            or checkout.resolve() != checkout):
        raise ValueError('untrusted checkout location')
    mounts = [
        '-v', str(checkout) + ':/work:ro',
        '-v', '/opt/loop-review/effect_day_acceptance.ts:/acceptance/check.ts:ro',
    ]
    targets = [
        'node_modules',
        'services/webapp/node_modules',
        'services/collector/node_modules',
        'services/control-plane/.venv',
    ]
    for index, target in enumerate(targets):
        source = checkout.parent / 'writable' / ('dep-' + str(index))
        if source.is_symlink() or not source.is_dir() or source.resolve() != source:
            raise ValueError('prepared dependency missing')
        mounts += ['-v', str(source) + ':/work/' + target + ':ro']
    return [
        'docker', 'run', '--rm', '--name', name, '--network', 'none',
        '--memory', '512m', '--cpus', '1', '--pids-limit', '64',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
        '--read-only', '--user', '1000:1000',
        '--tmpfs', '/tmp:rw,noexec,size=64m',
        *mounts, '-w', '/work', IMAGE,
        'timeout', '--kill-after=5s', '80s',
        'node', '--import', '/work/node_modules/tsx/dist/loader.mjs',
        '/acceptance/check.ts', job,
    ]


def _unique_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate output key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def _call(call):
    if type(call) is not dict or set(call) != {'sql', 'args'}:
        raise ValueError('invalid query capture')
    if type(call['sql']) is not str or not call['sql'].strip():
        raise ValueError('invalid query capture')
    if call['args'] is not None and type(call['args']) is not list:
        raise ValueError('invalid query capture')
    return ' '.join(call['sql'].split()), call['args']


def _uuid(value):
    return type(value) is str and UUID.fullmatch(value) is not None


def _validate_sequence(case, target_day, missing):
    if type(case) is not dict or set(case) != {'name', 'calls', 'release_count'}:
        raise ValueError('invalid case')
    if type(case['calls']) is not list or len(case['calls']) != 14 or case['release_count'] != 1:
        raise ValueError('incomplete query sequence')
    calls = [_call(item) for item in case['calls']]
    sql = [item[0] for item in calls]
    args = [item[1] for item in calls]
    checks = [
        sql[0] == 'BEGIN',
        sql[1].startswith("SELECT set_config('proxima.tenant_id'"),
        sql[2].startswith('SELECT role FROM cabinet_memberships'),
        sql[3].startswith('SELECT pg_advisory_xact_lock'),
        sql[4].startswith('SELECT t.task_id, t.assignee_id'),
        sql[5].startswith('SELECT pg_advisory_xact_lock'),
        sql[6].startswith('SELECT run_id, request_hash, result FROM workflow_runs'),
        sql[7].startswith('INSERT INTO workflow_runs'),
        sql[8].startswith('SELECT b.run_id, b.brief_day::text, b.payload FROM brief_current'),
        sql[9].startswith('SELECT d.signal_snapshot, d.payload FROM decision_records'),
        sql[10].startswith('SELECT calendar_day::text, orders_count, revenue_rub::text, run_id, evidence_sha256 FROM fact_nm_daily_current'),
        sql[11].startswith('INSERT INTO task_observations'),
        sql[12].startswith("UPDATE workflow_runs SET state='succeeded'"),
        sql[13] == 'COMMIT',
    ]
    if not all(checks):
        raise ValueError('query sequence changed')
    if args[0] is not None or args[13] is not None:
        raise ValueError('transaction capture changed')
    if args[1] != ['tenant-a'] or args[2] != ['tenant-a', 'owner-a']:
        raise ValueError('tenant membership changed')
    if args[3] != ['tenant-a:task:' + TASK_ID]:
        raise ValueError('task lock changed')
    if args[4] != ['tenant-a', TASK_ID, 'owner', 'owner-a']:
        raise ValueError('task authorization changed')
    expected_key = 'observe-' + case['name']
    if args[5] != ['tenant-a:owner-a:' + expected_key]:
        raise ValueError('command lock changed')
    if args[6] != ['tenant-a', 'owner-a', expected_key]:
        raise ValueError('command lookup changed')
    workflow = args[7]
    if (type(workflow) is not list or len(workflow) != 6 or workflow[0] != 'tenant-a'
            or not _uuid(workflow[1]) or workflow[2:5] != ['owner-a', 'observe', expected_key]
            or type(workflow[5]) is not str or not SHA256.fullmatch(workflow[5])):
        raise ValueError('workflow insert changed')
    if args[8] != ['tenant-a'] or args[9] != ['tenant-a', TASK_ID]:
        raise ValueError('evidence lookup changed')
    if args[10] != ['tenant-a', 12345, target_day]:
        raise ValueError('effect day query changed')
    observation = args[11]
    if (type(observation) is not list or len(observation) != 8
            or observation[0] != 'tenant-a' or not _uuid(observation[1])
            or observation[2] != TASK_ID or observation[3] != workflow[1]
            or observation[4] != 'owner-a'):
        raise ValueError('observation identity changed')
    if missing:
        if observation[5] != 'unknown' or type(observation[6]) is not str or not observation[6].strip() or observation[7] is not None:
            raise ValueError('missing fact outcome changed')
    else:
        if observation[5] != 'observed' or type(observation[6]) is not str:
            raise ValueError('observed outcome changed')
        snapshot = observation[7]
        if type(snapshot) is not dict or set(snapshot) != {'grain', 'nm_id', 'baseline', 'evaluation_day', 'fact_run_id', 'measurements'}:
            raise ValueError('snapshot schema changed')
        if (snapshot['grain'] != 'sku' or snapshot['nm_id'] != 12345
                or snapshot['evaluation_day'] != target_day
                or snapshot['fact_run_id'] != FACT_RUN_ID):
            raise ValueError('snapshot identity changed')
        measurements = snapshot['measurements']
        if type(measurements) is not list or len(measurements) != 2:
            raise ValueError('measurements changed')
        expected = [
            ('orders', '9.00', '10.00', 'count'),
            ('revenue', '90.00', '100.00', 'RUB'),
        ]
        for item, values in zip(measurements, expected):
            if type(item) is not dict:
                raise ValueError('measurement schema changed')
            if (item.get('name'), item.get('expected'), item.get('actual'), item.get('unit')) != values:
                raise ValueError('measurement changed')
            if item.get('target_reached') is not True or item.get('source_refs') != SOURCES:
                raise ValueError('measurement evidence changed')
    finish = args[12]
    if (type(finish) is not list or len(finish) != 3 or finish[0] != 'tenant-a'
            or finish[1] != workflow[1]
            or finish[2] != {'taskId': TASK_ID, 'runId': workflow[1]}):
        raise ValueError('workflow finish changed')


def validate_output(raw, job):
    if not isinstance(raw, (bytes, str)):
        raise ValueError('invalid output')
    if len(raw) > MAX_OUTPUT:
        raise ValueError('output limit')
    value = _unique_json(raw)
    if (type(value) is not dict or set(value) != {'version', 'job_id', 'cases'}
            or value.get('version') != 1 or value.get('job_id') != job or job not in APPROVED_JOBS):
        raise ValueError('incomplete evaluator output')
    cases = value['cases']
    if type(cases) is not list or len(cases) != 3:
        raise ValueError('incomplete evaluator output')
    expected = [
        ('before-moscow-midnight', '2026-09-14', False),
        ('at-moscow-midnight', '2026-09-15', False),
        ('missing-fact', '2026-09-15', True),
    ]
    for case, (name, target_day, missing) in zip(cases, expected):
        if type(case) is not dict or case.get('name') != name:
            raise ValueError('case order changed')
        _validate_sequence(case, target_day, missing)


def main():
    checkout, base, head, job = sys.argv[1:]
    name = 'loop-effect-day-accept-' + uuid.uuid4().hex
    argv = command(checkout, base, head, job, name)

    def interrupted(*_args):
        raise RuntimeError('acceptance interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    process = None
    try:
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(
                argv, stdout=output, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL
            )
            deadline = time.monotonic() + 90
            while process.poll() is None:
                if output.tell() > MAX_OUTPUT or time.monotonic() >= deadline:
                    raise RuntimeError('evaluation bounded limit')
                time.sleep(0.1)
            if process.returncode:
                raise ValueError('candidate evaluation failed')
            output.seek(0)
            raw = output.read(MAX_OUTPUT + 1)
            validate_output(raw, job)
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        subprocess.run(
            ['docker', 'rm', '--force', name], timeout=10,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    print(json.dumps({
        'sha': head,
        'status': 'pass',
        'skipped': 0,
        'worker_prompt': worker_prompt(),
    }))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'status': 'blocked', 'reason': 'independent acceptance failed'}))
        raise SystemExit(1)
