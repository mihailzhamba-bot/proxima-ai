import json
import fcntl
import os
from pathlib import Path
import sys
import stat
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import night_batch as driver


def manifest(tmp_path, count=1):
    work = tmp_path / 'work'; work.mkdir(exist_ok=True)
    return {'tasks': [{'key': 'night-key-' + str(n), 'job_id': 'night-job-' + str(n),
                      'template': 'night-template', 'template_fingerprint': 'd' * 64} for n in range(count)],
        'template_bases': {'night-template': 'a' * 40}, 'end_at': 2000,
        'job_timeout_seconds': 120, 'poll_seconds': 10, 'disk_floor_bytes': 3 * 1024**3,
        'state_file': str(tmp_path / 'state.json'), 'work_root': str(work),
        'evidence_root': str(tmp_path / 'evidence'), 'glm_config': str(tmp_path / 'glm.json'),
        'glm_script': str(tmp_path / 'glm_review.py'), 'review_receipts': str(tmp_path / 'receipts'),
        'operator_key_file': str(tmp_path / 'operator-key'), 'runner_key_file': str(tmp_path / 'runner-key')}


class Clock:
    def __init__(self):
        self.now = 1000
    def __call__(self):
        return self.now
    def sleep(self, duration):
        self.now += duration


class Stage:
    def __init__(self, blocked=False, clock=None):
        self.calls, self.admissions = [], []
        self.blocked, self.clock = blocked, clock
    def observe(self, _task):
        return {'checkout': '/fixture/candidate', 'base_sha': 'a' * 40,
                'head_sha': 'b' * 40, 'diff_sha256': 'c' * 64}
    def review(self, observed, timeout):
        self.calls.append((observed, timeout))
        if self.clock:
            self.clock.now += 200
        if self.blocked:
            raise driver.BatchError('glm_review_blocked')
        return {**observed, 'model': 'glm-5.3-flash', 'reviewed_at_utc': 'fixture-date',
                'evidence_ref': '/fixture/evidence'}
    def admit(self, reviewed):
        self.admissions.append(reviewed)


