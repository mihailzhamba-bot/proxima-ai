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
