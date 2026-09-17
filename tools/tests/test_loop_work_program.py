import json
from datetime import datetime, timezone
from pathlib import Path
import os
import stat
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import work_program as program


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args],
                                   stderr=subprocess.DEVNULL).decode().strip()


@pytest.fixture(autouse=True)
def allow_pytest_tmp_ancestors(monkeypatch):
    original = program._validate_ancestor_chain
    monkeypatch.setattr(program, '_validate_ancestor_chain', lambda *_args, **_kwargs: None)
    return original


@pytest.fixture
def setup(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    state = tmp_path / 'state'
    evidence = tmp_path / 'evidence'
    repo.mkdir(); state.mkdir(mode=0o700); evidence.mkdir(mode=0o700)
    fixture_uid = os.getuid()
    def fixture_secure_dir(path, reason):
        path = Path(path)
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != fixture_uid
                or info.st_mode & 0o022):
            raise program.ProgramError(reason)
        return path
    def fixture_owned_file(fd, reason):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != fixture_uid
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise program.ProgramError(reason)
    monkeypatch.setattr(program, '_secure_dir', fixture_secure_dir)
    monkeypatch.setattr(program, '_check_owned_file', fixture_owned_file)
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


def run(config, send, now=None, tariff=allowed, offpeak=lambda **_: None,
        key_reader=lambda _: 'fixture-key', clock=None):
    observed = now or datetime(2026, 9, 13, tzinfo=timezone.utc)
    return program.run_once(config, send=send, key_reader=key_reader,
                            now=observed, clock=clock or (lambda: observed),
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


def test_transport_tariff_deferral_is_known_unsent_and_retries(setup):
    config, _repo, state, _evidence = setup
    config['tasks'] = config['tasks'][:1]
    calls = []
    def send(*_args):
        calls.append(1)
        if len(calls) == 1:
            raise program.TariffDeferred('weekday_peak', 12345)
        return response()
    first = run(config, send)
    assert first['status'] == 'waiting_window'
    assert first['resume_at'] == 12345
    events = [json.loads(line) for line in (state / 'journal.jsonl').read_text().splitlines()]
    assert [event['event'] for event in events] == ['intent', 'deferred']
    second = run(config, send)
    assert second['status'] == 'idle' and second['reason'] == 'task_completed'
    assert calls == [1, 1]


def test_quota_day_reserved_after_key_read_crosses_midnight(setup):
    config, _repo, _state, _evidence = setup
    config['max_calls_per_day'] = 1
    before = datetime(2026, 9, 15, 15, 59, 59, tzinfo=timezone.utc)
    after = datetime(2026, 9, 15, 16, 0, 1, tzinfo=timezone.utc)
    current = [before]
    calls = []
    def key_reader(_path):
        current[0] = after
        return 'fixture-key'
    first = run(config, lambda *args: calls.append(args) or response(),
                now=before, key_reader=key_reader, clock=lambda: current[0])
    assert first['reason'] == 'task_completed'
    second = run(config, lambda *args: calls.append(args) or response(),
                 now=after, key_reader=key_reader, clock=lambda: current[0])
    assert second['reason'] == 'daily_quota_exhausted'
    assert second['local_day'] == '2026-09-16'
    assert len(calls) == 1


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


def test_rejects_writable_and_symlink_ancestor_chains(tmp_path,
                                                        allow_pytest_tmp_ancestors,
                                                        monkeypatch):
    original = allow_pytest_tmp_ancestors
    unsafe = tmp_path / 'unsafe'
    unsafe.mkdir(mode=0o700)
    unsafe.chmod(0o777)
    state = unsafe / 'state'
    state.mkdir(mode=0o700)
    with pytest.raises(program.ProgramError):
        original(state, 'untrusted_state_root', include_leaf=True)

    safe = tmp_path / 'safe'
    safe.mkdir(mode=0o700)
    child = safe / 'child'
    child.mkdir(mode=0o700)
    link = tmp_path / 'link'
    link.symlink_to(safe, target_is_directory=True)
    with pytest.raises(program.ProgramError):
        original(link / 'child', 'untrusted_state_root', include_leaf=True)

    config_path = unsafe / 'work-program.json'
    config_path.write_text('{}')
    config_path.chmod(0o600)
    monkeypatch.setattr(program, '_validate_ancestor_chain', original)
    with pytest.raises(program.ProgramError, match='untrusted_config_ancestor'):
        program.load_config(config_path)


def test_promisor_remote_helper_never_executes(setup, tmp_path):
    config, repo, _state, _evidence = setup
    missing = '1' * 40
    tree = subprocess.check_output(
        ['git', '-C', str(repo), 'mktree', '--missing'],
        input=('100644 blob ' + missing + chr(9) + 'facts.txt' + chr(10)).encode()).decode().strip()
    commit = subprocess.check_output(
        ['git', '-C', str(repo), 'commit-tree', tree, '-m', 'missing blob'],
        stderr=subprocess.DEVNULL).decode().strip()
    subprocess.check_call(['git', '-C', str(repo), 'update-ref', 'HEAD', commit])
    sentinel = tmp_path / 'remote-helper-executed'
    helper = tmp_path / 'helper.sh'
    helper.write_text('#!/bin/sh' + chr(10) + f'touch "{sentinel}"' + chr(10)
                      + 'exit 1' + chr(10))
    helper.chmod(0o700)
    subprocess.run([str(helper)], check=False)
    assert sentinel.exists()
    sentinel.unlink()
    git(repo, 'config', 'core.repositoryformatversion', '1')
    git(repo, 'config', 'extensions.partialClone', 'origin')
    git(repo, 'config', 'remote.origin.promisor', 'true')
    git(repo, 'config', 'remote.origin.url', f'ext::{helper}')
    git(repo, 'config', 'protocol.ext.allow', 'always')
    config['tasks'] = config['tasks'][:1]
    with pytest.raises(program.ProgramError):
        program.collect_context(config, config['tasks'][0])
    assert not sentinel.exists()


def test_bounded_state_and_journal_reads(setup):
    config, _repo, state, _evidence = setup
    (state / 'state.json').write_bytes(b'x' * (program.MAX_STATE_BYTES + 1))
    (state / 'state.json').chmod(0o600)
    with pytest.raises(program.ProgramError, match='state_too_large'):
        program.read_state(state)
    (state / 'state.json').unlink()
    (state / 'journal.jsonl').write_bytes(b'x' * (program.MAX_JOURNAL_LINE + 1) + b'\\n')
    (state / 'journal.jsonl').chmod(0o600)
    with pytest.raises(program.ProgramError, match='journal_line_too_large'):
        program.read_journal(state)


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


def adaptive_config(base, complexity='standard'):
    value = dict(base)
    value['provider_policy'] = 'adaptive'
    value['openai_url'] = 'http://127.0.0.1:18772/v1/infer'
    value['openai_token_file'] = '/etc/loop/secrets/openai_broker'
    value['tasks'] = [dict(value['tasks'][0], complexity=complexity)]
    return value


def routed_research_response(model='gpt-5.6-sol', usage=None):
    data = json.loads(response())
    effort = 'low' if model == 'gpt-5.6-luna' else (
        'high' if model == 'gpt-5.6-sol-high' else 'medium')
    if model == 'gpt-5.6-sol-high':
        model = 'gpt-5.6-sol'
    route = {'provider': 'openai-codex', 'model': model,
             'reasoning_effort': effort, 'reason': 'fixture'}
    data['model'] = model
    data['provider'] = 'openai-codex'
    data['provider_route'] = route
    data['actual_request_sha256'] = 'e' * 64
    data['usage'] = usage
    return json.dumps(data).encode()


def test_adaptive_peak_runs_openai_and_persists_route(setup, monkeypatch):
    base, _repo, state, _evidence = setup
    settings = adaptive_config(base)
    calls = []
    monkeypatch.setattr(program.model_router, 'read_broker_token',
                        lambda _path: 'openai-fixture')
    def routed(payload, glm_key, timeout, config, purpose, complexity, **kwargs):
        calls.append((purpose, complexity, kwargs))
        data = json.loads(routed_research_response())
        kwargs['on_route'](data['provider_route'])
        verdict = json.loads(data['choices'][0]['message']['content'])
        verdict['summary'] = 'openai-fixture'
        data['choices'][0]['message']['content'] = json.dumps(verdict)
        return json.dumps(data).encode()
    monkeypatch.setattr(program.model_router, 'routed_transport', routed)
    result = program.run_once(settings, now=datetime(2026, 9, 16, 7,
        tzinfo=timezone.utc), clock=lambda: datetime(2026, 9, 16, 7,
        tzinfo=timezone.utc), tariff_check=lambda **_: {
            'allowed': False, 'reason': 'weekday_peak', 'resume_at': 99},
        offpeak_check=lambda **_: pytest.fail('adaptive peak must not GLM defer'),
        key_reader=lambda _: 'glm-fixture')
    assert result['status'] == 'idle' and result['reason'] == 'task_completed'
    artifact = json.loads(Path(result['evidence_path']).read_text())
    assert artifact['model'] == 'gpt-5.6-sol'
    assert artifact['provider'] == 'openai-codex'
    assert artifact['planned_provider_route']['model'] == 'gpt-5.6-sol'
    assert artifact['actual_provider_route']['model'] == 'gpt-5.6-sol'
    assert artifact['actual_request_sha256'] == 'e' * 64
    assert artifact['usage'] is None
    assert artifact['verdict']['summary'] == '[redacted]'
    intent = json.loads((state / 'journal.jsonl').read_text().splitlines()[0])
    assert intent['provider_route']['model'] == 'gpt-5.6-sol'
    assert calls[0][0:2] == ('research', 'standard')


def test_adaptive_broker_busy_is_deferred_then_retryable(setup, monkeypatch):
    base, _repo, state, _evidence = setup
    settings = adaptive_config(base, 'small')
    route = {'provider': 'openai-codex', 'model': 'gpt-5.6-luna',
             'reasoning_effort': 'low', 'reason': 'glm_peak'}
    current = [datetime(2026, 9, 16, 7, tzinfo=timezone.utc)]
    resume_at = int(current[0].timestamp()) + 15
    calls = []
    monkeypatch.setattr(program.model_router, 'read_broker_token',
                        lambda _path: 'openai-fixture')
    def routed(*_args, **kwargs):
        calls.append(1)
        kwargs['on_route'](route)
        if len(calls) == 1:
            raise program.model_router.RouterDeferred(
                'openai_broker_busy', resume_at, route)
        return routed_research_response('gpt-5.6-luna')
    monkeypatch.setattr(program.model_router, 'routed_transport', routed)
    def invoke():
        return program.run_once(settings, now=current[0], clock=lambda: current[0],
            tariff_check=lambda **_: {'allowed': False, 'reason': 'weekday_peak',
                                      'resume_at': int(current[0].timestamp()) + 100},
            key_reader=lambda _: 'glm-fixture')
    first = invoke()
    assert first['status'] == 'waiting_window'
    assert first['reason'] == 'openai_broker_busy' and first['resume_at'] == resume_at
    assert invoke()['status'] == 'waiting_window'
    assert calls == [1]
    current[0] = datetime.fromtimestamp(resume_at + 1, tz=timezone.utc)
    second = invoke()
    assert second['reason'] == 'task_completed' and calls == [1, 1]
    events = [json.loads(line)['event']
              for line in (state / 'journal.jsonl').read_text().splitlines()]
    assert events == ['intent', 'route', 'deferred', 'intent', 'route', 'complete']


def test_adaptive_peak_observe_reports_enabled(setup):
    base, *_ = setup
    settings = adaptive_config(base)
    status = program.observe(settings, now=datetime(2026, 9, 16, 7,
        tzinfo=timezone.utc), tariff_check=lambda **_: {
            'allowed': False, 'reason': 'weekday_peak', 'resume_at': 999})
    assert status['status'] == 'enabled'


def test_extended_daily_limit_is_bounded(setup):
    settings, *_ = setup
    settings['max_calls_per_day'] = 96
    assert program.validate_config(settings)
    settings['max_calls_per_day'] = 97
    with pytest.raises(program.ProgramError, match='invalid_daily_limit'):
        program.validate_config(settings)


def test_adaptive_oversize_broker_fallback_blocks_before_intent(setup, monkeypatch):
    base, repo, state, _evidence = setup
    (repo / 'facts.txt').write_text('\\' * 90_000)
    git(repo, 'commit', '-qam', 'large escaped context')
    settings = adaptive_config(base)
    monkeypatch.setattr(program.model_router, 'read_broker_token',
                        lambda _path: pytest.fail('credential read after oversize'))
    monkeypatch.setattr(program.model_router, 'routed_transport',
                        lambda *_a, **_k: pytest.fail('transport after oversize'))
    result = program.run_once(settings,
        now=datetime(2026, 9, 13, tzinfo=timezone.utc),
        clock=lambda: datetime(2026, 9, 13, tzinfo=timezone.utc),
        tariff_check=allowed, key_reader=lambda _: 'glm')
    assert result['status'] == 'blocked'
    assert result['reason'] == 'invalid_broker_request'
    assert not (state / 'journal.jsonl').exists()


def test_research_parser_accepts_captured_glm_usage_after_router_normalization():
    content = json.dumps({'summary': 'ok', 'findings': [], 'next_steps': []})
    raw = {'model': program.MODEL,
        'choices': [{'finish_reason': 'stop',
                     'message': {'role': 'assistant', 'content': content}}],
        'usage': {'completion_tokens': 6,
                  'completion_tokens_details': {'reasoning_tokens': 0},
                  'prompt_tokens': 19,
                  'prompt_tokens_details': {'cached_tokens': 0},
                  'total_tokens': 25}}
    route = {'provider': 'z.ai', 'model': program.MODEL,
             'reasoning_effort': None, 'reason': 'off_peak'}
    normalized = program.model_router.normalize_glm(
        json.dumps(raw).encode(), route, 'a' * 64)
    verdict, usage, model, provider, actual_route, request_hash = (
        program.parse_response(normalized))
    assert verdict['summary'] == 'ok'
    assert usage['reasoning_tokens'] == 0 and usage['cached_tokens'] == 0
    assert (model, provider, actual_route, request_hash) == (
        program.MODEL, 'z.ai', route, 'a' * 64)


def test_unknown_read_only_retry_is_explicit_bounded_and_journaled(setup):
    config,_repo,state,_evidence=setup;config["tasks"]=config["tasks"][:1]
    config["unknown_retry_limit"]=1;config["unknown_retry_after_seconds"]=0
    calls=[]
    def transport(*_args):
        calls.append(1)
        if len(calls)==1:raise TimeoutError("lost")
        return response("Recovered read-only research.")
    assert run(config,transport)["status"]=="unknown"
    assert run(config,transport)["status"]=="idle"
    assert run(config,transport)["status"]=="idle"
    events=[json.loads(line) for line in (state/"journal.jsonl").read_text().splitlines()]
    assert [event["event"] for event in events].count("retry")==1
    assert calls==[1,1]


def test_unknown_retry_waits_for_configured_delay(setup):
    config,_repo,_state,_evidence=setup;config["tasks"]=config["tasks"][:1]
    config["unknown_retry_limit"]=1;config["unknown_retry_after_seconds"]=3600
    calls=[]
    def transport(*_args):
        calls.append(1)
        if len(calls)==1:raise TimeoutError("lost")
        return response("Recovered after delay.")
    start=datetime(2026,9,13,tzinfo=timezone.utc)
    assert run(config,transport,now=start)["status"]=="unknown"
    assert run(config,transport,now=start)["reason"]=="unresolved_intent"
    assert calls==[1]
    assert run(config,transport,now=datetime(2026,9,13,1,0,1,tzinfo=timezone.utc))["status"]=="idle"
    assert calls==[1,1]

def test_unknown_retry_exhaustion_never_creates_third_intent(setup):
    config,_repo,state,_evidence=setup;config["tasks"]=config["tasks"][:1]
    config["unknown_retry_limit"]=1;config["unknown_retry_after_seconds"]=0
    calls=[]
    def lost(*_args):calls.append(1);raise TimeoutError("lost")
    assert run(config,lost)["status"]=="unknown"
    assert run(config,lost)["status"]=="unknown"
    third=run(config,lost)
    assert third["status"]=="unknown" and third["reason"]=="unresolved_intent"
    assert calls==[1,1]
    events=[json.loads(line) for line in (state/"journal.jsonl").read_text().splitlines()]
    assert [event["event"] for event in events].count("intent")==2
