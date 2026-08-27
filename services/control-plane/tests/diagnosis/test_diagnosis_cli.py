import json

from proxima_control_plane.diagnosis.cli import main

SIGNAL = {
    "signal_id": "SYNTH-SIG-001",
    "scenario_id": "SCN-001",
    "generated_at": "2026-08-27T00:00:00Z",
    "trust": "unreleased",
    "payload": {"sku_synth": "SYNTH-SKU-1", "units_drop_pct": 34.5},
    "context_extracts": [],
    "source_refs": ["SYNTH-SRC-A"],
}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def make_config(tmp_path):
    cfg = tmp_path / "cfg.toml"
    cfg.write_text(f'[diagnosis]\nprovider = "mock"\naudit_path = "{tmp_path}/audit.jsonl"\n', encoding="utf-8")
    return cfg


def test_cli_run_writes_parsable_artifact(tmp_path):
    signals = tmp_path / "signals.json"
    write_json(signals, [SIGNAL])
    output = tmp_path / "out" / "diagnoses.json"
    code = main(
        ["run", "--input", str(signals), "--output", str(output), "--config", str(make_config(tmp_path))]
    )
    assert code == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["generated_at"]
    assert len(artifact["items"]) == 1
    item = artifact["items"][0]
    assert item["signal_id"] == "SYNTH-SIG-001"
    assert item["status"] == "ok"
    assert item["diagnosis"]["signal_id"] == "SYNTH-SIG-001"
    assert item["diagnosis"]["trust"] == "unreleased"
    audit_lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(audit_lines) == 1


def test_cli_run_bad_envelope_isolated_not_fatal(tmp_path):
    signals = tmp_path / "signals.json"
    write_json(signals, [SIGNAL, {"signal_id": "SYNTH-BAD", "scenario_id": "SCN-999"}])
    output = tmp_path / "diagnoses.json"
    code = main(
        ["run", "--input", str(signals), "--output", str(output), "--config", str(make_config(tmp_path))]
    )
    assert code == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert [item["status"] for item in artifact["items"]] == ["ok", "failed"]
    assert artifact["items"][1]["signal_id"] == "SYNTH-BAD"
    assert artifact["items"][1]["error"]


def test_cli_run_missing_input_exit_2(tmp_path):
    code = main(
        [
            "run",
            "--input",
            str(tmp_path / "nope.json"),
            "--output",
            str(tmp_path / "o.json"),
            "--config",
            str(make_config(tmp_path)),
        ]
    )
    assert code == 2


def test_cli_run_malformed_json_exit_2(tmp_path):
    signals = tmp_path / "signals.json"
    signals.write_text("{not json", encoding="utf-8")
    code = main(
        ["run", "--input", str(signals), "--output", str(tmp_path / "o.json"), "--config", str(make_config(tmp_path))]
    )
    assert code == 2


def test_cli_run_wrong_top_level_exit_2(tmp_path):
    signals = tmp_path / "signals.json"
    write_json(signals, {"foo": 1})
    code = main(
        ["run", "--input", str(signals), "--output", str(tmp_path / "o.json"), "--config", str(make_config(tmp_path))]
    )
    assert code == 2


def test_cli_discovers_diagnosis_toml_in_cwd(tmp_path, monkeypatch):
    (tmp_path / "diagnosis.toml").write_text("[diagnosis]\nllm_enabled = false\n", encoding="utf-8")
    signals = tmp_path / "signals.json"
    write_json(signals, [SIGNAL])
    output = tmp_path / "diagnoses.json"
    monkeypatch.chdir(tmp_path)
    code = main(["run", "--input", str(signals), "--output", str(output)])
    assert code == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["items"][0]["status"] == "skipped_flag"


def test_cli_without_config_uses_defaults(tmp_path, monkeypatch):
    signals = tmp_path / "signals.json"
    write_json(signals, [SIGNAL])
    output = tmp_path / "diagnoses.json"
    monkeypatch.chdir(tmp_path)
    code = main(["run", "--input", str(signals), "--output", str(output)])
    assert code == 0
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["items"][0]["status"] == "ok"
