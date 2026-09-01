# Review: «проверено, а не заявлено» - ARCHITECTURE-SPINE.md (wb-morning-brief)

**Дата:** 30.08.2026. **Режим:** read-only, мак Mike, ветка `docs/session-1-inventory` @ `bbbcf6c`, remote-ветки через `git show`/`git ls-tree`. Сервер не трогался, секреты не читались. Каждая строка = конкретный файл/команда, по которым проверялось утверждение спайна.

**Итог:** 85 строк-утверждений. Подтверждено 60, расходится 10, частично 11, не проверено 4 (плюс 4 вторичных проверки в последней таблице).

Легенда статусов: **OK** - подтверждено; **DIFF** - расходится с реальностью; **N/V** - не проверено (нужен доступ/вызов); **PART** - подтверждено частично.

---

## 1. Таблица Stack

| # | Утверждение спайна | Источник проверки | Статус | Что исправить |
|---|---|---|---|---|
| 1.1 | Node.js 22.23 (engines >=22 <23) | `package.json` engines `>=22 <23`; `node -v` = v22.23.2 (мак); `docs/state/INVENTORY.md` §11: сервер node v22.23.2 | OK | Писать `22.23.2` |
| 1.2 | TypeScript 5.8.3 | `services/collector/package.json`, `services/webapp/package.json`, `package-lock.json` | OK | - |
| 1.3 | pg 8.16.3 | collector + webapp `package.json`, lock | OK | - |
| 1.4 | ajv 8.20.0 | `services/collector/package.json`, lock | OK | - |
| 1.5 | tsx 4.20.3 | `services/collector/package.json` devDeps, lock | OK | - |
| 1.6 | Next.js 16.3.3 | `services/webapp/package.json`, lock; INVENTORY №4 (staging-контейнер 16.3.3) | OK | - |
| 1.7 | React 19.2.8 | webapp `package.json`, lock | OK | - |
| 1.8 | drizzle-orm 0.45.2 | webapp `package.json`, lock | OK | - |
| 1.9 | better-auth 1.7.1 | webapp `package.json`; lock `services/webapp/node_modules/better-auth` 1.7.1 | OK | - |
| 1.10 | vitest 4.1.11 | webapp devDeps; lock `services/webapp/node_modules/vitest` 4.1.11 | OK | - |
| 1.11 | Python 3.14 (uv 0.11.7) | `services/control-plane/pyproject.toml` `requires-python = ">=3.14,<3.15"`; `uv.lock` `requires-python = "==3.14.*"`; `uv --version` = 0.11.7 (мак) | PART | На сервере `uv` нет, системный Python 3.12.3 (INVENTORY §11). AD-5 ставит control-plane job'ы на хост-таймеры - без установки uv/3.14 на VPS `norm@`/`brief@` не запустятся. Добавить в AD-10 шаг bootstrap uv на сервере |
| 1.12 | psycopg 3.3.4 | `uv.lock` psycopg 3.3.4 | DIFF | Версия верна, но psycopg объявлен только в `[project.optional-dependencies] test`, не в runtime `dependencies`. AD-6 (`loader` через psycopg в проде) требует перенести psycopg в `dependencies` или завести extra `db` и использовать его в юнитах |
| 1.13 | pydantic 2.13.4 | `pyproject.toml` dependencies, `uv.lock` | OK (версия) | В `proxima_control_plane` pydantic не используется вовсе (`grep -rn pydantic services/control-plane/src` - только замороженное `src/proxima/evals/`). См. 6.3 |
| 1.14 | jsonschema 4.25.1 | `pyproject.toml`, `uv.lock` | OK | - |
| 1.15 | pytest 8.4.2 | `pyproject.toml` extra `test`, `uv.lock` | OK | - |
| 1.16 | PostgreSQL 16.10 (postgres:16.10-alpine) | `infra/compose.yaml` image; INVENTORY №1 контейнер `postgres:16.10-alpine` | OK | - |
| 1.17 | json-schema-to-typescript 15.0.4 | корневой `package.json` `^15.0.4`; `package-lock.json` resolved 15.0.4 | OK | Пин с caret - зафиксировать `15.0.4` без `^`, раз спайн фиксирует версию |
| 1.18 | systemd (Ubuntu 24.04) | `README.md:24` «Ubuntu 24.04 LTS»; `infra/vps-contract.json` `operating_system: ubuntu-24.04-lts` (observed 13.08) | OK | Версия systemd в docs не зафиксирована (для 24.04 это 255 по дистрибутиву); при желании - `systemctl --version` на сервере |

