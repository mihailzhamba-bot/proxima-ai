# Ревью спайна по чеклисту «хорошего спайна» - wb-morning-brief

Дата: 2026-08-30. Объект: `ARCHITECTURE-SPINE.md` (status: draft, 13 AD). Режим: read-only, сверка с кодом main + ветками `ai/pa-50`, `pa41-full-w2-phase3`, `PA-03-02-promotion`, `pmm-20-scn-001`, `pmm29-contracts`. Пути от корня репо.

## Вердикт

Как build-substrate спайн **не готов**: 2 critical + 6 high. Парадигма, AD-1/2/6/7/8 и стек ратифицированы верно, но AD-3, AD-4, AD-9, AD-12 противоречат уже включённым гейтам репо (`tools/verify_migrations.py`, `tools/verify_business_signal.py`) и существующему реестру прогонов `business_signal_runs`. Единицы M-01 (collect) и M-01b (funnel), собранные независимо, разойдутся минимум в 5 точках, которые спайн не фиксирует.

## Сводка находок

| ID | Severity | Где | Суть |
|---|---|---|---|
| C1 | critical | AD-3, AD-9, AD-12 | Ledger-гейт запрещает то, что спайн кладёт в миграции 011-015: `GRANT DELETE`, роль `webapp_readonly`, `REVOKE`, `CREATE DATABASE` |
| C2 | critical | AD-1, AD-3 | Два реестра прогонов: `business_signal_raw_artifacts.run_id` → `business_signal_runs` (RESTRICT), спайн вводит `collector_runs`; связь не определена, delete-run не удалит доказательства |
| H1 | high | AD-4, AD-5 | `verify_business_signal.py` - не allowlist; запрещает `reportDetailByPeriod`, который спайн включает в реестр; перенос URL в `wb/client.ts` ломает гейт; запрет `setInterval` не покрывает новые каталоги |
| H2 | high | CAP-6, AD-4, AD-13 | Недельный CSV идёт через `tools/wb_async_report.py` (Python, без run_id, payload в БД) - второй WB-клиент и второе хранилище доказательств |
| H3 | high | AD-2, AD-5, Conventions | `ON CONFLICT DO NOTHING` по `srid` теряет поздние `isCancel`; ключ staging и выбор последней версии строки не определены; окно `today-3` - непомеченное допущение |
| H4 | high | AD-5, AD-6, AD-7 | Четыре таймера по времени без зависимости от успеха; «полный день» = `< today` даже при упавшем сборе; «stale > 24 ч» пишет job, который при мёртвом таймере не запустится |
| H5 | high | AD-9, AD-11, AD-7 | Роли 009 - NOLOGIN; LOGIN-пользователи, их URI, `security_invoker` у view, tenant-GUC для webapp не определены; при подключении superuser-URI RLS и «janitor - единственная роль с DELETE» ничего не значат |
| H6 | high | AD-5, AD-10 | На хосте нет uv/Python 3.14/psql/node_modules; `make apply-migrations` = `uv run`; образец `proxima-host-monitor.service` имеет `ProtectHome=true`, что закрывает `~/proxima-ai` |
| M1 | medium | AD-10 | Канон `~/proxima-ai` против `infra/vps-contract.json paths.repository=/srv/proxima-ai/repo` (гейт `make vps`) и `REPOSITORY_DIR` в bootstrap-скриптах; допущение не помечено |
| M2 | medium | AD-3 | `ON DELETE CASCADE` по `run_id` рядом с `attempt_id … ON DELETE RESTRICT` - каскад может упасть; `source_family` CHECK неизменяем под additive-only |
| M3 | medium | Conventions | `CREATE OR REPLACE` запрещён гейтом - view `_current` неизменяемы, правила эволюции нет; `security_invoker = true` обязателен, в спайне не назван |
| M4 | medium | AD-11 | tenant в спайне `amirova`, в данных сервера и Makefile `amirova-test`; правила переименования нет |
| M5 | medium | Deferred, CAP-7 | `fact_order_counts` (nm-report `ordersCount`, nmId) и `fact_cabinet_daily.orders_count` (Statistics `orders` без `isCancel`) - два определения «заказов» при глоссарии с одним |
| M6 | medium | AD-9 | `proxima_test` не создаётся compose; `psql` на хосте нет; доступность `172.17.0.1` из rootless-зоны OpenHands не проверена; bridge открыт всем root-docker контейнерам |
| M7 | medium | AD-10, Structural Seed | webapp нет в `infra/compose.yaml`; overlay `webapp.compose.yaml` = auth ON + Caddy (отложено); сентябрьский способ запуска webapp не определён |
| M8 | medium | AD-5, измерение «операции» | `OnFailure=` требует юнит-отправитель, которого нет; нет dead-man проверки «сводка не пришла»; GlitchTip и journald не упомянуты |
| M9 | medium | AD-1, измерение «данные» | Raw CAS-store на диске не входит в ночной бэкап (только pg_dump); ретеншн raw/версий/runs не задан |
| M10 | medium | AD-5, CAP-6 | v3 `sales-funnel` «за вчера», хотя часть данных доезжает несколько дней (API-FACTS рекомендует перекрытие 7 дней) |
| L1 | low | AD-2 | `evidence_sha256[]` в факте против существующего `fact_lineage_records` - два механизма lineage |
| L2 | low | ERD, Structural Seed | Нет рёбер `collector_runs` ↔ raw-артефакты / `fact_order_counts`; нет evidence для `fact_funnel_daily`; `MON -.OnFailure.-> TIMERS` направлен наоборот |
| L3 | low | AD-13 | Граф не содержит `tools/wb_async_report.py` и S3; целевой путь codegen для webapp не назван |
| L4 | low | Docs | `docs/architecture/*.mmd` (рендер `make architecture`) описывают «TypeScript scheduler», «Restic backup» - противоречат спайну, план обновления не назван |
| L5 | low | AD-4 | `services/collector/tests/fixtures/wb-api/` одноимённо с gitignored `fixtures/wb-api/` (паттерн якорный, не игнорируется) - стоит сказать явно |
| L6 | low | Stack | `psycopg` только в extra `test` control-plane, не runtime-зависимость; `uv 0.11.7` - версия с мака, в репо не закреплена |
| L7 | low | Проза | Непомеченные допущения: канон `~/proxima-ai`, `dateFrom=today-3`, tenant `amirova`, 05:30 как момент полноты вчерашних данных, bridge из rootless-зоны, 200 КБ лимит фикстур |

