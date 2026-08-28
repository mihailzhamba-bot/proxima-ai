# Манифест требований

Источник: `2026-08-27-brief.md` (Jira PMM-5 + грилл 10/10, ответы Mike). Строку из этого списка может снять **только пользователь**.

| ID | Из брифа (дословно) | Статус | Основание | Где |
|----|---------------------|--------|-----------|-----|
| R01 | «Диагноз сигналов SCN-008, SCN-001, SCN-005: primary hypothesis + 2-3 альтернативы + unknowns» | done | f818e62 (T01-доля) | T01 |
| R02 | «Тон объясняющий (№18); каждый факт со SourceRef (№19)»; «диагноз на русском» | done | f818e62 (T01-доля) | T01 |
| R03 | «Вход: только verified/staging сигналы с маркировкой доверия `unreleased`» | done | f818e62 (T01-доля) | T01 |
| R04 | «Декомпозиция U×CVR×AOV для SCN-001 как контекст диагноза» | done | 8856274 | T03 |
| R05 | «Вход: signal payload (детекторы) + контекст-выдержки»; Q1: «Fixtures-first... Не ждём никого» | done | 8856274 | T03 |
| R06 | «Выход: structured output (JSON-schema): primary_cause, alternatives[], unknowns[], source_refs[], confidence_note» | done | f818e62 (T01-доля) | T01 |
| R07 | «Каждый source_ref указывает на конкретный артефакт/таблицу/дату» | done | 8856274 | T03 |
| R08 | «Запрещено генерировать числа, отсутствующие во входе»; запрет №6 репо: «LLM не считает метрики» | done | 3c53bf4 (T02-доля) | T02+T03 |
| R09 | AC: «GIVEN сигнал SCN-001 ... THEN primary_cause указывает на декомпозицию (какой из U/CVR/AOV просел)» | done | 8856274 | T03 |
| R10 | AC: «GIVEN сигнал SCN-005 (OOS) ... THEN alternatives содержат ≥2 гипотезы и unknowns ≥1» | done | 8856274 | T03 |
| R11 | AC: «GIVEN eval dataset (≥10 кейсов W1) WHEN прогон THEN ≥80% кейсов проходят проверку SourceRef-полноты; 0 unsupported чисел» | done | 8856274 | T03 |
| R12 | Test plan: «unit: schema валидация structured output» | done | 8856274 | T03 |
| R13 | Test plan: «integration: сигнал → диагноз ... на staging fixtures (без живого токена)» | done | 3c53bf4 (T02-доля) | T02+T03 |
| R14 | §14: «Промпт-инъекция через текстовые поля: вход экранируется, structured output - единственный канал выхода»; test plan: «adversarial» | done | f818e62 (T01-доля) | T01+T03 |
| R15 | §8: «latency budget: диагноз батча сигналов утреннего цикла ≤ 5 мин» | done | 8856274 | T03 |
| R16 | §8: «auditability: все вызовы логируются (input hash, model, версия промпта)»; Q8а: «JSONL-аудит (ts, signal_id, sha256(input), model, prompt_version, outcome)» | done | 3c53bf4 (T02-доля) | T02 |
| R17 | §16 Rollback: «Флаг отключения LLM-диагнозов: Daily Brief деградирует до детерминированных сигналов без диагноза (fallback без LLM)» | done | 3c53bf4 (T02-доля) | T02 |
| R18 | Q2: «Внутренняя draft - ... внутри control-plane ..., помечена draft + указатель на PMM-29. Не трогаем contracts/ (bot lane)» | done | f818e62 (T01-доля) | T01 |
| R19 | Q3: «интерфейс LLMClient ... + mock-провайдер для CI/тестов + провайдер из конфига (env ...)»; «вендор-агностично» | done | f818e62 (T01-доля) | T01 |
| R20 | Q4: «services/control-plane/src/proxima_control_plane/diagnosis/ (adapters/, prompts/, schema/, service.py, cli.py ...)»; «Не задеваем future verbatim-дерево proxima/ (PA-41)» | done | f818e62 (T01-доля) | T01 |
| R21 | Q5: «DiagnosisInput = {scenario_id, generated_at, trust: "unreleased", payload, context_extracts, source_refs}»; payload: SCN-008 = форма scn_008_partial.json, SCN-001 = U×CVR×AOV, SCN-005 = OOS/days-cover | done | f818e62 (T01-доля) | T01 |
| R22 | Q6: «JSON Schema провайдеру ..., retry до 2 раз, потом fail-closed»; «текстовые поля входа в ограничителях DATA»; «промпт версионируется» | done | f818e62 (T01-доля) | T01+T02 |
| R23 | Q7: «Свои ≥12 кейсов ...: schema-valid, все числа output ∈ input, каждый факт с source_ref», + adversarial-кейс + кейс «числа Z нет во входе»; «Формат датасета расширяемый для PMM-33» | done | 8856274 | T03 |
| R24 | Q8а: «остаётся: flag llm_enabled ..., per-signal timeout, JSONL-аудит ...; Уезжает в PMM-31: дневной token-лимит» | done | 3c53bf4 (T02-доля) | T02 |
| R25 | Q9: «CLI run --input/--output + JSON-артефакт»; «Daily Brief ... = PMM-32 (транспорт)»; fixtures SYNTH-* (запрет №5 репо) | done | 3c53bf4 (T02-доля) | T02 |
| R26 | Q10: «ветка pmm-5-llm-analyst, implementation + eval + make verify ... + reviewer subagent ... + PR»; DoD-чеклист PMM-12 по завершении | in-ticket | — | T03+финальные фазы |
| R27i | *(подразумевается)* jsonschema - runtime-зависимость control-plane (валидация в прод-пути, не только в тестах) | done | f818e62 (T01-доля) | T01 |
| R28i | *(подразумевается)* CLI читает конфиг (флаг llm_enabled, timeout, провайдер) из файла/окружения; секреты - только имена, значения вне кода | done | f818e62 (T01-доля) | T01+T02 |
| R29 | Out of Scope тикета: «₽-оценка ...; verification expected vs actual ...; Самостоятельный сбор данных LLM; любые write-действия; чат Q&A; SCN-004 маржа / W2+ сценарии» | deferred | Out of Scope PMM-5 §6 + гриль Q9/Q8а | spec Out of Scope |
| R30 | Independent Reviewer BLOCK-режим (AGT-002, PMM-25) | deferred | PMM-25 - отдельная задача, «наш выход должен быть проверяемым» | spec Out of Scope |
| R31 | Daily Brief показывает диагноз (транспорт/рендер) | deferred | Q9: «выполняется на PMM-32 (транспорт)»; комментарий в Jira PMM-5 | spec Out of Scope |
| R32 | Дневной token-лимит/кабинет и enforcement | deferred | Q8а: «Уезжает в PMM-31» | spec Out of Scope |
