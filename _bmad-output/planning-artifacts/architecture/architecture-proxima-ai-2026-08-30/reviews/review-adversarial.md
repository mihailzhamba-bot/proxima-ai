# Adversarial review - ARCHITECTURE-SPINE wb-morning-brief

- Дата: 2026-08-30. Режим: read-only, враждебный. Объект: `ARCHITECTURE-SPINE.md` (draft, AD-1..AD-13) против `SPEC.md` + `glossary.md`.
- Метод: для каждой пары единиц работы (U1..U10) искал реализацию, которая буквально соблюдает каждый AD и всё равно несовместима с соседом. Каждая найденная пара = дыра. Доказательства - файлы репо и ветки, ссылки в тексте.
- Итог: **16 дыр**. 5 критических (цифры на `/brief` будут неверными или пустыми при полном соблюдении спайна), 6 серьёзных, 5 средних.

Формат каждой дыры: пара единиц → как расходятся → предлагаемый AD (Binds / Prevents / Rule).

---

## КРИТИЧЕСКИЕ

### H1. Из каких строк считается «версия дня»: свои строки прогона или все наблюдения по ключу

**Пара:** U3 (collect) ↔ U4 (backfill); U3 ↔ U6 (norm).

**Расхождение.** AD-2: «прогон вставляет новую версию затронутых дней». AD-5: `dateFrom = today-3, flag=0`. У WB `flag=0` фильтрует по `lastChangeDate` (существующий клиент так и пагинирует: `services/collector/src/business-signal/wb-client.ts:117-153`, курсор по `lastChangeDate`). Значит ответ 05:30 содержит заказ от D-30, отменённый вчера (`isCancel=true`, `date=D-30`). День D-30 - «затронутый».

- U3, соблюдая AD-3 («идемпотентность по естественному ключу внутри одного прогона»), агрегирует строки своего `run_id`: версия D-30 = 1 строка, `orders_count=0, cancelled_count=1`. Все остальные 40 заказов дня D-30 «исчезли». `_current` показывает эту версию. U6 берёт её в медиану.
- U4 с `--from 2026-03-01 flag=0` получает полный ряд и пишет правильные версии - но только один раз при деплое. Через неделю ежедневные прогоны U3 перетирают дни с поздними отменами усечёнными версиями.
- Обратный вариант (U3 агрегирует по всем staging-строкам дня через все прогоны) не описан: нужна дедупликация по `srid` с выбором последнего `lastChangeDate`, а staging с `ON CONFLICT DO NOTHING` по `(tenant_id, srid)` молча теряет обновление `isCancel`/`finishedPrice` (WB обновляет `lastChangeDate` и отдаёт строку заново). Существующий клиент падает на изменившейся строке внутри окна (`wb-client.ts:143`, `saleID changed inside one collection`) - т.е. прецедент «одна строка = одно состояние» уже в коде.

Два соблюдающих спайн исполнителя дадут разные `orders_count` за один и тот же день. CAP-5 «цифры совпадают с кабинетом WB» не выполнится ни в одном варианте без правила.

**AD-14 (новый) - Staging = журнал наблюдений, версия дня = свёртка последних наблюдений.**
- Binds: CAP-1, CAP-2, CAP-4, CAP-5.
- Prevents: версия дня из одного частичного ответа; потеря обновления `isCancel`/`finishedPrice`; два агрегатора с разным входом.
- Rule: `stg_wb_orders_rows` PK `(tenant_id, run_id, srid)`, `stg_wb_sales_rows` PK `(tenant_id, run_id, sale_id)`; обязательные колонки `calendar_day date` (= `left(date,10)`), `last_change_at timestamptz`, `is_cancel`/`sale_kind`, `finished_price numeric(14,2)`, `for_pay`, `payload jsonb` (строка WB целиком), `content_sha256`. Один прогон вставляет каждую строку ответа под своим `run_id`, `ON CONFLICT DO NOTHING` только по этому PK. View `stg_wb_orders_latest` = `DISTINCT ON (tenant_id, srid) ORDER BY last_change_at DESC, run.finished_at DESC` по прогонам `status='SUCCEEDED'`; аналогично для sales. `facts/cabinet-daily.ts` - единственный агрегатор - читает только `_latest` и пишет версию дня D для каждого D, встретившегося в строках текущего прогона, при `D ∈ [period_floor, run_day_msk - 1]`. `period_floor` = `--from` для backfill и `run_day - 3` для collect; строки с `calendar_day < period_floor` остаются в staging, версия по ним не пишется. `evidence_sha256[]` версии = все артефакты, чьи строки вошли в свёртку.

