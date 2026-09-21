# HANDOFF — PROXIMA AI

## Fix-ран по находкам Code Review Crew (tier 1 + 1.5) - 2026-09-20

Ветка `fix/loop-pilot-review-tier1` (от `8d23519`), PR без merge - merge и deploy за Mike. Реализованы 8 требований из протокола адверсариального ревью PR #140: guard `/brief` на истёкшей сессии, ISO-таймстемпы задач (JSC/iOS), честный 409 на ре-подтверждение отменённого сигнала, вердикт наблюдения прибит к дню конца горизонта, стоп-клин childless paperclip (upstream-подтверждение + идемпотентный `/stop` + защита от регресса `cancelled`→`cancelling`), 500+traceback+uncertain вместо молчаливого 400 в bridge (диагностика больше не глушится), единая `PAPERCLIP_STATUS_MAP`, bind 127.0.0.1 в example + TLS-требование в OPERATIONS.txt. `make verify` PASS (один SKIP - `pg-roundtrip`, локально нет PG16); лог - `.autopilot/2026-09-20-loop-tier1-fixes--wip/verification.log`; независимый ревьюер: 0 blockers после фикса child-cleanup (ранний возврат `cancelled` только при отсутствии живых children/jobs), 1 warning снят в коде. Follow-ups (tier 2/ниты, не в этой ветке): fail_job ownership, статический bearer `/api/loop/context`, HTTP-таймауты bridge, burn 429-ключа, adopt-no-op, write-only events, рукописные пулы, SSH-словари, контракт `loop-task` без рантайм-потребителя. Примечание: общий чекаут `/root/loop-install/proxima-ai` в момент рана был занят другим агентом (merge-работа PR #89/#98) - работа шла в linked worktree, чужое дерево не тронуто.

## LOOP server runtime - 2026-09-16

LOOP now runs on dedicated LOOP-control (135.106.211.149), with isolated OpenHands on Claudette and verification on Harper. Project worktrees and state are server-side; the Mac project folders were removed after a verified migration. Simone is outside this deployment.

- Canonical operator checkout: `/srv/loop/source/proxima-ai` on LOOP-control. Runtime manual: `/etc/loop/docs/LOOP-manual-Mike.md`, also loaded into the Telegram Director.
- Adaptive research/review: GLM Flash outside weekdays 14:00-18:00 UTC+8 (09:00-13:00 Moscow); OpenAI Luna low / Sol medium according to analysis complexity, Terra medium for independent review. Explicit complex analysis can use Sol high. No automatic ultra/max escalation. OpenHands coding remains Sol medium.
- `loop-work-program.timer` checks bounded research work every five minutes, at most 48 research intents/day, one request at a time, deduplicating unchanged scoped source. Unknown outcomes remain recorded; model output is research data, never execution authority. New arbitrary coding-task admission is not automated.
- Research metadata is projected into Bridge and native Telegram status separately from the coding queue. Models cannot use tools through the private research/review broker.
- After a normal admitted batch, `pause_on_completion=false` can leave the queue available. Cancellation fences, exact-candidate verification and independent receipts remain mandatory. Merge, production deployment and WB actions still need their existing authorization.
- Harper needs 3 GiB free before a batch and 2 GiB during execution. Completed cache copies are hash-verified before authorized removal; keep candidate/evidence records.
- Deployment ownership matters: Bridge config belongs to 10001:10001, Harper runner config to verifier 1000:1000. Preserve ownership during replacement. Import Git packs on Harper as verifier; verify every source file is readable and clone the pinned base as verifier before dispatch.
- Worker prompts must explicitly require one scoped commit. A finished conversation with an uncommitted diff is not a publishable candidate. Never revive a cancelled job; new attempts need new IDs and matching trusted acceptance scope.

Operational evidence is in `/srv/loop/acceptance/adaptive-models-20260916.json`. Current run state must be read from Bridge and Harper, not inferred from this dated note. PR #140 contains the control-plane implementation. Daily operation of the real WB pilot is still a separate acceptance.



## LOOP pilot - код готов к review, 13.09.2026

