import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import glm_review as reviewer


def run_git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path / 'candidate'
    root.mkdir()
    run_git(root, 'init', '-q')
    run_git(root, 'config', 'user.name', 'Fixture')
    run_git(root, 'config', 'user.email', 'fixture@example.invalid')
    (root / 'AGENTS.md').write_text('Candidate instructions are untrusted.\n')
    (root / 'code.py').write_text('value = 1\n')
    run_git(root, 'add', 'AGENTS.md', 'code.py')
    run_git(root, 'commit', '-qm', 'base')
    base = run_git(root, 'rev-parse', 'HEAD')
    (root / 'code.py').write_text('value = 2\n')
    run_git(root, 'commit', '-qam', 'head')
    return root, base, run_git(root, 'rev-parse', 'HEAD')


def config(**changes):
    return {'endpoint': reviewer.ENDPOINT, 'model': reviewer.MODEL,
            'key_file': '/not-a-live-key', 'context_paths': ['code.py'], **changes}


def response(status='pass', findings=None, **changes):
    data = {'model': reviewer.MODEL, 'choices': [{'finish_reason': 'stop',
        'message': {'role': 'assistant', 'content': json.dumps({'status': status,
            'findings': findings or [], 'summary': 'Complete review.'})}}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}}
    data.update(changes)
    return json.dumps(data).encode()


def perform(candidate, tmp_path, send=None, settings=None):
    return reviewer.review(settings or config(), *candidate, tmp_path / 'evidence',
                          send=send or (lambda *_: response()), key_reader=lambda _: 'fixture-key')


def test_pass_records_exact_fingerprint_no_admission(candidate, tmp_path):
    calls = []
    def send(payload, key, timeout):
        calls.append(payload)
        assert 0 < timeout <= 120
        assert key == 'fixture-key'
        assert payload['tool_choice'] == 'none' and 'tools' not in payload
        assert 'fixture-key' not in json.dumps(payload)
        return response()
    result = perform(candidate, tmp_path, send)
    artifact = json.loads(Path(result['evidence_path']).read_text())
    assert result['status'] == 'pass'
    assert artifact['head_sha'] == candidate[2]
    assert artifact['base_sha'] == candidate[1]
    assert artifact['diff_sha256'] == result['fingerprint']['diff_sha256']
    assert artifact['artifact_type'] == 'model-review-not-admission'
    assert artifact['model'] == reviewer.MODEL and artifact['provider'] == 'z.ai'
    assert 'skipped' not in artifact and 'status' not in artifact
    assert Path(result['evidence_path']).stat().st_mode & 0o777 == 0o600
    assert len(calls) == 1


def test_blocked_finding_retained(candidate, tmp_path):
    finding = {'severity': 'warning', 'path': 'code.py', 'line': 1, 'message': 'Needs investigation.'}
    result = perform(candidate, tmp_path, lambda *_: response('blocked', [finding]))
    assert result['status'] == 'blocked'
    assert json.loads(Path(result['evidence_path']).read_text())['verdict']['findings'] == [finding]


@pytest.mark.parametrize('raw', [b'not json', b'{}', response(choices=[]),
    response('pass', [{'severity': 'blocker', 'path': 'code.py', 'line': 1, 'message': 'Bug'}]),
    response(model='different-model'), response(usage={}), response(status='pending')])
def test_invalid_response_fails_closed(candidate, tmp_path, raw):
    with pytest.raises(reviewer.ReviewError, match='invalid_or_incomplete'):
        perform(candidate, tmp_path, lambda *_: raw)
    assert not (tmp_path / 'evidence').exists()


@pytest.mark.parametrize('edit', ['truncated', 'tools'])
def test_no_tools_complete_response(candidate, tmp_path, edit):
    data = json.loads(response())
    if edit == 'truncated':
        data['choices'][0]['finish_reason'] = 'length'
    else:
        data['choices'][0]['message']['tool_calls'] = [{'id': 'tool'}]
    with pytest.raises(reviewer.ReviewError):
        perform(candidate, tmp_path, lambda *_: json.dumps(data).encode())