### H2. Что такое «последняя версия» в `_current`, и что она показывает после FAILED и в текущий день

**Пара:** U3 ↔ U6/U7 (читатели `_current`); U3 ↔ U9 (Persistent-перезапуск).

**Расхождение.**
1. AD-2 «view отдаёт последнюю версию каждого дня» - по чему? `run_id uuid` не упорядочен; `created_at` строки факта, `started_at` и `finished_at` прогона дают разные ответы при пересечении backfill (стартовал 10:00, закончил 11:00) и collect (05:30-05:35) в один день, и при повторном ручном backfill для починки.
2. Conventions: «частичный результат остаётся под своим run_id». U3 в 05:30 упал после вставки версий по orders, но до sales: версия дня с `revenue_rub=0`. Если `_current` не фильтрует по статусу прогона, U6 в 06:00 берёт 0 в медиану, U7 показывает «-100 % по выручке». Persistent-перезапуск в 05:31 вставит ещё одну версию - какая из двух «последняя»?
3. Окно `today-3` включает текущий день (05:30 = 5.5 часов данных). AD-6 «полный день = `calendar_day < today`» - день T, записанный прогоном дня T, станет «полным» в T+1 автоматически, даже если прогоны T+1..T+3 упали и версия T осталась пятичасовой. Глоссарий говорит «день последней частичной выгрузки - неполный», операционного определения в спайне нет. Ложная тревога -85 % гарантирована на первом же сбое таймера.

**AD-2 (ужесточение).**
- Rule (добавить): версия дня уникальна по `(tenant_id, calendar_day, run_id)`. `fact_cabinet_daily_current` выбирает для каждого дня версию прогона с максимальным `collector_runs.finished_at` среди `status='SUCCEEDED'`; версии прогонов `RUNNING`/`FAILED` невидимы для всех читателей. Вставка версий и перевод прогона в `SUCCEEDED` - одна транзакция. Прогон никогда не пишет версию за `calendar_day >= run_day_msk` (текущий день только в staging). Следствие: «полный день» = «у дня есть видимая версия»; отсутствие версии за вчера - это `stale`, не «0 заказов».

### H3. RLS + `set_config` + view: в проде 0 строк или все tenant'ы сразу

**Пара:** U10 (роли/RLS) ↔ U3 (TS-job), U6/U7 (psycopg), U8 (webapp).

**Расхождение.** AD-11: политика `USING (tenant_id = current_setting('proxima.tenant_id', true))`, `set_config(..., $1, true)` «в начале транзакции». AD-7: webapp делает два SELECT из view под `webapp_readonly`.
- Postgres: view без `security_invoker` проверяет права и RLS **от имени владельца view**. Владелец = тот, кто применил миграцию (в compose - `POSTGRES_USER`, он же владелец таблиц; `infra/compose.yaml`). Владелец таблицы обходит RLS. Итог: `webapp_readonly` через `brief_current` видит все tenant'ы, `set_config` не нужен и не проверяется. В сентябре с одним tenant «работает», со вторым - утечка (blind spot «wrong config»).
- Если U10 сделает view `WITH (security_invoker = true)` (правильно), то U8 в текущем виде (`services/webapp/src/lib/db/client.ts:42-50`, drizzle pool без `set_config`) получит `current_setting(...) = NULL` → 0 строк → пустой экран или «данных нет» как факт о кабинете.
- `set_config(name, value, true)` = transaction-local. node-postgres pool по умолчанию autocommit: `set_config` в отдельном запросе исчезает сразу после него. U3, буквально следуя AD-11, получит `WITH CHECK` violation на первом INSERT. psycopg (U6/U7) открывает неявную транзакцию - у него сработает. Один AD, два поведения по языкам.
- Роли 009 - `NOLOGIN` (`db/migrations/009_runtime_roles.sql:3-6`). Спайн говорит «под ролью proxima_norm_publisher», но не говорит, каким login-пользователем и через `SET ROLE` ли. Если login = владелец БД, `SET ROLE` не выполнен → RLS обойдён молча.

