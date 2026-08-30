---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - _bmad-output/specs/spec-wb-morning-brief/SPEC.md
  - _bmad-output/specs/spec-wb-morning-brief/glossary.md
  - _bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md
  - DECISIONS.md
  - docs/state/BACKLOG-REVIEW.md
  - docs/state/API-FACTS.md
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
FR9: Система еженедельно (понедельник) получает воронку через async CSV `DETAIL_HISTORY_REPORT` и промоутит её в те же наблюдения и факты (`source='csv'`); не более одного созданного отчёта в сутки. [CAP-6, AD-5]
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
NFR9: Сроки: первая единица M-01 уходит в OpenHands не позже 08.09.2026; M-03 работает к 30.09.2026; бэкфилл запускается при первом деплое M-01 (март выпадает из окна WB по одному дню в сутки). [D6, D19]
NFR10: Перед каждым релизом прогоняется `WORKS-TODAY.md` целиком; `make verify` - гейт (на маке/CI; в сандбоксе OpenHands гейт = CI); RLS-тест под реальными ролями в `make verify`. [AD-11, AD-12, спека]
NFR11: Наблюдаемость: JSON-строка на событие с `run_id`/`tenant_id`/`kind`/`step`, `collector_runs` - единственный источник статуса, `OnFailure` → Telegram-канал монитора, `stale` на `/brief` как dead-man. [AD-17]
NFR12: Время: `calendar_day` в Europe/Moscow по полю WB `date` через единственный helper (TS/Python/SQL-форма), `OnCalendar` с явным TZ, `CURRENT_DATE` в `db/` запрещён. [AD-7]
NFR13: Контракты: любая форма данных через границу сервиса - JSON Schema в `contracts/`, TS через `make codegen` (расширить на webapp), Python через dataclass + jsonschema; деньги строкой в JSON, `numeric(14,2)` в БД. [AD-10]

### Additional Requirements

- AR1 Миграции `011`-`016` по плану AD-14: run ledger (`collector_runs`, `collector_run_inputs`, `wb_raw_artifacts`, роль `proxima_run_janitor` + политики, `collector_run_id` в `fact_attempt_runs`/`wb_analytics_report_tasks`); `stg_wb_orders_obs`/`stg_wb_sales_obs` + `_latest`; `fact_cabinet_daily` + `_current` + `data_status_current`; `stg_wb_funnel_obs`/`fact_funnel_daily` + `_current`; `norm_daily` + `_current`; `brief_daily` + `brief_current` + роли `proxima_job_collector`/`proxima_job_norm`/`proxima_webapp_readonly` с грантами и политиками на базовые таблицы. Все проходят `tools/verify_migrations.py`. [AD-11, AD-14]
- AR2 Образы и compose: `services/collector/Dockerfile`, `services/control-plane/Dockerfile` (multi-stage, контекст - корень, `USER 1010`), корневой `.dockerignore`, сервисы `collector`/`control-plane` в `infra/compose.yaml` (`profiles: [jobs]`, `secrets:`, `env_file: infra/jobs.env`), `infra/webapp.staging.compose.yaml` (auth off, loopback :3000, `WEBAPP_DATA_MODE`, `WEBAPP_TENANT_ID`, `WEBAPP_DATA_DATABASE_URI` из секрета). [AD-6, AD-15]
- AR3 Планировщик: `infra/systemd/proxima-morning@.{service,timer}` (05:30 Europe/Moscow, `Persistent`, `User=root`, `ProtectHome`, `OnFailure=proxima-alert@%n`), `proxima-funnel-csv@.{service,timer}` (Пн 06:30), `proxima-alert@.service` (Telegram монитора), `tools/morning_run.sh <tenant>` (collect → funnel_v3 → norm → brief, стоп на первой ошибке, `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID`). [AD-6]
- AR4 Роли вне ledger: `infra/bootstrap/provision-runtime-roles.sh` (идемпотентный, после миграций): LOGIN `proxima_collector`, `proxima_norm`, `proxima_webapp`, `proxima_janitor` (+ `GRANT DELETE`), база `proxima_test`, LOGIN `proxima_sandbox` (CONNECT только к `proxima_test`), `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC`, URI-файлы `/etc/proxima-ai/secrets/<user>_uri`. [AD-11, AD-12]
- AR5 WB-клиент: `services/collector/src/wb/{client,transport,fixture-transport,msk-day}.ts` (реестр эндпоинтов и бюджетов поверх `RecordedHttpClient`), `tools/verify_wb_client.py` в `make verify` (URL только в реестре, запрет `setInterval`/`node-cron` на `src/**`, запрет write-эндпоинтов), `tools/record_fixture.ts` (артефакт → обезличенная фикстура), фикстуры `services/collector/tests/fixtures/wb-api/`. [AD-4]
- AR6 Проверки живым API внутри единиц (разрешены D22): `flag=0` + `dateFrom` фильтрует по `lastChangeDate` (2 read-вызова) и `count(*) = count(distinct srid)` на фикстурах - до агрегатора; async CSV create/status/file и глубина `startDate` (≤ 3 вызова) - до фазы 2 `funnel_csv`. [AD-2, AD-4, AD-5]
- AR7 Контракты: `contracts/{cabinet-daily,norm,brief}.schema.json`, принять `signal`/`diagnosis`/`decision-record` из `origin/mihailzhamba-bot/pmm29-contracts`; `tools/generate_contract_types.mjs` расширить на `services/webapp/src/lib/contracts/`; удалить копию схемы внутри пакета diagnosis; удалить ручные `types.ts` из ai/pa-50 после codegen. [AD-10]
- AR8 Helper дня: `services/collector/src/wb/msk-day.ts`, `proxima_control_plane/common/msk_day.py`, SQL-форма `(now() AT TIME ZONE 'Europe/Moscow')::date`; тест на границу полуночи. [AD-7]
- AR9 Обратимость: `tools/delete_run.py --tenant --run [--dry-run]` (транзитивное замыкание по `collector_run_inputs`), RLS-тест «без GUC - ошибка, не нули». [AD-3]
- AR10 Тестовая база: `tools/test_db_refresh.sh` (terminate → DROP WITH FORCE → CREATE → `pg_dump | psql -v ON_ERROR_STOP=1` → GRANT sandbox → `ALTER ROLE proxima_sandbox SET proxima.tenant_id`), `make test-db-refresh`, еженедельная проверка восстановления (Пн до `funnel_csv`); OpenHands `.env.task` → URI `proxima_sandbox`. [AD-12, AD-17]
- AR11 Первый релиз M-01 (операции на сервере, по явному «деплой»): восстановить `origin` у `/srv/proxima-ai/repo` и перевести на тег; вывести `~/proxima-webapp-staging` и ручной контейнер `proxima-webapp-staging`; вывести пустые `proxima_dev` (хост и зона); `mv` токенов в `<tenant>_wb_<category>_token` с chown `1010:1010`; `systemctl enable --now proxima-morning@amirova-test.timer`; запустить бэкфилл `--from 2026-03-01`; включить `PROXIMA_RAW_DIR` в ночной бэкап; `CHANGELOG.md` + план отката. [AD-13, AD-15, AD-17]
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
FR3: Epic 1 - бэкфилл истории с 01.03.2026 до вытеснения окном WB
FR4: Epic 1 - статус данных на /brief (last_full_day, collected_at)
FR5: Epic 1 - предупреждение stale вместо цифр
FR6: Epic 2 - норма = медиана 14 дней, insufficient при < 14
FR7: Epic 2 - вчера против нормы в % на /brief
FR8: Epic 3 - воронка v3 ежедневно (окно 7 дней)
FR9: Epic 3 - воронка async CSV еженедельно, промоушен в те же факты
FR10: Epic 1 - delete_run транзитивно, --dry-run
FR11: Epic 4 (октябрь) - аномалии с приоритетом по деньгам
FR12: Epic 5 (октябрь) - план действий с источниками