class HTTP:
    def __init__(self, settings, stage=None, run_status='running', job_state='dispatching', nojob=False):
        self.settings, self.stage, self.run_status, self.job_state, self.nojob = settings, stage, run_status, job_state, nojob
        self.calls = []
        self.parent_run_id = None
    def __call__(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == '/v1/wake':
            assert kwargs['payload']['source'] == 'operator_batch'
            assert kwargs['key'].startswith('night-key-')
            return {'run_id': 'run-' + kwargs['payload']['job_id'], 'status': 'running'}
        if path.endswith('/stop') or path == '/v1/pause':
            return {'status': 'stopped'}
        if path.startswith('/v1/runner/jobs/'):
            assert kwargs['role'] == 'runner'
            if self.nojob:
                raise driver.HTTPError(404)
            index = int(path.rsplit('-', 1)[1])
            state = 'ready_pr' if self.stage and len(self.stage.admissions) > index else self.job_state
            return {'state': state, 'template': 'night-template', 'template_fingerprint': 'd' * 64,
                    'parent_run_id': self.parent_run_id,
                    'pr_url': 'https://github.com/fixture/pull/1', 'candidate_sha': 'b' * 40}
        if path.startswith('/v1/runs/'):
            self.parent_run_id = path.rsplit('/', 1)[1]
            return {'status': self.run_status}
        raise AssertionError(path)


def execute(settings, http=None, stage=None, clock=None, disk=None):
    clock = clock or Clock(); stage = stage or Stage()
    http = http or HTTP(settings, stage)
    result = driver.Batch(settings, http, stage, clock, clock.sleep,
                         disk_free=disk or (lambda _: 10 * 1024**3)).run()
    return result, http, stage, clock


def test_review_then_ready_pr_then_next_task(tmp_path):
    settings = manifest(tmp_path, 2)
    result, http, stage, _ = execute(settings)
    assert result['status'] == 'completed'
    assert all(task['phase'] == 'ready_pr' for task in result['tasks'])
    assert len(stage.calls) == 1  # exact SHA review reused across both fixture tasks
    wake = [call for call in http.calls if call[1] == '/v1/wake']
    assert len(wake) == 2
    assert http.calls[-1][1] == '/v1/pause'
    assert json.loads((tmp_path / 'status.json').read_text())['status'] == 'completed'


def test_lost_dispatch_response_never_reposts(tmp_path):
    settings = manifest(tmp_path)
    http = HTTP(settings)
    original = http.__call__
    calls = []
    def lost(method, path, **kwargs):
        calls.append(path)
        if path == '/v1/wake':
            persisted = json.loads(Path(settings['state_file']).read_text())
            assert persisted['tasks'][0]['phase'] == 'dispatching'
            raise TimeoutError('secret raw failure')
        return original(method, path, **kwargs)
    result, _, _, _ = execute(settings, lost)
    assert result['status'] == 'blocked'
    assert 'secret' not in result['reason']
    assert calls.count('/v1/wake') == 1
    result, _, _, _ = execute(settings, lost)
    assert result['status'] == 'blocked' and calls.count('/v1/wake') == 1


@pytest.mark.parametrize('phase', ['dispatching', 'reviewing'])
def test_restart_uncertain_phase_halts(tmp_path, phase):
    settings = manifest(tmp_path)
    batch = driver.Batch(settings, None, None)
    state = {'status': 'running', 'manifest_sha256': batch.digest,
             'tasks': [{'key': settings['tasks'][0]['key'], 'job_id': settings['tasks'][0]['job_id'],
                        'phase': phase, 'run_id': 'existing-run'}]}
    driver.atomic_json(settings['state_file'], state)
    result, http, stage, _ = execute(settings)
    assert result['reason'] == 'uncertain_' + phase
    assert not stage.calls
    assert [call[1] for call in http.calls] == ['/v1/pause', '/v1/runs/existing-run/stop']


def test_existing_run_monitor_without_wake(tmp_path):
    settings = manifest(tmp_path)
    settings['tasks'][0]['existing_run_id'] = 'existing-run'
    result, http, _, _ = execute(settings)
    assert result['status'] == 'completed'
    assert not any(call[1] == '/v1/wake' for call in http.calls)


def test_completed_no_job_is_not_success(tmp_path):
    settings = manifest(tmp_path)
    result, _, stage, clock = execute(settings, HTTP(settings, run_status='completed', nojob=True))
    assert result['reason'] == 'completed_without_job'
    assert clock.now == 1060 and not stage.calls


@pytest.mark.parametrize('kind', ['deadline', 'job_timeout', 'disk'])
def test_limits_pause_stop_and_no_next_dispatch(tmp_path, kind):
    settings = manifest(tmp_path, 2)
    settings['end_at'] = 1020 if kind == 'deadline' else 2000
    settings['job_timeout_seconds'] = 20
    http = HTTP(settings, nojob=True)
    result, http, _, _ = execute(settings, http, disk=(lambda _: 0) if kind == 'disk' else None)
    assert result['reason'] == {'deadline': 'batch_deadline', 'job_timeout': 'job_timeout', 'disk': 'disk_floor'}[kind]
    assert len([call for call in http.calls if call[1] == '/v1/wake']) <= 1
    assert any(call[1] == '/v1/pause' for call in http.calls)
    if kind != 'disk':
        assert any(call[1].endswith('/stop') for call in http.calls)


@pytest.mark.parametrize('state', ['unknown', 'cancelled', 'failed', 'quarantined', 'recoverable', 'invalid'])
def test_bad_job_halts_before_review(tmp_path, state):
    settings = manifest(tmp_path, 2)
    result, _, stage, _ = execute(settings, HTTP(settings, job_state=state))
    assert result['reason'] == 'job_terminal_or_unknown'
    assert not stage.calls


def test_glm_blocked_never_admits_or_advances(tmp_path):
    settings = manifest(tmp_path, 2)
    stage = Stage(blocked=True)
    result, http, stage, _ = execute(settings, HTTP(settings, stage), stage)
    assert result['reason'] == 'glm_review_blocked'
    assert len(stage.calls) == 1 and not stage.admissions
    assert len([call for call in http.calls if call[1] == '/v1/wake']) == 1


def test_deadline_crossed_during_model_no_receipt(tmp_path):
    settings = manifest(tmp_path)
    clock = Clock(); stage = Stage(clock=clock)
    result, _, _, _ = execute(settings, HTTP(settings, stage), stage, clock)
    assert result['reason'] == 'review_deadline' and not stage.admissions


def test_model_intent_saved_before_call(tmp_path):
    settings = manifest(tmp_path)
    stage = Stage()
    original = stage.review
    def review(observed, timeout):
        persisted = json.loads(Path(settings['state_file']).read_text())
        assert persisted['tasks'][0]['phase'] == 'reviewing'
        assert persisted['tasks'][0]['review_sha'] == observed['head_sha']
        return original(observed, timeout)
    stage.review = review
    assert execute(settings, HTTP(settings, stage), stage)[0]['status'] == 'completed'


def test_duplicate_manifest_rejected(tmp_path):
    settings = manifest(tmp_path, 2)
    settings['tasks'][1] = settings['tasks'][0].copy()
    with pytest.raises(driver.BatchError, match='duplicate_task'):
        driver.checked(settings)


def test_changed_manifest_cannot_restart(tmp_path):
    settings = manifest(tmp_path)
    execute(settings)
    settings['end_at'] += 1
    with pytest.raises(driver.BatchError, match='manifest_changed'):
        execute(settings)


def test_state_is_mode_600(tmp_path):
    settings = manifest(tmp_path)
    execute(settings)
    assert Path(settings['state_file']).stat().st_mode & 0o777 == 0o600


def test_stage_discovery_checks_both_exact_receipts(tmp_path, monkeypatch):
    settings = manifest(tmp_path)
    candidate = Path(settings['work_root']) / 'loop-night-job-0-fixture/candidate'
    candidate.mkdir(parents=True)
    evidence = Path(settings['evidence_root']) / 'night-job-0/123'
    evidence.mkdir(parents=True)
    monkeypatch.setattr(driver, 'git', lambda *_: ('b' * 40).encode())
    scope = {'base_sha': 'a' * 40, 'head_sha': 'b' * 40, 'diff_sha256': 'c' * 64}
    monkeypatch.setattr(driver, 'fingerprint', lambda *_: scope)
    for name in ('verify', 'build'):
        driver.atomic_json(evidence / (name + '-receipt.json'), {'status': 'pass',
            'checks': {name: {'sha': 'b' * 40, 'status': 'pass', 'skipped': 0}}})
    stage = driver.ReviewStage(settings)
    assert stage.observe(settings['tasks'][0])['head_sha'] == 'b' * 40
    driver.atomic_json(evidence / 'build-receipt.json', {'status': 'pass',
        'checks': {'build': {'sha': 'b' * 40, 'status': 'pass', 'skipped': 1}}})
    assert stage.observe(settings['tasks'][0]) is None


def test_stage_rejects_model_artifact_wrong_sha(tmp_path, monkeypatch):
    settings = manifest(tmp_path)
    evidence = Path(settings['evidence_root']) / 'model-review'
    evidence.mkdir(parents=True)
    artifact = evidence / 'review.json'
    scope = {'base_sha': 'a' * 40, 'head_sha': 'b' * 40, 'diff_sha256': 'c' * 64}
    driver.atomic_json(artifact, {'artifact_type': 'model-review-not-admission', 'review_complete': True,
        **scope, 'head_sha': 'f' * 40, 'model': 'glm-5.3-flash', 'verdict': {'status': 'pass', 'findings': []}})
    class Result:
        returncode = 0
        stdout = json.dumps({'status': 'pass', 'fingerprint': scope, 'evidence_path': str(artifact)}).encode()
    stage = driver.ReviewStage(settings, execute=lambda *_args, **_kwargs: Result())
    with pytest.raises(driver.BatchError, match='glm_artifact_invalid'):
        stage.review({'checkout': '/fixture', **scope}, 120)


def test_flock_prevents_second_consumer(tmp_path):
    settings = manifest(tmp_path)
    lock = os.open(settings['state_file'] + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(driver.BatchError, match='batch_already_running'):
            execute(settings)
    finally:
        os.close(lock)


def test_same_sha_across_tasks_not_double_billed(tmp_path):
    settings = manifest(tmp_path, 2)
    stage = Stage()
    http = HTTP(settings, stage)
    original = http.__call__
    def separate_jobs(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if path.startswith('/v1/runner/jobs/'):
            index = int(path.rsplit('-', 1)[1])
            result['state'] = 'ready_pr' if len(stage.admissions) > index else 'dispatching'
        return result
    result, _, _, _ = execute(settings, separate_jobs, stage)
    assert result['status'] == 'completed'
    assert len(stage.calls) == 1 and len(stage.admissions) == 2
    assert len(result['reviews']) == 1


def test_cancellation_during_model_blocks_receipt(tmp_path):
    settings = manifest(tmp_path)
    stage = Stage()
    http = HTTP(settings, stage)
    original = http.__call__
    def revoked(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if path.startswith('/v1/runs/') and stage.calls:
            result['status'] = 'cancelled'
        return result
    result, _, _, _ = execute(settings, revoked, stage)
    assert result['reason'] == 'review_attempt_revoked'
    assert not stage.admissions


def test_acceptance_hook_before_model_and_evidence(tmp_path):
    settings = manifest(tmp_path)
    settings['acceptance_command'] = ['/usr/bin/python3', '-I', '/trusted/acceptance.py']
    stage = Stage(); order = []
    def accept(observed, timeout):
        assert observed['job_id'] == 'night-job-0' and timeout <= 240
        order.append('acceptance')
        return '/fixture/acceptance.json'
    original = stage.review
    def review(observed, timeout):
        order.append('model')
        return original(observed, timeout)
    stage.accept, stage.review = accept, review
    result, _, _, _ = execute(settings, HTTP(settings, stage), stage)
    assert result['status'] == 'completed' and order == ['acceptance', 'model']
    assert result['tasks'][0]['acceptance_ref'] == '/fixture/acceptance.json'


@pytest.mark.parametrize('receipt', [{'sha': 'b' * 40, 'status': 'pass', 'skipped': 1},
    {'sha': 'c' * 40, 'status': 'pass', 'skipped': 0},
    {'sha': 'b' * 40, 'status': 'pass', 'skipped': False},
    {'sha': 'b' * 40, 'status': 'blocked', 'skipped': 0}])
def test_acceptance_fail_closed(tmp_path, receipt):
    settings = manifest(tmp_path)
    settings['acceptance_command'] = ['/trusted/acceptance']
    class Result:
        returncode = 0
        stdout = json.dumps(receipt).encode()
    calls = []
    def execute(argv, **kwargs):
        calls.append((argv, kwargs))
        return Result()
    stage = driver.ReviewStage(settings, execute)
    observed = {'checkout': '/fixture/candidate', 'base_sha': 'a' * 40,
                'head_sha': 'b' * 40, 'job_id': 'night-job-0'}
    with pytest.raises(driver.BatchError, match='independent_acceptance_blocked'):
        stage.accept(observed, 200)
    assert calls[0][0] == ['/trusted/acceptance', '/fixture/candidate', 'a' * 40, 'b' * 40, 'night-job-0']
    assert calls[0][1]['timeout'] == 120 and 'shell' not in calls[0][1]
    evidence = next((Path(settings['evidence_root']) / 'acceptance').glob('*.json'))
    assert json.loads(evidence.read_text())['status'] == 'blocked'


def test_acceptance_rejection_prevents_model(tmp_path):
    settings = manifest(tmp_path)
    settings['acceptance_command'] = ['/trusted/acceptance']
    stage = Stage()
    def accept(*_):
        raise driver.BatchError('independent_acceptance_blocked')
    stage.accept = accept
    result, _, _, _ = execute(settings, HTTP(settings, stage), stage)
    assert result['reason'] == 'independent_acceptance_blocked' and not stage.calls


def test_truncated_saved_task_list_cannot_fake_completion(tmp_path):
    settings = manifest(tmp_path, 2)
    batch = driver.Batch(settings, None, None)
    driver.atomic_json(settings['state_file'], {'status': 'running',
        'manifest_sha256': batch.digest, 'tasks': []})
    with pytest.raises(driver.BatchError, match='invalid_saved_state'):
        execute(settings)


@pytest.mark.parametrize('owner,mode,allowed,passes', [
    (1000, stat.S_IFDIR | 0o700, (0, 1000), True),
    (0, stat.S_IFDIR | 0o755, (0, 1000), True),
    (1001, stat.S_IFDIR | 0o700, (0, 1000), False),
    (1000, stat.S_IFDIR | 0o700, (0,), False),
    (1000, stat.S_IFDIR | 0o777, (0, 1000), False),
    (1000, stat.S_IFDIR | 0o770, (0, 1000), False),
    (1000, stat.S_IFLNK | 0o777, (0, 1000), False),
])
def test_runtime_directory_owner_policy(monkeypatch, owner, mode, allowed, passes):
    def info(path):
        if path == Path('/srv/loop-runner/work'):
            return SimpleNamespace(st_uid=owner, st_mode=mode)
        return SimpleNamespace(st_uid=0, st_mode=stat.S_IFDIR | 0o755)
    monkeypatch.setattr(Path, 'lstat', info)
    if passes:
        driver.trusted_directory('/srv/loop-runner/work', allowed_owners=allowed)
    else:
        with pytest.raises(driver.BatchError, match='untrusted_directory'):
            driver.trusted_directory('/srv/loop-runner/work', allowed_owners=allowed)


def test_runtime_uid_is_optional_and_bounded(tmp_path):
    settings = manifest(tmp_path)
    assert driver.checked(settings)
    settings['runtime_owner_uid'] = 1000
    assert driver.checked(settings)
    settings['runtime_owner_uid'] = True
    with pytest.raises(driver.BatchError, match='invalid_runtime_owner'):
        driver.checked(settings)


def test_poll_heartbeat_updates_during_long_monitoring(tmp_path):
    settings = manifest(tmp_path)
    clock = Clock()
    http = HTTP(settings, nojob=True)
    snapshots = []
    def sleep(duration):
        snapshots.append(json.loads(Path(settings['state_file']).read_text()))
        clock.sleep(duration)
    result = driver.Batch(settings, http, Stage(), clock, sleep,
                         disk_free=lambda _: 10 * 1024**3).run()
    assert result['reason'] == 'job_timeout'
    assert len(snapshots) == 12
    assert [saved['updated_at'] for saved in snapshots] == list(range(1000, 1120, 10))
    assert all(saved['tasks'][0]['observed_run_status'] == 'running' for saved in snapshots)
    assert all(saved['tasks'][0]['observed_job_status'] == 'absent' for saved in snapshots)


@pytest.mark.parametrize('parent', [None, 'different-parent-run'])
def test_colliding_job_parent_blocks_before_model(tmp_path, parent):
    settings = manifest(tmp_path)
    stage = Stage(); http = HTTP(settings, stage)
    def call(method, path, **kwargs):
        value = http(method, path, **kwargs)
        if path.startswith('/v1/runner/jobs/'):
            value['parent_run_id'] = parent
        return value
    result, _, _, _ = execute(settings, call, stage)
    assert result['reason'] == 'job_parent_run_mismatch'
    assert not stage.calls and not stage.admissions


def test_adopted_run_cannot_attach_other_parent_job(tmp_path):
    settings = manifest(tmp_path)
    settings['tasks'][0]['existing_run_id'] = 'adopted-parent-run'
    stage = Stage(); http = HTTP(settings, stage)
    def call(method, path, **kwargs):
        value = http(method, path, **kwargs)
        if path.startswith('/v1/runner/jobs/'):
            value['parent_run_id'] = 'other-parent-run'
        return value
    result, _, _, _ = execute(settings, call, stage)
    assert result['reason'] == 'job_parent_run_mismatch'
    assert not stage.calls
    assert not any(path == '/v1/wake' for _method, path, _kwargs in http.calls)


def test_fresh_job_lineage_checked_before_admission(tmp_path):
    settings = manifest(tmp_path)
    stage = Stage(); http = HTTP(settings, stage)
    def call(method, path, **kwargs):
        value = http(method, path, **kwargs)
        if path.startswith('/v1/runner/jobs/') and stage.calls:
            value['parent_run_id'] = 'wrong-fresh-parent'
        return value
    result, _, _, _ = execute(settings, call, stage)
    assert result['reason'] == 'review_attempt_revoked'
    assert len(stage.calls) == 1 and not stage.admissions


def test_ready_pr_requires_this_batch_recorded_review(tmp_path):
    settings = manifest(tmp_path)
    stage = Stage(); http = HTTP(settings, job_state='ready_pr')
    result, _, _, _ = execute(settings, http, stage)
    assert result['reason'] == 'ready_pr_without_batch_review'
    assert not stage.calls and not stage.admissions


def test_disk_start_reserve_is_higher_than_inflight_floor(tmp_path):
    settings = manifest(tmp_path)
    settings['disk_floor_bytes'] = 2 * 1024**3
    result, http, _, _ = execute(settings, disk=lambda _: int(2.5 * 1024**3))
    assert result['reason'] == 'disk_start_floor'
    assert not any(call[1] == '/v1/wake' for call in http.calls)

def test_nonsecret_attestation_is_readable_but_state_stays_private(tmp_path):
    receipt=tmp_path/'receipt.json';state=tmp_path/'state-private.json'
    driver.atomic_json(receipt, {'status':'pass'},mode=0o644)
    driver.atomic_json(state, {'status':'running'})
    assert stat.S_IMODE(receipt.stat().st_mode)==0o644
    assert stat.S_IMODE(state.stat().st_mode)==0o600


def test_review_failure_keeps_only_sanitized_reason(tmp_path):
    settings = manifest(tmp_path)
    stage = driver.ReviewStage(settings, execute=lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=b'{"reason":"provider_unavailable","secret":"fixture-private"}'))
    with pytest.raises(driver.BatchError, match='provider_unavailable'):
        stage.review({'checkout':'/fixture','base_sha':'a'*40,'head_sha':'b'*40},1)
    files=list((Path(settings['evidence_root'])/'model-review').glob('error-*.json'))
    assert len(files)==1
    assert json.loads(files[0].read_text())['reason']=='provider_unavailable'
    assert 'fixture-private' not in files[0].read_text()
