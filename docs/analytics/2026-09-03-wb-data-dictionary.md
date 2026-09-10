# WB API для Proxima — полный field-by-field словарь, cross-source сверка и trust-map

> **Статус:** `unreleased`  
> **Primary evidence:** run `20260903T162418_b4b34738`.  
> **Важно:** ниже перечислены поля, **фактически присутствовавшие в raw-ответах этого run**. Если точная семантика поля не была доказана в аудите, оно помечено `RAW/OPEN`, а не додумывается.

> **Актуализация 09.09.2026:** словарь описывает семантику источников и результаты независимого аудита. Для проверки business-day полноты Statistics используется `flag=1`. В текущем `main` Proxima `flag=0` используется намеренно как incremental/revision stream, а дневной ряд агрегируется по `Orders.date`; это не считается дефектом (PMM-61 закрыт 08.09).


## 0. Что это за документ

Это подробная часть PMM-58/PMM-59.  
Jira должна содержать короткое резюме, а здесь хранится то, что мы разбирали поле за полем:

- название поля API;
- нормальное русское название;
- что оно означает;
- зачем оно Proxima;
- с каким полем другого источника его можно сравнить;
- где оно authority, а где только diagnostic/raw.

### Условные роли
- **CORE** — базовое поле для расчёта/связи;
- **P&L** — денежная статья экономики;
- **DIM** — аналитический разрез;
- **DIAG** — диагностика/объяснение;
- **TECH** — техническая трассировка;
- **RECON** — сверка, нельзя автоматически считать отдельным доходом/расходом;
- **RAW/OPEN** — сохраняем, но бизнес-правило пока не подтверждено.

---

# 1. Statistics Orders — `/api/v1/supplier/orders`

**Grain:** одна товарная позиция заказа.  
**Business date:** `date`.  
**Cross-domain lifecycle key:** `srid`.  
**Analytical request:** `flag=1`.

**Важно про FBS:** Statistics sample может содержать строки `warehouseType=Склад продавца`, но для **полной operational картины FBS этого недостаточно**. Нужен отдельный Marketplace FBS Orders `/api/v3/orders` и дальнейший crosswalk. Поэтому полный Orders-domain компании пока `PARTIAL`.

| Поле API | По-русски | Что означает | Практическая ценность | Сопоставление |
| --- | --- | --- | --- | --- |
| date | Дата и время заказа | Когда клиент оформил конкретную товарную позицию. | CORE: business-date; спрос по дням/часам. | Finance.orderDt; Funnel date только агрегат. |
| lastChangeDate | Последнее изменение записи | Техническое время последнего изменения строки в Statistics. | TECH: revision/freshness; НЕ период заказа. | Нет прямого business-аналога. |
| warehouseName | Склад исполнения | Склад, с которого WB/продавец исполняет заказ. | DIAG: склад, логистика, локализация исполнения. | Sales.warehouseName; частично Finance.officeName. |
| warehouseType | Тип склада | Например «Склад WB» / «Склад продавца». | CORE DIM: различать модели исполнения; не заменяет отдельный Marketplace FBS source. | Sales.warehouseType. |
| countryName | Страна назначения | Страна покупателя/доставки. | DIM: география спроса. | Sales.countryName; Finance.country. |
| oblastOkrugName | Федеральный округ назначения | Крупная географическая зона заказа. | DIM: региональная аналитика/локализация. | Sales.oblastOkrugName. |
| regionName | Регион назначения | Регион доставки заказа. | CORE DIM: спрос по регионам. | Sales.regionName. |
| supplierArticle | Артикул продавца | Человекочитаемый SKU продавца. | DIM/DISPLAY: join с внутренним каталогом. | Sales.supplierArticle; Finance.vendorCode. |
| nmId | Артикул WB / ID номенклатуры | Основной идентификатор товара в WB. | CORE FK: общий ключ Orders/Sales/Funnel/Finance/Stocks. | Есть во всех основных товарных источниках. |
| barcode | Баркод варианта | Идентификатор конкретного barcode/варианта. | VARIANT/OPS: поставки и диагностика; не основной product key. | Sales.barcode; Finance.sku. |
| category | Категория WB | Высокоуровневая категория товара. | DIM: агрегаты. | Sales.category. |
| subject | Предмет WB | Тип товара внутри категории. | DIM: продуктовая аналитика. | Sales.subject; Finance.subjectName; Funnel.product.subjectName. |
| brand | Бренд | Бренд товара. | DIM. | Sales.brand; Finance.brandName; Funnel.product.brandName. |
| techSize | Технический размер/вариант | Размер/вариант WB. | VARIANT: полезно для size-specific проблем. | Sales.techSize; Finance.techSize. |
| incomeID | ID поставки | Связь товара с поставкой. | DIAG: анализ партии/поставки. | Sales.incomeID; Finance.giId — похожая supply lineage, но не объявляем автоматически идентичными. |
| isSupply | Служебный флаг WB | Точная актуальная бизнес-семантика по sample не подтверждена. | RAW/OPEN: хранить, в KPI не использовать. | — |
| isRealization | Служебный флаг WB | Точная актуальная бизнес-семантика по sample не подтверждена. | RAW/OPEN. | — |
| totalPrice | Базовая цена | Цена до части скидочных механизмов. | PRICE LINEAGE: объяснение формирования цены, не revenue. | Sales.totalPrice. |
| discountPercent | Скидка продавца, % | Собственная скидка продавца. | PRICING/DIAG. | Sales.discountPercent. |
| spp | СПП WB, % | Скидочный параметр WB на конкретной операции. | PRICING SIGNAL: вариативен между заказами; нужен sample-size. | Sales.spp; Finance.spp. |
| finishedPrice | Покупательская ценовая компонента Statistics Orders | Buyer-side поле Statistics Orders. | PRICE/DQ: НЕ приравнивать напрямую к Sales.finishedPrice. | Orders.finishedPrice = Sales.finishedPrice + Sales.paymentSaleAmount — 516/516 matched. |
| priceWithDisc | Цена продавца после скидки | Основная seller-side сумма конкретного order event. | CORE MONEY operational; для final P&L authority = Finance weekly. | Sales.priceWithDisc; Finance.retailPriceWithDisc; Funnel.orderSum агрегат. |
| isCancel | Отменён ли заказ | Признак eventual cancellation. | CORE lifecycle; отдельно от same-day cancellation. | — |
| cancelDate | Дата отмены | Когда заказ отменили. | CORE: same-day cancel и time-to-cancel. | — |
| sticker | Стикер/технический ID | Операционный идентификатор WB. | TECH/OPS: troubleshooting. | Sales.sticker; Finance.stickerId. |
| gNumber | Группа оформления | Группирует позиции одного оформления/корзины. | ANALYTICAL: basket analysis, товары вместе. | Sales.gNumber. |
| srid | ID позиции заказа | Главный lifecycle ID конкретной товарной позиции. | CORE ID: Orders→Sales→Finance. | Sales.srid; Finance.srid. |

