---
cluster: C3 «Отзывы и вопросы покупателей»
sources: .orca/drops/функции новые/skills/{wb-reviews, wb-feedbacks, wb-questions-autoresponder}
extracted: 2026-09-02
mode: read-only extract; ни одно значение токена не выводится (grep по паттернам секретов - пусто во всех трёх скиллах)
---

# Extract C3 - отзывы и вопросы покупателей

Сокращения: `D` = `.orca/drops/функции новые/skills`; `spec` = `D/wb-reviews/references/api-spec.yaml` (OpenAPI 3.0.1 «Общение с покупателями», `spec:1-4`, 4016 строк). Статус READ/WRITE у эндпоинтов взят из поля `x-readonly-method` самой спеки, категория токена - из `x-category: questionsandfeedback` (`spec:35` и далее). Даты версий - из `.orca/drops/функции новые/MANIFEST.md:5-22` (копия собрана 30.08.2026, файлы в репо датированы 02.09.2026 04:46; в git не отслеживаются - `.orca/.gitignore:1`).

Контекст проекта, который ограничивает перенос: реестр AD-4 (statistics `supplier/orders`, `supplier/sales`, analytics `v3/sales-funnel/products/history`, `v2/nm-report/downloads`) не содержит ни одного эндпоинта feedbacks-api/content-api; allowlist `tools/verify_business_signal.py:19-29` - тоже; в `docs/state/API-FACTS.md` (таблица `:21-32`) строк по feedbacks-api нет. Единственное свидетельство работоспособности - личный кабинет Mike до 29.08.2026 (`event-diagnosis/EXTRACTED.md:24-28`), не сервер и не токен ИП Амировой (`event-diagnosis/SPEC.md:84`). В репо ни `feedbacks-api`, ни `/api/v1/questions` не упоминаются (grep по `services tools docs contracts db` - пусто).

---

## 1. wb-reviews (версия 28.05.2026)

### 1.1 Capability, пользователь, триггер
- **Одной строкой:** bash-CLI + инструкция агенту для чтения отзывов WB, **публикации и редактирования ответов на отзывы и оформления возврата товара по отзыву** через feedbacks-api.
- **Пользователь:** селлер через чат-агента (OpenClaw; ключ в `/root/.openclaw/api-keys.env` - `SKILL.md:18`, `scripts/wb-reviews.sh:12-15`).
- **Триггер:** фразы «отзывы WB», «есть неотвеченные», «ответить на отзыв», «негативные отзывы», «статистика отзывов» и любое упоминание обратной связи покупателей (`SKILL.md:5-9`).
- **Дата версии:** 28.05.2026 (`MANIFEST.md:14`); есть бандл `bundles/wb-reviews.skill` из `~/Downloads` (`MANIFEST.md:33`).

### 1.2 Входы
Base URL `https://feedbacks-api.wildberries.ru` (`SKILL.md:16`, `wb-reviews.sh:9`). Токен: единая переменная `WB_API_KEY`, категория «Вопросы и отзывы» (`spec:35`), заголовок `Authorization: <key>` (`wb-reviews.sh:29`).

| Команда | Метод + путь | Код | Спека | Статус |
|---|---|---|---|---|
| feedbacks-count-unanswered | GET `/api/v1/feedbacks/count-unanswered` | `wb-reviews.sh:93-95` | `spec:803-807` readonly=true | READ |
| feedbacks-count | GET `/api/v1/feedbacks/count?dateFrom&dateTo&isAnswered` | `:97-102` | `spec:873-877` | READ |
| feedbacks-list | GET `/api/v1/feedbacks?isAnswered&take&skip&order&dateFrom&dateTo&nmId` | `:104-109` | `spec:971-975`; take ≤5000, skip ≤199990 (`spec:1016,1023`) | READ |
| feedback-by-id | GET `/api/v1/feedback?id=` | `:111-114` | `spec:1362-1366` | READ |
| archive-list | GET `/api/v1/feedbacks/archive` | `:131-136` | `spec:1667-1671` | READ |
| new-check | GET `/api/v1/new-feedbacks-questions` | `:138-140` | `spec:30-34` | READ |
| **feedback-answer** | **POST `/api/v1/feedbacks/answer`** `{id,text}` | `:116-119` | `spec:1157-1161` readonly=**false**; text 2..5000, ID не валидируется (`spec:1172-1174`) | **WRITE** |
| **feedback-answer-edit** | **PATCH `/api/v1/feedbacks/answer`** | `:121-124` | `spec:1224-1225`; 1 раз за 60 дней | **WRITE** |
| **feedback-return** | **POST `/api/v1/feedbacks/order/return`** `{feedbackId}` | `:126-129` | `spec:1275-1279`; только при `isAbleReturnProductOrders=true` | **WRITE (финансовое действие)** |

Внешних сервисов нет (только curl + jq). Ручных входов нет: текст ответа приходит через stdin из LLM (`SKILL.md:53-58`, пример `SKILL.md:122-125`).
Лимиты: 3 req/s, интервал 333 мс, burst 6, `sleep 0.35` (`SKILL.md:65-74`; совпадает со спекой `spec:44-49`).

