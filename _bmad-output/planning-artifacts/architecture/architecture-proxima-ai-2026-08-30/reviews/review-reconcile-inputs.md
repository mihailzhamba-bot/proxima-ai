# Сверка входов против ARCHITECTURE-SPINE - wb-morning-brief

- Дата: 2026-08-30. Режим: read-only, claim-by-claim.
- Спайн: `ARCHITECTURE-SPINE.md` (13 AD, updated 2026-08-30T17:42).
- Входы: `_bmad-output/specs/spec-wb-morning-brief/SPEC.md` + `glossary.md`, `DECISIONS.md` (D1-D21), `docs/state/API-FACTS.md`, `docs/state/WEB-STATE.md` §4/§8, `docs/state/MIGRATION-GAPS.md` §4, `docs/state/INVENTORY.md` §4.
- Дополнительно сверено с кодом (main + origin-ветки): `.gitignore`, `infra/compose.yaml`, `infra/webapp.compose.yaml`, `infra/monitoring/*`, `tools/verify_business_signal.py`, `Makefile`, `db/migrations/007,009,010`, `services/collector/src/business-signal/{http,wb-client}.ts`, `tools/wb_async_report.py`, ветки `pa41-full-w2-phase3`, `pmm-20-scn-001`, `pmm29-contracts`, `ai/pa-50`, lock-файлы версий.

## Вердикт

**Покрытие неполное: 3 искажения высокой важности, 6 пропусков/искажений средней, 8 низких.** Все 8 CAP имеют место и AD. Все 7 пунктов промта (а-ж) приземлились, но три из них (д, е, ж) - с внутренними противоречиями или без ответа на красный флаг INVENTORY. Лимиты API совпадают по числам. Версии стека совпадают с lock-файлами.

## Пропуски и искажения по убыванию важности

