# EVALS — PROXIMA AI

> How an agent or a program decides the result is good. Canonical full gate: `make verify` (Makefile). Fast agent gate: `scripts/agent/verify`.

## Verification stack

| Layer | Command | Notes |
|---|---|---|
| Install | `make install` | `npm ci` + `uv sync --python 3.14 --project services/control-plane --extra test --locked` |
| Codegen | `make codegen` | `node tools/generate_contract_types.mjs` → `services/collector/src/contracts/` |
| Typecheck | `npm run typecheck` | `tsc --noEmit` in `@proxima/collector` workspace |
| Unit tests (TS) | `npm test` | `tsx --test services/collector/tests/**/*.test.ts` + build + import smoke (`redactValue`, `intakeManualWbXlsx`) |
| Unit tests (Python) | `uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests tools/tests` | 48 passed, 1 skipped @ 2026-08-16 |
| Contracts | `make contracts` | `tools/verify_contracts.py` |
| Migrations | `make migrations` | `tools/verify_migrations.py` |
| Provenance | `make provenance` | `tools/verify_provenance.py` |
| Architecture render | `make architecture` | `node tools/render_architecture.mjs` (mermaid 11.16.0) |
| Runtime boundary | `make boundary` | `tools/verify_runtime_boundary.py` (incl. generated-vs-handwritten contracts gate) |
| Secrets scan | `make secrets` | `tools/secret_scan.py --self-test` + full scan |
| VPS contract | `make vps` | `tools/verify_vps_contract.py` |
| Business signal | `make business-signal` | `tools/verify_business_signal.py` |
| Full gate | `make verify` | chains all of the above; single exit code |
| Lint | N/A | No separate lint script exists in package.json / Makefile @ 2026-08-16 |

`scripts/agent/verify` runs the fast subset (structural + typecheck + TS tests + pytest). Where a layer does not exist, it is marked N/A — do not invent checks.

## Per-task-type rubrics

### Docs / agent-system change
1. `scripts/agent/verify` structural checks pass.
2. Every factual claim has source + date, or is marked `UNKNOWN`.
3. No duplication of `docs/archive/planning-m1/` content — routes/links only.

### Collector code change (TS)
1. `npm run typecheck` + `npm test` green (tests + build + import smoke).
2. New behavior covered by a test in `services/collector/tests/` (fixtures are structural, anonymized).
3. No hand-edits under `services/collector/src/contracts/` (codegen-owned).
4. Raw-evidence paths stay immutable and outside Git.

### Schema / migration change
1. `make migrations` + `make contracts` green; migration is ordered, immutable, additive-only.
2. Provenance chain intact (`make provenance`).

### Infra / VPS change
1. `make vps` green; secrets scan green (`make secrets`).
2. No secret values in repo, logs, or commit messages; changes to the VPS itself need explicit Mike approval.

## Review checklist (independent reviewer)

- [ ] Task understood correctly (vs acceptance criteria)
- [ ] Functional correctness
- [ ] No regressions (test suites green)
- [ ] Security (secrets, injection, tenant scoping, no WB WRITE)
- [ ] Edge cases (cancellation, rate limits, wait states)
- [ ] Tests cover the change
- [ ] Docs/state files updated (TASKS / HANDOFF / EVIDENCE)

## Eval scenarios (v2.0, automatable)

- E1 Full gate: `make verify` → typecheck + TS tests + pytest + contracts + secrets scan all green (CI runs on push/PR; local run before slice completion).
- E2 Secrets negative control: plant `TOKEN=canary-abc123` in a TRACKED temp file → secrets scan must FAIL; remove → PASS. Validates the scanner is alive, not decorative.
- E3 Fail-closed DONE: `scripts/agent/test-ai-os --fail-closed` → PASS.
- E4 (manual-gated, DEC-010-adjacent) WB READ-only invariant: any code path calling mutating WB endpoint fails review — checked by reviewer + boundary tool (`tools/verify_runtime_boundary.py`).
