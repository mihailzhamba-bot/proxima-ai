# Release Gate: `/now` project orchestrator

## Gate

- Gate ID: RG-20260828-now-orchestrator
- Target release: internal project-management facade v1
- Source roadmap item: Mike-approved plan dated 2026-08-28
- Verdict: KEEP
- Handoff status: READY_AUTO
- Confidence: high
- DISCOVERY_STATUS: READY

## 1. Release outcome

- User/operator: Mike, COO and project owner.
- Current problem: Jira, Git worktrees, Orca and repo mirrors drift; choosing the next task requires repeated manual reconciliation.
- Observable post-release behavior: `/now` renders one evidence-backed card for Tracks A/B/C, keeps D frozen, repairs mechanically safe Jira drift, and `/now go <KEY>` routes approved work through the existing supervised pipeline.
- Success metric: the same normalized snapshot produces identical cards in Codex, Claude and opencode; no task starts or becomes Done outside the approved state machine.
- Deadline: current internal release; no production deploy in scope.
- Constraints: no secrets, no WB writes, no sibling-worktree mutations, explicit merge gate.
- Non-goals: second orchestration engine, scheduled unattended runs, product-code changes.

## 2. Why this exists

- Who uses it: Mike when asking what the project should do now.
- What breaks without it: active-task and ownership drift can select an already implemented, blocked or foreign-lane task.
- Why now: live Jira and Git audit on 2026-08-28 found PMM-20/PMM-11 active, stale PA statuses and unmerged branches while HANDOFF/TASKS lagged.
- Evidence: `docs/agent-system/HANDOFF.md`, `TASKS.md`, `ORCHESTRATION.md`, `.planning/PRODUCT-VISION.md`, live Jira and `git worktree list` read on 2026-08-28.
- Assumptions: Mike will invoke `/now`; safe repairs can be classified deterministically.
- Unknowns: 14-day usage frequency is not yet measured.

## 3. Kill assumptions

- Usage: zero Mike-initiated invocations in 14 days returns further investment to Release Gate.
- Safe repair: any live mutation outside the fixture-classified safe set fails acceptance and disables repair.
- Concurrency: any missed file-zone overlap or unreleasable merge lock stops the rollout.
- Codex config: rejection by `codex mcp list` must be fixed before Jira writes are enabled.

## 4. Existing assets and reuse

- Existing code: Orca tasks/dispatch/worktrees, Autopilot, reviewer, `make verify`.
- Existing configuration: Jira Atlassian MCP in all three clients; Codex currently allowlists reads only.
- Existing dependencies: no new runtime dependency required.
- Official API: Atlassian MCP already exposes create/edit/comment/link/transition tools.
- External options: no additional service is justified.
- Reuse recommendation: build only the facade, deterministic policy layer and adapters; route execution through Orca.
- External research status: not required; official installed integrations satisfy the slice.

## 5. Options

| Option | User value | Time to feedback | Build cost | Test cost | Operating cost | Risk | Reversibility |
|---|---:|---:|---:|---:|---:|---:|---:|
| Defer/manual | none new | immediate | 0 | 0 | recurring reconciliation | high drift | n/a |
| Read-only facade | partial | 1-2 days | M | M | low | under-delivers approved policy | high |
| Approved full scope | full | 3-5 days | L | M-L | medium | bounded external writes | per-slice revert |
| Reuse/buy | same as full | immediate platform | low | M-L | low | low | high |

## 6. Scope decision

| Item | Class | Decision | Reason | Return condition |
|---|---|---|---|---|
| Three-client `/now` facade and deterministic cards | CORE | in scope | approved entry point | n/a |
| Safe Jira writes, audit ledger and repair rules | CORE | in scope | explicit Mike approval | recalibrate after any wrong repair |
| A/B/C worktrees, declared zones and global merge lock | CORE | in scope | explicit Mike approval | n/a |
| `/now go`, verify/review/merge state machine | CORE | in scope | release outcome | n/a |
| Ops worktree + PR repo sync | SUPPORTING | in scope | dirty-tree safety | n/a |
| Jira delete/archive/bulk automation | DROP | approval-only | policy boundary | explicit future approval |

