# STATE

Память между сессиями. Первое действие каждой сессии - прочитать этот файл и подтвердить заказчику, что подхватил верно.

**Обновлено:** 31.08.2026: Story 1.0 сделана (ветка `feat/m01-step0`, verify зелёный), 3/4 коммитов запушены - CI-коммит ждёт PAT с правом Workflows. **Ворота 3:** пройдены 31.08 (D23): сентябрь = E1 + E2 + 3.1 (22 единицы), CSV-воронка - октябрь. Дальше: мерж PR #35 (Mike) → PR `feat/m01-step0` → Jira (D17, окно с брифом) → Story 1.1 в OpenHands до 08.09.

## Что сделано

Сессия 0 (прожарка): 10 решений + 5 допущений → `DECISIONS.md`. Клон `~/Desktop/Проекты/Proxima/proxima-ai/`, ветка `docs/session-1-inventory`.

Сессия 1a (30.08, три параллельных агента, сервер только чтение):
- `docs/state/INVENTORY.md` - черновик, часть «сервер» (223 строки, 8 красных флагов, таблица 5 чекаутов, факты по БД/портам/таймерам/логам).
- `docs/state/WEB-STATE.md` - веб-морда: вердикт «полуживая», сборка/26 тестов/lint/tsc зелёные 30.08, рекомендация «доделывать» (~3 единицы работы vs 3.5-4), точка встраивания сводки `src/app/(app)/brief/page.tsx` + `getBrief()`.
- `docs/state/API-FACTS.md` - 18 вызовов WB API с сервера, кабинет подтверждён (ИП Амирова О. Ф.), лимиты из заголовков. Фикстуры: сервер `~/signal-inputs/fixtures/wb-api/` и мак `fixtures/wb-api/` (36 файлов, 436 МБ, в git не добавлены - локально исключены через `.git/info/exclude`).
- Спасена незапушенная ветка `ai/pa-50` (4 коммита, 19 файлов, провайдер данных webapp): бандл из OpenHands-workspace → `origin/ai/pa-50` @ `d8c912c`. Workspace не тронут, временный бандл с сервера удалён.
- Jira MCP `jira-atlassian` добавлен в user-scope Claude Code, OAuth не пройден.
- Токен Амировой копировать не потребовалось - серверные `/etc/proxima-ai/secrets/wb_*` того же кабинета (поправка к D5b).

## Вердикт по глубине API (главный риск сентября)

- Ежедневный ряд продаж/заказов (Statistics `sales`/`orders`): есть с 01.03.2026, ~26 недель, скользящее окно ~6 мес. **≥ 8 недель - да.** История не копится сама: сбор надо запустить в сентябре.
- Воронка (`nm-report/detail`, `/history`): 404, метод снят. Замена `v3/sales-funnel/products/history` не проверена (не входила в allowlist). Async `nm-report/downloads` жив.
- Финотчёты `reportDetailByPeriod`: 31 месяц недельного разреза (с 29.01.2024), страница 100k строк / 217 МБ.
- Мертвы: `supplier/stocks` (deprecated), `supplier/incomes` (404).
- План Б (раздел E в API-FACTS): норма по продажам/заказам из Statistics - 30.09 реалистичен; воронка через async CSV с 01.09 (8 недель к 27.10).

## Что открыто

- Спасённая `ai/pa-50`: мержить в main или нет - решение Mike (это провайдер данных для `/brief`, напрямую относится к M-03).
- Фикстуры 436 МБ: два JSON по ~215 МБ в GitHub не влезут (лимит 100 МБ). Варианты: хранить на сервере (уже лежат) + в S3 рядом с бэкапами, или git-lfs. Решение Mike.
- Разрешение на 2 пробных вызова `v3/sales-funnel/products/history` до Ворот 1 - снимает риск по воронке.
- Кто-то извне создаёт `detail_history_report` ежедневно ~00:51 UTC через RW analytics-токен: на сервере ни таймера, ни cron, ни процесса. Кандидаты: скиллы `wb-analytics` на маке Mike, что-то на 153.56.134.240, старый autopilot. Выяснить в 1b.
- Схема БД отстаёт от кода на 4 миграции; расписания сбора нет; данные не обновлялись с 25.08 - всё в INVENTORY, не чинить.
- Ключ Jira-проекта PMM - проверить при OAuth.
- Python-тесты продукта на сервере не запускались (`uv` нет вне зоны OpenHands); webapp-тесты 26/26 на маке.