# 2. Statistics Sales — `/api/v1/supplier/sales`

**Grain:** одно событие sale или return. **PK:** `saleID`. **Lifecycle FK:** `srid`.

| Поле API | По-русски | Что означает | Практическая ценность | Сопоставление |
| --- | --- | --- | --- | --- |
| date | Дата события продажи/возврата | Business-date события Sale или Return. | CORE lifecycle date; не дата первоначального заказа. | Finance.saleDt/rrDate в зависимости от анализа. |
| lastChangeDate | Последнее изменение записи | Техническая дата изменения. | TECH: revision, не business period. | — |
| warehouseName | Склад исполнения | Склад, связанный с sale/return. | DIAG: проблема склада/логистики. | Orders.warehouseName. |
| warehouseType | Тип склада | WB / seller warehouse. | DIM: модель исполнения. | Orders.warehouseType. |
| countryName | Страна | География события. | DIM. | Orders.countryName; Finance.country. |
| oblastOkrugName | Федеральный округ | География. | DIM. | Orders.oblastOkrugName. |
| regionName | Регион | География. | DIM. | Orders.regionName. |
| supplierArticle | Артикул продавца | SKU. | DIM/DISPLAY. | Orders.supplierArticle; Finance.vendorCode. |
| nmId | ID товара WB | Товарный ключ. | CORE FK. | Orders/Funnel/Finance/Stocks. |
| barcode | Баркод | Variant ID. | VARIANT/OPS. | Orders.barcode; Finance.sku. |
| category | Категория | Категория товара. | DIM. | Orders.category. |
| subject | Предмет | Тип товара. | DIM. | Orders.subject; Finance.subjectName. |
| brand | Бренд | Бренд. | DIM. | Orders.brand; Finance.brandName. |
| techSize | Размер/вариант | Variant attribute. | VARIANT. | Orders/Finance.techSize. |
| incomeID | ID поставки | Supply lineage. | DIAG: партия/поставка. | Orders.incomeID. |
| isSupply | Служебный флаг | Семантика не подтверждена sample. | RAW/OPEN. | — |
| isRealization | Служебный флаг | Семантика не подтверждена sample. | RAW/OPEN. | — |
| totalPrice | Базовая цена | Исходная цена. | PRICE LINEAGE. | Orders.totalPrice. |
| discountPercent | Скидка продавца, % | Собственная скидка. | PRICING. | Orders.discountPercent. |
| spp | СПП WB, % | WB discount parameter. | PRICING/DIAG. | Orders.spp; Finance.spp. |
| paymentSaleAmount | Оплата/компонент WB Кошелька | Отдельная buyer-side компонента Statistics Sales. | CORE PRICE COMPONENT: хранить отдельно. | Orders.finishedPrice = Sales.finishedPrice + paymentSaleAmount. |
| forPay | Предварительно к перечислению | Statistics payout-поле, не final accounting truth. | PROVISIONAL MONEY/DQ: не считать revenue или profit. | Finance.forPay — final-detail analogue. |
| finishedPrice | Buyer-side компонента Sales | Покупательская цена в Statistics Sales без отдельной Wallet-компоненты. | PRICE/DQ. | ≈ Finance.retailAmount в 762/766 ±0,02 ₽. |
| priceWithDisc | Seller-side цена sale/return | Цена продавца события. | CORE MONEY operational. | Orders.priceWithDisc; Finance.retailPriceWithDisc. |
| saleID | ID продажи/возврата | Уникальный event ID: S... sale, R... return. | PRIMARY KEY Sales: дедупликация только по нему. | — |
| sticker | Стикер | Technical ID. | TECH/OPS. | Orders.sticker; Finance.stickerId. |
| gNumber | Группа оформления | Связь с basket/order group. | ANALYTICAL. | Orders.gNumber. |
| srid | ID исходной позиции заказа | Связывает sale/return с исходным заказом. | CORE LIFECYCLE FK; НЕ уникален в Sales. | Orders.srid; Finance.srid. |

# 3. Analytics Funnel v3 History

**Grain:** `nmId × business-day`. Источник агрегированный и исторически пересчитывается.

