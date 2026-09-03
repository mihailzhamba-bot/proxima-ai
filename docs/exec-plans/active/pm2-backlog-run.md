> **Статус на 03.09.2026: неактивен.** План относится к рамке M1/W1, снятой решением D2 (30.08.2026) в пользу лестницы M-00..M-05. Действующая нарезка - `_bmad-output/planning-artifacts/epics.md`, состояние - `STATE.md` и `docs/agent-system/HANDOFF.md`. Файл сохранён как история.

# ExecPlan: PMM backlog-run — M2/M3 вертикальный срез

*Created: 2026-08-17. Operator: Mike + orchestrator (Claude). Status: COMPLETE — прогон завершён, backlog среза живёт в PMM.*

## SSOT этого прогона

- **Manifest (единственный источник правды по прогону):** `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`
  Ссылки команд комплекта (`/Users/mikezhamba/Downloads/ai-marketplace-os`) на корневой
  `backlog-manifest.yaml` ОТМЕНЕНЫ — действуют пути этого файла.
- **Методика:** `Downloads/ai-marketplace-os/AGENTS.md` + `docs/02-wbs-catalog.md` + `docs/03-issue-templates.md`.
  Комплект остаётся методикой без git-репо; протокол сессии — AGENTS.md репозитория Proxima.
- **Jira:** проект **PMM** «Proxima M2-M3» (id 10043, company-managed, проверено 2026-08-17).
  PA — только чтение и link-цели (Relates из PMM), PA не пишется.

## Снимок решений (зафиксировано Mike 2026-08-17)

| Параметр | Значение |
|---|---|
| engineers_fte | 1 → срез (протокольное правило capacity, подтверждено) |
| known_velocity | null → без дат, только порядок спринтов |
| tax_regime | UNKNOWN до ADR спайка AIOS-FIN-001 (не «mixed») |
| legal_entities | 4+ (точный перечень — вход спайка FIN-001) |
| cogs_source | Sheets/Excel от AM при онбординге |
| marketplaces_now | [wildberries]; Ozon исключён (STUB-маркер отложенного) |
| ops_project_key | отложен до R4 (STUB-маркер) |

## Состав среза (28 issue: 25 FULL / 3 STUB)

Гейт B3 пройден: 25-40 всего / 15-25 FULL / 2-3 STUB → 28 / 25 / 3.

- **Governance эпик (AIOS-PROD-010):** charter-pointer, Glossary+KPI, реестр допущений,
  Risk Register, спайк FIN-001 (налоги → ADR), спайк PROD-004 (Build vs Buy, полный охват
  ≤3 дн), baseline velocity, refinement-каденция, DoD-чеклист, exit-критерии, onboarding
  AI-ops, ретро/sprint review каденция.
- **W1-срез эпик (AIOS-DEC-010):** SCN-001 детектор (U×CVR×AOV), SCN-005 детектор OOS,
  Client Passport v1, ₽-оценка сигналов (revenue-based v1; profit — после FIN-001),
  LLM Analyst W1 + SourceRef, Independent Reviewer (BLOCK с дня 1), Decision Memory v0,
  Telegram critical-алерты, Decision Inbox ↔ PA-38, V1 value-gate (демо сквозного сигнала).
- **Верхний уровень:** init-m2 управляющая (PROD-000) + 3 STUB-маркера отложенного
  (Ozon, ops-проект, growth-gate 2+ FTE).

## Existing-карта (PA — источник знания / живёт в PA; PMM не дублирует)

| PA | Роль | Действие в PMM |
|---|---|---|
| PA-37 | эпик Трека B — источник знания | Relates из эпика W1-среза |
| PA-38 | web-кабинет v0 — живёт в PA | link-only; BI-001 relates |
| PA-39 | аудит scenario engine — живёт в PA | link-only; AGT-001 relates |
| PA-41 | импорт scenario engine — живёт в PA | link-only; AGT-001 relates |
| PA-42, PA-40 | Трек C интервью — живёт в PA | link-only |
| PA-26 | devex — вне среза | none |

