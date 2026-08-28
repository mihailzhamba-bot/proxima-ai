import pytest

from proxima_control_plane.diagnosis.config import load_config


def test_defaults_without_file() -> None:
    cfg = load_config(None)
    assert cfg.llm_enabled is True
    assert cfg.provider == "mock"
    assert cfg.model == "mock-v1"
    assert cfg.base_url is None
    assert cfg.api_key_env == "PROXIMA_LLM_API_KEY"
    assert cfg.timeout_seconds == 90
    assert cfg.audit_path == "logs/diagnosis-audit.jsonl"


def test_toml_overrides_partial(tmp_path) -> None:
    cfg_path = tmp_path / "diagnosis.toml"
    cfg_path.write_text(
        '[diagnosis]\nprovider = "openai-compatible"\n'
        'model = "llama-3"\nbase_url = "https://synth.example.internal/v1"\n'
        'api_key_env = "PROXIMA_LLM_API_KEY"\ntimeout_seconds = 30\n'
        'llm_enabled = false\naudit_path = "logs/audit.jsonl"\n',
        encoding="utf-8",
    )
    cfg = load_config(cfg_path)
    assert cfg.provider == "openai-compatible"
    assert cfg.model == "llama-3"
    assert cfg.base_url == "https://synth.example.internal/v1"
    assert cfg.api_key_env == "PROXIMA_LLM_API_KEY"
    assert cfg.timeout_seconds == 30
    assert cfg.llm_enabled is False
    assert cfg.audit_path == "logs/audit.jsonl"


def test_toml_partial_keeps_defaults(tmp_path) -> None:
    cfg_path = tmp_path / "diagnosis.toml"
    cfg_path.write_text('[diagnosis]\ntimeout_seconds = 15\n', encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.timeout_seconds == 15
    assert cfg.provider == "mock"
    assert cfg.audit_path == "logs/diagnosis-audit.jsonl"


def test_api_key_env_stores_name_not_value(tmp_path) -> None:
    cfg_path = tmp_path / "diagnosis.toml"
    cfg_path.write_text('[diagnosis]\napi_key_env = "MY_KEY_NAME"\n', encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.api_key_env == "MY_KEY_NAME"


def test_unknown_key_rejected(tmp_path) -> None:
    cfg_path = tmp_path / "diagnosis.toml"
    cfg_path.write_text('[diagnosis]\napi_key = "sk-synth"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown config keys"):
        load_config(cfg_path)


def test_wrong_type_rejected(tmp_path) -> None:
    cfg_path = tmp_path / "diagnosis.toml"
    cfg_path.write_text('[diagnosis]\ntimeout_seconds = "soon"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="timeout_seconds"):
        load_config(cfg_path)


def test_non_positive_timeout_rejected(tmp_path) -> None:
    cfg_path = tmp_path / "diagnosis.toml"
    cfg_path.write_text('[diagnosis]\ntimeout_seconds = 0\n', encoding="utf-8")
    with pytest.raises(ValueError, match="positive"):
        load_config(cfg_path)
