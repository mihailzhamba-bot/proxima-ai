# BACKLOG-REVIEW - Jira PA и PMM против лестницы M-00..M-05

**Дата:** 30.08.2026, ~09:50-10:30 МСК, Сессия 1b (окно B, пункт 1.5). **Источники:** Jira `zhamba.atlassian.net` через MCP `jira-atlassian`, только чтение (JQL `project = PA|PMM AND statusCategory != Done` и `= Done`, описания 17 задач точечно); репо `origin/main` = `db56429` (29.08), ветки `git for-each-ref refs/remotes/origin` 30.08; `docs/state/{INVENTORY,WEB-STATE,API-FACTS}.md` 30.08; `docs/agent-system/{HANDOFF,TASKS}.md` (29.08). В Jira ничего не менялось (Ворота 2 не пройдены). Лестница и границы - `DECISIONS.md` D2, D6, D10.

## TL;DR

- Ключ PMM существует: проект `PMM` «Proxima M2-M3» (id 10043, company-managed). Всего задач: PA 55 (39 открытых + 16 Done), PMM 36 (29 открытых + 7 Done). Итого 91, открытых 68.
- Вердикты по 68 открытым: **актуально 28**, **переписать под лестницу 20**, **свернуть 16**, **сделано - закрыть 4** (PA-16, PA-27, PA-49, PMM-5: в коде/доках выполнено, статус Jira отстаёт).
- Done (23): с артефактом в `origin/main` - 15. **Done-без-кода - 7**, из них по замыслу 6 (PA-9 cancelled, PA-43/45/46/47/48 superseded-by-pmm) и **1 красный флаг: PMM-8** (Glossary + KPI-дерево, Готово 27.08, файл `docs/governance/m2-glossary-kpi.md` лежит только в незамерженной ветке бота). Ещё **PA-29** (отказ от harness): Done 15.08, артефакт только в ветке `pa-29-agent-harness`, в main следов нет - второй флаг. PA-33 - частично (таблица toolchain в main есть, таблица зависимостей - только в ветке).
- Код без Done: 8 веток origin с содержательным кодом, не слитым в main (§5): `ai/pa-50` (M-03), `pmm29-contracts` (контракты signal/diagnosis/decision-record), `pmm-20-scn-001…` (детектор падения продаж, 10 файлов + тесты), `PA-03-02-promotion` (атомарная promotion order_count + миграция 010), `PA-56-glitchtip`, `pmm-8-glossary…`, `pa-29…`, `pa-30…`. Это вопрос Ворот 1: мержить, списывать или переносить в единицы лестницы.
- Самое важное для сентября (D6, M-03 к 30.09): PMM-32 (ежедневный цикл сбора - расписания на сервере нет вообще, данные заморожены с 25.08), PA-3/PA-23 (бэкфилл 26 недель Statistics - окно API скользящее, март выпадет в сентябре), PMM-20/PMM-29/PA-50 (норма, контракт сигнала, провайдер данных в `/brief`). Всё это уже частично написано и лежит в ветках.

## 1. Легенда

Ступени (D2): **M-00** разведка API · **M-01** сбор и хранение · **M-02** база нормы · **M-03** отклонения в утренней сводке (граница сентября, D6) · **M-04** аномалии с приоритетом (октябрь) · **M-05** план действий (октябрь) · **вне** - инфра, процесс, discovery, не ступень.

Вердикты: **актуально** - остаётся, привязана к ступени · **переписать** - цель жива, скоуп и формулировку переделать под ступень · **свернуть** - закрыть без преемника (или преемник = одна строка в другой единице) · **сделано - закрыть** - выполнено в коде/доках, Jira отстаёт · **Done-без-кода** - в Jira Готово, в `origin/main` артефакта нет.

Колонка «Факт» - что проверено в репо/на сервере и где (файл, ветка, документ).

## 2. PA - открытые (39)

### 2.1. Эпики фаз M1 и треки