Критерий верификации: каждый PMM-эпик M2-тематики либо link на PA-предка, либо помечен
«новое, в PA отсутствовало».

### Correction 2026-08-17 (аудит): карта выше была неполной

Фаза B1 читала PA-37…PA-42 и PA-26. Задачи **PA-43…PA-48** созданы 2026-08-16 в 21:04, за сутки
до прогона, и в existing-карту не попали. Пять из них дублировали срез один-в-один.

| PA | Отношение к срезу | Действие 2026-08-17 |
|---|---|---|
| PA-43 Client Passport v1 + PDF + Auditor | дубль PMM-21 | закрыт superseded; поля → PMM-21, PDF и Auditor → PMM-4 |
| PA-47 LLM Analyst + Independent Reviewer | дубль PMM-5 + PMM-25 | закрыт superseded |
| PA-46 Verification-петля + Decision Memory | дубль PMM-26; п.4 = гейт V1 = PMM-28 | закрыт superseded; scheduler-часть → PMM-32 |
| PA-38 п.1 детерминированные сигналы | перекрытие с PMM-20, PMM-23 | остаётся в PA, граница зафиксирована комментарием; п.3 (Telegram-дайджест) отменён решением web-first |
| PA-45 волна W3 | вне W1-среза | закрыт; состав → PMM-4 |
| PA-48 волна W2 | вне W1-среза | закрыт; состав → PMM-4 |
| PA-44 источники M2 | предвосхищал спайк Build vs Buy | остаётся в PA, добавлен blocked-by PMM-14 |

Решение Mike 2026-08-17: **PMM - единственный дом M2/M3**. PA остаётся домом M1, Трека C и
инфраструктуры Трека B (PA-38, PA-39, PA-41, PA-44). Зафиксировано в `.planning/PRODUCT-VISION.md`,
раздел «Трекер».

## Preflight-факты (zhamba.atlassian.net, 2026-08-17)

- PMM company-managed; типы: Эпик/История/Задача/Подзадача/Баг; Initiative-уровня нет → label `init-m2`.
- Spike/Risk типов нет → Задача + label `spike` / `risk`.
- Компоненты: MCP-endpoint создания компонентов отсутствует → label `comp-<name>` (fallback активирован;
  если Mike создаст компоненты в UI — привяжем editJiraIssue пост-фактум).
- Версии: аналогично → label `rel-r0` (Discovery-срез).
- Приоритеты Jira: Highest/High/Medium/Low (P0→Highest, P1→High).
- Link types: Blocks / Relates доступны. Bulk-create через MCP нет → создание по одному, один батч.
- Labels `aios-run-*` / `wbs-aios-*` в Jira не существовали (проверено JQL) — чисто.

## Фазы и статусы

| Фаза | Статус |
|---|---|
| A2 living plan + manifest | DONE 2026-08-17 |
| B1 existing-карта (PA-37..42, PA-26 прочитаны) | DONE 2026-08-17 |
| B3 сводка трёх чисел (28/25/3) | DONE — гейт Mike пройден |
| C1 sample 5 issue → гейт Mike формата | DONE — «ок» 2026-08-17 |
| C2 батч 23 + связи + верификация | DONE — 28/28 created, 11 blocks + 4 Relates PMM→PA, PMM-28 spot-check OK |
| D git-ритуал + HANDOFF/TASKS + отчёт | DONE 2026-08-17 |

## Результат прогона (финал)

28 issue в PMM (PMM-1..28): 2 эпика, 8 Историй, 18 Задач; 25 FULL / 3 STUB;
приоритеты: 5 Highest, 12 High, 8 Medium, 3 Low. Ключевая карта - в manifest (Key map).
Верификация: WBS-ID уникальны (28 labels), parent-links 22/22, blocks 11/11,
Relates на PA-37/38/39/41 стоят, дублей против PA нет (existing-карта: link-only).
Откат: `labels = "aios-run-2026-08-17" ORDER BY created DESC` (удаление - только вручную).