## 2. Артефакты кода

| # | Утверждение спайна | Источник проверки | Статус | Что исправить |
|---|---|---|---|---|
| 2.1 | `business-signal/{http,raw-store,wb-client}.ts` существуют | `ls services/collector/src/business-signal/` | OK | - |
| 2.2 | `RecordedHttpClient` - существующий клиент с записью артефактов | `http.ts:65` class; `request()` сначала `store.persist` + `repository.recordRawArtifact`, потом проверка статуса (`http.ts:78-108`) | OK | Инвариант AD-1 «артефакт до парсинга» в коде уже соблюдён |
| 2.3 | «Транспорт - интерфейс» | `http.ts`: конструктор принимает `transport: HttpTransport = fetchTransport` | OK | `FixtureTransport` - новая реализация того же интерфейса, не новая абстракция |
| 2.4 | CAS `artifact://…/sha256/<hex>` | `raw-store.ts:74-106`: sha256 тела, `objects/sha256/<2>/<hex>`, locator `artifact://business-signal/sha256/<hex>`; `db/migrations/004:96` CHECK на regex locator | OK | В спайне написано `artifact://…/sha256/` - фактический префикс `artifact://business-signal/sha256/` |
| 2.5 | 429 «обрабатывается по `X-Ratelimit-Retry`» | `http.ts:29-33` заголовок попадает в allowlist записи; `http.ts:104-106` 429 -> throw `WB_RATE_LIMITED`, ретрая нет; `wb-client.ts:10-12` фиксированные паузы 60/20/60 с | DIFF | Это новое поведение, не существующее. В коде - тот самый «ручной sleep», который AD-4 запрещает. Пометить как «реализовать в `wb/client.ts`» |
| 2.6 | Таблица `business_signal_raw_artifacts` | `004:84-104` (+ `response_headers` в `006`) - `run_id`, `http_status`, `content_sha256`, `object_locator`, `manifest_sha256` | OK | - |
| 2.7 | Таблица `raw_wb_analytics_responses` | `003:68-85`: `content_sha256`, payload `body_base64`, FK `task_id` | OK | Ключ - `task_id`, не `run_id`; при миграции 011 (run_id additively) это одна из таблиц |
| 2.8 | `fact_order_counts` (есть), грейн nmId | `007:49-64`: `attempt_id, tenant_id, nm_id, calendar_day, order_count`, UNIQUE по `(attempt_id, tenant_id, nm_id, calendar_day)` | OK | - |
| 2.9 | `fact_attempt_runs` (существующие `attempt_id`-таблицы) | `007:3` | OK | - |
| 2.10 | `stg_wb_nm_report_rows` (есть) | `005:3` | OK | - |
| 2.11 | `tenants`, `dim_client_passport` | `002:3`, `010:2` | OK | - |
| 2.12 | Роли «по образцу 009»: спайн перечисляет `proxima_source_publisher`, `proxima_norm_publisher`, `webapp_readonly`, `proxima_run_janitor`, `proxima_sandbox` | `009:3-6`: реально есть **только** `proxima_migration_owner`, `proxima_source_publisher`, `proxima_release_publisher`, `proxima_data_health_read` | DIFF | В AD-9 явно разделить: существующие (4) и новые (015). `proxima_release_publisher` и `proxima_data_health_read` в спайне не упомянуты - решить, что с ними (они держат UPDATE на `domain_release_pointers`) |
| 2.13 | `tools/verify_business_signal.py` - «allowlist эндпоинтов» | Файл, 73 строки. Правила дословно: `required_endpoints = (statistics .../supplier/sales, analytics .../stocks-report/wb-warehouses, finance .../sales-reports/detailed)` - должны присутствовать; `for forbidden in ("/api/v1/supplier/stocks", "/api/v5/supplier/reportDetailByPeriod")` -> «deprecated endpoint entered signal runtime»; `"setInterval" in source or "node-cron" in source` -> «must remain a manual one-shot»; `source` = только `services/collector/src/business-signal/*.ts` (строки 11-12) | DIFF | (а) Это не allowlist, а required+forbidden списки. (б) Сканируется только `business-signal/`; новый `services/collector/src/wb/client.ts` гейт не увидит - AD-4 «добавляется в allowlist» невыполнимо без переписывания гейта. (в) **`reportDetailByPeriod` прямо запрещён** гейтом, а AD-4 вносит его в реестр с бюджетом 1/мин - либо убрать из реестра (в лестнице M-01..M-05 он не нужен), либо менять гейт с отдельным решением |
| 2.14 | AD-5: `setInterval`/`node-cron` «запрещены `verify_business_signal.py`» | `verify_business_signal.py:33` - проверка только по `business-signal/*.ts` | PART | Для `jobs/` и `wb/` запрет не действует. Расширить гейт на `services/collector/src/**` |
| 2.15 | `infra/monitoring/proxima-host-monitor.timer` - образец для таймеров | Файл: `OnBootSec=2min`, `OnUnitActiveSec=1min`, `Persistent=true`, `Unit=proxima-host-monitor.service`; `OnCalendar` **нет** | PART | Образец монотонный, а спайн нужен календарный. `Persistent=true` есть (для монотонного таймера он no-op). Написать `OnCalendar=*-*-* 05:30:00 Europe/Moscow` явно, не полагаться на TZ хоста |
| 2.16 | `OnFailure=` алерт «в существующий Telegram-канал монитора» | `proxima-host-monitor.service` - `OnFailure` нет; `host_monitor.py:310` `send_telegram()` с `PROXIMA_TELEGRAM_TOKEN_FILE`/`CHAT_ID_FILE`; `monitor.env.example:5-6` | PART | Канал есть, точки входа «отправь произвольное сообщение» нет - `host_monitor.py` шлёт только свои события. Нужен новый юнит `proxima-alert@.service` (или CLI-флаг у монитора) - добавить в Structural Seed |
| 2.17 | `infra/compose.yaml`: Postgres 16, базы `proxima` и `proxima_test` | `POSTGRES_DB: proxima`; второй базы в compose нет | DIFF | `proxima_test` создаётся миграцией/скриптом, не compose. Указать, кто создаёт (initdb-скрипт в `docker-entrypoint-initdb.d` или `make test-db-refresh` с `createdb`) |
| 2.18 | bridge `172.17.0.1:5432` из compose | `infra/compose.yaml:19` `"172.17.0.1:5432:5432"`; INVENTORY §4.6: на хосте **не развёрнуто** (`/srv` compose без строки, `ss` только 127.0.0.1) | PART | В main есть, на сервере нет (D8 не реализован). Первый релиз M-01 должен это доставить - отметить в AD-10 |
| 2.19 | AD-10 `docker compose up -d` (postgres, webapp) | `compose.yaml` содержит только `postgres`; webapp - в overlay `infra/webapp.compose.yaml` с `WEBAPP_REQUIRE_AUTH: "true"` + Caddy :80/:443; INVENTORY №4: staging webapp запущен `docker run` без compose | DIFF | Overlay противоречит «Auth выключена до октября» и «только tcp/22». Нужен либо третий compose-файл для loopback-webapp без Caddy, либо явное решение оставить `docker run`. Спайн это не описывает |
| 2.20 | compose монтирует `../db/migrations` в initdb | `compose.yaml:15` | OK | Initdb срабатывает только на пустом volume; дальнейшие миграции - `make apply-migrations` (2.21) |
| 2.21 | `tools/apply_migrations.py`, `make apply-migrations` (ledger self-checksum) | Файл есть; `LEDGER_PATTERN` regex по `VALUES (N, 'name', '<sha256>')`; `Makefile:62-63` через `uv run … --extra test` | OK | Запуск требует extra `test` из-за psycopg (см. 1.12) |
| 2.22 | `services/webapp/src/lib/data/` на `origin/ai/pa-50` | `git ls-tree`: `fixtures-provider.ts, index.ts, postgres-provider.ts, provider.ts, types.ts`; `postgres-provider.ts` - заглушка, `getBrief()` -> `Promise.reject(NOT_IMPLEMENTED)`; `DATA_MODE_ENV = "WEBAPP_DATA_MODE"`; `BriefData` в `types.ts:89` | OK | В таблице Design Paradigm колонка «Где (существующий код)» указывает `postgres-provider.ts`, которого на main нет - пометить «(pa-50, заглушка)» |
| 2.23 | На main webapp читает фикстуры | `services/webapp/src/app/(app)/brief/page.tsx:6` `import { getBrief } from "@/lib/fixtures/brief"`; `src/lib/data` на main отсутствует | OK | - |
| 2.24 | `detectors/scn001/` на ветке `pmm-20-…` | `git ls-tree`: `__init__, baseline, clock, config, decomposition, loader, metrics, signal, smoke` | OK | - |
| 2.25 | scn001: «окна 7/14/28 со средним» | `config.py:12` `windows = (7, 14, 28)`, `trigger_window = 28`; `baseline.py:38` `moving_average` (среднее), `WEEKDAY_WINDOW_DAYS = 28` | OK | - |
| 2.26 | scn001 подключается «через адаптер loader.py -> fact_*_current» | `loader.py:44` `DbExecutor` Protocol (psycopg лениво), реестр колонок «DailyMetrics -> WB report column в payload jsonb» | OK | Адаптер реально нужен: loader читает jsonb-payload, а не плоские колонки `fact_cabinet_daily` |
| 2.27 | `contracts/` на `pmm29-contracts`: `signal`, `diagnosis`, `decision-record` | `git ls-tree`: + `acquisition-attempt`, `domain-release`, `source-artifact`, `examples/*` (9 synthetic) | OK | На main - `acquisition-attempt, client-passport, domain-release, source-artifact, supply-plan`; `signal/diagnosis/decision-record` только в ветке - как и заявлено |
| 2.28 | Миграции: «main занял 010; ветки pa41 (`010_phase3_promotion_privileges`) и PA-03-02» | main `010_client_passport_supply_plan.sql`; `git ls-tree` pa41 -> `010_phase3_promotion_privileges.sql`; PA-03-02 -> `010_promotion_attempt_completion.sql`; PA-03-01 заканчивается на 009 | OK | Назвать файл PA-03-02 явно: `010_promotion_attempt_completion.sql` |
| 2.29 | Фикстуры: `services/collector/tests/fixtures/wb-api/<api>/<endpoint>/*.json` коммитятся | `services/collector/tests/fixtures/` есть, содержит только `blocked-run-child.ts`; `.gitignore:19` `fixtures/wb-api/`; `DECISIONS.md` D15: «малые обезличенные фикстуры (< 1 МБ) для автотестов - решение в Сессии 3» | PART | Путь новый, не gitignored - ок. Но это закрытие открытого пункта D15, а не только «спека №2» - записать как решение в DECISIONS, иначе останется ASSUMPTION |
| 2.30 | Полные фикстуры на VPS `~/signal-inputs/fixtures/wb-api/` + S3 | D15; API-FACTS §1 (40 файлов, 436 МБ) | OK | - |
| 2.31 | `tools/wb_async_report.py` (CSV weekly) | Файл: `API_ROOT = …/api/v2/nm-report/downloads`, `REPORT_TYPE = DETAIL_HISTORY_REPORT`, `DAILY_REPORT_QUOTA = 20`, `MOSCOW = ZoneInfo("Europe/Moscow")` | OK | - |
| 2.32 | Тесты: collector `node:test` + `tsx`, webapp `vitest`, control-plane `pytest` | collector `package.json` `"test": "tsx --test tests/**/*.test.ts …"`; webapp `"test": "vitest run"`; pyproject extra `test` | OK | - |
| 2.33 | `WEBAPP_REQUIRE_AUTH=false` до октября | `src/app/(app)/layout.tsx:18` проверяет env; INVENTORY №4 staging-контейнер `WEBAPP_REQUIRE_AUTH=false` | OK | - |
| 2.34 | AD-10: чекауты `~/proxima-ai`, `/srv/proxima-ai/repo`, `~/proxima-webapp-staging` | INVENTORY №13-15, §4.4 «пять копий кода» | OK | В `~/proxima-ai` нет `node_modules`/`.venv`/`uv` (INVENTORY №13) - см. 1.11 |
| 2.35 | AD-9: age-шифрованный дамп в бэкапе; пустые `proxima_dev` (хост и зона) | INVENTORY №11 (`age -> S3 proxima-backups`, дампы `proxima` 64K и `proxima_dev` 4K); §4.1 две пустые `proxima_dev` | OK | - |
| 2.36 | AD-5: «`sudo` у деплоя есть» | INVENTORY §Метод: всё под `sudo` от `proxima-admin` | OK | - |
| 2.37 | Structural Seed: VPS только tcp/22; webapp :3000 loopback | `infra/vps-contract.json` `inbound_allow: [tcp/22]`; INVENTORY §ss `127.0.0.1:3000` | OK | - |
| 2.38 | `WB_*_TOKEN_FILE` как паттерн переменных | INVENTORY §4.7(c): `.env` ссылается на `WB_PRICES_TOKEN_FILE`, `WB_PROMOTION_TOKEN_FILE`; CLI-опции `statistics-token-file` и т.д. (`verify_business_signal.py:30`) | OK | - |