**AD-11 (ужесточение).**
- Rule (добавить): все view `*_current`, `brief_current`, `data_status_current` создаются `WITH (security_invoker = true)`; читающие роли получают SELECT на базовые таблицы. Для каждой job-роли и `webapp_readonly` в 015 создаётся LOGIN-роль-член (`proxima_collect_login` и т.д., пароль из `/etc/proxima-ai/secrets/pg_<role>_password`); DSN владельца используется только `make apply-migrations`. TS-job держит один выделенный client и выполняет прогон в одной транзакции `BEGIN; set_config(...,true); ...; COMMIT`; webapp вызывает `set_config('proxima.tenant_id', WEBAPP_TENANT_ID, false)` в `pool.on('connect')`. `make verify` включает RLS-тест под реальной ролью: без `set_config` - 0 строк, с чужим tenant - 0 строк, INSERT с чужим tenant - ошибка.

### H4. `delete-run` откатывает факты, но не норму и сводку, посчитанные по ним

**Пара:** U9 (delete-run) ↔ U6/U7 (norm/brief).

**Расхождение.** AD-3: cascade от `collector_runs` к таблицам с этим `run_id`. `norm_daily.run_id` = прогон norm, `brief_daily.run_id` = прогон brief. Удаление плохого collect-прогона `X` возвращает предыдущую версию дней, но `norm_daily`, посчитанная по версии `X`, и `brief_daily` с `deviation_pct` по ней остаются `SUCCEEDED` и остаются «текущими». AD-3 обещает «прогон обратим целиком» - он обратим на треть. Дополнительно: `--dry-run` печатает счётчики по таблицам, но не знает о зависимых прогонах, потому что связи нет.

**AD-3 (ужесточение).**
- Rule (добавить): таблица `collector_run_inputs(run_id uuid REFERENCES collector_runs ON DELETE CASCADE, input_run_id uuid REFERENCES collector_runs ON DELETE CASCADE, PRIMARY KEY (run_id, input_run_id))`. Каждый прогон, читающий версии (cabinet-daily из `_latest`, norm из `_current`, brief из `norm_daily` и `_current`), записывает все `run_id` прочитанных версий. `tools/delete_run.py` считает транзитивное замыкание зависимых прогонов, `--dry-run` печатает его целиком, удаление идёт по замыканию в одной транзакции. Файлы CAS на диске не удаляются (артефакт может быть скопирован в фикстуру) - это записать явно.

### H5. Реестр артефактов: `business_signal_raw_artifacts` ссылается на `business_signal_runs`, не на `collector_runs`

**Пара:** U2 (WB-клиент) ↔ U1 (миграции), U9 (delete-run).

**Расхождение.** AD-1 требует «строку в реестре артефактов с `run_id`» и AD-4 - расширять существующий `RecordedHttpClient`. Существующий реестр: `business_signal_raw_artifacts.run_id NOT NULL REFERENCES business_signal_runs ON DELETE RESTRICT` (`db/migrations/004_business_signal_slice.sql:86`), locator `CHECK ~ '^artifact://business-signal/sha256/'` (`:96`), `business_signal_runs.status` из enum `RUNNING|NO_SIGNAL|BLOCKED|READY|SENT|SEND_FAILED` с обязательными `window_from/to` (`:33-57`). U2, переиспользуя клиент, обязан завести `business_signal_runs`-строку на каждый прогон - второй run-ledger рядом с `collector_runs`, и `delete-run` через `collector_runs` до артефактов не дотянется (RESTRICT на другой FK). Если U2 вместо этого создаст новую таблицу артефактов - в репо будет три формата locator: `artifact://business-signal/sha256/` (004), `artifact://sha256/` (`services/collector/src/intake/manifest.ts:101`, `contracts/source-artifact.schema.json`), и «`artifact://…/sha256/<hex>`» из AD-1 с многоточием. `stg_*` ссылаются на `content_sha256` - на какую таблицу FK?

