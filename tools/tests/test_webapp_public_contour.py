"""Offline gate for the public web contour of release 2.6 (D42, §3b).

Pins the three decisions that make the 29.09 deploy assemble-able:
- infra/webapp.compose.yaml serves the postgres mode through the secret-file
  form (the staging-overlay shape proven on the 08.09 rehearsal) and takes
  better-auth secrets from an env_file in the secrets dir, never from .env;
- infra/Caddyfile.rehearsal exists for the 27-28.09 first-login rehearsal
  (internal CA: Let's Encrypt needs public port 80);
- infra/vps-contract.json and tools/verify_vps_contract.py agree on the D42
  amendment: TCP/22 stays admin-only, TCP/80+443 belong to Caddy.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OVERLAY = ROOT / "infra" / "webapp.compose.yaml"
REHEARSAL_CADDYFILE = ROOT / "infra" / "Caddyfile.rehearsal"
CONTRACT = ROOT / "infra" / "vps-contract.json"
VERIFIER = ROOT / "tools" / "verify_vps_contract.py"


def overlay_text() -> str:
    return OVERLAY.read_text(encoding="utf-8")


def test_public_overlay_serves_postgres_mode_and_never_leaks_secrets_via_env() -> None:
    text = overlay_text()
    assert 'WEBAPP_REQUIRE_AUTH: "true"' in text
    assert "WEBAPP_DATA_MODE: ${WEBAPP_DATA_MODE:?set in .env on VPS}" in text
    assert "WEBAPP_TENANT_ID: ${WEBAPP_TENANT_ID:?set in .env on VPS}" in text
    assert "WEBAPP_DATA_DATABASE_URI_FILE: /run/secrets/proxima_webapp_uri" in text
    assert "BETTER_AUTH_URL: ${BETTER_AUTH_URL:?set in .env on VPS}" in text
    # The data URI comes from the secret file, never as a plain interpolated env.
    assert "WEBAPP_DATA_DATABASE_URI:" not in text
    # better-auth secrets live in the secrets-dir env_file (path interpolated:
    # battle default, rehearsal override via PROXIMA_WEBAPP_AUTH_ENV_FILE), not in .env.
    assert "env_file:" in text
    assert "${PROXIMA_WEBAPP_AUTH_ENV_FILE:-/etc/proxima-ai/secrets/webapp_auth.env}" in text
    assert "BETTER_AUTH_SECRET:" not in text
    assert "WEBAPP_AUTH_DATABASE_URI:" not in text
    assert "proxima_webapp_uri" in text


def test_public_overlay_keeps_caddy_fronting_the_webapp() -> None:
    text = overlay_text()
    assert "./Caddyfile:/etc/caddy/Caddyfile:ro" in text
    assert "reverse_proxy" not in text  # the proxy target lives in the Caddyfile
    assert '"80:80"' in text and '"443:443"' in text
    assert "WEBAPP_DOMAIN: ${WEBAPP_DOMAIN:?set in .env on VPS}" in text


def test_overlay_network_matches_the_base_compose_key() -> None:
    """Codex audit 22.09, P2: the overlay must attach to the base network key
    (`private`), not to a docker name - otherwise `docker compose config`
    fails with "undefined network" and the release path is dead."""
    text = overlay_text()
    assert "proxima-ai-private" not in text
    assert text.count("      - private") == 2  # webapp + caddy


def test_signup_is_fail_closed_and_the_bootstrap_flag_is_explicit() -> None:
    """Codex audit 22.09, P5: registration is disabled unless the operator
    exports WEBAPP_ALLOW_SIGNUP=1 for the first-user bootstrap."""
    overlay = overlay_text()
    assert "WEBAPP_ALLOW_SIGNUP: ${WEBAPP_ALLOW_SIGNUP:-0}" in overlay
    auth_ts = (ROOT / "services" / "webapp" / "src" / "lib" / "auth.ts").read_text(encoding="utf-8")
    assert "disableSignUp: process.env.WEBAPP_ALLOW_SIGNUP !== \"1\"" in auth_ts
    layout_ts = (ROOT / "services" / "webapp" / "src" / "app" / "(app)" / "layout.tsx").read_text(encoding="utf-8")
    assert "api.getSession" in layout_ts  # P3/P4: server-side validation, not cookie presence
    assert "cookieStore.has" not in layout_ts


def test_rehearsal_override_pins_loopback_ports_and_the_internal_ca() -> None:
    """Codex audit 22.09, P6: the rehearsal recipe references a real override
    file, not an ad-hoc edit."""
    override = (ROOT / "infra" / "webapp.rehearsal.compose.yaml").read_text(encoding="utf-8")
    assert "127.0.0.1:8080:80" in override and "127.0.0.1:8443:443" in override
    assert "./Caddyfile.rehearsal:/etc/caddy/Caddyfile:ro" in override
    assert 'WEBAPP_ALLOW_SIGNUP: "1"' in override


def test_compose_config_renders_with_stub_secrets(tmp_path: Path) -> None:
    """P2 reproduction, turned into a gate: the merged stack must render
    (`config`, no containers started) with a stub auth env-file."""
    import os
    import shutil
    import subprocess

    if shutil.which("docker") is None:
        import pytest

        pytest.skip("docker is not available on this host")
    env_file = tmp_path / "webapp_auth.env"
    env_file.write_text("BETTER_AUTH_SECRET=stub\nWEBAPP_AUTH_DATABASE_URI=postgresql://stub\n", encoding="utf-8")
    stubs = tmp_path / "secrets"
    stubs.mkdir()
    (stubs / "proxima_webapp_uri").write_text("postgresql://stub\n", encoding="utf-8")
    env = dict(
        os.environ,
        PROXIMA_RAW_DIR=str(tmp_path / "raw"),
        PROXIMA_SECRETS_DIR=str(stubs),
        PROXIMA_WEBAPP_AUTH_ENV_FILE=str(env_file),
        WEBAPP_DATA_MODE="postgres",
        WEBAPP_TENANT_ID="fixture-review",
        BETTER_AUTH_URL="https://example.invalid",
        WEBAPP_DOMAIN="example.invalid",
    )
    result = subprocess.run(
        [
            "docker", "compose",
            "-f", str(ROOT / "infra" / "compose.yaml"),
            "-f", str(OVERLAY),
            "config", "--quiet",
        ],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert result.returncode == 0, result.stderr


def test_rehearsal_caddyfile_uses_the_internal_ca() -> None:
    text = REHEARSAL_CADDYFILE.read_text(encoding="utf-8")
    assert "tls internal" in text
    assert "reverse_proxy webapp:3000" in text
    assert "{$WEBAPP_DOMAIN}" in text


def test_contract_carries_the_d42_amendment() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    security_group = contract["network"]["security_group"]
    assert security_group["inbound_allow"] == ["tcp/22", "tcp/80", "tcp/443"]
    assert security_group["application_public_ports"] == [80, 443]
    assert contract["network"]["application_access"] == "caddy_https"
    # The decision stays attributed and reviewable.
    assert contract["decision"]["source"].startswith("Mike")


def test_vps_contract_verifier_stays_in_sync_with_the_contract() -> None:
    spec = importlib.util.spec_from_file_location("verify_vps_contract_under_test", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify()  # raises ValueError on any drift between contract and gate