| Ключ | Статус | Суть | Ступень | Вердикт | Факт |
|---|---|---|---|---|---|
| PA-36 | К выполнению | [Трек A] эпик M1 Data Foundation, фазы 2-8 | M-00..M-03 | переписать | D2: роадмап M1 заменён лестницей. Эпик переименовать в эпик лестницы или закрыть и завести новый после Ворот 2 |
| PA-4 | К выполнению | Phase 2 - vertical slice intake → facts → preview | - | свернуть | HANDOFF 25-27.08: Mike выбрал «close with descope», XLSX-план 02-02 отменён; переход в Jira не сделан |
| PA-1 | К выполнению | Phase 3 - PostgreSQL quality, atomic releases | M-01 | переписать | Часть уже в main: миграции 007-009 (ветка `PA-03-01-schema-foundation` merged); promotion order_count - в незамерженной `PA-03-02-promotion` (§5). Остаток = единица M-01 «атомарный релиз дневного ряда» |
| PA-3 | К выполнению | Phase 4 - официальный WB READ + 90-дневный бэкфилл | M-01 | переписать | API-FACTS: ряд `orders`/`sales` 26 недель, окно скользящее, бэкфилл надо запустить в сентябре. Переписать как «бэкфилл 26 недель + ежедневный инкремент» - это ядро M-01 |
| PA-6 | К выполнению | Phase 5 - order_count authority, reconciliation | - | свернуть | Сверка XLSX vs API потеряла смысл после отмены 02-02; источник истины = Statistics `orders`. Одна строка в M-02, не эпик |
| PA-8 | К выполнению | Phase 6 - Data Health UI (FastAPI/Jinja, SSH-only) | - | свернуть | Заменена админкой webapp PA-54 (DEC-006, интервью Mike 25.08); `/admin` со стабами 6 модулей уже в main |
| PA-7 | К выполнению | Phase 7 - VPS operations, backup/restic, restore, incident playbook | M-01 | переписать | INVENTORY §1 №10-12: монитор, ночной бэкап в S3 (`proxima-pg-backup.sh` 29.08), zone-check уже есть. Остаток = расписание сбора (см. PMM-32) + проверка восстановления из бэкапа |
| PA-5 | К выполнению | Phase 8 - evidence gate, Data GO / Live Deploy GO | - | свернуть | Гейты M1 заменены Воротами 1-4 (D2, D9). Шаблонов GO не будет |
| PA-2 | К выполнению | Hygiene & Technical Debt (эпик-контейнер) | вне | актуально | Контейнер для PA-13/15/16/17/25; жив пока живут дети |
| PA-26 | К выполнению | Подготовить Proxima AI к агентной разработке (эпик) | вне | актуально | Дети PA-28..33 Done (с оговорками §4), открыт только PA-27. Закрыть вместе с PA-27 |
| PA-37 | К выполнению | [Трек B] эпик M2 AI Daily Manager | - | свернуть | HANDOFF 17.08: PMM - единственный дом M2/M3, PA-37 «исторический указатель». Детей (PA-38/41/44) перепривязать к ступеням, эпик закрыть |
| PA-35 | К выполнению | [Трек C] Discovery: интервью AM/клиентов, конкуренты, Torgstat | вне | актуально | Дети PA-40, PA-42. Не код; вход для M-04/M-05 и Ворот |
| PA-34 | К выполнению | [Трек D] M3 SaaS 50+ кабинетов, заморожен до V3 | вне | актуально | Заморожен явно; после M-05. Не трогать |

### 2.2. Задачи гигиены и безопасности (PA-2)

| Ключ | Статус | Суть | Ступень | Вердикт | Факт |
|---|---|---|---|---|---|
| PA-13 | В работе | [P1] Analytics RW-токен → READ-only, снять `--allow-analytics-read-write` из 3 мест | M-01 | актуально | D5b/API-FACTS 30.08: на сервере RW-токен, кто-то вне сервера создаёт `detail_history_report` ежедневно ~00:51 UTC через него. Блокер внешний: READ-only токен от владельца кабинета. Статус «В работе» неверен - «ожидает входа» (HANDOFF: rollback оставлен по решению Mike 25.08) |
| PA-15 | На проверке | [P2] нет `wb_prices_token` и `wb_promotion_token` на VPS | вне | переписать | INVENTORY Прил. i: отсутствуют и 30.08. Проверять нечего - нужен вариант B из описания: README = 3 токена до тех пор, пока цены/промо не понадобятся (M-04, PA-44). Ветка бота `pa-15-…` содержит только `.codex/config.toml` |
| PA-16 | К выполнению | [P2] runbook: SSH к VPS с VPN-машины | вне | сделано - закрыть | Коммит `708933c` «правило SSH-доступа переписано по факту (PA-16)» в main; раздел «SSH-доступ к VPS» в AGENTS.md; `infra/ssh-doctor` |
| PA-17 | В работе | [P3] чистка build/ от PNG + закрыть review-статус provenance-импортов | вне | актуально | `git ls-files build/` = 0 (сделано). Остаток: `provenance/import-inventory.json` - 3 записи `pending_independent_review` (auth-error, path-safety, redact). Одно решение Mike, 10 минут |
| PA-25 | К выполнению | [P3] re-stage из raw evidence для DOWNLOADED-задач без staging | - | свернуть | `grep restage tools/` пусто. Задача под один застрявший отчёт 13.08; прогон 25.08 уже дал 1220 строк staging. Если понадобится - требование «re-stage без сети» в единице M-01 по async CSV |

### 2.3. Планирование фаз и политики (PA-36)