| Поле API | По-русски | Что означает | Практическая ценность | Сопоставление |
| --- | --- | --- | --- | --- |
| product.nmId | ID товара WB | Товар, по которому построена воронка. | CORE FK. | Orders/Sales/Finance/Stocks.nmId. |
| product.title | Название товара | Название карточки. | DISPLAY/DIM. | Finance.title. |
| product.vendorCode | Артикул продавца | SKU. | DIM/DISPLAY. | Orders.supplierArticle; Finance.vendorCode. |
| product.brandName | Бренд | Бренд карточки. | DIM. | Orders.brand; Finance.brandName. |
| product.subjectId | ID предмета WB | Системный ID предмета. | DIM/TECH: стабильнее текста для справочника предметов. | — |
| product.subjectName | Предмет | Название типа товара. | DIM. | Orders.subject; Finance.subjectName. |
| history.date | Дата агрегата | День, к которому WB относит funnel metrics. | CORE grain: nmId×day; значения могут пересчитываться. | Orders.date сопоставляется только агрегировано. |
| history.openCount | Открытия карточки | Сколько открывали карточку. | FUNNEL CORE: трафик/интерес. | Нет аналога в Orders. |
| history.cartCount | Добавления в корзину | Сколько событий cart. | FUNNEL CORE: card→cart. | Нет аналога в Orders. |
| history.orderCount | Заказы Funnel | Агрегированное число заказов по логике Funnel. | DIAG, НЕ authority для event-level Orders. | Сравнивали с COUNT(Statistics Orders): систематически расходится. |
| history.orderSum | Сумма заказов Funnel | Агрегированная seller-side сумма заказов. | DIAG/DQ. | ≈ Σ Orders.priceWithDisc на большинстве product-day с совпавшим count. |
| history.buyoutCount | Выкупы | Количество выкупов cohort. | OUTCOME DIAG: maturity lag. | Sales даёт конкретные sale events, но grain/semantics не одинаковы. |
| history.buyoutSum | Сумма выкупов | Денежная сумма buyout cohort. | OUTCOME DIAG, revisable. | Finance не прямой аналог. |
| history.buyoutPercent | Процент выкупа WB | Готовый агрегированный KPI WB. | DIAG; на свежих cohorts PROVISIONAL. | — |
| history.addToCartConversion | Конверсия в корзину | Переход open→cart по логике WB. | FUNNEL KPI. | — |
| history.cartToOrderConversion | Конверсия корзина→заказ | Переход cart→order. | FUNNEL KPI; >100% не всегда corruption из-за междневных событий. | — |
| history.addToWishlistCount | Добавления в избранное | Wishlist interest. | DIAG: ранний интерес. | — |
| currency | Валюта | Валюта денежных Funnel metrics. | TECH/CONTROL. | Finance.currency. |

# 4. Stocks WB Warehouses

**Тип:** current snapshot. В текущем доступном ответе WB физическая warehouse localization **не раскрыта**: `warehouseName/regionName = Склад WB`.

| Поле API | По-русски | Что означает | Практическая ценность | Сопоставление |
| --- | --- | --- | --- | --- |
| nmId | ID товара WB | Товар. | CORE FK. | Все товарные источники. |
| chrtId | ID варианта WB | Variant/size characteristic ID. | VARIANT: деталь внутри nmId. | Paid Storage.chrtId. |
| warehouseId | ID склада | В текущем доступном ответе агрегирован как -999999. | TECH, сейчас НЕ даёт физическую FBW локализацию. | — |
| warehouseName | Название склада | В текущем ответе «Склад WB». | LIMITATION: только агрегированный WB stock, не физический склад. | Orders.warehouseName относится к исполнению заказа, не stock location snapshot. |
| regionName | Регион склада | В текущем ответе также агрегированный «Склад WB». | LIMITATION: не использовать для FBW localization. | — |
| quantity | Остаток | Физическое количество товара в возвращённой строке. | CORE STOCK. | Seller Stocks.quantity. |
| inWayToClient | В пути к клиенту | Товар уже движется к покупателям. | CORE MOVEMENT: помогает отличать zero physical stock от полного zero-state. | — |
| inWayFromClient | В пути от клиента | Возвратное движение товара к WB. | CORE MOVEMENT. | — |

# 5. Stocks Seller Warehouses / FBS

**Тип:** current snapshot по конкретным seller warehouses. Здесь warehouse localization доступна.

| Поле API | По-русски | Что означает | Практическая ценность | Сопоставление |
| --- | --- | --- | --- | --- |
| nmId | ID товара WB | Товар. | CORE FK. | Orders/Sales/Finance. |
| chrtId | ID варианта | Variant ID. | VARIANT. | Stocks WB/Paid Storage.chrtId. |
| warehouseId | ID склада продавца | Конкретный FBS/seller warehouse. | CORE LOCATION: складская локализация FBS. | Marketplace warehouse directory — будущий crosswalk. |
| warehouseName | Название склада продавца | Человекочитаемый FBS warehouse. | CORE LOCATION. | — |
| regionName | Регион склада продавца | Регион FBS warehouse. | CORE LOCATION: локализация FBS. | — |
| quantity | Остаток на складе продавца | Количество товара на конкретном seller warehouse. | CORE STOCK. | Stocks WB.quantity для другого контура. |

# 6. Finance — метод 1: `/api/finance/v1/sales-reports/list`

**Grain:** один сформированный финансовый отчёт. Это report registry и контроль totals, а не поартикульная детализация.

