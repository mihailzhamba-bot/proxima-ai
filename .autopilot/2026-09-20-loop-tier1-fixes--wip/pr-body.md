## Code Review Crew tier 1 + 1.5 fixes (adversarial review of PR #140)

8 findings from a 3-round cross-verified adversarial review session, implemented
and independently reviewed (0 blockers; review warning on child-cleanup fixed
in code).

### Tier 1
1. `/brief` crashes on expired session → guard like `/inbox`, 401 → /login (482cb8c)
2. `timestamptz::text` → Invalid Date in JSC/iOS → `to_json` ISO output (482cb8c)
3. Re-accepting a cancelled signal lied about success → honest 409 (482cb8c)
4. Observation verdict measured a foreign day → pinned to horizon end (482cb8c)
5. Childless paperclip stop wedged in eternal `cancelling` → upstream-confirmed
   stop, idempotent repeat, no `cancelled`→`cancelling` regression (b4ac6d5)
6. Example config advertised `bind: 0.0.0.0` with cleartext capability tokens →
   loopback default + TLS requirement in OPERATIONS.txt (5f35d21)

### Tier 1.5 (same commit as #5)
- Bridge internal errors: 500 + traceback + `uncertain:true` instead of a lying
  400; request-log silencer removed; runner serve-loop prints failures (b4ac6d5)
- Single `PAPERCLIP_STATUS_MAP` for reconcile/fence/cancel (b4ac6d5)

### Verification
- `make verify` PASS (single SKIP: `pg-roundtrip` — no local PG16), log committed
  at `.autopilot/2026-09-20-loop-tier1-fixes--wip/verification.log`
- pytest tools/tests 1015 passed; webapp vitest 148 passed / 10 skipped (db tests run in CI)
- New tests fail on the pre-fix code (verified by reviewer)

Merge decision stays with @mihailzhamba-bot. Includes cherry-pick c2badd6 of the agent-toolset verifier fix (#156) - the base line had the verifier/config mismatch; config itself was already compliant.

**PR base: `server/loop-continuous`** (not main - the LOOP pilot itself is not merged to main yet; this PR contains only the 4 fix commits on top of the loop-continuous line).
