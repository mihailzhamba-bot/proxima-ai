# Phase 2 Evidence - Immutable Intake to Visible Facts

## Plan 02-01 - Immutable official WB XLSX intake foundation

- **Implementation commit:** `56ebe00096150cda667507e03be8340ca50e301c` (`feat: add immutable official WB XLSX intake`).
- **Root verification:** `make verify` PASS on that exact commit, 2026-08-12. It ran clean `npm ci`, 14 TypeScript tests, 9 Python tests, contract and migration checks, provenance verification, Mermaid rendering, runtime boundary verification and secret scan.
- **Hosted CI:** GitHub Actions [`verify` run 31594703739](https://github.com/mihailzhamba-bot/proxima-ai/actions/runs/31594703739) PASS on exact SHA `56ebe00096150cda667507e03be8340ca50e301c`, completed 2026-08-12 12:05 UTC.
- **Operator smoke test:** compiled CLI accepted only a synthetic ZIP-signature `.xlsx` fixture in a temporary private store outside the repository and returned an artifact ID, SHA-256 locator and `created` state. No pilot bytes or business values were used.
- **Self-review:** PASS. The test suite proves byte-for-byte content storage, contract-valid canonical manifest, private permissions, Git-external root, same-input idempotence, metadata conflict rejection, invalid metadata rejection before raw write, missing raw object fail-closed behaviour, symlink rejection and four forced-crash recovery points.
- **Source worktree preservation:** after implementation, `torgstat-collector` status fingerprint remained `0e77e03f38430d8c1021b134494862a2825c10006be41183e632adb978fad29f`; `proxima-ai-manager` remained `e02a035d7885b7a9ead9e9eb8b13f4f2da202a3e3e57b52ad83a8eea8ae70fc3`.
- **Independent review status:** two read-only reviewer invocations were attempted on 2026-08-12 and did not return because their selected model stalled at capacity. No independent `0 blocker / 0 warning` verdict is claimed. Under the M1 execution contract, Phase 2 requires root verification, CI evidence and self-review; independent review is mandatory for Phases 3, 4 and 7.

## Plan 02-02 - Observed XLSX parser, staging and localhost preview

**Checkpoint resolution and pivot (2026-08-15, Mike GO, PA-9).** Two official
WB XLSX exports supplied by Mike from the Amirova pilot cabinet were inspected
locally before any parser code was written. Only structure is recorded here;
no workbook bytes, cell values, customer payloads or tokens are committed.

- Observed export 1: sales funnel workbook `1 с 14.07.2026 по 14.08.2026.zip`
  (outer ZIP 109,646 bytes, SHA-256 `f89da726fdb76306c03fb142c51d90271ba888673c661ff18e1dc05e340e35cc`;
  inner XLSX 133,570 bytes, SHA-256 `bd8763359d639d4ba854e47d1ebcd72e90a9fce2b3f35e46f92a86548c80596c`).
  Sheets: Общая информация, Метрики, Фильтры, Товары (348 product rows), Промосервисы.
  Headers on «Товары»: Артикул продавца, Артикул WB, Название, Предмет, Бренд, Удаленный товар,
  Рейтинг карточки, Рейтинг по отзывам, Показы (+ previous period), CTR (+ previous period),
  Доля карточки в выручке, Переходы в карточку, Положили в корзину, Добавили в отложенные,
  Заказали товаров шт, Выкупили шт, Отменили шт, Конверсии. No calendar-day column anywhere.
- Observed export 2: supplier report
  `supplier-goods-45871-2026-07-14-2026-08-14-iiyngpinc.XLSX` (58,159 bytes, SHA-256
  `e682e80397ad0f169fa8aedda23f053173a30d74c3dfae722cf6b4fbe5786004`, one sheet, 617 data rows).
  Headers: Бренд, Предмет, Сезон, Коллекция, Наименование, Артикул продавца, Артикул WB, Баркод,
  Размер, Контракт, Склад, Заказано шт., Сумма заказов минус комиссия WB руб., Выкупили шт.,
  К перечислению за товар руб., Текущий остаток шт. No calendar-day column.
- Conclusion: the pilot cabinet's manual XLSX exports are period aggregates;
  the daily `order_count` grain lives in the official WB Analytics
  DETAIL_HISTORY_REPORT (already collected via API into
  `stg_wb_nm_report_rows`). Mike approved building the preview from the API
  staging leg and deferring XLSX reconciliation to a separate plan. The two
  observed workbooks stay recorded as candidate period-grain reconciliation
  sources for that future plan.

**Implementation (2026-08-16).** Migration `007_preview_order_counts.sql`
(ordered, transaction-bounded, self-checksum) adds `artifact_parse_runs`
(unique per task+profile, FK to `wb_analytics_report_tasks`), typed
`preview_quarantine_rows` (NM_ID_INVALID / ROW_DATE_INVALID /
ORDER_COUNT_INVALID) and `preview_order_counts` (PK
tenant/task/calendar_day/nm_id, `release_status` fixed to `unreleased`).
TypeScript transform `services/collector/src/staging/preview-transform.ts` +
CLI `preview-transform` runs one PostgreSQL transaction: lock task, verify
DOWNLOADED status and artifact SHA-256, classify staging rows into
valid/quarantine, aggregate `order_count` per calendar day and nmId, insert
run + quarantine + preview facts, mark success, commit. The localhost preview
(`services/control-plane/src/proxima_control_plane/preview.py`) is a FastAPI
read-only route bound to loopback with a host guard, an `UNRELEASED PREVIEW`
banner, lineage to run/task/artifact SHA-256, 405 on all mutations and no
docs/openapi surface.

**Verification (2026-08-16).** Root `make verify` PASS: 60 TypeScript tests,
55 Python tests (2 environment-gated skips), migration, contract, provenance,
architecture, runtime-boundary, secret-scan, VPS-contract and business-signal
checks. A dedicated PostgreSQL 16.14 integration suite
(`preview-transform-postgres.test.ts`, enabled via
`PROXIMA_TEST_POSTGRES_DSN`) proves: one complete preview set per task,
idempotent retry (`existing`, no duplicate rows), typed rejections for
non-DOWNLOADED tasks, tenant mismatch and staged-count drift, and full
rollback with a clean single-set retry after injected crashes at all four
write boundaries (run created, quarantine written, preview written, success
marker). Route/bind tests plus a browserless HTTP smoke against a real
uvicorn loopback server confirm the unreleased banner, day tables, 405 on
POST/PUT/PATCH/DELETE and 404 outside the single route.

**End-to-end local smoke (2026-08-16).** Disposable local PostgreSQL 16.14
applied migrations 001-007; a synthetic five-row task for tenant
`amirova-test` (3 valid rows incl. two same-day rows for one nmId, 2
quarantined) was transformed by the compiled CLI (`created` then `existing`
with identical run id, exactly one run/quarantine/preview set), and the
compiled preview server on `127.0.0.1:8788` rendered the daily `order_count`
page with lineage to the synthetic artifact checksum. No customer values,
tokens or pilot bytes were used.

**Live collection leg deferred.** The planned real-cabinet collect via
`make collect-wb-analytics` requires the Analytics token stored on the VPS;
SSH to `135.106.186.210:22` timed out from the operator network
(2026-08-15/16). No token was fetched and no external WB endpoint was
touched. The live run (collect -> transform -> preview on real pilot data)
remains the only open PA-9 item and must be executed once VPS access or a
READ-only Analytics token is available; identity/rollback guarantees are
already proven by the integration suite.

## Plan 02-01A - Margin and out-of-stock Telegram proof

- **Implementation commits:** `76d39a2` (schema/private config), `0d5b950` (collector/calculation/Telegram), `20ea8cf` (Node 22 VPS contract/runbook), `fe0bc5d` (WB page pacing/full token scope validation), `255e6c0` (Finance line-amount commission fix), `deeefcb` (skip unused Puppeteer download on VPS), `ab8f451` (private input bundle validation/installation), `6e0a605` (founder chat discovery), `fcb3841` (explicit temporary Analytics RW opt-in), `5393bcb` (empty Finance document labels) and `2d0f6ec` (skip unattributable Finance rows while preserving pagination).
- **Root verification:** `make verify` PASS on current and deployed implementation HEAD `2d0f6ec`, repeated 2026-08-14. Evidence: 37 TypeScript tests, 35 Python tests, 1 existing Docker-dependent test skipped, contracts, 4 ordered migration checks, provenance, 4 Mermaid renders, runtime boundary, secret scan, VPS and business-signal verifier PASS.
- **PostgreSQL smoke:** disposable local PostgreSQL 16.14 applied migrations 001-004, idempotently seeded synthetic config twice (`schema_migrations=4`, `dim_product=1`, `dim_warehouse_map=1`) and accepted one synthetic run/raw lineage insert. No customer values or persistent database were used.
- **Observed official schemas:** test-cabinet probes by root on 2026-08-13 confirmed 459 sales rows with strict `saleID` prefixes S (454) / R (5), current stock response under `data.items`, and non-identical sales/stock warehouse vocabularies requiring the planned private mapping. No values or response payloads are committed.
- **Self-review:** PASS. Exact bodies are fsynced/content-addressed and linked in PostgreSQL before parse; Statistics and Finance are separate READ-only scopes; Analytics RW requires an explicit temporary runtime opt-in and cannot pass the secure default. Unknown S/R prefix, schema, mapping, pagination, 401/403/429 and Telegram failure stop without an automatic notification retry. Deterministic top-risk and HTML escaping are tested.
- **Staging deploy:** clean detached HEAD `2d0f6ec` on `135.106.186.210`, Node `v22.23.2`, npm `10.9.8`, compiled CLIs and PostgreSQL migration ledger `001-004`, observed 2026-08-13. Before migration, root created and validated private dump `/srv/proxima-ai/backups/pre-phase-2.1-20260813.dump`, 39,747 bytes, mode `0600`, SHA-256 `745abc25ceded8768213c623614687643e3b32b7d860b5c5037536f03d0741d8`.
- **Private installer smoke:** one synthetic 7-file bundle passed on VPS with sanitized counts only; a second bundle with Analytics plus unrelated Content scope returned `TOKEN_SCOPE_INVALID` before runtime installation. The pre-existing Analytics file remained byte-identical, and the 6 absent runtime inputs remained absent.
- **Private input inventory:** the VPS seed recorded 4 versioned `dim_product` rows and 24 versioned `dim_warehouse_map` rows on 2026-08-13. Seven private source files are installed with mode `0600`; values were not logged or committed. Statistics and Finance tokens are exact-category READ-only. Analytics is exact-category RW behind the explicit temporary opt-in approved by Mike on 2026-08-13 and remains a hardening debt.
- **Hosted CI:** PASS on main `1a211c93f50a4f93937a772bbe0ac2d5dc90541a` - a descendant of deployed HEAD `2d0f6ec` that contains all 02-01A code: the `verify` run completed 2026-08-14T19:25 UTC (commit pushed 22:24:59 Moscow), verified 2026-08-15 (PA-12) via the [commit checks page](https://github.com/mihailzhamba-bot/proxima-ai/commit/1a211c9/checks). No hosted run is claimed for the exact SHA `2d0f6ec` itself.
- **Live technical acceptance:** run `ce53fb4e-8052-4956-ab45-00d230f66be0` collected all three official WB sources on 2026-08-13, persisted raw lineage, selected one deterministic risk and recorded `SENT` with Telegram `message_id=4`. The production Telegram client executed one `getMe`, one `getChat` and exactly one `sendMessage`, with no retry. Because direct VPS TLS to `api.telegram.org` timed out while local reachability passed, the one-shot sender ran through an SSH PostgreSQL tunnel from the operator Mac and wrote the result to the VPS ledger; the data pipeline and source-of-truth database remained on the VPS.
- **Live raw lineage:** the `SENT` run links Analytics page 0 SHA-256 `79d4d4d4ff31510a71a374bfcd0c8d4c2e575f0ce7ab85bd5b127e776e6e9e95`, Finance page 0 `302eeee3dcb007dd3b2e97ff36c6b4e3489730f863914ea73e37bd69e8203660`, Finance HTTP 204 terminator `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` and Statistics page 0 `941ee151c53b3c0e3574bc5a57b4a41666a5aad9eecb54f2e40d28389fa44009`, observed 2026-08-13.
- **Founder receipt:** PASS. On 2026-08-14 root opened the exact BotFather-created chat `@proximaaaai_bot` in Mike's local Telegram account and visually observed the formatted alert sent at 18:03 Moscow time on 2026-08-13. The visible message contained the selected internal SKU, warehouse, stock cover, lead time, buffer and unit margin. No screenshot, chat ID, token or business value is committed.
- **Release boundary:** staging exception only. Production release pointers, Phase 2 requirements, Data GO and Live Deploy GO are unchanged.
