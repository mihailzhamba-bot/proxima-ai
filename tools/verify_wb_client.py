"""Contract gate for the single WB client (Story 1.1, AD-4).

Fail-closed checks:
- WB URLs live only in the endpoint registry (`src/wb/registry.ts`);
- the registry contains exactly the four allowed endpoints with their
  per-minute budgets taken from docs/state/API-FACTS.md;
- removed/deprecated endpoints (`reportDetailByPeriod`, `supplier/stocks`,
  `nm-report/detail*`, `supplier/incomes`) appear nowhere in `src/wb/`;
- `tools/record_fixture.ts` exists and only anonymizes through
  `tools/anonymize_fixture.py`;
- no `setInterval`/`node-cron` anywhere in collector/control-plane `src/**`;
- `tools/verify_business_signal.py` still contains its required checks
  (this story must not edit it).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_SRC = ROOT / "services" / "collector" / "src"
WB_DIR = COLLECTOR_SRC / "wb"
JOBS_DIR = COLLECTOR_SRC / "jobs"
BUSINESS_SIGNAL_VERIFIER = ROOT / "tools" / "verify_business_signal.py"

EXPECTED_REGISTRY: dict[str, tuple[str, int]] = {
    "statistics.orders": (
        "https://statistics-api.wildberries.ru/api/v1/supplier/orders",
        10,
    ),
    "statistics.sales": (
        "https://statistics-api.wildberries.ru/api/v1/supplier/sales",
        1,
    ),
    "analytics.sales_funnel_v3_history": (
        "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history",
        3,
    ),
    "analytics.nm_report_downloads": (
        "https://seller-analytics-api.wildberries.ru/api/v2/nm-report/downloads",
        3,
    ),
}

FORBIDDEN_MARKERS = (
    "/api/v5/supplier/reportDetailByPeriod",
    "/api/v1/supplier/stocks",
    "/api/v1/supplier/incomes",
    "/api/v2/nm-report/detail",
    "/api/v2/nm-report/detail/history",
)

WB_HOST_RE = re.compile(r"https?://[A-Za-z0-9.-]*wildberries\.ru[^'\"\s]*")
URL_TEMPLATE_RE = re.compile(r"https://[A-Za-z0-9.-]+\.wildberries\.ru")
TIMER_RE = re.compile(r"\bsetInterval\s*\(|\bnode-cron\b")
RETRY_RE = re.compile(r"x-ratelimit-retry", re.IGNORECASE)
TOKEN_FLAG_RE = re.compile(r"--(statistics|analytics|finance)-token-file")


def registry_source() -> str:
    return (WB_DIR / "registry.ts").read_text(encoding="utf-8")


def verify_registry() -> list[str]:
    errors: list[str] = []
    path = WB_DIR / "registry.ts"
    if not path.is_file():
        return [f"missing endpoint registry: {path.relative_to(ROOT)}"]

    source = registry_source()
    found: dict[str, tuple[str, int]] = {}
    for endpoint_id, (url, limit) in EXPECTED_REGISTRY.items():
        if url not in source:
            errors.append(f"registry missing endpoint URL: {endpoint_id} -> {url}")
            continue
        block = source.split(url, 1)[1]
        match = re.search(r"limitPerMinute:\s*(\d+)", block)
        if match is None:
            errors.append(f"registry endpoint {endpoint_id} has no limitPerMinute next to its URL")
            continue
        found[endpoint_id] = (url, int(match.group(1)))
        if int(match.group(1)) != limit:
            errors.append(
                f"registry budget mismatch for {endpoint_id}: "
                f"expected {limit}/min, found {match.group(1)}"
            )

    extra = set(found) - set(EXPECTED_REGISTRY)
    if extra:
        errors.append(f"registry holds unexpected endpoints: {', '.join(sorted(extra))}")
    urls_in_registry = set(WB_HOST_RE.findall(source))
    expected_urls = {url for url, _ in EXPECTED_REGISTRY.values()}
    if urls_in_registry != expected_urls:
        errors.append(
            "registry URL set differs from the allowed four: "
            f"unexpected={sorted(urls_in_registry - expected_urls)} "
            f"missing={sorted(expected_urls - urls_in_registry)}"
        )
    return errors


def verify_urls_only_in_registry() -> list[str]:
    errors: list[str] = []
    allowed_urls = {url for url, _ in EXPECTED_REGISTRY.values()}
    roots = [WB_DIR]
    if JOBS_DIR.is_dir():
        roots.append(JOBS_DIR)
    for root in roots:
        for path in sorted(root.rglob("*.ts")):
            if path.name == "registry.ts":
                continue
            content = path.read_text(encoding="utf-8")
            for marker in FORBIDDEN_MARKERS:
                if marker in content:
                    errors.append(
                        f"{path.relative_to(ROOT)}: forbidden endpoint {marker} outside the registry"
                    )
            for url in sorted(set(WB_HOST_RE.findall(content))):
                if url not in allowed_urls:
                    errors.append(
                        f"{path.relative_to(ROOT)}: WB URL literal outside the registry: {url}"
                    )
    return errors


def verify_business_signal_untouched() -> str | None:
    if not BUSINESS_SIGNAL_VERIFIER.is_file():
        return "tools/verify_business_signal.py is missing"
    content = BUSINESS_SIGNAL_VERIFIER.read_text(encoding="utf-8")
    required = (
        'ROOT / "services" / "collector" / "src" / "business-signal"',
        "required_endpoints = (",
        "/api/v1/supplier/stocks",
        "/api/v5/supplier/reportDetailByPeriod",
        "statistics-token-file",
        "analytics-token-file",
        "finance-token-file",
        "must remain a manual one-shot",
    )
    for marker in required:
        if marker not in content:
            return (
                "tools/verify_business_signal.py was modified and lost a required check: "
                f"{marker!r}"
            )
    return None


def verify_no_timers() -> list[str]:
    errors: list[str] = []
    for root in (COLLECTOR_SRC, ROOT / "services" / "control-plane" / "src"):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in {".ts", ".js", ".py"}:
                continue
            content = path.read_text(encoding="utf-8")
            for match in TIMER_RE.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                errors.append(
                    f"{path.relative_to(ROOT)}:{line}: in-process timer forbidden (AD-6): {match.group(0)!r}"
                )
    return errors


def verify_wb_module_files() -> list[str]:
    errors: list[str] = []
    required = ["client.ts", "transport.ts", "fixture-transport.ts", "artifact-sink.ts", "msk-day.ts", "registry.ts"]
    for name in required:
        path = WB_DIR / name
        if not path.is_file():
            errors.append(f"missing required WB client file: services/collector/src/wb/{name}")
            continue
        content = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_MARKERS:
            if marker in content and name != "registry.ts":
                errors.append(f"services/collector/src/wb/{name}: forbidden endpoint {marker}")
    client = (WB_DIR / "client.ts").read_text(encoding="utf-8") if (WB_DIR / "client.ts").is_file() else ""
    if "MAX_RETRIES_AFTER_RATE_LIMIT = 3" not in client:
        errors.append("services/collector/src/wb/client.ts must cap 429 retries at 3")
    if client and not RETRY_RE.search(client):
        errors.append("services/collector/src/wb/client.ts must wait on X-Ratelimit-Retry")
    msk_day = (WB_DIR / "msk-day.ts").read_text(encoding="utf-8") if (WB_DIR / "msk-day.ts").is_file() else ""
    if msk_day and "Europe/Moscow" not in msk_day:
        errors.append("services/collector/src/wb/msk-day.ts must resolve Europe/Moscow explicitly")
    return errors


def verify_record_fixture_tool() -> list[str]:
    errors: list[str] = []
    path = ROOT / "tools" / "record_fixture.ts"
    if not path.is_file():
        return [f"missing tools/record_fixture.ts ({path})"]
    content = path.read_text(encoding="utf-8")
    if "anonymize_fixture.py" not in content:
        errors.append("tools/record_fixture.ts must delegate to tools/anonymize_fixture.py")
    if "wb-api" not in content:
        errors.append("tools/record_fixture.ts must write into tests/fixtures/wb-api/")
    for endpoint in EXPECTED_REGISTRY:
        if endpoint not in content and "WB_ENDPOINTS" not in content:
            errors.append("tools/record_fixture.ts must derive endpoints from the registry")
            break
    return errors


def verify_token_flags_pattern() -> list[str]:
    errors: list[str] = []
    cli_path = COLLECTOR_SRC / "cli" / "stockout-signal.ts"
    if cli_path.is_file():
        content = cli_path.read_text(encoding="utf-8")
        for option in ("statistics-token-file", "analytics-token-file", "finance-token-file"):
            if option not in content:
                errors.append(f"stockout-signal.ts lost the --{option} option")
    wb_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WB_DIR.glob("*.ts"))
    )
    if TOKEN_FLAG_RE.search(wb_sources) and "readPrivateSecret" not in wb_sources:
        errors.append("src/wb/ must not read token files itself; CLI owns --<category>-token-file")
    return errors


def verify() -> None:
    errors: list[str] = []
    errors += verify_wb_module_files()
    errors += verify_registry()
    errors += verify_urls_only_in_registry()
    errors += verify_no_timers()
    errors += verify_record_fixture_tool()
    errors += verify_token_flags_pattern()

    business_signal = verify_business_signal_untouched()
    if business_signal:
        errors.append(business_signal)

    if errors:
        raise ValueError("WB client contract violations:\n" + "\n".join(sorted(set(errors))))


if __name__ == "__main__":
    verify()
    print("wb client contract verification passed")
