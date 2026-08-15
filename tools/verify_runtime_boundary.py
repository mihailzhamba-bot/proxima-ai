from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "services" / "collector"
CONTROL_PLANE = ROOT / "services" / "control-plane"
BANNED_DEPENDENCIES = {"playwright", "playwright-core", "puppeteer", "puppeteer-core"}
BANNED_AGENT_DEPENDENCIES = {"@anthropic-ai/sdk", "openai"}
BANNED_AGENT_PACKAGES = {"anthropic", "openai"}
BANNED_RUNTIME_PATTERNS = {
    "torgstat": re.compile(r"torgstat", re.IGNORECASE),
    "browser session": re.compile(r"browsercontext|launchpersistentcontext|live[_-]?session", re.IGNORECASE),
    "browser runtime": re.compile(r"from\s+['\"](?:playwright|puppeteer)|require\(['\"](?:playwright|puppeteer)", re.IGNORECASE),
    "agent sdk (js)": re.compile(r"(?:from|import)\s+['\"](?:@anthropic-ai/sdk|openai)['\"]|require\(['\"](?:@anthropic-ai/sdk|openai)['\"]", re.IGNORECASE),
    "agent sdk (py)": re.compile(r"^\s*(?:from|import)\s+(?:anthropic|openai)\b", re.IGNORECASE | re.MULTILINE),
}


def forbidden_agent_dependencies(manifest: dict) -> list[str]:
    runtime = set(manifest.get("dependencies", {})) | set(manifest.get("optionalDependencies", {}))
    return sorted(runtime & BANNED_AGENT_DEPENDENCIES)


def forbidden_agent_packages(project: dict) -> list[str]:
    runtime = set(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        runtime.update(extra)
    names = {re.split(r"[=<>!~;\[]", dependency)[0].strip() for dependency in runtime}
    return sorted(names & BANNED_AGENT_PACKAGES)


def production_files() -> list[Path]:
    roots = [COLLECTOR / "src", CONTROL_PLANE / "src"]
    return sorted(
        path
        for source_root in roots
        for path in source_root.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".js", ".py"}
    )


def verify() -> None:
    manifest = json.loads((COLLECTOR / "package.json").read_text(encoding="utf-8"))
    runtime_dependencies = set(manifest.get("dependencies", {})) | set(manifest.get("optionalDependencies", {}))
    forbidden = sorted(runtime_dependencies & BANNED_DEPENDENCIES)
    if forbidden:
        raise ValueError(f"browser dependency in collector runtime: {', '.join(forbidden)}")
    agent_forbidden = forbidden_agent_dependencies(manifest)
    if agent_forbidden:
        raise ValueError(f"agent SDK dependency in collector runtime: {', '.join(agent_forbidden)}")

    root_manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    agent_forbidden = forbidden_agent_dependencies(root_manifest)
    if agent_forbidden:
        raise ValueError(f"agent SDK dependency in root runtime: {', '.join(agent_forbidden)}")

    pyproject = tomllib.loads((CONTROL_PLANE / "pyproject.toml").read_text(encoding="utf-8"))
    agent_forbidden = forbidden_agent_packages(pyproject.get("project", {}))
    if agent_forbidden:
        raise ValueError(f"agent SDK dependency in control-plane runtime: {', '.join(agent_forbidden)}")

    violations: list[str] = []
    for path in production_files():
        content = path.read_text(encoding="utf-8")
        for label, pattern in BANNED_RUNTIME_PATTERNS.items():
            if pattern.search(content):
                violations.append(f"{path.relative_to(ROOT)}: {label}")

    compose = (ROOT / "infra" / "compose.yaml").read_text(encoding="utf-8")
    if re.search(r"TORGSTAT|LIVE[_-]?SESSION", compose, re.IGNORECASE):
        violations.append("infra/compose.yaml: forbidden live adapter flag")
    if "0.0.0.0" in compose or "127.0.0.1:${PROXIMA_POSTGRES_PORT:-5432}:5432" not in compose:
        violations.append("infra/compose.yaml: PostgreSQL must bind only to configurable loopback")
    if "postgres:16" not in compose or "name: proxima-ai-private" not in compose:
        violations.append("infra/compose.yaml: PostgreSQL 16 isolated bridge boundary missing")

    exports = manifest.get("exports", {})
    if not isinstance(exports, dict) or "import" not in exports:
        violations.append("services/collector/package.json: built import export missing")
    else:
        target = COLLECTOR / str(exports["import"]).removeprefix("./")
        if not target.is_file():
            violations.append("services/collector/package.json: built import target missing")

    if violations:
        raise ValueError("runtime boundary violations:\n" + "\n".join(sorted(violations)))


if __name__ == "__main__":
    verify()
    print("runtime boundary verification passed")