**AD-1 (ужесточение).**
- Rule (заменить): реестр для всех новых прогонов - `wb_raw_artifacts(artifact_id uuid PK, run_id uuid NOT NULL REFERENCES collector_runs ON DELETE CASCADE, tenant_id, endpoint_path, query_canonical jsonb, page_sequence, http_status, response_headers jsonb (allowlist), content_sha256 char(64), content_size, locator CHECK ~ '^artifact://sha256/[0-9a-f]{64}$', retrieved_at timestamptz, UNIQUE (run_id, endpoint_path, page_sequence))` в миграции 011. CAS-каталог один: `$PROXIMA_RAW_DIR/sha256/<hex>`. `business_signal_raw_artifacts` не трогается (business-signal до M-04 живёт на своём ledger). `stg_*.content_sha256` - без FK (артефакт может быть удалён по AD-3 позже staging), проверка целостности - в `make verify` (`tools/verify_business_signal.py` расширить на новый реестр).

---

## СЕРЬЁЗНЫЕ

### H6. Время: наивные даты WB парсятся часовым поясом хоста; таймеры «05:30 МСК» пишутся в UTC

**Пара:** U3/U4 (collect) ↔ U9 (systemd, compose); U6 (Python today) ↔ U3 (TS today).

**Расхождение.** WB отдаёт `date`, `lastChangeDate`, `cancelDate` как `2026-08-30T07:01:10` без смещения (`docs/state/API-FACTS.md`, таблица B/C) - это МСК. Существующий код делает `new Date(value)` (`services/collector/src/business-signal/date-window.ts:29`): без смещения JS парсит как локальное время процесса. На маке Mike (МСК) тесты зелёные; на VPS (`infra/compose.yaml` без `TZ`, хост Ubuntu, `timedatectl` в инвентаризации не зафиксирован) заказ `22:30` МСК ляжет в следующий день. U3, взяв этот helper по AD-4 («расширение существующего клиента»), получит сдвиг дня для ~12 % заказов (вечерние часы), U6 на Python `ZoneInfo` (как `scn001/clock.py`) считает `today` правильно - норма и факт считают «вчера» по-разному. Таймер `OnCalendar=05:30` без суффикса = 05:30 UTC = 08:30 МСК; прецедента с `OnCalendar` в репо нет (`infra/monitoring/proxima-host-monitor.timer` - `OnUnitActiveSec`). SQL с `CURRENT_DATE` в view `data_status_current` даст UTC-дату.

**AD-15 (новый) - Календарный день считается строкой, момент - только с явным поясом.**
- Binds: CAP-1, CAP-3, CAP-4, CAP-5.
- Prevents: зависимость дня от TZ хоста; `new Date(naive)`; `CURRENT_DATE` в SQL; таймеры в UTC под именем МСК.
- Rule: поля WB `date/lastChangeDate/cancelDate` - naive Europe/Moscow. `calendar_day = left(date, 10)::date`, без парсинга; `last_change_at = (lastChangeDate::timestamp) AT TIME ZONE 'Europe/Moscow'`. `today_msk` в TS - `Intl.DateTimeFormat('en-CA', {timeZone: 'Europe/Moscow'})`, в Python - `ZoneInfo`; каждый job принимает `--now <ISO с offset>`. В SQL «сегодня» только как `(now() AT TIME ZONE 'Europe/Moscow')::date`. Postgres-контейнер явно `TZ=UTC`, `PGTZ` не задаётся. Таймеры `OnCalendar=*-*-* 05:30:00 Europe/Moscow`. `make verify` grep-гейт на `new Date(` над строками без `Z`/offset в `services/collector/src/wb/**` и `jobs/**`.

### H7. `brief.schema.json`: кто пишет первым, что в нём деньги, и почему `signal` v1 не рендерится

**Пара:** U7 (builder, pydantic) ↔ U8 (webapp codegen).

**Расхождение.** AD-8 требует схему в `contracts/`, но не говорит, кто её пишет и когда. U7 выведет схему из pydantic (`revenue: float`, `deviation_pct: float`), U8 - из `services/webapp/src/lib/data/types.ts` ветки `ai/pa-50` (`BriefSignal{status GYR, title, cause, costEstimate, riskLevel, primaryCause, alternatives, unknowns, recommendation, sourceRefs: SourceRef{id,label,period,source}}`). AD-7 вкладывает `signals[]` по `signal.schema.json` из `pmm29` - там `detection_data{value,is_unknown}`, `rub_assessment`, `trust_marking`, `source_refs: string[]` и ни одного поля для отображения. U8 либо пишет адаптер `detection_data → title/cause/recommendation` (бизнес-логика в Next.js - запрещено AD-7), либо UI-компоненты остаются на ручных типах (запрещено AD-8). Деньги: `numeric(14,2)` из pg приходит строкой в node-postgres, из psycopg - `Decimal`; в JSON U7 запишет `34595.5` (float), U8 codegen ждёт то, что в схеме - схемы нет. `deviation_pct` округляет U7 или U8 - оба.

