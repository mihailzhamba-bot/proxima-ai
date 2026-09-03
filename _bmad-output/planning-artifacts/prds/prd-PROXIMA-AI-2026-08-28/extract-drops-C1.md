---
cluster: C1 «Воронка, просадки, событийный диагноз»
extracted: 2026-09-02
role: analyst (read-only), выход для PM
source_root: /home/proxima-admin/orca/proxima-ai-sunfish/.orca/drops/функции новые/
---

# Extract C1 — воронка, просадки, событийный диагноз

## 0. Метод и границы

- Прочитано 24 файла целиком: `skills/wb-daily-drops/` (SKILL.md, 10 references, 8 scripts), `skills/wb-analytics/` (только SKILL.md — других файлов в дропе нет), `event-diagnosis/` (SPEC.md, ARCHITECTURE.md, EXTRACTED.md, BRAINSTORM.md). Бинарных файлов нет, `.DS_Store` пропущен. Все `file:line` ниже — относительно `source_root`.
- Скан секретов (`eyJ…`-JWT, `api_key|secret|password|token = "…"`): пусто. Значений токенов в дропе нет. Единственное упоминание места хранения ключа — `skills/wb-analytics/SKILL.md:17` (путь `/root/.openclaw/api-keys.env`, без значения).
- Опорные факты проекта: `docs/state/API-FACTS.md` (таблица эндпоинтов :19-34, «Воронка v3» :73-100), `DECISIONS.md` D16/D20/D21 (:128-163), `tools/verify_business_signal.py:19-29`, `_bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md` (:51 `fact_cabinet_daily`, :69 `fact_funnel_daily`, :87 `norm_daily`).
- Статусы источников (легенда колонки «статус»): **реестр** = в реестре AD-4; **READ вне реестра** = официальный READ-эндпоинт WB, в реестр не внесён, с сервера/на токене Амировой не проверен; **мёртв** = 404 по API-FACTS; **не проверен** = `stocks-report/wb-warehouses` (есть в коллекторе, живой вызов не делался); **внешний** = не WB; **ручной** = вводит человек.
- Правило проекта, против которого всё сверялось: WB только READ; без скрейпинга и браузерной автоматизации; цифры считает детерминированный код, LLM метрики не считает.

---

## 1. Скилл `wb-daily-drops` — утренний брифинг по просадкам воронки

### 1.1 Capability, пользователь, триггер, версия

- **Одной строкой:** для каждого SKU кабинета сравнить «вчера» с бейзлайном (среднее 6 предыдущих дней без акционных), отобрать SKU с отклонением выше порога, указать первый сломанный этап воронки и приложить четыре контекстных флага (остатки/склад, РК, цена, свежий негатив); выдать HTML-дашборд и Excel (`SKILL.md:3, :8-10`).
- **Пользователь:** селлер WB, включая новичка без технического бэкграунда (`SKILL.md:39-51`, `references/welcome.md`).
- **Триггер:** фразы «что с продажами», «где упало», «утренний отчёт WB» и т.п. (`SKILL.md:3`); авто-запуск по cron через `mcp__scheduled-tasks__create_scheduled_task`, дефолт `0 11 * * *` МСК (`SKILL.md:205`, `references/scheduling.md:7-8`).
- **Явные не-цели:** прогноз продаж (скилл №22), оптимизация РК (№29), конкуренты (№13/№34), глубокий разбор отзывов (`SKILL.md:19-24`).
- **Версия/дата:** frontmatter без версии (`SKILL.md:1-4`). Даты в тексте: боевой прогон 27.05.2026 (`references/api-endpoints.md:3`), миграция остатков и fullstats 03.08.2026 (`api-endpoints.md:74, :136`); `event-diagnosis/EXTRACTED.md:3` датирует версию 03.08.2026. Пайплайн гонялся ежедневно до 29.08.2026 на маке Mike (`DECISIONS.md` D20, `EXTRACTED.md:26`).

### 1.2 Входы

| # | Назначение | Эндпоинт (как в коде) | Где | Токен-категория | Статус |
|---|---|---|---|---|---|
| 1 | Воронка по дням, nmId | `POST https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history`, тело `{nmIds, selectedPeriod{start,end}, timezone:"Europe/Moscow", aggregationLevel:"day"}` | `scripts/fetch_funnel.py:40, :162-167`; `references/api-endpoints.md:13, :21-29` | Аналитика | **реестр** (API-FACTS:32, D16/D20) |
| 2 | Список карточек: nmID, title, brand, subjectName, createdAt | `POST https://content-api.wildberries.ru/content/v2/get/cards/list`, курсор по 100 | `fetch_funnel.py:39, :89-155`; `api-endpoints.md:61-68` | Контент | **READ вне реестра** |
| 3 | Остатки по складам (текущие) | `POST https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses`, тело `{limit:100000, offset:0}` | `scripts/enrich_stocks.py:14-16, :31, :51`; `api-endpoints.md:76-79` | Аналитика | **не проверен** (в коллекторе `wb-client.ts:157-190`, API-FACTS:53) |
| 4 | Список РК (статусы 9/11, changeTime ≤ 14 дн.) | `GET https://advert-api.wildberries.ru/adv/v1/promotion/count` | `scripts/enrich_ads.py:28, :46-91`; `api-endpoints.md:124-129` | Продвижение | **READ вне реестра** |
| 5 | Расход РК по nmId по дням (опционально) | `GET https://advert-api.wildberries.ru/adv/v3/fullstats?ids=<advertId>&beginDate=&endDate=`, один advertId за вызов, пауза 65 с | `enrich_ads.py:29, :31, :106-133`; `api-endpoints.md:133-143` | Продвижение | **READ вне реестра**; жёсткий лимит ~1 req/min (`api-endpoints.md:141`), по умолчанию выключен (`enrich_ads.py:185-187`) |
| 6 | Цены и скидки | `GET https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter?limit=1000&offset=N` | `scripts/enrich_prices.py:26, :47`; `api-endpoints.md:151` | Цены и скидки | **READ вне реестра** |
| 7 | Отзывы за 48 ч | `GET https://feedbacks-api.wildberries.ru/api/v1/feedbacks?isAnswered=false&take=5000&skip=N&dateFrom=<unix>&dateTo=<unix>&order=dateDesc` | `scripts/enrich_reviews.py:19, :42-49`; `api-endpoints.md:162` | Вопросы и отзывы | **READ вне реестра**; содержит ПД (см. 1.7) |
| 8 | Планировщик и артефакт | `mcp__scheduled-tasks__create_scheduled_task`, `mcp__cowork__create_artifact` | `SKILL.md:35, :117, :189, :205`; `scheduling.md:3, :17, :23` | — | **внешний** (платформа Cowork/Claude, не WB) |
| 9 | Chart.js | `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/...` | `scripts/build_artifact.py:29` | — | **внешний** CDN |
| 10 | Конфиг онбординга | `.wb-daily-drops.json`: JWT, selection, thresholds, promo_dates, zero_orders_rule, schedule | `references/onboarding.md:19-43` | — | **ручной**: порог %, мин. объём, акционные дни, правило «0 заказов», время запуска (`SKILL.md:85-97`) |

