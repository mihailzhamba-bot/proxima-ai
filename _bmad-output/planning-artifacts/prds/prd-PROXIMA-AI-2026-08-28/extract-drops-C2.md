# Extract C2 «Реклама: аналитика и слив бюджета» — дропы `.orca/drops/функции новые/skills/`

Дата извлечения: 2026-09-02. Режим: read-only анализ трёх скиллов (markdown, bash, python, json, yaml), без запуска и без обращений к WB API. Значения токенов в дропах не найдены (скан `eyJ…` и присваиваний `token/key/secret = "…"` по всем трём каталогам пуст).

Сокращения путей (все относительно корня репо):

- `PS/` = `.orca/drops/функции новые/skills/wb-promotion-stats/`
- `LF/` = `.orca/drops/функции новые/skills/wb-rk-leak-finder/`
- `PR/` = `.orca/drops/функции новые/skills/wb-promotion/`
- `spec` = `PR/references/api-spec.yaml` (OpenAPI 3.0.1 «Маркетинг и продвижение», 219 КБ, `spec:1-3`)

Легенда статуса источника: **в реестре AD-4** / **READ вне реестра** / **WRITE** / **мёртв** / **не проверен** / **внешний сервис** / **ручной ввод**. Реестр AD-4 сегодня: statistics `supplier/orders`, `supplier/sales`, analytics `v3/sales-funnel/products/history`, `v2/nm-report/downloads`; мёртвые: `supplier/stocks`, `supplier/incomes`, `v2/nm-report/detail(/history)` (`docs/state/API-FACTS.md:26-31`); не проверен: analytics `v1/stocks-report/wb-warehouses` (`API-FACTS.md:34`).

## 0. Контекст, общий для кластера

1. **Все три скилла работают с WB Promotion API (`https://advert-api.wildberries.ru`) — категория токена «Продвижение» (`x-category: advert`, `spec:2846`).** На VPS этого токена нет: `docs/state/INVENTORY.md:215` («Отсутствуют: `wb_prices_token`, `wb_promotion_token`»), задача PA-15 (`docs/state/BACKLOG-REVIEW.md:46`). Обвязка под него в репо уже есть: `WB_PROMOTION_TOKEN_FILE` (`tools/wb_api_probe.py:31,66`, `infra/bootstrap/prepare-day1-runtime.sh:51`), ping `advert-api.wildberries.ru/ping` (`tools/wb_api_probe.py:84`).
2. **Ни один advert-эндпоинт не входит в реестр AD-4 и не проверялся на кабинете** — в `API-FACTS.md` нет ни одного вызова к advert-api. Все статусы ниже для advert-api = «READ вне реестра, не проверен» либо «WRITE».
3. Спека даёт машинный признак безопасности: `x-readonly-method: true` стоит на 22 путях из 36; WRITE-пути включают GET-мутации (`GET /adv/v0/start|pause|stop|delete?id=`, `spec:749-923`). Следствие для гейта: allowlist по пути + `x-readonly-method`, а не по HTTP-методу.
4. Дневной ряд лестницы, на который переформулируются capabilities: `fact_cabinet_daily(tenant_id, calendar_day, run_id, orders_count, cancelled_count, sales_count, returns_count, revenue_rub, forpay_rub, evidence_sha256[])` (`_bmad-output/implementation-artifacts/story-1.6.md:72`); `norm_daily` — медиана 14 полных дней, `UNIQUE(tenant, evaluation_day, metric, run_id)` (architecture `.memlog.md` AD-6, AD-8); `fact_funnel_daily(open_count, cart_count, order_count, order_sum_rub, buyout_count, buyout_sum_rub, wishlist_count)` (`architecture-proxima-ai-2026-08-30/reviews/review-adversarial.md:106`).

---

## 1. `wb-promotion-stats` — READ-статистика рекламных кампаний (CLI)

### 1.1 Capability

Bash-обёртка над шестью READ-эндпоинтами статистики WB Promotion: полная статистика кампаний, история списаний, история пополнений, статистика поисковых кластеров (v0 агрегат, v1 по дням), статистика медиакампаний. Расчётов нет — JSON API печатается через `jq` (`PS/scripts/wb-promo-stats.sh:30-51`).

- Пользователь: продавец WB через агента OpenClaw (`{baseDir}` подставляется платформой, `PS/SKILL.md:18`).
- Триггер: любой вопрос про деньги/расходы/метрики РК — CTR/CPC/CPM, кластеры, normquery, история затрат и пополнений (`PS/SKILL.md:4-8`).
- Дата версии: явной нет. Следы: примеры дат 2026-02 (`PS/SKILL.md:131-134`), в changelog соседнего скилла запись 2026-02-15 «expenses: добавлена новая команда для GET /adv/v1/upd» (`PR/references/changelog.md:19`) — скилл отпочкован от `wb-promotion` в феврале 2026.

### 1.2 Входы

Токен: env `WB_API_KEY` или флаг `--key=<token>` (`PS/scripts/wb-promo-stats.sh:10-17`), заголовок `Authorization: <JWT>` (`:27`). Категория — promotion/advert для всех строк.