**AD-8 (ужесточение).**
- Rule (добавить): `contracts/brief.schema.json` v1 и `contracts/source-ref.schema.json` (`{id, label, period, source, content_sha256?}`) пишутся в U1 вместе с 015 и замораживаются до старта U7/U8; U7 и U8 только валидируют. В payload: счётчики `integer`; деньги `string` с `^-?[0-9]+\.[0-9]{2}$`; проценты `number`, округлённые builder'ом до 1 знака; webapp ничего не пересчитывает и не округляет. `brief_daily.schema_version int NOT NULL` дублирует `payload.schema_version`; webapp сравнивает с константой из codegen и при несовпадении рендерит `blocked`. `signals[]` в brief - render-ready объект (`title, cause, recommendation, source_refs[]` по `source-ref.schema.json`) с вложенным `signal` v1 как есть; `signal.source_refs: string[]` не меняется до v2.

### H8. `fact_funnel_daily`: два писателя на двух языках с двумя словарями колонок и двумя реестрами доказательств

**Пара:** U5 (funnel: v3 TS + async CSV Python) ↔ U1 (013/011), U9 (delete-run), CAP-7.

**Расхождение.** v3 отдаёт `openCount, cartCount, orderCount, orderSum, buyoutCount, buyoutSum, buyoutPercent, addToCartConversion, cartToOrderConversion, addToWishlistCount` (API-FACTS, «Структура ответа»). CSV `DETAIL_HISTORY_REPORT` в `stg_wb_nm_report_rows.payload` - `nmID, dt, ordersCount, openCardCount, ordersSumRub, buyoutsCount, addToCartCount, cancelCount…` (`scn001/loader.py COLUMN_MAP`, ветка pmm-20). CSV-сборщик - `tools/wb_async_report.py`, Python вне обоих сервисов, пишет `wb_analytics_report_tasks` (ключ `task_id`, не `attempt_id` и не `run_id`), `raw_wb_analytics_responses`, `stg_wb_nm_report_rows` (`:313, :409, :477`). AD-3 обещает `run_id` только «attempt_id-таблицам»; AD-13 диаграмма не содержит узла `tools/`. Итог: v3-версии дня под `collector_runs`, CSV-версии под `task_id`; delete-run не видит вторую половину; `_current` для (nmId, day) при 7 перекрывающихся v3-версиях + 1 CSV не имеет правила выбора, а `buyoutCount` v3 (по дню заказа) и `buyoutsCount` CSV семантически разные числа под одной колонкой.

**AD-16 (новый) - Одна витрина воронки, одна карта колонок, один писатель.**
- Binds: CAP-6, CAP-7.
- Prevents: Python-писатель staging вне AD-13; два словаря полей; неразличимые источники в одной строке.
- Rule: `contracts/funnel-daily.schema.json` фиксирует канонические поля `open_count, cart_count, order_count, order_sum_rub, buyout_count, buyout_sum_rub, wishlist_count`. `fact_funnel_daily(tenant_id, nm_id, calendar_day, source 'v3'|'csv', run_id, …, evidence_sha256, UNIQUE(tenant_id, nm_id, calendar_day, source, run_id))`. Единственный писатель - `collector/src/jobs/funnel.ts`: режим `--v3` и режим `--from-task <task_id>` (читает `stg_wb_nm_report_rows`, сам CSV не качает). `wb_async_report.py` остаётся только загрузчиком CSV; 011 добавляет `wb_analytics_report_tasks.run_id uuid NULL REFERENCES collector_runs ON DELETE CASCADE`. `fact_funnel_daily_current` выбирает по правилу H2 внутри каждого `source`; выбор между источниками - решение M-04, `source` обязателен в любом читателе.

### H9. Control-plane и `collector_runs`: кто вставляет, `evaluation_day` чей, окно нормы включает ли «вчера»

**Пара:** U6 (norm) ↔ U7 (brief); U6 ↔ U1 (гранты).

