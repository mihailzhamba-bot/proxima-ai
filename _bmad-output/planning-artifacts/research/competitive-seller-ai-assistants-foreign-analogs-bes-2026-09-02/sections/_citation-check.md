# Проверка цитирований (fresh-context citation check)

**Дата проверки:** 2026-09-02
**Проверяющий:** независимый агент со свежим контекстом (research firewall: читались только `research.md`, `prd.md` §16 и внешние URL).
**Что проверялось:** совпадает ли утверждение в потребительском тексте (PRD §16 / Executive summary отчёта) с тем, что реально говорит источник по URL из «Приложение: источники».

**Выборка:** 68 различных `[n]` (64 в PRD §16, 49 в Executive summary, пересечение 45).
**Бюджет:** 50 запросов — исчерпан. Проверено 48 источников (49 строк: `[215]` разведён на два утверждения). Не проверено 20 — список в конце.
**Метод:** прямой WebFetch; при 403 — вторая попытка через `https://r.jina.ai/<url>`. Цитаты приведены дословно (≤200 символов), где источник отдал текст.

---

## Таблица

| [n] | Утверждение (как использовано) | Вердикт | Цитата | Статус URL | Реком. уверенность |
|---|---|---|---|---|---|
| [104] | Helium 10 Ads Change Log: журнал изменений рекламы с атрибуцией «кто изменил» («Change By»); суррогат записи решения | подтверждает | «The Change By filter allows you to filter the source of the change type selected, such as an AI rule, dayparting schedule, bid rule, etc.» | 403 напрямую → OK через r.jina.ai | high |
| [107] | Агент Helium: изменение → корневая причина → следующее действие | подтверждает | «Helium surfaces next best actions aligned to profitability, growth, or efficiency goals, reducing guesswork and analysis paralysis.» | OK | high |
| [113] | Пример диагноза: «margin dropped from 22% to 18% … Higher TACOS on your top ASIN is the main reason» | подтверждает | «Your margin dropped from 22% to 18% this month. Higher TACOS on your top ASIN is the main reason.» + «Helium is read-only. It does not pause campaigns, change bids, or move budgets.» | OK | medium (affiliate-блог, но цитата дословная) |
| [116] | PRD §16: «Helium 10 — email в режиме "daily"» (утренний бриф по расписанию) | **не подтверждает** | «There are two ways you can get notified. You could either get notifications via email or SMS.» — режима «daily», расписания и push на странице нет | OK | low — убрать Helium 10 из строки про утренний бриф или переатрибутировать |
| [123] | Sellerboard: взвешенная скорость + сезонные коэффициенты + % роста | подтверждает | «The adjusted sales velocity is the average number of units sold per day. This number is adjusted by the 'weight' entered per period.» + «you can project a monthly growth rate in %» | OK | medium (блог 2023, вендор) |
| [129] | Amazon Seller Assistant: «If the seller approves, Seller Assistant implements the solution» | подтверждает | «If the seller approves, Seller Assistant implements the solution and clears the warning before it becomes a problem.» | OK | high |
| [140] | DataHawk Sherlock: изменение → наиболее вероятная причина → следующее действие; «advises — it does not automate» | подтверждает | «Shows the most likely explanation - not just a list of metrics»; «Sherlock advises - it does not automate. You stay in full control.» | OK | high |
| [142] | DataHawk MCP: «Why did revenue drop last week?» → Buy Box loss → next step | подтверждает | «Revenue dropped 23% last week … Primary driver: B08FHD3QPL lost buy box on Apr 23» + «Ask your Amazon data anything.» | OK | high |
| [200] | SoStocked называет сезонность, тренд, lead time, MOQ, safety stock, горизонты 30/90/365 | частично | «Automatically factor things like past sales, Prime Day, seasonality, and sales spikes.» — есть сезонность, «Adjusted Velocity», «Buffer Stock», PO-статусы; **не названы** lead time, MOQ, safety stock как компоненты и горизонты 30/90/365 | OK | medium |
| [205] | Inventory Planner называет сезонность, тренд, lead time, safety stock, горизонты + overrides | частично | «Optimize 'safety stock'»; «Tweak your 'stock coverage days' at every level, from SKU to supplier»; «Configurable forecasting models» — **не названы** «тренд», «lead time», горизонты | OK | medium |
| [215] (Exec summary) | «самоконтроль точности прогноза у Stockful и Prediko» | **не подтверждает** | На странице нет заявления об измерении точности собственного прогноза; ближайшее — «Prediko's AI agent generates draft purchase orders and recommends what to order» | OK | low — оставить самоконтроль точности только за Stockful [239] |
| [215] (PRD §16) | Prediko: черновик PO / рекомендация к закупке | подтверждает | «Yes, Prediko's AI agent generates draft purchase orders and recommends what to order»; «Pia doesn't just show data; it also recommends what actions to take» | OK | high |
| [218] | Prediko: Draft → Sent for Approval → Approved | подтверждает | Статусы «Draft» → «Sent for Approval» → «Approved» перечислены как последовательные в группе «Created» | OK | high |
| [228] | Inventory Hero: горизонты 30/90/365 и «ready for your approval» | подтверждает | «Auto-updating 30, 90, and 365 day forecasts from real sales velocity and seasonality»; «Drafted POs, flagged reorders, and priced lost sales, ready for your approval» | OK | high |
| [236] | Antipattern: Amazon MIL без overrides получает жалобы | подтверждает | «The metric is entirely broken, as has been pointed out numerous times without any resolution.»; «Amazon is forcing these policies down the throats of 3rd party sellers, without consultation or representation.» | OK | medium (форум, не документация) |
| [239] | Stockful: самоконтроль точности прогноза; все функции в каждом плане | подтверждает | «every forecast keeps proving itself against what actually sold» (+ «Self-tracked accuracy»); «Plans differ only by tracked SKUs and locations. No feature gating, AI included, 14-day free trial.» | OK | high (про «триал без карты» страница молчит — только «14-day free trial») |
| [300] | Pacvue: «full record of what changed and why» + «approval-based execution with clear guardrails» | подтверждает | «Pacvue Agent turns recommendations into approval-based execution with clear guardrails and a full record of what changed and why.» | OK | high |
| [302] | Pacvue: авто-пауза рекламы по weeks-of-inventory | подтверждает | «Create inventory rules to automatically pause products that have low inventory or based on 'weeks of inventory on hand' so you are not promoting items out of stock.» | OK | high |
| [305] | Те же дословные формулировки Pacvue Agent («approval-based execution with clear guardrails», «full record of what changed and why») | частично | В статье: «includes built-in guardrails, approval steps, and an audit trail» — смысл совпадает, но **дословных формулировок, приписанных [305], в тексте нет** (они принадлежат [300]) | OK | medium — оставить как вторичное подтверждение смысла, цитату атрибутировать только [300] |
| [312] | Perpetua: рекомендация паузы по порогу остатков; «up to 24 hours for inventory data to sync» | подтверждает | «Perpetua will send a recommendation to pause the ads that are serving the product»; «It may take up to 24 hours for inventory data to sync from Amazon.» | OK | high |
| [335] | «m19 Inventory Threshold за $59 / $59 в мес» | **не подтверждает** | Тариф $59/мес — это план **Autopilot**, в котором Inventory Threshold отсутствует; сама функция значится только в тарифе «Agencies & Enterprise» с ценой «Cut to fit / Based on your needs» (проверено дважды: прямой fetch + r.jina.ai) | OK (обе попытки) | low — цену $59 отвязать от Inventory Threshold |
| [403] | Triple Whale Compass: «every recommendation from Moby 2 … is informed by that trusted data» | **не подтверждает** | Статья KB говорит обратное: «You do not need Compass to use Moby»; Compass «adds another layer of context» | 403 напрямую → OK через r.jina.ai | low — цитату перепроверить по [408] (не проверен) или снять |
| [407] | Moby 2: Copilot (человек одобряет) / Autopilot «within predefined guardrails», GA 19.05.2026; Moby Specialists | подтверждает | Copilot — «customers approve actions»; Autopilot — исполняет «within predefined guardrails»; GA 19 мая 2026; специалисты Media Buyer / Creative Director / Conversion Optimizer | OK | high |
| [409] | GMV-привязанный прайс как главная боль Triple Whale | подтверждает | «Tying pricing to GMV is the biggest downside.»; «Pricing is based on GMV or gross merchandise value. The higher the GMV, the more you pay for the same plan» | OK | medium (обзорный блог, один издатель) |
| [418] | Shopify Campaign Autopilot: approve/reject | подтверждает | «Approve actions that you want to run or reject the ones that you don't want to run. You decide what goes live.» | OK | high |
| [420] | Shopify: «more room as campaigns evolve», 17.06.2026 | подтверждает | «You decide how much control you want, from approving every campaign before it runs to giving Campaign Autopilot more room as campaigns evolve.» (дата публикации 17.06.2026) | OK | high |
| [422] | Shopify Pulse Card: «что происходит → почему важно → следующие шаги» | частично | На странице есть только: «Sidekick Pulse delivers personalized recommendations before you even ask. Based on market trends and your shop data, it suggests concrete optimizations.» — **трёхчастной структуры карточки нет** | OK | low для формулы карточки (второй источник [423] не проверен) |
| [435] | Polar: утренний Slack-бриф по расписанию; governed metrics через MCP; «CAC spike … with the reason» | подтверждает | «A morning read on revenue, spend and blended CAC, posted before standup.»; «Hermes reads your governed metrics over the Polar MCP, so every answer is first-party and sourced, never a guess.»; «A CAC spike, a revenue drop, a channel that fell off, flagged in the channel with the reason.» | OK | high (в отчёте цитата дана как «each morning before standup» — на странице «posted before standup», формулировку поправить) |
| [436] | Polar: черновик действия в трекере с владельцем; агент = роль с KPI | подтверждает | «Let your Weekly Team agents push prioritized action items straight into a Notion tracker, each tagged with owner, priority, and the numbers behind it.»; «Media Buyer Agent … built on ROAS, CAC, and incrementality» | OK | high |
| [450] | Luca сверяет цифры с банковскими данными | подтверждает | «Platform-reported numbers reconciled against the bank. Margin-adjusted, refund-adjusted, shipping-adjusted.»; «Meta says 4.2×. Reconciled, it's 2.6×.» | OK | high |
| [500] | Платформенные ассистенты шлют **push** о срочном (Amazon) | частично | «Seller Assistant will continuously monitor a seller's account status and surface potential issues and actions»; «alerting sellers to actions they can take» — проактивные алерты есть, **канал push не заявлен** | OK | high для «проактивные алерты», low для «push» |
| [512] | TikTok Shop: действия «with your permission» | подтверждает | «Take action on your behalf (with your permission)» | OK | high |
| [514] | Rakuten データ分析エージェント объясняет причины через декомпозицию трафик × чек × конверсия | частично | 「自店舗へのアクセス人数や客単価、転換率などの指標を中心に分析し、前年対比での売り上げ傾向や特徴を解説する機能」 — анализ по трём метрикам и объяснение трендов есть; **«декомпозиция причин» как метод не заявлена**; релиз 30.04.2024 описывает AI-функцию RMS, а не продукт «データ分析エージェント» | OK | medium |
| [516] | Rakuten: traction «~50% активных магазинов»; та же декомпозиция | частично | 「約5万の出店店舗様の約半分が毎月、何らかの形でAI機能を活用いただいている」 — это про **AI-функции в целом**, не про агент; для агента приведено 「利用店舗の72.9％が追加の分析を実施」; декомпозиции трафик × чек × конверсия в статье нет | OK | medium для «~50% магазинов пользуются AI-функциями», low для привязки к агенту |
| [542] | Coupang Wing: push о срочном | подтверждает | 「즉시 처리해야 할 일이 있다면, 윙 앱이 알려줍니다. 가격 관리 알람을 확인하고 신규 주문을 놓치지 마세요!」 (+ настройка «не беспокоить») | OK | medium (карточка App Store) |
| [600] | MPStats: с 09.02.2026 принадлежит Точка Банку; самооценка доли «около 80%» | частично | «этот сервис является лидером в сегменте сервисов для селлеров и занимает **более трети рынка**» — сделка и дата (публикация 09.02.2026) подтверждены, **доля «около 80%» источником не поддержана и расходится с ним** | OK | high для сделки, low для «80%» (проверить [601][602] — не проверены) |
| [603] | MPStats: журнал биддера 90 дней с вкладками; guardrail «без выхода из акций»; MCP для внешних агентов | подтверждает | «Теперь в истории показываем все события, которые совершал пользователь или Биддер за последние 90 дней»; «История делится на 4 вкладки — Все события, Ставки, Кластеры и Автоматизации»; «умеет управлять акционной ценой товара без автоматического выхода из акции» | OK | high |
| [604] | MPStats: скилл/подключение аналитики к внешним AI-агентам | подтверждает | «Подключите аналитику маркетплейсов к AI-агентам»; «Установите скилл MPSTATS, чтобы подключить Внешнюю аналитику к вашему AI-агенту» | OK | high (один издатель) |
| [606] | Маяк: самозаявление «850 000+»; guardrail «сохраняет маржу»; годовые пакеты | подтверждает | «850 000+ предпринимателей уже растут с Маяком»; «сохраните до 25% маржи: репрайсер удерживает нужную стоимость»; пакет «Доминирование» (12 мес) «от 7 417 ₽/мес или сразу: 98 000 ₽» | OK | high для наличия заявлений; traction — самоотчёт |
| [607] | Маяк: 2.9/5 по 46 независимым отзывам | подтверждает | «Маяк - 46 реальных отзывов (2.9) о сервисе аналитики 2026»; на странице «2.9» и «Всего отзывов 46» | OK | high |
| [608] | JVO продаёт «сотрудника 24/7» | **не подтверждает** | На главной не найдено ни позиционирования «24/7», ни тарификации по обороту, ни «100+ показателей»; страница — лендинг с формой заявки и кейсами (поле «Оборот на маркетплейсе» — сегментация лида, не тариф) | OK (но возможен JS-рендер) | low — переатрибутировать на [609]/[610] или снять; нужен ручной снимок |
| [609] | JVO «формирует задачи»; в РФ автостоп рекламы при нулевом остатке никто не заявляет | подтверждает | «формирует задачи, чтобы вы не теряли деньги»; «Система предупреждает о критичных ошибках, полных или частичных out-of-stock товарах» — автостопа рекламы нет (подтверждает отсутствие) | OK | high |
| [611] | Sirena AI: «сотрудник 24/7», 24 ч триала без карты, ежедневные отчёты; сверки исхода нет | подтверждает | «Ваш новый сотрудник, который работает 24/7 без перерывов»; «24 часа полного доступа без ограничений. Без привязки карты»; «отчёты — ежедневно»; механизма проверки результата рекомендаций на странице нет | OK | high (вендор, один издатель) |
| [612] | MP Manager: «сотрудник 24/7», guardrail по марже, триал без карты; автостоп рекламы при OOS не заявлен | подтверждает | «Работает 24/7 вместо вас»; «Цены меняются по вашим правилам - прибыль не уходит в минус»; «3 дня полного доступа без ограничений. Карта не требуется»; «Алерты … приближение к нулевому остатку» — только алерты, без автостопа | OK | high |
| [613] | РНП: диагностическое дерево → задача с ответственным; триал без карты | подтверждает | «Найдите свою проблему – РНП покажет, что делать»; «Превращайте аналитику в конкретные действия для команды»; «5 дней бесплатно без привязки карты» | OK | high (но см. оговорку ниже про «эффект») |
| [614] | WBRay: Telegram-сводки, «тихие часы», 3 проверки в сутки | подтверждает | «как только проверка находит значимое изменение, WBRay присылает сообщение в Telegram»; «Ночью сообщения копятся и приходят одним разом»; «Три раза в сутки» | OK | high |
| [621] | WB «Помощник» (в «Джем») — платформенный ассистент **бесплатно** внутри панели, действий не исполняет | частично | «Wildberries запустил аналитического ИИ-ассистента для селлеров»; «Инструмент уже доступен всем продавцам **по подписке «Джем»**» — запуск и канал подтверждены, **«бесплатно» источником не подтверждено** (подписка); «не исполняет действий» явно не сказано | OK | high для запуска/канала, low для «бесплатно» |
| [624] | Ozon «Умный ассистент» — бесплатно в личном кабинете, отвечает, но не исполняет | частично | «Ozon внедрил в личный кабинет продавца ИИ-ассистента — «Умный ассистент»»; «Система учтет контекст диалога, уточнит запросы и предложит релевантные действия» — **стоимость не указана**; исполнение действий не заявлено (подтверждает «только подсказки») | OK | high для факта запуска и характера, low для «бесплатно» |
| [627] | Точка «AI Ассистент селлера» — целиком в Telegram | подтверждает | «первый виртуальный помощник, который адаптирован под специфику экономики маркетплейсов и **полностью доступен через Телеграм**» | OK | high |

