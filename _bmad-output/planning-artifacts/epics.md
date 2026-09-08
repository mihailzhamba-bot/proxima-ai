---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/specs/spec-wb-morning-brief/SPEC.md
  - _bmad-output/specs/spec-wb-morning-brief/glossary.md
  - _bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md
  - DECISIONS.md
  - docs/state/BACKLOG-REVIEW.md
  - docs/state/API-FACTS.md
  - _bmad-output/planning-artifacts/prds/prd-PROXIMA-AI-2026-08-28/prd.md (v2.2, 02.09.2026)
  - _bmad-output/planning-artifacts/sprint-change-proposal-2026-09-02.md
updated: 2026-09-02
---

# PROXIMA AI - Epic Breakdown

## Overview

Нарезка лестницы M-01..M-05 (утренняя сводка WB с отклонениями от нормы, кабинет `amirova-test`) на эпики и единицы работы для OpenHands (`bmad-build-auto`). Источники: SPEC.md (CAP-1..8), ARCHITECTURE-SPINE.md (AD-1..18), DECISIONS.md (D1-D22), BACKLOG-REVIEW.md. UX-контракта нет (D19: веб-морду доделываем, `bmad-ux` не запускался).

Единица работы = один сеанс OpenHands + один связный PR + один результат, который Mike проверяет одним действием (D7, спека). В единицу кладётся только принятое решение со ссылкой на AD/D.

## Requirements Inventory

### Functional Requirements

FR1: Система ежедневно забирает из WB Statistics заказы (`orders`) и продажи (`sales`) кабинета за прошедшие дни и накапливает дневной ряд кабинета (`fact_cabinet_daily`). [CAP-1, AD-2, AD-6]
FR2: Повторный прогон сбора за тот же день не создаёт дублей: то же наблюдение - `DO NOTHING`, новая версия дня - только по прогону. [CAP-1, AD-2, AD-3]
FR3: При подключении кабинета система загружает всю доступную историю (сейчас с 01.03.2026, окно WB ~6 мес) до того, как окно её вытеснит; недельные суммы совпадают с фикстурами 30.08 (W10 = 649 / 700 860 ₽, W35 = 225 / 263 089 ₽). [CAP-2, AD-2, AD-6]
FR4: На `/brief` виден статус данных: до какой даты есть полный день и когда прошёл последний успешный сбор. [CAP-3, AD-7, AD-9]
FR5: При отсутствии успешного сбора более 24 часов или при `last_full_day < вчера` `/brief` показывает явное предупреждение вместо цифр. [CAP-3, AD-7, AD-9]
FR6: Каждое утро система считает норму кабинета: медиану заказов без отмен и медиану выручки за 14 календарных дней перед оцениваемым днём (сам день исключён); при `sample_days < 14` - статус `insufficient`. На фикстурах 30.08 для 29.08 норма = 34.5 заказа и 34 595 ₽. [CAP-4, AD-8, D21]
FR7: Каждое утро `/brief` показывает вчерашний (последний полный) день против нормы в процентах по заказам и выручке; цифры показываются только при `brief.status='ok'`, `stale=false` и `brief_day = last_full_day`. [CAP-5, AD-9]
FR8: Система ежедневно забирает воронку по nmId через `v3 sales-funnel` (окно 7 дней, пакеты ≤ 20 nmId) и копит её в `fact_funnel_daily`. [CAP-6, AD-5]
FR9 (октябрь, D23): Система еженедельно (понедельник) получает воронку через async CSV `DETAIL_HISTORY_REPORT` и промоутит её в те же наблюдения и факты (`source='csv'`); не более одного созданного отчёта в сутки; в сентябре CSV не собирается. [CAP-6, AD-5, D23]
FR10: Любой прогон можно удалить целиком одной командой (`tools/delete_run.py --tenant --run`), включая транзитивно зависимые нормы и сводки; `--dry-run` печатает счётчики. [AD-3]
FR11 (октябрь, M-04): Система отделяет сигнал от шума и ранжирует отклонения по потерянной выручке в разрезе SKU и категории. [CAP-7]
FR12 (октябрь, M-05): К каждой аномалии система даёт гипотезу причины и что проверить, с источником каждой цифры. [CAP-8]

### NonFunctional Requirements

NFR1: Источник данных - только официальный WB API кабинета, только READ-эндпоинты из реестра (`orders` 10/мин, `sales` 1/мин, `v3 sales-funnel` 3/мин, `nm-report/downloads` 3/мин); `reportDetailByPeriod` и `supplier/stocks` запрещены; 429 - ожидание по `X-Ratelimit-Retry`, ≤ 3 повторов. [AD-4, API-FACTS]
NFR2: Тесты не ходят в сеть: `FixtureTransport` + обезличенные фикстуры ≤ 200 КБ в git; полные ответы - VPS + S3; в тестовом окружении токены не заданы. [AD-4, D15]
NFR3: Обратимость: каждая новая строка несёт `run_id`, прогон = три вида транзакций (RUNNING autocommit; артефакты autocommit; данные + SUCCEEDED одна транзакция; FAILED отдельно), частичных данных не существует. [AD-3]
NFR4: Multi-tenant: `tenant_id` и RLS по шаблону 009 в каждой новой таблице, view с `security_invoker`, гранты и политики на базовые таблицы; job никогда не подключается superuser-URI (исключения: `apply-migrations`, фаза 1 `funnel_csv`). [AD-11, AD-13]
NFR5: Секреты не покидают VPS: токены и URI ролей - файлы `/etc/proxima-ai/secrets/` (`1010:1010 0600`) через compose `secrets:`; значения никогда в env, логах, артефактах, фикстурах. [AD-6, AD-13]
NFR6: Сервер для агентов - только чтение; деплой только по явному «деплой» от Mike с записанным планом отката; релиз = тег + образы; миграции additive-only с self-checksum (`verify_migrations.py`), не откатываются. [AD-14, AD-15, D7]
NFR7: Единица работы = один сеанс OpenHands + один PR + один результат, проверяемый Mike одним действием; в единице - только принятое решение со ссылками на AD/D. [D7, спека]
NFR8: Без авторизации и ролей до октября; auth-зона webapp, `services/control-plane/src/proxima/`, `business-signal` pipeline и `raw-store.ts` заморожены. [AD-18, D19]
NFR9: Сроки: первая единица M-01 ушла в OpenHands 31.08.2026 (условие D19/D23 закрыто); M-03 работает к 30.09.2026; бэкфилл (Story 1.5) в main не позже 08.09.2026 и запускается в первом деплое M-01 до включения таймеров; скорость сдвига окна WB - `UNKNOWN` (снимки 30.08 и 31.08 оба начинаются с 01.03); серверный релиз 1.14 - не позже 20.09 при выполненном бэкфилле, релиз 2.6 - не позже 23.09 `[ожидает календаря Mike]`. [D6, D19, решения 1 и 5а 02.09]
NFR10: Перед каждым релизом прогоняется `WORKS-TODAY.md` целиком; `make verify` - гейт (на маке/CI; в сандбоксе OpenHands гейт = CI); RLS-тест под реальными ролями в `make verify`. [AD-11, AD-12, спека]
NFR11: Наблюдаемость: JSON-строка на событие с `run_id`/`tenant_id`/`kind`/`step`, `collector_runs` - единственный источник статуса, `OnFailure` → Telegram-канал монитора, `stale` на `/brief` как dead-man. [AD-17]
NFR12: Время: `calendar_day` в Europe/Moscow по полю WB `date` через единственный helper (TS/Python/SQL-форма), `OnCalendar` с явным TZ, `CURRENT_DATE` в `db/` запрещён. [AD-7]
NFR13: Контракты: любая форма данных через границу сервиса - JSON Schema в `contracts/`, TS через `make codegen` (расширить на webapp), Python через dataclass + jsonschema; деньги строкой в JSON, `numeric(14,2)` в БД. [AD-10]

### Additional Requirements

- AR1 Миграции `011`-`016` по плану AD-14: run ledger (`collector_runs`, `collector_run_inputs`, `wb_raw_artifacts`, роль `proxima_run_janitor` + политики, `collector_run_id` в `fact_attempt_runs`/`wb_analytics_report_tasks`); `stg_wb_orders_obs`/`stg_wb_sales_obs` + `_latest`; `fact_cabinet_daily` + `_current` + `data_status_current`; `stg_wb_funnel_obs`/`fact_funnel_daily` + `_current`; `norm_daily` + `_current`; `brief_daily` + `brief_current` + роли `proxima_job_collector`/`proxima_job_norm`/`proxima_webapp_readonly` с грантами и политиками на базовые таблицы. Все проходят `tools/verify_migrations.py`. [AD-11, AD-14]
- AR2 Образы и compose: `services/collector/Dockerfile`, `services/control-plane/Dockerfile` (multi-stage, контекст - корень, `USER 1010`), корневой `.dockerignore`, сервисы `collector`/`control-plane` в `infra/compose.yaml` (`profiles: [jobs]`, `secrets:`, `env_file: infra/jobs.env`), `infra/webapp.staging.compose.yaml` (auth off, loopback :3000, `WEBAPP_DATA_MODE`, `WEBAPP_TENANT_ID`, `WEBAPP_DATA_DATABASE_URI` из секрета). [AD-6, AD-15]
- AR3 Планировщик: `infra/systemd/proxima-morning@.{service,timer}` (05:30 Europe/Moscow, `Persistent`, `User=root`, `ProtectHome`, `OnFailure=proxima-alert@%n`), `proxima-funnel-csv@.{service,timer}` (Пн 06:30), `proxima-alert@.service` (Telegram монитора), `tools/morning_run.sh <tenant>` (collect → norm → brief, стоп на первой ошибке, `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID`); `proxima-funnel-v3@.{service,timer}` (06:15 МСК, свой `OnFailure`) - после утверждения CR к AD-6 (решение 4а 02.09); до утверждения действует прежняя цепочка `collect → funnel_v3 → norm → brief`, риск записан в PRD §14. [AD-6]
- AR4 Роли вне ledger: `infra/bootstrap/provision-runtime-roles.sh` (идемпотентный, после миграций): LOGIN `proxima_collector`, `proxima_norm`, `proxima_webapp`, `proxima_janitor` (+ `GRANT DELETE`), база `proxima_test`, LOGIN `proxima_sandbox` (CONNECT только к `proxima_test`), `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC`, URI-файлы `/etc/proxima-ai/secrets/<user>_uri`. [AD-11, AD-12]
- AR5 WB-клиент: `services/collector/src/wb/{client,transport,fixture-transport,msk-day}.ts` (реестр эндпоинтов и бюджетов поверх `RecordedHttpClient`), `tools/verify_wb_client.py` в `make verify` (URL только в реестре, запрет `setInterval`/`node-cron` на `src/**`, запрет write-эндпоинтов), `tools/record_fixture.ts` (артефакт → обезличенная фикстура), фикстуры `services/collector/tests/fixtures/wb-api/`. [AD-4]
- AR6 Проверки живым API внутри единиц (разрешены D22): `flag=0` + `dateFrom` фильтрует по `lastChangeDate` (2 read-вызова) и `count(*) = count(distinct srid)` на фикстурах - до агрегатора; async CSV create/status/file и глубина `startDate` (≤ 3 вызова) - до фазы 2 `funnel_csv`. [AD-2, AD-4, AD-5]
- AR7 Контракты: `contracts/{cabinet-daily,norm,brief}.schema.json`, принять `signal`/`diagnosis`/`decision-record` из `origin/mihailzhamba-bot/pmm29-contracts`; `tools/generate_contract_types.mjs` расширить на `services/webapp/src/lib/contracts/`; удалить копию схемы внутри пакета diagnosis; удалить ручные `types.ts` из ai/pa-50 после codegen. [AD-10]
- AR8 Helper дня: `services/collector/src/wb/msk-day.ts`, `proxima_control_plane/common/msk_day.py`, SQL-форма `(now() AT TIME ZONE 'Europe/Moscow')::date`; тест на границу полуночи. [AD-7]
- AR9 Обратимость: `tools/delete_run.py --tenant --run [--dry-run]` (транзитивное замыкание по `collector_run_inputs`), RLS-тест «без GUC - ошибка, не нули». [AD-3]
- AR10 Тестовая база: `tools/test_db_refresh.sh` (terminate → DROP WITH FORCE → CREATE → `pg_dump | psql -v ON_ERROR_STOP=1` → GRANT sandbox → `ALTER ROLE proxima_sandbox SET proxima.tenant_id`), `make test-db-refresh`, еженедельная проверка восстановления (Пн до `funnel_csv`); OpenHands `.env.task` → URI `proxima_sandbox`. [AD-12, AD-17]
- AR11 Первый релиз M-01 (операции на сервере, по явному «деплой»), порядок обязателен: оживить чекаут `/srv/proxima-ai/repo` (на 02.09 - detached на `fd95fcb` от 25.08, `remote` пуст, 210 коммитов позади main, таймеров нет, миграции 001-006): восстановить `origin`, тег `v2026.09.0-baseline`, перевести на релизный тег; `mv` токенов в `<tenant>_wb_<category>_token` с chown `1010:1010`; миграции и provision; бэкфилл из артефактов 30.08 (`cas_import.ts` → `backfill --source artifact:…` → `collect --date-from`) и только после SUCCEEDED - `systemctl enable --now proxima-morning@amirova-test.timer`; включить `PROXIMA_RAW_DIR` в ночной бэкап; `CHANGELOG.md` + план отката. Вывод `~/proxima-webapp-staging`, ручного контейнера и пустых `proxima_dev` - октябрь. [AD-13, AD-15, AD-17; CP-1]
- AR12 Control-plane: `psycopg` в `dependencies`; модули `norm/` (loader, median, writer, cli) и `brief/` (builder, cli); `wb_async_report.py` - убрать автосоздание `tenants`. [AD-5, AD-8, AD-9]
- AR13 Webapp: `postgres-provider.ts` из `origin/ai/pa-50` реализовать (собственный `Pool`, `set_config` на connect, `WEBAPP_TENANT_ID` валидация, два SELECT из `brief_current`/`data_status_current`, правило показа цифр), `WEBAPP_DATA_MODE=postgres` только после первого SUCCEEDED `brief`. [AD-9]
- AR14 Переиспользование веток через ревью (D14): `origin/ai/pa-50` (провайдер), `origin/mihailzhamba-bot/pmm29-contracts` (схемы), `origin/mihailzhamba-bot/pmm-20-scn-001-…` (детектор, M-04), `origin/mihailzhamba-bot/pa41-full-w2-phase3` (перенумеровать `010` после `016`, M-04+); `PA-03-02-promotion`, `pa-9`, `stash/pa-27` - списать.
- AR15 Старый бэклог (BACKLOG-REVIEW): 16 задач свернуть, 4 закрыть как сделанные (PA-16, PA-27, PA-49, PMM-5), 20 переписать под ступени; Done-без-кода PMM-8 и PA-29 - закрыть честно. В Jira - только после Ворот 3 (D17): 6 эпиков по ступеням + задача на единицу работы.
- AR16 Наблюдение после релиза: сутки; для сводки - «пришла ли на следующее утро с верными цифрами»; не пришла - откат, не починка на боевом (конвейер, шаг 9).