**Расхождение.**
1. `kind norm|brief` → два прогона. Строку в `collector_runs` пишет Python под `proxima_norm_publisher`, но 015 по AD-12 создаёт только `webapp_readonly` и `proxima_sandbox`; INSERT/UPDATE на `collector_runs` для norm-роли нигде не назначен. U6 либо получит permission denied, либо U1 «на всякий случай» даст роли больше, чем нужно.
2. `norm_daily(evaluation_day, …)`: для U6 это день расчёта (`today`) или оцениваемый день (`today-1`, как `scn001/clock.py: default_evaluation_date = today_msk - 1`)? U7 ищет норму для `brief_day = today-1`. Разные трактовки = off-by-one или пустая сводка. Уникального ключа у `norm_daily` нет: retry norm-прогона даёт две строки на `(evaluation_day, metric)`.
3. AD-6: «14 последних полных дней, полный = `< today`» → на T в 06:00 окно `[T-14, T-1]` включает T-1 - тот самый день, который сводка сравнивает с нормой. Глоссарий/D21 этого не уточняют. CAP-4 (для 29.08 норма 34.5 на фикстурах 30.08) можно удовлетворить обоими окнами при разных данных; U6 и тест зафиксируют одно, U7 (и Mike, читая «вчера против нормы») будет ожидать другое.
4. `sample_days < 14` (пропуски после сбоев): U6 fail-closed не пишет строку, U7 ждёт строку с `sample_days`.

**AD-6 (ужесточение).**
- Rule (добавить): `evaluation_day` = оцениваемый день (день сводки), не день расчёта. Окно нормы = `[evaluation_day - 14, evaluation_day - 1]` - оцениваемый день в медиану не входит; CAP-4-фикстура пересчитывается под это окно и становится тестом. `norm_daily UNIQUE (tenant_id, evaluation_day, metric, window_days, run_id)`, `norm_daily_current` по правилу H2. U6 всегда пишет строку: `value NULL`, если `sample_days < 7`; `sample_days` фактический. 015 выдаёт `proxima_norm_publisher` INSERT на `collector_runs`, `norm_daily`, `brief_daily`, `collector_run_inputs` и UPDATE `(status, finished_at)` на `collector_runs`; norm и brief - два прогона, brief пишет `collector_run_inputs` на norm-прогон.

### H10. `stale` считается дважды, `brief_current` после упавшего brief показывает позавчера как «ok»

**Пара:** U7 (payload.data_status, status) ↔ U8 (webapp, `data_status_current`); U1 (view) ↔ U7.

**Расхождение.** AD-7: `payload.data_status{last_full_day, collected_at, stale}` - снимок на 06:10; `data_status_current` - живой view (CAP-3 строка). Webapp читает оба. Сценарий: brief T успешен; на T+1 collect и brief упали. `brief_current` = brief за T-1 со `status=ok`; `data_status_current` (если он считает от `collector_runs`) - `stale=true` через 24 часа, а до этого `stale=false`. Webapp по AD-7 рендерит предупреждение «при `status=stale|blocked`» - по какому из двух статусов? Ни один не говорит, что сводка за T-1 показывается утром T+1 как сегодняшняя. «Сегодня» в webapp считается Node-процессом в контейнере (UTC). Само правило 24 ч: от `finished_at` последнего collect, от `collected_at` последнего полного дня, или `last_full_day < today-1`?

**AD-7 (ужесточение).**
- Rule (добавить): `data_status_current(tenant_id, last_full_day, collected_at, stale)` создаётся в 013: `last_full_day = max(calendar_day)` из `fact_cabinet_daily_current`, `collected_at = finished_at` его прогона, `stale = collected_at < now() - interval '24 hours' OR last_full_day < (now() AT TIME ZONE 'Europe/Moscow')::date - 1`. Builder копирует `data_status` из этого view (не считает сам). `brief_current` = строка с максимальным `finished_at` среди `SUCCEEDED` brief-прогонов. Webapp показывает цифры только при `brief.status = 'ok' AND NOT data_status.stale AND brief.brief_day = data_status.last_full_day`; иначе предупреждение с `last_full_day` и `collected_at`. Дата «сегодня» в webapp не вычисляется вообще.

### H11. `make test-db-refresh` = полная копия данных кабинета в базу, к которой ходит сандбокс

**Пара:** U10 (test-db-refresh) ↔ AD-9 Prevents («OpenHands с доступом к данным кабинета»).

