#!/usr/bin/python3 -I
"""Deterministic GLM/OpenAI routing through the trusted local no-tools broker."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import signal
import threading
import time
import urllib.error
import urllib.request

try:
    from .openai_no_tools import (MAX_PROMPT_CHARS, MAX_SYSTEM_CHARS,
                                  MODELS as BROKER_MODELS)
except ImportError:
    from openai_no_tools import (MAX_PROMPT_CHARS, MAX_SYSTEM_CHARS,
                                 MODELS as BROKER_MODELS)

GLM_MODEL = 'glm-5.3-flash'
GLM_PROVIDER = 'z.ai'
OPENAI_PROVIDER = 'openai-codex'
OPENAI_MODELS = {
    ('research', 'small'): ('gpt-5.6-luna', 'low'),
    ('research', 'standard'): ('gpt-5.6-sol', 'medium'),
    ('research', 'complex'): ('gpt-5.6-sol', 'high'),
    ('review', 'standard'): ('gpt-5.6-terra', 'medium'),
}
BROKER_URLS = {'http://127.0.0.1:18772/v1/infer',
               'http://127.0.0.1:18773/v1/infer'}
POLICIES = {'glm_only', 'adaptive'}
MAX_RESPONSE = 100_000
MAX_BROKER_REQUEST = 128 * 1024
MAX_TIMEOUT = 125
BROKER_COOLDOWN = 15

if not {model for model, _effort in OPENAI_MODELS.values()} <= BROKER_MODELS:
    raise RuntimeError('router_model_not_supported_by_broker')


class RouterError(ValueError):
    """Fixed nonsecret provider-routing failure reason."""


def strict_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise RouterError('duplicate_json_key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique)


class RouterDeferred(RuntimeError):
    """A known retry-safe provider rejection with no ambiguous model result."""

    def __init__(self, reason, resume_at, route):
        super().__init__(reason)
        self.reason = reason
        self.resume_at = int(resume_at)
        self.route = dict(route)

    def as_dict(self):
        return {'reason': self.reason, 'resume_at': self.resume_at,
                'provider_route': self.route}


def validate_provider_config(config):
    if type(config) is not dict:
        raise RouterError('invalid_provider_config')
    policy = config.get('provider_policy', 'glm_only')
    if policy not in POLICIES:
        raise RouterError('invalid_provider_policy')
    url = config.get('openai_url')
    token = config.get('openai_token_file')
    if policy == 'adaptive':
        if url not in BROKER_URLS:
            raise RouterError('invalid_openai_url')
        if type(token) is not str or not Path(token).is_absolute():
            raise RouterError('invalid_openai_token_path')
    elif url is not None or token is not None:
        if url not in BROKER_URLS or type(token) is not str or not Path(token).is_absolute():
            raise RouterError('invalid_openai_config')
    return policy


def _route(provider, model, effort, reason):
    return {'provider': provider, 'model': model, 'reasoning_effort': effort,
            'reason': reason}


def select_route(config, purpose, complexity='standard', *, now=None,
                 glm_rate_limited=False, tariff_check=None):
    policy = validate_provider_config(config)
    if purpose not in ('research', 'review'):
        raise RouterError('invalid_route_purpose')
    if purpose == 'review':
        complexity = 'standard'
    if (purpose, complexity) not in OPENAI_MODELS:
        raise RouterError('invalid_task_complexity')
    if policy == 'glm_only':
        return _route(GLM_PROVIDER, GLM_MODEL, None, 'glm_only')
    if glm_rate_limited:
        model, effort = OPENAI_MODELS[(purpose, complexity)]
        return _route(OPENAI_PROVIDER, model, effort, 'glm_rate_limited')
    if tariff_check is None:
        try:
            from .glm_tariff import tariff_status
        except ImportError:
            from glm_tariff import tariff_status
        tariff_check = tariff_status
    status = tariff_check(now=now, request_seconds=120)
    if type(status) is not dict or type(status.get('allowed')) is not bool:
        raise RouterError('invalid_tariff_status')
    if status['allowed']:
        return _route(GLM_PROVIDER, GLM_MODEL, None, 'off_peak')
    model, effort = OPENAI_MODELS[(purpose, complexity)]
    return _route(OPENAI_PROVIDER, model, effort, 'glm_peak')


def identity_allowed(model, provider, purpose):
    if (model, provider) == (GLM_MODEL, GLM_PROVIDER):
        return True
    if provider != OPENAI_PROVIDER:
        return False
    if purpose == 'review':
        return model == OPENAI_MODELS[('review', 'standard')][0]
    return model in {value[0] for key, value in OPENAI_MODELS.items()
                     if key[0] == 'research'}


def response_route_allowed(route, model, provider, purpose):
    if type(route) is not dict or set(route) != {
            'provider', 'model', 'reasoning_effort', 'reason'}:
        return False
    if (route['model'], route['provider']) != (model, provider):
        return False
    if provider == GLM_PROVIDER:
        return model == GLM_MODEL and route['reasoning_effort'] is None
    expected = {(selected_model, effort) for (route_purpose, _complexity),
                (selected_model, effort) in OPENAI_MODELS.items()
                if route_purpose == purpose}
    return (provider == OPENAI_PROVIDER
            and (model, route['reasoning_effort']) in expected)


def read_broker_token(path):
    try:
        try:
            from .glm_review import read_key
        except ImportError:
            from glm_review import read_key
        return read_key(path)
    except Exception as error:
        if error.__class__.__name__ == 'ReviewError':
            raise RouterError(str(error)) from None
        raise RouterError('openai_token_unavailable') from None


def _usage(value):
    if value is None:
        return None
    if type(value) is not dict or len(value) > 32:
        raise RouterError('invalid_broker_response')
    for key, item in value.items():
        if (type(key) is not str or not key or len(key) > 80
                or type(item) not in (int, float) or isinstance(item, bool)
                or not math.isfinite(item) or item < 0):
            raise RouterError('invalid_broker_response')
    return value


def _normalized(model, provider, response, usage, route, request_sha256):
    return json.dumps({'model': model, 'provider': provider,
        'provider_route': route, 'actual_request_sha256': request_sha256,
        'choices': [{'finish_reason': 'stop',
                     'message': {'role': 'assistant', 'content': response}}],
        'usage': usage}, ensure_ascii=False).encode('utf-8')


def normalize_glm(raw, route, request_sha256):
    try:
        value = strict_json(raw)
        if type(value) is not dict or value.get('model') != GLM_MODEL:
            raise ValueError()
        value = dict(value)
        value['provider'] = GLM_PROVIDER
        value['provider_route'] = route
        value['actual_request_sha256'] = request_sha256
        return json.dumps(value, ensure_ascii=False).encode('utf-8')
    except Exception:
        raise RouterError('invalid_glm_response') from None


def _messages(payload):
    try:
        messages = payload['messages']
        if (type(messages) is not list or len(messages) != 2
                or messages[0].get('role') != 'system'
                or messages[1].get('role') != 'user'
                or type(messages[0].get('content')) is not str
                or type(messages[1].get('content')) is not str):
            raise ValueError()
        return messages[0]['content'], messages[1]['content']
    except Exception:
        raise RouterError('invalid_router_payload') from None


def broker_request_wire(system, prompt, route):
    if (type(prompt) is not str or not prompt
            or len(prompt) > MAX_PROMPT_CHARS):
        raise RouterError('invalid_broker_prompt')
    if type(system) is not str or len(system) > MAX_SYSTEM_CHARS:
        raise RouterError('invalid_broker_system')
    body = {'prompt': prompt, 'system': system, 'model': route['model'],
            'reasoning_effort': route['reasoning_effort']}
    wire = json.dumps(body, ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')
    if len(wire) > MAX_BROKER_REQUEST:
        raise RouterError('broker_request_too_large')
    return wire


def validate_broker_payload(payload, route):
    system, prompt = _messages(payload)
    return hashlib.sha256(broker_request_wire(system, prompt, route)).hexdigest()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RouterError('broker_redirect_refused')


def broker_transport(system, prompt, route, url, token, timeout, *,
                     opener=None, clock=time.time):
    if url not in BROKER_URLS or route.get('provider') != OPENAI_PROVIDER:
        raise RouterError('invalid_broker_route')
    expected = OPENAI_MODELS.values()
    if (route.get('model'), route.get('reasoning_effort')) not in expected:
        raise RouterError('invalid_broker_model')
    if (type(timeout) not in (int, float) or isinstance(timeout, bool)
            or not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT):
        raise RouterError('invalid_broker_timeout')
    if type(token) is not str or not token or any(char.isspace() for char in token):
        raise RouterError('invalid_openai_token')
    wire = broker_request_wire(system, prompt, route)
    request_sha256 = hashlib.sha256(wire).hexdigest()
    request = urllib.request.Request(url, data=wire,
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + token}, method='POST')
    opener = opener or urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _NoRedirect())
    if threading.current_thread() is not threading.main_thread() or signal.getitimer(signal.ITIMER_REAL)[0]:
        raise RouterError('absolute_timeout_unavailable')
    def expired(_signal, _frame):
        raise RouterError('broker_timeout')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise RouterDeferred('openai_broker_busy',
                                     int(clock()) + BROKER_COOLDOWN, route) from None
            raise RouterError('openai_broker_rejected') from None
        except RouterDeferred:
            raise
        except RouterError:
            raise
        except Exception:
            raise RouterError('openai_broker_unavailable') from None
        if len(raw) > MAX_RESPONSE:
            raise RouterError('broker_response_too_large')
        value = strict_json(raw)
        allowed = {'ok', 'response', 'model', 'provider', 'usage', 'completed'}
        if (type(value) is not dict or not {'ok', 'response', 'model', 'provider', 'usage'} <= set(value)
                or set(value) - allowed or value['ok'] is not True
                or ('completed' in value and value['completed'] is not True)
                or value['model'] != route['model']
                or value['provider'] != OPENAI_PROVIDER
                or type(value['response']) is not str
                or not 1 <= len(value['response'].encode('utf-8')) <= MAX_RESPONSE):
            raise RouterError('invalid_broker_response')
        usage = _usage(value['usage'])
        return _normalized(value['model'], value['provider'], value['response'],
                           usage, route, request_sha256)
    except RouterDeferred:
        raise
    except RouterError:
        raise
    except Exception:
        raise RouterError('invalid_broker_response') from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def routed_transport(payload, glm_key, timeout, config, purpose,
                     complexity='standard', *, openai_token=None,
                     glm_send=None, opener=None, now=None, clock=time.time,
                     tariff_check=None, on_route=None,
                     monotonic=time.monotonic):
    if (type(timeout) not in (int, float) or isinstance(timeout, bool)
            or not math.isfinite(timeout) or timeout <= 0):
        raise RouterError('invalid_router_timeout')
    deadline = monotonic() + timeout
    route = select_route(config, purpose, complexity, now=now,
                         tariff_check=tariff_check)
    if route['provider'] == OPENAI_PROVIDER:
        if on_route:
            on_route(route)
        token = openai_token or read_broker_token(config['openai_token_file'])
        system, prompt = _messages(payload)
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise RouterError('router_timeout')
        return broker_transport(system, prompt, route, config['openai_url'],
                                token, min(remaining, MAX_TIMEOUT),
                                opener=opener, clock=clock)
    if glm_send is None:
        try:
            from .glm_review import transport
        except ImportError:
            from glm_review import transport
        glm_send = transport
    try:
        if on_route:
            on_route(route)
        glm_wire = json.dumps(payload).encode('utf-8')
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise RouterError('router_timeout')
        return normalize_glm(glm_send(payload, glm_key, remaining), route,
                             hashlib.sha256(glm_wire).hexdigest())
    except Exception as error:
        policy = config.get('provider_policy', 'glm_only')
        rate_limited = isinstance(error, urllib.error.HTTPError) and error.code == 429
        tariff_deferred = error.__class__.__name__ == 'TariffDeferred'
        if policy != 'adaptive' or not (rate_limited or tariff_deferred):
            raise
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise RouterError('router_timeout')
        fallback = select_route(config, purpose, complexity, now=now,
                                glm_rate_limited=True, tariff_check=tariff_check)
        if on_route:
            on_route(fallback)
        token = openai_token or read_broker_token(config['openai_token_file'])
        system, prompt = _messages(payload)
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise RouterError('router_timeout')
        return broker_transport(system, prompt, fallback, config['openai_url'],
                                token, min(remaining, MAX_TIMEOUT),
                                opener=opener, clock=clock)
