# Agent System — PROXIMA AI

Mapping of the AI Operating System roles to this repository's existing documents. Principle: **route, don't duplicate**. The project already has a strong `.planning/` layer and `docs/`; this directory only adds what was missing (always-current handoff, task snapshot, rules/evals/memory/decisions/tools in agent-facing form).

## Role map

| System role | Filled by | Notes |
|---|---|---|
| Bootloader / router / contract | `AGENTS.md` (repo root) | Extended 2026-08-16 with startup sequence, working contract, Definition of Done |
| Claude Code adapter | `CLAUDE.md` | `@AGENTS.md` import + Claude-specific notes only |
| What/why/for whom | `.planning/PRODUCT-VISION.md`, `README.md`, `.planning/REQUIREMENTS.md` | Not duplicated here |
| How it is built | `docs/architecture/*.mmd` (+ `docs/architecture/README.md`), `contracts/`, `db/migrations/` | Render via `make architecture` |
| Roadmap, phases, gates | `.planning/ROADMAP.md`, `.planning/phases/` | Phase CONTEXT lives there |
| Current project state (canonical, deep) | `.planning/STATE.md` | Updated by Mike/planning sessions |
| Current state + exact next action (agent handoff) | `docs/agent-system/HANDOFF.md` | Always-current, updated by agents |
| Active task snapshot | `docs/agent-system/TASKS.md` | Jira PA stays the primary tracker |
| Rules: MUST / SHOULD / MAY | `docs/agent-system/RULES.md` | English distillation of AGENTS.md bans + conventions |
| Verification stack + rubrics | `docs/agent-system/EVALS.md` + `scripts/agent/verify` + Makefile `verify` target | `make verify` remains the canonical full gate |
| Stable facts, pitfalls | `docs/agent-system/MEMORY.md` | |
| Engineering decisions | `docs/agent-system/DECISIONS.md` | Canonical decision log stays in `.planning/STATE.md` (Russian); DEC file holds pointers + agent-relevant subset |
| Tools, access, dangerous ops | `docs/agent-system/TOOLS.md` | |
| Big-task living plans | `docs/exec-plans/active/` → `completed/` | |
| Operations runbooks | `docs/operations/business-signal-runbook.md` | Extend this dir for future runbooks |

## Conventions

- Language: English inside `docs/agent-system/` and `docs/exec-plans/`; Russian for `.planning/` and communication with Mike.
- Every claim: source + date. Unknown → `UNKNOWN`.
- Update HANDOFF after every meaningful stage; TASKS at every state change of the active task.
- Do not create parallel copies of `.planning/` content here — link to it.