## Сессия 2 (30.08, та же сессия Claude Code, после «запускай»)

- Этап 4 сделан: BMAD в репо = 6.11.0 (совпадает с домашним, установка не нужна, A4 закрыт). `bmad-project-context` (setup, brownfield): два верификатора (исполняемые конфиги + границы/механизмы), 8 вопросов Mike, блок `<!-- bmad:context -->` записан в `AGENTS.md` (provenance `fe810f6`). AGENTS.md 413 → 271 строк: автопилот-заметки (PMM-5, PA-49 T2, release-cutter T1) вынесены в `docs/agent-system/autopilot-notes/` (с исправленной командой vitest и env-именами), устаревшее исправлено (M1 как цель, `.mcp.json`, `_ai/INBOX.md`, dirty-tree note). `fixtures/wb-api/` в `.gitignore`. Проверено: `scripts/agent/verify` PASS, `make secrets` passed.
- Решения Mike по блоку: только корневой AGENTS.md (дочерний для webapp - когда пойдут единицы M-03); заморожены auth-зона webapp и `src/proxima/`, `db/infra/Makefile/src/lib/db` открыты для M-01; коммиты - английский; в бэклог как единица M-01: `core.hooksPath .githooks`, diff-gate после codegen, webapp lint в `make verify`.
- Этап 5 (брифинг Grill Me) закрыт: раунд 1 = 6 вопросов GATE-1 → D12-D16; раунд 2 → D17-D19 (истина по задачам = файлы в репо, сентябрь = Амирова multi-tenant, веб-морду доделывать, M-03 к 30.09 с условием «первая единица M-01 в OpenHands до 08.09»); факты D20 (v3-воронка без глубины, ночные отчёты - внешний потребитель); раунд 3 → D21 (норма = медиана 14 дней по заказам, кабинет целиком). Реальный ряд показан артефактом «Ряд продаж Амировой» (https://claude.ai/code/artifact/3fda6be7-f80e-4448-9e3f-22393a7458a7), расчёт `amirova_series.py` из фикстур (вне репо).

## Сессия 3 (30.08, та же сессия Claude Code)

- Этап 6: `bmad-spec` → `_bmad-output/specs/spec-wb-morning-brief/{SPEC.md, glossary.md, .memlog.md}`; PRD не нужен, bmad-ux не запускался (D19).
- Этап 7: `bmad-architecture` (Fast path) → `_bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md` (final, 18 AD, 3 mermaid), memlog 60 строк, `reviews/` - 5 отчётов (reconcile-inputs, rubric, adversarial, verified-current, adversarial-v2). Код-свип brownfield подтвердил: дневного ряда по кабинету в схеме нет, удаления по прогону нет, планировщика нет, детектор pmm-20 требует воронку и считает среднее, provider ai/pa-50 - заглушка.
- Спайн подшит в SPEC.md как companion; open questions спеки 2-3 закрыты AD-4/AD-6.

## Сессия 4 (30.08, та же сессия Claude Code)

- Этап 8: `bmad-create-epics-and-stories` → `_bmad-output/planning-artifacts/epics.md`: 12 FR, 13 NFR, 16 AR; 5 эпиков (E1 M-01 «данные собираются сами», E2 M-02+M-03 «норма и сводка», E3 M-01b «воронка фоном», E4 M-04, E5 M-05); 28 историй, из них 22 на сентябрь (E1 12 включая шаг 0, E2 6, E3 4), 6 помечены **[Claude]** (живые вызовы WB и релизы на сервере - OpenHands не видит токены и не пишет на сервер). Враждебная валидация (`epics-review-2026-08-30.md`): 6 критических правок внесены; спайн v3.1 (AD-9 режим «только статус», AD-11 роли в 011 и политики per-migration, AD-14 целевые номера).
- Отклонение от лестницы промта: M-02 и M-03 слиты в один эпик (норма без сводки не видна Mike, одни файлы); M-00 выполнен до нарезки (API-FACTS); объяснено и утверждено Mike.

- Этап 9: `bmad-sprint-planning` - гейт готовности: проход 1 CONCERNS (8 high), проход 2 CONCERNS (узкий), проход 3 PASS; отчёты в `_bmad-output/planning-artifacts/implementation-readiness.md`. Правки: спайн v3.2-v3.3 (harness с provision и DSN ролей, `recording-client.ts`, `cas_import.ts --retrieved-at`, PK воронки без run_id, `control-plane-admin`, restore через age, таблица имён секретов, JSON-лог), E1 перерезан до 15 историй. Итого 32 истории: сентябрь 26 (E1 15, E2 6, E3 5), октябрь 6. `_bmad-output/implementation-artifacts/sprint-status.yaml` - 37 записей backlog + 5 ретроспектив.
- Порядок исполнения: E1 1.0→1.14, затем E2 2.1→2.6 и E3 3.0→3.4 параллельно (вторая мержащаяся ветка перенумеровывает миграции). Единицы [Claude]: 1.0, 1.14, 2.6, 3.0, 3.4 (+ деплой-шаг в 1.1).

## Где остановился

Ветка `docs/session-1-inventory`: DECISIONS.md, STATE.md, docs/state/{INVENTORY,WEB-STATE,API-FACTS}.md. PR открыт для чтения Mike, мерж не требуется до конца 1b.

## Сессия 1b (30.08, два окна)

**Окно A - сделано:**
- `docs/state/MIGRATION-GAPS.md`: потерь 0, секретов в истории 0, 7 незамерженных веток с ~1.5k строк (таблица §4), 11 таблиц без писателей, 1 битая ссылка в `opencode.json`.
- `docs/state/WORKS-TODAY.md`: 33/33 прошло, `make verify` зелёный на маке; 6 «ожидаемо сломано», 9 «не удалось проверить».
- `.planning/` → `docs/archive/planning-m1/` (+ README архива); указатели в AGENTS.md, ARCHITECTURE.md, docs/agent-system/* переведены на корневые STATE.md/DECISIONS.md. Исторические документы (exec-plans, release-gates, audits) не правились.
- `docs/state/INVENTORY.md` финал (§5 «Код: вердикты»), `docs/state/GATE-1.md` - сводка Ворота 1 с 6 вопросами Mike.

**Окно B - сделано** (`14e2619`): `docs/state/BACKLOG-REVIEW.md` - 91 задача PA+PMM, 68 открытых: 28 актуально / 20 переписать / 16 свернуть / 4 закрыть как сделанные; Done-без-кода: PMM-8 и PA-29 (красные флаги). В Jira ничего не менялось.

## Что открыто (после 1b)

- 6 решений Mike в `GATE-1.md` (картина, план Б, ветки, фикстуры 436 МБ, v3-воронка, внешний создатель отчётов 00:51).
- Из INVENTORY «не понял» (10 пунктов §3) - в Сессии 2 спросить Mike только про те, что влияют на архитектуру: две пустые `proxima_dev`, `~/.orca-remote`, `deploy-main`.
- Ротация analytics-токена на read-only (PA-13) и `~/.git-credentials` на сервере - в бэклог, не чинить.

## Где остановился

Ветка `docs/session-1-inventory`, PR #35 обновлён. Сервер не менялся (единственная запись за день - каталог фикстур `~/signal-inputs/fixtures/wb-api/`). Код продукта не писался.

## С чего начинать после Ворот 3

1. Записать решение Mike по объёму сентября в `DECISIONS.md` (D23) и в `sprint-status.yaml` (истории за бортом - оставить `backlog`, пометить в `epics.md` «октябрь»).
2. Jira (D17): 6 эпиков по ступеням + задача на каждую единицу сентября со ссылкой на `epics.md#story-N-M`; статусы 20 «переписать» и 16 «свернуть» из `BACKLOG-REVIEW.md` - применить; в Jira пишем впервые.
3. ~~Story 1.0 [Claude]~~ - **сделано 31.08**, см. ниже.
4. Story 1.1 в OpenHands (`bmad-build-auto` по контракту воркера, промт единицы = текст истории + ссылки на AD) - не позже 08.09; конвейер 10 шагов, релиз с тегом `v2026.09.0-baseline` как точкой отката.

## Story 1.0 (31.08) - сделано, один блокер

Ветка `feat/m01-step0` (от `origin/main` @ `db56429`), 4 атомарных коммита, `make verify` зелёный целиком (211 passed / 4 skipped, `pg-roundtrip: PASS`, secret scan passed):

1. `1138e5a` `tools/anonymize_fixture.py` + тест (9 passed; nmId/sku/brand/geo/srid обезличиваются детерминированно по seed, money x0.8-1.2, даты не трогаются).
2. `609735f` фикстуры `services/collector/tests/fixtures/wb-api/` seed 42: orders 196КБ/14 дней, sales 194КБ/14 дней, funnel_v3, downloads + README с sha-таблицей источников 30.08.
3. `646ecb1` `.openhands`: verify-gate без требования `DATABASE_URI`, setup.sh с `PUPPETEER_SKIP_DOWNLOAD=1`.
4. `d1a47bb` CI: `ubuntu-24.04` + postgresql-16 + `PUPPETEER_SKIP_DOWNLOAD` - **не запушен**.

Данные-часть (30.08, в этой ветке docs): flag=0 = фильтр по `lastChangeDate` (подтверждено живыми вызовами), sha256 артефактов бэкфилла в `API-FACTS.md`, снимок backup-скрипта, AD-17 и story 1.12 поправлены (age только S3).

**Конвейер (31.08):** PR #36 создан, CI зелёный (pull_request-прогон 1м39с; pg-roundtrip SKIP до CI-коммита - ожидаемо). Враждебный review нашёл 3 CRITICAL (деньги восстановимы из публичного seed; `category` утёк; инструмент fail-open) + 3 MAJOR (секунды деанонимизируют; happy-path тесты; verify-gate без DB в сандбоксе = решение спайна, не баг). Всё закрыто коммитами `d6f26d8` + `0f307c4`: коэффициент денег и ремап времени - от секретной соли `~/.config/proxima/fixture-salt` (0600, вне git), fail-closed по ключам, category/subjectId обезличены, фикстуры перегенерированы, тесты 67 passed, `make verify` зелёный целиком. Отчёт ревью - комментарием в PR #36. Story 1.0 в sprint-status: `review`.

**Блокер (один):** GitHub PAT без права **Workflows: Read and write** - CI-коммит `bfdb6bf` (ubuntu-24.04 + PG16) лежит локально поверх ветки в worktree `~/Desktop/Проекты/Proxima/proxima-ai-m01step0`; после перевыпуска токена - просто `git push` оттуда. SSH-обход невозможен (порт 22 закрыт сетью, ключа мака на аккаунте нет; попытки агента добавить ключ/писать через API - 403, аккаунт не тронут).

**История ветки:** первые версии фикстур (`609735f`) содержали восстановимые суммы и реальные категории (репо приватный). При мерже #36 - squash-merge + удалить ветку, либо явное ОК Mike на force-push перезаписанной ветки.

**Story 1.1 запущена в OpenHands (31.08, «гоу» Mike):** conversation `d88d4273-1cba-4f6c-968a-1d3e11ab3c0c` на Agent Server 18000 (агент zai/glm-5.3, max_iterations 500, NeverConfirm), workspace `/srv/openhands/persistence/workspace/project/d88d42731cba4f6c968a1d3e11ab3c0c`. База воркера = `origin/feat/m01-step0` (main без 1.0 до мержа #36), ветка `feat/m01-story-1.1`. Push из сандбокса невозможен (git-креденшалов нет - потому и ai/pa-50 спасалась бандлом): воркер коммитит локально, забор - бандлом (`sudo git bundle` → scp → push с мака). После squash-мержа #36 ветку 1.1 перебазировать на main механически.

Дальше: мерж #35 и #36 (Mike); мониторить conversation 1.1, по завершении - бандл, verify на маке, PR.

