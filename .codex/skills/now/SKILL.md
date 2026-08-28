---
name: now
description: Gather a live read-only /now snapshot and render the shared card.
---

1. Read Jira PA and PMM with this client's Jira MCP. Collect each issue's key, track, lifecycle, owner, owned/readiness flags, dependency path, Jira numeric priority, safe slice, outcome, blockers, AC, DoD, zones and evidence sources.
2. Read local Git/PR/worktrees, Orca, `HANDOFF.md`, `TASKS.md` and active ExecPlans. Reconcile the six sources; mark a missing, stale or conflicting source instead of guessing.
3. Build the normalized JSON in memory and pipe it to the single core:

```bash
scripts/agent/now render --stdin
```

This adapter is read-only. It contains no ranking or mutation logic and returns the CLI output unchanged.

For an explicit confirmation, send the same fresh normalized JSON to `scripts/agent/now go <KEY> --stdin`. Return its deterministic `ActionPlan` unchanged; T03 creates only an ephemeral claim and plan, while actual Orca dispatch is T04. Never execute merge, deploy, destructive work, or a Jira write from this path.

For every executable Jira task write, the payload must carry the full execution contract: Mike owner/account identity, lane, blockers, AC, DoD, Gate ID, evidence locators and declared file zones. Run `scripts/agent/now jira authorize --intent <intent.json>` first; only `AUTO` may reach Jira MCP, then run `scripts/agent/now jira record --result <result.json>`. After a failed write, perform a live Jira readback, record it with `scripts/agent/now jira reconcile --result <readback.json>`, and retry only when that evidence says the effect is absent. The installed Codex allowlist currently exposes only read tools, so a write remains `BLOCKED` until a confirmed installed write tool is explicitly allowlisted.