| Команда | Метод и URL (file:line) | Тип по спеке | Лимит/батч (спека) | Статус для PROXIMA |
|---|---|---|---|---|
| `stats` | `GET /adv/v3/fullstats?ids=<csv≤50>&beginDate=&endDate=` (`wb-promo-stats.sh:70`) | READ (`spec:2845`) | 3/мин, интервал 20 с (`spec:2858-2862`); период ≤31 день (`spec:2852`); только статусы 7/9/11 (`spec:2854`) | READ вне реестра, не проверен |
| `expenses` | `GET /adv/v1/upd?from=&to=` (`:76`) | READ (`spec:1440`) | 1/сек; интервал 1-31 день (`spec:1466-1469`) | READ вне реестра, не проверен |
| `payments` | `GET /adv/v1/payments?from=&to=` (`:86`) | READ (`spec:1558`) | 1/сек; ≤31 день | READ вне реестра, не проверен |
| `clusters-stats` | `POST /adv/v0/normquery/stats` body `{from,to,items:[{advert_id,nm_id}]}` (`:103`), вспомогательно `GET /api/advert/v2/adverts?ids=` для nm_id (`:99`) | READ (`spec:1798`) | 10/мин, интервал 6 с (`spec:1813-1815`); только cpm-кампании (`spec:1806-1807`); ≤100 items | READ вне реестра, не проверен |
| `normquery-stats` | `POST /adv/v1/normquery/stats` (`:111`) | READ (`spec:3548`) | 10/мин, 6 с | READ вне реестра, не проверен |
| `media-stats` | `POST https://advert-media-api.wildberries.ru/adv/v1/stats` body `[{id}]` (`:121`) | READ (`spec:3249`) | 10/сек | READ вне реестра, не проверен; для нашего кабинета неактуален (медиакампании) |

WRITE-эндпоинтов в скилле нет; SKILL.md явно отсылает к `wb-promotion` за управлением (`PS/SKILL.md:143-148`).

Поля ответов (по спеке, важны для переноса):

- fullstats: верхний уровень `advertId, views, clicks, ctr, cpc, cr, sum (Затраты ₽), sum_price (Сумма заказов ₽), orders, shks (заказанных товаров шт.), atbs (корзины), canceled, boosterStats[], days[]`; `days[].apps[].nms[]` — разрез день × платформа (`appType`) × артикул (`spec:4684-4760`, пример `spec:2870-2930`). `cr` = заказы/клики (`spec:4727-4730`).
- normquery v0: `stats[]{advert_id, nm_id, stats[]{norm_query, views, clicks, ctr, cpc, cpm, atbs, orders, avg_pos, shks, spend}}` (`spec:3871-3930`). **`orders` и `spend` по кластеру в спеке есть.** Скилл описывает другой формат — `{clusters:[{cluster, count, views, clicks, ctr, sum}]}` (`PS/SKILL.md:71-78`); расхождение унаследовано leak-finder'ом (см. 2.7).
- normquery v1: `items[]{advertId, nmId, dailyStats[]{date, stat{normQuery, views, clicks, ctr, cpc, cpm, atbs, orders, shks, spend, avgPos}}}` (`spec:3583-3620`) — **дневной ряд по кластеру с заказами и расходом**, лучший источник для ежедневного сигнала.
- upd: `updNum, updTime, updSum, advertId, campName, advertType, paymentType (Баланс/Бонусы/Счёт/Кэшбэк), advertStatus` (`spec:1484-1515`) — журнал фактических списаний.
- payments: `id, date, sum, type (0 счёт/1 баланс/3 картой), statusId, cardStatus` (`spec:1598-1630`).

### 1.3 Расчёт

Отсутствует. Скилл — pass-through `curl → jq` (`wb-promo-stats.sh:30-51`); единственная логика — портируемый `date -d/-v` для «N дней назад» (`:53-57`), дефолт 7 дней для `payments`/`clusters-stats` (`:82, :96`) и извлечение `nm_id` первого артикула кампании через `/api/advert/v2/adverts` (`:99-100`). Правила батчинга (50 IDs + `sleep 20`, при 429 пауза 60-120 с без ретраев) — текст для LLM (`PS/SKILL.md:105-125`). Интерпретация цифр целиком на LLM в чате — формулы в скилле не заданы.

### 1.4 Выход

JSON в stdout (через `jq .`), при ошибке `HTTP <code>` и тело в stderr, exit 1 (`wb-promo-stats.sh:38-51`). Рекомендаций нет.

### 1.5 Переформулировка как per-tenant capability PROXIMA

Это не capability, а **адаптер источника**. В лестнице превращается в ежедневный сбор трёх фактов (все с `run_id`, идемпотентно, версия по прогону как `fact_cabinet_daily`):

| Факт | Источник | Зерно | Глубина/окно |
|---|---|---|---|
| `fact_advert_daily` | `GET /adv/v3/fullstats` | tenant × advert_id × nm_id × calendar_day × platform: views, clicks, spend_rub (`sum`), orders, shks, order_sum_rub (`sum_price`), atbs, canceled | вызов ≤31 день; 3/мин → 1 кабинет с ≤50 активными РК = 1 вызов/день; перекрытие `[run_day-3, run_day-1]` (лаг обновления статистики неизвестен — проверить) |
| `fact_advert_cluster_daily` | `POST /adv/v1/normquery/stats` | tenant × advert_id × nm_id × norm_query × calendar_day: views, clicks, spend, orders, shks, atbs, avgPos | 10/мин, ≤100 items; N вызовов = ceil(активных пар advert×nm / 100) |
| `fact_advert_upd` | `GET /adv/v1/upd` | tenant × advert_id × updTime: updSum, paymentType | ≤31 день; сверка Σ`updSum` по дню с Σ`sum` fullstats (контроль расхода) |

Ежедневные сигналы строятся уже над этими фактами (раздел 2.5). Необходимые действия до сбора: READ-only токен «Продвижение» на VPS (PA-15), эндпоинты в allowlist `tools/verify_business_signal.py`, сессия разведки по образцу `API-FACTS.md` (глубина назад fullstats, реальная структура normquery v0/v1, лимиты из заголовков).

ML-потенциал: **0** сам по себе (ingestion). Как база данных — обязательное условие для ML-потенциала 2 у leak-finder.

### 1.6 Код к переиспользованию