**Расхождение.** AD-9 буквально: `pg_dump proxima | psql proxima_test` перед каждым тест-запуском, и `proxima_sandbox` ходит в `proxima_test`. U10 сделает ровно это: 26 недель заказов Амировой с `srid`, `finishedPrice`, брендами окажутся в базе, которую читает агент с доступом к LLM через внешний туннель (`docs/state/INVENTORY.md:71`). Prevents нарушен самим Rule. Дополнительно: `pg_dump | psql` в непустую базу сыплет ошибками на существующих объектах; `DROP DATABASE` невозможен, пока сандбокс держит соединение; `pg_dump` не переносит роли (они на уровне кластера - ок), но `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC` не упомянут - по умолчанию `PUBLIC` имеет CONNECT, «без CONNECT к proxima» не выполняется.

**AD-9 (ужесточение).**
- Rule (заменить фрагмент): `make test-db-refresh` = `dropdb --force --if-exists proxima_test && createdb proxima_test && pg_dump --schema-only proxima | psql proxima_test && загрузка обезличенных фикстур` (`services/collector/tests/fixtures/wb-api/**` через FixtureTransport, без строк боевой базы). `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC; GRANT CONNECT … TO` перечисленным ролям - в 015. Если для CAP-2-проверки нужны реальные суммы (W10/W35) - они считаются на VPS-фикстурах под `proxima_source_publisher`, не в `proxima_test`.

---

## СРЕДНИЕ

### H12. `collector_runs.kind` и `status`: имена job'ов и регистр расходятся с существующими таблицами и схемами

**Пара:** U1 (CHECK) ↔ U3/U6 (значения).

**Расхождение.** AD-3: `kind backfill|daily|funnel|norm|brief`; AD-5 и Structural Seed: job `collect`, файл `collect.ts`, таймер `proxima-collect@`. U3 напишет `kind='collect'`. Статусы: 007 - `RUNNING|SUCCEEDED|FAILED`, 004 - `RUNNING|NO_SIGNAL|…`, `contracts/acquisition-attempt.schema.json` - `running|succeeded|failed|partial|stale`, brief - `ok|stale|blocked`. Conventions говорят `status=FAILED`; Python-исполнитель, глядя на JSON-контракт, напишет `failed`.

**AD-3 (уточнение).** `collector_runs.kind CHECK IN ('collect','backfill','funnel','norm','brief')` = имя job'а в `proxima-<kind>@<tenant>` буквально; `status CHECK IN ('RUNNING','SUCCEEDED','FAILED')` как в 007; в JSON-контрактах регистр нижний, маппинг в одном месте (`contracts/README`).

### H13. `run_id` у существующих `attempt_id`-таблиц: NULL или NOT NULL, CASCADE рядом с RESTRICT

**Пара:** U1 (011) ↔ U9 (delete-run), pa41-writer.

**Расхождение.** `fact_order_counts.attempt_id → fact_attempt_runs ON DELETE RESTRICT` (`007:47`). AD-3 добавляет `run_id … ON DELETE CASCADE` «additively» - у существующих строк `run_id` нет; NOT NULL невозможен без синтетических прогонов, NULL означает, что delete-run эти строки не видит, а RESTRICT на старом FK блокирует ручной откат. Writer из `pa41` заполняет только `attempt_id`.

**AD-3 (уточнение).** 011: `run_id uuid NULL REFERENCES collector_runs ON DELETE CASCADE` на `fact_attempt_runs`, `fact_order_counts`, `fact_lineage_records`, `quality_check_results`, `stg_quarantine_rows`, `wb_analytics_report_tasks`; адаптация pa41-writer обязана заполнять `run_id`; `delete-run --dry-run` печатает число строк с `run_id IS NULL` как «unmanaged» по каждой таблице.

### H14. Tenant: `amirova` в спайне, `amirova-test` в базе, `tenants` авто-создаётся любой строкой

**Пара:** U3 (`@amirova`) ↔ существующие `fact_order_counts`/`business_signal_runs` (`amirova-test`, API-FACTS §A), `tools/wb_async_report.py:296` (`INSERT INTO tenants … ON CONFLICT DO NOTHING` из CLI-аргумента).

