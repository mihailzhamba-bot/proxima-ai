# API-FACTS: разведка WB API для PROXIMA AI

Сессия 1a, 30.08.2026, 05:59-06:11 UTC. Все вызовы с сервера `proxima` (`ssh -o BatchMode=yes`), токены из `/etc/proxima-ai/secrets/wb_*_token`, значения токенов не выводились и сервер не покидали. 18 вызовов, бюджет 35. Сессия 1b, 14:14 UTC: +2 вызова v3 `sales-funnel` по разрешению D16 (раздел «Воронка v3»), итого 20. Фикстуры: сервер `~/signal-inputs/fixtures/wb-api/`, копия в клоне `fixtures/wb-api/` (40 файлов, 436 МБ, untracked; `grep -rlE 'eyJ[A-Za-z0-9_-]{40,}' fixtures/` -> `clean` и на сервере, и на маке). Каждый факт ниже = вызов из лога в конце файла; чего не вызывал - помечено «не проверено».

## TL;DR

- **Ежедневный ряд продаж и заказов (Statistics API): 26 недель.** `sales` и `orders` с `dateFrom=2023-01-01&flag=0` отдают ряд с `2026-03-01` по сегодня (10 611 и 13 325 строк, потолок 80k не достигнут). `flag=1` по дню: `2026-02-28` отдаёт данные (77 продаж / 135 заказов), `2026-02-21` и `2026-02-15` - пустой массив. Окно скользящее, ~6 календарных месяцев назад; всё старше исчезает из API. Ряд непрерывный по месяцам (март-август по 1.7-2.6k строк/мес).
- **Воронка (просмотры, корзина): синхронно - только последние 7 дней.** v2 `POST /api/v2/nm-report/detail` и `/detail/history` -> `404 path not found` (путь снят, дедлайн миграции был 09.12.2025). Замена `POST /api/analytics/v3/sales-funnel/products/history` проверена 30.08 (D16): 200 за 24.08-30.08 с дневными записями (переходы, корзина, заказы, выкупы, конверсии - 11 полей; до 20 nmId за вызов, 3 вызова/мин), **400 `invalid start day: excess limit on days`** за 23.02-01.03. Спека: «максимум за последнюю неделю». Глубже недели - только async CSV `nm-report/downloads` (`DETAIL_HISTORY_REPORT`; по спеке до года и «только с подпиской Джем», глубина `startDate` не проверена).
- **Финотчёты (`reportDetailByPeriod`): 31 месяц, недельный разрез.** Первая страница (100 000 строк, 217 МБ) покрывает `2024-01-29..2025-10-18`, страница за 2026 (94 773 строки) - `2026-01-01..2026-08-23`, 34 недели. Последняя закрытая неделя `2026-08-17..2026-08-23` создана `2026-08-24`, лаг 1-8 дней.
- **`supplier/stocks` и `supplier/incomes` мертвы** (404 «This method is deprecated», «path not found»). Остатки - только через Analytics `stocks-report/wb-warehouses` (уже в коллекторе, не проверено).
- **Лимиты из заголовков:** `sales` 1/мин (429 после 32 с, `X-Ratelimit-Retry: 29`), `reportDetailByPeriod` 1/мин, `orders` 10, `seller-info` 10, `nm-report/downloads` 3. `X-Ratelimit-Reset` приходит только с 429.
- **Вердикт «>= 8 недель ежедневного ряда»: ДА** для продаж и заказов (26 недель). **НЕТ** для воронки: v3 отдаёт ровно последние 7 дней (проверено 30.08, D16), дневную историю глубже можно получить только через async CSV (`downloads`, квота 20 отчётов/день по коду репо).
- **Главный риск:** базы нормы по воронке к 30.09 не будет ни из одного источника: v3 не бэкфиллит (окно 7 дней), async CSV на глубину 6-12 мес не проверен. M-03 держится на заказах/продажах (D13), воронка - октябрь, и только если ежедневный сбор v3 или CSV стартует в первую неделю сентября: день, не снятый за 7 дней, из v3 пропадает. Второй риск: окно 6 мес означает, что история не копится сама - сбор надо запустить в сентябре, иначе к марту 2027 базы YoY не будет.

## A. Кабинет

`GET https://common-api.wildberries.ru/api/v1/seller-info`, statistics-токен, 05:59:04 UTC, 200, 139 B: `name` = «ИП Амирова О. Ф.», `tradeMark` = «ИП Амирова», `sid` = `a6836b3b-2db4-5dfb-b5d2-3987c12b8de9`. Подтверждено: все три токена того же кабинета (тенант `amirova-test`); аналитический и финансовый на другие хосты не проверялись отдельно, но `reportDetailByPeriod` прошёл на statistics-токене без 401, finance-токен не понадобился. В данных бренды `Meizel`, `Fanzo`, `Funny Elf`, первая `order_dt` в финотчётах `2023-12-03`.

## B/C. Таблица эндпоинтов