### UX Design Requirements

Нет UX-контракта: веб-морда доделывается на существующем каркасе (D19); единственное UI-изменение в сентябре - экран `/brief` читает `brief_current`/`data_status_current` и показывает предупреждение при `stale`/`insufficient`/`blocked` (FR4, FR5, FR7).

### FR Coverage Map

FR1: Epic 1 - ежедневный сбор orders/sales в дневной ряд кабинета
FR2: Epic 1 - идемпотентность повтора (наблюдения + версии по прогону)
FR3: Epic 1 - бэкфилл истории (Story 1.5: артефакты 30.08 + живой хвост)
FR4: Epic 1 - статус данных на /brief (last_full_day, collected_at)
FR5: Epic 1 - предупреждение stale вместо цифр
FR6: Epic 2 - норма = медиана 14 дней, insufficient при < 14
FR7: Epic 2 - вчера против нормы в % на /brief
FR8: Epic 3 - воронка v3 ежедневно (окно 7 дней)
FR9: Epic 3 (октябрь) - воронка async CSV еженедельно, промоушен в те же факты
FR10: Epic 1 - delete_run транзитивно, --dry-run
FR11: Epic 4 (октябрь) - аномалии с приоритетом по деньгам
FR12: Epic 5 (октябрь) - план действий с источниками

Трассировка требований PRD v2.2 (FR-1..FR-40) к историям - раздел «PRD v2.2 → истории» в конце файла.

NFR1-NFR13 действуют во всех эпиках; AR1-AR11 - Epic 1; AR7, AR12, AR13 - Epic 2; AR5, AR6 (async CSV), AR12 (`wb_async_report.py`) - Epic 3; AR14 - Epic 2 (pa-50, pmm29) и Epic 4 (pmm-20, pa41); AR15 - после Ворот 3 (Jira); AR16 - каждый релиз.

## Epic List

### Epic 1: Данные кабинета собираются сами (M-01)
Mike открывает `/brief` и видит «данные до <вчера>, обновлено сегодня 05:xx»; в БД дневной ряд заказов и продаж кабинета Амировой с 01.03.2026, пополняется каждое утро без участия человека; любой прогон можно откатить одной командой. Внутри - весь конвейер: WB-клиент с фикстурами и гейтом, миграции 011-013, образы и systemd, роли, первый релиз на сервере с бэкфиллом. Первая единица маленькая и обкатывает конвейер целиком.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR10

### Epic 2: Норма и утренняя сводка (M-02 + M-03, граница сентября)
Каждое утро `/brief` показывает «вчера: N заказов против нормы M (−x %), выручка …» по медиане 14 дней; цифры прячутся при stale/insufficient. Внутри: контракты `norm`/`brief` (+ `signal` из pmm29), control-plane `norm/` и `brief/`, миграции, реализация `postgres-provider.ts`, переключение `WEBAPP_DATA_MODE=postgres`. Использует Epic 1, не требует Epic 3.
**FRs covered:** FR6, FR7

### Epic 3: Воронка копится фоном (M-01b)
Воронка по nmId копится из v3 ежедневно с первого серверного релиза, в котором едет Story 3.1 (план - тег 2.6, не позже 23.09); async CSV - октябрь (D23), затем еженедельно; к 27.10 - N недель, N = (27.10 − дата первого успешного `funnel_v3` на сервере)/7 ≈ 5 (PRD SM-7). Внутри: миграция воронки, `jobs/funnel-v3.ts`, `funnel_csv` (две фазы), таймер понедельника, проверка глубины async CSV. Использует Epic 1, независим от Epic 2 по коду (миграции перенумеровываются при мерже).
**FRs covered:** FR8, FR9

### Epic 4: Аномалии с приоритетом (M-04, октябрь)
В сводке появляются ранжированные по потерянной выручке аномалии по SKU/категории, шум отсечён. Внутри: измерение SKU и категории с писателем `fact_order_counts` (4.0), адаптер детектора `pmm-20` к `fact_*_current` (4.1), ранжирование по деньгам (4.2), аномалии на `/brief` (4.3), порог тревоги как значение конфигурации с источником и датой (4.4; предварительно 30 % на падение, решение 6а 02.09). Policy Layer (FR-20/FR-21 PRD) в M-04 не строится - CM-20. Использует Epic 2 и Epic 3.
**FRs covered:** FR11 (PRD FR-1, FR-8, FR-9, FR-25, FR-34)

### Epic 5: План действий (M-05, октябрь)
К каждой аномалии - гипотеза причины и что проверить, с источником каждой цифры. Внутри: AD записи из webapp (5.0), `diagnosis/` с реальным LLM-провайдером и eval-гейтом (5.1), диагноз в сводке (5.2), запись решения и сверка (5.3). Использует Epic 4.
**FRs covered:** FR12 (PRD FR-4, FR-5, FR-12, FR-14, FR-15, FR-16, FR-18, FR-35)

### Epic 6: Верификационный контур (независимая проверка расчётов)
Каждое число цепочки независимо пересчитано человеком (Владислав) своим кодом от исходных данных, эталоны лежат в репозитории, гейт `make verify` роняет сборку при расхождении. Внутри: теневой пересчёт сентябрьской цепочки (6.1), гейт сверки с эталоном (6.2), инструмент и разметка ретро-тревог (6.3), доступ аналитика к данным и пересчёт на живых данных (6.4), пересчёт октябрьского контура (6.5). Не создаёт продуктовых требований - проверяет существующие.
**FRs covered:** независимая проверка FR1-FR12 (PRD FR-26..FR-32, FR-1, FR-8, FR-9, FR-34)


## Epic 1: Данные кабинета собираются сами (M-01)

Mike открывает `/brief` и видит «данные до <вчера>, обновлено сегодня»; в БД дневной ряд заказов и продаж кабинета `amirova-test` с 01.03.2026, пополняется каждое утро без участия человека; любой прогон откатывается одной командой. Каждая история = один сеанс исполнителя + один PR + одна проверка Mike. Исполнитель по умолчанию - OpenHands (`bmad-build-auto`); истории с пометкой **[Claude]** выполняет Claude (нужны токены на VPS или запись на сервер). Ссылки: AD-1..AD-7, AD-11..AD-15, AD-17 (спайн v3.3); D7, D14, D15, D21, D22.

Правила для всех эпиков: (1) `tools/verify_migrations.py` запрещает пропуски в нумерации - номера в историях целевые; ветка, мержащаяся второй, перенумеровывает свои миграции с пересчётом self-checksum (AD-14); AC не содержат «ledger N/N». (2) Имена секретов и env-переменных - только из таблицы Conventions спайна; история не вводит своих. (3) Каждый job пишет JSON-лог по Conventions через `log.ts` / `log.py`.

### Story 1.0: Шаг 0 - живые проверки, артефакты и обвязка **[Claude]**

As a оператор конвейера,
I want до первого сеанса OpenHands снять с сервера всё, что требует токенов или сервера, и починить обвязку исполнителя,
So that исполнитель работал только на фикстурах, а бэкфилл имел готовые артефакты.

**Acceptance Criteria:**

**Given** разрешение D22 на 2 read-вызова
**When** с VPS выполняются `orders?dateFrom=<run_day-3>&flag=0` и `sales?dateFrom=<run_day-3>&flag=0`
**Then** в `docs/state/API-FACTS.md` раздел «flag=0 семантика (дата)» с формулой вердикта: если в ответе есть строки с `date < dateFrom` и `lastChangeDate >= dateFrom` - фильтр по `lastChangeDate` (AD-4 остаётся); если все `date >= dateFrom` - фильтр по дате, AD-4 меняется на `dateFrom = run_day-14` записью в memlog спайна; на полной фикстуре `orders` 30.08 записан результат `count(*) = count(distinct srid)`