**Расхождение.** Одна и та же касса под двумя `tenant_id`; M-04 join по tenant между `fact_cabinet_daily` и `fact_order_counts` даёт пустоту; опечатка в `--tenant` создаёт третьего tenant'а и RLS честно спрячет данные.

**AD-11 (уточнение).** 011: `tenants.wb_seller_sid uuid UNIQUE` (= `sid` из `seller-info`); job перед первой записью вызывает `seller-info` и fail-closed сверяет `sid` с `tenants` по `--tenant`; авто-вставка в `tenants` из job'ов запрещена (убрать из `wb_async_report.py` при адаптации). Строки `amirova-test` не переименовываются, помечаются в `tenants.notes` как разведка.

### H15. FixtureTransport: ключ поиска фикстуры против запросов с датой «сегодня»

**Пара:** U2 (FixtureTransport, record-fixture) ↔ U3/U5 (query строится от wall-clock).

**Расхождение.** AD-4: фикстуры `fixtures/wb-api/<api>/<endpoint>/*.json`; текущее именование `20260830T055939Z__dateFrom-2023-01-01_flag-0.json` (API-FACTS, лог). Collect строит `dateFrom = today-3` - каждый день новый query, фикстуры на него нет. U2 сделает поиск «по endpoint, первый файл» - тест перестанет проверять параметры; или «по точному query» - тест зелёный только 30.08. `record-fixture` не знает, какое имя ждёт FixtureTransport.

**AD-4 (уточнение).** Каждый job принимает `--now` (см. H6), тесты всегда передают фиксированный `--now`. `FixtureTransport` ищет по `manifest.json` в каталоге endpoint'а: `{method, path, query_canonical, body_sha256?, file}`; несовпадение = ошибка, без «ближайшего» файла. `record-fixture` пишет и файл, и запись манифеста из `wb_raw_artifacts.query_canonical`.

### H16. Бэкфилл: пагинация при 80k, курсор по неотсортированному ответу, строки февраля в ответе за март

**Пара:** U4 (backfill) ↔ U2 (реестр бюджетов), U3 (agregator).

**Расхождение.** Сегодня 26 недель = 13 325 orders / 10 611 sales - один ответ (API-FACTS TL;DR), но правило «что при ровно 80 000» в спайне отсутствует; существующий клиент берёт `pageRows.at(-1).lastChangeDate` как курсор (`wb-client.ts:150`) - предполагает сортировку ответа, WB её не гарантирует. `--from 2026-03-01 flag=0` фильтрует по `lastChangeDate`: в ответ попадают февральские заказы с мартовскими отменами (`date` в феврале) - без H1-floor U4 запишет «дни» февраля с `orders_count=0`. `wb_window_floor` (окно ~6 мес, на 30.08 = 01.03) нигде не фиксируется в прогоне - через месяц нельзя понять, почему ряд начинается с 01.03.

**AD-4/AD-5 (уточнение).** Реестр эндпоинта объявляет `page_limit` (80 000) и `cursor_field` (`lastChangeDate`); страница «полная» (`len == page_limit`) → следующий `dateFrom = max(cursor_field)` по странице, не последний элемент; повторные строки дедуплицируются по H1. `--from` = `period_floor` версий; `collector_runs.notes` backfill-прогона содержит `period_floor` и фактический `min(calendar_day)` ответа. Бюджет 1/мин на `sales` разделяется с `reportDetailByPeriod` только если оба в одном прогоне - реестр считает лимит per-endpoint, per-token; это записать.

---

## Сводка по единицам работы

| Единица | Дыры, в которых участвует |
|---|---|
| U1 миграции | H2, H4, H5, H7, H8, H9, H10, H12, H13, H14 |
| U2 WB-клиент | H5, H15, H16 |
| U3 collect | H1, H2, H3, H6, H12, H14, H16 |
| U4 backfill | H1, H16 |
| U5 funnel | H8, H15 |
| U6 norm | H1, H2, H3, H4, H6, H9 |
| U7 brief | H4, H7, H9, H10 |
| U8 webapp | H3, H7, H10 |
| U9 systemd/delete-run | H2, H4, H5, H6, H13 |
| U10 test-db/роли | H3, H11 |

Порядок закрытия: H1 и H2 (модель версий) → H3 (RLS) → H4/H5 (ledger) → H6 (TZ) → остальное. Без H1-H3 любая нарезка на единицы даст десять зелёных PR и красную сводку 30.09.
