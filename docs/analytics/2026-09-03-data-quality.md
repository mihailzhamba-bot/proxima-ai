# PMM-58 — Data-quality аудит доменных источников WB API

> **Статус:** `unreleased`  
> **Scope:** live read-only WB API; реальные cabinet ID и SKU в документе не публикуются.  
> **Primary evidence run:** `20260903T162418_b4b34738`  
> **Период Statistics:** 2026-08-13 — 2026-09-02  
> **Finance settled candidate:** 2026-08-24 — 2026-08-30

## 1. Итог

Аудит установил не универсальное «API точный/неточный», а правила доверия к каждому домену.

| Домен | Итоговый статус доверия | Основное применение |
|---|---|---|
| Statistics Orders | **TRUSTED for business-day demand** при `flag=1` | оперативный спрос и отмены |
| Statistics Sales | **TRUSTED / PROVISIONAL** | lifecycle sale/return и диагностика |
| Analytics Funnel | **DIAGNOSTIC / PROVISIONAL** | конверсии и локализация этапа проблемы |
| Stocks WB / Seller | **CURRENT SNAPSHOT, PARTIAL COVERAGE** | остатки, но отсутствие строки не объявляется OOS без catalog rule |
| Finance daily | **HIGH CONFIDENCE / PROVISIONAL** | текущая незакрытая неделя |
| Finance weekly | **SETTLED / AUTHORITY** после формирования weekly report | финальные деньги закрытой недели |

Главный принцип для платформы: успешный API-response не равен финальному факту. Источник должен иметь quality/finality status.

## 2. Паспорт primary run

| Source | Запрос | Результат |
|---|---|---:|
| Statistics Orders | 21 отдельных `GET /api/v1/supplier/orders`, `flag=1`, по одному business-day | **894 строки** |
| Statistics Sales | 21 отдельных `GET /api/v1/supplier/sales`, `flag=1`, по одному business-day | **766 строк** |
| Funnel v3 history | `POST /api/analytics/v3/sales-funnel/products/history`, 27.08–02.09 | **124 nmId × 7 дней = 868 product-day** |
| Stocks WB | `POST /api/analytics/v1/stocks-report/wb-warehouses` | 375 строк / **115 из 124 nmId** |
| Stocks Seller | `POST /api/analytics/v1/stocks-report/seller-warehouses` | 395 строк / **54 из 124 nmId** |
| Stocks union | WB + Seller | **117 из 124 nmId** |
| Finance daily | `POST /api/finance/v1/sales-reports/detailed`, `period=daily` | **5 620 строк** |
| Finance weekly | тот же endpoint, `period=weekly`, 24–30.08 | **2 125 строк** |
| Finance report list | `POST /api/finance/v1/sales-reports/list`, weekly | **2 отчёта** |
| Finance by report ID | `POST /api/finance/v1/sales-reports/detailed/{reportId}` | **2 125 строк** |
| Paid Storage | отдельный report API, 24–30.08 | **36 074 raw rows / 161 nmId** |
| Acceptance Report | отдельный report API, 24–30.08 | **0 строк** |
| Promotion | optional source | **SKIPPED: Promotion token не передан** |

Raw responses сохранены с `run_id`, временем получения и SHA-256.

### Ограничение stock universe

В этом run Promotion-token отсутствовал, поэтому product universe сформирован fallback-способом из `Statistics Orders + Sales`: **124 nmId**. Это не полный каталог активных карточек кабинета. Следовательно, Stocks-аудит подтверждает семантику ответа для наблюдаемого universe, но не доказывает полноту OOS-контроля по всему каталогу.

## 3. Что проверялось

- корректность API-параметров;
- grain и ключи;
- NULL / пустые ключи / дубли;
- отрицательные и нулевые значения;
- business-day completeness Statistics через `flag=1`;
- Orders ↔ Sales;
- Sales ↔ Finance;
- Orders ↔ Funnel;
- Stocks coverage WB / Seller / union;
- Finance daily ↔ weekly;
- Finance list ↔ `detailed/{reportId}` ↔ weekly;
- Finance operation semantics и P&L-классификация;
- отдельная SKU-атрибуция хранения/приёмки;
- freshness / finality.