**Given** два полных ответа 30.08 в `~/signal-inputs/fixtures/wb-api/statistics/supplier-{sales,orders}/…flag-0.json`
**When** для них вычисляются sha256 и берётся `retrieved_at` из имени файла (UTC-метка)
**Then** оба sha256 и `retrieved_at` записаны в `docs/state/API-FACTS.md` (раздел «Артефакты для бэкфилла») - вход для Story 1.5 и runbook (импорт в CAS на VPS делает `tools/cas_import.ts` в Story 1.14); `infra/backup/proxima-pg-backup.sh` снят с сервера в git как есть (`sha256` совпадает); формат дампа (`gzip | age`) и наличие identity `/etc/proxima-ai/secrets/backup_age_key.txt` подтверждены read-only и записаны в API-FACTS/INVENTORY; обезличенные фикстуры `services/collector/tests/fixtures/wb-api/{statistics/orders,statistics/sales,analytics/sales_funnel_v3_history,analytics/nm_report_downloads}/*.json` (≤ 200 КБ; инструмент `tools/anonymize_fixture.py`: nmId → детерминированный хэш, артикулы → `sku-<n>`, суммы × случайный коэффициент 0.8-1.2 с сохранением дней и структуры) закоммичены в ветку `feat/m01-step0` вместе с инструментом

**Given** `.openhands/hooks/verify-gate.sh` требует `DATABASE_URI`, `npm ci` тянет Chromium, CI на `ubuntu-latest` даёт `pg-roundtrip: SKIP`
**When** обвязка правится в той же ветке
**Then** стоп-хук не требует `DATABASE_URI`; `PUPPETEER_SKIP_DOWNLOAD=1` в `.openhands/setup.sh` и CI; CI-job на `ubuntu-24.04` с `postgresql-16` даёт `pg-roundtrip: PASS`; `make verify` зелёный на маке и в CI
**And** Mike выполняет одно действие: открывает зелёный CI-прогон `feat/m01-step0` с `pg-roundtrip: PASS`

### Story 1.1: WB-клиент с реестром эндпоинтов и гейт - обкатка конвейера целиком

As a оператор конвейера,
I want чтобы единственный WB-клиент с бюджетами лимитов, приёмником артефактов и тестами на фикстурах прошёл все 10 шагов конвейера,
So that следующие единицы шли по проверенному пути.

**Acceptance Criteria:**

**Given** `services/collector/src/wb/{client,transport,fixture-transport,artifact-sink,msk-day}.ts` по AD-4/AD-7: реестр эндпоинтов и бюджетов, `ArtifactSink` (интерфейс) + in-memory реализация для тестов (БД-реализация `WbArtifactSink` и `recording-client.ts` - в Story 1.3), токены через CLI-флаги `--<category>-token-file` по образцу `stockout-signal.ts`; `tools/record_fixture.ts` (артефакт → обезличенная фикстура через `tools/anonymize_fixture.py`)
**When** `make verify`
**Then** новый гейт `tools/verify_wb_client.py` проходит: URL WB только в реестре; реестр = `statistics.orders` (10/мин), `statistics.sales` (1/мин), `analytics.sales_funnel_v3_history` (3/мин), `analytics.nm_report_downloads` (3/мин); `reportDetailByPeriod`/`supplier/stocks` отсутствуют; `setInterval`/`node-cron` не встречаются в `src/**`; `tools/verify_business_signal.py` не изменён
**And** тесты через `FixtureTransport` при незаданных токенах: 429 ждёт по `X-Ratelimit-Retry`, сдаётся после 3 повторов; бюджет не допускает второй `sales` раньше 60 с (виртуальные часы); сетевой вызов падает; `mskDay('2026-08-29T23:30:00Z') = 2026-08-30`, `mskDay('2026-08-29T20:59:59Z') = 2026-08-29`

**Given** PR открыт исполнителем
**When** конвейер проходит шаги 3-10: `bmad-code-review`; `bmad-qa-generate-e2e-tests` на фикстурах с `tests/test-summary.md`; прогон `WORKS-TODAY.md`; тест-запуск = `make verify` в CI; приёмка Mike; мерж + тег `v2026.09.NN-1` + `CHANGELOG.md`; «деплой» = безопасный шаг AR11 п.1 (восстановить `origin` у `/srv/proxima-ai/repo`, тег `v2026.09.0-baseline` на текущий коммит как точка отката, `checkout` нового тега; код не исполняется); наблюдение сутки; Jira закрыта
**Then** все 10 шагов задокументированы в `docs/operations/releases/2026-09-NN-m01-1.md`
**And** Mike выполняет одно действие: `make verify` - `verify_wb_client: PASS`

### Story 1.2: TS↔PG harness в make verify

As a оператор,
I want чтобы collector-тесты с БД выполнялись против одноразового PG16 внутри `make verify` под теми же LOGIN-ролями, что в проде,
So that все следующие истории с БД имели место для тестов без `SET ROLE` и без superuser.

**Acceptance Criteria:**

**Given** `infra/bootstrap/provision-runtime-roles.sh` по AD-11/AD-12 (идемпотентный; параметры: путь к `psql`, каталог секретов; LOGIN `proxima_collector` (член `proxima_job_collector` и `proxima_source_publisher`), `proxima_norm`, `proxima_webapp`, `proxima_janitor` (+ `GRANT DELETE`); база `proxima_test`; `proxima_sandbox` с CONNECT только к `proxima_test`, `BYPASSRLS`; `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC`; URI-файлы по таблице Conventions) и `tools/pg_local_roundtrip.sh` по AD-12: миграции (pytest `apply_migrations`) → provision на одноразовом PG16 (временный каталог секретов) → `npm --workspace @proxima/collector run test:db` (только `*.db.test.ts`, `--test-concurrency=1`; glob `make test` их исключает), DSN каждой роли в `PROXIMA_TEST_DSN_<ROLE>`
**When** `make verify` на маке (Homebrew PG16) и в CI (`ubuntu-24.04` + PG16)
**Then** `pg-roundtrip: PASS` включает `provision: idempotent (2 runs)` и `collector db-tests: N passed`; без PG16 - явный `SKIP`; пример db-теста: под `PROXIMA_TEST_DSN_COLLECTOR` `SELECT 1` проходит, `CONNECT` `proxima_sandbox` к основной базе - отказ
**And** Mike выполняет одно действие: `make verify` - строки `provision` и `collector db-tests` в выводе

### Story 1.3: Реестр прогонов, роли и приёмник артефактов

As a оператор,
I want чтобы у прогонов был единый реестр с ролями, а каждый ответ WB ложился артефактом в CAS и в `wb_raw_artifacts`,
So that любая строка в БД была прослеживаема до прогона и доказательства.

**Acceptance Criteria:**

**Given** `db/migrations/011_run_ledger.sql`: `collector_runs` (kinds по AD-3), `collector_run_inputs`, `wb_raw_artifacts` (все с `tenant_id`, RLS), NOLOGIN-роли `proxima_job_collector`, `proxima_job_norm`, `proxima_webapp_readonly`, `proxima_run_janitor` с грантами и политиками шаблона AD-11, `collector_run_id uuid NULL` в `fact_attempt_runs` и `wb_analytics_report_tasks`; `src/wb/recording-client.ts` (обёртка по AD-4 поверх `raw-store.ts`/`fetchTransport`, артефакт до проверки статуса), `WbArtifactSink` в БД, `src/wb/run-ledger.ts` (RUNNING autocommit / SUCCEEDED в транзакции / FAILED autocommit, GUC на сессию при подключении), `log.ts`
**When** `make verify`
**Then** `verify_migrations.py` проходит; harness: `pg_policies` содержит janitor-политику для каждой таблицы с `run_id`; db-тест под `PROXIMA_TEST_DSN_COLLECTOR`: прогон открыт RUNNING, два артефакта записаны (файл в `PROXIMA_RAW_DIR`, строка в `wb_raw_artifacts`, locator `artifact://business-signal/sha256/<hex>`), прогон закрыт SUCCEEDED; искусственная ошибка → FAILED отдельным autocommit, артефакты остались
**And** Mike выполняет одно действие: `make verify` - `run-ledger: running/succeeded/failed` зелёный

### Story 1.4: Наблюдения заказов и продаж

As a оператор,
I want чтобы прогон сбора записывал наблюдения заказов и продаж с их `lastChangeDate` идемпотентно,
So that повтор не создавал дублей, а поздняя отмена не терялась.

**Acceptance Criteria:**

**Given** `012_stg_wb_orders_sales.sql`: `stg_wb_orders_obs` PK `(tenant_id, srid, last_change_at)`, `stg_wb_sales_obs` PK `(tenant_id, sale_id, last_change_at)`, `canonical_sha256`, view `_latest` (`security_invoker`), гранты/политики collector + janitor; `jobs/collect.ts` (`collect --tenant amirova-test --date-from <d> --statistics-token-file …`, подключение по `COLLECTOR_DATABASE_URI_FILE`) на `FixtureTransport`, использующий Story 1.3
**When** прогон выполняется в harness под `PROXIMA_TEST_DSN_COLLECTOR`
**Then** наблюдения + `SUCCEEDED` в одной транзакции; повтор на тех же фикстурах: 0 новых наблюдений, новая строка `collector_runs`; тот же `srid` с новым `lastChangeDate` - вторая строка, `_latest` отдаёт новую; тот же PK с другим payload - `WB_SCHEMA_DRIFT`, `FAILED`, наблюдений прогона нет
**And** Mike выполняет одно действие: `make verify` - `collect: idempotent replay 0 new rows` зелёный

### Story 1.5: Бэкфилл истории из артефактов и живого хвоста

As a Mike,
I want загрузить всю доступную историю одной командой - из двух сохранённых ответов 30.08 и живого хвоста,
So that март не пропал, даже если релиз случится после того, как окно WB его вытеснит.

**Acceptance Criteria:**

**Given** до старта проверены sha256 двух артефактов 30.08 против `API-FACTS.md` и наличие второй копии в S3 (единственная копия истории до окна WB лежит вне git, D15); срок - в main не позже 08.09.2026, едет одним тегом с 1.14 (решение 5а 02.09; CP-3)
**Given** `tools/cas_import.ts <file> --retrieved-at <ISO> --source official_wb_statistics` (кладёт файл в CAS с манифестом; тот же инструмент используется в runbook на VPS) и `jobs/backfill.ts` по AD-2: `backfill --tenant --source artifact:<sha256_sales>,<sha256_orders> [--retrieved-at <ISO>]` читает артефакты из CAS (регистрирует их в `wb_raw_artifacts` прогона `backfill`), `run_day := mskDay(retrieved_at)` из манифеста или флага; живой режим `backfill --from <d>`: бюджет `sales` 1/мин, при 80 000 строк продолжение с `dateFrom = lastChangeDate` последней строки, `--resume` по последнему `last_change_at`
**When** в harness два синтетических артефакта (структура ответов 30.08, известные суммы) импортированы `cas_import.ts --retrieved-at 2026-08-30T05:59:00Z` и выполняется режим `artifact`
**Then** наблюдения созданы за все дни артефактов, `run_day = 2026-08-30`; повтор - 0 новых; живой режим с виртуальными часами: паузы ≥ 60 с и пагинация на синтетическом ответе из 80 000 строк; зависимые истории (1.6) получают данные только через `backfill --source artifact` на синтетических артефактах - прямые INSERT в `stg_wb_*_obs`/`fact_cabinet_daily` в тестах запрещены
**And** Mike выполняет одно действие: `make verify` - `backfill: artifact replay + pagination` зелёный

### Story 1.6: Дневной ряд кабинета и статус данных

As a Mike,
I want чтобы после прогона в БД лежала версия каждого дня интервала, а view отвечал, до какого дня данные полные,
So that норма и сводка читали один ряд.

**Acceptance Criteria:**

**Given** `013_fact_cabinet_daily.sql` (`fact_cabinet_daily` по AD-2, `fact_cabinet_daily_current` по AD-3, `data_status_current` по AD-7 с `COALESCE(…, true)` и `(now() AT TIME ZONE 'Europe/Moscow')::date`; гранты/политики collector, norm (SELECT), webapp (SELECT), janitor; гейт: `CURRENT_DATE` в `db/` отсутствует) и агрегатор `facts/cabinet-daily.ts` в конце `collect`/`backfill`
**When** прогон выполняется
**Then** версия для каждого дня `[floor, run_day-1]` (день без строк = нули + артефакты прогона); `floor = mskDay(dateFrom)` для `collect`, `--from + 1` для живого `backfill`, первый день артефакта для режима `artifact`; `= run_day` не версионируется; `collector_run_inputs` содержит distinct `run_id` наблюдений свёртки; `dateFrom` для `collect` без флага = `min(run_day-3, last_full_day+1)`

