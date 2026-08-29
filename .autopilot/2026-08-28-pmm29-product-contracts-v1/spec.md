# Спецификация: PMM-29 product contracts v1

## Задача

Детекторы, LLM Analyst, Decision Memory и web-кабинет должны читать один версионируемый контракт. Несовместимое изменение должно обнаруживаться локальным и CI-гейтом до runtime.

## Решение

Появятся три канонические JSON Schema Draft 2020-12: детерминированный signal, структурированный diagnosis и append-only decision record. Для каждой схемы будут synthetic positive/negative examples, generated TypeScript types и Ajv-контрактные тесты. Python verifier будет автоматически находить все `contracts/*.schema.json`, а negative fixtures - проверяться fail-closed с путём ошибки.

## Пользовательские истории

| # | Метка | История | Приёмка |
|---|-------|---------|---------|
| 1 | R01,R06,R09,R10,R11,R12 | Как consumer контракта, я получаю три v1-схемы в каноническом пространстве имён | три новых Draft 2020-12 object schemas; `$id` соответствует `https://proxima.local/contracts/<name>/v1`; existing M1 schemas unchanged |
| 2 | R13,R14,R15,R16,R17,R18,R19,R20,R21 | Как детектор, я публикую воспроизводимый signal с trust, ₽-методом, refs и явным UNKNOWN | Ajv принимает valid signal и отвергает неверный enum, пустой ref, пропущенный method; `null + is_unknown:true` не смешивается с `0 + false` |
| 3 | R22,R23,R24,R25,R26,R27 | Как LLM Analyst, я отдаю diagnosis без расчёта чисел и с reviewer verdict | schema принимает 2-3 alternatives, refs и reviewer; числовые значения не являются полями diagnosis |
| 4 | R28,R29,R30,R31,R32,R33 | Как AM, я создаю append-only decision record и закрываю его только фактом verification | rejected требует непустой reason; `actual:null` оставляет open; непустой actual требует outcome; horizon_days > 0 |
| 5 | R34,R35,R36,R37 | Как CI, я проверяю positive и negative synthetic fixtures и показываю поле ошибки | три positive проходят; минимум три negative отклоняются Python verifier с `schema` и JSON path/field в сообщении |
| 6 | R38,R39 | Как TypeScript consumer, я использую generated types и реальный Ajv test seam | `make codegen` создаёт banner `AUTO-GENERATED`; один TS suite покрывает positive/negative для всех трёх схем |
| 7 | R02,R03,R04,R05,R07,R08,R40,R41,R42,R43,R44,R45,R46,R47 | Как владелец release, я получаю атомарный, проверенный и ограниченный diff | Node 22/npm workspace и uv Python 3.14 соблюдены; Makefile и чужие файлы не изменены; `make verify` зелёный; merge не выполняется |

## Решения по реализации

### Общие правила

- Все три schema используют `$schema` Draft 2020-12, root `type: object`, `additionalProperties: false`, `schema_version: {"const": 1}` и required `schema_version`.
- Все `$id` используют `https://proxima.local/contracts/<name>/v1`.
- ID и refs - non-empty strings. ISO timestamps используют `format: date-time`.
- Новые v1-поля, добавляемые в следующих совместимых версиях, optional; удаление или смена типа требует нового major `$id`.
- Existing `source-artifact`, `acquisition-attempt`, `domain-release` schemas и examples не редактируются.

### Signal

Required: `schema_version`, `signal_id`, `scenario_code`, `snapshot_id`, `tenant_id`, `created_at`, `trust_marking`, `rub_assessment`, `source_refs`, `detection_data`.

- `signal_id`, `tenant_id` - non-empty strings; `snapshot_id` is an opaque non-empty reproducibility key. Producers must keep it byte-identical for the same input snapshot; synthetic fixtures use `SYNTH-SNAP-*` (the schema deliberately does not impose a lowercase regex because existing consumers use opaque uppercase IDs). `scenario_code` - `SCN-001 | SCN-005 | SCN-008`; `trust_marking` - `unreleased | released`.
- `created_at` - ISO 8601 date-time.
- `rub_assessment` - object or null. Object requires `value_rub` number and `method` enum `revenue | profit`; null means estimate unknown.
- `source_refs` - array of non-empty strings, `minItems: 1`.
- `detection_data` - object whose keys are scenario-specific lower snake-case names. Each value is an object with required `value` and `is_unknown`; `value` accepts number/string/boolean/null, `is_unknown` is boolean. `value:null` is UNKNOWN only when `is_unknown:true`; zero with `is_unknown:false` is a measured zero. This keeps W2 keys additive without inventing a fixed scenario field list.

### Diagnosis

Required: `schema_version`, `signal_id`, `primary_cause`, `alternatives`, `unknowns`, `source_refs`, `confidence_note`, `reviewer`.

- `primary_cause`, `confidence_note`, and every array item are non-empty strings.
- `alternatives` has 2-3 items. `unknowns` is an array of strings and may be empty.
- `source_refs` has non-empty strings and maps one-to-one to assertions by deterministic order: index 0 is `primary_cause`, then one ref per `alternatives` item, then one ref per `unknowns` item. The verifier and contract tests enforce `source_refs.length = 1 + alternatives.length + unknowns.length`, so every assertion has a concrete ref while the user-requested string fields remain intact.
- `reviewer` requires `verdict` (`pass | block`) and non-empty `model`.
- Diagnosis contains no metric calculation fields. Numeric facts remain in external input/source refs.

### Decision record

Required: `schema_version`, `signal_id`, `decision`, `actor`, `decided_at`, `reason`, `expected`, `actual`, `delta`.

- `decision` is `accepted | rejected`; `actor` and `signal_id` are non-empty strings; `decided_at` is ISO date-time.
- `reason` is string or null. Root conditional: when `decision` is `rejected`, `reason` is required and non-empty; accepted may use null.
- `expected` is required object: `metrics` is a non-empty array of `{name, value, unit, source_ref}` and `horizon_days` is integer greater than zero. Metric `name`, `unit`, `source_ref` are non-empty strings; `value` is a number.
- `actual` and `delta` are null or objects with the same `metrics` array shape as expected. Null actual means status `open`.
- Root conditional: when `actual` is not null, `outcome` is required and is `confirmed | refuted | partial | unknown`; when actual is null, outcome is omitted. `delta` remains nullable and records measured difference when available.
- Append-only is a contract invariant: this v1 has no update operation and the record schema has no mutable revision field.

### Verification and generated types

The Python verifier discovers every schema by globbing `contracts/*.schema.json` and associates positive fixtures by `*.synthetic.json`. Negative fixtures use a `-bad-` marker, are validated against the matching schema, and must fail; output includes the fixture name, schema, and validator path. It also enforces the diagnosis positional source-ref invariant. Makefile is not changed.

`make codegen` remains the sole owner of `services/collector/src/contracts/*.ts`; generated files are not hand-edited. The TS test suite compiles each schema with `Ajv2020({allErrors:true, strict:true})` plus `ajv-formats`, asserts valid fixtures, and asserts invalid fixtures with a matching error path or missing property.

Synthetic values use `fixture-*`/`SYNTH-*` identifiers and no real cabinet IDs, SKU, prices, tokens, or credentials.

## Границы и швы

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `contracts` | canonical JSON Schemas, examples, version/conditional rules | schema files consumed by verifier and codegen | generated implementation and consumer runtime behavior |
| `contract-verifier` | schema/example discovery and negative validation diagnostics | `tools/verify_contracts.py` command behavior | Ajv test details and generated type internals |
| `contract-codegen` | schema-to-TypeScript generation | `make codegen` output | handwritten contract types |
| `contract-tests` | real Ajv positive/negative assertions for all three schemas | npm test discovery | production consumers |

Test seam: `contract-tests` reads only canonical schemas and synthetic fixtures, then calls Ajv directly. The Python seam is `tools/verify_contracts.py` over the same files.

## Вне рамок

| Требование | Почему не сейчас |
|---|---|
| R14/R21 - новые W2 scenario enum values or fixed detection field names | v1 keeps the explicit W1 enum and extensible key map; W2 adds fields/major contract only when specified |
| R22/R23 - LLM runtime integration or numeric calculation | PMM-29 supplies the output contract; PMM-5/31 own runtime and deterministic calculations |
| R28/R32 - database persistence and append-only API | PMM-26 owns storage/API; this task only encodes the record contract |
| R40 - existing M1 schema/example changes | explicitly forbidden by the brief |
| R40/R42 - README/docs edits, merge, deploy, Jira writes | explicitly forbidden; coordinator review follows worker_done |

## Открытые места

Нет. Все briefing decisions закрыты: verifier modification accepted 2026-08-28; `detection_data` accepted 2026-08-28; metrics/actual/delta shape and open status accepted 2026-08-29.

## Покрытие манифеста

| Требования | Раздел спецификации |
|---|---|
| R01-R11 | Решения: Общие правила; История 1 |
| R12-R21 | Решения: Signal; История 2 |
| R22-R27 | Решения: Diagnosis; История 3 |
| R28-R33 | Решения: Decision record; История 4 |
| R34-R37 | Решения: Verification; История 5 |
| R38-R39 | Решения: Verification и generated types; История 6 |
| R40-R47 | Решения: Общие правила, Verification; История 7; Вне рамок |