- `PS/scripts/wb-promo-stats.sh` — bash, 161 строка; зависимости `curl`, `jq`, `python3` (парсинг JSON аргументов `:67-69, :100`). Тестов нет. Секретов нет.
- Переиспользовать: карту эндпоинтов, параметры (`ids`/`beginDate`/`endDate`, не `dateFrom/dateTo`), лимиты и правила батчинга — как спецификацию TS-клиента по паттерну `services/collector/src/business-signal/wb-client.ts` (`API-FACTS.md:53`). Сам bash в runtime не переносится (проект — TypeScript collector; секреты только из файла, не из argv).

### 1.7 Красные флаги

- `--key=<token>` в argv (`wb-promo-stats.sh:13-16`) — токен виден в `ps` и истории shell; нарушает правило «значения токенов никуда не выводить».
- Формат ответа `normquery/stats v0` в SKILL.md (`PS/SKILL.md:71-78`) не совпадает со спекой (`spec:3871-3930`) — источник каскадной ошибки в leak-finder.
- Пометки «Проверено ✅» относятся к чужому кабинету в феврале 2026; для PROXIMA всё «не проверено».
- Media API и `payments` — вне потребностей M-0x; тащить не нужно.

---

## 2. `wb-rk-leak-finder` — аудит слива рекламного бюджета

### 2.1 Capability

Пайплайн: собрать активные РК → fullstats за 7 дней (заканчивая вчера) → кластеры normquery → заказы/выкупы/остатки из Statistics → 8 правил-детекторов слива → оценка экономии ₽ и приоритет P1-P3 → Excel-отчёт из 9 листов + JSON-саммари в чат (`LF/SKILL.md:105-126`, `LF/scripts/run_audit.py:152-179`).

- Пользователь: продавец WB; онбординг из 8 вопросов по одному (`LF/SKILL.md:45-103`, `run_audit.py:49-137`), в агентном режиме — через AskUserQuestion (`LF/scripts/utils.py:264-265`).
- Триггер: «слив бюджета РК», «куда уходят деньги в рекламе», «аудит рекламы», «РК с плохим ДРР», «какие кластеры отключить» (`LF/SKILL.md:8-11, 21-32`).
- Дата версии: живая проверка API 2026-05-27 (`LF/SKILL.md:247, 269`); `detect_leaks.py` v2.0 pandas (`LF/scripts/detect_leaks.py:2`); упоминание deprecated `supplier/stocks` «PLUG-404-20260720» (`LF/scripts/fetch_analytics.py:84-85`) — правки не раньше 20.07.2026. Примеры сгенерированы 2026-05-27 (`LF/examples/sample_leaks.json:285`).

### 2.2 Входы

Два токена: `wb_promotion_jwt` (advert-api) и `wb_analytics_jwt` (на деле **Statistics-категория**: host `statistics-api.wildberries.ru`, `utils.py:208-209, 239-248`). Хранятся в `.wb-leak-finder/settings.json` с chmod 0600 (`utils.py:100-110`).

| Эндпоинт (file:line) | Категория | Назначение в скилле | Статус для PROXIMA |
|---|---|---|---|
| `GET /adv/v1/promotion/count` (`collect_campaigns.py:57`; валидация токена `utils.py:230`) | promotion | ID кампаний по статусам; берутся 9 и 11 (`collect_campaigns.py:34, 60-70`); `type` кампании — отсюда (`:73-85`) | READ вне реестра, не проверен |
| `GET /api/advert/v2/adverts?ids=<csv≤50>` (`collect_campaigns.py:111-113`, sleep 1.2 с `:40`) | promotion | справочник РК: `settings.name/payment_type/placements`, `nm_settings[].nm_id/bids_kopecks/subject`, `status`, `timestamps` (`:92-104`); старый `/adv/v1/promotion/adverts` → 404 (`:7`, `LF/SKILL.md:252-254`) | READ вне реестра, не проверен |
| `GET /adv/v3/fullstats` (`fetch_stats.py:72-74`; батч 50, sleep 20 `:31-32, :81-83`) | promotion | расход/заказы/выручка по дням, платформам, артикулам; период `[today-7, today-1]` (`fetch_stats.py:44-47`) | READ вне реестра, не проверен |
| `POST /adv/v0/normquery/stats` (`fetch_stats.py:105-106`; по одной РК, ≤100 nm `:102`, sleep 6 `:127`) | promotion | кластеры; парсер ждёт `payload["clusters"][]{cluster,count,views,clicks,sum,ctr}` (`detect_leaks.py:447-454`) | READ вне реестра; **формат не по спеке** (2.7) |
| `GET /api/v1/supplier/orders?dateFrom=<ISO>&flag=0` (`fetch_analytics.py:61-62`) | statistics | заказы по nm (без `isCancel`, сумма `priceWithDisc`) (`:110-121`) | **в реестре AD-4** |
| `GET /api/v1/supplier/sales?dateFrom=&flag=0` (`fetch_analytics.py:73-74`; валидация токена `utils.py:246-248` с `dateFrom=2020-01-01`) | statistics | выкупы/возвраты по nm: `saleID` с `R` = возврат (`:124-142`) | **в реестре AD-4**; валидационный вызов тянет весь 6-месячный ряд (~9 МБ, лимит 1/мин, `API-FACTS.md:24`) |
| `GET /api/v1/supplier/stocks?dateFrom=` (`fetch_analytics.py:91-92`) | statistics | остатки → `oos_nms` при `Σquantity == 0` (`:145-167`); при 404 тихо возвращает `[]` (`:93-101`) | **мёртв** (`API-FACTS.md:26`); OOS-детектор фактически отключён |
| Ручной ввод (`utils.py:64-68`) | — | `target_drr_pct=20`, `min_spend_for_audit_rub=500`, `spend_zero_orders_threshold_rub=1500`, `bad_drr_multiplier=1.5`, `attribution_mode=orders|buyouts`, `period_days=7` (`:79`) | ручной ввод |