### 1.3 Расчёт / логика
- **Код не считает ничего.** Скрипт - обёртка над curl: `do_get/do_post/do_patch` (`wb-reviews.sh:32-42`), `parse_response` печатает `HTTP <code>` в stderr и JSON через jq в stdout (`:44-58`), `build_query` склеивает параметры (`:79-89`). Счётчики необработанных (`countUnanswered`, `countUnansweredToday`) - готовые поля ответа WB (`spec:833-840`), не вычисляются.
- **Рейтинг:** только поле `productValuation` 1-5 (`SKILL.md:155`, `spec:1426`). Средний рейтинг карточки нигде не считается.
- **Детекция негатива - в прозе для LLM, не в коде:** позитив 4-5★ (`SKILL.md:84-89`), негатив 1-3★ (`:91-97`), нейтральный «3★ без текста» (`:99-101`); пересечение 3★ в двух ветках не разрешено.
- **Tone-of-voice для LLM:** обращаться по `userName`, упоминать конкретику из отзыва, без шаблонов, «живым языком» (`SKILL.md:78-82`); запреты: не копировать ответ, не спорить, «не обещать того, что не можешь выполнить», не редактировать без причины (`:103-108`). Одновременно инструкция велит «предложи конкретное решение - замена, возврат, связь с поддержкой» (`:94`) и в примере обещает «мы передадим информацию в отдел качества» (`:97`) - то есть обещания от имени селлера генерирует LLM без проверки.
- **Кто что считает:** код - 0; LLM - классификация тона по звёздам, текст ответа, решение о возврате.

### 1.4 Выход
JSON WB как есть в stdout (`parse_response`), HTTP-код в stderr; потребитель - агент, который сразу шлёт ответ в WB. **Шага одобрения человеком в скилле нет** - пример `echo '{"id":…,"text":…}' | bash wb-reviews.sh feedback-answer` (`SKILL.md:122-125`).

### 1.5 Переформулировка на лестнице PROXIMA
См. §4 кластера. От этого скилла в продукт переносится только справочник полей (`spec`) и список READ-эндпоинтов; три WRITE-команды - вне продукта.

### 1.6 Код к переиспользованию
- `scripts/wb-reviews.sh` - bash, 165 строк, curl+jq, тестов нет; ценность низкая (тонкая обёртка без ретраев и лимитера).
- `references/api-spec.yaml` - **основная ценность**: полная схема Feedbacks/Questions/Pins/Chats/Claims c `x-readonly-method` на каждом методе (`spec:33-2717`), схема объекта отзыва `responseFeedback` (`spec:2916-3107`): `productValuation`, `matchingSize` (` `/`ok`/`smaller`/`bigger`, `spec:3042-3050`), `orderStatus` (`buyout`/`rejected`/`returned`/`notSpecified`, `spec:3033-3041`), `bables` (теги покупателя, `spec:1123`), `isAbleReturnProductOrders`, `parentFeedbackId/childFeedbackId`. Пригодна как источник для `contracts/*.schema.json` и фикстур.
- Секреты: значений нет; путь `/root/.openclaw/api-keys.env` и `source` файла с ключом - `wb-reviews.sh:5,12-14`.

### 1.7 Красные флаги
1. **WRITE ×3** - публикация/редактирование ответа и **оформление возврата** (`wb-reviews.sh:116-129`). Запрещено политикой WB READ-only; возврат - ещё и денежное действие по ID, который WB не валидирует (`spec:1172-1174`).
2. **LLM → WB без человека** (`SKILL.md:122-125`); нет ни dry-run, ни лога отправок.
3. **ПДн покупателей:** `userName`, `photoLinks`, `video`, `lastOrderShkId` в каждом ответе (`spec:1489-1559`); инструкция требует обращаться по имени (`SKILL.md:79`).
4. **Выдуманные факты/обещания:** примеры ответов содержат обещания и обязательства (`SKILL.md:94,97`) при отсутствии проверки текста.
5. Токен подгружается через `source` произвольного файла (`wb-reviews.sh:13`) - выполнение кода из env-файла.

---

## 2. wb-feedbacks (версия 28.05.2026)

### 2.1 Capability, пользователь, триггер
- **Одной строкой:** read-only bash-CLI на четыре GET-команды feedbacks-api: есть ли новое, сколько необработанных, сколько за период, список с пагинацией.
- **Пользователь:** тот же агент/селлер; «Скилл только для чтения (read-only). Ответы на отзывы не поддерживаются» (`SKILL.md:10`).
- **Триггер:** «проверить отзывы», «что пишут покупатели», «жалобы на товар», «счётчики непросмотренных» (`SKILL.md:4-9`).
- **Дата версии:** 28.05.2026 (`MANIFEST.md:12`).

