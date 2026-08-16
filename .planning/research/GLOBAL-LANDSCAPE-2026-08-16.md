# Global Landscape Research - AI Daily Manager для маркетплейс-селлеров

*Researched: 2026-08-16. Method: web-search (Tavily) + full-page reads. Markets: US, China, Korea, SEA, LatAm, Turkey, Poland, India, Japan, Russia. ~30 продуктов.*
*Confidence: MEDIUM-HIGH. Цены и фичи - из открытых источников на дату ресёрча; перед использованием в pricing-решениях перепроверить.*

## 1. Карта по рынкам

### US / Amazon

| Продукт | Суть | Цена | Урок для нас |
|---|---|---|---|
| **Seller Assistant (ex-Project Amelia)** | NL-ассистент селлера от самого Amazon: Q&A по своим метрикам (продажи/трафик/CVR/остатки, YTD/MoM/YoY), drill-down по товару/категории; issue resolution - coming soon; learns over time | бесплатно (embed) | Маркетплейс сам строит ассистента - у WB этого нет и в горизонте M2-M3 не будет. Окно возможностей |
| **Helium 10 Alerts** | 24/7 мониторинг карточек: hijackers, подавление листинга, смена тайтла/фото/цены/категории; фильтры по ASIN, история с таймстампами | $39-279/мес | Контент-алерты = SCN-011. На WB карточки тоже падают и меняются - незанятая ниша в РФ |
| **SoStocked (Carbon6)** | 12-мес inventory-прогноз: velocity types, сезонность, lead times, буферы; **combo-forecasting** = ручные date-based override'ы поверх скользящей (напр. «листинг был подвешен - исключить период»); авто-PO; учёт Restock Limits | $474/3 мес | Combo-forecasting - точная механика для W4 (SCN-006): baseline + ручные исключения периодов |
| **Pacvue** | Enterprise retail-media: guardrails + approvals + полная transparency изменений; commerce-aware optimization - биды/бюджеты адаптируются к стоку/цене/спросу; кейс L'Oréal UK: автоотвод бюджета от неконвертирующих (OOS) товаров -> ROAS x1.42, CTR x1.44 | enterprise | Автопауза РК при OOS - индустриально отработанное первое R1-действие. Guardrails+approvals = наша R0-R3 модель подтверждена |
| **Lebesgue** | AI CMO для SMB: **Auditor** - аудит по 50+ industry best practices при подключении; бенчмарки индустрии; прогноз CPC/CPM; «Next Steps» - план действий | от ~$20/мес | Auditor-паттерн: второй режим продукта помимо сигналов. Еженедельный чек-лист кабинета -> питает клиентский PDF |
| **Triple Whale (Moby 2)** | «AI operating system для e-commerce», 60k+ брендов, 2000+ агентств. 4 слоя: Data Platform (60+ интеграций) -> **Trust Layer (Compass - measurement validation)** -> BI -> AI (Moby: бюджетные перераспределения, креативы, audience suggestions; LLM-агностик). 9.2B событий/день. Ключевой месседж: «80% бизнеса не видят эффекта от AI - потому что generic AI не знает ваш бизнес; доверие = полный контекст + валидация измерений» | $100-1000+/мес | Их Trust Layer = наш M1 provenance-тезис, подтверждённый рынком. Agency-кейс: «scale через leverage, не через headcount» - буквально наша экономика. Для V3: язык продаж «measurement validation» |

### Китай

| Продукт | Суть | Урок |
|---|---|---|
| **Taobao 生意管家 + 生意参谋 5.0** | AI-продукт платформы для всех продавцов: Q&A по 1000+ метрикам симальфигурированного 生意参谋, ежедневные отчёты (数据日报), аномалии трафика (流量异常提醒), анализ конкурентов и трендов; 1M+ активных продавцов/нед; 74% сообщают экономию ~1 ставки (дизайнера) | бесплатно (embed) | Daily-отчёт + аномалии - мировая НОРМА на масштабе 1M+. Мы не over-engineerим |
| **蝉妈妈 (Chanmama) / Douyin** | AI-подбор блогеров по многомерным кросс-данным (带货能力, матчинг аудитории, тональность контента) | подписка | За пределами scope, но фиксируем как смежный рынок |

