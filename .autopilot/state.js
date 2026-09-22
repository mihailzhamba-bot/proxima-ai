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
  "updatedAt": "2026-09-21T16:20:00+00:00",
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
    "total": 13, "done": 1, "inTicket": 11, "inSpec": 0,
    "placeholder": 0, "deferred": 1, "dropped": 0
  },
  "tickets": [
    { "id": "01", "title": "Диагностика VPS: почему деплой 1.14 сломался", "requirements": ["R01","R04","R05","R07","G01","R08"], "blockedBy": [], "wave": 1, "zone": [".autopilot/2026-09-21-morning-brief-live--wip/", "VPS read-only"], "status": "done", "startedAt": "2026-09-21T11:44:30+00:00", "finishedAt": "2026-09-21T15:52:00+00:00", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": [] },
    { "id": "02", "title": "Починка: минимальные правки по находкам", "requirements": ["R01","R05","R08"], "blockedBy": ["01"], "wave": 2, "zone": ["services/*", "infra/*", "docs/operations/*"], "status": "done", "startedAt": "2026-09-21T15:52:00+00:00", "finishedAt": "2026-09-21T16:20:00+00:00", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": [] },
    { "id": "03", "title": "Деплой 1.14 по runbook: боевое состояние", "requirements": ["R01","R02","R07","R08"], "blockedBy": ["02"], "wave": 3, "zone": ["VPS runbook release-m01"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": [] },
    { "id": "04", "title": "Приёмка: чек-лист, URL, три утра SUCCEEDED", "requirements": ["R02","R03","R06","R10i","R11i","G01","R08"], "blockedBy": ["03"], "wave": 4, "zone": [".autopilot/2026-09-21-morning-brief-live--wip/"], "status": "pending", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": [] }
  ],
  "singlePass": null,
  "tests": { "passed": 250, "failed": 0, "note": "локальный срез: collector 130 + webapp 120, tsc/eslint чисто; pytest/pg-roundtrip - CI" },
  "debt": { "placeholders": ["G01 - URL: заглушка снята кандидатом localhost:3000 через туннель, домен - решение Mike"], "assumptions": [], "emptyEnv": [] },
  "additions": ["брифинг 21.09: CI жив; доступ «решим по ходу»; сверка «смотрю сам»; постоянный URL - G01 (найти домены)"],
  "coverage": { "g2_findings": 12, "missing": 0, "half": 1, "extra": 11, "fixed": 1, "justified_kept": 11 },
  "concerns": ["docs/operations/release-m01.md §8 - формулировка о 2.6 (переключение витрины) устарела после D01, поправить в релизе 2.6"],
  "reviewers": { "manifestSpec": null, "craft": null },
  "blind": null
}
