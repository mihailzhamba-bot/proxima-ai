# Adversarial review v2 - ARCHITECTURE-SPINE wb-morning-brief

- Дата: 2026-08-30. Режим: read-only, враждебный, второй проход. Объект: `ARCHITECTURE-SPINE.md` v2 (18 AD, updated 18:01).
- Входы: `reviews/review-{adversarial,reconcile-inputs,rubric,verified-current}.md` (разделы critical/high), код main: `tools/verify_migrations.py`, `db/migrations/003,005,007,009,010`, `infra/compose.yaml`, `Makefile`, `tools/{apply_migrations,wb_async_report}.py`, `services/collector/src/business-signal/{secrets,http,raw-store,types,wb-client}.ts`, `infra/monitoring/*`, `infra/bootstrap/*.sh`, `docs/state/{INVENTORY,API-FACTS}.md`.
- Задача A: каждая critical/high находка первого гейта → «закрыто AD-N / частично / не закрыто». Задача B: пары единиц U1..U10, которые соблюдают все 18 AD и всё равно расходятся.
- Итог A: **32 находки critical/high в четырёх отчётах: 16 закрыто, 15 закрыто частично, 1 не закрыто.** Частичные закрытия сводятся к шести дырам ниже (N1-N3, N5-N7): v2 принял правильные правила, но не довёл их до исполнимой формы под гейтом `verify_migrations.py` и под RLS.
- Итог B: **14 новых дыр v2**: 2 критических (N1, N2), 7 серьёзных (N3-N9), 5 средних (N10-N14) + мелочи.

---

## A. Закрытие находок первого гейта

Статусы: **закрыто** - правило есть и исполнимо; **частично** - правило есть, но пара единиц всё ещё расходится (ссылка на N); **нет** - в v2 не адресовано.

### review-adversarial.md (v1)

| ID | Sev | Суть | Статус | Чем закрыто / чего не хватает |
|---|---|---|---|---|
| A-H1 | crit | версия дня из строк своего прогона vs всех наблюдений | частично | AD-2: PK `(tenant, srid, last_change_at)`, `_latest` как единственный вход, пересчёт затронутых дней из всех наблюдений. Нет: `period_floor`, нулевые дни, «затронутые дни» при DO NOTHING/ретрае → N4 |
| A-H2 | crit | `_current` после FAILED; текущий день как «полный» | закрыто | AD-3 (`max finished_at` среди SUCCEEDED, версии + статус в одной транзакции), AD-2 (`run_day` не версионируется), AD-7 (полный = `< run_day` и есть версия) |
| A-H3 | crit | RLS + `set_config` + view: 0 строк или все tenant'ы | частично | AD-13 `security_invoker` + `WITH CHECK`, AD-9 `set_config` на connect, AD-11 LOGIN вне ledger. Нет: гранты и политики на базовые таблицы для webapp/norm под `security_invoker` (N3); «одна транзакция» TS-job против FAILED-статуса (N1) |
| A-H4 | crit | delete-run не откатывает норму и сводку | частично | AD-3 `collector_run_inputs` + транзитивный `delete_run.py`. Нет: что агрегатор пишет во входы, RLS-политика janitor, `--tenant` (N1, N2) |
| A-H5 | crit | реестр артефактов ссылается на `business_signal_runs` | частично | AD-1 `wb_raw_artifacts → collector_runs CASCADE`, business-signal не трогается. Нет: locator `artifact://wb/` против константы замороженного `raw-store.ts:99` (N11); `tenant_id` в таблице (N13) |
| A-H6 | high | naive даты WB по TZ хоста; таймеры «МСК» в UTC | закрыто | AD-7 `mskDay()/msk_day()` + тест полуночи, `TIMESTAMPTZ`; AD-6 `OnCalendar … Europe/Moscow`. Остаток: SQL-форма «сегодня» не названа (N5) |
| A-H7 | high | `brief.schema.json`: кто пишет первым, деньги, signal v1 | закрыто | AD-10 владелец = control-plane, деньги строкой `.2f`, `schema_version`; AD-9 payload; `signals[]` пусто до M-04 |
| A-H8 | high | `fact_funnel_daily`: два писателя, два словаря, два реестра | частично | AD-5 одна таблица, `COLUMN_MAP`, csv-грандфазер с `collector_run_id`. Нет: кто пишет csv-факты и obs, повтор после delete-run, роль Python-пути под AD-11 (N6, N7) |
| A-H9 | high | norm: кто вставляет runs, `evaluation_day`, окно, `sample_days` | частично | AD-8 `evaluation_day` = последний полный день, окно исключает его [ASSUMPTION], `insufficient` всегда пишется; AD-11 гранты norm. Нет: ключ и `_current` у `norm_daily`, календарное vs «доступное» окно (N12) |
| A-H10 | high | stale дважды; `brief_current` после упавшего brief | частично | AD-7 stale только в view, brief копирует, webapp читает view. Нет: правило соединения статусов в webapp, `stale = NULL` (N5) |
| A-H11 | high | `test-db-refresh` = копия кабинета в базу сандбокса | частично | AD-12 Prevents переписан честно (сознательно, D8). Нет: механика refresh, гранты/RLS сандбокса, порядок с provision (N10) |

### review-reconcile-inputs.md

