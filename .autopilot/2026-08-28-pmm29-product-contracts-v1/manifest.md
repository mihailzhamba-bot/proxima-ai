# Манифест требований

Источник: `2026-08-28-brief.md`. Строку из этого списка может снять **только пользователь**.

| ID | Из брифа (дословно) | Статус | Основание | Где |
|----|---------------------|--------|-----------|-----|
| R01 | «продуктовые контракты v1 в contracts/ + codegen + контрактные тесты» | done | T01,T02 | spec → T01,T02 |
| R02 | «Работай в режиме autopilot semi» | done | semi run | T01,T02 |
| R03 | «атомарные шаги, каждый шаг проверяется» | done | per-ticket verify | T01,T02 |
| R04 | «Прочти AGENTS.md в корне перед стартом» | done | completed preflight | T01 |
| R05 | «Node 22 (npm workspace services/collector), Python 3.14 через uv (tools/)» | done | toolchain constraints | T02 |
| R06 | «Контрактные схемы в contracts/ (JSON Schema Draft 2020-12)» | done | schema contract | T01 |
| R07 | «TS-типы генерируются make codegen в services/collector/src/contracts/ - руками не редактировать (правило DEC-001)» | done | codegen boundary | T02 |
| R08 | «tools/verify_contracts.py итерирует contracts/*.schema.json и валидирует contracts/examples/*.synthetic.json - новые схемы подхватятся без правок кода» | done | verifier auto-discovery approved | T01 |
| R09 | «три новые схемы по образцу существующих (contracts/source-artifact.schema.json - структура» | done | three schemas | T01 |
| R10 | «$id стиль https://proxima.local/contracts/<name>/v1» | done | v1 IDs | T01 |
| R11 | «additive-only версионирование: новые поля опциональны, удаление/смена типа = новая мажорная версия» | done | version rule | T01 |
| R12 | «contracts/signal.schema.json - детерминированный сигнал детектора» | done | signal schema | T01 |
| R13 | «signal_id (uuid/строка)» | done | non-empty string | T01 |
| R14 | «scenario_code (enum: SCN-001 \| SCN-005 \| SCN-008 - расширяемый под W2)» | done | W1 enum | T01 |
| R15 | «snapshot_id (обязателен, формат как в существующих схемах - воспроизводимость)» | done | opaque reproducibility key | T01 |
| R16 | «tenant_id, created_at (ISO 8601)» | done | metadata formats | T01 |
| R17 | «trust_marking (enum: unreleased \| released - обязательное поле)» | done | trust enum | T01 |
| R18 | «rub_assessment (объект {value_rub: number, method: enum revenue\|profit} - method ОБЯЗАТЕЛЬЕН внутри объекта» | done | conditional method | T01 |
| R19 | «сам rub_assessment nullable = оценка неизвестна» | done | nullable assessment | T01 |
| R20 | «source_refs (массив непустых строк-ссылок на артефакт/таблицу/дату, minItems 1)» | done | refs constraints | T01 |
| R21 | «поля данных обнаружения nullable с явной unknown-семантикой (unknown = null + соседнее boolean-поле is_unknown, ноль не является unknown)» | done | accepted detection_data shape | T01 |
| R22 | «contracts/diagnosis.schema.json - выход LLM-диагноза» | done | diagnosis schema | T01 |
| R23 | «LLM НЕ генерирует числа, все цифры приходят извне» | done | no numeric diagnosis fields | T01 |
| R24 | «signal_id, primary_cause (строка)» | done | diagnosis fields | T01 |
| R25 | «alternatives (массив 2-3 строк), unknowns (массив строк)» | done | arrays constraints | T01 |
| R26 | «source_refs (minItems 1 - каждое утверждение имеет ссылку), confidence_note (строка)» | done | positional refs invariant | T01 |
| R27 | «reviewer (объект {verdict: enum pass\|block, model: string})» | done | reviewer object | T01 |
| R28 | «contracts/decision-record.schema.json - запись решения AM (append-only)» | done | decision schema | T01 |
| R29 | «signal_id, decision (enum: accepted \| rejected), actor (строка), decided_at (ISO 8601)» | done | decision fields | T01 |
| R30 | «reason (nullable: обязательна при rejected - вырази через if/then на JSON Schema)» | done | conditional reason | T01 |
| R31 | «expected (объект {metrics: array, horizon_days: integer > 0})» | done | accepted metrics shape | T01 |
| R32 | «actual (nullable - null означает статус «открыто», решение ещё не проверено), delta (nullable)» | done | nullable same metrics shape | T01 |
| R33 | «outcome (enum: confirmed \| refuted \| partial \| unknown; обязательным становится только при непустом actual - вырази через if/then)» | done | conditional outcome | T01 |
| R34 | «contracts/examples/signal.synthetic.json, diagnosis.synthetic.json, decision-record.synthetic.json - валидные примеры» | done | positive fixtures | T01 |
| R35 | «Плюс минимум 3 негативных примера» | done | negative fixtures | T01 |
| R36 | «Negative примеры должны ПАДАТЬ на tools/verify_contracts.py с указанием поля» | done | negative diagnostics | T01 |
| R37 | «Проверь, как существующий verify_contracts.py отличает валидные примеры от негативных ... - следуй тому же механизму» | done | mechanism documented | T01 |
| R38 | «make codegen - TS-типы с баннером AUTO-GENERATED» | done | generated output | T02 |
| R39 | «Контрактный тест TS по образцу services/collector/tests/intake-contract.test.ts: реальная Ajv-валидация, позитив + негатив кейсы на каждую схему» | done | Ajv suite | T02 |
| R40 | «не трогать существующие три M1-схемы ... и их examples; generated-файлы руками; секреты; Makefile ...; README/docs» | done | safety boundary | T01,T02 |
| R41 | «git add ТОЛЬКО пофайлово для своих файлов ... их не трогать и не коммитить» | done | staged paths only | T01,T02 |
| R42 | «Не мержить в main» | done | handoff boundary | T02 |
| R43 | «Не выдумывать данные: в примерах синтетические значения (fixture-стиль), не реальные SKU/цены» | done | synthetic fixtures | T01 |
| R44 | «npm install в worktree перед прогоном; make codegen; make verify зелёный» | done | verification sequence | T02 |
| R45 | «список созданных файлов, sha атомарного коммита (ветка worktree), вывод make verify» | done | final report | T02 |
| R46 | «список AC из задачи PMM-29 Jira с отметкой выполнено/нет» | done | final report | T02 |
| R47 | «Остановиться и ждать ревью координатора - merge не делать» | done | final handoff | T02 |