## 4. Находки

### DQ-01 — Statistics business period должен собираться только через `flag=1`

Primary run полностью пересобран по business-date.

**Orders:** 21 daily request, 894 строки.  
**Sales:** 21 daily request, 766 строк.

Для **аналитического аудита PMM-58** полнота business-day доказывалась отдельными `flag=1` запросами по `source.date`.

Правило аудита:
- доказательство полноты конкретного business-day → `flag=1`;
- `flag=0` нельзя интерпретировать как готовый календарный срез, потому что он возвращает поток изменений по `lastChangeDate`.

**Уточнение после сверки с текущим `main` 08.09.2026.** PMM-61 закрыт как не воспроизводимый в текущем production-контуре: collector намеренно использует `flag=0` как incremental/revision stream, хранит версии наблюдений, а `fact_cabinet_daily` агрегируется по дню заказа `date`. Поэтому вывод PMM-58 относится к способу независимой проверки business-day и старому exporter, а не требует перевода текущего collector на `flag=1`. Корректность текущей цепочки проверяется независимо в PMM-124 (Story 6.1).

### DQ-02 — Orders cancellation semantics

На 894 Orders:

- `isCancel=true`: **193 (21,6%)** — это eventual cancellation для cohort;
- отменено в тот же календарный business-day: **21 (2,35%)**.

Это разные KPI и их нельзя смешивать.

Для оперативного спроса:
`net_orders_day = Orders(date=D) − Orders(date=D AND cancelDate=D)`.

Eventual cancellation rate нужен для lifecycle/качества заказов, но не должен задним числом менять показатель исходного спроса дня.

### DQ-03 — Sales grain подтверждён

На 766 Sales events:

- `saleID` уникален **766/766**;
- `srid` уникален **756/766**;
- **756** `S...` sale;
- **10** `R...` return.

Повторы `srid` являются корректной парой sale→return.  
`PRIMARY EVENT KEY = saleID`, `LIFECYCLE FK = srid`.

### DQ-04 — Orders ↔ Sales

Из 756 sale-events текущего 21-дневного Sales-window **516** имеют исходный Orders `srid` внутри того же 21-дневного Orders-window.

На matched rows:
- `nmId`: 516/516;
- `gNumber`: 516/516;
- `totalPrice`: 516/516;
- `discountPercent`: 516/516;
- `priceWithDisc`: 516/516;
- `spp`: 516/516;
- `Orders.finishedPrice = Sales.finishedPrice + Sales.paymentSaleAmount`: 516/516.

Оставшиеся 240 Sales не считаются DQ-error: sale-event попал в период по дате продажи, а исходный order мог быть создан до начала 21-дневного Orders-window.

Вывод: `srid` подтверждён как lifecycle-link; referential completeness требует persistent Orders history, а не join двух одинаковых календарных окон.

### DQ-05 — Sales ↔ Finance

На текущем run:

- Sales events: **766**;
- matched Finance по `srid + operation type`: **766/766**;
- unmatched: **0**;
- seller-side price совпадает в пределах 0,02 ₽: **763/766**;
- в пределах 1 ₽: **765/766**.

Это сильное независимое подтверждение Statistics Sales через Finance.

Finance остаётся authority для денег; Sales — оперативный lifecycle source.

### DQ-06 — Funnel не является authority для количества Orders

Контрольный `flag=1` Orders и Funnel сравнивались на одном business-day.

| Дата | Orders | Funnel | Δ Funnel−Orders |
|---|---:|---:|---:|
| 27.08 | 36 | 39 | +3 |
| 28.08 | 43 | 39 | −4 |
| 29.08 | 28 | 32 | +4 |
| 30.08 | 32 | 37 | +5 |
| 31.08 | 30 | 36 | +6 |
| 01.09 | 25 | 29 | +4 |
| 02.09 | 28 | 32 | +4 |

Расхождение сохраняется не только на свежих, но и на D+4…D+7 датах. Следовательно, оно **не объясняется только arrival lag**: `Funnel.orderCount` и Statistics Orders имеют различающуюся бизнес-семантику/правила включения событий.