---

## Сводка

**Проверено 48 источников (49 строк). Не проверено 20 (бюджет 50 запросов исчерпан).**

| Вердикт | Строк |
|---|---|
| подтверждает | 34 |
| частично | 10 |
| не подтверждает | 5 |
| недоступен | 0 |

Ни один источник не остался недоступным: две страницы (`kb.helium10.com` [104], `kb.triplewhale.com` [403]) отдали 403 напрямую, но прочитаны со второй попытки через `r.jina.ai`.

### «Не подтверждает» — 5 строк (5 источников; [215] разведён: строка PRD §16 подтверждена, строка Exec summary — нет)

- **[116] Helium 10 Alerts.** PRD §16 в строке «Утренний бриф» пишет «Helium 10 — email в режиме "daily"». Страница знает только два канала («email or SMS»), никакого расписания, режима «daily» и push. → Убрать Helium 10 из строки про утренний бриф или найти другой источник (в самом приложении режим «daily» уже помечен `unverified`).
- **[215] Prediko (только для Exec summary).** Утверждение «самоконтроль точности прогноза у Stockful и Prediko» для Prediko не поддержано: страница не заявляет измерения точности своего прогноза. Черновики PO (использование [215] в PRD §16) — подтверждаются. → Самоконтроль точности оставить только за Stockful [239].
- **[335] m19.** «Inventory Threshold за $59» неверно: $59/мес — цена плана Autopilot, в котором этой функции нет; Inventory Threshold есть только в «Agencies & Enterprise» с ценой «Cut to fit». Проверено двумя проходами. → Правка нужна и в Exec summary п.7, и в строке PRD §16 «OOS-aware guardrail» («m19 Inventory Threshold ($59/мес)»).
- **[403] Triple Whale Compass.** Приписанная цитата «every recommendation from Moby 2 … is informed by that trusted data» не найдена; KB-статья утверждает противоположное по смыслу: «You do not need Compass to use Moby», Compass лишь «adds another layer of context». → Тезис «доверенный слой данных — рыночная норма» держится на [435][450]; цитату Triple Whale перепроверить по [408] (не проверен) либо снять.
- **[608] JVO (главная).** Exec summary п.8: «челленджеры JVO, Sirena AI, MP Manager продают "сотрудника 24/7"». На главной JVO нет ни «24/7», ни тарификации по обороту, ни «100+ показателей» — это лендинг с формой заявки. Оговорка: возможен JS-рендер, нужен ручной снимок. → Для JVO переатрибутировать на [609]/[610]; для Sirena [611] и MP Manager [612] утверждение подтверждено дословно.

