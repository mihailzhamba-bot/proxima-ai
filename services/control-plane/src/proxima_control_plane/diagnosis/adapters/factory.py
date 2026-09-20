"""Client factory: fail-fast on unknown provider."""

from __future__ import annotations

from typing import Any

from proxima_control_plane.diagnosis.adapters.base import LLMClient
from proxima_control_plane.diagnosis.adapters.mock import MockLLMClient
from proxima_control_plane.diagnosis.config import DiagnosisConfig

_PROVIDERS: dict[str, type] = {"mock": MockLLMClient}


def create_client(config: DiagnosisConfig) -> LLMClient:
    provider = config.provider
    client_cls = _PROVIDERS.get(provider)
    if client_cls is None:
        raise ValueError(f"unknown llm provider: {provider!r}; available: {sorted(_PROVIDERS)}")
    return client_cls()