Токен: **один JWT** на шесть категорий «Аналитика, Контент, Статистика, Цены и скидки, Реклама, Вопросы и отзывы» (`SKILL.md:87`, `onboarding.md:71-77`); о бите read-only не говорится нигде. Хранится в открытом виде в `.wb-daily-drops.json` в рабочей папке (`onboarding.md:21, :86-87`; `SKILL.md:226`); в скрипты — через `WB_ANALYTICS_JWT` (`fetch_funnel.py:57`). MPStats и внешние сервисы не используются (`SKILL.md:37`).

Лимиты, зашитые в код: воронка — батч 20 nmId, пауза 20 с, 5 ретраев с экспонентой (`fetch_funnel.py:42-47, :169-199`); Content — 5 ретраев на страницу, best-effort (`:104-155`); stocks — при 429 пауза 25 с (`enrich_stocks.py:62-66`); fullstats — 65 с между вызовами (`enrich_ads.py:31`); prices — пауза 6 с между страницами (`enrich_prices.py:82`).

### 1.3 Расчёт (что считает код)

Вся арифметика — детерминированный Python; LLM в расчёте не участвует. Роль LLM (Claude в Cowork): онбординг и объяснения (`onboarding.md`, `welcome.md`), проверка первого запуска (`SKILL.md:41-47`), постановка отложенного перезапуска при exit 2 (`SKILL.md:117`), выбор режима «0 заказов». Принцип «без гипотез»: `references/drops-detection.md:3, :69-73` («не пишем “вероятно, дело в обложке”»), `SKILL.md:152`.

**Окно и бейзлайн**
- Период запроса = target (вчера) + 6 предыдущих дней; `--baseline-days > 6` принудительно урезается до 6 — лимит WB 7 дней включительно (`fetch_funnel.py:47, :249-251`; `api-endpoints.md:17`; `references/baseline.md:7`).
- Бейзлайн = арифметическое среднее абсолютных метрик по дням, не исключённым как акционные и имеющим данные (`scripts/detect_drops.py:57-74, :129-132`; `baseline.md:8-9`). Все дни недели равны (`baseline.md:8`).
- Производные конверсии — от **сумм** за окно, не среднее процентов: `addToCartConversion = Σcart/Σopen·100`, `cartToOrderConversion = Σorder/Σcart·100`, `buyoutPercent = Σbuyout/Σorder·100` (`detect_drops.py:44-54`; `baseline.md:30-39`). Для target-дня проценты тоже пересчитываются из абсолютных полей, «WB иногда округляет» (`detect_drops.py:77-82`).
- Ненадёжный бейзлайн: `len(effective_baseline_dates) < 3` → флаг `baseline_unreliable` (`detect_drops.py:131`). Флаг только записывается в JSON (`:162, :189`) — ни Excel, ни HTML его не показывают (grep по `scripts/` даёт только эти три строки); обещанный баннер `baseline.md:12` не реализован.
- Новый SKU: `card.createdAt` моложе 7 дней относительно target → `skipped_new` (`detect_drops.py:112-121`). Нет данных за target → `skipped_no_data` (`:123-126`).

**Фильтр объёма:** SKU остаётся, если `baseline.orderCount ≥ 3` **или** `baseline.orderSum ≥ 5000 ₽/день` (дефолты; `detect_drops.py:134-140`; `drops-detection.md:9-16`).

**Метрики и дельты** (`detect_drops.py:18-37, :85-88, :142-149`):
- `PCT_METRICS = openCount, cartCount, orderCount, orderSum` — `delta_pct = (today − base)/base·100`; при `base = 0`: `None` если today = 0, иначе `inf`.
- `PP_METRICS = addToCartConversion, cartToOrderConversion` — дельта в п.п.
- Справочно, без триггера: `buyoutCount`, `buyoutPercent` — лаг выкупа 5-14 дней делает дневное сравнение бессмысленным (`detect_drops.py:22-24`; `api-endpoints.md:53`; `howitworks.md:52-58`). `addToWishlistCount` считается, но не триггерит.

**Правила решения** (`detect_drops.py:151-183`):
- `drop_flag` если хотя бы одна PCT-метрика `≤ −drop_pct` (дефолт 20); `growth_flag` если `≥ growth_pct` (дефолт 20). Категории: `drop` / `growth` / `mixed` (оба) / `ok`.
- Правило «0 заказов» (`today.orderCount == 0 and base_orders > 0`): `hide` → скрыть; `oos_section` → отдельный раздел `oos_candidate` с `first_break = "orderCount"`; `drop_100` → обычный путь (`:155-164`; `drops-detection.md:53-59`).
- **Локализация этапа** — первый по порядку `openCount → addToCartConversion → cartCount → cartToOrderConversion → orderCount → orderSum`, где `pct ≤ −drop_pct` или для п.п.-метрик `pp ≤ −drop_pct/4` (`detect_drops.py:34-37, :91-104`). Порог `/4` (при дефолте — 5 п.п.) **нигде в references не описан**.
- Сортировка: просадки — по убыванию абсолютной потери выручки `−Δ orderSum`; росты — по приросту; OOS-кандидаты — по бейзлайн-выручке (`detect_drops.py:257-259`; `drops-detection.md:75-83`).
- **Общесистемное явление:** суммы по всем не-skipped SKU, дельты те же; баннер в HTML при `pct ≤ −20` / `≥ 20` — порог **зашит 20**, независимо от настроек селлера (`detect_drops.py:193-215`; `build_artifact.py:223, :233-251`). Excel «Сводка» подсвечивает `±20 %` и `±5 п.п.` тоже жёстко (`build_excel.py:118-121`).
- Top-N по выручке: воронка сначала тянется **по всем** карточкам, отсечение по Σ`orderSum` за бейзлайн-дни делается после (`fetch_funnel.py:211-213, :304-314`) — экономии вызовов нет.
- Данные за target не пришли ни по одному SKU → exit 2 → перезапуск через 2 ч (`fetch_funnel.py:316-323`; `run_all.sh:61-64`; `scheduling.md:15-19`).