### 2.2 Входы
Base URL `feedbacks-api.wildberries.ru` (`scripts/wb-feedbacks.sh:8`), тот же `WB_API_KEY` из `/root/.openclaw/api-keys.env` или `--key=` (`:9-30`), категория «Вопросы и отзывы».

| Команда | Метод + путь | Код | Статус |
|---|---|---|---|
| check-new | GET `/api/v1/new-feedbacks-questions` → `hasNewQuestions`, `hasNewFeedbacks` | `wb-feedbacks.sh:58-61` | READ |
| feedbacks-unanswered | GET `/api/v1/feedbacks/count-unanswered` → `countUnanswered`, `countUnansweredToday` | `:63-66` | READ |
| feedbacks-count | GET `/api/v1/feedbacks/count?dateFrom&dateTo&isAnswered` | `:68-82` | READ |
| feedbacks-list | GET `/api/v1/feedbacks?isAnswered&take&skip&nmId&order&dateFrom&dateTo` | `:84-103` | READ |

WRITE-команд нет. Внешних сервисов и ручных входов нет.

### 2.3 Расчёт / логика
- Код не считает: `do_get` + `parse_response` (`:37-54`; при не-2xx тело уходит в stderr и exit 1).
- Единственная «логика» - порядок вызовов в прозе: сначала дешёвый `check-new`, потом `feedbacks-list` (`SKILL.md:36-38`); пагинация `--skip` при >5000 (`SKILL.md:40-42`).
- Документированная структура отзыва (`SKILL.md:93-121`) даёт поля для будущих сигналов: `productValuation`, `matchingSize`, `bables`, `subjectId/subjectName`, `answer.state`, `wasViewed`.
- Кто считает: код - 0; LLM - интерпретация JSON в чате.

### 2.4 Выход
JSON в stdout (jq). Потребитель - агент. Одобрения нет, т.к. нет записи.

### 2.5 Переформулировка
Это де-факто прототип READ-адаптера для `snapshot_feedback` (см. §4). Семантику `isAnswered` (обязательный параметр, `spec:997-1004`) надо учитывать: за день нужно два вызова (`true` и `false`), либо ходить по `dateFrom/dateTo` дважды.

### 2.6 Код к переиспользованию
`scripts/wb-feedbacks.sh` - bash, 142 строки, curl+jq, тестов нет. Переиспользовать как спецификацию параметров; в проекте адаптер должен быть в TS-клиенте с реестром (AD-4), а не bash. Секреты: значений нет; `source /root/.openclaw/api-keys.env` - `wb-feedbacks.sh:12-14`.

### 2.7 Красные флаги
- WRITE - нет.
- ПДн: `userName`, `photoLinks`, `video` возвращаются и оседают в контексте LLM (`SKILL.md:103-113`).
- `source` env-файла (`:13`), общий read-write токен вместо split-токена.

---

## 3. wb-questions-autoresponder «Скилл №18» (версия 19.08.2026)

### 3.1 Capability, пользователь, триггер
- **Одной строкой:** двухфазный автоответчик на **вопросы** покупателей: онбординг (карточки + история Q&A + канонический FAQ + tone-of-voice + политика селлера) → рабочий режим: выгрузка необработанных вопросов, детерминированная классификация, черновики «строго по карточке» (FAQ-ответ / цитата характеристики / LLM-черновик), Excel с колонкой «✓ Одобрить», затем **`send_approved.py` публикует одобренные через PATCH**.
- **Пользователь:** селлер-новичок в Cowork/Claude без понимания API (`SKILL.md:76`); онбординг ведётся блоками `WELCOME.md` с подтверждением каждого шага (`SKILL.md:78-112`).
- **Триггер:** «что в вопросах», «подготовь ответы», «есть ли неотвеченные вопросы», «автоответ покупателям» (`SKILL.md:11-13, 29-33`); опционально расписание cron `0 9 * * *` через `mcp__scheduled-tasks__create_scheduled_task` (`SKILL.md:233-239`).
- **Дата версии:** 19.08.2026, «без DEBTS.md/data» (`MANIFEST.md:19`); упомянутые `DEBTS.md`, `ТЗ.md`, `описание.md`, пример xlsx (`README.md:99-102`) в дропе отсутствуют.

### 3.2 Входы
**Токен.** Один `WB_API_KEY` с категориями «Контент», «Вопросы и отзывы», «Аналитика»; инструкция прямо запрещает ставить «Только для чтения» - «иначе я не смогу отправлять ответы» (`SKILL.md:142-151`, `WELCOME.md:98`). Токен просят **прислать в чат** (`SKILL.md:148-149`) и пишут `echo "WB_API_KEY=<токен>" >> ~/.openclaw/api-keys.env` (`SKILL.md:155-159`).