| Поле API | По-русски | Что означает | Практическая ценность | Сопоставление |
| --- | --- | --- | --- | --- |
| reportId | ID финансового отчёта | Уникальный номер сформированного отчёта. | PRIMARY KEY / FINALITY: затем идём в detailed/{reportId}. | Finance detailed.reportId. |
| sellerFinanceName | Юрлицо/продавец отчёта | Кому принадлежит отчёт. | DIM/CONTROL: кабинет/юрлицо. | — |
| dateFrom | Начало периода | Начало финансового отчёта. | CORE PERIOD. | Detailed.dateFrom. |
| dateTo | Конец периода | Конец периода. | CORE PERIOD. | Detailed.dateTo. |
| createDate | Дата формирования отчёта | Когда WB сформировал отчёт. | CORE FINALITY: weekly появился → период settled. | Detailed.createDate. |
| currency | Валюта | Валюта отчёта. | CONTROL. | Detailed.currency. |
| reportType | Тип отчёта | WB разделяет отчёты по типам. | CORE/CONTROL: один период может иметь несколько reportId. | Detailed.reportType. |
| retailAmountSum | Итого buyer-side реализации | Агрегат retailAmount с бизнес-знаками. | FINANCE CONTROL: total отчёта, не SKU. | Σ detailed.retailAmount signed. |
| forPaySum | Итого к перечислению по товарным/компенсационным операциям | Report-level forPay total. | FINANCE CONTROL; не profit. | Σ detailed.forPay с корректной классификацией операций. |
| avgSalePercent | Средняя скидка, % | Агрегированный discount KPI отчёта. | DIAG/CONTROL. | Detailed salePercent/productDiscountForReport. |
| deliveryServiceSum | Итого логистика | Сумма начисленной логистики. | P&L CONTROL. | Σ detailed.deliveryService. |
| paidStorageSum | Итого платное хранение | Report total storage. | P&L CONTROL/AUTHORITY total. | Σ detailed.paidStorage; Paid Storage API — SKU allocation. |
| paidAcceptanceSum | Итого платная приёмка/обработка | Report total. | P&L CONTROL. | Σ detailed.paidAcceptance; Acceptance Report/FBS processing. |
| deductionSum | Итого удержания | Прочие удержания WB. | P&L/CLASSIFICATION CONTROL: нельзя слепо считать всё одним расходом. | Σ detailed.deduction. |
| penaltySum | Итого штрафы | Штрафы отчёта. | P&L CONTROL. | Σ detailed.penalty. |
| additionalPaymentSum | Итого дополнительные выплаты | Компенсации/доплаты. | P&L CONTROL: обычно плюс, но смотреть operation class. | Σ detailed.additionalPayment. |
| cashbackAmountSum | Итого cashback/loyalty удержания | Report loyalty aggregate. | LOYALTY CONTROL. | Σ detailed.cashbackAmount. |
| cashbackDiscountSum | Итого loyalty-компенсации/скидки | Отдельный loyalty reconciliation component. | RECON: не прибавлять второй раз без mapping. | Σ detailed.cashbackDiscount. |
| cashbackCommissionChangeSum | Изменение комиссии loyalty | Стоимость/изменение комиссии участия. | P&L/LOYALTY CONTROL. | Σ detailed.cashbackCommissionChange. |
| paymentSchedule | Изменение графика выплаты / финансовая услуга | Отдельная report financial component. | P&L только после classifier. | Detailed.paymentSchedule. |
| bankPaymentSum | Итог к оплате | Итоговая сумма report-level перечисления. | TOP CONTROL: сверка всех aggregate components. | Сверяется с report aggregates; не SKU metric. |

# 7. Finance — методы 2 и 3: Detailed

Методы:
1. `POST /api/finance/v1/sales-reports/detailed/{reportId}` — exact detail конкретного сформированного отчёта;
2. `POST /api/finance/v1/sales-reports/detailed` — period query (`daily`/`weekly`).

В union-схеме текущего raw weekly detail фактически присутствовало **91 уникальное поле**. Отдельные строки содержали 89–90 полей, поскольку часть атрибутов WB передаётся условно. Ниже перечислена полная union-схема из 91 поля.