**Given** синтетические артефакты Story 1.5 с известными суммами недель S1 и S2
**When** `backfill --source artifact` + агрегатор выполняются в harness
**Then** суммы `_current` за S1/S2 равны эталону (формулы `glossary.md`); `data_status_current` отдаёт `last_full_day`, `stale = true` при прогоне старше 24 ч (подмена часов) и `false` в пределах 24 ч; сверка с реальными W10/W35 из API-FACTS - на VPS в Story 1.14
**And** условие приёмки (CP-4, 02.09): ветка принимается после мержа 1.5; тест `services/collector/tests/cabinet-daily.db.test.ts` использует `backfill --source artifact` из 1.5 вместо прямых INSERT и не идёт `{ skip }` в `make verify` с PG16 (`PROXIMA_TEST_DSN_COLLECTOR` задаёт harness Story 1.2)
**And** Mike выполняет одно действие: `make verify` - `cabinet-daily: versions every day, S1/S2 sums` зелёный

### Story 1.7: Откат прогона

As a оператор,
I want удалять любой прогон целиком одной командой, включая транзитивно зависимые версии,
So that плохой прогон не оставлял следов.

**Acceptance Criteria:**

**Given** `tools/delete_run.py --tenant <t> --run <uuid> [--dry-run]` по AD-3 (подключение по `JANITOR_DATABASE_URI_FILE`; в harness - `PROXIMA_TEST_DSN_JANITOR`)
**When** выполняется без `--tenant` или без GUC
**Then** ошибка «0 строк для run_id», не нули; с флагами - счётчики транзитивного замыкания по `collector_run_inputs`, удаление в одной транзакции; FAILED - только строка прогона и артефакты; файлы CAS остаются
**And** RLS-матрица в harness по AD-12: ожидания из грантов AD-11 - у роли с грантом на базовые таблицы view отдаёт `> 0` с GUC и `0` без, у роли без гранта - `permission denied`; `pg_policies` содержит janitor-политику для каждой таблицы с `run_id`
**And** Mike выполняет одно действие: `make verify` - `delete_run: closure` и `rls: matrix` зелёные

### Story 1.8: Тестовая база и сандбокс OpenHands

*(октябрь: снята из сентября правилом сжатия, решение 2а 02.09.2026; зона OpenHands в сентябре сдаётся по CI - AD-12; `proxima_test` создаётся provision из Story 1.2, `restore-check` от 1.8 не зависит)*

As a оператор,
I want чтобы тестовая копия базы обновлялась одной командой, а сандбокс OpenHands видел её целиком и только её,
So that агент тестировал на копии данных, не касаясь боевой базы.

**Acceptance Criteria:**

**Given** `tools/test_db_refresh.sh` по AD-12 (`pg_terminate_backend` → `DROP DATABASE proxima_test WITH (FORCE)` → `CREATE` → `pg_dump proxima | psql -v ON_ERROR_STOP=1 proxima_test` → `GRANT ALL ON ALL TABLES IN SCHEMA public TO proxima_sandbox` → `ALTER ROLE proxima_sandbox IN DATABASE proxima_test SET proxima.tenant_id`), цель `make test-db-refresh`, шаблон `infra/openhands/env.task.template` с `DATABASE_URI` из `proxima_sandbox_uri`, обновление `.openhands/hooks/verify-gate.sh` и `docs/agent-system/TOOLS.md` под сандбокс
**When** скрипт выполняется дважды подряд в harness (provision из Story 1.2 уже применён)
**Then** второй запуск проходит; под `PROXIMA_TEST_DSN_SANDBOX` в `proxima_test` `SELECT count(*) FROM fact_cabinet_daily_current` > 0 и `INSERT` в тестовую таблицу проходит; подключение `proxima_sandbox` к основной базе - отказ
**And** Mike выполняет одно действие: `make verify` - `test-db-refresh: sandbox sees copy` зелёный

### Story 1.9: Образы, compose и staging-overlay

As a оператор,
I want чтобы collector и control-plane собирались в образы и запускались одноразовыми контейнерами из compose с секретами по таблице Conventions, а webapp поднимался staging-overlay'ем,
So that на хосте не требовались uv/psql/node_modules.

**Acceptance Criteria:**

**Given** `services/collector/Dockerfile`, `services/control-plane/Dockerfile` (multi-stage, контекст корень, `USER 1010`), корневой `.dockerignore`, сервисы `collector`, `control-plane` (только URI своих ролей) и `control-plane-admin` (owner-секреты; цели `apply-migrations`, `funnel_csv_download`) в `infra/compose.yaml` (`profiles: [jobs]`, `secrets:` по Conventions, `env_file: infra/jobs.env`), `infra/webapp.staging.compose.yaml` (auth off, `127.0.0.1:3000`, `WEBAPP_DATA_MODE`, `WEBAPP_TENANT_ID`, `WEBAPP_DATA_DATABASE_URI_FILE=/run/secrets/proxima_webapp_uri`); `psycopg` в `dependencies`; `make apply-migrations ENV_FILE=infra/jobs.env`
**When** CI выполняет `docker build` обоих образов, `docker compose config` базы и overlay, `apply-migrations` внутри `control-plane-admin` против service-container PG16
**Then** всё зелёное; `.env` и `node_modules` в контексте отсутствуют; в `config` сервис `collector` не имеет owner-секретов
**And** Mike выполняет одно действие: открывает зелёный CI-прогон с job'ами `build-images`, `apply-migrations-in-container`

### Story 1.10: Принять провайдер данных webapp из ветки ai/pa-50

As a оператор,
I want принять через ревью ветку `origin/ai/pa-50` (интерфейс `DataProvider`, `WEBAPP_DATA_MODE`, fixtures-provider, заглушка postgres-provider) без реализации SQL,
So that следующая история писала только `postgres-provider.ts`.

**Acceptance Criteria:**

**Given** ревью ветки по D14 (5 файлов `lib/data/*` и карточка сигнала; ручной `types.ts` помечен временным до Story 2.2)
**When** перенесено в PR от `main`
**Then** `npm --workspace @proxima/webapp test`, `run typecheck`, `run lint` зелёные; `WEBAPP_DATA_MODE` пусто → fixtures, неизвестное → ошибка при старте; postgres-режим бросает `NOT_IMPLEMENTED`; auth-зона не изменена
**And** Mike выполняет одно действие: `make verify`

### Story 1.11: Статус данных на /brief

*(объём перенесён в Story 2.5 правилом сжатия, решение 2а 02.09.2026; AC ниже - спецификация строки статуса, исполняется в 2.5; закрывается вместе с 2.5; ключ трекинга и задача PMM-49 сохраняются)*

As a Mike,
I want видеть на `/brief` строку «данные до <дата>, обновлено <время>» и предупреждение вместо цифр, если сбор не проходил больше суток,
So that я всегда знал, можно ли верить экрану.

**Acceptance Criteria:**

**Given** `postgres-provider.ts` в части статуса по AD-9 (v3.2): собственный `Pool` по URI из файла `WEBAPP_DATA_DATABASE_URI_FILE`, `pool.on('connect')` с `set_config('proxima.tenant_id', $1, false)` и `.catch`, `WEBAPP_TENANT_ID` валидируется `^[a-z0-9][a-z0-9_-]{2,63}$`, один `SELECT` из `data_status_current`; режим `postgres` до первого SUCCEEDED `brief` = «только статус»: `getBrief()` отдаёт fixtures-brief с пометкой «сводка ещё не считается»
**When** `data_status_current` отдаёт `last_full_day=2026-09-09, collected_at=…, stale=false`
**Then** на `/brief` строка «Данные до 09.09, обновлено 10.09 05:41»; при `stale=true` или пустом view - «Сбор не проходил больше суток» вместо цифр; `UnreleasedBanner` не снимается
**And** vitest через шов (мок `Pool`): stale/не stale/пусто; `test`, `typecheck`, `lint` зелёные; auth-зона не изменена
**And** Mike выполняет одно действие: `make verify` - тест `provider: data status states` зелёный (живой экран - в Story 1.14)

### Story 1.12: Планировщик, алерт и бэкап в git

As a оператор,
I want systemd-юниты утреннего прогона, алерта и проверки восстановления, скрипт шагов и скрипт бэкапа под контролем git,
So that расписание и восстановление были воспроизводимы.

**Acceptance Criteria:**

**Given** `infra/systemd/proxima-morning@.{service,timer}` (`OnCalendar=*-*-* 05:30:00 Europe/Moscow`, `Persistent=true`, `User=root`, `ProtectHome=true`, `OnFailure=proxima-alert@%n.service`), `proxima-alert@.service` (Telegram монитора), `proxima-restore-check@.{service,timer}` (Пн 06:00: последний локальный дамп `/var/backups/proxima/*.sql.gz` → `gunzip | psql proxima_test` после `DROP/CREATE` + `SELECT count(*) FROM fact_cabinet_daily_current`, AD-17; факт 31.08 - plain gzip), `tools/morning_run.sh <tenant>` (шаг `collect`; шаги `funnel_v3`/`norm`/`brief` добавляются своими эпиками; пути секретов по таблице Conventions; `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID`), `infra/backup/proxima-pg-backup.sh` из Story 1.0 + `PROXIMA_RAW_DIR` в набор бэкапа + установка на место серверного (`install` в runbook)
**When** CI выполняет `systemd-analyze verify`, `bash -n`, shellcheck; `morning_run.sh --dry-run` печатает команды `docker compose --profile jobs run --rm …`
**Then** без ошибок
**And** Mike выполняет одно действие: открывает зелёный CI-прогон с job `systemd-verify`

### Story 1.13: Runbook первого релиза

As a оператор,
I want пошаговый runbook релиза M-01 с планом отката, где каждая команда - копипастой с ожидаемым выводом,
So that релиз выполнялся без импровизации.

**Acceptance Criteria:**

**Given** `docs/operations/release-m01.md` по AD-15/AR11
**When** Mike читает его
**Then** разделы в строгом порядке (CP-1, 02.09): (0) оживление чекаута - `/srv/proxima-ai/repo`: восстановить `origin`, тег `v2026.09.0-baseline` на текущий коммит как точка отката, `checkout` релизного тега, проверка, что миграции 007-010 на боевом ещё не применены; (1) подготовка - `mv` токенов в `<tenant>_wb_<category>_token` + chown 1010, `provision-runtime-roles.sh`; (2) деплой без таймеров - build → `apply-migrations` через `control-plane-admin` → `compose up -d` с overlay (bridge-порт пересоздаёт postgres на ~10 с); (3) бэкфилл - проверка sha256 двух артефактов 30.08 против `API-FACTS.md` → `cas_import.ts` с `--retrieved-at` → `backfill --source artifact:<sha256_sales>,<sha256_orders>` → живой хвост `collect --date-from 2026-08-27`; (4) проверка - W10 = 649 / 700 860 ₽ и W35 = 225 / 263 089 ₽ в `_current`, `data_status_current.last_full_day` = вчера (SQL), `WORKS-TODAY.md`; строка статуса на `/brief` - релиз 2.6; (5) включение таймеров - `systemctl enable --now` `morning` и `restore-check` только после SUCCEEDED бэкфилла; (6) проверка алерта - намеренно уронить `proxima-morning@` в тестовом прогоне и получить сообщение в Telegram; `TimeoutStartSec` юнита и ретрай алерта (PA-65) на месте; (7) откат - тег baseline + `delete_run.py` по прогонам релиза + `WEBAPP_DATA_MODE=fixtures`, миграции не откатываются; (8) наблюдение 3 дня (CAP-1); `CHANGELOG.md`. Раздел «октябрь» (не условие релиза): вывод `~/proxima-webapp-staging`, ручного контейнера, пустых `proxima_dev`, `env.task` в зону, `test_db_refresh`, установка `infra/backup/*`
**And** Mike выполняет одно действие: читает runbook и не находит шага, требующего объяснений

