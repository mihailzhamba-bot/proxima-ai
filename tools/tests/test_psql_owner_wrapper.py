"""Offline contract for the production owner-psql wrapper (C6, D36)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "infra" / "bootstrap" / "proxima-psql-owner"


def wrapper_text() -> str:
    return WRAPPER.read_text(encoding="utf-8")


def test_wrapper_exists_is_executable_and_parses() -> None:
    assert WRAPPER.is_file()
    assert os.stat(WRAPPER).st_mode & 0o111 == 0o111
    result = subprocess.run(
        ["bash", "-n", str(WRAPPER)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_wrapper_uses_strict_mode_and_the_production_container() -> None:
    text = wrapper_text()
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text
    assert "docker exec -i proxima-ai-postgres-1" in text


def test_password_is_read_only_from_the_container_secret_file() -> None:
    text = wrapper_text()
    command = next(line for line in text.splitlines() if "PGPASSWORD=" in line)
    assert command.count("PGPASSWORD=") == 1
    assert 'PGPASSWORD="$(cat /run/secrets/postgres_password)"' in command
    assert "read " not in command
    assert "printf" not in command
    assert "echo" not in command
    assert not re.search(r"PGPASSWORD=(?!\"\$\(cat )[A-Za-z0-9]", command)


def test_sql_is_not_evaluated_or_converted_to_a_positional_command() -> None:
    """Arguments go unchanged to psql; SQL is accepted through stdin or psql -c."""
    text = wrapper_text()
    assert "eval" not in text
    assert 'exec psql "$@"' in text
    assert text.rstrip().endswith("sh \"$@\"")
    assert 'psql "$*"' not in text