NFR1-NFR13 действуют во всех эпиках; AR1-AR11 - Epic 1; AR7, AR12, AR13 - Epic 2; AR5, AR6 (async CSV), AR12 (`wb_async_report.py`) - Epic 3; AR14 - Epic 2 (pa-50, pmm29) и Epic 4 (pmm-20, pa41); AR15 - после Ворот 3 (Jira); AR16 - каждый релиз.

## Epic List

### Epic 1: Данные кабинета собираются сами (M-01)
Mike открывает `/brief` и видит «данные до <вчера>, обновлено сегодня 05:xx»; в БД дневной ряд заказов и продаж кабинета Амировой с 01.03.2026, пополняется каждое утро без участия человека; любой прогон можно откатить одной командой. Внутри - весь конвейер: WB-клиент с фикстурами и гейтом, миграции 011-013, образы и systemd, роли, первый релиз на сервере с бэкфиллом. Первая единица маленькая и обкатывает конвейер целиком (клиент + фикстуры + гейт + проверка `flag=0`).
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR10

### Epic 2: Норма и утренняя сводка (M-02 + M-03, граница сентября)
Каждое утро `/brief` показывает «вчера: N заказов против нормы M (−x %), выручка …» по медиане 14 дней; цифры прячутся при stale/insufficient. Внутри: контракты `norm`/`brief` (+ `signal` из pmm29), control-plane `norm/` и `brief/`, миграции 015-016, реализация `postgres-provider.ts` из ai/pa-50, переключение `WEBAPP_DATA_MODE=postgres`. Использует Epic 1, не требует Epic 3.
**FRs covered:** FR6, FR7

### Epic 3: Воронка копится фоном (M-01b)
С первой недели сентября воронка по nmId (открытия → корзина → заказ → выкуп) ежедневно из v3 и еженедельно из async CSV ложится в `fact_funnel_daily`; к 27.10 - 8 недель. Внутри: миграция 014, `jobs/funnel-v3.ts`, `funnel_csv` (две фазы), таймер понедельника, проверка глубины async CSV (≤ 3 вызова). Использует Epic 1, независим от Epic 2 - идёт параллельно с ним.
**FRs covered:** FR8, FR9

### Epic 4: Аномалии с приоритетом (M-04, октябрь)
В сводке появляются ранжированные по потерянной выручке аномалии по SKU/категории, шум отсечён. Внутри: адаптер детектора `pmm-20` к `fact_*_current`, порог тревоги (решение Mike), сверка кабинетного ряда с суммой nmId. Использует Epic 2 и Epic 3.
**FRs covered:** FR11

### Epic 5: План действий (M-05, октябрь)
К каждой аномалии - гипотеза причины и что проверить, с источником каждой цифры. Внутри: `diagnosis/` с реальным LLM-провайдером и eval-гейтом, `decision-record`. Использует Epic 4.
**FRs covered:** FR12

## Epic 1: Данные кабинета собираются сами (M-01)

Mike открывает `/brief` и видит «данные до <вчера>, обновлено сегодня»; в БД дневной ряд заказов и продаж кабинета `amirova-test` с 01.03.2026, пополняется каждое утро без участия человека; любой прогон откатывается одной командой. Каждая история = один сеанс OpenHands + один PR + одна проверка Mike. Ссылки: AD-1..AD-7, AD-11..AD-15, AD-17; D14, D15, D21, D22.

### Story 1.1: WB-клиент с реестром эндпоинтов, фикстуры и гейт (обкатка конвейера)

As a Mike (владелец кабинета и оператор конвейера),
I want чтобы единственный WB-клиент с бюджетами лимитов и тестами на фикстурах прошёл весь конвейер поставки от единицы работы до зелёного `make verify`,
So that следующие единицы шли по проверенному пути, а тесты никогда не ходили в сеть.

**Acceptance Criteria:**