| ID | Sev | Суть | Статус | Чем закрыто / чего не хватает |
|---|---|---|---|---|
| R-1 | high | `DO NOTHING` по `srid` теряет поздние отмены | закрыто | AD-2 (= A-H1) |
| R-2 | high | на хосте нет uv/psql/node_modules | закрыто | AD-6 one-shot контейнеры, psql через `docker compose exec postgres`. Остаток: образов нет (N8), `.env` в контейнере (N9) |
| R-3 | high | `reportDetailByPeriod` в реестре против гейта | закрыто | AD-4 реестр без него |

### review-rubric.md

| ID | Sev | Суть | Статус | Чем закрыто / чего не хватает |
|---|---|---|---|---|
| U-C1 | crit | ledger-гейт запрещает GRANT DELETE, `webapp_readonly`, REVOKE, CREATE DATABASE | частично | AD-11 bootstrap вне ledger, роль `proxima_webapp_readonly`. Нет: column-level `GRANT UPDATE(status, finished_at)` не проходит гейт, `FOR DELETE` не в шаблоне политик, janitor-роль не в ledger (N2, N13) |
| U-C2 | crit | два реестра прогонов | частично | AD-1 (= A-H5) |
| U-H1 | high | `verify_business_signal.py` не allowlist; setInterval только в `business-signal/` | закрыто | AD-4: новый `tools/verify_wb_client.py`, запрет расширен на `src/**` |
| U-H2 | high | CSV через `wb_async_report.py` - второй клиент и хранилище | закрыто как исключение | AD-5 грандфазер + `collector_run_id`; остаток - A-H8 |
| U-H3 | high | DO NOTHING / ключ staging / `today-3` без пометки | закрыто | AD-2; AD-4 [ASSUMPTION] с шагом проверки до агрегатора |
| U-H4 | high | четыре таймера без зависимости; «полный день» при упавшем сборе; stale пишет job | закрыто | AD-6 один юнит, шаги последовательно, стоп на первой ошибке; AD-7 |
| U-H5 | high | роли NOLOGIN; LOGIN-пользователи, `security_invoker`, tenant-GUC webapp | частично | AD-11/13/9. Нет: гранты базовых таблиц под `security_invoker` (N3) |
| U-H6 | high | toolchain хоста; `apply-migrations = uv run`; `ProtectHome` | частично | AD-6 контейнеры, AD-15 канон `/srv`. Нет: `.env` внутри контейнера (N9), Dockerfile/`User=`/секреты (N8) |

### review-verified-current.md (меток severity нет; взяты 10 позиций «Сводки расхождений по важности»)

| ID | Суть | Статус | Чем закрыто / чего не хватает |
|---|---|---|---|
| V-1 | `flag=0` с коротким `dateFrom` не проверен (помечено «критично») | закрыто | AD-4 [ASSUMPTION] + два read-вызова в первой единице M-01 до реализации агрегатора |
| V-2 | `reportDetailByPeriod` | закрыто | AD-4 |
| V-3 | codegen только collector; Python-образец без pydantic, копия схемы в пакете | закрыто | AD-10: codegen на `services/webapp/src/lib/contracts/`, `dataclass + jsonschema`, копия удаляется. Остаток: `contracts/` должен попасть в образ control-plane (N8) |
| V-4 | CASCADE упрётся в RESTRICT промоутированных; webapp через view = 0 строк | частично | AD-3 `collector_run_id NULL` без CASCADE - закрыто; `set_config` на connect - закрыто; гранты базовых таблиц - нет (N3) |
| V-5 | webapp не в compose; overlay = auth ON + Caddy | закрыто | AD-15 `infra/webapp.staging.compose.yaml` (создать) |
| V-6 | control-plane на хост-таймерах; psycopg только в extra `test` | частично | AD-6 контейнеры - закрыто; перенос psycopg в `dependencies` не записан |
| V-7 | 4 из 5 ролей не существуют; 2 существующие не упомянуты | частично | AD-11 перечисляет новые роли как создаваемые. Нет: судьба `proxima_source_publisher` / `release_publisher` / `data_health_read`; роль CSV-пути (N6) |
| V-8 | TZ хоста не зафиксирован | закрыто | AD-6 `OnCalendar` с TZ, AD-7 |
| V-9 | `OnFailure` без приёмника | закрыто | AD-6 `proxima-alert@.service` |
| V-10 | async CSV create/status/file и глубина `startDate` не вызывались | **нет** | AD-5 опирается на `wb_async_report.py` без [ASSUMPTION] и без шага проверки (в отличие от `flag=0` в AD-4) |

---

## B. Новые дыры v2

Формат: пара единиц → как расходятся при полном соблюдении 18 AD → правило.

### N1 [critical] Модель транзакций прогона: AD-13 «одна транзакция» несовместима с AD-3/Conventions «FAILED + частичные строки» и с DO NOTHING из AD-2

**Пара:** U3/U4 (collect, backfill) ↔ U1 (011/012) ↔ U10 (`delete_run.py`).

**Расхождение.** AD-13: «TS-job выполняет прогон в одной транзакции с `set_config(…, true)` первым statement». AD-17: «`collector_runs` - единственный источник статуса прогонов». Conventions «Ошибки»: «job падает … `status=FAILED`; частичные строки остаются под своим `run_id` и удаляются `delete_run.py`». AD-3: «запись версий и перевод статуса в SUCCEEDED - одна транзакция».

