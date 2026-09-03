# Extract C7 — «Конкуренты и внешний трафик» (кластер `wb-competitor-viral`)

Дата извлечения: 2026-09-02. Источник: `/home/proxima-admin/orca/proxima-ai-sunfish/.orca/drops/функции новые/skills/wb-competitor-viral/` — 8 файлов: `SKILL.md` (200 строк), `references/data_spec.md` (132), `references/onboarding.md` (217), `references/vision_prompt.md` (55), `references/apify_actors.md` и `references/scoring.md` (оба DEPRECATED → `data_spec.md`), `scripts/run_pipeline.py` (249), `scripts/build_excel.py` (413). Бандл `bundles/wb-competitor-viral.skill` — те же файлы (zip, 2026-05-28). Ссылки `file:line` — относительно каталога кластера. Секреты: не найдены (скан пуст; имён токен-переменных в файлах нет — Apify-токен живёт в конфиге MCP вне дропа).

## 1. Скилл `wb-competitor-viral`

- **Capability:** собрать топовые Reels/TikTok по аккаунтам конкурентов и/или хэштегам через Apify, отскорить по «виральности», разобрать обложки vision-моделью и выдать Excel с топ-20, паттернами хуков и 5-7 идеями роликов для карточки WB/внешнего трафика (`SKILL.md:4-7`, `:19`).
- **Пользователь:** селлер/маркетолог в чате агента (MCP-имена Cowork `mcp__cowork__present_files` `:146`; `MANIFEST.md:13` — установлен в `~/.codex/skills`, 28.05.2026).
- **Триггер:** фразы про виральные ролики, «что зашло у конкурентов», хуки, идеи внешнего трафика (`SKILL.md:8-14`).
- **Версия:** номера нет; акторы верифицированы 27.05.2026 (`data_spec.md:3`).

## 2. Входы

| Источник | Вызов | Стоимость | Статус |
|---|---|---|---|
| Apify `clockworks/tiktok-scraper` | `mcp__Apify__call_actor` `{profiles[], resultsPerPage 30, profileSorting "popular"}` (`SKILL.md:64-67`, `data_spec.md:10-23`); `oldestPostDateUnified` — платная фича (`data_spec.md:18`) | free | внешний сервис, скрейпинг TikTok |
| Apify `apify/instagram-reel-scraper` | `{username[], resultsLimit 30, onlyPostsNewerThan "<N> days", skipPinnedPosts}` (`SKILL.md:69-73`, `data_spec.md:25-34`) | ~$0.003/reel | внешний **платный**, скрейпинг Instagram |
| Apify `apify/instagram-hashtag-scraper` | `{hashtags[], resultsType "reels", resultsLimit 50}` (`SKILL.md:75-79`, `data_spec.md:36-44`) | free (1-я страница) | внешний, скрейпинг Instagram |
| Apify `apify/instagram-profile-scraper` (опц.) | подписчики уникальных авторов → `followers_lookup` (`SKILL.md:85-91`); иначе дефолт 10 000 (`:91`) | не указана | внешний, скрейпинг |
| Firecrawl (опц.) | fallback при rate limit (`SKILL.md:179`, `:192`) | не указана | внешний, скрейпинг |
| LLM vision (Claude multimodal) | обложки топ-10 по `cover_url` + контекст поста, ответ строго JSON (`SKILL.md:95-104`, `vision_prompt.md:7-24`) | токены | внешний LLM |
| Ручной ввод | `niche` (обяз.), `accounts`/`hashtags` (одно из), `period_days` 30, `platforms` TikTok+IG, `min_engagement` 500 (`SKILL.md:42-49`); онбординг 6 шагов (`onboarding.md:36-175`), ≤15 аккаунтов (`:88`), ≤10 тегов (`:104`) | — | ручной |
| Прочие MCP | `mcp__cowork__present_files` (`SKILL.md:146`); `mcp__scheduled-tasks__create_scheduled_task` cron `0 9 * * 1` (`:168-169`) | — | платформенные |

WB API: **не используется, 0 эндпоинтов**. Стоимость прогона ~$0.80, еженедельно ~$3.20/мес (`data_spec.md:124-132`); в онбординге $0.50-1.00 (`onboarding.md:168-169`).

## 3. Расчёт — что считает код, что LLM

**Код (`scripts/run_pipeline.py`):**
- Нормализация TikTok `:62-79` (`diggCount→likes`, `commentCount`, `shareCount`, `collectCount→saves`, `playCount→views`, `authorMeta.fans→followers`, `videoMeta.coverUrl/duration`, `createTimeISO`); Instagram `:85-105` (`likesCount`, `commentsCount`; `shares = saves = views = duration = 0` `:98-102`; `followers` из lookup или **`10_000`** `:89`; хэштеги regex `#([\wЀ-ӿ]+)` `:82,104`). Маппинг задокументирован в `data_spec.md:50-64`.
- Скоринг `:120-137`:
  - `er = (likes + 3·comments + 2·shares + 2·saves) / max(followers, 1000)` (`:126-128`)
  - `vf = log10(views + 100)` (`:129`)
  - `recency = 1.5` при возрасте ≤ 7 дн., `1.0` при ≤ 30, иначе `0.7` (`:131-132`)
  - `viral_score = er · vf · recency` (`:134`); `_days_since` при пустой/битой дате возвращает 30 (`:110-117`).