### «Частично» — что именно не поддержано (10 источников)

- **[200] SoStocked** — есть сезонность, «Adjusted Velocity», «Buffer Stock»; **не названы** lead time, MOQ, safety stock и горизонты 30/90/365.
- **[205] Inventory Planner** — есть сезонность, safety stock, настраиваемые модели/overrides; **не названы** «тренд», «lead time», горизонты.
- **[305] PPC Land (Pacvue)** — смысл совпадает («built-in guardrails, approval steps, and an audit trail»), но **дословные цитаты, приписанные [305], в статье отсутствуют**; они принадлежат [300].
- **[422] Shopify Pulse** — Sidekick Pulse и «concrete optimizations» есть; **трёхчастная формула карточки** «что происходит → почему важно → следующие шаги» **не заявлена** (второй источник [423] не проверен).
- **[500] Amazon** — проактивные алерты подтверждены; **канал «push» не заявлен** на странице.
- **[514] Rakuten (пресс-релиз 2024)** — анализ по アクセス人数 / 客単価 / 転換率 и объяснение трендов есть; **«декомпозиция причин» как метод не заявлена**; релиз описывает AI-функции RMS, а не продукт «データ分析エージェント».
- **[516] netkeizai** — «около половины из ~50 000 магазинов» относится к **AI-функциям в целом**, а не к агенту (для агента в статье другая цифра — 72,9% пользующихся магазинов делают доп. анализ); **декомпозиции трафик × чек × конверсия в статье нет**.
- **[600] Forbes/MPStats** — сделка и дата подтверждены; **доля «около 80%» не поддержана и расходится с источником**: «занимает более трети рынка». Проверить [601][602] (не проверены).
- **[621] WB «Помощник»** — запуск и доступ «в Джем» подтверждены; **«бесплатно» опровергается формулировкой «по подписке «Джем»»**; «не исполняет действий» явно не сказано.
- **[624] Ozon «Умный ассистент»** — запуск и характер (ответы, рекомендации, без исполнения) подтверждены; **стоимость («бесплатно») не указана**.