Практическое правило:
- demand authority → Statistics Orders;
- Funnel → diagnostic KPI/conversions.

Денежная семантика Funnel `orderSum` в большинстве matched product-day соответствует `Orders.priceWithDisc`, но общий итог расходится вместе с составом Orders.

> QA note: derived `orders_funnel_reconciliation.csv`, сгенерированный exporter v1.3, содержит дефект нормализации Funnel и выводит нули. Таблица выше пересчитана непосредственно из immutable raw Funnel + Orders artifacts данного run. Raw evidence корректен; дефект относится только к derived helper CSV и должен быть исправлен в exporter.

### DQ-07 — Funnel maturity

Funnel исторически пересчитывает прошлые cohorts. Особенно поздно созревают:
- `buyoutCount`;
- `buyoutSum`;
- `buyoutPercent`.

На 868 product-day текущего window:
- `openCount=0`: 26 (3,0%);
- `cartCount=0`: 319 (36,8%);
- `orderCount=0`: 695 (80,1%);
- `buyoutCount=0`: 807 (93,0%);
- `openCount < cartCount`: 0;
- `cartCount < orderCount`: 4;
- `orderCount < buyoutCount`: 0.

`cartCount < orderCount` не маркируется автоматически как corruption: заказ сегодняшнего дня может быть оформлен из корзины предыдущего дня.

Fresh outcome Funnel → `PROVISIONAL/SETTLING`, не `SETTLED`.

### DQ-08 — Stocks WB + Seller

Для fact-discovered universe 124 nmId:

| Snapshot | Returned nmId | Missing |
|---|---:|---:|
| WB warehouses | 115 | 9 |
| Seller warehouses | 54 | 70 |
| WB ∪ Seller | **117** | **7** |

В обоих endpoint нет полностью all-zero rows: если строка присутствует, у неё есть остаток и/или движение.

Стабильная гипотеза: полностью zero-state товар может не возвращаться API. Но этот контракт явно не доказан; поэтому `missing row = OOS` автоматически не применяется.

Дополнительно: Seller-warehouse coverage не обязано быть 100%, потому что не каждый SKU используется по FBS.

Для production OOS-control нужен полный active catalog / `dim_nomenclature`; текущий run этого не доказал, поскольку Promotion token отсутствовал.

### DQ-09 — Finance daily ↔ weekly

Для закрытой недели 24–30.08:

- daily rows: **2 125**;
- weekly rows: **2 125**;
- `rrdId` intersection: **2 125**;
- daily-only: 0;
- weekly-only: 0.

После join по `rrdId` изменяются только report-level metadata:
`reportId`, `dateFrom`, `dateTo`, `createDate`.

Остальные бизнес-поля совпадают.

Вывод:
- `daily` — высокоточный оперативный источник, но период ещё `PROVISIONAL`;
- после появления weekly production financial fact закрытой недели переключается на `weekly`;
- raw daily сохраняется для provenance/DQ, но не конкурирует с weekly как authority.

### DQ-10 — Finance list ↔ detailed/{reportId} ↔ weekly

`/sales-reports/list` вернул два weekly report.  
`detailed/{reportId}` вернул **2061 + 64 = 2125** строк.

Для обоих report:
- множество `rrdId` exact-detail полностью совпало с weekly-period source;
- union-схема run содержит **91 уникальное поле**; отдельные строки содержат 89–90 полей из-за условных полей API; после нормализации по union-схеме значения exact-detail и weekly совпали по каждому `rrdId` во всех присутствующих полях.

Report-level aggregates:
- `retailAmountSum`, delivery, storage, acceptance, deduction, penalty, additionalPayment, loyalty aggregates — сходятся с детализацией после применения бизнес-знаков;
- первоначальная разница `forPaySum` по report type 1 = **1 781,22 ₽** полностью объясняется двумя строками `Добровольная компенсация при возврате`, которые входят в `forPaySum`, но были ошибочно исключены первым classifier-ом.

После включения этой компенсации `forPaySum` сходится точно.

Также на обоих reports эмпирически выполняется контроль:
`bankPaymentSum = forPaySum + additionalPaymentSum − deliveryServiceSum − paidStorageSum − paidAcceptanceSum − deductionSum − penaltySum − cashbackAmountSum − cashbackCommissionChangeSum − paymentSchedule`.