[PR #140](https://github.com/mihailzhamba-bot/proxima-ai/pull/140), ветка `feat/loop-pilot`, проверенный код `1dfb971b09d873e47aa31e80c9b785bfbbf722b2`.
Baseline `6912a92`; scope: `docs/exec-plans/active/loop-pilot.txt`.
Сохранены сбор, PostgreSQL, календарная норма и SourceRef. Добавлены реальные
BetterAuth-сессии/membership, атомарные решение и задача, личная очередь сотрудника,
evidence/блокер и отдельное наблюдение эффекта. Порог пилота -30% задан планом Mike
13.09.2026. Диагноз основан на кодовых фактах и явно отмеченных гипотезах.

Harper: immutable prepare/make verify/pg-roundtrip/build PASS; scripts/agent/verify
PASS; шесть Linux-тестов publication process PASS. Browser: 41 PASS на synthetic
данных с настоящим PostgreSQL/BetterAuth, проверены light/dark/mobile/keyboard.
Webapp-код после browser-прогона не менялся. GitHub CI на проверенном коде зелёный.
Три control image собраны и прошли изолированные smoke; реальные providers не вызывались.
Подробные commits, hashes и evidence: `docs/exec-plans/active/loop-pilot.verification.json`.

Приёмка кода/PR завершена. Новый LOOP-control не создан, отдельные credentials
и модель Director не настроены; live_ready=false. Полный живой управляющий маршрут,
restore и ежедневная работа кабинета принимаются отдельно. Simone, production и
кабинет WB не изменялись; merge/deploy не выполнялись и требуют решения Mike.
Следующий шаг после review: получить SSH-алиас нового VPS для отдельной подготовки стенда.


> **30.08.2026:** роадмап M1 заменён лестницей M-00..M-05 (см. `/DECISIONS.md` D2, `/STATE.md`, `/docs/state/`). Всё ниже - состояние на 25-29.08, историческое; не считать текущими требованиями до обновления в Сессии 2 (bmad-project-context).

> If the current agent disappears right now, what must the next one know? Update after every meaningful stage.

## День 09.09.2026 - дневной прогон оркестратора (Claude Code, D37)

**Старт (06:15 UTC):** Mike после ночного отчёта - «Так, запускаем задачи дальше в работу»; заморозка D35 снята, в работе все четыре трека. Решение и три ответа Mike записаны в `/DECISIONS.md` D37.

**CI лежит - приёмка по локальному `make verify`.** С 18:34 UTC 08.09 все задания GitHub Actions падают мгновенно, без единого шага и без логов: четыре попытки, включая ручные перезапуски; до 18:30 того же дня всё было зелёное. Вероятная причина - исчерпаны минуты Actions; биллинг проверяет Mike. Пока CI лежит, единица принимается по локальному `make verify` (ровно один `SKIP` - `pg-roundtrip`), мерж выполняет оркестратор. Без CI не проверяются: тесты с базой (`*.db.test.ts`, `test_*_postgres.py`), накат миграций в контейнере (`apply-migrations-in-container`), `systemd-analyze verify` юнитов, сборка образов - всё это надо перепроверить, когда CI вернётся. **Возврат к правилу «мерж только по зелёному CI» - в тот же день, когда CI оживёт**, и следом прогон CI на `main`, чтобы убедиться, что накопленные мержи зелёные.

**Очередь дня - пять единиц по четырём трекам.**

| Единица | Что | Исполнитель |
|---|---|---|
| M1 | репетиция наката миграций 007-018 поверх копии боевой схемы 6 из дампа `/var/backups/proxima/2026-09-09-proxima.sql.gz` на одноразовом compose-проекте; боевая база не трогается; закрывает `docs/state/RELEASE-READINESS-1.14.md` §6 п. 4 | оркестратор |
| M2 | Story 4.4, обвязка порога: значение остаётся незаданным (все три поля `null`) до разметки Владислава (Story 6.3), появляются гейт `threshold: -31 signals, -29 silent, payload carries source` и подпись порога с источником и датой на `/brief` | Codex |
| M3 | подготовка Epic 5: черновик AD для Story 5.0 (`decision_records`, роль `proxima_webapp_writer` только INSERT, RLS `WITH CHECK`, атомарный коммит до закрытия экрана, `orphaned` при откате, синтетический прогон `kind = decision`); принятие AD - за Mike | Claude-субагент (`bmad-architecture`) |
| M4 | разведка «Источники v2»: черновик эпика по остаткам и финансовому отчёту из фактов проб (`docs/state/API-FACTS.md`, разделы про остатки 02.09 и async CSV), без единого живого вызова WB | GLM |
| M5 | шаг воронки в runbook 2.6: раздел в `docs/operations/release-m03.md` (включение `proxima-funnel-v3@`, временный drop-in до ротации PA-13, недельный `proxima-funnel-csv@`, проверки) - по D33 воронка едет тем же тегом 22.09, своей единицы не имеет | GLM |

**Уборка диска (оркестратор, 06:00-06:30 UTC).** Удалены `node_modules` и 48 слитых рабочих копий (32 ГБ), висячие образы и кэш сборки Docker (2 ГБ), 25 песочниц OpenHands от завершённых бесед моста (27 ГБ), три зависших дерева процессов Codex; занятость диска с 96 % до 56 %. Не тронуты: песочницы Дирижёра и других сессий, стенд репетиции `proxima-rehearsal` (нужен для M1), боевые контейнеры.

**Не меняется:** деплоя нет без слова «деплой»; живые вызовы WB - только по явному разрешению; в Jira не пишем; `.github/workflows` не правим; воркер Codex - один одновременно; Claude - резерв и исполнитель части единиц.

**Ждёт Mike:** биллинг GitHub Actions; принятие AD Story 5.0 (M3); решения, оставшиеся с ночи, - `/brief` на стенде и слово на уборку стенда, порт 3000, форма релизного тега 2.6, окно наблюдения 2.6.

### День 09.09.2026, M1 - репетиция наката миграций 007-018 поверх боевого дампа

**Закрыт последний непроверенный шаг готовности 1.14** (`docs/state/RELEASE-READINESS-1.14.md` §6 п. 4): до 09.09 миграции 007-018 нигде не накатывались поверх живой схемы 6 с данными - репетиция D35, CI `apply-migrations-in-container` и `pg-roundtrip` стартуют с пустого тома. На одноразовом compose-проекте `proxima-migtest` (свой postgres `127.0.0.1:5435`, своя сеть, том и секреты, корень `~/orca/migtest`; override снимает initdb-монтирование `db/migrations`, чтобы база поднялась пустой) восстановлен ночной дамп `/var/backups/proxima/2026-09-09-proxima.sql.gz` и поверх него прогнан `apply-migrations` через `control-plane-admin`: exit 0, 007…018 одним проходом (`applied_at` 10:15:17.229 → 10:15:17.519 UTC). Итог: `schema_migrations` `18|18`, 48 объектов в `public` (35 таблиц + 13 вьюх), 58 политик на 24 таблицах, **все строки пилота не изменились** (1220 / 60 / 27 / 11 / 9 / 7 / 2), новые таблицы лестницы созданы и пусты, `provision-runtime-roles.sh` идемпотентен. Сверка со стендом `proxima-rehearsal`, собранным с нуля: колонки 429 = 429, индексы 86 = 86, политики 58 = 58 - расхождений ноль; единственная разница - 48 грантов `SELECT` роли `proxima_diagnostics`, которые боевая база раздаёт автоматически через `pg_default_acl` (роль `NOLOGIN`/`NOBYPASSRLS`, ни одна политика её не называет, под `SET ROLE` - 0 строк из таблиц с RLS: ожидаемо и безвредно). Вторая находка - для отката §7: `pg_dump` одной базы несёт GRANT'ы, но не роли, поэтому restore в чистый кластер падает на `ERROR: role "proxima_diagnostics" does not exist`; роли-грантополучатели надо создавать до restore. Боевой `proxima-ai-postgres-1` не трогался, сервер только на чтение. Протокол и все числа - `docs/state/API-FACTS.md`, раздел «Репетиция наката миграций 007-018 поверх боевого дампа»; ожидания дня релиза - `docs/operations/release-m01.md` §2 и п. 22 «Сверки 08.09.2026».

## Ночь 08-09.09.2026 - автономный прогон оркестратора (Claude Code, D36)

**Итог (18:30 UTC 08.09):** одиннадцать единиц в `main` (#119-#129), очередь исчерпана за 2 ч 51 мин от первого диспатча (15:39 UTC), `blocked` - ни одной, файл STOP не создавался, 12-часовое окно (жёсткая остановка 03:39 UTC 09.09) не понадобилось. Деплоя, живых вызовов WB, записей в Jira и правок `.github/workflows` не было; Дирижёр остался выключенным. Состояние прогона - `~/orca/proxima-ai-night/logs/night-2026-09-08/state.json`, промты и результаты моста - `~/orca/proxima-ai-night/logs/openhands-bridge/<run-id>/`.

| Единица | Ветка | PR | Исполнитель | Фикс-раунды | Мерж (UTC) |
|---|---|---|---|---|---|
| C1 provenance в compose | `fix/compose-provenance-env` | #119 | Fedor (Codex) | 0 | 16:08 |
| G1 `docs/operations/releases/` + `CHANGELOG.md` | `docs/releases-changelog-skeleton` | #120 | GLM | 0 | 16:11 |
| C2 роль аналитика (Story 6.4, без серверной части) | `feat/analyst-role-provision` | #121 | Fedor | 0 | 16:23 |
| G2 DATA-DICTIONARY, миграции 012-018 | `docs/data-dictionary-012-018` | #122 | GLM | 0 | 16:42 |
| C3 метрики дашборда в postgres-режиме | `feat/webapp-metrics-postgres` | #123 | Fedor | 0 | 16:52 |
| C4 тексты `/brief` для `blocked` и несовпадения дня | `fix/webapp-brief-wording-states` | #124 | Fedor | 0 | 16:55 |
| G3 INVENTORY, раздел кода | `docs/inventory-refresh-2026-09-08` | #125 | GLM | 0 | 17:06 |
| G5 черновик runbook 2.6 | `docs/release-m03-runbook-draft` | #127 | Claude-субагент (резерв, полоса GLM стояла) | 0 | 17:43 |
| C6 `proxima-psql-owner` в репозитории | `chore/psql-owner-bootstrap` | #128 | Fedor | 0 | 17:46 |
| C5 бэкап как systemd-юниты | `feat/backup-systemd-units` | #126 | Fedor | 2 (красный `systemd-verify`) | 18:07 |
| G4 дрейф MEMORY/TOOLS | `docs/agent-memory-tools-drift` | #129 | Claude-субагент (попытка GLM - таймаут, exit 5) | 0 | 18:30 |

**Что вошло.**

- **C1 (#119)** - `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID` объявлены в `infra/compose.yaml` у трёх сервисов, пишущих в ledger (`collector`, `control-plane`, `control-plane-admin`); пустое значение нормализуется в SQL `NULL` в TS-ledger, гейт - `tools/tests/test_compose_collector_mounts.py`. Закрывает пункт provenance из readiness §6.
- **C2 (#121)** - `infra/bootstrap/provision-analyst-role.sh`: прямая read-only LOGIN-роль `proxima_analyst` с таймаутами и грантами, файлы URI и пароля `0600 root`, скрипт идемпотентен; таблица грантов и порядок выдачи - `docs/operations/access-provisioning.md`, шаг - в runbook §1.4, есть тест. Блокер B5 упирается теперь только в шаг Mike на сервере.
- **C3 (#123)** - метрики дашборда в postgres-режиме: `orders-day` и `revenue-day` из `fact_cabinet_daily_current`, `freshness` из `data_status_current`; `signals` и `oos-risks` скрыты, `FxBadge` только в fixtures; два SELECT на полосу, уточнение AD-9 записано в memlog.
- **C4 (#124)** - тексты предупреждений `/brief`: «Данных за день нет» для `blocked` и отдельный текст, когда день сводки не совпадает с запрошенным.
- **C5 (#126)** - `infra/systemd/proxima-pg-backup.{service,timer}`: 03:00 МСК, `PROXIMA_RAW_DIR`, алерт по `OnFailure`; в скрипт добавлен guard, в runbook - шаг установки, есть тест.
- **C6 (#128)** - `infra/bootstrap/proxima-psql-owner` вынесен из heredoc runbook §1.4 в репозиторий + `infra/bootstrap/README.md` + тест.
- **G1 (#120)** - `docs/operations/releases/` (README, TEMPLATE, заготовка `2026-09-15-m01.md`) и `CHANGELOG.md` в формате Keep a Changelog с разделом Unreleased за 07-08.09.
- **G2 (#122)** - DATA-DICTIONARY: миграции 012-018 разнесены как существующие таблицы, таблица трёх состояний схемы обновлена.
- **G3 (#125)** - INVENTORY: раздел кода приведён к `main` со схемой 018, серверные факты сохранены с датой перепроверки 08.09.
- **G4 (#129)** - MEMORY/TOOLS: цепочка verify, CAS-путь `/srv/proxima-ai/raw`, имена токенов, `apply-migrations` через `control-plane-admin`, новые артефакты репозитория.
- **G5 (#127)** - `docs/operations/release-m03.md`: черновик runbook релиза 2.6 (§0 предусловия … §6 журнал), одиннадцать пунктов `UNKNOWN`.

Каждая единица: семь гейтов моста → `make verify` в worktree с ровно одним `pg-roundtrip: SKIP` → PR → зелёный CI (`verify`, `build-images`, `apply-migrations-in-container`, `systemd-verify`) → merge-коммит оркестратора. Ревьюера не было (правило D31/D36).

**Что делал оркестратор сам (объявлено в PR):** два маленьких doc-коммита там, где воркеры оставили дыру - строка статуса блокера B5 в `RELEASE-READINESS-1.14.md` (после C2) и восстановленные строки воронки миграции 017 в DATA-DICTIONARY, которые воркер G2 вычистил. Два конфликта мержа в нумерованном списке «Сверка» runbook `release-m01.md` (C2 против C1, C5 против C6) разрешены сохранением обоих пунктов и перенумерацией - список дошёл до пункта 21. Job-код и SQL руками не трогались.

**Инциденты.**

- **C5 - красный CI и один пустой фикс-раунд.** `systemd-verify` падал, потому что `ExecStart` указывал на `/usr/local/bin/proxima-pg-backup.sh`, которого в раннере нет. Фикс-раунд 1 вернулся без единого коммита; раунд 2 перевёл юнит на `/usr/bin/env bash /srv/proxima-ai/repo/infra/backup/proxima-pg-backup.sh` (форма соседних юнитов), и runbook больше не копирует скрипт в `/usr/local/bin`. Единица уложилась в лимит двух раундов, `blocked` не потребовался.
- **GLM не довёл два последних дока.** G5 ушла резервному Claude-субагенту, потому что полоса GLM встала; на G4 попытка GLM отвалилась по таймауту (exit 5) - 90 минут на 144 событиях и ни одного коммита, единицу тоже забрал Claude по правилу D36 (после двух провалов - Claude). Беседа `1d1c1143-777c-54ce-b660-f3fb6dc122f7` осталась запущенной - закрыть руками в UI OpenHands.

**Проверка на стенде.** После мержа C3 (17:05 UTC) полоса метрик на `proxima-rehearsal` проверена на живых данных: выручка/день 25 тыс. ₽ (−23,3 % к 7 дням), заказы/день 30 (+17,3 %), свежесть 16:11; `signals` и `oos-risks` скрыты, FX-плашки на полосе нет. `/brief` в postgres-режиме остаётся гибридом: сводка, аномалии и полоса - настоящие, дайджест, вердикт, строки сигналов и подпись переключателя кабинетов - по-прежнему FX-фикстуры, до Epic 5. Стенд (`proxima-rehearsal`, postgres 5434, webapp 3434) работает и ждёт Mike; уборка - `bash tools/rehearsal_run.sh down --root ~/orca/rehearsal && sudo rm -rf ~/orca/rehearsal` (`rm -rf` - только с подтверждения Mike).

**Что осталось до релиза 1.14 (вт 15.09):** Story 6.1 Владислава (пт 11.09, CP-12); слово «деплой» от Mike плюс шаги runbook §1 на сервере (переименование токенов, `.env`, raw-каталог); создание роли аналитика на сервере - скрипт готов (C2), запускает Mike; B6 - копия артефактов бэкфилла в S3, `UNKNOWN`.

**До 2.6 (вт 22.09):** ротация analytics-токена PA-13; конфликт порта 3000 с ручным контейнером `proxima-webapp-staging` - нужно решение; шаг воронки едет тем же тегом, но своей единицы не имеет; форма релизного тега для 2.6 не определена; окно наблюдения расходится - D33 даёт 23-29.09, AC Story 2.6 - 24-30.09.

**Заморожено (D35):** Story 4.4, Epic 5, «Источники v2».

**Следующее действие:** очередь D36 исчерпана, новых диспатчей нет. Утром - решения Mike: посмотреть `/brief` на стенде и дать слово на уборку, порт 3000, форма тега 2.6, окно наблюдения 2.6; закрыть зависшую беседу GLM в UI. Пт 11.09 - проверить Story 6.1 в `main`; вт 15.09 - по слову «деплой» runbook `release-m01.md` с §0.

## День 08.09.2026 - интерактивный прогон оркестратора (Claude Code, D32)

**Итог (10:24 UTC):** Mike за компьютером, гейты только по решениям объёма (D32 + дополнения), запуски и мержи автоматические. Epic 4 стартовал до гейта 30.09 по решению Mike. Состояние прогона - `~/orca/proxima-ai-night/logs/day-2026-09-08/state.json`.

| Единица | PR | Исполнитель | Примечание |
|---|---|---|---|
| AD-19 (грейн nmId, `fact_nm_daily`, `dim_nm_subject`, 018) | #87 | Claude (bmad-architecture, update) | принят Mike; уточнения в memlog (#96, #105) |
| D32 + тексты 4.0/4.1 под AD-19 | #88 | оркестратор | |
| 3.1 follow-ups (окно `[today-6, today]`, log-and-skip, drop-in PA-13, **баг вызова коллектора**: у образа нет ENTRYPOINT) | #90 | Fedor | 1 фикс-раунд обвязки (db-тест) |
| Проба Story 3.0 → API-FACTS «async CSV глубина» | #91 | оркестратор, 6 HTTP-запросов, 1 отчёт | 6 месяцев принято, 15 колонок, `name` = `userReportName`, `createdAt` UTC |
| PA-33 таблица версий → AGENTS.md | #92 | Claude | старый #3 закрыт |
| Чек-лист готовности 1.14 | #93 | Claude, сервер только чтение | блокеры B1-B6 |
| Журнал Jira-записей оркестратора | #94 | оркестратор | дубликаты с #89 помечены |
| Story 4.0 | #95 | Claude | 6 вопросов → решения Mike |
| 3.2/3.3 follow-ups (guard по префиксу, реальные колонки CSV) | #97 | Fedor | попытка 1 упала по вине оркестратора (клон не на main) |
| Runbook 1.14 сверен с main и сервером; W10/W35 в API-FACTS | #99 | Claude | найден блокер кода (compose) |
| Story 4.1 (переписана по каркасу `norm/`, ветка pmm-20 списана) | #100 | Claude | агент умер на 429, гейт прогнал оркестратор |
| 4.1 follow-ups (заказы ИЛИ выручка, знак денег, UNKNOWN категория) | #102 | Fedor | |
| Compose: токены и raw в контейнер collector, контейнерные пути в runners | #103 | Fedor + 1 коммит оркестратора в CI (AD-15 allowlist, разрешено Mike) | |
| Story 4.2 (порог из конфигурации null, ранжирование по деньгам) | #104 | Claude | brief v1 расширен `threshold` на месте (Mike) |
| Story 4.3 (аномалии на /brief) | #106 | Claude | |

Sprint-status: 4.0-4.3 `done`, Epic 4 `in-progress`. Закрыты старые PR #3, #26, #32, #34 (ветки сохранены); #31 оставлен по решению Mike.

**Jira (approve Mike):** PA-60, PMM-51, PMM-47, PMM-56, PA-63, PMM-49 → Готово; созданы PA-67 (гигиена M-01), PA-68 (KF-3), PMM-137 (Story 4.0, В работе). Параллельная сессия (PR #89, D33) записала раньше PMM-123..134/PA-64/PA-65; мои дубликаты PMM-135, PMM-136, PA-66 помечены «[дубликат …]» (`docs/state/JIRA-SYNC-2026-09-08-orchestrator.md`). Правило: одна сессия-писатель в день. **В Jira не записаны сегодня:** 4.1-4.3 (нет ключей; PMM-137 - только 4.0).

**Инциденты:** лимит сессии Anthropic (429) в 07:15 UTC убил субагент 4.1 после коммитов - гейт и отчёт восстановлены; MCP `jira` в уже запущенной сессии не виден - Jira идёт через `claude -p`; проверка контрактных файлов моста читает рабочее дерево клона - перед диспатчем клон на `main`.

**Что держит релизы (из чек-листа #93 и runbook #99):** Story 6.1 Владислава (ничего нет), дата + слово «деплой» (D33 в #89: 1.14 = вт 15.09, 2.6 = вт 22.09), переименование токенов на сервере в имена AD-13 (`amirova-test_wb_*_token`, `1010:1010 0600`, runbook §1), ротация analytics-токена до 2.6 (PA-13), роль аналитика (6.4), S3-копия артефактов `UNKNOWN`, `WORKS-TODAY.md` не обновлён.

**Открытые вопросы в телах PR** (решения не срочные): 4.3 - гейт как vitest-describe, Ajv в webapp запрещён как новая зависимость, два раздела vs плоский список; 4.2 - конфиг порога в образе (смена = релиз), спайн AD-9; runbook #99 - `proxima-psql-owner` в `infra/bootstrap/`, `PROXIMA_RAW_DIR=/srv/proxima-ai/raw` подтвердить, W35 снят с неполного снимка.

**Следующее:** 4.4 после разметки ретро-тревог Владислава (PMM-126); Epic 5 требует решений Mike (5.0 AD, 5.1 egress PMM-31); релизный трек - по D33 с Владиславом.

### Трек сбора данных (08.09, после D35) - единицы дня выполнены, репетиция SUCCEEDED

**Итог (вечер 08.09 UTC):** девять PR в `main` (#108-#116), репетиция цепочки 1.14 на VPS прошла с живым хвостом - все четыре прогона ledger `SUCCEEDED`, гейт §4 пройден; боевой контур не тронут (схема 6, таймеров `proxima-*` нет). Решения Mike за день: D35 (четыре пункта, ~10:30 UTC) + «Дополнения по репетиции» (~13:40 UTC, четыре: правило гейта §4 по дням, определение заказов «на момент `run_day − 3`» + открытый вопрос Владиславу в 6.1/6.3, секрет webapp `1001:1001`, полоса метрик скрыта) - всё в `DECISIONS.md` D35. Стенд репетиции оставлен работать, пока Mike не посмотрит `/brief`.

**Диагноз (утро, D35).** Конвейер целиком построен в `main` (джобы `collect`/`backfill`/`funnel-v3`/`funnel-csv-promote`, ledger `collector_runs`, откат по `run_id`, роли/RLS, образы, compose, systemd-юниты, runbook `docs/operations/release-m01.md`, `norm` → `brief`, `/brief` на Postgres), но на сервере из него не работало ничего: схема 6 против 18 в коде, `collector_runs` нет, таймеров нет, чекаут `/srv/proxima-ai/repo` на `fd95fcb`, данные WB - 25.08 16:33 UTC; цепочка ни разу не прогонялась на реальных артефактах 31.08. Найден баг релизного пути: `WB_ALLOW_LIVE_NETWORK=1` (AD-4) не выставлен нигде в контуре деплоя → утренний `collect` упал бы на `WB_NETWORK_FORBIDDEN`. Закрыто за день (таблица ниже).

| PR | Ветка | Единица | Что вошло |
|---|---|---|---|
| #108 | `docs/d35-collector-track` | D35 | решение в `DECISIONS.md`, active task в `TASKS.md`, утренняя версия этого раздела |
| #109 | `chore/story-1.11-done` | U-A4 | Story 1.11 → `done`: объём отгружен в Story 2.5 (CP-5) |
| #110 | `fix/live-network-env` | U-A1 | `WB_ALLOW_LIVE_NETWORK=1` у сервиса `collector` в `infra/compose.yaml` + гейт `tools/verify_live_network.py` (`make live-network`) + runbook §3/§5 |
| #111 | `feat/rehearsal-stack` | U-A2 | `infra/compose.rehearsal.yaml` (проект `proxima-rehearsal`, postgres `127.0.0.1:5434`), `tools/rehearsal_run.sh` (`init → up → backfill → tail --live → steps → check → down`), runbook «Репетиция на VPS (D35, не деплой)» |
| #112 | `docs/rehearsal-facts-2026-09-08` | B | факты репетиции в `docs/state/API-FACTS.md` + эталон W10 с копейками |
| #113 | `docs/readiness-1.14-v2` | U-A3 | `RELEASE-READINESS-1.14.md` v2 (блокеры B1-B10) + блок конвейера в `WORKS-TODAY.md` + исполнитель runbook по D7 |
| #114 | `fix/webapp-metrics-postgres-mode` | B10 | `MetricStrip` скрыт при `supportsMetrics=false` (postgres-режим давал 500 на каждой странице); «Сводка ещё не считается» вместо «Сбор не проходил больше суток», пока первая сводка не посчитана |
| #115 | `fix/webapp-secret-uid` | B9 | `proxima_webapp_uri`/`_password` - владелец `1001:1001` (uid образа webapp) в `provision-runtime-roles.sh`, `init` репетиции, runbook §1.2/§1.4, memlog |
| #116 | `docs/w35-gate-rule` | дополнение D35 | гейт §4: W35 по дням; глоссарий - заказы «на момент `run_day − 3`»; дополнение D35 в `DECISIONS.md`; `rehearsal_run.sh check` реализует правило; readiness и бриф аналитика ссылаются на правило |

**Репетиция (B).** 13:10:14-13:11:55 UTC, `main` `1c5e256`, стенд `proxima-rehearsal`, корень `~/orca/rehearsal`, postgres `127.0.0.1:5434`, webapp `127.0.0.1:3434` (пересобран на `fcab598`, после #114). Схема `18|18`; provision ×2 идемпотентен; `backfill` SUCCEEDED (`run_day` 2026-08-31, 183 дня, orders 13 386, sales 10 675, nm_subjects 201, nm_rows 36 783); живой хвост `collect` SUCCEEDED - ровно 2 read-вызова (`dateFrom=2026-08-27`; orders 353 строк / 217 пропущено, sales 215 / 191), боевой `wb_statistics_token` прошёл `assertLeastPrivilegeToken`, значение токена не печаталось; `norm` + `brief` SUCCEEDED; `data_status_current` 2026-09-07 `stale=false`; `brief_current` 2026-09-07 `ok`. Гейт §4: W10 649 | 700 860.50 = пересчёт фикстуры; W35 по дням 8/8 PASS после #116. `/brief` на стенде: 07.09 заказы 30 против нормы 26.5 (+13.2 %), выручка 25 450 ₽ против нормы 35 466 ₽ (−28.2 %), аномалии по SKU: 2 critical / 5 attention. Полный разбор - `API-FACTS.md` «Репетиция цепочки 1.14 на VPS», `RELEASE-READINESS-1.14.md` §4-§5.

**Уборка (после того как Mike посмотрел стенд; `rm -rf` - только с его подтверждения):** `bash tools/rehearsal_run.sh down --root ~/orca/rehearsal && sudo rm -rf ~/orca/rehearsal`; остановить при уборке также превью webapp на фикстурах `127.0.0.1:3100` (`next start` из `~/orca/proxima-ai-night`, запущено утром, ещё работает).

**Что осталось до релиза 1.14 (вт 15.09, D33):**

- B1 - Story 6.1 Владислава в `main` до пт 11.09 (CP-12); ни одного коммита Владислава в `origin/main`, waiver D26 не пишется.
- B2 - слово «деплой» от Mike в день релиза + шаги runbook §1 на сервере (переименование токенов под AD-13 с `1010:1010 0600`, правка `.env`, raw-каталог `/srv/proxima-ai/raw`) - делает Mike или Claude по слову «деплой».
- B5 - LOGIN-роль аналитика (Story 6.4): состав грантов не предложен, роль обещана D33 вместе с релизом.
- B6 - копия артефактов бэкфилла в S3: `UNKNOWN`, проверить может только Mike.

**До 2.6 (вт 22.09):** настоящие метрики дашборда в postgres-режиме (follow-up к Story 2.5, после #114 полоса просто скрыта); ротация analytics-токена PA-13.

**Кандидаты в единицы (не запланированы, readiness §6):** передача `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID` через `environment:` compose - на сервере provenance ledger будет `NULL`; инкрементальный накат 007-018 поверх дампа боевой базы в репетиционном проекте; оставшиеся противоречивые тексты `/brief` для `blocked` и несовпадения дня; `proxima-psql-owner` в `infra/bootstrap/`, `docs/operations/releases/`, `CHANGELOG.md` - не созданы.

**Заморожено (D35):** Story 4.4, Epic 5, «Источники v2» (эпик не создан, после первого SUCCEEDED утра).

**Следующее действие:** очередь единиц трека исчерпана. После просмотра Mike - уборка стенда (выше); кандидаты §6 - только по решению Mike; пт 11.09 - проверить Story 6.1 в `main`; вт 15.09 - по слову «деплой» runbook с §0.

## Ночь 07-08.09.2026 - автономный прогон оркестратора (Claude Code, D31)

**Итог (17:54 UTC, окно до 03:09 UTC ещё открыто):** шесть единиц в `main`, очередь исчерпана, `blocked` - ни одной, деплоя и записей в Jira не было. Состояние прогона - `~/orca/proxima-ai-night/logs/night-2026-09-07/state.json`, промты и результаты моста - `~/orca/proxima-ai-night/logs/openhands-bridge/<run-id>/`.

| Единица | Jira | Ветка | PR | Исполнитель | Фикс-раунды | Мерж (UTC) |
|---|---|---|---|---|---|---|
| Story 1.8 тестовая база и сандбокс | PA-60 | `feat/m01-story-1.8` | #73 (+#74 sprint) | воркер Дирижёра (Fedor), собрана бандлом из его workspace | 0 | 15:13 |
| KF-3 плавающий `mskDay` | - | `fix/collector-kf3-msk-day` | #75 | Claude-субагент (GLM-воркер завис на сломанном терминале) | 0 | 16:34 |
| Story 3.2 CSV как прогон реестра | - (бриф 03.09 не исполнен) | `feat/m01b-story-3.2` | #76 (+#77) | Claude-субагент | 0 | 16:56 |
| Story 3.1 воронка v3 ежедневно | PMM-51 | `feat/m03-story-3.1` | #78 (+#79) | Fedor начал (914 строк черновика), умер по таймауту ACP; Claude-субагент переписал по AD | 0 (конфликт `Makefile` с 3.2 разрешён оркестратором) | 17:11 |
| PA-65 ретрай алерта, `TimeoutStartSec` | PA-65 (предложенный ключ) | `feat/pa-65-alert-retry-timeout` | #80 | GLM-воркер (попытка 4; 1 - ошибка промта оркестратора, 2-3 - падения Codex) | 0 | 17:20 |
| Story 3.3 промоушен CSV | - | `feat/m01b-story-3.3` | #82 (+#83) | Fedor-воркер (единственный Codex) | 2 (обвязка: путь фикстуры/`$1` uuid vs text; строка гейта) | 17:52 |
| Мост: `title_llm_profile` | - | `fix/bridge-title-llm-profile` | #81 | оркестратор | - | 17:29 |
| D31 | - | `docs/d31-night-run-2026-09-07` | #72 | оркестратор | - | 15:10 |

Каждая единица: семь гейтов моста (для 1.8 - те же проверки руками) → `make verify` локально с ровно одним `pg-roundtrip: SKIP` → PR → зелёный CI (`verify` + `images`: сборка образов, миграция в контейнере, `systemd-verify`) → merge-коммит. Ревьюера не было (решение Mike, Q7).

**Что чинил сам (обвязка, объявлено в PR):** #78 - конфликт `Makefile` (обе истории добавили цель в `verify`, оставлены обе); #82 - `test(collector)`: путь к фикстуре и `tools/delete_run.py` от cwd (CI гоняет db-тесты из `services/collector`), `$1` как uuid и `::text` в одном INSERT (42P08), и `test(gate)`: маркер `delete_run.py` в `tools/verify_funnel_csv.py`. Job-код и SQL руками не трогались.

**Инциденты и выученные правила.**
- **Fedor - строго один одновременно.** Второй Codex под тем же `~/.codex` (PA-65 рядом с 3.1) сломал sqlite-состояние (`failed to initialize state runtime`), а 3.1 замолчала на 30 мин и была добита agent-server'ом (`ACP prompt timed out after 1800s`, профиль `Fedor.acp_prompt_timeout = 1800`). Черновик 3.1 (15 файлов, не закоммичен) спасён диффом и доведён Claude.
- **GLM-воркер KF-3** упал на терминале: `fork failed: Resource temporarily unavailable` в 15:48 (транзиентный шторм процессов: `make verify` в двух песочницах + цикл тестов ×10); беседа `3585fc77` до сих пор `running` с мёртвым терминалом - закрыть руками в UI.
- **Ошибки при запуске GLM (просьба Mike):** глобальные MCP `tavily`/`mcp-atlassian@0.23.1` стартовали в каждой беседе, `mcp-atlassian` не знает `server/discover` (31 ошибка валидации), процессы переживали беседы (15 висящих к 17:30). Профилям `ORK_Z` и `Fedor` выставлено `mcp_server_refs: []` (бэкапы `.ORK_Z.json.bak-20260907T172639Z`, `.Fedor.json.bak-…` рядом), осиротевшие процессы завершённой беседы убиты, мост передаёт `title_llm_profile` (#81). Дымовой тест: свежая беседа GLM без ошибок, без MCP-процессов.
- Первая попытка PA-65 упала на моей ошибке: обрезанный байтом UTF-8 промт (`cut -c`), мост не собрал payload.
- Pull_request-воркфлоу не стартуют для PR с конфликтом (GitHub не строит merge-ref) - именно так проявился конфликт #78.

**Сервер:** `codex-conductor.timer` выключен (`disable --now`) на ночь по решению Mike; профили воркеров OpenHands изменены (выше); `proxima-tg-bot.service` не тронут; деплоя нет. **Обратно:** обновить `/srv/proxima-ai/conductor-repo-checkout` до текущего `main` (иначе Дирижёр заново ревьюит/PR-ит 1.8, которая уже в `main`), затем `sudo systemctl enable --now codex-conductor.timer`. Его мёртвые воркеры 1.7/2.5/1.8 не тронуты.

**Jira (OAuth не пройден, работал по таблицам ключей репо, D17/D24) - таблица синхронизации под approve Mike:**

| Ключ | Действие |
|---|---|
| PA-60 (Story 1.8) | → Готово; комментарий: PR #73, merge 07.09 15:13 UTC |
| PMM-51 (Story 3.1) | → Готово / На проверке; комментарий: PR #78; открытые вопросы 1-6 из тела PR |
| PMM-49 (Story 1.11) | → Готово (свёрнуто): объём влит в 2.5 (CP-5), PR #69 |
| Story 3.2, 3.3 | ключей нет (бриф 03.09 разделы 4 не исполнены, PMM-63..75 заняты модулями D29) - завести как задачи PMM-39 со ссылками на PR #76 и #82 |
| PA-65 | завести по брифу 03.09 §2, ссылка PR #80 |
| KF-3 | задача не заводилась; комментарий к PA-36 или к задаче 1.4 (PMM-45): PR #75, причина в теле PR, до 24.09 фикс обязан быть на сервере вместе с релизом |

**Открытые вопросы воркеров (все в телах PR):** KF-3 - 3 (production-экспозиция 24-го числа, формулировка причины в реестре, Python-двойник не затронут); 3.1 - 6 (окно `[run_day-6, run_day-1]` vs 21/21, строгость покрытия, `notes` на FAILED, PA-13 флаг в юните, `morning_run.sh` зовёт `collector collect` vs Dockerfile `npm run <job>`, DATA-DICTIONARY «014»); 3.2 - 8 (главный: guard «один отчёт в сутки» блокируется внешним потребителем токена до ротации OQ-10); 3.3 - 1 (имена колонок реального CSV - подтвердить Story 3.0, правка одна таблица `CSV_COLUMN_MAP`).

**Дополнение 08.09 (03:07 UTC), Q21a Mike:** гигиена M-01 (решения 30.08) выполнена Fedor-воркером за 13 минут и смержена - **PR #85**: `webapp-lint` в `verify` (0 ошибок / 0 предупреждений, eslint-конфиг игнорирует unused-disable в сгенерированных контрактах), `codegen-diff` сразу после `codegen` (дрейф сгенерированных `contracts/*.ts` = красный `verify`, тест в `tools/tests/test_verifiers.py`), `hooks` из `make install` (идемпотентный `core.hooksPath=.githooks`, `SKIP` вне git); AGENTS.md pitfall и dev-onboarding обновлены. Открытых вопросов нет. Единица запущена в 02:48 UTC по прямому указанию Mike после закрытия 12-часового окна (T0+12h = 03:09 UTC).

**Рекомендации на утро:** принять решения по открытым вопросам 3.1/3.2 до релиза 2.6; поднять `Fedor.acp_prompt_timeout` выше 1800 с или запретить длинные `make verify` внутри Codex-песочницы; закрыть беседу `3585fc77`; следующий шаг очереди - AD для 4.0 (`bmad-architecture`), затем 4.0 → 4.1.

## 03.09.2026 (вечер) - конвейер сведён в main (John, PM)

**Что изменилось за день.** Из одиннадцати открытых PR закрыто шесть, все с зелёным гейтом: #50 (Story 1.4), #51 (Story 1.6), #52 (ловушки), #54 (правило записи в Jira и статус `blocked`), #45 (маршрут онбординга, переписан под хартию v2), #43 (Дирижёр), #55 (конвенции расчёта), #56 (починка юнитов), #57 (BAD и мост, заменил #47). Открытыми остались пять PR эпохи до 30.08: #34, #32, #31, #26, #3.

**Серверный конвейер теперь в `main`.** `tools/orchestrator/` (Дирижёр, мост `bad_dev_story.sh`), `infra/hermes/`, юниты systemd, модули BMAD TEA и BAD 1.2.0. Ограничения, установленные фактом и записанные в `docs/agent-system/ORCHESTRATOR.md`: три слота воркеров максимум, воркер не пушит и не открывает PR (это делают три root-обёртки на сервере), истории 1.14, 2.6, 3.0 и 3.4 конвейеру недоступны, Jira конвейеру недоступна, `.openhands/hooks.json` к разговорам моста не применяется, BAD и Дирижёр одновременно не работают.

**Решения.** D27 - четыре конвенции расчёта, закрывают OQ-18 (канон в `glossary.md`, продублировано в контрактах `norm` и `brief`). D28 - BAD рядом с Дирижёром; записано 01.09 как D25, переномеровано при мерже, потому что номера D25-D27 заняты решениями 02-03.09.

**Что разблокировано.** Story 6.1 (теневой пересчёт) больше не ждёт конвенций и может стартовать в день выхода Владислава. Story 2.3 и 2.4 не ждут 1.6 - она в `main`. Очередь после правила сжатия: `1.5 → 1.7 → 1.13 → 1.14 → 2.3 → 2.4 → (2.5 + 1.11) → 2.6`, плюс 3.1.

**Что по-прежнему ждёт Mike.** Две даты деплоя в календаре (1.14 не позже 20.09, 2.6 не позже 23.09). Ротация analytics-токена (OQ-10) до Story 3.1. Правки канона OQ-16: CAP-6 «8 недель» в SPEC, цепочка AD-6 в спайне (держит мерж 3.1), порог Deferred. Approve таблиц синхронизации Jira. Доступы Владиславу по чек-листу хартии §6.1.

**Найденная нестабильность.** KF-3: тест `mskDay: midnight boundary in both directions` падает примерно раз на три прогона `npm test`, в изоляции и на чистом `main` проходит. Не связан ни с одной из сегодняшних веток.

## 02.09.2026 (вечер) - PRD v2.2, дельта epics, роль Владислава (John, PM)

Сделано: PRD доведён до v2.2 (`_bmad-output/planning-artifacts/prds/prd-PROXIMA-AI-2026-08-28/prd.md`; рецензия v3 `validation-report.md` grade Poor по правилу «есть critical», решения комнаты 2а-7а применены; документ для чтения - `decision-brief-2026-09-02.md`). Нарезка: `epics.md` обновлён дельтой (сентябрь по `sprint-change-proposal-2026-09-02.md` CP-1..CP-10; октябрь - детальные AC 4.0-4.4 и 5.0-5.3; раздел «PRD v2.2 → истории»); `sprint-status.yaml` пересобран (35 историй, 9 done); кандидаты M-06+ - `epics-candidates-m06.md`; Jira - `docs/state/JIRA-SYNC-BRIEF-2026-09-03.md` (на approve, записей нет). Владислав - `docs/agent-system/roles/analyst-vladislav.md` + журналы `docs/state/{CABINET-RECONCILIATION,RETRO-ALARM-LABELS,SM3-BASELINE}.md`. Батарея рецензентов PRD закреплена в `_bmad/custom/bmad-prd.toml` + `reviewers/`.

Ждёт Mike: (1) две даты деплоя - 1.14 ≤ 20.09 (13.09 без бэкфилла), 2.6 ≤ 23.09; (2) approve `JIRA-SYNC-BRIEF-2026-09-03.md`; (3) доступы Владиславу по чек-листу хартии §3; (4) команда на коммит в ветку `docs/prd-ladder-2026-09-02` от `origin/main`; (5) CR к AD-6 и правка SPEC (OQ-16) - отдельными единицами `bmad-architecture`/`bmad-spec`. Гейт готовности проход 5 (`implementation-readiness.md`): CONCERNS - 5 из 14 находок прохода 4 закрыты, две новые high (Given 1.14 и приёмка 1.14 без `brief_current`) исправлены в `epics.md` в тот же вечер; остаток - правка канона SPEC/glossary/спайн (OQ-16, PA-64) и D25 в `DECISIONS.md` записан. Ничего не закоммичено; Jira и сервер не тронуты.

Следующее действие: после дат Mike - зафиксировать их в PRD §13/§14 и epics NFR9, затем коммит; параллельно Story 1.5 с реальным бэкфиллом в main до 08.09 и Story 3.1 в работу.

## 03.09.2026 (вечер) - закрыты пробелы документации (John, PM)

Написано: `docs/operations/dev-onboarding.md` (вход для человека-разработчика) и `infra/local.env.example`; `docs/operations/access-provisioning.md` (выдача и отзыв доступов, включая почему доступ к боевой базе сегодня выдать нечем); `docs/operations/observability.md` (стандарт логов, статусов и алертов - закрывает пункт 6 DoD-чеклиста, который сам признавал «канона нет»); `docs/operations/incident-runbook.md` (семь сценариев от «нет сводки» до утечки токена); `docs/state/DATA-DICTIONARY.md` (все таблицы миграций 001-011 и планируемые 012-016: кто пишет, кто читает, чем удаляется).

Обновлено: `README.md` переписан под лестницу (описывал снятую рамку M1 от 26.08); в routing-таблицу `AGENTS.md` добавлены строки на действующие требования - раньше каталога `_bmad-output/` не было ни в одном контрактном файле, и агент по инструкции приходил в архив M1; исправлены три указателя, называвшие каноном решений `STATE.md` (канон - `DECISIONS.md`); сам `STATE.md` обновлён до 03.09 с блоком расхождений канона; реестры в `docs/governance/` и шесть планов в `docs/exec-plans/active/` помечены архивом рамки M1.

**Главное для конвейера:** канон противоречит принятым решениям в трёх местах - CAP-6 в SPEC всё ещё требует 8 недель воронки, AD-6 в спайне описывает старую цепочку (блокирует мерж Story 3.1), Deferred спайна не знает о пороге 30 %. Правки заведены как OQ-16 и задача PA-64. Подсистема кондуктора (пять коммитов 01.09, systemd-юниты, `ORCHESTRATOR.md`) не отражена ни в одном реестре решений и ни в одной архитектурной карте.

## 03.09.2026 - роль Владислава v2 и Epic 6 (John, PM)

Сделано: роль расширена решением Mike до независимого пересчёта всей цепочки - хартия v2 `docs/agent-system/roles/analyst-vladislav.md` (метод, 11 шагов сверки, эталоны `verification/golden/`, гейт `shadow`, право блокировать релиз, свои зоны кода, доступы), решения записаны как D26. В нарезке новый Epic 6 «Верификационный контур» (истории 6.1-6.5, 40 историй всего), критерии приёмки 1.14, 2.6 и 4.4 дополнены (CP-12..CP-14 в `sprint-change-proposal-2026-09-02.md`). PRD доведён до v2.3: §8.0 пять новых пунктов очереди, OQ-18 (конвенции расчёта), риск и правило релиза в §14/§15. Новый журнал `docs/state/SHADOW-RECONCILIATION.md`. Бриф Jira дополнен разделом 4б (эпик + пять задач).

Две находки разведки, меняющие исполнение: (1) на боевой базе схема версии 6, RLS выключен, ролей спайна нет - доступ Владиславу к базе сегодня выдать нечем, роль заводится Story 6.4; (2) деньги в обезличенных фикстурах умножены на секретный коэффициент - W10/W35 по репозиторию невоспроизводимы, поэтому эталоны сначала на синтетике, недельные суммы - на полных фикстурах и в приёмке 1.14.

Ждёт Mike: даты деплоя; approve брифа Jira; доступы Владиславу (§6.1 хартии) и решение по LOGIN-роли; конвенции расчёта (OQ-18) до первого пересчёта; команда на коммит.

## Current objective

Ship M1 — a production-ready read-only data foundation for one pilot WB cabinet (Bogatova Belle Robe) with SHA-256 provenance from official WB evidence to PostgreSQL domain releases (Phase 2 of 8 in progress).

## Последнее (01.09.2026): BMAD достроен, BAD установлен, шаг реализации ведёт в OpenHands

Ветка `feat/bmad-bad` от `origin/feat/orchestrator-conductor`. Сделано:

- BMAD 6.11.0 достроен: модуль **TEA v1.23.4**, цели установки `claude-code` (появился `.claude/skills/`, 59 скиллов) и `openhands`. Конфиги `_bmad/config.toml` + `_bmad/{core,bmm,tea}/config.yaml` целы, рендер скиллов проверен.
- `gh` 2.45.0 из Ubuntu universe (стороннего репозитория не добавлял). **`gh auth login` за Mike** - токену нужен scope `workflow`, иначе повторится блокер 31.08.
- BAD 1.2.0 в `.claude/skills/bad/` (`npx skills add … --copy`, запись источника - `skills-lock.json`). Настроен: `max_parallel_stories: 3`, `auto_pr_merge: false`, statusline- и activity-хуки в `.claude/settings.local.json` (поставлен `jq` - без него activity-хук молча ничего не пишет).
- Шаг 3 BAD переписан на `tools/orchestrator/bad_dev_story.sh` (новый; `lib.sh` переиспользован, скрипты Дирижёра не тронуты). 12 офлайн-тестов - `tools/tests/test_bad_dev_story.py`.
- Решение D25 в `DECISIONS.md`; правила сосуществования - `ORCHESTRATION.md`.

**Живой прогон моста сделан 01.09.2026** (Дирижёр остановлен Mike, `gh auth login` выполнен, scopes включают `workflow`). Шесть попыток, каждая вскрыла свой дефект - все починены коммитом `6e12f25`; седьмая прошла целиком: 1 коммит, все гейты зелёные, коммит - потомок записанной базы. Артефакты убраны.

## 02.09.2026: 1.3 и 2.2 забраны, четыре PR открыты

Дирижёр остановлен Mike, `gh auth login` выполнен. Обе несобранные истории вынуты из песочниц OpenHands бандлами (push оттуда невозможен), прогнаны через гейты входящего диапазона и `make verify`, отревьюены по чек-листу `ORCHESTRATOR.md`:

- **Story 1.3** → PR **#48**, ветка `feat/m01-story-1.3`, CI зелёный. Четыре фикс-раунда в живой conversation `07f644d6`, история не переписана. Раунд 1 — ревью: два CRITICAL (тихий 0-row UPDATE в `RunLedger`; GUC арендатора переживал прогон на `pg.Pool`) и MAJOR (гранты против AD-11). Раунды 2-4 — нашёл CI: `policy_count` off-by-one, `seedTenant` сеял в пустую `proxima_test` через sandbox-DSN, `assertTenantGucReset` ждал NULL вместо `''` после `RESET` кастомного GUC. Заодно в тест добавлена прямая проверка RLS: без GUC прогон не виден.
- **Story 2.2** → PR **#46**, ветка `feat/m03-story-2.2-v2`. Из двух расходящихся реализаций Mike выбрал версию песочницы (новее, есть `msk_day` по AD-7 и `contracts.test.ts`). PR **#44** закрыт комментарием со ссылкой; ветка `feat/m03-story-2.2` в origin оставлена как единственная копия первой попытки. Блокеров нет; правка `tools/verify_contracts.py` разобрана построчно — добавляет `referencing.Registry`, ни одна проверка не ослаблена.
- **Инфраструктура** → PR **#47** (`feat/bmad-bad` на базе `feat/orchestrator-conductor`) и **#43** (Дирижёр). Порядок мержа жёсткий: сначала #43, потом #47.

`sprint-status.yaml`: 1.3 и 2.2 → `review` (по коммиту в своей ветке).

**Почему BAD ещё не запущен.** Его Phase 0 первым делом делает `git switch main`, а на `main` нет ни моста, ни скилла BAD, ни TEA — всё это в #43 и #47. Плюс пока 1.3/2.2 не смержены, эпик 1 не пускает 1.4. То есть запуск упирается ровно в четыре мержа.

**Свойство контура, вскрытое этими раундами.** В песочнице OpenHands нет PostgreSQL: `pg-roundtrip` там SKIP, `*.db.test.ts` не исполняются вообще. Значит любая история с db-тестом уезжает из песочницы непроверенной, и первым её реально запускает CI. Три из четырёх раундов по 1.3 — именно этот класс. Для таких историй закладывать 2-3 круга CI как норму, а не как отклонение.

**Факт про CI, проверенный 02.09:** `pg-roundtrip` в CI **выполняется** — `pg_local_roundtrip.sh` находит PostgreSQL 16 на ubuntu-раннере, хотя `.github/workflows/verify.yml` его не ставит явно; `*.db.test.ts` там гоняются по-настоящему. Локально на этом VPS `initdb` нет, поэтому шаг даёт SKIP: **локальный зелёный ничего не доказывает про db-тесты**, ориентироваться надо на CI. Первое впечатление «тест зелёный только на маке» было ошибочным и снято комментарием в PR #48.

**Требует внимания прямо сейчас:** Дирижёр остановлен, и два его воркера остались в состоянии `finished`, но **несобранными** - story 1.3 (`feat/m01-story-1.3`, conversation `07f644d6`) и story 2.2 (`feat/m03-story-2.2`, `d067112d`), деревья чистые. Их коммиты живут в workspace'ах OpenHands и не потеряются, но в `sprint-status.yaml` обе висят `in-progress`. Забрать их можно либо снова включив таймер Дирижёра (он соберёт их первым же тиком), либо руками через `collect_branch.sh`. **До сбора таймер лучше не включать одновременно с работой BAD.**

**Осталось за Mike:** мерж четырёх PR по порядку — #43, #47, #48, #46.

**Заметка:** строка в `bmad:context` блоке AGENTS.md про `DATABASE_URI` из `.env.task` устарела - требование снято коммитом `646ecb1`. Блок управляется скиллом `bmad-project-context`, руками не правил; поправить при следующем рефреше блока.

## Current task

**PA-13 enforcement rollback оставлен по решению Mike 2026-08-25;** live Jira всё ещё «В работе» и требует ручной актуализации: исходная цель superseded, successor = READ-only Analytics token → повторный revert. **Plan 02-02 cancelled; выбран Phase 2 вариант A (close with descope), Jira-переход ещё не выполнен.**

**PA-41 W1 verbatim import и SCN-008 adapter slice выполнены 2026-08-27.** 18/18 allowlist SHA-256 совпали с source pin `53b7d604`; добавлены `src/proxima` и `pydantic==2.13.4`, обновлён `services/control-plane/uv.lock`. `make verify` PASS: 131 passed, 1 skipped. W2 остаётся после PMM-29.

**PMM-5 DONE 2026-08-28 (this worktree, autopilot full):** LLM-диагноз SCN-008/001/005 fixtures-first - пакет `proxima_control_plane.diagnosis` (draft-схема внутри control-plane, вендор-агностичный LLMClient+Mock, DATA-промпт anti-injection, retry ×2 fail-closed, timeout, rollback-флаг `llm_enabled`, JSONL-аудит, CLI run/eval) + eval 12 кейсов 12/12 (гейт ≥80%). PR #29 merged `6c29398`; `make verify` PASS; Jira PMM-5 Готово (DoD PMM-12, комментарий 10377). Грилль-бриф 10/10: `docs/exec-plans/active/pmm-5-llm-analyst-w1.md`; autopilot-прогон `.autopilot/2026-08-27-pmm-5-llm-analyst-w1` (сдан). Известные ограничения перед PMM-31 (real provider hardening) - в Jira-комментарии. Следующие по спринту: PMM-31 (нужно одобрение Mike на VPS-операции), PMM-25, PMM-32, PMM-33.

**PA-49 Warm Precision сдан 2026-08-26 (autopilot interview deep polish, этот worktree, ветка `feat/pa-49-warm-precision`, коммиты 0dbfa71..12651e4 + gitignore-хвост; в main НЕ мержено - ждёт Mike: новый PR или прямой merge; №17 занят rollback-PR PA-13).** Редизайн webapp по DESIGN.md: тёплые токены обеих тем, Inter+IBM Plex Mono, метрическая полоса 5 карточек (GYR/выручка/заказы/OOS/свежесть) с FX-бейджами на демо-цифрах, редакционный /brief (вердикт-строка, critical-строки 36px, ₽ mono, CountUp+reduced-motion), спроектированные скелеты inbox/dashboard/admin с per-секционными error-boundaries, стайлгайд-эталон; staging-контейнер proxima-webapp-staging на VPS (только 127.0.0.1:3000; смотреть: `ssh -N proxima-app` → http://localhost:3000); фикс Dockerfile PUPPETEER_SKIP_DOWNLOAD (ADR-0006/D01); ADR 0002-0006; память AGENTS.md между autopilot-маркерами; Jira PA-49 комментарий 10334 (статус не менялся). Verify: make verify PASS end-to-end, vitest 26, lint 0, build зелёный. G4 слепая приёмка 16/18 (2 процессных); доводка 1 круг: 6 найдено, 5 закрыто, 1 отклонено (violet-подложка активного пункта - буква R04). Запись: `.autopilot/2026-08-25-pa49-warm-precision/`. После решения по ветке: PA-50 (контракт сигнала - PMM-29 bot lane); PA-49 закрывается деплой-сессией 2 (домен + 80/443).

## Current state

- Состояние на 2026-08-29: разработка мигрирована на VPS `135.106.186.210` в изолированную зону OpenHands под пользователем `openhands-agent`; используется rootless Docker с лимитами 2 CPU/4 GB. Исходящий LLM-трафик идёт через SOCKS/HTTP-прокси на NL-сервер. Git-flow: агент коммитит в ветки `ai/*`, а push и merge выполняет человек с хоста.
- Phase 2 (Vertical Slice: Immutable Intake to Visible Facts): выбран close with descope 2026-08-27; criterion visible facts переносится в Phase 3/6, документальный и Jira-синк pending.
- M2 track opened in Jira PMM (sprint-0/1 backlog); PMM-30 (DEC-006) done; PMM-2 spike merged as above.
- Staging VPS Selectel `135.106.186.210` bootstrapped; host monitor live since 2026-08-15 (Telegram delivery tested, `/etc/hosts` pin for `api.telegram.org` in place). Business data blocked until the backup guardrail (Phase 7).
- 2026-08-16 planning session: PRODUCT-VISION.md approved, Jira PA epics PA-34/35/36/37 created (source: `.planning/STATE.md`).
- Note: local `main` is checked out by the sibling worktree `!Proxima/PROXIMA AI`; this worktree works on feature branches rebased onto `origin/main`.

## Completed

- 2026-08-26: **PA-49 Warm Precision autopilot-прогон сдан** (см. Current task). 7 тасков в 5 волнах + волна ремонта (R15) + 3 доводочных таска; G2 независимая сверка поймала 4 пробела спеки (закрыты); G4 16/18; 12+ коммитов на feat/pa-49-warm-precision. Stage-дашборд прогона заморожен (`.autopilot/dashboard.html`).
- 2026-08-25: **PA-13 rollback deployed** (this agent, branch `mihailzhamba-bot/PA-13-rw-optin`, worktree PA-9). Revert `267cc3c` → `fd95fcb` restores the temporary `--allow-analytics-read-write` exception across collector, CLIs, installer, Python tools, tests and runbook; `make verify` PASS; VPS deployed via bundle (dump `000577e0…`, detached `fd95fcb`, build green; fixed root-owned `docs/agent-system`/`scripts/agent` that broke checkout). Diagnostics proved: fail-closed default intact flagless; both Aug-16 RW tokens dead at WB with `crypto/ecdsa: verification error` (broken copies at the cabinet owner); paste channel clean (Statistics/Finance byte-identical). RW token №4 (Mike-approved) installed `0600 proxima-admin`; local+VPS temp token files removed. Same session: **Plan 02-02 cancelled** by Mike (XLSX `c6dce3b4…` profiled into EVIDENCE, no parser code).
- 2026-08-23: **PA-39 audit of scenario engine in Опрос-v2.2 - DONE** (this agent, worktree `PA-39`, branch `mihailzhamba-bot/PA-39`). Artifacts: `docs/audits/pa-39-scenario-engine-audit.md` (module map deep/card zones, scenario-to-wave mapping SCN-001..008 + greenfield 009/010/011, dependency graph, consumed-surface map of 18 symbols from `ai/contracts.py` as PMM-29 input, analytics_reader interface spec, PA-41 estimate) + `pa-39-import-allowlist.yaml` (27 entries: W1 deterministic core 18 files incl. evals/evidence data, W2 LLM-slice 8 files, settings adaptation base) + `pa-39-hash-transcript.txt` (27/27 machine PASS). Provenance pinned to `53b7d604` (baseline `9cca25d1` ancestor; delta = 10 docs files only). Key grill decisions: destination `services/control-plane/src/proxima/` (verbatim imports resolve); two-commit import scheme (verbatim -> adaptation onto PMM-29 contracts); PA-41 W1 can start immediately, W2 waits for PMM-29 (Jira link created: PMM-29 blocks PA-41). Verification: machine hash-transcript caught one real transcription error (wrong hash for test_model_adapter.py) - fixed; independent reviewer 2 passes: final state 0 blockers (3 numeric fixes + YAML note sync). Source worktree untouched (git status identical before/after). Jira PA-39: В работе -> На проверке with PR link.
- 2026-08-22: **Tracker-vs-repo reconciliation (both Jira projects).** Counts taken live, not from docs: PA 47 issues — 14 Done, 1 In Progress (PA-13), 32 To Do; PMM 33 — 4 Done (PMM-7/9/10/30), 1 In Progress (PMM-2), 28 Backlog; PMM sprint-0 is 14 issues with 4 closed. **PA "Done" overstates progress:** PA-43/45/46/47/48 carry `superseded-by-pmm` — moved to PMM by the 2026-08-17 audit, not executed; genuine PA completions are nine (PA-10/11/12 + PA-28…33). Two issues are the reverse — done but still open: PA-27 (Makefile is the working single entry point, 18 targets) and half of PA-17 (`git ls-files build/` returns zero, only the provenance review status remains). Verified directly on the VPS: `/etc/proxima-ai/secrets/` holds three of five WB tokens (statistics, analytics, finance — no prices/promotion, confirming PA-15), monitor timer active+enabled, Postgres 16.10 healthy 7 days, disk 3%. Two stale PRs: #5 (PA-12) fully duplicates merged #6 — safe to close; #3 (PA-33) is NOT a duplicate — its exact dependency-version table (TypeScript 5.8.3, Ajv 8.20.0, decimal.js 10.6.0, pg 8.16.3) is absent from main, so closing it drops content. 49 reconciliation comments posted — every unclosed issue in both projects plus epics PA-36/PA-37; count cross-checked with `project in (PA, PMM) AND updated >= startOfDay()` = 49, not self-reported. Issue statuses deliberately untouched (Mike's call). Critical path unchanged and idle: PA-39 → PA-41 → PMM-5/20/23 → PMM-32 → PMM-28, and PA-39 has no external blocker.
- 2026-08-22: **VPS SSH access restored.** Symptom was `Permission denied (publickey)` while the server was healthy the whole time. Root cause was NOT the VPN: through the active AmneziaVPN full tunnel, TCP/22 connects in 0.148 s, RTT 140 ms, and the host key still matches `known_hosts` (server never recreated). The real cause was three-layered: (1) no VPS entry in `~/.ssh/config`, so ssh only offered `id_rsa`/`id_ed25519`, neither of which is in `authorized_keys`; (2) the key the server *does* accept — `~/.ssh/id_ed25519_proxima_selectel_20260813`, proven by `Server accepts key` in `ssh -vv` — is passphrase-protected, and without `UseKeychain yes` ssh never reads the passphrase from the macOS Keychain; (3) attempts as `root`, which is locked by design (`PermitRootLogin no`, `AllowUsers proxima-admin`, `passwd --lock root`). Fix: `proxima` / `proxima-db` aliases in `~/.ssh/config` (backup `~/.ssh/config.bak-2026-08-22`) with `IdentitiesOnly yes` (server `MaxAuthTries 3`) + `UseKeychain yes`, plus new read-only diagnostic `infra/ssh-doctor`. Verified end to end: `ssh proxima` → `claudette`, tunnel `ssh -N proxima-db` → Postgres 16.10 answers on `localhost:5433`, and `proxima-psql-readonly` returns `proxima|proxima_diagnostics`. The 2026-08-14 memory claim that "AmneziaVPN cuts port 22" is retracted; the supported way to take the host out of the tunnel is Amnezia's own `ExceptSites` list, not a manual `sudo route add`.
- 2026-08-17: M2/M3 backlog-slice run complete — new company-managed Jira project **PMM** «Proxima M2-M3» (id 10043) populated with 28 issues (25 FULL / 3 STUB, labels `aios-run-2026-08-17` + `wbs-aios-*`), 11 blocks-links, 4 Relates PMM→PA (37/38/39/41). PA untouched (link-only). Manifest + living plan: `docs/exec-plans/active/pm2-backlog-run.*`. Capacity decision: 1 FTE → vertical slice (growth beyond = separate gate PMM-4). Rollback JQL: `labels = "aios-run-2026-08-17"`.
- 2026-08-14: collector cancellation thread (see above); runbook warehouse-mapping pin (`5603f50`); contract repository path fix (`453ffe0`).
- 2026-08-16: agent operating system layer deployed (this directory, AGENTS.md extension, `scripts/agent/verify`).
- 2026-08-16: reviewer subagent deployed in three tool formats (`.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml`) + AGENTS.md "Delegation protocol" section (task-class → orchestration mapping, cross-model review gate 0/0 for phases 3/4/7). Not yet committed; needs live smoke test after session restart (agent dirs created mid-session are not discovered by already-running sessions).
- Earlier: Phase 1 complete (3/3 plans, 3/3 cross-model reviews 0/0); Day-1 WB API proof (5 split read-only tokens); async Analytics CSV proof with quota reservation.

## In progress

- None committed as open by the current agent. Pre-existing dirty tree (other threads, do not stage/commit blindly): `Makefile`, `README.md`, `package.json`, `package-lock.json`, `.planning/STATE.md`, `tools/verify_runtime_boundary.py` (modified); untracked `.mcp.json`, `opencode.json`, `.codex/`, `.planning/PRODUCT-VISION.md`, `.planning/research/GLOBAL-LANDSCAPE-2026-08-16.md`, `services/collector/src/contracts/`, `tools/generate_contract_types.mjs`, `AGENTS.md`, `CLAUDE.md` (AGENTS/CLAUDE now committed by the AI-OS layer). Reviewer-deploy thread (this agent, uncommitted): `AGENTS.md` modified (Delegation protocol + routing row), untracked `.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml`.

## Blockers

- ~~No live WB Analytics token~~ снято 2026-08-25: live-сбор прошёл. READ-only перевыпуск → вернуть enforcement остаётся successor, не текущая инженерная очередь.
- Jira write operations are unavailable in the current MCP session; live status/links need a Chrome session or manual Mike action.
- First approved data release blocked on Phase 8 Data GO; live deployment blocked on separate Live Deploy GO (STATE.md).
- No local Docker — DB dev goes through SSH tunnel to staging VPS (Mike decision 2026-08-16).

## Important discoveries

- Jira site: ALL projects were team-managed; PMM (2026-08-17) is the first company-managed. MCP has NO endpoints for creating components/versions — `comp-*` / `rel-*` labels are the working substitute; if native components appear (UI), they can be backfilled via editJiraIssue.
- Python must run via `uv` (3.14), never the system 3.9 (AGENTS.md toolchain table).
- `services/collector/src/contracts/` TS types are generated by `make codegen` — never hand-edit.
- Local fast verification works without full `make verify`: typecheck + TS tests + pytest all pass (run 2026-08-16: 48 passed, 1 skipped).
- Sibling worktrees `Опрос-v2.2` (baseline `9cca25d1`) and `torgstat-collector` (baseline `610169a6`) must never be mutated; import only via allowlist + SHA-256.

## Files changed

- 2026-08-25 (PA-13 rollback): revert commit `fd95fcb` (13 files, restores `--allow-analytics-read-write` everywhere); docs: `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/phases/02-vertical-slice-immutable-intake/EVIDENCE.md`, `docs/agent-system/HANDOFF.md` (this update), `docs/agent-system/TASKS.md`. VPS: secrets `wb_analytics_token` replaced (RW №4, Mike-approved), `/srv/proxima-ai/backups/pre-pa13rw-20260825.dump`, ownership fix on `docs/agent-system` + `scripts/agent`.
- 2026-08-16 (AI-OS deploy): `AGENTS.md` (extended), `CLAUDE.md` (symlink → adapter file), `docs/agent-system/*`, `docs/exec-plans/{active,completed}/.gitkeep`, `scripts/agent/verify`.
- 2026-08-16 (reviewer deploy): `AGENTS.md` (+18 lines: delegation protocol, routing row), `docs/agent-system/HANDOFF.md` (this update); new `.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml`.

## Verification status

- Last full `make verify` run by this agent: **PASS on `fd95fcb` (2026-08-25, PA-13 rollback worktree)** — install + codegen + typecheck + TS tests (incl. build) + 51 pytest passed / 1 Docker-dependent skip + contracts + migrations + provenance + 4 Mermaid renders + boundary + secrets scan + VPS contract + business-signal. Note: this worktree needed `npm ci` inside `services/collector` for the first run.
- Reviewer read-only runtime proof (2026-08-16, canary-file edit test, canary hash unchanged in all runs): opencode — delegation confirmed (child session), edit tool absent from reviewer pool, bash denied except git-read (agent quoted its own deny rules); Claude Code — write blocked, no retry/workaround; Codex — `operation not permitted` via read-only sandbox (note: that run executed in main thread; reviewer spawn proven separately by REVIEWER-CODEX-OK smoke test; whether the TOML `sandbox_mode` applies when the parent session is non-read-only was NOT isolated — for critical phases prefer launching the reviewer with an explicit read-only sandbox). Caveat for all CLI (`-p`/`run`/`exec`) modes: `@reviewer` mention does NOT force delegation — phrase tasks as review-matching descriptions or explicitly instruct "use the task tool to delegate".
- Last full `make verify` run by this agent: not run (performs `npm ci`, codegen, renders; pre-existing dirty `package-lock.json` belongs to another thread). UNKNOWN when it last ran green end-to-end.

## Exact next action

1. Reconcile Jira status/links in Chrome for PA-13, PA-15, PA-17, PA-38, PA-41, PA-49, PA-50, PA-55, PMM-2 and PMM-29.
2. Keep PA-41 W2 blocked until PMM-29 contracts are accepted; then import only the approved W2 allowlist.

Sprint 0 progress: PMM-30 done (DEC-006, PR #9); PMM-2 spike merged (PR #10: ADR-0001 + DEC-007, LE-1 pilot entity filled, stays Draft until accountant Q1-Q4 + remaining entities); PMM-9 + PMM-10 done (PR #12: `docs/governance/assumptions-register.md` 11 entries, `risk-register.md` 13 risks, both Jira Done). **PMM-29 = bot lane (claimed, do not duplicate).** Proxima engineering lane: PA-41 W1 + SCN-008 adapter slice done; after Jira sync, queue PMM-11, PMM-8, PMM-12 unless Mike reorders. PMM-31 needs explicit Mike approval (VPS operations). PMM-2 closes only at ADR Accepted.

**Coordination note (2026-08-17, updated 2026-08-18).** This repo has a second executor: `mihailzhamba-bot` opens PRs against Jira PMM issues (PR #9 was the first). Mike's lane split, resolved 2026-08-18: **PMM-29 (contracts) = bot lane**, claimed in the PMM-29 Jira comment; the Proxima agent does NOT start it. Proxima agent completed PMM-9 + PMM-10 (governance registers, PR #12, merge `4a6b23a`, both Jira issues Done). Always `git fetch` before assuming local `main` is current; never run the same PMM task on both lanes.

In parallel on Track A: confirm closure of COLLECTOR-WB-BRANCHES with Mike in Jira PA (epic PA-36); if DONE, move it to TASKS "Done". **PA-39 audit complete (2026-08-23, see Completed); PA-41 W1 verbatim-import + SCN-008 slice done** (does not wait for PMM-29), which unblocks PMM-5/20/23 after Jira sync.

Two things need Mike before they can move: the pilot XLSX (Phase 2 plan 02-02) and four Jira components in the PMM UI (`governance`, `w1-slice`, `delivery`, `finance`) — the MCP has no endpoint for creating them.

## Backlog audit 2026-08-17

The M2 backlog was audited against primary sources (JQL counters + repo files). Three verification claims of run `aios-run-2026-08-17` did not hold, and four critical-path blockers had no issue at all. Full write-up: `docs/exec-plans/active/pmm-audit-2026-08-17.md`; corrections recorded in the run manifest under `verification_correction`.

Headline: M2 existed twice. Epic PA-37 had nine children; five duplicated the PMM slice one-for-one, because phase B1 built its existing-map from PA-37…PA-42 while PA-43…PA-48 had been created a day earlier. Mike's decision: PMM is the single home of M2/M3. PA-43/45/46/47/48 closed (label `superseded-by-pmm`, reversible); PA-38/39/41/44 stay in PA as Track B infrastructure. New issues PMM-29…33 close the blockers. Fix label: `aios-fix-2026-08-17`.

Note for anyone touching the LLM layer: DEC-006 now permits LLM runtime and client-facing web UI outside the M1 contour under three conditions (staging data only, `unreleased` marking, release pointer unmoved). WB WRITE, Ozon, WB Advertising and Torgstat automation remain forbidden.

---

Last updated: 2026-08-29
