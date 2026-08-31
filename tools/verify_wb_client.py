"""Contract gate for the single WB client (Story 1.1, AD-4).

Fail-closed checks:
- the endpoint registry holds exactly the four allowed endpoints with their
  per-minute budgets from docs/state/API-FACTS.md, entry by entry: any extra
  key, duplicated URL or per-entry budget drift fails the gate;
- WB hosts appear nowhere in `services/collector/src/**` outside
  `src/wb/registry.ts` — including `src/cli/**` and string concatenations
  (`.wildberries` substring). `src/business-signal/` is exempt: it is frozen
  read-only by AD-18 and carries its own verified endpoint list;
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
BUSINESS_SIGNAL_VERIFIER = ROOT / "tools" / "verify_business_signal.py"
# AD-18: frozen Story 1.0 module, verified by tools/verify_business_signal.py.
SCAN_EXEMPT_DIRS = ("business-signal",)

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
WB_HOST_SUBSTRING = ".wildberries"
TIMER_RE = re.compile(r"\bsetInterval\s*\(|\bnode-cron\b")
RETRY_RE = re.compile(r"x-ratelimit-retry", re.IGNORECASE)
TOKEN_FLAG_RE = re.compile(r"--(statistics|analytics|finance)-token-file")

# One registry entry: `  '<id>': { ... }` — spec objects contain no nested braces.
REGISTRY_ENTRY_RE = re.compile(
    r"^\s{2}'(?P<key>[^']+)':\s*\{(?P<body>[^{}]*)\}\s*,?\s*$",
    re.MULTILINE | re.DOTALL,
)
URL_FIELD_RE = re.compile(r"url:\s*'([^']+)'")
LIMIT_FIELD_RE = re.compile(r"limitPerMinute:\s*(\d+)")


def parse_registry_entries(source: str) -> dict[str, dict[str, str]]:
    """Parses every entry of the WB_ENDPOINTS object, keyed by its literal key."""
    entries: dict[str, dict[str, str]] = {}
    for match in REGISTRY_ENTRY_RE.finditer(source):
        key = match.group("key")
        body = match.group("body")
        url = URL_FIELD_RE.search(body)
        limit = LIMIT_FIELD_RE.search(body)
        if key in entries:
            entries[key]["_duplicated_key"] = "true"
            continue
        entries[key] = {
            "url": url.group(1) if url else "",
            "limit": limit.group(1) if limit else "",
        }
    return entries


def verify_registry(registry_path: Path = WB_DIR / "registry.ts") -> list[str]:
    errors: list[str] = []
    if not registry_path.is_file():
        return [f"missing endpoint registry: {registry_path}"]

    source = registry_path.read_text(encoding="utf-8")
    entries = parse_registry_entries(source)

    unexpected = sorted(set(entries) - set(EXPECTED_REGISTRY))
    if unexpected:
        errors.append(
            "registry holds endpoints outside the allowed four: " + ", ".join(unexpected)
        )
    missing = sorted(set(EXPECTED_REGISTRY) - set(entries))
    if missing:
        errors.append("registry is missing endpoints: " + ", ".join(missing))

    url_counts: dict[str, int] = {}
    for entry in entries.values():
        if entry["url"]:
            url_counts[entry["url"]] = url_counts.get(entry["url"], 0) + 1
    duplicated_urls = sorted(url for url, count in url_counts.items() if count > 1)
    if duplicated_urls:
        errors.append("registry URLs are not unique: " + ", ".join(duplicated_urls))

    for endpoint_id, (url, limit) in EXPECTED_REGISTRY.items():
        entry = entries.get(endpoint_id)
        if entry is None:
            continue
        if entry["url"] != url:
            errors.append(
                f"registry URL mismatch for {endpoint_id}: expected {url}, found {entry['url'] or '<missing>'}"
            )
        if entry["limit"] != str(limit):
            errors.append(
                f"registry budget mismatch for {endpoint_id}: expected {limit}/min, found {entry['limit'] or '<missing>'}"
            )

    # No WB host may hide anywhere else in the registry source (concatenations
    # included); literals are covered by the entry checks above.
    for match in WB_HOST_RE.finditer(source):
        url = match.group(0)
        if url not in {expected for expected, _ in EXPECTED_REGISTRY.values()}:
            errors.append(f"registry contains an unexpected WB URL: {url}")
    if source.count(WB_HOST_SUBSTRING) != sum(
        url.count(WB_HOST_SUBSTRING) for url, _ in EXPECTED_REGISTRY.values()
    ):
        errors.append(
            "registry contains WB host fragments beyond the four allowed endpoints"
        )
    for forbidden in FORBIDDEN_MARKERS:
        if forbidden in source:
            errors.append(f"forbidden endpoint in the registry: {forbidden}")
    return errors


def collector_sources(collector_src: Path = COLLECTOR_SRC) -> list[Path]:
    if not collector_src.is_dir():
        return []
    return [
        path
        for path in sorted(collector_src.rglob("*.ts"))
        if not any(part in SCAN_EXEMPT_DIRS for part in path.relative_to(collector_src).parts[:-1])
    ]


def verify_urls_only_in_registry(collector_src: Path = COLLECTOR_SRC) -> list[str]:
    errors: list[str] = []
    allowed_urls = {url for url, _ in EXPECTED_REGISTRY.values()}
    for path in collector_sources(collector_src):
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
        if WB_HOST_SUBSTRING in content:
            line = content[: content.index(WB_HOST_SUBSTRING)].count("\n") + 1
            errors.append(
                f"{path.relative_to(ROOT)}:{line}: WB host fragment outside the registry"
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
    if client and "fallbackRetryDelayMilliseconds" not in client:
        errors.append(
            "services/collector/src/wb/client.ts must fall back to a paced delay when 429 carries no retry header"
        )
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
    wb_collect = COLLECTOR_SRC / "cli" / "wb-collect.ts"
    if not wb_collect.is_file():
        errors.append("services/collector/src/cli/wb-collect.ts is missing (Story 1.1 CLI)")
    else:
        content = wb_collect.read_text(encoding="utf-8")
        for option in ("--endpoint", "--statistics-token-file", "--analytics-token-file"):
            if option not in content:
                errors.append(f"wb-collect.ts lost the {option} option")
        if "readPrivateSecret" not in content:
            errors.append("wb-collect.ts must read tokens through readPrivateSecret")
    wb_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(WB_DIR.glob("*.ts"))
    )
    if TOKEN_FLAG_RE.search(wb_sources) and "readPrivateSecret" not in wb_sources:
        errors.append("src/wb/ must not read token files itself; CLI owns --<category>-token-file")
    return errors


def verify(
    registry_path: Path = WB_DIR / "registry.ts",
    collector_src: Path = COLLECTOR_SRC,
) -> None:
    errors: list[str] = []
    errors += verify_wb_module_files()
    errors += verify_registry(registry_path)
    errors += verify_urls_only_in_registry(collector_src)
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