**Given** ветка от `main`, `services/collector/src/wb/{client,transport,fixture-transport,msk-day}.ts` по AD-4/AD-7
**When** запускается `make verify`
**Then** новый гейт `tools/verify_wb_client.py` проходит: все URL WB только в реестре `src/wb/client.ts`; реестр содержит ровно `statistics.orders` (10/мин), `statistics.sales` (1/мин), `analytics.sales_funnel_v3_history` (3/мин), `analytics.nm_report_downloads` (3/мин); `reportDetailByPeriod`/`supplier/stocks` отсутствуют; `setInterval`/`node-cron` не встречаются в `src/**`
**And** `tools/verify_business_signal.py` не изменён и по-прежнему зелёный

**Given** `services/collector/tests/fixtures/wb-api/` с обезличенными фикстурами `orders`, `sales`, `sales_funnel_v3_history`, `nm_report_downloads` (каждая ≤ 200 КБ, без заголовков авторизации, записаны `tools/record_fixture.ts` из артефактов на VPS)
**When** тесты клиента выполняются через `FixtureTransport` при незаданных `WB_*_TOKEN_FILE`
**Then** тест на 429 ждёт по `X-Ratelimit-Retry` и сдаётся после 3 повторов; тест на бюджет не допускает второй вызов `sales` раньше 60 с (виртуальные часы); любая попытка сетевого вызова падает
**And** `mskDay('2026-08-29T23:30:00Z') = 2026-08-30`, `mskDay('2026-08-29T20:59:59Z') = 2026-08-29` (граница полуночи МСК)

**Given** разрешение D22 на 2 read-вызова с сервера
**When** с VPS выполняются `orders?dateFrom=<run_day-3>&flag=0` и `sales?dateFrom=<run_day-3>&flag=0` (ответы в фикстуры на VPS)
**Then** в `docs/state/API-FACTS.md` появляется раздел «flag=0 семантика (дата)»: фильтр по `lastChangeDate` подтверждён или опровергнут, и на фикстурах `orders` выполнено `count(*) = count(distinct srid)` (результат записан)
**And** при опровержении `dateFrom` для `collect` в AD-4 меняется на `run_day-14` записью в memlog спайна

**Given** PR открыт
**When** Mike выполняет одно действие: `make verify`
**Then** вывод содержит `verify_wb_client: PASS` и строку из API-FACTS про `flag=0`

### Story 1.2: Реестр прогонов и наблюдения заказов и продаж

As a оператор конвейера,
I want чтобы прогон сбора записывал артефакты, наблюдения заказов и продаж с их `lastChangeDate` и завершался статусом в едином реестре прогонов,
So that каждая строка в БД была прослеживаема до прогона и доказательства, а повтор не создавал дублей.

**Acceptance Criteria:**

**Given** миграции `011_run_ledger.sql` (`collector_runs`, `collector_run_inputs`, `wb_raw_artifacts` с `tenant_id`, роль `proxima_run_janitor` NOLOGIN + политики `FOR ALL`, `collector_run_id uuid NULL` в `fact_attempt_runs` и `wb_analytics_report_tasks`) и `012_stg_wb_orders_sales.sql` (`stg_wb_orders_obs` PK `(tenant_id, srid, last_change_at)`, `stg_wb_sales_obs` PK `(tenant_id, sale_id, last_change_at)`, `canonical_sha256`, view `_latest` с `security_invoker`), RLS и политики по AD-11/AD-13
**When** запускается `make verify`
**Then** `tools/verify_migrations.py` проходит (self-checksum, additive-only, шаблоны политик), `pg-roundtrip: PASS` на локальном PG16, ledger 12/12

**Given** job `services/collector/src/jobs/collect.ts` (CLI `collect --tenant amirova-test --date-from <d>`) на `FixtureTransport`
**When** прогон выполняется против локальной БД
**Then** порядок по AD-3: строка `collector_runs … RUNNING` autocommit → каждая строка `wb_raw_artifacts` autocommit по получении (locator `artifact://business-signal/sha256/<hex>`, файл в `PROXIMA_RAW_DIR`) → наблюдения в одной транзакции с `set_config('proxima.tenant_id', $1, true)` первым statement → `UPDATE … SUCCEEDED` в той же транзакции
**And** повторный прогон на тех же фикстурах: 0 новых наблюдений (`DO NOTHING` при том же `canonical_sha256`), новая строка `collector_runs`
**And** фикстура с тем же `srid` и новым `lastChangeDate` даёт вторую строку наблюдения, `_latest` отдаёт новую; фикстура с тем же PK и другим payload валит прогон `WB_SCHEMA_DRIFT` и оставляет `FAILED` отдельным autocommit, наблюдений этого прогона в БД нет

**Given** PR открыт
**When** Mike выполняет `make verify`
**Then** в выводе тест `collect: idempotent replay 0 new rows` зелёный и `pg-roundtrip: PASS`

### Story 1.3: Дневной ряд кабинета и статус данных

As a Mike,
I want чтобы после прогона в БД лежала версия каждого дня интервала с заказами, отменами, продажами, возвратами и выручкой, а view отвечал, до какого дня данные полные,
So that норма и сводка читали один ряд, а бэкфилл с 01.03.2026 совпадал с тем, что я видел в фикстурах.

**Acceptance Criteria:**

**Given** миграция `013_fact_cabinet_daily.sql` (`fact_cabinet_daily` по AD-2, view `fact_cabinet_daily_current` по AD-3, view `data_status_current` по AD-7 с `COALESCE(…, true)` и `(now() AT TIME ZONE 'Europe/Moscow')::date`; `CURRENT_DATE` в `db/` отсутствует - проверяется гейтом)
**When** агрегатор `facts/cabinet-daily.ts` выполняется в конце прогона `collect`/`backfill`
**Then** версия создаётся для **каждого** дня `[floor, run_day-1]` (день без строк = нули + артефакты прогона), `floor = mskDay(dateFrom)` для `collect` и `--from + 1` для `backfill`; день `= run_day` не версионируется; `collector_run_inputs` содержит distinct `run_id` всех наблюдений свёртки
**And** `dateFrom` для `collect` без флага = `min(run_day-3, last_full_day+1)`

