# inventory-forecasting - round 1

Дата доступа ко всем источникам: 2026-09-02. Бюджет: 18 tool-вызовов израсходован; прочитано 9 первичных страниц + 5 поисковых выдач. Заблокированы (HTTP 403 / пустая страница): `sostocked.com/pricing`, `g2.com/products/sostocked/reviews`, `sellercentral.amazon.com/help/.../G200798270` (Amazon Restock Inventory help вернул только навигацию).

## Карта сегмента (широкий срез)

- **Лидеры (по объёму и зрелости):** Inventory Planner (Sage) - enterprise-ориентированный, «Request pricing»; SoStocked (Carbon6) - Amazon-специфичный; RestockPro (eComEngine) - Amazon FBA, самый дешёвый вход.
- **Челленджеры:** Flieber (multi-channel, «AI-powered demand forecasting», 14-day trial); Prediko (Shopify-first, AI-агент Pia).
- **Мёртвые / поглощённые:** Forecastly (закрыт 15.09.2021, функциональность в Jungle Scout); Cogsy («discontinued», теперь «part of Mayple»).
- **Wildcard:** Inventory Hero (запущен 2026; MCP-сервер внутри Claude, «Drafted POs … ready for your approval», «AI Employee Handbook» как командная память).
- **Amazon native:** Restock Inventory / FBA recommendations - первичную документацию за этот раунд получить не удалось (см. «Не нашёл»).

## Что искал и что нашёл (по продуктам)

### SoStocked (Carbon6)

