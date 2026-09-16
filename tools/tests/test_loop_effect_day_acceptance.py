import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / 'tools/loop/effect_day_acceptance.py'
    spec = importlib.util.spec_from_file_location('effect_day_acceptance', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def calls_for(name, target_day, missing=False):
    m = module()
    run_id = '22222222-2222-4222-8222-222222222222'
    observation_id = '44444444-4444-4444-8444-444444444444'
    key = 'observe-' + name
    metrics = [
        {'name': 'orders', 'value': '9.00', 'unit': 'count', 'source_ref': 'goal-orders'},
        {'name': 'revenue', 'value': '90.00', 'unit': 'RUB', 'source_ref': 'goal-revenue'},
    ]
    snapshot = None if missing else {
        'grain': 'sku',
        'nm_id': 12345,
        'baseline': {'detection_data': {'level': {'value': 'sku'}, 'nm_id': {'value': 12345}}},
        'evaluation_day': target_day,
        'fact_run_id': m.FACT_RUN_ID,
        'measurements': [
            {**metrics[0], 'expected': '9.00', 'actual': '10.00',
             'target_reached': True, 'source_refs': m.SOURCES},
            {**metrics[1], 'expected': '90.00', 'actual': '100.00',
             'target_reached': True, 'source_refs': m.SOURCES},
        ],
    }
    reason = 'missing fact' if missing else 'target reached'
    sql = [
        'BEGIN',
        "SELECT set_config('proxima.tenant_id', $1, true)",
        'SELECT role FROM cabinet_memberships WHERE tenant_id=$1',
        'SELECT pg_advisory_xact_lock(hashtextextended($1, 0))',
        'SELECT t.task_id, t.assignee_id FROM loop_tasks t',
        'SELECT pg_advisory_xact_lock(hashtextextended($1, 0))',
        'SELECT run_id, request_hash, result FROM workflow_runs',
        "INSERT INTO workflow_runs values ($1,$2,$3,$4,$5,$6,'running')",
        'SELECT b.run_id, b.brief_day::text, b.payload FROM brief_current b',
        'SELECT d.signal_snapshot, d.payload FROM decision_records d',
        'SELECT calendar_day::text, orders_count, revenue_rub::text, run_id, evidence_sha256 FROM fact_nm_daily_current',
        'INSERT INTO task_observations values ($1,$2,$3,$4,$5,$6,$7,$8)',
        "UPDATE workflow_runs SET state='succeeded'",
        'COMMIT',
    ]
    args = [
        None,
        ['tenant-a'],
        ['tenant-a', 'owner-a'],
        ['tenant-a:task:' + m.TASK_ID],
        ['tenant-a', m.TASK_ID, 'owner', 'owner-a'],
        ['tenant-a:owner-a:' + key],
        ['tenant-a', 'owner-a', key],
        ['tenant-a', run_id, 'owner-a', 'observe', key, 'c' * 64],
        ['tenant-a'],
        ['tenant-a', m.TASK_ID],
        ['tenant-a', 12345, target_day],
        ['tenant-a', observation_id, m.TASK_ID, run_id, 'owner-a',
         'unknown' if missing else 'observed', reason, snapshot],
        ['tenant-a', run_id, {'taskId': m.TASK_ID, 'runId': run_id}],
        None,
    ]
    return [{'sql': query, 'args': values} for query, values in zip(sql, args)]


def valid_payload():
    m = module()
    specs = [
        ('before-moscow-midnight', '2026-09-14', False),
        ('at-moscow-midnight', '2026-09-15', False),
        ('missing-fact', '2026-09-15', True),
    ]
    return {
        'version': 1,
        'job_id': m.JOB,
        'cases': [
            {'name': name, 'calls': calls_for(name, day, missing), 'release_count': 1}
            for name, day, missing in specs
        ],
    }


def test_complete_host_assertions_accept_expected_capture():
    m = module()
    m.validate_output(json.dumps(valid_payload()), m.JOB)


@pytest.mark.parametrize('raw', [
    b'',
    b'null',
    b'{}',
    b'{"version":1,"version":1}',
    json.dumps({'version': 1, 'job_id': 'wrong', 'cases': []}),
])
def test_exit_zero_or_malformed_output_cannot_pass(raw):
    m = module()
    with pytest.raises((ValueError, TypeError, KeyError, json.JSONDecodeError)):
        m.validate_output(raw, m.JOB)


def test_old_brief_day_query_is_red():
    m = module()
    payload = valid_payload()
    payload['cases'][0]['calls'][10]['args'][2] = '2026-09-16'
    with pytest.raises(ValueError, match='effect day query changed'):
        m.validate_output(json.dumps(payload), m.JOB)


def test_old_brief_day_snapshot_is_red():
    m = module()
    payload = valid_payload()
    payload['cases'][1]['calls'][11]['args'][7]['evaluation_day'] = '2026-09-16'
    with pytest.raises(ValueError, match='snapshot identity changed'):
        m.validate_output(json.dumps(payload), m.JOB)


def test_missing_fact_must_query_target_day_and_store_null_snapshot():
    m = module()
    payload = valid_payload()
    payload['cases'][2]['calls'][11]['args'][7] = {'evaluation_day': '2026-09-15'}
    with pytest.raises(ValueError, match='missing fact outcome changed'):
        m.validate_output(json.dumps(payload), m.JOB)


def test_measurements_require_exact_values_and_source_refs():
    m = module()
    payload = valid_payload()
    payload['cases'][0]['calls'][11]['args'][7]['measurements'][0]['source_refs'] = ['a' * 64]
    with pytest.raises(ValueError, match='measurement evidence changed'):
        m.validate_output(json.dumps(payload), m.JOB)


def test_candidate_location_and_job_are_fixed(tmp_path):
    m = module()
    with pytest.raises(ValueError):
        m.command('/tmp/candidate', 'a' * 40, 'b' * 40, m.JOB,
                  'loop-effect-day-accept-' + 'c' * 32)
    with pytest.raises(ValueError):
        m.command(tmp_path, 'a' * 40, 'b' * 40, 'other',
                  'loop-effect-day-accept-' + 'c' * 32)


@pytest.mark.parametrize("retry_suffix", ["", "-r2", "-r3"])
def test_command_is_pinned_offline_readonly_and_has_four_ro_dependencies(tmp_path, retry_suffix):
    m = module()
    job = m.JOB + retry_suffix
    m.RUNNER_ROOT = tmp_path
    job_root = tmp_path / ('loop-' + job + '-fixture')
    candidate = job_root / 'candidate'
    candidate.mkdir(parents=True)
    for index in range(4):
        (job_root / 'writable' / ('dep-' + str(index))).mkdir(parents=True)
    name = 'loop-effect-day-accept-' + 'c' * 32
    argv = m.command(candidate, 'a' * 40, 'b' * 40, job, name)
    assert argv[:6] == ['docker', 'run', '--rm', '--name', name, '--network']
    assert argv[6] == 'none'
    assert ['--read-only', '--user', '1000:1000'] == argv[
        argv.index('--read-only'):argv.index('--read-only') + 3]
    assert m.IMAGE in argv
    assert m.IMAGE.endswith('cf2053695d05fc3ee894def2eee3b25f1e2c1aff252fef7e0b1038937327dd31')
    mounts = [argv[index + 1] for index, item in enumerate(argv) if item == '-v']
    assert str(candidate) + ':/work:ro' in mounts
    assert '/opt/loop-review/effect_day_acceptance.ts:/acceptance/check.ts:ro' in mounts
    assert sum(value.endswith(':ro') and '/writable/dep-' in value for value in mounts) == 4
    assert argv[-5:] == ['node', '--import', '/work/node_modules/tsx/dist/loader.mjs',
                         '/acceptance/check.ts', job]


def test_evaluator_output_is_bounded():
    m = module()
    with pytest.raises(ValueError, match='output limit'):
        m.validate_output(b'x' * (m.MAX_OUTPUT + 1), m.JOB)


def test_typescript_evaluator_has_intact_output_statements():
    path = Path(__file__).resolve().parents[2] / 'infra/loop-control/effect_day_acceptance.ts'
    source = path.read_text()
    assert 'String.fromCharCode(10)' in source
    assert '+ "\n"' not in source
    assert 'process.exitCode = 1;' in source


def test_worker_prompt_is_fixed_to_two_line_service_change():
    prompt = module().worker_prompt()
    assert 'only services/webapp/src/lib/loop/service.ts' in prompt
    assert chr(96) + 'end' + chr(96) in prompt and 'row.brief_day' in prompt
    assert 'two-line change' in prompt
    assert 'do not alter SQL structure, authorization, or other functions' in prompt
    assert "Create exactly one commit containing only services/webapp/src/lib/loop/service.ts" in prompt
    assert "Commit: fix(loop): use observation target day" in prompt
    assert len(prompt) < 800


@pytest.mark.parametrize("retry_suffix", ["-r2", "-r3"])
def test_retry_result_is_bound_to_exact_approved_job(retry_suffix):
    m = module()
    payload = valid_payload()
    payload["job_id"] = m.JOB + retry_suffix
    m.validate_output(json.dumps(payload), m.JOB + retry_suffix)
    with pytest.raises(ValueError):
        m.validate_output(json.dumps(payload), m.JOB)
    payload["job_id"] = m.JOB + "-r4"
    with pytest.raises(ValueError):
        m.validate_output(json.dumps(payload), m.JOB + "-r4")
