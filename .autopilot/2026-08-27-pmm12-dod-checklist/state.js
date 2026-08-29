window.STATE =
{
  "slug": "pmm12-dod-checklist",
  "dir": "2026-08-27-pmm12-dod-checklist",
  "title": "PMM-12: DoD-чеклист среза (verify→commit, unreleased, SourceRef, 7 пунктов)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T0",
  "briefFile": "2026-08-27-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.agents/skills/autopilot",
  "startedAt": "2026-08-27T19:47:40+03:00",
  "updatedAt": "2026-08-27T20:27:07+03:00",
  "finishedAt": "2026-08-27T20:27:07+03:00",
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-08-27T19:47:40+03:00", "finishedAt": "2026-08-27T19:50:14+03:00" },
    { "id": "manifest",  "status": "done", "finishedAt": "2026-08-27T19:50:14+03:00" },
    { "id": "briefing",  "status": "done", "finishedAt": "2026-08-27T19:50:14+03:00" },
    { "id": "spec",      "status": "done", "startedAt": "2026-08-27T19:47:40+03:00", "finishedAt": "2026-08-27T19:55:55+03:00" },
    { "id": "plan",      "status": "skipped", "note": "ярус T0 - без разбивки на таски" },
    { "id": "build",     "status": "done", "startedAt": "2026-08-27T19:56:56+03:00", "finishedAt": "2026-08-27T20:16:34+03:00" },
    { "id": "review",    "status": "done", "startedAt": "2026-08-27T20:16:34+03:00", "finishedAt": "2026-08-27T20:16:34+03:00", "note": "T0 inline + independent reviewer: 0 blocking, 3 non-blocking -> concerns" },
    { "id": "final",     "status": "done", "startedAt": "2026-08-27T20:16:34+03:00", "finishedAt": "2026-08-27T20:27:07+03:00" }
  ],
  "requirements": {
    "total": 12, "done": 12, "inTicket": 0, "inSpec": 0,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [],
  "singlePass": {"files": ["docs/governance/dod-checklist.md", "scripts/agent/verify", "AGENTS.md", "docs/agent-system/RULES.md", "docs/agent-system/TASKS.md", "docs/agent-system/HANDOFF.md", ".autopilot/**"], "tests": "make verify PASS (full, commit a5a5197); scripts/agent/verify PASS; independent reviewer 0 blocking; blind acceptance: no drift", "commit": "a5a5197 (+ merge commit c6c3374, PR #23 merged)", "startedAt": "2026-08-27T19:56:56+03:00", "finishedAt": "2026-08-27T20:27:07+03:00"},
  "tests": null,
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": [],
  "coverage": {"findings": 8, "missing": 1, "half": 0, "extra": 7, "action": "missing: parent/relates PMM-12 добавлены в spec+manifest R10; extra: 7 craft/факты репо - легитимны (depth normal)"},
  "concerns": [{"finding": "state.js закоммичен WIP-снимком", "verdict": "drop", "reason": "финальный снимок в закрывающем коммите"}, {"finding": "R09/R10 утверждали Jira-шаги до выполнения", "verdict": "drop", "reason": "Jira-шаги выполнены в этом же прогоне (комментарии 10369-10373, статус Готово)"}],
  "reviewers": { "manifestSpec": null, "craft": null },
  "blind": {"verdict": "no drift", "detail": "все in-repo требования реализовано; Jira-пункты (PMM-30/9/10 комментарии, Done PMM-12, parent PMM-6, Relates PMM-15, merge PR #23) вне репо - подтверждены агентом после приёмки (комментарии 10369-10373)", "commands": "bash scripts/agent/verify -> VERIFY: PASS"}
}
