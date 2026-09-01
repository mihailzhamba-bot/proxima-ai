# Agent System — PROXIMA AI

> **2026-08-30:** M1 roadmap superseded by the M-00..M-05 ladder (`/DECISIONS.md` D2). Current state = `/STATE.md`, decisions = `/DECISIONS.md`, inventory facts = `/docs/state/`. `docs/archive/planning-m1/` is history, not current requirements.

Mapping of the AI Operating System roles to this repository's existing documents. Principle: **route, don't duplicate**. The project already has a strong `docs/archive/planning-m1/` layer and `docs/`; this directory only adds what was missing (always-current handoff, task snapshot, rules/evals/memory/decisions/tools in agent-facing form).

## Role map

| System role | Filled by | Notes |
|---|---|---|
| Bootloader / router / contract | `AGENTS.md` (repo root) | Extended 2026-08-16 with startup sequence, working contract, Definition of Done |
| Claude Code adapter | `CLAUDE.md` | `@AGENTS.md` import + Claude-specific notes only |
| What/why/for whom | `docs/archive/planning-m1/PRODUCT-VISION.md`, `README.md`, `docs/archive/planning-m1/REQUIREMENTS.md` | Not duplicated here |
| How it is built | `docs/architecture/*.mmd` (+ `docs/architecture/README.md`), `contracts/`, `db/migrations/` | Render via `make architecture` |
| Roadmap, phases, gates | `docs/archive/planning-m1/ROADMAP.md`, `docs/archive/planning-m1/phases/` | Phase CONTEXT lives there |
| Current project state (canonical, deep) | `STATE.md` (root) | Updated by Mike/planning sessions |
| Current state + exact next action (agent handoff) | `docs/agent-system/HANDOFF.md` | Always-current, updated by agents |
| Active task snapshot | `docs/agent-system/TASKS.md` | Jira PA stays the primary tracker |
| Rules: MUST / SHOULD / MAY | `docs/agent-system/RULES.md` | English distillation of AGENTS.md bans + conventions |
| Verification stack + rubrics | `docs/agent-system/EVALS.md` + `scripts/agent/verify` + Makefile `verify` target | `make verify` remains the canonical full gate |
| Stable facts, pitfalls | `docs/agent-system/MEMORY.md` | |
| Engineering decisions | `docs/agent-system/DECISIONS.md` | Canonical decision log stays in `STATE.md` (root) (Russian); DEC file holds pointers + agent-relevant subset |
| Tools, access, dangerous ops | `docs/agent-system/TOOLS.md` | |
| Orca coordinator playbook (supervised orchestration) | `docs/agent-system/ORCHESTRATION.md` + release-critic agent `.opencode/agents/release-critic.md` | Contract summary in AGENTS.md «Orca coordinator protocol»; Release Gate: `docs/release-gates/README.md` |
| Big-task living plans | `docs/exec-plans/active/` → `completed/` | |
| Operations runbooks | `docs/operations/business-signal-runbook.md` | Extend this dir for future runbooks |

## Conventions

- Language: English inside `docs/agent-system/` and `docs/exec-plans/`; Russian for `docs/archive/planning-m1/` and communication with Mike.
- Every claim: source + date. Unknown → `UNKNOWN`.
- Update HANDOFF after every meaningful stage; TASKS at every state change of the active task.
- Do not create parallel copies of `docs/archive/planning-m1/` content here — link to it.
