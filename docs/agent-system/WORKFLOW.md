# WORKFLOW — PROXIMA AI

States: INBOX → UNDERSTAND → PLAN → READY → IN_PROGRESS → VERIFY → REVIEW → DONE (GLOBAL_RULES).

- Task source: Jira PA (external). Repo TASKS.md keeps the active-task snapshot + last-sync date; if Jira unreachable → WAITING_FOR_EXTERNAL_SYNC, never invent a task.
- Vertical slices end with clean implementation commit that passed `make verify`.
- Critical phases (3, 4, 7) require independent cross-model review: 0 blockers / 0 warnings (see EVALS.md, delegation protocol in AGENTS.md).
- Fail-closed DONE: `scripts/agent/complete-task` gate + CI `verify.yml` + pre-commit DONE-guard. Evidence dir: `docs/agent-system/evidence/`.
- Working tree carries pre-existing dirty files from other threads (see AGENTS.md Dirty-tree note): stage only your files; `git add -A` forbidden.
