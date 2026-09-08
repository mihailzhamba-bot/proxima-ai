"""Гейт Story 4.1 `tools/verify_detector.py`: проходит на репозитории и падает при дрейфе."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_gate():
    path = ROOT / "tools" / "verify_detector.py"
    spec = importlib.util.spec_from_file_location("verify_detector", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_detector"] = module
    spec.loader.exec_module(module)
    return module


def test_detector_gate_passes_on_the_repository() -> None:
    gate = load_gate()
    assert gate.verify() == {"sku_total": 5, "sku_insufficient": 2, "subject_total": 2, "subject_insufficient": 0, "signals": 3}


def test_detector_gate_rejects_an_unwired_makefile(tmp_path: Path) -> None:
    gate = load_gate()
    unwired = tmp_path / "Makefile"
    unwired.write_text("verify: install test nm-daily\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="must follow `nm-daily`"):
        gate.check_wiring(makefile=unwired)


def test_detector_gate_rejects_a_brief_cli_without_the_ok_guard(tmp_path: Path) -> None:
    gate = load_gate()
    original = (ROOT / "services" / "control-plane" / "src" / "proxima_control_plane" / "brief" / "cli.py").read_text(encoding="utf-8")
    drifted = tmp_path / "cli.py"
    drifted.write_text(original.replace('            if day.status == "ok":\n                # Детектор', '            if True:\n                # Детектор'), encoding="utf-8")
    with pytest.raises(AssertionError, match="must guard the detector"):
        gate.check_wiring(brief_cli=drifted)


def test_detector_gate_rejects_a_loader_that_reads_staging(tmp_path: Path) -> None:
    gate = load_gate()
    source = ROOT / "services" / "control-plane" / "src" / "proxima_control_plane" / "detector" / "loader.py"
    drifted = tmp_path / "loader.py"
    shutil.copyfile(source, drifted)
    drifted.write_text(drifted.read_text(encoding="utf-8") + "\nSTG = 'FROM stg_wb_orders_latest'\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="never reads stg_"):
        gate.check_wiring(loader=drifted)
