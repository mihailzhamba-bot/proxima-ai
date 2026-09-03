# ads-retail-media - round 2

Дата доступа ко всем источникам: 2026-09-02. Бюджет раунда: 15 вызовов инструментов, 9 страниц прочитано (WebFetch), 6 поисковых выдач. Приоритет раунда - лиды и противоречия из раунда 1: Amazon Ads Agent (первичный источник), m19 pricing, Pacvue inventory rules / «100+ retailers», Skai Ticketing Automation и Revenue Recovery, Perpetua low stock, Teikametrics Inventory, отзывы Quartile, Adbrew как challenger.

## Что искал и что нашёл (по продуктам)

### Amazon Ads - Ads Agent (первичный источник вместо SellerApp)

**A (дайджест/алерты).** На странице анонса нет ни слова об алертах, ежедневных отчётах и каналах доставки - только «data-driven recommendations» внутри консоли (Amazon Ads, 2025-11-11, https://advertising.amazon.com/resources/whats-new/unboxed-2025-introducing-ads-agent, доступ 2026-09-02).

**B (аномалия → диагноз → действие, approval).** Ads Agent «reviews thousands of audience segments to recommend the most relevant Amazon audience segments», умеет «adjusting pacing across hundreds of campaigns», а при загрузке медиаплана создаёт структуру кампаний, но «Campaigns only launch after you review and approve» (Amazon Ads, 2025-11-11, https://advertising.amazon.com/resources/whats-new/unboxed-2025-introducing-ads-agent, доступ 2026-09-02). Это подтверждает раунд-1 тезис SellerApp «Nothing goes live without your approval» вторым, первичным издателем.

**C (память решений).** Не упоминается.

**D (прогноз спроса).** Не упоминается.

**E (guardrails рекламы).** Доступ: «All users with access to Amazon Marketing Cloud (AMC) and U.S. users of Multimedia Solutions with Amazon DSP» - то есть Sponsored-Products-only селлеры на момент анонса не в периметре (Amazon Ads, 2025-11-11, https://advertising.amazon.com/resources/whats-new/unboxed-2025-introducing-ads-agent, доступ 2026-09-02). Явных guardrails (min/max bid, бюджетные пороги) в анонсе нет. Статус «beta» на самой странице анонса не назван, но в заголовке смежной страницы «Accelerate Amazon Marketing Cloud workflows with Ads Agent (beta)» слово «beta» присутствует (Amazon Ads, дата не считана, https://advertising.amazon.com/resources/whats-new/unboxed-2025-ads-agent-in-amazon-marketing-cloud, доступ 2026-09-02, только заголовок из поисковой выдачи). Противоречие раунда 1 «beta в течение 2026» (SellerApp) частично снято: beta относится к AMC-контуру, формулировка «в течение 2026» первичным источником не подтверждена.

**F, G.** Не относится к Ads Agent; в той же выдаче Amazon анонсировал «Creative Agent» (контент/креативы) и «Campaign Manager beta» - не читал (Amazon Ads, заголовки из выдачи, https://advertising.amazon.com/resources/whats-new/unboxed-2025-creative-agent, https://advertising.amazon.com/resources/whats-new/unboxed-2025-campaign-manager, доступ 2026-09-02).

**Цены.** Нативная функция консоли, отдельной цены нет (в анонсе не упоминается).

**Позиционирование vs продукт.** Маркетинг: агент «simplifies how advertisers plan, launch, and optimize campaigns»; фактически - помощник внутри DSP/AMC с обязательным ручным approve на запуск, без описанных SP-возможностей для селлеров.

### m19 (лид: противоречие «$59/mo» vs «free до 10,000 EUR»)

**Цены и упаковка.** Противоречие снято живой страницей: тариф Autopilot - «€49/month» / «$59/month» фиксированно, excl. VAT, для «Sellers, Vendors under 5K€ of adspend / month»; m19 Professional - «€400 + 3% of total ad spend/month» / «$479 + 3% of total ad spend/month» для «above 5K€ of adspend / month»; Agencies & Enterprise - «Cut to fit»; оба платных тарифа - «30-day free trial», «No credit card required»; бесплатного тарифа «до 10,000 EUR» на странице нет (m19, дата публикации не указана, https://www.m19.com/pricing-automated-ppc-campaigns, доступ 2026-09-02).

**E (guardrails).** В блоке функций тарифов перечислены «Target daily spend», «Target monthly spend», «TACOS Targeting», «Inventory Threshold», «Peak season Boost option»; Autopilot - «100% Automated setup (SP only)», Professional - «Advanced Strategies (SP, SB, SD, DSP)» (m19, дата не указана, https://www.m19.com/pricing-automated-ppc-campaigns, доступ 2026-09-02). То есть OOS-aware поведение (Inventory Threshold) заявлено как штатный guardrail даже в самом дешёвом тарифе; механика порога (bid-down или pause) на странице цен не раскрыта.

**A, B, C, D, F, G.** На странице цен не описаны; отдельная документация m19 в этом раунде не читалась.

### Pacvue (лиды: inventory rules, approval-очередь Agent, «100+» vs «90+»)

**Противоречие «100+ retailers» vs «90+ marketplace integrations».** Страница платформы заявляет «100+ retailers» и «30+ global markets» (Pacvue, страница датируется ссылками на «Q1 2026» и «H2 2026», https://pacvue.com/platform/, доступ 2026-09-02). Цифра «90+» у atom11 - вторичный источник; принимаю «100+» как актуальную по свежести и первичности.

**E (inventory rules, механика).** По сводке поисковой выдачи из блога Pacvue: Rule Library позволяет создавать правила по уровню запасов; «Inventory rules can automatically pause products that have low inventory or based on "weeks of inventory on hand"», а также «bidding rules to lower bids on keywords advertising products that have low inventory»; правила DSP работают по логике «if-this-then-that»; можно «create e-mail alerts on items that have low inventory» (Pacvue, дата статьи не считана, https://pacvue.com/blog/using-pacvue-during-q4-inventory-challenges/ и https://pacvue.com/blog/weeks-of-cover-preventing-out-of-stock-inventory-lost-sales-and-seo-ranking/, доступ 2026-09-02, сводка выдачи - средняя уверенность). Страница платформы формулирует это как «When inventory drops, purchase position shifts, or margin thresholds are breached, Pacvue automatically pauses or reallocates spend» (по сводке выдачи, Pacvue, https://pacvue.com/platform/unified-commerce-execution-operation/, доступ 2026-09-02, средняя уверенность).

**B/C (approval и audit trail).** На странице платформы: «Turn signals into action with Pacvue Agent, automating bids, budgets, and pacing», «goal-aware intelligence from Pacvue Agent», упоминания «governed workflows», но явного описания approval-очереди, audit trail или сравнения ожидаемого и фактического эффекта на странице нет (Pacvue, 2026, https://pacvue.com/platform/, доступ 2026-09-02). Раунд-1 тезис о «full record of what changed and why» остаётся подтверждённым только главной страницей Pacvue - вторым издателем не подтверждён.

**A.** На странице платформы каналы алертов (email/Slack/дайджест) не названы; e-mail-алерты по низким остаткам - только в сводке выдачи из блога (см. E).

**D.** Прогнозирование на странице платформы явно не заявлено; измерение - «incrementality and business outcomes» (Pacvue, 2026, https://pacvue.com/platform/, доступ 2026-09-02).

**F, G.** Не описаны на прочитанной странице.

**Проверка вторым издателем.** Попытка прочитать статью Amazon Ads «How vendors manage inventory and advertising spend with Pacvue» (https://advertising.amazon.com/en-gb/blog/sellers-manage-inventory-and-advertising-spend-with-pacvue) - URL отдал общую библиотеку ресурсов без содержимого статьи; второй издатель по inventory rules не получен.

### Perpetua (лид: поведение при low stock / OOS, goals + guardrails)

**B/E (approval-gated OOS-цепочка).** Help-статья «SP Inventory Recommendations»: пользователь задаёт порог остатков и тип запасов «FBA, FBM, or both via the dropdown»; «Once the inventory goes below this threshold for any of the products in any of the selected goals, Perpetua will send a recommendation to pause the ads» для этого продукта, а при возврате запасов выше порога - рекомендацию включить; создание стратегии не меняет кампании автоматически - каждую рекомендацию нужно просмотреть и принять или отклонить, авто-пауза без approval не выполняется (Perpetua, «Article last updated October 2024», https://help.perpetua.io/en/articles/7120742-sp-inventory-recommendations, доступ 2026-09-02). Это первый в сегменте задокументированный пример «рекомендация → человек утверждает → действие» именно для OOS.

**A (задержка данных, канал).** «It may take up to 24 hours for inventory data to sync from Amazon»; рекомендации отправляются «to the account where the strategy was created» - канал (email/in-app) в статье не уточнён (Perpetua, 2024-10, https://help.perpetua.io/en/articles/7120742-sp-inventory-recommendations, доступ 2026-09-02). По сводке выдачи, Perpetua также имеет «real-time Inventory Notifications» и авто-остановку показа: «If your products are out of stock or no longer the "Featured Offer," the ads will automatically stop serving» (Perpetua help/blog, дата не считана, https://help.perpetua.io/en/articles/5385958-how-to-pause-an-asin и https://perpetua.io/blog-avoid-wasted-ad-spend-why-you-need-to-be-retail-aware/, доступ 2026-09-02, средняя уверенность).

**C, D, F, G.** В прочитанной статье нет; min/max bid guardrails у goals в этом раунде не проверены (бюджет).

### Skai (лиды: Ticketing Automation, Revenue Recovery, дата пресс-релиза)

**Trajectory.** Пресс-релиз от 14 мая 2025: Skai запустила Celeste AI и расширила платформу пакетом Commerce Insights and Operations: «Strategic Digital Shelf», «Retail Insights», «Content Optimization», «Retail Operations», «Revenue Recovery»; Celeste вышла в closed beta с «over 50 clients»; ранние пользователи заявили «30-50% efficiency gains and 10-20% performance improvements»; Skai обслуживает «over 8,000 brands and agencies» (Skai, 2025-05-14, https://skai.io/press-releases/skai-launches-celeste-ai-and-expands-platform-with-commerce-insights-and-operations-solutions/, доступ 2026-09-02). Цифры self-reported, маркетинговый регистр - средняя уверенность; «8,000 brands» вторым издателем не подтверждено. Формулировка «agent-native operating system» присутствует только как навигационная ссылка на другой релиз - дата не получена.

**B (объяснение «почему»).** Celeste даёт «budget recommendations and bidding strategy insights to cross-channel performance comparisons and anomaly detection» и помогает понять «both the 'what' and the 'why' behind performance shifts, offering actionable recommendations»; approval и guardrails в релизе не упоминаются (Skai, 2025-05-14, тот же URL, доступ 2026-09-02).

**G (Ticketing Automation).** Страница продукта: «Reinstate suppressed SKUs, fix variations, and update PDPs automatically»; ошибки по цене, контенту и доступности; исполнение через «browser automation and API-driven workflows»; плановые исправления с повторением daily/weekly/monthly; метрики «~80% of issues resolved in under 2 days», «71% cost savings per ticket», «70% cut to manual catalog checks and 5x faster»; маршрутизация тикетов, approval и каналы алертов на странице не описаны (Skai, дата не указана, © 2026, https://skai.io/ticketing-automation/, доступ 2026-09-02). Таким образом Ticketing Automation - это контент/каталог-операции (область G), а не OOS-bidding.

**Revenue Recovery.** По сводке выдачи: возврат chargebacks/deductions/invoice errors, «powered by Carbon6»; в пресс-релизе Carbon6 не упомянут (Skai, https://skai.io/revenue-recovery/, не читал, доступ 2026-09-02, низкая уверенность). Это финансовые операции, не области A-G.

**A, C, D, F.** Не описаны на прочитанных страницах.

### Teikametrics (лид: метод и горизонт прогноза Inventory)

**D.** Страница «AI Inventory Optimization Platform» ограничивается «Forecast demand precisely and sync advertising with real-time inventory signals»; метод, горизонт, overrides, сезонность не названы (Teikametrics, дата не указана, футер © 2025/2026, https://www.teikametrics.com/inventory-optimization/, доступ 2026-09-02). По сводке выдачи, Teikametrics «analyzes historical sales data along with seasonal trends and market demand» и позволяет настроить «personalized email notifications for rate of sale changes, stockouts, and reorder timelines» (Teikametrics, https://help.teikametrics.com/en/, сводка выдачи, доступ 2026-09-02, средняя уверенность).

**A.** Help-статья «Unsold Inventory in L90 Days / Excess Stock» описывает dashboard и email-алерты по товарам без продаж 90 дней (Teikametrics help, дата не считана, https://help.teikametrics.com/en/articles/8618450-inventory-unsold-inventory-in-l90-days-excess-stock, сводка выдачи, доступ 2026-09-02, средняя уверенность).

**E (inventory-aware ads).** Механика bid-down/pause при низких остатках на странице не раскрыта - лишь «sync advertising with real-time inventory signals» (тот же URL).

**B, C, F, G.** Не описаны на прочитанной странице.

### Adbrew (новая сущность, challenger)

**E.** Главная страница: «Automation with control: Use AI or custom rule based PPC automation to automate bids, budget, placement, and targets»; поддержка Amazon Sponsored Ads, DSP, AMC и Walmart Sponsored Ads; «AI-driven Insights: Get precise, AI-driven, actionable insights for your ad campaigns»; заявление «Trusted by 5000+ Brands, Agencies and Aggregators across the globe»; «12 nominations & 3 wins» в Amazon Ads Partner Awards (Adbrew, дата не указана, https://www.adbrew.io/, доступ 2026-09-02). OOS-aware поведение, каналы алертов, approval-flow и цены на главной странице отсутствуют - для лида «OOS-aware bidding» Adbrew пока не подтверждён.

**A, B, C, D, F, G.** Не описаны на главной странице.

### Quartile (лид: независимые отзывы)

**Голос клиентов.** По сводке выдачи Trustpilot: рейтинг 4 звезды при ~535 отзывах; хвалят аккаунт-менеджеров, onboarding, рост ROAS/ACOS; жалобы - «poor communication through email», аккаунт-менеджеры «not showing up on scheduled days», плохо обученный персонал, «poor campaign outcomes and difficulty cancelling»; Trustpilot пометил, что Quartile «may be collecting reviews in ways that don't fully align with Trustpilot's guidelines» (Trustpilot, дата не считана, https://www.trustpilot.com/review/quartile.com, сводка выдачи, доступ 2026-09-02, низкая уверенность - страница не прочитана). Важно: отзывы описывают Quartile как managed service с людьми, а не self-serve SaaS.

### Не покрыты в этом раунде
Helium 10 Ads, Optmyzr, atom11, Indition SellerTools, Jinnify, Xneeti - бюджет исчерпан на приоритетных лидах.

## Claims (нумерованный список)

1. m19 Autopilot - «€49/month» / «$59/month» фиксировано, excl. VAT, для «under $5K of adspend / month»; бесплатного тарифа «до 10,000 EUR» на странице нет | pricing | https://www.m19.com/pricing-automated-ppc-campaigns | m19 | unknown | accessed 2026-09-02 | high | no
2. m19 Professional - «€400 + 3% of total ad spend/month» / «$479 + 3% of total ad spend/month» для «above $5K of adspend / month»; «30-day free trial», «No credit card required» | pricing | https://www.m19.com/pricing-automated-ppc-campaigns | m19 | unknown | accessed 2026-09-02 | high | no
3. m19 в тарифах заявляет guardrails «Target daily spend», «Target monthly spend», «TACOS Targeting», «Inventory Threshold», «Peak season Boost option» | features | https://www.m19.com/pricing-automated-ppc-campaigns | m19 | unknown | accessed 2026-09-02 | high | yes
4. m19 Autopilot - «100% Automated setup (SP only)», Professional - «Advanced Strategies (SP, SB, SD, DSP)», «Unlimited Accounts & Marketplaces» | features | https://www.m19.com/pricing-automated-ppc-campaigns | m19 | unknown | accessed 2026-09-02 | high | no
5. Amazon Ads Agent анонсирован 11.11.2025; доступ «All users with access to Amazon Marketing Cloud (AMC) and U.S. users of Multimedia Solutions with Amazon DSP» | features | https://advertising.amazon.com/resources/whats-new/unboxed-2025-introducing-ads-agent | Amazon Ads | 2025-11-11 | accessed 2026-09-02 | high | no
6. Amazon Ads Agent: «Campaigns only launch after you review and approve»; умеет «adjusting pacing across hundreds of campaigns», «recommend the most relevant Amazon audience segments», генерировать SQL для AMC | features | https://advertising.amazon.com/resources/whats-new/unboxed-2025-introducing-ads-agent | Amazon Ads | 2025-11-11 | accessed 2026-09-02 | high | yes
7. Заголовок страницы Amazon Ads для AMC называет Ads Agent «(beta)» | trajectory | https://advertising.amazon.com/resources/whats-new/unboxed-2025-ads-agent-in-amazon-marketing-cloud | Amazon Ads | unknown | accessed 2026-09-02 | medium | no
8. Perpetua SP Inventory Recommendations: порог остатков по «FBA, FBM, or both»; при падении ниже порога «Perpetua will send a recommendation to pause the ads», при восстановлении - рекомендацию включить; рекомендации требуют ручного accept/dismiss, авто-пауза не выполняется | features | https://help.perpetua.io/en/articles/7120742-sp-inventory-recommendations | Perpetua | 2024-10 | accessed 2026-09-02 | high | yes
9. Perpetua: «It may take up to 24 hours for inventory data to sync from Amazon»; канал доставки рекомендаций в статье не указан | features | https://help.perpetua.io/en/articles/7120742-sp-inventory-recommendations | Perpetua | 2024-10 | accessed 2026-09-02 | high | no
10. Perpetua: «If your products are out of stock or no longer the "Featured Offer," the ads will automatically stop serving» (сводка выдачи) | features | https://help.perpetua.io/en/articles/5385958-how-to-pause-an-asin | Perpetua | unknown | accessed 2026-09-02 | medium | no
11. Pacvue platform: «100+ retailers», «30+ global markets» | traction | https://pacvue.com/platform/ | Pacvue | 2026 | accessed 2026-09-02 | high | no
12. Pacvue platform: «Turn signals into action with Pacvue Agent, automating bids, budgets, and pacing», «governed workflows»; audit trail / expected-vs-actual на странице не описаны | features | https://pacvue.com/platform/ | Pacvue | 2026 | accessed 2026-09-02 | medium | no
13. Pacvue Rule Library: «Inventory rules can automatically pause products that have low inventory or based on "weeks of inventory on hand"», «bidding rules to lower bids on keywords advertising products that have low inventory», «e-mail alerts on items that have low inventory» (сводка выдачи блога Pacvue) | features | https://pacvue.com/blog/using-pacvue-during-q4-inventory-challenges/ | Pacvue | unknown | accessed 2026-09-02 | medium | yes
14. Skai Celeste AI (пресс-релиз 14.05.2025): «budget recommendations and bidding strategy insights to cross-channel performance comparisons and anomaly detection», объясняет «both the 'what' and the 'why' behind performance shifts»; closed beta «over 50 clients»; «30-50% efficiency gains and 10-20% performance improvements» | features | https://skai.io/press-releases/skai-launches-celeste-ai-and-expands-platform-with-commerce-insights-and-operations-solutions/ | Skai | 2025-05-14 | accessed 2026-09-02 | medium | yes
15. Skai заявляет «over 8,000 brands and agencies» (один источник, self-reported) | traction | https://skai.io/press-releases/skai-launches-celeste-ai-and-expands-platform-with-commerce-insights-and-operations-solutions/ | Skai | 2025-05-14 | accessed 2026-09-02 | medium | no
16. Skai Commerce Insights and Operations: «Strategic Digital Shelf», «Retail Insights», «Content Optimization», «Retail Operations», «Revenue Recovery» | features | https://skai.io/press-releases/skai-launches-celeste-ai-and-expands-platform-with-commerce-insights-and-operations-solutions/ | Skai | 2025-05-14 | accessed 2026-09-02 | high | no
17. Skai Ticketing Automation: «Reinstate suppressed SKUs, fix variations, and update PDPs automatically», «browser automation and API-driven workflows», плановые фиксы daily/weekly/monthly, «~80% of issues resolved in under 2 days», «71% cost savings per ticket» | features | https://skai.io/ticketing-automation/ | Skai | unknown | accessed 2026-09-02 | medium | yes
18. Skai Revenue Recovery «powered by Carbon6» - chargebacks, deductions, invoice errors (сводка выдачи; в пресс-релизе Carbon6 не упомянут) | features | https://skai.io/revenue-recovery/ | Skai | unknown | accessed 2026-09-02 | low | no
19. Teikametrics Inventory: «Forecast demand precisely and sync advertising with real-time inventory signals»; метод/горизонт/overrides не названы | features | https://www.teikametrics.com/inventory-optimization/ | Teikametrics | unknown | accessed 2026-09-02 | medium | no
20. Teikametrics help: dashboard и email-алерты по товарам без продаж за последние 90 дней (excess stock) (сводка выдачи) | features | https://help.teikametrics.com/en/articles/8618450-inventory-unsold-inventory-in-l90-days-excess-stock | Teikametrics | unknown | accessed 2026-09-02 | medium | no
21. Adbrew: «Automation with control: Use AI or custom rule based PPC automation to automate bids, budget, placement, and targets»; Amazon SP/DSP/AMC + Walmart; «Trusted by 5000+ Brands, Agencies and Aggregators»; OOS-логика, алерты, approval, цены на главной не описаны | features | https://www.adbrew.io/ | Adbrew | unknown | accessed 2026-09-02 | medium | no
22. Quartile на Trustpilot: 4 звезды, ~535 отзывов; жалобы на неявку аккаунт-менеджеров, слабое обучение, «difficulty cancelling»; пометка Trustpilot о способе сбора отзывов (сводка выдачи) | sentiment | https://www.trustpilot.com/review/quartile.com | Trustpilot | unknown | accessed 2026-09-02 | low | no

## Паттерны, повторяющиеся у лидеров

1. **Порог остатков как штатный guardrail рекламы.** Inventory threshold встречается у m19 («Inventory Threshold» уже в тарифе за $59, claim 3), Pacvue (правила pause / bid-down по «weeks of inventory on hand», claim 13), Perpetua (порог по FBA/FBM с рекомендацией pause/enable, claim 8), Teikametrics («sync advertising with real-time inventory signals», claim 19); в раунде 1 - SellerStack. Различается только режим: авто-исполнение (m19, Pacvue rules) или рекомендация с approval (Perpetua).
2. **Два уровня автоматизации сосуществуют в одном продукте: правила-автоисполнители и агент/рекомендации с approval.** Amazon Ads Agent - «Campaigns only launch after you review and approve» (claim 6); Perpetua - рекомендации без авто-паузы (claim 8); Pacvue - «governed workflows» + Rule Library с автоматическим pause (claims 12-13). Для селлерского продукта это аргумент за явный переключатель «авто / с подтверждением» на уровне каждого правила.
3. **Объяснение «почему» становится маркетинговым стандартом, но не документированной механикой.** Skai Celeste обещает «the 'what' and the 'why' behind performance shifts» (claim 14), Pacvue - «what changed and why» (раунд 1); ни у кого нет описания формата объяснения, тем более сравнения ожидаемого и фактического эффекта.
4. **Задержка данных как ограничитель ежедневной цепочки.** Perpetua прямо предупреждает «up to 24 hours for inventory data to sync» (claim 9) - утренний дайджест по остаткам у любого продукта опирается на данные вчерашнего дня; честная плашка «данные на T-1» - отраслевая норма.
5. **Расширение ad-платформ в «commerce ops»: каталог, тикеты, возвраты денег.** Skai - Ticketing Automation, Content Optimization, Revenue Recovery (claims 16-18); Teikametrics - Catalog/Inventory/Refunds (раунд 1). Область G закрывается операционными тикетами (Skai: «~80% of issues resolved in under 2 days», claim 17), а не SEO-аудитом.
6. **Модель цены «фикс + % от рекламного бюджета» с порогом по spend.** m19 Professional «$479 + 3% of total ad spend/month» с границей $5K/мес (claims 1-2); Perpetua Growth «$695/mth + % of ad spend» (раунд 1). Порог по spend определяет самообслуживание vs enterprise.
7. **Email как единственный подтверждённый канал алертов.** Pacvue e-mail alerts по низким остаткам (claim 13), Teikametrics email notifications (claim 20); Slack/push/утреннее расписание не подтверждены ни у кого.

## Лиды для следующего раунда

- **Противоречие (приоритет):** Skai Revenue Recovery «powered by Carbon6» в сводке выдачи vs отсутствие Carbon6 в пресс-релизе 14.05.2025 - прочитать https://skai.io/revenue-recovery/ и найти датированный анонс партнёрства.
- **Противоречие:** SellerApp «beta в течение 2026» для Amazon Ads Agent vs первичная страница без слова beta (beta только в заголовке AMC-страницы) - прочитать https://advertising.amazon.com/resources/whats-new/unboxed-2025-ads-agent-in-amazon-marketing-cloud и unBoxed recap https://advertising.amazon.com/library/news/unboxed-2025-recap; уточнить, появился ли Ads Agent для Sponsored Products в 2026 («Campaign Manager beta», «Amazon Ads MCP Server» - https://advertising.amazon.com/library/news/amazon-ads-mcp-server-open-beta).
- **Противоречие:** Pacvue «full record of what changed and why» (главная) vs страница платформы без audit trail - искать в help-центре Pacvue (support.pacvue.com) «change log», «rule history», «Agent approvals».
- **Второй издатель для Pacvue inventory rules:** статья Amazon Ads о Pacvue редиректит в библиотеку - искать её по заголовку «How vendors manage inventory and advertising spend with Pacvue» через другой регион (/blog/ без en-gb) или веб-архив.
- **Perpetua goals guardrails:** min/max bid, ACOS-target, канал доставки Inventory Recommendations (email vs in-app) - help.perpetua.io статьи «goal settings», «notifications».
- **Teikametrics:** 16 статей раздела Inventory в help.teikametrics.com - метод прогноза, горизонт, reorder timeline; связь с bid-down.
- **Adbrew:** страницы features/pricing (не главная) - OOS-rules, алерты, approval; Adbrew заявляет «5000+ Brands» - нужен второй источник.
- **Quartile:** прочитать 1-2-звёздочные отзывы Trustpilot (фильтр stars=1,2) и Capterra; уточнить, self-serve или managed.
- **Новые сущности не покрыты:** Helium 10 Ads (Adtomic), Optmyzr (Amazon rules), atom11, Indition SellerTools, Jinnify, Xneeti - проверить OOS-aware bidding и approval.
- **Amazon Creative Agent** (https://advertising.amazon.com/resources/whats-new/unboxed-2025-creative-agent) - возможный нативный ответ на область G.
- **Область C** по-прежнему без единого подтверждения - целевой запрос по help-центрам: «recommendation history», «applied recommendations report», «impact of changes».

## Не нашёл

- Ни на одной прочитанной странице (Amazon Ads, m19, Perpetua help, Pacvue platform, Skai x2, Teikametrics, Adbrew): запись решения с последующим сравнением ожидаемого и фактического эффекта (область C).
- Утренний дайджест с фиксированным временем и каналом (Slack/push): ни у одного продукта; подтверждён только email (Pacvue, Teikametrics - сводки выдачи) и in-account рекомендации (Perpetua).
- Метод и горизонт прогноза спроса Teikametrics - на странице Inventory Optimization не названы; help-статьи не читались.
- Guardrails Amazon Ads Agent (лимиты бюджета/ставок) - в анонсе отсутствуют; доступность для SP-only селлеров - не заявлена.
- Adbrew: OOS-aware поведение, каналы алертов, approval-flow, цены - на главной странице нет.
- Skai: маршрутизация и approval тикетов, каналы алертов, список ритейлеров - на странице Ticketing Automation нет; дата релиза «agent-native operating system» - не получена.
- Второй независимый издатель для: Pacvue inventory rules (статья Amazon Ads не читается), Skai «8,000 brands», Adbrew «5000+ Brands», Celeste «over 50 clients».
- Область F (отзывы/вопросы) - по-прежнему нигде в сегменте рекламных платформ.
- Цены Pacvue, Skai, Quartile, Adbrew - не публикуются на прочитанных страницах.
