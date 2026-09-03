# dtc-ai-operating-systems - независимая верификация (spot-check)

Дата проверки: 2026-09-02. Уровень: normal - только load-bearing утверждения, по одной независимой проверке на каждое. Бюджет: 12 вызовов инструментов (5 поисков, 4 fetch; из них 3 fetch неуспешны: triplewhale.com/pricing 403, apps.shopify.com/triple-whale 404, apps.shopify.com/lebesgue 404). Все URL - доступ 2026-09-02. Выводы только по страницам/выдаче, полученным в этом прогоне.

Правило независимости: синдикации пресс-релиза (Yahoo Finance, TMCnet, Morningstar, cision-зеркала) и trade-пересказы - это один и тот же upstream (сам вендор), а не независимые данные. Там, где подтверждение только такое, это явно указано.

## Сводка

| # | Утверждение | Статус | Независимый источник |
|---|---|---|---|
| 1 | Moby Agents - публичный запуск 23.07.2025, «proactive, autonomous AI agents … step-by-step recommendations» | verified (дата и формулировка; независимость слабая - синдикации/пересказы одного релиза) | TMCnet 23.07.2025; MarTech360; Practical Ecommerce (не прочитан) |
| 2 | Moby Agents: daily briefs, budget reallocation, one-click publishing в рекламные кабинеты | unverified (частично: «optimize spend» и «take action directly» есть; «daily briefs» и «one-click publishing» не подтверждены) | Morningstar/PR Newswire 19.05.2026 (Moby 2) |
| 3 | Sidekick Pulse: персонализированные рекомендации и next steps по рыночным трендам и данным магазина в админке | verified | what.digital; MESA (getmesa.com) - два независимых издателя |
| 4 | Sidekick Campaign Autopilot: early access, Facebook/Instagram/Shop/email, guardrails мерчанта | verified (первичный источник Shopify + независимый ContentGrip) | Shopify News Spring '26 Edition; contentgrip.com |
| 5 | Lebesgue: Free $0 / Ultimate $79 (10 вопросов Henri) / Ultimate AI $149 (Unlimited Henri, approved execution, budget allocation) | verified по живой странице цен (второго издателя нет - App Store 404) | lebesgue.io/pricing, прочитано 2026-09-02 |
| 6 | Polar Slack: авто-постинг daily/weekly briefs, агент Hermes (Nous Research) через MCP | unverified (подтверждено только страницами самого Polar; существование Hermes как OSS Nous Research подтверждено) | polaranalytics.com/hermes-ecommerce-ai-agent; github.com/nousresearch/hermes-agent |
| 7 | Compass: MTA+MMM+incrementality «in one calibrated system», еженедельная калибровка, Moby 2 опирается на эти данные | verified (формулировки; независимость слабая - синдикация релиза Moby 2) | Morningstar (PR Newswire) 19.05.2026 |
| 8 | Triple Whale pricing: Free $0 / Foundation от $219 / Automate от $749 / Enterprise; Moby Concierge - add-on | unverified (ни живая страница цен, ни App Store не открылись; источник дайджеста - третья сторона без даты) | - |

## Детали по утверждениям

### 1. Публичный запуск Moby / Moby Agents 23.07.2025

Поиск (prnewswire.com и triplewhale.com исключены) выдал синдикации того же релиза с датой 23.07.2025: TMCnet, https://www.tmcnet.com/usubmit/2025/07/23/10228453.htm ; Yahoo Finance, https://finance.yahoo.com/news/triple-whale-announces-public-launch-190100572.html ; cision-зеркала abc27/fox4kc (ID 20250723CL36491). Trade-пересказы: MarTech360 «Triple Whale Launches Moby, Agentic System for Insights», https://martech360.com/analytics/triple-whale-launches-moby-agentic-system-for-insights/ ; MarTechVibe, http://martechvibe.com/article/triple-whale-announces-public-launch-of-moby/ . В сводке выдачи воспроизведена формулировка «Moby Agents (proactive, autonomous AI agents that analyze complex data and deliver step-by-step recommendations to optimize spend…)», плюс упоминание беты Moby Agents с начала апреля 2025.

