import io
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.loop import openai_no_tools as runner


def request(**changes):
    value = {'prompt': 'Analyze this.', 'system': '', 'model': 'gpt-5.6-sol',
             'reasoning_effort': 'low'}
    value.update(changes)
    return value


def encoded(**changes):
    return json.dumps(request(**changes)).encode()


class FakeAgent:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.enabled_toolsets = kwargs['enabled_toolsets']
        self.tools = []
        self.valid_tool_names = set()
        self._memory_manager = None
        self.memory_manager = None
        self.provider = kwargs['provider']
        self.closed = False
        self.ran = False
        self.__class__.instances.append(self)

    def run_conversation(self, prompt, **kwargs):
        assert self._persist_disabled is True
        assert self._dump_api_request_debug('secret') is None
        self.ran = True
        self.prompt = prompt
        self.run_kwargs = kwargs
        return {'completed': True, 'final_response': 'done', 'api_calls': 1,
                'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15,
                'estimated_cost_usd': 999, 'secret': 'must-not-leak'}

    def close(self):
        self.closed = True


def resolver(provider, model):
    assert provider == 'openai-codex'
    assert model in runner.MODELS
    return {'provider': 'openai-codex', 'api_key': 'fixture-secret',
            'base_url': 'https://fixture.invalid', 'api_mode': None,
            'command': None, 'args': [], 'credential_pool': None}


@pytest.fixture(autouse=True)
def reset_agents():
    FakeAgent.instances = []


@pytest.mark.parametrize('model', sorted(runner.MODELS))
@pytest.mark.parametrize('effort', sorted(runner.EFFORTS))
def test_allowed_models_and_efforts_build_exact_no_tools_agent(model, effort):
    output, agent = runner.run_request(request(model=model, reasoning_effort=effort),
                                       resolver, FakeAgent)
    assert output == {'ok': True, 'completed': True, 'response': 'done',
        'model': model, 'provider': 'openai-codex',
        'usage': {'api_calls': 1, 'input_tokens': 10, 'output_tokens': 5,
                  'total_tokens': 15}}
    assert agent.kwargs['enabled_toolsets'] == []
    assert agent.kwargs['max_iterations'] == 1
    assert agent.kwargs['max_tokens'] == 4096
    assert agent.kwargs['reasoning_config'] == {'enabled': True, 'effort': effort}
    assert agent.kwargs['run_budget_seconds'] == 110
    assert agent.kwargs['fallback_model'] is None
    assert agent.kwargs['session_db'] is None
    assert agent.kwargs['checkpoints_enabled'] is False
    assert agent.kwargs['skip_context_files'] is True
    assert agent.kwargs['skip_memory'] is True
    assert agent.kwargs['skip_background_review'] is True
    assert agent.kwargs['platform'] == 'api_server'
    assert agent.run_kwargs == {'system_message': None, 'conversation_history': []}


@pytest.mark.parametrize('changes', [
    {'model': 'gpt-5.6-sol-900k'},
    {'model': 'gpt-6-astra-ultra'},
    {'reasoning_effort': 'ultra'},
    {'prompt': ''},
    {'prompt': 'x' * 100_001},
    {'system': 'x' * 20_001},
])
def test_request_allowlist_and_bounds(changes):
    with pytest.raises(ValueError):
        runner.parse_request(encoded(**changes))


@pytest.mark.parametrize('raw', [
    b'not-json',
    b'{"prompt":"a","prompt":"b","system":"","model":"gpt-5.5","reasoning_effort":"low"}',
    json.dumps({**request(), 'tools': []}).encode(),
    json.dumps({**request(), 'network': True}).encode(),
    json.dumps({**request(), 'calls': []}).encode(),
])
def test_malformed_duplicate_or_capability_fields_rejected(raw):
    with pytest.raises(ValueError):
        runner.parse_request(raw)


def test_input_byte_limit_rejected():
    with pytest.raises(ValueError):
        runner.parse_request(b' ' * (runner.MAX_INPUT_BYTES + 1))


def test_provider_must_match_before_constructor():
    with pytest.raises(RuntimeError, match='provider_mismatch'):
        runner.run_request(request(), lambda *_: {'provider': 'openai'}, FakeAgent)
    assert FakeAgent.instances == []


