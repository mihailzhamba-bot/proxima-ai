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

**Checkpoint pending:** Mike supplies one official WB XLSX from the pilot cabinet. Before any parser code, record only private locator, filename, workbook sheet names, header names, byte size, SHA-256, retrieval time and approved field mapping. Never commit workbook bytes, cells, customer values or WB tokens.

## Plan 02-01A - Margin and out-of-stock Telegram proof

- **Implementation commits:** `76d39a2` (schema/private config), `0d5b950` (collector/calculation/Telegram), `20ea8cf` (Node 22 VPS contract/runbook).
- **Root verification:** `make verify` PASS on implementation HEAD `20ea8cf`, 2026-08-13. Evidence: 29 TypeScript tests, 35 Python tests, 1 Docker-dependent PostgreSQL test skipped, contracts, 4 ordered migration checks, provenance, 4 Mermaid renders, runtime boundary, secret scan, VPS and business-signal verifier PASS.
- **Observed official schemas:** test-cabinet probes by root on 2026-08-13 confirmed 459 sales rows with strict `saleID` prefixes S (454) / R (5), current stock response under `data.items`, and non-identical sales/stock warehouse vocabularies requiring the planned private mapping. No values or response payloads are committed.
- **Self-review:** PASS. Exact bodies are fsynced/content-addressed and linked in PostgreSQL before parse; token scopes are separate/read-only; unknown S/R prefix, schema, mapping, pagination, 401/403/429 and Telegram failure stop without an automatic notification retry. Deterministic top-risk and HTML escaping are tested.
- **Hosted CI:** pending for implementation HEAD `20ea8cf`; no PASS is claimed.
- **Live acceptance:** pending. Repository execution did not mutate `135.106.186.210` or send Telegram. Root must supply private config/tokens, deploy reviewed code, record one `SENT` run with source SHA-256 and `message_id`, and obtain founder receipt confirmation.
- **Release boundary:** staging exception only. Production release pointers, Phase 2 requirements, Data GO and Live Deploy GO are unchanged.
