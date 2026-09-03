# c1-c5-demand-stock-events - round 1

Дата раунда: 2026-09-02. Бюджет: 18 вызовов инструментов, 10 прочитанных источников (2 страницы MPSTATS не отдали контент). Все даты доступа - 2026-09-02.

## Что искал и что нашёл

### Карта: кто что предлагает (C1 - просадки/диагноз, C5 - ABC/закупки)

**JVO (jvo.ru) - единственный из прочитанных российских провайдеров, кто явно продаёт «событийный диагноз» просадок.** Инструмент «События» отслеживает «управлением ценой», «отгрузок», «изменений в карточках», «действия конкурентов», «характеристик и описания» и показывает «все что в этот день произошло с нашей карточкой»; воронка описана как «просмотры, добавления в корзину и заказы» с промежуточными конверсиями, и сервис «мгновенно определяет на каком этапе воронки произошли проблемы» (JVO blog, 2024-02-06, https://jvo.ru/blog/jvo-sobytiya, доступ 2026-09-02). Пороги, окна baseline и источник сезонности на странице не раскрыты; упоминается «личный api кабинет» как источник данных (там же). На главной jvo.ru «События» присутствует в навигации наряду с «Агент ценообразования», «Агент рекламы», «Дашборд», «Логистика», но цены на странице не показаны - только ссылка «Тарифы» (JVO, дата неизвестна, https://jvo.ru/, доступ 2026-09-02).

**Sirena AI (sirena-ai.ru)** - ежедневные отчёты («отчёты — ежедневно»), подключение через «API-токен Wildberries» за 2 минуты, блок «Управление остатками» с предупреждениями о дефиците и «оптимальную поставку», пример сигнала «Частичный OOS менее чем через 14 дней»; на дашборде-примере флаги «12 товаров с низким рейтингом» и «8 товаров с отрицательной маржой»; «Воронка продаж» упомянута; ABC и событийные объяснения на странице не найдены; тарифы не отрисовались («Загрузка тарифов...»), есть 24-часовой бесплатный доступ (SIRENA AI, дата неизвестна, https://sirena-ai.ru/, доступ 2026-09-02). Вторичный каталог a2is.ru указывает «от 490 руб/мес», бесплатную версию и пробный период, рейтинг 5/5 по 22 отзывам (a2is.ru, дата неизвестна, https://a2is.ru/catalog/servisy-analitiki-marketplejsov/sirena-ai, доступ 2026-09-02).

**Маяк (mayak.bz)** - «Точный ABC-анализ» с делением групп по 80% / 15% / 5% выручки, «Расчет поставок по складам» (когда и куда поставлять, предложение новых складов), «Таблица с ключевыми показателями» (прибыль по SKU, изменение процента выкупа, возвраты, маржинальность); заявлен статус «официальным авторизованным партнером Wildberries», данные «с 2020 года», «демо-доступ 3 дня»; рублёвые цены на этой странице не указаны (Маяк, дата неизвестна, https://mayak.bz/commodity-analytics, доступ 2026-09-02).

**Moneyplace (moneyplace.io)** - «ABC-анализ, XYZ-анализ и другие отчёты» в API-дашборде, «Расчет и контроль поставок»: «получайте уведомления, когда нужно поставлять товар на склад и через сколько дней он закончится», цель - «избежать падения продаж и позиций»; данные обновляются «каждый день», сбор «4 раза в сутки»; отдельной воронки нет (упомянута «конверсия карточки товара»); цены - только форма консультации (Moneyplace, дата неизвестна, https://moneyplace.io/prodaji-na-wildberries, доступ 2026-09-02).

**MPSTATS** - по сниппету поиска в базе знаний есть раздел «Уведомления» (создание уведомлений по SKU/бренду/продавцу) и графики «заказы + остатки + цены» для понимания причин изменения заказов; страницы wiki.mpstats.io и mpstats.io/pricing при прямом чтении вернули только заголовок (wiki - «Уведомления | База знаний MPSTATS», pricing - «Вход в личный кабинет MPSTATS»), поэтому пороги и цены не подтверждены (MPSTATS wiki, дата неизвестна, https://wiki.mpstats.io/ru/Возможности/Уведомления, доступ 2026-09-02 - контент не получен).

### Глобальные провайдеры (C5-методика)

**sellerboard** - планировщик запасов учитывает «Historic sales and sales velocity», «Seasonal trends and anticipated demand spikes», «Supplier settings, including manufacturing and shipping times», «Your preferences for reorder frequency and liquidity»; выдаёт «days of stock left, and days until your next order»; цена «Starting at $15 Monthly», «1 month free trial»; точное окно velocity и формула reorder не раскрыты (sellerboard, дата неизвестна, https://sellerboard.com/inventory, доступ 2026-09-02). По сниппету блога sellerboard от 2025-05-26 добавлена метрика упущенной прибыли из-за стокаута «over the past 90 days, based on your product's sales velocity and average profit per unit» (sellerboard blog, 2025-05-26, https://blog.sellerboard.com/2025/05/26/whats-new-in-sellerboard-awd-stock-sync-missed-profit-tracking-and-a-new-cogs-interface/, доступ 2026-09-02 - только сниппет).

**Inventory Planner** - определения: lead time - «The amount of time that elapses between placing a purchase order and receiving its products into stock»; days of stock - «The period of time for which you would like to have enough stock - in other words, the stock cover. The days of stock also represents your purchasing frequency»; формула safety stock и метод прогноза в этой статье не описаны (Inventory Planner Help Center, автор Monica, 2025-09-18, http://help.inventory-planner.com/articles/590496-how-to-choose-the-lead-time-and-days-of-stock, доступ 2026-09-02).

**Helium 10** - «Helium 10 applies advanced forecasting models to your sales and inventory data to provide recommendations on when to order or transfer your products»; настраиваются «lead times, reorder frequency, and shipment speeds»; алерты low stock; методика days-of-supply не раскрыта; Inventory Management доступен с тарифа Diamond ($279–$359/мес), Platinum $99–$129/мес, Enterprise от $1,499/год (Helium 10, дата неизвестна, https://www.helium10.com/tools/operations/inventory-management/, доступ 2026-09-02).

### Что говорят пользователи

JVO на crmindex.ru: рейтинг 4.6/5 по 24 отзывам; хвалят «сократила ручные операции на 80%» (2025-03-31), «сэкономил неделю на рутине», «мощная связка с моими личными системами отчетов» (2025-07-28); жалобы - «Сервис сырой! Не удобный!», «менеджер который все красиво рассказал сразу слился», «3 месяца прошло и ни чего не поменялось» (2025-01-28), нет демо перед покупкой, дорого относительно конкурентов, нет возврата (crmindex.ru, отзывы 2025-01..2025-07, https://crmindex.ru/services/jvo, доступ 2026-09-02). Проверить, исправлены ли жалобы января 2025 к версии сентября 2026, в этом раунде не удалось.

Sirena AI на a2is.ru: «Подключила ради интереса тестовый период, осталась на годовой подписке» - система алертов «пару раз сэкономила бюджет» (2026-02-02); «Сверял данные Сирены с финотчетами ВБ — всё сходится до копейки» (2026-02-02); «Сирена все свела в один чат» (2025-06-03) (a2is.ru, https://a2is.ru/catalog/servisy-analitiki-marketplejsov/sirena-ai, доступ 2026-09-02). Все 22 отзыва с оценкой 5/5 на каталоге-агрегаторе - признак кураторской подборки, доверие низкое.

### Доказательства влияния на retention/решения

Найдены только отзывы-свидетельства (JVO: «сократила ручные операции на 80%»; Sirena: годовая подписка после триала, алерты «сэкономили бюджет»). Ни один провайдер не публикует retention-метрики или A/B-данные о влиянии функций просадок/закупок на решения продавцов. Вывод: доказательная база - анекдотическая, уровень «sentiment».

### Сводка по методам (что раскрыто)

- Baseline/пороги просадки: не раскрыты ни у JVO, ни у Sirena, ни у Moneyplace, ни у Маяка (по прочитанным страницам).
- Локализация этапа воронки: заявлена у JVO (просмотры → корзина → заказы); выкупы в описании воронки JVO отдельно не названы.
- Событийная лента: JVO (цена, отгрузки, карточка, конкуренты); у остальных - нет на прочитанных страницах.
- ABC: Маяк (80/15/5), Moneyplace (ABC+XYZ).
- Days-of-cover / рекомендации поставок: Sirena («OOS менее чем через 14 дней», «оптимальная поставка»), Moneyplace («через сколько дней он закончится»), Маяк («когда и куда поставлять»), sellerboard (days of stock left, days until next order, сезонность заявлена), Inventory Planner (lead time + days of stock как параметры), Helium 10 (forecasting models, lead time, reorder frequency).
- Сезонность: заявлена только у sellerboard («Seasonal trends»); источник не раскрыт. Явных «30/60/90-дневных рекомендаций закупки» ни у кого на прочитанных страницах.
- Данные: Sirena и JVO - API-кабинет продавца; Маяк - авторизованный партнёр WB; Moneyplace - «API-кабинет» плюс внешние данные, сбор 4 раза в сутки.

## Claims (нумерованный список)

1. JVO «События» отслеживает изменения цены, отгрузок, карточки, действия конкурентов и показывает «все что в этот день произошло с нашей карточкой» | method | https://jvo.ru/blog/jvo-sobytiya | JVO | 2024-02-06 | accessed 2026-09-02 | high | yes
2. JVO «мгновенно определяет на каком этапе воронки произошли проблемы» по воронке «просмотры, добавления в корзину и заказы»; пороги и baseline-окна не раскрыты | method | https://jvo.ru/blog/jvo-sobytiya | JVO | 2024-02-06 | accessed 2026-09-02 | high | yes
3. На прочитанных страницах JVO, Sirena AI, Маяк, Moneyplace не раскрыты числовые пороги просадки, окна baseline и источник сезонности | pattern | https://jvo.ru/blog/jvo-sobytiya | JVO (+ sirena-ai.ru, mayak.bz, moneyplace.io) | unknown | accessed 2026-09-02 | medium | yes
4. Sirena AI подключается через «API-токен Wildberries», даёт ежедневные отчёты и предупреждения «Частичный OOS менее чем через 14 дней» с «оптимальную поставку» | method | https://sirena-ai.ru/ | SIRENA AI | unknown | accessed 2026-09-02 | medium | yes
5. Sirena AI: «от 490 руб/мес», есть бесплатная версия и триал; 5/5 по 22 отзывам | pricing | https://a2is.ru/catalog/servisy-analitiki-marketplejsov/sirena-ai | a2is.ru (вторичный каталог) | unknown | accessed 2026-09-02 | low | no
6. Маяк: «Точный ABC-анализ» (80%/15%/5% выручки), «Расчет поставок по складам», «официальным авторизованным партнером Wildberries», данные с 2020, демо 3 дня | method | https://mayak.bz/commodity-analytics | Маяк | unknown | accessed 2026-09-02 | medium | no
7. Moneyplace: «ABC-анализ, XYZ-анализ», «Расчет и контроль поставок» - уведомления «когда нужно поставлять товар на склад и через сколько дней он закончится», сбор данных «4 раза в сутки» | method | https://moneyplace.io/prodaji-na-wildberries | Moneyplace | unknown | accessed 2026-09-02 | medium | no
8. sellerboard inventory planner использует «Historic sales and sales velocity», «Seasonal trends and anticipated demand spikes», lead time поставщика; выдаёт «days of stock left, and days until your next order»; «Starting at $15 Monthly» | method | https://sellerboard.com/inventory | sellerboard | unknown | accessed 2026-09-02 | medium | yes
9. sellerboard добавил метрику упущенной прибыли от стокаута за «the past 90 days, based on your product's sales velocity and average profit per unit» (по сниппету) | version | https://blog.sellerboard.com/2025/05/26/whats-new-in-sellerboard-awd-stock-sync-missed-profit-tracking-and-a-new-cogs-interface/ | sellerboard blog | 2025-05-26 | accessed 2026-09-02 | medium | no
10. Inventory Planner: lead time = «time that elapses between placing a purchase order and receiving its products into stock»; days of stock = «stock cover ... also represents your purchasing frequency» | method | http://help.inventory-planner.com/articles/590496-how-to-choose-the-lead-time-and-days-of-stock | Inventory Planner Help Center | 2025-09-18 | accessed 2026-09-02 | high | yes
11. Helium 10 Inventory Management: «advanced forecasting models», настраиваемые lead times / reorder frequency / shipment speeds; доступен с Diamond ($279–$359/мес); методика не раскрыта | pricing | https://www.helium10.com/tools/operations/inventory-management/ | Helium 10 | unknown | accessed 2026-09-02 | medium | no
12. JVO на crmindex.ru: 4.6/5 по 24 отзывам; «сократила ручные операции на 80%» (2025-03-31); «Сервис сырой! Не удобный!», «менеджер ... сразу слился», нет демо и возврата (2025-01-28) | sentiment | https://crmindex.ru/services/jvo | crmindex.ru | 2025-07-28 | accessed 2026-09-02 | medium | no
13. Sirena AI отзыв: «Подключила ради интереса тестовый период, осталась на годовой подписке», алерты «пару раз сэкономили бюджет» (2026-02-02); «всё сходится до копейки» с финотчётами WB | sentiment | https://a2is.ru/catalog/servisy-analitiki-marketplejsov/sirena-ai | a2is.ru | 2026-02-02 | accessed 2026-09-02 | low | no
14. MPSTATS имеет функцию «Уведомления» по SKU/бренду/продавцу (по сниппету поиска); страницы wiki и pricing при чтении вернули только заголовок | api | https://wiki.mpstats.io/ru/Возможности/Уведомления | MPSTATS wiki | unknown | accessed 2026-09-02 | low | no
15. Ни один из прочитанных провайдеров не публикует retention-метрики или данные о влиянии функций просадок/закупок на решения продавцов; доказательства - только отзывы | evidence | https://crmindex.ru/services/jvo | crmindex.ru / a2is.ru | 2025-07-28 | accessed 2026-09-02 | medium | no

## Лиды для следующего раунда

- Не покрыты: WBStat, SellerFox, Anabar, Shopstat, Stat4Market, Marketguru, SoStocked - нужны прямые страницы функций и тарифов.
- MPSTATS: wiki «Уведомления» и pricing не отдаются WebFetch (JS-рендер?) - пробовать mpstats.ru, wiki.mpstats.io без /ru/, или сниппеты через поиск «MPSTATS уведомления порог заказы».
- JVO: страница «Тарифы» (jvo.ru/tariffs или аналог) для цен; проверить, актуальны ли жалобы января 2025 (сырой сервис, поддержка) - искать отзывы 2026 на vc.ru / Telegram.
- Противоречие приоритетное: a2is.ru даёт Sirena AI 5/5 по 22 отзывам и «от 490 руб/мес», сама sirena-ai.ru тарифов не показывает - нужна вторая независимая цена (otzovik, vc.ru, Telegram-канал Sirena).
- Sellerboard $15/мес - одна страница; для «verified» нужна вторая (sellerboard.com/pricing или обзор 2026).
- Методика: ни один RU-провайдер не раскрывает пороги/окна; искать Habr/VC-посты «как считаем просадку заказов» от MPSTATS/JVO/Anabar, а также Helium 10 / SoStocked help-center по «days of supply» и «velocity window».
- Формула safety stock у Inventory Planner - другие статьи help-center (forecast method, seasonality).
- Воронка с выкупами (buyouts) как отдельная стадия - у JVO не названа; проверить у Маяка/Anabar.

## Не нашёл

- Числовые пороги просадки (%), окна baseline (7/14/28 дней), источник сезонности - ни у одного RU-провайдера на прочитанных страницах.
- Явные «30/60/90-дневные рекомендации закупки» с сезонностью - нигде на прочитанных страницах (sellerboard заявляет сезонность без деталей).
- Формулы safety stock - ни у Inventory Planner (в прочитанной статье), ни у Helium 10, ни у sellerboard.
- Тарифы MPSTATS, JVO, Маяк, Moneyplace в рублях с живых страниц - страницы не отдали контент или требуют консультации.
- Retention-метрики или исследования влияния на решения - только отзывы.
- Ретроспективные треды на VC.ru/Habr/Telegram про C1/C5-функции - в этом раунде не читались (бюджет).
- WBStat, SellerFox, Anabar, Shopstat, Stat4Market, Marketguru, SoStocked - не прочитаны.
