---
stepsCompleted: [1, 2, 3, 4]
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
FR3: Epic 1 - бэкфилл истории (Story 1.5: артефакты 30.08 + живой хвост)
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
Mike открывает `/brief` и видит «данные до <вчера>, обновлено сегодня 05:xx»; в БД дневной ряд заказов и продаж кабинета Амировой с 01.03.2026, пополняется каждое утро без участия человека; любой прогон можно откатить одной командой. Внутри - весь конвейер: WB-клиент с фикстурами и гейтом, миграции 011-013, образы и systemd, роли, первый релиз на сервере с бэкфиллом. Первая единица маленькая и обкатывает конвейер целиком.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR10

### Epic 2: Норма и утренняя сводка (M-02 + M-03, граница сентября)
Каждое утро `/brief` показывает «вчера: N заказов против нормы M (−x %), выручка …» по медиане 14 дней; цифры прячутся при stale/insufficient. Внутри: контракты `norm`/`brief` (+ `signal` из pmm29), control-plane `norm/` и `brief/`, миграции, реализация `postgres-provider.ts`, переключение `WEBAPP_DATA_MODE=postgres`. Использует Epic 1, не требует Epic 3.
**FRs covered:** FR6, FR7

### Epic 3: Воронка копится фоном (M-01b)
С первой недели сентября воронка по nmId ежедневно из v3 и еженедельно из async CSV ложится в `fact_funnel_daily`; к 27.10 - 8 недель. Внутри: миграция воронки, `jobs/funnel-v3.ts`, `funnel_csv` (две фазы), таймер понедельника, проверка глубины async CSV. Использует Epic 1, независим от Epic 2 по коду (миграции перенумеровываются при мерже).
**FRs covered:** FR8, FR9

### Epic 4: Аномалии с приоритетом (M-04, октябрь)
В сводке появляются ранжированные по потерянной выручке аномалии по SKU/категории, шум отсечён. Внутри: адаптер детектора `pmm-20` к `fact_*_current`, порог тревоги (решение Mike), сверка кабинетного ряда с суммой nmId. Использует Epic 2 и Epic 3.
**FRs covered:** FR11

### Epic 5: План действий (M-05, октябрь)
К каждой аномалии - гипотеза причины и что проверить, с источником каждой цифры. Внутри: `diagnosis/` с реальным LLM-провайдером и eval-гейтом, `decision-record`. Использует Epic 4.
**FRs covered:** FR12


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

**Given** `tools/cas_import.ts <file> --retrieved-at <ISO> --source official_wb_statistics` (кладёт файл в CAS с манифестом; тот же инструмент используется в runbook на VPS) и `jobs/backfill.ts` по AD-2: `backfill --tenant --source artifact:<sha256_sales>,<sha256_orders> [--retrieved-at <ISO>]` читает артефакты из CAS (регистрирует их в `wb_raw_artifacts` прогона `backfill`), `run_day := mskDay(retrieved_at)` из манифеста или флага; живой режим `backfill --from <d>`: бюджет `sales` 1/мин, при 80 000 строк продолжение с `dateFrom = lastChangeDate` последней строки, `--resume` по последнему `last_change_at`
**When** в harness два синтетических артефакта (структура ответов 30.08, известные суммы) импортированы `cas_import.ts --retrieved-at 2026-08-30T05:59:00Z` и выполняется режим `artifact`
**Then** наблюдения созданы за все дни артефактов, `run_day = 2026-08-30`; повтор - 0 новых; живой режим с виртуальными часами: паузы ≥ 60 с и пагинация на синтетическом ответе из 80 000 строк
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

**Given** `infra/systemd/proxima-morning@.{service,timer}` (`OnCalendar=*-*-* 05:30:00 Europe/Moscow`, `Persistent=true`, `User=root`, `ProtectHome=true`, `OnFailure=proxima-alert@%n.service`), `proxima-alert@.service` (Telegram монитора), `proxima-restore-check@.{service,timer}` (Пн 06:00: последний дамп из `/var/backups/proxima` → `age -d -i /etc/proxima-ai/secrets/backup_age_key.txt | gunzip | psql proxima_test` после `DROP/CREATE` + `SELECT count(*) FROM fact_cabinet_daily_current`, AD-17), `tools/morning_run.sh <tenant>` (шаг `collect`; шаги `funnel_v3`/`norm`/`brief` добавляются своими эпиками; пути секретов по таблице Conventions; `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID`), `infra/backup/proxima-pg-backup.sh` из Story 1.0 + `PROXIMA_RAW_DIR` в набор бэкапа + установка на место серверного (`install` в runbook)
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
**Then** разделы: подготовка (`mv` токенов в `<tenant>_wb_<category>_token` + chown 1010; `provision-runtime-roles.sh`; `env.task` в зону; `test_db_refresh`); деплой (build → `apply-migrations` через `control-plane-admin` → `compose up -d` с overlay - с пометкой, что добавление bridge-порта пересоздаёт контейнер postgres на ~10 с, старый `proxima-webapp-staging` остаётся до конца наблюдения → `systemctl enable --now` таймеров `morning` и `restore-check`); бэкфилл (`cas_import.ts` двух файлов 30.08 с `--retrieved-at` из API-FACTS → `backfill --source artifact:<sha256_sales>,<sha256_orders>` → `collect --date-from 2026-08-27`); проверка (`WORKS-TODAY.md`; W10 = 649 / 700 860 ₽ и W35 = 225 / 263 089 ₽ в `_current`; строка статуса на `/brief`); вывод старого контейнера, `~/proxima-webapp-staging`, пустых `proxima_dev`, установка `infra/backup/*`; откат (тег `v2026.09.0-baseline` + `delete_run.py` по прогонам релиза + `WEBAPP_DATA_MODE=fixtures`; миграции не откатываются); наблюдение 3 дня (CAP-1); `CHANGELOG.md`
**And** Mike выполняет одно действие: читает runbook и не находит шага, требующего объяснений