Замена для остатков, которую предлагает SKILL.md — `/api/v3/stocks/{warehouse}` (`LF/SKILL.md:119`, `fetch_analytics.py:99`) — это Marketplace API (склад продавца FBS), не остатки WB; для PROXIMA правильный кандидат — analytics `v1/stocks-report/wb-warehouses` (уже в коллекторе, не проверен, `API-FACTS.md:54`).

WRITE-вызовов в скилле нет. Существующие минус-фразы (`/adv/v0/normquery/get-minus`) не запрашиваются, хотя SKILL.md обещает их учитывать (`LF/SKILL.md:138`).

### 2.3 Расчёт (что считает код `detect_leaks.py`)

Все числа — детерминированный pandas-код; LLM не участвует в расчёте (онбординг, саммари в чат — `LF/SKILL.md:126`).

**Нормализация fullstats** (`detect_leaks.py:56-185`):

- строка на (advertId, date): `date = d["date"][:10]`, `spend = sum`, `revenue = sum_price`, `orders`, `clicks`, `views`, `canceled` (`:81-98`);
- по РК: `ctr = clicks/views·100`, `cpc = spend/clicks`, `cpm = spend/views·1000` (`:112-117`);
- по дню (все РК): `drr_pct = spend/revenue·100` (`:121-130`);
- по платформе `appType` 0 сайт / 1 android / 32 iOS / 64 desktop (`:44-49, :133-171`) и по артикулу из `apps[].nms[]` (`:149-180`).

**Базовые средние по кабинету** — взвешенные суммы, не среднее по РК (`:214-223`): `avg_ctr = Σclicks/Σviews·100`, `avg_cpc = Σspend/Σclicks`, `avg_cpm = Σspend/Σviews·1000`, `account_drr = Σspend/Σsum_price·100`.

**Порог входа**: РК с `spend < min_spend_for_audit_rub` пропускается (`:255-256`). Режим `buyouts`: `orders/revenue` РК заменяются на Σ по её артикулам `(buyouts − returns)` из Statistics (`:292-304`) — это выкупы всего кабинета по nm, не атрибуция к рекламе. `drr_pct = spend/revenue·100`, `inf` при нулевой выручке (`:306`).

| # | Правило (цитата кода) | Экономия | Приоритет |
|---|---|---|---|
| 1 Холостая РК | `orders == 0 and spend > zero_orders_threshold` (`:316`) | `spend` (`:319`) | 1 если `spend > 5000`, иначе 2 (`:320`) |
| 2 Плохой ДРР | `revenue > 0 and drr_pct > target_drr·bad_drr_multiplier` (`:323`), дефолт 20 %·1.5 = 30 % | `spend·(1 − target_drr/drr_pct)` (`:326`) | 1 если `drr_pct > 3·target`, иначе 2 (`:328`) |
| 3 OOS-алерт | артикул РК ∈ `oos_nms` (`:354`); `estimated_oos_days = max(1, in_way/avg_daily_orders + 2)`, `2` если в пути есть, `3` fallback (`:361-369`) | `nm_spend/period_days · estimated_oos_days` (`:370-372`) | 1 (`:383, :388`) |
| 4 Слабый кластер | `(cl_ctr < 0.5·avg_ctr and cl_spend > min_spend)` или `(РК в dead_campaigns and cl_spend > min_spend)` или `(orders == 0 and cl_spend > zero_threshold)` если поле `orders` есть (`:457-468`) | `cl_spend` (`:482`) | 2 если `cl_spend > zero_threshold`, иначе 3 (`:484`) |
| 5 Минус-фраза | каждый кластер из правила 4 → `phrase_to_add` (`:486-491`); без сверки с текущими минус-фразами | = кластер | — |
| 6 Каннибализация | кластер, где `len(nm_ids) ≥ 2 and len(advert_ids) ≥ 2` (`:518-519`); nm берутся из состава РК, а не из факта показов (`:509-515`) | Σ `spend` артикулов кроме топ-1 по расходу (`:522-532`; текст действия говорит «лучший по CR», `:536-538`) | 2 (`:540`) |
| 7 Дорогой CPM/CPC | `cpm > 1.5·avg_cpm` или `cpc > 1.5·avg_cpc` (`:331-333`) | 0, вторичный сигнал | — |
| 8 Низкий CTR | `ctr < 0.5·avg_ctr` (`:336`) | 0, вторичный сигнал | — |

Дополнительно: `platform_note` — площадка с максимальным расходом, если `orders == 0 and spend > 0.5·zero_threshold` (`:339-348`); `top_leak_skus` — экономия РК распределяется по артикулам пропорционально доле расхода (`:412-418`), top-10 (`:555-559`).

**Агрегация**: экономия РК = `max` по правилам 1-3 (`:319, :327, :387`), но `total_leak = Σ expected_saving_rub по всем рекомендациям` (`:565`) — РК, её кластеры и каннибализация складываются. Годовая оценка `total_leak · 52` (`:589`). Сортировка `(priority asc, saving desc)` (`:553`). Сегодняшний день исключён из окна из-за лага WB 6-12 ч (`:610-614`, `fetch_stats.py:41-46`); флаг `data_incomplete` при лаге последней записи ≥ 6 ч (`fetch_analytics.py:195-217`).

Проверка на фикстуре: `examples/sample_inputs/leaks.baseline.json:3-8` — `total_spend_rub 8190`, `total_leak_rub 10999`, годовая `571948` — **«потенциальная экономия» превышает весь расход за период на 34 %** (двойной счёт РК 1001: 3010 холостая + 2100 + 800 её кластеры + 2695 каннибализация).