> **Correction 2026-08-17.** Три утверждения из абзаца выше не подтвердились при проверке
> счётчиками JQL. Parent-links были 21 из 25, а не 22/22: без эпика оставались PMM-1, PMM-2,
> PMM-4, PMM-17, PMM-18. Связей 11 на 28 задач было мало: у PMM-21, PMM-26, PMM-27 их не было
> вообще. «Дублей против PA нет» неверно - их было пять (см. correction в разделе existing-карты).
> Разбор в `verification_correction` манифеста; исходные строки сохранены как есть.

## Состояние после аудита 2026-08-17

Метка правок `aios-fix-2026-08-17`, отдельная от метки прогона.

* 33 issue в PMM. Добавлены пять задач, закрывающих блокеры критического пути:
  **PMM-29** контракты signal/diagnosis/decision-record + codegen (Highest, Sprint 0);
  **PMM-30** DEC-006 поверх DEC-005 (Highest, Sprint 0);
  **PMM-31** LLM-доступ, две независимые модели, egress с VPS, бюджет токенов → ADR (Highest, Sprint 0);
  **PMM-32** daily-цикл 07:00 MSK и осознанное снятие `manual one-shot` (High, Sprint 1);
  **PMM-33** eval-инфраструктура с порогами в CI (High, Sprint 1).
* Без parent теперь только 3 issue: два эпика и управляющая PMM-1 (проверено счётчиком).
* Спринты 0/1/2 существовали только в этом файле и манифесте; проставлены метками
  `sprint-0` / `sprint-1` / `sprint-2` на 28 задачах (`can_manage_sprints: false` в Jira MCP).
* Приоритеты выровнены по критическому пути: PMM-20, PMM-21, PMM-23 → Highest; PMM-1 → High.
* Оценки не проставлялись намеренно. Размер зафиксирован только там, где он назван в тексте:
  `size-s` у трёх STUB, `timebox-3d` у двух спайков. Оценка остальных 23 - первый пункт повестки
  refinement (PMM-15), иначе замер baseline velocity (PMM-13) не на чем выполнять.
* Открытые вопросы Mike и найденные пробелы - в блоке `open_for_mike` манифеста и в отчёте
  `docs/exec-plans/active/pmm-audit-2026-08-17.md`.

Откат правок аудита: `labels = "aios-fix-2026-08-17" ORDER BY created DESC`; закрытые PA-задачи
возвращаются переходом в «К выполнению» (метка `superseded-by-pmm`).

## Sample-набор (C1)

PROD-000 (Task, управляющая) · DEC-010 (Epic W1) · AGT-001 (Story FULL, 22 секции +
LLM-чеклист) · DEL-003 (Task STUB, 7 полей) · FIN-001 (Task SPIKE FULL). После создания —
СТОП, проверка Mike глазами, только после «ок» — батч.

## Git-ритуал (фаза D, обязательный)

1. `git status --short` → вывод сохранить в отчёт прогона.
2. `git add` ТОЛЬКО явных путей: `docs/exec-plans/active/pm2-backlog-run.md`,
   `docs/exec-plans/active/pm2-backlog-run.manifest.yaml`, `docs/agent-system/HANDOFF.md`,
   `docs/agent-system/TASKS.md`.
3. Запрещено: `git add -A`, glob-пути. В дереве чужие незакоммиченные потоки (см. Dirty-tree note AGENTS.md).
4. Перед commit проверить отсутствие git lock (MILV autosync каждые 20 мин).

## Rollback прогона

JQL: `labels = "aios-run-2026-08-17" ORDER BY created DESC` — массовое удаление только
вручную в Jira, не агентом (протокол).