### Корея

| Продукт | Суть | Цена | Урок |
|---|---|---|---|
| **CoupangData** | Аналитика + автобид для Coupang Wing: ROAS-таргет 24/7, ABC-диагностика товаров; **«매일 아침» - ежедневный утренний отчёт о вчерашней рекламе в KakaoTalk** | ₩0-19,000/мес (~0-1.3k ₽) | Прямой аналог формата: утро + мессенджер + реклама. Дешёвый entry-уровень удержания |

### SEA

| Продукт | Суть | Урок |
|---|---|---|
| **Shopdora / 知虾** | Shopee-аналитика по 9+ рынкам, агентские тарифы $40-100+/мес | Рынок инструментально зрелый; Shopee x OpenAI partnership (июнь) - платформы сами катятся в conversational AI |

### LatAm

| Продукт | Суть | Урок |
|---|---|---|
| **Nubimetrics** | Meli-селлерам: подбор товаров, стратегия конкурентов, свои продажи | $20-60/мес | Паттерны те же, рынок реже; Meli сам даёт только базовую аналитику |

### Турция

| Продукт | Суть | Урок |
|---|---|---|
| **Trendyol Seller Center «Ortak»** | Predictive AI recommendations, tailored growth strategies; iF Design Award 2025 | Второй «платформенный» AI-ассистент после Amazon - тренд универсальный |

### Польша

| Продукт | Суть | Урок |
|---|---|---|
| **Allegro Analytics** | Бесплатно в подписке продавца: My Account vs Across Allegro (свои vs вся платформа) | Бенчмарк «я vs платформа» - базовый уровень, не premium. Мы добавляем MPStats-гранулярность |

### Индия

| Продукт | Суть | Урок |
|---|---|---|
| **Flipkart Setu AI + Seller Lens** | NL-ассистент селлера (beta) + AI-инсайты портала | Третий рынок с NL-ассистентом от платформы |

### Япония

| Продукт | Суть | Урок |
|---|---|---|
| **Rakuten RMS AI Assistant** | Тексты, картинки, ответы на вопросы, анализ динамики продаж, AI-чат поддержки | Embed, норма |
| **R-Karte (店舗カルテ)** | Методология: выручка = **U x CVR x AOV**; разбор каждого множителя; сравнение со средним по жанру и с YoY; план-факт от формулы | **Готовая методология декомпозиции для SCN-001/002** - принять в MetricAuthority v1 |

### Россия / WB (прямые конкуренты)

| Продукт | Суть | Цена | Слабость (наш ход) |
|---|---|---|---|
| **MPStats** | Глубокая внешняя аналитика + AI-подбор карточек, предиктивные гипотезы закупок | ~30k ₽/мес | Нет proactive daily, нет диагноза как продукта. Наш источник бенчмарков |
| **Маяк** | Mass-market, ИИ-помощник = навигатор по инструментам, автоответы на отзывы | 3-7k ₽/мес | Точность скрытых остатков страдает (сами признают) - verified-подход бьёт |
| **Sirena AI** | Ближайший аналог «ИИ-офиса»: ежедневные отчёты (в т.ч. в Telegram!), план-факт, ABC, аудит карточек, СПП/цена-мониторинг realtime, OOS-прогноз «<14 дней у 5 позиций»; таргетит в т.ч. менеджеров МП («часы на отчёты по понедельникам»); pricing **по числу SKU, кабинеты без наценки**; отзывы: «сверял с финотчётами WB - сходится до копейки» | **от 490 ₽/мес** | Селлерский self-serve: нет agency-контекста, Client Passport, Decision Memory (expected vs actual), нет verification-петли. Их «сходится до копейки» = наш provenance, но у них нет доказательств per-fact |
| **JVO (Дживио)** | «100+ показателей daily -> готовые приоритизированные задания вместо графиков»; ML учится на 1M+ карточек крупных брендов; JVO Agent - NL-агент («запусти РК с бюджетом 50к»); планирование поставки на несколько складов | **22.9k-54k ₽/мес** | «Задания вместо графиков» = наш Decision Inbox - подтверждение формата. Нет verification исходов, нет agency-слоя. Дорогой |