## Чеклист

### 1. Точки расхождения для M-01..M-05 - FAIL

Спайн фиксирует много (run_id, версии фактов, контракты, роли, номера миграций), но пропускает точки, в которых две независимые единицы разойдутся:

- Ключ staging и обработка поздних обновлений строки (H3). `orders` содержит `isCancel`/`cancelDate` (`docs/state/API-FACTS.md:25`); при `flag=0` строка приезжает повторно с новым `lastChangeDate`. Спайн: «`ON CONFLICT DO NOTHING` по естественному ключу внутри одного прогона» (Conventions «Записи») и «upsert по ключу» (AD-5) - взаимоисключающие формулировки. Единица collect выберет `(srid)`, единица facts - `(srid, run_id)`, и `orders_count без isCancel` начнёт расходиться с кабинетом (CAP-5 success).
- Какой реестр прогонов у raw-артефактов (C2). `services/collector/src/business-signal/http.ts:78-90` пишет через `repository.recordRawArtifact` в `business_signal_raw_artifacts`, чей `run_id` - FK на `business_signal_runs` (`db/migrations/004_business_signal_slice.sql:86`, `ON DELETE RESTRICT`), со статусами stockout-сценария (`:36-38`) и `window_from/to NOT NULL`. Единица collect либо вставит фиктивную строку в `business_signal_runs`, либо заведёт новый реестр - спайн не говорит.
- Кто и где вычисляет `stale` (H4): CAP-3 row говорит «view `data_status_current` ← `collector_runs`», AD-7 - «`brief_daily.status ok|stale|blocked`» и webapp рендерит по `status`. Два места, две единицы (M-01 и M-03).
- tenant_id (M4): `Makefile:66` `--tenant-id amirova-test`, `API-FACTS.md:17` «тенант `amirova-test`», на сервере 1220 строк `stg_wb_nm_report_rows` под ним; спайн - `amirova` (AD-11, AD-5). Единица funnel продолжит писать под старым, единица collect - под новым.
- Как webapp попадает под RLS (H5): view с `security_invoker` пропускают RLS до таблиц; `webapp_readonly` должен выставлять `proxima.tenant_id` в каждой транзакции - в webapp нет понятия tenant до октября. Не определено.
- Создание `proxima_test` и refresh без `psql` на хосте (M6), сентябрьский запуск webapp (M7), эволюция view при запрете `CREATE OR REPLACE` (M3), механизм lineage - массив в факте или `fact_lineage_records` (L1), путь codegen для webapp (L3).

