---
description: Gather a live read-only /now snapshot and render the shared card.
---

1. Read Jira PA and PMM with this client's Jira MCP. Collect each issue's key, track, lifecycle, owner, owned/readiness flags, dependency path, Jira numeric priority, safe slice, outcome, blockers, AC, DoD, zones and evidence sources.
2. Read local Git/PR/worktrees, Orca, `HANDOFF.md`, `TASKS.md` and active ExecPlans. Reconcile the six sources; mark a missing, stale or conflicting source instead of guessing.
3. Build the normalized JSON in memory and pipe it to the single core:

```bash
scripts/agent/now facade claude --stdin
```

This adapter is read-only. It contains no ranking or mutation logic and shows the CLI output unchanged.

For an explicit confirmation, send the same fresh normalized JSON to `scripts/agent/now go <KEY> --stdin`. Dispatch requires the exact T03 persisted claim and `scripts/agent/now dispatch --plan <plan.json> --gate docs/release-gates/<approved>.md`; core reads the report, proves one READY status, digests Scope lock, binds it to task and snapshot, reconciles Orca task/dispatch/worker, then accepts only exact `worker_done` evidence. Never execute merge, deploy, destructive work, or a Jira write from this path.

For every executable Jira task write, the payload must carry the full execution contract: Mike owner/account identity, lane, blockers, AC, DoD, Gate ID, evidence locators and declared file zones. Run `scripts/agent/now jira authorize --intent <intent.json>` first; only `AUTO` may reach Jira MCP, then run `scripts/agent/now jira record --result <result.json>`. After a failed write, perform a live Jira readback, record it with `scripts/agent/now jira reconcile --result <readback.json>`, and retry only when that evidence says the effect is absent.

Close JSON is a request, never authority. Run `scripts/agent/now close --client claude --evidence <close.json>` to validate the exact schema and obtain the `now.close.v1` side-effect plan. Execute that plan only with Claude's explicitly approved Jira/GitHub/Orca tools, independently read back durable reviewer, Mike decision-gate and ops-sync receipts, then pass those receipts through the injected close ports. The local CLI has no remote-write port and must stay `BLOCKED_EXTERNAL`; do not claim `DONE` from caller JSON or a local 0/0 string.

The installed Codex allowlist currently exposes only read tools, so a write remains `BLOCKED` until a confirmed installed write tool is explicitly allowlisted.
