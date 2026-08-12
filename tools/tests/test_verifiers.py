from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_tool(name: str):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_checksum_rejects_changed_content() -> None:
    migrations = load_tool("verify_migrations")
    content = (ROOT / "db" / "migrations" / "001_bootstrap.sql").read_bytes()
    assert migrations.normalized_sha256(content) in content.decode()
    changed = content.replace(b"name text NOT NULL UNIQUE", b"name text UNIQUE")
    assert migrations.normalized_sha256(changed) not in changed.decode()


def test_source_path_rejects_parent_traversal() -> None:
    provenance = load_tool("verify_provenance")
    with pytest.raises(ValueError, match="unsafe source path"):
        provenance.safe_source_path("../dirty-secret")


def test_cross_language_contracts_accept_only_fail_closed_examples() -> None:
    contracts = load_tool("verify_contracts")
    contracts.verify()


def test_runtime_boundary_has_no_live_torgstat_path() -> None:
    boundary = load_tool("verify_runtime_boundary")
    boundary.verify()


def test_secret_scanner_patterns_are_live() -> None:
    scanner = load_tool("secret_scan")
    scanner.self_test()