## 3. WB API (AD-4 / AD-5) против `docs/state/API-FACTS.md`

| # | Утверждение спайна | Источник проверки | Статус | Что исправить |
|---|---|---|---|---|
| 3.1 | `sales` 1/мин | API-FACTS TL;DR + таблица B/C: `x-ratelimit-limit: 1`, 429 через 32 с, `x-ratelimit-retry: 29` | OK | - |
| 3.2 | `orders` 10/мин | API-FACTS: «limit 10, remaining 9» (заголовки) | OK | Единица «в минуту» - из заголовка `x-ratelimit-limit`, окно сброса на 200-ответах не приходит (API-FACTS §Ошибки) |
| 3.3 | `reportDetailByPeriod` 1/мин | API-FACTS: «limit 1, remaining 0» | OK (лимит) | Но эндпоинт запрещён гейтом - см. 2.13. В лестнице M-01..M-05 он не используется; убрать из реестра AD-4 или вынести в Deferred |
| 3.4 | `sales-funnel/v3` 3/мин | API-FACTS §Воронка v3: заголовки `limit 3`; спека 3/мин, интервал 20 с, всплеск 3 | OK | - |
| 3.5 | `nm-report/downloads` 3/мин | API-FACTS: «limit 3, remaining 2» на GET списка; единица времени в заголовке не указана | PART | Для POST create лимит не наблюдался (не вызывался). Оставить «3 по заголовку, окно не подтверждено» |
| 3.6 | 429 по `X-Ratelimit-Retry` | API-FACTS §Ошибки: `x-ratelimit-retry: 29`, `x-ratelimit-reset: 29`; `Retry-After` «не встречался ни разу» | OK | - |
| 3.7 | AD-5: ежедневный `collect` с `dateFrom = today-3, flag=0` - т.е. flag=0 отдаёт строки, изменённые с `dateFrom` по `lastChangeDate` | API-FACTS проверял flag=0 **только** с `dateFrom=2023-01-01` (окно 6 мес). Строка 42: «`flag=0` фильтрует по дате продажи/заказа, не только по `lastChangeDate` - продажи 28.02 с `lastChangeDate` до 14.03 в выборке отсутствуют». Существующий `wb-client.ts:150` курсор по `lastChangeDate` - из документации WB, не из наблюдения | **N/V (критично)** | Проверить 2 вызовами с сервера (read-only, statistics-токен): `sales?dateFrom=<today-3>&flag=0` и `orders?dateFrom=<today-3>&flag=0`; сравнить `min(date)` и `min(lastChangeDate)`. Вопрос: попадёт ли заказ 10-дневной давности, отменённый сегодня (`isCancel`, `cancelDate`), в окно `today-3`? От ответа зависит корректность `cancelled_count`/`returns_count` в AD-2 и размер окна (3 дня может быть мало) |
| 3.8 | Окно WB ~6 мес, «март выпадает по одному дню в сутки» | API-FACTS: flag=1 `02-28` данные, `02-21` и `02-15` пусто; «точный алгоритм WB не подтверждён»; ряд с `2026-03-01` | OK | Граница бисекцией не найдена (429 остановил). Бэкфилл `--from 2026-03-01` актуален на 30.08; к первому деплою в сентябре начало марта уже выпадет - спайн это учитывает |
| 3.9 | Потолок 80k строк на страницу | Спайн явно не заявляет. API-FACTS: «потолок 80k не достигнут» (10.6k / 13.3k строк за 6 мес); `wb-client.ts:6` `SALES_PAGE_LIMIT = 80_000` - из документации | N/V | Не критично: при 26 неделях ряд кабинета в 6 раз меньше потолка. Если в реестр AD-4 добавляется пагинация - пометить «80k по документации, не наблюдалось» |
| 3.10 | v3 `sales-funnel` - окно 7 дней, «за вчера» ежедневно | API-FACTS §Воронка v3: `start = today-6` -> 200, 7 записей; `23.02..01.03` -> 400 `invalid start day: excess limit on days`; граница `today-7` не бисектирована | OK | Для «за вчера» достаточно `today-1`; запас 7 дней ловит «малую часть данных в течение нескольких дней» |
| 3.11 | 201 nmId = 11 вызовов по 20 nmId, 4 мин при 3/мин | API-FACTS §Воронка v3 п.2 | OK | - |
| 3.12 | async CSV `nm-report/downloads` раз в неделю | API-FACTS: GET списка 200 (2 отчёта SUCCESS, окна по 6 дней, создаёт внешний потребитель); строка 34: `POST …/downloads`, `GET …/file/{id}`, глубина `startDate` - **не проверено**; оговорка «только с подпиской Джем» | N/V | Не проверено: создание отчёта нашим кодом, 7-дневное окно (наблюдались только 6-дневные), глубина `startDate` для бэкфилла. Нужно 3 вызова (create + status + file) по разрешению Mike, как предлагает API-FACTS §Воронка п.1 |
| 3.13 | Квота async-отчётов 20/день | `tools/wb_async_report.py:35` `DAILY_REPORT_QUOTA = 20` - константа кода, не заголовок API | PART | В API-FACTS помечено «по коду репо». Оставить как есть с пометкой |