| Метод + путь | Токен | Ключевые поля | Проверенная глубина назад | Лимит (заголовки) | Ответ | Фикстура (`fixtures/wb-api/`) |
|---|---|---|---|---|---|---|
| GET common-api `/api/v1/seller-info` | statistics | name, tradeMark, sid, tin | n/a | limit 10, remaining 9 | 139 B, 0.08 s | `common/seller-info/20260830T055904Z__statistics-token.json` |
| GET statistics `/api/v1/supplier/sales` | statistics | date, lastChangeDate, nmId, supplierArticle, barcode, brand, subject, warehouseName, totalPrice, discountPercent, spp, priceWithDisc, finishedPrice, forPay, paymentSaleAmount, saleID (S/R), srid, isRealization (28 полей) | flag=0: `2026-03-01T05:51:52` .. `2026-08-30T07:01:10`, 10 611 строк; flag=1: 02-28 = 77, 02-21 = 0, 02-15 = 0 | limit 1, remaining 0; 429: reset 29, retry 29 | 8.77 МБ, 0.84 s | `statistics/supplier-sales/20260830T055939Z__dateFrom-2023-01-01_flag-0.json` (+4 flag=1) |
| GET statistics `/api/v1/supplier/orders` | statistics | как sales минус forPay/paymentSaleAmount/saleID, плюс isCancel, cancelDate (27 полей) | flag=0: `2026-03-01T00:51:40` .. `2026-08-30T06:39:33`, 13 325 строк; flag=1 02-28 = 135 | limit 10, remaining 9 | 10.85 МБ, 18.65 s | `statistics/supplier-orders/20260830T060041Z__dateFrom-2023-01-01_flag-0.json` |
| GET statistics `/api/v1/supplier/stocks` | statistics | - | **404 deprecated** | нет заголовков лимита | 258 B | `statistics/supplier-stocks/20260830T060148Z__dateFrom-2023-01-01.json` |
| GET statistics `/api/v1/supplier/incomes` | statistics | - | **404 path not found** | нет | 170 B | `statistics/supplier-incomes/20260830T060153Z__dateFrom-2023-01-01.json` |
| GET statistics `/api/v5/supplier/reportDetailByPeriod` | statistics (finance не понадобился) | 96 полей: realizationreport_id, date_from/date_to/create_dt, rr_dt, rrd_id, nm_id, doc_type_name (Продажа/Возврат/''), supplier_oper_name, quantity, retail_price, retail_amount, retail_price_withdisc_rub, ppvz_for_pay, ppvz_sales_commission, delivery_rub, storage_fee, penalty, deduction, acceptance, order_dt, sale_dt, srid | стр.1 (rrdid=0, limit 100000): rr_dt `2024-01-29..2025-10-18`, ровно 100 000 строк = потолок, 32 526 строк «Продажа»; 2026: rr_dt `2026-01-01..2026-08-23`, 94 773 строки, 34 недели, 15 774 «Продажа», retail_amount 13.72 M₽. Хвост `2025-10-19..2025-12-31` не вытянут (нужна пагинация rrdid) | limit 1, remaining 0 | 217.5 МБ 24.4 s; 211.3 МБ 25.8 s | `statistics/reportDetailByPeriod/20260830T060158Z__dateFrom-2023-01-01_...json`, `...20260830T060458Z__dateFrom-2026-01-01_...json` |
| POST analytics `/api/v2/nm-report/detail` | analytics (RW, только чтение) | - | **404 path not found**, 4 периода (20 мес, 6 мес, 3 мес, 1 мес) | нет | 176 B | `analytics/nm-report-detail/*.json` |
| POST analytics `/api/v2/nm-report/detail/history` | analytics | - | **404 path not found** (nmIDs 168118957, 686893199, 230474773 - топ-3 по priceWithDisc из фикстуры sales) | нет | 176 B | `analytics/nm-report-detail-history/20260830T060835Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` |
| GET analytics `/api/v2/nm-report/downloads` | analytics | data[]: id, status, name, size, startDate, endDate, createdAt | список: 2 отчёта `detail_history_report`, SUCCESS, окна `08-25..08-30` (создан `2026-08-30 00:51:06`) и `08-24..08-29` (`2026-08-29 00:53:37`), 8.3-8.5 КБ | limit 3, remaining 2 | 391 B, 0.12 s | `analytics/nm-report-downloads/20260830T060719Z__list.json` |
| POST analytics `/api/analytics/v3/sales-funnel/products/history` | analytics | product{nmId, title, vendorCode, brandName, subjectId, subjectName}, history[]{date, openCount, cartCount, orderCount, orderSum, buyoutCount, buyoutSum, buyoutPercent, addToCartConversion, cartToOrderConversion, addToWishlistCount}, currency | `2026-08-24..2026-08-30` = 7 дневных записей на каждый из 3 nmId; `2026-02-23..2026-03-01` = **400 `invalid start day: excess limit on days`** (спека: «максимум за последнюю неделю») | limit 3, remaining 2 (спека: 3/мин, интервал 20 с, всплеск 3) | 5 188 B, 0.88 s; 332 B, 0.08 s | `analytics/sales-funnel-v3-history/*.json` |

Не проверено (вне allowlist сессии): `POST /api/analytics/v3/sales-funnel/products` (агрегат за период до 365 дней с `pastPeriod`, без дневного разреза) и `/grouped/history`; `POST /api/analytics/v1/stocks-report/wb-warehouses`; `POST finance-api /api/finance/v1/sales-reports/detailed`; создание отчётов `POST nm-report/downloads`; скачивание `GET nm-report/downloads/file/{id}`; глубина `startDate` для async-отчёта.

## Ошибки и ограничения дословно