### 2.4 Выход

- Excel `wb-rk-leak-audit-YYYY-MM-DD.xlsx` (`build_excel_report.py:414`), по умолчанию в `~/Downloads` (`:383-391`). Листы фактически 9 (порядок `:401-409`; в `examples/sample_output*.xlsx`: Сводка, Рекомендации, Топ-слив (РК), Слив по кластерам, Минус-фразы, Каннибализация, OOS-алерты, Топ-сливающих SKU, Методология); SKILL.md обещает 7 (`LF/SKILL.md:36`), docstring — 8 (`build_excel_report.py:4-12`).
- Поля: Сводка — расход, выручка с рекламы, ДРР кабинета и целевой, экономия за 7 дней и ×52, средние CTR/CPC/CPM, режим атрибуции (`:90-108`) + combo-график расход/выручка/ДРР по дням (`:142-163`); Топ-слив (РК) — priority, advertId, name, type, spend, orders, revenue, drr, ctr, cpc, cpm, reason, action, expected_saving, platform_note, secondary_flags (`:198-215`); Слив по кластерам (`:225-238`); Минус-фразы — advertId, campaign_name, phrase_to_add, spend_to_save (`:244-249`); Каннибализация (`:264-270`); OOS-алерты — nm_id, spend_7d, in_way_qty, estimated_oos_days (`:276-286`); Рекомендации — priority, action, reason, saving (`:292-299`); Методология — пороги, правила, источники, дата (`:303-332`).
- JSON-контракт `.wb-leak-finder/leaks.json` (`detect_leaks.py:635-647`) и stdout `{status, excel_path, summary, top_actions[:3]}` (`run_audit.py:174-179`).
- Тексты рекомендаций: «Выключить РК» (`:317`), «Снизить ставку до целевого ДРР N % или выключить» (`:325`), «Поставить РК на паузу до прихода товара или исключить nm_id» (`:381`), «Добавить в минус-фразы РК» (`:482`), «Оставить в кластере один SKU с лучшим CR; остальным добавить кластер в минусы» (`:536-538`) — все действия WRITE в кабинете, скилл их не выполняет.

### 2.5 Переформулировка как per-tenant capability PROXIMA

Формат лестницы: не разовый «аудит», а **ежедневные сигналы «расход × результат × норма»** над фактами из 1.5 и `fact_cabinet_daily` / `norm_daily`. Все сигналы детерминированы; LLM только объясняет.

Необходимая READ-аналитика рекламы (глубина указана для расчёта, не для бэкфилла):

- `fact_advert_daily` из `/adv/v3/fullstats` — 14 дней для нормы, 7 для сигналов, ежедневный инкремент с перекрытием 3 дня;
- `fact_advert_cluster_daily` из `/adv/v1/normquery/stats` — 7-14 дней;
- справочник РК из `/api/advert/v2/adverts` + `/adv/v1/promotion/count` — ежедневный снимок статусов/ставок/состава;
- текущие минус-фразы `/adv/v0/normquery/get-minus` (READ, `spec:2228`) — чтобы не рекомендовать уже добавленное;
- остатки из analytics `stocks-report/wb-warehouses` (уже в `business_signal_runs.stock_quantity`) — для OOS;
- бюджет/баланс `/adv/v1/budget?id=`, `/adv/v1/balance` (READ) — для сигнала «бюджет кончается».

Что можно считать ежедневно (per tenant, calendar_day = МСК, `run_id`):

| Сигнал | Формула | Норма/порог | Из скилла |
|---|---|---|---|
| S1 Расход без заказов | `spend_7d(advert) > T1 and orders_7d(advert) == 0` | `T1` — конфиг tenant (дефолт 1500 ₽, как в скилле) | правило 1 |
| S2 ДРР выше нормы | `drr_day = Σspend_day(advert-факты) / revenue_rub(fact_cabinet_daily)`; отклонение от `norm_daily(metric='drr_pct')` (медиана 14 дней) | `> norm · k` (k = 1.5 дефолт) — вместо ручного «целевого ДРР» | правило 2, переведено на норму кабинета |
| S3 Реклама на товар без остатка | `stock_quantity(nm) == 0 and spend_day(advert, nm) > 0` | без порога | правило 3, источник заменён |
| S4 Кластер-слив | по `fact_advert_cluster_daily`: `spend_7d(cluster) > T1 and orders_7d(cluster) == 0` или `ctr_7d(cluster) < 0.5 · ctr_7d(advert)` при `clicks ≥ n_min` | `n_min` защищает от малых выборок | правило 4, теперь с реальными `orders` из v1 |
| S5 Каннибализация | ≥2 nm с `spend_7d > 0` в одном `normQuery` (по факту показов) | — | правило 6, исправлено |
| S6 Аномалия расхода | `spend_day(advert)` vs `norm_daily(metric='advert_spend')` | `> norm + k·MAD` | новое (скилл не сравнивает периоды, `LF/SKILL.md:235`) |
| S7 Бюджет кончается | `budget(advert) / median(spend_day, 7) < 2 дней` | — | новое, из READ `budget` |

«Экономия» — только как «расход в зоне сигнала» за окно, `max` по правилам одной РК, без суммирования разных детекторов и без ×52.

**ML-потенциал: 2 из 3.**

