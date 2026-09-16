import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import work_program as program


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args],
                                   stderr=subprocess.DEVNULL).decode().strip()


@pytest.fixture
def setup(tmp_path):
    repo = tmp_path / 'repo'
    state = tmp_path / 'state'
    evidence = tmp_path / 'evidence'
    repo.mkdir(); state.mkdir(mode=0o700); evidence.mkdir(mode=0o700)
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.name', 'Fixture')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    (repo / 'facts.txt').write_text('trusted source facts\n')
    (repo / 'other.txt').write_text('more facts\n')
    git(repo, 'add', 'facts.txt', 'other.txt')
    git(repo, 'commit', '-qm', 'base')
    config = {'enabled': True, 'source_repo': str(repo), 'state_root': str(state),
              'evidence_root': str(evidence), 'key_file': '/fixture/key',
              'max_calls_per_day': 24,
              'tasks': [{'id': 'audit-1', 'prompt': 'Find evidence gaps.',
                         'paths': ['facts.txt']},
                        {'id': 'audit-2', 'prompt': 'List follow-up research.',
                         'paths': ['other.txt']}]}
    return config, repo, state, evidence


def response(summary='Useful research.'):
    return json.dumps({'model': program.MODEL,
        'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant',
            'content': json.dumps({'summary': summary,
                                   'findings': ['One bounded finding.'],
                                   'next_steps': ['Read-only follow-up.']})}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5,
                  'total_tokens': 15}}).encode()


def allowed(**_kwargs):
    return {'allowed': True, 'reason': 'off_peak', 'resume_at': None}


def run(config, send, now=None, tariff=allowed, offpeak=lambda **_: None):
    return program.run_once(config, send=send, key_reader=lambda _: 'fixture-key',
                            now=now or datetime(2026, 9, 13, tzinfo=timezone.utc),
                            tariff_check=tariff, offpeak_check=offpeak)


def test_one_task_per_tick_artifact_and_dedup(setup):
    config, _repo, state, evidence = setup
    calls = []
    def send(payload, key, timeout):
        calls.append(payload)
        assert key == 'fixture-key' and timeout == 120
        assert payload['model'] == 'glm-5.3-flash'
        assert payload['tool_choice'] == 'none' and 'tools' not in payload
        return response()
    first = run(config, send)
    assert first['status'] == 'idle' and first['reason'] == 'task_completed'
    assert len(calls) == 1
    artifact = json.loads(Path(first['evidence_path']).read_text())
    assert artifact['artifact_type'] == 'model-research-data-not-admission'
    assert artifact['source_sha'] == git(config['source_repo'], 'rev-parse', 'HEAD')
    assert artifact['context'][0]['path'] == 'facts.txt'
    assert artifact['model'] == 'glm-5.3-flash'
    assert artifact['usage']['total_tokens'] == 15
    assert Path(first['evidence_path']).stat().st_mode & 0o777 == 0o600
    second = run(config, send)
    assert second['task_id'] == 'audit-2'
    assert len(calls) == 2
    third = run(config, send)
    assert third['status'] == 'idle' and third['reason'] == 'no_model_work'
    assert len(calls) == 2
    events = [json.loads(line) for line in (state / 'journal.jsonl').read_text().splitlines()]
    assert [item['event'] for item in events] == ['intent', 'complete', 'intent', 'complete']
    assert len(list(evidence.iterdir())) == 2


def test_changed_source_creates_new_work_key(setup):
    config, repo, _state, _evidence = setup
    config['tasks'] = config['tasks'][:1]
    calls = []
    run(config, lambda *args: calls.append(args) or response())
    (repo / 'facts.txt').write_text('changed source facts\n')
    git(repo, 'commit', '-qam', 'change')
    result = run(config, lambda *args: calls.append(args) or response())
    assert result['reason'] == 'task_completed'
    assert len(calls) == 2


def test_unrelated_head_change_does_not_repeat_unchanged_approved_context(setup):
    config, repo, _state, _evidence = setup
    config['tasks'] = config['tasks'][:1]
    calls = []
    run(config, lambda *args: calls.append(args) or response())
    (repo / 'other.txt').write_text('unrelated changed facts\n')
    git(repo, 'commit', '-qam', 'unrelated change')
    result = run(config, lambda *args: calls.append(args) or response())
    assert result['reason'] == 'no_model_work'
    assert len(calls) == 1


def test_peak_saves_waiting_without_key_or_transport(setup):
    config, _repo, _state, _evidence = setup
    calls = []
    def peak(**_kwargs):
        return {'allowed': False, 'reason': 'weekday_peak', 'resume_at': 12345}
    result = program.run_once(config, send=lambda *args: calls.append(args),
        key_reader=lambda _: (_ for _ in ()).throw(AssertionError('key read')),
        now=datetime(2026, 9, 16, 7, tzinfo=timezone.utc), tariff_check=peak)
    assert result['status'] == 'waiting_window'
    assert result['resume_at'] == 12345
    assert calls == []


