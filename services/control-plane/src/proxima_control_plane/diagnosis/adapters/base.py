"""Provider-agnostic LLM client seam."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def diagnose(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a diagnosis JSON object built from system+user prompt per schema."""
        ...