- `supplier/stocks`, 404, `application/problem+json`: `{"status":404,"statusText":"Not Found","title":"Not Found","detail":"This method is deprecated. Link: https://dev.wildberries.ru/release-notes?id=494","requestId":"bd8e4660c9f09fb7f54c19827f6d819b","origin":"ag-statistics"}`.
- `supplier/incomes`, 404: `{"detail":"Please consult the https://dev.wildberries.ru/openapi/api-information","origin":"ag-statistics","status":404,"statusText":"Not Found","title":"path not found"}`.
- `nm-report/detail` и `nm-report/detail/history`, 404, все 5 вызовов одинаково: `{"detail":"Please consult the https://dev.wildberries.ru/openapi/api-information","origin":"ag-contentanalytics","status":404,"statusText":"Not Found","title":"path not found"}`. Ошибки про длину периода получить не удалось - путь отсутствует целиком.
- `supplier/sales`, 429 (второй вызов через 32 с после предыдущего): `{"status":429,"statusText":"Too Many Requests","title":"Too Many Requests","detail":"rate limit exceeded, retry after the period specified in the X-RateLimit-Retry header","requestId":"1d80f4f389f047c0bdb00abc603fee02","origin":"ag-statistics"}`; заголовки `x-ratelimit-limit: 1`, `x-ratelimit-remaining: 0`, `x-ratelimit-reset: 29`, `x-ratelimit-retry: 29`. Это моя ошибка в темпе, не поведение API; после 429 эндпоинт больше не вызывался, бисекция границы окна на `2026-02-27` не сделана.
- Окно Statistics: `flag=0` фильтрует по дате продажи/заказа, не только по `lastChangeDate` - продажи 28.02 с `lastChangeDate` до `2026-03-14` в выборке `flag=0` отсутствуют. Граница между `02-21` (пусто) и `02-28` (данные есть); «сегодня минус 6 календарных месяцев» = `02-28` сходится, но точный алгоритм WB не подтверждён.
- `reportDetailByPeriod`: `limit=100000` - реальный потолок страницы (страница 1 вернула ровно 100 000), дальше только `rrdid` = последний `rrd_id` страницы (`3046950521984`); одна страница = 210-220 МБ и 25 с, полный бэкфилл 31 мес = 3-4 страницы при 1 вызове/мин.
- Заголовок `x-ratelimit-reset` на 200-ответах не приходит; `Retry-After` не встречался ни разу.
- Analytics-токен на сервере read-write; кто-то создаёт `detail_history_report` ежедневно около 00:51 МСК (окна по 6 дней) - на сервере нет ни таймера, ни cron, ни процесса под это (`systemctl list-timers`, `crontab -l`, `ps` 30.08). Потребитель токена вне сервера - вопрос в INVENTORY/бэклог PA-13 (ротация на read-only).

## D. Что уже написано в репо

| Эндпоинт | Код | Хранение |
|---|---|---|
| common `ping`, `seller-info`; `ping` statistics/analytics/finance/prices/promotion | `tools/wb_api_probe.py:72-82` (`ENDPOINTS`, `CATEGORY_PINGS`), `run_probe` `:292-394`, проверка JWT-скоупов `decode_token_claims` `:135-166` | content-addressed JSON в `/srv/proxima-ai/data/day1-wb-api/sha256/`, без БД |
| statistics `supplier/sales` (`flag=0`, 7 дней по lastChangeDate) | `tools/wb_api_probe.py:374-393`; `services/collector/src/business-signal/wb-client.ts:113-155` `WbSignalClient.sales` (курсор по lastChangeDate, страница 80 000, пауза 60 с, окно МСК `date-window.ts`) | `business_signal_raw_artifacts`, `business_signal_runs` (`db/migrations/004`), `fact_order_counts` nm_id x calendar_day (`007`) |
| analytics `POST /api/analytics/v1/stocks-report/wb-warehouses` | `wb-client.ts:157-190` `stocks` (offset-пагинация 250 000, пауза 20 с) | `business_signal_runs.stock_quantity/stock_as_of` |
| finance `POST /api/finance/v1/sales-reports/detailed` | `wb-client.ts:192-243` `finance` (rrdId-пагинация 100 000, пауза 60 с, терминатор 204); маржа в `calculate.ts:18` `calculateMargins` | `business_signal_raw_artifacts` |
| analytics `nm-report/downloads` create/status/file/retry (DETAIL_HISTORY_REPORT, day, последняя закрытая неделя) | `tools/wb_async_report.py` (`API_ROOT :32`, квота 20/день `:35`, poll 21 с `:34`, `AsyncReportCollector :652`) | `wb_analytics_report_tasks`, `wb_analytics_quota_events`, `raw_wb_analytics_responses` (`003`), `stg_wb_nm_report_rows` nm_id x row_date (`005`) |
| statistics `supplier/stocks`, `v5/reportDetailByPeriod` | запрещены гейтом `tools/verify_business_signal.py:27-29` («deprecated endpoint entered signal runtime») | - |
| statistics `supplier/orders`, v3 `sales-funnel/*` | нигде не используются | - |
| ручной XLSX-интейк WB | `services/collector/src/intake/manual-wb-xlsx.ts`, CLI `cli/manual-wb-xlsx-intake.ts` | `source_artifacts`, `artifact_manifests`, `intake_attempts` (`002`) |
| контракты | `contracts/source-artifact.schema.json` enum `source`: `official_wb_manual/statistics/analytics/finance`, `torgstat_supporting` | TS-типы `services/collector/src/contracts/` (codegen) |

Итого: продажи и финотчёт собираются, но в окне 7 дней под один сигнал (stockout); ни бэкфилла на 6 месяцев, ни ежедневного инкремента, ни таблицы дневного ряда продаж/заказов в миграциях нет. `wb_api_probe.py` и `wb_async_report.py` рабочие, обвязка (`prepare-day1-runtime.sh`, venv на сервере) есть по README.

## E. План Б по глубине

Условие D6 (>= 8 недель ежедневного ряда) для продаж/заказов выполнено: 26 недель. План Б нужен только для воронки (просмотры, корзина, конверсии), где синхронного метода нет и глубина не подтверждена. Варианты для заказчика, не решение:

1. **Копить N недель через async CSV (`nm-report/downloads`, уже написано в `wb_async_report.py`).** Старт 01.09: 4 недели к 29.09, 8 недель к 27.10. К 30.09 база нормы по воронке не успевает; отклонения по воронке уезжают в октябрь (M-04). Затраты: включить ежедневный запуск, квота 20 отчётов/день хватает на 1 кабинет с запасом. Неизвестно, как далеко назад принимает `startDate` (не проверено - возможно, один отчёт за 6 мес закроет бэкфилл сразу).
2. **Норма на финотчётах `reportDetailByPeriod`.** 31 месяц, есть YoY и сезонность, но разрез недельный и лаг 1-8 дней: «минус 23% против обычного вторника» на них не построить, только «неделя против типичной недели» и деньги (forPay, комиссия, логистика, хранение). Готово к использованию сразу, бэкфилл 3-4 страницы по 200+ МБ, 5 минут.
3. **Переопределить норму под доступную глубину: продажи и заказы из Statistics.** «Обычный вторник» = медиана того же дня недели за последние 8-12 недель по `orders`/`sales` (шт., приценка `priceWithDisc`, `forPay`). Данные есть уже сегодня, 30.09 реалистичен; воронка добавляется позже как второй слой. Обязательное условие: запустить ежедневный сбор в первую неделю сентября, потому что окно API скользящее и март 2026 выпадет из API в начале сентября.

Рекомендация к Воротам 1: вариант 3 как основа M-02/M-03 + вариант 1 в фоне с первого дня + отдельное разрешение на одну проверку `v3/sales-funnel/products/history` (2 вызова: неделя назад и 12 месяцев назад) - это снимает главный риск. Проверка выполнена 30.08 (D16), результат в разделе «Воронка v3»: истории нет, вариант 1 остаётся единственным путём к глубине.

## Воронка v3 (30.08.2026, D16)

Сессия 1b, 14:14 UTC, 2 вызова по разрешению Mike (D16), оба с сервера `proxima`, analytics-токен `/etc/proxima-ai/secrets/wb_analytics_token`. Фикстуры: сервер `~/signal-inputs/fixtures/wb-api/analytics/sales-funnel-v3-history/`, копия в клоне (4 файла, `grep -rlE 'eyJ[A-Za-z0-9_-]{40,}'` -> `clean` на сервере и на маке).

**Спека.** `dev.wildberries.ru/openapi/analytics` (раздел «Воронка продаж») на fetch отдаёт 498; контракт взят из зеркала OpenAPI-спеки WB `github.com/eslazarev/wildberries-sdk`, файл `specs/11-analytics.yaml` (`info.title` «Аналитика и данные»), коммит `75743e63` от 25.08.2026. Описание метода дословно совпадает с поисковой выдачей по `dev.wildberries.ru/en/docs/openapi/analytics`.

- `POST https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history`, тело `ItemHistoryRequest`: `selectedPeriod{start, end}` (даты `YYYY-MM-DD`, обязательно), `nmIds` (uint64[], 1..20, обязательно), `aggregationLevel` (`day` | `week`, по умолчанию `day`), `skipDeletedNm` (bool).
- Ограничения по спеке: «можно получить данные максимум за последнюю неделю»; обновление 1 раз в час; большая часть заказов/переходов/корзин появляется в течение часа, «малая часть - в течение нескольких дней»; выкупы, отмены и возвраты пишутся в день заказа. Лимит на аккаунт: 3 запроса/мин, интервал 20 с, всплеск 3 (персональный, сервисный, базовый с секретом); базовый токен - 2 запроса/ч. Коды ответов: 200, 400, 401, 402 (только для решений из каталога WB), 403, 429.
- Соседи: `POST …/v3/sales-funnel/products` - агрегат за период с сравнением `pastPeriod`, до 365 дней назад, пагинация, но без разреза по дням; `POST …/v3/sales-funnel/grouped/history` - дневной разрез по группам карточек. Для «периода до года» спека отправляет в CSV-отчёты `DETAIL_HISTORY_REPORT` (`nm-report/downloads`) с пометкой «доступны только с подпиской Джем».

**Вызовы (UTC).**

| Время | Период, параметры | Код | Время | Байт | Заголовки лимита | Файл (`fixtures/wb-api/analytics/sales-funnel-v3-history/`) |
|---|---|---|---|---|---|---|
| 14:14:24 | `2026-08-24..2026-08-30`, nmIDs [686893199, 168118957, 230474773], day | 200 | 0.88 s | 5 188 | `x-ratelimit-limit: 3`, `x-ratelimit-remaining: 2` | `20260830T141424Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` |
| 14:14:57 | `2026-02-23..2026-03-01`, те же nmIDs, day | 400 | 0.08 s | 332 | `limit: 3`, `remaining: 2` | `20260830T141457Z__nmIDs-3_period-2026-02-23_2026-03-01_day.json` |

nmIDs - топ-3 по числу строк в фикстуре `supplier-sales` (745 / 568 / 433 строк), тот же набор, что в v2-вызове 06:08. Ошибка 400 дословно: `{"title":"Invalid request body","detail":"code=400, message={Invalid request body validate: invalid start day: excess limit on days d1b265d8-6b48-4a3e-804a-86a1cdbdaede analytics-open-api}, internal=validate: invalid start day: excess limit on days","requestId":"d1b265d8-6b48-4a3e-804a-86a1cdbdaede","origin":"analytics-open-api"}`. `x-ratelimit-reset` / `retry` не приходили; `remaining` через 33 с снова 2 - слот вернулся по интервалу 20 с либо 400 не списывается, без третьего вызова не различить.

**Глубина назад: 7 дней, февраль-март недоступен.** `start = сегодня - 6` (24.08) прошёл и вернул по 7 дневных записей на nmId, включая текущий неполный день 30.08 (14:14 UTC: 152 перехода у 686893199 против 214-271 в полные дни); `start = 23.02` отклонён валидатором до обращения к данным. Точная граница (`start = сегодня - 7`, 8 дней) не бисектирована - бюджет 2 вызова.

