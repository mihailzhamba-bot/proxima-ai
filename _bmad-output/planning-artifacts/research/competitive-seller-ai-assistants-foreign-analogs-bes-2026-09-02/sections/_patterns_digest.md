### 3. Реклама и retail media: автоматизация с guardrails

#### 3.1 Кто в поле (лидеры, челленджеры, wildcard)
- **Лидеры (enterprise / multi-retailer, цены не публикуют).** Pacvue - «100+ retailers», «30+ global markets» [301], Pacvue Agent с «approval-based execution with clear guardrails» [300][305]; Skai - Celeste AI, «8,200+ brands», «300+ publishers» [329] (self-reported; уверенность: низкая); Quartile - платформа + full-service («dedicated account support»), «5,300+ Customers Globally in Over 32 Countries» [325] (self-reported; уверенность: низкая). Perpetua - лидер SMB/mid-market с публичной ценой [310].
- **Челленджеры (SMB / mid-market, публичные цены).** Teikametrics - «Artificial Retail Intelligence», suite Ads + Catalog + Inventory + Insights [318]; Adbrew - «правила + AI», «Retail-aware Ad Optimization» [333][334]; m19 - low-cost autopilot от $59/мес [335]; Helium 10 Ads (Adtomic) - реклама внутри all-in-one подписки [339].
- **Платформенный игрок.** Amazon Ads: Ads Agent (unBoxed, 2025-11-11) [341], Ads Agent в AMC «(beta)» [342], MCP Server (open beta, 2026-02-02) [343], Creative Agent и Full-Funnel Campaigns [344][345].
- **Wildcard.** SellerStack - узкий продукт «inventory protection»: ступенчатое снижение ставок по days-to-stockout с авто-восстановлением [354] (unverified - единственный источник, страница вендора).
- **Разметка рынка третьей стороной.** atom11 делит поле на «AI-driven, black-box style bid optimization» (Perpetua, Quartile) и «rules-based, 'you set the guardrails' control» [306] (уверенность: низкая - агрегатор без даты).
- **Не покрыты (только сниппеты).** atom11 «Auto-adjusts bids & budget based on inventory rules» [355], Indition SellerTools - правила паузы по инвентарю на ASIN [356]; Optmyzr [350], Jinnify, Xneeti - не исследованы как продукты.

#### 3.7 Паттерны, которые стоит перенять
1. **Порог остатков как штатный guardrail, работающий до стокаута.** Платформа сама останавливает SP/SD только по факту OOS [350][313]; ценность - в low-stock зоне: m19 «Inventory Threshold» уже в тарифе за $59 [335][338]; Pacvue - авто-пауза по «weeks of inventory on hand» и bid-down [302], пауза на уровне креатива при OOS / потере Buy Box [303]; Perpetua - порог FBA/FBM с рекомендацией pause/enable [312]; Teikametrics - «sync advertising with real-time inventory signals» [321]; SellerStack - ступени 25/50/90/99% с авто-восстановлением при 30 днях запаса [354] (unverified).
2. **Переключатель «авто / с подтверждением» на уровне каждого правила.** Оба режима сосуществуют: Amazon Ads Agent - «Campaigns only launch after you review and approve» [341][348]; Perpetua - рекомендация с ручным accept/dismiss, авто-паузы нет [312]; Pacvue - «governed workflows» рядом с авто-исполняющей Rule Library [301][302][305].
3. **Guardrails задаются на уровне цели/сегмента, и «дыры» документируются честно.** Perpetua: min/max на сегмент, placement multipliers могут пробить лимит [315]; m19: target daily/monthly spend, TACOS [335][336]; Pacvue: «Automated budget pacing & overspend stops» [303].
4. **«Что изменилось и почему» - обещают все, документирует никто: окно для памяти решений.** Pacvue «full record of what changed and why» [300][305], Skai «the 'what' and the 'why'» [330]; ближайшее к оценке исхода - совет Amazon ждать «at least 2 weeks» [346] и timestamp предложений у Helium 10 [339]. Авто-сравнение ожидаемого и фактического не показал ни один продукт.
5. **Честная плашка задержки данных (T-1).** Perpetua прямо предупреждает «It may take up to 24 hours for inventory data to sync from Amazon» [312] - утренняя цепочка по остаткам везде опирается на вчерашние данные.
6. **Почасовые данные (Amazon Marketing Stream) как база интрадня и dayparting.** Perpetua Growth [310], Adbrew [333], m19 Professional [335][336], Pacvue (dayparting подтверждён SmartScout) [309].
7. **Слой approval/лимитов поверх нативных «рук» платформы.** MCP Server даёт агентам create/update/delete без описанных guardrails [343], AMC-агент ограничен контролем «query logic» [342] - место для стороннего продукта с лимитами и журналом.
8. **Self-serve с объяснимостью и «кнопкой стоп» против болей managed-модели.** Жалобы Quartile 1-2★ - непрозрачные действия, невозможность выйти, скрытый 30-дневный notice [328].
9. **Ценообразование «фикс + % от ad spend» с порогом самообслуживания.** Perpetua [310], Teikametrics [318], m19 [335], Adbrew «whichever is greater» [333]; email - единственный подтверждённый канал алертов (Pacvue [302], Teikametrics [321][323]), Slack/push/расписание не подтверждены ни у кого.
10. **Digital shelf / SOV / commerce-ops внутри рекламного продукта.** Perpetua SOV и organic rank [310], Adbrew Digital Shelf Analytics [333], Skai Content Optimization и Ticketing Automation с «~80% of issues resolved in under 2 days» [330][331].