### 2. Исполнимость Rule и связь с Prevents - FAIL

- AD-3: «`make delete-run` под ролью `proxima_run_janitor` (единственная роль с DELETE)» неисполнимо через ledger: `tools/verify_migrations.py:35-39` `GRANT_ALLOWED_FORM` допускает только `SELECT|INSERT|UPDATE|USAGE`. Либо janitor - superuser (тогда «единственная роль» - декларация), либо GRANT живёт вне ledger, чего спайн не говорит (C1).
- AD-4: «новый эндпоинт добавляется в реестр и в allowlist `tools/verify_business_signal.py`» - в верификаторе нет allowlist: он требует присутствия трёх URL в `services/collector/src/business-signal/*.ts` (`:19-26`) и запрещает два пути (`:27-29`). Реестр с `reportDetailByPeriod` противоречит запрету. Prevents «второй http-клиент» не обеспечивается ничем (H1).
- AD-5: «in-process `setInterval`/`node-cron` запрещены `verify_business_signal.py`» - верно только для `business-signal/*.ts` (`:31`); для `jobs/`, `wb/` проверки нет.
- AD-9: «bridge `172.17.0.1:5432` используется только `proxima_sandbox`» - порт на docker0 виден всем контейнерам root-docker; ограничение не выражено ни pg_hba, ни compose (M6).
- AD-11: шаблон политики без `TO <role>` и `WITH CHECK` - `009_runtime_roles.sql` и `CREATE_POLICY_ALLOWED_FORM` (`verify_migrations.py:46-56`) требуют `FOR … TO proxima_[a-z_]+ USING (…) [WITH CHECK (…)]`. Rule как записано не пройдёт гейт.
- AD-13: «разрешённые рёбра только как на диаграмме» - ни одного именованного механизма проверки (import-boundary есть только для `imported/`, `tools/verify_runtime_boundary.py`). Декларация.
- AD-10: `docker compose up -d (postgres, webapp)` - webapp в `infra/compose.yaml` отсутствует (M7).

Исполнимые и совпадающие с Prevents: AD-1 (raw-store существует, `raw-store.ts:60-130`), AD-2, AD-6, AD-7 (кроме stale), AD-8 (`diagnosis/validator.py` есть, `make codegen` есть), AD-12 (нумерация и self-checksum проверяются `verify_migrations.py:261-280`).

### 3. Deferred не даёт разойтись - FAIL (частично)

- «SKU/категорийный грейн - на существующем `fact_order_counts`» - `fact_order_counts` наполняется `promote-order-counts.ts` (pa41) из `stg_wb_nm_report_rows` (async CSV, поле `ordersCount`), а не из Statistics `orders`; Σ по nmId ≠ `fact_cabinet_daily.orders_count` (M5). M-04 получит второй смысл слова «заказы» вопреки глоссарию.
- «Отказ от async CSV в пользу v3 - пересмотр в октябре» - до октября CAP-6 живёт двумя путями с разными правилами доказательств и обратимости (H2); отложено не решение, а конфликт с AD-1/3/4.
- «Auth и роли - октябрь» - оставляет открытым, как webapp выставляет tenant для RLS уже в сентябре (H5).
- Остальные пункты (порог, LLM, второй tenant, Telegram, git-lfs, ротация) - действительно не создают расхождений.

### 4. Стек ратифицирован из репо - PASS с оговорками

