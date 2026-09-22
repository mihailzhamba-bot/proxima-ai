# Spec - host-harper-audit

## Результат

Ветка `docs/d42-grill-plan` в origin содержит: D42 (уже в ветке), `docs/state/HOST-harper.md`, раздел 22.09 в `HANDOFF.md`/`TASKS.md`, шапки-указатели в двух стейт-доках. Mike открывает и мержит PR.

## Границы

- Тела `RELEASE-READINESS-1.14.md` и `INVENTORY.md` не переписываются - только вставка в шапку.
- Ничего не удаляется (30 ГБ архива - только список кандидатов в HOST-harper.md).
- `server/loop-continuous`, системные юниты, VPS, живые WB-вызовы - не затрагиваются.
- Значения секретов не читаются и не выводятся; упоминаются только имена файлов/путей.

## Словоупотребление

- «mainline» - линия `origin/main`; «LOOP» - линия `server/loop-continuous` (orphan-история, без merge-base с main).
- «verify PASS» - полный `make verify` с `pg-roundtrip: PASS`, как зафиксировано 22.09 на `08043bb`.

## Критерии приёмки

1. `git ls-remote origin` содержит `docs/d42-grill-plan` (=R01).
2. Файлы R02-R04 присутствуют в ветке, шапки - вставками, дифф тел пуст.
3. Коммиты атомарные, английские, conventional.
