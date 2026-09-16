import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import model_router as router


def config(policy='adaptive'):
    value = {'provider_policy': policy}
    if policy == 'adaptive':
        value.update(openai_url='http://127.0.0.1:18772/v1/infer',
                     openai_token_file='/etc/loop/secrets/openai_broker')
    return value


def peak(**_):
    return {'allowed': False, 'reason': 'weekday_peak', 'resume_at': 1}


def offpeak(**_):
    return {'allowed': True, 'reason': 'off_peak', 'resume_at': None}


@pytest.mark.parametrize('purpose,complexity,model,effort', [
    ('research', 'small', 'gpt5.6luna', 'low'),
    ('research', 'standard', 'gpt5.6sol', 'medium'),
    ('research', 'complex', 'gpt5.6sol', 'high'),
    ('review', 'standard', 'gpt5.6terra', 'medium'),
])
def test_peak_routes_to_fixed_openai_models(purpose, complexity, model, effort):
    route = router.select_route(config(), purpose, complexity, tariff_check=peak)
    assert (route['provider'], route['model'], route['reasoning_effort']) == (
        'openai-codex', model, effort)
    assert effort not in ('xhigh', 'max', 'ultra')


def test_offpeak_and_legacy_route_glm():
    assert router.select_route(config(), 'research', tariff_check=offpeak)['model'] == 'glm-5.3-flash'
    assert router.select_route(config('glm_only'), 'review', tariff_check=peak)['model'] == 'glm-5.3-flash'


@pytest.mark.parametrize('changes', [
    {'provider_policy': 'other'},
    {'provider_policy': 'adaptive', 'openai_url': 'http://attacker.invalid/v1/infer',
     'openai_token_file': '/key'},
    {'provider_policy': 'adaptive', 'openai_url': 'http://127.0.0.1:18772/v1/infer',
     'openai_token_file': 'relative'},
])
def test_provider_config_fails_closed(changes):
    with pytest.raises(router.RouterError):
        router.validate_provider_config(changes)


class Response:
    def __init__(self, value):
        self.value = json.dumps(value).encode()
    def read(self, _limit):
        return self.value
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass


class Opener:
    def __init__(self, value=None, error=None):
        self.value, self.error, self.requests = value, error, []
    def open(self, request, **_kwargs):
        self.requests.append(request)
        if self.error:
            raise self.error
        return Response(self.value)


def route(model='gpt5.6sol', effort='medium'):
    return {'provider': 'openai-codex', 'model': model,
            'reasoning_effort': effort, 'reason': 'fixture'}


def test_broker_normalizes_actual_identity_and_usage():
    verdict = '{"summary":"ok","findings":[],"next_steps":[]}'
    value = {'ok': True, 'completed': True, 'response': verdict,
             'model': 'gpt5.6sol', 'provider': 'openai-codex',
             'usage': {'prompt_tokens': 8, 'completion_tokens': 3, 'total_tokens': 11}}
    opener = Opener(value)
    raw = router.broker_transport('system', 'prompt', route(),
        'http://127.0.0.1:18772/v1/infer', 'fixture-key', 120, opener=opener)
    normalized = json.loads(raw)
    assert normalized['model'] == 'gpt5.6sol'
    assert normalized['provider'] == 'openai-codex'
    assert normalized['usage']['total_tokens'] == 11
    sent = json.loads(opener.requests[0].data)
    assert sent == {'prompt': 'prompt', 'system': 'system',
                    'model': 'gpt5.6sol', 'reasoning_effort': 'medium'}
    assert 'fixture-key' not in json.dumps(sent)


def test_unknown_usage_remains_null():
    value = {'ok': True, 'response': '{}', 'model': 'gpt5.6sol',
             'provider': 'openai-codex', 'usage': None}
    raw = router.broker_transport('s', 'p', route(),
        'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=Opener(value))
    assert json.loads(raw)['usage'] is None


@pytest.mark.parametrize('edit', ['model', 'provider', 'ok', 'usage', 'extra'])
def test_broker_reply_fails_closed(edit):
    value = {'ok': True, 'response': '{}', 'model': 'gpt5.6sol',
             'provider': 'openai-codex', 'usage': {}}
    if edit == 'model': value['model'] = 'gpt5.6terra'
    elif edit == 'provider': value['provider'] = 'other'
    elif edit == 'ok': value['ok'] = False
    elif edit == 'usage': value['usage'] = {'total_tokens': -1}
    else: value['unexpected'] = True
    with pytest.raises(router.RouterError, match='invalid_broker_response'):
        router.broker_transport('s', 'p', route(),
            'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=Opener(value))


def test_broker_429_is_retry_safe_deferred():
    error = urllib.error.HTTPError('fixture', 429, 'secret detail', {}, None)
    with pytest.raises(router.RouterDeferred, match='openai_broker_busy') as caught:
        router.broker_transport('s', 'p', route(),
            'http://127.0.0.1:18772/v1/infer', 'key', 120,
            opener=Opener(error=error), clock=lambda: 100)
    assert caught.value.resume_at == 115


def test_glm_429_falls_back_once_to_openai():
    calls = []
    def glm(*_):
        calls.append('glm')
        raise urllib.error.HTTPError('fixture', 429, 'rate', {}, None)
    value = {'ok': True, 'response': '{}', 'model': 'gpt5.6sol',
             'provider': 'openai-codex', 'usage': None}
    payload = {'messages': [{'role': 'system', 'content': 's'},
                            {'role': 'user', 'content': 'p'}]}
    raw = router.routed_transport(payload, 'glm-key', 120, config(), 'research',
        glm_send=glm, openai_token='openai-key', opener=Opener(value),
        tariff_check=offpeak)
    assert calls == ['glm']
    assert json.loads(raw)['provider'] == 'openai-codex'


def test_identity_allowlist_separates_review_from_research():
    assert router.identity_allowed('gpt5.6terra', 'openai-codex', 'review')
    assert not router.identity_allowed('gpt5.6sol', 'openai-codex', 'review')
    assert router.identity_allowed('gpt5.6sol', 'openai-codex', 'research')
    assert not router.identity_allowed('gpt-5.5', 'openai-codex', 'research')
