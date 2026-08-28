import pytest

from proxima_control_plane.diagnosis.validator import validate_diagnosis


def valid_diagnosis() -> dict:
    return {
        "schema_version": "diagnosis.draft.v1",
        "signal_id": "SYNTH-SIG-001",
        "scenario_id": "SCN-005",
        "trust": "unreleased",
        "primary_cause": {"hypothesis": "Остаток на SYNTH-WH-1 исчерпан.", "source_refs": ["SYNTH-SRC-A"]},
        "alternatives": [
            {"hypothesis": "Отгрузки задержаны.", "source_refs": ["SYNTH-SRC-B"]},
            {"hypothesis": "Спрос сместился.", "source_refs": ["SYNTH-SRC-A"]},
        ],
        "unknowns": [{"question": "Какова реальная дата OOS?", "why_it_matters": "Влияет на оценку потерь."}],
        "confidence_note": "Уверенность средняя.",
        "model": "mock-v1",
        "prompt_version": "v1",
        "generated_at": "2026-08-27T00:00:00Z",
    }


def test_valid_diagnosis_has_no_errors() -> None:
    assert validate_diagnosis(valid_diagnosis()) == []


def test_alternatives_one_is_rejected() -> None:
    obj = valid_diagnosis()
    obj["alternatives"] = obj["alternatives"][:1]
    errors = validate_diagnosis(obj)
    assert any("alternatives" in e for e in errors)


def test_alternatives_four_is_rejected() -> None:
    obj = valid_diagnosis()
    extra = {"hypothesis": "Ещё одна.", "source_refs": ["SYNTH-SRC-A"]}
    obj["alternatives"] = obj["alternatives"] + [extra, extra]
    errors = validate_diagnosis(obj)
    assert any("alternatives" in e for e in errors)


def test_unknowns_zero_is_rejected() -> None:
    obj = valid_diagnosis()
    obj["unknowns"] = []
    errors = validate_diagnosis(obj)
    assert any("unknowns" in e for e in errors)


def test_primary_cause_without_source_refs_is_rejected() -> None:
    obj = valid_diagnosis()
    obj["primary_cause"] = {"hypothesis": "Без ссылок."}
    errors = validate_diagnosis(obj)
    assert errors != []


def test_wrong_trust_is_rejected() -> None:
    obj = valid_diagnosis()
    obj["trust"] = "released"
    errors = validate_diagnosis(obj)
    assert any("trust" in e for e in errors)


def test_extra_field_is_rejected() -> None:
    obj = valid_diagnosis()
    obj["unexpected"] = 1
    errors = validate_diagnosis(obj)
    assert errors != []


def test_non_dict_returns_error() -> None:
    assert validate_diagnosis([1, 2]) != []


@pytest.mark.parametrize(
    "field",
    ["schema_version", "signal_id", "scenario_id", "confidence_note", "model", "prompt_version", "generated_at"],
)
def test_missing_required_top_level_field_is_rejected(field: str) -> None:
    obj = valid_diagnosis()
    del obj[field]
    errors = validate_diagnosis(obj)
    assert any(field in e for e in errors)