- Фильтр `:142-156`: дубли по `url` (`:147-149`), `likes ≥ min_engagement` (только лайки, `:150`), возраст ≤ `period_days` (`:152`). Скоринг делается до фильтра (`:172-179`).
- Отбор: сортировка по `viral_score` desc, `top20 = filtered[:20]` (`:182-183`); vision подмешивается по `url` (`:186-189`); статистика `avg_likes_top20`, `avg_views_top20`, счётчики по платформам (`:191-207`).
- Excel (`scripts/build_excel.py`): 5 листов — Сводка `:96-174`, Топ-20 `:179-243` (колонки `:179-183`: Подписч., Лайки, Комм., Просм., ER, Score, Длит., Хук, Тема, Эмоция, Текст на обложке, Дата, Ссылка), Паттерны `:248-282`, Идеи `:287-314`, Сырые данные `:319-372`; `fmt_num` `:48-60`, `fmt_pct` `:63-66`.

**LLM (не код):**
- Отбор топ-10 для vision «по простому прокси-скору likes + comments» руками агента (`SKILL.md:99`) — критерий отличается от финального `viral_score`, поэтому у части топ-20 vision пустой («—», `build_excel.py:211-214`).
- Классификация обложки: `hook_type` (11 значений), `theme` (10), `emotion` (8), `in_frame[]`, `text_overlay`, `composition` (`vision_prompt.md:16-23`); при протухшем CDN — по caption с пометкой `source: "by_caption"` (`:26-31`).
- Паттерны: группировка по `(hook_type, theme)`, группа ≥ 3 постов = паттерн; **«средние метрики» и доминирующая эмоция считаются LLM** (`vision_prompt.md:33-39`) и записываются в Excel как числа (`build_excel.py:268-270`: `avg_likes/avg_views/avg_er`).
- Идеи 5-7 под топ-3 паттерна (`concept/hook/development/cta/pattern`, `vision_prompt.md:41-53`), insights, warnings — «заполняешь ты, скрипт их просто прокидывает» (`SKILL.md:140`).

**Дефекты скоринга (факты кода):**
1. Кросс-платформенный пул ранжируется вместе (`run_pipeline.py:170,182`), хотя у Instagram `views = 0` ⇒ `vf ≡ log10(100) = 2`, а у TikTok `vf` до ~7; `data_spec.md:66-69` сам ограничивает сравнимость «внутри платформы».
2. `followers` для Instagram по умолчанию 10 000 (`:89`) → ER произвольный; пол `max(followers, 1000)` (`:126`).
3. Посты без даты получают возраст 30 → проходят 30-дневный фильтр с `recency = 1.0` (`:110-117`).
4. «< 20 постов после фильтра → снизить `min_engagement` и пересобрать» (`SKILL.md:182`) — подгонка порога под размер топа.
5. Ступенчатый recency 1.5/1.0/0.7 и веса 3/2/2 — эвристика без обоснования и без валидации.

## 4. Выход

`viral-report-YYYY-MM-DD.xlsx` (5 листов) + отладочный `<name>.data.json` (`run_pipeline.py:237-239`); сводка в чат 8-12 строк по шаблону (`SKILL.md:149-166`); предложение еженедельного cron (`:168-169`). Потребитель — селлер/контент-менеджер. Пути жёстко Cowork/macOS: `/sessions/.../outputs/config.json`, `/Users/.../viral-report-….xlsx` (`SKILL.md:125-130`).

## 5. Переформулировка как per-tenant capability

**Прямая capability («что виралится у конкурентов») в PROXIMA невычислима без скрейпинга.** Все входы внешние (Apify/Firecrawl = скрейпинг Instagram/TikTok), WB-данных нет. По правилам проекта (WB READ-only; запрет скрейпинга и браузерной автоматизации в runtime — `tools/verify_runtime_boundary.py:13-17`) и принципу K4 из `.memlog.md` («фичи без источника — в Non-Goals») → Non-Goal с указанием причины «источник».

**Что вычислимо без скрейпинга на данных лестницы — «Эффект внешнего трафика на своих карточках»:**
- Данные: `fact_funnel_daily(tenant_id, nm_id, calendar_day, open_card, cart, orders, orders_sum_rub, buyouts, buyouts_sum_rub, …)` (`ARCHITECTURE-SPINE.md:69`; из v3 `sales-funnel/products/history` — в реестре, окно 7 дней, и CSV `nm-report/downloads`) + `norm_daily` (медиана 14 дней, `:87`).
- Детектор (детерминированный): всплеск `open_card` ≥ k × норма при `cart/open_card` ниже нормы = сигнатура внешней волны (блогер/виральное упоминание) в отличие от поиска/рекламы; после подключения WB Advertising API (PRD `prd.md:102` — источник W1, данные копятся; в реестре AD-4 отсутствует, не проверен) рекламные показы вычитаются, остаток — органический внешний трафик.
- Атрибуция по ручному событию (AM/клиент, паттерн products.csv): «размещение у @x, дата, ссылка» → uplift `open_card`/`orders` за 3-7 дней против нормы, ₽-оценка через `forpay_rub` по AD-10 — «сколько принесла интеграция». Это единственная per-tenant capability по теме «внешний трафик», совместимая с правилами; ступень M-04+.
- Формула `viral_score` на WB-данных неприменима (нет likes/views/followers); переиспользуема лишь идея нормировки на аудиторию (аналог — конверсии `addToCartConversion`, уже в v3).

