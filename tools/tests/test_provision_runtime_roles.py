"""Offline contract for infra/bootstrap/provision-runtime-roles.sh secret ownership.

The script is only executed for real against a PostgreSQL superuser (VPS or the
disposable harness cluster); these tests read its text and pin the ownership
rule that the rehearsal stand exposed on 08.09.2026 (D35 addendum, Mike): the
webapp image runs as uid 1001 (services/webapp/Dockerfile), the job images as
uid 1010, so proxima_webapp_{password,uri} must be chowned 1001:1001 while every
other runtime secret stays 1010:1010. The rule is tied to the Dockerfiles so a
uid change in an image fails here before it fails on the server.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "bootstrap" / "provision-runtime-roles.sh"
WEBAPP_DOCKERFILE = ROOT / "services" / "webapp" / "Dockerfile"
JOB_DOCKERFILES = (
    ROOT / "services" / "collector" / "Dockerfile",
    ROOT / "services" / "control-plane" / "Dockerfile",
)
STAGING_OVERLAY = ROOT / "infra" / "webapp.staging.compose.yaml"

JOB_ROLES = ("proxima_collector", "proxima_norm", "proxima_janitor", "proxima_sandbox")


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def chown_targets(text: str, owner_variable: str) -> str:
    """Return the argument text of every `chown "${<owner_variable>}" ...` call, joined."""
    pattern = rf'chown "\$\{{{owner_variable}\}}"((?:[^\n]*\\\n)*[^\n]*)'
    matches = re.findall(pattern, text)
    assert matches, f"no chown with ${{{owner_variable}}} in {SCRIPT}"
    return "\n".join(matches)


def test_script_parses() -> None:
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_image_uids_are_the_ones_the_script_assumes() -> None:
    webapp = WEBAPP_DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"useradd --system --uid 1001 ", webapp), "webapp image uid moved away from 1001"
    assert "USER webapp" in webapp
    for dockerfile in JOB_DOCKERFILES:
        assert "USER 1010" in dockerfile.read_text(encoding="utf-8"), dockerfile


def test_webapp_secrets_are_owned_by_the_webapp_uid() -> None:
    text = script_text()
    assert 'SECRETS_OWNER="1010:1010"' in text
    assert 'WEBAPP_SECRETS_OWNER="1001:1001"' in text
    webapp_targets = chown_targets(text, "WEBAPP_SECRETS_OWNER")
    assert "proxima_webapp_password" in webapp_targets
    assert "proxima_webapp_uri" in webapp_targets
    # Only the two webapp files move to 1001: no glob that could catch a job secret.
    assert "proxima_webapp_*" not in webapp_targets
    for role in JOB_ROLES:
        assert role not in webapp_targets, f"{role} must not be chowned to the webapp uid"


def test_job_secrets_keep_the_job_uid() -> None:
    text = script_text()
    job_targets = chown_targets(text, "SECRETS_OWNER")
    for role in JOB_ROLES:
        assert f"{role}_*" in job_targets, f"{role} secrets are no longer chowned 1010:1010"
    assert "proxima_webapp" not in job_targets, "webapp secrets must not be chowned back to 1010"
    # The secrets directory itself stays with the job uid (AD-11).
    assert re.search(r'chown "\$\{SECRETS_OWNER\}" "\$\{SECRETS_DIR\}"\n', text)


def test_ownership_is_reported_without_values_and_documented() -> None:
    text = script_text()
    assert "proxima_webapp_password, proxima_webapp_uri owned by ${WEBAPP_SECRETS_OWNER}" in text
    assert "services/webapp/Dockerfile" in text
    assert "D35 addendum" in text
    # The `--help` header (usage prints the comment block) carries the rule too.
    header = text.split("set -euo pipefail", 1)[0]
    assert "1001:1001" in header


def test_staging_overlay_binds_the_uri_file_as_is() -> None:
    """The overlay needs no change: compose bind-mounts the host file with its owner and mode."""
    overlay = STAGING_OVERLAY.read_text(encoding="utf-8")
    assert "WEBAPP_DATA_DATABASE_URI_FILE: /run/secrets/proxima_webapp_uri" in overlay
    assert re.search(r"(?m)^  proxima_webapp_uri:\n    file: \$\{PROXIMA_SECRETS_DIR:\?[^}]*\}/proxima_webapp_uri$", overlay)
    assert "user:" not in overlay, "the overlay must not override the image uid"
