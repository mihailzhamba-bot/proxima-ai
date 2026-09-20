"""Гейт Story 4.2 `tools/verify_signals_ranking.py`: проходит на репозитории и падает при дрейфе."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIEF_CLI = ROOT / "services" / "control-plane" / "src" / "proxima_control_plane" / "brief" / "cli.py"


def load_gate():
    path = ROOT / "tools" / "verify_signals_ranking.py"
    spec = importlib.util.spec_from_file_location("verify_signals_ranking", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_signals_ranking"] = module
    spec.loader.exec_module(module)
    return module


def test_ranking_gate_passes_on_the_repository() -> None:
    gate = load_gate()
    assert gate.verify() == ["Платье", "2002", "2001", "2004", "2003", "Юбка"]


def test_ranking_gate_rejects_an_unwired_makefile(tmp_path: Path) -> None:
    gate = load_gate()
    unwired = tmp_path / "Makefile"
    unwired.write_text("verify: install test nm-daily detector\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="must follow `detector`"):
        gate.check_wiring(makefile=unwired)


def test_ranking_gate_rejects_a_brief_cli_that_does_not_read_the_threshold(tmp_path: Path) -> None:
    gate = load_gate()
    original = BRIEF_CLI.read_text(encoding="utf-8")
    drifted = tmp_path / "cli.py"
    drifted.write_text(original.replace("threshold = load_alert_threshold(args.threshold_config)", "threshold = NOT_APPLIED"), encoding="utf-8")
    with pytest.raises(AssertionError, match="exactly once"):
        gate.check_wiring(brief_cli=drifted)


def test_ranking_gate_rejects_a_brief_cli_that_builds_the_payload_without_the_threshold(tmp_path: Path) -> None:
    gate = load_gate()
    original = BRIEF_CLI.read_text(encoding="utf-8")
    drifted = tmp_path / "cli.py"
    drifted.write_text(original.replace("fact_run_ids, threshold=threshold)", "fact_run_ids)"), encoding="utf-8")
    with pytest.raises(AssertionError, match="assembler.build_day"):
        gate.check_wiring(brief_cli=drifted)


def test_ranking_gate_rejects_a_contract_without_a_required_threshold(tmp_path: Path) -> None:
    gate = load_gate()
    schema = json.loads((ROOT / "contracts" / "brief.schema.json").read_text(encoding="utf-8"))
    schema["required"].remove("threshold")
    drifted = tmp_path / "brief.schema.json"
    drifted.write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(AssertionError, match="required `threshold`"):
        gate.check_wiring(schema=drifted)


def test_ranking_gate_rejects_a_packaged_configuration_with_a_source_but_no_value(tmp_path: Path) -> None:
    gate = load_gate()
    config = tmp_path / "threshold.toml"
    config.write_text('[threshold]\nthreshold_source = "x"\nthreshold_date = 2026-09-02\n', encoding="utf-8")
    with pytest.raises(ValueError, match="together"):
        gate.check_wiring(config=config)
