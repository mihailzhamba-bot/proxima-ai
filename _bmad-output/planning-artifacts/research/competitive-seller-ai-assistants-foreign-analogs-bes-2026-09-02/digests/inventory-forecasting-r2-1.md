# inventory-forecasting - round 2

Дата доступа ко всем источникам: 2026-09-02. Бюджет раунда: 15 вызовов инструментов (7 WebFetch/WebSearch в первой волне, 8 во второй), 12 источников. Приоритет раунда - противоречия (цены SoStocked и RestockPro), затем незакрытые вопросы (Prediko Pia guardrails, Amazon native, Sage Copilot, Jungle Scout, независимые отзывы, Scale Insights).

## Что искал и что нашёл (по продуктам)

### Prediko (Pia)

**(A) Дайджест/алерты.** Лента продуктовых обновлений вендора датирует запуск Pia и Slack-интеграции апрелем 2026: «PIA to help teams execute tasks and also show insights from your data directly inside Slack. Think of it as your AI co-worker» (Prediko, 2026-04, https://www.prediko.io/product-updates, доступ 2026-09-02). Там же в апреле 2026: «Users can now schedule Pia insights via email» и «New connections & notifications settings» (Prediko, 2026-04, https://www.prediko.io/product-updates, доступ 2026-09-02). В мае 2026 - «Release of PIA», «Improvement of Data Accuracy», «Slack, WhatsApp & Email Notifications live» (Prediko, 2026-05, https://www.prediko.io/product-updates, доступ 2026-09-02). Оговорка: даты на странице отрисовались как «April 26, 2026», «May 26, 2026», «June 26, 2026», «July 26, 2026» - одинаковый день «26» во всех записях наводит на мысль, что это помесячные метки, а не точные даты; трактую как «месяц 2026». Каналы, таким образом, подтверждены вторым источником (лента обновлений против продуктовой страницы Pia из раунда 1): Slack, WhatsApp, email, плюс расписание insights по email. Частота «ежедневно» нигде не заявлена - пользователь сам задаёт расписание.

**(B) Аномалия → диагноз → действие, guardrail.** Help-центр описывает статусную модель PO как явный human-approval workflow: «Draft - All new POs are dropped into the 'Draft' state», «Sent for Approval - Once PO is ready to be reviewed internally», «Approved - Once approved, the reviewer sets the 'Approved' state», далее «Ordered - Units are now confirmed both internally and with the Supplier», «Partially received», «Closed» (Prediko Help Center, дата обновления показана относительно - «Updated yesterday», https://help.prediko.io/en/articles/6842185-purchase-order-statuses, доступ 2026-09-02). Статья не указывает, кто вправе утверждать (роли), и не говорит, может ли Pia переводить PO дальше «Draft» - то есть guardrail для «creating and updating POs» из раунда 1 существует на уровне статусов, но связь Pia ↔ статусы вендором не документирована. Объяснение причин (why) в найденных источниках не описано.

**(C) Память решений.** Не найдено. Статусы PO - журнал исполнения заказа, а не журнал решений с ожидаемым/фактическим.

**(D) Прогноз.** Из ленты обновлений: «Link multiple suppliers to a single SKU» (2026-06), «Stock Takes» со сканированием штрихкодов и «discrepancy reports» (2026-07), «SKU Hover Card» в «3-tab planning system» (2026-03) (Prediko, 2026-03..2026-07, https://www.prediko.io/product-updates, доступ 2026-09-02). Метод, горизонт и overrides в этом раунде не уточнены (в раунде 1 - «обновление прогноза до 12 мес» через Pia).

**(E) Ads-guardrails.** Не найдено. **(F) Отзывы/вопросы.** Не найдено. **(G) Листинг-аудит.** Не найдено.

**Цены.** Страница https://www.prediko.io/pricing в раунд не читалась (бюджет). **Trajectory.** Релизы ежемесячно с марта по июль 2026 (лента обновлений выше) - самый живой сигнал в сегменте. **Голос клиентов.** Не читал.

### Inventory Planner (Sage)

**(A) Алерты.** Листинг в Shopify App Store перечисляет «Low stock alerts and replenishment reminders» без канала и расписания (Shopify App Store, страница приложения запущена 2013-01-15, https://apps.shopify.com/inventory-planner, доступ 2026-09-02).

**(B) Диагноз/действие.** Sage Copilot, по сниппету поиска на блог вендора, «available within Inventory Planner for Premium subscribers … highlights priority replenishments, flags overdue items with late deliveries, and identifies products missing cost prices» (Inventory Planner, дата unknown, https://www.inventory-planner.com/sage-copilot-for-inventory-planner-ai-powered-inventory-planning-for-retailers/, доступ 2026-09-02 - только сниппет, страница не прочитана; confidence medium). Т.е. Copilot - приоритизатор, а не объяснитель причин; про approval не сказано.

**(C) Память решений.** Не найдено. **(D) Прогноз.** Листинг: «Demand forecasting with precision», «Automated stock replenishment», «Multi-location inventory planning», «SKU-level profitability analysis» (Shopify App Store, https://apps.shopify.com/inventory-planner, доступ 2026-09-02). Горизонт и overrides - не уточнены сверх раунда 1.

**(E) Ads-guardrails.** Не найдено. **(F), (G).** Не найдено.

**Цены.** Shopify App Store: «Free to install; custom pricing based on business needs» (Shopify App Store, https://apps.shopify.com/inventory-planner, доступ 2026-09-02). Агрегатор в выдаче утверждает «Premium pricing is roughly $600 to $900/month and adds the Sage Copilot AI assistant» (checkthat.ai, дата unknown, https://checkthat.ai/brands/inventory-planner/pricing, доступ 2026-09-02 - сниппет агрегатора, confidence low; первичного прайса нет).

**Голос клиентов.** Shopify App Store: рейтинг 4.4/5 при 130 отзывах, 85% - 5 звёзд (110), 9% - 1 звезда (12) (Shopify App Store, https://apps.shopify.com/inventory-planner, доступ 2026-09-02). Негатив (2025-10-20, Morning Lavender, США, 4+ года): «Data is not syncing and we are not able to use it...paid for entire year ($4k)...customer service is slow». Позитив (2025-10-31, Supplement Hub Global): «Platform gives us clear visibility into what to reorder, when to reorder, and how much to buy»; (2025-12-04, Pulsio EU) - про онбординг менеджером. Жалобы - синхронизация данных и скорость поддержки при годовой предоплате; хвалят - ответ на «что/когда/сколько заказать».

### RestockPro (eComEngine)

**Цены - противоречие остаётся, но с направлением.** Живая страница https://www.restockpro.com/pricing/ отдаёт 301 на https://www.ecomengine.com/restockpro (доступ 2026-09-02) - т.е. отдельного прайса RestockPro больше нет, он слит в eComEngine (в раунде 1 там читалось «from $49/mo»). Capterra показывает «$49.99/month (Usage-based)» (Capterra, дата unknown, https://www.capterra.com/p/144970/RestockPro/, доступ 2026-09-02). Сниппет выдачи (источник в сниппете не атрибутирован, вероятно help-центр/агрегатор) даёт лестницу «Starter: $99.99 per month for up to 1,000 FBA orders; Pro: $139.99 … 2,500; Premium: $249.99 … 7,500; Ultimate: $399.99 … 20,000; Enterprise: $599.99 … 35,000 to 300,000 FBA orders», «21-day free trial», годовой план «twelve months of service at the cost of ten» (WebSearch snippet, дата unknown, https://www.ecomengine.com/pricing, доступ 2026-09-02, confidence low). Разрешение по правилу «свежесть + качество издателя»: живой прайс eComEngine «from $49» и Capterra «$49.99» согласуются между собой; лестница $99.99-$599.99 - старая структура (ITQlick датирует свой обзор Oct 2024). Верхние ступени текущего прайса остаются непрочитанными.

**(A)-(G).** Новых фактов не добавлено. **Голос клиентов.** Capterra: 4.0/5 при 4 отзывах, все 2016-2018 - старше 12-месячного порога свежести, сентиментом не считаю; для протокола: 2 звезды (2018-02-09) «RestockPro Does Not Scale and Has Lots of Bugs», минусы - «cannot search by UPC scanning», «help links broken (404 errors)»; 5 звёзд (2016-11-21) - «Excellent restock suggestions; … integrated profit/ROI calculations», минус «cannot assign multiple suppliers to kits» (Capterra, https://www.capterra.com/p/144970/RestockPro/, доступ 2026-09-02).

### SoStocked (Carbon6)

**Цены - противоречие не разрешено.** https://carbon6.io/pricing не показывает цену SoStocked - только «Intelligently manage inventory with advanced forecasting» и кнопку «Book a Call» (Carbon6, дата unknown, https://carbon6.io/pricing, доступ 2026-09-02). https://carbon6.io/sostocked/pricing - 404 (доступ 2026-09-02). Trustpilot: профиль sostocked.com без отзывов - «0 reviews», unclaimed (Trustpilot, https://www.trustpilot.com/review/sostocked.com, доступ 2026-09-02). Итог: единственный прямой ценник ($474/3 мес) остаётся односторонним; публичного прайса у Carbon6 для SoStocked сейчас нет - продажа через звонок. **(A)-(G).** Новых фактов нет. **Голос клиентов.** Не найден ни один отзывный источник (Trustpilot пуст, G2 блокирует).

### Amazon native (Minimum Inventory Level / Restock recommendations)

**(A) Дайджест/алерты.** Официальный пост Amazon на Seller Forums: «We've launched a new Minimum Inventory Level metric to help FBA sellers plan inventory levels more effectively, improve delivery speeds, and help them to avoid the recently announced low-inventory-level fee»; метрика на «FBA Inventory page» в Seller Central; обещание «specific recommended ship-by dates and replenishment quantities for your next incoming shipments» и «We're working to bring restock recommendations to the FBA Inventory page … in the coming weeks» (Amazon Seller Forums, ~2024-01/02 - страница показывает «3 years ago», согласуется с датой вступления сбора 2024-04-01, https://sellercentral.amazon.com/seller-forums/discussions/t/1aa7614a-5542-4529-abe1-ddf452681630, доступ 2026-09-02). Канал - страница в Seller Central, не push/дайджест.

**(B) Диагноз/действие.** Рекомендация = количество + ship-by дата; объяснения причин нет; guardrail не нужен - продавец сам создаёт отправку. Экономический стимул: «Effective April 1, 2024, the fee applies when both 90-day and 30-day historical days of supply fall below 28 days» (там же).

**(C) Память решений.** Нет. **(D) Прогноз.** По сниппету выдачи, метрика «uses machine learning to recommend the minimum number of units per product» и «analyzes demand forecasts and replenishment settings» (WebSearch snippet, источник неатрибутирован, confidence low). Цифра «sellers who maintain units above the Minimum Inventory Level see a 15% increase in sales over a four-week period on average» - в сниппете без первоисточника; помечаю как unsourced. Overrides: в посте не описаны; продавцы жалуются, что метрика «does NOT account for sellers intentionally selling out» и сезонность (там же).

**(E)-(G).** Не рассматривались (вне инвентарного инструмента). **Голос клиентов** (Seller Forums, тот же тред, ~2024): «entirely broken» - рекомендации совпадают с текущим остатком; у товара с нулевыми продажами за 90 дней minimum level = 3; «Fees ranging $0.32-$0.89 per unit deemed 'unsustainable' for seasonal sellers»; алгоритм «ignores inventory in transit». Сентимент старше 12 мес - контекст, не свежий сигнал.

### Scale Insights (новая сущность, область E)

**(E) Ads-guardrails.** Позиционирование: «Scale and automate Amazon PPC with absurd control», «Advanced solution engineered by 5 Amazon FBA sellers with $200M+ revenue»; «11 algorithms with 200+ parameters»; типы правил - «Bidding rule», «Status rule: Pauses or enable ads based on their performance», «Negative rule», «Dayparting rule», «Daily budget: Adjust campaign budget based on performance and day of the week», «Import rule», «Placement rule» (Scale Insights, © 2026, https://scaleinsights.com/, доступ 2026-09-02). OOS-aware правил на главной странице нет. Guardrail-паттерн - прозрачность: «Unthinkable transparency across each step», возможность «preview changes and review calculations» перед применением (там же). **(A)** Ежедневных отчётов/каналов на главной не описано. **Цены.** «$78/month (5 automated ASINs)» до «$688/month (100 ASINs)» или «1% of ad spend» без лимита ASIN, годовая оплата -20% (там же). **(B)-(D), (F), (G).** Не найдено - это чистый PPC-инструмент, прогнозирование спроса не заявлено (лид раунда 1 «forecasting» не подтвердился).

### Jungle Scout (наследник Forecastly)

URL https://www.junglescout.com/features/inventory-manager/ отдал лендинг «Jungle Scout Catalyst» без единого упоминания прогноза, реордера, алертов; на странице «critical metrics like ROI and net margin», «sales trends across custom date ranges», фокус на product discovery, keyword research, review automation (Jungle Scout, дата unknown, https://www.junglescout.com/features/inventory-manager/, доступ 2026-09-02). Вывод: отдельной страницы Inventory Manager по старому адресу больше нет; статус функции неизвестен.

### Flieber, Cogsy, Inventory Hero, Forecastly

В этом раунде не читались (бюджет ушёл на противоречия и Prediko/Amazon/Sage). Лиды по ним перенесены ниже.

## Claims (нумерованный список)

1. Prediko запустил Pia и Slack-интеграцию: «PIA to help teams execute tasks and also show insights from your data directly inside Slack» | trajectory | https://www.prediko.io/product-updates | Prediko | 2026-04 | accessed 2026-09-02 | high | yes
2. Prediko: «Users can now schedule Pia insights via email», «New connections & notifications settings» | features | https://www.prediko.io/product-updates | Prediko | 2026-04 | accessed 2026-09-02 | high | no
3. Prediko: «Slack, WhatsApp & Email Notifications live», «Release of PIA», «Improvement of Data Accuracy» | features | https://www.prediko.io/product-updates | Prediko | 2026-05 | accessed 2026-09-02 | high | yes
4. Prediko: ежемесячные релизы март-июль 2026 (SKU Hover Card, multi-supplier per SKU, Stock Takes, barcode labels, FIFO COGS «Last Week») | trajectory | https://www.prediko.io/product-updates | Prediko | 2026-07 | accessed 2026-09-02 | high | no
5. Prediko PO-статусы: «Draft» → «Sent for Approval» → «Approved» («the reviewer sets the 'Approved' state») → «Ordered» → «Partially received» → «Closed»; роли и участие Pia не описаны | features | https://help.prediko.io/en/articles/6842185-purchase-order-statuses | Prediko Help Center | unknown | accessed 2026-09-02 | high | yes
6. Amazon: «We've launched a new Minimum Inventory Level metric … to avoid the recently announced low-inventory-level fee»; рекомендации «ship-by dates and replenishment quantities» на FBA Inventory page | features | https://sellercentral.amazon.com/seller-forums/discussions/t/1aa7614a-5542-4529-abe1-ddf452681630 | Amazon Seller Forums | 2024-01 (approx, «3 years ago») | accessed 2026-09-02 | high | yes
7. Amazon low-inventory-level fee: с 2024-04-01, когда 90-дневный и 30-дневный days of supply оба ниже 28 дней | features | https://sellercentral.amazon.com/seller-forums/discussions/t/1aa7614a-5542-4529-abe1-ddf452681630 | Amazon Seller Forums | 2024-01 (approx) | accessed 2026-09-02 | high | no
8. Продавцы о Minimum Inventory Level: «does NOT account for sellers intentionally selling out», «entirely broken», игнорирует inventory in transit и сезонность | sentiment | https://sellercentral.amazon.com/seller-forums/discussions/t/1aa7614a-5542-4529-abe1-ddf452681630 | Amazon Seller Forums | 2024 (approx) | accessed 2026-09-02 | medium | no
9. «sellers who maintain units above the Minimum Inventory Level see a 15% increase in sales over a four-week period» - число без первоисточника в сниппете | traction | (search snippet, source unattributed) | unknown | unknown | accessed 2026-09-02 | low | no
10. Sage Copilot в Inventory Planner «for Premium subscribers … highlights priority replenishments, flags overdue items with late deliveries, and identifies products missing cost prices» | features | https://www.inventory-planner.com/sage-copilot-for-inventory-planner-ai-powered-inventory-planning-for-retailers/ | Inventory Planner (Sage) | unknown | accessed 2026-09-02 | medium | yes
11. Inventory Planner в Shopify App Store: 4.4/5, 130 отзывов, 85% пятизвёздочных, 9% однозвёздочных; «Free to install; custom pricing» | sentiment | https://apps.shopify.com/inventory-planner | Shopify App Store | 2025-12 (latest review) | accessed 2026-09-02 | high | yes
12. Inventory Planner, отзыв 1★ 2025-10-20: «Data is not syncing and we are not able to use it...paid for entire year ($4k)...customer service is slow» | sentiment | https://apps.shopify.com/inventory-planner | Shopify App Store | 2025-10-20 | accessed 2026-09-02 | high | no
13. Inventory Planner, отзыв 5★ 2025-10-31: «clear visibility into what to reorder, when to reorder, and how much to buy» | sentiment | https://apps.shopify.com/inventory-planner | Shopify App Store | 2025-10-31 | accessed 2026-09-02 | high | no
14. Inventory Planner Premium «roughly $600 to $900/month and adds the Sage Copilot AI assistant» - агрегатор, не первичный прайс | pricing | https://checkthat.ai/brands/inventory-planner/pricing | checkthat.ai | unknown | accessed 2026-09-02 | low | no
15. RestockPro: https://www.restockpro.com/pricing/ → 301 на https://www.ecomengine.com/restockpro (отдельного прайса нет) | pricing | https://www.restockpro.com/pricing/ | eComEngine | unknown | accessed 2026-09-02 | high | no
16. RestockPro на Capterra: «$49.99/month (Usage-based)», 4.0/5 при 4 отзывах (2016-2018) | pricing | https://www.capterra.com/p/144970/RestockPro/ | Capterra | unknown | accessed 2026-09-02 | medium | no
17. RestockPro лестница «Starter $99.99 … Enterprise $599.99», «21-day free trial», годовой = 10 месяцев - сниппет выдачи, вероятно устаревшая структура | pricing | https://www.ecomengine.com/pricing | (search snippet) | unknown | accessed 2026-09-02 | low | no
18. Carbon6 /pricing не публикует цену SoStocked - только «Book a Call»; /sostocked/pricing - 404 | pricing | https://carbon6.io/pricing | Carbon6 | unknown | accessed 2026-09-02 | high | no
19. SoStocked на Trustpilot: 0 отзывов, профиль unclaimed | sentiment | https://www.trustpilot.com/review/sostocked.com | Trustpilot | unknown | accessed 2026-09-02 | high | no
20. Scale Insights: PPC-автоматизация, «11 algorithms with 200+ parameters», правила Bidding/Status/Negative/Dayparting/Daily budget/Import/Placement; OOS-aware правил на главной нет | features | https://scaleinsights.com/ | Scale Insights | 2026 (© year) | accessed 2026-09-02 | high | yes
21. Scale Insights guardrail: «Unthinkable transparency across each step», «preview changes and review calculations» | features | https://scaleinsights.com/ | Scale Insights | 2026 | accessed 2026-09-02 | medium | no
22. Scale Insights цены: «$78/month (5 automated ASINs)» - «$688/month (100 ASINs)» или «1% of ad spend», годовая -20% | pricing | https://scaleinsights.com/ | Scale Insights | 2026 | accessed 2026-09-02 | high | no
23. Jungle Scout: адрес /features/inventory-manager/ отдаёт лендинг Catalyst без упоминания прогноза/реордера/алертов | positioning | https://www.junglescout.com/features/inventory-manager/ | Jungle Scout | unknown | accessed 2026-09-02 | medium | no

## Паттерны, повторяющиеся у лидеров

- **Алерт приходит туда, где работает команда (Slack/email/WhatsApp), а частоту выбирает пользователь.** Prediko: Slack + WhatsApp + email, «schedule Pia insights via email» (claims 1-3). Inventory Planner: «Low stock alerts and replenishment reminders» без канала (claim 11). Amazon: только страница в Seller Central (claim 6). Ни у кого - фиксированный «утренний» дайджест.
- **Рекомендация = количество + дата, без объяснения причины.** Amazon «ship-by dates and replenishment quantities» (claim 6); Inventory Planner - «what to reorder, when to reorder, and how much to buy» (claim 13); Sage Copilot - приоритизация (priority replenishments, late POs, missing costs), не диагноз (claim 10).
- **Human approval как статус документа, а не как свойство ИИ.** Prediko: Draft → Sent for Approval → Approved (claim 5); Scale Insights: preview changes перед применением (claim 21). Guardrail живёт в workflow PO / правил, а не в агенте.
- **Экономический триггер вместо прогноза как мотивация.** Amazon строит метрику вокруг штрафа (low-inventory-level fee, claim 7) - и получает жалобы, что метрика не учитывает намеренный sell-out и сезонность (claim 8).
- **Ценообразование: «свяжитесь с нами» у корпоративных, лестница по объёму у SMB.** Inventory Planner custom (claim 11), SoStocked через звонок (claim 18), Scale Insights по ASIN/доле бюджета (claim 22), RestockPro usage-based (claim 16).
- **Ads и inventory по-прежнему в разных продуктах.** Scale Insights не знает про OOS (claim 20); инвентарные инструменты не трогают рекламу - разрыв области E подтверждён вторым раундом.

## Лиды для следующего раунда

Противоречия (приоритет):
1. SoStocked: прайса на carbon6.io нет (claim 18); единственный ценник $474/3 мес (раунд 1) остаётся односторонним. Искать: Amazon Seller Central Appstore listing SoStocked, Capterra/Software Advice, архив sostocked.com/pricing (Wayback).
2. RestockPro: «from $49» (eComEngine live, раунд 1) + Capterra $49.99 vs лестница $99.99-$599.99 (сниппет). Прочитать https://www.ecomengine.com/restockpro и help-статью eComEngine о планах RestockPro целиком, зафиксировать верхние ступени.
3. Даты в ленте Prediko (все «26-е число») - проверить в исходном HTML/RSS, помесячные это метки или точные даты.
4. Sage Copilot: прочитать первичную страницу вендора (claim 10 - пока сниппет) и Sage KB https://gb-kb.sage.com/portal/app/portlets/results/view2.jsp?k2dockey=241107162041297 - есть ли чат по данным и объяснения.

Новые сущности:
5. Stockful (stockful.app) - позиционируется как «Prediko Alternative … Flat Pricing»; проверить алерты/прогноз.
6. Eightx (eightx.co) и checkthat.ai - агрегаторы TCO Inventory Planner; использовать только как указатели на первичные цены.

Незакрытые вопросы:
7. Может ли Pia переводить PO из Draft в Sent for Approval/Ordered сама - искать help-статьи Prediko про Pia («How to create a Purchase Order» https://help.prediko.io/en/articles/9557310-how-to-create-a-purchase-order).
8. Amazon: актуальная (2026) help-страница «Restock recommendations»/«FBA Restock Tool» - PDF-гайд https://m.media-amazon.com/images/G/01/sell/pdf/FBA-Restock-Guide-EN.pdf; есть ли overrides (замена прогноза продавцом).
9. Jungle Scout: жив ли Inventory Manager под новым URL / внутри Catalyst.
10. Flieber, Cogsy (сделка с Mayple), Inventory Hero (независимый источник), Forecastly - не тронуты в раунде 2, лиды раунда 1 остаются в силе.
11. Свежие (≤12 мес) отзывы 1-3★ для SoStocked, Flieber, Cogsy: Reddit r/FulfillmentByAmazon, Amazon Appstore.

## Не нашёл

- (C) Память решений и сверка ожидаемое vs фактическое - по-прежнему ни у одного продукта; статусы PO у Prediko - ближайший аналог, но это журнал исполнения, не решений.
- (E) OOS-aware ads-правила - у Scale Insights на главной странице нет; у инвентарных инструментов не найдено.
- Публичный прайс SoStocked у Carbon6 - отсутствует (страница 404 / «Book a Call»).
- Верхние ступени актуального прайса RestockPro и Prediko; любые первичные цены Inventory Planner (только «custom»).
- Горизонт прогноза и overrides у Inventory Planner, SoStocked, RestockPro - не уточнены.
- Ежедневный фиксированный дайджест (утро, канал) - ни у одного продукта; у Prediko расписание задаёт пользователь.
- Объяснение причины (why) в рекомендации - ни у Amazon, ни у Sage Copilot, ни у Prediko не задокументировано.
- Свежие отзывы (≤12 мес) на SoStocked (Trustpilot пуст, G2 недоступен) и RestockPro (Capterra - 2016-2018).
- Страница Jungle Scout Inventory Manager - по старому URL отдаёт Catalyst без инвентарных функций.
- Первоисточник цифры «15% increase in sales» для Amazon Minimum Inventory Level.
