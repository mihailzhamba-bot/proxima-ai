# Interfaces — PMM-5 LLM Analyst W1

## Границы, решённые в спецификации

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `models.py` | envelope DiagnosisInput, Diagnosis, BatchItem, BatchResult; парсинг/сериализация | `parse_signal(raw)->DiagnosisInput`, `diagnosis_to_dict()`, `batch_to_dict()` | правила имён полей |
| `schema/` + `validator.py` | draft-JSON-Schema диагноза + валидация | `validate_diagnosis(obj) -> list[str]` (пусто = ок) | структуру схемы |
| `adapters/` | protocol LLMClient, MockLLMClient, factory | `create_client(config) -> LLMClient`; `diagnose(system, user, schema) -> dict` | как именно mock строит ответ |
| `prompts/` | версионированный системный промпт, DATA-обёртка | `build_messages(signal) -> (system, user, prompt_version)` | шаблон промпта |
| `service.py` | оркестрация: retry, timeout, флаг, числа-проверка, аудит | `run_batch(signals: list[DiagnosisInput], config) -> BatchResult` | порядок проверок |
| `config.py` | DiagnosisConfig, TOML-загрузка, дефолты | `load_config(path) -> DiagnosisConfig` | поиск файла |
| `audit.py` | JSONL-писатель | `AuditLog(path).record(entry)` | формат строки |
| `cli.py` | argv-поверхность | `main(argv) -> int` | всё остальное |
| `eval_runner.py` | датасет-критерии, pass-rate | `run_eval(cases, client) -> EvalReport` | правила number-extraction |

**Шов для тестов - один:** `LLMClient` (в тесты всегда подставляется Mock, в т.ч. ломающиеся варианты: битый JSON, инъекция, числа-не-из-входа). Поведение проверяется через `service.run_batch` / `cli.main` / `eval_runner.run_eval`.

**Ключевые формы** (проза хуже кода):

```
DiagnosisInput = {signal_id, scenario_id: "SCN-001"|"SCN-005"|"SCN-008", generated_at,
                  trust: "unreleased", payload: dict, context_extracts: list, source_refs: list[str]}
Diagnosis      = {schema_version, signal_id, scenario_id, trust, primary_cause: {hypothesis, source_refs[]},
                  alternatives: [{hypothesis, source_refs}] (2..3), unknowns: [{question, why_it_matters}] (>=1),
                  confidence_note, model, prompt_version, generated_at}
BatchItem      = {signal_id, status: "ok"|"failed"|"timeout"|"skipped_flag", diagnosis?|error?}
BatchResult    = {generated_at, items: [BatchItem]}
AuditEntry     = {ts, signal_id, scenario_id, input_sha256, model, prompt_version,
                  outcome: "ok"|"failed"|"timeout"|"skipped_flag", attempts, latency_ms}
Config (TOML)  = llm_enabled(bool, default true), provider(str, default "mock"), model(str),
                 base_url(str, опционально), api_key_env(str, имя env), timeout_seconds(int, default 90),
                 audit_path(str, default "logs/diagnosis-audit.jsonl")
```

## Правила проекта (субагенту нельзя выводить самому)

- Python только через `uv` (3.14), НЕ системный 3.9. Тесты: `uv run pytest services/control-plane/tests` из корня репо.
- Полный verify: `make verify` (финал, не на каждый шаг). Локальный быстрый прогон: pytest + typecheck-стек не требуется для control-plane (нет mypy-гейта на пакет) - pytest достаточен.
- Зона строго `services/control-plane/`. НЕ трогать: `contracts/` (PMM-29 bot lane), `services/collector/`, `services/control-plane/src/proxima/` (future verbatim-дерево PA-41), sibling-worktrees `Опрос-v2.2` и `torgstat-collector`.
- Секретов нет нигде: в конфиге - только имя env-переменной (`api_key_env`). Никаких реальных cabinet ID/SKU/цен - только SYNTH-* значения.
- LLM не считает метрики: все числа в диагнозе приходят из входа; проверка детерминированная (regex-извлечение чисел).
- Каждый факт в диагнозе - с source_ref из input.source_refs.
- Тексты диагноза - на русском, объясняющий тон.
- Зависимость не ставится самостоятельно: нет нужного пакета в pyproject → верни BLOCKED (исключение подтверждено брифом: `jsonschema` переезжает в main deps, optional-группа `llm` резервируется пустой).
- Комментарии в коде - без лишнего; идентификаторы на английском, доменные тексты (промпт, diagnosis-строки) на русском.
- Коммит атомарный: `feat(diagnosis): ...` / `test(diagnosis): ...`; один тикет - один коммит (или два: feat+test).

## Из таска 01 - ядро diagnosis

- Пакет: `services/control-plane/src/proxima_control_plane/diagnosis/` (models, validator, config, schema/, prompts/, adapters/)
- `models.parse_signal(raw) -> DiagnosisInput` (ValueError на битый envelope; source_refs обязателен непустой); `Diagnosis.diagnosis_to_dict()`; `BatchResult.batch_to_dict()`
- `validator.validate_diagnosis(obj, version="draft.v1") -> list[str]` (пусто = ок); схема в `schema/diagnosis.draft.v1.json` (+$comment-указатель на PMM-29)
- `LLMClient.diagnose(system, user, schema) -> dict` - runtime-checkable Protocol; `adapters.mock.MockLLMClient` - детерминированный, парсит machine-readable блок DIAGNOSIS_INPUT из user (ValueError без него); `adapters.factory.create_client(config)` - unknown provider → ValueError
- `prompts.builder.build_messages(signal) -> (system, user, "v1")`; `PROMPT_VERSION="v1"`; маркеры BEGIN/END = "DIAGNOSIS_INPUT"/"END_DIAGNOSIS_INPUT"; формат справки numbers=`payload.key=v|...`
- `config.load_config(path|None) -> DiagnosisConfig` (llm_enabled/provider/model/base_url/api_key_env/timeout_seconds/audit_path; частичный TOML мержится с дефолтами; unknown keys → ValueError)
- pyproject: jsonschema==4.25.1 в main deps; optional-группа `llm = []` зарезервирована
- Тест-команда каноническая: `uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests -q` (голый `uv run pytest` от корня НЕ работает)
- ВАЖНО для service.py (таск 02): mock берёт данные из блока DIAGNOSIS_INPUT - перед diagnose() всегда звать build_messages(signal) и передавать user в diagnose