**Обогатители** (best-effort, каждый пишет `enrichment.<src>` в `insights.json`; при 401/403 — `NO_DATA`):
- *Остатки* (`enrich_stocks.py:85-127, :139-144, :185-189`): группировка `nmId × warehouseName`, `Σ quantity` (только `quantity`, без `inWayToClient`); `OOS_full` если `total_today == 0`; `OOS_warehouse_dropoff` + имя склада, если вчера по складу `> 0`, сегодня `0`. «Вчера» — кэш `stocks_<target_date>.json` предыдущего прогона; без кэша dropoff принудительно `OK`. Один запрос, без пагинации (`limit 100000`, `:51`).
- *Реклама* (`enrich_ads.py:46-91, :137-179, :208-220`): кампании со статусом `{9, 11}` и `changeTime` за 14 дней; по умолчанию `max_campaigns = 0` → флаг `SUMMARY_ONLY` с числом кампаний; при включении — `spend` из `days[].apps[].nm[].sum`, `spent_avg = Σ(baseline dates)/len(baseline_dates)` (делит на все 6 дат, акционные и пропуски не исключаются, `:156`). Флаги: `avg < 1` → `no_baseline`/`started`; `today == 0 and avg > 100` → `RK_off`; `today/avg < 0.1` → `RK_dropped`; `> 2.0` → `RK_boosted`; иначе `RK_ok` (при `1 ≤ avg ≤ 100` и `today = 0` получается `RK_dropped`, не `RK_off`).
- *Цена* (`enrich_prices.py:28, :63-75, :136-146`): `final = sizes[0].price·(1 − discount/100)`; «spp_price» = `sizes[0].clubDiscountedPrice` или `final` (это цена WB Club, не СПП); сравнение с кэшем `prices_<target_date>.json`; `|Δ| ≥ 3 %` → `price_changed`, иначе `no_change`; без кэша — `no_history`.
- *Отзывы* (`enrich_reviews.py:34-49, :95-111, :113-125`): окно 48 ч, `productValuation ≤ 3`, текст = `text · cons: … · pros: …` до 200 символов; `fresh_negative` с числом и самым свежим примером. Фильтр `isAnswered=false` — отвеченные негативные отзывы не видны.

**Сезонность/акции:** только ручной список `promo_dates` (`onboarding.md:163-177`); дни недели не учитываются; статистическая значимость не считается «по решению селлера» (`drops-detection.md:73`). Прогноза нет по определению.

### 1.4 Выход

- `funnel_raw.json` (`fetch_funnel.py:325-337`), `insights.json` — единый источник для Excel и HTML (`detect_drops.py:261-277`; `enrichment.md:92-117`).
- **Excel** (`openpyxl`, `build_excel.py:425-431`): «Сводка» (9 метрик: вчера / среднее / Δ абс / Δ %; `:74-135`), «Топ просадок» и «Топ ростов» (32 колонки, включая первый сломанный этап, OOS-флаг, склад, остатки, РК-флаг и расход, цена и Δ %, негатив, ссылка на карточку; `:138-171`), «По брендам» (`:275-309`), «OOS-кандидаты», «Воронка-графики» (LineChart открытий/корзины/заказов/выкупов для топ-10 просадок; `:358-401`), «Методология» (`:312-355`). Имя `WB_утренний_отчёт_DD-MM-YYYY.xlsx` (`run_all.sh:93`).
- **HTML-дашборд** (`build_artifact.py:24-442`): плашки кабинета по 5 метрикам с баннером «просел/вырос весь кабинет» (`:209-252`), блок «свежий негатив» (`:254-277`), просадки/росты/OOS с группировкой по брендам, флаги-бейджи (`:279-301`), карточка SKU с «Сломалось на: …» и sparkline **только по `orderCount`** (`:319-358, :445-458`), фильтры в `localStorage` (`:166-193`), inline JSON в `<script id="data">`.
- Потребитель — селлер (открывает утром). Рекомендаций нет намеренно: только «где» (`howitworks.md:62-76`).
- Метрики успеха скилла: ≤ 90 с до дашборда при ≤ 200 SKU; ≥ 95 % SKU с полной воронкой; топ-3 просадок совпадают с аналитиком ≥ 4/5; 0 выдуманных гипотез (`SKILL.md:228-233`).

### 1.5 Переформулировка как per-tenant capability на данных лестницы

Данные лестницы (ARCHITECTURE-SPINE): `fact_cabinet_daily(tenant_id, calendar_day, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub)` (:51); `norm_daily` — медиана 14 полных дней по `orders|revenue`, окно `[eval−14, eval−1]` (:87; D21); `fact_funnel_daily(tenant_id, nm_id, calendar_day, source v3|csv, open_card, cart, orders, orders_sum_rub, buyouts, buyouts_sum_rub)` (:69) — v3 скользящее окно 7 дней ежедневно, CSV еженедельно; сырые строки `stg_wb_orders_obs` / `stg_wb_sales_obs` с полями WB (nmId, brand, subject, warehouseName, totalPrice, discountPercent, spp, priceWithDisc, finishedPrice — API-FACTS:24-25); `dim_product`, `dim_warehouse_map` (`event-diagnosis/ARCHITECTURE.md:32-33`).

| Элемент скилла | На лестнице сегодня | Чего не хватает |
|---|---|---|
| Бейзлайн 6 дней по воронке | `fact_funnel_daily` даёт ровно это (6 полных дней до вчера); те же формулы «от сумм» | Норма ≥ 14 дней по воронке — только после накопления v3/CSV (по API-FACTS:67 — конец октября) |
| Просадка заказов по SKU | Лучше, чем в скилле: `stg_wb_orders_latest` → nmId × день, 26 недель глубины (API-FACTS:5) → **медиана 14 дней по SKU** вместо среднего 6 дней; заказы без отмен как в D21 | Ничего; нужен только агрегат nmId × день (в SPINE запланирован `fact_order_counts` из CSV, не из orders) |
| Локализация этапа | Три ступени `open_card → cart → orders` (+ `orders_sum_rub`) и две конверсии из сумм — считается на `fact_funnel_daily`; показов в WB нет вообще (API-FACTS:97), «выкуп» — справочно | Клики/CTR не существуют; этап «выкуп» нужно считать по `sales flag` с лагом (см. BRAINSTORM №8) |
| Фильтр объёма, top-N, «0 заказов», общесистемный баннер | Всё считается на `fact_cabinet_daily` + агрегате по nmId; кабинетный баннер = уже существующее отклонение M-03 к `norm_daily` | — |
| Акционные дни | Ручного списка нет; частично выводимо: медиана `discountPercent`/`spp` по строкам orders за день — «акция кабинета» как скачок скидки | Календарь акций WB (нет источника); ввод человеком — UI/auth заморожены до октября |
| Новые SKU (< 7 дней) | Прокси: первая дата наблюдения nmId в `stg_wb_orders_obs` | `createdAt` карточки — только Content API (вне реестра) |
| Группировка по брендам/категориям | `brand`, `subject` есть в строках orders/sales и в `dim_product` | Content API не нужен |
| OOS_full / выпадение склада | Только точечный `business_signal_runs.stock_quantity/stock_as_of` (API-FACTS:53); ряда нет | Ежедневный снапшот `stocks-report/wb-warehouses` по складам (не проверен) — или проверить v2 «История остатков» из `wb-analytics` (см. 2.5) |
| РК-флаги | Нет | Promotion API вне реестра; `fullstats` ~1 req/min → per-nm расход к 05:30 недостижим при десятках кампаний; реалистичен только `promotion/count` (1 вызов) |
| Цена изменилась | Частично без нового эндпоинта: медиана `priceWithDisc` и `spp` по заказам nmId за день — ряд «реализованной цены» на 26 недель назад; нет наблюдения в дни без заказов | Prices API вне реестра — нужен только для дней без заказов и для «цены до/после» точной |
| Свежий негатив | Нет | Feedbacks API вне реестра; ПД |
| Excel/HTML/cron | Webapp `/brief` (Next.js) и systemd-таймер 05:30 МСК уже в лестнице | Cowork-артефакт и MCP-планировщик не нужны |