### Story 1.14: Первый релиз M-01 на сервере **[Claude]**

As a Mike,
I want чтобы после моего «деплой» конвейер M-01 работал на VPS и наутро статус на `/brief` обновился сам,
So that данные кабинета копились с сентября.

**Acceptance Criteria:**

**Given** Stories 1.0-1.7, 1.9, 1.10, 1.12, 1.13 смержены (1.8 - октябрь, 1.11 - в составе 2.5: правило сжатия), в том числе 1.5 с реальным бэкфиллом (без синтетических строк); теневой пересчёт шагов 1-4 и 6 (Story 6.1) выполнен - расхождений нет либо каждое объяснено записью в `docs/state/SHADOW-RECONCILIATION.md` (CP-12); тег `v2026.09.NN-2`, runbook по CP-1, явное «деплой» от Mike (D7); дата деплоя стоит в календаре Mike - не позже 20.09.2026 при выполненном бэкфилле (13.09 без него) `[ожидает календаря Mike]`
**When** Claude выполняет runbook шаг за шагом, фиксируя вывод в `docs/operations/releases/2026-09-NN-m01.md`
**Then** миграции применены полностью; provision идемпотентен; бэкфилл из артефактов 30.08 + живой хвост SUCCEEDED; `fact_cabinet_daily_current` содержит дни с 02.03.2026 по вчера; W10 и W35 совпадают с API-FACTS; `WORKS-TODAY.md` прогнан и дополнен (таймеры активны, `data_status_current`, `restore-check`); план отката записан до первого шага; порядок исполнения - бэкфилл → первый `collect` → включение таймеров (CP-1); утренний прогон `collect` завершается SUCCEEDED и `data_status_current` обновлён не позже 06:30 МСК (PRD FR-22; `brief_current` появляется в релизе 2.6), превышение видно как алерт через `TimeoutStartSec` юнита `proxima-morning@` с `OnFailure` (задача PA-65 sync-brief 03.09, до релиза 1.14)
**And** три утра подряд `collector_runs` содержит SUCCEEDED `collect` (CAP-1); `data_status_current` отдаёт `last_full_day` = вчера и `stale = false` (проверка SQL под `proxima_webapp_readonly` через `ssh -N proxima-db`, пункт `WORKS-TODAY.md`); строка статуса на `/brief` появляется в релизе 2.6 (Story 2.5 с объёмом 1.11); не пришёл - откат по плану; Владислав в течение суток после релиза повторяет шаги 1-4 и 6 теневого пересчёта против боевых данных (Story 6.4) и заполняет первую строку журнала сверки с кабинетом (`docs/state/CABINET-RECONCILIATION.md`) по дню, закрытому не менее 3 суток назад
**And** Mike выполняет одно действие: по пункту `WORKS-TODAY.md` одной командой через `ssh -N proxima-db` видит `last_full_day` = вчера и `stale = false`; экран `/brief` со строкой статуса - в релизе 2.6

## Epic 2: Норма и утренняя сводка (M-02 + M-03, граница сентября)

Каждое утро `/brief` показывает «вчера: N заказов против нормы M (−x %), выручка …» по медиане 14 дней; цифры прячутся при stale/insufficient. Использует Epic 1. Миграции целевые `014`-`015`; при мерже после Epic 3 - перенумеровать. Ссылки: AD-8, AD-9, AD-10, AD-11, AD-14; D14, D21.

### Story 2.1: Принять контракты сигнала из ветки pmm29

As a оператор,
I want принять через ревью `signal`, `diagnosis`, `decision-record` из `origin/mihailzhamba-bot/pmm29-contracts` с их TS-типами и Ajv-тестом,
So that схема `brief` могла ссылаться на `signal` v1, а не на ручные типы.

**Acceptance Criteria:**

**Given** ревью ветки по D14 (26 файлов); пакет `diagnosis` не трогается (его схема draft.v1 остаётся до Story 5.1)
**When** перенесено в PR от `main`, `make codegen` перегенерировал типы collector
**Then** `make verify` зелёный, включая `product-contracts.test.ts` и `verify_contracts.py`; `services/webapp/src/lib/data/types.ts` пока остаётся (удаляется в 2.2)
**And** Mike выполняет одно действие: `make verify`

### Story 2.2: Контракты нормы и сводки с генерацией типов для webapp

As a оператор конвейера,
I want схемы `cabinet-daily`, `norm`, `brief` в `contracts/` и генерацию типов для collector и webapp,
So that control-plane и webapp читали один контракт.

**Acceptance Criteria:**

**Given** `contracts/{cabinet-daily,norm,brief}.schema.json` по AD-9/AD-10 (деньги строкой, `schema_version`, `source_refs` minItems 1, `signals[]` со `$ref` на `signal.schema.json` v1 из Story 2.1), synthetic-примеры; `tools/generate_contract_types.mjs` расширен на `services/webapp/src/lib/contracts/`; `proxima_control_plane/common/msk_day.py` с тестом границы полуночи
**When** `make verify`
**Then** `make contracts` валидирует схемы и примеры; `make codegen` без diff при повторе; `services/webapp/src/lib/data/types.ts` удалён, импорты на `lib/contracts/`; webapp `typecheck` зелёный
**And** Mike выполняет одно действие: `make verify` - `contracts: PASS`, `codegen` без diff

### Story 2.3: Норма по медиане 14 дней

As a Mike,
I want чтобы каждое утро система считала норму заказов и выручки как медиану 14 календарных дней перед оцениваемым днём и записывала её версией по прогону,
So that сводка и детекторы сравнивали «вчера» с одной нормой.

**Acceptance Criteria:**

**Given** `014_norm_daily.sql` (`norm_daily` по AD-8, `UNIQUE (tenant_id, evaluation_day, metric, run_id)`, `norm_daily_current`, RLS, гранты/политики norm (`FOR ALL`), webapp (SELECT), janitor) и `proxima_control_plane/norm/` (`loader.py` через psycopg по `NORM_DATABASE_URI_FILE`, GUC на сессию, `median.py`, `writer.py`, `cli.py`: `python -m proxima_control_plane.norm run --tenant amirova-test [--date]`, `log.py`)
**When** прогон выполняется в harness на синтетическом ряду с известной медианой
**Then** `norm_daily` содержит `orders`/`revenue` по окну `[eval-14, eval-1]`, `sample_days = 14`, `status = ok`; `collector_runs` `kind = norm`, `run_inputs` записаны; при 5 удалённых версиях - `sample_days = 9`, `status = insufficient`; повтор - новая версия, `_current` отдаёт последнюю SUCCEEDED; сверка с реальным 29.08 (34.5 / 34 595 ₽) - на VPS в Story 2.6
**And** Mike выполняет одно действие: `make verify` - `norm: median window, insufficient 9/14` зелёный

### Story 2.4: Материализованная сводка дня

As a Mike,
I want чтобы после нормы система собирала сводку дня в БД по контракту `brief` с отклонением и статусом,
So that экран только читал готовый результат.

**Acceptance Criteria:**

**Given** `015_brief_daily.sql` (`brief_daily`, `brief_current` = одна строка на tenant, RLS, гранты/политики norm (`FOR ALL`), webapp (`FOR SELECT` на `brief_daily`), janitor) и `proxima_control_plane/brief/` (`builder.py`, `cli.py`)
**When** прогон выполняется после Story 2.3 на синтетике (вчера: 27 заказов, 41 141 ₽; норма 34.5 / 34 595)
**Then** `brief_daily.payload` валиден по `contracts/brief.schema.json`: `deviation_pct = {orders: -21.7, revenue: 18.9}`, `signals = []`, `source_refs` непустой, `status = ok`, `data_status` скопирован из view; `norm.status = insufficient` → `insufficient`; нет версии за `evaluation_day` → `blocked`; `run_inputs` записаны; RLS: `proxima_webapp_readonly` видит `brief_current` с GUC и 0 без
**And** Mike выполняет одно действие: `make verify` - `brief: payload valid, orders -21.7%` зелёный

### Story 2.5: /brief показывает вчера против нормы

As a Mike,
I want открыть `/brief` утром и увидеть вчерашние заказы и выручку против нормы с отклонением,
So that я за 10 секунд понимал, упали продажи или нет.

**Acceptance Criteria:**

**Given** `postgres-provider.ts` в части статуса по Story 1.11 (`Pool` по URI из файла, `set_config('proxima.tenant_id', $1, false)` на connect, валидация `WEBAPP_TENANT_ID`, `SELECT` из `data_status_current`, режим «только статус» до первого SUCCEEDED `brief`) реализуется в этой истории (CP-6); `postgres-provider.ts` дополнен `getBrief()` по AD-9 (второй `SELECT` из `brief_current`, сгенерированные типы, правило `brief.status = 'ok' AND stale IS FALSE AND brief_day = last_full_day`), блок сводки на `/brief` (компоненты `brief/`, без новых зависимостей, `UnreleasedBanner` остаётся): заказы и выручка - значение / норма / отклонение %, цвет по знаку через `lib/gyr`; `tools/morning_run.sh` получает шаги `norm` и `brief`
**When** `brief_current` содержит сводку за вчера
**Then** «29.08: 27 заказов против нормы 34.5 (−21.7 %), выручка 41 141 ₽ против 34 595 ₽ (+18.9 %)» + строка статуса; `insufficient` - «норма копится: 9/14 дней»; `stale` или пустой view - «Сбор не проходил больше суток» вместо цифр (AC 1.11); строка «Данные до <дата>, обновлено <время>»
**And** vitest через шов: ok/insufficient/stale/blocked и состояния статуса из 1.11 (stale/не stale/пусто); `test`, `typecheck`, `lint` зелёные; auth-зона не изменена
**And** Mike выполняет одно действие: `make verify` - тест `provider: brief states` зелёный (живой экран - в Story 2.6)

### Story 2.6: Релиз M-03 - сводка приходит каждое утро **[Claude]**

As a Mike,
I want чтобы после «деплой» сводка считалась на сервере каждое утро и цифры совпадали с кабинетом WB,
So that к 30.09 утренняя сводка работала без меня.

**Acceptance Criteria:**

**Given** Stories 2.1-2.5 и 3.1 смержены (миграции перенумерованы при необходимости; шаг воронки едет этим же тегом), CR к AD-6 утверждён (задача PA-64 sync-brief 03.09; воронка отдельным юнитом после `brief`), теневой пересчёт шага 7 (сводка: отклонение и статусы) выполнен на синтетике и эталон лежит в `verification/golden/` (Story 6.1, CP-13); тег, релиз-заметка с планом отката, явное «деплой»; дата деплоя не позже 23.09.2026 `[ожидает календаря Mike]` - иначе семь утр 24-30.09 не помещаются (CP-7)
**When** Claude выполняет runbook: `apply-migrations` через `control-plane-admin`, provision (гранты), пересборка образов, ручной первый прогон `norm` + `brief`, включение шагов в `morning_run.sh`, `compose up -d webapp`
**Then** `brief_current` содержит сводку за вчера `status = ok`; норма на VPS за ближайший день с 14 полными сверена с расчётом из артефакта «Ряд продаж Амировой»; `/brief` через туннель показывает цифры; `WORKS-TODAY.md` прогнан и дополнен; план отката: prev tag + режим «только статус» + `delete_run.py`; процедура сверки с кабинетом: эталон - экран кабинета WB и фильтр, зафиксированные первой строкой `docs/state/CABINET-RECONCILIATION.md`; сверяется день, закрытый ≥ 3 суток назад; допуск `[ASSUMPTION]` ±1 заказ и ±0.5 % выручки до решения Mike; расхождение больше допуска = гейт не пройден; сводка «вчера» показывается с пометкой «предварительно» до 14 суток (поздние отмены, решение 5б1)
**And** семь утр подряд 24-30.09 `collector_runs` содержит SUCCEEDED `collect`, `norm`, `brief` (CAP-5) - считается по `collector_runs`, не по доставке алерта; каждое утро Владислав заполняет строку журнала сверки; Mike выполняет одно действие - открывает `/brief` и сверяет вчерашние заказы и выручку с кабинетом WB по процедуре; не пришла - откат. **Релиз не выпускается, пока расхождение теневого пересчёта или сверки с кабинетом не закрыто**: правит наш код, правит свой пересчёт, либо Mike снимает блокировку записью в `DECISIONS.md` (D26)

