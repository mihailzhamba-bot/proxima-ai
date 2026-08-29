# 01 — Canonical product schemas and verifier

**Требования:** R01, R06, R08-R37, R40-R43
**Blocked by:** none
**Зона:** `contracts/`, `tools/verify_contracts.py`
**Волна:** 1
**Status:** ready

## Что должно заработать

Three Draft 2020-12 v1 schemas define signal, diagnosis and decision-record contracts. Synthetic positive fixtures pass. At least three `-bad-` fixtures fail with schema and field/path diagnostics. Existing M1 contract files remain byte-identical.

## Из брифа, дословно

> «три новые схемы по образцу существующих»
> «Negative примеры должны ПАДАТЬ на tools/verify_contracts.py с указанием поля»
> «не трогать существующие три M1-схемы»

## Разделы спецификации

Решения: Общие правила, Signal, Diagnosis, Decision record, Verification.

## Критерии приёмки

- [ ] Three new schemas use Draft 2020-12, v1 IDs, schema_version const 1, and root closed objects.
- [ ] Signal validates required metadata, W1 scenarios, trust, nullable rub assessment with required method, refs, and detection_data unknown semantics.
- [ ] Diagnosis validates 2-3 alternatives, reviewer, refs and positional assertion-ref invariant.
- [ ] Decision record validates rejected reason condition, metrics shape, horizon > 0, nullable actual/delta, and conditional outcome.
- [ ] Three positive fixtures pass and at least three `-bad-` fixtures fail with paths.
- [ ] `tools/verify_contracts.py` auto-discovers all schemas/examples; Makefile and existing M1 files are unchanged.

## Проверка

`python3 tools/verify_contracts.py` and targeted negative fixture run. Do not run `make codegen` in this ticket.