Независимая редакционная статья существует - Practical Ecommerce «Triple Whale's Moby AI Gets Things Done», https://www.practicalecommerce.com/triple-whales-moby-ai-gets-things-done (дата не установлена, не прочитана в рамках бюджета).

Вердикт: **verified** для даты и цитаты; подтверждение - синдикации и пересказы одного релиза, т.е. независимость по данным не достигнута, но для факта «релиз опубликован такого-то числа с такой формулировкой» это достаточно. Красный флаг: числа «$55 billion … 40,000 brands» - самоотчёт вендора, не проверялись.

### 2. Функции Moby Agents (daily briefs, budget reallocation, one-click publishing)

Первичная страница https://www.triplewhale.com/moby-agents в дайджесте не читалась (снипет). Независимый контекст: релиз Moby 2 (GA 19.05.2026) в синдикации Morningstar, https://www.morningstar.com/news/pr-newswire/20260519cl62731/triple-whale-unveils-the-ai-operating-system-for-ecommerce-with-the-launch-of-moby-2 : Moby 2 «can generate campaigns and creative, analyze performance, forecast inventory, build landing pages, monitor anomalies, and take action directly across ecommerce and marketing systems». Это подтверждает слой действий, но не конкретно «daily briefs» и «one-click publishing directly to ad platforms».

Вердикт: **unverified** (частичное совпадение). Важно для дайджеста: с 19.05.2026 продукт называется Moby 2 («AI-Operating System for Ecommerce»); страница moby-agents может быть устаревшей упаковкой.

### 3. Sidekick Pulse

Независимые издатели (shopify.com исключён из поиска): what.digital «Shopify Winter Edition 2026: New Features Overview», https://what.digital/shopify-winter-edition-2026-new-features/ ; MESA «What is Shopify Sidekick? Complete Guide for Merchants in 2026», https://www.getmesa.com/blog/shopify-sidekick ; Create8, https://www.create8.co.uk/shopify-sidekick-ai-review-what-is-it-and-what-can-it-do/ (даты публикаций в выдаче не показаны; все 2026). Сводка выдачи: Pulse «proactively monitors your store's performance and market trends», рекомендации выводятся «Pulse Card» на главной админки, каждая содержит «what's happening, why it matters … actionable next steps»; не все магазины eligible, требуется включить Shopify Network Intelligence.

Вердикт: **verified** (два независимых издателя). Уточнение для дайджеста: eligibility ограничена и требует Network Intelligence - это условие, а не «у всех в админке».

### 4. Sidekick Campaign Autopilot

Первичный источник найден: Shopify News «Selling everything, everywhere, all at once: The Spring '26 Edition», https://www.shopify.com/news/spring-26-edition-merchant : Campaign Autopilot «runs AI-powered marketing campaigns automatically across Facebook, Instagram, Shop, and email, and uses commerce intelligence to optimize over time within guardrails you set. It is now in early access». Независимый: ContentGrip «Shopify Campaign Autopilot brings AI campaign management to admins», https://www.contentgrip.com/shopify-campaign-autopilot/ - мерчант задаёт бюджет и guardrails, система исполняет и оптимизирует. Дополнительно wrkngdigital, https://wrkngdigital.com/post/shopify-campaign-autopilot-honest-review : сейчас работает на Meta ads, Shop Campaigns и Shopify Messaging (email); анонсированы Microsoft Advertising, ChatGPT Ads, Snapchat.

Вердикт: **verified**. Поправка к дайджесту: это Spring '26 Edition (выход 17.06.2026 по Digital Applied), а не Summer.

### 5. Lebesgue pricing

Живая страница https://lebesgue.io/pricing (Lebesgue, дата публикации не указана, прочитана 2026-09-02): Free $0/мес; Ultimate $79/мес - «Limited Henri AI access (10 business questions/month)»; Ultimate AI $149/мес - «Unlimited Henri AI analysis», «Approved AI marketing execution», «Budget allocation recommendations». Add-ons Le Pixel: Attribution $99-$1,499/мес и Enrichment $149-$1,649/мес по тиру выручки, требуют Ultimate или Ultimate AI. Листинг Shopify App Store https://apps.shopify.com/lebesgue - 404, второго издателя нет.