| # | Важность | Тип | Суть | Где чинить |
|---|---|---|---|---|
| 1 | высокая | искажение | Conventions «Записи»: `ON CONFLICT DO NOTHING` по естественному ключу + «никаких UPDATE фактов»; AD-5: «upsert по ключу». API-FACTS: отмены/возвраты доезжают тем же `srid`/`saleID` с новым `lastChangeDate` до 2 недель (продажи 28.02 с `lastChangeDate` до 14.03). При DO NOTHING на `srid` вторая версия строки (isCancel=true) отбрасывается - `cancelled_count` и `orders_count` (метрика тревоги CAP-1) замирают на первом виде строки | AD-3 + Conventions: ключ staging = `(srid, lastChangeDate)` или `(run_id, srid)`, `stg_*_current` по max(lastChangeDate); убрать «upsert» из AD-5 |
| 2 | высокая | пропуск | INVENTORY §4.11: на хосте нет `uv`, нет `psql`, системный Python 3.12, в `~/proxima-ai` нет `node_modules`; `proxima-host-monitor.service` бежит на `/usr/bin/python3`. AD-5 запускает `collector` и `control-plane` как one-shot на хосте, AD-9 делает `pg_dump proxima \| psql proxima_test` - ни одного слова, чем и откуда это исполняется (uv на хосте? venv? `docker exec` в postgres-контейнер, как делает `proxima-pg-backup.sh`?) | Новый AD или строка в «Среды и деплой»: runtime хоста (uv + node в `~/proxima-ai`, `test-db-refresh` через `docker exec proxima-ai-postgres-1`) |
| 3 | высокая | искажение | AD-4 реестр включает `reportDetailByPeriod` 1/мин. `tools/verify_business_signal.py:27-29` запрещает `/api/v5/supplier/reportDetailByPeriod` в runtime («deprecated endpoint entered signal runtime»). Ни один CAP его не требует (D13 отклонил вариант C «норма по финотчётам») | Убрать из реестра AD-4 или явно записать изменение гейта |
| 4 | средняя | пропуск | Средство деплоя webapp в сентябре не существует: `infra/compose.yaml` = только `postgres`; `infra/webapp.compose.yaml` жёстко `WEBAPP_REQUIRE_AUTH: "true"` + `caddy` + обязательный `WEBAPP_DOMAIN`. AD-10 «`docker compose up -d` (postgres, webapp)» неисполним; Deferred откладывает `webapp.compose.yaml` на октябрь, а D19 требует «staging пересобирать из main через `infra/webapp.compose.yaml`» | AD-10: назвать compose-фрагмент/override для сентября (auth=false, `127.0.0.1:3000`, `WEBAPP_DATA_MODE`, `WEBAPP_DATA_DATABASE_URI`) и снять конфликт с D19 |
| 5 | средняя | искажение | AD-9 «Prevents: OpenHands с доступом к данным кабинета» противоречит собственному правилу: `proxima_test` = полный дамп боевой, `proxima_sandbox` её читает. D8 так и задуман; D5b: «чужие данные на сервере с LLM-агентом без причины не нужны» | Переписать prevents честно (Амирова - кабинет Mike) или добавить обезличивание в `test-db-refresh` |
| 6 | средняя | пропуск | Conventions «Ошибки»: частичный результат остаётся под своим `run_id` до удаления; AD-2 view `_current` = «последняя версия дня». Упавший прогон становится «текущим» для нормы (06:00) и сводки (06:10) | AD-2: `_current` фильтрует `collector_runs.status = 'ok'` |
| 7 | средняя | искажение | CAP-6 / API-FACTS §Воронка v3 п.2: снимать окно 7 дней ежедневно (данные «в течение нескольких дней»), 11 вызовов/день; AD-5: `funnel@amirova` «v3 за вчера» - теряет поздние заказы/выкупы. D20: дневная квота async-отчётов разделяемая (внешний потребитель ~00:51 МСК) «учесть в M-01» - в AD-4/AD-5 нет; `wb_async_report.py` считает только свои задачи (`DAILY_REPORT_QUOTA = 20`) | AD-5: v3 = окно `today-7..yesterday`, версии по AD-2; AD-4: бюджет `downloads` с поправкой на внешний отчёт |
| 8 | средняя | искажение | pa41 `facts/promote-order-counts.ts` читает `stg_wb_nm_report_rows` (CSV-воронка, `payload.ordersCount`, `row_date`), не Statistics `orders`. Спайн кладёт его в `facts/` рядом с `cabinet-daily.ts`, в erDiagram `fact_order_counts` без источника, CAP-7 «SKU-грейн на `fact_order_counts`». Получаются два определения «заказы»: WB Analytics (nmId) и Statistics (кабинет) без правила сверки. Спека/D14 зовут pa41 «писатель дневного ряда» - по факту это nmId-ряд из CSV, место в CAP-6 | AD-2 или Capability map: `fact_order_counts` ← `stg_wb_nm_report_rows` (CSV), канон сводки = `fact_cabinet_daily`; pa41 → CAP-6 |
| 9 | средняя | пропуск | CAP-3 «>24 ч без сбора → предупреждение вместо цифр»: число 24 ч в AD-7/`data_status_current` не записано. `brief_daily.status` пишется в 06:10; если `brief@` упал, webapp читает вчерашний `brief_current` со `status=ok`. Правило «stale вычисляется на чтении из `data_status_current`, не из `brief_daily.status`» отсутствует | AD-7: `stale = now() - collected_at > 24h` в view; webapp сравнивает `brief_current.brief_day` с `data_status_current` |
| 10 | низкая-средняя | пропуск | Окно нормы: входит ли «вчера» в 14 дней `norm_daily(evaluation_day)`? CAP-4 «для 29.08 = 34.5» на фикстурах 30.08 (данные до 30.08 07:01 UTC). Глоссарий: термин с двумя значениями = дефект. «Полный день»: глоссарий исключает «день последней частичной выгрузки», спайн - `calendar_day < today(МСК)`; при упавшем сборе вчерашний день без строки (0 или пропуск?) - не сказано | AD-6: `window = [evaluation_day-14, evaluation_day-1]` (или включительно) + «день полный = есть ok-прогон с `finished_at > день+1 00:00 МСК`» |
| 11 | низкая | пропуск | Спека: заморожен `services/control-plane/src/proxima/` (verbatim-дерево существует); спайн - только «`business-signal/` не трогать до M-04» | Conventions «Auth/заморозки» |
| 12 | низкая | искажение | AD-12: «ветки pa41 и PA-03-02 при мерже перенумеровываются» - D14 и MIGRATION-GAPS §4: выбрать одну (pa41 новее на 2 дня, то же ядро) | AD-12: только pa41 |
| 13 | низкая | пропуск | AD-11: токены второго tenant в `/etc/proxima-ai/secrets/<tenant>_*`; существующие - `wb_{statistics,analytics,finance}_token` + `.env` `WB_*_TOKEN_FILE` (INVENTORY 7b: два разных analytics-токена в `/etc` и `~/signal-inputs`). Правило «файл ↔ tenant» (через `dim_client_passport`?) не задано | Conventions «Конфигурация и секреты» |
| 14 | низкая | пропуск | WEB-STATE §8: контейнеру нужен `WEBAPP_DATA_DATABASE_URI`; `UnreleasedBanner` → `dataMode="staging"`; loader заменяет `getBrief` при `hasDataDb()`. AD-7 называет только `WEBAPP_DATA_MODE` | AD-7 |
| 15 | низкая | пропуск | Спека: `WORKS-TODAY.md` прогоняется целиком перед каждым релизом. Conventions упоминают файл, деплой-последовательность AD-10 шага не содержит; `systemctl restart` есть, `install/enable` новых юнитов - нет | AD-10 |
| 16 | низкая | искажение | Спека: «каждый новый ответ при первом прогоне сохраняется как фикстура»; AD-4 - ручной `record-fixture`. Процедура обезличивания малых фикстур (nmId, бренды, артикулы реальные) не определена | AD-4 |
| 17 | низкая | пропуск | «WB только READ, запись в WB никогда» (спека, non-goals) - явного правила в спайне нет; реестр + allowlist подразумевают | Conventions |
| 18 | низкая | замечание | `OnFailure=` алерт «в существующий Telegram-канал монитора»: у `proxima-host-monitor` нет OnFailure-юнита, только `send_telegram()` внутри `host_monitor.py`. Нужен новый `proxima-alert@.service` - как артефакт не назван | Structural Seed `infra/systemd/` |