| Назначение | Метод + путь | Код | Спека | Статус |
|---|---|---|---|---|
| проверка токена / новое | GET `feedbacks-api…/api/v1/new-feedbacks-questions` | `scripts/wb-questions.sh:114-117` | `spec:30-34` | READ |
| счётчик | GET `/api/v1/questions/count-unanswered` → `countUnanswered`, `countUnansweredToday` | `:119-122`; `fetch_questions.py:70-78` | `spec:105-109` | READ |
| счётчик за период | GET `/api/v1/questions/count?dateFrom&dateTo&isAnswered` | `:124-129` | `spec:174-178` | READ |
| список вопросов | GET `/api/v1/questions?isAnswered&take&skip&order&dateFrom&dateTo&nmId` | `:131-136`; история `--isAnswered=true --take=500` (`SKILL.md:184-186`); рабочий режим `--isAnswered=false --take=20` (`fetch_questions.py:89-93`) | `spec:272-276`; ≤10 000, `take+skip` ≤10 000 (`spec:288,319-331`) | READ |
| вопрос по id | GET `/api/v1/question?id=` | `:138-141` | `spec:641-645` | READ |
| **ответ / отклонение / «просмотрено»** | **PATCH `/api/v1/questions`** тело `{"id","answer":{"text"},"state":"wbRu"}`; `state:"none"` = отклонить; `{"id","wasViewed":true}` = просмотрено | `wb-questions.sh:145-156`; `send_approved.py:50-70` | `spec:490-580`, readonly=**false** (`spec:494`), примеры `spec:563-575` | **WRITE** |
| карточки | POST `content-api.wildberries.ru/content/v2/get/cards/list` курсор `limit/updatedAt/nmID` | `scripts/wb-content.sh:8,95-104`; пагинация `onboarding.py:317-367` (≤50×100) | нет в spec | READ по семантике (POST-запрос списка), токен «Контент» |
| активные SKU | GET `statistics-api.wildberries.ru/api/v1/supplier/sales?dateFrom=<now-30d>` → уникальные `nmId` | `scripts/fetch_active_skus.py:34,59-60,134-141` | в реестре AD-4, API-FACTS `:24` | READ |

Расхождение в документации: `SKILL.md:145` и `fetch_active_skus.py:92` называют это «Аналитика», но эндпоинт - категория statistics; `SKILL.md:259` говорит «берёт из `wb-analytics`», хотя код ходит в statistics напрямую.

**Внешние сервисы:** `mcp__scheduled-tasks` (`SKILL.md:239`); LLM-генерация «в артефакте через `window.cowork.askClaude`» (`generate_drafts.py:316,326`) либо самим Claude в сессии (`SKILL.md:286-304`); `openpyxl` (`build_excel.py:36-40`, `send_approved.py:30-31`). Стандартная библиотека Python для остального.

**Ручные входы:** 6 вопросов политики → `data/config.json`: `safe_categories`, `manual_categories`, `suggestion_policy` (ignore/mark_feedback/polite_reply), `wrong_card_policy` (skip/ask/manual), `stop_words` (дефолт «гарантируем», «100%», «лучший», «обещаем»), `signature`, плюс `style_override`, `faq_match_threshold`, `use_llm` (`SKILL.md:216-231`; `classify.py:153-165`; `generate_drafts.py:40,428,497`). Excel: колонка A «✓ Одобрить» со списком TRUE/FALSE/- (`build_excel.py:230-233`), правка текста прямо в колонке G (`SKILL.md:326`).