**Given** фикстуры `supplier-sales` и `supplier-orders` от 30.08.2026 (полные, на VPS; локально - их обезличенная выжимка по неделям W10 и W35)
**When** `backfill --from 2026-03-01` выполняется против локальной БД на фикстурах
**Then** в `fact_cabinet_daily_current` суммы за W10 = 649 заказов / 700 860 ₽ и за W35 = 225 / 263 089 ₽ (детерминированный тест по `glossary.md`: заказы без `isCancel`, выручка Σ `finishedPrice` по `S`, возвраты `R` исключены)
**And** `data_status_current` отдаёт `last_full_day = 2026-08-29`, `stale = true` (прогон старше 24 ч в тесте с подменой часов) и `stale = false` при `collected_at` в пределах 24 ч

**Given** PR открыт
**When** Mike выполняет `make verify`
**Then** тест `cabinet-daily: W10 649/700860, W35 225/263089` зелёный

### Story 1.4: Откат прогона и роли доступа

As a оператор,
I want удалять любой прогон целиком одной командой и подключать каждого участника (collector, norm, webapp, janitor, sandbox) своей ролью без superuser,
So that плохой прогон не оставлял следов, а агент в сандбоксе видел только тестовую копию.

**Acceptance Criteria:**

**Given** `tools/delete_run.py --tenant <t> --run <uuid> [--dry-run]` по AD-3
**When** выполняется без `--tenant` или без GUC
**Then** завершается ошибкой «0 строк для run_id», не нулями; с флагами - печатает счётчики по таблицам транзитивного замыкания по `collector_run_inputs` и удаляет их в одной транзакции под ролью `proxima_run_janitor`; для FAILED-прогона удаляет только строку прогона и его артефакты; файлы CAS остаются

**Given** `infra/bootstrap/provision-runtime-roles.sh` по AD-11 (идемпотентный; LOGIN `proxima_collector`, `proxima_norm`, `proxima_webapp`, `proxima_janitor` + `GRANT DELETE`, база `proxima_test`, `proxima_sandbox` с CONNECT только к `proxima_test`, `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC`, URI-файлы `<user>_uri` `1010:1010 0600`) и `tools/test_db_refresh.sh` по AD-12
**When** скрипты выполняются дважды подряд на локальном PG16 (в тесте `pg_local_roundtrip`)
**Then** второй запуск не падает и ничего не меняет; `proxima_sandbox` не может подключиться к `proxima`; после refresh под `proxima_sandbox` в `proxima_test` `SELECT count(*) FROM fact_cabinet_daily_current` > 0 благодаря `ALTER ROLE … SET proxima.tenant_id`

**Given** RLS-тест в `make verify`
**When** под каждой ролью выполняется `SELECT count(*)` из каждого view
**Then** с GUC - > 0, без GUC - 0 без ошибки прав; `proxima_collector` не может `UPDATE kind` в `collector_runs` (конвенция) - тест фиксирует текущее поведение

**Given** PR открыт
**When** Mike выполняет `make verify`
**Then** тесты `delete_run: closure` и `rls: roles` зелёные

### Story 1.5: Образы, compose и staging-overlay

As a оператор,
I want чтобы collector и control-plane собирались в образы и запускались как одноразовые контейнеры из compose с секретами, а webapp поднимался staging-overlay'ем без auth,
So that на хосте не требовались uv/psql/node_modules, а деплой был одной последовательностью команд.

**Acceptance Criteria:**

**Given** `services/collector/Dockerfile`, `services/control-plane/Dockerfile` (multi-stage, контекст корень, `USER 1010`), корневой `.dockerignore` (`.env`, `.git`, `node_modules`, `fixtures/`, `_bmad-output/`), сервисы `collector`/`control-plane` в `infra/compose.yaml` (`profiles: [jobs]`, `secrets:` для `postgres_user`/`postgres_password`/`<user>_uri`/`<tenant>_wb_*_token`, `env_file: infra/jobs.env`), `infra/webapp.staging.compose.yaml` (auth off, `127.0.0.1:3000`, `WEBAPP_DATA_MODE`, `WEBAPP_TENANT_ID`, `WEBAPP_DATA_DATABASE_URI` из секрета)
**When** CI (`.github/workflows/verify.yml`) выполняет `docker build` обоих образов и `docker compose config` для базового и staging-overlay
**Then** сборка проходит, `docker compose config` валиден, `.env` и `node_modules` в контексте отсутствуют (проверка `docker build --no-cache` с выводом слоёв)
**And** `psycopg` перенесён в `dependencies` control-plane; `make apply-migrations ENV_FILE=infra/jobs.env` внутри образа control-plane применяет миграции к `postgres:5432` (проверено в CI service-container PG16)

**Given** PR открыт
**When** Mike выполняет одно действие: открывает зелёный CI-прогон PR
**Then** видны job'ы `build-images` и `apply-migrations-in-container` со статусом success

### Story 1.6: Статус данных на /brief

As a Mike,
I want видеть на `/brief` строку «данные до <дата>, обновлено <время>» и предупреждение вместо цифр, если сбор не проходил больше суток,
So that я всегда знал, можно ли верить экрану.

**Acceptance Criteria:**