## 4. systemd и TZ хоста

| # | Утверждение спайна | Источник проверки | Статус | Что исправить |
|---|---|---|---|---|
| 4.1 | `Persistent=true` - реальная возможность | `systemd.timer(5)`: есть с v212; в репо уже используется `proxima-host-monitor.timer:5` | OK | Работает только для `OnCalendar`-таймеров; в монотонном мониторе - no-op. В спайне применение корректное |
| 4.2 | `OnFailure=` | `systemd.unit(5)` - директива `[Unit]` любого юнита; Ubuntu 24.04 (systemd 255) поддерживает | OK | Ставить на `.service`, не на `.timer` (таймер «падает» практически никогда). Форма: `OnFailure=proxima-alert@%n.service` |
| 4.3 | Шаблонные юниты `name@.service` / `name@.timer` | `systemd.unit(5)` §Specifiers, `%i`; `proxima-collect@.timer` активирует `proxima-collect@amirova.service` с тем же instance | OK | - |
| 4.4 | Расписание «в МСК» 05:30/05:45/06:00/06:10 | Хост-TZ нигде не зафиксирован (см. 4.5) | PART | Писать TZ прямо в `OnCalendar=*-*-* 05:30:00 Europe/Moscow` (поддерживается с systemd 229) - тогда TZ хоста не важен |
| 4.5 | TZ хоста | `grep -i timedatectl docs/state/*` - пусто. INVENTORY/WORKS-TODAY цитируют journal и `state.json` в UTC; cron-бэкап «03:00» без TZ. **Противоречие в docs:** API-FACTS:45 «~00:51 МСК» vs WORKS-TODAY NW-2 «~00:51 UTC» об одном и том же событии | **N/V** | Нужен `timedatectl` на сервере (read-only). Пока - явный TZ в `OnCalendar` (4.4) и `TZ=Europe/Moscow` в `[Service] Environment=` |

