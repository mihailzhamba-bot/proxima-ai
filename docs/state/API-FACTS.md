# API-FACTS: разведка WB API для PROXIMA AI

Сессия 1a, 30.08.2026, 05:59-06:11 UTC. Все вызовы с сервера `proxima` (`ssh -o BatchMode=yes`), токены из `/etc/proxima-ai/secrets/wb_*_token`, значения токенов не выводились и сервер не покидали. 18 вызовов, бюджет 35. Фикстуры: сервер `~/signal-inputs/fixtures/wb-api/`, копия в клоне `fixtures/wb-api/` (36 файлов, 436 МБ, untracked; `grep -rlE 'eyJ[A-Za-z0-9_-]{40,}' fixtures/` -> `clean` и на сервере, и на маке). Каждый факт ниже = вызов из лога в конце файла; чего не вызывал - помечено «не проверено».

## TL;DR

- **Ежедневный ряд продаж и заказов (Statistics API): 26 недель.** `sales` и `orders` с `dateFrom=2023-01-01&flag=0` отдают ряд с `2026-03-01` по сегодня (10 611 и 13 325 строк, потолок 80k не достигнут). `flag=1` по дню: `2026-02-28` отдаёт данные (77 продаж / 135 заказов), `2026-02-21` и `2026-02-15` - пустой массив. Окно скользящее, ~6 календарных месяцев назад; всё старше исчезает из API. Ряд непрерывный по месяцам (март-август по 1.7-2.6k строк/мес).
- **Воронка (просмотры, корзина) - синхронных методов больше нет.** `POST /api/v2/nm-report/detail` и `/detail/history` -> `404 path not found` на всех периодах. Жив только асинхронный `GET /api/v2/nm-report/downloads` (2 готовых `detail_history_report` в списке). Замена по докам WB - `POST /api/analytics/v3/sales-funnel/products/history` (дедлайн миграции был 09.12.2025) - в allowlist сессии не входила, **не проверено**.
- **Финотчёты (`reportDetailByPeriod`): 31 месяц, недельный разрез.** Первая страница (100 000 строк, 217 МБ) покрывает `2024-01-29..2025-10-18`, страница за 2026 (94 773 строки) - `2026-01-01..2026-08-23`, 34 недели. Последняя закрытая неделя `2026-08-17..2026-08-23` создана `2026-08-24`, лаг 1-8 дней.
- **`supplier/stocks` и `supplier/incomes` мертвы** (404 «This method is deprecated», «path not found»). Остатки - только через Analytics `stocks-report/wb-warehouses` (уже в коллекторе, не проверено).
- **Лимиты из заголовков:** `sales` 1/мин (429 после 32 с, `X-Ratelimit-Retry: 29`), `reportDetailByPeriod` 1/мин, `orders` 10, `seller-info` 10, `nm-report/downloads` 3. `X-Ratelimit-Reset` приходит только с 429.
- **Вердикт «>= 8 недель ежедневного ряда»: ДА** для продаж и заказов (26 недель). **НЕТ** для воронки: дневную историю просмотров/корзины сегодня можно получить только через async CSV (`downloads`, квота 20 отчётов/день по коду репо) или непроверенный v3.
- **Главный риск:** база нормы по воронке не подтверждена ни одним вызовом; если M-03 считает отклонения по просмотрам/конверсии, а не по заказам, срок 30.09 держится только на v3 `sales-funnel`, который надо проверить отдельным разрешением до Ворот 1. Второй риск: окно 6 мес означает, что история не копится сама - сбор надо запустить в сентябре, иначе к марту 2027 базы YoY не будет.

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

Не проверено (вне allowlist сессии): `POST /api/analytics/v3/sales-funnel/products` и `/products/history` (замена v2 по докам WB, заявлено 365 дней истории - по поисковой выдаче dev.wildberries.ru, сам сайт отдаёт 498 на fetch); `POST /api/analytics/v1/stocks-report/wb-warehouses`; `POST finance-api /api/finance/v1/sales-reports/detailed`; создание отчётов `POST nm-report/downloads`; скачивание `GET nm-report/downloads/file/{id}`; глубина `startDate` для async-отчёта.

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

Рекомендация к Воротам 1: вариант 3 как основа M-02/M-03 + вариант 1 в фоне с первого дня + отдельное разрешение на одну проверку `v3/sales-funnel/products/history` (2 вызова: неделя назад и 12 месяцев назад) - это снимает главный риск.

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

Пропущенные по плану вызовы: 3 глубинных `detail/history` (3/6/12 мес) - не выполнялись, потому что базовый вызов вернул 404; finance-токен для `reportDetailByPeriod` - не понадобился (statistics-токен прошёл).
