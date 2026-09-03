# dtc-ai-operating-systems - round 1

Дата доступа ко всем источникам: 2026-09-02. Бюджет: 18 вызовов инструментов (5 поисков, 13 fetch; 3 fetch неуспешны - Triple Whale pricing 403, Triple Whale KB 403, отзывы Triple Whale в Shopify App Store 404). Всё, что не подтверждено страницей, полученной в этом прогоне, помечено как «непроверено».

## Карта сегмента (широкий срез)

- **Лидеры**: Triple Whale (Moby Agents - агентная «операционка» поверх DTC-данных, публичный запуск 23.07.2025) и Shopify Sidekick + Sidekick Pulse (встроенный в админку ассистент, проактивные next best actions на главной админки, Winter '26). Оба - «платформа + агент», у обоих в 2026 появился слой действий (одноклик-публикация в рекламные кабинеты у Triple Whale по снипету; Campaign Autopilot у Shopify в early access).
- **Челленджеры**: Polar Analytics (BI на Snowflake + AI Agents + MCP + Slack-брифы), Lebesgue (Auditor - ежедневный аудит рекламы + Henri AI, дёшево: $0/$79/$149), Lifetimely (P&L/LTV + AI Profit Agent + Slack), Northbeam (атрибуция/MMM/инкрементальность; отдельного AI-ассистента в найденных первичных источниках нет), Peel (когорты/ретеншн, автоматические инсайты в Slack/email, дорого от $449).
- **Wildcard**: Polar Headless MCP и Slack-агент на открытом Hermes (Nous Research) - паттерн «аналитика как MCP-сервер, агент любой» вместо собственного чата; также Luca / Finsi как «AI reasoning layer» над данными магазина (только по снипетам, непроверено).

## Что искал и что нашёл (по продуктам)

### Triple Whale (Moby, Moby Agents; Compass)

**(A) Утренний бриф / дайджест / алерты.** По поисковому снипету маркетинговой страницы, «Moby agents deliver daily briefs, budget reallocation suggestions, creative briefs with image and video generation, and one-click publishing directly to ad platforms» (Triple Whale, дата неизвестна, https://www.triplewhale.com/moby-agents, доступ 2026-09-02; снипет, страница не прочитана - средняя уверенность). Канал доставки (email/Slack/in-app) и время отправки в найденных источниках не зафиксированы. Страницы pricing и kb.triplewhale.com отдали 403 - первичные тексты не прочитаны.

**(B) Аномалия → диагноз → действие.** Пресс-релиз описывает Moby Agents как «proactive, autonomous AI agents that analyze complex data and deliver step-by-step recommendations to optimize spend, boost efficiency, and maximize performance» с областями acquisition strategy, creative strategy, spend allocation, funnel optimization, retention workflows, inventory management (PR Newswire / Triple Whale, 2025-07-23, https://www.prnewswire.com/news-releases/triple-whale-announces-public-launch-of-moby-the-first-agentic-system-designed-to-turn-insights-into-income-302512339.html, доступ 2026-09-02). Цитата CEO AJ Orbach: «Ask Moby a question, and it doesn't just give an answer. It surfaces the next best move…» (там же). Снипет стороннего блога: агенты «detect issues proactively (margin drops, inventory risks)» (Stormy AI, 2026, https://stormy.ai/blog/triple-whale-moby-agents-shopify-amazon-ads-tutorial, доступ 2026-09-02; вторичный источник, низкая уверенность). Наличие явного шага approval перед публикацией в рекламные кабинеты - не найдено ни в одном прочитанном первичном источнике (пресс-релиз «does not explicitly detail … approvals»).

**(C) Память решений и проверка результата.** Не найдено. Ни пресс-релиз, ни снипеты не описывают запись решения и сравнение ожидаемого с фактическим.

**(D) Прогноз спроса/запасов.** Пресс-релиз называет «inventory management» как область агентов; страница Moby AI озаглавлена «Smarter Ecommerce AI Analytics & Forecasting» (Triple Whale, дата неизвестна, https://www.triplewhale.com/moby-ai, доступ 2026-09-02; только заголовок в выдаче). Метод, горизонт, override, сезонность - не найдены.

**(E) Рекламные guardrails.** Снипет: «budget reallocation suggestions» и «one-click publishing directly to ad platforms» (см. A). Уровни автоматизации, OOS-aware поведение - не найдены.

**(F) Отзывы и вопросы.** Не найдено.

**(G) Аудит контента/листинга.** Не найдено (creative briefs - генерация креативов, не аудит листинга).

**Цены и упаковка.** Страница pricing не открылась (403). Пресс-релиз: цена не раскрыта, «free trial access offered for public launch» (PR Newswire, 2025-07-23, см. выше). Есть отдельная агентская страница «Moby Agents for Agencies» (Triple Whale, https://www.triplewhale.com/moby-agents-agencies, доступ 2026-09-02; только заголовок).

**Позиционирование.** «the First Agentic System Designed to Turn Insights into Income», «Moby Agents are not just new tools. They're new teammates» (PR Newswire, 2025-07-23). Gap: заявка «autonomous» против отсутствия в первичных текстах описания approval-шага и учёта результата.

**Траектория.** Публичный запуск Moby Agents 23.07.2025; заявка «40,000 brands» и «$55 billion in ecommerce transaction data» (PR Newswire, 2025-07-23) - единственный источник, traction не верифицирована по правилу двух источников.

**Голос клиентов.** Не получен: страница отзывов в Shopify App Store вернула 404, независимый обзор не прочитан.

### Shopify Sidekick + Sidekick Pulse

**(A) Бриф/дайджест/алерты.** Sidekick Pulse «provides personalized recommendations and next steps for your business using market trends and data from your store», выдаётся проактивно внутри админки (Shopify, Winter '26, https://www.shopify.com/editions/winter2026, доступ 2026-09-02). Вторичный источник: Pulse «converts your own sales, traffic, and inventory data into next best actions, displayed on a redesigned Admin home» (Digital Applied, 2026-06-17, https://www.digitalapplied.com/blog/shopify-spring-2026-edition-sidekick-campaign-autopilot-ai, доступ 2026-09-02). Канал - главная админки; email/Slack-доставка и время не найдены.

**(B) Аномалия → диагноз → действие.** Pulse даёт «next steps»; Sidekick умеет generating custom apps, workflow automations, editing themes «with merchant oversight» (Shopify, Winter '26, там же). Отдельного описания confirmation-шага для Pulse-действий на странице нет («does not mention … specific confirmation workflows for Pulse actions»).

**(C) Память решений.** Не найдено.

**(D) Прогноз спроса.** Снипет стороннего блога утверждает, что Pulse «ingests global macroeconomic data, weather patterns, and even political stability indices to predict demand» (wearepresta.com, 2026, https://wearepresta.com/shopify-sidekick-features-2026-the-merchants-guide-to-agentic-commerce/, доступ 2026-09-02) - маркетинговый регистр, не подтверждено Shopify, низкая уверенность.

**(E) Рекламные guardrails.** Sidekick Campaign Autopilot: «AI-powered marketing campaigns automatically across Facebook, Instagram, Shop and email from a single AI-managed console», «learns and optimize[s] over time» в рамках «merchant-defined guardrails»; статус - early access, Microsoft Advertising / ChatGPT Ads / Snapchat «coming soon»; автор предупреждает: «Campaign Autopilot is the feature most likely to change shape between now and general availability» (Digital Applied, 2026-06-17, см. выше; вторичный источник со ссылкой на Shopify-материалы).

**(F) Отзывы/вопросы.** Не найдено ни на help-странице, ни в Editions.

**(G) Аудит листинга.** Sidekick редактирует темы/контент и генерирует медиа (logo, background removal, banners) (Shopify Help Center, дата не указана, https://help.shopify.com/en/manual/shopify-magic/sidekick, доступ 2026-09-02); аудита изменений листинга/сравнения с конкурентами не найдено.

**Цены.** «Shopify Magic tools and experiences are available for free, regardless of your subscription plan», «the access and availability of specific features might vary» (Shopify Help Center, там же).

**Позиционирование.** «AI-powered commerce assistant trained to know all of Shopify's features» (Shopify Help Center). Gap: Pulse - рекомендации без описанного цикла проверки результата.

**Траектория.** Winter '26: Pulse; Spring '26 (публикация 2026-06-17): Sidekick everywhere и Sidekick App Extensions (15+ partners) GA, Campaign Autopilot early access (Digital Applied, 2026-06-17). Снипет: «Sidekick's weekly active shops grew 4x year-over-year in Q1 2026» (wearepresta.com, 2026, https://wearepresta.com/shopify-ai-the-definitive-strategic-blueprint-for-2026/, доступ 2026-09-02; вторичный, первоисточник Shopify не прочитан - непроверено).

**Голос клиентов.** Не собран (обзор create8.co.uk найден, не прочитан).

### Lebesgue (Auditor, Henri AI)

**(A) Бриф/алерты.** Auditor - «Daily account auditing and error detection» (Lebesgue, © 2025, https://lebesgue.io/, доступ 2026-09-02). Free-план включает «automated audits for Meta/Google/TikTok» (Lebesgue, дата неизвестна, https://lebesgue.io/pricing, доступ 2026-09-02). Канал и время доставки на страницах не указаны («specific reporting frequencies aren't detailed»).

**(B) Аномалия → диагноз → действие.** Henri AI: «clear explanations · root-cause analysis · step-by-step growth strategy», показывает «the real contribution of every channel» для бюджета (Lebesgue, https://lebesgue.io/). План Ultimate AI ($149/мес) включает «approved marketing execution» и «budget allocation recommendations» (Lebesgue pricing) - формулировка «approved» указывает на шаг одобрения, но механика не описана.

**(C) Память решений.** Не найдено.

**(D) Прогноз.** Не найдено (есть «predictive models» в описании Henri без деталей).

**(E) Рекламные guardrails.** «approved marketing execution» + «budget allocation recommendations» (Lebesgue pricing). OOS-aware, уровни автоматизации - не найдены.

**(F) Отзывы.** Не найдено.

**(G) Аудит контента / конкуренты.** Агенты «Echo» («decodes competitors' email strategies to reveal product launches and discounts») и «Sentinel» («real-time competitor ad monitoring and analysis»); «Monitor competitor ads, creative trends, and spend patterns across major platforms» (Lebesgue, https://lebesgue.io/). Аудит собственного листинга/SEO не найден.

**Цены.** Free $0; Ultimate $79/мес («Limited Henri AI access (10 business questions/month)»); Ultimate AI $149/мес («Unlimited Henri AI analysis»); Le Pixel Attribution от $99 до $999/мес по выручке; Le Pixel Enrichment $149-$1,099/мес (Lebesgue pricing, доступ 2026-09-02).

**Позиционирование.** «AI CMO». Противоречие на одной странице: «Trusted by 10,000+ eCommerce brands worldwide» и «5,000+» в другом месте (Lebesgue, https://lebesgue.io/) - traction непроверена.

**Голос клиентов.** Не собран.

### Polar Analytics

**(A) Бриф/алерты.** Alerts - «customizable notifications for increases or decreases in metrics of your choosing, whenever a set threshold is met», через email, Slack или оба, с дополнительными получателями (Polar Analytics Help Center, дата неизвестна, https://intercom.help/polar-app/en/articles/5500342-how-do-i-set-up-my-alerts-on-slack-or-email, доступ 2026-09-02; снипет). Smart alerts: «monitors data 24/7 to find abnormalities and optimizations, and notifies … immediately through email or Slack» (Polar, https://www.polaranalytics.com/features/smart-alerts, снипет). Slack-интеграция: «schedule daily and weekly briefs to post automatically», «powered by Hermes, the open-source AI agent from Nous Research, connected to Polar data over MCP» (Polar, https://www.polaranalytics.com/integrations/slack, снипет, доступ 2026-09-02).

**(B) Аномалия → диагноз → действие.** Снипет страницы «What Is Agentic Analytics»: агент «can flag issues like CAC spikes, revenue drops, or channels that have fallen off in Slack with explanations», агенты «can write to Slack, drop pages in Notion, fire emails, open tickets, or adjust spend» (Polar, https://www.polaranalytics.com/post/what-is-agentic-analytics-the-future-of-ecommerce-data, снипет). Approval-шаг - не найден.

**(C) Память решений.** Не найдено.

**(D) Прогноз.** Не найдено на pricing/в снипетах.

**(E) Guardrails.** «adjust spend» упомянут в снипете без описания ограничений; Custom-план включает «Incrementality Testing» с «Dedicated data scientist» и «Advertising Signals» (Polar pricing, https://www.polaranalytics.com/pricing, доступ 2026-09-02).

**(F) Отзывы.** Не найдено.

**(G) Аудит листинга.** Не найдено.

**Цены.** Тарифы по годовому GMV, суммы скрыты за выбором диапазона; Core («All Business Intelligence», «AI Agents», «Data Activations») и Custom (+ Incrementality Testing, Advertising Signals, Polar Headless MCP «400+ pre-built ecommerce metrics (semantic layer)»); везде «Dedicated Snowflake database», «Unlimited users», «Dedicated Success Manager, Slack channel» (Polar pricing, доступ 2026-09-02). Заголовок страницы: «Plans for Ecommerce Brands & Agencies» - агентские тарифы есть, детали не прочитаны.

**Позиционирование/траектория.** «Agentic analytics», MCP-native для Claude/ChatGPT (Polar pricing; https://www.polaranalytics.com/ai). Голос клиентов - не собран.

### Lifetimely (AMP)

**(A/B/E)** «AI Profit Agent (paid tiers)», «Slack integration for AI insights and alerts», «Real-time P&L», «Channel-level marketing attribution & ROAS» (Shopify App Store, листинг, доступ 2026-09-02, https://apps.shopify.com/lifetimely-lifetime-value-and-profit-analytics). Содержание бриф-письма, время, диагностика причин - не описаны.

**(C)** Не найдено. **(D)** «Predictive LTV modeling», «Sales forecasting» - метод/горизонт не указаны (там же). **(F/G)** Не найдено.

**Цены.** Free до 50 заказов/мес; S $49 (500 заказов); M $149 (3,000); L $299 (7,000); Amazon add-on $75/мес; 14-day trial (там же).

**Голос клиентов.** 4.9/5, 474 отзыва, 97% пятизвёздочных; хвалят команду («They go above and beyond», CS2, US, август 2026) и простоту («Simple and fast and not bloated…acts as our source of truth», Nikura, UK, июль 2026) (там же). 1-3-звёздные отзывы в выдаче не прочитаны.

### Northbeam

**(A-G)** Первичный блог (Northbeam, 2024-02-08, https://www.northbeam.io/blog/how-does-northbeam-use-ai, доступ 2026-09-02): ML для атрибуции («assign a percentage attribution to each campaign or touch»), прогноз каналов («predict how different channels would continue to perform in the future», «run simulations … at different spending levels»). Ассистент/агент, брифы, алерты, approval - не найдены. Снипет: «self-service incrementality tests (coming Q1 2026)» (aisystemscommerce.com, 2026, https://www.aisystemscommerce.com/post/northbeam-review-2026-incrementality-attribution-dtc; вторичный, будущее время - низкая уверенность). Цены и отзывы не прочитаны. Внимание: «Northbeams» (northbeams.com) - другой продукт (AI agent control plane), не смешивать.

### Peel Insights

**(A)** «Automated insights via Slack/email» на всех планах (Peel, © 2026, https://www.peelinsights.com/pricing, доступ 2026-09-02). Частота, аномалии, прогноз, Magic Dash AI, агентские планы - на странице отсутствуют («does not mention»). **(B-G)** Не найдено.

**Цены.** Essentials «$449/mo (billed ANNUALLY) or $499 monthly» (>16,000 заказов/мес), Accelerate «$809/mo … or $899 monthly» (>29,000), Tailored - custom (≥62,000); «Free 7-day trial … No call, no commitment and no credit card required»; Snowflake data access (там же). Peel - «A Relay Commerce Company» (там же). Снипет: «Used By 50 Brands» (1800d2c.com, 2025, https://www.1800d2c.com/tool/peel; непроверено).

## Claims (нумерованный список)

1. Triple Whale публично запустила Moby Agents 23.07.2025 как «proactive, autonomous AI agents … deliver step-by-step recommendations» | trajectory | https://www.prnewswire.com/news-releases/triple-whale-announces-public-launch-of-moby-the-first-agentic-system-designed-to-turn-insights-into-income-302512339.html | PR Newswire (Triple Whale) | 2025-07-23 | accessed 2026-09-02 | high | yes
2. Triple Whale заявляет 40,000 brands и $55B транзакционных данных (один источник, не верифицировано) | traction | тот же URL | PR Newswire (Triple Whale) | 2025-07-23 | accessed 2026-09-02 | low | no
3. Moby Agents «deliver daily briefs, budget reallocation suggestions … one-click publishing directly to ad platforms» (снипет, страница не прочитана) | features | https://www.triplewhale.com/moby-agents | Triple Whale | unknown | accessed 2026-09-02 | medium | yes
4. Sidekick Pulse даёт «personalized recommendations and next steps … using market trends and data from your store» в админке | features | https://www.shopify.com/editions/winter2026 | Shopify | 2026-01 (Winter '26) | accessed 2026-09-02 | high | yes
5. Pulse «converts your own sales, traffic, and inventory data into next best actions, displayed on a redesigned Admin home» | features | https://www.digitalapplied.com/blog/shopify-spring-2026-edition-sidekick-campaign-autopilot-ai | Digital Applied | 2026-06-17 | accessed 2026-09-02 | medium | no
6. Sidekick Campaign Autopilot - early access, каналы Facebook/Instagram/Shop/email, «merchant-defined guardrails» | trajectory | тот же URL | Digital Applied | 2026-06-17 | accessed 2026-09-02 | medium | yes
7. Shopify Magic/Sidekick «available for free, regardless of your subscription plan» | pricing | https://help.shopify.com/en/manual/shopify-magic/sidekick | Shopify Help Center | unknown | accessed 2026-09-02 | high | no
8. Sidekick weekly active shops выросли 4x YoY в Q1 2026 (вторичный источник) | traction | https://wearepresta.com/shopify-ai-the-definitive-strategic-blueprint-for-2026/ | wearepresta.com | 2026 | accessed 2026-09-02 | low | no
9. Lebesgue: Free $0, Ultimate $79/мес (10 вопросов Henri/мес), Ultimate AI $149/мес («Unlimited Henri AI», «approved marketing execution», «budget allocation recommendations») | pricing | https://lebesgue.io/pricing | Lebesgue | unknown | accessed 2026-09-02 | high | yes
10. Lebesgue Auditor - «Daily account auditing and error detection»; Henri - «root-cause analysis · step-by-step growth strategy» | features | https://lebesgue.io/ | Lebesgue | 2025 (©) | accessed 2026-09-02 | high | no
11. Lebesgue: агенты Echo (email конкурентов) и Sentinel (реклама конкурентов) | features | https://lebesgue.io/ | Lebesgue | 2025 (©) | accessed 2026-09-02 | high | no
12. Lebesgue заявляет «10,000+» и «5,000+» брендов на одной странице (противоречие) | traction | https://lebesgue.io/ | Lebesgue | 2025 (©) | accessed 2026-09-02 | low | no
13. Polar: пороговые алерты по метрикам в email/Slack с доп. получателями | features | https://intercom.help/polar-app/en/articles/5500342-how-do-i-set-up-my-alerts-on-slack-or-email | Polar Analytics Help Center | unknown | accessed 2026-09-02 | medium | no
14. Polar Slack: «schedule daily and weekly briefs to post automatically», агент на Hermes (Nous Research) через MCP | features | https://www.polaranalytics.com/integrations/slack | Polar Analytics | unknown | accessed 2026-09-02 | medium | yes
15. Polar pricing по годовому GMV; Core = BI + AI Agents + Data Activations; Custom + Incrementality Testing, Advertising Signals, Headless MCP («400+ pre-built ecommerce metrics») | pricing | https://www.polaranalytics.com/pricing | Polar Analytics | unknown | accessed 2026-09-02 | high | no
16. Polar агент «can flag issues like CAC spikes, revenue drops … with explanations» и «adjust spend» | positioning | https://www.polaranalytics.com/post/what-is-agentic-analytics-the-future-of-ecommerce-data | Polar Analytics | unknown | accessed 2026-09-02 | low | no
17. Lifetimely: Free (50 заказов), S $49, M $149, L $299, Amazon add-on $75; «AI Profit Agent (paid tiers)», Slack alerts | pricing | https://apps.shopify.com/lifetimely-lifetime-value-and-profit-analytics | Shopify App Store | unknown | accessed 2026-09-02 | high | no
18. Lifetimely: 4.9/5, 474 отзыва, 97% пятизвёздочных | sentiment | тот же URL | Shopify App Store | 2026-08 | accessed 2026-09-02 | high | no
19. Northbeam: ML-атрибуция, прогноз каналов и симуляции по уровням спенда; агент/бриф не описаны | features | https://www.northbeam.io/blog/how-does-northbeam-use-ai | Northbeam | 2024-02-08 | accessed 2026-09-02 | high | no
20. Northbeam: self-service incrementality tests «coming Q1 2026» (вторичный, будущее время) | trajectory | https://www.aisystemscommerce.com/post/northbeam-review-2026-incrementality-attribution-dtc | aisystemscommerce.com | 2026 | accessed 2026-09-02 | low | no
21. Peel: Essentials $449/мес (annual) / $499, Accelerate $809 / $899, Tailored custom; 7-day trial без карты; «Automated insights via Slack/email» | pricing | https://www.peelinsights.com/pricing | Peel Insights | 2026 (©) | accessed 2026-09-02 | high | no
22. Peel - «A Relay Commerce Company» | trajectory | https://www.peelinsights.com/pricing | Peel Insights | 2026 (©) | accessed 2026-09-02 | high | no
23. Triple Whale: цена Moby не раскрыта, «free trial access offered for public launch» | pricing | PR Newswire URL (см. 1) | PR Newswire | 2025-07-23 | accessed 2026-09-02 | medium | no

## Паттерны, повторяющиеся у лидеров

1. **Проактивные «next best actions» вместо чата по запросу.** Sidekick Pulse на главной админки (Shopify Winter '26; Digital Applied 2026-06-17), Moby Agents «surfaces the next best move» (PR Newswire 2025-07-23), Henri «step-by-step growth strategy» (lebesgue.io). Точка входа - место, где продавец уже находится (админка / Slack), а не отдельный дашборд.
2. **Бриф и алерты в Slack/email по расписанию + пороговые алерты.** Polar («schedule daily and weekly briefs», threshold alerts email/Slack), Lifetimely (Slack alerts AI Profit Agent), Peel («Automated insights via Slack/email»), Triple Whale («daily briefs», снипет). Время отправки нигде не задокументировано в прочитанных источниках.
3. **Слой действий с guardrails, но approval описан слабо.** Shopify Campaign Autopilot - «merchant-defined guardrails», early access; Lebesgue - «approved marketing execution»; Triple Whale - «one-click publishing»; Polar - «adjust spend». Ни у одного продукта в прочитанных первичных текстах нет описания цикла approval→execute→verify.
4. **«Объясни почему» как явное обещание.** Henri «root-cause analysis», Polar «with explanations», Moby «step-by-step recommendations». Проверка результата после действия (expected vs actual) - не найдена ни у кого.
5. **Дешёвый вход через free-tier + AI-дозировка.** Lebesgue Free/$79 с 10 вопросами Henri/$149 unlimited; Lifetimely Free до 50 заказов; Shopify Magic бесплатно. Премиум-BI (Polar, Peel от $449) - по GMV/заказам.
6. **Данные как открытый слой (MCP/Snowflake) вместо закрытого ассистента.** Polar Headless MCP + Hermes-агент в Slack, Peel Snowflake access, Polar Snowflake database. Wildcard для позиционирования: «наш семантический слой доступен любому агенту».
7. **Мониторинг конкурентов как AI-агенты.** Lebesgue Echo/Sentinel (email и реклама конкурентов). Аудит собственного листинга/SEO у DTC-инструментов не найден - это амазоно-/маркетплейс-специфичная область.

## Лиды для следующего раунда

- **Противоречие (приоритет):** Lebesgue на одной странице заявляет «10,000+» и «5,000+» брендов - запросить G2/Shopify App Store для traction.
- **Противоречие:** снипет Stormy AI называет «Moby 2 AI agents» и «action-based», пресс-релиз 2025 - Moby Agents; проверить changelog Triple Whale (kb.triplewhale.com, 403 в этом прогоне - попробовать через другой fetch или Wayback).
- **Незакрыто:** Triple Whale pricing (403) - нужен живой прайс и агентский workspace (https://www.triplewhale.com/moby-agents-agencies). Compass (упомянут в брифе) в этом прогоне вообще не найден - выяснить, что это (продукт/фича/устарело).
- **Незакрыто:** Shopify - первичная страница Summer '26 / Spring '26 Editions на shopify.com (Campaign Autopilot, Pulse-каналы, approvals); первоисточник цифры «4x weekly active shops» (Shopify Q1 2026 earnings).
- **Незакрыто:** Polar - прочитать https://www.polaranalytics.com/ai и https://www.polaranalytics.com/integrations/slack целиком (агент Hermes + MCP, approval при «adjust spend»); агентские планы.
- **Незакрыто:** Northbeam - живой прайс, наличие AI-ассистента/алертов (первичный блог 2024 устарел); Peel «Magic Dash AI» и частота брифов.
- **Новые сущности:** Luca (ask-luca.com, «AI reasoning layer … finds root cause, simulates changes»), Finsi (finsi.ai), Tydo, Cometly, Relay Commerce (владелец Peel), Northbeams (не путать).
- **Голос клиентов:** ни для одного лидера не прочитан 1-3-звёздный отзыв (Shopify App Store для Triple Whale 404 - попробовать https://apps.shopify.com/triple-whale/reviews без фильтров; G2 для Triple Whale/Polar/Northbeam; обзор create8.co.uk по Sidekick).
- **Вопрос:** есть ли у кого-то из сегмента запись решения и последующая проверка результата (C) - в раунде 1 не найдено ни у одного продукта; проверить changelog Triple Whale и Polar «Data Activations».

## Не нашёл

- Triple Whale pricing и KB (403) - нет первичных цен и описания расписания/каналов Moby-брифов; Compass не обнаружен ни в одной выдаче.
- Отзывы 1-3 звезды на Triple Whale (404 на фильтрованной странице App Store); независимые обзоры для Shopify Sidekick, Polar, Lebesgue, Northbeam, Peel не прочитаны в рамках бюджета.
- Capability (C) - память решений и сверка ожидаемого с фактическим - не найдена ни у одного из 7 продуктов.
- Capability (F) - работа с отзывами/вопросами покупателей - не найдена ни у одного продукта сегмента (DTC-инструменты не работают с отзывами маркетплейсов).
- Capability (G) - аудит собственного листинга/SEO/алерты на изменение карточки - не найден (есть только мониторинг конкурентов у Lebesgue).
- OOS-aware поведение рекламной автоматизации (E) - не описано ни у кого.
- Время суток отправки daily brief и метод/горизонт прогноза (D) - не задокументированы ни у одного продукта в прочитанных источниках.
- Агентские multi-brand workspace: есть только заголовки страниц (Triple Whale «Moby Agents for Agencies», Polar «Plans for Ecommerce Brands & Agencies») без прочитанного содержания.
