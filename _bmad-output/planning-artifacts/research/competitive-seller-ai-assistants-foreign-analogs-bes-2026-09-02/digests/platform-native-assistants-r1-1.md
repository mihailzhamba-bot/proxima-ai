# platform-native-assistants - round 1

Дата доступа ко всем источникам: 2026-09-02. Бюджет: 18 вызовов инструментов, 7 прочитанных страниц (2 primary-страницы не открылись: 403 / пустая заглушка), остальное - сниппеты поиска (ниже помечены как «сниппет», уверенность low).

Карта сегмента по итогам раунда 1:
- Лидеры (агентный/аналитический ассистент внутри Seller Central-панели, бесплатно): **Amazon Seller Assistant** (US, агентные действия с одобрением), **楽天 RMS AI アシスタント β版** (с модулем анализа R-Karte), **Allegro asystent AI** (апрель 2026).
- Челленджеры: **Mercado Libre Asistente Inteligente** (рекомендации + черновики ответов, ручное одобрение), **Taobao/Tmall 生意参谋** (аналитика, с 2024 бесплатна для всех), **Shopee Shop AI Assistant** (только чат/поддержка), **Lazada Lazzie Seller / LISA** (чат, риск-оценка магазина - только сниппет).
- Wildcard: **Flipkart Seller Lens** (Chrome-расширение с product research + «что будет популярно в следующем месяце» - только сниппет, primary-страница не отдаёт контент).
- Не найдено в этом раунде (см. «Не нашёл»): Coupang Wing AI / CoupangData, Trendyol «Ortak», 生意管家, Nubimetrics.

## Что искал и что нашёл (по продуктам)

### Amazon Seller Assistant (agentic AI, Seller Central)

