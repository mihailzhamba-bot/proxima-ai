window.STATE =
{
  "slug": "w1-exit-criteria",
  "dir": "2026-08-27-w1-exit-criteria",
  "title": "Exit-критерии W1-среза (PMM-11)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": null,
  "briefFile": "2026-08-27-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.agents/skills/autopilot",
  "startedAt": "2026-08-27T19:06:39+03:00",
  "updatedAt": "2026-08-27T19:31:00+03:00",
  "finishedAt": "2026-08-27T19:31:00+03:00",
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-08-27T19:06:39+03:00", "finishedAt": "2026-08-27T19:09:10+03:00" },
    { "id": "manifest",  "status": "done", "startedAt": "2026-08-27T19:09:10+03:00", "finishedAt": "2026-08-27T19:11:00+03:00" },
    { "id": "briefing",  "status": "skipped", "note": "вопросов не потребовалось — все развилки закрыты гриллем 2026-08-27" },
    { "id": "spec",      "status": "done", "startedAt": "2026-08-27T19:11:00+03:00", "finishedAt": "2026-08-27T19:16:40+03:00" },
    { "id": "plan",      "status": "skipped", "note": "ярус T0 — без разбивки на таски" },
    { "id": "build",     "status": "done", "startedAt": "2026-08-27T19:18:10+03:00", "finishedAt": "2026-08-27T19:22:30+03:00" },
    { "id": "review",    "status": "done", "startedAt": "2026-08-27T19:22:30+03:00", "finishedAt": "2026-08-27T19:23:30+03:00", "note": "T0 inline: manifest clean, spec clean, craft 1 находка (PMM-29 sprint) исправлена" },
    { "id": "final",     "status": "done", "startedAt": "2026-08-27T19:24:00+03:00", "finishedAt": "2026-08-27T19:31:00+03:00" }
  ],
  "requirements": {
    "total": 12, "done": 12, "inTicket": 0, "inSpec": 12,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [],
  "singlePass": {
    "files": ["docs/exec-plans/active/w1-slice-exit-criteria.md", ".autopilot/ (прогон)", "AGENTS.md (скелет памяти)", ".gitignore (serve.*)"],
    "tests": "docs-only прогон: полный make verify не требуется по решению спецификации; структурная проверка - git-коммит a8b8950, 12 файлов",
    "commit": "a8b8950",
    "startedAt": "2026-08-27T19:18:10+03:00",
    "finishedAt": "2026-08-27T19:23:30+03:00"
  },
  "tests": "docs-only; make verify не запускался (правки не касаются кода)",
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": [],
  "coverage": { "checkedAt": "2026-08-27T19:16:40+03:00", "missing": 0, "halfCovered": 0, "extra": 6, "extraNote": "все 6 — из тела PMM-11 (тикет из брифа) и утверждённого плана; привязаны к R07/R08, резать нечего" },
  "concerns": [],
  "reviewers": { "manifestSpec": null, "craft": null },
  "blind": { "checkedAt": "2026-08-27T19:29:00+03:00", "matched": 12, "checked": 12, "mismatches": [], "note": "Jira-комментарий 10367 непроверяем из репо (подтверждён tool-результатом оркестратора); прогон 2 корректно отсутствует — гейт утверждения" }
}