| Поле API | По-русски | Что означает | Практическая ценность | Сопоставление |
| --- | --- | --- | --- | --- |
| reportId | ID отчёта | К какому сформированному отчёту относится строка. | CORE LINEAGE; exact report. | Finance List.reportId. |
| dateFrom | Начало периода отчёта | Report metadata. | TECH/LINEAGE. | Finance List.dateFrom. |
| dateTo | Конец периода отчёта | Report metadata. | TECH/LINEAGE. | Finance List.dateTo. |
| createDate | Дата формирования отчёта | Report finality metadata. | CORE FINALITY. | Finance List.createDate. |
| currency | Валюта | Валюта денежных полей. | CONTROL. | Finance List.currency. |
| reportType | Тип отчёта | Разделяет несколько reports одного периода. | CORE CONTROL. | Finance List.reportType. |
| rrdId | ID строки финансового отчёта | Уникальный ID financial event. | PRIMARY KEY Finance; pagination/reconciliation. | Daily/weekly/exact report сверяются по rrdId. |
| giId | ID поставки / supply lineage | Связь financial event с поставкой, когда заполнено. | DIAG: партия/поставка. | Orders/Sales.incomeID — родственная lineage, равенство не предполагается без проверки. |
| dlvPrc | Зафиксированный тарифный/коэффициентный параметр логистики | Параметр, участвующий в расчёте логистики. | DIAG/RAW: объяснять стоимость, НЕ умножать повторно на deliveryService. | warehouseLogisticsCoeff — связанный explanatory field. |
| fixTariffDateFrom | Начало действия фиксированного тарифа | Период применённого тарифного условия. | DIAG/TECH. | — |
| fixTariffDateTo | Окончание фиксированного тарифа | Конец tariff window. | DIAG/TECH. | — |
| subjectName | Предмет товара | Тип товара. | DIM. | Orders.subject; Funnel.product.subjectName. |
| nmId | ID товара WB | Товарный FK; у common operations может быть 0/пусто. | CORE FK. | Orders/Sales/Funnel/Stocks.nmId. |
| brandName | Бренд | Бренд товара. | DIM. | Orders.brand; Funnel.product.brandName. |
| vendorCode | Артикул продавца | SKU. | DIM/DISPLAY. | Orders.supplierArticle. |
| title | Название товара | Название карточки. | DISPLAY. | Funnel.product.title. |
| techSize | Размер/вариант | Variant attribute. | VARIANT. | Orders/Sales.techSize. |
| sku | Баркод | Barcode товара/варианта. | VARIANT/OPS. | Orders/Sales.barcode. |
| docTypeName | Тип документа | Например Продажа/Возврат; один из признаков business sign. | CORE CLASSIFIER. | Sales.saleID S/R и type. |
| quantity | Количество | Количество единиц операции. | CORE units; знак задаётся operation semantics. | Sales event quantity implicit row/event. |
| retailPrice | Розничная цена до части скидок | Price lineage. | PRICE RAW/DIAG. | Orders.totalPrice — похожая база, не объявлять 1:1 без check. |
| retailAmount | Фактическая buyer-side сумма Finance | Сумма, связанная с фактической оплатой покупателя в Finance. | CORE MONEY / buyer-side authority weekly. | ≈ Sales.finishedPrice в текущем sample. |
| salePercent | Скидка/процент продажи | Процентный price parameter отчёта. | PRICING DIAG. | Finance List.avgSalePercent aggregate. |
| commissionPercent | Комиссия WB, % | Процент комиссии конкретной операции. | CORE COMMISSION DIAG. | Контроль фактической commission amount. |
| officeName | Склад/офис в Finance | Локационный атрибут financial operation. | DIAG; не использовать как current stock location. | Orders/Sales warehouseName частично сопоставимы. |
| sellerOperName | Обоснование/тип финансовой операции | Главный business classifier: Продажа, Возврат, Логистика, Хранение, Удержание и т.п. | CORE CLASSIFIER: определяет P&L treatment. | Вместе с bonusTypeName. |
| orderDt | Дата исходного заказа | Дата заказа, которую Finance хранит для lifecycle. | CORE LINEAGE. | Orders.date. |
| saleDt | Дата продажи | Дата sale/return в Finance. | CORE LINEAGE. | Sales.date для sale/return. |
| rrDate | Дата финансовой операции | Когда операция признана в отчёте. | CORE ACCOUNTING DATE. | Основная дата Finance P&L/report. |
| shkId | ID штрихкода/операционного объекта WB | Technical identifier. | TECH/OPS. | — |
| retailPriceWithDisc | Seller-side цена реализации | Цена продавца после скидок, используемая в financial fact. | CORE MONEY / final seller-side authority. | Orders/Sales.priceWithDisc. |
| deliveryAmount | Количество доставок | Количество логистических событий/единиц в строке. | LOGISTICS DIAG. | — |
| returnAmount | Количество возвратов/обратной доставки | Return logistics count. | LOGISTICS CORE/DIAG. | Используется вместе с bonusTypeName. |
| deliveryService | Фактически начисленная логистика | Денежная стоимость логистики. | CORE P&L COST. | Finance List.deliveryServiceSum. |
| giBoxTypeName | Тип короба/упаковки | Логистический атрибут поставки. | DIAG/RAW. | — |
| productDiscountForReport | Итоговый discount parameter для отчёта | Скидка, используемая в report calculation. | PRICING DIAG. | — |
| sellerPromo | Промо продавца / promo component | Поле промо в financial row. | RAW/PRICING: использовать только после подтверждения semantics конкретных значений. | sellerPromoId/sellerPromoDiscount. |
| spp | СПП WB | WB discount parameter. | PRICING/DIAG. | Orders/Sales.spp. |
| kvwBase | Базовый коэффициент/процент вознаграждения WB | Базовая tariff commission component. | COMMISSION DIAG. | kvw — фактический. |
| kvw | Фактический коэффициент/процент вознаграждения WB | Commission tariff после корректировок. | CORE COMMISSION DIAG. | kvwBase, supRatingUp. |
| supRatingUp | Корректировка комиссии за рейтинг | Rating-related tariff adjustment. | DIAG: объяснить изменение комиссии. | — |
| isKgvpV2 | Служебный признак версии расчёта комиссии | Техническая ветка расчёта WB. | TECH/RAW, не KPI. | — |
| ppvzSalesCommission | Компонента вознаграждения/комиссии WB | Одна из commission components, но НЕ полная комиссия продавца. | RECON/DIAG: не использовать как total commission самостоятельно. | Полную commission контролировать через Finance economics. |
| forPay | К перечислению по строке | Сумма после ряда удержаний внутри товарной операции. | CORE CONTROL, но НЕ revenue и НЕ profit. | Sales.forPay provisional analogue; Finance List.forPaySum aggregate. |
| ppvzReward | Возмещение/расчётная компонента ПВЗ | В sample участвует в технических взаиморасчётах. | RECON/PASS-THROUGH: не вычитать как отдельный cost автоматически. | vw/vwNds часто дают compensating entries. |
| acquiringFee | Эквайринг, ₽ | Фактический расход обработки платежа. | CORE P&L COST. | Explains part of Sales.forPay vs Finance. |
| acquiringPercent | Эквайринг, % | Ставка эквайринга. | DIAG: effective acquiring. | — |
| paymentProcessing | Тип обработки платежа | Способ/тип payment processing. | DIAG/RAW. | acquiringBank. |
| acquiringBank | Банк-эквайер | Банк/платёжный provider. | DIAG: anomalies by bank/provider. | — |
| vw | Вознаграждение WB, компонент без НДС | Расчётная компонента вознаграждения WB. | RECON: не double-count с основной commission без доказанной формулы. | vwNds, ppvzReward, rebill. |
| vwNds | НДС на компонент вознаграждения WB | НДС расчётной компоненты WB. | RECON/ACCOUNTING. | vw. |
| ppvzOfficeName | Название ПВЗ/офиса | ПВЗ, связанный с financial operation. | LOCATION/DIAG. | — |
| ppvzOfficeId | ID ПВЗ/офиса | Системный ID точки. | LOCATION FK. | — |
| ppvzSupplierName | Партнёр/юрлицо ПВЗ | Контрагент ПВЗ. | ACCOUNTING/DIAG. | — |
| ppvzSupplierInn | ИНН партнёра ПВЗ | Контрагентный идентификатор. | ACCOUNTING/TECH. | — |
| declarationNumber | Номер декларации | Таможенная/декларационная информация, если применимо. | RAW/COMPLIANCE. | — |
| bonusTypeName | Расшифровка финансовой операции | Причина логистики/удержания/корректировки. | CORE CLASSIFIER: direct/reverse logistics, promo, услуги, авансы и т.д. | Вместе с sellerOperName. |
| stickerId | ID стикера | Technical order/package link. | TECH/OPS. | Orders/Sales.sticker. |
| country | Страна | Страна financial event. | DIM. | Orders/Sales.countryName. |
| srvDbs | Служебное DBS/service поле | Точная бизнес-семантика по текущему аудиту не подтверждена. | RAW/OPEN: не использовать в P&L. | — |
| penalty | Штраф | Денежная сумма штрафа. | CORE P&L COST с учётом корректирующих знаков/operations. | Finance List.penaltySum. |
| additionalPayment | Доплата/компенсация | Дополнительная выплата/корректировка. | CORE P&L INCOME/CORRECTION после classification. | Finance List.additionalPaymentSum. |
| rebillLogisticCost | Возмещение логистических/складских издержек | Техническая/pass-through financial component. | RECON: в sample компенсируется другими remuneration components; не double-count. | vw/vwNds. |
| rebillLogisticOrg | Организация, выполнившая перевыставленную логистику | Условное поле: присутствовало в 35 строках текущего weekly run. | RECON/LINEAGE: контрагент перевыставленной логистики; не отдельная сумма и не P&L-статья. | Используется вместе с `rebillLogisticCost`. |
| paidStorage | Платное хранение | Storage cost в Finance. | CORE P&L TOTAL/row. | Finance List.paidStorageSum; Paid Storage API для SKU. |
| deduction | Удержание | Прочие удержания/возвраты удержаний. | CORE CLASSIFICATION: знак и P&L зависят от sellerOperName+bonusTypeName. | Finance List.deductionSum. |
| paidAcceptance | Платная приёмка/обработка | Приёмка/обработка, в т.ч. наблюдали FBS processing. | CORE P&L COST. | Finance List.paidAcceptanceSum; Acceptance Report для FBW. |
| orderId | ID заказа/сборочного задания в Finance | Operational order identifier. | TECH/LINEAGE: дополнительный join при отсутствии nmId. | — |
| isB2b | Признак B2B | Продажа бизнес-клиенту. | DIM/SEGMENT. | b2bCustomerTin. |
| trbxId | ID короба | Короб/транспортная единица. | OPS/LOGISTICS. | — |
| installmentCofinancingAmount | Софинансирование рассрочки | Сумма co-financing payment mechanic. | P&L/PRICING only after mapping; отдельная статья. | — |
| wibesDiscountPercent | Скидка Wibes, % | Скидочный механизм Wibes. | PRICING/DIAG. | — |
| cashbackAmount | Сумма cashback/баллов | Удержание/движение loyalty баллов. | LOYALTY P&L после classifier. | Finance List.cashbackAmountSum. |
| cashbackDiscount | Компенсационная loyalty-скидка | Отдельная loyalty reconciliation component. | RECON: не считать автоматически дополнительной выручкой. | Finance List.cashbackDiscountSum. |
| cashbackCommissionChange | Изменение комиссии loyalty | Стоимость/изменение участия в loyalty. | LOYALTY P&L/CONTROL. | Finance List.cashbackCommissionChangeSum. |
| paymentSchedule | Изменение графика выплаты / финансовая услуга | Сумма услуги/корректировки payment schedule. | P&L только после operation mapping. | Finance List.paymentSchedule. |
| deliveryMethod | Метод доставки/исполнения | Модель исполнения financial event. | CORE DIM: FBS/FBW и т.п., когда заполнено. | Orders.warehouseType — related, not exact. |
| sellerPromoId | ID промо продавца | Identifier promotion mechanic. | PRICING/LINEAGE. | sellerPromoDiscount. |
| sellerPromoDiscount | Скидка промо продавца | Promo discount. | PRICING. | sellerPromoId. |
| loyaltyId | ID loyalty программы | Identifier loyalty mechanic. | LOYALTY LINEAGE. | loyaltyDiscount. |
| loyaltyDiscount | Loyalty скидка | Процент/параметр loyalty discount. | PRICING/LOYALTY. | loyaltyId. |
| uuidPromocode | UUID промокода | Identifier promocode. | PRICING LINEAGE. | salePricePromocodeDiscountPrc. |
| salePricePromocodeDiscountPrc | Скидка промокода, % | Promocode discount component. | PRICING. | uuidPromocode. |
| articleSubstitution | Подменный/замещающий артикул | Identifier article substitution scenario. | DIAG/RAW: substitutions. | salePriceAffiliatedDiscountPrc. |
| salePriceAffiliatedDiscountPrc | Скидка при аффилированной/замещающей механике | Специальная discount component. | PRICING/RAW. | articleSubstitution. |
| salePriceWholesaleDiscountPrc | Оптовая/B2B скидка, % | Wholesale discount component. | B2B PRICING. | isB2b. |
| b2bCustomerTin | ИНН B2B-покупателя | Business customer identifier. | B2B/ACCOUNTING; персонально/чувствительно не тащить в аналитические docs. | isB2b. |
| paidWithSocialCertificate | Оплата социальным сертификатом | Признак special payment method. | SEGMENT/ACCOUNTING. | — |
| warehouseLogisticsCoeff | Коэффициент логистики склада | Коэффициент, действующий для расчёта логистики. | CORE DIAG: объясняет variation; НЕ применять второй раз к deliveryService. | dlvPrc related. |
| orderUid | ID корзины/позиции заказа Finance | Дополнительный order grouping/link. | LINEAGE: может помогать атрибутировать common rows. | — |
| srid | Lifecycle ID позиции | Связывает Finance с Orders/Sales. | CORE FK: главный cross-domain lifecycle link. | Orders.srid, Sales.srid. |