### 3.3 Расчёт / логика (что считает код)
Порядок в `generate_for_question` (`generate_drafts.py:397-608`):
1. `too_long` (>1000 симв., `fetch_questions.py:133-147`) → `requires_review` (`:404-417`).
2. **Классификация** `classify.py:153-246`: `normalize()` → счёт совпадений regex-ключей по 16 категориям (`KEYWORDS :32-97`), argmax; `detect_emotion` (`:127-150`): ≥2 «!», >40 % слов КАПСОМ при ≥3 словах, маркеры «ужас/кошмар/бред/что за». Решение: эмоция → `manual_only`; `complaint` → `manual_only`; `suggestion`/`wrong_card` → по политике; `price/delivery/warranty/return/availability` (`DEFAULT_MANUAL :109-112`) → `manual_only`; `effect/recommendation` (`CONSULTATIVE :107`) → `requires_review`; `size/material/color/dimensions/complectation/care/compatibility/shelf_life` (`DEFAULT_SAFE :101-104`) → `safe`; иначе `other` → `requires_review`.
3. **FAQ-матч (primary):** `match_global_faq` (`:273-310`) - Jaccard по shingles ≥ 0.50 (`:40`) с `data/global_faq.json`; при матче сразу `safe_from_faq` с каноническим ответом селлера (`:427-450`). FAQ строится `build_global_faq.py`: стоп-слова (`:44-54`), суффиксный стемминг (`:62-83`), признаки = стемы + биграммы без цифр (`:86-108`), жадная кластеризация с центроидом-объединением (`:141-171`), кластер ≥3 (`:202-203`), порог 0.45 по умолчанию (`:204-205`; `SKILL.md:203` советует 0.30), канонический вопрос - самый короткий не ниже медианы−10 (`:174-181`), канонический ответ - самый частый при ≥30 % повторов, иначе медианный по длине (`:184-197`).
4. Нет карточки локально → `no_data` (`:453-467`); `manual_only` → пустой черновик + `is_emotion` (`:470-484`).
5. **Tone:** локальный `data/faq/<nmId>.json` или `global_tone.json` (`:486-493`). `analyze_tone` (`onboarding.py:195-240`): средняя длина в символах и предложениях, `uses_emoji` (>30 % ответов), `uses_greeting` (>50 %), `uses_name_address` (>30 %), `common_signature` = последняя строка, повторяющаяся >30 % и <80 симв., `sample_answers[:3]`.
6. Консультативная категория + `use_llm` → `llm_pending` с `build_llm_context` (`:495-513`); нет фактов у `compatibility/care/shelf_life/complectation/other` → `llm_pending` (`:520-536`), у остальных → `no_data` (`:537-549`); >2 фактов у `compatibility/care/complectation` → `llm_pending` (`:553-570`).
7. **Факты из карточки** `find_card_facts` (`:61-176`): `field_map` категория → regex по имени характеристики (`:77-89`); `sizes` с фильтром безразмерных `techSize in ("0","","-")` (`:121-141`); `dimensions` length/width/height/weightBrutto (`:143-157`); fallback - первое предложение описания с ключом (`:159-174`).
8. **Сборка** `render_answer` (`:182-270`): шаблоны «Состав: …», «Доступны размеры: …», «Срок годности: …» (`:203-220`) по **первому** найденному полю (`:198`); обращение по имени никогда не срабатывает - у вопросов нет `userName` (`:222-229`, подтверждается схемой `spec:394-447`); «Добрый день! » при `uses_greeting` (`:232-233`); второй факт + мостик при средней длине ≥200 (`:237-246`); подпись из config → tone → regex «С уважением/любовью…» по сэмплам (`:249-258`).
9. **Проверка обещаний** `check_promises.py:24-52`: `delivery_promise` («доставим за N», «в течение N час/дн», «завтра придёт»), `guarantee` («гарантируем», «обещаем», «точно подойдёт»), `superlative` («100%» кроме состава ткани `:38`, «лучший», «идеальн», «превосходн»), `free_promise`, `price_promise` («скидк», «промокод») + `custom_stop_word` из config (`:73-81`). Нарушение → `requires_review` (`generate_drafts.py:575-583`); 2 факта → `requires_review` (`:589-591`); >2 → `requires_review` (`:584-588`); иначе `safe`.
10. Статистика по уровням и сортировка «жалобы наверх» (`:638-665`); алерт о жалобах в stderr для дублирования в чат (`:667-674`).

**Что делает LLM:** для `llm_pending` Claude читает `llm_context.system_prompt` (правила: «Используй ТОЛЬКО факты из карточки», фиксированная фраза при отсутствии ответа, без сроков/скидок/гарантий, без штампов, копировать стиль, без эмодзи - `generate_drafts.py:369-379`) и `user_prompt` (карточка ≤1500 симв. описания + характеристики + 2-3 примера ответов + вопрос, `:328-386`) и пишет `draft_answer` прямо в `drafts.json` (`SKILL.md:286-304`). **LLM-черновики через `check_promises` не проходят** - проверка есть только в kw-ветке (`generate_drafts.py:575-577`), а `SKILL.md:275` декларирует её для всех.

Тесты: `test_corner_cases.py` - 13 функций, 47 assert (совпадает с «47 кейсов» в `SKILL.md:393`): нормализация, все ветки классификатора, ложные срабатывания цвета, размер «0», пустая карточка, обещания, массив/число в `value`, LLM-контекст, длинный/пустой вопрос.

Целевые метрики (без источника): ≥60 % вопросов с уровнем «Безопасно», 20 вопросов за ≤5 мин, ≥90 % согласия модерации на 50 вопросах, 0 выдуманных фактов (`README.md:196-201`).

### 3.4 Выход
- `data/drafts.json` (`stats` + список с `confidence ∈ {safe_from_faq, safe, llm_pending, requires_review, no_data, manual_only}`, `facts`, `reason`, `promise_violations`, `llm_context`).
- `data/answers_review.xlsx` - 4 листа: «Сводка» (`build_excel.py:116-162`), «Все вопросы» 11 колонок A..K (`:167-171`), «⚠ Жалобы» (`:242-278`), «🔒 Только руками» (`:281-315`). **Дефолт колонки A: TRUE для `safe` и `safe_from_faq`** (`:185`), FALSE для `llm_pending/requires_review`, «-» для `manual_only/no_data` (`:211-214`).
- `send_approved.py`: берёт строки с A ∈ {TRUE,1,YES,ДА} и пустым статусом (`:104-108`), шлёт ровно текст ячейки G без повторной проверки (`:112`, `README.md:167`), пауза 335 мс (`:77,163-164`), статус «отправлено HH:MM»/«ошибка» обратно в Excel (`:141-150`), лог `data/send_log.json` (`:169`), есть `--dry-run` (`:124-130`).
- Итоговое саммари в чат: отправлено / отредактировано / пропущено / требуют ручного ответа (`SKILL.md:342-349`).
- **Шаг одобрения:** есть - галочка в Excel + команда «отправь одобренные» (`README.md:133`). Но одобрение по умолчанию уже проставлено для safe/FAQ, и это осознанно: «если ты в спешке нажмёшь "отправить одобренные" - отправятся только те, где я уверен на 90%+» (`WELCOME.md:78`).