@pytest.mark.parametrize('kind', ['sha', 'dirty', 'untracked', 'oversize'])
def test_scope_rejected_before_network(candidate, tmp_path, kind):
    root, base, head = candidate
    settings = config()
    if kind == 'sha':
        head = base
    elif kind == 'dirty':
        (root / 'code.py').write_text('dirty')
    elif kind == 'untracked':
        (root / 'unexpected').write_text('unknown')
    else:
        settings['max_diff_bytes'] = 1
    calls = []
    with pytest.raises(reviewer.ReviewError):
        perform((root, base, head), tmp_path, lambda *args: calls.append(args), settings)
    assert calls == []


def test_candidate_fsmonitor_never_executes(candidate, tmp_path):
    root, _, _ = candidate
    sentinel = tmp_path / 'executed'
    script = tmp_path / 'fsmonitor'
    script.write_text('#!/bin/sh\ntouch "' + str(sentinel) + '"\n')
    script.chmod(0o700)
    run_git(root, 'config', 'core.fsmonitor', str(script))
    assert perform(candidate, tmp_path)['status'] == 'pass'
    assert not sentinel.exists()


@pytest.mark.parametrize('code,count', [(429, 2), (503, 2), (401, 1), (500, 1), (302, 1)])
def test_only_one_retry_for_rejection(candidate, tmp_path, code, count):
    calls = []
    def send(*args):
        calls.append(args)
        raise urllib.error.HTTPError(reviewer.ENDPOINT, code, 'fixture-key raw error', {}, None)
    with pytest.raises(reviewer.ReviewError, match='provider_rejected') as error:
        perform(candidate, tmp_path, send)
    assert 'fixture-key' not in str(error.value)
    assert len(calls) == count


def test_timeout_never_retries(candidate, tmp_path):
    calls = []
    def send(*args):
        calls.append(args)
        raise TimeoutError('fixture-key')
    with pytest.raises(reviewer.ReviewError, match='provider_unavailable'):
        perform(candidate, tmp_path, send)
    assert len(calls) == 1


def test_redirect_handler_refuses_authorization_forwarding():
    with pytest.raises(reviewer.ReviewError, match='redirect_refused'):
        reviewer.NoRedirect().redirect_request(urllib.request.Request(reviewer.ENDPOINT), None,
                                               307, '', {}, 'https://attacker.invalid/')


@pytest.mark.parametrize('changes', [{'endpoint': 'https://attacker.invalid'},
    {'retry_count': 2}, {'timeout_seconds': 121}, {'context_paths': ['../outside']},
    {'context_paths': ['.env']}, {'context_paths': ['secrets/key']}, {'tools': []}])
def test_config_bounds(changes):
    with pytest.raises(reviewer.ReviewError):
        reviewer.config_checked(config(**changes))


def test_key_rejects_nonroot_or_bad_mode(tmp_path):
    path = tmp_path / 'key'
    path.write_text('fixture-key')
    path.chmod(0o644)
    with pytest.raises(reviewer.ReviewError, match='untrusted_key_(file|directory)'):
        reviewer.read_key(path)


def test_key_rejects_symlink(tmp_path):
    path = tmp_path / 'key'
    path.symlink_to(tmp_path / 'other')
    with pytest.raises(reviewer.ReviewError, match='key_unavailable|untrusted_key_directory'):
        reviewer.read_key(path)


def test_provider_echo_of_key_is_redacted(candidate, tmp_path):
    data = json.loads(response())
    verdict = json.loads(data['choices'][0]['message']['content'])
    verdict['summary'] = 'fixture-key'
    data['choices'][0]['message']['content'] = json.dumps(verdict)
    result = perform(candidate, tmp_path, lambda *_: json.dumps(data).encode())
    assert 'fixture-key' not in Path(result['evidence_path']).read_text()


def test_candidate_change_during_review_fails(candidate, tmp_path):
    def send(*_):
        (candidate[0] / 'code.py').write_text('changed mid-review')
        return response()
    with pytest.raises((reviewer.ReviewError, ValueError)):
        perform(candidate, tmp_path, send)
    assert not (tmp_path / 'evidence').exists()


def test_context_not_silently_truncated(candidate, tmp_path):
    with pytest.raises(reviewer.ReviewError, match='git_output_or_time_limit'):
        perform(candidate, tmp_path, settings=config(max_context_bytes=1))