### Отдельные оговорки к формулировкам (не меняют вердикт)

- **[435] Polar.** В Exec summary и PRD цитата дана как «each morning before standup»; на странице — «A morning read on revenue, spend and blended CAC, **posted before standup**». Смысл сохранён, кавычки надо поправить.
- **[613] РНП.** Кроме диагностического дерева на странице заявлен **цикл «отклонение — причина — действие — эффект»**. Это ослабляет категоричность тезиса «ни один из ~45 продуктов не сверяет ожидание с фактом»: у РНП стадия «эффект» декларирована (без документированной сверки «ожидали → получили»). Формулировку в Exec summary п.1 и R1-1 стоит уточнить: «никто не публикует сверку ожидания с фактом», а не «никто не смотрит на эффект».
- **[239] Stockful.** «Все функции в каждом плане» подтверждено дословно («No feature gating»); «триал без карты» на странице **не сказано** (только «14-day free trial») — в строке прайса PRD §16 это относится к Sirena [611] (24 ч без карты — подтверждено) и MP Manager [612] (3 дня без карты — подтверждено).

### Не проверено (20) — бюджет исчерпан

`[109]` `[202]` `[224]` `[229]` `[328]` `[338]` `[354]` `[408]` `[410]` `[411]` `[412]` `[423]` `[437]` `[511]` `[519]` `[525]` `[601]` `[602]` `[605]` `[610]`

Приоритет для следующего прохода (каждый — единственная оставшаяся опора спорного утверждения):

1. **[408]** — единственный непроверенный носитель цитаты Triple Whale про «trusted data» после провала [403].
2. **[601] [602]** — единственные оставшиеся опоры доли MPStats «около 80%» после расхождения с [600].
3. **[338]** — второй источник по «m19 Inventory Threshold за $59» после опровержения [335].
4. **[423]** — второй источник по формуле Shopify Pulse Card после частичного [422].
5. **[354]** — SellerStack, единственный источник по ступеням 25/50/90/99 % (в PRD уже помечен `unverified`).
