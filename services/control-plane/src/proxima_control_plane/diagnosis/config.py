"""DiagnosisConfig: TOML loading with built-in defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_API_KEY_ENV = "PROXIMA_LLM_API_KEY"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_AUDIT_PATH = "logs/diagnosis-audit.jsonl"
DEFAULT_MODEL = "mock-v1"

_KNOWN_KEYS = {"llm_enabled", "provider", "model", "base_url", "api_key_env", "timeout_seconds", "audit_path"}


@dataclass(frozen=True)
class DiagnosisConfig:
    llm_enabled: bool = True
    provider: str = "mock"
    model: str = DEFAULT_MODEL
    base_url: str | None = None
    api_key_env: str = DEFAULT_API_KEY_ENV
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    audit_path: str = DEFAULT_AUDIT_PATH


def _typed(section: dict[str, Any], key: str, expected: type) -> Any:
    value = section[key]
    if expected is bool:
        ok = isinstance(value, bool)
    elif expected is int:
        ok = isinstance(value, int) and not isinstance(value, bool)
    else:
        ok = isinstance(value, expected)
    if not ok:
        raise ValueError(f"config key diagnosis.{key} must be {expected.__name__}, got {type(value).__name__}")
    return value


def load_config(path: str | Path | None = None) -> DiagnosisConfig:
    """Load TOML config; path=None (or missing file) yields built-in defaults.

    A partial file overrides only the keys it contains; the rest stay default.
    """
    if path is None:
        return DiagnosisConfig()
    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    section = data.get("diagnosis", data)
    if not isinstance(section, dict):
        raise ValueError("config section 'diagnosis' must be a table")

    unknown = set(section) - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")

    overrides: dict[str, Any] = {}
    for key in ("llm_enabled", "timeout_seconds"):
        if key in section:
            overrides[key] = _typed(section, key, bool if key == "llm_enabled" else int)
    for key in ("provider", "model", "api_key_env", "audit_path"):
        if key in section:
            overrides[key] = _typed(section, key, str)
    if "base_url" in section:
        overrides["base_url"] = _typed(section, "base_url", str)

    if overrides.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS) <= 0:
        raise ValueError("config key diagnosis.timeout_seconds must be positive")

    return DiagnosisConfig(**overrides)
