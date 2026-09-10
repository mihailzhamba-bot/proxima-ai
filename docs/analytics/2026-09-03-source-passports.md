# PMM-58 — паспорта источников primary evidence

> **Статус:** `unreleased`  
> **Run:** `20260903T162418_b4b34738`  
> **Purpose:** `PMM-58 local data-quality export v1.3`  
> **Read-only:** `true`  
> **Run status:** `OK`  
> **Started:** `2026-09-03T16:24:18+03:00`  
> **Finished:** `2026-09-03T16:57:40+03:00`

## Как устроен паспорт

Боевые raw-файлы в репозиторий не переносятся. Для каждого локального raw artifact уже существует sidecar `.meta.json`, где сохранены `run_id`, endpoint, method, безопасные request params, `retrieved_at`, HTTP status, row count и SHA-256. Этот документ — обезличенная сводка для PR. Полный manifest и raw остаются локально под NDA.

## Statistics Orders

- Endpoint: `GET /api/v1/supplier/orders`
- Request semantics: `flag=1`, один запрос на один business-day
- Requested period: `2026-08-13` — `2026-09-02`
- Artifacts: `21`
- Rows: `894`
- `date`: `2026-08-13T00:08:39` — `2026-09-02T23:15:14`
- `lastChangeDate`: `2026-08-13T06:14:29` — `2026-09-03T14:40:15`
- HTTP: 200 for all 21 artifacts
- Per-artifact SHA-256: stored in local manifest / `.meta.json`

## Statistics Sales

- Endpoint: `GET /api/v1/supplier/sales`
- Request semantics: `flag=1`, один запрос на один business-day
- Requested period: `2026-08-13` — `2026-09-02`
- Artifacts: `21`
- Rows: `766`
- `date`: `2026-08-13T07:37:51` — `2026-09-02T20:38:03`
- `lastChangeDate`: `2026-08-13T07:51:48` — `2026-09-02T20:52:44`
- HTTP: 200 for all 21 artifacts
- Per-artifact SHA-256: stored in local manifest / `.meta.json`

## Analytics Funnel v3

- Endpoint: `POST /api/analytics/v3/sales-funnel/products/history`
- Requested period: `2026-08-27` — `2026-09-02`
- Requested product universe: `124 nmId`
- Artifacts: `7`
- Normalized evidence: 868 product-day rows
- HTTP: 200 for all artifacts
- Raw SHA-256: local manifest / `.meta.json`

## Analytics Stocks

### WB warehouses
- Endpoint: `POST /api/analytics/v1/stocks-report/wb-warehouses`
- Requested universe: `124 nmId`
- Artifact count: `1`
- Returned normalized rows: 375
- Returned nmId: 115 / 124
- Snapshot type: current state, not closed-day report

### Seller warehouses
- Endpoint: `POST /api/analytics/v1/stocks-report/seller-warehouses`
- Requested universe: `124 nmId`
- Artifact count: `1`
- Returned normalized rows: 395
- Returned nmId: 54 / 124
- WB ∪ Seller: 117 / 124; missing 7

Stock universe source for this run: `statistics.orders+sales_fallback`. Поэтому это не доказательство полного active catalog.

## Finance

### Detailed daily
- Endpoint: `/api/finance/v1/sales-reports/detailed`, `period=daily`
- Window: `2026-08-13` — `2026-09-02`
- Run rows: 5 620
- Closed-week reconciliation subset: 2 125 `rrdId`

### Detailed weekly
- Same detailed endpoint, `period=weekly`
- Candidate closed week: `2026-08-24` — `2026-08-30`
- Rows: 2 125

### Report list + exact report detail
- `/sales-reports/list`: 2 weekly reports
- `detailed/{reportId}`: 2 061 + 64 = 2 125 rows
- Reconciliation: daily closed week = weekly = exact detail = 2 125 by `rrdId`; business-field mismatches 0

## Paid Storage / Acceptance

### Paid Storage
- Window: 2026-08-24 — 2026-08-30
- Raw rows: 36 074
- Products: 161 nmId
- Sum: 1 434.846636 ₽
- Finance weekly storage: 1 434.80 ₽
- Delta: 0.046636 ₽

### Acceptance
- Window: 2026-08-24 — 2026-08-30
- Endpoint returned 0 business rows in the audited week
- Finance had 40 ₽ `paidAcceptance` as 4 FBS processing rows; separate Acceptance schema therefore remains not empirically validated for FBW in this run

## Promotion

- Status: `SKIPPED`
- Reason: optional Promotion token was not supplied to this run
- Consequence: promotion reconciliation and full catalog proof are outside PMM-58 evidence

## Reproducibility boundary

Primary numbers in `2026-09-03-data-quality.md` are reproducible from local run `20260903T162418_b4b34738`. Raw payloads, full fixtures and real IDs stay outside Git. Repository evidence contains only `unreleased` aggregate results, source contracts and sanitized passports.