def test_response_oversize(candidate, tmp_path):
    with pytest.raises(reviewer.ReviewError, match='response_too_large'):
        perform(candidate, tmp_path, lambda *_: b'x' * (reviewer.MAX_RESPONSE + 1))


def test_rejection_retry_can_succeed(candidate, tmp_path):
    calls = []
    def send(*args):
        calls.append(args)
        if len(calls) == 1:
            raise urllib.error.HTTPError(reviewer.ENDPOINT, 429, 'rejected', {}, None)
        return response()
    assert perform(candidate, tmp_path, send)['status'] == 'pass'
    assert len(calls) == 2


def test_base_must_be_ancestor(candidate, tmp_path):
    root, base, head = candidate
    tree = run_git(root, 'rev-parse', base + '^{tree}')
    unrelated = run_git(root, 'commit-tree', tree, '-m', 'unrelated')
    with pytest.raises(reviewer.ReviewError, match='git_scope_invalid'):
        perform((root, unrelated, head), tmp_path)


def test_transport_absolute_timeout(monkeypatch):
    monkeypatch.setattr(reviewer, 'require_offpeak', lambda *_: None)
    class SlowOpener:
        def open(self, *_args, **_kwargs):
            time.sleep(1)
    monkeypatch.setattr(reviewer.urllib.request, 'build_opener', lambda *_: SlowOpener())
    started = time.monotonic()
    with pytest.raises(reviewer.ReviewError, match='request_timeout'):
        reviewer.transport({}, 'fixture-key', 0.02)
    assert time.monotonic() - started < 0.5


def test_duplicate_json_keys_rejected():
    with pytest.raises(ValueError):
        reviewer.strict_json('{"status":"blocked","status":"pass"}')


def test_gitlink_rejected_before_nested_fsmonitor_can_execute(candidate, tmp_path):
    root, base, _head = candidate
    sub = root / 'sub'; sub.mkdir()
    run_git(sub, 'init', '-q')
    run_git(sub, 'config', 'user.name', 'Fixture')
    run_git(sub, 'config', 'user.email', 'fixture@example.invalid')
    (sub / 'file.txt').write_text('fixture')
    run_git(sub, 'add', 'file.txt'); run_git(sub, 'commit', '-qm', 'sub base')
    (root / '.gitmodules').write_text('[submodule "sub"]\n path = sub\n url = ./sub\n')
    run_git(root, 'add', 'sub', '.gitmodules'); run_git(root, 'commit', '-qm', 'tracked gitlink')
    head = run_git(root, 'rev-parse', 'HEAD')
    sentinel = tmp_path / 'submodule-executed'
    script = tmp_path / 'nested-fsmonitor'
    script.write_text('#!/bin/sh\ntouch "' + str(sentinel) + '"\n')
    script.chmod(0o700)
    run_git(sub, 'config', 'core.fsmonitor', str(script))
    with pytest.raises(reviewer.ReviewError, match='submodules_not_allowed'):
        perform((root, base, head), tmp_path)
    assert not sentinel.exists()


def test_json_escaped_key_redacted_after_decoding(candidate, tmp_path):
    data = json.loads(response())
    data['choices'][0]['message']['content'] = '{"status":"pass","findings":[],"summary":"\\u0066ixture-key"}'
    result = perform(candidate, tmp_path, lambda *_: json.dumps(data).encode())
    artifact = Path(result['evidence_path']).read_text()
    assert 'fixture-key' not in artifact
    assert json.loads(artifact)['verdict']['summary'] == '[redacted]'


def test_identical_base_head_blob_only_charged_once(candidate, tmp_path):
    captured = []
    def send(payload, *_args):
        captured.append(json.loads(payload['messages'][1]['content'])['context'])
        return response()
    # Repeated fixture AGENTS would exceed 70 bytes; unique content fits.
    result = perform(candidate, tmp_path, send, config(max_context_bytes=70))
    agents = [item for item in captured[0] if item['path'] == 'AGENTS.md']
    assert len(agents) == 1
    assert agents[0]['revisions'] == [candidate[1], candidate[2]]
    assert agents[0]['revision'] == candidate[1]
    assert len(agents[0]['blob_sha']) == 40
    artifact = json.loads(Path(result['evidence_path']).read_text())
    agent_refs = [item for item in artifact['context'] if item['path'] == 'AGENTS.md']
    assert agent_refs[0]['revisions'] == [candidate[1], candidate[2]]


