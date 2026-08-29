window.STATE =
{
  "slug": "release-cutter",
  "dir": "2026-08-27-release-cutter",
  "title": "Release Cutter — шлюз между планированием и Autopilot",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T1",
  "briefFile": "2026-08-27-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.agents/skills/autopilot",
  "startedAt": "2026-08-27T20:35:04+03:00",
  "updatedAt": "2026-08-27T22:31:00+03:00",
  "finishedAt": "2026-08-27T22:31:00+03:00",
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-08-27T20:35:04+03:00", "finishedAt": "2026-08-27T20:36:10+03:00" },
    { "id": "manifest",  "status": "done", "startedAt": "2026-08-27T20:36:10+03:00", "finishedAt": "2026-08-27T20:44:30+03:00" },
    { "id": "briefing",  "status": "skipped", "note": "вопросов не потребовалось — развилки закрыты grill-интервью 2026-08-27" },
    { "id": "spec",      "status": "done", "startedAt": "2026-08-27T20:44:30+03:00", "finishedAt": "2026-08-27T21:02:00+03:00" },
    { "id": "plan",      "status": "done", "startedAt": "2026-08-27T21:02:00+03:00", "finishedAt": "2026-08-27T21:12:00+03:00", "note": "2 таска, ярус T1, 2 волны" },
    { "id": "build",     "status": "done", "startedAt": "2026-08-27T21:12:00+03:00", "finishedAt": "2026-08-27T22:03:00+03:00", "note": "2 из 2 тасков готовы" },
    { "id": "review",    "status": "done", "startedAt": "2026-08-27T21:30:00+03:00", "finishedAt": "2026-08-27T22:03:00+03:00", "note": "T01 3 оси 0 blocking; T02 inline, чисто" },
    { "id": "final",     "status": "done", "startedAt": "2026-08-27T22:03:00+03:00", "finishedAt": "2026-08-27T22:31:00+03:00", "note": "G4 24/25, 0 drift; память AGENTS.md дописана" }
  ],
  "requirements": {
    "total": 34, "done": 34, "inTicket": 0, "inSpec": 0,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [
    { "id": "01", "title": "Процессный слой Release Cutter: все файлы и перенаправления", "requirements": ["R01","R02","R03","R04","R05","R06","R07","R08","R09","R10","R11","R12","R13","R14","R15","R16","R17","R18","R19","R20","R21","R22","R23","R24","R25","R27","R28i","G01","G02","G03","G04","G05","G06"], "blockedBy": [], "wave": 1, "zone": [".opencode/","docs/release-gates/","AGENTS.md","docs/agent-system/"], "status": "done", "startedAt": "2026-08-27T21:16:00+03:00", "finishedAt": "2026-08-27T21:44:00+03:00", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": ["SKILL.md build-vs-buy: 12 пунктов из брифа vs 11 в критерии таска - бриф каноничен, оставлено", "SKILL.md Evidence missing (шаг) vs Evidence needed (шаблон) - обе формы дословно из брифа, оставлено", "ORCHESTRATION.md:41 гейт Майка всё ещё Task Brief - переименовать в Release Gate", "README третья копия Scope lock с расхождением правила 4 - сослаться на канон"] },
    { "id": "02", "title": "Dry-run: Release Gate по PMM-7", "requirements": ["R25","R26","G05"], "blockedBy": ["01"], "wave": 2, "zone": ["docs/release-gates/"], "status": "done", "startedAt": "2026-08-27T21:44:30+03:00", "finishedAt": "2026-08-27T22:03:00+03:00", "retries": 0, "repairs": 0, "handoffs": 0, "commit": null, "concerns": ["DISCOVERY_STATUS мэппинг неоднозначен для уже-выполненных задач - кодифицировать verdict-side precedence"] }
  ],
  "singlePass": null,
  "tests": null,
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": [],
  "coverage": { "g2_findings": 14, "missing": 3, "half": 7, "extra": 4, "fixed": 13, "justified_kept": 1 },
  "concerns": [],
  "reviewers": { "manifestSpec": null, "craft": null },
  "blind": { "verdict": "принято", "done": 24, "partial": 0, "missing": 0, "nodata": 1, "drift": 0 }
}
