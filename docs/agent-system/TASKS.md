# TASKS — PROXIMA AI

> Snapshot of task state in this repo. Full backlog lives in Jira project PA (zhamba.atlassian.net); this file mirrors only what an agent needs to resume work.

## Snapshot 22.09.2026, 13:06 UTC — PR/merge review

По запросу Mike выполнен аудит 9 открытых PR, последних мёржей #162–164 и D42 `ca8a67e`: `docs/audits/2026-09-22-pr-and-merge-review.md`. **Аудит завершён; merge/release readiness не подтверждена.** Блокеры: public compose/provision/auth, rollback runbook, незавершённая WORKS-TODAY-приёмка, LOOP bind/cancel. Полный локальный verify `ca8a67e` прошёл с pg-roundtrip PASS; CI main `24d585f` восстановлен и зелёный. #145/#147 уже merged. Подробные решения для всех открытых PR и порядок исправлений — в отчёте; внешних записей и деплоя в рамках аудита не было. Основной продуктовый трек остаётся утренней сводкой; аудит не открывает работы по октябрьским функциям.

## Дневной прогон 08.09.2026 - выполнен (D32)

Epic 4 стартовал: AD-19 (#87), Stories 4.0 (#95), 4.1 (#100 + #102), 4.2 (#104), 4.3 (#106) в `main`; follow-ups 3.1/3.2/3.3 (#90, #97), проба 3.0 (#91), runbook 1.14 (#99), compose-fix блокера релиза (#103), чек-лист готовности (#93), таблица версий (#92), Jira-журнал (#94). Отчёт, инциденты и что держит релизы - `HANDOFF.md`, раздел «День 08.09.2026». Трек сбора данных (D35, с ~10:30 UTC): девять PR #108-#116 в `main`, репетиция цепочки 1.14 на VPS - 4× SUCCEEDED - раздел «Active main task» ниже; 4.4 (разметка Владислава, PMM-126) и Epic 5 заморожены до трёх SUCCEEDED утр; релизы 1.14/2.6 - по D33 (#89, параллельная сессия) с Владиславом и словом «деплой».

## Ночной прогон 07-08.09.2026 - выполнен (D31)

Семь единиц смержены в `main`: 1.8 (#73), KF-3 (#75), 3.2 (#76), 3.1 (#78), PA-65 (#80), 3.3 (#82), гигиена M-01 (#85, Q21a); мост #81, D31 #72. `blocked` нет. Отчёт, инциденты, таблица синхронизации Jira и рекомендации - `HANDOFF.md`, раздел «Ночь 07-08.09.2026». Ждёт Mike: approve таблицы Jira; решения по открытым вопросам 3.1/3.2/3.3 (в PR); включение `codex-conductor.timer` после обновления его чекаута; следующий шаг - AD для Story 4.0.

## Snapshot 03.09.2026 (модули M-06+)

Модули приняты решением D29 и заведены в Jira: 10 эпиков PMM-63…PMM-72 и 50 задач PMM-73…PMM-122, все в `Backlog`, все с меткой `modules-run-2026-09-03`. Таблицы ключей — `docs/state/JIRA-SYNC-MODULES-2026-09-03.md`.

Реализация модулей начинается после гейта M-03 30.09. Раньше идёт эпик предпосылок PMM-63: два архитектурных решения (остатки OQ-13, ML-платформа OQ-11), живая проба финансового API (OQ-14), два READ-токена, решение по персональным данным (OQ-15) и правка SPEC.

Первый модуль к раздаче — PMM-64 (события и диагноз по SKU): задачи PMM-80…PMM-85 стартуют без единого внешнего решения, PMM-86 и PMM-87 ждут AD об остатках, PMM-88 ждёт записей решений из M-05.

## Snapshot 03.09.2026 (вечер)

Конвейер сведён в `main`: Дирижёр, мост в OpenHands, модули BMAD TEA и BAD. Шесть PR смержены за день, пять открытых остались от эпохи до 30.08 (#34, #32, #31, #26, #3) и ждут решения Mike: закрыть или доработать.

Очередь готова к запуску, три слота: 1.5 (бэкфилл), 1.7 (откат прогона), 2.3 (норма). Вне слотов - Владислав на Story 6.1 и `bmad-architecture` на PA-64 (CR к AD-6, держит мерж 3.1).

BLOCKED: 3.1 держит ротация токена (OQ-10) и PA-64; 1.14 и 2.6 держат даты деплоя в календаре Mike; 6.4 держит отсутствие роли аналитика в боевой базе; запись в Jira держит approve таблиц.

## Snapshot 02.09.2026 (вечер)

- 02.09.2026 PRD v2.2 + дельта epics + Jira sync-brief + роль Владислава: DONE (John); ждёт Mike - даты деплоя, approve брифа, доступы Владиславу, команда на коммит (см. HANDOFF 02.09 вечер).
- 03.09.2026 Документация разработки: dev-onboarding, access-provisioning, observability, incident-runbook, DATA-DICTIONARY, README под лестницу, routing-таблица на действующие требования, исправлены указатели на канон решений: DONE (John); не закоммичено; ждёт Mike - решение по трём расхождениям канона (OQ-16, PA-64) и по конвенциям расчёта (OQ-18).
- 03.09.2026 Роль Владислава v2 (теневой пересчёт цепочки, право блокировать релиз, свои зоны кода) + Epic 6 из пяти историй + PRD v2.3 + D26: DONE (John); ждёт Mike - конвенции расчёта (OQ-18), LOGIN-роль аналитика для чтения базы, approve раздела 4б брифа Jira (см. HANDOFF 03.09).

## Active main task

### План «одна функция» до гейта 30.09 (D42) - active

Решения Mike 21.09 (гриль, D42): приёмка - глазами на `/brief` по домену (1.14+2.6 вместе); чекпоинт Владислава **26.09** - нет 6.1 в `main` → 2.6 деплим 29.09 без теневого пересчёта; домен+Caddy+auth едут с 2.6; вторая функция после гейта - остатки/OOS. Календарь и полный список «ждёт Mike» - `HANDOFF.md`, раздел «День 21.09.2026».

- 22.09 - деплой 1.14 по слову «деплой», тег `v2026.09.22-2`, журнал `2026-09-22-m01.md`.
- 23-25.09 - три утра SUCCEEDED (CAP-1).
- 26.09 - чекпоинт 6.1; 27-28.09 - секреты `BETTER_AUTH_*` + прогон Caddy/auth на стенде; 29.09 - деплой 2.6 (витрина postgres, воронка, порт 3000, Caddy+домен+auth, 80/443); 30.09 - гейт M-03 по ledger + живой экран.
- Кандидат в единицы: раздел домена/Caddy/auth в runbook `release-m03.md` (черновик покрывает только туннельный вариант).
- 22.09 - аудит harper: `make verify` PASS с pg-roundtrip на `08043bb`, карта машины и бэклог - `docs/state/HOST-harper.md`; ветка `docs/d42-grill-plan` (D42 + аудит) запушена, PR/merge - за Mike. Вечер: §3b runbook 2.6 + публичный контур исполнены (`ca8a67e`: auth-роль/схема в provision - проверено живым PG16, боевой overlay, vps-контракт `caddy_https`, `Caddyfile.rehearsal`), полный verify PASS; Codex-ревью - не блокер (бриф в `.autopilot/2026-09-22-public-web-contour/`).

### Дневной прогон 09.09.2026: M1-M5 (D37)

Решение Mike 09.09 (~06:15 UTC, `DECISIONS.md` D37) после ночного отчёта: «запускаем задачи дальше в работу»; заморозка D35 снята, в работе все четыре трека. **Приёмка временная: CI лежит с 18:34 UTC 08.09 - все задания GitHub Actions падают мгновенно, без шагов и логов (вероятно исчерпаны минуты Actions, биллинг проверяет Mike), поэтому единица принимается по локальному `make verify` (ровно один `SKIP` - `pg-roundtrip`), мерж выполняет оркестратор; возврат к «мерж только по зелёному CI» - в тот же день, когда CI оживёт, с прогоном CI на `main` по накопленным мержам.** Без CI не проверяются: тесты с базой (`*.db.test.ts`, `test_*_postgres.py`), `apply-migrations-in-container`, `systemd-analyze verify` юнитов, сборка образов.

- **M1** репетиция наката миграций 007-018 поверх копии боевой схемы 6 из свежего дампа `/var/backups/proxima/2026-09-09-proxima.sql.gz` на одноразовом compose-проекте; боевая база не трогается; закрывает последний непроверенный шаг релиза 1.14 (`docs/state/RELEASE-READINESS-1.14.md` §6 п. 4) - **оркестратор**.
- **M2** Story 4.4, обвязка порога: значение остаётся незаданным (все три поля `null`) до разметки Владислава (Story 6.3), но появляются гейт `threshold: -31 signals, -29 silent, payload carries source` и подпись порога с источником и датой на `/brief` - **Codex**.
- **M3** подготовка Epic 5: черновик AD для Story 5.0 (`decision_records`, роль `proxima_webapp_writer` только INSERT, RLS `WITH CHECK`, атомарный коммит до закрытия экрана, пометка `orphaned` при откате, синтетический прогон `kind = decision`); принятие AD остаётся за Mike - **Claude-субагент по скиллу `bmad-architecture`**.
- **M4** разведка «Источники v2»: черновик эпика по остаткам и финансовому отчёту из уже собранных фактов проб (`docs/state/API-FACTS.md`, разделы про остатки 02.09 и async CSV), без единого живого вызова WB - **GLM**. Черновик: `_bmad-output/planning-artifacts/epics-sources-v2-draft.md` (эпик «Источники v2: остатки и финансовый отчёт»: срез остатков, CSV-история, реестр+гейт, разведка финансового; решение о заведении - за Mike, `DECISIONS.md` пишет Mike).
- **M5** шаг воронки в runbook 2.6: раздел в `docs/operations/release-m03.md` (включение `proxima-funnel-v3@`, временный drop-in до ротации PA-13, недельный `proxima-funnel-csv@`, проверки) - по D33 воронка едет тем же тегом 22.09, своей единицы не имеет - **GLM**.

Уборка диска 06:00-06:30 UTC (оркестратор): `node_modules` и 48 слитых рабочих копий (32 ГБ), висячие образы и кэш сборки Docker (2 ГБ), 25 песочниц OpenHands завершённых бесед моста (27 ГБ), три зависших дерева процессов Codex; занятость диска с 96 % до 56 %. Стенд `proxima-rehearsal` сохранён - нужен для M1.

### Ночной прогон 08-09.09.2026: релизный трек (D36) - выполнен (#119-#130)

Решение Mike 08.09 (~15:00 UTC, `DECISIONS.md` D36): ночь без человека в контуре, только единицы критического пути релизов 1.14 (вт 15.09) и 2.6 (вт 22.09) от `main` `aa32feb`; Codex (`fedor`, один воркер) - код по порядку, GLM - документация параллельно, Claude-субагенты - резерв. Прогон: первый диспатч 15:39 UTC, очередь исчерпана 18:30 UTC того же дня - одиннадцать единиц в `main`, `blocked` ни одной, файл STOP не создавался, 12-часовое окно (до 03:39 UTC 09.09) не выбрано; деплоя, живых вызовов WB, записей в Jira и правок `.github/workflows` не было. Отчёт, инциденты, «Что вошло» и проверка стенда - `HANDOFF.md`, раздел «Ночь 08-09.09.2026» (смержен PR #130).

Код (Codex, профиль `fedor`, по порядку):

- C1 - **done**, PR #119 `fix/compose-provenance-env`: `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID` в `environment:` сервисов `collector`/`control-plane`/`control-plane-admin`, пустое значение → SQL `NULL`, тест `tools/tests/test_compose_collector_mounts.py`; закрыт пункт provenance readiness §6.
- C2 - **done**, PR #121 `feat/analyst-role-provision`: `infra/bootstrap/provision-analyst-role.sh` (read-only LOGIN `proxima_analyst`, таймауты, гранты, файлы секретов `0600 root`, идемпотентность) + таблица грантов и порядок выдачи в `docs/operations/access-provisioning.md` + шаг runbook §1.4 + тест. Блокер B5 ждёт только шага Mike на сервере.
- C3 - **done**, PR #123 `feat/webapp-metrics-postgres`: `orders-day`/`revenue-day` из `fact_cabinet_daily_current`, `freshness` из `data_status_current`; `signals`/`oos-risks` скрыты, `FxBadge` только в fixtures, 2 SELECT на полосу, AD-9 в memlog.
- C4 - **done**, PR #124 `fix/webapp-brief-wording-states`: тексты `/brief` для `blocked` («Данных за день нет») и несовпадения дня сводки.
- C5 - **done**, PR #126 `feat/backup-systemd-units`: `infra/systemd/proxima-pg-backup.{service,timer}` (03:00 МСК, `PROXIMA_RAW_DIR`, `OnFailure`), guard в скрипте, шаг установки в runbook, тест. **2 фикс-раунда**: красный `systemd-verify` (`ExecStart` на отсутствующий в раннере `/usr/local/bin/proxima-pg-backup.sh`), раунд 1 без коммитов, раунд 2 - `/usr/bin/env bash` из чекаута, как у соседних юнитов.
- C6 - **done**, PR #128 `chore/psql-owner-bootstrap`: `infra/bootstrap/proxima-psql-owner` из heredoc runbook §1.4 + `infra/bootstrap/README.md` + тест.

Документация (GLM, при срыве - Claude-субагент):

- G1 - **done**, PR #120 `docs/releases-changelog-skeleton` (GLM): `docs/operations/releases/` (README, TEMPLATE, заготовка `2026-09-15-m01.md`) + `CHANGELOG.md` (Keep a Changelog, Unreleased за 07-08.09).
- G2 - **done**, PR #122 `docs/data-dictionary-012-018` (GLM): миграции 012-018 как существующие таблицы, таблица трёх состояний схемы; строки воронки (017) вернул оркестратор.
- G3 - **done**, PR #125 `docs/inventory-refresh-2026-09-08` (GLM): раздел кода приведён к `main` 018, серверные факты - с датой перепроверки 08.09.
- G4 - **done**, PR #129 `docs/agent-memory-tools-drift` (Claude-субагент; попытка GLM - таймаут exit 5, 90 мин без коммитов, беседа `1d1c1143-777c-54ce-b660-f3fb6dc122f7` осталась запущенной, закрыть в UI OpenHands): цепочка verify, CAS-путь `/srv/proxima-ai/raw`, имена токенов, `apply-migrations` через `control-plane-admin`, новые артефакты репозитория.
- G5 - **done**, PR #127 `docs/release-m03-runbook-draft` (Claude-субагент, резерв): `docs/operations/release-m03.md` - черновик runbook 2.6 (§0 предусловия … §6 журнал), одиннадцать пунктов `UNKNOWN`.

Осталось до 1.14 (вт 15.09): Story 6.1 Владислава в `main` до пт 11.09 (CP-12); слово «деплой» от Mike + шаги runbook §1 на сервере (переименование токенов, `.env`, raw-каталог); создание роли аналитика на сервере (скрипт C2 готов, запускает Mike); B6 копия артефактов в S3 - `UNKNOWN`.
До 2.6 (вт 22.09): ротация analytics-токена PA-13; конфликт порта 3000 с ручным контейнером `proxima-webapp-staging` (нужно решение Mike); шаг воронки едет тем же тегом, своей единицы не имеет; форма релизного тега 2.6 не определена; окно наблюдения расходится - D33 даёт 23-29.09, AC Story 2.6 - 24-30.09.
Стенд `proxima-rehearsal` (postgres 5434, webapp 3434) работает и ждёт Mike: после C3 полоса метрик проверена на живых данных, `/brief` в postgres-режиме - гибрид (сводка, аномалии, полоса настоящие; дайджест, вердикт, сигналы, подпись переключателя кабинетов - FX-фикстуры до Epic 5). Уборка - `bash tools/rehearsal_run.sh down --root ~/orca/rehearsal && sudo rm -rf ~/orca/rehearsal` (`rm -rf` - с подтверждения Mike).
Заморожено (D35): Story 4.4, Epic 5, «Источники v2». Не в очереди: `tools/verify_shadow.py` (ждёт эталоны 6.1), тела деплоя 2.6/3.4, S3/токены/накат поверх дампа.

### Запуск сбора данных на сервере: подготовка релиза 1.14 (D35) - выполнен 08.09 (#108-#117)

Решение Mike 08.09 (~10:30 UTC, `DECISIONS.md` D35, + «Дополнения по репетиции» ~13:40 UTC): конвейер сбора построен в `main`, но на сервере не запускался ни разу (схема 6 против 18, `collector_runs` нет, таймеров нет, данные WB - 25.08); плюс баг релизного пути - `WB_ALLOW_LIVE_NETWORK=1` не выставлен нигде в контуре деплоя. Октябрь заморожен, все исполнители - на трек запуска. Единицы (все в `main` 08.09):

- U-A1 - **done**, PR #110 `fix/live-network-env`: `WB_ALLOW_LIVE_NETWORK=1` у сервиса `collector` в `infra/compose.yaml` + гейт `tools/verify_live_network.py` (`make live-network`) + runbook §3/§5.
- U-A2 - **done**, PR #111 `feat/rehearsal-stack`: `infra/compose.rehearsal.yaml` + `tools/rehearsal_run.sh`, compose-проект `proxima-rehearsal`, postgres `127.0.0.1:5434`, runbook «Репетиция на VPS (D35, не деплой)»; боевая база и `/srv/proxima-ai` не тронуты.
- U-A3 - **done**, PR #113 `docs/readiness-1.14-v2`: `docs/state/RELEASE-READINESS-1.14.md` v2 (блокеры B1-B10) + блок конвейера в `docs/state/WORKS-TODAY.md` + исполнитель runbook по D7.
- U-A4 - **done**, PR #109 `chore/story-1.11-done`: Story 1.11 `done`, объём отгружен в 2.5 (CP-5).
- Репетиция на VPS с живым хвостом - **проведена** 13:10:14-13:11:55 UTC на `main` `1c5e256`: `backfill`/`collect`/`norm`/`brief` SUCCEEDED, ровно 2 read-вызова на боевом statistics-токене (прошёл `assertLeastPrivilegeToken`), W10 649 | 700 860.50 сошёлся с пересчётом фикстуры, W35 по дням 8/8 PASS; факты - PR #112 (`API-FACTS.md`), правило гейта §4 + определение заказов + дополнение D35 - PR #116; отчёт - `HANDOFF.md`, «Трек сбора данных (08.09, после D35)». Стенд `proxima-rehearsal` (`~/orca/rehearsal`, webapp `:3434`) работает, пока Mike не посмотрит `/brief`; уборка - `bash tools/rehearsal_run.sh down --root ~/orca/rehearsal && sudo rm -rf ~/orca/rehearsal` (`rm -rf` - с подтверждения Mike), остановить при уборке и превью на фикстурах `127.0.0.1:3100`.
- Находки репетиции - **done**: PR #114 (`MetricStrip` скрыт при `supportsMetrics=false`, postgres-режим давал 500; текст «Сводка ещё не считается», пока первой сводки нет), PR #115 (секрет webapp `1001:1001` в provision, `init` репетиции, runbook §1.2/§1.4, memlog). D35 - PR #108.

Осталось до релиза 1.14 (вт 15.09, D33): B1 Story 6.1 Владислава в `main` до пт 11.09 (CP-12, waiver D26 не пишется); B2 слово «деплой» от Mike + runbook §1 на сервере (токены под AD-13, `.env`, raw-каталог) - Mike или Claude по слову «деплой»; B5 LOGIN-роль аналитика (Story 6.4, состав грантов не предложен); B6 копия артефактов в S3 - `UNKNOWN`, за Mike.
До 2.6 (вт 22.09): настоящие метрики дашборда в postgres-режиме (follow-up к Story 2.5); ротация analytics-токена PA-13.
Кандидаты в единицы (не запланированы, readiness §6): `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID` через `environment:` compose (provenance ledger на сервере будет `NULL`); инкрементальный накат 007-018 на дамп боевой базы в репетиционном проекте; противоречивые тексты `/brief` для `blocked` и несовпадения дня; `proxima-psql-owner` в `infra/bootstrap/`, `docs/operations/releases/`, `CHANGELOG.md` - не созданы.
Заморожено до трёх SUCCEEDED утр подряд на сервере (D35): Story 4.4, Epic 5; «Источники v2» (остатки, финотчёт, реклама, цены) - после первого утра, эпик не создан.
### Аналитик, неделя 2 (08.09.2026, D33)

Владислав: Epic PMM-123 «Верификационный контур» - Story 6.1 (PMM-124) до пт 11.09 как предусловие релиза 1.14 (вт 15.09), 6.2 до пн 14.09, 6.3 до 21.09; задачи PMM-129..132 (сверка с кабинетом, SM-3, API-FACTS, OQ-10); долг DoD недели 1 - PR по PMM-58/59. Журнал Jira - `docs/state/JIRA-SYNC-2026-09-08.md`; материал созвона - артефакт «Владислав · неделя 2». Второй пакет Jira (ответы на его вопросы) - после подтверждения Mike.

### BMAD + BAD с делегированием реализации в OpenHands — implementation done (2026-09-01)

Ветка `feat/bad-pipeline` (замена `feat/bmad-bad`, PR #47 закрыт как перенесённый). TEA-модуль, цели `claude-code`/`openhands`, BAD 1.2.0, мост `tools/orchestrator/bad_dev_story.sh` + 12 офлайн-тестов, решение **D28** (записано как D25 01.09, переномеровано при мерже 03.09), гейт «BAD не стартует при активном Дирижёре». Живой прогон моста пройден 01.09. Через мост забраны и отревьюены stories 1.3 (PR #48) и 2.2 (PR #46) - обе в `main`. PR #43 (Дирижёр) смержен 03.09; вендоренные деревья записаны в `provenance/import-inventory.json`. Подробности - `docs/agent-system/HANDOFF.md`.


### PA-41 W1 + SCN-008 adapter slice — implementation done (2026-08-27)

Главная цель: V1-сигнал. PA-41 W1 импортирован из source pin `53b7d604` строго по 18-файловому allowlist; destination SHA-256 совпадает 18/18. `pydantic==2.13.4` добавлен в control-plane и `uv.lock` обновлён.

Проверка: `make verify` PASS (131 тест, 1 skip); W1 evidence приведён к фактическому срезу без claims о неимпортированных W2/DB поверхностях. SCN-008 adapter slice на импортированном fixture завершён и покрыт e2e-тестом; W2 остаётся за PMM-29.

COLLECTOR-WB-BRANCHES (former active task, implementation landed at `1a211c9`..`8b07249`): closure still unconfirmed with Mike in Jira PA (epic PA-36) — kept below in Queue until confirmed.

## Queue

1. COLLECTOR-WB-BRANCHES closure: confirm with Mike / Jira PA (epic PA-36), then move to Done. Implementation arc `99fea05` → `dc68839` → `1a211c9` (+`8b07249`), verify green 2026-08-18.
2. PMM (M2/M3 backlog среза): **PMM-29** остаётся за `mihailzhamba-bot`; не дублировать. После успешного PA-41 W1 - PMM-11, PMM-8, PMM-12.
3. Track B PA-39: **аудит завершён 2026-08-23** - артефакты `docs/audits/pa-39-scenario-engine-audit.md` + `pa-39-import-allowlist.yaml` (27 записей: W1 18 / W2 8 / settings-adaptation 1) + `pa-39-hash-transcript.txt` (27/27 PASS); machine-верификация поймала и закрыла ошибку переноса хэша; reviewer re-check: 0 blockers после фиксов. Ключевые решения grill-сеанса: пин `53b7d604`, PMM-29 проектирует контракты с нуля (PA-41 adaptation-коммитом перепривязывает), PA-41 = W1 (не ждёт PMM-29) + W2 (после PMM-29). W1 verbatim импортирован и SCN-008 adapter slice завершён 2026-08-27; W2 ждёт PMM-29.
4. ~~Phase 2 `02-02`~~ — **cancelled by Mike 2026-08-25**; выбран вариант A: закрыть Phase 2 с descope criterion №5 и перенести visible facts в Phase 3/6. Документальный синк и Jira-переход ещё не выполнены.
5. Phase 2 leftovers: CI pipeline green run on the cancellation/revert PRs; observed-XLSX parser больше не нужен (02-02 отменён; машина уезжает в Phase 4).
6. From Mike (inputs): READ-only Analytics перевыпуск (не горит; закрывает RW-исключение), production Bogatova token, interview slots, AI-ops analyst onboarding (02.09: аналитик = Владислав, хартия `docs/agent-system/roles/analyst-vladislav.md`, доступы по чек-листу §3), COGS data; инвентаризация прочих юрлиц для ADR-0001 (Q2) и подтверждение ставок бухгалтером (Q1, Q3, Q4).
7. Онбординг Владислава: маршрут первой недели - `docs/agent-system/ONBOARDING-analyst-week1.md` (шаги хартии §8). Ручные шаги Mike: NDA, приглашения в GitHub и Jira, проверка branch protection на `main`, копия каталога фикстур. Доступ к серверу и к боевой базе не выдаётся - роль в базе заводится отдельной единицей (Story 6.4).

## Done (recent)
- 2026-08-28 PMM-5 (LLM Analyst W1) done: `proxima_control_plane.diagnosis` (fixtures-first, mock LLM, draft-схема, DATA anti-injection, fail-closed retry/timeout, rollback-флаг, JSONL-аудит, CLI run/eval) + eval 12/12; PR #29 merged `6c29398`, make verify PASS, Jira Готово (DoD PMM-12). Известные ограничения PMM-31 - в Jira-комментарии 10377. Грилль-бриф: `docs/exec-plans/active/pmm-5-llm-analyst-w1.md`.

- 2026-08-25 PA-13 rollback: revert `fd95fcb` (`make verify` PASS) + VPS deploy + полная диагностика токенов (батч 2026-08-16 мёртв по подписям, канал чист) + RW №4 установлен; Plan 02-02 cancelled решением Mike.
- 2026-08-18 PMM-2 (SPIKE tax regimes) merged PR #10 (`7acd0a8`): ADR-0001 + DEC-007, LE-1 (пилот) заполнен; ADR Draft до Q1-Q4 и инвентаризации прочих юрлиц. Post-merge review: 0 blockers / 3 warnings (doc-tails, закрыты в PR `docs/pmm2-postmerge-review`).
- 2026-08-17 Аудит M2-бэклога: снят двойной бэклог M2 (PA-37 имел 9 детей, пять дублировали срез — PA-43/45/46/47/48 закрыты, метка `superseded-by-pmm`, откат обратим); DEC-006 снял конфликт с DEC-005; заведены PMM-29…33 под четыре блокера критического пути; сироты разведены по эпикам, достроен граф связей, проставлены метки спринтов. Отчёт: `docs/exec-plans/active/pmm-audit-2026-08-17.md`; rollback JQL `labels = "aios-fix-2026-08-17"`.
- 2026-08-17 PMM backlog-slice run: 28 issues созданы в PMM (company-managed), верифицированы, manifest в `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`; rollback JQL `labels = "aios-run-2026-08-17"`. Три верификационных утверждения прогона позже опровергнуты аудитом (см. `verification_correction` в манифесте).
- 2026-08-14 `1a211c9` test(collector): prove BLOCKED cancels detached WB branches.
- 2026-08-14 `dc68839` fix(collector): cancel detached WB branches when a run leaves RUNNING.
- 2026-08-14 `99fea05` feat(collector): abortable sleep and run cancellation helpers.
- 2026-08-14 `5603f50` docs(runbook): pin warehouse mapping effective_from and service sales warehouses.
- 2026-08-14 `a4b0ed6` feat(collector): persist rate-limit response headers in raw evidence.

---

Rules: one active main task; new ideas go to the Jira backlog, not here — **M1 / Track A / Track C → PA, M2 / M3 → PMM** (split recorded in `.planning/PRODUCT-VISION.md`, section «Трекер», 2026-08-17); update this file at every state change of the active task.