Вердикт: **verified** (бар свежести для pricing выполнен: живая страница на дату доступа). Поправка: в дайджесте не отражены revenue-based add-ons - «дёшево $0/$79/$149» верно только без атрибуции.

### 6. Polar Slack + Hermes

Выдача: Polar «Slack Integration», https://www.polaranalytics.com/integrations/slack и Polar «Hermes: Autonomous AI Agents for Ecommerce», https://www.polaranalytics.com/hermes-ecommerce-ai-agent (даты неизвестны): агент «powered by Hermes, the open-source AI agent from Nous Research, wired to your Polar data over MCP», «schedule the daily and weekly briefs so they post themselves», один агент на канал (#growth, #finance), рекомендуется guided deployment. Независимо подтверждено лишь существование Hermes Agent как OSS-проекта Nous Research: https://github.com/nousresearch/hermes-agent и https://hermes-agent.nousresearch.com/docs/ - упоминания Polar в снипетах нет.

Вердикт: **unverified** - обе подтверждающие страницы принадлежат вендору; capability-claim класса «два источника» не закрыт. Утверждение остаётся с флагом.

### 7. Compass (Triple Whale)

Синдикация релиза Moby 2 (PR Newswire, 19.05.2026) на Morningstar, https://www.morningstar.com/news/pr-newswire/20260519cl62731/... : Compass «combines multiple measurement methodologies into a single continuously calibrated system»; MMM «generates weekly AI-powered action plans identifying where brands should scale or reduce spend»; Incrementality Testing; MTA «deterministic, user-level attribution». Trade-пересказы: MarTechVibe, https://martechvibe.com/article/triple-whale-introduces-moby-2/ ; Stellagent, https://stellagent.ai/insights/triple-whale-moby-2-ai-operating-system . Независимый обзор существует, не прочитан: rule1.ai «Triple Whale review 2026», https://rule1.ai/articles/triple-whale-review .

Вердикт: **verified** по формулировкам «calibrated system» и еженедельному ритму; «every recommendation from Moby 2 … informed by that trusted data automatically» дословно в выдаче не найдено, но Moby 2 позиционируется поверх Compass в том же релизе. Независимость - как в п.1, слабая (один upstream).

### 8. Triple Whale pricing 2026 (wetracked.io)

https://www.triplewhale.com/pricing - 403; https://apps.shopify.com/triple-whale - 404. В выдаче есть сторонние разборы цен, не прочитанные в бюджете: rule1.ai (2026), https://rule1.ai/articles/triple-whale-review ; skywork.ai (2025), https://skywork.ai/skypage/en/Triple-Whale-Pricing-in-2025... . Цифры $219/$749 и статус Moby Concierge как add-on ни одним полученным источником не подтверждены и не опровергнуты.

Вердикт: **unverified**. Дополнительный риск: источник дайджеста - третья сторона без даты, а упаковка могла измениться с запуском Moby 2 (19.05.2026); бар свежести для pricing (≤3 мес, живая страница) не выполнен. Нужен ручной просмотр pricing-страницы в браузере.

## Что важно для дайджеста

1. Terminology: Triple Whale с 19.05.2026 продаёт «Moby 2» как «AI-Operating System for Ecommerce» - формулировка сегмента «DTC AI operating systems» подтверждается самим вендором, но по пресс-релизу.
2. Shopify: Campaign Autopilot - Spring '26 Edition (не Summer); Pulse требует eligibility + Network Intelligence.
3. Lebesgue: дешёвый тариф - без атрибуции; с Le Pixel цена растёт до $99-$1,649/мес по выручке.
4. Не подтверждены: pricing Triple Whale, Hermes-Polar вторым издателем, «daily briefs»/«one-click publishing» у Moby Agents.