**Структура ответа** (`ItemHistoryResponse`): массив по nmId; элемент = `product{nmId, title, vendorCode, brandName, subjectId, subjectName}` + `history[]` + `currency` (`RUB`). Дневная запись `history[]` - 11 полей, все целые: `date`, `openCount` (переходы в карточку), `cartCount`, `orderCount`, `orderSum`, `buyoutCount`, `buyoutSum`, `buyoutPercent`, `addToCartConversion` (%, целое), `cartToOrderConversion` (%, целое), `addToWishlistCount`. Показов (impressions) в v3 нет. Сумма за 24-30.08 по 686893199: 1 616 переходов, 141 корзина, 12 заказов на 17 303 ₽, 4 выкупа (выкупы неполные - считаются по дню заказа); по 168118957: 166 переходов, 1 корзина, 0 заказов.

**Вывод для плана Б (D13).** v3 - не история, а скользящее окно 7 дней: ежедневный инкремент, бэкфилла не даёт. Базу нормы по воронке (8 недель) он не построит ни к 30.09, ни к 27.10 без ежедневного сбора - день, не снятый за неделю, из API пропадает. Что это меняет в D13:

1. Бэкфилл глубже недели - по-прежнему только async CSV `DETAIL_HISTORY_REPORT` (вариант 1, без изменений). По спеке он и предназначен для «периода до года», но с оговоркой про подписку Джем; на кабинете ежедневные `detail_history_report` с окнами 6 дней создаются и получают SUCCESS - либо Джем есть, либо короткие окна проходят без него. `startDate` на 6-12 мес назад не проверен: отдельное разрешение, 3 вызова (create + status + file).
2. Ежедневный сбор v3 стоит запустить с первой недели сентября параллельно CSV как дневной источник воронки без парсинга CSV: 201 nmId в кабинете (уникальные `nmId` в `orders` flag=0) = 11 вызовов по 20 nmId, при 3/мин - 4 минуты в день; каждый день перекрывается 7 раз, что ловит «малую часть данных, которая появляется в течение нескольких дней».
3. Для M-03 (30.09) ничего не меняется: норма по заказам/продажам из Statistics; по воронке уже с 01.09 доступно только «вчера против последних 6 дней», полноценная норма - конец октября при сборе без пропусков.

## Лог вызовов (UTC 30.08.2026)

| Время | Эндпоинт | Параметры | Код | Время | Байт | Файл (`fixtures/wb-api/`) |
|---|---|---|---|---|---|---|
| 05:59:04 | GET common `seller-info` | statistics-токен | 200 | 0.08 s | 139 | `common/seller-info/20260830T055904Z__statistics-token.json` |
| 05:59:39 | GET statistics `supplier/sales` | dateFrom=2023-01-01T00:00:00&flag=0 | 200 | 0.84 s | 8 766 279 | `statistics/supplier-sales/20260830T055939Z__dateFrom-2023-01-01_flag-0.json` |
| 06:00:41 | GET statistics `supplier/orders` | dateFrom=2023-01-01T00:00:00&flag=0 | 200 | 18.65 s | 10 854 000 | `statistics/supplier-orders/20260830T060041Z__dateFrom-2023-01-01_flag-0.json` |
| 06:01:48 | GET statistics `supplier/stocks` | dateFrom=2023-01-01T00:00:00 | 404 | 0.06 s | 258 | `statistics/supplier-stocks/20260830T060148Z__dateFrom-2023-01-01.json` |
| 06:01:53 | GET statistics `supplier/incomes` | dateFrom=2023-01-01T00:00:00 | 404 | 0.04 s | 170 | `statistics/supplier-incomes/20260830T060153Z__dateFrom-2023-01-01.json` |
| 06:01:58 | GET statistics `v5/reportDetailByPeriod` | dateFrom=2023-01-01&dateTo=2026-08-30&limit=100000&rrdid=0 | 200 | 24.40 s | 217 458 289 | `statistics/reportDetailByPeriod/20260830T060158Z__dateFrom-2023-01-01_dateTo-2026-08-30_limit-100000_rrdid-0_statistics-token.json` |
| 06:02:34 | GET statistics `supplier/sales` | dateFrom=2026-02-15&flag=1 | 200 | 0.08 s | 2 | `statistics/supplier-sales/20260830T060234Z__dateFrom-2026-02-15_flag-1.json` |
| 06:04:58 | GET statistics `v5/reportDetailByPeriod` | dateFrom=2026-01-01&dateTo=2026-08-30&limit=100000&rrdid=0 | 200 | 25.79 s | 211 293 715 | `statistics/reportDetailByPeriod/20260830T060458Z__dateFrom-2026-01-01_dateTo-2026-08-30_limit-100000_rrdid-0_statistics-token.json` |
| 06:05:32 | GET statistics `supplier/sales` | dateFrom=2026-02-28&flag=1 | 200 | 0.54 s | 62 967 | `statistics/supplier-sales/20260830T060532Z__dateFrom-2026-02-28_flag-1.json` |
| 06:05:33 | POST analytics `nm-report/detail` | period 2025-01-01..2026-08-30, page 1 | 404 | 0.04 s | 176 | `analytics/nm-report-detail/20260830T060533Z__period-2025-01-01_2026-08-30_page-1.json` |
| 06:05:54 | POST analytics `nm-report/detail` | period 2026-03-01..2026-08-30 | 404 | 0.05 s | 176 | `analytics/nm-report-detail/20260830T060554Z__period-2026-03-01_2026-08-30_page-1.json` |
| 06:06:16 | POST analytics `nm-report/detail` | period 2026-06-01..2026-08-30 | 404 | 0.04 s | 176 | `analytics/nm-report-detail/20260830T060616Z__period-2026-06-01_2026-08-30_page-1.json` |
| 06:06:37 | POST analytics `nm-report/detail` | period 2026-08-01..2026-08-30 | 404 | 0.05 s | 176 | `analytics/nm-report-detail/20260830T060637Z__period-2026-08-01_2026-08-30_page-1.json` |
| 06:07:19 | GET analytics `nm-report/downloads` | без параметров | 200 | 0.12 s | 391 | `analytics/nm-report-downloads/20260830T060719Z__list.json` |
| 06:08:35 | POST analytics `nm-report/detail/history` | nmIDs [168118957, 686893199, 230474773], 2026-08-24..2026-08-30, day | 404 | 0.05 s | 176 | `analytics/nm-report-detail-history/20260830T060835Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` |
| 06:08:35 | GET statistics `supplier/sales` | dateFrom=2026-02-21&flag=1 | 200 | 0.09 s | 2 | `statistics/supplier-sales/20260830T060835Z__dateFrom-2026-02-21_flag-1.json` |
| 06:08:38 | GET statistics `supplier/orders` | dateFrom=2026-02-28&flag=1 | 200 | 0.19 s | 108 338 | `statistics/supplier-orders/20260830T060838Z__dateFrom-2026-02-28_flag-1.json` |
| 06:09:07 | GET statistics `supplier/sales` | dateFrom=2026-02-27&flag=1 | 429 | 0.55 s | 279 | `statistics/supplier-sales/20260830T060907Z__dateFrom-2026-02-27_flag-1.json` |
| 14:14:24 | POST analytics `v3/sales-funnel/products/history` | nmIds [686893199, 168118957, 230474773], selectedPeriod 2026-08-24..2026-08-30, day (D16) | 200 | 0.88 s | 5 188 | `analytics/sales-funnel-v3-history/20260830T141424Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` |
| 14:14:57 | POST analytics `v3/sales-funnel/products/history` | те же nmIds, selectedPeriod 2026-02-23..2026-03-01, day (D16) | 400 | 0.08 s | 332 | `analytics/sales-funnel-v3-history/20260830T141457Z__nmIDs-3_period-2026-02-23_2026-03-01_day.json` |