#### 3.8 Что не нашли и открытые вопросы
- **Область C** - ни у одного из продуктов: запись решения с последующим сравнением ожидаемого и фактического эффекта; ближайшее - Pacvue «full record» (заявление) [300][305], Amazon «2 weeks» [346], Helium 10 timestamps [339].
- **Область F** - нигде в сегменте рекламных платформ.
- **Область A** с фиксированным временем и каналом (Slack/push) - нигде; подтверждены только email [302][321][323] и in-account рекомендации [312].
- **Pacvue audit trail / change log** - в документации не найден; сниппет «full transparency via logs» vs прочитанный текст без логов [303] (disputed); второй издатель по inventory rules не получен - статья Amazon Ads о Pacvue отдала библиотеку без содержимого [353]; G2 Pacvue - HTTP 403 [300]; «Net PPM» - только вендор [300].
- **Amazon Ads Agent для SP-only селлеров** - источники расходятся [340][341][347] (disputed, открыто); guardrails/permissions MCP Server (возможны ли read-only credentials) - в анонсе нет [343]; расхождение даты страницы CES 2026 (2025-01-09 vs заголовок) [344].
- **Teikametrics** - метод прогноза (окно, сезонность), overrides, логика reorder не документированы [324]; 16 help-статей раздела Inventory не прочитаны [322].
- **Adbrew** - OOS-поведение, каналы алертов, approval: /features 404, /pricing даёт только названия фич [333]; «5000+ Brands» без второго источника [334].
- **Skai** - маршрутизация и approval тикетов, каналы алертов [331]; дата пресс-релиза «agent-native operating system» [329]; датированный анонс партнёрства с Carbon6 [332]; «8,000 brands» и «over 50 clients» без второго издателя [330].
- **Perpetua** - канал доставки Inventory Recommendations (email vs in-app) [312]; статьи «Advanced Settings for Sponsored Products Goals» и «Stream - Automated Intraday Bid Schedule» не читались [315].
- **Helium 10 Ads** - inventory в правилах и канал «Alerts» (email/push) не проверены [339].
- **SellerStack** - unverified: стороннего покрытия продукта не найдено [354].
- **m19** - механика «Inventory Threshold» (bid-down или pause) на странице цен не раскрыта [335]; «Target monthly spend», «Peak season Boost» - только вендор [336].
- **Не покрыты** как продукты: Optmyzr [350], atom11 [355], Indition SellerTools [356], Jinnify, Xneeti; Amazon Creative Agent [351] и Campaign Manager beta [352] - только заголовки.
- **Финансирование и найм** - данных нет ни по одному вендору; цены Pacvue, Skai, Quartile не публикуются [300][329][325].

---

### 1. Аналитика и алерты для Amazon-селлеров

#### 1.1 Кто в поле (лидеры, челленджеры, wildcard)
Карта - оценка исследователя по итогам раундов, не факт из источника.

| Роль | Продукт | Почему здесь |
|---|---|---|
| Лидер | Helium 10 | Сьют «всё-в-одном», упаковка по обороту продавца; AI-агент «Helium» и полноценные алерты - в верхних тарифах [100]; агент запущен 24.08.2026 [107] |
| Лидер | Jungle Scout | Сьют; линейки Catalyst (до $1M оборота) и Cobalt ($1M+, custom через демо) [118] |
| Челленджер | Sellerboard | Профит-аналитика + алерты + прогноз запасов за $19-79/мес [121]; Trustpilot 4.6 [122] |
| Челленджер | SellerApp | Аналитика + PPC-автоматизация: freemium → $149/мес + managed-планы [137]; пороговые алерты [138] |
| Челленджер | Perpetua (ex-Sellics) | Ads-автоматизация «goals, not campaigns» от $695/мес [143][145]; Sellics объединён с Perpetua («joins forces»): sellics.com → 301 на perpetua.io [146][147] |
| Челленджер | DataHawk | Enterprise-аналитика для брендов и агентств (white-label отчёты), цены по demo [139] |
| Wildcard | Amazon Seller Assistant (ex-Project Amelia) | Бесплатный agentic-ассистент самой площадки; действует с разрешения селлера [129][131] |
| Wildcard | DataHawk Sherlock + DataHawk MCP | Агент «аномалия → причина → действие» в private beta [140][141]; «спроси свои данные» через Claude/ChatGPT/Cursor [142] |
| Замечены, не разобраны | Nova Analytics, Seller Sprite, SellerStacked, Indellia, Aelestra | Nova: SKU-level P&L, 21 маркетплейс, «200+ metrics» (vendor-описание, уверенность: средняя) [134]; Seller Sprite использован как источник, не как продукт [133]; SellerStacked не проверен; Indellia/Aelestra - ответы на отзывы, область F [150][151] |

#### 1.7 Паттерны, которые стоит перенять
1. **Разрешение перед действием; уровень автономии - по типу операции, не глобально.** Amazon: «If the seller approves, Seller Assistant implements the solution» [129], «with their permission» [130]; агент Helium - только анализ и рекомендации, write позже [107][113]; Helium 10 Ads Suggestions - «checkmark to apply» / «X to defer» [106] (сн.); Sherlock - «advises - it does not automate» [140]; Perpetua - стратегия не меняет цели автоматически [144] (unverified). Режимы «suggest only»/«auto-approve» по категориям задач - только у вторичных источников об Amazon [134] (disputed), но как модель настройки стоит взять.
2. **Цепочка «изменение → наиболее вероятная причина → следующее действие».** Sherlock [140][141]; DataHawk MCP: «Why did revenue drop last week?» → основной драйвер (Buy Box loss) → сопутствующие факторы → «Next step» [142]; агент Helium: «Your margin dropped from 22% to 18% this month. Higher TACOS on your top ASIN is the main reason» → «Fix the listing on this ASIN first, then move budget…» [113][107]. У Helium 10 Alerts, Sellerboard, SellerApp - только «что случилось» [101][121][138].
3. **«Спроси свои данные» (MCP/чат) как форма диагностики.** DataHawk MCP - Claude, ChatGPT, Cursor, n8n, 10+ доменов данных, 180 дней истории [142]; Helium 10 MCP Connector [109][107][100]; Jungle Scout AI Assist с квотами на план [119].
4. **Мониторинг листинга + Buy Box + отзывов как базовая защита.** Helium 10 - изменения image/title/bullets/price + исторические скриншоты [101]; Sellerboard [121]; SellerApp - Hijacker/LQI/Buy Box [138]; DataHawk - Buy Box [139].
5. **Журнал действий с атрибуцией источника есть, журнала ожиданий нет.** Helium 10 Ads Change Log: «approved Suggestion that came via a rule» / вручную / Seller Central, фильтр «Change By» [104] (сн.). Ни один продукт не фиксирует ожидаемый эффект решения и не сверяет его с фактом - свободная ниша для области C.
6. **Рекламные guardrails через цели и пороги.** Perpetua: target ACoS + дневной бюджет на goal, сезонные автоповышения («Prime Day … +75%») [143]; Helium 10: bid («clicks exceeding a specific number») / harvest / negative («clicks with no sales within a specific period») / budget rules [105] (сн.); OOS-порог с рекомендацией паузы - Perpetua [144] (unverified). Sellerboard «target profitability or ACOS» [121] - глубина оспорена [126].
7. **Прогноз запасов = прозрачная арифметика с ручными коэффициентами, не ML.** Sellerboard: взвешенная скорость продаж + сезонные коэффициенты (дефолт/ручные) + % роста [123]; Amazon - «comparing historical data with current trends» [129]; никто из проверенных не заявляет ML-метод. Для селлера важны видимость метода и override.
8. **Три ритма: пороговые алерты - мгновенно, предложения - раз в неделю, дайджест - опционально.** SellerApp «instant», 24*7 [138]; Helium 10 Ads - «revisit it the following week», новые предложения через 7-10 дней [106] (сн.); Helium 10 email-алерты с режимом «daily» [116] (сн., уверенность: средняя) - ближайший аналог утреннего дайджеста. Приоритизированной утренней сводки нет ни у кого.
9. **Публичная метрика качества рекомендаций.** Amazon - «over 90%» принятых рекомендаций [135] (vendor) - единственный найденный показатель; сторонние тулы такого не публикуют.
10. **Прозрачный прайс как контрпункт ценовой боли лидера.** Helium 10: 38% единиц на Trustpilot, «Removing features while holding the price is a price increase», скрытые продления [110]; Perpetua - от $695 + % от ad spend [145]; Sellerboard хвалят за «unbeatable» цену [122] и месяц trial без карты [121].
11. **Ответы на отзывы: черновик → очередь → человек одобряет/правит/пропускает (или автопилот по правилам).** Есть как категория: Indellia Response Agent (Beta) - «drafts replies for every new review … a queue with pre-filled drafts that a human approves, edits, or skips», Amazon/Walmart/Bazaarvoice/Trustpilot [150]; Aelestra - «Suggestive Mode» / «Auto-Pilot … based on your rules», Google/Yelp [151] (оба - сн., уверенность: низкая). У семи продуктов сегмента не найдено.

