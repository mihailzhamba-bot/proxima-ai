# 02 — Generated TypeScript types and Ajv contract tests

**Требования:** R01-R05, R07, R38-R39, R44-R47
**Blocked by:** 01
**Зона:** `services/collector/src/contracts/`, `services/collector/tests/product-contracts.test.ts`
**Волна:** 2
**Status:** ready

## Что должно заработать

After T01 lands, codegen creates generated TypeScript types for all three schemas. A real Ajv2020 suite validates positive and negative cases for every schema and checks expected error paths. The full repo gate is green.

## Из брифа, дословно

> «make codegen - TS-типы с баннером AUTO-GENERATED»
> «реальная Ajv-валидация, позитив + негатив кейсы на каждую схему»
> «ГОТОВНОСТЬ: npm install в worktree перед прогоном; make codegen; make verify зелёный»

## Разделы спецификации

Решения: Verification и generated types; Границы и швы.

## Критерии приёмки

- [ ] `npm install` completes in the worktree without dependency changes.
- [ ] `make codegen` generates three TypeScript files with the exact AUTO-GENERATED banner.
- [ ] Ajv2020 strict + allErrors + ajv-formats tests cover positive and negative fixtures for signal, diagnosis and decision-record.
- [ ] Negative assertions inspect `instancePath` or `missingProperty`, not only boolean false.
- [ ] `make verify` passes; only owned files are staged; no merge/push is performed.

## Проверка

`npm test -- --test-name-pattern=product-contracts`, `make codegen`, then `make verify`.
