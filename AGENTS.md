# Coding Agents Standard

Scope: this standard is canonical for all Proxima AI repositories. The sibling source
repositories `torgstat-collector` and `proxima-ai-manager` are read-only provenance
sources and are out of scope (see `.planning/STATE.md`, Source Boundaries).

## Supported agents

Two terminal coding agents are supported:

- **Claude Code**
- **Codex**

Both are equal first-class agents for any task in this repository: TypeScript
collector/data-plane, Python control-plane, infrastructure, migrations,
documentation. Agent choice per task belongs to the engineer running it.

`AGENTS.md` is the single source of truth for these instructions. `CLAUDE.md` is a
relative symlink to `AGENTS.md`, never a separate copy.

## Commands

Root `make verify` is the single CI entry point (mirrors `.github/workflows/verify.yml`).

- `make install` - npm ci (Node 22) + uv sync (Python 3.14, control-plane with test extra)
- `make typecheck` - TypeScript check of the collector workspace
- `make test` - collector tests (npm workspace) + pytest (control-plane, tools)
- `make contracts` - JSON Schema contract verification (Python side)
- `make migrations` - migration verification
- `make provenance` - provenance attestation verification
- `make architecture` - Mermaid render of architecture sources
- `make boundary` - runtime boundary verification
- `make secrets` - secret scan self-test + full scan
- `make vps` - VPS contract verification
- `make business-signal` - business-signal pipeline verification

Ops commands (not part of `verify`, require `.env` outside Git):
`make probe-wb-api`, `make apply-migrations`, `make collect-wb-analytics`.
These touch external WB endpoints or the production database; never run them
speculatively.

## Context routing

Load only the context the current task needs. Open the entrypoints below first,
then follow imports; do not read a whole directory when one file answers the
question.

| Path | Read when the task touches | Open first | Verify with |
|---|---|---|---|
| `services/collector` | TypeScript intake, WB collection, business signals | `src/index.ts` (public exports), then `src/cli/`, `src/business-signal/pipeline.ts`, `src/intake/manual-wb-xlsx.ts` | `make typecheck`, `make test` |
| `services/control-plane` | Python control plane, plane boundaries | `pyproject.toml`, `src/proxima_control_plane/__init__.py`, `tests/test_boundary.py` | `make test` |
| `contracts` | payload shape changes, intake or release schemas | the specific `*.schema.json` named by the failing check, `examples/*.synthetic.json` | `make contracts` |
| `db/migrations` | PostgreSQL schema changes | highest-numbered `*.sql`, then the verifier `tools/verify_migrations.py` | `make migrations` |
| `infra` | Compose stack, VPS bootstrap, runtime contracts | `compose.yaml`, `vps-contract.json`, `bootstrap/`, `monitoring/` | `make vps`, `make boundary` |
| `tools` | verifiers, WB probes, operational scripts | the script behind the failing make target, `tools/tests/` | the matching target above |
| `docs/architecture` | system, data flow, deployment and delivery questions | `README.md`, then `system.mmd` (mind map) and the one diagram matching the question | `make architecture` |
| `docs/operations` | production runs, secrets, business-signal operation | `business-signal-runbook.md` (authority for secret locations) | `make business-signal`, `make secrets` |
| `.planning` | scope, phase status, standing decisions | `STATE.md` (current position, decisions), `PROJECT.md` (out of scope) | - |

Rules:

- Never load the whole repository, all of `docs/` or all of `.planning/` when the
  task is bound to one area. Use targeted search (grep/glob) and open the files the
  table points to.
- Tests and fixtures for an area live next to it (`services/collector/tests/`,
  `services/control-plane/tests/`, `tools/tests/`) with synthetic data only; read
  them before writing new tests.
- For test tasks run the matching target from the table; for infrastructure tasks
  `make vps` / `make boundary`; for production-touching tasks follow
  `docs/operations/business-signal-runbook.md` and treat WB-facing operations as
  fail-closed.

## Architecture boundaries

- Hybrid monorepo: Node.js 22 + TypeScript collector/data-plane in `services/collector`;
  Python 3.14 + FastAPI control-plane in `services/control-plane`. Do not rewrite the
  proven TypeScript collector in Python without a separate ADR and benchmark evidence.
- Cross-language contracts live in `contracts/` as JSON Schema; both planes must validate
  against them.
- PostgreSQL migrations live in `db/migrations`; `infra/` is the single-VPS Docker
  Compose boundary (one host, one stack, no orchestration in M1).
- Raw WB artifacts and evidence bytes stay outside Git (content-addressed storage);
  only SHA-256 manifests and lineage metadata are committed.
- Source Boundaries: never mutate, stash, clean or commit the sibling worktrees
  (`torgstat-collector`, `proxima-ai-manager`). Dirty candidates require an explicit
  allowlist with relative path, byte SHA-256, review status and destination.
- Out of scope for M1: LLM runtime, Ozon, WB Advertising APIs, WB WRITE operations,
  client-facing UI, Torgstat live sessions (see `.planning/PROJECT.md`, Out of Scope).

## Access model

- The only supported access path is the vendor subscription of the corresponding
  agent (Anthropic subscription for Claude Code, OpenAI subscription for Codex).
- API pay-as-you-go billing is not used for regular interactive development.
  Regular means day-to-day coding, review and documentation work in this
  repository.
- Examples that fall under the exception process instead: batch evaluation runs,
  a CI bot, or a one-off script that must call the vendor API directly.
- Any such exception requires a separate Jira task in project PA stating: the
  reason, the owner, a monthly spend limit and a review date. No exception is
  implied by silence or habit.
- Vendor subscription credentials are personal. They are never shared with
  third-party agents or tools.

## Review process

Agent usage does not change the review gate. The binding rule lives in
`.planning/STATE.md`: independent cross-model review with 0 blockers / 0 warnings
is mandatory for phases 3, 4 and 7; all other work ships with root `make verify`,
CI evidence and self-review in EVIDENCE.md.

## Credentials hygiene and data fidelity

- No API keys, billing data or vendor subscription credentials in Git, project
  prompts, shell history or tracker issues.
- Secret locations and modes are defined in `docs/operations/business-signal-runbook.md`
  (`/etc/proxima-ai/secrets/` on the VPS, owner `proxima-admin`, mode `0600`).
  That runbook is the authority; this file does not restate its content.
- Keep official WB XLSX bytes outside Git; tests use synthetic structural fixtures
  with anonymized values only.
- Never fabricate cabinet IDs, SKUs, prices, thresholds or expected outcomes, even
  in tests.
- WB WRITE operations are forbidden; external-source operations are fail-closed:
  full success or rollback, no partial commits.

## Changing this standard

Changes go through a Jira task in project PA plus a commit to this file. Do not
fork the standard in project prompts or per-repository copies.

## Ownership and review cycle

- Owner: Mihail Zhamba.
- This standard is re-verified every 3 months: re-run the generator, then manually
  diff against the repository state (commands, boundaries, security rules).
- Current review cycle started 2026-08-15 (PA-32); next review due **2026-11-15**.
  The next date is fixed in the Jira task that closes each review.