Пропущенные по плану вызовы: 3 глубинных `detail/history` (3/6/12 мес) - не выполнялись, потому что базовый вызов вернул 404; finance-токен для `reportDetailByPeriod` - не понадобился (statistics-токен прошёл).

## flag=0 семантика (31.08.2026, Story 1.0)

Два read-вызова с сервера (`dateFrom=2026-08-28T00:00:00&flag=0`, D22): `orders` - 172 строки, `date` от 06.08 до 31.08, все `lastChangeDate` ≥ 28.08, **69 строк с `date < dateFrom`** → фильтр по `lastChangeDate`, допущение AD-4 подтверждено, `dateFrom = run_day-3` остаётся. `sales` - 108 строк, `date` 28-31.08, 0 строк раньше окна (обновления продаж реже). Уникальность ключей: `srid` 172/172, `saleID` 108/108 (и 13 325/13 325, 10 611 - на полных фикстурах 30.08 с учётом пар продажа+возврат по разным `saleID`). Фикстуры: `~/signal-inputs/fixtures/wb-api/statistics/supplier-{orders,sales}/*step0.json`.

## Артефакты для бэкфилла (Story 1.5 / 1.14)

| Файл (VPS `~/signal-inputs/fixtures/wb-api/statistics/`) | sha256 | retrieved_at |
|---|---|---|
| `supplier-sales/20260830T055939Z__dateFrom-2023-01-01_flag-0.json` | `77c99ddac2bbcf3fcedcecc0a386a5abb5727c2f213d38950b89a6916e13fc29` | 2026-08-30T05:59:39Z |
| `supplier-orders/20260830T060041Z__dateFrom-2023-01-01_flag-0.json` | `d2d0ecfed34b67dd0e4b4dc34228fa434d102b190ce18f8f27686987e76aa03e` | 2026-08-30T06:00:41Z |
| `supplier-sales/20260831T155341Z__dateFrom-2023-01-01_flag-0.json` | `d2f1dc9581ad1f1ab67d1f7ac874b1fa93109915a06d3b09505d960e0b65ec96` | 2026-08-31T15:53:41Z |
| `supplier-orders/20260831T155341Z__dateFrom-2023-01-01_flag-0.json` | `0c0318ff835d59e263a32cd1f565d8f899e28173e4eacc942c414756214daa40` | 2026-08-31T15:53:41Z |

Импорт в CAS - `tools/cas_import.ts` в Story 1.14 (runbook). `run_day` = дата `retrieved_at` артефакта; бэкфилл берёт самую свежую пару (31.08: sales 8.8 МБ, orders 10.9 МБ, оба ряда по-прежнему с 2026-03-01). Снапшот 31.08 снят как страховка непрерывности ряда до запуска ежедневного сбора.

## Формат бэкапа (31.08.2026, факт)

`/var/backups/proxima/YYYY-MM-DD-{proxima,proxima_dev}.sql.gz` - локально **plain gzip, без age**; age-ключи (`backup_age_key.txt` 0600 root, `backup_age_recipient` 0644) используются скриптом только для S3-копии. `proxima-pg-backup.sh` снят в `infra/backup/` (sha256 `d29feb24…`). Для `proxima-restore-check@` локальный дамп: `gunzip | psql` без age; AD-17 уточнён.

## Остатки (02.09.2026, OQ-13)

