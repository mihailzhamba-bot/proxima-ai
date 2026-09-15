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