## 5. Postgres: CASCADE, RLS, DELETE

| # | Утверждение спайна | Источник проверки | Статус | Что исправить |
|---|---|---|---|---|
| 5.1 | `ON DELETE CASCADE` совместим с RLS/ролями 009 | PostgreSQL docs (Row Security Policies): «referential integrity checks … always bypass row security»; каскад выполняется RI-триггером с правами владельца таблицы-потомка. `009:55-57` комментарий: владелец таблиц обходит RLS, `FORCE ROW LEVEL SECURITY` нигде нет | OK (совместимо) | Три оговорки: (а) если на `collector_runs` включён RLS (AD-11 «каждая новая таблица»), `proxima_run_janitor` без своей политики удалит 0 строк молча - нужна `CREATE POLICY … FOR DELETE TO proxima_run_janitor` или `set_config` в `delete_run.py`; (б) `--dry-run` считает счётчики под той же ролью - те же политики; (в) см. 5.3 |
| 5.2 | «`proxima_run_janitor` - единственная роль с DELETE»; в 009 DELETE никому не выдан? | `grep -n DELETE db/migrations/009*` - только `ON DELETE RESTRICT` в тексте политик нет; GRANT'ы 009:8-44 - `SELECT, INSERT`, `UPDATE` (на `schema_migrations`, `domain_release_pointers`); **DELETE не гранчен никому** | OK | Владелец таблиц (роль из `/run/secrets/postgres_user`, под которой идут миграции) имеет DELETE implicitly и обходит RLS - зафиксировать в AD-3 как известное исключение или использовать `FORCE ROW LEVEL SECURITY` |
| 5.3 | AD-3: существующие `attempt_id`-таблицы получают `run_id` additively с CASCADE | Все 30 FK в 002-010 - `ON DELETE RESTRICT`; `release_promoted_facts -> fact_attempt_runs` RESTRICT (`008:33`), `fact_order_counts -> fact_attempt_runs` RESTRICT (`007:51`) | DIFF | Если `fact_order_counts.run_id` станет CASCADE, а факт уже промоутирован (`release_promoted_facts`), `delete-run` упадёт на RESTRICT. Определить правило: промоутированный прогон не удаляется (fail-closed) или каскад доходит до release-таблиц. Спайн молчит |
| 5.4 | AD-11: политика `USING (tenant_id = current_setting('proxima.tenant_id', true))` «по образцу 009» | `009:62-121`: `FOR ALL TO <роль> USING (...) WITH CHECK (...)`; для `raw_wb_analytics_responses`/`stg_wb_nm_report_rows` - `FOR SELECT` через `EXISTS` по `task_id` | PART | Дописать в AD-11 `WITH CHECK` (иначе INSERT в чужой tenant проходит) и адресацию `TO <роль>` - в 009 политики ролевые, не глобальные |
| 5.5 | AD-7: `webapp_readonly` - «SELECT только на view `brief_current`, `data_status_current`» | Существующие view 008 объявлены `WITH (security_invoker = true)`; при RLS на `brief_daily` и неустановленном `proxima.tenant_id` `current_setting(..., true)` = NULL -> 0 строк | DIFF (дизайн) | Либо webapp делает `set_config('proxima.tenant_id', …)` перед двумя запросами (тогда «ровно два запроса» = три), либо view без `security_invoker` + политика `FOR SELECT TO webapp_readonly`. Выбрать и записать |
| 5.6 | «`UPDATE` фактов нет, кроме `status`/`finished_at` у runs» | 009: UPDATE только на `schema_migrations` и `domain_release_pointers` | OK | `domain_release_pointers` - не факт, конвенция не нарушена; упомянуть как существующее исключение |