## Epic 3: Воронка копится фоном (M-01b)

D23: в сентябре только Story 3.1 (v3 ежедневно); CSV-путь - октябрь. Воронка по nmId копится из v3 ежедневно с первого серверного релиза, в котором едет Story 3.1 (план - тег 2.6, не позже 23.09); async CSV - октябрь (D23), затем еженедельно; к 27.10 - N недель, N = (27.10 − дата первого успешного `funnel_v3` на сервере)/7 ≈ 5 (PRD SM-7). Использует Epic 1, независим от Epic 2 по коду; миграция целевая `014` - при мерже после Epic 2 перенумеровать. Ссылки: AD-4, AD-5, AD-6, AD-14; D13, D20, D22.

### Story 3.0: Шаг 0 - глубина async CSV **[Claude]** *(октябрь, D23)*

As a оператор,
I want проверить с сервера, как далеко назад отдаёт async CSV и сколько занимает цикл create → status → file,
So that промоушен строился на фактах.

**Acceptance Criteria:**

**Given** разрешение D22 на ≤ 3 read-вызова
**When** с VPS выполняются create (`startDate` на 6 месяцев назад) → status → file для одного отчёта, не более одного в сутки, с проверкой `nm_report_downloads` до создания
**Then** в `docs/state/API-FACTS.md` раздел «async CSV глубина (дата)»: максимальный `startDate`, размер, время готовности, квота; ответы в фикстуры на VPS; обезличенная synthetic-фикстура структуры `stg_wb_nm_report_rows` в `services/collector/tests/fixtures/` (через `anonymize_fixture.py`)
**And** Mike выполняет одно действие: читает раздел API-FACTS

### Story 3.1: Воронка v3 ежедневно

As a Mike,
I want чтобы каждое утро система забирала воронку за последние 7 дней по активным nmId и версионировала её,
So that к октябрю у детектора была дневная воронка.

**Acceptance Criteria:**

**Given** `014_funnel.sql` (целевой номер; `stg_wb_funnel_obs` PK `(tenant_id, nm_id, calendar_day, source, canonical_sha256)` с `run_id`, `observed_at`, view `_latest`; `fact_funnel_daily`, `fact_funnel_daily_current` с предпочтением `csv`; RLS, гранты/политики collector, norm (SELECT), janitor; поля по `COLUMN_MAP` scn001) и `jobs/funnel-v3.ts` (активные nmId = distinct из `stg_wb_orders_latest` за 30 дней; пакеты ≤ 20; окно `[run_day-6, run_day-1]` - единственная подтверждённая граница `сегодня-6`, `API-FACTS.md`; бюджет 3/мин по спецификации, живой лимит по заголовку ответа фиксируется первым серверным прогоном - замер побеждает спецификацию, PRD §4.0); срок - в работу не позже 08.09.2026, в main до тега 2.6 (PRD FR-30, SM-7; CP-8)
**When** прогон выполняется в harness на фикстуре `sales_funnel_v3_history` (3 nmId, 7 дней)
**Then** 21 наблюдение `source = v3` с `evidence_sha256`, 21 строка в `_current`; повтор - 0 новых (тот же `canonical_sha256`); изменённый payload за тот же день - новое наблюдение и новая версия; `= run_day` не версионируется; шаг `funnel_v3` - отдельный юнит `proxima-funnel-v3@.{service,timer}` (06:15 МСК) со своим `OnFailure=proxima-alert@%n`, не шаг `morning_run.sh` (CR к AD-6, решение 4а; до утверждения CR - шаг после `brief`); каждый прогон перезапрашивает окно целиком, падение одного пакета не отменяет полученные, день считается собранным, когда покрыты все активные nmId; при 429 - ожидание по `X-Ratelimit-Retry`, ≤ 3 повторов (NFR1)
**And** Mike выполняет одно действие: `make verify` - `funnel_v3: 21 obs, replay 0, changed payload versions` зелёный

### Story 3.2: Загрузка CSV как прогон реестра *(октябрь, D23)*

As a оператор,
I want чтобы существующий `tools/wb_async_report.py` создавал прогон `funnel_csv_download` в реестре и не создавал tenant сам,
So that фаза 1 была прослеживаема и не ломала fail-closed.

**Acceptance Criteria:**

**Given** `tools/wb_async_report.py` изменён минимально: автосоздание `tenants` удалено (нет tenant - ошибка); при старте выполняет `set_config('proxima.tenant_id', tenant, false)` и создаёт `collector_runs` `kind = funnel_csv_download` (owner-URI, исключение AD-11 до M-04), пишет `collector_run_id` в `wb_analytics_report_tasks`, закрывает прогон SUCCEEDED/FAILED; `--period from..to` явный; создаёт не более одного отчёта в сутки после проверки `nm_report_downloads`
**When** `make verify` (`tools/tests/test_wb_async_report*.py` расширены)
**Then** тесты: отсутствующий tenant → ошибка; прогон создан и закрыт; второй запуск за день не создаёт отчёт
**And** Mike выполняет одно действие: `make verify` - `wb_async_report: run ledger` зелёный

### Story 3.3: Промоушен CSV в наблюдения и факты *(октябрь, D23)*

As a оператор,
I want чтобы строки скачанного CSV промоутились в те же наблюдения и факты воронки, что и v3,
So that воронка накапливалась и назад, и вперёд.

**Acceptance Criteria:**

**Given** `jobs/funnel-csv-promote.ts` (`collector_runs` `kind = funnel_csv_promote`; `stg_wb_nm_report_rows(task_id)` → `stg_wb_funnel_obs(source = 'csv', evidence = tasks.downloaded_sha256)` → `fact_funnel_daily`; под `proxima_collector` - член `proxima_source_publisher`, читает 003/005 без новой миграции; всегда, независимо от состояния задачи), `proxima-funnel-csv@.{service,timer}` (Пн 06:30; фаза 1 через `control-plane-admin`, фаза 2 через `collector`)
**When** промоушен выполняется в harness на synthetic-фикстуре Story 3.0
**Then** наблюдения `csv` и факты созданы; `_current` предпочитает `csv` там, где есть оба; после `delete_run.py` прогона промоушена повтор восстанавливает факты без нового отчёта; `systemd-analyze verify` зелёный
**And** Mike выполняет одно действие: `make verify` - `funnel_csv: promote + replay after delete` зелёный

### Story 3.4: Релиз воронки **[Claude]** *(октябрь, D23)*

As a Mike,
I want чтобы после «деплой» воронка копилась на сервере сама,
So that к 27.10 воронка накопилась на N недель (PRD SM-7).

**Acceptance Criteria:**

**Given** Stories 3.0-3.3 смержены (миграция перенумерована при необходимости), тег, релиз-заметка с планом отката, явное «деплой»
**When** Claude выполняет runbook: `apply-migrations`, пересборка образов, юнит `proxima-funnel-v3@` (после CR к AD-6) и `systemctl enable --now proxima-funnel-csv@amirova-test.timer`, ручной первый прогон `funnel_v3`
**Then** `fact_funnel_daily_current` содержит 7 дней по активным nmId; `WORKS-TODAY.md` дополнен пунктом «воронка v3 за вчера есть»; релиз-заметка со счётчиками и планом отката
**And** следующим утром и в понедельник `collector_runs` содержит SUCCEEDED `funnel_v3`, `funnel_csv_download`, `funnel_csv_promote`; Mike выполняет одно действие - `WORKS-TODAY.md` пункт «воронка» проходит по записанным шагам

## Epic 4: Аномалии с приоритетом (M-04, октябрь)

В сводке появляются ранжированные по потерянной выручке аномалии по SKU и категории, шум отсечён предварительным порогом 30 % на падение (решение 6а 02.09). Использует Epic 2 и Epic 3. Детальные AC написаны 02.09 по PRD v2.2 §4.C (FR-1, FR-8, FR-9, FR-25, FR-34) и контракту `signal.schema.json`; Policy Layer (PRD FR-20/FR-21) в M-04 не строится - кандидат CM-20. Миграции целевые `016`+ (перенумеровать при мерже). Ссылки: AD-1, AD-3, AD-5, AD-8, AD-10, AD-13, AD-14; D14 (pmm-20, pa41), D21; решения 2а, 6а (02.09). Стартует после гейта 30.09 (правило сжатия).

### Story 4.0: Измерение SKU и категории для аномалий

As a оператор,
I want чтобы у фактов появился разрез по nmId и категории с писателем, принятым через ревью,
So that детектор и сводка считали отклонения по SKU и категории на тех же прогонах, что и кабинетный ряд.

**Acceptance Criteria:**

**Given** предложение AD от `bmad-architecture` (грейн `(tenant_id, calendar_day, nm_id)` для `fact_order_counts`; категория - `subjectName` из payload наблюдений заказов через справочник по nmId, не колонка в каждой строке); ветка `origin/mihailzhamba-bot/pa41-full-w2-phase3` принята через ревью (D14): писатель `fact_order_counts` перенумерован после текущих миграций, `run_id`, RLS по шаблону 009, гранты collector/norm/janitor, без гранта webapp (AD-9, AD-19); `fact_nm_daily` - разрез заказов по nmId, не подмена кабинетного ряда (`story-1.6.md`); существующая таблица `fact_order_counts` из миграции 007 остаётся легаси; **AD-19 принят 08.09 (D32): новая таблица `fact_nm_daily` и словарь `dim_nm_subject` в миграции 018**
**When** прогон `collect` выполняется в harness на фикстурах 30.08
**Then** `fact_nm_daily_current` содержит строку на (день, nmId) с категорией; сумма по nmId за день сравнивается с `fact_cabinet_daily_current.orders` как quality-check (порог расхождения `UNKNOWN` до OQ-7; расхождение пишется в лог `quality_check`, не блокирует прогон); `delete_run.py` удаляет строки транзитивно; `verify_migrations.py` проходит
**And** Mike выполняет одно действие: `make verify` - `order-counts: per-nm sums vs cabinet` зелёный

### Story 4.1: Детектор нормы на реальных фактах

As a оператор,
I want подключить детектор SCN-001 из ветки `pmm-20` к `fact_cabinet_daily_current`, `fact_nm_daily_current` и `fact_funnel_daily_current` через адаптер `loader.py`, с выходом по `contracts/signal.schema.json`,
So that аномалии считались на тех же фактах, что и норма, а не на staging CSV.

**Acceptance Criteria:**