### Story 1.14: Первый релиз M-01 на сервере **[Claude]**

As a Mike,
I want чтобы после моего «деплой» конвейер M-01 работал на VPS и наутро статус на `/brief` обновился сам,
So that данные кабинета копились с сентября.

**Acceptance Criteria:**

**Given** Stories 1.0-1.13 смержены, тег `v2026.09.NN-2`, runbook, явное «деплой» от Mike (D7)
**When** Claude выполняет runbook шаг за шагом, фиксируя вывод в `docs/operations/releases/2026-09-NN-m01.md`
**Then** миграции применены полностью; provision идемпотентен; бэкфилл из артефактов 30.08 + живой хвост SUCCEEDED; `fact_cabinet_daily_current` содержит дни с 02.03.2026 по вчера; W10 и W35 совпадают с API-FACTS; `WORKS-TODAY.md` прогнан и дополнен (таймеры активны, статус на `/brief`, `restore-check`); план отката записан до первого шага
**And** три утра подряд `collector_runs` содержит SUCCEEDED `collect` (CAP-1), `/brief` показывает «данные до <вчера>, обновлено сегодня 05:3x»; не пришёл - откат по плану
**And** Mike выполняет одно действие: открывает `/brief` через `ssh -N proxima-app` и видит строку статуса с сегодняшним временем

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

**Given** `postgres-provider.ts` дополнен `getBrief()` по AD-9 (второй `SELECT` из `brief_current`, сгенерированные типы, правило `brief.status = 'ok' AND stale IS FALSE AND brief_day = last_full_day`), блок сводки на `/brief` (компоненты `brief/`, без новых зависимостей, `UnreleasedBanner` остаётся): заказы и выручка - значение / норма / отклонение %, цвет по знаку через `lib/gyr`; `tools/morning_run.sh` получает шаги `norm` и `brief`
**When** `brief_current` содержит сводку за вчера
**Then** «29.08: 27 заказов против нормы 34.5 (−21.7 %), выручка 41 141 ₽ против 34 595 ₽ (+18.9 %)» + строка статуса; `insufficient` - «норма копится: 9/14 дней»; `stale` - предупреждение без цифр
**And** vitest через шов: ok/insufficient/stale/blocked; `test`, `typecheck`, `lint` зелёные; auth-зона не изменена
**And** Mike выполняет одно действие: `make verify` - тест `provider: brief states` зелёный (живой экран - в Story 2.6)

### Story 2.6: Релиз M-03 - сводка приходит каждое утро **[Claude]**

As a Mike,
I want чтобы после «деплой» сводка считалась на сервере каждое утро и цифры совпадали с кабинетом WB,
So that к 30.09 утренняя сводка работала без меня.

**Acceptance Criteria:**

**Given** Stories 2.1-2.5 смержены (миграции перенумерованы при необходимости), тег, релиз-заметка с планом отката, явное «деплой»
**When** Claude выполняет runbook: `apply-migrations` через `control-plane-admin`, provision (гранты), пересборка образов, ручной первый прогон `norm` + `brief`, включение шагов в `morning_run.sh`, `compose up -d webapp`
**Then** `brief_current` содержит сводку за вчера `status = ok`; норма на VPS за ближайший день с 14 полными сверена с расчётом из артефакта «Ряд продаж Амировой»; `/brief` через туннель показывает цифры; `WORKS-TODAY.md` прогнан и дополнен; план отката: prev tag + режим «только статус» + `delete_run.py`
**And** семь утр подряд `collector_runs` содержит SUCCEEDED `collect`, `norm`, `brief` (CAP-5); Mike выполняет одно действие - открывает `/brief` и сверяет вчерашние заказы и выручку с кабинетом WB; не пришла - откат

## Epic 3: Воронка копится фоном (M-01b)

С первой недели сентября воронка по nmId ежедневно из v3 и еженедельно из async CSV ложится в `fact_funnel_daily`; к 27.10 - 8 недель. Использует Epic 1, независим от Epic 2 по коду; миграция целевая `014` - при мерже после Epic 2 перенумеровать. Ссылки: AD-4, AD-5, AD-6, AD-14; D13, D20, D22.