## 6. Codegen и контракты

| # | Утверждение спайна | Источник проверки | Статус | Что исправить |
|---|---|---|---|---|
| 6.1 | `make codegen` (`json-schema-to-typescript`) | `Makefile:10-11` -> `npm run codegen:contracts` -> `tools/generate_contract_types.mjs` (`import { compile } from "json-schema-to-typescript"`) | OK | - |
| 6.2 | TS-типы webapp из codegen, ручные `types.ts` удаляются | `generate_contract_types.mjs:8` `OUT_DIR = services/collector/src/contracts` - **только collector**; webapp-выход отсутствует | DIFF | Добавить второй `OUT_DIR` (`services/webapp/src/contracts/`) или общий workspace-пакет; иначе AD-8 для webapp невыполним и `types.ts` из pa-50 останется |
| 6.3 | Python: «pydantic-модели, валидируемые `jsonschema` против той же схемы (образец - `diagnosis/validator.py`)» | `validator.py:9-20`: только `jsonschema.Draft202012Validator`; схема читается из **пакета** `proxima_control_plane/diagnosis/schema/diagnosis.draft.v1.json`, не из `contracts/`; `models.py:13` `DiagnosisInput` - `@dataclass(frozen=True)`, не pydantic; pydantic в `proxima_control_plane` не импортируется нигде | DIFF | Образец даёт только jsonschema-часть. Для «той же схемы» нужен механизм доставки `contracts/*.schema.json` в Python-пакет (package-data копия с проверкой sha в `make contracts`, либо чтение по пути от корня репо). Pydantic - новая практика, не образец; либо убрать из AD-8, либо описать генерацию (`datamodel-code-generator`?) - иначе дрейф, который AD-8 запрещает, возникает между pydantic-моделью и схемой |
| 6.4 | `jsonschema`/`pydantic` объявлены в pyproject | `pyproject.toml` `dependencies = ["pydantic==2.13.4", "jsonschema==4.25.1"]` | OK | - |
| 6.5 | `contracts/diagnosis.schema.json` существует (для `diagnosis/`) | На main нет; есть только на `pmm29-contracts`; control-plane держит свою копию `diagnosis.draft.v1.json` | PART | После принятия pmm29 - сверить копию в пакете с `contracts/diagnosis.schema.json` (sha256) и оставить один источник |