## 7. Recommended release slice

Ship four vertical slices under this Gate ID: R0 facade/read-only cards; R1 Jira policy, ledger and safe repair; R2 track concurrency and merge lock; R3 `/now go` execution loop and ops-sync close transaction.

## 8. Scope lock

### In scope

- `/now` skill plus thin Claude/Codex/opencode adapters.
- Deterministic renderer, drift classification and structural fixtures.
- Jira PA/PMM safe operations only, pre-write audit ledger and approval boundary.
- One write task per A/B/C track, mandatory file zones, overlap block and one integration lock.
- Existing Release Gate → Autopilot/Orca → verify → reviewer → Mike merge gate.
- Codex Jira write-tool allowlist and project-policy documentation.

### Explicitly out of scope

- Delete/archive/bulk Jira automation, scheduled unattended runs, WB operations, product services, contracts, migrations and sibling worktrees.

### Must reuse

- Orca, Autopilot, Release Cutter, reviewer, Jira Atlassian MCP, Git worktrees and existing project state files.

### Must not introduce

- A second state store or orchestration engine, unlogged writes, silent conflict resolution, undeclared task zones or automatic merge/deploy.

## 9. Acceptance criteria

- [ ] Identical three-client card output ranks B > C > A and freezes D, with source and date.
- [ ] Safe drift is repaired and audited; ambiguous or lane-owned drift is flagged without mutation.
- [ ] Every Jira write is allowlisted, PA/PMM-only and recorded before execution; unsafe operations require approval.
- [ ] Same-track or overlapping-zone tasks refuse to start; leaked locks are recoverable.
- [ ] `/now go` requires Mike confirmation and Done is impossible before merge and state synchronization.
- [ ] Dirty-tree sync stages only thread-owned files; `git add -A` is absent.
- [ ] `codex mcp list`, full tests, `make verify` and reviewer pass.

## 10. Verification

- Tests: golden cards, drift policy, Jira write policy/ledger, concurrency, lock recovery, confirmation gate and forbidden patterns.
- Manual verification: same fixture in three clients; `codex mcp list`; one approved throwaway Jira fire-test only if a live test issue is designated.
- Metrics/logs: append-only Jira write ledger plus Git/Orca evidence.
- Post-deploy check: 14-day invocation count and weekly audit-log review.

## 11. Rollback

- Trigger: wrong repair/write, stuck lock, misleading cards or config validation failure.
- Procedure: revert independent slice commits; use the ledger for manual Jira reversal; force-release the integration lock using the documented command.
- Irreversible effects: none; destructive Jira operations and merges remain approval-gated.

## 12. Autopilot handoff

- Goal: ship R0-R3 as clean reviewed vertical slices.
- In scope: exactly section 8.
- Out of scope: exactly section 8.
- Reuse: existing Orca/Autopilot/Release Gate/reviewer/Jira MCP stack.
- Constraints: fail closed; deterministic state; audit-before-write; structural fixtures; declared zones; no secrets.
- Dependencies: none external; do not touch active bot-lane worktrees.
- Acceptance criteria: section 9.
- Verification: section 10 plus `make verify` before worker completion.
- Rollback: section 11.
- Stop conditions: unsafe live repair, missing write audit, missed overlap, unreleasable lock, config validation failure or ambiguous policy conflict.

## 13. Final decision

- Verdict: KEEP.
- Handoff status: READY_AUTO.
- Why: Mike explicitly approved the policy changes and full scope; installed Orca and Atlassian MCP provide the required mechanisms without a new platform.
- Required user decision: none blocking; merge, deploy and destructive actions retain their standing gates.

DISCOVERY_STATUS: READY
