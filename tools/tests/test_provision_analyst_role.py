from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "bootstrap" / "provision-analyst-role.sh"


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_script_parses() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_role_is_login_read_only_and_bounded() -> None:
    text = script_text()
    for attribute in (
        "LOGIN", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE", "NOINHERIT",
        "NOREPLICATION", "NOBYPASSRLS",
    ):
        assert attribute in text
    assert "default_transaction_read_only = on" in text
    assert "statement_timeout = '30s'" in text
    assert "lock_timeout = '5s'" in text
    assert "idle_in_transaction_session_timeout = '60s'" in text


def test_grants_are_select_only_and_memberships_are_removed() -> None:
    text = script_text()
    assert "GRANT CONNECT ON DATABASE proxima TO proxima_analyst" in text
    assert "GRANT USAGE ON SCHEMA public TO proxima_analyst" in text
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA public TO proxima_analyst" in text
    assert "GRANT SELECT ON TABLES TO proxima_analyst" in text
    assert not re.search(r"GRANT\s+(?:INSERT|UPDATE|DELETE|ALL)\b", text)
    assert "pg_auth_members" in text
    assert "REVOKE %I FROM proxima_analyst" in text
    assert not re.search(r"GRANT\s+proxima_[a-z_]+\s+TO\s+proxima_analyst", text)


def test_secret_files_are_root_only_and_values_are_not_printed() -> None:
    text = script_text()
    assert text.count("--mode 0600 --owner root --group root") >= 1
    assert 'chmod 0600 "${PASSWORD_FILE}"' in text
    assert 'chmod 0600 "${URI_FILE}"' in text
    assert 'chown root:root "${PASSWORD_FILE}"' in text
    assert 'chown root:root "${URI_FILE}"' in text
    assert not re.search(r"(?:cat|echo|printf)[^\n]*(?:PASSWORD|password|URI_FILE).*value", text)
    assert "password file: ${PASSWORD_FILE}" in text
    assert "URI file: ${URI_FILE}" in text