**(A) Утренний дайджест / алерты.** На странице продукта заявлены «Get Reorder Alerts» и «Monitor inventory health with pre-designed or customized dashboards»; канал (email/Slack) и периодичность (ежедневно/по событию) на странице не раскрыты (Carbon6, дата неизвестна, https://carbon6.io/sostocked, доступ 2026-09-02).
**(B) Аномалия → диагноз → действие.** Цепочка сводится к «velocity → рекомендация min/max restock → quick PO»: «Generate quick POs and know the status (Production, customs, 3PL, checked-in)»; объяснение «почему» и шаг одобрения на странице не описаны (Carbon6, дата неизвестна, https://carbon6.io/sostocked, доступ 2026-09-02).
**(C) Память решений / проверка исхода.** Не найдено ни на странице продукта, ни в поисковых сниппетах.
**(D) Прогноз.** Метод назван как «Adjusted Velocity», который автоматически учитывает «past sales, Prime Day, seasonality, and sales spikes»; горизонт прогноза и ручные корректировки на странице не раскрыты (Carbon6, дата неизвестна, https://carbon6.io/sostocked, доступ 2026-09-02).
**(E) Реклама.** Не найдено - продукт не позиционируется как ads-инструмент.
**(F) Отзывы/вопросы.** Не найдено.
**(G) Контент/листинг.** Не найдено.
**Цены и упаковка.** Первичная страница цен недоступна (403). На странице Carbon6 указано «$474 USD» за 3-месячный план, «longer-term contracts available», агентская цена по консультации и баннер «Sign up for SoStocked before prices increase on March 1» без года (Carbon6, дата неизвестна, https://carbon6.io/sostocked, доступ 2026-09-02). Вторичный источник даёт «basic plan is $158 monthly and supports up to 1,000 orders», «$126 USD per month as an annual plan», 30-day free trial и «ProfitFlow starts at $97 a month», «full inventory product is demo-led from $250 a month» (RevenueGeeks, дата неизвестна, https://revenuegeeks.com/sostocked-pricing/, доступ 2026-09-02, только поисковый сниппет) - три цифры ($158/мес, $474/3 мес = $158/мес, «from $250 a month») конфликтуют, точная модель не подтверждена.
**Позиционирование.** «SoStocked by Carbon6», агентский мультиаккаунт: «Do you manage multiple brands that have different account owners?» (Carbon6, дата неизвестна, https://carbon6.io/sostocked, доступ 2026-09-02).
**Траектория.** Только факт владения Carbon6; релизов/финансирования за 6 мес не найдено.
**Голос клиентов.** G2 заблокирован (403); независимых отзывов за этот раунд не получено.

### Inventory Planner (Sage)

**(A)** «Purchasing recommendations based on up-to-date forecasts, for all locations» и «Know what to order, when and where»; email-дайджест или утренняя сводка на странице функций не упомянуты (Inventory Planner/Sage, дата неизвестна, https://www.inventory-planner.com/features/, доступ 2026-09-02).
**(B)** Рекомендация закупки есть; «Sage Copilot» описан лишь как «Your AI productivity assistant for retail insights», а «Sage AI» - как «recommendation engine»; объяснения причин и approval-контура в описании нет (Inventory Planner/Sage, дата неизвестна, https://www.inventory-planner.com/features/ и https://www.inventory-planner.com/pricing/, доступ 2026-09-02).
**(C)** Не найдено.
**(D)** Явно названы: «Select the most suitable forecasting model for each product» (сезонные/несезонные/retail/wholesale), «Automated trend adjustment» («constantly monitors your sales patterns and adjusts demand forecasts»), прогноз новых товаров «borrows» данные похожих товаров (style, size, color, material), ручная настройка «stock coverage days at every level, from SKU to supplier»; горизонт не указан (Inventory Planner/Sage, дата неизвестна, https://www.inventory-planner.com/features/, доступ 2026-09-02).
**(E)** Косвенно - «Inventory-powered marketing: Sync purchasing with campaigns» (Inventory Planner/Sage, дата неизвестна, https://www.inventory-planner.com/pricing/, доступ 2026-09-02); никаких ads-guardrails.
**(F), (G)** Не найдено.
**Цены и упаковка.** Цен на странице нет: «Request pricing now», «Our pricing is based on the volume of inventory you manage – with no nasty surprises», «unlimited users at no extra cost», «Go live in 4 weeks (on average)», «24/7 monitored support plus dedicated account management» (Inventory Planner/Sage, дата неизвестна, https://www.inventory-planner.com/pricing/, доступ 2026-09-02).
**Позиционирование vs продукт.** Заявка «save around 23 hours a week» - маркетинговая цифра без источника (там же). Open-to-buy бюджетирование - явный уклон в retail/ERP, а не в marketplace-селлера.
**Траектория, голос клиентов.** Не получено за этот раунд.

### Flieber

**(A)** «Stockout, overstock, and replenishment alerts» входят во все планы; канал и расписание не указаны (Flieber, дата неизвестна, https://www.flieber.com/pricing, доступ 2026-09-02).
**(B)** «Scenario analysis for purchase and transfer orders» - селлер сравнивает сценарии, но описания диагноза «почему» и approval-шага нет (там же).
**(C)** Не найдено.
**(D)** «AI-powered demand forecasting»; метод/горизонт/overrides на странице цен не раскрыты (там же).
**(E), (F), (G)** Не найдено.
**Цены и упаковка.** Публичных тарифов нет: «Pricing is calculated from a few key inputs about your business — sales volume, channels, and SKU count»; «14-day free trial — no credit card required»; «Most brands are fully set up in under an hour»; «Free onboarding with no implementation fees»; «Google Sheets bridge automation»; работает поверх существующих ERP/IMS (Flieber, дата неизвестна, https://www.flieber.com/pricing, доступ 2026-09-02).
**Голос клиентов, траектория.** Не получено.

### Prediko

**(A)** Агент «Pia» «shares stockout risks, late POs, and inventory health straight to inbox or chat», подключается к Slack «to receive updates and ask questions directly from where your team already works» (Prediko, дата неизвестна, https://www.prediko.io/product/inventory-ai-agent, доступ 2026-09-02, поисковый сниппет).
**(B)** «Pia recommends what to reorder and what needs attention»; «executes commands including creating and updating POs, refreshing forecasts for up to 12 months, generating and scheduling reports»; есть «back-and-forth conversations … to dig into any data point» - это ближе всего к цепочке аномалия→диагноз→действие в сегменте, но approval/guardrail-шаг в сниппете не описан (там же).
**(C)** Не найдено.
**(D)** «Revenue & Inventory AI Forecasting», горизонт «up to 12 months» (через Pia); заявка «trained on 25M+ SKUs across 15 industries» - маркетинг без независимого подтверждения (Prediko, https://www.prediko.io/pricing и https://www.prediko.io/product/inventory-ai-agent, доступ 2026-09-02).
**(E), (F), (G)** Не найдено.
**Цены и упаковка.** «The plan amount is based on total annual revenue taken from Shopify»; вход «<$100k GMV — $49/month»; сетка до «$50m+ GMV» (цены верхних ступеней на странице не читаются); add-on «Raw Materials Forecasting & BOMs: $20»; «14 day free trial»; во всех планах «Unlimited Users, SKUs, POs», «AI Inventory Coworker - PIA», «Private Slack Channel», «Full API Access», «Dedicated Customer Success Manager» (Prediko, дата неизвестна, https://www.prediko.io/pricing, доступ 2026-09-02).
**Позиционирование.** Shopify-first («taken from Shopify»); marketplace-селлер (Amazon/WB) не в фокусе.

### Forecastly

**Статус.** «As of September 15, 2021, Forecastly is no longer available», возможности перенесены в Jungle Scout (ProjectFBA, обновлено 2025-07-29, https://projectfba.com/forecastly-review/, доступ 2026-09-02; подтверждено сниппетом Jungle Scout, https://www.junglescout.com/resources/articles/amazon-inventory-forecasting/, доступ 2026-09-02). Историческая цена «$80/month for sellers with ≤$3,000 monthly sales», 14-day trial (ProjectFBA, 2025-07-29). По областям A-G - только исторические «demand forecasting with real-time results», «replenishment statistics», «inbound shipment tool» (там же). Для тирдауна нерелевантен; наследник - Jungle Scout Inventory Manager.

### Cogsy

**Статус.** «Cogsy has been discontinued and is no longer available», «part of Mayple», дата сделки не указана (Mayple, дата неизвестна, https://maypleglobal.com/cogsy, доступ 2026-09-02; редирект 301 с https://www.cogsy.com/pricing). Области A-G не оцениваются.

### RestockPro (eComEngine)

**(A)** На странице цен - «Priority Flags»; отдельно у FeedbackFive - «Feedback & Review Alerts» и «Listing Change Alerts», у SellerPulse - «FBA Fee Insights and Alerts»; расписание/канал не указаны (eComEngine, дата неизвестна, https://www.ecomengine.com/pricing, доступ 2026-09-02).
**(B)** «Inventory Forecasting», «Build and Optimize Kits», «Supplier Management», «Custom Amazon Item Labels» - workflow закупки, без описанного слоя объяснения/одобрения (там же).
**(C)** Не найдено.
**(D)** «Inventory Forecasting» без названного метода/горизонта (там же).
**(E)** Не найдено.
**(F)** В экосистеме eComEngine - FeedbackFive: «Review Automation», «Review Monitoring & Analytics», «Feedback & Review Alerts» от $34/мес (там же).
**(G)** FeedbackFive: «Listing Change Alerts» (там же).
**Цены.** RestockPro «Starting at $49/mo», ступени по FBA-заказам от 1,000 до 300,000; FeedbackFive от $34/мес; SellerPulse от $89/мес и включает «Inventory Planning», «Buy Box Report», «SKU Economics Report» (eComEngine, дата неизвестна, https://www.ecomengine.com/pricing, доступ 2026-09-02). Сниппет help-центра расходится с этим («$99 per month (1,000 monthly orders) … $399 per month (20,000 monthly orders)»; «12 months for the price of 10»; агентские тарифы) (eComEngine Help, дата неизвестна, https://www.ecomengine.com/help/subscriptions-plans-pricing, доступ 2026-09-02, сниппет) - live-страница цен приоритетнее.

### Inventory Hero (wildcard)

**(A/B)** «Drafted POs, flagged reorders, and priced lost sales, ready for your approval» - явный approval-паттерн; рекомендации учитывают «supplier lead time, MOQ, safety stock, and seasonal peaks» (Inventory Hero, 2026, https://www.inventoryhero.ai/alternatives/forecastly, доступ 2026-09-02).
**(C)** «AI Employee Handbook» - «Permanent, team-shared business memory» (там же); это память контекста, а не журнал решений с проверкой ожидаемое/фактическое.
**(D)** «Auto-updating 30, 90, and 365 day forecasts from real sales velocity and seasonality» (там же).
**Интерфейс.** «Works inside Claude (MCP server)» - «Talk to your real inventory data from Claude desktop, web, or Claude Code» (там же).
**Цены.** «plans start at $79 per month, billed by order volume, with a free trial and no credit card required» (там же). «launched 2026, ongoing marketplace rollouts» (там же). Единственный источник - сама страница вендора-конкурента Forecastly; уверенность низкая-средняя.

### Amazon native restock tools

Help-страница Seller Central (G200798270) отдала только навигацию без контента; вторичный сниппет Jungle Scout лишь описывает, что Amazon-прогнозирование «uses machine learning algorithms to analyze purchasing data» (Jungle Scout, дата неизвестна, https://www.junglescout.com/resources/articles/amazon-inventory-forecasting/, доступ 2026-09-02). Утверждений о native-инструменте за этот раунд сделать нельзя.

## Claims (нумерованный список)

1. Inventory Planner не публикует цены: «Request pricing now», «pricing is based on the volume of inventory you manage» | pricing | https://www.inventory-planner.com/pricing/ | Inventory Planner (Sage) | unknown | accessed 2026-09-02 | high | no
2. Inventory Planner: конфигурируемая модель прогноза на товар, «Automated trend adjustment», прогноз новинок по похожим товарам, «stock coverage days» от SKU до поставщика | features | https://www.inventory-planner.com/features/ | Inventory Planner (Sage) | unknown | accessed 2026-09-02 | high | yes
3. Inventory Planner: «Sage Copilot — Your AI productivity assistant for retail insights», «Sage AI (recommendation engine)», «unlimited users», «Go live in 4 weeks (on average)» | positioning | https://www.inventory-planner.com/pricing/ | Inventory Planner (Sage) | unknown | accessed 2026-09-02 | high | no
4. Flieber: цены не публичны, считаются от «sales volume, channels, and SKU count»; 14-day free trial без карты | pricing | https://www.flieber.com/pricing | Flieber | unknown | accessed 2026-09-02 | high | no
5. Flieber: во все планы входят «Stockout, overstock, and replenishment alerts», «Scenario analysis for purchase and transfer orders», «AI-powered demand forecasting» | features | https://www.flieber.com/pricing | Flieber | unknown | accessed 2026-09-02 | high | yes
6. Prediko: тариф от «$49/month» при «<$100k GMV», привязан к «total annual revenue taken from Shopify»; add-on «Raw Materials Forecasting & BOMs: $20»; 14 day free trial | pricing | https://www.prediko.io/pricing | Prediko | unknown | accessed 2026-09-02 | high | no
7. Prediko: во всех планах «AI Inventory Coworker - PIA», «Purchase Order Management & Buying Alerts», «Private Slack Channel», «Full API Access» | features | https://www.prediko.io/pricing | Prediko | unknown | accessed 2026-09-02 | high | no
8. Prediko Pia «shares stockout risks, late POs, and inventory health straight to inbox or chat», подключается к Slack, «recommends what to reorder», исполняет команды (создание/обновление PO, обновление прогноза до 12 мес, планирование отчётов) | features | https://www.prediko.io/product/inventory-ai-agent | Prediko | unknown | accessed 2026-09-02 | medium | yes
9. Prediko: «trained on 25M+ SKUs across 15 industries» | traction | https://www.prediko.io/product/inventory-ai-agent | Prediko | unknown | accessed 2026-09-02 | low | no
10. Forecastly закрыт «As of September 15, 2021», функции - в Jungle Scout | trajectory | https://projectfba.com/forecastly-review/ | ProjectFBA | 2025-07-29 | accessed 2026-09-02 | high | no
11. Forecastly закрыт с 15.09.2021, возможности доступны через Jungle Scout (второй издатель) | trajectory | https://www.junglescout.com/resources/articles/amazon-inventory-forecasting/ | Jungle Scout | unknown | accessed 2026-09-02 | medium | no
12. Cogsy «has been discontinued and is no longer available», «part of Mayple»; cogsy.com/pricing даёт 301 на maypleglobal.com/cogsy | trajectory | https://maypleglobal.com/cogsy | Mayple | unknown | accessed 2026-09-02 | high | no
13. RestockPro «Starting at $49/mo», ступени по FBA-заказам 1,000…300,000; включает «Inventory Forecasting», «Supplier Management», «Priority Flags», «Build and Optimize Kits» | pricing | https://www.ecomengine.com/pricing | eComEngine | unknown | accessed 2026-09-02 | high | no
14. FeedbackFive (eComEngine) от $34/мес включает «Review Automation», «Feedback & Review Alerts», «Listing Change Alerts»; SellerPulse от $89/мес - «FBA Fee Insights and Alerts», «Inventory Planning» | features | https://www.ecomengine.com/pricing | eComEngine | unknown | accessed 2026-09-02 | high | yes
15. Help-центр eComEngine называет RestockPro «$99 per month (1,000 monthly orders)» … «$399 per month (20,000 monthly orders)» и «12 months for the price of 10» - расходится с live-страницей цен | pricing | https://www.ecomengine.com/help/subscriptions-plans-pricing | eComEngine | unknown | accessed 2026-09-02 | low | no
16. SoStocked: метод «Adjusted Velocity» учитывает «past sales, Prime Day, seasonality, and sales spikes»; «Get Reorder Alerts»; «Generate quick POs and know the status (Production, customs, 3PL, checked-in)»; агентский мультиаккаунт | features | https://carbon6.io/sostocked | Carbon6 | unknown | accessed 2026-09-02 | medium | yes
17. SoStocked (Carbon6): «$474 USD» за 3-месячный план, «longer-term contracts available», агентская цена по консультации, баннер «before prices increase on March 1» без года | pricing | https://carbon6.io/sostocked | Carbon6 | unknown | accessed 2026-09-02 | medium | no
18. SoStocked: «basic plan is $158 monthly … up to 1,000 orders», «$126 USD per month as an annual plan», 30-day free trial, «ProfitFlow starts at $97 a month», inventory «from $250 a month» | pricing | https://revenuegeeks.com/sostocked-pricing/ | RevenueGeeks | unknown | accessed 2026-09-02 | low | no
19. Inventory Hero: «Drafted POs, flagged reorders, and priced lost sales, ready for your approval»; прогнозы «30, 90, and 365 day … from real sales velocity and seasonality»; «Works inside Claude (MCP server)»; «AI Employee Handbook — Permanent, team-shared business memory» | features | https://www.inventoryhero.ai/alternatives/forecastly | Inventory Hero | 2026 | accessed 2026-09-02 | medium | yes
20. Inventory Hero: «plans start at $79 per month, billed by order volume», free trial без карты; «launched 2026» | pricing | https://www.inventoryhero.ai/alternatives/forecastly | Inventory Hero | 2026 | accessed 2026-09-02 | medium | no
21. Inventory Planner заявляет «save around 23 hours a week» на автоматизации пополнения - без источника | positioning | https://www.inventory-planner.com/pricing/ | Inventory Planner (Sage) | unknown | accessed 2026-09-02 | low | no

## Паттерны, повторяющиеся у лидеров

1. **Цена по объёму, не по фичам.** Все живые продукты тарифицируются от объёма (заказы FBA - RestockPro, SoStocked; GMV - Prediko; объём инвентаря - Inventory Planner; sales/channels/SKU - Flieber; orders - Inventory Hero) (claims 1, 4, 6, 13, 17, 20). Верхний сегмент (Inventory Planner, Flieber, SoStocked full) уходит в demo-led без публичных цен.
2. **Алерт = «reorder now», а не «почему».** Во всех продуктах есть stockout/reorder/overstock-алерты (Flieber, SoStocked, Prediko, RestockPro «Priority Flags»), но ни один публичный источник не описывает слой диагноза причины отклонения (claims 5, 7, 13, 16).
3. **Push в чат как новая норма для AI-агентов.** Prediko Pia пушит риски «straight to inbox or chat» и в Slack; Inventory Hero живёт внутри Claude через MCP (claims 8, 19). У классических инструментов (Inventory Planner, RestockPro) канал доставки не декларируется.
4. **Рекомендация → черновик PO → одобрение человеком.** «Drafted POs … ready for your approval» (Inventory Hero), «Generate quick POs» (SoStocked), «Purchase Order Management & Buying Alerts» (Prediko), «Scenario analysis for purchase and transfer orders» (Flieber) (claims 5, 7, 16, 19). Approval явно назван только у Inventory Hero.
5. **Именованные компоненты прогноза как доверие.** Сезонность, тренд, lead time, MOQ, safety stock, Prime Day называются явно (Inventory Planner, SoStocked, Inventory Hero) (claims 2, 16, 19); горизонт назван только у Inventory Hero (30/90/365) и Prediko (до 12 мес).
6. **Консолидация сегмента.** Forecastly → Jungle Scout (2021), Cogsy → Mayple, SoStocked → Carbon6, Inventory Planner → Sage (claims 10-12, 16): standalone-прогнозирование выживает как модуль платформы.
7. **Отзывы и листинг - в соседних продуктах того же вендора, не в инвентарном.** eComEngine: FeedbackFive («Listing Change Alerts», «Feedback & Review Alerts») рядом с RestockPro (claim 14).

## Лиды для следующего раунда

- **Конфликт цен SoStocked** (приоритет): $474/3 мес (Carbon6) vs $158/мес и «from $250 a month» (RevenueGeeks) vs недоступный sostocked.com/pricing (403). Нужен второй прямой источник (Shopify/Amazon Appstore listing, Tekpon, Capterra).
- **Конфликт цен RestockPro**: live-страница «from $49/mo» vs help-центр «$99…$399». Прочитать help-страницу целиком.
- **Jungle Scout Inventory Manager** - наследник Forecastly, не рассмотрен; проверить, есть ли дайджест/алерты.
- **Prediko Pia**: получить первичную страницу продукта и help-доки - есть ли approval-guardrail на «creating and updating POs», как выглядит Slack-дайджест, есть ли объяснение причин.
- **Inventory Hero**: единственный источник - собственная страница; нужен независимый (Shopify App Store, Product Hunt), и уточнить «AI Employee Handbook» как форму decision memory.
- **Amazon native**: Restock Inventory / FBA Inventory recommendations / «Minimum inventory level» - получить доступную help-страницу или Amazon Seller blog; проверить, показывает ли Amazon «recommended replenishment quantity» и когда.
- **Sage Copilot** внутри Inventory Planner: что реально умеет (чат по данным? объяснения?), релиз-ноуты Sage.
- **Mayple × Cogsy**: дата сделки и что из Cogsy (Slack digests, «operational model») попало в Mayple.
- **Независимые отзывы**: G2 блокирует фетч - использовать Capterra/Trustpilot/Reddit r/FulfillmentByAmazon для SoStocked, Inventory Planner, Flieber.
- Новые сущности из выдачи: SKU Compass, Drivepoint (FP&A для DTC), Scale Insights (Amazon ads + forecasting - потенциально закрывает область E), Nova Data.

## Не нашёл

- **(C) Память решений и сверка ожидаемое vs фактическое** - ни у одного продукта сегмента; ближайшее - «business memory» у Inventory Hero, но это контекст, а не журнал решений.
- **(E) Ads-guardrails с учётом OOS** - у инвентарных инструментов не найдено; единственная связка - «Inventory-powered marketing» у Inventory Planner без деталей.
- **Каналы и расписание дайджестов** для Inventory Planner, Flieber, SoStocked, RestockPro - вендоры не указывают, ежедневно ли и куда приходят алерты.
- **Горизонт прогноза** у Inventory Planner, Flieber, SoStocked, RestockPro.
- **Ручные overrides прогноза** - явно описаны только «stock coverage days» (Inventory Planner) и «forecasting model per product»; у остальных не найдено.
- **Amazon native restock docs** - help-страница отдала только навигацию.
- **Независимые отзывы 1-3 звезды** - G2 403; за раунд ни одного отзывного источника не прочитано.
- **Цены верхних ступеней Prediko** и любые цены Inventory Planner / Flieber / Cogsy.
- **Trajectory-сигналы ≤6 мес** (релизы, финансирование, найм) - не найдены ни для одного продукта; лишь косвенные («launched 2026» у Inventory Hero, «before prices increase on March 1» у SoStocked без года).
