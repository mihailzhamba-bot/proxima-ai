# TASKS — PROXIMA AI

> Snapshot of task state in this repo. Full backlog lives in Jira project PA (zhamba.atlassian.net); this file mirrors only what an agent needs to resume work.

## Active main task

### COLLECTOR-WB-BRANCHES — WB run cancellation / detached branch handling (Phase 2 collector hardening)

Status: IN_PROGRESS (implementation thread landed at `1a211c9`, later commits `e867911..8b07249` landed on top; final integration state unconfirmed — see Next action)
Priority: P1 (Track A / M1, epic PA-36)
Type: feature/bug (collector robustness)
Tracker: UNKNOWN (specific Jira issue key not established from repo evidence; epic PA-36)
Dependencies: none open in-repo

### Why
The collector's async WB intake must never leave orphaned RUNNING state or keep detached WB report branches alive after a run is cancelled or fails. Long waits (rate limits, `WAITING`/`PROCESSING`/`RETRY` states) must be abortable so scheduled runs cannot hang indefinitely.

### Desired outcome
A cancelled/failed run reliably aborts pending waits and cancels detached WB branches; BLOCKED outcomes provably cancel the detached branches; behavior is covered by tests.

### Scope / Out of scope
In scope: `services/collector` cancellation helpers, abortable sleep, detached-branch cancellation on RUNNING leftovers, rate-limit response header persistence in raw evidence.
Out of scope: WB WRITE endpoints (forbidden), scheduler/SLA work (Phase 4), control-plane changes.

### Acceptance criteria
- Abortable sleep + run cancellation helpers exist and are used (commit `99fea05`, 2026-08-14).
- A run leaving RUNNING cancels detached WB branches (commit `dc68839`).
- Test proves BLOCKED cancels detached WB branches (commit `1a211c9`).
- `scripts/agent/verify` (typecheck + TS tests + pytest) green — confirmed 2026-08-16.

### Verification
`scripts/agent/verify` (fast gate) or `make verify` (full canonical gate).

### Next action
Confirm with Mike / Jira PA whether this thread is DONE and can be closed (then record it under Done and pull the next task from Jira PA). Per `.planning/STATE.md` (2026-08-16), the planned next main thread is Track B: scenario-engine audit in the `Опрос-v2.2` source worktree (PA-39) — which lives OUTSIDE this repo.

## Queue

1. Track B PA-39: scenario engine audit in `Опрос-v2.2` (other repo; do not mutate that worktree without allowlist — see RULES).
2. Phase 2 `02-02`: checkpointed on the official WB XLSX from Mike — blocked until the file is delivered (STATE.md, 2026-08-16).
3. Phase 2 leftovers: CI pipeline green run; observed-XLSX parser (STATE.md: "CI and the observed XLSX parser remain pending").
4. From Mike (inputs): pilot XLSX, production Bogatova token, interview slots, AI-ops analyst onboarding, COGS data (STATE.md, 2026-08-16).

## Done (recent)

- 2026-08-14 `1a211c9` test(collector): prove BLOCKED cancels detached WB branches.
- 2026-08-14 `dc68839` fix(collector): cancel detached WB branches when a run leaves RUNNING.
- 2026-08-14 `99fea05` feat(collector): abortable sleep and run cancellation helpers.
- 2026-08-14 `5603f50` docs(runbook): pin warehouse mapping effective_from and service sales warehouses.
- 2026-08-14 `a4b0ed6` feat(collector): persist rate-limit response headers in raw evidence.

---

Rules: one active main task; new ideas go to Jira PA backlog, not here; update this file at every state change of the active task.