- Класс задач: (a) детекция аномалий дневных рядов spend/orders/ДРР по РК и кабинету (unsupervised: robust z-score/MAD, STL с недельной сезонностью) — заменяет фиксированные 1500 ₽ и 0.5×CTR; (b) оценка конверсии кластера/артикула с shrinkage к среднему РК (empirical Bayes/beta-binomial) — чтобы «0 заказов при 15 кликах» не становилось минус-фразой; (c) позже — incrementality: регрессия `orders_count(fact_cabinet_daily)` на `spend` с лагами 0-3 дня, чтобы отличать «ДРР высок, но реклама даёт прирост» от слива.
- Данные: `fact_advert_daily` + `fact_advert_cluster_daily` ≥ 8 недель per tenant (сегодня 0 — сбор не запущен), `fact_cabinet_daily` (26 недель доступны, `API-FACTS.md:7`).
- Горизонт: сигналы — день; прогноз spend/orders — 1-7 дней.
- Метрика: доля подтверждённых сигналов (разметка Mike) / precision@k для (a)-(b); MAPE и покрытие интервала для (c).
- Обоснование оценки «2, не 3»: правила скилла — разумная baseline-эвристика, ML нужен для порогов и малых выборок, но без данных advert-api оценить эффект нельзя; «3» — только когда появится incrementality на ≥ 3 месяцах ряда.

### 2.6 Код к переиспользованию

| Файл | Язык/строк | Что внутри | Оценка |
|---|---|---|---|
| `LF/scripts/detect_leaks.py` | Python, 663 | `flatten_fullstats` (`:56-185`) — проверенный маппинг структуры fullstats (`days[].apps[].nms[]`, `nmId`, `date` ISO) и 8 правил | **переносить**: парсер — в TS-коллектор как схема `fact_advert_daily`; правила — как спецификация тестов сигналов S1-S5 |
| `LF/scripts/utils.py` | Python, 318 | `WBClient` с backoff 1→2→4 с, 429 → sleep 20 с, 401/403 → `WBAuthError` (`:125-193`); Settings dataclass (`:57-83`) | паттерн есть в `wb-client.ts`; не нужен |
| `LF/scripts/fetch_stats.py`, `collect_campaigns.py`, `fetch_analytics.py` | Python, 167/203/236 | батчинг, окна дат, агрегаты orders/sales/stocks по nm (`fetch_analytics.py:110-167`) | знания о параметрах — да; код — нет (Statistics уже в коллекторе) |
| `LF/scripts/build_excel_report.py` | Python, 422, openpyxl | 9 листов + 2 графика | не нужен (сводка в webapp) |
| `LF/scripts/dev/regen_fixtures.py`, `compare_baseline.py` | Python, 306/178 | генератор синтетических входов (3 РК × 7 дней, `:10-18`) и regression-сравнение с допуском ±0.02 (`compare_baseline.py:31`) | образец структурных фикстур; сам baseline расходится с `sample_leaks.json` (`total_leak` 10999 vs 8304) — эталон нестабилен |
| `LF/examples/sample_inputs/*.json` | JSON | обезличенные входы (advertId 1001-1003, nm 111111-444444) | пригодны как структурные фикстуры после проверки формата v0/v1 |

Зависимости: Python ≥ 3.9, `requests`, `pandas`, `openpyxl` (`LF/SKILL.md:206`); `run_audit.sh:24` проверяет только `requests`, `openpyxl` — `pandas` не проверяется. Unit-тестов нет. Секреты: значений нет; JWT пишутся в `.wb-leak-finder/settings.json` рядом со скриптами (`utils.py:30-31, :100-110`).

### 2.7 Красные флаги

1. **Парсер кластеров не совпадает со спекой.** Код читает `payload["clusters"][]` с полями `cluster/count/sum` (`detect_leaks.py:447-454`), спека отдаёт `stats[].stats[]` с `norm_query/spend/orders` (`spec:3871-3930`). В live-прогоне `cluster_leaks`, `minus_words`, `cannibalization` пусты (`LF/examples/sample_leaks_live.json:97-100`) — детекторы 4-6 на реальном кабинете, вероятно, не срабатывали.
2. **OOS-детектор мёртв**: `supplier/stocks` 404 (`API-FACTS.md:26`), код тихо возвращает `[]` (`fetch_analytics.py:93-101`); предложенная замена `/api/v3/stocks/{warehouse}` — Marketplace API, не остатки WB.
3. **Двойной счёт экономии** (`:565`) и экстраполяция ×52 (`:589`): на фикстуре экономия 10 999 ₽ при расходе 8 190 ₽ (`leaks.baseline.json:3-8`). В сводке PROXIMA недопустимо — каждое число со SourceRef и без выдуманных горизонтов.
4. **Атрибуция**: `sum_price` fullstats — «сумма заказов» по WB-атрибуции, режим `buyouts` подменяет её выкупами всего кабинета по nm (`:292-304`) — смешение; в PROXIMA ДРР считать от `revenue_rub` кабинета (S2) и явно называть базу.
5. **Каннибализация по составу РК**, а не по факту показов (`:509-515`) — РК с 20 артикулами даст ложные пары; «лучший по CR» в тексте против «по расходу» в коде (`:531`, `:536`).
6. **Минус-фразы без сверки с существующими** — `get-minus` не вызывается, обещание `LF/SKILL.md:138` не выполнено.
7. **Валидация Statistics-токена** вызовом `sales` с `dateFrom=2020-01-01` (`utils.py:246-248`) — полный 6-месячный ряд ради проверки 401, при лимите 1/мин.
8. **WRITE-действия** не выполняются, но каждая рекомендация — WRITE в кабинете (пауза, ставка, минус-фразы); в описании соседний WRITE-скилл (`LF/SKILL.md` не ссылается, но `PS/SKILL.md:143-148` — да). В PROXIMA: рекомендация + ссылка на кабинет, действие делает человек.
9. **Чужие коммерческие данные** в дропе: реальные advertId/nmId/названия кампаний живого кабинета (`LF/examples/sample_leaks_live.json:21-22, 41-42, 60-61, 79-80`, `sample_output_live.xlsx`) — не использовать как фикстуры и не переносить в репо.
10. Токены plaintext на диске (`settings.json`), Excel в `~/Downloads` (`build_excel_report.py:391`), `pip install --break-system-packages` (`run_audit.sh:30`) — всё вне контура проекта.
11. Онбординг просит «целевой ДРР» и пороги в рублях у пользователя (`LF/SKILL.md:65-93`) — в лестнице это конфиг tenant с калибровкой (PMM-35), не вопрос в чате.