Совпадает: Node `>=22 <23` (`package.json:17`), TS 5.8.3, pg 8.16.3, ajv 8.20.0, tsx 4.20.3 (`services/collector/package.json`), Next 16.3.3, React 19.2.8, drizzle 0.45.2, better-auth 1.7.1, vitest 4.1.11 (`services/webapp/package.json`), json-schema-to-typescript 15.0.4 (`package.json:21`, lock 15.0.4), pydantic 2.13.4, jsonschema 4.25.1, pytest 8.4.2, psycopg 3.3.4 (`services/control-plane/pyproject.toml`, `uv.lock`), postgres:16.10-alpine (`infra/compose.yaml:5`), Ubuntu 24.04 (`infra/vps-contract.json`). Новых технологий нет; `FixtureTransport`/реестр - код, не технология.
Оговорки: `psycopg` только в extra `test` (`pyproject.toml` `test = [...]`) - AD-6 loader требует его в `dependencies` (L6); `uv 0.11.7` - локальный `uv --version` на маке, в репо не закреплён; на сервере uv нет вовсе (H6).

### 5. Ратификация brownfield-кода - FAIL

| Проверка | Факт | Вывод |
|---|---|---|
| `RecordedHttpClient` / raw-store существуют? | Да: `http.ts:58-97`, `raw-store.ts:52-130`; локатор `artifact://business-signal/sha256/<hex>` (`raw-store.ts:99`), CHECK в `004:96` | AD-1 совпадает по форме. Но регистрация идёт в `business_signal_raw_artifacts` с FK на `business_signal_runs` (C2) |
| `fact_order_counts` UNIQUE и `attempt_id` совместимы с run_id? | `007:49-60`: `attempt_id uuid NOT NULL … ON DELETE RESTRICT`, `UNIQUE (attempt_id, tenant_id, nm_id, calendar_day)`, составной FK на `fact_attempt_runs`. На сервере 007-010 не применены (`MIGRATION-GAPS.md` §7.6), таблица пуста | `ADD COLUMN run_id` additively - да. Но `ON DELETE CASCADE` по run_id рядом с RESTRICT по attempt_id: каскад из `collector_runs` через `fact_attempt_runs` упрётся в RESTRICT на `fact_order_counts.attempt_id` (порядок RI-триггеров не гарантирован) - M2. `source_family` CHECK (`007:6`) под additive-only не расширить |
| `verify_business_signal.py`: setInterval/node-cron и «ровно 3 URL»? | `:19-26` - три URL должны **присутствовать** в `business-signal/*.ts` (не «ровно»); `:27-29` - запрещены `/api/v1/supplier/stocks` и `/api/v5/supplier/reportDetailByPeriod`; `:31` - `setInterval`/`node-cron` только в этом каталоге | AD-4 сломает гейт двумя способами: реестр содержит запрещённый `reportDetailByPeriod`; вынос URL из `business-signal/` в `wb/client.ts` даст «missing official READ endpoint». Оставить URL в обоих местах = второй клиент (H1) |
| RLS-паттерн 009 = AD-11? | `009:60-160`: `ENABLE ROW LEVEL SECURITY` + политики `FOR ALL/SELECT TO <proxima_role> USING (…) WITH CHECK (…)`, per-role; комментарий `009:58-60`: владелец таблицы обходит RLS. Роли NOLOGIN (`009:3-6`) | AD-11 воспроизводит только `USING`, без `TO` и `WITH CHECK`; не говорит о LOGIN-пользователях и об обходе RLS владельцем (H5) |
| compose bridge `172.17.0.1` = AD-9? | `infra/compose.yaml:18-19`: и `127.0.0.1:${PROXIMA_POSTGRES_PORT}` и `172.17.0.1:5432:5432` | Совпадает в main; на сервере не задеплоено (`INVENTORY.md` флаг 6), зона OpenHands - rootless docker UID 1002 с собственным `proxima-dev` Postgres; путь к `proxima_test` ещё никто не проверял (M6). `proxima_test` в compose не создаётся (`compose.yaml:7` только `POSTGRES_DB: proxima`) |
| Ветки для переиспользования существуют? | `origin/ai/pa-50`, `…/pa41-full-w2-phase3`, `…/PA-03-02-promotion`, `…/pmm-20-scn-001-…`, `…/pmm29-contracts` - все есть (`git branch -a`) | PASS. `postgres-provider.ts` в pa-50 - заглушка с `reject`; `signal.schema.json` в pmm29 - draft 2020-12, `scenario_code` enum SCN-001/005/008 |

