# 03 - R2: track claims, file zones, lifecycle и integration lock

**Требования:** R05, R06, R08, R12, G02
**Blocked by:** 01, 02
**Зона:** `tools/now_orchestrator/runtime/` · `scripts/agent/now` · `tools/tests/test_now_runtime.py`
**Волна:** 3
**Status:** ready

## Что должно заработать

`/now go <KEY>` валидирует fresh selection, same-track owner и declared zones, затем atomically создаёт ephemeral claim. Lifecycle идемпотентно resume-ит тот же run, не допускает duplicate worker, сериализует integration и считает Done только после merge и source convergence.

## Из брифа, дословно

> «Пока не закончим, не касаемся.»
> «он контролирует эти процессы у меня»
> «закрепляет, и мы потом идём дальше»
> «полностью автономны агент»

## Разделы спецификации

Истории 9-12, 15-16, 21-22, 32, 34-35; Решения 3, 5-6; Границы `claims`, `lifecycle`.

## Критерии приёмки

- [ ] Start без exact key, fresh snapshot, known Track и non-empty normalized zones отклоняется.
- [ ] Same-track active claim и любое prefix-overlap зон блокируют start до worker creation.
- [ ] Разные Track с disjoint zones допустимы; один global integration lease сериализует integration.
- [ ] Claim/lease создаются atomically в Git common dir; owner release и audited stale recovery проверены тестами.
- [ ] Lifecycle transitions fail closed; repeated `/now go` resumes provenance и не создаёт duplicate task/worker.
- [ ] DONE невозможен без merge commit, Jira/Orca/Git/HANDOFF/TASKS/ExecPlan convergence.

