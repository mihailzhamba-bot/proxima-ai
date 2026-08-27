"""Draft-schema validation: validate_diagnosis(obj) -> list[str] (empty = ok)."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

import jsonschema

_SCHEMA_CACHE: dict[str, jsonschema.Draft202012Validator] = {}


def _validator(version: str) -> jsonschema.Draft202012Validator:
    if version not in _SCHEMA_CACHE:
        text = resources.files("proxima_control_plane.diagnosis").joinpath(
            "schema", f"diagnosis.{version}.json"
        ).read_text(encoding="utf-8")
        schema = json.loads(text)
        _SCHEMA_CACHE[version] = jsonschema.Draft202012Validator(schema)
    return _SCHEMA_CACHE[version]


def validate_diagnosis(obj: Any, version: str = "draft.v1") -> list[str]:
    if not isinstance(obj, dict):
        return ["diagnosis must be a JSON object"]
    validator = _validator(version)
    return [
        f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
    ]
