# amazon-analytics-alerts - независимая верификация (normal)

Дата проверки: 2026-09-02. Уровень: normal - выборочная проверка 8 load-bearing claims, по одному независимому источнику на claim. Бюджет 12 вызовов израсходован полностью (7 поисковых выдач, 5 страниц прочитано). Независимый источник = другой издатель с собственными данными; синдикации пресс-релизов (Manila Times, MartechCube, Yahoo Finance) в зачёт не шли.

Итог: verified - 5, disputed - 2, unverified - 1, overturned - 0.

## Результаты по claims

### 1. Helium 10 Alerts только с Diamond; Diamond «$359 $279 / month» - DISPUTED (цена подтверждена, гейтирование оспорено)

- Цена: независимый обзор даёт Diamond «$359» помесячно и «$279/month» при годовой оплате (GoFBAHub, 2026-06-15, https://www.gofbahub.com/helium10/diamond-plan/, доступ 2026-09-02). Поисковая выдача по ещё нескольким обзорам 2026 (demandsage, revenuegeeks, xneeti, sellersprite) сходится на тех же $279/$359 и упоминает повышение цен в апреле 2026 с удалением Starter-плана (сниппеты, доступ 2026-09-02). Цена - verified.
- Гейтирование Alerts: претензия «только с Diamond» оспаривается двумя независимыми источниками. SentryKit: минимальный план для Alerts - «the Platinum plan», с оговоркой, что на Platinum Alerts ограничен «5 ASINs lifetime» (SentryKit, 2026-06-26, https://sentrykit.com/blog/helium-10-buy-box-alert-vs-dedicated-monitor/, доступ 2026-09-02). GoFBAHub в таблице сравнения показывает «Alert for frauds» - 20 products на Platinum vs 600 ASINs на Diamond (GoFBAHub, 2026-06-15, та же ссылка). Прайс-страница Helium 10 (по дайджесту r1/r3) маркирует «Get Notified About Listing Changes» только для Diamond+.
- Обе цифры, без усреднения: вендор - Alerts с Diamond; независимые - Alerts есть на Platinum с жёстким лимитом ASIN (5 или 20), полноценно - на Diamond. Корректная формулировка для дайджеста: «Alerts на Platinum номинально есть, но с лимитом в единицы-десятки ASIN; практически рабочий объём - только Diamond». Это меняет тезис «ежедневный мониторинг закрыт для entry-тарифа» на «закрыт по объёму, а не по факту».

### 2. Helium 10 Alerts: email/SMS/push, обновление «approximately every four days» - VERIFIED

- Каденс: «Helium 10 Alerts checks for changes approximately every 4 days»; автор называет это «a research cadence», а не мониторингом (SentryKit, 2026-06-26, https://sentrykit.com/blog/helium-10-buy-box-alert-vs-dedicated-monitor/, доступ 2026-09-02). Источник - конкурирующий вендор мониторинга Buy Box, мотивирован подчёркивать лаг, но цифра совпадает с KB Helium 10.
- Каналы: по сводке поисковой выдачи (независимые туториалы RevenueGeeks https://revenuegeeks.com/helium10-alerts/, AMZToolset https://amztoolset.com/helium-10-alerts/, доступ 2026-09-02, сниппеты) - «email, SMS and push notification using the Helium 10 app»; уточнение: «SMS notifications are only available with Diamond and higher plans» и только для критичных событий (Buy Box loss, listing suppression); email можно получать «immediately, daily, or turn off». Атрибуция конкретной фразы к конкретному URL в сводке не точная - средняя уверенность.
- Дополнение к дайджесту: SMS - Diamond+; для email есть режим «daily» - это ближайшее к «дайджесту», что есть у Helium 10.

### 3. Sellerboard: алерты listing changes/new sellers/Buy Box/fees/negative feedback/ASIN; PPC bid automation по target profitability/ACOS, harvesting - DISPUTED (алерты подтверждены, bid automation оспорена)

- Алерты: сводка поисковой выдачи по обзорам 2026 (DigiExe https://digiexe.com/blog/sellerboard-review/, Traksource https://traksource.com/sellerboard-review/, TheSellingGuys, доступ 2026-09-02, сниппеты) подтверждает уведомления «about listing and fee changes, negative feedback and stock shortages» и «listing updates, fees, or Buy Box loss». New sellers / ASIN changes независимо не подтверждены отдельно (не опровергнуты). Часть про алерты - verified.
- PPC: противоречие. Те же обзоры пишут, что sellerboard «automatizes your bids by automatically customizing them based on your ACOS targets and profitability» (сниппет, доступ 2026-09-02). Но свежий обзор The Price Geek (обновлён 2026-06-26, https://www.thepricegeek.com/profit-analytics/sellerboard-review/, доступ 2026-09-02, прочитан целиком) прямо утверждает: «sellerboard includes PPC analytics showing true profit after ad spend», «it does not include bid management or campaign creation. A separate PPC tool is needed for advertising management».
- Обе позиции, без усреднения: вендор + часть обзоров - автоматизация ставок есть; The Price Geek (июнь 2026) - только аналитика, без bid management. Возможное объяснение (гипотеза, не факт): функция есть, но заметно слабее, чем у ads-платформ, и часть обозревателей её не считает «bid management». Для дайджеста: заявленную PPC-автоматизацию sellerboard считать неподтверждённой по глубине; в сравнении с Perpetua/Helium 10 Ads не ставить в один ряд.

### 4. Amazon Seller Assistant: мониторит inventory/account health/compliance/CS; действует только с одобрения; бесплатно; всем US-продавцам - VERIFIED

- Независимые издания в день анонса: TechCrunch (2025-09-17, https://techcrunch.com/2025/09/17/amazon-launches-ai-agent-to-help-sellers-complete-tasks-and-manage-their-businesses/, доступ 2026-09-02, сниппет): «always-on AI agent», «currently available to U.S. merchants at no cost and will be introduced in more countries in the coming months», «The company doesn't currently plan to charge merchants». CNBC (2025-09-17, https://www.cnbc.com/2025/09/17/amazon-ai-agent-sellers.html, доступ 2026-09-02, сниппет): «can monitor merchant inventory levels, analyze demand patterns, optimize shipments, identify slow-moving products before they incur storage fees and suggest price markdowns»; «can take action on a merchant's behalf with their permission». Также Retail Dive, PYMNTS, Digital Commerce 360 (2025-09-17/18) - согласуются.
- Оговорка: все издания пересказывают один анонс Amazon (Accelerate 2025), собственных данных о фактическом использовании у них нет; но для feature-claim это норма. «Account health / compliance» в сниппетах CNBC/TechCrunch явно не упомянуты - подтверждены только по первичному тексту Amazon; не опровергнуты.

### 5. DataHawk Sherlock: детектирует shifts, анализирует факторы, «most likely explanation», рекомендует действия, «advises - does not automate» - VERIFIED (с оговоркой)

- Независимый обзор: Sherlock «is designed to detect performance anomalies in your marketplace data, diagnose root causes, and recommend actions»; «As of June 2026, Sherlock is still in limited beta with a waitlist and is not yet generally available to all DataHawk customers» (Hack'celeration, 2026-06, https://hackceleration.com/labs/review/datahawk, доступ 2026-09-02, сниппет). Цепочка «что изменилось - почему - что делать» подтверждена.
- Не подтверждено независимо: формулировка «advises - it does not automate» (нет упоминания в сниппете; не опровергнуто - обзор не приписывает Sherlock исполнение действий). Список анализируемых факторов (Buy Box/pricing/ads/reviews/rankings) - только вендор. Статус beta означает, что независимых пользовательских свидетельств о качестве диагноза нет; capability-claim держится на vendor-описании + одном обзоре.

### 6. Perpetua OOS: рекомендация паузы при инвентаре ниже порога; «creating a strategy does not automatically make changes to goals» - UNVERIFIED

- Поиск (perpetua.io исключён) не дал независимого источника, описывающего именно inventory-рекомендацию паузы и её не-автоматический характер. Ближайшее: Sitruna пишет, что Perpetua позволяет «adjusting ACoS to inventory levels» и что уровень запасов - один из сигналов алгоритма ставок (Sitruna, дата неизвестна, https://www.sitruna.com/post/perpetua-review-how-ad-tech-can-help-your-sales-skyrocket, доступ 2026-09-02, сниппет) - это про корректировку ставок, не про рекомендацию паузы с ручным подтверждением. Optmyzr и Intentwise описывают отраслевой паттерн «pause when Days of Supply < N» для своих продуктов, не для Perpetua.
- Claim остаётся на единственном источнике (Perpetua Help Center, по сниппету, страница не открывалась и в r1). Флаг: в дайджесте держать как «по документации вендора, не проверено».

### 7. Helium 10 на Trustpilot: 2.1/5, 712 отзывов, 54% - 5 звёзд, 38% - 1 звезда - VERIFIED (прямое повторное измерение)

- Живая страница Trustpilot на 2026-09-02: TrustScore 2.1, 712 отзывов, распределение 5★ 54% / 4★ 3% / 3★ 2% / 2★ 3% / 1★ 38% (Trustpilot, https://www.trustpilot.com/review/helium10.com, доступ 2026-09-02). Числа совпадают с дайджестом r2 один в один. Trustpilot отмечает, что компания не запрашивала отзывы недавно и не отвечает на негатив.
- Оговорка по методике: это повторное чтение первоисточника, а не второй независимый набор данных (G2/Capterra в бюджет не вошли). Для sentiment-класса при normal-уровне считаю достаточным: claim - прямое измерение публичной метрики, а не интерпретация. Независимый ракурс на причины (поляризация, рост цен, удаление функций, отказы в возврате) совпадает с обзорами BagEngine («Is It Still Worth It After the Price Hike?», https://bagengine.com/articles/helium-10-review, доступ 2026-09-02, только заголовок из выдачи).

### 8. Агент «Helium» (2026-08-24): корневые причины, «next best actions», без «write execution» - VERIFIED

- Независимый обзор (не синдикация пресс-релиза), опубликован до запуска: «Helium goes live on August 24, 2026»; пример диагноза «Your margin dropped from 22% to 18% this month. Higher TACOS on your top ASIN is the main reason»; пример рекомендации «Fix the listing on this ASIN first, then move budget off these two campaigns and into your winners»; исполнение: «does not pause campaigns, change bids, move budgets», нет «access to change your campaigns, bids, or budgets»; «Helium is included with the Helium 10 Diamond plan at no extra cost» (Mastery Blogging, 2026-08-15, https://www.masteryblogging.com/helium-review/, доступ 2026-09-02). Красный флаг: сайт похож на affiliate-блог, вероятно писал по материалам вендора до релиза; но он даёт независимую формулировку «read-only», совпадающую с пресс-релизом («write execution capabilities soon» - по сводке выдачи, MartechCube/Manila Times - синдикации, в зачёт не идут).
- Уточнение к дайджесту r2: план для агента - Diamond (в r2 стоял UNKNOWN; в r3 уже «Included in Diamond» по прайс-странице - теперь подтверждено независимо).

## Что это меняет в выводах дайджестов

1. Тезис «алерты закрыты для entry-тарифа Helium 10» смягчить: на Platinum Alerts есть с лимитом единиц-десятков ASIN (claim 1). Аргумент про ценовую боль остаётся, но в форме «лимиты, а не отсутствие».
2. PPC-автоматизацию sellerboard не ставить в один ряд с Perpetua/Helium 10 Ads - независимый обзор июня 2026 отрицает bid management (claim 3).
3. Perpetua OOS-рекомендация - единственный источник, держать с флагом (claim 6).
4. Helium 10 email-алерты имеют режим «daily» - это ближайший аналог дайджеста в сегменте; в паттерне «утреннего брифа нет ни у кого» стоит оговорить (claim 2, сниппет, средняя уверенность).

## Не проверено (за бюджетом)

- G2/Capterra как второй независимый набор по sentiment Helium 10.
- Trustpilot sellerboard (не в списке load-bearing).
- Полный текст Perpetua Help Center (article 7120742) и любое независимое описание inventory-recommendations Perpetua.
- Sellerboard: «new sellers» и «ASIN changes» как отдельные типы алертов; глубина bid automation (help-центр sellerboard).
- Traction Amazon Seller Assistant (230k MAU / 90% acceptance) - не в списке, остаётся single-publisher.
