# amazon-analytics-alerts - round 3

Дата доступа ко всем источникам: 2026-09-02. Бюджет: 15 вызовов инструментов, 8 страниц прочитано целиком (2 запроса к KB Helium 10 - HTTP 403), плюс сниппеты 6 поисковых выдач. Раунд шёл по лидам раунда 2: противоречия по Amazon Seller Assistant и ценам Jungle Scout, KB Helium 10, Perpetua/Sellics, области C/D/F, Sellerboard и SellerApp напрямую, freshness цен Helium 10.

## Что искал и что нашёл (по продуктам)

### Amazon Seller Assistant (ex-Project Amelia)

**Противоречие раунда 2 (US rollout: «все селлеры США» vs «декабрь 2025») - разрешено в пользу первичного источника.** Официальный текст Amazon говорит: «Seller Assistant is currently available to all sellers in the U.S. store» и «will be rolled out to other countries in the coming months, at no additional cost»; дата публикации на странице не выведена (About Amazon, дата unknown - по контексту Amazon Accelerate 2025, https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai, доступ 2026-09-02). Формулировки Nova/Seller Sprite про «US rollout Dec 2025» первичным текстом не подтверждаются; для EU/UK первичного анонса по-прежнему нет.

**(A) Проактивные сигналы.** Первичный текст описывает не дайджест, а мониторинг: «continuously monitor a seller's account status and surface potential issues», «will proactively flag slow-moving products before they incur long-term storage fees», «will alert sellers prior to seasonal peaks with ready-to-implement strategies» (About Amazon, unknown, https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai, доступ 2026-09-02). Обратите внимание на будущее время «will» - красный флаг: это заявленные, а не подтверждённо отгруженные функции. Фиксированное время/канал утренней сводки не описаны.

**(B) Аномалия -> диагноз -> действие с разрешением.** Модель разрешения в первичном тексте: «help take action with a seller's permission», «when authorized», «If the seller approves, Seller Assistant implements the solution», «Once approved, it coordinates everything» (About Amazon, unknown, https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai, доступ 2026-09-02). **Противоречие/несоответствие с раундом 2:** формулировка Nova Analytics про режимы «suggest only» / «auto-approve» в первичном тексте Amazon отсутствует - там только «with permission»; режим auto-approve остаётся неподтверждённым вторичным утверждением. Страница для селлер-партнёров подтверждает общую модель: «tailored insights and recommendations, and with permission from the seller, takes action on their behalf», области экспертизы «inventory optimization, advertising strategy, compliance, and more» (Amazon Selling Partners, страница ссылается на материал от 2026-06-18, https://sellingpartners.aboutamazon.com/seller-assistant, доступ 2026-09-02).

**(C) Память решений.** Ни один из двух первичных текстов не описывает запись решения и сравнение ожидания с фактом; есть только метрика принятия рекомендаций (см. traction).

**(D) Прогноз спроса.** Метод не назван: «analyze demand patterns and prepare shipment recommendations», «comparing historical data with current trends» (About Amazon, unknown, https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai, доступ 2026-09-02). Горизонт, сезонность, overrides - не описаны.