**Given** `services/webapp/src/lib/data/postgres-provider.ts` из `origin/ai/pa-50` реализован по AD-9 в части статуса: собственный `Pool`, `pool.on('connect')` с `set_config('proxima.tenant_id', $1, false)` и `.catch`, `WEBAPP_TENANT_ID` валидируется `^[a-z0-9][a-z0-9_-]{2,63}$` при старте, один `SELECT` из `data_status_current` под `proxima_webapp_readonly`; `getBrief()` в этом режиме возвращает fixtures-brief с пометкой «сводка ещё не считается»
**When** `WEBAPP_DATA_MODE=postgres` и `data_status_current` отдаёт `last_full_day=2026-09-09, collected_at=…, stale=false`
**Then** на `/brief` над контентом строка «Данные до 09.09, обновлено 10.09 05:41»; при `stale=true` или пустом view - предупреждение «Сбор не проходил больше суток» вместо цифр (`UnreleasedBanner` не снимается)
**And** vitest покрывает провайдер через шов (мок `Pool`): stale/не stale/пусто; `npm --workspace @proxima/webapp test`, `run typecheck`, `run lint` зелёные; auth-зона не изменена (`git diff --stat` не содержит `lib/auth*`, `app/api/auth`, `app/login`)

**Given** PR открыт
**When** Mike выполняет `npm --workspace @proxima/webapp run dev` с `WEBAPP_DATA_MODE=postgres` и локальной БД (или `ssh -N proxima-db`)
**Then** открывает `/brief` и видит строку статуса

### Story 1.7: Планировщик и runbook первого релиза

As a оператор,
I want systemd-юниты утреннего прогона и алерта, скрипт шагов и пошаговый runbook релиза с планом отката,
So that релиз M-01 выполнялся по записанной последовательности, а сбой сообщался в Telegram.

**Acceptance Criteria:**

**Given** `infra/systemd/proxima-morning@.{service,timer}` (`OnCalendar=*-*-* 05:30:00 Europe/Moscow`, `Persistent=true`, `User=root`, `ProtectHome=true`, `OnFailure=proxima-alert@%n.service`), `proxima-funnel-csv@.timer` (Пн 06:30, шаг пока no-op до Epic 3), `proxima-alert@.service` (Telegram монитора), `tools/morning_run.sh <tenant>` (`collect` → `funnel_v3` → `norm` → `brief`, стоп на первой ошибке, шаги norm/brief/funnel_v3 включаются флагами и по умолчанию выключены до своих эпиков; `PROXIMA_GIT_SHA`, `PROXIMA_IMAGE_ID`)
**When** CI выполняет `systemd-analyze verify` для юнитов и `bash -n` + shellcheck для скриптов
**Then** без ошибок; `morning_run.sh` в dry-run печатает последовательность `docker compose --profile jobs run --rm …` команд

**Given** `docs/operations/release-m01.md`
**When** Mike читает его
**Then** в нём по AD-15/AR11: подготовка (`/srv/proxima-ai/repo` origin + тег; `mv` токенов в `<tenant>_wb_*_token` с chown 1010; `provision-runtime-roles.sh`; `test_db_refresh`), деплой (build → apply-migrations → compose up с overlay → enable timer), бэкфилл (`collect --from 2026-03-01 --backfill`, ожидание ~10-15 мин при 1/мин), проверка (`WORKS-TODAY.md` + строка статуса на `/brief`), вывод `~/proxima-webapp-staging`, контейнера `proxima-webapp-staging`, пустых `proxima_dev`, включение `PROXIMA_RAW_DIR` в бэкап; откат (prev tag + rebuild + `delete_run.py` по прогонам релиза; миграции не откатываются); наблюдение сутки: «пришёл ли утренний прогон и обновился ли статус»; запись в `CHANGELOG.md`
**And** каждая команда runbook'а - копипастой, с ожидаемым выводом

### Story 1.8: Первый релиз M-01 на сервере

As a Mike,
I want чтобы после моего «деплой» конвейер M-01 работал на VPS и наутро статус на `/brief` обновился сам,
So that данные кабинета копились с сентября и март не выпал из окна WB.

**Acceptance Criteria:**

**Given** Stories 1.1-1.7 смержены в `main`, тег `v2026.09.NN-1`, runbook `docs/operations/release-m01.md`, явное «деплой» от Mike в чате (D7)
**When** Claude выполняет runbook на сервере шаг за шагом (единственная запись на сервер за релиз), фиксируя фактический вывод в `docs/operations/releases/2026-09-NN-m01.md`
**Then** `make apply-migrations` показывает ledger 13/13; `provision-runtime-roles.sh` идемпотентен; бэкфилл завершён `SUCCEEDED`, `fact_cabinet_daily_current` содержит дни с 02.03.2026 по вчера, недельные суммы W10/W35 совпадают с API-FACTS; `WORKS-TODAY.md` прогнан целиком, новые пункты добавлены (таймер активен, статус на `/brief`)
**And** план отката записан в релиз-заметке до первого шага

**Given** релиз выполнен
**When** наступает следующее утро (05:30 МСК)
**Then** `collector_runs` содержит SUCCEEDED `collect` за сегодня, `/brief` показывает «данные до <вчера>, обновлено сегодня 05:3x»; не пришёл - откат по плану, не починка на боевом
**And** Mike выполняет одно действие: открывает `/brief` через `ssh -N proxima-app` и видит строку статуса с сегодняшним временем

## Epic 2: Норма и утренняя сводка (M-02 + M-03, граница сентября)

Каждое утро `/brief` показывает «вчера: N заказов против нормы M (−x %), выручка …» по медиане 14 дней; цифры прячутся при stale/insufficient. Использует Epic 1 (дневной ряд, статус, роли), не требует Epic 3. Ссылки: AD-8, AD-9, AD-10, AD-11, AD-14; D14 (ai/pa-50, pmm29), D21.

### Story 2.1: Контракты нормы, сводки и сигнала

As a оператор конвейера,
I want чтобы формы данных нормы, сводки и сигнала были описаны JSON-схемами в `contracts/` с генерацией типов для collector и webapp,
So that control-plane, webapp и будущие детекторы читали один контракт, а не три версии типов.

**Acceptance Criteria:**

