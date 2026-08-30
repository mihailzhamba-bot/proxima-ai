# Control-plane: LLM-диагноз (PMM-5)

> Перенесено из `AGENTS.md` 30.08.2026 (bmad-project-context). Память автопилота на момент прогона PMM-5 (диагноз сигналов); не текущие требования - актуальное в `/STATE.md`, `/DECISIONS.md`, блоке `bmad:context` в `AGENTS.md`.

## Control-plane: LLM-диагноз (PMM-5, прогон сдан)

Построен слой LLM-диагноза сигналов WB в `services/control-plane` (пакет `proxima_control_plane.diagnosis`): сигнал (payload + context_extracts + source_refs) → промпт → LLM-клиент (mock по умолчанию) → диагноз по JSON-Schema с детерминированной проверкой, что все числа и source_refs взяты из входа → батч-артефакт + JSONL-аудит. Для агентов, дорабатывающих diagnosis (далее по плану: реальный LLM-провайдер и eval-пайплайн). Срез M2/M3 ведётся в Jira-проекте PMM.

## Команды

| Команда | Что делает |
|---------|------------|
| `make verify` | Полный verify-гейт репо (канонический, fail-closed) |
| `scripts/agent/verify` | Быстрый структурный subset для агента |

Тесты diagnosis (голый `uv run pytest` от корня НЕ работает):
```bash
uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests -q
```

CLI batch run (`diagnosis.toml` ищется от cwd вверх, не найден - дефолты):
```bash
uv run --python 3.14 --project services/control-plane python -m proxima_control_plane.diagnosis run --input signals.json --output diagnoses.json [--config diagnosis.toml]
```

CLI eval (печатает pass-rate; полный гейт 0.80 - в `eval_runner.py`):
```bash
uv run --python 3.14 --project services/control-plane python -m proxima_control_plane.diagnosis eval --dataset services/control-plane/tests/diagnosis/data/eval/cases.json
```

## Структура

```
services/control-plane/                         - Python-пакет proxima-control-plane (uv, Python >=3.14; deps: jsonschema)
  src/proxima_control_plane/diagnosis/          - вся построенная диагностика
    models.py                                   - DiagnosisInput/Diagnosis/BatchItem/BatchResult; parse_signal (сценарии SCN-001/005/008, trust=unreleased, source_refs непустой)
    schema/diagnosis.draft.v1.json              - draft-JSON-Schema диагноза; каноническая строится в PMM-29/contracts - НЕ переносить
    validator.py                                - validate_diagnosis(obj) -> list[str] (пусто = ок), jsonschema Draft 2020-12
    adapters/                                   - Protocol LLMClient, детерминированный MockLLMClient, factory.create_client (провайдера кроме mock нет)
    prompts/                                    - system.v1.md (анти-инъекция + запрет считать метрики) + builder.build_messages (DATA-блоки, справка DIAGNOSIS_INPUT, PROMPT_VERSION v1)
    service.py                                  - run_batch: retry невалидного ответа (max 2), timeout без retry, rollback-флаг llm_enabled, детерминизм-проверки чисел/ссылок, аудит
    audit.py / config.py / cli.py               - JSONL-аудит (глотает OSError); TOML-конфиг с дефолтами (provider=mock, timeout 90); CLI run|eval, exit 0/2
  tests/diagnosis/                              - pytest по каждому модулю + eval_runner.py (полные критерии) + data/eval/cases.json (12 кейсов: standard/closed_numbers/adversarial)
contracts/, services/collector/, db/, tools/    - другие треки; зона diagnosis-задач - только services/control-plane
```

## Подводные камни

- Python только через uv (3.14); системный 3.9 не подходит.
- MockLLMClient парсит блок DIAGNOSIS_INPUT из user-сообщения: перед `client.diagnose()` всегда звать `build_messages(signal)`, иначе ValueError.
- Детерминизм-проверка чисел: regex сканирует только текстовые поля (hypothesis/question/why_it_matters/confidence_note); числа из индексов списков входа (`payload.x[0].value` → токен «0») дают ложное срабатывание - в fixtures числовые значения JSON заменены SYNTH-строками.
- Timeout - финал без retry; retry только когда ответ невалиден по схеме или детерминизму.
- CLI возвращает 0, даже если часть сигналов failed (изоляция per-signal); exit 2 - только ошибка конфига/входа; битый envelope становится item failed, а не падением.
- `provider` отличный от mock → ValueError в factory; реального провайдера ещё нет (optional-группа `llm` в pyproject пустая, зарезервирована).
- Секретов нет: в конфиге только ИМЯ env-переменной `api_key_env` (по умолчанию PROXIMA_LLM_API_KEY), значение нигде не задаётся.
- Дефолтный audit_path `logs/diagnosis-audit.jsonl` - вне git (`logs/` в .gitignore).
- Не трогать: `contracts/` (PMM-29), `services/collector/`, `services/control-plane/src/proxima/` (verbatim-дерево PA-41), sibling-worktrees.
- Тексты диагноза и системный промпт - на русском; идентификаторы кода - английские.

## Как здесь работает Autopilot

Сборка ведётся навыком `/autopilot`. Требования, спецификация и таски — в `.autopilot/`.
Прогресс — `.autopilot/dashboard.html`. Правило: требование из `manifest.md`
может снять только пользователь.

Если работа продолжается — скажи «продолжи автопилот»: состояние поднимется
из `.autopilot/state.js`, переспрашивать ничего не нужно.

---
