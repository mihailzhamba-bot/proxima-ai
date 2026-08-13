from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def verify() -> None:
    errors: list[str] = []
    source_root = ROOT / "services" / "collector" / "src" / "business-signal"
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(source_root.glob("*.ts")))
    cli = (ROOT / "services" / "collector" / "src" / "cli" / "stockout-signal.ts").read_text(encoding="utf-8")
    migration = (ROOT / "db" / "migrations" / "004_business_signal_slice.sql").read_text(encoding="utf-8")
    runtime = (ROOT / "infra" / "bootstrap" / "prepare-business-signal-runtime.sh").read_text(encoding="utf-8")

    required_endpoints = (
        "https://statistics-api.wildberries.ru/api/v1/supplier/sales",
        "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses",
        "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed",
    )
    for endpoint in required_endpoints:
        if endpoint not in source:
            errors.append(f"missing official READ endpoint: {endpoint}")
    for forbidden in ("/api/v1/supplier/stocks", "/api/v5/supplier/reportDetailByPeriod"):
        if forbidden in source:
            errors.append(f"deprecated endpoint entered signal runtime: {forbidden}")
    for option in ("statistics-token-file", "analytics-token-file", "finance-token-file"):
        if option not in cli:
            errors.append(f"missing separate token file option: {option}")
    if "--send" not in cli or "setInterval" in source or "node-cron" in source:
        errors.append("business signal must remain a manual one-shot")
    if source.count("transport.call('sendMessage'") != 1:
        errors.append("Telegram surface must contain exactly one send call site")
    for table in ("dim_product", "dim_warehouse_map", "business_signal_runs", "business_signal_raw_artifacts"):
        if f"CREATE TABLE {table}" not in migration:
            errors.append(f"migration missing table: {table}")
    for required in ('NODE_MAJOR="22"', "node_${NODE_MAJOR}.x", "npm --prefix", "run build"):
        if required not in runtime:
            errors.append(f"business signal runtime bootstrap missing: {required}")
    for forbidden in ("FOUNDER_CHAT_ID =", "founderChatId: 1", "founderChatId: -1"):
        if forbidden in source:
            errors.append("founder chat value or placeholder must not be committed in source")

    if errors:
        raise ValueError("business signal contract violations:\n" + "\n".join(sorted(errors)))


if __name__ == "__main__":
    verify()
    print("business signal contract verification passed")