**Given** схемы `signal`, `diagnosis`, `decision-record` приняты из `origin/mihailzhamba-bot/pmm29-contracts` через ревью (D14) и новые `contracts/{cabinet-daily,norm,brief}.schema.json` по AD-9/AD-10 (деньги - строка с двумя знаками, `schema_version`, `source_refs` minItems 1)
**When** запускается `make verify`
**Then** `make contracts` валидирует все схемы и synthetic-примеры (по одному на схему, обезличенные); `make codegen` генерирует типы в `services/collector/src/contracts/` и `services/webapp/src/lib/contracts/` без diff при повторном запуске; ручные `services/webapp/src/lib/data/types.ts` удалены, импорты переведены на сгенерированные
**And** `diagnosis/validator.py` читает схему из `contracts/`, копия внутри пакета удалена; pytest control-plane зелёный

**Given** PR открыт
**When** Mike выполняет `make verify`
**Then** `contracts: PASS`, `codegen` без diff, `webapp typecheck` зелёный

### Story 2.2: Норма по медиане 14 дней

As a Mike,
I want чтобы каждое утро система считала норму заказов и выручки кабинета как медиану 14 календарных дней перед оцениваемым днём и записывала её версией по прогону,
So that сводка и детекторы сравнивали «вчера» с одной и той же нормой.

**Acceptance Criteria:**

**Given** миграция `015_norm_daily.sql` (`norm_daily` по AD-8 с `UNIQUE (tenant_id, evaluation_day, metric, run_id)`, view `norm_daily_current` с `security_invoker`, RLS) и модуль `proxima_control_plane/norm/` (`loader.py` через psycopg под ролью `proxima_norm`, `median.py` чистые функции, `writer.py`, `cli.py`: `python -m proxima_control_plane.norm run --tenant amirova-test [--date YYYY-MM-DD]`)
**When** прогон выполняется против БД с дневным рядом из фикстур 30.08 (дата 30.08.2026, `evaluation_day = 29.08`)
**Then** `norm_daily` содержит `orders = 34.5`, `revenue = 34595.00`, `window_days = 14`, `sample_days = 14`, `status = ok`, окно `[15.08, 28.08]` (оцениваемый день исключён); `collector_runs` содержит `kind = norm`, `collector_run_inputs` - `run_id` прочитанных версий
**And** при удалении версий 5 дней окна прогон пишет `sample_days = 9`, `status = insufficient`, `value` по имеющимся дням; повтор прогона за тот же день - новая версия, `norm_daily_current` отдаёт последнюю SUCCEEDED

**Given** PR открыт
**When** Mike выполняет `make verify`
**Then** тест `norm: 29.08 -> 34.5 / 34595, insufficient at 9/14` зелёный, `pg-roundtrip: PASS` (ledger 15/15)

### Story 2.3: Материализованная сводка дня

As a Mike,
I want чтобы после нормы система собирала сводку дня в БД по контракту `brief`, с отклонением в процентах и статусом,
So that экран только читал готовый результат и никогда не считал сам.

**Acceptance Criteria:**

**Given** миграция `016_brief_daily_roles.sql` (`brief_daily`, view `brief_current` = одна строка на tenant, роли `proxima_job_collector`/`proxima_job_norm`/`proxima_webapp_readonly` с грантами и политиками на базовые таблицы по AD-11; проходит `verify_migrations.py`) и модуль `proxima_control_plane/brief/` (`builder.py`, `cli.py`: `python -m proxima_control_plane.brief run --tenant amirova-test`)
**When** прогон выполняется после нормы Story 2.2 на данных фикстур (вчера = 29.08: 27 заказов, 41 141 ₽)
**Then** `brief_daily.payload` валиден по `contracts/brief.schema.json`: `evaluation_day = 2026-08-29`, `actual = {orders: 27, revenue: "41141.00"}`, `norm = {orders: 34.5, revenue: "34595.00", window_days: 14, sample_days: 14}`, `deviation_pct = {orders: -21.7, revenue: 18.9}`, `signals = []`, `source_refs` непустой, `status = ok`; `data_status` скопирован из view на момент записи
**And** при `norm.status = insufficient` → `brief.status = insufficient`; при отсутствии версии за `evaluation_day` → `blocked`; `run_inputs` записаны; RLS-тест: `proxima_webapp` видит `brief_current` с GUC и 0 строк без

**Given** PR открыт
**When** Mike выполняет `make verify`
**Then** тест `brief: payload valid, orders -21.7%` зелёный

### Story 2.4: /brief показывает вчера против нормы

As a Mike,
I want открыть `/brief` утром и увидеть вчерашние заказы и выручку против нормы с отклонением в процентах,
So that я за 10 секунд понимал, упали продажи или нет.

**Acceptance Criteria:**

**Given** `postgres-provider.ts` дополнен `getBrief()` по AD-9: второй `SELECT` из `brief_current`, маппинг `payload` в сгенерированные типы, правило показа цифр `brief.status = 'ok' AND stale IS FALSE AND brief_day = last_full_day`, иначе предупреждение с `last_full_day` и `collected_at`; блок сводки на `/brief` (компоненты `brief/`, без новых зависимостей, `UnreleasedBanner` остаётся) показывает две строки: заказы и выручка, значение / норма / отклонение %, цвет по знаку через `lib/gyr`
**When** `WEBAPP_DATA_MODE=postgres` и `brief_current` содержит сводку за вчера
**Then** на `/brief`: «29.08: 27 заказов против нормы 34.5 (−21.7 %), выручка 41 141 ₽ против 34 595 ₽ (+18.9 %)», строка статуса из Story 1.6; при `insufficient` - «норма копится: 9/14 дней»; при `stale` - предупреждение без цифр
**And** vitest через шов провайдера (мок `Pool`) покрывает ok/insufficient/stale/blocked; `npm --workspace @proxima/webapp test`, `typecheck`, `lint` зелёные; auth-зона не изменена; `tools/morning_run.sh` включает шаги `norm` и `brief` по умолчанию

**Given** PR открыт
**When** Mike выполняет `npm --workspace @proxima/webapp run dev` с `WEBAPP_DATA_MODE=postgres` и БД с данными Story 2.3
**Then** открывает `/brief` и видит две строки сводки

