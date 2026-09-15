"""A supplied model manifest is not its own source of installation authority."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / 'infra/loop-control/configure_local_stt.py'
spec = importlib.util.spec_from_file_location('loop_stt_installer', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def assets(tmp_path):
    model = tmp_path / 'faster-whisper-base'
    model.mkdir()
    (model / 'model.bin').write_bytes(b'fixture model')
    manifest = {'model': 'fixture', 'revision': 'fixed', 'files': [
        {'file': 'model.bin', 'bytes': 13, 'sha256': hashlib.sha256(b'fixture model').hexdigest()}]}
    (tmp_path / 'model-manifest.json').write_text(json.dumps(manifest))
    package = tmp_path / 'python-deps/faster_whisper'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('')
    meta = tmp_path / 'python-deps/faster_whisper-1.2.1.dist-info/METADATA'
    meta.parent.mkdir()
    meta.write_text('Name: faster-whisper\nVersion: 1.2.1\n')
    return {'model': manifest, 'packages': [{'name': 'faster-whisper', 'version': '1.2.1'}]}, meta


def test_accepts_exact_model_and_dependency_lock(tmp_path):
    lock, _ = assets(tmp_path)
    assert module.validate_assets(tmp_path, lock) == lock['model']


def test_rejects_model_changed_together_with_untrusted_manifest(tmp_path):
    lock, _ = assets(tmp_path)
    (tmp_path / 'faster-whisper-base/model.bin').write_bytes(b'changed model')
    forged = json.loads(json.dumps(lock['model']))
    forged['files'][0]['sha256'] = hashlib.sha256(b'changed model').hexdigest()
    (tmp_path / 'model-manifest.json').write_text(json.dumps(forged))
    with pytest.raises(ValueError, match='trusted lock'):
        module.validate_assets(tmp_path, lock)


def test_rejects_wrong_dependency_version(tmp_path):
    lock, meta = assets(tmp_path)
    meta.write_text('Name: faster-whisper\nVersion: 9.9.9\n')
    with pytest.raises(ValueError, match='packages'):
        module.validate_assets(tmp_path, lock)


def test_rejects_changed_model_bytes_with_original_manifest(tmp_path):
    lock, _ = assets(tmp_path)
    (tmp_path / 'faster-whisper-base/model.bin').write_bytes(b'changed model')
    with pytest.raises(ValueError, match='integrity'):
        module.validate_assets(tmp_path, lock)