#### 1.8 Что не нашли и открытые вопросы
- Утренний бриф с фиксированным временем, каналом и приоритизацией - ни у одного из 7 продуктов. Оговорка: email-режим «daily» у Helium 10 [116] (сн.); пост sellerboard «Automated Reporting for Amazon Sellers» (2025-05-19) не открыт.
- Область C (запись решения, «ожидание vs факт») - нигде; у Amazon только vendor-метрика принятия [135].
- Область D: метод прогноза найден только у Sellerboard [123], горизонт не назван; Helium 10, Jungle Scout, DataHawk, Amazon - метод/горизонт/сезонность/overrides не раскрыты [100][119][139][129].
- Область F: черновики ответов на отзывы/вопросы с одобрением - ни у одного из 7; Jungle Scout Review Automation оказался сбором отзывов [120].
- Helium 10: KB 403 три раунда - OOS-логика в Ads и авто-применение без одобрения не проверены [105][106]; конфликт «MCP для Diamond+» [107] vs «free up to 1,000 calls» [100] не разрешён; первичный GlobeNewswire не открыт (timeout) [108]; принадлежность (в r2 упомянут Pacvue в заголовке без источника) не проверена; G2/Capterra как второй набор по sentiment не смотрели.
- Amazon: первичного анонса EU/UK и режима auto-approve нет [129]; дата публикации статьи About Amazon неизвестна; traction «230,000 / >90%» - один издатель [135]; страница canvas не открыта [136].
- Jungle Scout: помесячный ряд цен ($49/$79/$149) с живой страницы не извлечён [119]; есть ли Alerts как функция - не найдено [119].
- Perpetua: владелец (IPG / Flywheel / Omnicom) - только косвенная ссылка Careers [145], страница Sellics молчит [147]; OOS-рекомендация - единственный источник, help-статья не открывалась [144]; дата объединения Sellics с Perpetua не найдена.
- Sellerboard: канал/время алертов и горизонт прогноза не найдены; «new sellers» и «ASIN changes» независимо не подтверждены [121]; глубина bid automation - спор [126] vs [127]; Trustpilot [122] независимо не проверялся.
- DataHawk: «1,200+ users» - vendor [139]; цены Sherlock после запуска и MCP - нет [140][142]; независимых свидетельств о качестве диагноза Sherlock нет (beta).
- Финансирование и найм по всем продуктам - не исследовались.
- Новые сущности без разбора: Nova Analytics (прайс, алерты) [134]; Seller Sprite как продукт [133]; SellerStacked; Indellia - реальный продукт или лендинг [150].

---

### 4. AI-операционки для DTC/Shopify-брендов и агентств

#### 4.1 Кто в поле (лидеры, челленджеры, wildcard)
**Лидеры (платформа + агент + слой действий).**

- **Triple Whale - Moby 2 (+ Compass).** Публичный запуск Moby Agents 23.07.2025 как «proactive, autonomous AI agents that … deliver step-by-step recommendations» [400] (verified по дате и формулировке; независимость слабая - синдикации и пересказы одного релиза [452][453]). 19.05.2026 - GA Moby 2, вендор называет продукт «AI Operating System for Ecommerce» [407]; три «Moby Specialists» (Media Buyer, Creative Director, Conversion Optimizer), режимы Copilot (человек одобряет действия) и Autopilot (исполняет «within predefined guardrails») [407]. Compass - измерительный слой (MTA + MMM + инкрементальность «in one calibrated system», еженедельная калибровка), на который опираются рекомендации Moby 2 [403][405][408] (verified по формулировкам, один upstream); Compass позиционируется для omnichannel-брендов, «selling DTC, on marketplaces, and through retail partners» [404] (снипет; уверенность: средняя).
- **Shopify - Sidekick + Sidekick Pulse + Campaign Autopilot.** Pulse (Winter '26): проактивные «personalized recommendations and next steps for your business using market trends and data from your store» на главной админки [413] (verified двумя независимыми издателями [422][423]); поправка верификации - не для всех магазинов: требуется eligibility и Shopify Network Intelligence [422][423]. Campaign Autopilot (Spring '26, 17.06.2026, early access): AI-кампании в Meta / Shop Campaigns / Shopify Messaging / Microsoft Advertising с approve/reject и guardrails мерчанта [418][420] (verified [419][424]).

**Челленджеры.**

- **Polar Analytics** - BI на выделенном Snowflake + «AI Agents» + Headless MCP + брифы в Slack по расписанию [435][436][437]; Slack-агент - на открытом Hermes (Nous Research) через Polar MCP [435] (unverified вторым издателем).
- **Lebesgue** - Auditor (ежедневный аудит рекламных аккаунтов) + Henri AI («root-cause analysis · step-by-step growth strategy»), позиционирование «AI CMO» [426]; вход $0 / $79 / $149 в месяц [427] (verified по живой странице; без атрибуции - см. 4.3).
- **Lifetimely (внутри Amp)** - P&L/LTV + «AI Profit Agent (paid tiers)» + Slack-алерты [441]; lifetimely.io редиректит на useamp.com, «© Copyright 2026 AMP» [442].
- **Northbeam** - атрибуция / MMM / инкрементальность; AI-ассистента, брифов и алертов нет ни в блоге [444], ни на прайсе [445]; «дежурный» - человек (Dedicated Media Strategist на Professional) [445].
- **Peel Insights** («A Relay Commerce Company») - когорты/ретеншн; Magic Dash - генератор дашбордов по вопросу [447][448].

