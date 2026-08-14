---
phase: 02-vertical-slice-immutable-intake
plan: 01A
subsystem: data-plane
tags: [typescript, postgresql, wildberries, telegram, provenance, decimal]
requires:
  - phase: 02-01
    provides: immutable byte-first evidence conventions and ordered migration ledger
provides:
  - versioned private SKU/COGS and warehouse mapping seed
  - raw-before-parse clients for three official WB READ categories
  - deterministic margin and out-of-stock signal with one Telegram call site
  - Node 22 one-shot VPS runtime contract
affects: [02-02, phase-3, phase-4, phase-7]
tech-stack:
  added: [decimal.js, csv-parse, node-postgres]
  patterns: [raw-before-parse, typed-block-reason, private-source-config, no-automatic-send-retry]
key-files:
  created:
    - db/migrations/004_business_signal_slice.sql
    - services/collector/src/business-signal/pipeline.ts
    - services/collector/src/business-signal/wb-client.ts
    - services/collector/src/business-signal/telegram.ts
    - docs/operations/business-signal-runbook.md
  modified:
    - Makefile
    - services/collector/package.json
    - docs/architecture/data-flow.mmd
key-decisions:
  - "Phase 2.1 is a staging exception: no production release pointer, scheduler, Data GO or Live Deploy GO changes."
  - "Current stock uses POST /api/analytics/v1/stocks-report/wb-warehouses; deprecated stock and realization endpoints are forbidden."
  - "Founder chat ID lives only in a private source file; no business values or send-capable placeholders are committed."
patterns-established:
  - "HTTP evidence pattern: persist exact body and manifest, record DB lineage, then parse."
  - "Notification pattern: preflight getMe/getChat, one sendMessage call site, no automatic retry."
requirements-completed: []
duration: 31min
completed: 2026-08-13
---

# Phase 2 Plan 01A: Margin and out-of-stock Telegram proof Summary

**Manual Node 22 slice that preserves three WB sources before parse, calculates Decimal unit margin and sends at most one deterministic stockout alert**

## Performance

- **Duration:** 31 min
- **Started:** 2026-08-13T10:39:00Z
- **Completed:** 2026-08-13T10:59:45Z
- **Tasks:** 3
- **Files modified:** 30

## Accomplishments

- Added additive versioned product/COGS, warehouse mapping, run and raw lineage tables without committing business values.
- Implemented strict Statistics sales, current Analytics stock and Finance detailed-report collection with exact raw bytes durable before parse.
- Added 14 completed Moscow-day velocity, Decimal margin, deterministic top-risk selection, escaped founder message and no automatic Telegram retry.
- Added a Node 22 VPS bootstrap and private one-shot runbook; root deployed the reviewed slice and recorded one live Telegram `SENT` run on 2026-08-13.

## Task Commits

1. **Task 1: Add versioned config and provenance schema** - `76d39a2`
2. **Task 2: Collect, calculate and send one signal** - `0d5b950`
3. **Task 3: Add pinned VPS runtime and operator contract** - `20ea8cf`

Review fixes:

- **WB page pacing and complete least-privilege scope validation** - `fe0bc5d`
- **Finance line-amount commission semantics** - `255e6c0`
- **Skip unused Puppeteer browser download on VPS** - `deeefcb`
- **Fail-closed private input bundle validator and installer** - `ab8f451`
- **Fail-closed founder chat discovery after one private `/start`** - `6e0a605`
- **Explicit temporary Analytics RW opt-in with secure default rejection** - `fcb3841`
- **Observed Finance schema compatibility and unattributable-row pagination** - `5393bcb`, `2d0f6ec`

## Files Created/Modified

- `db/migrations/004_business_signal_slice.sql` - additive dimensions, run ledger and raw-source lineage.
- `services/collector/src/business-signal/wb-client.ts` - strict official WB READ clients and pagination terminators.
- `services/collector/src/business-signal/raw-store.ts` - private content-addressed HTTP body and manifest persistence.
- `services/collector/src/business-signal/calculate.ts` - velocity, stock cover, margin and deterministic risk ranking.
- `services/collector/src/business-signal/telegram.ts` - humanized HTML-safe copy and single send call site.
- `services/collector/src/cli/stockout-signal.ts` - dry-run/default and explicit `--send` entrypoint.
- `infra/bootstrap/prepare-business-signal-runtime.sh` - Node 22 installation/build contract for the observed VPS.
- `docs/operations/business-signal-runbook.md` - deploy, seed, dry-run and one-send acceptance steps.

