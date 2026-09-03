# Agent System — PROXIMA AI

> **2026-08-30:** M1 roadmap superseded by the M-00..M-05 ladder (`/DECISIONS.md` D2). Current state = `/STATE.md`, decisions = `/DECISIONS.md`, inventory facts = `/docs/state/`. `docs/archive/planning-m1/` is history, not current requirements.

Mapping of the AI Operating System roles to this repository's existing documents. Principle: **route, don't duplicate**. The project already has a strong `docs/archive/planning-m1/` layer and `docs/`; this directory only adds what was missing (always-current handoff, task snapshot, rules/evals/memory/decisions/tools in agent-facing form).

## Role map

| System role | Filled by | Notes |
|---|---|---|
| Bootloader / router / contract | `AGENTS.md` (repo root) | Extended 2026-08-16 with startup sequence, working contract, Definition of Done |
| Claude Code adapter | `CLAUDE.md` | `@AGENTS.md` import + Claude-specific notes only |
| What/why/for whom | `_bmad-output/planning-artifacts/prds/prd-PROXIMA-AI-2026-08-28/prd.md` (current), `README.md` | `docs/archive/planning-m1/*` is the archive of the superseded M1 frame |
| How it is built | `docs/architecture/*.mmd` (+ `docs/architecture/README.md`), `contracts/`, `db/migrations/` | Render via `make architecture` |
| Roadmap, steps, acceptance gates | PRD §13 (`.../prd.md`), `_bmad-output/planning-artifacts/epics.md` | `docs/archive/planning-m1/ROADMAP.md` is archive (M1 replaced by the ladder, D2) |
| Requirements contract and glossary | `_bmad-output/specs/spec-wb-morning-brief/SPEC.md`, `glossary.md` | Canonical for September; PRD defers to it |
| Architecture invariants AD-1..AD-18 | `_bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md` | `docs/architecture/*.mmd` still describe the M1 frame |
| Decisions (canonical register) | `DECISIONS.md` (root) | D1-D26; product, process and architecture-level decisions. Supersedes the older pointer to `STATE.md` |
| Current session state, what to pick up next | `STATE.md` (root) | Session memory, not a decision register |
| Current state + exact next action (agent handoff) | `docs/agent-system/HANDOFF.md` | Always-current, updated by agents |
| Active task snapshot | `docs/agent-system/TASKS.md` | Jira PA stays the primary tracker |
| Human roles (second person: analyst / vibe-coder) | `docs/agent-system/roles/analyst-vladislav.md` | Vladislav: independent shadow recomputation of the whole calculation chain (golden references in `verification/`, `shadow` gate in `make verify`), right to block a release, cabinet reconciliation, retro-alarm labels, AC acceptance, his own code zones, access checklist and prohibitions (D26) |
| Rules: MUST / SHOULD / MAY | `docs/agent-system/RULES.md` | English distillation of AGENTS.md bans + conventions |
| Verification stack + rubrics | `docs/agent-system/EVALS.md` + `scripts/agent/verify` + Makefile `verify` target | `make verify` remains the canonical full gate |
| Stable facts, pitfalls | `docs/agent-system/MEMORY.md` | |
| Engineering decisions (agent-relevant subset) | `docs/agent-system/DECISIONS.md` | Canonical register is `DECISIONS.md` (root); this file holds pointers and the agent-relevant subset |
| Tools, access, dangerous ops | `docs/agent-system/TOOLS.md` | |
| Orca coordinator playbook (supervised orchestration) | `docs/agent-system/ORCHESTRATION.md` + release-critic agent `.opencode/agents/release-critic.md` | Contract summary in AGENTS.md «Orca coordinator protocol»; Release Gate: `docs/release-gates/README.md` |
| Big-task living plans | `docs/exec-plans/active/` → `completed/` | |
| Operations runbooks | `docs/operations/` | `dev-onboarding.md` (human entry point), `access-provisioning.md`, `observability.md`, `incident-runbook.md`, `business-signal-runbook.md`, `agent-toolset.md`; the release runbook is still pending (Story 1.13) |
| Data dictionary (tables, writers, readers, retention) | `docs/state/DATA-DICTIONARY.md` | Covers migrations 001-011 and the planned 012-016 |
| Conductor / Hermes pipeline | `docs/agent-system/ORCHESTRATOR.md`, `tools/orchestrator/`, `infra/hermes/` | Landed 01.09.2026; not yet reflected in the architecture spine |
| Known failures and workflow notes | `docs/agent-system/KNOWN_FAILURES.md`, `docs/agent-system/WORKFLOW.md`, `docs/agent-system/PROJECT.md` | |

## Conventions

- Language: English inside `docs/agent-system/` and `docs/exec-plans/`; Russian for `docs/archive/planning-m1/` and communication with Mike.
- Every claim: source + date. Unknown → `UNKNOWN`.
- Update HANDOFF after every meaningful stage; TASKS at every state change of the active task.
- Do not create parallel copies of `docs/archive/planning-m1/` content here — link to it.