### Story 3.0: Шаг 0 - глубина async CSV **[Claude]**

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

**Given** `014_funnel.sql` (целевой номер; `stg_wb_funnel_obs` PK `(tenant_id, nm_id, calendar_day, source, canonical_sha256)` с `run_id`, `observed_at`, view `_latest`; `fact_funnel_daily`, `fact_funnel_daily_current` с предпочтением `csv`; RLS, гранты/политики collector, norm (SELECT), janitor; поля по `COLUMN_MAP` scn001) и `jobs/funnel-v3.ts` (активные nmId = distinct из `stg_wb_orders_latest` за 30 дней; пакеты ≤ 20; окно `[run_day-7, run_day-1]`; бюджет 3/мин)
**When** прогон выполняется в harness на фикстуре `sales_funnel_v3_history` (3 nmId, 7 дней)
**Then** 21 наблюдение `source = v3` с `evidence_sha256`, 21 строка в `_current`; повтор - 0 новых (тот же `canonical_sha256`); изменённый payload за тот же день - новое наблюдение и новая версия; `= run_day` не версионируется; `morning_run.sh` получает шаг `funnel_v3`
**And** Mike выполняет одно действие: `make verify` - `funnel_v3: 21 obs, replay 0, changed payload versions` зелёный

### Story 3.2: Загрузка CSV как прогон реестра

As a оператор,
I want чтобы существующий `tools/wb_async_report.py` создавал прогон `funnel_csv_download` в реестре и не создавал tenant сам,
So that фаза 1 была прослеживаема и не ломала fail-closed.

**Acceptance Criteria:**

**Given** `tools/wb_async_report.py` изменён минимально: автосоздание `tenants` удалено (нет tenant - ошибка); при старте выполняет `set_config('proxima.tenant_id', tenant, false)` и создаёт `collector_runs` `kind = funnel_csv_download` (owner-URI, исключение AD-11 до M-04), пишет `collector_run_id` в `wb_analytics_report_tasks`, закрывает прогон SUCCEEDED/FAILED; `--period from..to` явный; создаёт не более одного отчёта в сутки после проверки `nm_report_downloads`
**When** `make verify` (`tools/tests/test_wb_async_report*.py` расширены)
**Then** тесты: отсутствующий tenant → ошибка; прогон создан и закрыт; второй запуск за день не создаёт отчёт
**And** Mike выполняет одно действие: `make verify` - `wb_async_report: run ledger` зелёный

### Story 3.3: Промоушен CSV в наблюдения и факты

As a оператор,
I want чтобы строки скачанного CSV промоутились в те же наблюдения и факты воронки, что и v3,
So that воронка накапливалась и назад, и вперёд.

**Acceptance Criteria:**

**Given** `jobs/funnel-csv-promote.ts` (`collector_runs` `kind = funnel_csv_promote`; `stg_wb_nm_report_rows(task_id)` → `stg_wb_funnel_obs(source = 'csv', evidence = tasks.downloaded_sha256)` → `fact_funnel_daily`; под `proxima_collector` - член `proxima_source_publisher`, читает 003/005 без новой миграции; всегда, независимо от состояния задачи), `proxima-funnel-csv@.{service,timer}` (Пн 06:30; фаза 1 через `control-plane-admin`, фаза 2 через `collector`)
**When** промоушен выполняется в harness на synthetic-фикстуре Story 3.0
**Then** наблюдения `csv` и факты созданы; `_current` предпочитает `csv` там, где есть оба; после `delete_run.py` прогона промоушена повтор восстанавливает факты без нового отчёта; `systemd-analyze verify` зелёный
**And** Mike выполняет одно действие: `make verify` - `funnel_csv: promote + replay after delete` зелёный

### Story 3.4: Релиз воронки **[Claude]**

As a Mike,
I want чтобы после «деплой» воронка копилась на сервере сама,
So that к 27.10 было 8 недель воронки.

**Acceptance Criteria:**

**Given** Stories 3.0-3.3 смержены (миграция перенумерована при необходимости), тег, релиз-заметка с планом отката, явное «деплой»
**When** Claude выполняет runbook: `apply-migrations`, пересборка образов, шаг `funnel_v3` в `morning_run.sh`, `systemctl enable --now proxima-funnel-csv@amirova-test.timer`, ручной первый прогон `funnel_v3`
**Then** `fact_funnel_daily_current` содержит 7 дней по активным nmId; `WORKS-TODAY.md` дополнен пунктом «воронка v3 за вчера есть»; релиз-заметка со счётчиками и планом отката
**And** следующим утром и в понедельник `collector_runs` содержит SUCCEEDED `funnel_v3`, `funnel_csv_download`, `funnel_csv_promote`; Mike выполняет одно действие - `WORKS-TODAY.md` пункт «воронка» проходит по записанным шагам

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
