# 02 — Сервис диагноза: fail-closed pipeline, аудит, флаг rollback, CLI

**Требования:** R08, R13, R16, R17, R22, R24, R25, R28i
**Blocked by:** 01
**Зона:** `services/control-plane/src/proxima_control_plane/diagnosis/` (service.py, audit.py, cli.py), `services/control-plane/tests/`
**Волна:** 2
**Status:** ready

## Что должно заработать

Сквозной путь «батч сигналов → диагнозы» через CLI: каждый сигнал идёт через LLM (mock), строгую валидацию, проверку «числа только из входа» и «source_refs из входа», с retry ×2 и fail-closed. Зависший/сломанный сигнал изолируется (failed/timeout), флаг llm_enabled=false деградирует систему без вызова LLM, каждый вызов логируется в JSONL.

## Из брифа, дословно

> «выход строго валидируется jsonschema, при невалидном - retry до 2 раз, потом fail-closed (диагноз не выдаётся)»
> «все числа output ∈ input, каждый факт с source_ref»
> «flag llm_enabled в конфиге (rollback §16, деградация к детерминированному сигналу), per-signal timeout, JSONL-аудит вызова (ts, signal_id, sha256(input), model, prompt_version, outcome)»
> «CLI run --input/--output + JSON-артефакт»

## Разделы спецификации

Истории 1, 10, 12, 14, 15, 16, 18, 24; Решения: валидация/fail-closed, retry/timeout, флаг rollback, аудит, CLI; Границы: service, audit, cli.

## Критерии приёмки

- [ ] `service.run_batch(signals, config) -> BatchResult`: per-signal изоляция - failed/timeout не роняют батч
- [ ] Невалидный ответ LLM: retry до 2 повторных вызовов, затем item status=failed с reason; число attempts в аудите
- [ ] Timeout (default 90с из конфига): item status=timeout, батч продолжается
- [ ] Детерминированные проверки: все числа в строках диагноза ∈ числа входа (regex-извлечение); source_refs ⊆ input.source_refs; нарушение → fail-closed
- [ ] `llm_enabled=false`: все items status=skipped_flag, LLM не вызывается (mock считает вызовы), форма артефакта совместима
- [ ] `audit.py`: JSONL-строка на сигнал {ts, signal_id, scenario_id, input_sha256, model, prompt_version, outcome, attempts, latency_ms}; ошибка записи не роняет диагноз
- [ ] `cli.py`: `run --input signals.json --output diagnoses.json [--config x.toml]`; exit 0 - батч обработан, 2 - ошибка входа/конфига; output парсится: {generated_at, items: [{signal_id, status, diagnosis?|error?}]}
- [ ] Тесты через шов LLMClient: битый JSON → failed после retry×2; медленный клиент → timeout; флаг off → skipped_flag; аудит-поля присутствуют