### 6. Capability → Architecture Map - PASS с оговорками

Все восемь CAP присутствуют, привязки правдоподобны. Оговорки: CAP-6 row называет `tools/wb_async_report.py` - это нарушает AD-4 («все вызовы WB через `wb/client.ts`»), AD-13 (нет такого ребра) и AD-1/AD-3 (`raw_wb_analytics_responses` хранит payload jsonb с `task_id`, без run_id и CAS, `003:68-82`; `wb_async_report.py:296` сам вставляет в `tenants`) - H2. CAP-3 разнесён между view и `brief_daily.status` (H4). CAP-7 опирается на `fact_order_counts` с иным смыслом «заказов» (M5). Разделяемая дневная квота async-отчётов (D20, `DAILY_REPORT_QUOTA = 20`, `wb_async_report.py:35`) в карте не учтена.

### 7. Измерения инициативы - FAIL

| Измерение | Статус в спайне | Пробел |
|---|---|---|
| Деплой и среды | решено (AD-9, AD-10) | нет runtime на хосте для таймеров (uv, node_modules, psql) - `INVENTORY.md` §11, §41; `Makefile:62-63` `apply-migrations` = `uv run`; конфликт канона с `vps-contract.json` (M1); webapp вне compose (M7) |
| Инфра/провайдер | решено (VPS, S3) | - |
| Операции: мониторинг/алерты | частично (OnFailure → Telegram) | юнита-отправителя нет (`host_monitor.py` шлёт только capacity-алерты); нет dead-man на «brief не создан к 06:30»; какой Unix-пользователь запускает job и читает `/etc/proxima-ai/secrets` (0750 root:proxima-monitor) - не сказано (M8, H6) |
| Операции: бэкап/восстановление | частично | pg_dump age→S3 есть (`INVENTORY.md` §126); raw CAS-store `/srv/proxima-ai/data/business-signal` не бэкапится (M9); процедура восстановления боевой базы не описана (test-db-refresh - косвенная репетиция) |
| Операции: ротация секретов | отложено (PA-13 в Deferred) | пароли DB-ролей - молчание |
| Безопасность: роли, RLS, доступ агента | частично | LOGIN-пользователи, URI-файлы, pg_hba, `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC` (без него `proxima_sandbox` подключится к боевой), обход RLS владельцем/superuser (H5, C1) |
| Наблюдаемость | частично (JSON-логи) | назначение логов (journald), GlitchTip (работает на сервере, проект `webapp`) не упомянуты |
| Данные: хранение/обратимость/ретеншн | частично | обратимость сломана на артефактах (C2); ретеншн raw/версий/`collector_runs` не задан; переименование tenant (M4) |
| Тестирование | решено (AD-4, Conventions) | `.github/workflows/verify.yml` есть; где гейт для OpenHands-единиц (hook `verify-gate.sh` требует `DATABASE_URI`) - не сказано; low |
| Миграции | решено (AD-12) | но содержание 015 невозможно под гейтом (C1) |
| Планирование | решено (лестница, порядок 011-015) | - |

О чём спайн молчит полностью: **LOGIN-пользователи и их учётные данные** (безопасность) и **бэкап raw-store + dead-man алерт** (операции).

### 8. Диаграммы - PASS по синтаксису, FAIL по семантике

Все три блока отрендерены `node_modules/.bin/mmdc` 11.16.0 (`-p tools/puppeteer.ci.json`): SVG 24.7 / 34.9 / 29.6 КБ, ошибок нет.
- Граф AD-13: нет ребра WB → `tools/wb_async_report.py` → PG (CAP-6) и `collector → S3` (фикстуры); при сохранении CSV-пути граф ложен (L3).
- ERD: `business_signal_raw_artifacts` показан как evidence для staging, но его реальный родитель `business_signal_runs` отсутствует, а `collector_runs` с ним не связан; `fact_order_counts` не связан с `collector_runs` вопреки AD-3; `fact_funnel_daily` без evidence (`raw_wb_analytics_responses`/артефакты v3); `stg }o--|| fact_cabinet_daily` игнорирует версии (L2).
- Structural Seed: `WEB` внутри `docker compose`, которого для webapp нет (M7); `MON -.OnFailure.-> TIMERS` - стрелка от монитора к таймерам, тогда как OnFailure идёт от юнита к отправителю (L2).