## Decisions Made

- Kept Phase 2.1 unreleased and manual; Phase 4/7 retain ownership of scheduler and production operations.
- Used the current offset-paginated stock endpoint observed on 2026-08-13, not deprecated `/supplier/stocks`.
- Classified operational sales/returns by strict `saleID` S/R prefix observed on the test cabinet; unknown prefix blocks the run.
- Kept the founder chat value in a private JSON source with mode `0600`, satisfying hardcoding intent without committing a send-capable value.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Security] Closed private-file TOCTOU windows**
- **Found during:** Task 2
- **Issue:** `lstat` followed by path-based read could be swapped to a symlink.
- **Fix:** Tokens, config CSV and founder chat now use one `O_NOFOLLOW` handle for fstat and read.
- **Files modified:** `secrets.ts`, `config.ts`, `runtime.ts`
- **Verification:** private-mode tests, TypeScript typecheck and full collector suite pass.
- **Committed in:** `0d5b950`

**2. [Rule 1 - Correctness] Added sales boundary deduplication and safe JSON integers**
- **Found during:** Task 2 self-review
- **Issue:** inclusive cursor pages could repeat a sale; BigInt IDs serialized as strings could violate WB integer schemas.
- **Fix:** deduplicate by `saleID` with conflict detection and fail closed outside safe JSON integer range.
- **Files modified:** `wb-client.ts`
- **Verification:** 29 collector tests and build/typecheck pass.
- **Committed in:** `0d5b950`

**3. [Rule 3 - Blocking] Installed Node 22 in the deploy contract**
- **Found during:** VPS preflight from root on 2026-08-13
- **Issue:** host had git and free disk but no Node/npm.
- **Fix:** added major-pinned Node 22 NodeSource setup, major verification, `npm ci` and build.
- **Files modified:** `prepare-business-signal-runtime.sh`, VPS verifier, runbook.
- **Verification:** `bash -n`, VPS verifier and full `make verify` pass.
- **Committed in:** `20ea8cf`

**4. [Rule 1 - Correctness] Paced continuation pages at official WB limits**
- **Found during:** Root review after Task 3
- **Issue:** Immediate continuation requests would hit Statistics/Finance 1-minute and Analytics 20-second limits.
- **Fix:** Added dependency-injected 60s/20s/60s pacing before continuation pages; no HTTP request is retried.
- **Files modified:** `wb-client.ts`, `pipeline.ts`, business-signal tests.
- **Verification:** tests assert all three intervals without sleeping and Finance explicit field projection.
- **Committed in:** `fe0bc5d`

**5. [Rule 2 - Security] Rejected WB tokens with unrelated category scopes**
- **Found during:** Root review after Task 3
- **Issue:** The partial scope-bit map could accept required scope plus an unrecognized category.
- **Fix:** Reused the complete known category-bit map and require exactly one requested category plus READ-only.
- **Files modified:** `secrets.ts`, business-signal tests.
- **Verification:** negative Statistics/content and Finance/documents scope tests pass without logging claims.
- **Committed in:** `fe0bc5d`

**6. [Rule 1 - Correctness] Treated Finance commission as a line amount**
- **Found during:** Root review after Task 3
- **Issue:** Multiplying `ppvzSalesCommission` by quantity double-counted commission for multi-unit rows.
- **Fix:** Sum sale-row commissions once, then divide by total sold units; price remains quantity-weighted and logistics includes every SKU row.
- **Files modified:** `calculate.ts`, business-signal tests.
- **Verification:** quantity-2 regression test produces 549.90 RUB/unit and fails under the old formula.
- **Committed in:** `255e6c0`

