"""Enable offline local STT only in the dedicated LOOP Hermes deployment."""
import argparse
import datetime
import email
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import tarfile

def mount(service, source, target):
    volumes = service.setdefault('volumes', [])
    if any(not isinstance(v, str) for v in volumes):
        raise ValueError('Review structured volumes before configuring STT')
    service['volumes'] = [v for v in volumes if v.split(':')[1] != target]
    service['volumes'].append(str(source) + ':' + target + ':ro')


def validate_assets(assets, lock):
    manifest = json.loads((assets / 'model-manifest.json').read_text())
    expected = lock['model']
    if manifest != expected:
        raise ValueError('Model manifest differs from the trusted lock')
    model = (assets / 'faster-whisper-base').resolve()
    names = [item['file'] for item in expected['files']]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate model files in lock')
    for item in expected['files']:
        path = (model / item['file']).resolve()
        if not path.is_relative_to(model) or path.stat().st_size != item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Model integrity mismatch')
    normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
    actual = {}
    for path in (assets / 'python-deps').glob('*.dist-info/METADATA'):
        metadata = email.message_from_string(path.read_text())
        name = normalize(metadata['Name'])
        if name in actual:
            raise ValueError('Duplicate installed package metadata')
        actual[name] = metadata['Version']
    packages = {normalize(p['name']): p['version'] for p in lock['packages']}
    if actual != packages:
        raise ValueError('Installed STT packages differ from the trusted lock')
    if not (assets / 'python-deps/faster_whisper/__init__.py').is_file():
        raise ValueError('STT import package missing')
    return manifest


def main():
    import yaml
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--lock', type=Path, default=Path(__file__).with_name('local-stt.lock.json'))
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0 or socket.gethostname() != 'mckenzie':
        raise SystemExit('Dedicated LOOP-control root session required')
    assets = args.assets.resolve()
    manifest = validate_assets(assets, json.loads(args.lock.read_text()))
    model = assets / 'faster-whisper-base'
    if args.check_only:
        print(json.dumps({'assets_match_trusted_lock': True, 'configuration_changed': False}))
        return
    root = Path('/etc/loop')
    config_path, compose_path = root / 'hermes.yaml', root / 'compose.yaml'
    config = yaml.safe_load(config_path.read_text())
    compose = yaml.safe_load(compose_path.read_text())
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/var/backups/loop-native') / ('stt-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    archive = backup / 'configuration.tar.gz'
    with tarfile.open(archive, 'w:gz') as output:
        output.add(config_path, arcname='hermes.yaml')
        output.add(compose_path, arcname='compose.yaml')
    archive.chmod(0o600)
    stt = config.setdefault('stt', {})
    stt.update(enabled=True, provider='local', language='ru', echo_transcripts=True)
    stt.setdefault('local', {}).update(model='/opt/loop/stt-model', device='cpu', compute_type='int8',
                                     language='ru', vad=True, unload_after_idle_seconds=60,
                                     initial_prompt='Hermes, Хермес, LOOP, Paperclip, OpenHands, Harper, Claudette, Mike, PROXIMA.')
    service = compose['services']['hermes']
    mount(service, assets / 'python-deps', '/opt/loop/stt-python')
    mount(service, model, '/opt/loop/stt-model')
    env = service.setdefault('environment', {})
    paths = [p for p in env.get('PYTHONPATH', '').split(':') if p and p != '/opt/loop/stt-python']
    env['PYTHONPATH'] = ':'.join(['/opt/loop/stt-python', *paths])
    env.update(OMP_NUM_THREADS='2', HF_HOME='/var/lib/loop/hermes/cache/huggingface',
               HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1')
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    compose_path.write_text(yaml.safe_dump(compose, sort_keys=False))
    receipt = {'backup': str(archive), 'assets': str(assets), 'provider': 'local', 'language': 'ru',
               'model_revision': manifest['revision'], 'restart_performed': False,
               'queue_modified': False, 'other_profiles_modified': False}
    (root / 'stt-manifest.json').write_text(json.dumps({**receipt, 'model': manifest}, indent=2))
    (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    (backup / 'receipt.json').chmod(0o600)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