**ML-потенциал (0-3) по подзадачам:**
- *Детект отклонений по SKU* — класс: аномалии во временных рядах счётчиков. Данные: 201 nmId, ~13 тыс. заказов за 6 мес (API-FACTS:25) ≈ 70 заказов/день на кабинет → у большинства SKU единицы в день, доминирует пуассоновский шум. Горизонт: «вчера». Метрика: precision@k против ручной разметки селлера, доля ложных тревог/день. **Оценка 2**: сейчас выигрывает робастная статистика (медиана/MAD, пуассон-интервалы, иерархическое сглаживание по категории); модели сезонности (недельная/праздничная) осмысленны после ≥ 1 года ряда.
- *Локализация этапа* — детерминированное правило; ML не нужен. **Оценка 1** (максимум — квантильные пороги на конверсии вместо `drop_pct/4`).
- *Кабинетный уровень* — прогноз заказов/выручки на 1-7 дней с доверительным интервалом (26 недель есть). Класс: прогноз; метрика MAPE/coverage. **Оценка 2** — не в границах этого скилла, но данные готовы раньше всех.

### 1.6 Код к переиспользованию

| Файл | Строк | Что | Оценка |
|---|---|---|---|
| `scripts/detect_drops.py` | 283 | Чистые функции `compute_derived`, `aggregate_days`, `delta_pct`, `first_broken_stage`, `analyze_sku`, `account_overview` — единственный содержательный расчёт | Порт в `control-plane` (Python 3.14) уместен: 1 файл, stdlib; исправить противоречия из 1.7 |
| `scripts/fetch_funnel.py` | 343 | Content + v3 с батчами, ретраями, кэшем карточек | Проект уже пишет `jobs/funnel-v3.ts` (SPINE:69); ценность — как эталон поведения при 400/429/soft-error `{"error":true}` (`:124-127`) |
| `scripts/enrich_*.py` | 133-237 | Клиенты Promotion/Prices/Feedbacks/Stocks + пороги флагов | Пороги и парсинг ответов (`fullstats.days[].apps[].nm[].sum`, `listGoods[].sizes[0]`, `feedbacks[].productDetails.nmId`) — справочник для будущих снапшотов CAP-A |
| `scripts/build_excel.py`, `build_artifact.py` | 439, 524 | openpyxl-отчёт, самодостаточный HTML с Chart.js | Webapp другой (Next.js, DESIGN.md); переиспользовать только состав колонок/секций |
| `scripts/run_all.sh` | 103 | Оркестратор bash | Не нужен (systemd в лестнице) |

Язык Python ≥ 3.10 (`X | None`, `zoneinfo`); зависимости `requests`, `openpyxl` (без requirements-файла; `troubleshooting.md:34` ставит через `pip --break-system-packages`). **Тестов нет.** Секретов в коде нет. Импорт в репо — только через `provenance/import-inventory.json` (правило AGENTS.md), практичнее переписать.

### 1.7 Красные флаги и противоречия

- **WRITE в WB:** нет. Все семь вызовов — чтение (POST-тела — фильтры запросов). **Скрейпинг:** нет (ссылки на `wildberries.ru/catalog/<nm>` — только гиперссылки в отчёте, `build_excel.py:220`, `build_artifact.py:342`). **Платные внешние API:** нет (`SKILL.md:37`). Cowork MCP и CDN — платформенная зависимость, не платная.
- **Токен:** один JWT на 6 категорий, включая write-способные (Контент, Цены, Продвижение, Отзывы), хранится в открытом файле в рабочей папке (`onboarding.md:21`; `SKILL.md:226`). Противоречит правилу проекта «split-токен с битом read-only на категорию».
- **ПД:** `userName` автора отзыва и текст сохраняются в `insights.json` (`enrich_reviews.py:106-111`), текст попадает в HTML (`build_artifact.py:274`).
- **Мёртвый эндпоинт в документации:** `GET /api/v1/supplier/stocks` в `SKILL.md:30`, `enrichment.md:13, :17` (`quantityFull`), `howitworks.md:15`, `api-endpoints.md:183` (скоуп «Статистика») — код давно на `stocks-report/wb-warehouses` (`enrich_stocks.py:14-15`).
- **Эндпоинты рекламы расходятся:** `enrichment.md:34-35` описывает `/adv/v1/upd` и `/adv/v2/fullstats`; код зовёт только `promotion/count` и `v3/fullstats` (`enrich_ads.py:28-29`), а `api-endpoints.md:139` объявляет v2 мёртвым; docstring `enrich_ads.py:7` всё ещё говорит v2.
- **Глубина бейзлайна:** «7 предыдущих дней / 8 дней суммарно» (`SKILL.md:101-103, :124, :179`), «Бейзлайн: 7 дней» в HTML (`build_artifact.py:117`), «Среднее за 7 дней» в Excel (`build_excel.py:84`, `report-format.md:92`) против 6 в коде (`fetch_funnel.py:7-8, :249-251`, `baseline.md:7`).
- **14-дневные графики невозможны:** `report-format.md:27, :64-65, :147`, `SKILL.md:184`, `build_excel.py:359, :366`, `build_artifact.py:445-458` обещают 14 дней; v3 отдаёт 7. `baseline.md:13` предлагает `--baseline-days 14`, который код урезает до 6.
- **Порог ненадёжности:** `< 4` (`baseline.md:10`, `SKILL.md:127, :216`) против `< 3` (`detect_drops.py:131`, `howitworks.md:34`, `onboarding.md:177`); флаг не отображается.
- **Воронка 6 этапов в документации, 4 в коде:** `drops-detection.md:42-49`, `baseline.md:22-35`, `report-format.md:94-102, :116-122` содержат `clickCount`/CTR; в WB v3 клика нет (`api-endpoints.md:47-49`; `detect_drops.py:6-7`).
- **`openCount` подписан как «Показы»** (`SKILL.md:136`, `build_artifact.py:213`, `build_excel.py:90`); по спеке WB это переходы в карточку, показов (impressions) в v3 нет (API-FACTS:97). Для PM: «упали показы» в отчёте означает «упали открытия карточки».
- **Новый SKU:** по `createdAt` карточки (`detect_drops.py:112-119`) против «первая дата с заказами позже D-7» (`baseline.md:14`).
- **Порог настраиваемый, но зашит:** общесистемный баннер и подсветка — константы 20 % / 5 п.п. (`build_artifact.py:223, :235, :239, :347`; `build_excel.py:118-121`).
- **Параллелизм:** `SKILL.md:167`, `enrichment.md:7`, `EXTRACTED.md:67` говорят `ThreadPoolExecutor`; реально bash `&` (`run_all.sh:75-85`), причём комментарий `run_all.sh:74` «запускаем последовательно» противоречит следующей строке.
- **«Top-N быстрее»** (`onboarding.md:100, :108`) — ложно: воронка тянется по всем карточкам (`fetch_funnel.py:211-213, :304-314`); 1000 SKU = 50 батчей × 20 с ≈ 17 мин в любом режиме. Метрика «≤ 90 с при 200 SKU» (`SKILL.md:230`) несовместима с 10 батчами × 20 с (`howitworks.md:141` честно даёт ~3.7 мин).
- **Мелкие:** «СПП-цена» = `clubDiscountedPrice` (`enrich_prices.py:74`); комментарий «в копейках» без деления (`:68`); `isAnswered=false` теряет отвеченный негатив (`enrich_reviews.py:43`); stocks без пагинации при заявленных 250 тыс. строк (`enrich_stocks.py:51` vs `api-endpoints.md:111`); `spent_avg` делит на 6 дат без учёта акций (`enrich_ads.py:156`).
- **Иллюстративные данные** (не выдумка фактов, но не путать с реальными): nmId `46471381`/«Коледино» (`api-endpoints.md:87-97`), `12345678`/«Гирлянда» (`enrichment.md:96-113`, `report-format.md:36-42`).

