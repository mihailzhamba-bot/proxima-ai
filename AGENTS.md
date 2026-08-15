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

## Runtime and dependency versions

Manifests and lock files are the source of truth: `package.json`,
`package-lock.json`, `services/collector/package.json`,
`services/control-plane/pyproject.toml`, `services/control-plane/uv.lock`.
The table below is a navigational snapshot dated 2026-08-15 (PA-33).

| Component | Version | Source |
|---|---|---|
| Node | `>=22 <23` | root `package.json` `engines` |
| Python | `>=3.14 <3.15` | control-plane `requires-python` |
| TypeScript | `5.8.3` | collector devDependencies |
| tsx | `4.20.3` | collector devDependencies |
| Ajv | `8.20.0` | collector dependencies |
| ajv-formats | `3.0.1` | collector dependencies |
| csv-parse | `6.1.0` | collector dependencies |
| decimal.js | `10.6.0` | collector dependencies |
| pg | `8.16.3` | collector dependencies |
| @mermaid-js/mermaid-cli | `11.16.0` | root devDependencies |
| hatchling | `1.27.0` | control-plane build-system |
| httpx | `0.28.1` | control-plane test extra |
| jsonschema | `4.25.1` | control-plane test extra |
| psycopg | `3.3.4` | control-plane test extra |
| pytest | `8.4.2` | control-plane test extra |

Rules:

- Before generating code whose correctness depends on a library's API or
  behavior, the agent checks the actual version in the manifests and lock
  files; this table never substitutes for that check.
- A dependency update includes a synchronized update of this table in the same
  commit.

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