**(E) Реклама.** Заявлена как область экспертизы («advertising strategy»), гардрейлов и OOS-логики в текстах нет (Amazon Selling Partners, 2026-06, https://sellingpartners.aboutamazon.com/seller-assistant, доступ 2026-09-02).

**(F) Отзывы/вопросы.** Не упомянуты ни на одной из двух страниц (About Amazon; Amazon Selling Partners, доступ 2026-09-02).

**(G) Листинг.** Упомянут смежный инструмент «Enhance My Listing tool to make listing optimization effortless» (About Amazon, unknown, https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai, доступ 2026-09-02).

**Traction.** Amazon заявляет «more than 230,000 monthly users» и «Independent sellers accept the recommended actions of the AI-powered Seller Assistant over 90% of the time» (Amazon Selling Partners, 2026-06, https://sellingpartners.aboutamazon.com/seller-assistant, доступ 2026-09-02). Это single-publisher claim самого вендора - по правилу двух источников не «verified»; независимого подтверждения в этом раунде не искалось из-за бюджета.

**Новая сущность.** В выдаче About Amazon появилась страница «Amazon's new AI experience helps sellers visualize and grow their business in real time» - «canvas experience», по сниппету «built on the same agentic AI architecture as Seller Assistant, powered by Amazon Bedrock and leveraging Amazon Nova and Anthropic Claude» (About Amazon, дата unknown, https://www.aboutamazon.com/news/innovation-at-amazon/amazon-sellers-canvas-artificial-intelligence, доступ 2026-09-02 - только сниппет, страница не открыта; низкая уверенность).

### Helium 10

**Цены (freshness-лид раунда 2 закрыт).** Живая страница цен: Platinum «$129 $99 / month» (billed yearly), Diamond «$359 $279 / month» (billed yearly), Enterprise «$1499 / month» (billed annually, starting price); дата на странице отсутствует (Helium 10, unknown, https://www.helium10.com/pricing/, доступ 2026-09-02). Жалоба на Trustpilot «starter plan jumped to $129/month» из раунда 2 согласуется с помесячной ценой Platinum $129 - это не свежее повышение, а разница между помесячной и годовой оплатой (вывод аналитика, а не источника).

**Пакетирование AI.** На странице цен: агент «Helium» - «AI commerce agent», «Included in Diamond»; «Helium 10 MCP: Included free (up to 1,000 calls)» (Helium 10, unknown, https://www.helium10.com/pricing/, доступ 2026-09-02). **Уточнение к раунду 2:** пресс-релиз привязывал MCP к Diamond+, страница цен даёт бесплатный лимит 1 000 вызовов - вероятно, бесплатная квота с расширением в верхних планах; формулировка страницы неполная.

**(A) Алерты.** В таблице планов: «Alerts» в разделе «Daily Operations» - «Get Notified About Listing Changes»; «Forecast & Manage Inventory»; «Automate & Optimize Ads» (Helium 10, unknown, https://www.helium10.com/pricing/, доступ 2026-09-02). Канал и расписание уведомлений на странице не указаны.

**(B)/(E) Approval-режим в Ads - подтверждён сниппетами KB (полный текст недоступен: HTTP 403 на обе статьи).** Страница Suggestions «shows suggestions for the targets within your campaigns that have either applied AI Bid Rules or Custom Bid Rules, as well as Keyword Harvest and Negative Keyword Rules»; пользователь может «click the checkmark to apply Helium 10 Ads suggestion directly, such as pausing or adjusting a bid», «click the "X" to defer action on a suggestion, and if you'd like more data before deciding, you can revisit it the following week»; новые предложения появляются «within 7 to 10 days» после создания правил (Helium 10 KB, дата unknown, https://kb.helium10.com/hc/en-us/articles/12125578841883-Helium-10-Ads-Suggestions, доступ 2026-09-02 - по сниппету выдачи, средняя уверенность). Типы правил: «Bid rules ... based on a number of criteria such as clicks exceeding a specific number», «Keyword Harvest rules», «Negative Targeting rules ... such as the number of clicks with no sales within a specific period» (Helium 10 KB, unknown, https://kb.helium10.com/hc/en-us/articles/18076439623963-Helium-10-Ads-Rules-Automation, доступ 2026-09-02 - сниппет). Итого: гибрид «правило -> предложение -> человек одобряет/откладывает» с недельным ритмом пересмотра; авто-применение без одобрения и OOS-логика из сниппетов не видны.

**(C)/(D)/(F)/(G)** - новых свидетельств в этом раунде нет (KB закрыт 403).

### Jungle Scout

**Противоречие цен раунда 2 - разрешено.** Страница планов Catalyst показывает ряд «Starter $29/mo x12 months | $348 annually», «Growth Accelerator $49/mo x12 months | $588 annually», «Brand Owner + CI $129/mo x12 months | $1,548 annually» с пометкой «Save up to 40% on annual plans!» (Jungle Scout, unknown, https://www.junglescout.com/pricing/catalyst-plans/, доступ 2026-09-02). Значит, $29/$49/$129 - годовой ряд; помесячный ряд ($49/$79/$149 по раунду 2) на этой странице не извлечён и остаётся с прежней уверенностью. Общая страница цен: «Save up to $360 on annual plans», доп. место «$49/month per seat (or $459/yr on an annual plan)», Cobalt - «Custom Plans» через демо (Jungle Scout, unknown, https://www.junglescout.com/pricing/, доступ 2026-09-02).

**Пакетирование.** Inventory Manager, Sales Analytics и Review Automation включены в Growth Accelerator и Brand Owner, но не в Starter; «AI Assist»: Starter «Chat Only», Growth Accelerator «100/month», Brand Owner «500/month» (Jungle Scout, unknown, https://www.junglescout.com/pricing/catalyst-plans/, доступ 2026-09-02). Строка «Alerts» в таблице планов снова не найдена - лид раунда 2 закрыт как «не нашёл» дважды.

**(D)** метод прогноза Inventory Manager по-прежнему не описан на публичных страницах.

### Sellerboard

**(D) Метод прогноза - найден (закрывает лид раунда 2).** «The adjusted sales velocity is the average number of units sold per day. This number is adjusted by the 'weight' entered per period»; сезонность: «If you turn on this option, your future sales will be forecasted, taking into account the specified coefficients. You can use sellerboard default coefficients or change them based on your experience»; override роста: «Additionally, you can project a monthly growth rate in %, which will also be included in the forecast» (sellerboard blog, 2023-05-18, https://blog.sellerboard.com/2023/05/18/how-to-increase-profitability-by-optimizing-inventory-management-a-comprehensive-guide/, доступ 2026-09-02). Итог: взвешенное скользящее среднее по периодам + коэффициенты сезонности (дефолт/ручные) + ручной % роста; горизонт явно не назван. Источник старше 3 месяцев - описание механики, не цены; уверенность средняя.

**(A) Алерты.** По сниппетам: «You will be automatically notified whether it's time to restock the FBA warehouse or to place a new order with your supplier and how large this order should be» (sellerboard blog, 2020-10-19, https://blog.sellerboard.com/2020/10/19/inventory-management-with-sellerboard/, доступ 2026-09-02 - сниппет); «Days of Stock Left and Days Until Next Order ... based on your product's sales velocity and the lead times you input» (vovaeven.com, unknown, https://vovaeven.com/blog/does-sellerboard-have-an-inventory-planner, доступ 2026-09-02 - сниппет, вторичный). Канал и время доставки алертов не найдены; у sellerboard есть пост «Automated Reporting for Amazon Sellers» (2025-05-19), не открыт по бюджету.

**(B)/(C)/(E)/(F)/(G)** - не покрыты в этом раунде.

### SellerApp

**(A) Алерты - прямой заход выполнен.** Типы: «Price Alert», «Inventory Alert», «Listing Quality Alert» (LQI), «Hijacker Alert», «Budget Alert», плюс негативные отзывы и Buy Box; канал - email («set a contact list», «email addresses and other contact details»); режим - «Get instant alerts and emails», «receive notifications...24*7»; кастомизация - «choose which alerts you want to get notified for and define the condition» (SellerApp, unknown, https://www.sellerapp.com/amazon-product-alerts.html, доступ 2026-09-02). Дневного дайджеста, Slack/push и объяснения причины рядом с алертом на странице нет - это чистые пороговые триггеры.

**(B)** Объяснений «почему» и рекомендаций у алертов не найдено (та же страница). Остальные области не покрыты.

### Perpetua / Sellics

Страница «Sellics joins forces with Perpetua» без даты: «Together we are committed to bringing you the best single platform to profitably scale growth on Amazon, Walmart, and other top eCommerce marketplaces»; заголовок «Launch goals, not campaigns»; отчётность: «Our customizable, enterprise-level reporting allows you to understand, at a single glance, how your business and products are performing in your category across multiple channels and marketplaces»; владелец (Flywheel/IPG/Omnicom) не упомянут (Perpetua, unknown, https://perpetua.io/sellics-joins-perpetua/, доступ 2026-09-02). Лид по IPG остаётся открытым; область C (Goals «ожидание vs факт») на странице не раскрыта.

### DataHawk

В этом раунде не трогался (бюджет ушёл на противоречия).

### Область F: специализированные инструменты ответов на отзывы (новые сущности)

По сниппетам выдачи: Indellia «Response Agent (Beta) drafts replies for every new review in your connected retailer accounts, learns your specific brand voice from past responses, and presents a queue with pre-filled drafts that a human approves, edits, or skips», «tone-tuned responses for Amazon, Walmart, Bazaarvoice, and Trustpilot» (Indellia, unknown, https://indellia.com/tools/ai-review-response-generator/, доступ 2026-09-02 - сниппет, низкая уверенность). Aelestra: «AI draft responses for you to approve (Suggestive Mode), or enables full Auto-Pilot to post instantly based on your rules» - ориентирован на Google/Yelp, не на Amazon (Aelestra, unknown, https://aelestra.com/ai-review, доступ 2026-09-02 - сниппет). Паттерн «черновик -> очередь -> одобрение/автопилот по правилам» существует как категория, но у семи продуктов сегмента не подтверждён.

## Claims (нумерованный список)

1. Amazon Seller Assistant «currently available to all sellers in the U.S. store», другие страны - «in the coming months, at no additional cost» | positioning | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | unknown | accessed 2026-09-02 | high | yes
2. Seller Assistant действует «with a seller's permission»; «If the seller approves, Seller Assistant implements the solution»; режимы «suggest only»/«auto-approve» в первичном тексте отсутствуют | features | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | unknown | accessed 2026-09-02 | high | yes
3. Seller Assistant «will proactively flag slow-moving products before they incur long-term storage fees» и «will alert sellers prior to seasonal peaks with ready-to-implement strategies» (будущее время) | features | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | unknown | accessed 2026-09-02 | medium | no
4. Seller Assistant: «more than 230,000 monthly users», рекомендации принимаются «over 90% of the time» (заявление вендора, один издатель) | traction | https://sellingpartners.aboutamazon.com/seller-assistant | Amazon Selling Partners | 2026-06 | accessed 2026-09-02 | medium | yes
5. Seller Assistant покрывает «inventory optimization, advertising strategy, compliance, and more» | features | https://sellingpartners.aboutamazon.com/seller-assistant | Amazon Selling Partners | 2026-06 | accessed 2026-09-02 | medium | no
6. Amazon «canvas experience» построен «on the same agentic AI architecture as Seller Assistant, powered by Amazon Bedrock and leveraging Amazon Nova and Anthropic Claude» (сниппет) | trajectory | https://www.aboutamazon.com/news/innovation-at-amazon/amazon-sellers-canvas-artificial-intelligence | About Amazon | unknown | accessed 2026-09-02 | low | no
7. Helium 10: Platinum «$129 $99 / month», Diamond «$359 $279 / month» (billed yearly), Enterprise «$1499 / month» | pricing | https://www.helium10.com/pricing/ | Helium 10 | unknown | accessed 2026-09-02 | high | no
8. Helium 10: агент «Helium» - «AI commerce agent», «Included in Diamond»; «Helium 10 MCP: Included free (up to 1,000 calls)» | pricing | https://www.helium10.com/pricing/ | Helium 10 | unknown | accessed 2026-09-02 | high | yes
9. Helium 10 таблица планов: «Alerts - Get Notified About Listing Changes», «Forecast & Manage Inventory», «Automate & Optimize Ads» | features | https://www.helium10.com/pricing/ | Helium 10 | unknown | accessed 2026-09-02 | high | no
10. Helium 10 Ads Suggestions: «click the checkmark to apply ... such as pausing or adjusting a bid», «click the "X" to defer», «revisit it the following week»; предложения появляются «within 7 to 10 days» после создания правил (сниппет, KB 403) | features | https://kb.helium10.com/hc/en-us/articles/12125578841883-Helium-10-Ads-Suggestions | Helium 10 KB | unknown | accessed 2026-09-02 | medium | yes
11. Helium 10 Ads Rules: Bid rules по критериям («clicks exceeding a specific number»), Keyword Harvest, Negative Targeting («clicks with no sales within a specific period») (сниппет, KB 403) | features | https://kb.helium10.com/hc/en-us/articles/18076439623963-Helium-10-Ads-Rules-Automation | Helium 10 KB | unknown | accessed 2026-09-02 | medium | no
12. Jungle Scout Catalyst годовой ряд: Starter «$29/mo x12 months | $348 annually», Growth Accelerator «$49/mo ... $588», Brand Owner + CI «$129/mo ... $1,548»; «Save up to 40% on annual plans!» | pricing | https://www.junglescout.com/pricing/catalyst-plans/ | Jungle Scout | unknown | accessed 2026-09-02 | high | no
13. Jungle Scout: Inventory Manager, Sales Analytics, Review Automation - в Growth Accelerator и Brand Owner, не в Starter; AI Assist: «Chat Only» / «100/month» / «500/month» | pricing | https://www.junglescout.com/pricing/catalyst-plans/ | Jungle Scout | unknown | accessed 2026-09-02 | high | no
14. Jungle Scout: доп. пользователь Catalyst «$49/month per seat (or $459/yr on an annual plan)»; Cobalt «Custom Plans» | pricing | https://www.junglescout.com/pricing/ | Jungle Scout | unknown | accessed 2026-09-02 | high | no
15. Sellerboard прогноз: «adjusted sales velocity ... average number of units sold per day ... adjusted by the 'weight' entered per period»; сезонность через «default coefficients or change them based on your experience»; «project a monthly growth rate in %» | features | https://blog.sellerboard.com/2023/05/18/how-to-increase-profitability-by-optimizing-inventory-management-a-comprehensive-guide/ | sellerboard blog | 2023-05-18 | accessed 2026-09-02 | medium | yes
16. Sellerboard: «You will be automatically notified whether it's time to restock the FBA warehouse or to place a new order with your supplier and how large this order should be» (сниппет) | features | https://blog.sellerboard.com/2020/10/19/inventory-management-with-sellerboard/ | sellerboard blog | 2020-10-19 | accessed 2026-09-02 | medium | no
17. SellerApp алерты: Price/Inventory/Listing Quality/Hijacker/Budget + негативные отзывы/Buy Box; email-канал; «Get instant alerts and emails», «24*7»; дайджеста и объяснений нет | features | https://www.sellerapp.com/amazon-product-alerts.html | SellerApp | unknown | accessed 2026-09-02 | high | yes
18. Perpetua: «Sellics joins forces with Perpetua»; «Launch goals, not campaigns»; «customizable, enterprise-level reporting ... at a single glance»; владелец не указан | positioning | https://perpetua.io/sellics-joins-perpetua/ | Perpetua | unknown | accessed 2026-09-02 | medium | no
19. Indellia Response Agent (Beta) «drafts replies for every new review ... presents a queue with pre-filled drafts that a human approves, edits, or skips»; «Amazon, Walmart, Bazaarvoice, and Trustpilot» (сниппет) | features | https://indellia.com/tools/ai-review-response-generator/ | Indellia | unknown | accessed 2026-09-02 | low | no
20. Aelestra: «AI draft responses for you to approve (Suggestive Mode), or ... full Auto-Pilot to post instantly based on your rules» (Google/Yelp, сниппет) | features | https://aelestra.com/ai-review | Aelestra | unknown | accessed 2026-09-02 | low | no

## Паттерны, повторяющиеся у лидеров

- **«Разрешение перед действием» как норма для агентов.** Amazon Seller Assistant - «with a seller's permission» / «If the seller approves» (claim 2); Helium 10 Ads - предложение по правилу, человек нажимает галочку или откладывает (claim 10); из раунда 2 - агент Helium без «write execution». Ни у кого не подтверждён полностью автономный режим для чувствительных операций.
- **Недельный ритм пересмотра предложений.** Helium 10 Ads: «revisit it the following week», новые предложения через 7-10 дней (claim 10). Дневной ритм - только у пороговых алертов (SellerApp «instant», claim 17), утреннего дайджеста нет ни у кого.
- **Прогноз запасов = скользящее среднее + ручные коэффициенты.** Sellerboard: взвешенная скорость продаж + сезонные коэффициенты + % роста (claim 15); Amazon - «comparing historical data with current trends» (claim 3); Helium 10 - строка «Forecast & Manage Inventory» без метода (claim 9). Методы ML не заявляет никто из проверенных.
- **AI-агент как аргумент верхнего плана.** Helium агент только в Diamond, MCP - бесплатная квота 1 000 вызовов (claim 8); Jungle Scout AI Assist лимитирован по запросам в месяц (claim 13); Amazon - бесплатно для селлеров (claim 1).
- **Traction-метрика «доля принятых рекомендаций».** Amazon публикует «over 90%» принятия (claim 4) - это единственный найденный публичный показатель качества рекомендаций; ни один сторонний тул такого не публикует.
- **Пороговые алерты без диагноза.** SellerApp - только триггеры и email (claim 17); Helium 10 Alerts - «Get Notified About Listing Changes» (claim 9). Цепочка «почему -> что делать» есть только у агентных продуктов (Amazon, Helium, DataHawk MCP из раунда 2).

## Лиды для следующего раунда

- Противоречие (приоритет): режимы «suggest only»/«auto-approve» у Amazon Seller Assistant (Nova Analytics) vs первичный текст только «with permission». Искать в Seller Central Help («Seller Assistant» settings), в записи Amazon Accelerate 2026 (сентябрь 2026 - должна выйти на днях) и в форуме sellercentral.amazon.com.
- Противоречие (приоритет): Helium 10 MCP - «Diamond+» (пресс-релиз) vs «Included free (up to 1,000 calls)» (страница цен). Открыть страницу продукта MCP на helium10.com и FAQ по лимитам.
- Независимое подтверждение «230,000 monthly users / >90% acceptance» (single publisher - Amazon): искать в Marketplace Pulse, Modern Retail, EcommerceBytes.
- Новая сущность: Amazon «canvas experience» для селлеров (Bedrock, Nova, Claude) - открыть страницу, понять, это ли новый UI Seller Assistant и есть ли там сводка.
- Дата публикации первичной статьи About Amazon о Seller Assistant - найти через Wayback или пресс-раздел; сейчас unknown.
- Helium 10 KB стабильно 403: пробовать Wayback (web.archive.org) для статей Rules & Automation / Suggestions / Alerts, чтобы закрыть OOS-логику и авто-применение.
- Sellerboard: открыть «Automated Reporting for Amazon Sellers» (2025-05-19) и «Using Sales and Stock Maps» (2025-05-05) - канал/расписание отчётов (область A) и горизонт прогноза (D).
- Jungle Scout помесячный ряд ($49/$79/$149) - переключатель monthly на странице catalyst-plans не считывается; проверить через help.junglescout.com или Wayback.
- Perpetua/IPG: искать пресс-релиз «Flywheel Digital Perpetua» на interpublic.com / businesswire.
- Область C: у Amazon Seller Assistant искать историю действий/«what changed» в Seller Central; у Perpetua - «Goals» с фактическим vs целевым ACOS.
- Область F: Indellia - открыть страницу продукта (цены, поддержка Amazon Q&A, лимиты), проверить, реальный ли это продукт или landing.
- DataHawk и Sellics-analytics не тронуты в раунде 3 - при необходимости прямой заход в help/changelog.

## Не нашёл

- Первичный анонс Amazon о запуске Seller Assistant в EU/UK и о режиме auto-approve - в двух первичных страницах Amazon только «coming months» и «with permission».
- Дата публикации статьи About Amazon о Seller Assistant (страница без даты).
- Полные тексты статей KB Helium 10 (Rules & Automation, Suggestions) - HTTP 403 второй раунд подряд; OOS-логика и авто-применение без одобрения не проверены.
- Строка «Alerts» в таблице планов Jungle Scout Catalyst - отсутствует на странице планов.
- Помесячный ряд цен Jungle Scout Catalyst на живой странице.
- Канал и расписание алертов Sellerboard; горизонт прогноза Sellerboard.
- Дневной дайджест / утренняя сводка с фиксированным временем - ни у одного продукта (SellerApp явно «instant», без дайджеста).
- Сравнение «ожидание vs факт» по решению (область C) - ни у Amazon, ни у Helium 10, ни у Perpetua в открытых текстах.
- Владелец Perpetua (IPG/Flywheel) - страница Sellics/Perpetua молчит.
- Независимое подтверждение traction-цифр Amazon Seller Assistant.
- Пресс-релиз Helium на GlobeNewswire - не запрашивался (бюджет).
