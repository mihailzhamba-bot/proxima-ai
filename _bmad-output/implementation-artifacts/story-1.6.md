# Story 1.6: Дневной ряд кабинета и статус данных

Status: ready-for-dev
Jira: PMM-47 (эпик PMM-38, ступень M-01) · Epic 1 · AD-карта: AD-2, AD-7 (таблицы, гранты, политики: AD-3, AD-11, AD-13, AD-14)
Ветка исполнителя: `feat/m01-story-1.6` от `feat/m01-story-1.4` @ `81b3873` (PR #50 открыт, не влит)
Источник истории: `_bmad-output/planning-artifacts/epics.md:213-228` (дословно в разделах 1-2). Сужение второго AC-блока - решение Mike 02.09.2026 (раздел 2.2, 4.2).
Оценка объёма (implementation-readiness.md): 500-600 строк, «на грани» - не расширять.

## 0. Исполнителю

Ты - исполнитель единицы работы Story 1.6 проекта PROXIMA AI. Работай автономно до конца, вопросов по ходу не задавай - непонятное собери в раздел «Открытые вопросы» финального отчёта. **Факта нет в документах репо - это вопрос в отчёт, а не выдумка.**

### 0.1 Окружение

- Чекаут репозитория лежит в подкаталоге `proxima-ai/` твоего рабочего каталога. Первое действие - `cd proxima-ai`; все `git`, `npm`, `make` - оттуда. Рабочий каталог разговора намеренно корень workspace, не чекаут.
- Ветка `feat/m01-story-1.6` уже создана от `81b3873` (`feat/m01-story-1.4`) и выбрана; git identity задана. Другие ветки не создавать, на них не переключаться.
- Сети к GitHub нет, git remote нет - remote не создавать, `git init` не делать. `git push` и PR - не делать (раздел 9).
- `docs/state/` и `_bmad-output/` в дереве - справочные: читать, не менять, не стейджить.
- Тулчейн: Node 22, uv + Python 3.14 (`uv python install 3.14` при необходимости). Перед `npm ci` / `make verify` - `export PUPPETEER_SKIP_DOWNLOAD=1`.

### 0.2 Прочитать первым делом, в этом порядке

1. `AGENTS.md` целиком.
2. Этот файл целиком.
3. `_bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md`: AD-2 и AD-7 (следовать дословно), затем AD-3, AD-11, AD-13, AD-14 и таблицу «Consistency Conventions». Выдержки - в разделе 3, но читать оригинал.
4. `db/migrations/011_run_ledger.sql`, `db/migrations/012_stg_wb_orders_sales.sql` - образец грантов, политик, self-checksum. Менять их нельзя.
5. `services/collector/src/jobs/collect.ts` (`parseCollectArgs`, `runCollect`, `writeObservations`), `src/wb/observations.ts`, `src/wb/msk-day.ts` (`mskDay`, `mskToday`, `mskInstant`), `src/wb/run-ledger.ts` (`RunLedger.succeed` = транзакция (3) по AD-3), `src/wb/log.ts` (`logRunStep`), `src/wb/client.ts` (`Clock` - виртуальные часы для тестов).
6. `services/collector/tests/collect.db.test.ts` - образец db-harness: DSN из `PROXIMA_TEST_DSN_COLLECTOR` и `PROXIMA_TEST_POSTGRES_DSN`, skip без них, cleanup своих прогонов по `run_id`; `tests/collect.test.ts` - unit-образец.
7. `docs/state/API-FACTS.md`: раздел «flag=0 семантика (31.08.2026, Story 1.0)» и таблица полей `supplier/sales` (28 полей: `date`, `lastChangeDate`, `finishedPrice`, `forPay`, `saleID` S/R, `srid`, …) и `supplier/orders` (`isCancel`, `cancelDate`, …).
8. `_bmad-output/specs/spec-wb-morning-brief/glossary.md` - формулы (раздел 3.7).
9. `tools/tests/test_runtime_roles_schema.py` - pytest считает политики (`policy_count == 36`): после 013 число вырастет, тест обновить.

## 1. Story (epics.md, дословно)

As a Mike,
I want чтобы после прогона в БД лежала версия каждого дня интервала, а view отвечал, до какого дня данные полные,
So that норма и сводка читали один ряд.

## 2. Acceptance Criteria

### 2.1 Первый блок - дословно (`epics.md:221-223`)

**Given** `013_fact_cabinet_daily.sql` (`fact_cabinet_daily` по AD-2, `fact_cabinet_daily_current` по AD-3, `data_status_current` по AD-7 с `COALESCE(…, true)` и `(now() AT TIME ZONE 'Europe/Moscow')::date`; гранты/политики collector, norm (SELECT), webapp (SELECT), janitor; гейт: `CURRENT_DATE` в `db/` отсутствует) и агрегатор `facts/cabinet-daily.ts` в конце `collect`/`backfill`
**When** прогон выполняется
**Then** версия для каждого дня `[floor, run_day-1]` (день без строк = нули + артефакты прогона); `floor = mskDay(dateFrom)` для `collect`, `--from + 1` для живого `backfill`, первый день артефакта для режима `artifact`; `= run_day` не версионируется; `collector_run_inputs` содержит distinct `run_id` наблюдений свёртки; `dateFrom` для `collect` без флага = `min(run_day-3, last_full_day+1)`

Уточнение к «в конце `collect`/`backfill`» и к `--from + 1` / режиму `artifact`: в этой единице агрегатор подключается только к `collect`; `backfill` не существует (раздел 4.2). Агрегатор - функция с явными параметрами `{ tenantId, runId, floor, runDay }`, чтобы Story 1.5 вызвала её со своим `floor` без правок.

### 2.2 Второй блок - сужен решением Mike 02.09.2026

Оригинал `epics.md:225-228` (для справки, не действует в этой единице):

> **Given** синтетические артефакты Story 1.5 с известными суммами недель S1 и S2
> **When** `backfill --source artifact` + агрегатор выполняются в harness
> **Then** суммы `_current` за S1/S2 равны эталону (формулы `glossary.md`); `data_status_current` отдаёт `last_full_day`, `stale = true` при прогоне старше 24 ч (подмена часов) и `false` в пределах 24 ч; сверка с реальными W10/W35 из API-FACTS - на VPS в Story 1.14
> **And** Mike выполняет одно действие: `make verify` - `cabinet-daily: versions every day, S1/S2 sums` зелёный

Действующая редакция (Story 1.5 не запускалась, артефактов и `backfill` нет):

**Given** синтетические наблюдения двух недель S1 и S2 с заранее известными суммами, засеянные db-тестом прямо в `stg_wb_orders_obs` / `stg_wb_sales_obs` под синтетическим прогоном `collector_runs` со статусом `SUCCEEDED` (структура строк `payload` - как в `tests/fixtures/wb-api/statistics/{orders,sales}/sample.json`; значения обезличенные, никаких реальных SKU, цен, кабинетов - тест сам задаёт числа и сам считает эталон)
**When** агрегатор выполняется в harness - напрямую (экспортируемая функция под `PROXIMA_TEST_DSN_COLLECTOR`) и через `runCollect` на `FixtureTransport` (как в `collect.db.test.ts`)
**Then** суммы `fact_cabinet_daily_current` за S1/S2 равны эталону (формулы `glossary.md`, раздел 3.7); `data_status_current` отдаёт `last_full_day`; `stale = true` при прогоне старше 24 ч (подмена часов: `finished_at` синтетического прогона сдвигается в прошлое) и `false` в пределах 24 ч; сверка с реальными W10/W35 из API-FACTS - на VPS в Story 1.14
**And** (дополнение из `_bmad-output/planning-artifacts/epics-review-2026-08-30.md`, пункт M5) `stale = true` при `last_full_day < msk_today - 1` даже при свежем `collected_at`
**And** Mike выполняет одно действие: `make verify` - `cabinet-daily: versions every day, S1/S2 sums` зелёный

Имя db-теста (node:test) - ровно `cabinet-daily: versions every day, S1/S2 sums`, по образцу `collect: idempotent replay 0 new rows` из Story 1.4.

## 3. Инварианты спайна (обязательны; цитаты из `ARCHITECTURE-SPINE.md` v3.3)

### 3.1 AD-2 - Наблюдения с естественным ключом, факты - версии каждого дня интервала (Rule, дословно)

> `stg_wb_orders_obs` PK `(tenant_id, srid, last_change_at)`, `stg_wb_sales_obs` PK `(tenant_id, sale_id, last_change_at)`; колонки `run_id`, `content_sha256`, `payload jsonb`, `canonical_sha256`. Повтор PK с тем же `canonical_sha256` - `DO NOTHING`; тот же PK с другим payload - прогон падает `WB_SCHEMA_DRIFT` (как `wb-client.ts`). View `stg_wb_orders_latest` / `stg_wb_sales_latest` = `DISTINCT ON (tenant_id, key) ORDER BY last_change_at DESC`, без фильтра по статусу прогона (наблюдение = доказательство) - единственный вход агрегатора. `fact_cabinet_daily(tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub, evidence_sha256[])`, зерно день кабинета в МСК по WB `date`, формулы - `glossary.md`. Агрегатор версионирует **каждый** день интервала `[floor, run_day-1]` из `_latest`, включая дни без строк (версия с нулями и артефактами прогона); `floor = mskDay(dateFrom)` для `collect`, `--from + 1` для `backfill` (первый день ответа отброшен как усечённый окном WB); дни `< floor` и `= run_day` не версионируются. `dateFrom` для `collect` = `min(run_day-3, last_full_day+1)` - самолечение после простоя. […] Агрегатор пишет в `collector_run_inputs` distinct `run_id` всех наблюдений, вошедших в свёртку. «Заказы кабинета» берутся только отсюда; `fact_order_counts` (nmId, `ordersCount` из CSV) - воронка, их сумма никогда не подменяет кабинетный ряд (сверка - Deferred, M-04).

Опущенный фрагмент `[…]` описывает бэкфилл из сохранённого ответа и `tools/cas_import.ts` - это Story 1.5, в этой единице не реализуется.

Прочтение AD-2 для этой единицы (если видишь иное - в «Открытые вопросы»):
- `run_day` для `collect` = `mskToday(clock)` на момент прогона; `floor = mskDay(dateFrom)`; версии пишутся для каждого `calendar_day` из `[floor, run_day-1]`, даже если в `_latest` нет ни одной строки за день.
- `evidence_sha256[]` дня = distinct `content_sha256` наблюдений `_latest`, вошедших в день; для дня без строк - sha256 артефактов текущего прогона (`wb_raw_artifacts` по `run_id`).
- `collector_run_inputs(tenant_id, run_id, input_run_id)` получает distinct `run_id` наблюдений свёртки; `CHECK (run_id <> input_run_id)` в 011 - собственный прогон не записывается.
- `_latest` не фильтрует по статусу прогона - агрегатор тоже не фильтрует.

### 3.2 AD-7 - Время, «полный день» и `stale` определены в одном месте (Rule, дословно)

> `calendar_day` = дата поля WB `date` в `Europe/Moscow` через единственный helper `mskDay()` (TS) / `msk_day()` (Python) / SQL-форму `(now() AT TIME ZONE 'Europe/Moscow')::date` (в `db/` `CURRENT_DATE` запрещён), с тестом на границу полуночи; моменты - `TIMESTAMPTZ`; `OnCalendar` всегда с явным `Europe/Moscow`. Полный день = `calendar_day < run_day` **и** есть версия в `fact_cabinet_daily_current`. View `data_status_current`: `last_full_day`, `collected_at` (finished_at последнего SUCCEEDED прогона `kind IN ('collect','backfill')`), `stale = COALESCE(collected_at < now() - interval '24 hours' OR last_full_day < msk_today - 1, true)`. `stale` вычисляется только этим view; `brief_daily.status` копирует его на момент записи; webapp читает view.

Prevents (дословно): «день по UTC в одном job и по МСК в другом (`date-window.ts:29`); `stale = NULL`, читаемый как «свежо»; `CURRENT_DATE` контейнера (UTC) в SQL». `msk_today` в view - только через `(now() AT TIME ZONE 'Europe/Moscow')::date`.

### 3.3 AD-3 - Модель прогона (выдержки, дословно)

> Прогон = (1) `INSERT collector_runs … RUNNING` autocommit; (2) каждая строка `wb_raw_artifacts` autocommit по получении; (3) парсинг → наблюдения → версии → `run_inputs` → `UPDATE … SUCCEEDED` - одна транзакция; […] при ошибке - ROLLBACK (3) и отдельный autocommit `UPDATE … FAILED`. Частичных наблюдений и версий не существует. […] Все новые таблицы: `run_id NOT NULL REFERENCES collector_runs ON DELETE CASCADE`; `*_current` = строки прогона с максимальным `finished_at` среди `status='SUCCEEDED'` на ключ.

Для `collect.ts`: агрегатор вызывается внутри `RunLedger.succeed(...)` после `insertObservations` - тем же `client`, в той же транзакции; ключ `_current` = `(tenant_id, calendar_day)`.

### 3.4 AD-11 - Роли, гранты и политики (выдержки, дословно)

> каждая последующая миграция, создающая таблицу с `run_id`, в том же файле выдаёт гранты и политики всем ролям, которым таблица нужна, включая `FOR ALL` для `proxima_run_janitor`. В ledger - только `proxima_*` NOLOGIN-роли, `GRANT SELECT/INSERT/UPDATE` целиком на таблицу и политики шаблона `FOR SELECT|ALL TO <роль> USING (tenant guard) WITH CHECK (tenant guard)` **на базовые таблицы, которые читают view** (грант на view под `security_invoker` ничего не даёт): `proxima_job_collector` - `collector_runs`, `collector_run_inputs`, `wb_raw_artifacts`, `stg_wb_*_obs`, `fact_cabinet_daily`, `fact_funnel_daily`, `tenants`(SELECT); `proxima_job_norm` - SELECT `collector_runs`, `fact_cabinet_daily`, `tenants`; […] `proxima_webapp_readonly` - SELECT + `FOR SELECT` на `brief_daily`, `collector_runs`, `fact_cabinet_daily`, `tenants`; `proxima_run_janitor` - `FOR ALL` на всё с `run_id` (DELETE-грант вне ledger).

Prevents: `tools/verify_migrations.py` «запрещает `GRANT DELETE`, column-level GRANT, `REVOKE`, `CREATE DATABASE`, роли не `proxima_*`, политики вне шаблона». Шаблон политики - строки `CREATE POLICY tenant_isolation_<роль> … USING (tenant_id = current_setting('proxima.tenant_id', true)) WITH CHECK (…)` из 012. Гранты SELECT на `collector_runs` и `tenants` для norm/webapp уже выданы в 011 - проверь, не дублируй.

### 3.5 AD-13 - Tenant в каждой строке, RLS, `security_invoker` (Rule, выдержка)

> каждая новая таблица: `tenant_id text NOT NULL REFERENCES tenants`, `ENABLE ROW LEVEL SECURITY`, политика шаблона AD-11; каждый view - `WITH (security_invoker = true)`. TS- и Python-job: `set_config('proxima.tenant_id', $1, false)` первым statement соединения (AD-3); транзакция (3) GUC не переустанавливает. Tenant сентября - существующий `amirova-test`.

### 3.6 AD-14 - Миграции additive-only с self-checksum (Rule, выдержка)

> `db/migrations/NNN_<snake>.sql`, `BEGIN…COMMIT`, self-checksum `normalized-self-v1`, `tools/verify_migrations.py` […] План (целевые номера): […] `013` `fact_cabinet_daily`, `fact_cabinet_daily_current`, `data_status_current`.

Файл - `db/migrations/013_fact_cabinet_daily.sql`, комментарий `-- checksum-policy: normalized-self-v1` и `INSERT INTO schema_migrations (version, name, sha256)` как в 012; checksum считается функцией `normalized_sha256` из `tools/verify_migrations.py` (сам файл гейта не менять). Если на момент мержа `013` окажется занят - перенумерация с пересчётом checksum (правило AD-14), это делает не исполнитель.

### 3.7 Conventions и формулы

Строки таблицы «Consistency Conventions» спайна (дословно):

> | Naming | таблицы `stg_wb_<dataset>_obs`, `fact_<grain>_daily`, view `<table>_latest` / `<table>_current`; `kind` с `_`, юниты `proxima-<job>@<tenant>` с `-`; схемы `contracts/<entity>.schema.json`; роли `proxima_job_*`, `proxima_webapp_*`, `proxima_run_*`; идентификаторы английские, документация русская |
> | Ключи и время | `tenant_id text` (`amirova-test`), `run_id uuid`, `calendar_day date` в Europe/Moscow по полю WB `date` через `mskDay()`; естественные ключи WB: `srid` (orders), `saleID` (sales), `nmId`; `last_change_at TIMESTAMPTZ` из `lastChangeDate`; деньги `numeric(14,2)`, в JSON - строка |
> | Записи | наблюдения append-only, `DO NOTHING` только при том же `canonical_sha256`; факты - версии по `run_id`, читаются через `_current`; `UPDATE` только `status`/`finished_at` в `collector_runs` |
> | Логи | одна JSON-строка на событие в stdout (journald через docker): `{ts, level, run_id, tenant_id, kind, step, msg, ...}`; payload только в CAS; helper `log.ts` / `log.py` |
> | Тесты | collector `node:test` + `tsx`, webapp `vitest`, control-plane `pytest`; сеть запрещена (AD-4); фикстуры в `tests/fixtures/wb-api/`; RLS-тест под каждой ролью; `make verify` - гейт на маке/CI, в сандбоксе OpenHands гейт = CI; `WORKS-TODAY.md` - регрессия до автотестов |

Формулы из `glossary.md` (дословно):

> | Заказы | Строки WB Statistics `orders` за календарный день по полю `date`, без `isCancel`. Метрика тревоги. |
> | Продажи / выручка | Строки `sales` с `saleID` на `S`; выручка = сумма `finishedPrice`. Возвраты (`R`) в выручку не входят. Справочная метрика. |
> | Полный день | Календарный день, за который сбор завершён после его окончания. Текущий день и день последней частичной выгрузки - неполные, в норму не входят. |

Отсюда колонки `fact_cabinet_daily` за `calendar_day = mskDay(payload.date)`:
- `orders_count` - строки `stg_wb_orders_latest` без `isCancel`; `cancelled_count` - строки с `isCancel = true`;
- `sales_count` - строки `stg_wb_sales_latest` с `saleID`, начинающимся на `S`; `returns_count` - на `R`;
- `revenue_rub` - сумма `finishedPrice` по `S`-строкам; `forpay_rub` - сумма `forPay` по `S`-строкам (в `glossary.md` `forPay` не определён - принято по имени колонки из AD-2 и поля из API-FACTS; если считаешь иначе - в «Открытые вопросы», не молча).
- Деньги - `numeric(14,2)`.

## 4. Граница: что в Story 1.6 НЕ входит

### 4.1 Story 1.4 - уже сделано в базе ветки (`81b3873`), не переделывать

`012_stg_wb_orders_sales.sql` (таблицы `stg_wb_*_obs`, view `_latest`, гранты collector, политики collector + janitor), запросы WB в `collect.ts`, `observations.ts` (парсер, `canonical_sha256`, `DO NOTHING`, `WB_SCHEMA_DRIFT`), транзакция наблюдений + `SUCCEEDED`, `mskInstant`, `logRunStep`, тесты `collect.db.test.ts` / `collect.test.ts`. Миграцию 012 не менять. В `collect.ts` меняются ровно две вещи: вызов агрегатора в транзакции (3) после наблюдений и дефолт `--date-from` (раздел 5). Существующие тесты 1.4 должны остаться зелёными.

### 4.2 Story 1.5 - не существует, не реализовывать

`jobs/backfill.ts`, `tools/cas_import.ts`, режим `--source artifact`, живой режим с бюджетом `sales` 1/мин, пагинация 80 000 строк, `--resume`, `floor = --from + 1`, «первый день артефакта», регистрация артефактов в `wb_raw_artifacts` прогона `backfill`. Агрегатор 1.6 ничего не знает о backfill: только `{ tenantId, runId, floor, runDay }` на входе; вызов из `backfill` - задача 1.5.

### 4.3 Story 1.11 - статус данных на `/brief`, не трогать webapp

`services/webapp/src/lib/data/postgres-provider.ts`, `Pool` по `WEBAPP_DATA_DATABASE_URI_FILE`, `WEBAPP_TENANT_ID`, строка «Данные до …, обновлено …», `UnreleasedBanner`, vitest webapp. 1.6 даёт только view `data_status_current` и SELECT-гранты/политики `FOR SELECT` для `proxima_webapp_readonly` на базовые таблицы, которые view читает (AD-11). Ни одного файла в `services/webapp/` не менять.

### 4.4 Прочее

Story 1.7 (`tools/delete_run.py`, RLS-матрица) - здесь только `ON DELETE CASCADE` и политика janitor. Story 1.14 - сверка с реальными W10/W35 на VPS. Epic 2 (`norm_daily`, `brief_daily`) - только SELECT-гранты для `proxima_job_norm` на `fact_cabinet_daily`. Контракт `contracts/cabinet-daily.schema.json` (Story 2.2) не менять и не генерировать.

## 5. Хвост из Story 1.4: дефолт `--date-from`

Из тела PR #50 (Story 1.4), раздел «Вне scope (хвосты)»: «Дефолт `--date-from = min(run_day-3, last_full_day+1)` - Story 1.6.»

Текущее состояние (`services/collector/src/jobs/collect.ts` @ `81b3873`, `parseCollectArgs`): `--date-from` обязателен, проверяется regex `^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2})?$` с ошибкой «`--date-from must be YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS (Moscow wall clock)`»; значение уходит в WB как есть вместе с `flag=0` (`query = dateFrom, flag=0`).

Требуется в этой единице (AD-2: «самолечение после простоя»):
- флаг становится необязательным; явно заданный флаг побеждает всегда;
- без флага: `run_day = mskToday(clock.now())`, `last_full_day` - из `data_status_current` под GUC tenant'а (соединение прогона, до запросов к WB); `dateFrom = min(run_day-3, last_full_day+1)` в формате `YYYY-MM-DD`; если полного дня ещё нет (`last_full_day IS NULL`) - `run_day-3`;
- выбранное значение и его источник (`flag` | `default`) - в JSON-лог шага через `logRunStep` (`step: 'date-from'`);
- `floor` агрегатора = `mskDay(dateFrom)` для обоих случаев;
- unit-тесты с виртуальными часами (`Clock` из `client.ts`): нет данных → `run_day-3`; `last_full_day = run_day-1` → `run_day-3`; `last_full_day = run_day-10` → `run_day-9`; явный флаг → флаг.

Напоминание из API-FACTS (31.08, Story 1.0): `flag=0` фильтрует по `lastChangeDate`, «допущение AD-4 подтверждено, `dateFrom = run_day-3` остаётся» - окно в 3 дня не расширять.

## 6. Задачи / подзадачи

- [ ] `db/migrations/013_fact_cabinet_daily.sql`: `fact_cabinet_daily` (колонки AD-2, `tenant_id … REFERENCES tenants`, `run_id … ON DELETE CASCADE`, PK `(tenant_id, calendar_day, run_id)`, `numeric(14,2)`, `evidence_sha256 char(64)[]`), индексы по `run_id` и `(tenant_id, calendar_day)`; view `fact_cabinet_daily_current` (`security_invoker`, DISTINCT ON `(tenant_id, calendar_day)` по прогону с максимальным `finished_at` среди `SUCCEEDED`); view `data_status_current` (`security_invoker`, по tenant: `last_full_day`, `collected_at`, `stale` по формуле AD-7, `msk_today` через `(now() AT TIME ZONE 'Europe/Moscow')::date`); гранты и политики: collector ALL, norm SELECT + `FOR SELECT`, webapp SELECT + `FOR SELECT`, janitor `FOR ALL`; `ENABLE ROW LEVEL SECURITY`; self-checksum.
- [ ] `services/collector/src/facts/cabinet-daily.ts`: экспортируемая функция агрегатора `{ tenantId, runId, floor, runDay }` на переданном `client` транзакции: свёртка `_latest` по `mskDay(payload.date)` → версии всех дней `[floor, runDay-1]` (нули + evidence прогона для пустых) → `collector_run_inputs` (distinct `run_id` наблюдений, кроме собственного) → возвращает счётчики; `logRunStep` `step: 'aggregate'` с `floor`, `run_day`, `days`, `input_runs`. Экспорт из `src/index.ts` по образцу 1.4.
- [ ] `collect.ts`: вызов агрегатора внутри `ledger.succeed` после `insertObservations`; дефолт `--date-from` (раздел 5); `CollectResult` дополняется счётчиками агрегатора.
- [ ] Тесты: `tests/cabinet-daily.db.test.ts` (node:test, `*.db.test.ts`, skip без DSN) - `cabinet-daily: versions every day, S1/S2 sums` (версия на каждый день интервала включая пустые, суммы S1/S2 = эталон, `run_inputs`, `= run_day` не версионируется), `stale` три случая (свежо; `collected_at` старше 24 ч; `last_full_day < msk_today-1`), повтор прогона на тех же наблюдениях - новая версия каждого дня и `_current` указывает на неё; RLS: под `PROXIMA_TEST_DSN_NORM` / `PROXIMA_TEST_DSN_WEBAPP` view отдаёт строки с GUC и 0 без (по образцу RLS-ожиданий AD-12). `tests/cabinet-daily.test.ts` - формулы свёртки на структурных строках, дефолт `--date-from` (раздел 5). Каждый тест удаляет свои прогоны по `run_id`.
- [ ] Гейт «`CURRENT_DATE` в `db/` отсутствует»: pytest `tools/tests/test_migrations_no_current_date.py` - обходит `db/**/*.sql`, падает на токене `CURRENT_DATE` (регистронезависимо, по границам слова; `CURRENT_TIMESTAMP` разрешён). `tools/verify_*.py` не трогать - это защищённый путь, коммит с ним будет отвергнут.
- [ ] `tools/tests/test_runtime_roles_schema.py`: обновить ожидаемое число политик и список таблиц с RLS под 013.
- [ ] `make verify` целиком зелёный (раздел 8); коммиты атомарные: `feat(db): story 1.6 - cabinet daily facts and data status views`, `feat(collector): story 1.6 - cabinet-daily aggregator and date-from default`, `test(...)` при необходимости.

## 7. Правила репо (обязательные)

- Существующие `db/migrations/*` не менять и не переименовывать - только новая `013_*.sql`, additive, `BEGIN…COMMIT`, self-checksum.
- Не трогать: `tools/verify_*.py`, `.github/workflows/*`, `services/collector/src/contracts/*.ts` (генерируются `make codegen`), auth-зону webapp (`src/lib/auth*`, `src/app/api/auth/`, `src/app/login/`, `src/lib/db/`), `services/control-plane/src/proxima/`, `services/collector/src/business-signal/*` (только переиспользование).
- WB API только READ; живой сети в тестах нет (`WB_ALLOW_LIVE_NETWORK` не ставить); тесты - на фикстурах и синтетических наблюдениях.
- Каждая новая запись помечена `run_id`, идемпотентна, удаляется по `run_id` целиком (CASCADE).
- Ни одного выдуманного числа: реальные SKU, цены, cabinet ID не использовать; тестовые суммы задаёт сам тест.
- Значения токенов, паролей, URI нигде не появляются - ни в коде, ни в логах, ни в отчёте; только имена файлов/переменных.
- `git add <files>` только своих файлов; не `git add -A` / `git add .`. `next-env.d.ts` webapp не коммитить.
- Скрипты - bash-3.2-совместимые (без extglob, mapfile, ассоциативных массивов).
- Коммиты - английский, conventional-префикс; документация и комментарии в SQL/TS - можно английские, идентификаторы английские.
- Факта нет в документах репо - вопрос в отчёт, не выдумка.

## 8. Гейт

`PUPPETEER_SKIP_DOWNLOAD=1 make verify` зелёный целиком (install + codegen + typecheck + test + contracts + migrations + pg-roundtrip + provenance + architecture + boundary + secrets + vps + business-signal + wb-client).

Известное ограничение песочницы: PG16 `initdb` нет, поэтому `pg-roundtrip: SKIP` - db-тесты (`*.db.test.ts`) здесь не выполняются, их выполнит CI (`.github/workflows/verify.yml`, PG16) на PR. Поэтому: (а) SQL миграции проверь `make migrations` (статика + self-checksum); (б) db-тесты пиши строго по образцу `collect.db.test.ts` - те же переменные, тот же skip, cleanup по `run_id`; (в) всё, что можно проверить без БД (формулы, дефолт `--date-from`, `CURRENT_DATE`-гейт, число политик по тексту миграции), покрой unit-тестами и pytest, которые выполняются здесь.

## 9. Ветка и PR

- Вся работа - только в ветке `feat/m01-story-1.6` (уже выбрана). Коммитить в неё; ветки не переключать, не переименовывать.
- `git push` не делать, PR из песочницы не открывать (сети к GitHub нет). PR откроет оркестратор после внешнего `make verify`, на базу `feat/m01-story-1.4` (stacked поверх PR #50).
- **PR не мержить.** Мерж, тег и деплой - только явным решением Mike (DECISIONS.md D7, D25). Никаких `merge`, `rebase` в `main`, `proxima-pr-merge`.

## 10. Финальный отчёт

1. Коммиты: hash + subject, в порядке создания.
2. Хвост `make verify` с PASS-строками (и строкой `pg-roundtrip: SKIP`).
3. Список созданных и изменённых файлов.
4. Число политик до/после 013 и список таблиц с RLS.
5. «Открытые вопросы» - всё, чего нет в документах репо и что пришлось трактовать (например, `forpay_rub`, `evidence_sha256[]` для пустого дня). Пусто - так и напиши: «Открытые вопросы: нет».

## 11. Хронометраж (заполняет оркестратор, не исполнитель)

| Точка | UTC | Комментарий |
|---|---|---|
| T0 постановка (dispatch в OpenHands) | 2026-09-02T04:46:11Z | `bad_dev_story.sh`, prompt sha256 `e3d1b8e3…2ee675` |
| T1 воркер закончил (бандл забран) | 2026-09-02T04:56:29Z | 4 коммита, head `3e1b8a5`; Δ T1−T0 = 10 мин 18 с |
| T2 PR открыт | | |
| T3 CI `verify` зелёный | | |
| Δ T2−T0 | | от постановки до PR |

## 12. Dev Agent Record (заполняет оркестратор)

- Профиль: fedor (Codex) · run-id: `story-1-6` · попытка: 1
- Conversation id: `2805e5bb-11ff-517a-bd52-c3aa2a70ff8a` (workspace `/srv/openhands/persistence/workspace/project/2805e5bb11ff517abd52c3aa2a70ff8a`)
- Base: `81b38733fa8e3e3ec1bf770239e2f48a5b95457d` (`feat/m01-story-1.4`)
- local_ref: `refs/openhands/story-1-6/1/head`
- Гейты моста (base / contract_files / sandbox_clean / ancestry / forbidden_paths / secret_scan): pass / pass / pass / pass / pass / pass; `stop_hook: unknown` (hook к bridge-разговорам не применяется, гейт снаружи)
- Коммиты воркера: `9091f38` feat(db): story 1.6 - cabinet daily facts and data status views · `06fc34d` feat(collector): story 1.6 - cabinet-daily aggregator and date-from default · `d393d71` test(collector): cover cabinet daily facts and migration guards · `3e1b8a5` fix(collector): type cabinet daily database client precisely (410 добавленных строк, 10 файлов)
- Отчёт воркера: `make verify` в песочнице зелёный, `pg-roundtrip: SKIP`; политики RLS 36 → 40; «Открытые вопросы: нет»
- Внешний `make verify` (worktree `proxima-ai-story16`, хост claudette): все шаги PASS, `pg-roundtrip: SKIP` (нет PG16 на хосте; db-тесты - в CI). Рендер архитектуры потребовал скопировать `chrome-headless-shell` 151.0.7922.77 из кэша `openhands-agent` в `~/.cache/puppeteer` (сетевая загрузка недоступна)
- PR:
