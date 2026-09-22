# Interfaces

## Границы, решённые в спецификации

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `diagnostics` | факт «почему сломалось» | отчёт с находками (ступень, причина, источник) | сырой вывод команд, имена секретов без значений |
| `repair` | дифф починки в репо | ветку с зелёным make verify и разбором по пунктам отчёта | детали конфигов, правки вне находок |
| `deploy` | боевое состояние сервера | активные таймеры, схема 18\|18, ручной прогон SUCCEEDED | значения секретов, шаги с привилегиями |
| `acceptance` | журнал трёх утр и чек-лист | вердикт «3× SUCCEEDED, Mike подтвердил» | ничего |

Шов для проверок один и он существует: гейты репозитория (make verify, гейт §4 репетиции по W10/W35) и чек-лист runbook. Новых швов не заводить.

## Правила проекта, которые таск не выведет сам

- Канон контекста - `AGENTS.md` в корне репо (таблица версий, запреты, where things are). Перед правками кода сверять фактические версии в манифестах, не в таблице.
- Проверки: весь гейт - `make verify` (ожидать строку `pg-roundtrip: PASS`; `SKIP` = миграции не проверены); один vitest-файл - `npm --workspace @proxima/webapp exec -- vitest run <file>`; pytest - только `uv run --python 3.14 --project services/control-plane --extra test pytest …`.
- Нельзя трогать: auth-зона webapp (`src/lib/auth*`, `src/app/api/auth/`, `src/app/login/`), verbatim-дерево `services/control-plane/src/proxima/`, миграции `db/migrations/NNN_*.sql` (только новая NNN+1), сгенерированные `services/collector/src/contracts/*.ts` (править `contracts/*.schema.json` + `make codegen`), sibling-worktrees.
- WB API - только READ; живых вызовов из тасков нет, если таск прямо не говорит иного (их в этом прогоне нет).
- Секреты: значения не печатать и не коммитить - только имена переменных/файлов; на VPS живут в `/etc/proxima-ai/secrets/` (0600).
- Деплой и любой шаг с привилегиями на VPS - только после явного слова «деплой» от Mike в чате; до него сервер только читается.
- Коммиты: английский, conventional-префикс; стейджить только свои файлы; ветка прогона `autopilot/morning-brief-live` (база `main`), мерж - не в таске.
- Не хватает зависимости/доступа - таск возвращается `BLOCKED` с причиной, ничего не устанавливается и не настраивается молча.

## Из таска 02 - runbook и правило D01

- Правило D01: деплой 1.14 поднимает webapp в `WEBAPP_DATA_MODE=postgres` (overlay `infra/webapp.staging.compose.yaml`), ручной контейнер `proxima-webapp-staging` снимается до `up` (порт 3000). Форма: `docker compose -f infra/compose.yaml -f infra/webapp.staging.compose.yaml up -d --build webapp` из `/srv/proxima-ai/repo`.
- Runbook `release-m01.md` §1.1/§2/§7 согласованы на postgres-режим; откат - `down` без `-v`, возврата на фикстуры в §7 нет.
- Локальная среда `mckenzie` без make/uv: полный `make verify` не гоняется - гейт добирает CI на PR (CI жив); локально гоняются npm test (130), typecheck, webapp vitest (120)/lint.
