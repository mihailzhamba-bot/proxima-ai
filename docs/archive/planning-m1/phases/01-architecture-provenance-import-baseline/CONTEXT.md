# Phase 1 Context - Architecture & Provenance Import Baseline

## Locked decisions

- Hybrid boundary: TypeScript collector/data-plane, Python control-plane/Data Health, PostgreSQL 16, Docker Compose.
- Existing TypeScript collector is not rewritten in Python.
- Both sibling source worktrees are read-only. Import only from the recorded commits or an explicit dirty-file allowlist with byte SHA-256.
- Phase 1 imports only safe, network-free collector primitives from the clean tracked baseline. Official WB intake and manifests belong to Phase 2.
- Torgstat browser/session code may be referenced in provenance, but must not enter a production workspace, package dependency graph, container, script or runtime flag.
- Linear rebaseline creates a new hierarchy by explicit IDs. The 123 legacy issues visible on 2026-08-12 remain unchanged.
- Every implementation plan ends with a clean commit, root verification evidence and an independent cross-model review of that exact commit.

## Source fingerprints before import

- `torgstat-collector` tracked commit: `610169a6bd3253fa351fa6fbe4ff571d4f4d5539`.
- `torgstat-collector` worktree status SHA-256 on 2026-08-12: `0e77e03f38430d8c1021b134494862a2825c10006be41183e632adb978fad29f`.
- `proxima-ai-manager` tracked commit: `9cca25d1118ab74a113be43e4346a024b0c7abe7`.
- `proxima-ai-manager` worktree status SHA-256 on 2026-08-12: `e02a035d7885b7a9ead9e9eb8b13f4f2da202a3e3e57b52ad83a8eea8ae70fc3`.

Fingerprints are hashes of `git status --porcelain=v1 -uall`, not hashes of source data content.

## Import allowlist

Exact-import from the clean `torgstat-collector` commit:

- `src/auth-error.ts` -> `services/collector/src/imported/auth-error.ts`
- `src/path-safety.ts` -> `services/collector/src/imported/path-safety.ts`
- `src/redact.ts` -> `services/collector/src/imported/redact.ts`

No file from the dirty working tree is allowlisted in Phase 1. No file from `proxima-ai-manager` is imported in Phase 1; its architecture remains candidate reference for later control-plane work.

## Verification boundary

The root verification command must fail closed for TypeScript, Python, JSON Schema contracts, provenance inventory, Mermaid rendering, Torgstat runtime references and secret scanning. Local evidence may record unavailable external services, but cannot mark CI or independent review as passed without a real locator.