---

## 2. Скилл `wb-analytics` — CLI-обёртка над Analytics API

### 2.1 Capability, пользователь, триггер, версия

- **Одной строкой:** справочник и shell-обёртка для 17 методов `seller-analytics-api` (воронка v3, поисковые запросы v2, история остатков v2, async CSV); расчётов нет — только вызов и вывод JSON (`SKILL.md:11-13, :21-42`).
- **Пользователь:** оператор/агент, вызывающий API из чата (`SKILL.md:3-8`).
- **Триггер:** любые упоминания продаж, позиций, видимости, воронки, остатков WB (`SKILL.md:7-8`).
- **Версия:** 2.2 (`SKILL.md:236`), даты нет; примеры датированы февралём 2026.
- **В дропе только `SKILL.md`.** Файлы `scripts/wb-analytics.sh`, `references/api-spec.yaml` (5382 строки), `references/testing-status.md`, на которые ссылается `SKILL.md:217-235`, отсутствуют — проверить скрипт и статус тестирования невозможно.

### 2.2 Входы

Base URL `https://seller-analytics-api.wildberries.ru` (`SKILL.md:44`); ключ `WB_API_KEY` из `/root/.openclaw/api-keys.env` (`SKILL.md:17`) — платформа OpenClaw, категория токена «Аналитика».

| Группа | Эндпоинты (`SKILL.md`) | Статус |
|---|---|---|
| Воронка v3 | `POST /api/analytics/v3/sales-funnel/products` (агрегат до 365 дн., `pastPeriod`) :24; `…/products/history` (по дням, ≤ 7 дн.) :25; `…/grouped/history` :26 | history — **реестр**; products и grouped — READ вне реестра, **не проверены** (API-FACTS:34) |
| Поисковые запросы v2 | `POST /api/v2/search-report/report` :28, `/table/groups` :29, `/table/details` :30, `/product/search-texts` :31 (лимит 30/100 «зависит от тарифа» :142), `/product/orders` :32 | **READ вне реестра**; зависимость от тарифа/подписки «Джем» (:142, :202) |
| История остатков v2 | `POST /api/v2/stocks-report/products/groups` :34, `/products/products` :35, `/products/sizes` :36, `/offices` :37 — с `currentPeriod{start,end}` :69 | **READ вне реестра, не проверены**; принципиально: это **история** остатков, а не текущий срез |
| CSV-отчёты | `POST /api/v2/nm-report/downloads` :39 (≤ 20/сутки), `GET …/downloads` :40, `POST …/downloads/retry` :41, `GET …/downloads/file/{id}` :42 (ZIP, 48 ч). Типы: `DETAIL_HISTORY_REPORT, GROUPED_HISTORY_REPORT, SEARCH_QUERIES_PREMIUM_REPORT_{GROUP|PRODUCT|TEXT}, STOCK_HISTORY_REPORT_CSV, STOCK_HISTORY_DAILY_CSV` :191 | create/list — **реестр**; file/retry — не проверены (API-FACTS:34); квота 20/день разделяется с внешним потребителем (D20) |

Полезные справочные факты: три разных формата дат (`selectedPeriod` v3 / `currentPeriod` v2 / `period` для search-orders / `params.startDate` CSV — `SKILL.md:46-78`), обязательные поля по методам (`:80-97`), лимиты 3/мин, 20 с интервал, 429 → 60 с (`:115-119`), `funnel-grouped` произведение фильтров ≤ 16 (`:132`).

### 2.3 Расчёт

Отсутствует: скилл ничего не считает и не решает. Единственная «логика» — батчинг и пагинация с паузой 20 с (`SKILL.md:121-132`).

### 2.4 Выход

JSON ответа WB в stdout (`SKILL.md:126-127`); CSV — ZIP-файл (`:188`). Потребитель — агент/оператор.

### 2.5 Переформулировка на данных лестницы

- Ничего нового в расчётах не добавляет; всё, что уже есть — `fact_funnel_daily` (v3 history) и `wb_async_report.py` (CSV).
- **Стратегически важное указание:** группа «История остатков v2» (`/api/v2/stocks-report/products/*` с периодом) и CSV-типы `STOCK_HISTORY_REPORT_CSV` / `STOCK_HISTORY_DAILY_CSV` — если живы на кабинете, они дают **ряд остатков назад** без собственных ежедневных снапшотов. Это напрямую уменьшает объём CAP-A (event-diagnosis) и делает CAP-E проверяемым постфактум сразу. Проверка: 1-3 read-вызова с сервера под отдельным разрешением (аналог D16). Разрез по складам в v2-ответах из SKILL не следует — уточнить по спеке.
- Поисковые запросы v2 — данные для «каннибализации SKU» (BRAINSTORM №11) и видимости; вне кластера C1, зависят от тарифа.
- **ML-потенциал: 0** (нет расчёта). Как источник данных для других кластеров — до 2.

### 2.6 Код к переиспользованию

Кода в дропе нет (скрипт отсутствует). Ценность — таблицы форматов дат/обязательных полей (`SKILL.md:46-97`) как чек-лист при реализации `jobs/funnel-v3.ts` и будущих вызовов. Тестов нет (`testing-status.md` отсутствует). Оценка 1.

### 2.7 Красные флаги

- WRITE — нет (`csv-create` создаёт задачу отчёта на стороне WB, данные кабинета не меняет; квота 20/день — исчерпаемый ресурс, D20).
- `nmIds` «до 1000 в одном запросе» (`SKILL.md:123, :138`) противоречит hard-limit 20 для `history` (`fetch_funnel.py:42-44`; API-FACTS:32). Для `funnel-products`, возможно, верно — не проверено.
- Поля `addToWishlist`, `wbClub{…}`, `conversions{…}`, `timeToReady` и «Dynamic»-суффиксы для history (`SKILL.md:98-113`) не подтверждены фикстурой проекта: в ответе v3 history 11 полей, среди них `addToWishlistCount`, wbClub нет (API-FACTS:97). Либо поля есть только в `funnel-products`, либо документация опережает API.
- Зависимость от платной подписки WB «Джем» для части методов (`SKILL.md:142, :202`); для CSV `DETAIL_HISTORY_REPORT` та же оговорка в API-FACTS:8.
- Ссылка на путь `/root/.openclaw/api-keys.env` (`SKILL.md:17`) — чужая платформа и root-путь; значения нет.

---