**ML-потенциал:** as-is **1/3** — вся «интеллектуальная» часть (классификация обложек, кластеризация) — LLM, источника данных в PROXIMA нет. Реформулировка **2/3** — changepoint/anomaly на ряде `open_card` по nm_id, разделение рекламного и органического внешнего трафика, оценка uplift с контрольным окном; LLM объясняет причину по цифрам.

## 6. Код к переиспользованию

- `scripts/run_pipeline.py` (Python 3, stdlib; аннотации PEP 604 под `from __future__ import annotations`) — 0-1: скоринг специфичен для соцсетей; годится как образец «config.json → детерминированный расчёт → отчёт».
- `scripts/build_excel.py` (Python, `openpyxl` без пиновки, `:20-27`) — 1: аккуратный шаблон многолистового Excel (стили `:32-43`, гиперссылки, freeze panes, autofilter `:371-372`) для возможных выгрузок AM; выдача PROXIMA — webapp, потребность не подтверждена.
- Тесты: нет. Фикстуры: нет. Зависимости: `mcp__Apify__*` (обязательно), `openpyxl`, Firecrawl (опц.) (`SKILL.md:188-192`); установка `pip install openpyxl --break-system-packages` (`SKILL.md:191`, `build_excel.py:26`).
- Секреты: отсутствуют (факт скана).

## 7. Красные флаги

1. Скрейпинг Instagram/TikTok через Apify и Firecrawl (`SKILL.md:64-79`, `:179`) — внешний скрейпинг, запрещён политикой runtime; гейт `verify_runtime_boundary.py` ловит только playwright/puppeteer/torgstat/browser-session — Apify-клиент пройдёт мимо, нужна явная запись в правила.
2. Платный внешний сервис с рекуррентным cron (`:168-169`) без владельца бюджета; оценка ~$3.20/мес не подтверждена.
3. Правовые риски: сбор данных третьих лиц (ники, подписчики, подписи) в Excel; Instagram в РФ заблокирован, Meta признана экстремистской организацией — фича на парсинге IG для российского продукта требует юридической проверки.
4. Числа от LLM: средние метрики паттернов (`vision_prompt.md:38` → `build_excel.py:268-270`), insights в Сводке (`:150-160`) — нарушение «LLM не считает метрики / каждый факт со SourceRef».
5. Маркетинговые числа без источника: «1 подписчик ~200₽, Reels на 2 000 подписчиков = 400 000₽» (`onboarding.md:20-21`) — нарушает «каждое число с источником и датой».
6. Скоринг некорректен между платформами (§3), при этом топ-20 подаётся как «самые виральные».
7. Vision по `cover_url` с протухающим CDN (`SKILL.md:103`, `vision_prompt.md:28`) и fallback по caption под той же схемой — качество классификации не измеряется.
8. Привязка к Cowork-MCP и путям macOS (`SKILL.md:125-130`, `:146`) — в Codex-установке (`MANIFEST.md:13`) непереносимо.
9. `pip --break-system-packages` (`SKILL.md:191`) — ломает системный Python; в проекте только uv.

## Summary C7

| Скилл | Capability | Статус источника | WRITE? | Расчётность 0-3 | ML 0-3 | Переисп. 0-3 |
|---|---|---|---|---|---|---|
| `wb-competitor-viral` | Топ-20 виральных Reels/TikTok конкурентов, паттерны хуков, идеи роликов для внешнего трафика | внешний сервис Apify (платный, ~$0.80/прогон) + Firecrawl + LLM vision; WB API — 0 эндпоинтов | нет к WB; создаёт cron-задачу и локальные файлы | 2 (нормализация/скоринг/фильтр/топ-20 — код; паттерны и их средние — LLM) | 1 as-is / 2 реформулировка | 1 (`build_excel.py` как шаблон) |

Выводы:
- Кластер целиком построен на внешнем скрейпинге — в PROXIMA невоспроизводим; фиксировать как Non-Goal с причиной «источник», не как «отложено».
- Единственная законная capability по теме — измерение эффекта внешнего трафика на своих карточках (`fact_funnel_daily` + норма + ручное событие размещения); ступень M-04+, очистка от рекламы зависит от Advertising API (вне реестра, не проверен).
- Скоринговая формула переносу не подлежит (некорректна кросс-платформенно, нет данных); для переиспользования — только Excel-шаблон.
- Часть численных выводов скилла производит LLM — при любом заимствовании средние по паттернам переносятся в код.