Это DQ-control текущего sample, не объявляется универсальной бухгалтерской формулой без отдельного контракта.

**Вывод:** Finance weekly finality rule подтверждена на трёх уровнях:
`LIST summary → exact report detail → weekly period detail`.

### DQ-11 — Finance P&L: деньги нельзя сворачивать одним полем

Нужно хранить раздельно:
- `retailPriceWithDisc` — seller-side сумма реализации;
- `retailAmount` — фактическая buyer-side сумма/чек;
- commission;
- acquiring;
- direct logistics;
- reverse logistics;
- paid storage;
- paid acceptance/FBS processing;
- penalties/deductions;
- additional payments/compensations;
- loyalty;
- prepayments/refunds;
- reconciliation-only/pass-through rows.

`forPay` не является revenue или profit.

Для налоговой аналитики buyer-side amount хранится отдельно; налоговая формула должна быть закреплена отдельным accounting/ADR решением, а не выводиться из API эвристикой.

### DQ-12 — Direct / reverse logistics

Finance позволяет разделить логистику по `bonusTypeName`:

- `К клиенту при продаже` → DIRECT;
- `К клиенту при отмене` → DIRECT;
- `От клиента при отмене` → REVERSE;
- `От клиента при возврате` → REVERSE;
- `Возврат товара ... продавцу` → REVERSE / RETURN_TO_SELLER.

`warehouseLogisticsCoeff` — объясняющий тарифный атрибут. В P&L используется уже фактически начисленный `deliveryService`; коэффициент нельзя применять второй раз.

### DQ-13 — `srid` позволяет собрать экономику заказа

Finance ledger может связываться с Orders/Sales через `srid`.

В current weekly candidate построено **1 341** lifecycle-групп с Finance events.

Модель:
`order_date → sale/return date → rrDate Finance → seller revenue / commission / acquiring / direct logistics / reverse logistics / FBS processing / other`.

Это позволяет отдельно видеть:
- выкупленный заказ;
- отказ без продажи, но с прямой и обратной логистикой;
- поздний возврат;
- финансовое признание расходов через несколько дней после заказа.

`rrdId` = PK финансовой строки, `srid` = lifecycle FK.

### DQ-14 — Paid Storage по SKU подтверждён отдельным API

Paid Storage API за 24–30.08:
- 36 074 raw rows;
- 161 nmId;
- сумма SKU-level отчёта: **1 434,84 ₽**;
- Finance weekly `paidStorageSum`: **1 434,80 ₽**;
- delta: **0,04 ₽**.

Это практически точная независимая сверка и подтверждает правильную архитектуру:

`Finance weekly → authoritative total`,  
`Paid Storage API → SKU attribution`.

### DQ-15 — Paid Acceptance / FBS processing

Acceptance Report за 24–30.08 вернул 204 / no rows.

При этом Finance weekly содержит **40 ₽** `paidAcceptance`, которые представлены 4 строками `sellerOperName = Обработка товара` по 10 ₽ и относятся к FBS processing.

Следовательно:
- FBS обработку можно атрибутировать прямо из Finance detailed по `nmId/srid`;
- отдельный Acceptance Report нужен для FBW paid acceptance, когда такие строки есть;
- в проверенной неделе FBW paid acceptance не обнаружена.

### DQ-16 — Promotion reconciliation не оценён в этом run

Promotion source не запускался, поскольку optional Promotion token не передан.

Следовательно, данный run **не доказывает**:
- полный product catalog для Stocks;
- фактические рекламные spend vs Finance deduction;
- bonus-funded advertising split.

Это не блокирует DoD PMM-58: Promotion не входит в исходный scope задачи. Для рекламы правило остаётся fail-closed: не включать Finance `WB Продвижение` второй раз, если P&L строится из Promotion API.

## 5. Freshness / finality