- Вариант А (U3 буквально по AD-13): 429 или таймаут посреди прогона → ROLLBACK уносит и строку `collector_runs`. FAILED не записывается никогда; `collector_runs` не является источником статуса; «частичные строки» - пустое множество; `delete_run` для FAILED не нужен. Dead-man AD-17 живёт только на `OnFailure`.
- Вариант Б (U3 коммитит по шагам): наблюдения FAILED-прогона остаются. Ретрай (`Persistent=true` или ручной) видит те же `(srid, last_change_at)` → `DO NOTHING` → строка навсегда числится за FAILED-прогоном. `delete_run.py` FAILED-прогона - ровно то, что предписывают Conventions - каскадом удаляет наблюдения, из которых SUCCEEDED-ретрай собрал версии; `_latest` теряет строки, версии в `_current` остаются и указывают на удалённое доказательство; пересборки никто не запускает. Дополнительно `set_config(…, true)` умирает на COMMIT первого шага - следующий INSERT получает `WITH CHECK` violation (v1 H3 возвращается).
- Два исполнителя выберут разные варианты; каждый нарушает либо AD-17, либо AD-3.

**Правило (AD-13 + AD-3 + Conventions).** Прогон = три вида транзакций: (1) `INSERT collector_runs … RUNNING` - autocommit; (2) каждая строка `wb_raw_artifacts` - autocommit по мере получения (доказательство переживает сбой); (3) парсинг → наблюдения → версии → `UPDATE … SUCCEEDED` - одна транзакция, `set_config(…, true)` первым statement; при ошибке - ROLLBACK (3) и отдельный autocommit `UPDATE … FAILED`. Частичных наблюдений и версий не существует - строку «частичные строки остаются» из Conventions удалить; `delete_run` FAILED-прогона = строка прогона + его артефакты (файлы CAS остаются). `_latest` не фильтрует по статусу прогона - наблюдение есть доказательство, версия есть результат. Python-jobs (norm, brief) - та же схема; `set_config` на соединении допустим, потому что соединение живёт один прогон.

### N2 [critical] Janitor под RLS удаляет 0 строк; политика DELETE не проходит гейт; роль названа двумя именами

**Пара:** U10 (`delete_run.py`, `provision-runtime-roles.sh`) ↔ U1 (011/016).

**Расхождение.**
- AD-3: «запускается только под ролью `proxima_run_janitor`». AD-11: LOGIN-пользователь `proxima_janitor` с `GRANT DELETE` в bootstrap; в ledger-списке AD-11 NOLOGIN-роли для janitor нет.
- Все таблицы с `run_id` под RLS (AD-13). Роль без политики видит 0 строк: `DELETE FROM collector_runs WHERE run_id = $1` → `DELETE 0`, exit 0, `--dry-run` печатает нули по всем таблицам. «Прогон обратим транзитивно» - декларация, которую подтвердит зелёный `make verify`.
- `tools/verify_migrations.py:47-49`: `CREATE POLICY … FOR (SELECT|ALL|INSERT|UPDATE)` - `FOR DELETE` не в шаблоне. `CREATE POLICY … TO proxima_janitor` в 016 упадёт, если роль создаёт bootstrap после миграций (роль обязана существовать на момент CREATE POLICY); если U1 создаст `proxima_janitor NOLOGIN` в ledger - `CREATE ROLE proxima_janitor LOGIN` в bootstrap упадёт на существующей роли.
- `delete_run.py --run <uuid>`: чтобы выставить `proxima.tenant_id`, нужен tenant; узнать tenant по `run_id` нельзя - `SELECT tenant_id FROM collector_runs` под RLS без GUC пуст.

**Правило (AD-3 + AD-11).** 011 создаёт `proxima_run_janitor NOLOGIN` и политику `FOR ALL TO proxima_run_janitor USING (tenant guard) WITH CHECK (tenant guard)` на каждую таблицу с `run_id` (форма проходит гейт); bootstrap создаёт LOGIN `proxima_janitor` членом `proxima_run_janitor` и выдаёт `GRANT DELETE`. `delete_run.py --tenant <t> --run <uuid>`: оба флага обязательны, первый statement - `set_config`, без `--tenant` - отказ; `--dry-run` и удаление под одной ролью и одним GUC. RLS-тест в `make verify`: `delete_run` без GUC обязан упасть с ошибкой «0 строк для run_id», а не завершиться нулями.

### N3 [high] `security_invoker` + гранты только на view = `permission denied` для webapp и norm

**Пара:** U1 (016) ↔ U8 (`postgres-provider.ts`) ↔ U6 (`norm/loader.py`).

**Расхождение.**
- AD-11: `proxima_webapp_readonly` - «SELECT на view `brief_current`, `data_status_current`»; `proxima_job_norm` - «SELECT facts; INSERT norm, brief, runs, run_inputs». AD-13 и гейт `verify_migrations.py:71-74`: view только `WITH (security_invoker = true)`.
- При `security_invoker` привилегии и RLS проверяются от вызывающего: `SELECT FROM brief_current` под `proxima_webapp_readonly` → `permission denied for table brief_daily`; `data_status_current` читает `collector_runs` и `fact_cabinet_daily` - то же. Norm читает `fact_cabinet_daily_current`, который джойнит `collector_runs` (`finished_at`, `status`) - SELECT на runs для norm не выдан; brief читает `norm_daily` - у `proxima_job_norm` на неё только INSERT.
- Даже с грантами, без политик `FOR SELECT TO <роль>` таблицы под RLS отдают 0 строк (не ошибку). v1 H3 закрыт наполовину: `set_config` есть, гранты и политики на базовые таблицы - нет (v1 предлагал «читающие роли получают SELECT на базовые таблицы» - в v2 выпало).

