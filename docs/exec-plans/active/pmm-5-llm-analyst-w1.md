> **Статус на 03.09.2026: неактивен.** План относится к рамке M1/W1, снятой решением D2 (30.08.2026) в пользу лестницы M-00..M-05. Действующая нарезка - `_bmad-output/planning-artifacts/epics.md`, состояние - `STATE.md` и `docs/agent-system/HANDOFF.md`. Файл сохранён как история.

# Exec Plan: PMM-5 LLM Analyst W1 (SCN-008/001/005, primary + alternatives + unknowns)

| Поле | Значение |
|---|---|
| Задача | [PMM-5](https://zhamba.atlassian.net/browse/PMM-5) (parent PMM-3, epic PMM-1) |
| Worktree | `pmm-5-llm-analyst-w1-scn-008-001-005-primary-unk` |
| Ветка | `pmm-5-llm-analyst` |
| Статус | Approved brief (грилль 2026-08-27, 10/10 узлов закрыты Mike) |
| Класс | major (не критическая фаза 3/4/7 - reviewer single-pass, cross-model гейт не требуется) |
| DoD-чеклист | `docs/governance/dod-checklist.md` (PMM-12) применяется |

## 1. Контекст и стратегия

**Q1 - Fixtures-first.** Блокеры PMM-5 (PA-41, PMM-20/23, PMM-29, PMM-31) не выполнены; не ждём их. Вход - структурные fixtures (обезличенные SYNTH-* значения), LLM за адаптером, реальный провайдер включается после PMM-31.

## 2. Ключевые решения грилля

| # | Узел | Решение |
|---|---|---|
| Q2 | Схема диагноза | Внутренняя draft-схема в `services/control-plane` (не `contracts/` - там PMM-29 bot lane, не дублировать). При мерже PMM-29 - перенос в contracts/ + переключение на codegen-типы |
| Q3 | LLM-слой | Интерфейс `LLMClient` + MockLLMClient для тестов/CI + провайдер из конфига (env). Вендор-агностично, PMM-31 заполнит конфиг |
| Q4 | Размещение | `services/control-plane/src/proxima_control_plane/diagnosis/` (adapters/, prompts/, schema/, service.py, cli.py, audit.py). НЕ залезать в будущее verbatim-дерево `proxima/` (PA-41) |
| Q5 | Форма входа | Envelope: `{scenario_id, generated_at, trust: "unreleased", payload, context_extracts, source_refs}`. SCN-008 payload = форма `scn_008_partial.json` (PA-39); SCN-001 = синтетика с декомпозицией U×CVR×AOV; SCN-005 = OOS/days-cover |
| Q6 | Structured output | JSON Schema провайдеру (tool use / response_format где доступен) + строгая валидация jsonschema + retry ×2 → fail-closed. Anti-injection: текстовые поля входа в DATA-ограничителях, structured output - единственный канал выхода. Промпт версионируется |
| Q7 | Eval | Свои ≥12 кейсов на fixtures: schema-valid, все числа output ∈ input, каждый факт с source_ref, adversarial-инъекция, гейт ≥80% pass |
| Q8/8а | Бюджеты | Здесь: флаг `llm_enabled` (rollback §16 тикета), per-signal timeout, JSONL-аудит (ts, signal_id, sha256(input), model, prompt_version, outcome). В PMM-31: дневной token-лимит/кабинет |
| Q9 | Поверхность | CLI `run --input signals.json --output diagnoses.json` + JSON-артефакт с `trust: "unreleased"`. «Daily Brief показывает» = PMM-32 (транспорт), фиксируется комментарием в Jira |
| Q10 | Процесс | Бриф здесь + Jira PMM-5 «В работе» → implementation → eval → make verify → reviewer → PR |

**Фиксации без вопросов:** диагноз на русском, тон объясняющий (№18 интервью); LLM не считает метрики - все числа только из входа (жёсткий запрет №6 репо); fixtures обезличены SYNTH-*; review-поле схемы - расширение PMM-25/PMM-29, здесь не добавляем; jsonschema → main-deps control-plane; демо на ретро - CLI-прогон на eval-датасете с mock-LLM.

## 3. Scope (из тикета PMM-5 §5, §7)

- Диагноз SCN-008 / SCN-001 / SCN-005: primary_cause + 2-3 alternatives + unknowns ≥1 (SCN-005: alternatives ≥2, unknowns ≥1)
- Каждый source_ref указывает на артефакт/таблицу/дату из входа
- Запрещено генерировать числа, отсутствующие во входе
- SCN-001: primary_cause указывает, какой из U/CVR/AOV просел (декомпозиция в fixture)

**Out of scope (тикета):** ₽-оценка (AIOS-DEC-003), verification expected-vs-actual (AIOS-DEC-004), самостоятельный сбор данных LLM, write-действия, чат Q&A, SCN-004/W2+, Independent Reviewer (PMM-25 - наш выход должен быть проверяемым, сам reviewer не здесь), Daily Brief транспорт (PMM-32), token-бюджет (PMM-31).

## 4. Acceptance Criteria (из тикета §11, трактовка fixtures-first)

1. GIVEN сигнал SCN-001 WHEN диагноз THEN primary_cause указывает на декомпозицию (какой из U/CVR/AOV просел), каждый факт с SourceRef
2. GIVEN вход не содержит число Z THEN Z отсутствует в выходе (автотест на eval-датасете)
3. GIVEN SCN-005 THEN alternatives ≥2, unknowns ≥1
4. GIVEN eval-датасет ≥10 кейсов THEN ≥80% SourceRef-полнота, 0 unsupported чисел
5. Reviewer-BLOCK (AC №5 тикета) - интеграция в PMM-25; здесь schema-выход должен быть машино-проверяемым (это и есть подготовка)

## 5. План работ

1. Скелет пакета `diagnosis/`: schema draft (JSON Schema) + validator, models (dataclasses envelope + diagnosis)
2. `adapters/`: `base.py` (LLMClient protocol), `mock.py` (детерминированный генератор валидного диагноза), factory по конфигу
3. `prompts/`: системный промпт (версионированный файл + builder с DATA-ограничителями)
4. `service.py`: DiagnosisService - батч, timeout per signal, флаг llm_enabled (fallback к детерминированному сигналу), JSONL-аудит
5. `cli.py`: run --input/--output
6. Eval-датасет ≥12 кейсов + eval-раннер (детерминированные критерии)
7. Тесты: schema validation, no-hallucinated-numbers, SourceRef-полнота, alternatives/unknowns покрытие (SCN-005), adversarial-инъекция, fallback-флаг, timeout, audit-log поля, latency ≤5 мин на eval-батче
8. `make verify` + reviewer + PR `pmm-5-llm-analyst` → merge (после review)

## 6. Верификация

- `uv run pytest services/control-plane/tests` (Python 3.14 через uv, НЕ системный)
- `make verify` на финише (полный стек)
- Reviewer subagent по завершении (0 blocker / 0 warning)
- DoD-чеклист PMM-12 в Jira-комментарии

## 7. Риски

- Расхождение draft-схемы с будущей PMM-29 → схема помечена draft + указатель; перенос - механический
- PA-41 verbatim-импорт позже может конфликтовать по путям → наш код строго вне `proxima/`
- Real-provider поведение неизвестно до PMM-31 → контракт адаптера покрывает tool use и response_format варианты