Не пропуски (процесс, не архитектура): дедлайн 08.09 для первой единицы M-01; «единица работы = сеанс + PR + результат»; Jira (D4, D10, D17); приёмочные цифры CAP-2/CAP-4 (W10 = 649 / 700 860 ₽, норма 29.08 = 34.5 / 34 595 ₽) - место для них есть (фикстуры AD-4, `pytest`/`node:test`), формулы в `glossary.md`.

## Таблица сверки claim-by-claim

### 1. Семь обязательных пунктов промта (а-ж)

| Вход | Claim | Где в спайне | Искажение / замечание |
|---|---|---|---|
| промт а | переиспользование веток pmm-20 / pa41 / pmm29 / ai-pa-50 через ревью | AD-6 (pmm-20), AD-12 + Seed `facts/promote-order-counts.ts` (pa41), AD-8 (pmm29), AD-7 + Seed `lib/data/postgres-provider.ts` (ai/pa-50) | pa41 привязан к CSV-стейджингу, не к Statistics (#8); AD-12 мержит и pa41, и PA-03-02 (#12) |
| промт б | схема хранения дневного ряда | AD-2 `fact_cabinet_daily` + view; AD-12 миграция 013; Conventions «Ключи и время» | Колонки и формулы совпадают с глоссарием. Не задано, какая версия дня «текущая» при упавшем прогоне (#6) |
| промт в | режим API с лимитами + фикстуры при первом прогоне | AD-4 реестр бюджетов, `FixtureTransport`, `record-fixture` | `reportDetailByPeriod` в реестре против гейта (#3); «при первом прогоне» = ручной CLI (#16) |
| промт г | точка встраивания `/brief` | AD-7, Capability map CAP-5, Seed `services/webapp/src/lib/data/` | Нет средства деплоя webapp в сентябре (#4); env/banner из WEB-STATE §8 (#14) |
| промт д | run_id / идемпотентность / удаление прогона | AD-3 `collector_runs`, CASCADE, `make delete-run --dry-run`, роль `proxima_run_janitor` | DO NOTHING против поздних отмен (#1); `_current` без фильтра по статусу (#6) |
| промт е | боевая + `proxima_test` | AD-9 | Prevents-строка против правила (#5); `psql` на хосте нет (#2) |
| промт ж | расписание + бэкфилл 26 недель | AD-5 (systemd 05:30 → 05:45 → 06:00 → 06:10; `collect --from 2026-03-01 --backfill`), CAP-2 в Capability map | Toolchain хоста (#2); v3 «за вчера» (#7); OnFailure-юнит (#18) |

### 2. SPEC - Capabilities

| Вход | Claim | Где в спайне | Искажение / замечание |
|---|---|---|---|
| CAP-1 | ежедневный сбор orders + sales, ряд за каждый день, повтор без дублей | Capability map → `jobs/collect.ts`, `stg_wb_orders_rows`, `stg_wb_sales_rows`, `fact_cabinet_daily`; AD-1..5, AD-11 | «Без дублей» реализовано через DO NOTHING, что ломает отмены (#1) |
| CAP-2 | бэкфилл с 01.03.2026 до вытеснения; W10/W35 суммы = фикстуры 30.08 | Capability map → `jobs/backfill.ts` (= collect `--from`); AD-4, AD-5 | Совпадает с API-FACTS (один вызов `flag=0` отдаёт всё окно, 80k не достигнут). Приёмочный тест на недельные суммы - место есть (AD-4 фикстуры), явно не назван |
| CAP-3 | дата/время данных; >24 ч без сбора - предупреждение вместо цифр | Capability map → view `data_status_current`; AD-7 `status ok\|stale\|blocked` | Порог 24 ч и правило вычисления на чтении не записаны (#9) |
| CAP-4 | норма = медиана 14 полных дней по заказам без отмен и выручке; 29.08 → 34.5 / 34 595 ₽ | AD-6 `norm/`, `norm_daily`; Capability map CAP-4 | Границы окна и «полный день» неоднозначны (#10) |
| CAP-5 | вчера против нормы в % на `/brief`, 7 утр подряд | AD-7 `brief_daily.payload{yesterday, norm, deviation_pct}`; AD-5 порядок таймеров; AD-13 | Нет замечаний по данным; средство деплоя webapp (#4) |
| CAP-6 | воронка по nmId: async CSV с 01.09 + v3 ежедневно; 8 недель к 27.10 | Capability map → `jobs/funnel.ts` + `tools/wb_async_report.py`, `fact_funnel_daily`; AD-1, 3, 4, 5 | v3 «за вчера» вместо 7-дневного окна; разделяемая квота D20 (#7). Схема `fact_funnel_daily` (грейн, колонки, слияние CSV+v3; в v3 нет показов - только `openCount`) не задана - только имя |
| CAP-7 | аномалии, ранжирование по деньгам, SKU/категория | Capability map → `detectors/scn001` + адаптер, `signals[]` в payload; AD-6, AD-8; Deferred (порог, грейн) | SKU-грейн опирается на `fact_order_counts` из CSV - два определения «заказы» (#8) |
| CAP-8 | гипотеза + проверка + SourceRef к каждой аномалии | Capability map → `diagnosis/` (есть, mock LLM) → `signals[].diagnosis`; AD-8; Deferred (LLM-провайдер) | Покрыто; `source_refs[]` в payload есть |

### 3. SPEC - Constraints, Non-goals, Assumptions, Open questions

| Вход | Claim | Где в спайне | Искажение / замечание |
|---|---|---|---|
| Constraint 1 | только READ WB API; лимиты по API-FACTS; nm-report v2 снят; окно ~6 мес | AD-4 (бюджеты 1/10/1/3/3 - совпадают); AD-5 (март выпадает по дню) | Явного «WRITE запрещён» нет (#17); `reportDetailByPeriod` в реестре (#3); мёртвые `supplier/incomes` и `nm-report v2` в гейт `verify_business_signal.py` не входят - реестр-allowlist это покрывает косвенно |
| Constraint 2 | канал - `/brief` в `services/webapp`, не Telegram/почта | AD-7; Deferred «Telegram не в лестнице» | Покрыто |
| Constraint 3 | без auth; auth-зона webapp и `services/control-plane/src/proxima/` заморожены | Conventions «Auth» | `src/proxima/` не упомянут (#11) |
| Constraint 4 | тесты на фикстурах; живой API только когда без него никак; первый прогон → фикстура; канон VPS + S3, не git | AD-4; Conventions «Тесты» | Малые фикстуры в git = [ASSUMPTION], путь `services/collector/tests/fixtures/wb-api/` не попадает под `.gitignore` (`fixtures/wb-api/` якорен к корню - проверено `git check-ignore`) - ок. Автосохранение и обезличивание (#16) |
| Constraint 5 | run_id, идемпотентность, удаление прогона целиком | AD-3 | #1, #6 |
| Constraint 6 | multi-tenant `tenants` + RLS; сентябрь = один tenant | AD-11 (образец 009 подтверждён: `current_setting('proxima.tenant_id', true)`) | Покрыто |
| Constraint 7 | норма D21, метрика тревоги - заказы без отмен, выручка справочно | AD-6; AD-2 колонки | #10 |
| Constraint 8 | переиспользовать ветки через ревью; три `010_*.sql` перенумеровать; additive-only + self-checksum | AD-6/7/8/12 | #8, #12 |
| Constraint 9 | один VPS; боевая + `proxima_test`; сандбокс только `proxima_test` | AD-9 | #2, #5 |
| Constraint 10 | сервер только чтение; деплой по явному «деплой» с планом отката; секреты не покидают VPS | AD-10; Conventions «Конфигурация и секреты» | Покрыто |
| Constraint 11 | единица работы = сеанс + PR + результат | нет | Процесс, не архитектура - допустимо |
| Constraint 12 | расписания нет; первая единица M-01 до 08.09 | AD-5 | Дедлайн - процесс; допустимо |
| Constraint 13 | `WORKS-TODAY.md` перед каждым релизом | Conventions «Тесты» | В деплой-последовательности AD-10 нет (#15) |
| Non-goals | auth, Ozon, второй кабинет до M-03, Telegram/почта, воронка в сводке в сентябре, переписывание webapp, Torgstat, ветки pa-9/pa-27, запись в WB | Deferred; AD-7 payload без воронки; Structural Seed без pa-9/pa-27 | Покрыто; «запись в WB никогда» - #17 |
| Assumption 1 | квоты async-отчётов хватает при внешнем потребителе (D20) | нет | #7 |
| Assumption 2 | v3: 201 nmId = 11 вызовов/день при 3/мин | AD-4 бюджет 3/мин | Покрыто косвенно |
| Assumption 3 | `make verify` на маке (Homebrew PG16); зона OpenHands получает uv/node через `.openhands/setup.sh` | Conventions «Тесты» | На хост (не зону) ничего не ставится - #2 |
| Open Q 1 | порог тревоги - Mike после первых сводок | Deferred | Покрыто |
| Open Q 2 | малые фикстуры в git - решает архитектура | AD-4 [ASSUMPTION] | Решено; обезличивание - #16 |
| Open Q 3 | systemd на хосте vs планировщик в контейнере | AD-5 [ASSUMPTION] | Решено; следствие для toolchain хоста не проработано - #2 |

### 4. glossary.md

| Термин | Claim | Где в спайне | Искажение / замечание |
|---|---|---|---|
| Заказы | строки `orders` за день по `date`, без `isCancel` | AD-2 `orders_count`, `cancelled_count` | Формула ок; обновление `isCancel` задним числом - #1 |
| Продажи / выручка | `saleID` S, Σ `finishedPrice`; R не входят | AD-2 `sales_count`, `returns_count`, `revenue_rub` | Покрыто |
| Полный день | сбор завершён после окончания дня; последняя частичная выгрузка - неполный | AD-6 `calendar_day < today(МСК)` | Упрощение (#10) |
| Норма / Отклонение | медиана 14 полных дней; (вчера − норма)/норма | AD-6, AD-7 `deviation_pct` | Границы окна (#10) |
| Сводка | статус данных, вчера против нормы, с M-04 аномалии, с M-05 план | AD-7 payload | Покрыто |
| Прогон / run_id | каждая строка несёт run_id; удаляется целиком | AD-3 | Покрыто |
| Фикстура | реальный ответ без заголовков авторизации; канон VPS + S3 | AD-4 | Покрыто |
| Воронка | v3 / async CSV: открытия, корзина, заказы, выкупы | `fact_funnel_daily` (имя) | Схема не задана (CAP-6) |
| Окно WB | ~6 мес скользящих | AD-5 | Покрыто |
| Боевая / `proxima_test` | копия для тест-запусков; сандбокс только `proxima_test` | AD-9 | #5 |

### 5. DECISIONS D1-D21

| D | Claim | Где в спайне | Искажение / замечание |
|---|---|---|---|
| D1, D4, D9, D10, D17 | рамка, Jira, деление сессий, файлы единиц работы | n/a | Процесс; не противоречит |
| D2 | лестница; переиспользовать collector, миграции, `wb_api_probe.py`, `wb_async_report.py` | Paradigm, CAP-6 (`wb_async_report.py`) | `wb_api_probe.py` не упомянут - допустимо |
| D3 | истина = `origin/main`; серверные чекауты - предмет инвентаризации | AD-10 канон `~/proxima-ai` [ASSUMPTION] | Не противоречит |
| D5 / D5b | токены на сервере `/etc/proxima-ai/secrets/wb_*_token`; analytics-токен RW, только read-эндпоинты; ротация PA-13 в бэклоге | Conventions «Секреты» (`*_FILE`), AD-11 `<tenant>_*`, Deferred (PA-13) | Именование `<tenant>_*` расходится с существующими файлами (#13) |
| D6 | граница сентября = M-03 | scope, Capability map | Покрыто |
| D7 | деплой - Claude после «деплой», по записанной команде с откатом | AD-10 | Покрыто |
| D8 | один VPS; `proxima` + `proxima_test` dump/restore; сандбокс через bridge `172.17.0.1:5432` только к `proxima_test` | AD-9 (bridge в `infra/compose.yaml:19` подтверждён) | #2, #5 |
| D11 / D12 | `ai/pa-50` спасена; спасать, не переписывать; webapp доделывать | AD-7, Seed | Покрыто |
| D13 | A + B фоном: Statistics для нормы; воронка через async CSV с 01.09; бэкфилл в сентябре | AD-2, AD-5, CAP-6 | Покрыто; #7 |
| D14 | pa41 (новее PA-03-02); pmm-20 → M-02; pmm29 → M-03; ai/pa-50 → M-03; списать pa-9, pa-27; коллизия 010 → перенумерация | AD-6/7/8/12, Seed | AD-12 называет обе promotion-ветки (#12) |
| D15 | фикстуры VPS + S3; `fixtures/wb-api/` в `.gitignore`; малые < 1 МБ - решает архитектура | AD-4 (≤ 200 КБ в `services/collector/tests/fixtures/wb-api/`), Deferred (git-lfs нет) | Решено; путь не конфликтует с `.gitignore` |
| D16 | два пробных вызова v3 | n/a | Факт |
| D18 | сентябрь = Амирова; multi-tenant остаётся; второй tenant после M-03 | AD-11, Deferred | Покрыто |
| D19 | webapp доделывать; staging пересобирать из main через `infra/webapp.compose.yaml`, не `docker run`; auth не трогать; первая единица M-01 до 08.09 | AD-10 (`infra/compose.yaml`), Deferred (`webapp.compose.yaml` - октябрь) | Конфликт по средству деплоя webapp (#4) |
| D20 | v3 только 7 дней; async CSV единственный путь к глубине; квота разделяемая - «учесть в M-01»; источник отчётов вне сервера | AD-5 (v3 daily, CSV weekly); Deferred (PA-13) | Разделяемая квота не учтена (#7) |
| D21 | медиана 14 полных дней; заказы без отмен - тревога; выручка справочно; scn001 поддерживает окно 14 | AD-6 | Проверено по ветке: scn001 `baseline.py` = среднее по weekday в окне 28 (`WEEKDAY_WINDOW_DAYS = 28`, `windows (7, 14, 28)`, `trigger_window 28`), день оценки исключён - утверждение спайна «со средним» точное. #10 |

### 6. API-FACTS.md

| Claim | Где в спайне | Искажение / замечание |
|---|---|---|
| Лимиты: `sales` 1/мин, `orders` 10, `reportDetailByPeriod` 1, `seller-info` 10, `nm-report/downloads` 3, v3 3/мин (интервал 20 с, всплеск 3); `X-Ratelimit-Retry` только с 429; `Retry-After` не встречался | AD-4 реестр: 1 / 10 / 1 / 3 / 3, 429 по `X-Ratelimit-Retry` | Числа совпадают. `seller-info` (10/мин, нужен `wb_api_probe.py`) в реестре нет - низкое. `reportDetailByPeriod` против гейта (#3) |
| Окно Statistics ~6 мес; `flag=0` фильтрует по дате заказа/продажи, изменения (`lastChangeDate`) доезжают до 2 недель; один вызов отдаёт весь ряд (10 611 / 13 325 строк, 80k не достигнут) | AD-5 инкремент `dateFrom = today-3, flag=0`; бэкфилл `--from 2026-03-01` | Инкремент ловит поздние изменения только если staging версионируется (#1). Окно 3 дня при `Persistent=true` после простоя > 3 дней оставит дыру - `data_status` должен это видеть (#9) |
| Мёртвые: `supplier/stocks` (404 deprecated), `supplier/incomes` (404), `nm-report v2 detail/history` (404) | AD-4 (реестр = allowlist) | Явного списка запрещённых нет; гейт закрывает только stocks + reportDetail |
| v3: 7 дней, до 20 nmId, нет показов; 201 nmId = 11 вызовов; снимать ежедневно всё окно (перекрытие 7 раз) | AD-5 «v3 за вчера» | #7 |
| async CSV: `DETAIL_HISTORY_REPORT`, квота 20/день по коду, внешний потребитель создаёт ежедневный отчёт ~00:51; глубина `startDate` не проверена; `wb_async_report.py` = последняя закрытая неделя | AD-5 «раз в неделю», CAP-6 `tools/wb_async_report.py` | Недельный ритм совпадает с кодом; квота #7 |
| Существующий код: `WbSignalClient.sales` (курсор `lastChangeDate`, 80k, пауза 60 с), `RecordedHttpClient`, `raw-store` CAS, `fact_order_counts` nm_id × day (007), `stg_wb_nm_report_rows` (005) | Paradigm таблица, AD-1, AD-4 | Подтверждено в коде (`http.ts:65`, `wb-client.ts:98-150`) |
| `orders` и v3 нигде не используются | AD-4 «новый эндпоинт → реестр + allowlist одним PR» | Покрыто |

### 7. WEB-STATE.md §4, §8

| Claim | Где в спайне | Искажение / замечание |
|---|---|---|
| §4 fixtures - единственный источник; `getDataDb()/hasDataDb()` не вызываются; drizzle-схем доменных таблиц нет; ролей `webapp_readonly` в миграциях нет | AD-7 (`postgres-provider.ts` реализовать), AD-12 015 (`webapp_readonly`) | Через drizzle `getDataDb` или голый `pg` - не сказано; низкое |
| §4 auth-гейт только по cookie; env-имена расходятся | Conventions «Auth» (заморожено) | Покрыто |
| §8 встраивание: `brief/page.tsx` → `getBrief()`; loader заменяет при `hasDataDb()`; `BriefSignal` расширить (metric, actual, baseline, deltaPercent, window, sourceRef); `UnreleasedBanner dataMode="staging"`; `WEBAPP_DATA_DATABASE_URI` в контейнере; таблицы «сводка дня» нет - её даёт control-plane | AD-7 `brief_daily` + `contracts/brief.schema.json` (yesterday, norm, deviation_pct, signals, source_refs), AD-8 codegen вместо `types.ts` | Поля контракта покрывают требуемые. Env и banner (#14); средство деплоя (#4) |

### 8. MIGRATION-GAPS.md §4

| Claim | Где в спайне | Искажение / замечание |
|---|---|---|
| `ai/pa-50`: `lib/data/*`, `WEBAPP_DATA_MODE`, postgres-режим = заглушка «ждёт PMM-29 и `webapp_readonly`» | AD-7, Seed | Подтверждено по ветке |
| `pmm29-contracts`: `signal/diagnosis/decision-record.schema.json`, TS-типы, Ajv-тест, `verify_contracts.py` | AD-8 | Подтверждено по ветке; в main уже есть `acquisition-attempt`, `domain-release`, `client-passport`, `source-artifact`, `supply-plan` |
| `PA-03-02` vs `pa41`: то же ядро promotion, единственный писатель 5 таблиц; выбрать одну | AD-12 (обе), AD-3 (`attempt_id`-таблицы получают `run_id` в 011) | #12; источник pa41 = CSV-стейджинг (#8) |
| `pmm-20`: scn001 7/14/28, U×CVR×AOV, loader | AD-6 адаптер loader → `fact_*_current` (M-04) | Покрыто |
| `now-orchestrator`, `pa-9`, `stash/pa-27` - вне лестницы / списать | не упомянуты | Соответствует non-goals |
| Коллизия `010`: main = client_passport, PA-03-02 = promotion_attempt_completion, pa41 = phase3_promotion_privileges | AD-12 «011+» | Покрыто |

### 9. INVENTORY.md §4 - красные флаги

| Флаг | Claim | Где в спайне | Искажение / замечание |
|---|---|---|---|
| 1 | PA-50 незапушена - закрыт D11 | AD-7 | Покрыто |
| 2 | схема БД 6/10; `/srv` compose монтирует 001-006 как initdb | AD-10 (вывод `/srv` из эксплуатации, `make apply-migrations` - target есть в Makefile:62), AD-12 | Покрыто. Явно не сказано, что первый релиз сначала применяет 007-010 (роли 009, `dim_client_passport` 010), потом 011+ - низкое |
| 3 | данные не собираются; расписания нет | AD-5 | Покрыто; исполняемость на хосте (#2) |
| 4 | пять копий кода | AD-10 | Покрыто |
| 5 | webapp не из main, `docker run` вручную; `webapp.compose.yaml` не развёрнут, Caddy нет | AD-10, Deferred | #4 |
| 6 | D8 не реализован на хосте: bridge отсутствует в `/srv`, rootless Postgres в зоне | AD-9 (bridge из compose main; `proxima_dev` хост и зона выводятся) | Покрыто |
| 7a | `~/.git-credentials` на сервере | Deferred (бэклог M-01) | Явно Deferred - ок |
| 7b | analytics-токен RW; два разных analytics-токена в `/etc` и `~/signal-inputs` | Deferred (PA-13) | RW - Deferred. Какой из двух файлов канон для collector - не сказано (#13) |
| 7c | `wb_prices_token`, `wb_promotion_token` отсутствуют, `.env` на них ссылается | нет | Не нужны CAP-1..8; убедиться, что collector не требует их при старте - низкое, замечание к M-01 |
| 11 | toolchain хоста: нет uv/psql, Python 3.12, нет `node_modules` | нет | #2 |
| 8, 9, 10, 12, 13 | egress OpenHands, loopback-патч, память зоны, мусор, brute-force | нет | Вне архитектуры сводки; не запрашивались |

### 10. Стек

Все 18 версий спайна совпадают с `services/webapp/package.json`, `services/collector/package.json`, корневым `package.json` (`json-schema-to-typescript ^15.0.4`), `services/control-plane/uv.lock` (psycopg 3.3.4, pydantic 2.13.4, jsonschema 4.25.1, pytest 8.4.2) и INVENTORY §d (`postgres:16.10-alpine`).

## Что проверить у Mike (не решается сверкой)

1. Обезличивать ли `proxima_test` перед сандбоксом (#5) - или принять, что агент видит ряд Амировой.
2. Окно нормы включает вчера или нет (#10) - одно предложение в `glossary.md` и AD-6.
3. `reportDetailByPeriod`: убрать из реестра или снять запрет гейта (#3).