**Правило (AD-11).** Грант на view под `security_invoker` ничего не даёт - гранты и политики всегда на базовые таблицы, которые view читает. 016: `proxima_webapp_readonly` - SELECT + `FOR SELECT` на `brief_daily`, `collector_runs`, `fact_cabinet_daily`, `tenants`; `proxima_job_norm` - SELECT + `FOR SELECT`/`FOR ALL` на `collector_runs`, `fact_cabinet_daily`, `norm_daily`, `brief_daily`, `collector_run_inputs`. RLS-тест: под каждой ролью `SELECT count(*)` из каждого view с GUC (> 0) и без GUC (= 0, без ошибки прав).

### N4 [high] «Затронутые дни»: нулевой день, простой таймера, `period_floor`, ретрай

**Пара:** U3 (collect) ↔ U4 (backfill) ↔ U6 (norm) ↔ U8.

**Расхождение.**
- AD-2: «пересчитывает из `_latest` все дни, затронутые наблюдениями этого прогона». Два чтения: (a) дни из строк с `run_id = этот` в БД - после `DO NOTHING` это только новые наблюдения; (b) дни из всех строк ответа в памяти. По (a) ручной повтор collect в тот же день даёт ∅ затронутых дней → версии за вчера нет → `data_status_current.stale = true` при успешном сборе.
- День с 0 заказов (WB-сбой, праздник): ни одного наблюдения → день не «затронут» → версии нет → не «полный» (AD-7) → norm `sample_days < 14` → `insufficient`; если это вчера → `stale`. Ноль как факт неотличим от «не собирали».
- Простой таймера > 3 дней: `Persistent=true` запускает один прогон с `dateFrom = run_day-3`; если `flag=0` фильтрует по `lastChangeDate` (AD-4 [ASSUMPTION]), заказы дней простоя не приходят → дыра в ряду навсегда; `last_full_day = вчера` → `stale = false`; дыру не видит никто.
- Backfill `--from 2026-03-01`: первый день ответа усечён скользящим окном WB (`API-FACTS.md:7,42` - граница по дню, алгоритм не подтверждён) → версия первого дня неполная и «полная» по AD-7. `period_floor` из v1 H1 в v2 не вошёл. Будущих дат у WB `date` нет (`mskDay ≤ run_day`), `= run_day` исключён - здесь дыры нет.

**Правило (AD-2).** collect/backfill версионируют **каждый** день интервала `[floor, run_day-1]`, где `floor = mskDay(dateFrom)` для collect и `--from + 1` для backfill (первый день ответа отбрасывается как усечённый окном WB), независимо от того, пришли ли за день строки: нет строк = версия с нулями и `evidence_sha256[]` артефактов прогона. Дни `< floor` не версионируются никогда. `dateFrom` для collect = `min(run_day-3, last_full_day+1)` - самолечение после простоя. Затронутые дни считаются из ответа, не из `run_id` в БД.

### N5 [high] Webapp: какой статус гасит цифры; `stale = NULL` после бэкфилла

**Пара:** U8 ↔ U7 ↔ U1 (013).

**Расхождение.**
- AD-9: «при `status != ok` - предупреждение вместо цифр» - `brief_current.status` или `data_status_current.stale`? Сценарий: T-1 brief ok (`brief_day = T-2`); в T collect упал → norm/brief не запускались; `brief_current` = brief от T-1 со `status = ok`, `data_status_current.stale = true`. U8 по `brief.status` показывает T-2 как «вчера»; U8 по `stale` прячет цифры. v1 H10 предлагал правило соединения - в v2 его нет.
- AD-7: `stale = collected_at < now() - 24h OR last_full_day < today_msk - 1`; `collected_at` = `finished_at` последнего SUCCEEDED **`collect`**. После бэкфилла (`kind = backfill`) и ручных norm/brief `collected_at` NULL → `NULL OR false = NULL` → в JS `null` ложь → цифры показаны как свежие. То же при пустом `fact_cabinet_daily_current`.
- `today_msk` в SQL не определён (AD-7 даёт helper только для TS/Python); `CURRENT_DATE` в контейнере = UTC, расходится с МСК в 00:00-03:00.

**Правило (AD-9 + AD-7).** Цифры на `/brief` только при `brief.status = 'ok' AND data_status.stale IS FALSE AND brief.brief_day = data_status.last_full_day`; иначе предупреждение с `last_full_day` и `collected_at`. View 013: `stale = COALESCE(…, true)`, `collected_at` по `kind IN ('collect', 'backfill')`, «сегодня» только как `(now() AT TIME ZONE 'Europe/Moscow')::date` - записать в AD-7 как SQL-форму helper'а, `CURRENT_DATE` в `db/` запрещён.

### N6 [high] `funnel_csv` под AD-11 неисполним при текущем гейте: Python-путь пишет в таблицы без `tenant_id`

**Пара:** U5b (обёртка `wb_async_report.py`) ↔ U1 ↔ U10 (роли).

