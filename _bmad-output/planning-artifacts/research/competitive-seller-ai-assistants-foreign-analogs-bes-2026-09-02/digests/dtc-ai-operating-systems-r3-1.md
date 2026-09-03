# dtc-ai-operating-systems - round 3

Дата доступа ко всем источникам: 2026-09-02. Бюджет: 15 tool-вызовов, 6 страниц прочитано целиком (Shopify blog, Polar pricing, Peel Help, WRKNG Digital, PR Newswire, Amp/Lifetimely), 6 поисковых выдач (сниппеты - пониженная уверенность). Раунд лидоследования: приоритет - противоречия из раунда 2, потом новые сущности, потом незакрытые вопросы.

## Что искал и что нашёл (по продуктам)

### Shopify Sidekick / Campaign Autopilot (противоречие раунда 2 снято)

**Снятие противоречия по каналам.** Официальный пост о запуске Campaign Autopilot от 17.06.2026 перечисляет каналы: Meta ads, Microsoft Advertising, Shop Campaigns, Shopify Messaging; «Coming soon: ChatGPT Ads and Snapchat» (Shopify, 2026-06-17, https://www.shopify.com/blog/introducing-campaign-autopilot, доступ 2026-09-02). Это совпадает с Help Center из раунда 2 (Shopify Messaging, Shop Campaigns, Meta Ads, Microsoft Advertising). Независимый обзор WRKNG Digital от 23.06.2026 наблюдал Meta ads, Shop Campaigns, Shopify Email, а «ChatGPT Ads and Microsoft Advertising (coming July 2026)» (WRKNG Digital, 2026-06-23, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review, доступ 2026-09-02). Вывод: версия Digital Applied (Facebook/Instagram/Shop/email) - это те же Meta + Shop Campaigns + Shopify Messaging/Email в другой номенклатуре; расхождение по Microsoft Advertising (вендор - «доступно», обозреватель - «с июля») объясняется поэтапным ранним доступом; берём вендорский список как канонический, статус Microsoft Advertising на 09.2026 - UNKNOWN.

**(A) Бриф/алерты.** В посте о запуске нет упоминаний ежедневной или еженедельной каденции рекомендаций (Shopify, 2026-06-17, https://www.shopify.com/blog/introducing-campaign-autopilot, доступ 2026-09-02). Обозреватель предлагает ритм пользователя, а не продукта: «Thirty minutes per week. Check channel spend, ROAS by channel, and Sidekick's latest suggestions» (WRKNG Digital, 2026-06-23, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review, доступ 2026-09-02).

**(B) Аномалия → диагноз → действие.** Sidekick «surfaces suggestions for audience segments, creative rotation, and product promotion priorities»; формула обозревателя: «Sidekick recommends. You approve.» (WRKNG Digital, 2026-06-23, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review, доступ 2026-09-02).

**(C) Память решений.** Не описана ни вендором, ни обозревателем.

**(D) Прогноз спроса/запасов.** Обозреватель хвалит «operational intelligence connects marketing to inventory management», но метод/горизонт не назван (WRKNG Digital, 2026-06-23, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review, доступ 2026-09-02).

**(E) Guardrails рекламной автоматизации - главная находка.** Уровни автономии задаёт мерчант: «You decide how much control you want, from approving every campaign before it runs to giving Campaign Autopilot more room as campaigns evolve»; можно «reject a recommendation, change your budget, or pause at any time»; бюджет месячный, «Campaigns pause automatically when you reach your budget»; мерчант задаёт правила, что Autopilot может и не может (Shopify, 2026-06-17, https://www.shopify.com/blog/introducing-campaign-autopilot, доступ 2026-09-02). Обозреватель формулирует четыре обязательных guardrail'а перед включением: заполнить себестоимость товаров для margin-adjusted ROAS; задать channel budget floors, чтобы канал не обнулили; проверить Meta pixel + Conversions API; задать жёсткий потолок бюджета (WRKNG Digital, 2026-06-23, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review, доступ 2026-09-02). OOS-aware поведение явно не заявлено ни в одном из двух источников.

**(F) Отзывы/вопросы, (G) аудит листинга.** Не затронуты ни в посте, ни в обзоре.

**Прайс и упаковка.** «available now in early access», «free for all brands on paid Shopify plans», платится только прямой рекламный расход в Meta, Shop Campaigns и e-mail-сервисах (Shopify, 2026-06-17, https://www.shopify.com/blog/introducing-campaign-autopilot, доступ 2026-09-02); обозреватель подтверждает «Included free on all paid plans» (WRKNG Digital, 2026-06-23, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review, доступ 2026-09-02).

**Позиционирование vs продукт.** Ограничения по обзору: нет генерации креативов; нет гранулярного контроля аудиторий (нельзя собрать LTV-tier сегменты); базовая отчётность - разбивка по кампаниям требует Meta Ads Manager; окно атрибуции по умолчанию 7-day click / 1-day view; рекомендован магазинам с рекламным бюджетом до $50K/мес без собственного медиабайера (WRKNG Digital, 2026-06-23, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review, доступ 2026-09-02). Плюс - кросс-канальная атрибуция на «actual order data», а не самоотчёте Meta (там же).

**Не снято.** Первоисточник «4x weekly active shops» (Q1 2026 earnings) не искали в этом раунде - бюджет ушёл на противоречия.

### Triple Whale (Moby 2, Compass) - первичные страницы по-прежнему 403, Wayback недоступен

**Что удалось.** Прямой пресс-релиз о Moby 2 читается: датирован 19.05.2026, Columbus, Ohio; объявлена «general availability of Moby 2» (Triple Whale via PR Newswire, 2026-05-19, https://www.prnewswire.com/news-releases/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2-302776288.html, доступ 2026-09-02). Wayback (web.archive.org) инструментом не фетчится; G2 reviews - 403.

**(A) Бриф/алерты.** Пресс-релиз: Moby 2 может «monitor anomalies, and take action directly across ecommerce and marketing systems» - канал и расписание не названы (PR Newswire, 2026-05-19, та же ссылка, доступ 2026-09-02).

**(B) Аномалия → диагноз → действие, (E) guardrails.** Три «Moby Specialists», каждый вокруг одного KPI: Moby Media Buyer (кампании в Meta и Google, «every decision backed by first-party measurement»), Moby Creative Director (генерирует, тестирует, итерирует креатив против creative fatigue), Moby Conversion Optimizer (строит и улучшает лендинги). Режимы: «Copilot mode, where customers approve actions, or Autopilot mode, where Moby executes autonomously within predefined guardrails» (PR Newswire, 2026-05-19, https://www.prnewswire.com/news-releases/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2-302776288.html, доступ 2026-09-02). Сниппет поиска подтверждает оркестрацию «across frontier AI models including GPT, Claude, and Gemini» (Morningstar/PR Newswire, 2026-05-19, https://www.morningstar.com/news/pr-newswire/20260519cl62731/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2, доступ 2026-09-02, сниппет). Содержимое guardrails (что именно ограничивается: бюджет, ROAS-порог, OOS) в релизе не раскрыто.

**(C) Память решений / сверка результата.** В пресс-релизе о Moby 2 «no explicit language found regarding post-execution tracking, measurement of outcomes, or closed-loop learning» (PR Newswire, 2026-05-19, та же ссылка, доступ 2026-09-02). Единственный «closed loop» у Triple Whale остаётся калибровкой модели Compass (раунд 2), а не сверкой ожидаемого/фактического по решению.

**(D) Прогноз.** Заявлено «forecast inventory» без метода и горизонта (PR Newswire, 2026-05-19, та же ссылка, доступ 2026-09-02).

**(F), (G).** Не упомянуты.

**Traction.** «used by more than 60,000 ecommerce and retail brands» - только из вендорского релиза, независимого подтверждения нет (PR Newswire, 2026-05-19, та же ссылка, доступ 2026-09-02); класс two-source, не верифицировано.

**Прайс.** Живая страница 403; Wayback недоступен. Вторичный источник: «all prices are based on a combination of your brand's annual GMV and the package you choose»; add-on'ы Retention $19/мес и Conversion $79/мес (Eightx, дата unknown, https://eightx.co/blog/compare/reviews/triple-whale-for-ecommerce-review, доступ 2026-09-02, сниппет). Цены Foundation $219 / Automate $749 из раунда 2 вторым публикатором не подтверждены.

**Голос клиентов (сниппеты, вторичные).** «Cost is the most frequently cited reason to look elsewhere on Reddit» - 6 из 54 тредов (RedditMaster, 2026, https://www.redditmaster.com/reddit-intelligence/triple-whale, доступ 2026-09-02, сниппет). Повышение цен «30-50% across tiers in 2024, including for some existing customers mid-contract»; один оператор - «mid-contract jump from $329 to $549 a month» на 12-месячном контракте (Eightx, дата unknown, https://eightx.co/blog/compare/reviews/triple-whale-for-ecommerce-review, доступ 2026-09-02, сниппет). Пользователи G2 «from smaller stores under seven figures in annual revenue consistently flag Triple Whale's pricing as difficult to justify» (пересказ WiserReview, 2026, https://wiserreview.com/blog/triple-whale-alternatives/, доступ 2026-09-02, сниппет). Первичные тексты 1-3-звёздочных отзывов не получены (G2 403).

### Polar Analytics (pricing прочитан)

**Прайс и упаковка.** Два плана: «Core» («The essential data stack») и «Custom» («A customizable product stack»); селектор «Select your annual gross merchandise value» - цена зависит от GMV, конкретные суммы на странице без выбора GMV не отображаются. Core включает «All Business Intelligence», «AI Agents», «Data Activations», «Saves 20% on individual product costs»; Custom - Business Intelligence, Incrementality Testing, Polar Headless MCP, Klaviyo Audiences, Advertising Signals. Во всех планах: «Dedicated Snowflake database», «Unlimited users», «Unlimited historical data», «Dedicated Success Manager», «Slack channel», «Live chat» (Polar Analytics, дата unknown, https://www.polaranalytics.com/pricing, доступ 2026-09-02). Агенты Data Analyst, Media Buyer, Inventory Planner, Email Marketer упомянуты, но без привязки к плану.

**Агентский multi-brand workspace.** Отдельного агентского тарифа на странице нет; «Unlimited users» - единственный релевантный признак (там же). (A)-(G) в этом раунде не дополнены; approval-gate у Media Buyer Agent и OOS-связь с Inventory Planner Agent по-прежнему не задокументированы.

### Peel Insights (Magic Dash) - новая в этом раунде

**(A) Бриф/алерты.** В FAQ Magic Dash «Scheduled Reports/Email/Slack: not mentioned», «Anomaly Alerts: not mentioned» (Peel Insights Help, обновлено 2025-06-02, https://help.peelinsights.com/docs/magic-dash-faqs, доступ 2026-09-02). Ежедневного брифа как продуктовой функции не найдено.

**(B) Диагноз → действие.** Magic Dash - «An Insights Engine that answers your most important questions about your business. Ask it a question and it will automatically generate a dashboard using your data»; умеет «generate observations that provide a deeper understanding of your business» - рекомендации действий не описаны (Peel Insights Help, 2025-06-02, та же ссылка, доступ 2026-09-02). Сниппет сайта: дашборды включают Market Basket Analysis и RFM (Peel Insights, дата unknown, https://www.peelinsights.com/magic-dash, доступ 2026-09-02, сниппет).

**(C)-(G).** Не описаны. Особенность позиционирования по данным: «Your data is secure and is not being shared with an AI. The widgets can only display data that exists in your account» (Peel Insights Help, 2025-06-02, та же ссылка, доступ 2026-09-02) - т.е. LLM генерирует запрос/виджет, а не читает данные. Маркетинговая метрика «3x repeat purchases while cutting time spent on analysis by 90%» - без источника (Peel Insights LinkedIn, 2023-12, https://www.linkedin.com/posts/peel-insights_magic-dash-ai-retention-platform-for-d2c-activity-7136014723904409602-_ZhM, доступ 2026-09-02, сниппет; низкая уверенность). Дата LinkedIn-поста (12.2023) и обновления FAQ (06.2025) указывают, что Magic Dash - продукт 2023 года без заметных обновлений в окне 6 мес: траектория UNKNOWN.

### Lifetimely (теперь Amp) - новая в этом раунде

**Структурный факт.** URL lifetimely.io/blog-posts/new-predictive-ltv-model отдаёт 301 на useamp.com/products/analytics; страница продукта подписана «© Copyright 2026 AMP» и ссылается на «About Amp» (Amp, 2026, https://useamp.com/products/analytics/lifetime-value, доступ 2026-09-02) - Lifetimely живёт внутри Amp; дата/условия сделки не найдены.

**(D) Прогноз LTV.** На живой странице: «Our predictive LTV model uses AI to estimate future LTV of different segments of your customer base, allowing you to make more informed decisions about LTV, CAC payback period and more» - метод, горизонт, overrides, сезонность не раскрыты (Amp, 2026, https://useamp.com/products/analytics/lifetime-value, доступ 2026-09-02). Сниппет старого поста Lifetimely: горизонты 3/6/12/24 месяца; «instead of projecting just a single LTV number, they built their model to forecast the monthly sales of each individual customer over their lifetime»; модель в проде минимум с 04.2021 (Lifetimely blog, ~2021-04, https://www.lifetimely.io/blog-posts/new-predictive-ltv-model, доступ 2026-09-02, сниппет - страница переехала, текст недоступен). Прогноз спроса/запасов (не LTV) - не заявлен.

**(A)-(C), (E)-(G).** На странице «No mention of daily or weekly email reports, Slack digests, or automated alerts» (Amp, 2026, та же ссылка, доступ 2026-09-02).

### Lebesgue (Auditor) - traction

**Финансирование/траектория.** Seed $3M, лид Interactive Venture Partners, участники Bridge Investments, Fil Rouge Capital, K20 Fund, объявлено 21.01.2025; основана в 2018 Andrijana Brkić и Josip Begić; «optimized over $2 billion in marketing investments» (Dealroom, 2025-01, https://app.dealroom.co/news/feed/lebesgue-secures-3m-for-ai-marketing, доступ 2026-09-02, сниппет; Bridge Venture Fund, 2025-01, https://www.bridgeventurefund.com/news/lebesgue-raises-3m-seed-round, доступ 2026-09-02, сниппет). Раунд старше 6 мес - за пределами freshness-бара для траектории, свежих раундов не найдено.

**Противоречие «10,000+ vs 5,000+ brands» не снято.** Все три сниппета (Dealroom, Bridge, IT Logs) повторяют «trusted by 10,000+ eCommerce brands» из одного пресс-релиза - один upstream, не два публикатора; независимого подтверждения нет. Отзывы 120 vs 126 - не проверяли (бюджет).

### Luca (ask-luca.com) - второй источник не найден

Поиск отдал только собственные страницы Luca. Ими заявлено: «generates a five-section report structure automatically every Monday morning, compiled from connected Shopify, ad platform, accounting, and 3PL data» - еженедельный, не ежедневный бриф; таргет «Shopify and DTC stores between €1M and €5M in revenue» без аналитика в штате (Luca, дата unknown, https://ask-luca.com/blogs/ecommerce-reporting, доступ 2026-09-02, сниппет). Клиенты и модель финансирования вторым публикатором не подтверждены.

### Northbeam - не исследовалась в этом раунде (бюджет).

## Claims (нумерованный список)

1. Campaign Autopilot покрывает Meta ads, Microsoft Advertising, Shop Campaigns, Shopify Messaging; «Coming soon: ChatGPT Ads and Snapchat» | features | https://www.shopify.com/blog/introducing-campaign-autopilot | Shopify | 2026-06-17 | accessed 2026-09-02 | high | no
2. Campaign Autopilot: «You decide how much control you want, from approving every campaign before it runs to giving Campaign Autopilot more room as campaigns evolve»; «Campaigns pause automatically when you reach your budget» | features | https://www.shopify.com/blog/introducing-campaign-autopilot | Shopify | 2026-06-17 | accessed 2026-09-02 | high | yes
3. Campaign Autopilot «available now in early access», «free for all brands on paid Shopify plans», платится только прямой ad spend | pricing | https://www.shopify.com/blog/introducing-campaign-autopilot | Shopify | 2026-06-17 | accessed 2026-09-02 | high | no
4. Независимый обзор: «Sidekick recommends. You approve.»; рекомендуемый ритм «Thirty minutes per week»; четыре guardrail'а - себестоимость товаров, channel budget floors, Meta pixel/CAPI, hard budget ceiling | features | https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review | WRKNG Digital | 2026-06-23 | accessed 2026-09-02 | medium | yes
5. Ограничения Campaign Autopilot по обзору: нет генерации креативов, нет LTV-tier сегментов, разбивка по кампаниям только в Meta Ads Manager, окно атрибуции 7-day click/1-day view; рекомендован до $50K/мес ad spend | positioning | https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review | WRKNG Digital | 2026-06-23 | accessed 2026-09-02 | medium | no
6. Moby 2 GA 19.05.2026; три Moby Specialists (Media Buyer, Creative Director, Conversion Optimizer); «Copilot mode, where customers approve actions, or Autopilot mode, where Moby executes autonomously within predefined guardrails» | features | https://www.prnewswire.com/news-releases/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2-302776288.html | Triple Whale via PR Newswire | 2026-05-19 | accessed 2026-09-02 | high | yes
7. Moby 2 может «monitor anomalies, and take action directly across ecommerce and marketing systems» и «forecast inventory»; канал/расписание/метод не названы | features | https://www.prnewswire.com/news-releases/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2-302776288.html | Triple Whale via PR Newswire | 2026-05-19 | accessed 2026-09-02 | medium | no
8. В пресс-релизе Moby 2 нет формулировок о post-execution tracking / измерении результата действий / closed-loop learning | features | https://www.prnewswire.com/news-releases/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2-302776288.html | Triple Whale via PR Newswire | 2026-05-19 | accessed 2026-09-02 | medium | yes
9. Triple Whale «used by more than 60,000 ecommerce and retail brands» (только вендор) | traction | https://www.prnewswire.com/news-releases/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2-302776288.html | Triple Whale via PR Newswire | 2026-05-19 | accessed 2026-09-02 | low | no
10. Moby 2 оркестрируется «across frontier AI models including GPT, Claude, and Gemini» | features | https://www.morningstar.com/news/pr-newswire/20260519cl62731/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2 | Morningstar (PR Newswire syndication) | 2026-05-19 | accessed 2026-09-02 | medium | no
11. Triple Whale pricing «based on a combination of your brand's annual GMV and the package you choose»; add-on'ы Retention $19/мес, Conversion $79/мес; повышение 30-50% в 2024, случай $329→$549 mid-contract | pricing | https://eightx.co/blog/compare/reviews/triple-whale-for-ecommerce-review | Eightx | unknown | accessed 2026-09-02 | low | no
12. Reddit: cost - главная причина ухода от Triple Whale, 6 из 54 тредов | sentiment | https://www.redditmaster.com/reddit-intelligence/triple-whale | RedditMaster | 2026 | accessed 2026-09-02 | low | no
13. Polar pricing: планы Core и Custom, GMV-селектор; Core включает «All Business Intelligence», «AI Agents», «Data Activations»; во всех планах «Unlimited users», «Dedicated Snowflake database», «Slack channel» | pricing | https://www.polaranalytics.com/pricing | Polar Analytics | unknown | accessed 2026-09-02 | high | yes
14. Polar pricing: агентского/multi-brand тарифа на странице нет; агенты Data Analyst, Media Buyer, Inventory Planner, Email Marketer упомянуты без привязки к плану | pricing | https://www.polaranalytics.com/pricing | Polar Analytics | unknown | accessed 2026-09-02 | medium | no
15. Peel Magic Dash: «Ask it a question and it will automatically generate a dashboard using your data»; scheduled reports/Slack/anomaly alerts в FAQ не упомянуты; «Your data is secure and is not being shared with an AI» | features | https://help.peelinsights.com/docs/magic-dash-faqs | Peel Insights Help | 2025-06-02 | accessed 2026-09-02 | high | no
16. Peel: «3x repeat purchases while cutting time spent on analysis by 90%» (маркетинг, без источника) | positioning | https://www.linkedin.com/posts/peel-insights_magic-dash-ai-retention-platform-for-d2c-activity-7136014723904409602-_ZhM | Peel Insights (LinkedIn) | 2023-12 | accessed 2026-09-02 | low | no
17. Lifetimely живёт внутри Amp: 301 с lifetimely.io на useamp.com, «© Copyright 2026 AMP» | trajectory | https://useamp.com/products/analytics/lifetime-value | Amp | 2026 | accessed 2026-09-02 | medium | no
18. Lifetimely/Amp predictive LTV: «uses AI to estimate future LTV of different segments»; метод, горизонт, overrides, сезонность на странице не раскрыты; daily/weekly отчёты и алерты не упомянуты | features | https://useamp.com/products/analytics/lifetime-value | Amp | 2026 | accessed 2026-09-02 | medium | no
19. Lifetimely predictive LTV (старый пост): горизонты 3/6/12/24 мес; модель «forecast the monthly sales of each individual customer over their lifetime»; в проде с ~04.2021 | features | https://www.lifetimely.io/blog-posts/new-predictive-ltv-model | Lifetimely | 2021-04 | accessed 2026-09-02 | low | no
20. Lebesgue: seed $3M (лид Interactive Venture Partners; Bridge Investments, Fil Rouge Capital, K20 Fund), объявлен 2025-01-21; основана 2018 | trajectory | https://app.dealroom.co/news/feed/lebesgue-secures-3m-for-ai-marketing | Dealroom | 2025-01 | accessed 2026-09-02 | medium | no
21. Lebesgue «trusted by 10,000+ eCommerce brands» - все источники повторяют один пресс-релиз | traction | https://www.bridgeventurefund.com/news/lebesgue-raises-3m-seed-round | Bridge Venture Fund | 2025-01 | accessed 2026-09-02 | low | no
22. Luca: отчёт «automatically every Monday morning» из Shopify, ad platforms, accounting, 3PL; таргет «Shopify and DTC stores between €1M and €5M» | features | https://ask-luca.com/blogs/ecommerce-reporting | Luca | unknown | accessed 2026-09-02 | low | no

## Паттерны, повторяющиеся у лидеров

1. **Спектр автономии вместо переключателя «вкл/выкл».** Shopify: «from approving every campaign before it runs to giving Campaign Autopilot more room» (Shopify, 2026-06-17, https://www.shopify.com/blog/introducing-campaign-autopilot); Triple Whale: «Copilot mode, where customers approve actions, or Autopilot mode … within predefined guardrails» (PR Newswire, 2026-05-19, https://www.prnewswire.com/news-releases/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2-302776288.html). Оба вышли в мае-июне 2026 - сходятся к одной модели: approve-each → autopilot-with-guardrails.
2. **Guardrails = бюджетные, не товарные.** Заявленные ограничители - месячный бюджет с автопаузой (Shopify), «predefined guardrails» без расшифровки (Triple Whale), channel budget floors и hard ceiling (WRKNG Digital, 2026-06-23, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review). Ни у кого не заявлен OOS-aware стоп рекламы - потенциальная дифференциация.
3. **Специалисты по одному KPI.** Triple Whale: три Moby Specialists «each purpose-built around a specific ecommerce KPI» (PR Newswire, 2026-05-19); Polar: Data Analyst / Media Buyer / Inventory Planner / Email Marketer (Polar Analytics, https://www.polaranalytics.com/pricing). Агент = роль в команде, а не «чат по данным».
4. **Автоматизация бесплатна на платформе, платна у независимых.** Shopify - «free for all brands on paid Shopify plans» (Shopify, 2026-06-17); Triple Whale и Polar - GMV-зависимый прайс (Eightx; Polar pricing). Цена - главная боль клиентов Triple Whale (RedditMaster, 2026).
5. **Ежедневный бриф - редкость; норма - еженедельный или «по запросу».** Luca - «every Monday morning» (Luca, https://ask-luca.com/blogs/ecommerce-reporting); WRKNG рекомендует еженедельный ритм для Autopilot; Peel и Lifetimely/Amp - ни брифов, ни алертов в документации. Ежедневный бриф в раунде 2 подтверждён только у Polar (Slack).
6. **Память решений (C) не реализована ни у кого**: релиз Moby 2 не содержит формулировок о сверке результатов действий (PR Newswire, 2026-05-19); у Shopify и Polar - тоже. Это пустая ниша.

## Лиды для следующего раунда

- Противоречие (приоритет): статус Microsoft Advertising в Campaign Autopilot - вендор (17.06.2026) «доступно», WRKNG (23.06.2026) «coming July 2026»; проверить Help Center changelog https://changelog.shopify.com/ по запросу «Campaign Autopilot».
- Противоречие: цены Triple Whale Foundation $219 / Automate $749 (wetracked.io, раунд 2) vs «$329→$549» и GMV-полосы (Eightx) - нужен третий источник; попробовать https://www.g2.com/products/triple-whale/pricing или https://apps.shopify.com/triple-whale (пользовательский агент/другой домен).
- Triple Whale: расшифровка «predefined guardrails» Autopilot-режима и наличие post-execution отчёта по действиям специалистов - искать https://www.triplewhale.com/blog/product-event (2 апреля 2026, найден в выдаче, не читали) и Stellagent https://stellagent.ai/insights/triple-whale-moby-2-ai-operating-system.
- Lebesgue «10,000+ vs 5,000+»: искать CB Insights customers https://www.cbinsights.com/company/lebesgue/customers и Shopify App Store (точное число установок/отзывов с датой).
- Lifetimely/Amp: дата и условия сделки; текущий прайс https://useamp.com/pricing; есть ли у Amp daily digest.
- Polar: выбрать GMV в селекторе (нужен JS) - цены Core/Custom; changelog Data Activations на предмет approval-gate Media Buyer Agent.
- Shopify: первоисточник «4x weekly active shops» (Q1 2026 shareholder letter, https://investors.shopify.com/).
- Новая сущность: Amp (useamp.com) как консолидатор Shopify-аналитики (Lifetimely) - проверить, что ещё поглощено.
- Не тронуты: Northbeam (anomaly alerts, agency workspace), Finsi, Tydo, Cometly, Relay Commerce; Peel - есть ли Slack/email digest вне Magic Dash (https://help.peelinsights.com/).
- Luca: второй публикатор (Product Hunt, Crunchbase, LinkedIn-посты основателей).

## Не нашёл

- Живой прайс Triple Whale и Wayback-снимки: triplewhale.com/pricing - 403, web.archive.org не фетчится инструментом; G2 reviews - 403. Тексты 1-3-звёздочных отзывов Triple Whale - по-прежнему только пересказы агрегаторов.
- Содержание guardrails Autopilot-режима Moby 2 (бюджет? ROAS? запасы?) - пресс-релиз молчит.
- Capability (C) - запись решения и сверка ожидаемого с фактическим - ни у Shopify Campaign Autopilot, ни у Moby 2, ни у Peel/Lifetimely.
- Capability (F) отзывы/вопросы покупателей и (G) аудит листинга/конкурентов - ни у одного из продуктов сегмента в этом раунде.
- OOS-aware поведение рекламной автоматизации (E) - не заявлено ни Shopify, ни Triple Whale, ни в независимом обзоре.
- Метод и горизонт прогноза (D): Moby 2 - «forecast inventory» без деталей; Lifetimely/Amp - «uses AI» без метода на живой странице (детали только в сниппете поста 2021 г.).
- Ежедневный бриф как функция у Peel и Lifetimely/Amp - отсутствует в документации.
- Цены Polar (Core/Custom) - страница требует выбора GMV, статический фетч цифр не отдаёт.
- Независимое (не из пресс-релиза) подтверждение «60,000 brands» Triple Whale и «10,000+ brands» Lebesgue.
- Второй публикатор по Luca - выдача содержит только собственный домен ask-luca.com.
- Northbeam - не исследована (бюджет исчерпан).
