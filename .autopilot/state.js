window.STATE =
{
  "slug": "morning-brief-live",
  "dir": "2026-09-21-morning-brief-live--wip",
  "title": "Сервер сам делает утреннюю сводку: 3 утра SUCCEEDED",
  "mode": "semi",
  "depth": "deep",
  "polish": null,
  "tier": "T2",
  "briefFile": "2026-09-21-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/root/.agents/skills/autopilot",
  "baseBranch": "main",
  "startedAt": "2026-09-21T11:15:02+00:00",
  "updatedAt": "2026-09-21T11:44:30+00:00",
  "finishedAt": null,
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-09-21T11:15:02+00:00", "finishedAt": "2026-09-21T11:18:30+00:00" },
    { "id": "manifest",  "status": "done", "startedAt": "2026-09-21T11:18:30+00:00", "finishedAt": "2026-09-21T11:24:10+00:00" },
    { "id": "briefing",  "status": "done", "startedAt": "2026-09-21T11:24:10+00:00", "finishedAt": "2026-09-21T11:30:20+00:00" },
    { "id": "spec",      "status": "done", "startedAt": "2026-09-21T11:30:20+00:00", "finishedAt": "2026-09-21T11:37:00+00:00" },
    { "id": "plan",      "status": "done", "startedAt": "2026-09-21T11:37:00+00:00", "finishedAt": "2026-09-21T11:44:30+00:00" },
    { "id": "build",     "status": "active", "startedAt": "2026-09-21T11:44:30+00:00" },
    { "id": "review",    "status": "pending" },
    { "id": "final",     "status": "pending" }
  ],
  "requirements": {
    "total": 12, "done": 0, "inTicket": 0, "inSpec": 0,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [
    { "id": "01", "title": "Диагностика VPS: почему деплой 1.14 сломался", "requirements": ["R01","R04","R05","R07","G01","R08"], "blockedBy": [], "wave": 1, "zone": [".autopilot/2026-09-21-morning-brief-live--wip/", "VPS read-only"], "status": "in-progress", "startedAt": "2026-09-21T11:44:30+00:00", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": [] },
    { "id": "02", "title": "Починка: минимальные правки по находкам", "requirements": ["R01","R05","R08"], "blockedBy": ["01"], "wave": 2, "zone": ["services/*", "infra/*", "docs/operations/*"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": [] },
    { "id": "03", "title": "Деплой 1.14 по runbook: боевое состояние", "requirements": ["R01","R02","R07","R08"], "blockedBy": ["02"], "wave": 3, "zone": ["VPS runbook release-m01"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": [] },
    { "id": "04", "title": "Приёмка: чек-лист, URL, три утра SUCCEEDED", "requirements": ["R02","R03","R06","R10i","R11i","G01","R08"], "blockedBy": ["03"], "wave": 4, "zone": [".autopilot/2026-09-21-morning-brief-live--wip/"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": [] }
  ],
  "singlePass": null,
  "tests": null,
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": ["брифинг 21.09: CI жив; доступ «решим по ходу»; сверка «смотрю сам»; постоянный URL - G01 (найти домены)"],
  "coverage": { "g2_findings": 12, "missing": 0, "half": 1, "extra": 11, "fixed": 1, "justified_kept": 11 },
  "concerns": [],
  "reviewers": { "manifestSpec": null, "craft": null },
  "blind": null
}