**Расхождение.**
- AD-11: «Job никогда не подключается superuser-URI». `tools/wb_async_report.py` пишет `wb_analytics_report_tasks` (INSERT `:313` + UPDATE lifecycle `:440`), `wb_analytics_quota_events` (`:322`), `raw_wb_analytics_responses` (`:409`), `stg_wb_nm_report_rows` (`:477`) и `tenants` (`:296`, `ON CONFLICT DO NOTHING` - опечатка в `--tenant-id` создаёт tenant).
- `raw_wb_analytics_responses` и `stg_wb_nm_report_rows` без `tenant_id` (003, 005), RLS включён (`009:52-54`), политики только `FOR SELECT TO proxima_source_publisher` через EXISTS (`009:61-75`). Гейт `verify_migrations.py:46-56` допускает EXISTS-форму только `FOR SELECT` → INSERT-политику для этих таблиц в ledger написать нельзя; `ALTER TABLE ADD COLUMN tenant_id` можно, заполнить 1220 существующих строк - нет (UPDATE в ledger запрещён).
- Итог: под любой не-владельческой ролью INSERT в эти таблицы блокирует RLS. Единственный исполнимый вариант - владелец таблиц (superuser из `.env`, как сейчас `make collect-wb-analytics`), что AD-11 запрещает. U5b, соблюдая AD-11, не заработает; соблюдая AD-5 «оборачивает существующий скрипт» - нарушит AD-11.

**Правило (AD-5 + AD-11).** Грандфазер записать целиком: `funnel_csv` до переноса в TS (Deferred M-04) исполняется под owner-URI (`postgres_user`), это единственное разрешённое исключение из AD-11 с датой пересмотра; авто-INSERT в `tenants` из скрипта удаляется (tenant обязан существовать, fail-closed); новые таблицы `stg_wb_funnel_obs`/`fact_funnel_daily` пишутся под `proxima_job_collector` из TS-шага (N7), не из Python.

### N7 [high] `funnel_csv`: кто пишет факты из CSV, повтор после delete-run невозможен, воскресный таймер собирает неделю 8-дневной давности

**Пара:** U5b ↔ U1 (014) ↔ U9 (таймер) ↔ U10.

**Расхождение.**
- AD-5: `stg_wb_funnel_obs … source v3|csv`; AD-16 диаграмма: R (`wb_async_report.py`) → `wb_analytics_report_tasks, stg_wb_nm_report_rows, fact_funnel_daily` - минуя `stg_wb_funnel_obs`. Один исполнитель напишет csv-наблюдения, другой - только факты; `evidence_sha256` для csv-версии (артефакт лежит в `raw_wb_analytics_responses.content_sha256`, не в `wb_raw_artifacts`) не задан.
- `wb_async_report.py:683-687`: при `lifecycle_status = 'DOWNLOADED'` `collect()` возвращает задачу и ничего не делает; `UNIQUE (tenant_id, report_type, period_from, period_to)` (`003:45`) - второй задачи на ту же неделю не будет. После `delete_run` прогона funnel_csv каскад удалит `fact_funnel_daily(source = csv)` (`run_id` CASCADE), `stg_wb_nm_report_rows` останутся (`task_id` RESTRICT, `collector_run_id` без CASCADE) → повтор прогона = no-op → csv-факты не восстановить.
- `latest_closed_week` (`:242-247`) = `current_monday-7 .. current_monday-1`. Таймер `proxima-funnel-csv@` в воскресенье 06:30 (AD-6): `current_monday` = 6 дней назад → собирается неделя, закончившаяся 8 дней назад; неделя, заканчивающаяся сегодня, приедет через 7 дней. Лаг 7-8 дней при цели «8 недель к 27.10».

**Правило (AD-5 + AD-6).** `funnel_csv` = один прогон из двух фаз: (1) `wb_async_report.py` (download, идемпотентен, задача может существовать), (2) промоушен `stg_wb_nm_report_rows(task_id)` → `stg_wb_funnel_obs(source = 'csv', run_id, evidence = tasks.downloaded_sha256)` → `fact_funnel_daily` - всегда, независимо от состояния задачи; повтор после delete-run пересоздаёт только фазу 2. Таймер - понедельник 06:30 МСК (после утреннего юнита); `--period from..to` явный для ручных повторов.

### N8 [high] Образы, пользователь юнита, секреты: Dockerfile'ов нет, 0600-файлы читает только их владелец

**Пара:** U9 (compose/units/deploy) ↔ U2 (`secrets.ts`) ↔ U10 (provision).

**Расхождение.**
- В репо один `services/webapp/Dockerfile`; `.dockerignore` нет. AD-15 `docker compose build collector control-plane webapp` предполагает два Dockerfile'а, которых Structural Seed не перечисляет. Control-plane образу нужны `Makefile`, `tools/`, `db/migrations`, `contracts/` (AD-10 удаляет копию схемы из пакета) → контекст = корень репо; `COPY . .` без `.dockerignore` затянет `.env` (пути секретов) и `node_modules`.
- Кто запускает `docker compose run`: юнит «по образцу монитора» - `User=proxima-monitor`, `ProtectSystem=strict`, `PrivateDevices=true` (`infra/monitoring/proxima-host-monitor.service`) - без доступа к `docker.sock`; AD-6/AD-15 не называют `User=`.
- Секреты: WB-токены `0600 proxima-admin` (INVENTORY §i), URI ролей по AD-11 - `0600`, владелец не назван (существующие provision-скрипты пишут `root:root`, `provision-postgres-diagnostics.sh:31-35`). `secrets.ts:23-37` открывает файл с `O_NOFOLLOW` и требует `mode & 0o077 == 0` → внутри контейнера файл читает только процесс с uid владельца; compose `secrets:` (file) = bind-mount с хостовыми uid/mode. Непривилегированный `USER` в образе (как `webapp` uid 1001) не прочитает ни root-овые URI, ни admin-овские токены; `USER root` в контейнере никто не записал как решение.
- `/srv/proxima-ai/repo` принадлежит `proxima-admin` (`bootstrap-vps.sh:79`) - `git fetch` под ним, `docker compose` через `sudo`; последовательность в AD-15 этого не различает.

