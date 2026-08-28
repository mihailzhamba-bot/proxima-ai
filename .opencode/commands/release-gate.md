---
description: Release Gate — read-only аудит задачи, epic или roadmap через субагента release-critic. Возвращает отчёт Release Gate (вердикт, handoff-status, DISCOVERY_STATUS) и никогда не запускает Autopilot.
agent: release-critic
subtask: true
---

# /release-gate

Аргументы: `$ARGUMENTS` — задача / epic / roadmap / ключ Jira (`PA-XX`, `PMM-XX`) / `@файл` / свободный текст. Примеры:

- `/release-gate ROADMAP-42 — добавить ежедневный импорт Meta Ads`
- `/release-gate @docs/ROADMAP.md`
- `/release-gate PA-36`

Порядок обязательный:

1. Получи `$ARGUMENTS`. Если это ключ Jira `PA-XX`/`PMM-XX` — прочитай задачу через jira-atlassian MCP (только чтение, `getJiraIssue`). Входы `@файл` и свободный текст равнозначны.
2. Загрузи скилл `release-cutter` через skill tool и работай строго по нему.
3. Исследуй репозиторий и связанные документы read-only: roadmap, PRD, код, конфигурацию, зависимости, Git-историю, ADR, открытые задачи, тесты.
4. Не изменяй файлы. Аудит — read-only.
5. Верни полный отчёт Release Gate по шаблону скилла: шапка `## Gate` (Gate ID, Target release, Source roadmap item, Verdict, Handoff status, Confidence, DISCOVERY_STATUS) + 13 секций.
6. Закончи отчёт handoff-status и строкой `DISCOVERY_STATUS: ...` (READY_AUTO→READY; DROP/DEFER→NOT_NEEDED; NEEDS_APPROVAL/NEEDS_INPUT/BLOCKED→напрямую).

Жёсткое правило: НЕ запускай Autopilot. Эта команда — только аудит и отчёт. Запуск реализации — `/release-task`.