### 3.5 Переформулировка на лестнице
См. §4. Из скилла переносится детерминированный слой (классификатор жалоб/категорий, счётчики, возраст неотвеченных); генерация черновиков - только как вложение к карточке решения для человека; PATCH - нет.

### 3.6 Код к переиспользованию
| Файл | Язык / зависимости | Тесты | Оценка |
|---|---|---|---|
| `scripts/classify.py`, `normalize.py`, `check_promises.py` | Python, stdlib | покрыты `test_corner_cases.py` | **высокая** - чистые функции, переносимы в control-plane как правила детекции жалоб/категорий и фильтр обещаний |
| `scripts/build_global_faq.py` (стемминг, shingles, Jaccard, кластеризация) | Python, stdlib | косвенно | средняя - работает, но не учитывает nmId (см. флаги) |
| `scripts/onboarding.py` (`analyze_tone`, нормализация карточек, курсорная пагинация Content API) | Python, stdlib; вызывает bash | нет | средняя; дублирует классификатор упрощённым словарём (`:167-180`) |
| `scripts/generate_drafts.py` (`find_card_facts`, `render_answer`, `build_llm_context`) | Python, stdlib | частично | средняя - как эталон «черновик только из фактов карточки» с SourceRef-подобным полем `facts[].source` |
| `scripts/fetch_questions.py`, `fetch_active_skus.py`, `wb-questions.sh`, `wb-content.sh` | Python/bash, curl | нет | низкая - заменить TS-клиентом с реестром; ретраи 429/5xx с backoff 2/4/8 с (`wb-questions.sh:61-108`) - как требование |
| `scripts/build_excel.py`, `send_approved.py`, `demo_run.py` | Python, openpyxl | нет | не переносить (Excel-цикл и WRITE) |

Секреты: значений нет ни в одном файле (grep по JWT/`WB_API_KEY=<значение>`/`Authorization:` - пусто). Факты обращения с секретом: `~/.openclaw/api-keys.env` через `source` (`wb-questions.sh:12-14`, `wb-content.sh:11-14`), чтение файла в `fetch_active_skus.py:42-51`; токен проходит через чат и контекст LLM (`SKILL.md:148-149,157`).

### 3.7 Красные флаги
1. **WRITE:** PATCH `/api/v1/questions` публикует ответ, а тот же CLI-вход принимает произвольное тело - можно **отклонить вопрос** (`state:"none"`, `spec:568-573`) или отметить просмотренным (`wb-questions.sh:145-156`). Запрещено как продуктовое действие.
2. **Токен с правом записи, переданный в чат** и сохранённый скриптом (`SKILL.md:146-159`); прямой конфликт с политикой split-токенов read-only.
3. **Одобрение по умолчанию** для `safe`/`safe_from_faq` (`build_excel.py:185`, `WELCOME.md:78`) - human-in-the-loop формально есть, фактически «opt-out».
4. **Кросс-SKU перенос ответа:** FAQ-матч идёт по тексту вопроса до загрузки карточки и без учёта `nmId` (`generate_drafts.py:427-450`; кластеры собираются по всем карточкам, `build_global_faq.py:240`), результат помечается `safe_from_faq` и получает TRUE по умолчанию → канонический ответ про товар A может уйти на вопрос про товар B. Это главный канал «выдуманного факта» при декларации «0 кейсов» (`README.md:201`).
5. **LLM-черновики и правки в ячейке G не проходят `check_promises`** (`generate_drafts.py:495-513`, `send_approved.py:112`).
6. **Первое совпавшее поле = «самое релевантное»** (`generate_drafts.py:198`) и предложение описания по ключевому слову (`:159-174`) - цитата может быть не о том.
7. **ПДн:** история Q&A с `userName` кладётся в `data/history/<nmId>/<qId>.json` (`onboarding.py:141-147`); текст вопросов - в Excel и чат.
8. Утверждения без источника: «если не ответить за несколько часов - покупатель уходит к конкуренту» (`WELCOME.md:13`); «уверен на 90%+» (`WELCOME.md:78`).
9. Несогласованность глубины истории: 50 (`README.md:28`, `onboarding.py:383`) vs 500 (`SKILL.md:179-186`, `onboarding.py:406-407`).

---

## 4. Переформулировка кластера как per-tenant capability на данных лестницы

