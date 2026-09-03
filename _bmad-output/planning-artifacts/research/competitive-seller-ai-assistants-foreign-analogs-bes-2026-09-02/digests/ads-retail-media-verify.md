# ads-retail-media - независимая проверка (verify)

Дата проверки: 2026-09-02. Уровень: normal - выборочная проверка 8 нагруженных утверждений из дайджестов r1-r3, по одному независимому источнику на каждое. Бюджет: 12 вызовов (8 поисков + 4 чтения страниц), израсходован полностью. Все ссылки - доступ 2026-09-02.

Правило независимости: искал другого издателя с другими исходными данными (не синдикацию пресс-релиза и не другую страницу того же вендора). Где независимый источник лишь пересказывает пресс-релиз вендора - это отмечено явно и понижает уверенность.

## Итоги по утверждениям

| # | Утверждение (кратко) | Статус | Независимый источник |
|---|---|---|---|
| 1 | Pacvue Agent: approval-based execution + guardrails + запись «что изменилось и почему» | verified (как заявление вендора, с оговоркой) | PPC Land, 2026-04-14 |
| 2 | Pacvue: Net PPM / Buy Box / inventory rules, budget pacing, dayparting | verified (частично: Net PPM не подтверждён) | SmartScout, atom11 (сниппеты, дата неизвестна) |
| 3 | Perpetua: Essentials $695 до $10k; Growth $695 + %; Premium Custom > $500k | verified | Xneeti, 2026-05-12 |
| 4 | Teikametrics: ARI suite (Ads, Catalog, Inventory, Insights) + Refunds Recovery во всех тарифах | verified (сниппет-уровень) | G2 pricing / Xneeti (сниппеты, 2026) |
| 5 | Amazon Ads Agent по SellerApp: unBoxed 2025, бета в 2026, доступ DSP/AMC, «Nothing goes live without your approval» | verified (с уточнением по «бета» и по доступности для SP) | Adweek, 2025-11; Feedvisor / PPC Land (сниппеты) |
| 6 | SellerStack Inventory Protection: пороги 25/50/90/99 %, восстановление при 30 днях, прогон в 5am | unverified | независимый источник не найден |
| 7 | m19: Target daily/monthly spend, TACOS Targeting, Inventory Threshold, Peak season Boost | verified (частично: TACOS и daily spend / low inventory; monthly spend и Peak Boost - только вендор) | RevenueGeeks, 2026-08-09; Orange Klik (сниппет) |
| 8 | Amazon Ads (первичный): «review and approve», pacing по сотням кампаний, аудитории, SQL для AMC | verified | Adweek, 2025-11; Feedvisor, PPC Land (сниппеты) |

## Подробно