**(A) Утренняя сводка / алерты.** Ежедневного дайджеста как отдельной сущности не описано; вместо него - постоянный мониторинг: ассистент «actively monitor inventory levels, alerting sellers to actions they can take to optimize their costs and growth», в том числе флажки на медленно оборачиваемые товары до начисления платы за хранение (About Amazon, дата публикации на странице не указана, объявление датируется 17.09.2025 по CNBC/TechCrunch, https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai, доступ 2026-09-02). Канал - Seller Central; про push/e-mail/мессенджер источник молчит. Независимый обзор добавляет: «Monitors FBA inventory levels in real time. Proactively flags slow-moving products before long-term storage fees hit» и Canvas - визуальные дашборды на вопросы на естественном языке, запущен в марте 2026 для US и UK (Seller Sprite, 2026-07-17, https://www.sellersprite.com/en/blog/amazon-ai-seller-assistant-agentic-2026, доступ 2026-09-02).

**(B) Аномалия → диагноз → действие.** Ассистент «continuously monitor a seller's account status and surface potential issues and actions», по комплаенсу «guides sellers step-by-step through the process, explaining which specific standards apply»; действие выполняется только после одобрения: «If the seller approves, Seller Assistant implements the solution» (About Amazon, там же). Это самый явный approval-gate в сегменте. Seller Sprite фиксирует риск автоправок: «An AI-generated listing update that replaces your carefully researched keywords with more generic phrases can cause ranking drops within 72 hours» и советует валидировать предложения по keyword-данным до принятия (Seller Sprite, 2026-07-17, там же).

**(C) Память решений / проверка результата.** Ни один из двух источников не упоминает запись принятого решения и сравнение expected vs actual. Не найдено.

**(D) Прогноз спроса / запасов.** «Analyzes demand patterns and prepares shipment recommendations to reduce excess inventory and stockouts» (About Amazon, там же); метод, горизонт, сезонность и ручные overrides не названы. Seller Sprite: «Analyzes sales patterns to recommend shipment quantities» (там же).

**(E) Реклама.** Только генерация креативов: «Creative Studio generates ad concepts from conversational prompts» (About Amazon, там же). Guardrails по бюджету, OOS-логика, реаллокация - не описаны.

**(F) Отзывы и вопросы.** Не упомянуто ни в одном источнике.

**(G) Контент / листинг.** «Enhance My Listing» - автогенерация тайтлов и буллетов (Seller Sprite, там же); сканирование листингов против policy и product-safety требований (там же). Сравнение с конкурентами и алерты на изменение листинга - не описаны.

**Цены и упаковка.** «available to all sellers in the U.S. store and will be rolled out to other countries in the coming months, at no additional cost» (About Amazon, там же). «No premium tier - available to all Seller Central users», без per-action fee (Seller Sprite, 2026-07-17). Отдельной pricing-страницы нет (бесплатная функция).

**Позиционирование vs продукт.** Claim: агент, который «reason, plan, and help take action» (сниппет поиска About Amazon). Gap: заявленные действия ограничены инвентарём, комплаенсом, листингом, креативами; реклама (ставки/бюджеты), отзывы, память решений отсутствуют в описаниях.

**Траектория.** Декабрь 2025 - US rollout всем 3P-продавцам; март 2026 - Canvas (US/UK); Q1-Q2 2026 - расширение на EU/UK (Seller Sprite, 2026-07-17). Технологии: Amazon Bedrock, Amazon Nova и Anthropic Claude (About Amazon, там же).

**Голос клиентов.** Seller Sprite - единственный независимый источник; жалоб продавцов не документирует, предупреждает о рисках автоправок листинга. Форумные 1-3★ отзывы в этом раунде не найдены.

### 楽天市場 RMS AI アシスタント β版 (R-Karte, R-Messe, R-Storefront)

**(A)** Модуль «R-Karte：店舗カルテ分析支援AI» - AI-разбор карточки магазина (динамика продаж), без указания ежедневной рассылки или расписания (ECのミカタ, 2025-01-10, https://ecnomikata.com/original_news/45637/, доступ 2026-09-02). Сниппет поиска: функции включают «自店舗の売り上げ傾向などのデータ分析・解説» (сниппет, low).

**(B)** Объяснение динамики продаж есть, цепочка «диагноз → рекомендованное действие → одобрение» в источнике не описана.

**(C)** Не найдено.

**(D)** Не найдено.

**(E)** Не найдено.

**(F)** «R-Messe：問い合わせ回答作成支援AI» - генерация ответов на обращения покупателей; сценарий - магазины с большим объёмом обращений и малым штатом отмечают «業務効率が上がった» (ECのミカタ, там же). Автоотправка не описана - подразумевается черновик.

**(G)** «R-Storefront：商品説明文作成支援AI、商品画像加工支援AI»; генерация фона изображения около 30 сек, 7 шаблонов (ECのミカタ, там же). Ограничение по авторским правам на загружаемые изображения (там же).

**Цены.** Стоимость в статье не указана; по сниппетам Finner/EC-HOWTO - «追加の費用は一切かかりません» (сниппет, low).

**Траектория.** β-версия с марта 2024 (сниппет, low); цель Rakuten - проект «トリプル20» - +20% к маркетинговой, операционной и клиентской эффективности (ECのミカタ, 2025-01-10).

**Traction.** «店舗様全体のうち、一度でも利用したことのある店舗様は半数以上にのぼり、利用が定着している店舗様は20％を超えました» (ECのミカタ, 2025-01-10) - один издатель, вероятно со слов Rakuten; второго независимого подтверждения нет → не verified.

**Голос клиентов.** Сниппет Finner: β-версия, «機能ごとに精度の差があります» (сниппет, low).

### Taobao/Tmall 生意参谋

**(A)-(G)** Из primary-источника извлечено только про модель монетизации: с апреля 2024 «原先的三个付费版本标准版、专业版、旗舰版已全部升级为一个全新市场洞察版本，所有满足条件的商家均可免费使用», уже оплатившим - «一键申请权益领取及未使用费用全额退还»; в той же волне бесплатными стали 店小蜜 (чат-бот поддержки) и 图片空间 (阿里云创新中心, 2024-03-27, https://startup.aliyun.com/info/1083455.html, доступ 2026-09-02). AI-функции (аномалии, прогноз) в этой странице не упомянуты. Сниппет eshutong: «AI算法自动识别异常波动、趋势变化，辅助运营决策 … 智能趋势预测» (сниппет, маркетинговый регистр, low). Сниппет Sina (2025-04-03) про «上上参谋» с DeepSeek-R1 относится к другому продукту (数位大数据), не к Taobao - это ловушка одноимённости. 生意管家 не найден.

**Цены.** Бесплатно для всех продавцов с 04.2024 (阿里云创新中心, 2024-03-27). Свежесть >3 мес - требует перепроверки живой страницы в раунде 2.

### Mercado Libre - Asistente Inteligente para Vendedores

**(A)** Primary-страница https://vendedores.mercadolibre.com.mx/asistente вернула 403; по сниппету поиска ассистент даёт «recomendaciones para descubrir qué publicaciones o aspectos de tu negocio necesitan atención», «analiza tu negocio, publicaciones activas, historial y rendimiento» (сниппет Mercado Libre, low). Ежедневная сводка не упомянута.

**(B)** Сниппет: улучшение тайтлов/описаний, проверка конкурентности цены, анализ производительности, создание/корректировка промо (сниппет, low). Действия по цене/промо - через продавца, судя по формулировке «recomendaciones».

**(C), (D), (E)** Не найдено.

**(F)** Нативный AI «Suggests draft responses for incoming questions», «El vendedor debe revisar y aprobar manualmente cada sugerencia antes de que se envíe al comprador»; при этом 43% вопросов приходят вне рабочего времени, и автор называет нативный инструмент «una herramienta de productividad, no una herramienta de automatización» (shopao.io - конкурент, продающий автоответы, 2026-04-09 / обновл. 07.2026, https://shopao.io/es/blog/ia-para-vendedores-mercadolibre-2026, доступ 2026-09-02). Источник заинтересованный - уверенность medium; цифра 43% не подтверждена вторым источником.

**(G)** Сниппет merca20: бесплатный и безлимитный генератор коротких видео из карточки, представлен 01.09.2025 на Mercado Libre Experience 2025 (сниппет, low).

**Цены.** Нативный AI бесплатен, без интеграции (shopao.io, там же).

**Nubimetrics** - не найден в этом раунде (в shopao не упомянут).

### Shopee Shop AI Assistant

**(F)** «Provides immediate answers to common queries», рекомендует товары, помогает с трекингом заказов, настраиваемые FAQ и welcome-сообщения; после активации отвечает на pre- и post-sales вопросы автоматически, «available to selected sellers» в Seller Centre (Exabytes, 2025-06-23, https://www.exabytes.my/blog/shopee-shop-ai-assistant/, доступ 2026-09-02). Human-approval не упомянут - автоответ. Стоимость не указана.

**(A)-(E), (G)** Не найдено. Сниппет: партнёрство Shopee с OpenAI с начала 2025 (сниппет, low).

### Lazada (Lazzie Seller, LISA)

Только сниппеты (low): «Lazzie Seller is a dedicated AI assistant that helps with customer inquiries, quick navigation, and store risk assessments»; LISA - AI-ответы покупателям; AI-перевод контента; на Lazada Seller Summit 2025 анонсированы AI-инструменты «from onboarding and operations to campaign execution» (сниппеты bigseller.com / malaymail.com, low). Отдельно: отчёт Lazada - три из четырёх продавцов ЮВА нуждаются в помощи с внедрением AI (сниппет PR Newswire, low).

### Allegro - asystent AI w panelu sprzedaży + Allegro Analytics

**(A)** Ассистент в панели продавца даёт «real-time account insights»; проактивные дайджесты не описаны (Allegro press, 2026-04-29, https://media.allegro.pl/456160-ai-wesprze-sprzedajacych-na-allegro-wystartowal-osobisty-asystent-dostepny-w-panelu-sprzedazy, доступ 2026-09-02).

**(B)** Ассистент «wyjaśnić zmiany w punktacji jakości sprzedaży i wskaże obszary do optymalizacji» - объясняет изменение балла качества продаж и указывает зоны оптимизации; отвечает на вопросы о правилах, опираясь на «wszystkich regulaminów, materiałów pomocowych oraz treści szkoleniowych Akademii Allegro» (Allegro press, там же). Действий и approval-модели нет - советник.

**(C), (D), (F)** Не найдено.

**(E), (G)** В планах: «offer optimization, intelligent pricing management, and logistics support» - будущее время, не факт (Allegro press, там же).

**Цены.** «Asystent jest już dostępny dla wszystkich partnerów na Allegro», стоимость не раскрыта (там же). Allegro Analytics - отдельный аналитический продукт (транзакции, продано штук, стоимость продаж, распределение цен по категории) по сниппету vsprint.pl (сниппет, low); pricing-страница не прочитана.

**Траектория.** Первая фаза, «Development will be ongoing based on seller interactions» (Allegro press, 2026-04-29).

### Flipkart Seller Lens

Primary-страница https://seller.flipkart.com/seller-lens отдала только общий заголовок, содержимого нет. По сниппетам: «1st Product Research Tool for Flipkart Sellers», показывает impressions, ranking, top keywords, сравнение цен, «Tells you which items will be popular next month so you can stock up early», формат - дашборд + Chrome-расширение (сниппеты gonukkad.com / YouTube, low). Метод прогноза, алерты, A-G кроме (D)-(G) - не найдено.

### Trendyol

Только сниппеты (low): Trendyol LLM (7 версий за ~2 года) генерирует описания на десятках языков и переводит вопросы покупателей; платформа «Trendyol AI Agent»; листинг для экспорта ускорен на 60% (сниппеты AA / gazeteoksijen, low). Продукт «Ortak» не найден.

### Coupang Wing

Поиск по-корейски не дал AI-ассистента; Wing описан как общая система управления продажами (сниппет marketplace.coupang.com, low). CoupangData не найден.

## Claims (нумерованный список)

1. Amazon Seller Assistant мониторит инвентарь и алертит о действиях, включая медленно оборачиваемые товары до платы за хранение | features | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | 2025-09-17 | accessed 2026-09-02 | high | yes
2. Amazon Seller Assistant выполняет решение только после одобрения продавца («If the seller approves, Seller Assistant implements the solution») | features | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | 2025-09-17 | accessed 2026-09-02 | high | yes
3. Amazon Seller Assistant анализирует паттерны спроса и готовит рекомендации по отгрузкам (метод/горизонт не названы) | features | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | 2025-09-17 | accessed 2026-09-02 | high | no
4. Amazon Seller Assistant бесплатен для всех US-продавцов, без доплаты, расширение на другие страны | pricing | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | 2025-09-17 | accessed 2026-09-02 | high | no
5. Amazon Seller Assistant: no premium tier, без per-action fee; rollout US 12.2025, Canvas 03.2026 (US/UK), EU/UK Q1-Q2 2026 | pricing | https://www.sellersprite.com/en/blog/amazon-ai-seller-assistant-agentic-2026 | Seller Sprite | 2026-07-17 | accessed 2026-09-02 | medium | yes
6. Риск автоправок листинга: замена ключевых слов на generic может обрушить ранжирование в 72 часа - советуют валидировать до принятия | sentiment | https://www.sellersprite.com/en/blog/amazon-ai-seller-assistant-agentic-2026 | Seller Sprite | 2026-07-17 | accessed 2026-09-02 | medium | yes
7. Amazon Seller Assistant работает на Bedrock, Amazon Nova и Anthropic Claude | trajectory | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | 2025-09-17 | accessed 2026-09-02 | high | no
8. Rakuten RMS AI アシスタント β版 включает R-Storefront (описания, изображения), R-Messe (ответы на обращения), R-Karte (анализ карточки магазина), AI-чатбот | features | https://ecnomikata.com/original_news/45637/ | ECのミカタ | 2025-01-10 | accessed 2026-09-02 | high | no
9. Более половины магазинов Rakuten пробовали RMS AI アシスタント, регулярно используют >20% | traction | https://ecnomikata.com/original_news/45637/ | ECのミカタ | 2025-01-10 | accessed 2026-09-02 | medium | yes
10. Цель Rakuten «トリプル20» - +20% к маркетинговой, операционной и клиентской эффективности | positioning | https://ecnomikata.com/original_news/45637/ | ECのミカタ | 2025-01-10 | accessed 2026-09-02 | medium | no
11. 生意参谋 с 04.2024 бесплатен для всех продавцов; три платных версии слиты в бесплатную 市场洞察, неиспользованные платежи возвращаются | pricing | https://startup.aliyun.com/info/1083455.html | 阿里云创新中心 | 2024-03-27 | accessed 2026-09-02 | medium | no
12. Нативный AI Mercado Libre предлагает черновики ответов на вопросы; продавец обязан вручную одобрить каждый перед отправкой | features | https://shopao.io/es/blog/ia-para-vendedores-mercadolibre-2026 | shopao.io | 2026-04-09 | accessed 2026-09-02 | medium | yes
13. 43% вопросов на Mercado Libre приходят вне рабочего времени (заявление конкурента, без второго источника) | sentiment | https://shopao.io/es/blog/ia-para-vendedores-mercadolibre-2026 | shopao.io | 2026-04-09 | accessed 2026-09-02 | low | no
14. Mercado Libre Asistente Inteligente: рекомендации, какие публикации/аспекты бизнеса требуют внимания; проверка конкурентности цены; промо (сниппет, primary 403) | features | https://vendedores.mercadolibre.com.mx/asistente | Mercado Libre | unknown | accessed 2026-09-02 | low | no
15. Shopee Shop AI Assistant автоматически отвечает на pre/post-sales вопросы, настраиваемые FAQ; доступен выбранным продавцам в Seller Centre | features | https://www.exabytes.my/blog/shopee-shop-ai-assistant/ | Exabytes | 2025-06-23 | accessed 2026-09-02 | medium | no
16. Allegro asystent AI в панели продавца объясняет изменения балла качества продаж, указывает зоны оптимизации, отвечает по регламентам; доступен всем партнёрам | features | https://media.allegro.pl/456160-ai-wesprze-sprzedajacych-na-allegro-wystartowal-osobisty-asystent-dostepny-w-panelu-sprzedazy | Allegro (media.allegro.pl) | 2026-04-29 | accessed 2026-09-02 | high | yes
17. Allegro планирует расширить ассистента на оптимизацию офферов, управление ценами и логистику (будущее время) | trajectory | https://media.allegro.pl/456160-ai-wesprze-sprzedajacych-na-allegro-wystartowal-osobisty-asystent-dostepny-w-panelu-sprzedazy | Allegro | 2026-04-29 | accessed 2026-09-02 | medium | no
18. Flipkart Seller Lens - product-research инструмент (impressions, ranking, keywords, цены, «what will be popular next month»), дашборд + Chrome-расширение (сниппет) | features | https://www.gonukkad.com/blog/seller-lens-by-flipkart | GoNukkad | unknown | accessed 2026-09-02 | low | no
19. Lazada Lazzie Seller: обращения покупателей, навигация, оценка рисков магазина; LISA - AI-ответы (сниппет) | features | https://www.bigseller.com/blog/articleDetails/3130/lazada-AI-tools.htm | BigSeller | 2025 | accessed 2026-09-02 | low | no
20. Trendyol LLM генерирует описания на десятках языков и переводит вопросы покупателей; 7 версий за ~2 года (сниппет) | trajectory | https://www.aa.com.tr/tr/isdunyasi/e-ticaret/trendyol-yapay-zeka-zirvesinde-sektor-profesyonellerini-bulusturdu/700667 | Anadolu Ajansı | unknown | accessed 2026-09-02 | low | no

## Паттерны, повторяющиеся у лидеров

1. **Бесплатно и внутри панели платформы.** Amazon (claims 4-5), Rakuten (сниппеты, low), 生意参谋 (claim 11), Mercado Libre (claim 12), Allegro (claim 16). Платформы монетизируют не ассистента, а оборот; сторонний продукт не может конкурировать ценой «ниже бесплатного» - только глубиной и кросс-платформенностью.
2. **Approval-gate перед любым действием.** Amazon: «If the seller approves … implements» (claim 2); Mercado Libre: ручное одобрение каждого ответа (claim 12). Лидеры не автоматизируют без подтверждения; обратная сторона - узкое место человека (claim 13, low).
3. **Объяснение «почему» в терминах платформенного скоринга/комплаенса, а не P&L.** Allegro объясняет изменения балла качества (claim 16); Amazon - account health и какие стандарты применяются (claim 1, About Amazon). Ни у кого не найдена цепочка «аномалия продаж → причина → действие с ожидаемым эффектом».
4. **Инвентарь как первый агентный сценарий.** Amazon: slow-movers до storage fees и shipment recommendations (claims 1, 3); Allegro планирует логистику (claim 17). Метод прогноза нигде не назван.
5. **Ответы покупателям как самый распространённый генеративный модуль.** Rakuten R-Messe (claim 8), Shopee (claim 15), Lazada LISA (claim 19), Mercado Libre (claim 12). Отличие - автоотправка (Shopee) vs черновик с одобрением (MeLi, Rakuten).
6. **Отсутствие памяти решений и проверки результата** - у всех 9 продуктов область (C) пуста в найденных источниках. Это устойчивый «белый» участок сегмента (при уверенности low-medium: не найдено ≠ не существует).
7. **Утренней сводки как продукта нет** - все ассистенты reactive (чат/вопрос) или continuous-monitoring (Amazon), ни один источник не описывает ежедневный дайджест с расписанием и каналом.

## Лиды для следующего раунда

- Открыть Seller Central help-страницу Amazon Seller Assistant (не пресс-релиз) и Canvas: есть ли расписание уведомлений, e-mail/app push, какие именно действия выполняются автономно после «full autonomy features Q2 2026» (сниппет aboutamazon/others - не подтверждено).
- Противоречие: сниппет утверждает, что Amazon Seller Assistant появился «last year» как GenAI-эксперт (2024) и стал агентным в 09.2025; Seller Sprite датирует rollout 12.2025. Уточнить по primary.
- Rakuten: corp.rakuten.co.jp/news/press/2024/0430_01.html (primary) и страницы R-Karte - есть ли алерты по отклонениям продаж и как выглядит «解説».
- Allegro: pricing Allegro Analytics (платный ли), доки ассистента; независимые отзывы продавцов (forum.allegro / Facebook-группы).
- Mercado Libre: обойти 403 (другая страна: vendedores.mercadolibre.com.ar/asistente) и найти Nubimetrics отдельно; проверить цифру 43% (shopao - заинтересованный источник).
- 生意参谋: живая страница sycm.taobao.com и changelog 2025-2026 - AI-модули, 生意管家; исключить путаницу с «上上参谋» (数位大数据) и «袋鼠参谋» (Meituan).
- Coupang: искать «쿠팡 윙 AI 상품명 추천», «쿠팡 판매자 AI 답변» и CoupangData как отдельный сторонний продукт.
- Trendyol: «Trendyol Partner AI», «Trendyol satıcı paneli yapay zeka asistanı» - термин «Ortak» не нашёл.
- Flipkart: gonukkad/startuptalky для деталей Seller Lens, «Setu AI» - не искал.
- Новые платформенные ассистенты 2025-2026: TikTok Shop, Temu, Ozon-аналоги за рубежом - не покрыто.
- Seller Sprite и shopao.io - заинтересованные издатели (продают альтернативы); искать нейтральные форумы (r/FulfillmentByAmazon, Seller Central forums) для голоса клиентов.

## Не нашёл

- Coupang Wing AI-ассистент и CoupangData - ни одного релевантного результата по корейскому запросу.
- Trendyol Seller Center «Ortak» - продукт с таким именем не найден; только общие AI-новости Trendyol.
- 生意管家 - не упомянут; AI-функции 生意参谋 - только маркетинговые сниппеты.
- Nubimetrics - не всплыл ни в поиске по MeLi, ни в обзоре shopao.
- Flipkart Setu AI - не искал (бюджет); Seller Lens primary - пустая страница.
- Primary-страница Mercado Libre Asistente - 403.
- Ни у одного продукта: утренний дайджест с расписанием/каналом (A), память решений и expected-vs-actual (C), guardrails рекламы (бюджет, OOS, реаллокация) (E), алерты на изменение листинга/сравнение с конкурентами (G).
- Живые pricing-страницы: у всех ассистентов «бесплатно», отдельных pricing-страниц нет; pricing Allegro Analytics и 生意参谋 (свежее 3 мес.) не прочитаны.
- Независимые 1-3★ отзывы/форумные треды по любому из продуктов - не найдены в этом раунде.
