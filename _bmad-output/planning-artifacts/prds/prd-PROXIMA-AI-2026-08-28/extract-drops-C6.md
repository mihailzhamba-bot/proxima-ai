# Extract C6 — «Юнит-экономика и тарифы» (кластер `wb-tariffs`)

Дата извлечения: 2026-09-02. Источник: `/home/proxima-admin/orca/proxima-ai-sunfish/.orca/drops/функции новые/skills/wb-tariffs/` — один файл `SKILL.md` (151 строка). Бандл `bundles/wb-tariffs.skill` содержит тот же единственный `SKILL.md` (zip, 2026-05-28). Справочник: `docs/state/API-FACTS.md`. Ссылки `file:line` — относительно каталога кластера, если не указано иное. Секреты: в кластере не найдены (скан по шаблонам JWT/API-key — пусто; имён переменных токенов в файле нет).

## 1. Скилл `wb-tariffs`

- **Capability:** собрать тарифы WB (комиссии по категориям, логистика/хранение по складам, возвраты, фактическое платное хранение) и недельный отчёт реализации для расчёта маржи/юнит-экономики SKU (`SKILL.md:12`, `:16-20`).
- **Пользователь:** селлер/менеджер в чате coding-агента (`MANIFEST.md:11` — установлен в `~/.codex/skills`, 28.05.2026).
- **Триггер:** любой вопрос про затраты, комиссии, логистику, хранение, возвраты, маржу — «даже если пользователь не говорит "тарифы"» (`SKILL.md:4-7`).
- **Версия:** 1.1, команды протестированы 2026-02-25 (`SKILL.md:150-151`); дроп датирован 28.05.2026.

## 2. Входы

| Команда | Эндпоинт (`SKILL.md`) | Хост | Лимит (`SKILL.md:79-87`) | Статус для PROXIMA |
|---|---|---|---|---|
| `commission` | `GET /api/v1/tariffs/commission` (`:37`) | common-api (`:46`) | 1/мин | READ вне реестра AD-4; в API-FACTS не вызывался — не проверен |
| `box` | `GET /api/v1/tariffs/box?date=` (`:38`) | common-api | 60/мин | READ вне реестра, не проверен |
| `return` | `GET /api/v1/tariffs/return?date=` (`:39`) | common-api | 60/мин | READ вне реестра, не проверен |
| `paid-storage` / `-status` / `-download` | `GET /api/v1/paid_storage?dateFrom=&dateTo=`, `…/tasks/{id}/status`, `…/tasks/{id}/download` (`:40-42`) | seller-analytics-api (`:47`) | 1/мин | READ вне реестра, асинхронный: GET создаёт серверную задачу отчёта (данные продавца не меняет), результат через 1-2 мин (`:71-75`); не проверен |
| `report` | `GET /api/v5/supplier/reportDetailByPeriod` (`:43`) | statistics-api (`:48`) | 1/мин | READ вне реестра, **gated**: `tools/verify_business_signal.py:27-29` запрещает в signal runtime. Факты: `docs/state/API-FACTS.md:28` — 96 полей, страница 100 000 строк = 210-220 МБ за 25 с, недельный разрез, лаг 1-8 дней (`:9`), бэкфилл 31 мес = 3-4 страницы (`:43`) |

- Параметры: `--date`, `--dateFrom/--dateTo`, `--taskId`, `--limit`, `--rrdid` (курсор пагинации), `--entity=amatrade` — переключение юрлица Amatrade/PWR (`:52-60`, `:111`).
- Токен-скоуп «Тарифы» в скилле не упомянут. По соседнему кластеру `skills/wb-agency-report/scripts/fetch.py:222-223,234,251`: common-api принимает `Authorization: <token>` **без** `Bearer` и отвечает 401 без скоупа Tariffs. Split-токен PROXIMA на этот скоуп не проверялся.
- Пробел: `GET /api/v1/tariffs/pallet` (паллетная логистика) и коэффициенты складов в скилле отсутствуют (список полей `:123-126` их не содержит).
- Ручной вход: себестоимость — только «из головы» пользователя, поля/файла для неё нет.