---

## 3. `wb-promotion` — управление рекламными кампаниями (CLI, READ + WRITE)

### 3.1 Capability

Полный CLI над Promotion API: просмотр кампаний, создание, запуск/пауза/остановка/удаление, ставки, места размещения, состав артикулов, пополнение бюджета, кластеры и минус-кластеры, медиакампании, календарь акций (`PR/SKILL.md:3-11`). Расчётов нет.

- Пользователь: продавец/агент; активация «даже если пользователь не упоминает API» — любые вопросы про рекламу, ставки, бюджеты (`PR/SKILL.md:8-11`).
- Дата версии: changelog 2026-02-14 и 2026-02-15 (`PR/references/changelog.md:3, 11`); примеры спеки 2025-09..2026-01.

### 3.2 Входы

Токен `WB_API_KEY`/`--key=` (`PR/scripts/wb-promo.sh:10-17`). Домены: `advert-api`, `advert-media-api` (`:8-9`), `dp-calendar-api` (`:276-304`). Классификация по `x-readonly-method` спеки:

**READ (кандидаты в реестр, все «не проверен»):**

| Команда | URL (file:line) | Ценность для PROXIMA |
|---|---|---|
| `list` | `GET /adv/v1/promotion/count` (`:70`) | справочник РК/статусов — да |
| `info`, `campaign-nms` | `GET /api/advert/v2/adverts?ids=&statuses=&payment_type=` (`:83, :182`) | состав, ставки, размещения — да |
| `balance`, `budget` | `GET /adv/v1/balance` (`:161`), `GET /adv/v1/budget?id=` (`:166`); значения в копейках (`PR/SKILL.md:29, 209`) | сигнал S7 «бюджет кончается» — да |
| `subjects`, `nms`, `min-bids` | `GET /adv/v1/supplier/subjects` (`:101`), `POST /adv/v2/supplier/nms` (`:107`), `POST /api/advert/v1/bids/min` (`:113`) | только для создания РК — нет |
| `clusters-list`, `clusters-bids-get`, `clusters-minus-get` | `POST /adv/v0/normquery/list` (`:203`), `/get-bids` (`:209`), `/get-minus` (`:227`) | минус-фразы и ставки по кластерам — контекст для S4 — да |
| `media-count/list/info` | `GET media/adv/v1/count|adverts|advert` (`:240, :254, :259`) | нет |
| `promos`, `promo-details`, `promo-nms` | `GET dp-calendar-api /api/v1/calendar/promotions[/details|/nomenclatures]` (`:276, :281, :298`) | другой кластер (акции), не C2 |

**WRITE (запрещено политикой WB READ-only; в PROXIMA — Non-Goal):**

| Команда | URL (file:line) | Что меняет |
|---|---|---|
| `create` | `POST /adv/v2/seacat/save-ad` (`:92`) | создаёт РК |
| `start` / `pause` / `stop` / `delete` | `GET /adv/v0/start|pause|stop|delete?id=` (`:120, :125, :130, :135`) | статус РК — **мутация через GET** |
| `rename` | `POST /adv/v0/rename` (`:142`) | имя |
| `set-bids` | `PATCH /api/advert/v1/bids` (`:148`) | ставки CPM/CPC |
| `set-placements` | `PUT /adv/v0/auction/placements` (`:154`) | места размещения |
| `update-nms` | `PATCH /adv/v0/auction/nms` (`:189`) | состав артикулов |
| `deposit` | `POST /adv/v1/budget/deposit?id=` (`:174`), мин. 1000 ₽ кратно 50 (`PR/SKILL.md:33, 203`) | **списывает деньги** |
| `clusters-bids-set` / `clusters-bids-delete` | `POST|DELETE /adv/v0/normquery/bids` (`:215, :221`) | ставки по кластерам |
| `clusters-minus-set` | `POST /adv/v0/normquery/set-minus` (`:233`); пустой массив удаляет все минус-фразы (`rate-limits.md:34`) | минус-кластеры |
| `promo-upload` | `POST dp-calendar-api /api/v1/calendar/promotions/upload` (`:304`) | товары в акцию |

Статистика делегирована `wb-promotion-stats` (`PR/SKILL.md:141-144`).

### 3.3 Расчёт

Нет. Справочные знания: статусы `-1/4/7/8/9/11` (`PR/SKILL.md:173-179`), типы ставок `manual/unified`, оплаты `cpm/cpc`, размещения `search/recommendations/combined` (`:181-192`), копейки в `balance/budget` vs рубли в `deposit` (`:209`), таблица лимитов по 36 методам (`PR/references/rate-limits.md:5-43`; fullstats «самый опасный» `:58`; при 429 пауза 60-120 с `:72-75`).

### 3.4 Выход

JSON в stdout, `HTTP <code>` в stderr (`wb-promo.sh:50-63`).

### 3.5 Переформулировка

Для PROXIMA от скилла нужны две вещи:

1. **READ-справочник кампаний** (`promotion/count`, `v2/adverts`, `budget`, `balance`, `normquery/list|get-bids|get-minus`) как ежедневный снимок `dim_advert_campaign` (tenant, advert_id, name, type, status, payment_type, placements, bids_kopecks, nm_ids, budget_kopecks, snapshot_day, run_id) — контекст сигналов S1-S7 и источник S7.
2. **`references/api-spec.yaml`** как артефакт: `x-readonly-method` по 36 путям — готовая машинная основа для allowlist гейта (`tools/verify_business_signal.py`), включая правило «GET ≠ READ».