| Ключ | Статус | Суть | Ступень | Вердикт | Факт |
|---|---|---|---|---|---|
| PA-18 | К выполнению | [P1] спланировать Phase 3 | - | свернуть | Планы фаз заменены брифами единиц лестницы (D2); код фазы 3 частично есть (см. PA-1) |
| PA-19 | К выполнению | [P3] спланировать Phase 5 | - | свернуть | См. PA-6 |
| PA-20 | К выполнению | [P2] политика ротации WB-токенов: 3 split-scope + напоминание | M-01 | переписать | Объединить с PA-13 в одну единицу «READ-only токены + ротация». Ротация без READ-only токена не имеет смысла |
| PA-21 | К выполнению | [P2] ADR: точные WB READ endpoints и RPS-лимиты (C9) | M-00 | актуально | Вход уже собран: API-FACTS.md (18 вызовов, лимиты из заголовков, мёртвые методы). ADR пишется из него за одну сессию; на него ссылается PMM-36 |
| PA-22 | К выполнению | [P3] спланировать Phase 6 Data Health UI | - | свернуть | См. PA-8 |
| PA-23 | К выполнению | [P2] спланировать Phase 7: backup/restic, scheduler SLA, restore, incident | M-01 | переписать | См. PA-7; бэкап уже работает (INVENTORY №11), нет расписания сбора и проверки restore |
| PA-24 | К выполнению | [P3] спланировать Phase 8 evidence gate | - | свернуть | См. PA-5 |

### 2.4. Агентная разработка (PA-26)

| Ключ | Статус | Суть | Ступень | Вердикт | Факт |
|---|---|---|---|---|---|
| PA-27 | К выполнению | стандартизировать Makefile как точку входа | вне | сделано - закрыть | HANDOFF 22.08: Makefile - единая точка входа, 18 целей (INVENTORY Прил. j подтверждает `verify` + 17 целей). Хвост: `origin/stash/pa-27-snapshot` (1 коммит, «runtime config centralization», Makefile/README/tools/tests) - решить, нужен ли |

### 2.5. Веб-кабинет и Трек B (PA-37, PA-38)

| Ключ | Статус | Суть | Ступень | Вердикт | Факт |
|---|---|---|---|---|---|
| PA-38 | К выполнению | [P1] Web-кабинет v0: Daily Brief + Decision Inbox (GYR, ₽, SourceRef) | M-03 | переписать | Родитель PA-49..53. v0 = утренняя сводка по одному кабинету (M-03); Decision Inbox → M-05; дашборд → M-04. Разрезать по ступеням |
| PA-49 | В работе | v0 (1/5): каркас Next.js 16 + Better Auth + деплой на VPS | M-03 | сделано - закрыть | WEB-STATE: сдан 26.08, `feat/pa-49-warm-precision` merged в main, staging-контейнер отвечает 200, 26/26 тестов. Остаток «домен + 80/443» - отдельная единица по решению PA-55 |
| PA-50 | В работе | v0 (2/5): скелеты модулей + живой Daily Brief на fixtures | M-03 | актуально | Код в `origin/ai/pa-50` @ `d8c912c` (D11, 4 коммита: `lib/data/{provider,fixtures-provider,postgres-provider}.ts`, карточка сигнала). Не в main - решение Mike о мерже (STATE «Что открыто») |
| PA-51 | К выполнению | v0 (3/5): Decision Inbox - принял/отклонил/причина + история | M-05 | переписать | Дубль PMM-24/PMM-26 по содержанию. Оставить одну единицу M-05, октябрь |
| PA-52 | К выполнению | v0 (4/5): дашборд кабинета - графики, GYR по SKU, drill-down | M-04 | переписать | `/dashboard` - стаб. Ранжирование по SKU = M-04; до базы нормы рисовать нечего |
| PA-53 | К выполнению | v0 (5/5): утренняя Telegram-ссылка на Daily Brief | M-03 | актуально | «Обновляется каждое утро» (D6) требует доставки. Объединить с PMM-27 (critical-алерты) и PMM-32 (daily-цикл) в одну единицу доставки |
| PA-54 | К выполнению | админ-панель здоровья систем + deploy-лог (роль admin) | вне | актуально | `/admin` со стабами 6 модулей в main. Ценность для Mike, не ступень; после M-03. Заменяет PA-8/PA-22 |
| PA-55 | К выполнению | DEC: откат «UI только через SSH-туннель» → публичный URL + auth | вне | переписать | Противоречит ADR-0005 (26.08, «staging за SSH-туннелем, публичный URL отвергнут… до сессии 2»); WEB-STATE: auth не трогать до октября. Сжать до одной DEC-записи: «туннель до M-03, публичный URL + auth после» |
| PA-56 | К выполнению | GlitchTip self-hosted + агентский bugfix-воркфлоу | вне | актуально | Статус отстаёт: INVENTORY №5 - GlitchTip 6.2.6 работает на VPS (1 проект `webapp`, 1 issue 28.08); `infra/glitchtip.compose.yaml` в main; Phase 0+1 в ветке `PA-56-glitchtip` (3 коммита, не слиты). Phase 2-4 (SDK, `scripts/agent/errors`, доки) не начаты. Приоритет после M-03 |
| PA-41 | К выполнению | [P1] импорт scenario engine (fixtures + тесты) в монорепо | M-04 | переписать | W1 (18 файлов, SHA-256 18/18) + SCN-008 slice выполнены 27.08 и слиты (`services/control-plane/src/proxima/`, TASKS.md). Jira не обновлена. Закрыть W1 как сделанное; W2 (LLM-срез, 8 файлов) - единица M-04 после контрактов PMM-29 |
| PA-44 | К выполнению | [P1] источники M2: Advertising, Feedbacks, Content/цены, MPStats | M-04 | переписать | Ни одного адаптера в репо (API-FACTS §D). Разрезать по источникам, каждый - когда нужен сигнал; WB Advertising под запретом DEC-006 (HANDOFF) - снимать отдельным решением |

