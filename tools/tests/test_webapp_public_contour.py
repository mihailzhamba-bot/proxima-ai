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
    # better-auth secrets live in the secrets-dir env_file, not in .env interpolation.
    assert "- /etc/proxima-ai/secrets/webapp_auth.env" in text
    assert "BETTER_AUTH_SECRET:" not in text
    assert "WEBAPP_AUTH_DATABASE_URI:" not in text
    assert "proxima_webapp_uri" in text


def test_public_overlay_keeps_caddy_fronting_the_webapp() -> None:
    text = overlay_text()
    assert "./Caddyfile:/etc/caddy/Caddyfile:ro" in text
    assert "reverse_proxy" not in text  # the proxy target lives in the Caddyfile
    assert '"80:80"' in text and '"443:443"' in text
    assert "WEBAPP_DOMAIN: ${WEBAPP_DOMAIN:?set in .env on VPS}" in text


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
