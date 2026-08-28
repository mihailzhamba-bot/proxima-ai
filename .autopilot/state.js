window.STATE =
{
  "slug": "now-orchestrator",
  "dir": "2026-08-28-now-orchestrator--wip",
  "title": "/now - проектный оркестратор PROXIMA AI",
  "mode": "semi",
  "depth": "deep",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-08-28-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.agents/skills/autopilot",
  "startedAt": "2026-08-28T08:30:20+03:00",
  "updatedAt": "2026-08-28T10:06:00+03:00",
  "finishedAt": null,
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-08-28T08:30:20+03:00", "finishedAt": "2026-08-28T08:32:08+03:00" },
    { "id": "manifest", "status": "done", "startedAt": "2026-08-28T08:32:08+03:00", "finishedAt": "2026-08-28T08:42:00+03:00" },
    { "id": "briefing", "status": "skipped", "startedAt": "2026-08-28T08:42:00+03:00", "finishedAt": "2026-08-28T08:46:00+03:00", "note": "вопросов не потребовалось: grill и Release Gate закрыли продуктовые развилки" },
    { "id": "spec", "status": "done", "startedAt": "2026-08-28T08:46:00+03:00", "finishedAt": "2026-08-28T09:05:00+03:00" },
    { "id": "plan", "status": "done", "startedAt": "2026-08-28T09:05:00+03:00", "finishedAt": "2026-08-28T09:15:00+03:00", "note": "4 таска, ярус T2, 4 последовательные волны" },
    { "id": "build", "status": "active", "startedAt": "2026-08-28T09:15:00+03:00", "note": "2 из 4 тасков готовы" },
    { "id": "review", "status": "active", "startedAt": "2026-08-28T09:25:00+03:00", "note": "проверено 2 из 4" },
    { "id": "final", "status": "pending" }
  ],
  "requirements": {
    "total": 20, "done": 13, "inTicket": 7, "inSpec": 0,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [
    { "id": "01", "title": "R0: snapshot, selector и единые карточки", "requirements": ["R01","R02","R03","R04","R09","R10","R11","R13","R14"], "blockedBy": [], "wave": 1, "zone": ["tools/now_orchestrator/core/","tools/now_orchestrator/__init__.py","scripts/agent/now","tools/tests/test_now_core.py",".claude/commands/now.md",".codex/skills/now/SKILL.md",".opencode/commands/now.md"], "status": "done", "startedAt": "2026-08-28T09:18:00+03:00", "finishedAt": "2026-08-28T09:32:00+03:00", "retries": 2, "repairs": 2, "repairFindings": ["adapters must recover/reconcile live sources without caller-supplied snapshot","HANDOFF/TASKS/ExecPlans require typed models and initial loaders","malformed Jira issue records must fail closed","active foreign-lane task must block same-track START","restore approved B > C > A recommendation; global lifecycle reprioritization was extra","explicit Orca conflict regression was missing after retry 1"], "handoffs": 0, "files": [".claude/commands/now.md",".codex/skills/now/SKILL.md",".opencode/commands/now.md","tools/now_orchestrator/core/","scripts/agent/now","tools/tests/test_now_core.py"], "tests": { "passed": 24, "failed": 0 }, "commit": "29ee675", "concerns": [] },
    { "id": "02", "title": "R1: Jira policy, pre-write ledger и safe repair", "requirements": ["R15","R16","R17","R18"], "blockedBy": ["01"], "wave": 2, "zone": ["tools/now_orchestrator/jira/","scripts/agent/now","tools/tests/test_now_jira.py",".claude/commands/now.md",".codex/skills/now/SKILL.md",".opencode/commands/now.md",".codex/config.toml"], "status": "done", "startedAt": "2026-08-28T09:36:00+03:00", "finishedAt": "2026-08-28T10:06:00+03:00", "retries": 1, "repairs": 2, "handoffs": 0, "files": ["tools/now_orchestrator/jira/","tools/now_orchestrator/__main__.py","tools/tests/test_now_jira.py",".claude/commands/now.md",".codex/skills/now/SKILL.md",".opencode/commands/now.md",".codex/config.toml"], "tests": { "passed": 27, "failed": 0 }, "concerns": ["assign null/null regression is not isolated in one negative test", "boolean issue_count and empty transition ID share one assertion", "forged-contract and unresolved-key cases are covered through combined boundary tests rather than isolated mutation tests"] },
    { "id": "03", "title": "R2: track claims, file zones, lifecycle и integration lock", "requirements": ["R05","R06","R08","R12","G02"], "blockedBy": ["01","02"], "wave": 3, "zone": ["tools/now_orchestrator/runtime/","scripts/agent/now","tools/tests/test_now_runtime.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 },
    { "id": "04", "title": "R3: три adapters, supervised dispatch и close transaction", "requirements": ["R01","R03","R06","R07","R08","R12","R13","R16","R17","G01","G02"], "blockedBy": ["01","02","03"], "wave": 4, "zone": [".claude/commands/",".codex/skills/",".codex/config.toml",".opencode/commands/",".opencode/skills/",".opencode/agents/","docs/agent-system/","docs/release-gates/","tools/now_orchestrator/integration/","scripts/agent/now","tools/tests/test_now_adapters.py"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0 }
  ],
  "singlePass": null,
  "tests": { "passed": 173, "failed": 0, "skipped": 4 },
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": [],
  "coverage": {
    "firstPass": { "missing": 0, "half": 3, "extra": 12 },
    "actions": [
      "явно описано уточнение project-wide serialization до per-track и integration lock",
      "автономность уточнена как до merge gate и после merge до Done",
      "gap creation разделён на safe auto-repair и blocked scope-changing proposal",
      "12 implementation decisions привязаны к G02 и Gate RG-20260828-now-orchestrator"
    ],
    "secondPass": { "missing": 0, "half": 4, "extra": 12, "action": "referent утверждённого плана добавлен в brief" },
    "finalPass": { "missing": 0, "half": 0, "extra": 10, "action": "typed initial loaders для HANDOFF, TASKS и active ExecPlans добавлены и recheck подтвердил RESOLVED; extras привязаны к parent requirements как implementation craft" }
  },
  "concerns": [
    "Release Gate first dispatch lost provenance after agent_prompt_stalled; read-only report recovered from the same terminal and re-checked with Mike approvals",
    "Current parent checkout is dirty and must remain untouched; implementation worktree starts from origin/main f4b6e4c",
    "Phase 4 re-cut after T01 review: R0 adapters moved into T01 so each ticket closes a vertical user path",
    "tools/now_orchestrator/core/renderer.py:14 - multiline external values need final structural-injection triage",
    "scripts/agent/now:3 - CLI caller-cwd portability needs final triage"
  ],
  "reviewers": { "manifestSpec": "/root/manifest_spec_review", "craft": "/root/craft_review" },
  "blind": null
}
