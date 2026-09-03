# platform-native-assistants - round 2

Дата доступа ко всем источникам: 2026-09-02. Бюджет раунда: 15 вызовов инструментов, ~12 источников. Четыре primary-страницы не прочитаны (Seller Central help - отдаёт только login-shell; Allegro Analytics «o narzędziu» - timeout; Business Standard и MeLi Centro de Partners - HTTP 403) - по ним использованы поисковые сниппеты с пониженной уверенностью.

## Что искал и что нашёл (по продуктам)

### Amazon Seller Assistant (Seller Central, US)

**Противоречие по датам (приоритет 1).** Primary-страница About Amazon говорит, что ассистент запущен «last year» под именем Project Amelia и теперь стал агентным, «currently available to all sellers in the U.S. store», «will be rolled out to other countries in the coming months»; дата публикации в извлечённом тексте страницы не видна (About Amazon, дата unknown, https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai, доступ 2026-09-02). Seller Sprite датировал rollout 12.2025 (прошлый раунд); Zentail и Stormy пишут о расширении на EU/UK и «full autonomy features (auto-approve mode for routine tasks) rolling out in Q2 2026» (сниппет WebSearch по Zentail Help Center https://help.zentail.com/en/articles/15452466-amazon-seller-assistant-what-it-is-and-how-to-use-seller-central-s-ai-assistant и Stormy AI https://stormy.ai/blog/amazon-seller-central-automation-ai-agent-playbook, даты unknown, доступ 2026-09-02). Противоречие не снято: primary не датирована в тексте, вторичные источники расходятся (09.2025 vs 12.2025). Официальная help-страница существует - «Seller Assistant - Seller Central's agentic assistant» https://sellercentral.amazon.com/help/hub/reference/external/GLYJTRGQCYNYAZS9?locale=en-US - но без логина отдаёт только навигацию (доступ 2026-09-02).

(A) Дайджест/алерты: primary говорит только, что ассистент будет «actively monitor inventory levels, alerting sellers to actions» и «flag slow-moving products before they incur long-term storage fees»; канал и время доставки алертов не указаны (About Amazon, unknown, https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai, доступ 2026-09-02). Сторонний MyAmazonGuy сообщает, что в ассистент интегрированы Seller News (сниппет, https://myamazonguy.com/news/amazon-seller-assistant-amelia/, unknown, доступ 2026-09-02).
(B) Аномалия → диагноз → действие: «If the seller approves, Seller Assistant implements the solution»; «act when authorized»; пример compliance - «alert sellers to specific issues, such as missing UL certifications» (About Amazon, unknown, тот же URL). Второй издатель уточняет модель одобрений: «tiered permission model where Amazon never takes action on your account without your explicit authorization, and the permission settings you configure determine whether authorization is given once (auto-approve) or per action (suggest only)» (сниппет WebSearch, Stormy AI / Zentail, unknown, URL выше, доступ 2026-09-02). Это новая для тирдауна деталь - двухуровневый guardrail «auto-approve vs suggest only» - подтверждена пока одним независимым издателем вне Amazon.
(C) Память решений / expected-vs-actual: не упоминается ни в primary, ни во вторичных источниках.
(D) Прогноз спроса/запасов: только «monitor inventory levels» и «slow-moving products»; метод, горизонт, сезонность не названы (About Amazon, unknown, URL выше).
(E) Реклама: не упоминается.
(F) Отзывы/вопросы: не упоминается.
(G) Контент: генерация A+ Content названа как автономное действие (сниппет Zentail/Stormy, unknown, URL выше); аудит изменений листинга и сравнение с конкурентами - не найдено.
Pricing: «at no additional cost» (About Amazon, unknown, URL выше). Positioning: «handle everything from routine operations to complex business strategy» - обещание шире, чем документированные действия (инвентарь, compliance, A+ контент). Голос клиентов: независимых форумных тредов в этом раунде не читал (бюджет).

### TikTok Shop Seller Assistant (Seller Center, US) - новая сущность

Primary-страница TikTok Shop Academy «Seller Assistant: From Assistant → Agentic AI» датирована 07/22/2026: ассистент может «respond to questions, reason through problems, plan next steps, take action on your behalf (with your permission)» (TikTok Shop Seller University, 2026-07-22, https://seller-us.tiktok.com/university/essay?knowledge_id=8282858242754320, доступ 2026-09-02).
(A) Проактивные алерты/дайджесты не описаны (там же).
(B) Действия с разрешения: «complete tasks—like resolving violations, changing order information»; «Generate product videos, discover promotion tools, and launch GMV Max campaigns»; механика запроса/выдачи разрешения не раскрыта (там же).
(C) Память решений - нет.
(D) Прогноз - нет.
(E) Реклама: запуск GMV Max-кампаний через ассистента; guardrails (бюджет, OOS) не описаны (там же).
(F) Отзывы/вопросы: покрытие «returns, complaints», «complaint appeals»; авто-ответы покупателям не упоминаются (там же).
(G) Контент: «product listing and approval questions», генерация видео (там же).
Pricing: не указана; «Available to all TikTok Shop sellers», «around the clock», на десктопе «fuller features», на мобильном часть функций «limited or unavailable» (там же). Social Media Today сообщает о Seller Assistant 2.0 в июньском продукт-апдейте 2026 и расширении доступа к чат-боту (сниппет WebSearch, https://www.socialmediatoday.com/news/tiktok-shop-rolls-out-new-tools-including-expanded-chatbot-access/812401/, unknown, доступ 2026-09-02).

### Rakuten RMS AI アシスタント / R-Karte

Primary подтверждён: пресс-релиз 2024-04-30 описывает «RMS AIアシスタント β版», предоставляемый «2024年3月28日（木）より順次」; ключевая аналитическая функция - в R-Karte «AIを利用した店舗カルテ分析支援（「データを解説」機能）自店舗へのアクセス人数や客単価、転換率などの指標を中心に分析し、前年対比での売り上げ傾向や特徴を解説する機能» (Rakuten Group, 2024-04-30, https://corp.rakuten.co.jp/news/press/2024/0430_01.html, доступ 2026-09-02).
(A) Алерты по отклонениям продаж по расписанию - в пресс-релизе нет; «解説» это объяснение по запросу, не push.
(B) Диагноз есть (объяснение YoY-тренда через трафик/客単価/転換率), рекомендация действия и approval-контур не описаны (там же).
(C) Нет.
(D) Нет.
(E) Нет.
(F) Черновики ответов на запросы покупателей (問い合わせ対応文の作成) и чат-бот для вопросов операторов магазина (там же).
(G) Генерация описаний товаров; обработка изображений «2024年6月頃に提供予定» (там же).
Pricing: в релизе не раскрыта. Проверка цифры «>50% магазинов пробовали, >20% используют регулярно» (ECのミカタ, прошлый раунд) вторым издателем не выполнена - остаётся одноисточниковой.

### Allegro Analytics + asystent AI

Живая страница «o narzędziu» не загрузилась (timeout, https://allegro.pl/moje-allegro/sprzedaz/allegro-analytics/o-narzedziu, доступ 2026-09-02). По сниппетам сторонних гайдов: Allegro Analytics входит в абонемент Allegro - Podstawowy 49 PLN/мес (собственные данные продаж, горизонт 6 месяцев), Profesjonalny 199 PLN/мес (рыночная аналитика, планер кампаний Allegro Ads, до 10 доп. аккаунтов), Ekspert 3 000 PLN/мес (до 50 аккаунтов, рынок за 36 месяцев, выделенный менеджер); абонемент необязателен, только для бизнес-аккаунтов, для Strefa Marek скидка 20% (сниппет WebSearch по apilo.com https://apilo.com/pl/allegro-analytics-czym-jest-i-jak-analizowac-dane-sprzedazowe/ и sklepy.ai https://sklepy.ai/abonament-allegro, даты unknown, доступ 2026-09-02). Важно для позиционирования: рыночный срез (конкуренты) - платный tier, собственные данные - базовый.
(A)-(G): новых фактов сверх прошлого раунда (ассистент объясняет изменения балла качества продаж) не получено; алерты, память решений, guardrails рекламы - не найдены. Отзывы продавцов - не искал (бюджет).

### Mercado Libre: Nubimetrics (сторонний, в Centro de Partners)

Nubimetrics присутствует в официальном Centro de Partners Mercado Libre (MX и UY): «plataforma de inteligencia de ventas» с тремя инструментами Marketplace, Competencia, Mi Negocio; цена не публикуется - «contactar al partner»; пробный период 14 дней без карты (сниппет WebSearch, Mercado Libre Centro de Partners, https://centrodepartners.mercadolibre.com.mx/apps/nubimetrics, unknown, доступ 2026-09-02; страница отдаёт 403 при прямом fetch). Инструмент контроля цен - мониторинг и сравнение цен в реальном времени (сниппет, Nubimetrics Academia, https://academia.nubimetrics.com/precios-competitivos, unknown, доступ 2026-09-02). Сравнение Nubimetrics vs Real Trends есть у WooSync (https://www.woosync.io/blog/nubimetrics-vs-real-trends-analisis-completo/, unknown) - не читал. Primary-страница нативного Asistente MeLi (403 в прошлом раунде) - обходной путь не пробовал.
(A)-(G) по Nubimetrics: подтверждены только G-соседние функции (мониторинг конкурентов, контроль цен, сравнение публикаций); утренний дайджест, диагноз, память решений, прогноз - не найдены.

### Coupang Wing

Нативного AI-ассистента снова не найдено. Ближайшее к (A): App Store-описание приложения «쿠팡 윙 판매자센터»: «즉시 처리해야 할 일이 있다면, 윙 앱이 알려주며 가격 관리 알람을 확인하고 새로운 주문을 놓치지 마세요» - push-уведомления о срочных задачах и ценовые алармы (сниппет WebSearch, Apple App Store, https://apps.apple.com/kr/app/%EC%BF%A0%ED%8C%A1-%EC%9C%99-%ED%8C%90%EB%A7%A4%EC%9E%90%EC%84%BC%ED%84%B0/id1569143887, unknown, доступ 2026-09-02). CoupangData как отдельный продукт - не всплыл и в этом раунде.

### Trendyol

Нативный AI-ассистент в панели Partner не найден; есть курс «E-Ticarette Yapay Zeka» в Trendyol Akademi (https://akademi.trendyol.com/TrainingContent?TrainingId=19408, unknown). Нишу заполняют сторонние турецкие сервисы: Sopyo AI Hub (автозаполнение категории/бренда/атрибутов при загрузке), SETA Creative «Trendyol otomasyonu» (AI-анализ данных магазина: «günlük satışlar, 15 günlük performans, ürün bazlı reklam önerileri ve pratik büyüme adımları»), Celer/Sakans (ответы на вопросы покупателей «30 saniyeden kısa sürede» на базе описания товара, политики возврата и сроков доставки), UppyPro, RoMuAI, Yukworks (сниппеты WebSearch, https://www.sopyo.com/blog/trendyol-urun-yukleme, https://setacreative.com.tr/trendyol-otomasyonu/, https://sakans.com/blog/celer-ai-trendyol-30-saniyede-cevap, unknown, доступ 2026-09-02). Термин «Ortak» - не подтверждён.

### Flipkart Ask Setu / AI-дашборды

Ask Setu - AI-инструмент в Seller Hub «under Nxt Insights on Growth tab», которому можно задать «any question related to your flipkart selling account and listings» (сниппет WebSearch, Facebook-пост агентства Signature Ecom Solutions, https://www.facebook.com/signatureecomsolutions/posts/what-is-ask-setu-ai-tool-how-to-use-it-flipkart-selling-complete-guide-sellonfli/976733654954802/, unknown, доступ 2026-09-02). Business Standard (по номеру URL - 2026-05-10) сообщает об AI-дашбордах с поддержкой хинди и региональных языков, голосовым вводом, дающих «demand forecasting, pricing intelligence, and trend analysis»; пример - продавцу посоветовали производить москитные сетки перед летним спросом, через ~45 дней он начал продажи; у Flipkart 1,4 млн продавцов (сниппет WebSearch, Business Standard, https://www.business-standard.com/companies/news/flipkart-deploys-ai-tools-to-scale-small-town-sellers-across-india-126051000611_1.html, 2026-05-10, доступ 2026-09-02; страница отдаёт 403). Метод и горизонт прогноза не названы; «Seller Lens» в результатах этого раунда не всплыл.

### 生意参谋 (Taobao/Tmall)

Подтверждено primary-новостью: с апреля 2024 все модули 生意参谋 бесплатны, ранее оплаченным подписчикам - возврат неиспользованных средств (Xinhua/新华网, 2024-03-27, http://www.news.cn/tech/20240327/4f20386bdd4645faa52900b02b51bd5c/c.html, доступ 2026-09-02). Продукт ведёт 瓴羊 (Lingyang) - официальная страница https://www.lydaas.com/product-sycm (не читал). Обзор 2026 года описывает практику «生意参谋 + 炼丹炉»: 生意参谋 «向内看» (воронка, пути посетителей, конверсия), сторонние инструменты «向外看» (рынок) (сниппет WebSearch, huo1818.com, https://www.huo1818.com/news/detail/1514, unknown, доступ 2026-09-02). AI-модули/生意管家 - не подтверждены и в этом раунде.

## Claims (нумерованный список)

1. Amazon Seller Assistant: «If the seller approves, Seller Assistant implements the solution»; «act when authorized»; доступен всем продавцам US, «no additional cost» | features | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | unknown | accessed 2026-09-02 | high | no
2. Amazon Seller Assistant: tiered permission model - «authorization is given once (auto-approve) or per action (suggest only)»; auto-approve для рутинных задач - Q2 2026, расширение на EU/UK | features | https://help.zentail.com/en/articles/15452466-amazon-seller-assistant-what-it-is-and-how-to-use-seller-central-s-ai-assistant | Zentail Help Center (+ Stormy AI, сниппет) | unknown | accessed 2026-09-02 | medium | yes
3. Amazon Seller Assistant: primary говорит «launched last year» (Project Amelia) без даты публикации; вторичные источники расходятся (09.2025 vs 12.2025) - противоречие не снято | trajectory | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | unknown | accessed 2026-09-02 | medium | no
4. Amazon Seller Assistant: мониторит инвентарь, «flag slow-moving products before they incur long-term storage fees», compliance-алерты (UL); канал/время алертов не указаны | features | https://www.aboutamazon.com/news/innovation-at-amazon/seller-assistant-agentic-ai | About Amazon | unknown | accessed 2026-09-02 | high | no
5. TikTok Shop Seller Assistant стал агентным: «take action on your behalf (with your permission)» - «resolving violations, changing order information», «launch GMV Max campaigns»; доступен всем продавцам, десктоп полнее мобильного | features | https://seller-us.tiktok.com/university/essay?knowledge_id=8282858242754320 | TikTok Shop Seller University | 2026-07-22 | accessed 2026-09-02 | high | yes
6. TikTok Shop: Seller Assistant 2.0 в продукт-апдейте июня 2026, расширенный доступ к чат-боту | trajectory | https://www.socialmediatoday.com/news/tiktok-shop-rolls-out-new-tools-including-expanded-chatbot-access/812401/ | Social Media Today | unknown | accessed 2026-09-02 | medium | no
7. Rakuten RMS AIアシスタント β: R-Karte «データを解説» анализирует アクセス人数/客単価/転換率 и объясняет «前年対比での売り上げ傾向や特徴»; rollout с 2024-03-28 | features | https://corp.rakuten.co.jp/news/press/2024/0430_01.html | Rakuten Group | 2024-04-30 | accessed 2026-09-02 | high | yes
8. Rakuten RMS AIアシスタント: черновики ответов на запросы покупателей, генерация описаний, чат-бот для операторов; обработка изображений «2024年6月頃» | features | https://corp.rakuten.co.jp/news/press/2024/0430_01.html | Rakuten Group | 2024-04-30 | accessed 2026-09-02 | high | no
9. Allegro Analytics: Podstawowy 49 PLN/мес (свои данные, 6 мес.), Profesjonalny 199 PLN/мес (рынок, планер Ads), Ekspert 3 000 PLN/мес (50 аккаунтов, 36 мес.); абонемент необязателен; Strefa Marek -20% | pricing | https://apilo.com/pl/allegro-analytics-czym-jest-i-jak-analizowac-dane-sprzedazowe/ | Apilo (+ sklepy.ai, сниппет) | unknown | accessed 2026-09-02 | medium | yes
10. Nubimetrics в официальном Centro de Partners Mercado Libre: три инструмента Marketplace / Competencia / Mi Negocio; цена - «contactar al partner»; 14 дней бесплатно без карты | pricing | https://centrodepartners.mercadolibre.com.mx/apps/nubimetrics | Mercado Libre Centro de Partners (сниппет; страница 403) | unknown | accessed 2026-09-02 | medium | no
11. Nubimetrics: контроль цен - мониторинг и сравнение цен на Mercado Libre в реальном времени | features | https://academia.nubimetrics.com/precios-competitivos | Nubimetrics Academia | unknown | accessed 2026-09-02 | low | no
12. Coupang Wing app: «즉시 처리해야 할 일이 있다면, 윙 앱이 알려주며 가격 관리 알람을 확인» - push о срочных задачах и ценовые алармы; нативного AI-ассистента не найдено | features | https://apps.apple.com/kr/app/%EC%BF%A0%ED%8C%A1-%EC%9C%99-%ED%8C%90%EB%A7%A4%EC%9E%90%EC%84%BC%ED%84%B0/id1569143887 | Apple App Store (Coupang) | unknown | accessed 2026-09-02 | medium | no
13. Trendyol: нативного AI-ассистента в панели не найдено; нишу закрывают сторонние Sopyo AI Hub (загрузка), SETA Creative (AI-анализ: дневные продажи, 15-дневная динамика, рекламные рекомендации по SKU), Celer (ответы <30 с) | positioning | https://setacreative.com.tr/trendyol-otomasyonu/ | SETA Creative (+ Sopyo, Sakans, сниппеты) | unknown | accessed 2026-09-02 | low | no
14. Flipkart Ask Setu: AI-инструмент в Seller Hub «under Nxt Insights on Growth tab», отвечает на вопросы по аккаунту и листингам | features | https://www.facebook.com/signatureecomsolutions/posts/what-is-ask-setu-ai-tool-how-to-use-it-flipkart-selling-complete-guide-sellonfli/976733654954802/ | Signature Ecom Solutions (агентство, сниппет) | unknown | accessed 2026-09-02 | low | no
15. Flipkart: AI-дашборды на хинди/региональных языках с голосовым вводом дают «demand forecasting, pricing intelligence, and trend analysis»; кейс москитных сеток (~45 дней до старта продаж); 1,4 млн продавцов | features | https://www.business-standard.com/companies/news/flipkart-deploys-ai-tools-to-scale-small-town-sellers-across-india-126051000611_1.html | Business Standard (сниппет; 403) | 2026-05-10 | accessed 2026-09-02 | medium | yes
16. 生意参谋: с апреля 2024 все модули бесплатны, оплаченным подписчикам - возврат | pricing | http://www.news.cn/tech/20240327/4f20386bdd4645faa52900b02b51bd5c/c.html | 新华网 (Xinhua) | 2024-03-27 | accessed 2026-09-02 | high | yes
17. 生意参谋 в 2026: практика «生意参谋 (向内看) + 炼丹炉 (向外看)» - платформа даёт воронку/пути/конверсию, рынок - сторонние инструменты | positioning | https://www.huo1818.com/news/detail/1514 | huo1818.com | unknown | accessed 2026-09-02 | low | no
18. Amazon Seller Assistant: Seller News интегрированы в ассистента (Amelia) | features | https://myamazonguy.com/news/amazon-seller-assistant-amelia/ | MyAmazonGuy | unknown | accessed 2026-09-02 | low | no

## Паттерны, повторяющиеся у лидеров

1. **Агентность с явным разрешением, без документированного расписания.** Amazon («If the seller approves…», tiered auto-approve/suggest-only - claims 1-2) и TikTok Shop («take action on your behalf (with your permission)» - claim 5) оба переходят от Q&A к действиям, но ни один не описывает механику запроса разрешения, лог действий или откат. Human-in-the-loop - норма; «memory of decisions» - нет ни у кого.
2. **Объяснение YoY-отклонения через декомпозицию трафик × 客単価 × конверсия** - Rakuten R-Karte «データを解説» (claim 7); Allegro asystent объясняет изменения балла качества (прошлый раунд). Диагноз есть, рекомендованное действие и его верификация - нет.
3. **Push-алерты о срочных задачах вместо утреннего дайджеста** - Coupang Wing app (claim 12), Amazon inventory/compliance alerts (claim 4). Ни у одного продукта не найдено утренней сводки с фиксированным временем и каналом.
4. **Бесплатность нативной аналитики и монетизация рыночного среза.** 生意参谋 полностью бесплатен (claim 16); Amazon и TikTok Shop ассистенты без доплаты (claims 1, 5); Allegro берёт деньги именно за рыночную аналитику и глубину истории (claim 9). Внешние продукты (Nubimetrics, 炼丹炉, турецкие сервисы) живут на «向外看» - конкуренты, цены, рынок (claims 10-11, 13, 17).
5. **Локализация как продукт** - Flipkart (хинди, голос - claim 15), Rakuten (японский 解説), Trendyol (турецкие сторонние ассистенты). Платформенный ассистент не переносим между рынками, что оставляет нишу кросс-платформенным решениям.

## Лиды для следующего раунда

- **Противоречие (приоритет):** дата запуска агентного Amazon Seller Assistant - 09.2025 (пресс-цитаты) vs 12.2025 (Seller Sprite); primary About Amazon без видимой даты. Проверить через Wayback / Seller Central News («Seller Assistant» announcement) с датой; получить help-страницу GLYJTRGQCYNYAZS9 через залогиненный аккаунт или Wayback.
- **Противоречие/одиночный источник:** tiered permission model «auto-approve vs suggest only» (Zentail/Stormy) - нужен второй издатель (Seller Central forums, r/FulfillmentByAmazon) и подтверждение, что Q2 2026 auto-approve реально выкатился.
- TikTok Shop: страница «How Seller Assistant Works» (knowledge_id=6072511163025195) и June 2026 product update - есть ли proactive alerts, approval-лог, GMV Max guardrails.
- Allegro: прочитать живую https://allegro.pl/moje-allegro/sprzedaz/allegro-analytics/o-narzedziu (timeout) и cennik abonamentu на allegro.pl; отзывы продавцов об asystent AI.
- Nubimetrics: WooSync «Nubimetrics vs Real Trends» и landings.nubimetrics.com - алерты, прогноз, AI; MeLi нативный Asistente - попробовать vendedores.mercadolibre.com.ar через Wayback.
- Flipkart: Business Standard 2026-05-10 через Wayback; уточнить, Ask Setu и «AI-дашборды» - один продукт или два; Seller Lens.
- Rakuten: второй источник для «>50% пробовали / >20% регулярно» (ECのミカタ); RMS-страница R-Karte с описанием алертов.
- 生意参谋: официальная страница 瓴羊 https://www.lydaas.com/product-sycm - AI-модули, 生意管家, 2025-2026 changelog.
- Coupang: искать «쿠팡 윙 AI 상품명 추천» / «쿠팡 AI 고객문의 답변» (в прошлом раунде предложено, не выполнено); CoupangData.
- Не покрыто: Temu Seller Center AI, Shopee/Lazada seller AI tools (не искал в раунде 2), Ozon-аналоги.

## Не нашёл

- Amazon Seller Central help-страница Seller Assistant - без логина отдаёт только навигацию; расписание/канал уведомлений не подтверждены primary.
- Allegro Analytics живая страница «o narzędziu» - timeout; pricing только по сторонним гайдам (не свежее 3 мес. по primary).
- Business Standard (Flipkart) и MeLi Centro de Partners (Nubimetrics) - HTTP 403; использованы сниппеты.
- Coupang Wing нативный AI-ассистент и CoupangData - снова ни одного релевантного результата.
- Trendyol «Ortak» - не существует под таким именем; нативный AI в панели не найден.
- 生意管家 и AI-модули 生意参谋 - не подтверждены.
- Flipkart Seller Lens - не всплыл; Ask Setu - только агентский Facebook-пост и YouTube.
- Ни у одного продукта: (A) утренний дайджест с расписанием и каналом; (C) память решений и сравнение expected-vs-actual; (E) guardrails рекламы (OOS-aware пауза, реаллокация бюджета, лимиты); (G) алерты на изменение листинга и сравнение с конкурентами внутри платформенного ассистента.
- Независимые 1-3★ отзывы и форумные треды по любому из продуктов - не читал (бюджет исчерпан на primary/лиды).
