import pytest

from proxima_control_plane.diagnosis.adapters.factory import create_client
from proxima_control_plane.diagnosis.adapters.mock import MockLLMClient
from proxima_control_plane.diagnosis.config import DiagnosisConfig
from proxima_control_plane.diagnosis.models import parse_signal
from proxima_control_plane.diagnosis.prompts.builder import build_messages
from proxima_control_plane.diagnosis.validator import validate_diagnosis


def make_signal():
    return parse_signal(
        {
            "signal_id": "SYNTH-SIG-008",
            "scenario_id": "SCN-008",
            "generated_at": "2026-08-27T00:00:00Z",
            "trust": "unreleased",
            "payload": {"cycle": "W1", "coverage_pct": 62.5, "days_cover": 3},
            "context_extracts": [{"note": "SYNTH extract text"}],
            "source_refs": ["SYNTH-SRC-A", "SYNTH-SRC-B"],
        }
    )


def diagnose_once() -> dict:
    system, user, _version = build_messages(make_signal())
    return MockLLMClient().diagnose(system, user, {})


def text_strings(obj, acc):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"hypothesis", "question", "why_it_matters", "confidence_note"}:
                acc.append(value)
            else:
                text_strings(value, acc)
    elif isinstance(obj, list):
        for item in obj:
            text_strings(item, acc)
    return acc


def test_mock_output_is_schema_valid() -> None:
    assert validate_diagnosis(diagnose_once()) == []


def test_mock_is_deterministic_on_same_input() -> None:
    first = diagnose_once()
    second = diagnose_once()
    assert first == second


def test_mock_numbers_come_from_input_only() -> None:
    obj = diagnose_once()
    input_numbers = {62.5, 3}
    out_numbers = set()
    for text in text_strings(obj, []):
        for token in re_numbers(text):
            out_numbers.add(float(token))
    assert out_numbers == input_numbers


def re_numbers(text: str) -> list[str]:
    import re

    return [t for t in re.findall(r"\d+(?:\.\d+)?", text) if not re.fullmatch(r"0+\d*", t) or "." in t]


def test_mock_source_refs_come_from_input_only() -> None:
    obj = diagnose_once()
    used = set()
    for cause in [obj["primary_cause"], *obj["alternatives"]]:
        used.update(cause["source_refs"])
    assert used == {"SYNTH-SRC-A", "SYNTH-SRC-B"}


def test_factory_mock_returns_mock_client() -> None:
    client = create_client(DiagnosisConfig(provider="mock"))
    assert isinstance(client, MockLLMClient)


def test_factory_unknown_provider_raises_value_error() -> None:
    with pytest.raises(ValueError):
        create_client(DiagnosisConfig(provider="openai"))


def test_mock_rejects_user_without_reference_block() -> None:
    with pytest.raises(ValueError):
        MockLLMClient().diagnose("system", "no markers here", {})