@pytest.mark.parametrize(('attribute', 'value'), [
    ('enabled_toolsets', ['terminal']),
    ('tools', [{'function': {'name': 'terminal'}}]),
    ('valid_tool_names', {'terminal'}),
    ('_memory_manager', object()),
    ('memory_manager', object()),
])
def test_invariant_gate_runs_before_model(attribute, value):
    class UnsafeAgent(FakeAgent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            setattr(self, attribute, value)
    with pytest.raises(RuntimeError):
        runner.run_request(request(), resolver, UnsafeAgent)
    assert FakeAgent.instances[-1].ran is False


def test_main_closes_agent_when_invariant_gate_rejects_after_constructor():
    class UnsafeAgent(FakeAgent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.tools = [{'function': {'name': 'forbidden'}}]
    output = io.StringIO()
    assert runner.main(input_stream=io.BytesIO(encoded()), output_stream=output,
                       resolver=resolver, agent_cls=UnsafeAgent,
                       use_alarm=False) == 1
    assert json.loads(output.getvalue()) == runner.FAILURE
    assert FakeAgent.instances[-1].ran is False
    assert FakeAgent.instances[-1].closed is True


def test_main_silences_dependencies_and_closes_before_emitting(capsys):
    class NoisyAgent(FakeAgent):
        def __init__(self, **kwargs):
            print('constructor noise')
            super().__init__(**kwargs)
        def run_conversation(self, prompt, **kwargs):
            print('run noise', file=sys.stderr)
            return super().run_conversation(prompt, **kwargs)
        def close(self):
            print('close noise')
            super().close()
    def noisy_resolver(*args):
        print('resolver noise')
        return resolver(*args)
    output = io.StringIO()
    assert runner.main(input_stream=io.BytesIO(encoded()), output_stream=output,
                       resolver=noisy_resolver, agent_cls=NoisyAgent,
                       use_alarm=False) == 0
    result = json.loads(output.getvalue())
    assert result['response'] == 'done'
    assert 'fixture-secret' not in output.getvalue()
    assert FakeAgent.instances[-1].closed is True
    assert capsys.readouterr().out == ''


def test_main_malformed_input_is_fixed_json_without_dependencies():
    calls = []
    output = io.StringIO()
    assert runner.main(input_stream=io.BytesIO(b'bad'), output_stream=output,
                       resolver=lambda *_: calls.append('resolver'),
                       agent_cls=FakeAgent, use_alarm=False) == 1
    assert json.loads(output.getvalue()) == runner.FAILURE
    assert calls == []


def test_incomplete_or_oversized_output_becomes_fixed_failure():
    class Incomplete(FakeAgent):
        def run_conversation(self, *_args, **_kwargs):
            return {'completed': False, 'final_response': 'provider detail'}
    output = io.StringIO()
    assert runner.main(input_stream=io.BytesIO(encoded()), output_stream=output,
                       resolver=resolver, agent_cls=Incomplete,
                       use_alarm=False) == 1
    assert json.loads(output.getvalue()) == runner.FAILURE

    payload = {'ok': True, 'response': 'x' * runner.MAX_OUTPUT_BYTES}
    assert json.loads(runner._encode_output(payload)) == runner.FAILURE


def test_usage_only_contains_bounded_numeric_fields():
    result = {'api_calls': True, 'input_tokens': -1, 'output_tokens': float('nan'),
              'total_tokens': runner.MAX_USAGE_VALUE + 1,
              'reasoning_tokens': 7, 'prompt_tokens': 3.5,
              'secret': 100}
    assert runner._usage(result) == {'reasoning_tokens': 7, 'prompt_tokens': 3.5}


def test_timeout_handler_exits_immediately_without_cleanup(monkeypatch):
    agent = FakeAgent(**{'provider': 'openai-codex', 'enabled_toolsets': []})
    runner._ACTIVE_AGENT = agent
    codes = []
    monkeypatch.setattr(runner.os, '_exit', lambda code: codes.append(code))
    runner._timeout_handler(None, None)
    assert agent.closed is False
    assert codes == [124]
    runner._ACTIVE_AGENT = None


def test_blocking_close_cannot_extend_hard_alarm():
    root = Path(__file__).resolve().parents[2]
    code = r"""
import io
import json
import time
from tools.loop import openai_no_tools as runner

runner.HARD_TIMEOUT_SECONDS = 0.1

def resolver(_provider, _model):
    return {
        'provider': 'openai-codex',
        'api_key': 'fixture',
        'base_url': 'https://fixture.invalid',
        'api_mode': None,
        'command': None,
        'args': [],
        'credential_pool': None,
    }

class Agent:
    def __init__(self, **kwargs):
        self.provider = kwargs['provider']
        self.enabled_toolsets = []
        self.tools = []
        self.valid_tool_names = set()
        self._memory_manager = None
        self.memory_manager = None
    def run_conversation(self, *_args, **_kwargs):
        return {'completed': True, 'final_response': 'done'}
    def close(self):
        time.sleep(10)

payload = json.dumps({
    'prompt': 'test',
    'system': '',
    'model': 'gpt-5.6-luna',
    'reasoning_effort': 'low',
}).encode()
runner.main(
    input_stream=io.BytesIO(payload),
    output_stream=io.StringIO(),
    resolver=resolver,
    agent_cls=Agent,
    use_alarm=True,
)
"""
    started = time.monotonic()
    process = subprocess.run(
        [sys.executable, '-c', code],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=2,
    )
    assert process.returncode == 124
    assert time.monotonic() - started < 1.5
    assert process.stdout == b''
    assert process.stderr == b''


def test_alarm_remains_armed_through_close_then_disarms(monkeypatch):
    events = []
    class OrderedAgent(FakeAgent):
        def close(self):
            events.append('close')
            super().close()
    monkeypatch.setattr(runner.signal, 'signal',
                        lambda *_args: events.append('signal') or object())
    def timer(_kind, seconds):
        events.append(('timer', seconds))
    monkeypatch.setattr(runner.signal, 'setitimer', timer)
    output = io.StringIO()
    assert runner.main(input_stream=io.BytesIO(encoded()), output_stream=output,
                       resolver=resolver, agent_cls=OrderedAgent,
                       use_alarm=True) == 0
    assert events.index('close') < events.index(('timer', 0))
    assert ('timer', 120) in events