Все WRITE-возможности — навсегда в Non-Goals: политика проекта (WB READ only, никаких мутаций как продуктового действия). ML-потенциал: **0**.

### 3.6 Код к переиспользованию

`PR/scripts/wb-promo.sh` — bash, 364 строки, `curl`/`jq`/`python3`; тестов нет; секретов нет. Переиспользовать только `api-spec.yaml` (219 КБ) и таблицу лимитов. Скрипт в runtime не допускать (содержит WRITE).

### 3.7 Красные флаги

- **14 WRITE-команд** (таблица 3.2), включая `deposit` с реальными деньгами; в changelog зафиксирован живой тест пополнения на 1000 ₽ и удаления РК (`PR/references/changelog.md:25-26`).
- **Триггер скилла слишком широкий** («любые вопросы про рекламу», `PR/SKILL.md:8-11`) + готовый цикл массовой паузы `for id in …; do wb-promo.sh pause $id` (`:59-60`) — агент с таким скиллом выполнит WRITE без явного подтверждения. В PROXIMA такой скилл не подключать ни в какой конфигурации.
- **GET-мутации** (`/adv/v0/start|pause|stop|delete?id=`) — фильтр «только GET» не защищает; allowlist по пути.
- `--key=` в argv (`wb-promo.sh:13-16`).
- Календарь акций (`dp-calendar-api`) и медиа — вне C2 и вне M-0x.

---

## 4. Сводка по кластеру C2

| Скилл | Capability | Статус источника | WRITE? | Расчётность 0-3 | ML-потенциал 0-3 | Переиспользуемость 0-3 |
|---|---|---|---|---|---|---|
| `wb-promotion-stats` | READ-статистика РК: fullstats, upd, payments, normquery v0/v1, media | READ вне реестра AD-4; promotion-токен на VPS отсутствует; не проверен | нет | 0 (pass-through curl→jq) | 0 сам по себе (как источник — база для ML=2) | 2 (карта эндпоинтов/полей/лимитов; bash не переносится) |
| `wb-rk-leak-finder` | 8 правил слива бюджета + экономия ₽ + приоритеты + Excel | promotion: READ вне реестра, не проверен; statistics `orders`/`sales`: в реестре AD-4; `supplier/stocks`: мёртв; пороги: ручной ввод | нет (только рекомендует WRITE-действия человеку) | 3 (детерминированный pandas, LLM не считает) | 2 (аномалии рядов spend/ДРР, shrinkage конверсии кластеров, позже incrementality) | 2 (`flatten_fullstats` + правила как спецификация сигналов; Excel/онбординг/HTTP — нет) |
| `wb-promotion` | CLI управления РК (create/start/pause/bids/deposit/minus) + READ-справочники + OpenAPI-спека | READ-подмножество вне реестра, не проверен; 14 WRITE-путей — запрещены политикой | **да**, 14 команд, включая деньги (`deposit`) | 0 | 0 | 1 (только `api-spec.yaml` с `x-readonly-method` и READ-справочник count/adverts/budget/balance/get-minus) |

Выводы:

1. Единственная вычислительная логика кластера — `LF/scripts/detect_leaks.py`; два других скилла — тонкие curl-обёртки без формул. Ценность кластера для PRD = правила детекции как спецификация + карта READ-эндпоинтов Promotion API.
2. Данные рекламы для PROXIMA сегодня недоступны: нет токена «Продвижение» на VPS (PA-15), нет advert-эндпоинтов в реестре AD-4, нет ни одного факта разведки. Предусловие любой единицы C2 — READ-only токен, сессия разведки по образцу `API-FACTS.md` (структура normquery v0/v1, глубина fullstats назад, лимиты из заголовков), allowlist в гейте.
3. Правила переносятся только с исправлениями: кластеры через `v1/normquery/stats` (дневной ряд с `orders`/`spend`, снимает главный дефект скилла), OOS через `stocks-report/wb-warehouses`, каннибализация по факту показов, `max` вместо суммы экономии по одной РК, без ×52, ДРР от выручки кабинета `fact_cabinet_daily.revenue_rub` с явно названной базой.
4. В лестнице реклама ложится в общий формат «метрика × норма × отклонение»: `drr_pct` и `advert_spend` — ещё две метрики `norm_daily` (медиана 14 дней, AD-6), сигналы S1-S7 — ежедневные строки сводки, а не отдельный «аудит» с онбордингом и Excel.
5. WRITE (пауза, ставки, минус-фразы, пополнение) — Non-Goal по политике WB READ-only; сводка выдаёт рекомендацию и ссылку в кабинет. Мутации через GET в Promotion API означают: гейт allowlist строится по пути и признаку `x-readonly-method` спеки, не по HTTP-методу.
6. ML-потенциал кластера 2/3 и целиком зависит от запуска ежедневного сбора `fact_advert_daily`/`fact_advert_cluster_daily`: как и у воронки, история не копится сама (окно вызова ≤31 день, глубина назад не проверена) — сбор нужно стартовать до того, как сигналы понадобятся.
7. Дроп содержит живые коммерческие данные чужого кабинета (`LF/examples/sample_leaks_live.json`, `sample_output_live.xlsx`) — в фикстуры проекта не брать; структурные обезличенные входы (`LF/examples/sample_inputs/`) пригодны после приведения к реальному формату спеки.
8. Расхождения между текстом и кодом внутри самого дропа (число листов 7/8/9, «лучший по CR» vs топ по расходу, обещанная сверка минус-фраз, формат кластеров) — сигнал, что скилл не проходил ревью; брать из него формулы, а не утверждения.
