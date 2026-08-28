window.STATE =
{
  "slug": "pmm-5-llm-analyst-w1",
  "dir": "2026-08-27-pmm-5-llm-analyst-w1",
  "title": "PMM-5: LLM Analyst W1 - диагноз SCN-008/001/005 (primary + alternatives + unknowns, SourceRef)",
  "mode": "full",
  "depth": "normal",
  "polish": null,
  "tier": "T1",
  "briefFile": "2026-08-27-brief.md",
  "memoryFile": "AGENTS.md",
  "skillDir": "/Users/mikezhamba/.agents/skills/autopilot",
  "startedAt": "2026-08-27T21:18:39+03:00",
  "updatedAt": "2026-08-28T05:00:41+03:00",
  "finishedAt": "2026-08-28T05:00:41+03:00",
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
      "status": "done",
      "startedAt": "2026-08-27T21:28:54+03:00",
      "note": "3 из 3 тасков готовы",
      "finishedAt": "2026-08-28T04:54:23+03:00"
    },
    {
      "id": "review",
      "status": "done",
      "startedAt": "2026-08-28T04:54:23+03:00",
      "finishedAt": "2026-08-28T04:54:23+03:00",
      "note": "по таскам: T01 0/0 blocking, T02 1 blocking (gitignore) закрыт в T03, T03 0/0 blocking"
    },
    {
      "id": "final",
      "status": "done",
      "startedAt": "2026-08-28T04:54:23+03:00",
      "finishedAt": "2026-08-28T05:00:41+03:00"
    }
  ],
  "requirements": {
    "total": 32,
    "done": 28,
    "inTicket": 0,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 4,
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
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-08-27T21:29:32+03:00",
      "finishedAt": "2026-08-27T21:46:07+03:00",
      "commit": "f818e62",
      "files": [
        "services/control-plane/src/proxima_control_plane/diagnosis/",
        "services/control-plane/pyproject.toml",
        "services/control-plane/tests/diagnosis/"
      ],
      "tests": {
        "passed": 44,
        "failed": 0
      }
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
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-08-27T21:46:07+03:00",
      "finishedAt": "2026-08-27T22:00:25+03:00",
      "commit": "3c53bf4",
      "files": [
        "services/control-plane/src/proxima_control_plane/diagnosis/{service,audit,cli,__main__}.py",
        "services/control-plane/tests/diagnosis/{test_diagnosis_service,test_diagnosis_audit,test_diagnosis_cli}.py"
      ],
      "tests": {
        "passed": 61,
        "failed": 0
      }
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
        "services/control-plane/tests/diagnosis/",
        ".gitignore (одна строка logs/)"
      ],
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "handoffs": 0,
      "startedAt": "2026-08-27T22:00:25+03:00",
      "finishedAt": "2026-08-28T04:53:51+03:00",
      "commit": "8856274",
      "files": [
        "services/control-plane/tests/diagnosis/data/eval/cases.json",
        "services/control-plane/tests/diagnosis/eval_runner.py",
        "services/control-plane/tests/diagnosis/test_diagnosis_eval.py",
        "services/control-plane/src/proxima_control_plane/diagnosis/cli.py",
        ".gitignore"
      ],
      "tests": {
        "passed": 71,
        "failed": 0
      }
    }
  ],
  "singlePass": null,
  "tests": {
    "passed": 71,
    "failed": 0
  },
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
  "concerns": [
    "builder.py:67-74 - значения DIAGNOSIS_INPUT без экранирования: \\n или | в значении ломает разбор моком (SYNTH-fixtures не задеты)",
    "test_diagnosis_adapters.py:66 - фильтр отбрасывает чистые нули: выдуманный «0» невидим для проверки чисел",
    "mock.py:27-28 - _format_number speculative generality",
    "config.py:64-65 - base_url дублирует str-цикл однотипных ключей",
    "make_signal фикстура продублирована в двух тест-файлах - унести в conftest",
    "поиск diagnosis.toml рядом с cwd - владелец CLI (дописано в тикет 02)",
    "service.py:41 - дублирование загрузчика схемы (свой кэш рядом с validator) - Reinvention",
    "service.py:104 - ThreadPoolExecutor shutdown(wait=False): некancelable воркеры при реальном timeout (с mock не триггерится; учесть в PMM-31)",
    "service.py:96 - unknowns без source_refs-проверки: сужение зафиксировано схемой (unknowns = вопросы, не факты)",
    "фикстуры make_signal дублируются (T01 замечание не отработано) - conftest",
    "eval --dataset: dir-поддержка из спеки сужена до файла (cases.json канонический) - отложить/добавить по мере надобности PMM-33",
    "eval_runner _check_numbers/_used_source_refs дублируют правила service.py и в интегрированном пути перекрываются им (тесты ловит service) - одна реализация правил при переносе в PMM-33",
    "cli._load_dataset дублирует load_cases - один владелец формы датасета",
    ".gitignore: добавлена строка logs/ + пустая строка (косметика, drop)"
  ],
  "reviewers": {
    "manifestSpec": "ses_fbb798049ffeQBQNCU5nRzuRqh",
    "craft": "ses_fbb7967e8ffekqeGeAHs8w1H1z"
  },
  "blind": {
    "verdict": "no drift",
    "detail": "все требования брифа реализованы (Q1-Q8а - реализовано; Q10 частично = PR/merge выполняются финальными шагами вне репо). Demo-прогон: 3 сигнала -> диагнозы на русском с refs/alternatives/unknowns, audit-jsonl с sha256; eval 12/12 = 100%. contracts/ и src/proxima/ не тронуты.",
    "commands": "pytest 71 passed; CLI run exit=0 (3/3 ok); CLI eval 12/12 = 100.0%"
  },
  "build_note_next": null
}
