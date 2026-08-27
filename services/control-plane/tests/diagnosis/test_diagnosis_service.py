import hashlib
import json
import time
from dataclasses import asdict

from proxima_control_plane.diagnosis.adapters.mock import MockLLMClient
from proxima_control_plane.diagnosis.config import DiagnosisConfig
from proxima_control_plane.diagnosis.models import parse_signal
from proxima_control_plane.diagnosis.prompts.builder import PROMPT_VERSION
from proxima_control_plane.diagnosis.service import run_batch


def make_signal():
    return parse_signal(
        {
            "signal_id": "SYNTH-SIG-001",
            "scenario_id": "SCN-001",
            "generated_at": "2026-08-27T00:00:00Z",
            "trust": "unreleased",
            "payload": {"sku_synth": "SYNTH-SKU-1", "units_drop_pct": 34.5, "days_cover": 3},
            "context_extracts": [],
            "source_refs": ["SYNTH-SRC-A", "SYNTH-SRC-B"],
        }
    )


class BrokenClient:
    model = "broken-mock"

    def __init__(self):
        self.calls = 0

    def diagnose(self, system, user, schema):
        self.calls += 1
        raise ValueError("broken json from provider")


class SlowThenMockClient:
    model = "slow-mock"

    def __init__(self, seconds):
        self.seconds = seconds
        self.calls = 0
        self.mock = MockLLMClient()

    def diagnose(self, system, user, schema):
        self.calls += 1
        if self.calls == 1:
            time.sleep(self.seconds)
        return self.mock.diagnose(system, user, schema)


class FabricatedNumberClient:
    model = "fabricating-mock"

    def __init__(self):
        self.calls = 0

    def diagnose(self, system, user, schema):
        self.calls += 1
        return {
            "schema_version": "diagnosis.draft.v1",
            "signal_id": "SYNTH-SIG-001",
            "scenario_id": "SCN-001",
            "trust": "unreleased",
            "primary_cause": {
                "hypothesis": "Продажи упали на 77.7 процента по внешней причине.",
                "source_refs": ["SYNTH-SRC-A"],
            },
            "alternatives": [
                {"hypothesis": "Часть отклонения объясняется сезонностью.", "source_refs": ["SYNTH-SRC-B"]},
                {"hypothesis": "Отклонение носит временный характер.", "source_refs": ["SYNTH-SRC-A"]},
            ],
            "unknowns": [
                {"question": "Хватает ли данных за окно наблюдения?", "why_it_matters": "Уточнит диагноз."}
            ],
            "confidence_note": "Низкая уверенность.",
            "model": "fabricating-mock",
            "prompt_version": "v1",
            "generated_at": "2026-08-27T00:00:00Z",
        }


class ForeignRefClient:
    model = "foreign-mock"

    def __init__(self):
        self.calls = 0

    def diagnose(self, system, user, schema):
        self.calls += 1
        return {
            "schema_version": "diagnosis.draft.v1",
            "signal_id": "SYNTH-SIG-001",
            "scenario_id": "SCN-001",
            "trust": "unreleased",
            "primary_cause": {
                "hypothesis": "Отклонение связано с внешним источником.",
                "source_refs": ["SYNTH-SRC-FORBIDDEN"],
            },
            "alternatives": [
                {"hypothesis": "Часть отклонения объясняется сезонностью.", "source_refs": ["SYNTH-SRC-B"]},
                {"hypothesis": "Отклонение носит временный характер.", "source_refs": ["SYNTH-SRC-A"]},
            ],
            "unknowns": [
                {"question": "Хватает ли данных за окно наблюдения?", "why_it_matters": "Уточнит диагноз."}
            ],
            "confidence_note": "Низкая уверенность.",
            "model": "foreign-mock",
            "prompt_version": "v1",
            "generated_at": "2026-08-27T00:00:00Z",
        }


def test_flag_off_skips_llm_and_keeps_artifact_form(tmp_path):
    config = DiagnosisConfig(llm_enabled=False, audit_path=str(tmp_path / "audit.jsonl"))
    client = BrokenClient()
    result = run_batch([make_signal()], config, client=client)
    item = result.batch_to_dict()["items"][0]
    assert item["signal_id"] == "SYNTH-SIG-001"
    assert item["status"] == "skipped_flag"
    assert "diagnosis" not in item
    assert client.calls == 0


def test_ok_path_with_mock_client(tmp_path):
    config = DiagnosisConfig(audit_path=str(tmp_path / "audit.jsonl"))
    result = run_batch([make_signal()], config, client=MockLLMClient())
    item = result.items[0]
    assert item.status == "ok"
    assert item.diagnosis is not None
    assert item.diagnosis.signal_id == "SYNTH-SIG-001"
    assert item.diagnosis.trust == "unreleased"


def test_broken_json_fails_after_two_retries(tmp_path):
    config = DiagnosisConfig(audit_path=str(tmp_path / "audit.jsonl"))
    client = BrokenClient()
    result = run_batch([make_signal()], config, client=client)
    item = result.items[0]
    assert item.status == "failed"
    assert item.diagnosis is None
    assert item.error
    assert "broken json" in item.error
    assert client.calls == 3


def test_timeout_status_and_batch_continues(tmp_path):
    config = DiagnosisConfig(timeout_seconds=1, audit_path=str(tmp_path / "audit.jsonl"))
    result = run_batch([make_signal(), make_signal()], config, client=SlowThenMockClient(2.0))
    assert [item.status for item in result.items] == ["timeout", "ok"]
    assert result.items[0].diagnosis is None
    assert result.items[1].diagnosis is not None


def test_fabricated_number_fails_closed(tmp_path):
    config = DiagnosisConfig(audit_path=str(tmp_path / "audit.jsonl"))
    client = FabricatedNumberClient()
    result = run_batch([make_signal()], config, client=client)
    assert result.items[0].status == "failed"
    assert "77.7" in result.items[0].error
    assert client.calls == 3


def test_foreign_source_ref_fails_closed(tmp_path):
    config = DiagnosisConfig(audit_path=str(tmp_path / "audit.jsonl"))
    client = ForeignRefClient()
    result = run_batch([make_signal()], config, client=client)
    assert result.items[0].status == "failed"
    assert "SYNTH-SRC-FORBIDDEN" in result.items[0].error


def test_audit_fields_on_failed_signal(tmp_path):
    config = DiagnosisConfig(audit_path=str(tmp_path / "audit.jsonl"))
    signal = make_signal()
    run_batch([signal], config, client=BrokenClient())
    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    expected_sha = hashlib.sha256(
        json.dumps(asdict(signal), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert entry["input_sha256"] == expected_sha
    assert entry["signal_id"] == "SYNTH-SIG-001"
    assert entry["scenario_id"] == "SCN-001"
    assert entry["model"] == "broken-mock"
    assert entry["prompt_version"] == PROMPT_VERSION
    assert entry["outcome"] == "failed"
    assert entry["attempts"] == 3
    assert isinstance(entry["latency_ms"], int)
    assert entry["ts"]