**Правило (AD-6 + AD-15 + Conventions «Секреты»).** Structural Seed добавляет `services/collector/Dockerfile`, `services/control-plane/Dockerfile` (контекст - корень, multi-stage как webapp) и корневой `.dockerignore` (`.env`, `node_modules`, `.git`, `fixtures/`, `_bmad-output/`). Юниты `proxima-morning@`/`proxima-funnel-csv@`: `User=root`, `ProtectHome=true`, без `ProtectSystem=strict`/`PrivateDevices` (docker CLI). Контейнеры jobs - `USER 1010` (`proxima-jobs`); все `/etc/proxima-ai/secrets/*_uri` и `<tenant>_wb_*_token` - `1010:1010 0600` (provision + первый релиз делают chown), монтируются через compose `secrets:`. Деплой: `git` под `proxima-admin`, `docker compose` через `sudo` - записать как есть.

### N9 [high] `make apply-migrations` внутри control-plane читает `.env` хоста

**Пара:** U9 ↔ U1.

**Расхождение.** `Makefile:62-63` → `tools/apply_migrations.py --env-file .env` → `connect_repository` (`wb_async_report.py:891-908`): `POSTGRES_HOST` (default `127.0.0.1`), `POSTGRES_USER_FILE=/etc/proxima-ai/secrets/postgres_user`. На VPS `.env` = `/srv/proxima-ai/repo/.env` с host-путями (INVENTORY §i). Внутри `docker compose run control-plane` `127.0.0.1` - сам контейнер, `/etc/proxima-ai/secrets/` не смонтирован, `.env` в образе нет и не должно быть. Два исполнителя: bind-mount репо + `network_mode: host` vs `env_file` + `secrets:`. AD-15 пишет «`docker compose run --rm control-plane make apply-migrations`» как работающую команду.

**Правило (AD-15 + AD-6).** Сервис `control-plane` в `infra/compose.yaml` получает `env_file: infra/jobs.env` (в git, без секретов: `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`, `POSTGRES_DB=proxima`, `POSTGRES_USER_FILE=/run/secrets/postgres_user`, `POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password`) и `secrets: [postgres_user, postgres_password]`; цель `apply-migrations` принимает `ENV_FILE ?= .env`. Owner-URI (superuser) используется только здесь и в N6 - в AD-11 записать исчерпывающий список.

### N10 [medium] `make test-db-refresh`: порядок с provision, непустая база, гранты и RLS сандбокса

**Пара:** U10 ↔ U1 ↔ зона OpenHands.