**7. [Rule 3 - Blocking] Skipped unused Puppeteer browser downloads on VPS**
- **Found during:** Root staging deploy on 2026-08-13
- **Issue:** root `npm ci` stopped before build because Puppeteer tried to extract Chromium on a host without `unzip`; the business-signal runtime does not use Puppeteer.
- **Fix:** set `PUPPETEER_SKIP_DOWNLOAD=true` only for the VPS install and made the guard mandatory in both runtime verifiers.
- **Files modified:** `prepare-business-signal-runtime.sh`, VPS verifier, business-signal verifier.
- **Verification:** targeted verifiers and full `make verify` passed; the repeated VPS bootstrap installed 221 packages, audited 223 with 0 vulnerabilities and built the collector.
- **Committed in:** `deeefcb`

**Total deviations:** 7 auto-fixed (2 security, 3 correctness, 2 blocking).
**Impact on plan:** All changes close correctness or deployability gaps; scope remains one manual staging signal.

## Issues Encountered

- Local Docker daemon was unavailable. The Docker-dependent PostgreSQL test remained skipped; a separate disposable PostgreSQL smoke and the staging migration both passed.
- `make verify` passed on current and deployed implementation HEAD `2d0f6ec`, repeated 2026-08-14: 37 TypeScript tests, 35 Python tests, 1 existing Docker-dependent skip, all contract/migration/provenance/architecture/secret/VPS/business-signal verifiers.
- A disposable local PostgreSQL 16.14 cluster applied all 4 migrations, seeded the synthetic product/warehouse versions twice without duplicates (`4|1|1`), then accepted a run/raw lineage insert through its foreign keys and constraints.
- Staging VPS `135.106.186.210` had clean detached HEAD `2d0f6ec`, Node `v22.23.2`, npm `10.9.8`, compiled CLIs and migration ledger `001-004` when observed 2026-08-13. The private seed recorded 4 product versions and 24 warehouse mappings. The pre-migration private dump is `/srv/proxima-ai/backups/pre-phase-2.1-20260813.dump`, 39,747 bytes, mode `0600`, SHA-256 `745abc25ceded8768213c623614687643e3b32b7d860b5c5037536f03d0741d8`.
- Live run `ce53fb4e-8052-4956-ab45-00d230f66be0` recorded `SENT` and Telegram `message_id=4` on 2026-08-13 after one `sendMessage` call. The run retained four raw source-page checksums. Direct VPS Telegram TLS timed out, so the production sender used a temporary local operator path and updated the VPS PostgreSQL ledger through an SSH tunnel; temporary local secret copies and the tunnel were removed after the send.

## User Setup Required

Private setup for the one-shot proof is complete. Mike still needs to confirm founder receipt. Replacing the explicitly allowed Analytics RW token with Analytics READ-only remains follow-up hardening; no secret or business value is committed.

## Known Stubs

None. Private business values and credentials are intentional deployment inputs, not UI/data stubs.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: outbound-api | `wb-client.ts` | Three official WB READ boundaries with raw evidence and typed failures. |
| threat_flag: outbound-notification | `telegram.ts` | One manual Telegram send call site using a private token/chat source. |
| threat_flag: private-file-access | `secrets.ts` | Reads token/config files through private no-follow handles. |
| threat_flag: schema | `004_business_signal_slice.sql` | Adds staging-only dimensions and run/raw lineage tables. |

## Next Phase Readiness

- Repository implementation and local verification are complete.
- Staging deploy, migration and private seed are complete on `2d0f6ec`; the 2026-08-13 VPS ledger contains 4 product versions and 24 warehouse mappings.
- CI evidence is pending for deployed HEAD `2d0f6ec`.
- Dry run and one live send are complete with `SENT` DB evidence and Telegram `message_id=4`; only founder receipt confirmation remains for end-to-end acceptance.
- Plan 02-02 remains checkpointed on the official WB XLSX and is unchanged.

## Self-Check: PASSED

- All 8 key implementation/planning files exist.
- Commits `76d39a2`, `0d5b950`, `20ea8cf`, `fe0bc5d`, `255e6c0`, `deeefcb`, `ab8f451`, `6e0a605`, `fcb3841`, `5393bcb` and `2d0f6ec` exist in repository history.
- Secret scan passed; Phase 2 requirements remain Pending; no send-capable values were committed.

---
*Phase: 02-vertical-slice-immutable-intake*
*Completed: 2026-08-13*