# 8. Paid Storage API

**Grain:** строки расчёта хранения по SKU/варианту/складу/дню. В current run пришло 36 074 строк, 161 nmId.

| Поле API | По-русски | Что означает | Практическая ценность | Сопоставление |
| --- | --- | --- | --- | --- |
| date | Дата начисления хранения | День storage calculation. | CORE accounting/diagnostic date. | Finance.rrDate/report period — не 1:1 по строкам. |
| logWarehouseCoef | Логистический коэффициент склада | Дополнительный коэффициент склада в storage report. | DIAG/RAW: объясняющий tariff attribute. | — |
| officeId | ID офиса/склада | Системный ID места хранения. | CORE LOCATION для storage report. | — |
| warehouse | Склад | Физическое место storage начисления. | CORE LOCATION: здесь детализация есть. | Stocks WB current source физическую детализацию не даёт. |
| warehouseCoef | Коэффициент склада | Коэффициент, связанный с расчётом хранения. | CORE DIAG: тарифная причина. | — |
| giId | ID поставки | Supply lineage. | DIAG. | Finance.giId. |
| chrtId | ID варианта | Variant ID. | VARIANT FK. | Stocks.chrtId. |
| size | Размер | Размер варианта. | VARIANT. | Orders.techSize. |
| barcode | Баркод | Barcode. | VARIANT/OPS. | Orders/Sales.barcode; Finance.sku. |
| subject | Предмет | Тип товара. | DIM. | Orders.subject/Finance.subjectName. |
| brand | Бренд | Бренд. | DIM. | Orders.brand. |
| vendorCode | Артикул продавца | SKU. | DIM/DISPLAY. | Orders.supplierArticle. |
| nmId | ID товара WB | Товарный ключ. | CORE FK: позволяет поартикульное хранение. | Все товарные источники. |
| volume | Объём товара | Объём, участвующий в тарифе хранения. | CORE DIAG: почему storage cost такой. | — |
| calcType | Тип расчёта | Категория/основание начисления хранения. | CORE CLASSIFIER: объяснение storage charge. | — |
| warehousePrice | Стоимость хранения по строке | Денежное начисление storage row. | CORE P&L SKU ALLOCATION. | Σ ≈ Finance.paidStorageSum: 1434,84 vs 1434,80 ₽. |
| barcodesCount | Количество единиц/баркодов | Количество товара, участвующее в расчёте. | CORE QUANTITY. | — |
| palletPlaceCode | Код паллетоместа | Место хранения паллеты, если применимо. | OPS/DIAG. | — |
| palletCount | Количество паллет | Pallet quantity. | OPS/COST DIAG. | — |
| originalDate | Исходная дата | Original date для перерасчёта/начисления. | TECH/RECALC DIAG. | — |
| loyaltyDiscount | Loyalty discount | Скидочная/loyalty component report. | RAW/DIAG; не storage P&L сама по себе. | Finance.loyaltyDiscount. |
| tariffFixDate | Дата фиксации тарифа | Когда tariff condition зафиксировано. | DIAG/TECH. | Finance.fixTariffDateFrom/To related. |
| tariffLowerDate | Дата снижения тарифа | Когда применилось снижение тарифа. | DIAG/TECH. | — |