def test_intent_is_fsynced_before_transport_and_unknown_never_retries(setup):
    config, _repo, state, _evidence = setup
    config['tasks'] = config['tasks'][:1]
    calls = []
    def lost(*_args):
        calls.append(1)
        events = [json.loads(line) for line in (state / 'journal.jsonl').read_text().splitlines()]
        assert events[-1]['event'] == 'intent'
        assert json.loads((state / 'state.json').read_text())['status'] == 'running'
        raise TimeoutError('raw secret network detail')
    first = run(config, lost)
    assert first['status'] == 'unknown'
    assert first['reason'] == 'provider_failure'
    second = run(config, lost)
    assert second['status'] == 'unknown'
    assert second['reason'] == 'unresolved_intent'
    assert calls == [1]
    assert 'raw secret' not in (state / 'state.json').read_text()


def test_daily_quota_counts_intents(setup):
    config, _repo, _state, _evidence = setup
    config['max_calls_per_day'] = 1
    calls = []
    run(config, lambda *args: calls.append(args) or response())
    result = run(config, lambda *args: calls.append(args) or response())
    assert result['status'] == 'idle'
    assert result['reason'] == 'daily_quota_exhausted'
    assert len(calls) == 1


def test_disabled_is_persistent_pause(setup):
    config, _repo, _state, _evidence = setup
    config['enabled'] = False
    result = run(config, lambda *_: pytest.fail('transport called'))
    assert result['status'] == 'blocked' and result['reason'] == 'config_disabled'
    assert result['enabled'] is False


@pytest.mark.parametrize('path', ['../outside', '.env', 'secrets/key', 'api_token.txt'])
def test_config_rejects_unsafe_paths(setup, path):
    config, *_ = setup
    config['tasks'][0]['paths'] = [path]
    with pytest.raises(program.ProgramError, match='unsafe_task_path'):
        program.validate_config(config)


def test_git_symlink_and_gitlink_are_rejected(setup, tmp_path):
    config, repo, _state, _evidence = setup
    (repo / 'linked').symlink_to('facts.txt')
    git(repo, 'add', 'linked'); git(repo, 'commit', '-qm', 'symlink')
    config['tasks'] = [{'id': 'linked', 'prompt': 'inspect', 'paths': ['linked']}]
    # Core collector rejects before intent/network.
    with pytest.raises(program.ProgramError, match='context_not_regular_blob'):
        program.collect_context(config, config['tasks'][0])

    sub = tmp_path / 'sub'; sub.mkdir()
    git(sub, 'init', '-q'); git(sub, 'config', 'user.name', 'Fixture')
    git(sub, 'config', 'user.email', 'fixture@example.invalid')
    (sub / 'x').write_text('x'); git(sub, 'add', 'x'); git(sub, 'commit', '-qm', 'sub')
    git(repo, 'rm', '-q', 'linked')
    subprocess.check_call(['git', '-C', str(repo), '-c', 'protocol.file.allow=always',
                           'submodule', 'add', '-q', str(sub), 'nested'])
    git(repo, 'commit', '-qm', 'gitlink')
    config['tasks'] = [{'id': 'nested', 'prompt': 'inspect', 'paths': ['nested']}]
    with pytest.raises(program.ProgramError, match='context_not_regular_blob'):
        program.collect_context(config, config['tasks'][0])


@pytest.mark.parametrize('content', [
    {'summary': '', 'findings': [], 'next_steps': []},
    {'summary': 'ok', 'findings': 'bad', 'next_steps': []},
    {'summary': 'ok', 'findings': [], 'next_steps': [], 'extra': 1},
])
def test_strict_response_schema(content):
    raw = json.loads(response())
    raw['choices'][0]['message']['content'] = json.dumps(content)
    with pytest.raises(program.ProgramError, match='invalid_or_incomplete_response'):
        program.parse_response(json.dumps(raw).encode())


def test_observe_reports_actual_window_and_stale_running(setup):
    config, _repo, state, _evidence = setup
    peak = lambda **_: {'allowed': False, 'reason': 'weekday_peak', 'resume_at': 77}
    assert program.observe(config, tariff_check=peak)['status'] == 'waiting_window'
    program.write_json_atomic(state / 'state.json',
        {'schema_version': 1, 'status': 'running', 'reason': 'intent'})
    status = program.observe(config, tariff_check=allowed)
    assert status['status'] == 'unknown'
    assert status['reason'] == 'interrupted_or_inflight_intent'


def test_systemd_units_are_bounded_and_timer_has_no_catchup():
    root = Path(__file__).resolve().parents[2]
    service = (root / 'infra/loop-control/loop-work-program.service').read_text()
    timer = (root / 'infra/loop-control/loop-work-program.timer').read_text()
    for line in ('User=root', 'MemoryMax=256M', 'CPUQuota=50%', 'TasksMax=32',
                 'TimeoutStartSec=150s', 'ProtectSystem=strict',
                 'ReadWritePaths=/var/lib/loop-work-program /srv/loop/work-program/results'):
        assert line in service
    assert 'OnBootSec=30s' in timer
    assert 'OnUnitActiveSec=5min' in timer
    assert 'Persistent=false' in timer