**Расхождение.** AD-12 `pg_dump proxima | psql proxima_test`: в непустую базу - «already exists» на каждом объекте, без `ON_ERROR_STOP` - тихо частично; `DROP DATABASE` блокируется сессией `proxima_sandbox`; после пересоздания базы гранты `proxima_sandbox` (выданы provision'ом) пропадают - дамп несёт гранты только `proxima_*`-ролям ledger (кластерные роли переносить не надо - тот же кластер); сандбокс под RLS без GUC видит 0 строк - «видит только копию» превращается в «не видит ничего», и не решено, цель это или баг. Порядок первого запуска: миграции 011-016 (NOLOGIN-роли) → provision (LOGIN, `proxima_test`) → refresh → снова provision (гранты) - в AD-11/12 не записан.

**Правило (AD-12).** `tools/test_db_refresh.sh` = `pg_terminate_backend` для `proxima_test` → `DROP DATABASE proxima_test WITH (FORCE)` → `CREATE DATABASE proxima_test` → `pg_dump proxima | psql -v ON_ERROR_STOP=1 proxima_test` → `GRANT SELECT ON ALL TABLES IN SCHEMA public TO proxima_sandbox` → `ALTER ROLE proxima_sandbox IN DATABASE proxima_test SET proxima.tenant_id = '<tenant>'`. Provision идемпотентен и идёт строго после миграций; `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC` в provision явно.

### N11 [medium] AD-1 locator `artifact://wb/sha256/` против замороженного `raw-store.ts`

**Пара:** U2 ↔ U1 (011 CHECK) ↔ AD-18.

**Расхождение.** `raw-store.ts:99` хардкодит `artifact://business-signal/sha256/<hex>` и пишет манифест с этим locator в `manifests/<runId>/<source>/`; `SignalSource` (`types.ts:6`) = три литерала. AD-1 требует `artifact://wb/sha256/<hex>` и переиспользование `raw-store` без правок (AD-18). U2 либо правит замороженный файл, либо пишет в `wb_raw_artifacts` один locator, а в манифест на диске - другой; U1 ставит CHECK по AD-1.

**Правило (AD-1).** Канонический префикс для всех CAS-объектов = фактический `artifact://business-signal/sha256/` (один каталог `PROXIMA_RAW_DIR`, один префикс), `source` ∈ `official_wb_statistics | official_wb_analytics`; CHECK в 011 - `~ '^artifact://business-signal/sha256/[0-9a-f]{64}$'`. Переименование префикса - вместе с переездом business-signal (M-04).

### N12 [medium] Версии нормы и сводки: нет ключа и `_current` у `norm_daily`; `brief_current` - одна строка или по строке на день

**Пара:** U6 ↔ U7 ↔ U8 ↔ U1 (015/016).

**Расхождение.** AD-14: 015 = `norm_daily` без view; AD-8 - колонки без UNIQUE; повтор norm-прогона за тот же `evaluation_day` даёт две строки; brief «читает `norm_daily`» - какую версию? AD-9: `brief_current` «на ключ» - если ключ `(tenant, brief_day)`, view отдаёт по строке на день, и `SELECT … LIMIT 1` без ORDER BY в U8 берёт произвольный день. AD-8 «14 полных дней непосредственно перед `evaluation_day`»: календарные 14 (пропуск → `sample_days < 14` → `insufficient`) или последние 14 доступных (пропуски скрыты) - U6 и тест CAP-4 зафиксируют одно, U7 и Mike ждут другое.

**Правило (AD-8 + AD-9 + AD-14).** 015: `norm_daily UNIQUE (tenant_id, evaluation_day, metric, run_id)` + `norm_daily_current` по правилу AD-3; brief читает `norm_daily_current WHERE evaluation_day = brief_day` и пишет `run_inputs`; `brief_current` = ровно одна строка на tenant (SUCCEEDED brief с max `brief_day`, при равных - max `finished_at`); окно нормы = календарные `[eval-14, eval-1]`, `sample_days` = дни с версией, медиана по имеющимся, `< 14` → `insufficient` (пропуск виден, не скрыт).

### N13 [medium] Гейт миграций против буквы AD-1/AD-3/AD-11

**Пара:** U1 ↔ `tools/verify_migrations.py`.

**Расхождение.** (a) `GRANT … UPDATE(status, finished_at)` (AD-11) - `GRANT_PARSED_PATTERN` (`:160-164`) не знает column-list → banned; проходит только `GRANT UPDATE ON collector_runs` целиком, и «UPDATE только status/finished_at» остаётся конвенцией без DB-enforcement (триггеры запрещены: `CREATE FUNCTION` в `CREATE_RULE_PATTERN`). (b) `collector_run_inputs(run_id, input_run_id)` (AD-3) и `wb_raw_artifacts(artifact_id, run_id, endpoint, …)` (AD-1) без `tenant_id`; AD-13 требует `tenant_id` в каждой таблице, а гейт допускает политики только с tenant-guard или `task_id`-EXISTS → без колонки таблица либо без RLS (нарушение AD-13), либо не проходит гейт. (c) `kind` содержит `funnel_v3|funnel_csv`, юнит - `proxima-funnel-csv@` (`-` vs `_`, v1 H12 повторяется).

**Правило (AD-1 + AD-3 + AD-11).** Обе таблицы получают `tenant_id text NOT NULL REFERENCES tenants` и стандартную политику; UPDATE-грант на `collector_runs` целиком + правило в Conventions + RLS-тест, что job не меняет `kind`/`started_at`; `kind` = имя job'а с `_`, юнит - с `-`, маппинг записан один раз в AD-6.

### N14 [medium] Tenant `amirova-test` и файлы токенов: никто не переименовывает, симлинки не работают

**Пара:** U9 (`morning_run.sh`) ↔ U2 (client) ↔ INVENTORY §i.

**Расхождение.** AD-13: второй tenant = `/etc/proxima-ai/secrets/<tenant>_wb_*_token`; первый tenant - существующие `wb_statistics_token` / `wb_analytics_token` / `wb_finance_token` без префикса + `.env` `WB_*_TOKEN_FILE` (одно значение на хост). `morning_run.sh amirova-test` не знает, откуда брать путь: по шаблону `<tenant>_…` (файла нет) или из `.env` (не масштабируется на второй tenant). INVENTORY 7b: два разных `wb_analytics_token` (`/etc` 25.08 vs `~/signal-inputs` 13.08) - канон для `funnel_v3` не назван. `secrets.ts:23` `O_NOFOLLOW` - алиас через симлинк отвергается, значит «оставить старые имена и добавить симлинки» не работает.

**Правило (AD-13 + Conventions «Секреты»).** Единственная схема имён - `/etc/proxima-ai/secrets/<tenant>_wb_<category>_token`; первый релиз M-01 делает `mv` (не symlink) трёх файлов в `amirova-test_wb_*_token` с chown по N8; канон analytics-токена - `/etc`, `~/signal-inputs` коллектором не используется; `morning_run.sh <tenant>` передаёт `--<category>-token-file` по шаблону; `.env` `WB_*_TOKEN_FILE` остаётся только для `wb_api_probe.py`.

### Мелочи (low), без пар

- `collector_runs.image_digest` / `git_sha`: процесс в контейнере их не знает; локально собранные образы не имеют RepoDigest - `morning_run.sh` передаёт `PROXIMA_IMAGE_ID=$(docker image inspect -f '{{.Id}}' …)` и `PROXIMA_GIT_SHA=$(git -C /srv/proxima-ai/repo rev-parse HEAD)` в env контейнера.
- `psycopg` только в extra `test` (`services/control-plane/pyproject.toml`), AD-8 loader в проде - перенести в `dependencies` (V-6 не закрыт).
- Уникальность `srid` в `orders` (13 325 строк фикстуры) не проверена - PK AD-2 на этом стоит; добавить `count(*) = count(distinct srid)` в первую единицу M-01 рядом с проверкой `flag=0`.
- `DO NOTHING` при том же PK, но другом payload (WB поправил `finishedPrice` без смены `lastChangeDate`) молча отбрасывает изменение - при конфликте сравнивать canonical payload и падать `WB_SCHEMA_DRIFT`, как `wb-client.ts:143`.
- pg-roundtrip в сандбоксе: `pg_local_roundtrip.sh` требует локальный initdb PG16; в зоне OpenHands его нет, `proxima_dev` выводится (AD-12) → `make verify` там даёт `pg-roundtrip: SKIP` exit 0 (AGENTS.md pitfall) - RLS-тест «под реальной ролью» в сандбоксе не выполнится никогда; гейт для OpenHands-единиц = CI (`.github/workflows/verify.yml`), записать в Conventions «Тесты».
- `OnFailure=proxima-alert@%n.service` на шаблонном юните - рабочая форма; ставить на `.service`, не на `.timer` (V-4.2 первого гейта).

---

## C. Ответы на 10 вопросов задания

| № | Вопрос | Вердикт | Дыра |
|---|---|---|---|
| 1 | `_latest` DISTINCT ON при равном `last_change_at` из двух прогонов | Тай невозможен: PK `(tenant_id, srid, last_change_at)` - вторая строка = `DO NOTHING`. Реальные проблемы: (а) строка приписана первому наблюдателю; если это FAILED-прогон, его удаление уносит доказательство SUCCEEDED-ретрая; (б) тот же PK с другим payload отбрасывается молча; (в) уникальность `srid` не проверена | N1, мелочи |
| 2 | агрегатор «все дни, затронутые …»: строки до `period_floor`, будущие даты | Будущих дат нет (`mskDay(date) ≤ run_day`), `= run_day` исключён AD-2. До floor: floor в v2 не определён; усечённый первый день бэкфилла, нулевые дни и дни простоя без версий; «затронутые» через `run_id` в БД после DO NOTHING = ∅ | N4 |
| 3 | `collector_run_inputs` для агрегатора; delete старого прогона и каскад по наблюдениям | Не определено, что агрегатор пишет во входы. Если пишет distinct `run_id` всех наблюдений затронутых дней - удаление бэкфилла = замыкание на все collect'ы (полная переборка, документировать); если не пишет - каскад по наблюдениям ломает `_latest` под живыми версиями. Плюс FAILED-атрибуция | N1 (+ правило: агрегатор пишет distinct `run_id` всех наблюдений, вошедших в свёртку) |
| 4 | `funnel_csv`: UNIQUE(tenant, type, period), PK(task_id, row_number) без `run_id` → obs/facts; delete-run | Путь в `stg_wb_funnel_obs`/`fact_funnel_daily` не задан (диаграмма минует obs); повтор после delete-run = no-op (`DOWNLOADED` early-return + UNIQUE); RLS запрещает не-владельцу писать в таблицы 003/005 | N6, N7 |
| 5 | образы: кто собирает, `docker compose run` под кем, секреты, `ProtectHome`, `/srv` | Dockerfile'ов и `.dockerignore` нет; `User=` юнита не назван; `0600` + `O_NOFOLLOW` → uid контейнера = владелец файла, а владельцы разные (root / proxima-admin); `/srv/proxima-ai/repo` - `proxima-admin` (`bootstrap-vps.sh:79`) | N8 |
| 6 | `make apply-migrations` в образе и `.env` | Читает host-view `.env` (`127.0.0.1`, host-пути секретов, superuser) - в контейнере не работает | N9 |
| 7 | `proxima_test` refresh под superuser, RLS, роли, порядок | Роли кластерные - дамп одной базы их не переносит, но они уже есть (тот же кластер); `pg_dump` переносит RLS, политики и гранты ledger-ролям; порядок: миграции → provision → refresh → provision (гранты). Проблемы: непустая база, сессии сандбокса, потеря грантов, RLS без GUC у сандбокса | N10 |
| 8 | webapp `set_config(…, false)` в `pool.on('connect')` + pg 8.16 Pool | Работает: pg-pool эмитит `connect` до выдачи клиента, `Client` исполняет запросы FIFO → `set_config` идёт первым; сессионный GUC живёт с соединением - корректно, pgbouncer в стеке нет (при transaction-pooling в октябре правило меняется на per-transaction). Оговорки: `client.query(...).catch(...)` обязателен (unhandled rejection роняет Node 22); `WEBAPP_TENANT_ID` валидировать по `^[a-z0-9][a-z0-9_-]{2,63}$` при старте (пустая строка = 0 строк молча); `getDataDb()` в `lib/db/client.ts:42-50` хук не ставит - provider обязан владеть своим `Pool` | - (что показывать - N5) |
| 9 | `evaluation_day` при stale; brief за день не появится | Приемлемо: `data_status_current` зависит только от `collector_runs` + `fact_cabinet_daily_current` и станет `stale` по 24 ч / `last_full_day`; brief_daily за день не нужен. Не приемлемо: у webapp нет правила, какой статус гасит цифры, и `stale = NULL` после бэкфилла | N5 |
| 10 | `amirova-test` vs `<tenant>_wb_*_token` vs `wb_statistics_token` | Никто не переименовывает; симлинки отвергает `O_NOFOLLOW`; два analytics-токена без канона | N14 |

---

## D. Порядок закрытия

N1 → N2 → N3 (модель прогона и права: без них RLS-тест зелёный, а `delete_run` и `/brief` пустые) → N4/N5 (ряд и статус на `/brief` - приёмка CAP-1/CAP-3) → N6/N7 (воронка, CAP-6) → N8/N9 (деплой; без них первая единица M-01 не соберётся на VPS) → N10-N14 и мелочи. V-10 (async CSV не вызывался) - пометить [ASSUMPTION] в AD-5 с шагом проверки по образцу AD-4.