# 9. Acceptance Report

В контрольной неделе endpoint вернул **0 строк**. Поэтому field-by-field словарь Acceptance **не считаем эмпирически подтверждённым** и не заполняем его «по памяти».

Что подтверждено текущим run:
- Finance weekly `paidAcceptance = 40 ₽`;
- это 4 строки `sellerOperName = Обработка товара` по 10 ₽;
- строки имели `nmId/srid`, поэтому это FBS processing и поартикульно атрибутируется прямо из Finance.

Для FBW paid acceptance отдельный Acceptance Report остаётся правильным потенциальным source, но его фактическую схему надо зафиксировать на неделе, где endpoint вернёт строки.

---

# 10. Marketplace FBS Orders `/api/v3/orders`

**Не был выгружен в PMM-58**, поэтому field dictionary специально НЕ выдумываем.

Что фиксируем как gap:
- при компании с FBO/FBW + FBS одна Statistics Orders недостаточна для полного operational order contour;
- следующий сбор должен включать Marketplace FBS Orders;
- после этого отдельно фиксируем его grain/fields/statuses и crosswalk к Statistics Sales/Finance.

---

# 11. Cross-source map: какие бизнес-сущности повторяются

| Бизнес-сущность | Orders | Sales | Funnel | Finance | Stocks |
| --- | --- | --- | --- | --- | --- |
| Товар | `nmId` | `nmId` | `product.nmId` | `nmId` | `nmId` |
| Lifecycle позиции | `srid` | `srid` | — | `srid` | — |
| Event sale/return | — | `saleID` | — | `rrdId` + classifiers | — |
| Seller-side цена | `priceWithDisc` | `priceWithDisc` | `orderSum` aggregate | `retailPriceWithDisc` | — |
| Buyer-side money | `finishedPrice` | `finishedPrice` + `paymentSaleAmount` | — | `retailAmount` | — |
| Заказы, шт. | event rows | — | `orderCount` | — | — |
| Остаток | — | — | **нет** | — | `quantity` |
| Склад | `warehouseName` | `warehouseName` | — | `officeName`/metadata | WB aggregate / Seller concrete |
| Комиссия | — | provisional relationship | — | `commissionPercent`, commission components | — |
| Эквайринг | — | — | — | `acquiringFee` | — |
| Логистика | — | — | — | `deliveryService` | — |
| Хранение | — | — | — | `paidStorage` total | Paid Storage by SKU |