### Story 2.5: Релиз M-03 - сводка приходит каждое утро

As a Mike,
I want чтобы после моего «деплой» сводка считалась на сервере каждое утро и наутро цифры совпадали с кабинетом WB,
So that к 30.09 утренняя сводка работала без меня.

**Acceptance Criteria:**

**Given** Stories 2.1-2.4 смержены, тег `v2026.09.NN-2`, релиз-заметка с планом отката, явное «деплой» от Mike
**When** Claude выполняет runbook: `apply-migrations` (ledger 16/16), `provision-runtime-roles.sh` (гранты), пересборка образов, `morning_run.sh` с включёнными `norm`/`brief`, ручной первый прогон `norm` + `brief`, затем `WEBAPP_DATA_MODE=postgres` в staging-overlay и `compose up -d webapp`
**Then** `brief_current` содержит сводку за вчера со `status = ok`; `/brief` через туннель показывает цифры; `WORKS-TODAY.md` прогнан целиком, пункты «норма» и «сводка» добавлены; план отката: prev tag + `WEBAPP_DATA_MODE=fixtures` + `delete_run.py` по прогонам релиза

**Given** релиз выполнен
**When** наступает следующее утро
**Then** `collector_runs` содержит SUCCEEDED `collect`, `norm`, `brief` за сегодня; Mike выполняет одно действие - открывает `/brief` и сверяет вчерашние заказы и выручку с кабинетом WB (совпадают с точностью до отмен, доехавших после 05:30); не пришла - откат, не починка

## Epic 3: Воронка копится фоном (M-01b)

С первой недели сентября воронка по nmId (открытия → корзина → заказ → выкуп) ежедневно из v3 и еженедельно из async CSV ложится в `fact_funnel_daily`; к 27.10 - 8 недель. Использует Epic 1, независим от Epic 2. Ссылки: AD-4, AD-5, AD-6, AD-14; D13, D20, D22.

### Story 3.1: Воронка v3 ежедневно

As a Mike,
I want чтобы каждое утро система забирала воронку за последние 7 дней по всем активным nmId и версионировала её по дням,
So that к октябрю у детектора была дневная воронка без ручной выгрузки.

**Acceptance Criteria:**

**Given** миграция `014_funnel.sql` (`stg_wb_funnel_obs` PK `(tenant_id, nm_id, calendar_day, source, run_id)`, `fact_funnel_daily`, view `fact_funnel_daily_current` с предпочтением `csv` над `v3`, RLS; поля по словарю `COLUMN_MAP` scn001) и job `jobs/funnel-v3.ts` (активные nmId = distinct `nm_id` из `stg_wb_orders_latest` за 30 дней; пакеты ≤ 20; окно `[run_day-7, run_day-1]`; бюджет 3/мин из реестра)
**When** прогон выполняется на фикстуре `sales-funnel-v3-history` (30.08, 3 nmId, 7 дней)
**Then** в `stg_wb_funnel_obs` 21 наблюдение `source = v3` с `evidence_sha256` артефакта, в `fact_funnel_daily_current` 21 строка с `open_card`, `cart`, `orders`, `orders_sum_rub`, `buyouts`, `buyouts_sum_rub`; повтор - 0 новых наблюдений; день `= run_day` не версионируется
**And** `tools/morning_run.sh` включает шаг `funnel_v3` по умолчанию; `pg-roundtrip: PASS` (ledger 14/14 или 16/16 - в зависимости от порядка мержа с Epic 2)

**Given** PR открыт
**When** Mike выполняет `make verify`
**Then** тест `funnel_v3: 21 obs, replay 0` зелёный

### Story 3.2: Воронка из async CSV раз в неделю

As a оператор,
I want чтобы еженедельный CSV-отчёт воронки скачивался существующим инструментом и промоутился в те же наблюдения и факты, а глубина истории была проверена,
So that воронка накапливалась и назад, и вперёд, не съедая разделяемую квоту отчётов.

**Acceptance Criteria:**

**Given** разрешение D22 на ≤ 3 read-вызова async CSV с сервера
**When** с VPS выполняются create (`startDate` на 6 месяцев назад) → status → file для одного отчёта, не более одного созданного отчёта в сутки, с проверкой `nm_report_downloads` до создания
**Then** в `docs/state/API-FACTS.md` раздел «async CSV глубина (дата)»: максимальный `startDate`, размер, время готовности, квота; ответы в фикстуры на VPS

**Given** `tools/wb_async_report.py` изменён минимально (автосоздание `tenants` удалено - tenant обязан существовать; `--collector-run-id` пишется в `wb_analytics_report_tasks`; `--period from..to` явный) и job `jobs/funnel-csv-promote.ts` (фаза 2: `stg_wb_nm_report_rows(task_id)` → `stg_wb_funnel_obs(source = 'csv', evidence = tasks.downloaded_sha256)` → `fact_funnel_daily`, под `proxima_job_collector`, всегда, независимо от состояния задачи)
**When** промоушен выполняется на synthetic-фикстуре staging (структура `stg_wb_nm_report_rows` 25.08, обезличенная)
**Then** наблюдения `csv` и факты созданы; `fact_funnel_daily_current` за дни, где есть и `v3`, и `csv`, отдаёт `csv`; после `delete_run.py` прогона промоушена повтор фазы 2 восстанавливает факты без нового отчёта
**And** `proxima-funnel-csv@.service` выполняет фазу 1 под owner-URI (исключение AD-11, дата пересмотра M-04 в комментарии юнита) и фазу 2 под `proxima_collector`; таймер понедельник 06:30 МСК

**Given** PR открыт
**When** Mike выполняет `make verify`
**Then** тест `funnel_csv: promote + replay after delete` зелёный и раздел API-FACTS обновлён

### Story 3.3: Релиз воронки