### 9. Проза - PARTIAL

Решения, не рационализации: да, каждый AD - правило с Prevents; плейсхолдеров нет. `[ASSUMPTION]` помечены 3 (AD-2, AD-4, AD-5). Не помечены при неочевидном выборе: канон `~/proxima-ai` (`.memlog.md` сам называет это assumption, в тексте AD-10 маркера нет); `dateFrom = today-3` (в `.memlog.md` - «(assumption)»); tenant `amirova`; 05:30 МСК как момент, когда вчерашние `orders` полны; доступность bridge из rootless-зоны; «v3 за вчера» при данных, доезжающих несколько дней (`API-FACTS.md:80, :99`); лимит фикстуры 200 КБ (L7, M10).

## Детализация critical и high

### C1. Ledger-гейт против AD-3/AD-9/AD-12

Доказательство: `tools/verify_migrations.py:34` `ALLOWED_HEADS = {BEGIN, COMMIT, CREATE, GRANT, INSERT}` (нет `REVOKE`, `ALTER ROLE`); `:35-39` GRANT только `SELECT|INSERT|UPDATE|USAGE`; `:40` `CREATE ROLE proxima_[a-z_]+ NOLOGIN` - `webapp_readonly` не пройдёт; `:46-56` политики только `TO proxima_[a-z_]+`; `:22-25` `CREATE DATABASE|USER` запрещены; `:66-68` view только `WITH (security_invoker = true)`.
Что исправить: (1) переименовать роль в `proxima_webapp_readonly` и добавить ей SELECT-политики по шаблону 009; (2) в AD-9/AD-12 явно вынести за ledger и назвать артефакт: создание `proxima_test`, LOGIN-пользователи с membership, `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC`, `GRANT DELETE` janitor'у - например `infra/bootstrap/prepare-db-roles.sh` + `make db-roles`, с проверкой в `make vps`; либо расширить `verify_migrations.py` в том же PR и записать это как правило; (3) в Conventions добавить `security_invoker = true` для всех view.

### C2. Два реестра прогонов

Доказательство: `004:84-102` `business_signal_raw_artifacts.run_id … REFERENCES business_signal_runs(run_id) ON DELETE RESTRICT`; `004:33-41` статусы `RUNNING|NO_SIGNAL|BLOCKED|READY|SENT|SEND_FAILED`, `window_from/to NOT NULL`, `timezone = 'Europe/Moscow'`; `http.ts:78-90` регистрирует артефакт через `repository.recordRawArtifact` (`repository.ts:110-117`); `wb_async_report.py:409` пишет `raw_wb_analytics_responses` (payload jsonb, `task_id`, без run_id).
Что исправить: AD-3 объявить `collector_runs` единственным реестром; 011 добавляет `collector_run_id uuid REFERENCES collector_runs ON DELETE CASCADE` (nullable для legacy) в `business_signal_raw_artifacts`, `wb_analytics_report_tasks`, `fact_attempt_runs`; `RecordedHttpClient` получает `SignalRepository`-реализацию, пишущую `collector_run_id`; решить и записать, удаляются ли артефакты при delete-run (доказательство неизменяемо vs прогон обратим целиком) - сейчас AD-1 и AD-3 конфликтуют молча.

### H1. `verify_business_signal.py` против AD-4

Доказательство: `:19-26` presence-check трёх URL в `services/collector/src/business-signal/*.ts`; `:27-29` запрет `/api/v5/supplier/reportDetailByPeriod`; `:31` запрет `setInterval`/`node-cron` только там же; `docs/state/API-FACTS.md:56` «запрещены гейтом». CAP-1..8 `reportDetailByPeriod` не требуют.
Что исправить: убрать `reportDetailByPeriod` из реестра AD-4; записать, что `wb/client.ts` - единственный реестр, а `business-signal/wb-client.ts` импортирует URL из него (или верификатор в том же PR переводится на сканирование `src/**` и чтение реестра как allowlist); AD-5 - назвать реальный гейт для новых каталогов.

