import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import model_router as router
from tools.loop import openai_broker, openai_no_tools


def config(policy='adaptive'):
    value = {'provider_policy': policy}
    if policy in {'adaptive','openai_only'}:
        value.update(openai_url='http://127.0.0.1:18772/v1/infer',
                     openai_token_file='/etc/loop/secrets/openai_broker')
    return value


def peak(**_):
    return {'allowed': False, 'reason': 'weekday_peak', 'resume_at': 1}


def offpeak(**_):
    return {'allowed': True, 'reason': 'off_peak', 'resume_at': None}


@pytest.mark.parametrize('purpose,complexity,model,effort', [
    ('research', 'small', 'gpt-5.6-luna', 'low'),
    ('research', 'standard', 'gpt-5.6-sol', 'medium'),
    ('research', 'complex', 'gpt-5.6-sol', 'high'),
    ('review', 'standard', 'gpt-5.6-terra', 'medium'),
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


def route(model='gpt-5.6-sol', effort='medium'):
    return {'provider': 'openai-codex', 'model': model,
            'reasoning_effort': effort, 'reason': 'fixture'}


def test_broker_normalizes_actual_identity_and_usage():
    verdict = '{"summary":"ok","findings":[],"next_steps":[]}'
    value = {'ok': True, 'completed': True, 'response': verdict,
             'model': 'gpt-5.6-sol', 'provider': 'openai-codex',
             'usage': {'prompt_tokens': 8, 'completion_tokens': 3, 'total_tokens': 11}}
    opener = Opener(value)
    raw = router.broker_transport('system', 'prompt', route(),
        'http://127.0.0.1:18772/v1/infer', 'fixture-key', 120, opener=opener)
    normalized = json.loads(raw)
    assert normalized['model'] == 'gpt-5.6-sol'
    assert normalized['provider'] == 'openai-codex'
    assert normalized['usage']['total_tokens'] == 11
    sent = json.loads(opener.requests[0].data)
    assert sent == {'prompt': 'prompt', 'system': 'system',
                    'model': 'gpt-5.6-sol', 'reasoning_effort': 'medium'}
    assert 'fixture-key' not in json.dumps(sent)


def test_unknown_usage_remains_null():
    value = {'ok': True, 'response': '{}', 'model': 'gpt-5.6-sol',
             'provider': 'openai-codex', 'usage': None}
    raw = router.broker_transport('s', 'p', route(),
        'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=Opener(value))
    assert json.loads(raw)['usage'] is None


@pytest.mark.parametrize('edit', ['model', 'provider', 'ok', 'usage', 'extra'])
def test_broker_reply_fails_closed(edit):
    value = {'ok': True, 'response': '{}', 'model': 'gpt-5.6-sol',
             'provider': 'openai-codex', 'usage': {}}
    if edit == 'model': value['model'] = 'gpt-5.6-terra'
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
    value = {'ok': True, 'response': '{}', 'model': 'gpt-5.6-sol',
             'provider': 'openai-codex', 'usage': None}
    payload = {'messages': [{'role': 'system', 'content': 's'},
                            {'role': 'user', 'content': 'p'}]}
    routes = []
    raw = router.routed_transport(payload, 'glm-key', 120, config(), 'research',
        glm_send=glm, openai_token='openai-key', opener=Opener(value),
        tariff_check=offpeak, on_route=lambda selected: routes.append(selected))
    assert calls == ['glm']
    assert [item['provider'] for item in routes] == ['z.ai', 'openai-codex']
    assert json.loads(raw)['provider'] == 'openai-codex'


def test_identity_allowlist_separates_review_from_research():
    assert router.identity_allowed('gpt-5.6-terra', 'openai-codex', 'review')
    assert not router.identity_allowed('gpt-5.6-sol', 'openai-codex', 'review')
    assert router.identity_allowed('gpt-5.6-sol', 'openai-codex', 'research')
    assert not router.identity_allowed('gpt-5.5', 'openai-codex', 'research')


def test_tariff_boundary_deferral_falls_back_in_adaptive_mode():
    class TariffDeferred(RuntimeError):
        pass
    def glm(*_):
        raise TariffDeferred('boundary')
    value = {'ok': True, 'response': '{}', 'model': 'gpt-5.6-sol',
             'provider': 'openai-codex', 'usage': None}
    payload = {'messages': [{'role': 'system', 'content': 's'},
                            {'role': 'user', 'content': 'p'}]}
    raw = router.routed_transport(payload, 'glm-key', 120, config(), 'research',
        glm_send=glm, openai_token='openai-key', opener=Opener(value),
        tariff_check=offpeak)
    assert json.loads(raw)['provider'] == 'openai-codex'


def test_broker_duplicate_json_keys_fail_closed():
    class DuplicateOpener:
        def open(self, *_args, **_kwargs):
            return Response.__new__(Response)
    response = Response.__new__(Response)
    response.value = (b'{"ok":true,"ok":true,"response":"{}",'
                      b'"model":"gpt-5.6-sol","provider":"openai-codex","usage":null}')
    opener = DuplicateOpener()
    opener.open = lambda *_args, **_kwargs: response
    with pytest.raises(router.RouterError):
        router.broker_transport('s', 'p', route(),
            'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=opener)


def test_router_models_are_canonical_broker_allowlist_subset():
    selected = {model for model, _effort in router.OPENAI_MODELS.values()}
    assert selected == {'gpt-5.6-luna', 'gpt-5.6-sol', 'gpt-5.6-terra'}
    assert selected <= openai_no_tools.MODELS


def test_broker_utf8_wire_is_not_ascii_tripled():
    prompt = 'я' * 50_000  # exactly 100 KB UTF-8 before small JSON overhead
    value = {'ok': True, 'response': '{}', 'model': 'gpt-5.6-sol',
             'provider': 'openai-codex', 'usage': None}
    opener = Opener(value)
    raw = router.broker_transport('система', prompt,
        route('gpt-5.6-sol', 'medium'),
        'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=opener)
    wire = opener.requests[0].data
    assert len(wire) < openai_broker.MAX_REQUEST_BYTES
    assert b'\\u' not in wire
    normalized = json.loads(raw)
    assert normalized['actual_request_sha256']
    assert normalized['provider_route']['model'] == 'gpt-5.6-sol'


def test_broker_wire_limit_blocks_before_http():
    calls = []
    class Never:
        def open(self, *_args, **_kwargs):
            calls.append(1)
    with pytest.raises(router.RouterError, match='invalid_broker_request'):
        router.broker_transport('s', 'я' * 80_000,
            route('gpt-5.6-sol', 'medium'),
            'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=Never())
    assert calls == []


def test_fallback_recomputes_remaining_after_route_and_token_work():
    moments = iter([0, 0, 100, 110])
    received = []
    class TimedOpener(Opener):
        def open(self, request, **kwargs):
            received.append(kwargs['timeout'])
            return super().open(request, **kwargs)
    value = {'ok': True, 'response': '{}', 'model': 'gpt-5.6-sol',
             'provider': 'openai-codex', 'usage': None}
    def glm(*_args):
        raise urllib.error.HTTPError('fixture', 429, 'rate', {}, None)
    payload = {'messages': [{'role': 'system', 'content': 's'},
                            {'role': 'user', 'content': 'p'}]}
    router.routed_transport(payload, 'glm', 120, config(), 'research',
        glm_send=glm, openai_token='openai', opener=TimedOpener(value),
        tariff_check=offpeak, monotonic=lambda: next(moments))
    assert received == [10]


def test_expired_deadline_never_starts_fallback():
    moments = iter([0, 0, 121])
    broker_calls = []
    routes = []
    def glm(*_args):
        raise urllib.error.HTTPError('fixture', 429, 'rate', {}, None)
    payload = {'messages': [{'role': 'system', 'content': 's'},
                            {'role': 'user', 'content': 'p'}]}
    with pytest.raises(router.RouterError, match='router_timeout'):
        router.routed_transport(payload, 'glm', 120, config(), 'research',
            glm_send=glm, openai_token='openai',
            opener=type('Never', (), {'open': lambda *_a, **_k: broker_calls.append(1)})(),
            tariff_check=offpeak, monotonic=lambda: next(moments),
            on_route=lambda selected: routes.append(selected['provider']))
    assert routes == ['z.ai']
    assert broker_calls == []


def test_wrapper_prompt_char_limit_blocks_before_http():
    calls = []
    class Never:
        def open(self, *_args, **_kwargs):
            calls.append(1)
    with pytest.raises(router.RouterError, match='invalid_broker_request'):
        router.broker_transport('s', 'a' * 100_001,
            route('gpt-5.6-sol', 'medium'),
            'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=Never())
    assert calls == []


def test_broker_128k_limit_blocks_multibyte_body_before_http():
    calls = []
    class Never:
        def open(self, *_args, **_kwargs):
            calls.append(1)
    # Character count is valid, but encoded broker body exceeds 128 KiB.
    with pytest.raises(router.RouterError, match='invalid_broker_request'):
        router.broker_transport('s', 'я' * 66_000,
            route('gpt-5.6-sol', 'medium'),
            'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=Never())
    assert calls == []


def test_router_preflight_reuses_broker_and_wrapper_validators():
    selected = route('gpt-5.6-sol', 'medium')
    wire = router.broker_request_wire('system', 'я' * 50_000, selected)
    body = json.loads(wire)
    assert openai_broker.validate_request(body) == body
    assert openai_no_tools.parse_request(wire) == body


def test_broker_system_utf8_byte_limit_blocks_emoji_before_http():
    calls = []
    class Never:
        def open(self, *_args, **_kwargs):
            calls.append(1)
    # 9,000 emoji are 36 KB: under wrapper char limit, over broker 32 KiB.
    with pytest.raises(router.RouterError, match='invalid_broker_request'):
        router.broker_transport('😀' * 9_000, 'prompt',
            route('gpt-5.6-sol', 'medium'),
            'http://127.0.0.1:18772/v1/infer', 'key', 120, opener=Never())
    assert calls == []


def captured_glm_response(content='{}'):
    return json.dumps({'model': router.GLM_MODEL,
        'choices': [{'finish_reason': 'stop',
                     'message': {'role': 'assistant', 'content': content}}],
        'usage': {'completion_tokens': 6,
                  'completion_tokens_details': {'reasoning_tokens': 0},
                  'prompt_tokens': 19,
                  'prompt_tokens_details': {'cached_tokens': 0},
                  'total_tokens': 25}}).encode()


def test_glm_captured_usage_schema_normalizes_to_flat_numeric_counters():
    selected = {'provider': 'z.ai', 'model': router.GLM_MODEL,
                'reasoning_effort': None, 'reason': 'off_peak'}
    value = json.loads(router.normalize_glm(
        captured_glm_response(), selected, 'a' * 64))
    assert value['usage'] == {'prompt_tokens': 19, 'completion_tokens': 6,
                              'total_tokens': 25, 'cached_tokens': 0,
                              'reasoning_tokens': 0}


@pytest.mark.parametrize('details', [
    {'reasoning_tokens': True},
    {'reasoning_tokens': -1},
    {'unknown_counter': 1},
])
def test_glm_nested_usage_rejects_bool_negative_and_unknown(details):
    raw = json.loads(captured_glm_response())
    raw['usage']['completion_tokens_details'] = details
    selected = {'provider': 'z.ai', 'model': router.GLM_MODEL,
                'reasoning_effort': None, 'reason': 'off_peak'}
    with pytest.raises(router.RouterError, match='invalid_glm'):
        router.normalize_glm(json.dumps(raw).encode(), selected, 'a' * 64)


def test_operator_selected_review_routes_directly_to_terra_medium_without_tariff():
 checks=[];selected=router.select_route(config('openai_only'),'review',tariff_check=lambda **kwargs:checks.append(kwargs))
 assert selected=={'provider':'openai-codex','model':'gpt-5.6-terra','reasoning_effort':'medium','reason':'operator_selected'}
 assert checks==[] and router.response_route_allowed(selected,'gpt-5.6-terra','openai-codex','review')
 with pytest.raises(router.RouterError,match='openai_only_review_required'):router.select_route(config('openai_only'),'research')


def test_openai_only_uses_broker_with_zero_glm_transport():
 calls=[];route_log=[];value={'ok':True,'response':'{}','model':'gpt-5.6-terra','provider':'openai-codex','usage':None}
 payload={'messages':[{'role':'system','content':'review without tools'},{'role':'user','content':'bounded diff'}]}
 raw=router.routed_transport(payload,'unused-glm-key',120,config('openai_only'),'review',openai_token='openai-key',
  glm_send=lambda *_args:(_ for _ in ()).throw(AssertionError('GLM transport called')),opener=Opener(value),
  tariff_check=lambda **_kwargs:(_ for _ in ()).throw(AssertionError('tariff called')),on_route=lambda route:route_log.append(route))
 observed=json.loads(raw);assert observed['model']=='gpt-5.6-terra' and observed['provider']=='openai-codex'
 assert observed['provider_route']['reason']=='operator_selected' and observed['provider_route']['reasoning_effort']=='medium'
 assert len(route_log)==1 and observed['actual_request_sha256']==router.validate_broker_payload(payload,route_log[0])


def test_openai_only_rejects_missing_or_untrusted_broker_config():
 for value in ({'provider_policy':'openai_only'},{'provider_policy':'openai_only','openai_url':'http://attacker.invalid','openai_token_file':'/key'},{'provider_policy':'openai_only','openai_url':'http://127.0.0.1:18772/v1/infer','openai_token_file':'relative'}):
  with pytest.raises(router.RouterError):router.validate_provider_config(value)
