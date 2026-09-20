"""Offline contract between the collector image and its shell runners."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "services" / "collector" / "Dockerfile"
PACKAGE = ROOT / "services" / "collector" / "package.json"
COMPOSE = ROOT / "infra" / "compose.yaml"


def collector_service() -> str:
    compose = COMPOSE.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^  collector:\n(?P<body>.*?)(?=^  [a-zA-Z][a-zA-Z0-9_-]*:\n)", compose)
    assert match is not None
    return match.group("body")


def test_collector_image_requires_explicit_npm_script_command() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    directives = [line.strip() for line in dockerfile.splitlines() if not line.lstrip().startswith("#")]
    assert not any(re.match(r"^(ENTRYPOINT|CMD)\b", line) for line in directives)
    assert not re.search(r"(?m)^    (entrypoint|command):", collector_service())


def test_all_collector_runners_use_declared_npm_scripts() -> None:
    scripts = json.loads(PACKAGE.read_text(encoding="utf-8"))["scripts"]
    expected = {
        "tools/morning_run.sh": "collect",
        "tools/funnel_v3_run.sh": "funnel-v3",
        "tools/funnel_csv_run.sh": "funnel-csv-promote",
    }
    for relative, job in expected.items():
        runner = (ROOT / relative).read_text(encoding="utf-8")
        assert job in scripts, f"{job} is not declared in collector package.json"
        command = rf"docker compose --profile jobs run --rm(?:\s+\\?\s+--[^\n]+)*\s+collector(?:\s+\\?\s*)+npm run {re.escape(job)} --"
        assert re.search(command, runner), f"{relative} does not invoke collector via npm run {job} --"