## 3. Модуль `event-diagnosis` — событийный слой и диагноз отклонений

### 3.1 Capability, пользователь, триггер, версия

- **Одной строкой:** к каждому отклонению утренней сводки приложить кандидатов в причину — события кабинета (цена, остаток по складу, РК, негатив), совпавшие по времени и объясняющие именно отклонившуюся метрику, — либо явно «причина не найдена»; плюс признак полноты данных, география остатков и прогноз исчерпания (`SPEC.md:19-25, :72-74`).
- **Пользователь:** селлер (канон — Mike/кабинет Амировой по D18) на экране `/brief`.
- **Триггер:** ежедневный прогон после сбора (`ARCHITECTURE.md:82-91`); аномалия по заказам к медиане 14 дней.
- **Статус/дата:** «эксперимент, не канон proxima-ai» (`SPEC.md:2-3, :15`); 30.08.2026 (`ARCHITECTURE.md:3`, `EXTRACTED.md:4`, `BRAINSTORM.md:3`). Канонический контракт — `_bmad-output/specs/spec-wb-morning-brief/SPEC.md` (существует; CAP-6 :43, CAP-8 :49); при вливании CAP-A..E становятся расширением CAP-8 и соседом CAP-6 (`SPEC.md:15`; `ARCHITECTURE.md:100`).

### 3.2 Capabilities дословно (`SPEC.md:29-47`)

- **CAP-A. Событийный слой**
  - **intent:** Система ежедневно снимает состояние каждого активного nmId — цена и скидка, остатки в разрезе складов, статус и расход рекламных кампаний, свежие отзывы — и хранит снапшоты как временной ряд.
  - **success:** Три дня подряд без ручного вмешательства в БД есть снапшот за каждый день по каждому активному nmId; повторный прогон за тот же день не создаёт дублей и полностью удаляется по `run_id`; на четвёртый день по любому nmId можно вычислить, что изменилось между любыми двумя из этих дней.
- **CAP-B. Признак полноты данных**
  - **intent:** Каждый день в ряду несёт явный признак: данные полные, неполные или отсутствуют. Диагноз и отклонения не строятся на днях, помеченных как неполные.
  - **success:** День, за который WB не отдал часть батчей, помечен `incomplete` с указанием, чего не хватает; на экране вместо цифры отклонения — явная формулировка «данные за эту дату неполные»; ни одна аномалия и ни один диагноз не порождены таким днём. Проверяется на фикстуре с намеренно вырезанным батчем.
- **CAP-C. География остатков**
  - **intent:** Система различает «товара нет нигде» и «товар есть, но не там, где спрос»: сопоставляет остатки по складам с тем, через какие склады шли продажи.
  - **success:** Для nmId, у которого остаток обнулился на одном складе при наличии на других, событие содержит имя выпавшего склада и долю этого склада в продажах за предшествующий период; для nmId с остатком на всех складах такое событие не порождается.
- **CAP-D. Диагноз отклонения**
  - **intent:** К каждой аномалии, прошедшей отбор по деньгам, система прикладывает список кандидатов в причину — событий, совпавших по времени и объясняющих именно ту метрику, которая отклонилась, — либо явно сообщает, что объяснения не нашлось.
  - **success:** У каждой аномалии есть либо непустой список кандидатов, где каждый несёт класс события, дату, величину изменения и SourceRef на исходный снапшот, либо явный исход «причина не найдена»; ни одного кандидата, чей класс не объясняет отклонившуюся метрику; ни одной цифры без SourceRef; ни одного диагноза, порождённого LLM.
- **CAP-E. Прогноз исчерпания остатка**
  - **intent:** Система предупреждает об OOS до его наступления: на основе остатка по складу и темпа продаж сообщает, через сколько дней товар закончится.
  - **success:** Для nmId с ненулевым остатком и ненулевым темпом продаж выдаётся оценка в днях с указанием склада; при остатке 0 или темпе 0 выдаётся не число, а причина, почему оценка невозможна; прогноз, сделанный за N дней до фактического обнуления, проверяется постфактум на накопленном ряду.

### 3.3 Входы

| Снапшот / вход | Эндпоинт (как в `ARCHITECTURE.md:48-53`) | Статус |
|---|---|---|
| `snapshot_price` (`total_price, discount_percent, spp, price_with_disc`) | `GET discounts-prices-api…/api/v2/list/goods/filter` | READ вне реестра, с сервера не проверен (`SPEC.md:84`) |
| `snapshot_stock` (`canonical_warehouse, quantity`) | `POST seller-analytics-api…/api/analytics/v1/stocks-report/wb-warehouses` | не проверен; в коллекторе (`ARCHITECTURE.md:99`) |
| `snapshot_campaign` (`campaign_id, status, spend_rub, views`) | `GET advert-api…/adv/v1/promotion/count`, `/adv/v1/upd`, `/adv/v2/fullstats` | READ вне реестра; **`/adv/v1/upd` в коде скилла не вызывается, `/adv/v2/fullstats` объявлен мёртвым** (`api-endpoints.md:139`) — реальный источник `v3/fullstats` с лимитом ~1/мин |
| `snapshot_feedback` (`feedback_id, rating, created_at_wb`) | `GET feedbacks-api…/api/v1/feedbacks` | READ вне реестра |
| Аномалии | `fact_order_counts` к медиане 14 дней (`ARCHITECTURE.md:87`) | реестр (orders/sales) |
| Этап воронки | `funnel_daily` 6 дней (`ARCHITECTURE.md:18`; `SPEC.md:58`) | реестр (v3 history) |
| Доля склада в продажах | `supplier/sales.warehouseName` через `dim_warehouse_map` (`SPEC.md:86`; `ARCHITECTURE.md:33`) | реестр |
| Полнота | `quality_check_results`, `fact_lineage_records` как SourceRef (`ARCHITECTURE.md:34-35`) | данные лестницы |

Ограничения: только READ (`SPEC.md:51`), `run_id`-идемпотентность (:52), multi-tenant (:53), allowlist до реализации (:54), миграции additive-only (:55), LLM не считает (:56), снапшот хранит состояние, не разницу (:57; `ARCHITECTURE.md:23`), три окна разведены (:58), выкупы вне критериев (:59), фикстуры (:60).

### 3.4 Расчёт (что задано спекой)