**Куда это ложится.** Дроп `event-diagnosis` уже закладывает `snapshot_feedback (feedback_id, rating, created_at_wb)` из `GET feedbacks-api…/api/v1/feedbacks` и класс события `fresh_negative` (отзыв ≤3★ за последние 2 дня → объясняет `addToCartConversion`) (`event-diagnosis/ARCHITECTURE.md:53,76`; CAP-A `SPEC.md:29-31`). Кластер C3 расширяет этот снапшот вопросами и даёт ещё несколько детерминированных сигналов - все как события для CAP-D (диагноз) и как строки утренней сводки CAP-5/CAP-7.

**Ежедневные сигналы (детерминированный код, per tenant × nmId × calendar_day, ключ с `run_id`/`attempt_id`):**

| Сигнал | Формула | Данные | Порог |
|---|---|---|---|
| `feedback_new_negative` | число отзывов с `productValuation ≤ 3` и `createdDate ∈ D` по nmId; отдельно с `photoLinks`/`video` | GET `/api/v1/feedbacks` за окно `dateFrom/dateTo`, оба значения обязательного `isAnswered` | «≤3★» из скилла (`SKILL.md wb-reviews:91`), калибровать |
| `rating_drop` | средний `productValuation` за скользящие 14/30 дней против нормы по образцу CAP-4 (медиана предыдущих окон) | тот же снапшот | порог - решение Mike, как в SPEC OQ (`SPEC.md:93`); публичный рейтинг карточки в этом API **отсутствует** → UNKNOWN, не смешивать |
| `feedback_unanswered_age` | count и max(now − createdDate) для `isAnswered=false`; сверка с `countUnanswered/countUnansweredToday` | `/api/v1/feedbacks?isAnswered=false`, `/count-unanswered` | N часов - конфиг tenant'а |
| `question_unanswered_age` | то же для вопросов; `isWarned=true` (подозрительный) - отдельный флаг (`spec:430`) | `/api/v1/questions?isAnswered=false`, `/questions/count-unanswered` | N часов; заявленный эффект «уход за несколько часов» не подтверждён |
| `question_complaint` | вопросы, классифицированные `complaint`/эмоция правилами `classify.py:127-150,194-201` | список вопросов | правила скилла; только событие «нужен ручной ответ», без генерации |
| `size_mismatch_share` | доля отзывов с `matchingSize ∈ {smaller, bigger}` за окно; связь с `orderStatus ∈ {returned, rejected}` | поля `spec:3033-3050` | порог по данным |
| `feedback_tags` | частоты `bables` (тегов покупателя, `spec:1123`) по nmId и их сдвиг к прошлой неделе | снапшот | детерминированный счёт тегов WB |

**Что нужно.** (1) Новые READ-эндпоинты feedbacks-api (`/api/v1/feedbacks`, `/feedbacks/count-unanswered`, `/api/v1/questions`, `/questions/count-unanswered`, `/new-feedbacks-questions`) - **вне реестра AD-4**: добавить в allowlist `tools/verify_business_signal.py:19-29` и реестр клиента с фактическими лимит-заголовками и глубиной в API-FACTS по ADR-0007 (`docs/adr/0007-wb-read-endpoints-and-limits.md:34`); лимит категории 3 req/s, burst 6 (`spec:44-49`). (2) Отдельный split-токен «Вопросы и отзывы» с битом read-only на VPS в `/etc/proxima-ai/secrets/`; проверка с сервера на токене ИП Амировой - не проводилась. (3) Хранение: `snapshot_feedback` + `snapshot_question` с минимизацией ПДн - `feedback_id/question_id, nm_id, rating, created_at_wb, answered, matchingSize, orderStatus, bables`; текст - только если нужен для ML и с явным решением; `userName`, `photoLinks`, `video` не хранить. (4) Для `question_complaint` - Content API не нужен; для черновиков ответов (если когда-либо) - карточки из Content API, тоже вне реестра. (5) Черновики ответов допустимы только как текст для человека внутри карточки решения (`Decision Inbox`, PRD §4.1-4.2) с обязательным `check_promises` и без кнопки «отправить»; отзывы уже стоят в Non-Goals W1 как SCN-009 (`prd.md:350`; `docs/state/BACKLOG-REVIEW.md:149` - преемника в PMM нет).

**ML-потенциал (0-3) с обоснованием:**
- Тональность/темы отзывов и вопросов - **2.** Тональность почти полностью дана звёздами (`productValuation`) и тегами `bables`, поэтому классификатор нужен не для «негатив/позитив», а для темы негатива (брак, размер, запах, доставка, несоответствие фото). Детерминированный baseline - словари `classify.py`; ML оправдан, когда накопится ≥ несколько сотен размеченных отзывов на tenant; текст в LLM - только для объяснения, цифры - код.
- Связь отзывов с просадкой продаж - **2.** Прямой путь - событие `fresh_negative` в окне D..D-1 (уже в CAP-D); оценка величины эффекта (доля негатива → `cartToOrderConversion`/`addToCartConversion` из CAP-6) требует ≥8 недель дневной воронки (CAP-6 к 27.10.2026) и нескольких tenant'ов - на одном кабинете статистическая мощность низкая, ML не раньше M-05+.
- Кластеризация вопросов в FAQ - **1.** Jaccard по стемам (`build_global_faq.py`) достаточен; эмбеддинги дадут прирост, но capability «ответы на вопросы» сама вне продукта.
- Генерация ответов - **1** (это LLM, не ML; только черновик для человека).