---

## Сводка расхождений по важности

1. **[3.7] `flag=0` с коротким `dateFrom` не проверен** - вся дневная инкрементальная сборка AD-5 и `cancelled_count`/`returns_count` в AD-2 стоят на непроверенной семантике. 2 read-вызова с сервера.
2. **[2.13 / 3.3] `reportDetailByPeriod` запрещён гейтом**, а спайн вносит его в реестр; сам гейт сканирует только `business-signal/` и не является allowlist'ом - «добавить в allowlist одним PR» невыполнимо без переписывания `verify_business_signal.py`.
3. **[6.2 / 6.3] AD-8 не покрыт инструментами:** codegen пишет только в collector; Python-образец - jsonschema без pydantic, схема в копии внутри пакета.
4. **[5.3 / 5.5] Postgres-дизайн:** CASCADE упрётся в существующие RESTRICT на промоутированных фактах; `webapp_readonly` через `security_invoker`-view без `set_config` увидит 0 строк.
5. **[2.19] Webapp не в `compose.yaml`**, overlay включает auth и Caddy - AD-10 «compose up (postgres, webapp)» не соответствует ни одному файлу.
6. **[1.11 / 1.12] Control-plane на хост-таймерах:** на сервере нет uv/3.14, psycopg только в extra `test`.
7. **[2.12] Роли:** 4 из 5 перечисленных в AD-9 не существуют; 2 существующие не упомянуты.
8. **[4.5] TZ хоста не зафиксирован**, docs противоречат друг другу (МСК vs UTC для одного события). Явный TZ в `OnCalendar` снимает риск без похода на сервер.
9. **[2.16] `OnFailure` -> Telegram:** канала-приёмника произвольных сообщений нет, нужен новый юнит.
10. **[3.12] async CSV:** create/status/file и глубина `startDate` не вызывались; 7-дневные окна не наблюдались.

## Не проверено (нужен сервер или живой API, всё read-only)

| Что | Команда / вызов | Зачем |
|---|---|---|
| `flag=0` + `dateFrom=today-3` (3.7) | 2 GET с сервера statistics-токеном, ответы в фикстуры | Семантика инкремента AD-5, окно 3 дня |
| TZ хоста (4.5) | `ssh proxima timedatectl` | Расписание в МСК |
| async CSV create/status/file + глубина `startDate` (3.12) | 3 вызова analytics-токеном (POST = запись в WB, нужно разрешение Mike) | CAP-6 weekly, бэкфилл воронки |
| Лимит POST `nm-report/downloads` (3.5) | заголовки того же вызова | Бюджет в реестре AD-4 |
| Потолок 80k (3.9) | не нужен для одного кабинета | - |
| Версия systemd (1.18) | `systemctl --version` | Только для протокола |
| Наличие uv/Python 3.14 на сервере (1.11) | INVENTORY §11 уже говорит «нет» | Bootstrap-шаг в AD-10 |
| Граница окна WB (день, не неделя) (3.8) | бисекция `flag=1` по дням, 1/мин | Точная дата старта бэкфилла |
