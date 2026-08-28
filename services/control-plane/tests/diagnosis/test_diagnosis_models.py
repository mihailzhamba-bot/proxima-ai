import pytest

from proxima_control_plane.diagnosis.models import (
    BatchItem,
    BatchResult,
    Diagnosis,
    parse_signal,
)


def make_raw() -> dict:
    return {
        "signal_id": "SYNTH-SIG-001",
        "scenario_id": "SCN-008",
        "generated_at": "2026-08-27T00:00:00Z",
        "trust": "unreleased",
        "payload": {"cycle": "W1", "coverage_pct": 62.5},
        "context_extracts": [{"note": "SYNTH extract"}],
        "source_refs": ["SYNTH-SRC-A", "SYNTH-SRC-B"],
    }


def make_diagnosis() -> Diagnosis:
    return Diagnosis(
        signal_id="SYNTH-SIG-001",
        scenario_id="SCN-008",
        trust="unreleased",
        primary_cause={"hypothesis": "Основная гипотеза.", "source_refs": ["SYNTH-SRC-A"]},
        alternatives=[
            {"hypothesis": "Альтернатива 1.", "source_refs": ["SYNTH-SRC-B"]},
            {"hypothesis": "Альтернатива 2.", "source_refs": ["SYNTH-SRC-A"]},
        ],
        unknowns=[{"question": "Данных мало?", "why_it_matters": "Влияет на вывод."}],
        confidence_note="Уверенность низкая.",
        model="mock-v1",
        prompt_version="v1",
        generated_at="2026-08-27T00:00:00Z",
    )


def test_parse_signal_valid() -> None:
    sig = parse_signal(make_raw())
    assert sig.signal_id == "SYNTH-SIG-001"
    assert sig.scenario_id == "SCN-008"
    assert sig.trust == "unreleased"
    assert sig.payload == {"cycle": "W1", "coverage_pct": 62.5}
    assert sig.source_refs == ["SYNTH-SRC-A", "SYNTH-SRC-B"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"signal_id": None},
        {"scenario_id": "SCN-999"},
        {"trust": "released"},
        {"payload": [1, 2]},
        {"source_refs": []},
        {"generated_at": None},
    ],
)
def test_parse_signal_broken_rejected(mutation: dict) -> None:
    raw = make_raw()
    for key, value in mutation.items():
        if value is None:
            del raw[key]
        else:
            raw[key] = value
    with pytest.raises(ValueError):
        parse_signal(raw)


def test_diagnosis_to_dict_shape() -> None:
    d = make_diagnosis()
    obj = d.diagnosis_to_dict()
    assert obj["schema_version"] == "diagnosis.draft.v1"
    assert obj["primary_cause"] == {"hypothesis": "Основная гипотеза.", "source_refs": ["SYNTH-SRC-A"]}
    assert len(obj["alternatives"]) == 2
    assert obj["unknowns"] == [{"question": "Данных мало?", "why_it_matters": "Влияет на вывод."}]
    assert obj["model"] == "mock-v1"
    assert obj["prompt_version"] == "v1"


def test_batch_to_dict_shape() -> None:
    d = make_diagnosis()
    result = BatchResult(
        generated_at="2026-08-27T01:00:00Z",
        items=[
            BatchItem(signal_id="SYNTH-SIG-001", status="ok", diagnosis=d),
            BatchItem(signal_id="SYNTH-SIG-002", status="failed", error="битый JSON"),
        ],
    )
    obj = result.batch_to_dict()
    assert obj["generated_at"] == "2026-08-27T01:00:00Z"
    assert obj["items"][0]["status"] == "ok"
    assert obj["items"][0]["diagnosis"]["schema_version"] == "diagnosis.draft.v1"
    assert obj["items"][1]["status"] == "failed"
    assert obj["items"][1]["error"] == "битый JSON"