Разведка по разрешению Mike 02.09.2026 (план «проверка PRD v2», ветка 3): три read-вызова с сервера токеном категории «Аналитика» (`/etc/proxima-ai/secrets/wb_analytics_token`, подстановка через `sudo -n cat`, значение не выводилось). Ответы и заголовки ответов - фикстуры на VPS, без заголовков авторизации. В БД и код ничего не записано. Поводом были факты из зеркала спецификации OpenAPI (ресёрч R2, уверенность средняя); ниже - что подтвердилось живым вызовом.

| Вызов | Статус | Что вернул | Лимит из заголовков | Размер, время | Фикстура |
|---|---|---|---|---|---|
| `POST analytics /api/analytics/v1/stocks-report/wb-warehouses`, тело `{"params":{"nmIDs":[],"limit":50,"offset":0}}` (форма из `wb-client.ts:166`) | **200** | `data.items[]` - 444 строки с полями `nmId`, `chrtId`, `warehouseId`, `warehouseName`, `regionName`, `quantity`, `inWayToClient`, `inWayFromClient`; пустой `nmIDs` отдаёт весь кабинет, строка = размер × склад; `limit` ограничивает не строки (444 > 50), вероятно - число nmId на страницу (не проверено) | `x-ratelimit-limit: 1`, `x-ratelimit-remaining: 0` - **измеренный лимит 1 запрос на окно** (период окна в заголовках не назван; зеркало спецификации давало 3/мин - расхождение) | 76 608 B, 1.89 s | `analytics/stocks-report-wb-warehouses/20260902T130436Z__stocks_probe.json` |
| `POST analytics /api/v2/nm-report/downloads`, `reportType: STOCK_HISTORY_DAILY_CSV`, `params` как у `DETAIL_HISTORY_REPORT` (`nmIDs`, `startDate`, `endDate`, `timezone`, `aggregationLevel`) | **400** `Invalid request body` | `decode CSVDailyStocksParams: … decode field "params": invalid: currentPeriod (field required), stockType (field required), skipDeletedNm (field required)` - тип отчёта **существует и распознан**, отказа по подписке нет; тело должно нести `currentPeriod`, `stockType`, `skipDeletedNm` (те же параметры, что у метода остатков в спецификации). Задача не создана, квота не потрачена | `x-ratelimit-limit: 3`, `remaining: 2` (3/мин, как на 30.08) | 289 B, 0.62 s | `analytics/nm-report-downloads/20260902T130459Z__create_stock_history.json` |
| `GET analytics /api/v2/nm-report/downloads` | **200** | `data[]` - 2 задачи, обе `detail_history_report`, `SUCCESS`, окна `08-28..09-02` (создана `2026-09-02 01:04:29`) и `08-27..09-01` (`2026-09-01 01:03:43`), ~8 КБ - внешний потребитель токена продолжает создавать отчёт ежедневно (D20) | `x-ratelimit-limit: 3`, `remaining: 2` | 391 B, 0.51 s | `analytics/nm-report-downloads/20260902T130520Z__list.json` |

Выводы для реестра AD-4 и OQ-13:

- **Срез остатков по складам есть** и уже пригоден для `fact_stock_daily` при ежедневном снимке: поля дают остаток и «в пути» по каждому размеру и складу с регионом. Лимит по заголовку - 1 запрос на окно; пагинация по `offset` при полном кабинете (444 строк за один ответ при `limit 50`) требует отдельной проверки семантики `limit`. Кандидат на включение в реестр (новый AD, OQ-13).
- **Дневная история остатков через CSV `STOCK_HISTORY_DAILY_CSV` доступна на этом токене без подписки «Джем»** (отказа по подписке не было); обязательные параметры - `currentPeriod`, `stockType`, `skipDeletedNm`. Глубина `currentPeriod` и формат CSV не проверены: нужен один повторный вызов с исправленным телом и скачивание файла.
- Расхождение с зеркалом спецификации: лимит `stocks-report` 1 (заголовок) против 3/мин (зеркало). Приоритет у живого замера; в PRD и отчёте R2 уверенность по лимиту понижена.

### Лог вызовов (UTC 02.09.2026)

| Время | Вызов | Тело / параметры | Статус | Время | Байт | Фикстура |
|---|---|---|---|---|---|---|
| 13:04:36 | POST analytics `stocks-report/wb-warehouses` | `nmIDs: [], limit 50, offset 0` | 200 | 1.89 s | 76 608 | `analytics/stocks-report-wb-warehouses/20260902T130436Z__stocks_probe.json` |
| 13:04:59 | POST analytics `nm-report/downloads` | `STOCK_HISTORY_DAILY_CSV`, params в форме DETAIL_HISTORY_REPORT | 400 | 0.62 s | 289 | `analytics/nm-report-downloads/20260902T130459Z__create_stock_history.json` |
| 13:05:20 | GET analytics `nm-report/downloads` | - | 200 | 0.51 s | 391 | `analytics/nm-report-downloads/20260902T130520Z__list.json` |
| 13:10:44 | POST analytics `nm-report/downloads` | `STOCK_HISTORY_DAILY_CSV`, `params: {currentPeriod: {start: 2026-08-26, end: 2026-09-01}, stockType: "", skipDeletedNm: true}` | 200 `{"data": "Началось формирование файла/отчета"}` | 0.87 s | 77 | `analytics/nm-report-downloads/20260902T131044Z__create_stock_history_v2.json` |
| 13:11:50 | GET analytics `nm-report/downloads` | - | 200; задача `SUCCESS` через ~65 с | 0.51 s | 568 | `analytics/nm-report-downloads/20260902T131150Z__list_after_create.json` |
| 13:11:51 | GET analytics `nm-report/downloads/file/{id}` | - | 200, `application/zip` | 0.59 s | 12 203 | `analytics/nm-report-downloads/20260902T131151Z__download_stock_history.bin` |