- **Событие** = сравнение соседних снапшотов при чтении: `nm_id, event_class, calendar_day, value_before, value_after, magnitude, lineage_id` (`ARCHITECTURE.md:59`).
- **Классы, метрика-мишень, порог** (`ARCHITECTURE.md:69-76`): `price_up/price_down` → `cartToOrderConversion`, `orderCount`, порог > 3 %; `stock_zero` → `orderCount` до нуля, остаток 0 везде; `stock_warehouse_dropoff` → `orderCount` + география, 0 на складе при > 0 вчера; `campaign_stopped` → `openCount`, расход 0 при среднем > 100 ₽/день; `campaign_dropped` → `openCount`, < 10 % среднего; `fresh_negative` → `addToCartConversion`, отзыв ≤ 3★ за 2 дня. Правило соответствия «цена не объясняет показы» — содержательное ядро CAP-D (`:78`).
- **Окно совпадения:** D..D-1 относительно дня аномалии (`ARCHITECTURE.md:80`).
- **Исход:** `explained` со списком кандидатов (`event_class, magnitude, lineage_id, rank`) или **явный** `not_explained`; отсутствие строки ≠ «не найдено» (`:61-63`).
- **Порядок в прогоне** (`:84-91`): попытка → 4 снапшота параллельно best-effort с `quality_check_results FAIL` при падении → проверка полноты → аномалии по `fact_order_counts` к медиане 14 только по `PASS`-дням → диагноз D vs D-1 → CAP-E независимо.
- **CAP-E:** «остаток последнего дня против темпа по `fact_order_counts`» (`:89`); формула не задана (по смыслу `дней = остаток_склада / темп`), «темп» не определён (окно, медиана/среднее, по складу или по кабинету).
- **Ранжирование** кандидатов — фиксированный список классов, не вычисляется (`:107`; `SPEC.md:87`).
- Что LLM делает: только формулировка текста поверх посчитанного с гардрейлом (`SPEC.md:56`).

### 3.5 Выход

Экран `/brief`: связка «отклонение → этап воронки → событие с датой и величиной (“28.08 цена выросла с 2 190 ₽ до 2 490 ₽”) или “объяснения в данных кабинета не нашлось”» (`SPEC.md:74`). Форму `diagnosis` сверить с `contracts/diagnosis.schema.json` — по `ARCHITECTURE.md:101` контракты «в ветке pmm29-contracts», по AGENTS.md они уже в `contracts/` на main. Рекомендаций и оценки в рублях нет намеренно (`SPEC.md:64`).

### 3.6 Переформулировка на данных лестницы

- **Считается уже сегодня:** CAP-B (на `collector_runs` / `quality_check_results`, фикстура с вырезанным батчем); аномалии по SKU и кабинету (см. 1.5); ценовой ряд nmId из `priceWithDisc`/`spp` строк orders → события `price_up/down` без Prices API (слепая зона — дни без заказов); доля склада в продажах nmId по `warehouseName` за окно (CAP-C, половина); темп продаж по SKU и по складу для CAP-E.
- **Не хватает:** ряда остатков по складам (либо ежедневный снапшот `stocks-report/wb-warehouses`, либо проверка v2 «История остатков»/`STOCK_HISTORY_*` CSV из §2.5), рекламных событий (Promotion — вне реестра, `fullstats` ~1/мин; `promotion/count` даёт лишь статус кампаний), отзывов (Feedbacks — вне реестра, ПД), обратной связи о верности диагноза (auth/UI заморожены — `BRAINSTORM.md:35`).
- **ML-потенциал:** CAP-A — 0 (сбор). CAP-B — 0 (правила). CAP-C — 1 (правило + доля). **CAP-D — 2**: класс — ранжирование/атрибуция причин; данные — событийный ряд (не существует, копится с момента старта) + разметка селлера (заблокирована auth); горизонт — постфактум; метрика — доля принятых диагнозов, precision top-1; до накопления ≥ 3 месяцев событий и ввода обратной связи — фиксированный порядок классов, как и задано. **CAP-E — 2**: класс — прогноз исчерпания (survival/regression); данные — ряд остатков (нет) + темп продаж (есть, 26 недель); горизонт 7-30 дней; метрика — MAE дней до нуля, hit-rate «OOS в течение N дней»; первая версия — детерминированное деление с интервалом по вариации темпа, ML — после сезона.

### 3.7 Код к переиспользованию

Кода нет — только документы. Качество SPEC/ARCHITECTURE высокое: сущности сверены с миграциями на коммите `bbbcf6c` (`ARCHITECTURE.md:27-38`; таблицы `dim_warehouse_map`, `quality_check_results`, `fact_lineage_records`, `fact_order_counts`, `fact_attempt_runs` действительно есть в `db/migrations/`), явно обозначены расхождения (`run_id` vs `attempt_id`, CHECK на `acquired_via` — `:97-98`). Оценка переиспользуемости как спеки — 2.

### 3.8 Открытые вопросы (`SPEC.md:82-88`) и что требует отсутствующих данных

| Вопрос | Нужны данные, которых нет? |
|---|---|
| Доступ с сервера к Prices, Promotion, Feedbacks не проверен; без Promotion теряется класс «РК остановилась» (`:84`) | Да: 3 эндпоинта вне реестра, токен категорий на VPS не выдавался |
| Пороги значимости по классам (3 % цена, 0 при > 100 ₽/день РК) — годятся ли на другом кабинете (`:85`) | Да: нужен событийный ряд ≥ нескольких недель для калибровки |
| Что такое «активный склад»: приближение «остаток сегодня/вчера» vs доля по `supplier/sales.warehouseName` (`:86`) | Нет — `warehouseName` уже в реестре; нужна агрегация |
| Ранжирование при нескольких кандидатах (`:87`) | Да: история событий + обратная связь (auth) |
| Глубина хранения снапшотов (`:88`) | Решение, не данные |
| Не решено архитектурой (`ARCHITECTURE.md:103-108`): вью vs таблица для `event`, ретеншн, расписание | Решения при реализации |

### 3.9 Красные флаги и противоречия

- **Буквы CAP не совпадают между документами.** `BRAINSTORM.md:10-15, :25-29`: №1 «детектор качества» → CAP-C, №3 «прогноз OOS» → CAP-D, №4 «склады» → CAP-E, №6 «диагноз» → CAP-A+B. `SPEC.md:29-47`: CAP-B = полнота, CAP-C = география, CAP-D = диагноз, CAP-E = прогноз OOS. Любая ссылка «CAP-D» из брейншторма читается неверно.
- **Мёртвые/несуществующие эндпоинты в архитектуре:** `ARCHITECTURE.md:52` и `EXTRACTED.md:22` называют `/adv/v1/upd` и `/adv/v2/fullstats`; в коде скилла их нет, v2 мёртв (`api-endpoints.md:139`). Реальный `v3/fullstats` с лимитом ~1/мин делает ежедневный `snapshot_campaign.spend_rub` по nmId практически недостижимым — в спеке это не отражено.
- **Допущение «все шесть эндпоинтов живы»** (`SPEC.md:78`) опирается на личный кабинет Mike (`EXTRACTED.md:28`) — не факт для кабинета Амировой.
- **«Allowlist»** (`SPEC.md:54`, `ARCHITECTURE.md:99`): `tools/verify_business_signal.py:19-29` проверяет лишь наличие трёх обязательных и отсутствие двух запрещённых строк в `services/collector/src/business-signal/*.ts`; общего реестра эндпоинтов в коде нет — «внести в allowlist» означает расширить гейт, а не добавить строку в список.
- **Конфликт по `reportDetailByPeriod`** (`BRAINSTORM.md:33`): гейт запрещает, API-FACTS:28 показывает живой ответ с 96 полями; блокирует функции №9/№10 (маржа, хранение). Решение за Mike — вне кластера, но влияет на «отбор аномалий по деньгам», от которого зависит CAP-D (`SPEC.md:80`).
- **Иллюстративные цифры** в `BRAINSTORM.md:10-21` («23 400 ₽ хранения», «61 % против 78 %») — примеры формулировок, не факты; скоринг I/P/E субъективный.
- WRITE, скрейпинг, внешние платные API — нет (`SPEC.md:51, :67, :69`; `BRAINSTORM.md:39`: MPStats/Firecrawl/Apify вынесены за рамки).
- Устаревшая ссылка на ветку контрактов (`ARCHITECTURE.md:101`) — контракты уже в `contracts/`.

