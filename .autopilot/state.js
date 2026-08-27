window.STATE =
{
  "slug": "pmm20-scn001-core",
  "dir": "2026-08-27-pmm20-scn001-core--wip",
  "title": "PMM-20: ядро детектора SCN-001 (baseline 7/14/28 + сезонность, Шепли U×CVR×AOV, ₽-фильтр)",
  "mode": "semi",
  "depth": "normal",
  "polish": null,
  "tier": "T1",
  "briefFile": "2026-08-27-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.agents/skills/autopilot",
  "startedAt": "2026-08-27T21:08:18+03:00",
  "updatedAt": "2026-08-27T21:20:05+03:00",
  "finishedAt": null,
  "stages": [
    { "id": "preflight", "status": "done", "startedAt": "2026-08-27T21:08:18+03:00", "finishedAt": "2026-08-27T21:09:30+03:00" },
    { "id": "manifest",  "status": "done", "startedAt": "2026-08-27T21:09:30+03:00", "finishedAt": "2026-08-27T21:10:14+03:00" },
    { "id": "briefing",  "status": "done", "startedAt": "2026-08-27T21:10:14+03:00", "finishedAt": "2026-08-27T21:10:14+03:00", "note": "semi: бриф полон после грилля (9 решений утверждены), вопросов нет" },
    { "id": "spec",      "status": "done", "startedAt": "2026-08-27T21:10:14+03:00", "finishedAt": "2026-08-27T21:14:00+03:00" },
    { "id": "plan",      "status": "done", "startedAt": "2026-08-27T21:14:00+03:00", "finishedAt": "2026-08-27T21:18:30+03:00", "note": "2 таска, ярус T1, 2 волны" },
    { "id": "build",     "status": "active", "startedAt": "2026-08-27T21:18:30+03:00" },
    { "id": "build",     "status": "pending" },
    { "id": "review",    "status": "pending" },
    { "id": "final",     "status": "pending" }
  ],
  "requirements": {
    "total": 20, "done": 0, "inTicket": 19, "inSpec": 1,
    "placeholder": 0, "deferred": 0, "dropped": 0
  },
  "tickets": [
    { "id": "01", "title": "Ядро детектора SCN-001: baseline, Шепли, сигнал", "requirements": ["R01","R02","R03","R04","R05","R06","R07","R08","R10","R11","R12","R13","R14","R15","R19i","R20i","A01"],
      "blockedBy": [], "wave": 1, "zone": ["services/control-plane/src/proxima_control_plane/detectors/scn001/", "services/control-plane/tests/"], "status": "repair",
      "startedAt": "2026-08-27T21:21:00+03:00",
      "retries": 0, "repairs": 1, "handoffs": 0,
      "repairFindings": ["R05: знак revenue_delta_orders = Expected−Actual", "R06: снятие дедупа только по recovery (ratio_28 ≥ порога) или cooldown", "R19i: негативные метрики → INVALID_INPUT; exp_u=0 ломает точность суммы Шепли", "filtered_by_rub: только floor-отсечения", "snapshot_id: без excluded-SKU (по спеке)", "_encode: сортировать множества (PYTHONHASHSEED)", "убрать wall-clock default_evaluation_date", "тесты: точность Шепли на ≥2 факторах, collapse-ветка без исключения, явный ассерт delta_14"] },
    { "id": "02", "title": "Loader staging-данных + smoke + verify-гейт", "requirements": ["R09","R11","R16","R18"],
      "blockedBy": ["01"], "wave": 2, "zone": ["services/control-plane/src/proxima_control_plane/detectors/scn001/loader.py", "services/control-plane/src/proxima_control_plane/detectors/scn001/smoke.py"], "status": "pending",
      "retries": 0, "repairs": 0, "handoffs": 0 }
  ],
  "singlePass": null,
  "tests": null,
  "debt": { "placeholders": [], "assumptions": [], "emptyEnv": [] },
  "additions": [],
  "coverage": {"findings": 8, "missing": 0, "half": 4, "extra": 4, "action": "half: дефолты конфига вписаны, гистерезис заменён на «выше порога» из брифа, граница snapshot_id/run_fingerprint определена, source_refs=task_id зафиксировано; extra: A01 легитимно (parent R01), R19.1/19.2 трассируются в R19i брифа («не крэш и не NaN»), ₽-фильтр уточнён по уровню сигнала"},
  "concerns": [],
  "reviewers": { "manifestSpec": null, "craft": null },
  "blind": null
}