**Wildcard.**

- **Polar Headless MCP + Hermes**: «аналитика как MCP-сервер, агент любой» - семантический слой «400+ pre-built ecommerce metrics» открыт внешнему агенту (Hermes / Claude / ChatGPT) [436][437][439]; существование Hermes как OSS-проекта Nous Research подтверждено [440], связка с Polar - только страницами вендора (unverified).
- **Luca (ask-luca.com)** - «AI CFO» + revenue-based financing: root-cause по SKU-марже, правила-алерты («Tell me if cash runway dips below 60 days»), «You approve, the system pushes», еженедельный отчёт «every Monday morning» [450][451]; единственный источник - сам вендор (уверенность: низкая).

Не исследованы (лиды): Finsi, Tydo, Cometly, Relay Commerce, периметр консолидации Amp.

#### 4.7 Паттерны, которые стоит перенять
1. **Спектр автономии, а не тумблер «вкл/выкл».** «from approving every campaign before it runs to giving Campaign Autopilot more room as campaigns evolve» (Shopify) [420]; «Copilot mode, where customers approve actions, or Autopilot mode, where Moby executes autonomously within predefined guardrails» (Triple Whale) [407]; «You approve, the system pushes» (Luca) [450]; «every metric, threshold, and agent action is editable and stays up for human review» (Polar) [436]; «Approved AI marketing execution» (Lebesgue) [427]. Два лидера сошлись на модели approve-each → autopilot-with-guardrails в мае-июне 2026 [407][420].
2. **Бриф в Slack по расписанию, привязанный к ритуалу команды.** «Daily briefs post automatically each morning before standup», weekly «every Monday at 7am», «Tell Polar once … It runs on a schedule and posts to the channel» (Polar) [435] - единственное задокументированное время доставки в сегменте (unverified вторым издателем); еженедельный «every Monday morning» (Luca) [451]; Slack-алерты AI Profit Agent (Lifetimely) [441]; «Automated insights via Slack/email» (Peel) [447].
3. **Аномалия всегда с причиной; действие - черновик в трекере с владельцем.** «A CAC spike, a revenue drop, a channel that fell off» «with the reason» → «Draft the reallocation and put in Notion» [435]; Weekly Team agents → Notion-трекер, «each tagged with owner, priority, and the numbers behind it» [436] (Polar). Ближайший в сегменте суррогат памяти решений - и он живёт вне аналитики.
4. **Карточка рекомендации «что происходит → почему важно → следующие шаги».** Pulse Card (Shopify) [422][423]; Henri «clear explanations · root-cause analysis · step-by-step growth strategy» (Lebesgue) [426]; «step-by-step recommendations» (Triple Whale) [400].
5. **Агент = роль с одним KPI, а не «чат по данным».** Moby Media Buyer / Creative Director / Conversion Optimizer, «each purpose-built around a specific ecommerce KPI» (Triple Whale) [407]; Data Analyst / Media Buyer / Inventory Planner / Email Marketer (Polar) [436][437].
6. **Доверенные цифры - отдельный слой под агентом.** Compass → «every recommendation from Moby 2 … is informed by that trusted data automatically» [403][408]; «reads governed metrics over the Polar MCP, so every answer is first-party and sourced» [435]; сверка платформенных метрик с банковскими данными (Luca) [450].
7. **Данные как открытый слой (MCP / Snowflake), а не закрытый ассистент.** Polar Headless MCP «400+ pre-built ecommerce metrics (semantic layer)», dedicated Snowflake, unlimited users [437]; внешний агент (Hermes / Claude / ChatGPT) поверх [436][439]; Snowflake data access (Peel) [447].
8. **Guardrails рекламы - бюджетные, с автопаузой.** Месячный бюджет, «Campaigns pause automatically when you reach your budget», правила «что Autopilot может и не может» [420]; чек-лист обозревателя: себестоимость для margin-adjusted ROAS, channel budget floors, Meta pixel + Conversions API, жёсткий потолок бюджета [421]. OOS-aware стоп рекламы не заявлен никем [407][420][421] - место для дифференциации.
9. **Дешёвый вход + дозировка AI.** 10 вопросов Henri в месяц на $79, unlimited на $149 (Lebesgue) [427]; Free до 50 заказов (Lifetimely) [441]; бесплатный Sidekick / Autopilot на платформе [415][420].
10. **Мониторинг конкурентов как отдельные агенты.** Echo («decodes competitors' email strategies to reveal product launches and discounts»), Sentinel («real-time competitor ad monitoring») (Lebesgue) [426].
11. **Антипаттерн - GMV-привязанный прайс с докупаемыми модулями.** Главная боль клиентов Triple Whale [409][410][411][412]; на ней строится позиционирование Lebesgue [430].

Пустая ниша, подтверждённая тремя раундами: (C) запись решения и сверка «ожидали → получили через N дней» - ни у Moby 2 [407], ни у Shopify [420][421], ни у Polar [436], ни у Peel / Lifetimely [448][442].

#### 4.8 Что не нашли и открытые вопросы
- **Triple Whale - первичные страницы закрыты.** pricing, moby-agents-agencies, blog/moby-2, статьи KB - 403 (три раунда + верификация); Wayback не фетчится; G2 - 403; App Store - 404 [406][409][454]. Открыто: живые цены и агентский workspace; содержание «predefined guardrails» Autopilot-режима; есть ли post-execution отчёт по действиям Specialists; что изменилось между Moby Agents (07.2025) и Moby 2 (05.2026). Непрочитанные лиды: Practical Ecommerce («Triple Whale's Moby AI Gets Things Done»), rule1.ai (2026), Stellagent, skywork.ai (2025), пост «product event» 02.04.2026.
- **Незакрытые области.** (C) - ни у кого; (F) - ни у кого; (G) - только конкуренты (Lebesgue) [426]; OOS-aware поведение рекламной автоматизации (E) - ни у кого; метод и горизонт прогноза (D) - только «90-day cash projection» (Luca) [450] и горизонты 3/6/12/24 мес LTV в посте 2021 г. [443]; время суток daily brief - только Polar [435].
- **Shopify.** Первоисточник «4x weekly active shops» (Q1 2026 shareholder letter) [416]; статус Microsoft Advertising в Autopilot ([420] vs [421]); канал и расписание Pulse-рекомендаций; критерии eligibility Pulse [422][423]; отзывов мерчантов на Autopilot нет.
- **Lebesgue.** «10,000+» vs «5,000+» брендов [426] - независимого подтверждения нет, внешние повторы идут из одного пресс-релиза [432]; 120 vs 126 отзывов [428][429]; тексты 1-2★; верхняя граница Le Pixel [427].
- **Polar.** Суммы Core / Custom (нужен выбор GMV в селекторе) [437]; approval-gate у Media Buyer Agent и связь с Inventory Planner Agent (оба Waitlist) [436]; независимое подтверждение Hermes-интеграции [435][439][440]; агентские multi-brand планы.
- **Luca.** Второй издатель (Product Hunt, Crunchbase) - выдача содержит только ask-luca.com [450][451].
- **Lifetimely / Amp.** Дата и условия сделки, текущий прайс Amp, наличие дайджестов у Amp [442]; периметр консолидации Amp.
- **Не исследованы.** Northbeam - алерты и agency workspace (первичный блог 2024 г. устарел [444]); Finsi, Tydo, Cometly, Relay Commerce; Peel - Slack/email digest вне Magic Dash [448]; обзор Create8 по Sidekick не прочитан.
- **Голос клиентов.** Ни для одного лидера не прочитан первичный 1-3★ отзыв; Polar, Northbeam, Peel, Luca - без отзывов вообще.

---

### 2. Прогноз спроса и запасов для e-commerce селлеров

#### 2.1 Кто в поле (лидеры, челленджеры, wildcard)
Классификация - по зрелости и объёму из дайджестов; независимых данных о долях рынка нет (уверенность: средняя).

- **Лидеры.** Inventory Planner (Sage) - enterprise/retail, цены только по запросу, «unlimited users at no extra cost», «Go live in 4 weeks (on average)» [206]; в Shopify App Store с 2013 г., 130 отзывов [208]. SoStocked (Carbon6) - Amazon-специфичный, продажа через звонок [200][203]. RestockPro (eComEngine) - Amazon FBA, самый дешёвый вход среди лидеров: от $49/мес [224].
- **Челленджеры.** Flieber - multi-channel, «AI-powered demand forecasting», без публичного прайса, 14-дневный триал без карты [211]. Prediko - Shopify-first, AI-агент Pia в Slack/email/чате [215][216].
- **Wildcard.** Inventory Hero - «launched 2026», работает внутри Claude как MCP-сервер, «Drafted POs, flagged reorders, and priced lost sales, ready for your approval» [228]; наличие MCP-сервера подтверждено сторонним реестром [229] (verified). Stockful - Shopify, отдельная модель на каждую пару SKU×локация, плоский прайс от $19.99/мес, позиционируется как замена Shopify Stocky [239] (уверенность: средняя - один вендорский источник).
- **Нативный инструмент платформы.** Amazon MIL - метрика на FBA Inventory page с рекомендованными количествами и ship-by датами, привязана к low-inventory-level fee с 2024-04-01 [236].
- **Смежный (область E).** Scale Insights - чистая PPC-автоматизация, прогноз спроса не заявлен, OOS-aware правил нет [238].
- **Выбыли.** Forecastly - куплен Jungle Scout в 2018, закрыт 15.09.2021, функции перенесены в Jungle Scout Inventory Manager [230][231]; Cogsy - «discontinued», «part of Mayple» [234]; Shopify Stocky - «discontinued August 31, 2026» по утверждению Stockful [239] (уверенность: низкая - второго источника нет).

#### 2.7 Паттерны, которые стоит перенять
1. **Ежедневная выдача «что требует внимания» в канал команды; расписание задаёт пользователь.** Носители: Prediko Pia - четыре ежедневных блока по email/чату/Slack [215][217]; Stockful - low-stock alerts в Slack по правилам [239]; Sage Copilot - приоритеты внутри приложения [207]. Фиксированного утреннего времени нет ни у кого - свободная позиция для Proxima.
2. **Рекомендация = количество + дата + ссылка на действие; черновик PO, одобрение человека как статус документа.** Носители: Inventory Hero «ready for your approval» [228][229]; Prediko - direct links в чате и draft POs [215], статусы Draft → Sent for Approval → Approved [218]; SoStocked «Generate quick POs» [200]; Amazon - ship-by дата + количество [236]; Scale Insights - preview changes перед применением [238].
3. **Именованные компоненты прогноза как источник доверия.** Сезонность, тренд, промо, lead time, MOQ, safety stock, Prime Day называются явно: Inventory Planner [205], SoStocked [200][202], Inventory Hero [228][229], Stockful [239]. Горизонт назван у Inventory Hero (30/90/365) [228], Prediko (12 мес) [215], SoStocked (12 мес, независимо) [202], Stockful (пример 90 дней) [239].
4. **Самоконтроль точности прогноза вместо памяти решений.** Pia «Forecasts that need revisiting due to accuracy» [215]; Stockful «Self-tracked accuracy» [239]. Это сверка прогноз/факт, не запись решения человека и его исхода - область C свободна.
5. **Аномалия с вероятной причиной.** Stockful «spikes & drops with likely causes» [239]; Pia «Follow up to understand root causes» через чат [215]. Только новые игроки, только вендорские источники (unverified).
6. **Прайс по объёму, все функции в каждом плане.** RestockPro [224], Stockful [239], Prediko [216], Inventory Hero [228]; «No hidden costs or charges based on a percentage of sales» - RestockPro [224].
7. **Агент внутри LLM-клиента через MCP.** Inventory Hero [228][229] - verified; Prediko - только заявка в блоге [220] (уверенность: низкая).
8. **Постоянная командная память («AI Employee Handbook»).** Inventory Hero [228][229] - память контекста, которую можно расширить до памяти решений.
9. **Экономический триггер как мотивация - и его обратная сторона.** Amazon MIL строится вокруг штрафа [236] и получает жалобы на игнорирование сезонности, in-transit и намеренного sell-out [236] - анти-паттерн: метрика без ручных overrides.
10. **Разрыв ads × inventory.** Scale Insights не знает про OOS [238]; у инвентарных инструментов только «Sync purchasing with campaigns» без деталей [206] - область E не занята.

#### 2.8 Что не нашли и открытые вопросы
- **(C) Память решений** с проверкой «ожидаемое vs фактическое» - ни у одного продукта; ближайшее - контроль точности прогноза (Pia [215], Stockful [239]) и Handbook (Inventory Hero [228]).
- **(E) OOS-aware ads-guardrails** - нигде [238][206].
- **Фиксированное время дайджеста** - нигде; Pia «daily» без времени [215].
- **Объяснение «почему»** у классических инструментов (RestockPro [224], Inventory Planner [207], Amazon [236]) - не задокументировано.
- **Горизонт и ручные overrides** - не найдены у Inventory Planner, Flieber, SoStocked, RestockPro (кроме «stock coverage days» и модели на товар у Inventory Planner [205]).
- **Первичные цены:** SoStocked (403 / «Book a Call» [203]), Inventory Planner [206], верхние ступени Prediko [216]; Flieber - сайт против листинга [211][214].
- **Независимые отзывы 1-3★ ≤12 мес** - только Inventory Planner [208][210]; для SoStocked [204], Flieber, Prediko, Inventory Hero, Stockful, RestockPro [226] - нет.
- **Prediko:** ни одно утверждение о Pia не подтверждено вне prediko.io [221]; неясно, может ли Pia переводить PO дальше «Draft» [218][219]; MCP - только блог [220]; даты changelog - помесячные метки или точные [217].
- **Sage Copilot:** привязка к тарифу Premium - сниппет r2 против чтения r3 того же URL [207]; Sage KB не прочитана.
- **Cogsy:** Mayple [234] против BuzzTable в Crunchbase [235] (не прочитан); дата закрытия - UNKNOWN.
- **Jungle Scout Inventory Manager:** URL отдаёт Catalyst [232], help-статьи существуют, но не прочитаны [233].
- **Amazon:** первоисточник «15% increase in sales» [237]; overrides прогноза продавцом; FBA Restock Guide PDF не прочитан (>10 МБ); help-страница Seller Central отдала только навигацию.
- **Stockful:** второй источник для закрытия Stocky и рейтинга 5.0 [239]; страница «Prediko Alternative» не прочитана.
- **Финансирование и найм** - UNKNOWN для всех.
- **Не исследованы** сущности из выдачи: SKU Compass, Drivepoint, Nova Data, onepint.ai, Eightx.
- **Замечание к верификации.** Сводная строка файла верификации («verified 3, disputed 2, unverified 3») расходится с постатейными статусами: verified 2 (SoStocked, Inventory Hero), disputed 2 (Inventory Planner, FeedbackFive), unverified 4 (Flieber, три утверждения Prediko). В тексте использованы постатейные статусы. Overturned - 0. Между раундами исправлено: лестница цен RestockPro $99.99-$599.99 (сниппет r2) опровергнута живой страницей r3 [224]; вывод r2 «Inventory Manager недоступен» [232] смягчён r3 [233].

---

### 5. Платформенные AI-ассистенты маркетплейсов (Азия, Европа, LatAm)

#### 5.1 Кто в поле (лидеры, челленджеры, wildcard)
| Роль | Продукт (рынок) | Тип | Что подтверждено | Уверенность |
|---|---|---|---|---|
| Лидер | Amazon Seller Assistant (US; EU/UK анонсированы) | агентный: непрерывный мониторинг + действия после одобрения | инвентарь, комплаенс, листинг, креативы; бесплатно [500][502] | высокая (primary + Retail Dive) |
| Лидер | TikTok Shop Seller Assistant (US) | агентный: 24/7, действия «with your permission» | нарушения, заказы, трек-номера, апелляции, видео, запуск GMV Max [511][512] | высокая (primary) |
| Лидер | 楽天市場 RMS AI アシスタント β版 + データ分析エージェント (JP) | аналитический советник + генерация | YoY-декомпозиция трафик × 客単価 × 転換率 [514]; агент объясняет причины (04.2026) [516]; ~50% магазинов ежемесячно [516] | высокая (primary) / средняя (traction - self-reported) |
| Лидер (Европа) | Allegro asystent AI (PL) | советник в панели продавца | объясняет изменения балла качества продаж, отвечает по регламентам [519][520] | средняя (один upstream - пресс-релиз Allegro) |
| Челленджер | Mercado Libre Asistente Inteligente (LatAm) | чат 24 ч | рекомендации по публикациям, проверка цены, промо (сниппет; primary 403) [529] | низкая |
| Челленджер | Taobao/Tmall 生意参谋 (CN) | аналитика «向内看» | бесплатен для всех с 04.2024 [525][524]; AI-модули не подтверждены | средняя |
| Челленджер | Shopee Shop AI Assistant (SEA) | чат-бот для покупателей | автоответы pre/post-sales, FAQ; «selected sellers» [533] | средняя |
| Челленджер | Lazada Lazzie Seller / LISA (SEA) | чат + риск-оценка магазина | только сниппет [534] | низкая |
| Wildcard | Flipkart Seller Lens / Ask Setu / AI-дашборды (IN) | product research (Chrome-расширение) + Q&A + «прогноз» | ключевые слова, спрос категории, цены [535][537]; хинди/голос, «demand forecasting» [538] | низкая / средняя |
| Wildcard (сторонний) | Nubimetrics (Mercado Libre, 18 стран) | «inteligencia de ventas» | модули Mercado / Competencia / Mi Negocio в Centro de Partners MeLi [530] | низкая |
| Не найдено | Coupang Wing (KR) | - | три раунда без нативного AI; только push в приложении [542][543] | - |
| Не найдено | Trendyol (TR) | - | нативного ассистента нет; нишу закрывают Sopyo, SETA Creative, Celer [545][546][547]; продукт «Ortak» не существует | низкая |

#### 5.7 Паттерны, которые стоит перенять
1. **Бесплатно внутри панели; монетизируется рыночный срез.** Носители: Amazon [500][502], TikTok Shop [511], 生意参谋 [525], Allegro asystent [519]; платно - Allegro Analytics Profesjonalny/Ekspert (рынок, 36 мес. истории) [521], Nubimetrics [530], 炼丹炉 [526]. Вывод: конкурировать ценой «ниже бесплатного» нельзя - только глубиной, кросс-платформенностью и рыночным срезом.
2. **Approval-gate на входе, ноль верификации на выходе.** Amazon «If the seller approves» [500]; TikTok Shop «with your permission», «checks conditions» перед действием [512]. Ни у кого нет журнала решений и expected-vs-actual - это открытый белый участок. Ступенчатые права (suggest-only / auto-approve / manual-only, «наблюдай 30 дней») - disputed, только вендоры [501][503].
3. **Агентность стартует с рутины низкого риска; цены и крупные правки листинга - вручную.** TikTok Shop [512]; Amazon (по вендорам) [501] (средняя).
4. **Инвентарь - первый агентный сценарий.** Amazon: slow-movers до storage fees, shipment recommendations [500][502] (verified); Allegro - логистика в планах [519]. Метод прогноза нигде не назван.
5. **Диагноз через декомпозицию трафик × чек × конверсия и в терминах платформенного скоринга, а не P&L.** Rakuten R-Karte [514][516]; Allegro - балл качества продаж [519][520]; Amazon - account health и применимые стандарты [500]. Ни у кого цепочка не доходит до «аномалия продаж → причина → действие с ожидаемым эффектом».
6. **Эволюция «объяснить цифру» → «объяснить причину и следующий шаг анализа».** Rakuten 2024 → 2026 [517][516]; Amazon Canvas - визуальные ответы и симуляции сценариев [501] (низкая).
7. **Ответы покупателям - самый частый генеративный модуль; развилка «автоотправка vs черновик».** Shopee - автоответ без approval [533]; Rakuten - черновик [514]; Lazada LISA [534] (низкая); MeLi - черновик с одобрением, unverified [528].
8. **Push о срочном вместо утреннего дайджеста.** Coupang Wing app [542]; Amazon-алерты [500]; TikTok Shop - ничего проактивного [512]. Утренняя сводка с расписанием и каналом - свободная ниша.
9. **Локализация как продукт.** Flipkart - хинди и голос [538]; Rakuten - японское 解説 [514]; Trendyol - турецкие сторонние сервисы [545][547]. Нативный ассистент не переносим между рынками - ниша для кросс-платформенных решений.
10. **Traction меряют долей активных магазинов, не эффектом на выручку.** Rakuten ~50% MAU [516]; Amazon «available to all sellers» [500]. Измеренного влияния на продажи/маржу не приводит никто - публичного бенчмарка для value-claims в сегменте нет.

#### 5.8 Что не нашли и открытые вопросы
- **Primary недоступны:** Seller Central help «Seller Assistant - Seller Central's agentic assistant» (без логина - только навигация) [509]; MeLi asistente (403) [529]; MeLi Centro de Partners (403) [530]; Business Standard (403) [538]; CNBC и Chain Store Age (403) [506][508]; allegro.pl «o narzędziu» (timeout ×2) [523]; lydaas.com (JS, пустая) [527]; seller.flipkart.com/seller-lens (только заголовок) [537].
- **Не подтверждено ни одним primary:** режимы auto-approve / suggest-only и «full autonomy Q2 2026» у Amazon; Canvas 03.2026; фактический запуск EU/UK; расписание и канал уведомлений Amazon.
- **Не найдено:** Coupang Wing AI-ассистент и CoupangData (три раунда) [542][543]; Trendyol «Ortak» [548]; 生意管家 и AI-модули 生意参谋 [527]; Flipkart Ask Setu primary - только агентский Facebook-пост и YouTube [539][540]; риск путаницы seller.flipkart.com/seller-lens (официальный) vs сторонний sellerlens.in [537][541]; Nubimetrics - живые цены, наличие алертов/AI в «Mi Negocio»; нативный ассистент MeLi по обходному пути (.ar / Wayback) - не пробовали.
- **Не покрыто:** Temu Seller Center AI; Shopee/Lazada beyond чат-бота; Ozon-аналоги за рубежом; финансирование и найм; независимые 1-3★ отзывы по всем продуктам.
- **Открытые вопросы для PM:** (1) есть ли у Amazon реальный auto-approve и лог действий - нужен Seller Central help или форумный тред; (2) даёт ли Rakuten データ分析エージェント рекомендованное действие и алерты по отклонениям; (3) платен ли Allegro Analytics по primary и что реально умеет asystent по отзывам продавцов; (4) MeLi - черновики с одобрением или автоответ; (5) 生意参谋 - есть ли AI-детекция аномалий в 2025-2026; (6) существует ли где-либо в сегменте память решений (C) - три раунда говорят «нет», но покрытие форумов нулевое.

---

### 6. Российские сервисы для WB/Ozon-селлеров как референс позиционирования

#### 6.1 Кто в поле (лидеры, челленджеры, wildcard)
Классификация — по широте функций и заметности в источниках; независимых данных о долях рынка нет (единственная цифра — самооценка MPStats «около 80%», см. ниже). Уверенность классификации: средняя.

- **Лидеры-«комбайны»** (аналитика + биддер + репрайсер + автоответы + контент). **MPStats** — самый широкий набор инструментов; с 9 февраля 2026 принадлежит Точка Банку (оценка актива 2 млрд ₽, заявленная доля «около 80%» сегмента) [600][601][602] — уверенность: средняя (только сниппеты трёх изданий; «80%» — из пресс-релиза). Ход 2026 — не собственный ассистент, а открытие данных чужим AI-агентам через скилл + токен [603][604][605] (unverified: один издатель). **Маяк** — «самая популярная платформа», «850 000+ предпринимателей», «официальный авторизованный сервис Wildberries» — самозаявления без независимого подтверждения [606] (уверенность: низкая); на независимой площадке отзывов — 2.9/5 по 46 отзывам [607] (verified).
- **Челленджеры «агентского» типа** (продают «сотрудника», а не отчёт). **JVO (Дживио)** — три ИИ-агента (ценообразование, коммуникации, реклама), ежедневный мониторинг → задачи [608][609]; CRMindex 4.6/5 по 24 отзывам [610]. **Sirena AI** — «AI-агент, который знает ваш магазин»; подключён только Wildberries [611] (verified). **MP Manager** — AI-биддер, AI-ответы на отзывы, «AI отвечает на вопросы»; «120 000+ селлеров» — вендорская цифра без даты [612] (уверенность по traction: низкая).
- **Нишевые специалисты** (закрывают одну-две области A–G). **РНП «Рука на пульсе»** — дерево диагностики падения продаж и OOS-флаги [613]; **WBRay** — Telegram-мониторинг изменений карточек [614]; **Seller Moon** — чат-ассистент по API-данным WB/Ozon [615].
- **Бюджетный слой.** Moneyplace — 5 000–7 000 ₽ [616]; Stat4Market — «от 870 ₽/мес» [617]; Shopstat — «всё бесплатно» [618]; MarketGuru — «бесплатная аналитика Wildberries» [619]; SellerFox — «от 1099 ₽» [620]. Последние четыре — только по сниппетам, уверенность: низкая.
- **Wildcard — не сервисы аналитики, а ассистенты площадок и банка.** Wildberries «Помощник» в подписке «Джем» [621][622][623] (verified); Ozon «Умный ассистент» на Qwen 3.5, тестовый режим для части продавцов [624][625]; Точка Банк «AI Ассистент селлера» в Telegram [626][627] (verified). Все трое забирают нижний слой «объясни мои метрики в чате»; ни один не исполняет действия.
- **Не покрыты.** Anabar — «proxy refused the connection» три раунда подряд [628]; SellerFox — первичный сайт HTTP 403 [629], данные только с агрегатора; WBStat — тарифы и функции в поиске не найдены.

#### 6.7 Паттерны, которые стоит перенять
1. **Ежедневный автомониторинг → очередь задач, а не дашборд.** Носители: JVO («формирует задачи», предупреждает об OOS) [609][610], Sirena («подсветит, где теряете прибыль») [611], РНП (диагностика → задачи) [613]. У комбайнов (MPStats, Маяк) цепочки нет [603][606].
2. **Диагностическое дерево + задача с ответственным.** Носитель: РНП — «разрыв между заказами, прогнозом и фактом» → задача [613]. Единственный найденный суррогат памяти решений; замыкание цикла (сверка результата после исполнения) не делает никто — свободная ниша.
3. **Telegram с тихими часами и ежедневной сводкой вместо потока алертов.** Носители: WBRay — 3 проверки в сутки, «тихие часы», «ежедневные сводки» [614]; Точка — весь продукт в Telegram [627]; Маяк — Telegram-бот как один из трёх форматов [632]. Ближайший образец «утреннего дайджеста» в категории.
4. **OOS-флаги как минимум, автостоп — как дифференциатор.** Носители: РНП («Реклама / акция вымывает остатки», «Риск OOS») [613]; MP Manager («Алерты предупреждают до обнуления») [612]; JVO (предупреждает об OOS) [609]. Автостоп рекламы при нулевом остатке не заявил никто.
5. **Guardrail как бизнес-инвариант плюс явный аппрув (которого нет ни у кого).** Носители инварианта: MPStats («без автоматического выхода из акций») [603], Маяк («сохраняет маржу до 25%») [606], MP Manager («защита маржи») [612]. Режим «предложить → утвердить → выполнить» не найден — второй свободный слот.
6. **Объяснимость автоматики через журнал действий.** Носитель: биддер MPStats — 90 дней, вкладки All Events / Bids / Clusters / Automations с фильтрами [603]. Переносимо на журнал решений и их последствий.
7. **Триал без карты и короткий вход.** Носители: Sirena (24 ч, без карты, «подключение за 2 минуты») [611], MP Manager (3 дня без карты) [612], РНП (5 дней без карты) [613], Seller Moon (30 дней) [615]. Контраст — невозвратные годовые лицензии Маяка [606][607].
8. **Открытие данных внешним агентам read-only (токен + скилл).** Носители: MPStats [604][605] (unverified — один издатель), сторонний ru-marketplace-mcp [651] (уверенность: низкая). Дополнительная роль «источник для чужого агента» — рассматривать с оговоркой о статусе.
9. **Упаковка.** По обороту селлера — JVO (< 1 / 1–2 / > 2 млн ₽/мес) [608]; модульно со скидкой за срок — MP Manager (−20% / −30%) [612]; лимитами — Moneyplace (автоответы 7 000 / 60 000, ИИ-описания 80 / 1 000) [616]; годовыми пакетами — Маяк [606]. Автоответы на отзывы — коммодити: продаются лимитами [616][606], площадка делает их сама [635] (уверенность: низкая).
10. **Персонификация ИИ как «сотрудника».** Носители: Sirena («Ваш новый сотрудник, который работает 24/7») [611], JVO (три «агента»; клиенты — «лишний работник, который ничего не забывает») [608][610]. Работает как упаковка, но на фоне жалоб на «рекомендации без ответственности» [607] требует подкрепления сверкой результата (паттерн 2).

#### 6.8 Что не нашли и открытые вопросы
- **Живые тарифы MPStats** — три раунда: страница рендерится скриптом [637], Wayback заблокирован инструментом; три несовместимых набора цен во вторичных источниках [620][638][639] (disputed). Открытый вопрос: ручной скриншот и проверка, менялись ли тарифы после покупки Точкой.
- **Недоступные сайты.** Anabar — «proxy refused the connection» три раунда [628]; SellerFox — первичный сайт 403 [629]; WBStat — тарифы и функции не найдены; MPAgency (обзоры MPStats, Shopstat, Точки) — антибот [631][656].
- **Sirena AI** — цены («Загрузка тарифов...»), канал и время ежедневных отчётов [611]; независимый издатель.
- **JVO** — рублёвые цены (/tariffs — 404 [640]), механика аппрува агентов, первичное подтверждение «100+ метрик» [610].
- **Точка Банк** — статус и платность ассистента после I кв. 2026; реализовано ли «автоматическое выявление проблемных зон» [627]; обзор MPAgency закрыт [656].
- **Ozon «Умный ассистент»** — цена, открыт ли всем продавцам, выполняет ли действия; первичный пост в блоге Ozon Seller (найден только пресс-релиз) [624].
- **MP Manager** — цены в рублях, документация биддера (стоп при OOS?), режим согласования AI-ответов на отзывы, независимые отзывы [612].
- **WBRay** — стоимость Rays в рублях, алерты на смену заголовка/описания [614]; **РНП** — тарифы, расписание дайджеста, метод «Риск OOS < N дней» [613].
- **MPStats-скилл/«MCP»** — независимый обзор (vc.ru, Habr) не найден; дата последнего коммита не видна [605]; расхождение «прогнозы и рекомендации» на странице [604] vs README [605] не разрешено.
- **Маяк** — противоречие «850 000+ / 84,3% окупили» [606] против 2.9/5 [607] закрыто частично: тред Oborot.ru [652] и Otzovik [653] не прочитаны; конкурент «Mkiper» из отзыва не изучен.
- **Новые сущности без содержания** — Sellego (трекинг конкурентов) [657], Mpfinassist [658], Uniseller как продукт [659]: только заголовки поиска.
- **Категорийные пробелы (ни у одного из двенадцати продуктов):** запись решения и сверка «ожидалось vs получилось» (C); названный метод прогноза (D); человеческий аппрув перед действием и автостоп рекламы при OOS (E); «утренняя сводка» с временем отправки (A); алерты об изменениях собственного листинга по заголовку/описанию (G).
- **Независимые датированные отзывы за 12 месяцев** — только Маяк [607] и JVO [610]; для остальных десяти продуктов — нет.
- **Финансирование и найм** — кроме сделки Точка–MPStats, ничего.