def test_changed_context_keeps_both_exact_versions(candidate, tmp_path):
    captured = []
    def send(payload, *_args):
        captured.extend(json.loads(payload['messages'][1]['content'])['context'])
        return response()
    perform(candidate, tmp_path, send)
    versions = [item for item in captured if item['path'] == 'code.py']
    assert len(versions) == 2
    assert versions[0]['content'] == 'value = 1\n' and versions[0]['revisions'] == [candidate[1]]
    assert versions[1]['content'] == 'value = 2\n' and versions[1]['revisions'] == [candidate[2]]
    assert versions[0]['blob_sha'] != versions[1]['blob_sha']



def test_transport_tariff_guard_blocks_before_http(monkeypatch):
    calls = []
    class Opener:
        def open(self, *_args, **_kwargs):
            calls.append('http')
            raise AssertionError('HTTP must not run')
    monkeypatch.setattr(reviewer.urllib.request, 'build_opener', lambda *_: Opener())
    def defer(_timeout):
        raise reviewer.TariffDeferred('weekday_peak', 1_800_000_000)
    monkeypatch.setattr(reviewer, 'require_offpeak', defer)
    with pytest.raises(reviewer.TariffDeferred, match='weekday_peak'):
        reviewer.transport({}, 'fixture-key', 120)
    assert calls == []


@pytest.mark.parametrize('budget', [True, 0, 121])
def test_transport_rejects_invalid_request_budget_before_http(monkeypatch, budget):
    calls = []
    class Opener:
        def open(self, *_args, **_kwargs):
            calls.append('http')
    monkeypatch.setattr(reviewer.urllib.request, 'build_opener', lambda *_: Opener())
    with pytest.raises(ValueError, match='invalid_request_seconds'):
        reviewer.transport({}, 'fixture-key', budget)
    assert calls == []


def test_production_retry_rechecks_tariff_before_each_http(candidate, tmp_path, monkeypatch):
    checks = []
    opens = []
    monkeypatch.setattr(reviewer, 'require_offpeak', lambda seconds=120: checks.append(seconds))
    class RejectingOpener:
        def open(self, *_args, **_kwargs):
            opens.append('http')
            raise urllib.error.HTTPError(reviewer.ENDPOINT, 429, 'retry', {}, None)
    monkeypatch.setattr(reviewer.urllib.request, 'build_opener', lambda *_: RejectingOpener())
    with pytest.raises(reviewer.ReviewError, match='provider_rejected'):
        reviewer.review(config(), *candidate, tmp_path / 'evidence',
                        key_reader=lambda _: 'fixture-key')
    assert len(opens) == 2
    assert len(checks) == 4
    assert all(0 < seconds <= 120 for seconds in checks)


def test_production_review_rechecks_after_payload_before_key(candidate, tmp_path, monkeypatch):
    checks = []
    key_reads = []
    def cross_boundary(seconds=120):
        checks.append(seconds)
        if len(checks) == 2:
            raise reviewer.TariffDeferred('weekday_peak', 1_800_000_000)
    monkeypatch.setattr(reviewer, 'require_offpeak', cross_boundary)
    with pytest.raises(reviewer.TariffDeferred, match='weekday_peak'):
        reviewer.review(config(), *candidate, tmp_path / 'evidence',
                        key_reader=lambda _: key_reads.append('key'))
    assert len(checks) == 2
    assert key_reads == []


def test_transport_deferred_propagates_without_http_or_retry(candidate, tmp_path, monkeypatch):
    checks = []
    opens = []
    key_reads = []
    def cross_boundary(seconds=120):
        checks.append(seconds)
        if len(checks) == 3:
            raise reviewer.TariffDeferred('weekday_peak', 1_800_000_000)
    class Opener:
        def open(self, *_args, **_kwargs):
            opens.append('http')
            raise AssertionError('HTTP must not run')
    monkeypatch.setattr(reviewer, 'require_offpeak', cross_boundary)
    monkeypatch.setattr(reviewer.urllib.request, 'build_opener', lambda *_: Opener())
    def read_key(_path):
        key_reads.append('key')
        return 'fixture-key'
    with pytest.raises(reviewer.TariffDeferred, match='weekday_peak') as caught:
        reviewer.review(config(), *candidate, tmp_path / 'evidence', key_reader=read_key)
    assert caught.value.resume_at == 1_800_000_000
    assert len(checks) == 3
    assert key_reads == ['key']
    assert opens == []