### H2. CAP-6 через `tools/wb_async_report.py`

Доказательство: `Makefile:65-66` `collect-wb-analytics` = `uv run … tools/wb_async_report.py --tenant-id amirova-test`; `wb_async_report.py:32` `API_ROOT`, `:35` квота 20/день, `:296` INSERT в `tenants`, `:313, :322, :409, :477` INSERT в четыре таблицы без run_id; D20 - квота разделяется с внешним потребителем.
Что исправить: либо явное исключение в AD-4/AD-13 («CSV-путь grandfathered до октября; в 011 `wb_analytics_report_tasks` получает `collector_run_id`; job `funnel-csv` оборачивает скрипт и пишет `collector_runs`»), либо перенос в `collector/src/jobs/funnel-csv.ts` через реестр. Учесть разделяемую квоту D20 (резерв ≤ N отчётов/день).

### H3. Поздние обновления строк и ключ staging

Доказательство: `API-FACTS.md:25` `orders` содержит `isCancel`, `cancelDate`; `:24` `sales` - `lastChangeDate`; `.memlog.md` «(assumption) … + ON CONFLICT по srid/saleID; пересборка версии дня». Спайн: AD-5 «upsert по ключу», Conventions «`ON CONFLICT DO NOTHING` … никаких `UPDATE` фактов» - не совместимы.
Что исправить: ключ staging = `(tenant_id, srid, last_change_date)` (или `(srid, run_id)`), view `stg_wb_orders_rows_current` = последняя `last_change_date` на `srid`; `fact_cabinet_daily` агрегирует только из `_current`; пометить `today-3` как `[ASSUMPTION]` с обоснованием и явным правилом «отмены старше N дней ловит только еженедельный прогон `--from today-30`».

### H4. Порядок и полнота

Доказательство: AD-5 - четыре таймера по OnCalendar, нет `After=`/проверки статуса; AD-6 «день полный = `calendar_day < today`»; глоссарий: «день последней частичной выгрузки - неполный»; `sales` 1/мин на страницу (`wb-client.ts:10` `STATISTICS_PAGE_INTERVAL_MS = 60_000`) - collect может не уложиться до 05:45.
Что исправить: один `proxima-morning@<tenant>.service`, выполняющий collect → funnel → norm → brief последовательно с fail-closed на первом падении (или цепочка `Requires=`/`After=`), и правило: шаг N читает только при `collector_runs.status = SUCCEEDED` шага N-1 за сегодня; «полный день» = `< today` **и** покрыт SUCCEEDED-прогоном collect; `data_status_current` считает `stale` от `now() - max(finished_at)` в момент чтения, webapp использует его, а не только `brief_daily.status`.

### H5. Роли, LOGIN, RLS-обход, tenant для webapp

Доказательство: `009:3-6` роли NOLOGIN; `INVENTORY.md` §d - compose-пользователь superuser и владелец `proxima`; `009:58-60` владелец обходит RLS; `services/webapp/src/lib/db/client.ts:42-55` - drizzle `Pool` без `set_config`; `verify_migrations.py:66-68` - `security_invoker = true` обязателен, значит RLS дойдёт до таблиц и потребует GUC у webapp.
Что исправить: AD-9 добавить LOGIN-пользователей (`proxima_<role>_login`, создаются bootstrap-скриптом, URI в `/etc/proxima-ai/secrets/<role>_uri`, 0600), запрет superuser-URI для job/webapp (проверка в `make vps`), владелец новых таблиц = `proxima_migration_owner`; AD-7/AD-11: webapp выставляет `proxima.tenant_id` из `WEBAPP_TENANT_ID` в каждой транзакции; политики SELECT для `proxima_webapp_readonly`.

### H6. Runtime таймеров на хосте