**Given** ветка `origin/mihailzhamba-bot/pmm-20-scn-001-…` списана по D14-ревью 08.09 (D32: REWRITE), детектор пишется заново по каркасу пакета `norm/` с переносом `decomposition.py`, `to_decimal`/`DailyMetrics`, `canonical_hash`; loader читает `fact_nm_daily_current`, `dim_nm_subject_current`, `fact_funnel_daily_current` под `proxima_job_norm` (AD-19); норма SKU по D21 - медиана 14 полных дней по nmId, `insufficient` при < 14 дней; при норме 0 отклонение не вычисляется (статус `insufficient`, `NaN`/`Infinity` в payload не попадают); выход - `signal.schema.json` v1 с `scenario_code`, `rub_assessment` строкой с двумя знаками (AD-10), `source_refs` на факты и расчёт (AD-1)
**When** детектор выполняется в harness на фиксированных фактах (фикстуры + накопленное); этап воронки называется только при ≥ 8 недель воронки, иначе `stage = UNKNOWN`
**Then** результат валиден по схеме; `run_inputs` записаны; окна 7/14/28 детектора живут внутри адаптера и не подменяют норму D21; отклонение по SKU - против нормы SKU, по категории - против суммы SKU категории; `signals[]` не строятся при `brief.status != ok` (PRD FR-7, `[NOTE FOR PM]` закрыт этим AC); деньги под риском - разница нормы и факта по выручке `finishedPrice` (revenue-based; переход к прибыли только для SKU с `cogs_status` из паспорта, PRD FR-9)
**And** Mike выполняет одно действие: `make verify` - `detector: sku deviation, zero-norm insufficient, no signals when not ok` зелёный

### Story 4.2: Порог тревоги и ранжирование по деньгам

*(объём после решения 6а 02.09: ранжирование по деньгам; порог как значение конфигурации - Story 4.4; заголовок сохранён ради ключа трекинга)*

As a Mike,
I want видеть аномалии, отсортированные по потерянной выручке, независимо от того, задан ли уже порог,
So that в сводке первым стояло дорогое.

**Acceptance Criteria:**

**Given** `brief` собирает `signals[]` из результатов детектора (4.1); порог читается из конфигурации control-plane (`alert_threshold_pct`, `threshold_source`, `threshold_date`; значение приходит из Story 4.4, до неё - `null` = порог не применяется, все отклонения ниже нормы попадают в список)
**When** `brief` строится в harness на синтетике с пятью SKU и известными потерями
**Then** список отсортирован по `rub_assessment` по убыванию; аномалия с большей денежной оценкой выше при прочих равных (CAP-7); `brief.status` и правило показа цифр не меняются; `signals[]` пусто при `status != ok`; рост показывается числом и в `signals[]` не попадает (порог односторонний, PRD FR-34)
**And** Mike выполняет одно действие: `make verify` - `brief: signals sorted by rub_assessment` зелёный

### Story 4.3: Аномалии на /brief в разрезе SKU и категории

As a Mike,
I want видеть на `/brief` список аномалий с товаром, категорией и суммой потерь,
So that я знал, куда смотреть первым.

**Acceptance Criteria:**

**Given** `signals[]` в `brief_current` (4.2) и компонент `SignalRow` из каркаса PA-49
**When** открывается `/brief`
**Then** блок аномалий показывает nmId/артикул, категорию, отклонение в %, `rub_assessment` и `scenario_code` без раскрытия строки, `source_refs` - по раскрытию; пустой список - «критичных нет»; при `brief.status = blocked` (нет версии за `evaluation_day`, определение Story 2.4) блок скрыт и показана причина «данных за день нет», при `insufficient` - «норма копится: N/14 дней»; порядок строк = порядок `signals[]`
**And** vitest через шов: ok с сигналами / ok пусто / insufficient / blocked; `test`, `typecheck`, `lint` зелёные; auth-зона не изменена
**And** Mike выполняет одно действие: `make verify` - тест `provider: signals states` зелёный (живой экран - релиз M-04)

### Story 4.4: Порог тревоги как значение конфигурации с источником и датой

As a Mike,
I want чтобы порог тревоги был одним значением конфигурации с источником и датой, который я меняю решением, а не кодом,
So that сводка молчала в шуме и ловила события размера августовского (−36 %).

**Acceptance Criteria:**

**Given** запись в `DECISIONS.md` «порог 30 % на падение; источник - ретро-прогон 184 дней фикстур 01.03-31.08 (снимки 30.08/31.08): доля утр с тревогой при 15/20/30/40 % - 46/31/20/8 %; дата» до релиза 2.6 (PRD FR-34, OQ-7); конфигурация control-plane с полями `alert_threshold_pct = -30`, `threshold_source`, `threshold_date`; разметка ретро-тревог Владислава (Story 6.3, `docs/state/RETRO-ALARM-LABELS.md`) приложена как вход
**When** `brief` строится с заданным порогом
**Then** день с отклонением −31 % попадает в `signals[]`, −29 % - нет; рост не помечается; порог, источник и дата видны в `brief.payload` (`threshold: {value, source, date}`) и на `/brief` подписью; смена порога = новая запись `DECISIONS.md` + новое значение конфигурации, история значений в `CHANGELOG.md`; перекалибровка через две недели живых сводок - отдельное решение Mike; Policy Layer с метаданными не создаётся (CM-20, «правило трёх»)
**And** Mike выполняет одно действие: `make verify` - `threshold: -31 signals, -29 silent, payload carries source` зелёный

## Epic 5: План действий (M-05, октябрь)

К каждой аномалии - гипотеза причины и что проверить, с источником каждой цифры; решение Mike записывается и через срок сверяется с фактом. Использует Epic 4. Детальные AC написаны 02.09 по PRD v2.2 §4.D (FR-4, FR-5, FR-12, FR-14, FR-15, FR-16, FR-18, FR-35) и контрактам `diagnosis`/`decision-record`. Ссылки: AD-1, AD-3, AD-10, AD-11, AD-13; спайн Deferred (LLM-провайдер, eval-гейт); PMM-5, PMM-25, PMM-31, PMM-33; OQ-3, OQ-12, OQ-15. Стартует после M-04.

### Story 5.0: AD записи из webapp

As a оператор,
I want чтобы первая запись из UI в БД (решения по аномалиям, позже ручные вводы) опиралась на архитектурное решение, а не на догадку исполнителя,
So that Story 5.3 и кандидаты с ручным вводом (CM-19, CM-1) строились на одном правиле.

**Acceptance Criteria:**

**Given** единица `bmad-architecture`: предложение нового AD в `ARCHITECTURE-SPINE.md` (роль `proxima_webapp_writer` LOGIN с правом только INSERT в `decision_records`; RLS `WITH CHECK (tenant_id = current_setting('proxima.tenant_id'))`; атомарность «запись до закрытия экрана» - одна транзакция, ответ UI только после commit; записи решений не входят в транзитивное удаление прогонов - при откате помечаются `orphaned` с сохранением текста, автора и даты; каждая запись несёт `run_id` синтетического прогона `kind = decision` и `tenant_id`); исключение из AD-11 «webapp только читает» записано явно (PRD G-9, OQ-8)
**When** AD показан Mike
**Then** AD принят D-записью в `DECISIONS.md`; спайн обновлён; `epics.md` Story 5.3 ссылается на AD по номеру
**And** Mike выполняет одно действие: читает AD и записывает решение

### Story 5.1: Реальный LLM-провайдер диагноза с eval-гейтом

As a оператор,
I want заменить mock-провайдер `diagnosis/` на реальный с детерминированной проверкой чисел и источников и eval-гейтом ≥ 0.80,
So that гипотезы не выдумывали цифры.

**Acceptance Criteria:**

**Given** одобрение Mike на egress с VPS (PMM-31); `adapters/factory.py` получает провайдера через имя env-переменной ключа в `diagnosis.toml`, значение ключа только на VPS (`/etc/proxima-ai/secrets/`), в логах и артефактах значения нет; eval-датасет PMM-33 расширен живыми сигналами M-04; флаг отката `llm_enabled`; JSONL-аудит вызовов; вторая модель в режиме BLOCK (PMM-25) - только после реального провайдера
**When** запускается `python -m proxima_control_plane.diagnosis eval`
**Then** pass-rate ≥ 0.80; любой диагноз с числом или ссылкой не из входа отклоняется валидатором; при `llm_enabled = false` сводка публикуется без диагноза, не падает; тесты не ходят в сеть (mock-провайдер в тестах)
**And** Mike выполняет одно действие: `python -m proxima_control_plane.diagnosis eval` - `pass-rate >= 0.80`

### Story 5.2: Диагноз и «что проверить» в сводке

As a Mike,
I want видеть под каждой аномалией одну главную гипотезу, 2-3 альтернативы и конкретную проверку,
So that утро начиналось с действия, а не с расследования.

**Acceptance Criteria:**

**Given** `signals[].diagnosis` по `contracts/diagnosis.schema.json` в `brief_daily.payload` (`primary_cause`, 2-3 `alternatives`, `unknowns`, «что проверить»); справочник причин и чек-лист «что проверить» из эвристик менеджера (CM-15; источник - `extract-drops-C9.md`, оформляет John до старта 5.2) как вход для `alternatives`; тон объясняющий, LLM не считает - все цифры диагноза из сигнала и фактов
**When** `brief` собирает диагнозы для `signals[]` и открывается `/brief`
**Then** под аномалией - главная причина, альтернативы, `unknowns`, проверка; каждая цифра и ссылка диагноза несёт `source_ref` (валидатор 5.1); fail-closed: сигнал без `source_refs` или без `rub_assessment` не публикуется (PRD FR-4); при недостатке данных - режим UNKNOWN: `unknowns` перечислены, уверенной рекомендации нет, пометка «решение без системной рекомендации» (PRD FR-12); цифр без источника в сводке = 0 (SM-C4)
**And** vitest через шов: диагноз есть / UNKNOWN / сигнал отклонён fail-closed; `test`, `typecheck`, `lint` зелёные
**And** Mike выполняет одно действие: `make verify` - `diagnosis: source_refs on every number, fail-closed` зелёный

### Story 5.3: Запись решения и сверка ожидаемого с фактом

As a Mike,
I want отметить по аномалии «принял/отклонил» и через заданный срок увидеть, сработало ли,
So that система училась на моих решениях.

**Acceptance Criteria:**

**Given** AD из Story 5.0 принят и реализован (миграция `decision_records` с `run_id`, `tenant_id`, RLS `WITH CHECK`, роль `proxima_webapp_writer`); `contracts/decision-record.schema.json` (Story 2.1); причина обязательна только при «отклонил», «принял» - одна кнопка (`[ASSUMPTION]` до OQ-12); срок сверки N = 7 дней и границы «частично» 30-70 % ожидаемого эффекта (`[ASSUMPTION]` до OQ-3)
**When** Mike отмечает решение на `/brief`
**Then** запись создаётся в одной транзакции (кто, когда, принял/отклонил, причина, `expected`, `horizon_days`), отклонённые пишутся тем же контрактом; статус «открыто» до сверки; утренний прогон через `horizon_days` сравнивает `expected` с `actual` из фактов лестницы и записывает исход - подтвердилось / не подтвердилось / частично / UNKNOWN (метрика недоступна - UNKNOWN, не отбрасывается); при откате прогона фактов записи помечаются `orphaned`, не удаляются; сводка показывает исход по решению; счётчики SM-4 (доля решений с записью и сверкой) и SM-9 `[PROPOSED]` (доля «подтвердилось», доля решений, изменённых после сверки) считаются из таблицы
**And** vitest и pytest через шов: запись / отклонение с причиной / сверка четырёх исходов / `orphaned` после `delete_run`; RLS-тест: запись под чужим `tenant_id` отклонена
**And** Mike выполняет одно действие: отмечает решение на `/brief` и на следующее утро видит его в сводке как «открыто»

## Epic 6: Верификационный контур (независимая проверка расчётов)