## 3. Расчёт

Единственная формула — одна строка, выполняется LLM в чате, кода нет:

> «`выручка (ppvz_for_pay) − себестоимость = маржа`; детализируй по delivery_rub, commission_percent, penalty» (`SKILL.md:29`).

- Порог, точка безубыточности, хранение и возвраты в марже — не заданы; `paid-storage` и `return` — «при необходимости дополни» (`:31`).
- Семантика: `ppvz_for_pay` = «к перечислению продавцу» (`:138`), т.е. уже нетто комиссии; логистика/хранение/штрафы — отдельные строки операций `supplier_oper_name` (`:135`). Скилл говорит «детализируй», а не «вычти» — итог зависит от интерпретации LLM.
- Ограничение источника: отчёт недельный (пн-вс), незакрытая неделя не попадает, «для ежедневной аналитики не подходит» (`:64-68`); данные с 29.01.2024 (`:69`; совпадает с `API-FACTS.md:9`).
- Ключевые поля (`:114-139`): commission — `subjectID/subjectName`, `kgvpMarketplace` (FBO), `kgvpSupplier` (FBS), `kgvpSupplierExpress`, `paidStorageKgvp`; box — `warehouseName`, `boxDeliveryBase/boxDeliveryLiter`, `boxStorageBase/boxStorageLiter`; paid-storage — `tariffFixDate`, `tariffLowerDate` (переименованы, `:129-130` — признак дрейфа API), `warehousePrice`; report — `nm_id`, `supplier_oper_name`, `delivery_rub`, `commission_percent`, `ppvz_for_pay`, `penalty`.

Для сравнения — что уже считает детерминированный код:

- Репо: `services/collector/src/business-signal/calculate.ts:18-32` `calculateMargins` — маржа/ед. по nmId = avg(`retailPriceWithDisc`, строки «Продажа») − Σ`ppvzSalesCommission`/ед. − Σ`deliveryService`(все строки)/ед. − `cogsRub` (Decimal, 2 знака). Вход — finance `POST /api/finance/v1/sales-reports/detailed` (`wb-client.ts:192-243`, `API-FACTS.md:54`; живым вызовом не проверен, `API-FACTS.md:34`).
- Соседний кластер `skills/wb-agency-report/scripts/transform.py:353-385` `build_tariff_lookups`: `commission_pct[subjectID] = kgvpMarketplace`; `avg_delivery_base` = среднее `boxDeliveryBase` по всем складам; `avg_storage_per_liter_per_day` (считается, в P&L не используется). `:388-443` `derive_pnl_per_sku`: `commission = revenue × pct/100`, `logistics = buyouts × avg_delivery_base`, `margin = revenue − commission − logistics`, `margin_pct`; **`DEFAULT_COMMISSION_PCT = 20.0`** для неизвестной категории (`:406`) — выдуманный дефолт; COGS, хранение, возвраты не учтены (это валовая маржа, не юнит-экономика).

## 4. Выход

Сырой JSON ответов эндпоинтов в чат (формат не задан); маржа — текст LLM. Файлов, таблиц, схемы результата нет. Потребитель — селлер в чате.

## 5. Переформулировка как per-tenant capability на данных лестницы

**Capability «Оценочная дневная маржа по SKU + недельная сверка с фактом».** По PRD маржа/P&L — сценарии W2-W4 (`prd.md:350`), т.е. ступень M-04+.

