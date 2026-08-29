# Autopilot Run: PMM-29 - контракты signal / diagnosis / decision-record

```yaml
run_id: 2026-08-28-pmm29-contracts
task: "PMM-29 (эпик PMM-3, W1-срез)"
status: dispatched
mode: autopilot-semi
worker: codex (orca worktree pmm29-contracts)
coordinator: opencode main session
created: 2026-08-28
DISCOVERY_STATUS: READY
```

## Цель

Три продуктовых контракта v1 в `contracts/` + синтетические примеры + TS codegen + контрактные тесты. Полная спека: Jira PMM-29 (описание исчерпывающее), контекст: PRD `_bmad-output/planning-artifacts/prds/prd-PROXIMA-AI-2026-08-28/prd.md`.

## Файлы

- `contracts/signal.schema.json`, `contracts/diagnosis.schema.json`, `contracts/decision-record.schema.json`
- `contracts/examples/*.synthetic.json` (позитив + негативные)
- `services/collector/src/contracts/` - generated через `make codegen`
- Контрактный тест по образцу `services/collector/tests/intake-contract.test.ts`

## Запреты

- Не трогать `contracts/source-artifact|acquisition-attempt|domain-release.schema.json` (M1)
- Generated-файлы руками не править (DEC-001)
- `git add` только пофайлово - в главном дереве чужие незакоммиченные изменения
- Секреты, Makefile, README - не трогать без необходимости
- Не мержить в main - merge только после ревью Mike (гейт координатора)

## DoD

1. `make codegen` даёт TS-типы с AUTO-GENERATED баннером
2. `make verify` зелёный (включая цель contracts: позитивные примеры валидны, негативные падают с указанием поля)
3. ₽-оценка без `method` = невалидна
4. Контрактные тесты с обеих сторон (TS Ajv + python verify)
5. Атомарный коммит в worktree-ветке + отчёт координатору: список файлов, sha, вывод verify

## Приёмка (координатор)

worker_done → reviewer по diff → make verify на worktree → ревью Mike → merge.
