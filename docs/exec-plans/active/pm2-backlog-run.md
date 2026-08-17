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