A. Дневная оценка (детерминированно, ежедневно, по `run_id`):
- Грейн `nm_id × calendar_day`. `fact_cabinet_daily` — кабинетный грейн без nm_id (`ARCHITECTURE-SPINE.md:51`: `orders_count, …, revenue_rub, forpay_rub`), поэтому источник — `stg_wb_sales_latest` (строка продажи содержит `nmId, forPay, priceWithDisc, spp, subject, warehouseName, saleID S/R` — `API-FACTS.md:24`), свёрнутый в новый `fact_sku_daily` по правилам AD-1/AD-3 (SKU-грейн спайн относит к M-04, `ARCHITECTURE-SPINE.md:317`).
- Формула на единицу: `margin_est = forPay − logistics_est − storage_est − return_est − cogs_rub`, где `forPay` уже нетто комиссии [ASSUMPTION — сверить на фикстуре `fixtures/wb-api/statistics/supplier-sales/…` с недельным `ppvz_for_pay`]; `logistics_est = boxDeliveryBase(склад) + boxDeliveryLiter(склад) × доп. литры` из `tariffs/box?date=calendar_day` [семантика «первый литр / следующий литр» по спеке WB, в скилле не раскрыта, `:125`]; `storage_est = (boxStorageBase + boxStorageLiter × доп. литры) × дней на складе` — требует остатков (`POST /api/analytics/v1/stocks-report/wb-warehouses`, написан в `wb-client.ts:157-190`, вне реестра); `return_est` = тариф `tariffs/return` × возвраты (`saleID = R`); `cogs_rub` — `dim_product.cogs_rub` (`db/migrations/004_business_signal_slice.sql:7`), заполняется только для топ-SKU: `dim_client_passport.cogs_status ∈ {complete, top_sku, missing}` (`010_client_passport_supply_plan.sql:9`; решение PMM-21 от 28.08.2026 — COGS только топ-SKU, остальное явно revenue-based).
- Комиссия по категории для сверки: `subjectId` берётся из ответа воронки v3 `product.subjectId` (`API-FACTS.md:32`, в реестре) → `commission[subjectID].kgvpMarketplace` (FBO) или `kgvpSupplier` (FBS) по схеме тенанта.
- Что нужно: (1) три тарифных эндпоинта + `paid_storage` в allowlist `tools/verify_business_signal.py` и подтверждение read-only скоупа токена на сервере; (2) ежедневный снимок тарифов как артефакт с `run_id` (тарифы датированы `?date=`); (3) объём SKU в литрах — в реестре отсутствует (карточка через content-API READ вне реестра или ручной ввод в products.csv); (4) `stocks-report` в реестр для хранения.
- Выход: `signal` с `rub_assessment` по AD-10 (строка, 2 знака) и `source_refs` на артефакты тарифов и продаж; для SKU без COGS — `margin_est = UNKNOWN`, показывать только revenue-based часть.

B. Недельная сверка «оценка vs факт» (детерминированно): по `nm_id` за закрытую неделю `Σ ppvz_for_pay(Продажа) − Σ ppvz_for_pay(Возврат) − Σ delivery_rub − Σ storage_fee − Σ penalty − Σ deduction − Σ acceptance − cogs_rub × qty` из `reportDetailByPeriod` (поля — `API-FACTS.md:28`) или finance `sales-reports/detailed` (уже в `wb-client.ts`). Требует снятия гейта `verify_business_signal.py:27-29` через Release Gate; бюджет 1 вызов/мин, страницы 200+ МБ.

**ML-потенциал: 1/3.** Тарифы — детерминированный справочник. Ниша для ML одна: регрессия фактических `delivery_rub`/`storage_fee` на единицу по недельной истории для уточнения дневной оценки и outlier-детекция аномальных удержаний/штрафов. Объяснение отклонения маржи — LLM поверх цифр («ML считает / LLM объясняет», `.memlog.md`).

## 6. Код к переиспользованию

