"""Deterministic mock client: builds a schema-valid diagnosis from the builder reference block."""

from __future__ import annotations

from typing import Any

from proxima_control_plane.diagnosis.prompts.builder import BEGIN_MARKER, END_MARKER

MODEL = "mock-v1"


def _parse_reference(user: str) -> dict[str, str]:
    lines = user.splitlines()
    try:
        begin = lines.index(BEGIN_MARKER)
        end = lines.index(END_MARKER, begin + 1)
    except ValueError as exc:
        raise ValueError("mock client requires a DIAGNOSIS_INPUT reference block in user message") from exc
    reference: dict[str, str] = {}
    for line in lines[begin + 1 : end]:
        key, sep, value = line.partition("=")
        if sep:
            reference[key] = value
    return reference


def _format_number(value: int | float) -> str:
    return str(value)


def _numbers(reference: dict[str, str]) -> dict[str, int | float]:
    raw = reference.get("numbers", "")
    parsed: dict[str, int | float] = {}
    for pair in filter(None, raw.split("|")):
        path, sep, value = pair.partition("=")
        if not sep:
            continue
        parsed[path] = float(value) if "." in value else int(value)
    return parsed


def _refs(reference: dict[str, str]) -> list[str]:
    return [ref for ref in reference.get("source_refs", "").split("|") if ref]


class MockLLMClient:
    model = MODEL

    def diagnose(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        reference = _parse_reference(user)
        numbers = _numbers(reference)
        source_refs = _refs(reference)
        if not source_refs:
            raise ValueError("mock client requires non-empty source_refs in the reference block")

        if numbers:
            described = ", ".join(f"{_format_number(v)} ({k})" for k, v in numbers.items())
            hypothesis = (
                f"Основная гипотеза: наблюдаемое отклонение объясняется входными данными; "
                f"ключевые числа входа {described} указывают на расхождение с ожидаемым уровнем."
            )
        else:
            hypothesis = (
                "Основная гипотеза: числовые признаки во входе отсутствуют, "
                "отклонение объясняется качественными данными сигнала."
            )

        first_ref = source_refs[0]
        second_ref = source_refs[1] if len(source_refs) > 1 else first_ref

        return {
            "schema_version": "diagnosis.draft.v1",
            "signal_id": reference["signal_id"],
            "scenario_id": reference["scenario_id"],
            "trust": reference.get("trust", "unreleased"),
            "primary_cause": {"hypothesis": hypothesis, "source_refs": [first_ref]},
            "alternatives": [
                {
                    "hypothesis": "Альтернативная гипотеза: часть отклонения может объясняться влиянием другого источника.",
                    "source_refs": [second_ref],
                },
                {
                    "hypothesis": "Альтернативная гипотеза: отклонение носит временный характер и связано с периодом наблюдения.",
                    "source_refs": [first_ref],
                },
            ],
            "unknowns": [
                {
                    "question": "Каких данных не хватает, чтобы подтвердить основную гипотезу?",
                    "why_it_matters": "Ответ уточнит диагноз и снизит долю предположений.",
                }
            ],
            "confidence_note": "Уверенность понижена: диагноз сформирован mock-провайдером для тестирования.",
            "model": MODEL,
            "prompt_version": reference.get("prompt_version", "v1"),
            "generated_at": reference.get("generated_at", ""),
        }