---

# 12. Что фактически сошлось

## Orders ↔ Sales

На 516 matched `srid`:
- `nmId` — 516/516;
- `gNumber` — 516/516;
- `totalPrice` — 516/516;
- `discountPercent` — 516/516;
- `priceWithDisc` — 516/516;
- `spp` — 516/516;
- `Orders.finishedPrice = Sales.finishedPrice + Sales.paymentSaleAmount` — 516/516.

**Вывод:** Statistics Orders и Sales очень сильно подтверждают друг друга на одном lifecycle.

## Sales ↔ Finance

766/766 Sales events matched по `srid + sale/return`.

`Sales.priceWithDisc ≈ Finance.retailPriceWithDisc`:
- 763/766 в пределах 0,02 ₽;
- 765/766 в пределах 1 ₽.

`Sales.finishedPrice ≈ Finance.retailAmount`:
- 762/766 в пределах 0,02 ₽.

**Вывод:** Finance strongly confirms Sales lifecycle/money, но Finance не является счётчиком первоначальных Orders.

## Orders ↔ Funnel

Количество расходится:

| date | Statistics Orders `flag=1` | Funnel.orderCount |
| --- | ---: | ---: |
| 27.08 | 36 | 39 |
| 28.08 | 43 | 39 |
| 29.08 | 28 | 32 |
| 30.08 | 32 | 37 |
| 31.08 | 30 | 36 |
| 01.09 | 25 | 29 |
| 02.09 | 28 | 32 |

При этом среди product-day, где counts совпали и были >0:
- 143 product-day;
- `orderSum ≈ Σ Orders.priceWithDisc` в 133/143 в пределах 0,02 ₽.

**Вывод:** price semantics близка, но **population заказов Funnel и Statistics различается**.

---

# 13. Кому доверяем по итоговой метрике

| Вопрос | Authority | Почему |
| --- | --- | --- |
| FBO/FBW operational orders | Statistics Orders `flag=1` | event-level, `srid`, business date |
| FBS operational orders | Marketplace FBS Orders | отдельный source обязателен; пока не audited |
| Полный demand компании | FBO/FBW + FBS вместе | иначе неполная картина |
| Sale/Return lifecycle | Sales | `saleID`, `srid` |
| Funnel behaviour | Funnel | views/cart/conversions/buyout |
| Raw order count | Orders, НЕ Funnel | Funnel population отличается |
| Финальные деньги | Finance weekly | three-method reconciliation подтверждён |
| Текущие деньги | Finance daily / PROVISIONAL | weekly ещё не settled |
| FBS stock by location | Seller Stocks | конкретный warehouse |
| FBO/FBW current stock | WB Stocks aggregate | location недоступна |
| SKU storage cost | Paid Storage | 1434,84 vs Finance 1434,80 ₽ |

---

# 14. Finance: три метода — итоговая архитектура

```text
1. /sales-reports/list
   → какие reports существуют
   → reportId / totals / createDate
   → finality

2. /sales-reports/detailed/{reportId}
   → exact settled financial rows конкретного report

3. /sales-reports/detailed
   → period=daily: текущая неделя / PROVISIONAL
   → period=weekly: reconciliation/backfill
```

За 24–30.08:
- daily = 2125 rows;
- weekly = 2125;
- exact detail = 2061 + 64 = 2125;
- `rrdId` sets identical;
- exact detail и weekly совпали по business fields.

---

# 15. Открытые вопросы, которые нельзя потерять

1. **FBS Orders:** добавить отдельный Marketplace operational source и сверить его с Sales/Finance.
2. **Stocks missing rows:** почему 7 известных nmId отсутствуют и в WB, и Seller stock responses.
3. **FBW localization:** текущий доступный API агрегирует stock как `Склад WB`; физическую warehouse location восстановить нельзя.
4. **Funnel vs Orders:** точная причина различия population неизвестна; для PMM-58 достаточно authority rule.
5. **Delivery speed:** текущие источники не дают надёжный `arrived_to_pvz_at`; никаких 1–2/3–4/5–7 day зон пока не строим.
6. **Acceptance fields:** зафиксировать field schema на периоде с ненулевым Acceptance report.
7. **Promotion:** отдельная reconciliation расходов/бонусов остаётся follow-up.


# 16. Связанный архитектурный артефакт

Целевая модель хранения, DDL, правила миграции V17, dual-write/backfill, переключение UI, acceptance criteria, тесты и разбиение реализации вынесены в отдельный документ:

`docs/architecture/target-data-model-and-v17-migration.md`

Отзывы в этот архитектурный документ намеренно не входят и остаются отдельным будущим доменом.