## 2. Десять паттернов -> решения PROXIMA

| # | Паттерн (источник) | Решение |
|---|---|---|
| 1 | Утро + мессенджер (CoupangData, Sirena, Taobao) | Telegram = critical-алерты и инциденты; web = рабочее место AM |
| 2 | Задания вместо дашбордов (JVO, Sidekick Pulse) | Decision Inbox - центр UI; не строим BI |
| 3 | Декомпозиция U x CVR x AOV (Rakuten R-Karte) | Каркас SCN-001/002 в MetricAuthority v1 |
| 4 | Бенчмарк «я vs категория» (R-Karte, Lebesgue, Allegro) | MPStats-коннектор; в каждом сигнале SCN-001 линия «категория X% vs ты Y%» - отсекает «весь рынок упал» |
| 5 | Сезонные нормы + группировка + ₽ (Anodot) | Baseline с сезонностью (день недели на 90-дневном бэкфилле), один grouped-инцидент, «стоимость молчания ₽/день» на каждом сигнале |
| 6 | Trust Layer перед AI (Triple Whale Compass) | M1 provenance = Trust Layer. Язык V3: «measurement validation» |
| 7 | Auditor по best practices (Lebesgue) | Еженедельный аудит кабинета по чек-листу -> клиентский PDF |
| 8 | Автопауза рекламы при OOS (Pacvue/L'Oréal) | Первое R1 после V2 |
| 9 | Контент-алерты (Helium 10) | SCN-011 в W3 |
| 10 | Pricing по SKU/кабинетам (Sirena) | M3: тариф = кабинет + полоса SKU; наценка за verified-слой и AM-обёртку |

## 3. Ценовая лестница РФ (для V3)

```
Sirena 490₽ ── Маяк 3-7k ── [МЫ: 10-20k + agency] ── JVO 23-54k ── MPStats ~30k
  self-serve     mass          verified + AM            задания + ML     внешняя аналитика
```

Ниша 10-20k ₽/кабинет свободна: между mass-market и JVO, с verified-данными + Decision Memory + живым AM.

## 4. Конкурентный мониторинг (триггеры пересмотра)

- Sirena добавляет agency-режим / multi-кабинетные отчёты для менеджеров -> пересмотреть позиционирование V3
- JVO развивает verification исходов -> усилить акцент на provenance-доказательства
- WB выпускает собственный AI-ассистент -> смещение ценности в agency-контекст и мультиплатформенность (Ozon)

## Sources

- triplewhale.com (full read 2026-08-16), anodot.com/blog/ecommerce-real-time-anomaly-detection (full read)
- gobrandwoven.com, amalytix.com, aboutamazon.com (Amelia/Seller Assistant)
- shopify.com/enterprise/blog (Sidekick Pulse), getmesa.com, byradiant.com
- pacvue.com/platform (real-time optimization, L'Oréal case), lebesgue.io, skywork.ai (Lebesgue switch review)
- help.sostocked.com, carbon6.io/sostocked, spscommerce.com
- helium10.com/tools, myamazonguy.com (Alerts)
- aliyun.com/startup (生意管家), sycm.taobao.com, ai.chanmama.com, eshutong.com (九数云BI)
- coupangdata.co.kr, cloudecommerce.com, blog.shopdora.com, growthhq.io, finance.yahoo.com (Sea x OpenAI)
- nubimetrics.com, emarketer.com (Meli), quartr.com
- help.allegro.com (Analytics), ifdesign.com (Trendyol Ortak), sellenvo.com
- linkedin.com (Flipkart Setu AI), hiredigital.com
- corp.rakuten.co.jp (RMS AI Assistant), rakuten.co.jp (R-Karte), nint.jp, sobani.co.jp
- a2is.ru, sirena-ai.ru, youtube.com (Sirena обзор), stats-mp.ru, jvo.ru/faq, uniseller.io (JVO Agent), crmindex.ru
- uniseller.io, mpagency.ru, gb.ru (Маяк тарифы), moysklad.ru (24 сервиса)