### 1. Pacvue Agent - approval-based execution, guardrails, audit trail
- Проверка: PPC Land (автор Luis Rijo), «Pacvue Agent promises 200x faster commerce media workflows», 2026-04-14, https://ppc.land/pacvue-agent-promises-200x-faster-commerce-media-workflows/ (доступ 2026-09-02). Статья описывает «governed execution»: рекомендация превращается в обновление кампании через «an agentic workflow that includes built-in guardrails, approval steps, and an audit trail». Автор отдельно отмечает, что Pacvue не раскрывает точность рекомендаций и долю случаев, когда потребовался ручной override.
- Оговорка независимости: формулировки в статье атрибутированы пресс-релизу Pacvue от 14.04.2026 (GlobeNewswire, https://www.globenewswire.com/news-release/2026/04/14/3273156/0/en/...). То есть второй издатель подтверждает, что вендор действительно это заявляет, и датирует заявление (в дайджесте дата была «unknown»), но не подтверждает поведение продукта независимыми данными. Это согласуется с r2/r3: в документации Pacvue audit trail не найден.
- Вердикт: verified как задокументированное заявление вендора (дата 2026-04-14); как наблюдаемая возможность - не проверено. Для дифференциации опираться только с пометкой «заявлено, не подтверждено документацией».

### 2. Pacvue - profitability-aware automation (Net PPM, Buy Box, inventory rules), budget pacing, dayparting
- Проверка (поисковые сниппеты, страницы не открывались - бюджет): SmartScout, «Pacvue vs. Perpetua», дата неизвестна, https://www.smartscout.com/blog/pacvue-vs-perpetua-which-ppc-bid-management-tool-is-best-for-you - dayparting «на почасовом уровне», правила по ROAS/ACoS/CVR; atom11, «Pacvue vs Perpetua», дата неизвестна, https://www.atom11.co/blog/pacvue-vs-perpetua - Pacvue «connects to inventory, pricing, and Buy Box data, so it makes bidding decisions that aren't blind to whether you're actually winning the Buy Box»; также упомянуты «inventory-aware rules», «budget pacing».
- Не подтверждено: термин «Net PPM» ни в одном стороннем источнике не встретился (сводка выдачи прямо это отмечает). PPC Land (см. п.1) тоже не упоминает Net PPM, Buy Box, inventory rules.
- Вердикт: verified частично - dayparting, budget pacing, Buy Box- и inventory-aware правила подтверждены сторонними обзорами (сниппет-уровень, средняя уверенность, даты неизвестны); «Net PPM» остаётся односторонним заявлением вендора.

### 3. Perpetua - цены
- Проверка: Xneeti, «Perpetua Pricing in 2026: Plans, & Real Costs», 2026-05-12, https://xneeti.com/blog/perpetua-pricing (доступ 2026-09-02): Essentials «$695/mo (flat)», «Up to $10,000 monthly ad spend»; Growth «$695/mo + % of ad spend», «Ad spend above $10,000/mo», процент «not publicly disclosed»; Premium «Custom % of ad spend», «Typically $500,000+/mo ad spend».
- Совпадение с живой страницей perpetua.io/pricing (r1) полное. Свежесть: сторонний источник 3,7 мес., первичная страница прочитана 2026-09-02 - планка «<= 3 мес.» для цен выполнена первичным источником.
- Вердикт: verified.

### 4. Teikametrics - ARI suite и Refunds Recovery во всех тарифах
- Проверка (сниппеты): G2, «Teikametrics Pricing 2026», https://www.g2.com/products/teikametrics/pricing и Xneeti, «Teikametrics Pricing in 2026», https://xneeti.com/blog/teikametrics-pricing (даты страниц не считаны; доступ 2026-09-02). Сводка выдачи: «The ARI strategic suite includes Ads, Catalog, Inventory, Insights», trial даёт «the ARI strategic suite covering ads, catalog, inventory, and insights, plus refunds recovery and Teikacademy training»; Essentials «$179 per month» / «$149/month» годовая, до «$10K in monthly ad spend»; выше - «+3% of ad spend over $10K».
- Оговорка: агрегаторы цен, скорее всего, переписывают страницу вендора (те же формулировки), поэтому независимость данных слабая. Расхождений с r1 нет.
- Вердикт: verified (сниппет-уровень, средняя уверенность).

### 5. Amazon Ads Agent по версии SellerApp
- Проверка: Adweek (Trishla Ostwal, Kendra Barnett), «Amazon's Ads Agent Is Here, Alongside a New Ads Interface», ноябрь 2025, https://www.adweek.com/media/amazon-ai-ads-agent-campaign-manager/ (доступ 2026-09-02): анонс на unBoxed (ноябрь 2025); агент «can draft campaigns, optimize bids, manage targeting across channels, and engage in media buying»; работает внутри AMC и DSP; для AMC переводит запросы в SQL (цитата Kelly MacLean, VP Amazon DSP). Adweek не упоминает approval-шаг и не уточняет статус беты.
- Дополнительно (сниппеты): Feedvisor, «What is Amazon Ads Agent?», 2026, https://feedvisor.com/university/what-is-amazon-ads-agent/ - «Every action surfaces as a summary you approve before anything goes live»; PPC Land, https://ppc.land/amazon-launches-ai-agent-for-automated-campaign-management/ - «launched in open beta on November 11, 2025».
- Уточнения к формулировке SellerApp: (а) «бета в течение 2026» - точнее «open beta с 11.11.2025», продолжается в 2026; (б) доступ «в основном DSP/AMC» согласуется с Adweek и первичным анонсом Amazon (r2: AMC + US DSP Multimedia); при этом один из recap-обзоров в выдаче называет Ads Agent «AI assistant within campaign setup for Sponsored Ads» - это расходится с тезисом «недоступен SP-only селлерам» и оставляет вопрос о доступности для SP открытым (первичный источник Amazon SP-доступ не заявляет).
- Вердикт: verified (два независимых издателя: Adweek + Feedvisor/PPC Land; плюс первичный Amazon из r2); доступность для SP-only селлеров - не закрыта.

### 6. SellerStack Inventory Protection - пороги и восстановление
- Проверка: поиск по «SellerStack inventory protection bid down 25% 50% 90%» с исключением домена вендора вернул только общие статьи об inventory-aware PPC (Seller Labs, Optmyzr, SPS Commerce, форумы Seller Central) без упоминания SellerStack и без конкретных порогов. Ни одного стороннего описания продукта не найдено.
- Вердикт: unverified - утверждение остаётся на единственном источнике (страница вендора, июнь 2026); в дайджесте оставить с пометкой «односторонне».

### 7. m19 - guardrails в тарифах
- Проверка: RevenueGeeks, «m19 Review 2026», обновлено 2026-08-09, https://revenuegeeks.com/software/m19 (доступ 2026-09-02): Autopilot «$59/mo (€49), fixed», SP only; Professional «$479/mo + 3% of ad spend (€400)» с SB/SD/DSP, AMC-отчётами, dayparting; «TACoS targeting» - «Professional-only». В обзоре нет «target daily spend», «target monthly spend», «inventory threshold», «peak season boost».
- Сниппет Orange Klik, «Demo Mondays #69 - M19», дата неизвестна, https://orangeklik.com/demo-m19/: есть «minimum daily spending» (не оптимизировать ACoS, пока расход ниже порога) и стратегия «Low inventory» (ACoS ~3 % для товаров с низким остатком).
- Вердикт: verified частично - цены и TACOS Targeting подтверждены (с уточнением: TACOS только в Professional, чего в дайджесте r2 не было); daily-spend и inventory-порог подтверждены на уровне сниппета демо; «Target monthly spend» и «Peak season Boost option» - только страница вендора.

### 8. Amazon Ads Agent - первичные capability-claims
- Проверка: Adweek (см. п.5) подтверждает drafting кампаний, управление таргетингом, SQL для AMC из естественного языка. Сниппеты: Feedvisor - «Bulk actions run in seconds across hundreds of campaigns ... pausing or adjusting pacing at scale», «sifts tens of thousands of Amazon audience segments», генерирует и запускает AMC SQL, «Every action surfaces as a summary you approve before anything goes live»; PPC Land, «Amazon launches AI agent for automated campaign management», https://ppc.land/amazon-launches-ai-agent-for-automated-campaign-management/; MediaPost, 2025-11-11, https://www.mediapost.com/publications/article/410591/amazon-reboots-ads-system-agents-for-advertising.html (только заголовок).
- Вердикт: verified (первичный Amazon + Adweek + Feedvisor). Оговорка: все сторонние описания в конечном счёте восходят к анонсу Amazon; независимых тестов продукта не найдено.

## Что не удалось проверить в бюджет
- SellerStack (п.6) - нет стороннего покрытия продукта.
- Pacvue «Net PPM» (п.2), m19 «Target monthly spend» и «Peak season Boost» (п.7) - только вендор.
- Доступность Amazon Ads Agent для SP-only селлеров (п.5) - источники расходятся на уровне сниппетов; первичный Amazon SP не упоминает.
- Ни для одного из утверждений 1, 5, 8 не найдено независимого тестирования продукта: сторонние издатели пересказывают анонсы вендоров. Дифференциацию строить на «что заявлено», а не на «что делает».