Каждое число, которое считает наш код, независимо пересчитывается своим кодом человека от исходных данных; расхождение выше допуска блокирует релиз. Исполнитель всех историй - Владислав (роль и метод - `docs/agent-system/roles/analyst-vladislav.md`, шаги и допуски §2.2, эталоны `verification/golden/`, журнал `docs/state/SHADOW-RECONCILIATION.md`). Приёмка - Mike. Ссылки: D26 (решения по роли), AD-1, AD-2, AD-7, AD-8, AD-9, AD-10; SPEC CAP-2, CAP-4, CAP-5; PRD §15.

Ограничение, задающее порядок: деньги в обезличенных фикстурах репозитория умножены на секретный коэффициент 0.8-1.2 и строки прорежены до 200 КБ (`tools/anonymize_fixture.py`), поэтому суммы W10/W35 по репозиторию невоспроизводимы. Сначала эталоны на синтетике (норма, отклонение), затем недельные суммы - на полных фикстурах локально и в приёмке релиза 1.14.

### Story 6.1: Теневой пересчёт сентябрьской цепочки и первые эталоны

As a Mike,
I want чтобы числа сентябрьской цепочки были пересчитаны независимо, чужим кодом и от исходных данных,
So that ошибка в нашей логике нашлась до релиза, а не в день гейта.

**Acceptance Criteria:**

**Given** утверждённые Mike конвенции расчёта (медиана при чётном числе точек, округление денег, округление `deviation_pct` до 0.1 п.п., нумерация недель ISO для W10/W35) и доступ к полным фикстурам 30.08 (`~/signal-inputs/fixtures/wb-api/`, копируется только этот каталог)
**When** Владислав своим кодом считает шаги 1-4, 6, 7 из §2.2 хартии: sha256 артефактов, наблюдения (`count(*) = count(distinct srid)`, доля отмен), версии дней, дневной ряд, норму 14 дней, отклонение и статусы сводки
**Then** в `verification/golden/` лежат файлы эталонов с полями `calculation_id`, `formula_version`, `method`, `source.sha256`, `expected`, `tolerance` (деньги строкой с двумя знаками, AD-10): норма 29.08 = 34.5 / 34 595 ₽ (CAP-4), сводка на синтетике 27 / 41 141 ₽ с отклонением −21.7 % / +18.9 %, наблюдения на фикстурах 30.08 (`srid` 172/172, `saleID` 108/108); каждый шаг имеет строку в `docs/state/SHADOW-RECONCILIATION.md` с вердиктом
**And** расхождения либо закрыты правкой (нашей или его), либо стоят задачами в Jira с меткой блокера; ни одно не остаётся необъяснённым
**And** Mike выполняет одно действие: открывает журнал и видит по строке на каждый из шести шагов

### Story 6.2: Гейт сверки с эталоном в make verify

As a оператор,
I want чтобы подмена числа в нашем коде роняла сборку,
So that эталон работал каждый день, а не только в день, когда его посчитали.

**Acceptance Criteria:**

**Given** эталоны из Story 6.1 и новый верификатор `tools/verify_shadow.py` по образцу `tools/verify_business_signal.py` (только стандартная библиотека, `Decimal` вместо `float`, накопление всех нарушений, `ValueError` с перечислением при провале, строка `shadow reconciliation verification passed` при успехе); цель `shadow` добавлена в `.PHONY` и в зависимости `verify` в `Makefile`; правок `.github/workflows/verify.yml` не требуется - там уже `make verify`
**When** `make verify` выполняется на маке и в CI
**Then** цель `shadow` проходит; подмена любого числа в нашем расчёте роняет `make verify` с указанием шага, ожидаемого и полученного значений; отсутствие каталога эталонов - тоже провал, а не тихий пропуск; гейт файловый и не зависит от локального PostgreSQL (иначе он молча пропускался бы через `pg-roundtrip: SKIP`)
**And** тест верификатора в `tools/tests/test_verifiers.py` через `load_tool("verify_shadow")`: подделанный кейс роняет с сообщением про shadow
**And** Mike выполняет одно действие: `make verify` - строка `shadow reconciliation verification passed`

### Story 6.3: Инструмент ретро-тревог и разметка событий

As a Mike,
I want знать, за какими сработками порога стояли реальные события кабинета,
So that порог тревоги был откалиброван по смыслу, а не по разбросу.

**Acceptance Criteria:**

**Given** `tools/retro_alarms.py` (только чтение полных фикстур заказов, без сети и без базы): для каждого дня 15.03-31.08.2026 - заказы без отмен, норма как медиана предыдущих 14 полных дней, отклонение в процентах, флаг сработки при порогах 15/20/30/40 %
**When** инструмент выполняется и Владислав размечает сработки при 30 %
**Then** `docs/state/RETRO-ALARM-LABELS.md` заполнен: по каждой сработке событие (да / нет / неизвестно), тип, источник знания; итог - доля сработок с событием для каждого порога; «неизвестно» допустимо и не заменяется догадкой
**And** результат приложен как вход к Story 4.4 (порог как значение конфигурации) и к OQ-7
**And** Mike выполняет одно действие: открывает файл и видит итоговую долю по четырём порогам

### Story 6.4: Доступ аналитика к данным и пересчёт на живых данных

As a Mike,
I want чтобы после релиза те же проверки шли против боевых данных, а не только против фикстур,
So that расхождение сбора или нормы на живом кабинете находилось за сутки, а не в день гейта.

**Acceptance Criteria:**

**Given** на боевой базе на 03.09 схема версии 6, RLS выключен, ролей спайна нет (миграция 011 не написана), а единственный read-only путь требует root - поэтому заводится отдельная LOGIN-роль аналитика по образцу `infra/bootstrap/provision-postgres-diagnostics.sh`: `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS`, `default_transaction_read_only = on`, таймауты `statement`/`lock`/`idle_in_transaction`, `GRANT CONNECT` + `USAGE ON SCHEMA public` + `SELECT ON ALL TABLES` + `ALTER DEFAULT PRIVILEGES`; URI-файл `/etc/proxima-ai/secrets/<роль>_uri` с правами `0600`; состав грантов предлагает `bmad-architecture`, роль создаёт Mike на сервере, значение URI передаётся вне чата; процедура выдачи записана в `docs/operations/`
**When** после релиза 1.14 Владислав повторяет шаги 1-4, 6, 7 против боевой базы через туннель `ssh -N proxima-db`
**Then** результаты - строки в `docs/state/SHADOW-RECONCILIATION.md` со ссылкой на `run_id`; расхождение с эталоном блокирует следующий релиз; после включения RLS (миграция 011+) первым statement сессии идёт `set_config('proxima.tenant_id', 'amirova-test', false)`, и в `WORKS-TODAY.md` добавлен пункт с этой командой и ожидаемым результатом
**And** роль не имеет прав записи: попытка `INSERT` завершается ошибкой; `SELECT` вне разрешённых таблиц - `permission denied`
**And** Mike выполняет одно действие: `psql "$DATABASE_URI" -c "SELECT 1"` под ролью аналитика проходит, `INSERT` - нет

### Story 6.5: Пересчёт октябрьского контура

As a Mike,
I want чтобы воронка, аномалии и прогноз проверялись тем же способом, что и сентябрьские числа,
So that доверие к октябрьским модулям строилось на проверке, а не на обещании.

**Acceptance Criteria:**

**Given** реализованные истории Epic 3 (воронка на сервере), Epic 4 (детектор, порог, экран) и, когда появятся, модули M-06+
**When** Владислав пересчитывает шаги 8-10 §2.2 хартии: окно и полноту покрытия воронки, применение порога и сортировку аномалий по деньгам, оценку потерь, а для прогноза - rolling-origin backtest с исключением дней отсутствия товара
**Then** эталоны шагов 8-10 в `verification/golden/`, строки в журнале, гейт `shadow` расширен новыми кейсами; метрика ошибки прогноза зафиксирована до эксперимента (SM-8)
**And** Mike выполняет одно действие: `make verify` - цель `shadow` проходит с новыми кейсами

## PRD v2.2 → истории

Трассировка требований PRD (`_bmad-output/planning-artifacts/prds/prd-PROXIMA-AI-2026-08-28/prd.md`, ревизия v2.2) к историям этого файла. Нотация PRD: `FR-n`; нотация этого файла: `FRn`, `NFRn`, `ARn`.

| PRD | Истории-носители | Примечание |
|---|---|---|
| FR-26 сбор | 1.1, 1.3, 1.4, 1.14 | FR1, FR2 |
| FR-27 бэкфилл | 1.5, 1.13, 1.14 | 1.5 в main до 08.09, одним тегом с 1.14 (CP-3) |
| FR-28 статус данных | 1.6, 1.11 → 2.5, 1.14 | FR4, FR5; строка статуса исполняется в 2.5 (CP-6) |
| FR-29 откат прогона | 1.7 | FR10; неснимаема |
| FR-30 воронка фоном | 3.1 (сентябрь, старт ≤ 08.09), 3.0, 3.2, 3.3, 3.4 (октябрь) | FR8, FR9; SM-7 = N недель |
| FR-31 норма | 2.3 | FR6 |
| FR-32 сводка | 2.2, 2.4, 2.5, 2.6 | FR7; процедура сверки с кабинетом и пометка «предварительно» - 2.6 (CP-7) |
| FR-6 полнота и свежесть | 1.3, 1.6, 1.12, 2.5 | |
| FR-7 правило показа | 2.4, 2.5, 4.1 | `signals[]` только при `ok` - AC 4.1 |
| FR-22 утренний цикл | 1.12 (done), 1.14 (крайний срок 06:30), 3.1 (отдельный юнит воронки после CR к AD-6) | ретрай алерта - PA-задача (CP-11) |
| FR-1 сортировка | 4.2 | |
| FR-8 отклонение по SKU и категории | 4.0, 4.1 | измерение категории - 4.0 |
| FR-9 деньги под риском | 4.1 | |
| FR-25 строка аномалии | 4.3 | |
| FR-34 порог тревоги | 4.4 (значение конфига), 4.2 | предварительно 30 % на падение |
| FR-20, FR-21 Policy Layer | нет носителя намеренно → CM-20 | решение 6а 02.09 |
| FR-4 состав аномалии | 5.2 | |
| FR-5 решение | 5.0, 5.3 | |
| FR-12 режим UNKNOWN | 5.2 | |
| FR-14 диагноз | 5.2 | |
| FR-15 проверка диагноза | 5.1 | |
| FR-16 запись решения | 5.0, 5.3 | |
| FR-18 сверка | 5.3 | |
| FR-35 LLM-провайдер | 5.1 | |
| FR-2, FR-3, FR-10, FR-11, FR-13, FR-17, FR-19, FR-23, FR-24 | нет носителя (отложено → CM-3, CM-1, CM-6, CM-7, CM-2) | PRD §4.E |
| FR-36..FR-40 `[PROPOSED]` | нет носителя до D-решения; контур - `epics-candidates-m06.md` | PRD §4.F, §13 |
| UJ-5 второй tenant | единица без истории (после M-03, D18) | |
| Независимая проверка расчётов (все FR цепочки) | 6.1, 6.2, 6.4 (сентябрь), 6.5 (октябрь) | Теневой пересчёт: эталоны в `verification/golden/`, гейт `shadow`, журнал `SHADOW-RECONCILIATION.md`; расхождение блокирует релиз (D26) |
| Ground truth порога (вход FR-34) | 6.3 | Разметка ретро-тревог, вход Story 4.4 и OQ-7 |
| Единицы уровня NFR/AR (конвейер, не поведение продукта) | 1.0, 1.2, 1.8, 1.9, 1.12, 1.13 | PRD §11.2, §15; epics NFR1..NFR13, AR1..AR16; в §4 PRD как FR не дублируются |

Проверки, за которые отвечает Владислав (`docs/agent-system/roles/analyst-vladislav.md`): журнал сверки с кабинетом (1.14, 2.6), разметка ретро-тревог (вход 4.4), замер SM-3 «до» (до 2.6), приёмка историй по AC вторым человеком после агента-ревьюера.