---

## 5. Сводка кластера

| Скилл | Capability | Статус источника | WRITE? | Расчётность 0-3 | ML 0-3 | Переиспользуемость 0-3 |
|---|---|---|---|---|---|---|
| wb-reviews (28.05.2026) | чтение отзывов + публикация/правка ответа + возврат по отзыву | feedbacks-api: жив на кабинете Mike до 29.08 (по `event-diagnosis/EXTRACTED.md:24-28`), с сервера/токеном ИП не проверен, вне AD-4 и allowlist, нет в API-FACTS | **да** ×3 (POST/PATCH answer, POST order/return) | 0 (curl-обёртка, всё в прозе для LLM) | 1 | 1 (только `api-spec.yaml` как справочник) |
| wb-feedbacks (28.05.2026) | read-only счётчики и список отзывов | тот же API, тот же статус | нет | 0 | 1 | 2 (спецификация READ-адаптера; переписать в TS-клиент) |
| wb-questions-autoresponder (19.08.2026) | черновики ответов на вопросы из карточки/FAQ/LLM, Excel-одобрение, PATCH-отправка | feedbacks-api questions + content-api (оба вне AD-4, не проверены) + statistics `supplier/sales` (в AD-4, проверен 30.08) | **да** (PATCH `/api/v1/questions`: ответ, отклонение, просмотрено) | 2 (детерминированные классификатор, кластеризация, tone, check_promises; но ни одной бизнес-метрики) | 2 | 2 (`classify/normalize/check_promises/build_global_faq` - stdlib, 47 тестов; Excel/send - нет) |

**Выводы.**
1. Все три скилла живут на одном API «Вопросы и отзывы» (feedbacks-api), которого нет ни в реестре AD-4, ни в allowlist, ни в API-FACTS; единственная проверка - личный кабинет Mike; для продукта это «эндпоинт живой, доступ не проверен», нужен probe с сервера на split-токене read-only.
2. Два из трёх скиллов - WRITE: публикация ответов на отзывы и вопросы, отклонение вопросов и даже оформление возврата по отзыву. Как продуктовые действия все они запрещены; переносятся только READ-эндпоинты и детерминированные правила.
3. Вычислительной ценности в wb-reviews/wb-feedbacks нет (0 строк расчёта); ценность - схема полей `api-spec.yaml` (`productValuation`, `matchingSize`, `orderStatus`, `bables`, `isWarned`) как основа контрактов и фикстур.
4. wb-questions-autoresponder - единственный скилл кластера с детерминированным ядром: regex-классификатор категорий и жалоб, эвристика эмоций, суффиксный стемминг + Jaccard-кластеризация FAQ, tone-профиль, фильтр обещаний - всё stdlib и с тестами; это готовый прототип правил для событий `question_complaint` и фильтра «черновик без обещаний».
5. Дизайн «строго по данным карточки» в автоответчике дырявый: FAQ-матч без учёта nmId с одобрением по умолчанию, LLM-черновики и ручные правки без `check_promises`, «первое поле = самое релевантное»; декларация «0 выдуманных фактов» не обеспечена кодом.
6. Продуктовая переформулировка: не «ответчик», а ежедневные события per tenant × nmId - новый негатив (в т.ч. с фото), падение среднего рейтинга к норме, возраст неотвеченных отзывов/вопросов, жалобы в вопросах, доля «маломерит/большемерит», сдвиг тегов - как кандидаты причин в CAP-D и строки сводки CAP-5/CAP-7; это совпадает с уже заложенным `snapshot_feedback`/`fresh_negative` в `event-diagnosis`.
7. Черновики ответов - только как текст для человека в карточке решения с обязательным фильтром обещаний; кнопки отправки в продукте нет.
8. ML-потенциал кластера умеренный (2): темы негатива и оценка влияния отзывов на конверсию имеют смысл только после накопления воронки CAP-6 (≥8 недель) и, желательно, второго кабинета; до этого - правила и пороги, калибруемые решением Mike.
9. Обращение с секретом во всех трёх скиллах (общий read-write токен, `source` env-файла, передача токена в чат) переносить нельзя; в проекте - файл на VPS 0600 и вызовы с сервера.
10. Отзывы уже в Non-Goals W1 (SCN-009, `prd.md:350`) и потеряли преемника в PMM (`BACKLOG-REVIEW.md:149`); если сигналы C3 принимаются - им нужен новый носитель в лестнице (рядом с CAP-6/CAP-A в M-01b, диагноз - M-05), а не реанимация PA-45.