| Domain | На дату run | Правило |
|---|---|---|
| Orders | business-day до 02.09 получен `flag=1` | operational fact; arrival-lag SLA — PMM-60 |
| Sales | business-day до 02.09 получен `flag=1` | operational/provisional |
| Funnel | до 02.09 | outcome revisable, `PROVISIONAL/SETTLING` |
| Stocks | current snapshot 03.09 | current state; no historical finality |
| Finance daily | до 02.09 | `PROVISIONAL` |
| Finance weekly | report создан 31.08 за 24–30.08 | `SETTLED / AUTHORITY` |

Arrival lag на 14 дней вынесен Mike в PMM-60 и не является блокером PMM-58.

## 6. Влияние на сигналы / PMM-28

1. Orders-based demand должен строиться только из `flag=1` business-day facts.
2. Fresh Sales/Funnel/Finance нельзя маркировать как final без domain-specific status.
3. Funnel нельзя использовать как authority для Orders count.
4. Missing Stocks row нельзя превращать в `stock=0` без каталожного universe и подтверждённого contract.
5. Sale→return нельзя дедуплицировать по `srid`; event PK = `saleID`.
6. Финансовый сигнал должен переключать closed week с daily на weekly.
7. Finance P&L должен строиться из классифицированных atomic operations; prepayment/reconciliation/pass-through нельзя молча считать расходом.
8. Для расследования финансового отклонения используется `srid` lifecycle.
9. Storage SKU-cost подтверждается отдельным Paid Storage source.

## 7. Открытые вопросы / follow-up

Не блокируют PMM-58:
- **PMM-60:** longitudinal arrival-lag/finality calibration Orders/Sales; до релиза 1.14 локальные `flag=1` snapshots остаются страховкой, после релиза основной замер переносится на версии дней в production-контуре;
- **PMM-124:** независимая проверка того, что текущий `flag=0` observation stream корректно материализуется в business-day ряд по `Orders.date`;
- **PMM-127:** internal provenance `artifact → normalized fact → released fact` на боевой read-only базе; эта Story 6.4 заменила закрытый PMM-62;
- точный WB-contract отсутствующей Stocks row;
- полный stock catalog universe после подключения catalog source;
- Promotion spend/bonus reconciliation;
- точная классификация новых/редких Finance `bonusTypeName` должна быть fail-closed (`UNKNOWN_REVIEW`) до маппинга.

## 8. Синхронизация с каноном проекта на 08.09.2026

После недели 1 основной инженерный контур Proxima был синхронизирован в Jira и `main`. Для этого отчёта важно следующее:

- PMM-61 закрыт: текущий collector использует `flag=0` как поток наблюдений, а business-day строится по `Orders.date`;
- PMM-62 закрыт как superseded и заменён PMM-127 — provenance будет проверяться на боевой базе через отдельную read-only роль аналитика;
- результаты PMM-58 остаются аналитическим evidence package и не являются альтернативной архитектурой хранения;
- канонические архитектурные решения определяются репозиторием Proxima и `ARCHITECTURE-SPINE.md`; расхождение аналитических предложений с каноном оформляется отдельно, а не внедряется из этого отчёта.

## 9. Финальный статус PMM-58

**Analytical scope complete / READY FOR REVIEW.**

Ключевые блокеры ревью 02.09 закрыты:
- source passport — да;
- Orders `flag=1` пересборка — да;
- Sales grain — да;
- Orders↔Sales — да;
- Sales↔Finance — да;
- Orders↔Funnel — да; доказано семантическое расхождение;
- Funnel quality — да;
- Stocks set-check — да;
- freshness/finality — да;
- cancellation KPI — да;
- Finance daily↔weekly — да;
- Finance list↔exact report↔weekly — да.

Инженерные и longitudinal follow-up уже вынесены из PMM-58 и не должны удерживать задачу в аналитической работе.


## 10. Уточнение схемы Finance detailed

Независимая проверка raw weekly artifact показала:

- 2 125 строк;
- 91 уникальное имя поля в union-схеме run;
- отдельная строка содержит 89 или 90 полей, поскольку часть полей условная;
- `rebillLogisticOrg` встречается только в 35 строках;
- сверка exact report detail ↔ weekly выполняется после выравнивания по union-схеме и `rrdId`.

Поэтому прежняя формулировка «91 поле каждой строки» заменена на корректную: «91 поле в union-схеме, строки разрежены по optional-полям».