def test_production_review_peak_blocks_before_key_reader(candidate, tmp_path, monkeypatch):
    key_reads = []
    def defer(_timeout):
        raise reviewer.TariffDeferred('weekday_peak', 1_800_000_000)
    monkeypatch.setattr(reviewer, 'require_offpeak', defer)
    with pytest.raises(reviewer.TariffDeferred, match='weekday_peak'):
        reviewer.review(config(), *candidate, tmp_path / 'evidence',
                        key_reader=lambda _: key_reads.append('key'))
    assert key_reads == []


def test_main_peak_defers_for_legacy_glm_only(monkeypatch, capsys, tmp_path):
    config_path = tmp_path / 'glm-only.json'
    config_path.write_text(json.dumps(config()))
    monkeypatch.setattr(sys, 'argv', ['glm_review.py', '--config', str(config_path),
        '--checkout', str(tmp_path), '--base', '0' * 40, '--head', '1' * 40,
        '--evidence-root', str(tmp_path / 'evidence')])
    monkeypatch.setattr(reviewer, 'require_offpeak',
        lambda *_: (_ for _ in ()).throw(
            reviewer.TariffDeferred('weekday_peak', 1_800_000_000)))
    assert reviewer.main() == 75
    assert json.loads(capsys.readouterr().out) == {
        'status': 'deferred', 'reason': 'weekday_peak', 'resume_at': 1_800_000_000}
    assert config_path.exists()


def test_adaptive_review_uses_peak_openai_and_persists_actual_identity(
        candidate, tmp_path, monkeypatch):
    settings = config(provider_policy='adaptive',
        openai_url='http://127.0.0.1:18772/v1/infer',
        openai_token_file='/fixture/openai')
    monkeypatch.setattr(reviewer, 'require_offpeak',
                        lambda *_: pytest.fail('adaptive must not tariff-defer'))
    monkeypatch.setattr(reviewer.model_router, 'read_broker_token',
                        lambda _path: 'openai-fixture')
    calls = []
    def routed(payload, glm_key, timeout, route_config, purpose, **kwargs):
        calls.append((payload, glm_key, timeout, route_config, purpose, kwargs))
        data = json.loads(response())
        data['model'] = 'gpt-5.6-terra'
        data['provider'] = 'openai-codex'
        data['provider_route'] = {'provider': 'openai-codex',
            'model': 'gpt-5.6-terra', 'reasoning_effort': 'medium',
            'reason': 'fixture'}
        data['actual_request_sha256'] = 'f' * 64
        data['usage'] = None
        verdict = json.loads(data['choices'][0]['message']['content'])
        verdict['summary'] = 'openai-fixture'
        data['choices'][0]['message']['content'] = json.dumps(verdict)
        return json.dumps(data).encode()
    monkeypatch.setattr(reviewer.model_router, 'routed_transport', routed)
    result = reviewer.review(settings, *candidate, tmp_path / 'evidence',
                             key_reader=lambda _: 'glm-fixture')
    artifact = json.loads(Path(result['evidence_path']).read_text())
    assert artifact['model'] == 'gpt-5.6-terra'
    assert artifact['provider'] == 'openai-codex'
    assert artifact['planned_provider_route']['model'] == 'gpt-5.6-terra'
    assert artifact['actual_provider_route']['model'] == 'gpt-5.6-terra'
    assert artifact['actual_request_sha256'] == 'f' * 64
    assert artifact['usage'] is None
    assert artifact['verdict']['summary'] == '[redacted]'
    assert len(calls) == 1 and calls[0][4] == 'review'


def test_review_parser_rejects_research_model_for_review():
    data = json.loads(response())
    data['model'] = 'gpt-5.6-sol'
    data['provider'] = 'openai-codex'
    with pytest.raises(reviewer.ReviewError, match='invalid_or_incomplete'):
        reviewer.parse_response(json.dumps(data).encode())
