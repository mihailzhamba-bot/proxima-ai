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

