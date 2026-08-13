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
duration: 21min
completed: 2026-08-13
---

# Phase 2 Plan 01A: Margin and out-of-stock Telegram proof Summary

**Manual Node 22 slice that preserves three WB sources before parse, calculates Decimal unit margin and sends at most one deterministic stockout alert**

## Performance

- **Duration:** 21 min
- **Started:** 2026-08-13T10:39:00Z
- **Completed:** 2026-08-13T10:59:45Z
- **Tasks:** 3
- **Files modified:** 30

## Accomplishments

- Added additive versioned product/COGS, warehouse mapping, run and raw lineage tables without committing business values.
- Implemented strict Statistics sales, current Analytics stock and Finance detailed-report collection with exact raw bytes durable before parse.
- Added 14 completed Moscow-day velocity, Decimal margin, deterministic top-risk selection, escaped founder message and no automatic Telegram retry.
- Added a Node 22 VPS bootstrap and private one-shot runbook; no live VPS mutation or send occurred in repository execution.

## Task Commits

1. **Task 1: Add versioned config and provenance schema** - `76d39a2`
2. **Task 2: Collect, calculate and send one signal** - `0d5b950`
3. **Task 3: Add pinned VPS runtime and operator contract** - `20ea8cf`

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

**Total deviations:** 3 auto-fixed (1 security, 1 correctness, 1 blocking).
**Impact on plan:** All changes close correctness or deployability gaps; scope remains one manual staging signal.

## Issues Encountered

- Local Docker daemon was unavailable. The Docker-dependent PostgreSQL test remained skipped; no VPS mutation was used as a substitute.
- `make verify` passed on implementation HEAD `20ea8cf`: 29 TypeScript tests, 35 Python tests, 1 Docker-dependent skip, all contract/migration/provenance/architecture/secret/VPS/business-signal verifiers.

## User Setup Required

External WB and Telegram setup is required. Follow `docs/operations/business-signal-runbook.md`; it contains paths and commands but no secret, business value or chat ID placeholders.

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
- CI evidence is pending for implementation HEAD `20ea8cf`.
- End-to-end acceptance is pending private config/tokens, reviewed VPS deploy, one live `--send`, `SENT` DB evidence and founder receipt.
- Plan 02-02 remains checkpointed on the official WB XLSX and is unchanged.

## Self-Check: PASSED

- All 8 key implementation/planning files exist.
- Commits `76d39a2`, `0d5b950` and `20ea8cf` exist in repository history.
- Secret scan passed; Phase 2 requirements remain Pending; no send-capable values were committed.

---
*Phase: 02-vertical-slice-immutable-intake*
*Completed: 2026-08-13*
