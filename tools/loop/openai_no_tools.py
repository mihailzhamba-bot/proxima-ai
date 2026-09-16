#!/usr/bin/python3 -I
"""Trusted one-shot Hermes OpenAI runner with an empty tool surface."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import logging
import math
import os
from pathlib import Path
import signal
import sys
import threading

HERMES_ROOT = '/opt/hermes'
MAX_INPUT_BYTES = 160_000
MAX_OUTPUT_BYTES = 100_000
MAX_PROMPT_CHARS = 100_000
MAX_SYSTEM_CHARS = 20_000
HARD_TIMEOUT_SECONDS = 120
RUN_BUDGET_SECONDS = 110
MAX_USAGE_VALUE = 1_000_000_000
MODELS = frozenset({
    'gpt-5.6-luna',
    'gpt-5.6-sol',
    'gpt-5.6-terra',
    'gpt-6-astra',
    'gpt-5.5',
})
EFFORTS = frozenset({'low', 'medium', 'high'})
REQUEST_FIELDS = frozenset({'prompt', 'system', 'model', 'reasoning_effort'})
USAGE_FIELDS = (
    'api_calls',
    'input_tokens',
    'output_tokens',
    'cache_read_tokens',
    'cache_write_tokens',
    'reasoning_tokens',
    'prompt_tokens',
    'completion_tokens',
    'total_tokens',
)
FAILURE = {'ok': False, 'completed': False, 'response': '', 'model': None,
           'provider': None, 'usage': {}, 'error': 'request_failed'}
_ACTIVE_AGENT = None


def _strict_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate_key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique)


def parse_request(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        raise ValueError('invalid_input')
    try:
        request = _strict_json(raw.decode('utf-8', errors='strict'))
    except Exception:
        raise ValueError('invalid_input') from None
    if type(request) is not dict or set(request) != REQUEST_FIELDS:
        raise ValueError('invalid_request')
    prompt = request['prompt']
    system = request['system']
    model = request['model']
    effort = request['reasoning_effort']
    if type(prompt) is not str or not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError('invalid_prompt')
    if type(system) is not str or len(system) > MAX_SYSTEM_CHARS:
        raise ValueError('invalid_system')
    if model not in MODELS or type(model) is not str:
        raise ValueError('invalid_model')
    if effort not in EFFORTS or type(effort) is not str:
        raise ValueError('invalid_reasoning_effort')
    try:
        prompt.encode('utf-8')
        system.encode('utf-8')
    except UnicodeEncodeError:
        raise ValueError('invalid_text') from None
    return request


def _load_dependencies():
    root = Path(HERMES_ROOT)
    if not root.is_absolute() or str(root) != HERMES_ROOT:
        raise RuntimeError('runtime_unavailable')
    if HERMES_ROOT not in sys.path:
        sys.path.insert(0, HERMES_ROOT)
    from gateway.platforms.api_server import _resolve_request_runtime_agent_kwargs
    from run_agent import AIAgent
    return _resolve_request_runtime_agent_kwargs, AIAgent


def _usage(result):
    usage = {}
    for key in USAGE_FIELDS:
        value = result.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            continue
        if not 0 <= value <= MAX_USAGE_VALUE:
            continue
        usage[key] = value
    return usage


def _assert_no_tools(agent):
    if getattr(agent, 'enabled_toolsets', None) != []:
        raise RuntimeError('tool_invariant')
    if getattr(agent, 'tools', None):
        raise RuntimeError('tool_invariant')
    if getattr(agent, 'valid_tool_names', None):
        raise RuntimeError('tool_invariant')
    if getattr(agent, '_memory_manager', None) is not None:
        raise RuntimeError('memory_invariant')
    if getattr(agent, 'memory_manager', None) is not None:
        raise RuntimeError('memory_invariant')


def run_request(request, resolver, agent_cls, register_agent=lambda _agent: None):
    model = request['model']
    effort = request['reasoning_effort']
    runtime = resolver('openai-codex', model)
    if type(runtime) is not dict or runtime.get('provider') != 'openai-codex':
        raise RuntimeError('provider_mismatch')
    agent = agent_cls(
        model=model,
        **runtime,
        enabled_toolsets=[],
        max_iterations=1,
        max_tokens=4096,
        reasoning_config={'enabled': True, 'effort': effort},
        run_budget_seconds=RUN_BUDGET_SECONDS,
        quiet_mode=True,
        verbose_logging=False,
        save_trajectories=False,
        skip_context_files=True,
        skip_memory=True,
        skip_background_review=True,
        fallback_model=None,
        session_db=None,
        checkpoints_enabled=False,
        platform='api_server',
    )
    register_agent(agent)
    agent._persist_disabled = True
    agent._dump_api_request_debug = lambda *_args, **_kwargs: None
    _assert_no_tools(agent)
    result = agent.run_conversation(
        request['prompt'],
        system_message=request['system'] or None,
        conversation_history=[],
    )
    if type(result) is not dict or result.get('completed') is not True:
        raise RuntimeError('incomplete_result')
    response = result.get('final_response')
    if type(response) is not str:
        raise RuntimeError('invalid_result')
    provider = getattr(agent, 'provider', None)
    if provider != 'openai-codex':
        raise RuntimeError('provider_mismatch')
    return {
        'ok': True,
        'completed': True,
        'response': response,
        'model': model,
        'provider': provider,
        'usage': _usage(result),
    }, agent


def _close_agent(agent):
    if agent is None:
        return
    try:
        agent.close()
    except BaseException:
        pass


def _timeout_handler(_signum, _frame):
    try:
        _close_agent(_ACTIVE_AGENT)
    finally:
        os._exit(124)


def _encode_output(payload):
    try:
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False
        ).encode('utf-8')
    except Exception:
        encoded = json.dumps(FAILURE, separators=(',', ':')).encode('ascii')
    if len(encoded) > MAX_OUTPUT_BYTES:
        encoded = json.dumps(FAILURE, separators=(',', ':')).encode('ascii')
    return encoded


def main(*, input_stream=None, output_stream=None, resolver=None, agent_cls=None,
         use_alarm=True):
    global _ACTIVE_AGENT
    source = input_stream if input_stream is not None else sys.stdin.buffer
    destination = output_stream if output_stream is not None else sys.stdout
    payload = FAILURE
    agent = None
    previous_handler = None
    previous_logging = logging.root.manager.disable
    alarm_armed = False

    with open(os.devnull, 'w') as devnull, redirect_stdout(devnull), redirect_stderr(devnull):
        logging.disable(logging.CRITICAL)
        try:
            if use_alarm:
                if threading.current_thread() is not threading.main_thread():
                    raise RuntimeError('alarm_unavailable')
                previous_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.setitimer(signal.ITIMER_REAL, HARD_TIMEOUT_SECONDS)
                alarm_armed = True
            raw = source.read(MAX_INPUT_BYTES + 1)
            request = parse_request(raw)
            if resolver is None or agent_cls is None:
                resolver, agent_cls = _load_dependencies()
            def register(created):
                global _ACTIVE_AGENT
                _ACTIVE_AGENT = created
            payload, agent = run_request(request, resolver, agent_cls, register)
        except BaseException:
            payload = FAILURE
        finally:
            _close_agent(agent or _ACTIVE_AGENT)
            _ACTIVE_AGENT = None
            if alarm_armed:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous_handler)
            logging.disable(previous_logging)

    encoded = _encode_output(payload)
    text = encoded.decode('utf-8') + chr(10)
    destination.write(text)
    destination.flush()
    return 0 if payload.get('ok') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