As a Mike,
I want чтобы после «деплой» воронка копилась на сервере сама - ежедневно из v3 и по понедельникам из CSV,
So that к 27.10 было 8 недель воронки для аномалий.

**Acceptance Criteria:**

**Given** Stories 3.1-3.2 смержены, тег, релиз-заметка с планом отката, явное «деплой»
**When** Claude выполняет runbook: `apply-migrations`, пересборка образов, включение шага `funnel_v3`, `systemctl enable --now proxima-funnel-csv@amirova-test.timer`, ручной первый прогон `funnel_v3`
**Then** `fact_funnel_daily_current` содержит 7 дней по активным nmId; `WORKS-TODAY.md` дополнен пунктом «воронка v3 за вчера есть»; релиз-заметка содержит счётчики и план отката (`delete_run.py`, `systemctl disable`)

**Given** релиз выполнен
**When** проходит следующее утро и следующий понедельник
**Then** `collector_runs` содержит SUCCEEDED `funnel_v3` ежедневно и `funnel_csv` в понедельник; Mike выполняет одно действие - читает релиз-заметку с выводом `SELECT count(*), max(calendar_day) FROM fact_funnel_daily_current` через `ssh proxima-db`

## Epic 4: Аномалии с приоритетом (M-04, октябрь)

В сводке появляются ранжированные по потерянной выручке аномалии по SKU и категории, шум отсечён. Использует Epic 2 и Epic 3. Контуры: детальные AC пишутся после релиза M-03, когда есть живые сводки и решение Mike по порогу (Deferred в спайне). Ссылки: AD-5, AD-8, AD-10; D14 (pmm-20, pa41).

### Story 4.1: Детектор нормы на реальных фактах

As a оператор,
I want подключить детектор SCN-001 из ветки `pmm-20` к `fact_cabinet_daily_current` и `fact_funnel_daily_current` через адаптер `loader.py`, с выходом по `contracts/signal.schema.json`,
So that аномалии считались на тех же фактах, что и норма, а не на staging CSV.

**Acceptance Criteria:**

**Given** ветка `origin/mihailzhamba-bot/pmm-20-scn-001-…` принята через ревью, `loader.py` переписан на `fact_*_current`, сигнал маппится в `signal.schema.json` v1
**When** детектор выполняется на 8 неделях фактов (фикстуры + накопленное)
**Then** результат валиден по схеме, `run_inputs` записаны, окна 7/14/28 детектора не подменяют норму D21; сверка кабинетного ряда с суммой nmId (`fact_order_counts`) записана как quality-check с порогом расхождения
**And** детальные AC уточняются после M-03

### Story 4.2: Порог тревоги и ранжирование по деньгам

As a Mike,
I want задать порог тревоги по первым живым сводкам и видеть аномалии, отсортированные по потерянной выручке,
So that в сводке был сигнал, а не шум.

**Acceptance Criteria:**

**Given** решение Mike по порогу (после 2-3 недель живых сводок) записано в `DECISIONS.md`
**When** `brief` собирает `signals[]` из результатов детектора
**Then** дни в пределах шума (CV) не попадают; список отсортирован по `rub_assessment`; `brief.status` и правило показа цифр не меняются
**And** детальные AC уточняются после M-03

### Story 4.3: Аномалии на /brief в разрезе SKU и категории

As a Mike,
I want видеть на `/brief` список аномалий с товаром, категорией и суммой потерь,
So that я знал, куда смотреть первым.

**Acceptance Criteria:**

**Given** `signals[]` в `brief_current`
**When** открывается `/brief`
**Then** блок аномалий (компонент `SignalRow` из каркаса PA-49) показывает nmId/артикул, категорию, отклонение и `rub_assessment` с `source_refs`; пустой список - «критичных нет»
**And** детальные AC уточняются после M-03

## Epic 5: План действий (M-05, октябрь)

К каждой аномалии - гипотеза причины и что проверить, с источником каждой цифры. Использует Epic 4. Контуры; детализация после M-04. Ссылки: AD-10; спайн Deferred (LLM-провайдер, eval-гейт).

### Story 5.1: Реальный LLM-провайдер диагноза с eval-гейтом

As a оператор,
I want заменить mock-провайдер `diagnosis/` на реальный с детерминированной проверкой чисел и источников и eval-гейтом ≥ 0.80,
So that гипотезы не выдумывали цифры.

**Acceptance Criteria:**

**Given** `adapters/factory.py` получает провайдера (имя env-переменной ключа в `diagnosis.toml`, значение только на VPS), eval-датасет расширен живыми сигналами
**When** запускается `python -m proxima_control_plane.diagnosis eval`
**Then** pass-rate ≥ 0.80; любой диагноз с числом или ссылкой не из входа отклоняется валидатором
**And** детальные AC уточняются после M-04

### Story 5.2: Диагноз и «что проверить» в сводке

As a Mike,
I want видеть под каждой аномалией одну главную гипотезу, 2-3 альтернативы и конкретную проверку,
So that утро начиналось с действия, а не с расследования.

**Acceptance Criteria:**

**Given** `signals[].diagnosis` по `contracts/diagnosis.schema.json` в `brief_daily.payload`
**When** открывается `/brief`
**Then** под аномалией - `primary_cause`, `alternatives`, `unknowns`, проверка; каждая цифра с `source_ref`
**And** детальные AC уточняются после M-04

### Story 5.3: Запись решения и сверка ожидаемого с фактом

As a Mike,
I want отметить по аномалии «принял/отклонил» и через заданный срок увидеть, сработало ли,
So that система училась на моих решениях.

**Acceptance Criteria:**

**Given** `contracts/decision-record.schema.json`, таблица решений с `run_id` и RLS
**When** Mike отмечает решение на `/brief`
**Then** запись создаётся, через `horizon_days` сводка показывает `expected` vs `actual`
**And** детальные AC уточняются после M-04; это первая запись из webapp в БД - требует отдельного AD (роль, RLS `WITH CHECK`) до реализации
