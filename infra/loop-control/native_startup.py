"""Pinned Hermes native startup hook; registration itself needs no event loop."""
import importlib.util
import json
from pathlib import Path


async def handle(event_type, context):
    if event_type != 'gateway:startup':
        return
    from gateway.run import _gateway_runner_ref
    gateway = _gateway_runner_ref() if _gateway_runner_ref else None
    if gateway is None:
        raise RuntimeError('Native LOOP gateway unavailable')
    previous = getattr(gateway, '_loop_native_notify_task', None)
    if previous is not None and not previous.done():
        return
    path = Path('/var/lib/loop/hermes/plugins/loop-chat/__init__.py')
    spec = importlib.util.spec_from_file_location('_loop_native_notifications', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = json.loads(Path('/etc/loop/native-telegram.json').read_text())
    plugin = module.NativePlugin(config)
    gateway._spawn_supervised(plugin.notify, 'loop-native-notifications',
                              on_spawn=lambda task: setattr(gateway, '_loop_native_notify_task', task))
