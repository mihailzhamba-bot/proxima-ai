window.STATE =
{
  "slug": "pmm-5-llm-analyst-w1",
  "dir": "2026-08-27-pmm-5-llm-analyst-w1--wip",
  "title": "PMM-5: LLM Analyst W1 - диагноз SCN-008/001/005 (primary + alternatives + unknowns, SourceRef)",
  "mode": "full",
  "depth": "normal",
  "polish": null,
  "tier": "T1",
  "briefFile": "2026-08-27-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.agents/skills/autopilot",
  "startedAt": "2026-08-27T21:18:39+03:00",
  "updatedAt": "2026-08-27T21:29:32+03:00",
  "finishedAt": null,
  "stages": [
    {
      "id": "preflight",
      "status": "done",
      "startedAt": "2026-08-27T21:18:39+03:00",
      "finishedAt": "2026-08-27T21:18:39+03:00"
    },
    {
      "id": "manifest",
      "status": "done",
      "startedAt": "2026-08-27T21:18:39+03:00",
      "finishedAt": "2026-08-27T21:20:41+03:00"
    },
    {
      "id": "briefing",
      "status": "done",
      "finishedAt": "2026-08-27T21:20:41+03:00",
      "note": "full mode - self-briefing: гриль 10/10 закрыл продуктовые развилки; craft: конфиг TOML, timeout 90с"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-08-27T21:20:41+03:00",
      "finishedAt": "2026-08-27T21:26:05+03:00"
    },
    {
      "id": "plan",
      "status": "done",
      "startedAt": "2026-08-27T21:26:05+03:00",
      "finishedAt": "2026-08-27T21:28:54+03:00",
      "note": "3 таска, ярус T1, волны 1-2-3 (серийно)"
    },
    {
      "id": "build",
      "status": "active",
      "startedAt": "2026-08-27T21:28:54+03:00",
      "note": "0 из 3 тасков готовы"
    },
    {
      "id": "review",
      "status": "pending"
    },
    {
      "id": "final",
      "status": "pending"
    }
  ],
  "requirements": {
    "total": 0,
    "done": 0,
    "inTicket": 0,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 0,
    "dropped": 0
  },
  "tickets": [
    {
      "id": "01",
      "title": "Ядро diagnosis: models, draft-схема, adapters, prompts, config",
      "requirements": [
        "R01",
        "R02",
        "R03",
        "R06",
        "R14",
        "R18",
        "R19",
        "R20",
        "R21",
        "R22",
        "R27i",
        "R28i"
      ],
      "blockedBy": [],
      "wave": 1,
      "zone": [
        "services/control-plane/src/proxima_control_plane/diagnosis/",
        "services/control-plane/pyproject.toml"
      ],
      "status": "in-progress",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-08-27T21:29:32+03:00"
    },
    {
      "id": "02",
      "title": "Сервис диагноза: fail-closed pipeline, аудит, флаг rollback, CLI",
      "requirements": [
        "R08",
        "R13",
        "R16",
        "R17",
        "R22",
        "R24",
        "R25",
        "R28i"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "services/control-plane/src/proxima_control_plane/diagnosis/",
        "services/control-plane/tests/"
      ],
      "status": "pending",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    },
    {
      "id": "03",
      "title": "Eval: датасет >=12 кейсов, раннер, гейт >=80%, latency",
      "requirements": [
        "R04",
        "R05",
        "R07",
        "R08",
        "R09",
        "R10",
        "R11",
        "R12",
        "R13",
        "R14",
        "R15",
        "R23",
        "A01",
        "R26"
      ],
      "blockedBy": [
        "02"
      ],
      "wave": 3,
      "zone": [
        "services/control-plane/tests/diagnosis/"
      ],
      "status": "pending",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0
    }
  ],
  "singlePass": null,
  "tests": null,
  "debt": {
    "placeholders": [],
    "assumptions": [],
    "emptyEnv": []
  },
  "additions": [
    "A01: eval как CLI-подкоманда - ради PMM-33 (родитель R23)"
  ],
  "coverage": {
    "findings": 6,
    "missing": 4,
    "half": 2,
    "extra": 5,
    "action": "missing: base_url в конфиг + optional extra llm + демо на ретро + DoD PMM-12 - добавлены в spec; half: SCN-005 payload поля + раздел Поставка - дописаны; extra: 5 легитимны (≤5мин и ≥80% - из тикета PMM-5 §8/AC, timeout 90с/exit-коды/audit-поля/schema_version - craft, A01 с родителем R23)"
  },
  "concerns": [],
  "reviewers": {
    "manifestSpec": null,
    "craft": null
  },
  "blind": null
}
