window.STATE =
{
  "slug": "pmm12-dod-checklist",
  "dir": "2026-08-27-pmm12-dod-checklist--wip",
  "title": "PMM-12: DoD-чеклист среза (verify→commit, unreleased, SourceRef, 7 пунктов)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T0",
  "briefFile": "2026-08-27-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.agents/skills/autopilot",
  "startedAt": "2026-08-27T19:47:40+03:00",
  "updatedAt": "2026-08-27T19:56:56+03:00",
  "finishedAt": null,
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-08-27T19:47:40+03:00", "finishedAt": "2026-08-27T19:50:14+03:00" },
    { "id": "manifest",  "status": "done", "finishedAt": "2026-08-27T19:50:14+03:00" },
    { "id": "briefing",  "status": "done", "finishedAt": "2026-08-27T19:50:14+03:00" },
    { "id": "spec",      "status": "done", "startedAt": "2026-08-27T19:47:40+03:00", "finishedAt": "2026-08-27T19:55:55+03:00" },
    { "id": "plan",      "status": "skipped", "note": "ярус T0 - без разбивки на таски" },
    { "id": "build",     "status": "active", "startedAt": "2026-08-27T19:56:56+03:00" },
    { "id": "review",    "status": "pending" },
    { "id": "final",     "status": "pending" }
  ],
  "requirements": {
    "total": 12, "done": 0, "inTicket": 0, "inSpec": 0,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [],
  "singlePass": true,
  "tests": null,
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": [],
  "coverage": {"findings": 8, "missing": 1, "half": 0, "extra": 7, "action": "missing: parent/relates PMM-12 добавлены в spec+manifest R10; extra: 7 craft/факты репо - легитимны (depth normal)"},
  "concerns": [],
  "reviewers": { "manifestSpec": null, "craft": null },
  "blind": null
}