- В кластере кода **нет**: примеры `SKILL.md:93-111` вызывают `skills/wb-tariffs/scripts/wb-tariffs.sh`, файла нет ни в каталоге, ни в бандле. Тестов и фикстур нет. Переиспользуемы только таблицы эндпоинтов/лимитов/полей (`:35-48`, `:79-87`, `:114-139`) как черновик спецификации — после верификации живым вызовом с сервера в фикстуру.
- Справочно (другой кластер, Python + `requests`): `skills/wb-agency-report/scripts/fetch.py:225-297` (commission/box с retry на 429, заголовок без Bearer), `scripts/transform.py:335-443` (парсер «0,07» → float, lookups, P&L), тест `tests/test_phase4_tariffs.py` + фикстура `tests/fixtures/tariffs-mock.json`. Токены там читаются из `~/.claude/wb-tokens/<client>.env` (`fetch.py:32,50` — только пути; значений в дропе нет). Использовать как эталон для порта в TS collector, не импортировать (provenance).

## 7. Красные флаги

1. Скилл нерабочий как есть — отсутствует `wb-tariffs.sh` (`SKILL.md:93`).
2. Маржу считает LLM по одной строке без определения (`SKILL.md:29`) — нарушение правила «LLM не считает метрики»; двусмысленность «детализируй» vs «вычти».
3. `reportDetailByPeriod` под гейтом (`tools/verify_business_signal.py:27-29`), недельный, 200+ МБ на страницу — не источник дневной сводки.
4. Нет `tariffs/pallet`, коэффициентов складов и объёма SKU → логистика «по литрам» без внешнего входа не считается.
5. Лимит 1 req/min на commission/paid-storage/report (`:81-85`) — это бюджет планировщика (RateBudget Story 1.1), а не «по запросу в чате».
6. Мульти-юрлицо через `--entity` (`:60`, `:111`) — в PROXIMA это `tenant_id`; конфиг токенов жил в отсутствующем скрипте.
7. Дрейф API: переименованные поля (`:129-130`), отключённый `/storage-coefficient` (`:146`) — нужны схема ответа в `contracts/` и фикстуры.
8. При заимствовании формулы соседа: `DEFAULT_COMMISSION_PCT = 20.0` и усреднение логистики по всем складам (`transform.py:375-382,406`) — выдуманные/грубые допущения, запрещены правилом «не выдумывать данные».

## Summary C6

| Скилл | Capability | Статус источника | WRITE? | Расчётность 0-3 | ML 0-3 | Переисп. 0-3 |
|---|---|---|---|---|---|---|
| `wb-tariffs` | Тарифы WB (комиссия, логистика/хранение по складам, возвраты, платное хранение) + недельная маржа по факту удержаний | READ вне реестра: common-api tariffs ×3, analytics paid_storage ×3 (не проверены); `reportDetailByPeriod` — READ вне реестра, gated | нет (paid_storage — серверная задача отчёта, данные не меняет) | 2 (формула одна, считает LLM; на данных лестницы считается детерминированно) | 1 | 0 (кода нет) |
| (справочно) `wb-agency-report` Phase 4 P&L | P&L по SKU на тарифах: revenue − commission% − buyouts × avg_delivery | те же tariffs READ + funnel v3 (в реестре) | нет | 2 (без COGS/хранения/возвратов, дефолт 20%) | 1 | 1 (Python-эталон + тест, портировать) |

Выводы:
- Ценность кластера — карта эндпоинтов, лимитов и полей; вычислительной логики почти нет. Юнит-экономика в PROXIMA строится не из скилла, а из уже написанного `calculateMargins` + ежедневного снимка тарифов.
- Дневная маржа по SKU вычислима детерминированно, но требует четырёх входов вне реестра (tariffs ×3, stocks), объёма SKU и COGS топ-SKU (PMM-21); без объёма — только «базовая логистика».
- Точный факт удержаний — только недельный (`reportDetailByPeriod`/finance) и под гейтом; правильная архитектура — «дневная оценка + недельная сверка».
- PRD относит маржу/P&L к W2-W4 (`prd.md:350`) → ступень M-04, отдельный Release Gate на расширение allowlist и контракт снимка тарифов.
