from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "services" / "collector"
CONTROL_PLANE = ROOT / "services" / "control-plane"
GENERATED_CONTRACTS = COLLECTOR / "src" / "contracts"
GENERATED_BANNER = "AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT."
BANNED_DEPENDENCIES = {"playwright", "playwright-core", "puppeteer", "puppeteer-core"}
BANNED_RUNTIME_PATTERNS = {
    "torgstat": re.compile(r"torgstat", re.IGNORECASE),
    "browser session": re.compile(r"browsercontext|launchpersistentcontext|live[_-]?session", re.IGNORECASE),
    "browser runtime": re.compile(r"from\s+['\"](?:playwright|puppeteer)|require\(['\"](?:playwright|puppeteer)", re.IGNORECASE),
}


def production_files() -> list[Path]:
    roots = [COLLECTOR / "src", CONTROL_PLANE / "src"]
    return sorted(
        path
        for source_root in roots
        for path in source_root.rglob("*")
        if path.is_file()
        and path.suffix in {".ts", ".js", ".py"}
        and GENERATOR_EXEMPT.match(str(path)) is None
    )


GENERATOR_EXEMPT = re.compile(rf"^{re.escape(str(GENERATED_CONTRACTS))}/[^/]+$")


def verify() -> None:
    manifest = json.loads((COLLECTOR / "package.json").read_text(encoding="utf-8"))
    runtime_dependencies = set(manifest.get("dependencies", {})) | set(manifest.get("optionalDependencies", {}))
    forbidden = sorted(runtime_dependencies & BANNED_DEPENDENCIES)
    if forbidden:
        raise ValueError(f"browser dependency in collector runtime: {', '.join(forbidden)}")

    violations: list[str] = []

    generated_files = sorted(
        path for path in GENERATED_CONTRACTS.glob("*") if path.is_file() and path.suffix == ".ts"
    )
    if not generated_files:
        violations.append("services/collector/src/contracts: generated contract types missing (run `make codegen`)")
    for path in generated_files:
        if GENERATED_BANNER not in path.read_text(encoding="utf-8").splitlines()[1]:
            violations.append(
                f"{path.relative_to(ROOT)}: generated contract file missing AUTO-GENERATED banner"
            )

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

    glitchtip_path = ROOT / "infra" / "glitchtip.compose.yaml"
    if not glitchtip_path.is_file():
        violations.append("infra/glitchtip.compose.yaml: error collector compose missing (PA-56)")
    else:
        glitchtip = glitchtip_path.read_text(encoding="utf-8")
        if re.search(r"TORGSTAT|LIVE[_-]?SESSION", glitchtip, re.IGNORECASE):
            violations.append("infra/glitchtip.compose.yaml: forbidden live adapter flag")
        if "0.0.0.0" in glitchtip:
            violations.append("infra/glitchtip.compose.yaml: must not bind 0.0.0.0")
        if '"127.0.0.1:${GLITCHTIP_PORT:-8080}:8080"' not in glitchtip:
            violations.append("infra/glitchtip.compose.yaml: GlitchTip web must bind configurable loopback only")
        if "name: proxima-ai-glitchtip" not in glitchtip:
            violations.append("infra/glitchtip.compose.yaml: isolated bridge network missing")
        if "qcluster" in glitchtip:
            violations.append("infra/glitchtip.compose.yaml: removed qcluster worker command (v6 uses run-worker.sh)")
        if "POSTGRES_PASSWORD: ${GLITCHTIP_POSTGRES_PASSWORD" not in glitchtip:
            violations.append("infra/glitchtip.compose.yaml: postgres password must come from environment")
        if "GLITCHTIP_SECRET_KEY" not in glitchtip:
            violations.append("infra/glitchtip.compose.yaml: SECRET_KEY must come from environment")

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