Доказательство: `INVENTORY.md` §11 «`uv` нет, `psql` на хосте нет, системный Python 3.12.3 … в `~/proxima-ai` нет `node_modules`»; `Makefile:62-63` `apply-migrations` = `uv run --python 3.14`; `infra/monitoring/proxima-host-monitor.service` `ProtectHome=true`, `ExecStart=/usr/bin/python3`; секреты `0750 root:proxima-monitor` (`prepare-business-signal-runtime.sh:38`).
Что исправить: AD-5/AD-10 назвать bootstrap для лестницы (`infra/bootstrap/prepare-ladder-runtime.sh`: uv + `uv sync --locked`, `npm ci` в каноне), пользователя юнитов (`proxima-admin`, член `proxima-monitor`), шаблон unit без `ProtectHome` либо канон вне `$HOME` (см. M1: `/srv/proxima-ai/repo` уже объявлен каноном в `vps-contract.json` и bootstrap-скриптах - проще ратифицировать его).

## Medium (кратко, что исправить)

- M1: выбрать один канон и привести `infra/vps-contract.json paths.repository` (`tools/verify_vps_contract.py:59-66`), `REPOSITORY_DIR` в `infra/bootstrap/*.sh` в согласие; пометить `[ASSUMPTION]`.
- M2: `tools/delete_run.py` удаляет child-first явным списком таблиц в одной транзакции, не полагаясь на CASCADE; зафиксировать, что attempt-семейство остаётся только для CSV-пути.
- M3: Conventions: view `WITH (security_invoker = true)`, изменение = новая view `<table>_current_v2`, старая живёт до конца наблюдения.
- M4: зафиксировать `tenant_id` (`amirova-test` как есть, либо правило миграции: новая строка + повторный seed, старые строки не переписываются).
- M5: назвать метрику `fact_order_counts` «nm-report ordersCount» и запретить сравнение с `fact_cabinet_daily.orders_count`; для SKU-грейна Statistics завести `fact_nm_daily` из `stg_wb_orders_rows`.
- M6: `make test-db-refresh` через `docker exec proxima-ai-postgres-1` (createdb при первом запуске); `[ASSUMPTION]` о доступности `172.17.0.1` из rootless-зоны + smoke-тест как приёмка M-01; `REVOKE CONNECT … FROM PUBLIC` явно.
- M7: сентябрьский overlay `infra/webapp.loopback.compose.yaml` (127.0.0.1:3000, `WEBAPP_REQUIRE_AUTH=false`, `WEBAPP_DATA_MODE=postgres`, `WEBAPP_DATA_DATABASE_URI`), с учётом построчного гейта `verify_runtime_boundary.py:62-68`.
- M8: юнит `proxima-alert@.service` (тот же `telegram_bot_token`/`telegram_chat_id`), dead-man: монитор проверяет `brief_daily` за сегодня к 06:30; назвать journald и GlitchTip.
- M9: raw-store в ночной бэкап (`s3cmd sync`) или явный пункт Deferred с датой; ретеншн: «хранить всё до 2027-03-01, затем решение».
- M10: v3 - окно 7 дней с перекрытием и версией дня по прогону (как для orders), не «за вчера».

## Что проверено

Файлы: спайн, `.memlog.md`, `_bmad-output/specs/spec-wb-morning-brief/{SPEC,glossary}.md`, `DECISIONS.md` (D8, D13, D15, D18, D20, D21), `docs/state/{MIGRATION-GAPS,API-FACTS,WEB-STATE,INVENTORY}.md`, `db/migrations/001-010`, `services/collector/src/business-signal/{http,raw-store,repository,wb-client,types}.ts`, `tools/{verify_business_signal,verify_migrations,verify_runtime_boundary,verify_vps_contract,apply_migrations,wb_async_report}.py`, `infra/{compose,webapp.compose}.yaml`, `infra/monitoring/*`, `infra/bootstrap/*.sh`, `infra/vps-contract.json`, `Makefile`, `package.json` ×3, `package-lock.json`, `services/control-plane/{pyproject.toml,uv.lock}`, `.openhands/setup.sh`, `.gitignore`, ветки `ai/pa-50` (postgres-provider), `pa41`/`PA-03-02` (010, promote-order-counts), `pmm-20` (scn001/loader.py), `pmm29-contracts` (signal.schema.json). Диаграммы отрендерены `mmdc`.