## async CSV глубина (проба Story 3.0, 08.09.2026)

Выполнено оркестратором с VPS по исключению из решения 7а (D32), analytics-токен read-write (`wb_analytics_token`), ответы и заголовки сохранены в `~/signal-inputs/fixtures/wb-api/analytics/nm-report-downloads/20260908T06*__probe30_*`. Запросов всего 6: список до создания, create с телом без `id` (400), create, два status, file; отчётов создано 1 (квота D20: 1 из 20 в сутки).

| Факт | Значение | Источник |
|---|---|---|
| `POST nm-report/downloads` без клиентского `id` | **400** `{"title":"Invalid request body","detail":"invalid: id (field required)"}` - `id` (UUID клиента) обязателен, как в `tools/wb_async_report.py` `build_request` | `20260908T061830Z__probe30_create.json` |
| Максимальный `startDate` для `DETAIL_HISTORY_REPORT` | **6 месяцев принято**: `startDate: 2026-03-08`, `endDate: 2026-09-07`, `aggregationLevel: day`, `nmIDs: []` → 200 `{"data":"Началось формирование файла/отчета"}`; спека «до года» глубже не проверялась | `20260908T062012Z__probe30_create2.request.json`, `…__probe30_create2.json` |
| Время готовности | `SUCCESS` через **≈95 с** после создания (создан 06:20:12, первый status 06:21:48 уже SUCCESS) | `…__probe30_status1.json` |
| Размер | ZIP **289 118 байт**, один CSV `<id>.csv`, **32 172 строки** данных, **184 дня** (2026-03-08..2026-09-07), **328 nmId** | `…__probe30_file.bin` |
| Колонки CSV (`DETAIL_HISTORY_REPORT`, day) | `nmID, dt, openCardCount, addToCartCount, ordersCount, ordersSumRub, buyoutsCount, buyoutsSumRub, cancelCount, cancelSumRub, addToCartConversion, cartToOrderConversion, buyoutPercent, addToWishlist, currency` - длинный формат (строка на nmId × день), в отличие от широкого `STOCK_HISTORY_DAILY_CSV` (02.09) | заголовок CSV в `…__probe30_file.bin` |
| Поле `name` в списке | равно `userReportName` запроса (`proxima-probe30-2026-03-08-2026-09-07`); отчёты внешнего потребителя называются `detail_history_report` → guard Story 3.2 по префиксу `proxima-<tenant>-` возможен | `…__probe30_status1.json` |
| Часовой пояс `createdAt` | **UTC**: `createdAt: 2026-09-08 06:20:12` при create в 06:20:13Z; чтение D20 (UTC → день МСК) подтверждено | `…__probe30_status1.json` + журнал `logs/day-2026-09-08/probe-3.0.log` |
| Лимиты | `x-ratelimit-limit: 3`, `remaining: 2` на всех вызовах (3/мин, как 30.08 и 02.09) | заголовки `.headers` |
| Внешний потребитель | в списке до создания 2 отчёта `detail_history_report` за 2026-09-03..08 (создан 2026-09-08 00:50:38 UTC) и 09-02..07 - продолжает ежедневно (D20, OQ-10) | `20260908T061829Z__probe30_list_before.json` |

Следствия: Story 3.3 - `CSV_COLUMN_MAP` переводится на реальные имена (`openCardCount → open_card`, `addToCartCount → cart`, `ordersCount → orders`, `ordersSumRub → orders_sum_rub`, `buyoutsCount → buyouts`, `buyoutsSumRub → buyouts_sum_rub`; `cancelCount`/`cancelSumRub`/конверсии/`addToWishlist`/`currency` - в payload); Story 3.2 - guard по префиксу и трактовка `createdAt` как UTC подтверждены; бэкфилл воронки на 6 месяцев одним отчётом реалистичен (CAP-6). Не проверено: глубина больше 6 месяцев; `STOCK_HISTORY_DAILY_CSV` глубина `currentPeriod`.

### Дневная история остатков - подтверждено (второй заход, 3 вызова по отдельному ок Mike)

- Тип отчёта `STOCK_HISTORY_DAILY_CSV` создаётся на токене «Аналитика» **без подписки «Джем»**; обязательные `params`: `currentPeriod {start, end}`, `stockType` (пусто = все), `skipDeletedNm`. Формирование заняло меньше 65 секунд; лимит создания и списка - 3/мин по заголовкам; квота 1 из 20 в сутки (D20: внешний потребитель тратит ещё 1).
- Файл - ZIP с одним CSV (`<id>.csv`, разделитель запятая): 787 строк данных за 7 дней. Колонки: `VendorCode, Name, NmID, SubjectName, BrandName, SizeName, ChrtID, OfficeName` и далее по одной колонке на дату (`26.08.2026 … 01.09.2026`) с остатком в штуках. Строка = артикул × размер (`ChrtID`) × склад (`OfficeName`: склады WB и «Свой склад»). Даты - в формате `dd.mm.yyyy`, широкий формат, для загрузки нужен unpivot по датам.
- Глубина `currentPeriod` назад **не проверена** (запрошено 7 дней); проверить одним вызовом с `start = 2026-03-01` в единице работы (кандидат на бэкфилл истории остатков).
- Вывод для OQ-13: источник дневной истории остатков есть на текущем токене, для `fact_stock_daily` достаточно ежедневного снимка через `stocks-report/wb-warehouses` (лимит 1 на окно) плюс еженедельного CSV как источника истории и сверки. Включение в реестр AD-4 - новый AD; фикстура CSV содержит реальные названия товаров кабинета - в git только после обезличивания (`tools/anonymize_fixture.py`, D15).