---

## 4. Сводка кластера

Шкалы: **расчётность** 0 = нет вычислений / 3 = полностью детерминированный код с формулами; **ML** 0-3 (см. обоснования в 1.5, 2.5, 3.6); **переиспользуемость** 0 = не брать / 3 = брать как есть.

| Скилл | Capability | Статус источника | WRITE? | Расч. | ML | Reuse |
|---|---|---|---|---|---|---|
| wb-daily-drops | Детект просадок/ростов по SKU vs бейзлайн 6 дн., фильтр объёма, «0 заказов», top-N | v3 history — реестр; Content (createdAt, brand) — READ вне реестра | нет | 3 | 2 | 2 |
| wb-daily-drops | Локализация первого сломанного этапа (open → CR → cart → CR → orders → sum) | v3 history — реестр | нет | 3 | 1 | 2 |
| wb-daily-drops | OOS_full / выпадение склада (снапшот vs вчерашний кэш) | `stocks-report/wb-warehouses` — не проверен | нет | 3 | 1 | 2 |
| wb-daily-drops | РК-флаги RK_off/dropped/boosted (по умолчанию SUMMARY_ONLY) | Promotion `promotion/count`, `v3/fullstats` — READ вне реестра, ~1 req/min | нет | 3 (факт. 1) | 1 | 1 |
| wb-daily-drops | Цена изменилась ≥ 3 % (снапшот vs кэш) | Prices `list/goods/filter` — READ вне реестра | нет | 3 | 0 | 1 |
| wb-daily-drops | Свежий негатив ≤ 3★ за 48 ч | Feedbacks — READ вне реестра; ПД | нет | 2 | 1 | 1 |
| wb-daily-drops | Excel 7 листов + Live HTML + cron 11:00 | Cowork MCP, Chart.js CDN — внешний | нет | 0 | 0 | 0 |
| wb-analytics | Воронка v3: products / history / grouped | history — реестр; products, grouped — не проверены | нет | 0 | 0 | 1 |
| wb-analytics | Поисковые запросы v2 (5 методов) | READ вне реестра; тариф/«Джем» | нет | 0 | 0 | 1 |
| wb-analytics | История остатков v2 (4 метода) + CSV `STOCK_HISTORY_*` | READ вне реестра, не проверен; потенциальная замена снапшотов CAP-A | нет | 0 | 0 | 1 |
| wb-analytics | Async CSV create/list/retry/file | create/list — реестр; file/retry — не проверены; квота 20/день разделяемая | нет | 0 | 0 | 1 |
| event-diagnosis | CAP-A событийный слой (4 снапшота) | Prices/Promotion/Feedbacks — вне реестра; stocks — не проверен | нет | 3 (спека) | 0 | 2 |
| event-diagnosis | CAP-B полнота данных | данные лестницы (`quality_check_results`) | нет | 3 | 0 | 2 |
| event-diagnosis | CAP-C география остатков | `sales.warehouseName` — реестр; stocks — не проверен | нет | 3 | 1 | 2 |
| event-diagnosis | CAP-D диагноз (классы → метрика, окно D..D-1, `not_explained`) | зависит от CAP-A | нет | 3 | 2 | 2 |
| event-diagnosis | CAP-E прогноз исчерпания остатка | orders — реестр; stocks — не проверен | нет | 3 | 2 | 2 |

**Выводы**

1. В кластере нет ни одного WRITE-вызова, скрейпинга или платного внешнего API; единственные внешние зависимости — платформа Cowork (MCP-артефакт, планировщик) и CDN, обе для лестницы не нужны.
2. Из семи источников `wb-daily-drops` в реестре AD-4 только v3 history; `stocks-report` в коллекторе, но не проверен; Content, Promotion, Prices, Feedbacks — READ вне реестра и проверены лишь на личном кабинете Mike (`EXTRACTED.md:28`). Каждый из них — отдельное решение о токене категории и расширении гейта.
3. Расчётное ядро скилла (`detect_drops.py`, ~280 строк, без LLM) переносится в control-plane как порт с исправлением четырёх расхождений: 6 vs 7 дней, порог ненадёжности 3 vs 4, «14-дневные» графики при 7 днях данных, недокументированный порог `drop_pct/4` п.п.; общесистемный порог зашит 20 %.
4. На данных лестницы уже сейчас считается больше, чем умеет скилл: просадки заказов по SKU к **медиане 14 дней** (26 недель `orders`, а не 6-дневное среднее), локализация этапа на `fact_funnel_daily`, ценовой ряд nmId из `priceWithDisc`/`spp` строк заказов (события цены без Prices API), доля склада в продажах из `warehouseName` (CAP-C). Норма по воронке — не раньше конца октября (API-FACTS:67).
5. Три вещи нельзя получить из реестра: ряд остатков по складам, расход рекламы по nmId (даже при доступе — лимит ~1/мин ломает утренний прогон; реалистичен только статус кампаний), отзывы. Календарь акций и `createdAt` карточек — ручной ввод/Content API; частичная замена — скачок `discountPercent`/`spp` в заказах и первая дата наблюдения nmId.
6. Указание из `wb-analytics` на v2 «История остатков» и CSV `STOCK_HISTORY_*` стоит проверить 1-3 вызовами до проектирования CAP-A: если ряд остатков доступен с WB, ежедневные снапшоты остатков и постфактум-проверка CAP-E не требуют накопления с нуля.
7. ML в кластере — не первый шаг: ряды по SKU разрежены (≈ 70 заказов/день на кабинет), поэтому на 2026 год выигрывают робастные статистики; реальный ML-потенциал (2) — в ранжировании причин CAP-D после накопления событий и обратной связи (auth заморожен) и в прогнозе исчерпания CAP-E после появления ряда остатков.
8. Документы event-diagnosis содержат две ошибки, которые попадут в PRD при копировании: буквы CAP-B..E в `BRAINSTORM.md` перепутаны относительно `SPEC.md`, а `ARCHITECTURE.md:52` называет `/adv/v1/upd` и мёртвый `/adv/v2/fullstats` вместо реального `v3/fullstats`.
9. Для PRD кластер естественно делится на две capability лестницы: «отклонения по SKU + локализация этапа» (M-04, данные есть) и «событийный слой + диагноз + прогноз OOS» (M-05; требует 3-4 READ-эндпоинтов вне реестра, ежедневных снапшотов и старта их сбора как можно раньше — история событий не бэкфиллится, `SPEC.md:25`).
10. Безопасность при переносе: скилл держит один JWT на шесть категорий в открытом файле; в лестнице — split-токены read-only на VPS; персональные данные отзывов (`userName`, текст) в снапшоты не переносить без решения.