### 2.6. Discovery (PA-35)

| Ключ | Статус | Суть | Ступень | Вердикт | Факт |
|---|---|---|---|---|---|
| PA-40 | К выполнению | [P2] клиентские интервью 2-3: ценность AI-отчётов, готовность платить | вне | актуально | Не код. Вход для Ворот после M-03 и для M-05 |
| PA-42 | К выполнению | [P1] AM-интервью: валидация 8 сценариев + baseline времени на мониторинг | вне | актуально | Baseline time-to-detect нужен PMM-28 (value-gate). Провести до M-03, иначе «раньше ручного мониторинга» не измерить |

## 3. PMM - открытые (29)

### 3.1. Управление и governance (PMM-1, PMM-6)

| Ключ | Статус | Суть | Ступень | Вердикт | Факт |
|---|---|---|---|---|---|
| PMM-1 | Backlog | [init-m2] управляющая задача W1-среза | вне | переписать | Срез «сигналы → LLM → Daily Brief → подтверждение» = M-03..M-05 в терминах лестницы. Сжать до указателя на STATE.md и лестницу; открытый вопрос DECISIONS «где истина по задачам» |
| PMM-6 | Backlog | эпик Governance & Foundations M2 | вне | актуально | Контейнер: 5 детей Done (7/8/9/10/12), открыты PMM-2/4/11/13/14/15/16/17/18/19/31 |
| PMM-11 | В работе | exit-критерии W1-среза | M-03 | переписать | Утверждены Mike 27.08, `docs/exec-plans/active/w1-slice-exit-criteria.md` в main (PR #22). Шесть критериев (value-gate, оба ADR Accepted, реестры, reviewer-eval, velocity, ретро) шире D6. Сжать до DoD M-03: «сводка по одному кабинету обновляется каждое утро» |
| PMM-2 | В работе | [SPIKE] налоговые сценарии для юнит-экономики → ADR | M-04 | актуально | ADR-0001 в main, статус Draft (PR #10, DEC-007). Блокер внешний: бухгалтер Q1-Q4 + инвентаризация юрлиц (TASKS «From Mike»). Нужен для profit-версии ₽-оценки (PMM-22), то есть M-04. Статус «В работе» → «ожидает входа» |
| PMM-14 | Backlog | [SPIKE] Build vs Buy, полный охват, ≤3 дня | - | свернуть | Решение «строим лестницу» принято D2/D6; мировой ресёрч есть (`docs/archive/planning-m1/research/GLOBAL-LANDSCAPE-2026-08-16.md`); MPStats-бенчмарки живут в PA-44. Если Mike хочет ADR - 1 страница из существующего ресёрча, не спайк |
| PMM-31 | Backlog | LLM-доступ: две модели, egress с VPS, ключи, бюджет → ADR | M-04 | актуально | Провайдера кроме mock нет (`diagnosis/adapters/factory`: `provider != mock → ValueError`). INVENTORY флаг 8: egress = один SSH-туннель на 153.56.134.240. Нужно одобрение Mike на VPS-операции (HANDOFF) |
| PMM-4 | Backlog | growth-gate: расширение backlog при 2+ FTE | - | свернуть | Метка `deferred`; Ворота лестницы делают то же. Вернуть при V2 |
| PMM-13 | Backlog | baseline velocity после спринтов 0-1 | - | свернуть | 1 FTE + агенты, спринтов нет; ступени лестницы измеряются датами Ворот, не velocity. Тянет за собой exit-критерий 5 PMM-11 |
| PMM-15 | Backlog | refinement-каденция STUB → FULL перед спринтом | - | свернуть | Заменена брифом единицы работы (grill-me → release-gate → autopilot, AGENTS.md) |
| PMM-16 | Backlog | onboarding AI-ops аналитика | вне | актуально | Ждёт выхода аналитика (внешний вход, TASKS). Маршрут онбординга = STATE.md + DECISIONS.md + лестница; переписать список ролей после Ворот 2 |
| PMM-17 | Backlog | ops-проект для задач, создаваемых продуктом (до R4) | - | свернуть | `deferred`, за горизонтом M-05 |
| PMM-18 | Backlog | Ozon Seller/Performance API (post-M3) | - | свернуть | `deferred`, DEC-006 запрещает Ozon; за горизонтом |
| PMM-19 | Backlog | ретро + sprint review каденция | вне | переписать | Спринтов нет. Ретро - на каждых Воротах (rewrite-method Phase 6), шаблон RETRO переиспользовать |

### 3.2. W1-срез: сигналы, LLM, доставка, решения (PMM-3)

| Ключ | Статус | Суть | Ступень | Вердикт | Факт |
|---|---|---|---|---|---|
| PMM-3 | Backlog | эпик W1-срез: сигналы → Daily Brief → подтверждение (SCN-008/001/005) | M-03..M-05 | переписать | 13 детей. Разрезать: SCN-001 + сводка = M-03; SCN-005, LLM-диагноз, ₽, reviewer = M-04; inbox, decision memory, value-gate = M-05. Ветка `pmm-3-w1-daily-brief…` merged (только доки) |
| PMM-29 | В работе | контракты signal / diagnosis / decision-record v1 + codegen | M-03 | актуально | Bot lane. Ветка `mihailzhamba-bot/pmm29-contracts` @ `72423c2` «close PMM-29 contracts run» 29.08: `contracts/{signal,diagnosis,decision-record}.schema.json` + 6 synthetic-примеров + TS-типы. 4 коммита, не слиты (§5). Контракт сигнала нужен сводке M-03 - решение о мерже на Воротах 1 |
| PMM-20 | В работе | SCN-001 детектор падения продаж (U×CVR×AOV, baseline 7/14/28) | M-02 / M-03 | актуально | Ветка `pmm-20-scn-001-…` @ `7841ab0` (28.08, codex gate 0/0): `detectors/scn001/{baseline,decomposition,loader,metrics,signal,smoke,…}.py` + тесты, 7 коммитов, не слиты. Оговорка API-FACTS: воронки (CVR) в синхронном API больше нет - декомпозицию U×CVR×AOV сузить до заказов/продаж (вариант 3 плана Б), воронка вторым слоем |
| PMM-23 | Backlog | SCN-005 детектор OOS / days-cover | M-04 | актуально | Второй тип аномалии; вход `stocks-report/wb-warehouses` (в коллекторе, не проверен 30.08) + контракт поставок PMM-34 (в main). После M-03 |
| PMM-21 | В работе | Client Passport v1: контракт + пороги per-client | M-04 | актуально | Код в main: `contracts/client-passport.schema.json`, `db/migrations/010_client_passport_supply_plan.sql`, `services/collector/src/contracts/client-passport.ts` + тест (PR #33). Остаток = заполнить паспорт пилота (COGS от Mike). Пороги per-client нужны приоритету M-04 |
| PMM-22 | Backlog | ₽-оценка сигналов «стоимость молчания»: revenue v1 → profit v2 | M-04 | актуально | D6: ранжирование по деньгам = M-04. revenue v1 можно на `priceWithDisc`/`forPay` из Statistics (API-FACTS); profit v2 ждёт ADR-0001 Accepted |
| PMM-5 | Backlog | LLM Analyst W1: диагноз SCN-008/001/005 | M-04 | сделано - закрыть | HANDOFF/TASKS: DONE 28.08, PR #29 merged `6c29398`, пакет `proxima_control_plane.diagnosis`, eval 12/12; HANDOFF утверждает «Jira PMM-5 Готово», но live-статус 30.08 = Backlog. Только mock-провайдер; реальный = PMM-31 |
| PMM-25 | Backlog | Independent Reviewer BLOCK-режим с дня 1 | M-04 | актуально | Нужен только с реальным LLM (PMM-31). До этого - детерминированные проверки в `diagnosis/service.py` уже есть |
| PMM-33 | Backlog | eval-инфраструктура LLM: датасет, раннер, пороги в CI, adversarial | M-04 | актуально | Половина есть: `tests/diagnosis/eval_runner.py`, 12 кейсов (standard/closed_numbers/adversarial), гейт 0.80. Остаток = порог в CI + датасет на живых сигналах |
| PMM-32 | Backlog | daily-цикл 07:00 MSK: оркестрация, идемпотентность, freshness-гейт | M-01 / M-03 | актуально | **Критично для сентября.** INVENTORY флаг 3: расписания сбора нет (ни cron, ни timer), данные с 25.08 не обновлялись. Без этого нет ни бэкфилла, ни «каждое утро». Объединить с PA-7/PA-23 |
| PMM-27 | Backlog | Telegram critical-алерты, узкий канал | M-03 | переписать | Объединить с PA-53 в одну единицу доставки; бот и chat_id уже на сервере (монитор шлёт в тот же чат) |
| PMM-24 | Backlog | связка Decision Inbox (PMM) ↔ web-кабинет PA-38 | M-05 | переписать | Дубль PA-51 по содержанию; одна единица M-05 |
| PMM-26 | Backlog | Decision Memory v0: решение → expected → actual → learning | M-05 | актуально | Контракт decision-record в ветке PMM-29. Октябрь |
| PMM-35 | Backlog | калибровка Оценки 1-10 и осей сортировки Decision Inbox | M-04 | актуально | THIN; ждёт PMM-22 и PMM-26. Порог ярусов - конфиг, не UI |
| PMM-36 | Backlog | Supplies API spike фаза B: факт приёмки + lead time | M-04 | актуально | THIN, «после V1 gate». Нужен токен «Поставки» от Mike; результат - в C9-ADR (PA-21) |
| PMM-28 | Backlog | V1 value-gate: первый сквозной сигнал AI → AM → результат (демо) | M-03 / M-05 | переписать | 6 блокеров. Разрезать на Ворота: после M-03 - «сводка с отклонением видна и обновляется» (D6), после M-05 - сквозной цикл с подтверждением AM и expected-vs-actual. Baseline time-to-detect из PA-42 |

## 4. Done - сверка с кодом (23)

| Ключ | Готово | Суть | Артефакт в `origin/main` | Вердикт |
|---|---|---|---|---|
| PA-9 | 25.08 | [P1] план 02-02: XLSX → парсер → staging → preview | Метка `cancelled`; коммит `42616ba` (preview order_count) merged, ветка `pa-9-p1-02-02…` (5 коммитов) не слита | Done-без-кода по замыслу (отменён Mike 25.08) |
| PA-10 | 15.08 | [P1] диагностика async Analytics: 3 raw responses при 0 строк | Разбор в HANDOFF/EVIDENCE; преемник PA-25 | с артефактом (диагностика = документ) |
| PA-11 | 15.08 | [P1] delivery-тест Telegram + `proxima-host-monitor.timer` | `infra/monitoring/proxima-host-monitor.timer`; INVENTORY №10: таймер живой, state.json 30.08 | с артефактом |
| PA-12 | 15.08 | [P2] STATE/EVIDENCE: CI зелёный на `1a211c9` | `docs/archive/planning-m1/phases/02-…/EVIDENCE.md`; ветка `pa-12-state-evidence` (1 коммит, старый `.planning/`) не слита | с артефактом (хвост в ветке) |
| PA-28 | 15.08 | стандарт coding agents | `c3e4005` в main | с артефактом |
| PA-29 | 15.08 | отказ от собственного agent harness | **Нет:** `grep -i harness` по AGENTS.md/DECISIONS/MEMORY пусто; ветка `pa-29-agent-harness` (1 коммит, 5 файлов, +108) не слита | **Done-без-кода - флаг** |
| PA-30 | 15.08 | минимальный MCP + CLI toolset | `docs/operations/agent-toolset.md`, `tools/verify_agent_toolset.py`; ветка `pa-30-…` (4 коммита: Makefile, bootstrap, .codex) не слита | с артефактом (хвост в ветке) |
| PA-31 | 15.08 | маршрутизация контекста в AGENTS.md | «Карта контекста» в AGENTS.md | с артефактом |
| PA-32 | 15.08 | AGENTS.md + CLAUDE.md-адаптер | Оба файла в main (CLAUDE.md = `@AGENTS.md`) | с артефактом |
| PA-33 | 15.08 | версии зависимостей в AGENTS.md | Таблица toolchain (Node/Python/uv/PG/Mermaid) есть; таблица зависимостей (TS 5.8.3, Ajv, decimal.js, pg) - только в ветке `pa-33-agents.md` (HANDOFF 22.08: PR #3 не дубль) | частично |
| PA-39 | 23.08 | [P1] аудит scenario engine в Опрос-v2.2 | `docs/audits/pa-39-{scenario-engine-audit.md,import-allowlist.yaml,hash-transcript.txt}` | с артефактом |
| PA-43 | 17.08 | Client Passport + недельный PDF + Auditor | `superseded-by-pmm` → PMM-21 | Done-без-кода по замыслу |
| PA-45 | 17.08 | W3: SCN-009 отзывы + SCN-010 акции + SCN-011 контент | `superseded-by-pmm`, **преемника в PMM нет** (в PMM только W1 SCN-008/001/005) | Done-без-кода по замыслу; скоуп потерян |
| PA-46 | 17.08 | verification-петля expected vs actual + Decision Memory | `superseded-by-pmm` → PMM-26, PMM-28 | Done-без-кода по замыслу |
| PA-47 | 17.08 | LLM Analyst + Independent Reviewer | `superseded-by-pmm` → PMM-5, PMM-25 | Done-без-кода по замыслу |
| PA-48 | 17.08 | W2: SCN-007 DRR + SCN-002 заказы + SCN-004 маржа | `superseded-by-pmm`, **преемника в PMM нет** | Done-без-кода по замыслу; скоуп потерян |
| PMM-7 | 18.08 | charter-pointer: PRODUCT-VISION.md как чартер M2/M3 | Коммит `2d6e634` (release-gate dry-run 27.08 подтверждает); ветка `pmm-7-charter-pointer` = только `opencode.json` | с артефактом |
| PMM-8 | 27.08 | Glossary + KPI-дерево M2 (7 метрик PV §8) | **Нет:** `docs/governance/m2-glossary-kpi.md` только в ветке `mihailzhamba-bot/pmm-8-glossary-kpi-…` (коммит `0dfdc24`, снапшот pre-freeze 29.08); `git ls-files docs/governance` = 3 файла без него | **Done-без-кода - флаг** |
| PMM-9 | 18.08 | реестр допущений и открытых вопросов | `docs/governance/assumptions-register.md` (PR #12) | с артефактом |
| PMM-10 | 18.08 | risk register среза | `docs/governance/risk-register.md` (PR #12) | с артефактом |
| PMM-12 | 28.08 | DoD-чеклист среза | `docs/governance/dod-checklist.md`; ветка `pmm-12-dod-checklist` = только конфиги | с артефактом |
| PMM-30 | 17.08 | DEC-006: снять запрет на LLM runtime и client-facing UI | `docs/agent-system/DECISIONS.md` DEC-006 | с артефактом |
| PMM-34 | 28.08 | источник данных о поставках в пути: решение + контракт | `contracts/supply-plan.schema.json`, миграция 010, `collector/src/contracts/supply-plan.ts` (PR #33) | с артефактом |

Итог по Done: 15 с артефактом в main, 1 частично (PA-33), 7 Done-без-кода. Из семи - 5 superseded и 1 cancelled по решениям Mike (нормально, но PA-45 и PA-48 потеряли скоуп без преемника: сигналы SCN-002/004/007/009/010/011 нигде не заведены - это M-04, решить на Воротах 2), и 1 настоящий флаг PMM-8. Плюс PA-29 - Done с артефактом только в ветке (второй флаг). Ещё одна аномалия в обратную сторону: PMM-5 в HANDOFF «Jira Готово», в live-Jira - Backlog.

## 5. Код без Done: ветки origin впереди main (30.08)

`git rev-list --count origin/main..<ветка>`, содержательные файлы без `.autopilot/`, `docs/agent-system/`, конфигов агентов. Пересекается с MIGRATION-GAPS (окно A), но там сличение с локальным архивом, здесь - GitHub.

| Ветка | Дата | Впереди | Что внутри | Задача | Ступень |
|---|---|---|---|---|---|
| `ai/pa-50` | 29.08 | 4 | `webapp/src/lib/data/{provider,fixtures-provider,postgres-provider,types}.ts`, карточка сигнала, brief/page.tsx | PA-50 | M-03 |
| `mihailzhamba-bot/pmm29-contracts` | 29.08 | 4 | `contracts/{signal,diagnosis,decision-record}.schema.json` + 6 примеров + TS-типы | PMM-29 | M-03 |
| `mihailzhamba-bot/pmm-20-scn-001-…` | 28.08 | 7 | `control-plane/…/detectors/scn001/` (10 модулей) + `tests/detectors/` | PMM-20 | M-02/M-03 |
| `mihailzhamba-bot/PA-03-02-promotion` | 27.08 | 2 | `db/migrations/010_promotion_attempt_completion.sql`, `collector/src/facts/promote-order-counts.ts`, CLI, тест, `verify_migrations.py` | PA-1 | M-01 |
| `mihailzhamba-bot/pa41-full-w2-phase3` | 29.08 | 1 | те же файлы promotion + `010_phase3_promotion_privileges.sql` (имя ветки про PA-41 W2, содержимое - Phase 3); конфликт номера 010 с main | PA-1 | M-01 |
| `mihailzhamba-bot/PA-56-glitchtip` | 28.08 | 3 | `infra/glitchtip.compose.yaml` (правки), `verify_runtime_boundary.py` (loopback-гейт) | PA-56 | вне |
| `mihailzhamba-bot/pmm-8-glossary-kpi-…` | 29.08 | 2 | `docs/governance/m2-glossary-kpi.md` | PMM-8 (Done) | вне |
| `mihailzhamba-bot/pa-29-agent-harness` | 15.08 | 1 | AGENTS.md, CLAUDE.md, `docs/decisions/`, `verify_runtime_boundary.py` + тест | PA-29 (Done) | вне |
| `mihailzhamba-bot/pa-30-mcp-cli-toolset` | 15.08 | 4 | Makefile, `infra/bootstrap`, `.codex/config.toml`, тесты | PA-30 (Done) | вне |
| `mihailzhamba-bot/pa-33-agents.md` | 15.08 | 1 | таблица зависимостей в AGENTS.md | PA-33 (Done) | вне |
| `stash/pa-27-snapshot` | 29.08 | 1 | Makefile runtime config centralization | PA-27 | вне |
| `mihailzhamba-bot/pa-9-p1-02-02-…` | 16.08 | 5 | XLSX staging/preview (отменено) | PA-9 (cancelled) | - |

Не в таблице (только доки/конфиги/`.autopilot`): `feat/pa-49-webapp-skeleton` (2), `now-orchestrator` (5), `pa-12-state-evidence` (1), `pmm-12-dod-checklist` (1), `pmm-7-charter-pointer` (1), `pa-15-…` (1), `docs/session-1-inventory` (эта ветка). Ветки с `ahead=0` (merged) - 22, перечислять нет смысла.

Две ветки (`PA-03-02-promotion`, `pa41-full-w2-phase3`) обе добавляют миграцию с номером 010, который в main уже занят `010_client_passport_supply_plan.sql` (PR #33) - при мерже перенумеровать (ledger additive-only, DEC-002).

## 6. Сводка вердиктов

| | актуально | переписать | свернуть | сделано - закрыть | итого открытых | Done с артефактом | Done-без-кода |
|---|---|---|---|---|---|---|---|
| PA | 13 | 13 | 10 | 3 | 39 | 9 (+1 частично) | 6 (PA-9, 43, 45, 46, 47, 48) + флаг PA-29 |
| PMM | 15 | 7 | 6 | 1 | 29 | 6 | 1 (PMM-8, флаг) |
| **Итого** | **28** | **20** | **16** | **4** | **68** | **15 (+1)** | **7 (+ PA-29)** |

Свернуть (16, явно): PA-4, PA-5, PA-6, PA-8, PA-18, PA-19, PA-22, PA-24, PA-25, PA-37, PMM-4, PMM-13, PMM-14, PMM-15, PMM-17, PMM-18.

Сделано - закрыть (4): PA-16, PA-27, PA-49, PMM-5.

Статус в Jira врёт в обе стороны у 9 задач: «В работе» без движения - PA-13, PMM-2 (оба ждут внешний вход); «На проверке» без предмета проверки - PA-15; «К выполнению» при сделанном коде - PA-16, PA-27, PA-41 (W1), PA-56 (Phase 0-1); «В работе» при сданном - PA-49; «Backlog» при merged - PMM-5. HANDOFF от 29.08 сам просит сверить 10 ключей (п. «Exact next action») - эта таблица закрывает вопрос данными.

## 7. Что это значит для Ворот 1 и 2

1. **Мерж-решения Mike (Ворота 1):** `ai/pa-50`, `pmm29-contracts`, `pmm-20-scn-001`, `PA-03-02-promotion` - четыре ветки с кодом прямо под M-01..M-03 (§5). Вариант по умолчанию: ревью и мерж в порядке контракты → promotion → детектор → провайдер webapp; перенумеровать миграции 010.
2. **Два флага Done-без-кода:** PMM-8 и PA-29 - либо домержить ветки (по 1-2 коммита), либо снять Done. В Jira не трогать до Ворот 2.
3. **Перенос в лестницу (Ворота 2, разовая правка Jira):** 16 свернуть, 4 закрыть как сделанные, 9 статусов поправить, 20 переписать - переписывание удобнее делать созданием новых единиц под ступени и закрытием старых со ссылкой, чем редактированием описаний.
4. **Потерянный скоуп:** сигналы SCN-002/004/007/009/010/011 (PA-45, PA-48) не заведены нигде. Это M-04; решить, нужны ли в октябре.
5. **Сентябрьский критический путь по бэклогу:** PMM-32 (расписание) → PA-3 (бэкфилл 26 недель) → PMM-20 (норма по заказам) → PMM-29 (контракт сигнала) → PA-50 (провайдер в `/brief`) → PA-53 (утренняя доставка). Всё, кроме PA-3 и PA-53, уже частично написано.
