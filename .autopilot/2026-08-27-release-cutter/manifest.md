# Манифест требований

Источник: `2026-08-27-brief.md`. Строку из этого списка может снять **только пользователь**.

| ID | Из брифа (дословно) | Статус | Основание | Где |
|----|---------------------|--------|-----------|-----|
| R01 | «Создай `.opencode/skills/release-cutter/SKILL.md`. Frontmatter должен быть валидным и минимальным. Имя должно совпадать с директорией» | done | T01 | spec → T01 |
| R02 | «Release Cutter — независимый критик плана»; «должен иметь право сказать: Эта задача вообще не нужна»; «любое такое решение должно быть доказано» | done | T01 | spec → T01 |
| R03 | «Release Cutter обязан» 1–10: понять результат, привязать к релизу, проверить блокер/срок/дешевле, найти 11 возможностей сокращения, сравнить, in/out scope, acceptance criteria, brief для Autopilot | done | T01 | spec → T01 |
| R04 | «Правило доказательств»: исследовать до выводов (roadmap, код, зависимости, Git-история, ADR, тесты, инциденты); Evidence/Assumption/Unknown; «Не используй ложную точность» — S/M/L | done | T01 | spec → T01 |
| R05 | «Внешний поиск и GitHub»: build-vs-buy чек-лист (лицензия, активность, maintainers, security, TCO); «External reuse research: NOT VERIFIED» без интернета | done | T01 | spec → T01 |
| R06 | Шаг 1: «релизный результат» одной фразой + user/problem/behavior/metric/deadline/constraints/non-goals | done | T01 | spec → T01 |
| R07 | Шаг 2: «пять вопросов существования» | done | T01 | spec → T01 |
| R08 | Шаг 3: 3–5 load-bearing assumptions (Claim/Fails if/Evidence/Cheapest test/Kill criterion); «Не составляй длинный абстрактный список рисков» | done | T01 | spec → T01 |
| R09 | Шаг 4: «минимум три пути» A/B/C + D REUSE/BUY; таблица оценок (user value, time to feedback, build/test/operating cost, risk, reversibility) | done | T01 | spec → T01 |
| R10 | Шаг 5: CORE/SUPPORTING/DEFER/DROP + «Для каждого DEFER указывать условие возврата» | done | T01 | spec → T01 |
| R11 | Шаг 6: «минимальный vertical slice» end-to-end; «Не предлагай горизонтальные технические слои» | done | T01 | spec → T01 |
| R12 | Шаг 7: вердикты KEEP/REUSE/SHRINK/DEFER/DROP/BLOCKED | done | T01 | spec → T01 |
| R13 | Шаг 8: handoff-status READY_AUTO/NEEDS_APPROVAL/NEEDS_INPUT/BLOCKED; условия READY_AUTO; список триггеров NEEDS_APPROVAL; «не должен молча её переписывать» | done | T01 | spec → T01 |
| R14 | «Что запрещено сокращать автоматически»: auth/authz/tenant isolation/validation/secrets/целостность/идемпотентность/миграции/rollback/логирование/observability/failure paths/тесты AC/compliance/backup | done | T01 | spec → T01 |
| R15 | «Формат результата»: отчёт Release Gate, 13 секций по шаблону; «коротким и содержательным» | done | T01 | spec → T01 |
| R16 | Batch-режим для roadmap/epic: dependency graph, критический путь, RELEASE-BLOCKING/SUPPORTING/POST-RELEASE/DROP/NEEDS-EVIDENCE, параллельность, преждевременные платформы, дублирование, Release 0/1/Later/Drop; «Один утверждённый gate для epic» | done | T01 | spec → T01 |
| R17 | «Защита от бюрократии»: 10 правил, включая «Если исходный план уже минимален и разумен, выдать KEEP / READY_AUTO» | done | T01 | spec → T01 |
| R18 | `.opencode/agents/release-critic.md`: subagent, «низкой температурой», read-only permissions, granular git read-only bash, запрет мутирующих команд, может web search + «загружать скилл release-cutter» | done | T01 | spec → T01 |
| R19 | `/release-gate`: «запускать release-critic как отдельный subtask и передавать ему $ARGUMENTS»; вход @файл; вернуть отчёт, закончить handoff-status, «Не запускать Autopilot» | done | T01 | spec → T01 |
| R20 | `/release-task` оркестрация: READY_AUTO → сохранить в docs/release-gates/, загрузить реальный autopilot, передать только раздел Autopilot handoff + перечисленные поля, «Разрешить начать реализацию автоматически»; NEEDS_APPROVAL → разница scope, одно решение, не стартовать до ответа; NEEDS_INPUT → реальный grill-me, максимум Gate→Grill→Gate, потом BLOCKED; BLOCKED → блокировка/кто снимет/следующий шаг/независимые задачи | done | T01 | spec → T01 |
| R21 | «Scope lock для Autopilot»: 10 правил; «локальный рефакторинг только когда необходим и в том же slice» | done | T01 | spec → T01 |
| R22 | AGENTS.md: «одну компактную идемпотентную секцию», «Не переписывай существующий», «Не добавляй правило… на каждое изменение одной строки» | done | T01 | spec → T01 |
| R23 | docs/release-gates/README.md: зачем, разница Grill Me/Cutter/Autopilot, когда какая команда, вердикты, handoff-status, где хранятся отчёты, Scope lock, Gate ID ссылки, exemptions; «практическим и коротким» | done | T01 | spec → T01 |
| R24 | «Сначала исследуй текущее окружение»: реальные имена скиллов, версия OpenCode, адаптация формата, «Не перезаписывай существующие скиллы», идемпотентность, «не более трёх конкретных вопросов» | done | T01 | spec → T01 |
| R25 | «Проверка реализации»: YAML frontmatter, имя=директория, description не пустой, subagent, read-only агент, $ARGUMENTS, /release-gate → release-critic, /release-task не запускает Autopilot до gate, секция AGENTS.md не продублирована, статическая проверка | done | T01 | spec → T01 |
| R26 | «Проведи dry-run на одной реальной задаче из roadmap»; ожидание SHRINK/REUSE, «Не подгоняй вердикт искусственно» | done | T02 | spec → T02 |
| R27 | Финальный отчёт: 12 пунктов, включая `git diff --stat` и содержательный diff; «Не делай commit и не делай push» | done | T02 | spec → T02 |
| R28i | *(подразумевается)* «Не изменяй продуктовый код проекта» — только конфигурация OpenCode, инструкции агентов, команды, скиллы, служебная документация процесса | done | T01 | spec → T01 |
| G01 | Дополнение 2026-08-27: «Заменить briefmaker» — release-critic заменяет briefmaker в пайплайне major/critical | done | T01 | spec → T01 |
| G02 | Дополнение 2026-08-27: «Перенаправить, файл оставить» — briefmaker.md не трогать; AGENTS.md + ORCHESTRATION.md + README.md role-map перенаправить | done | T01 | spec → T01 |
| G03 | Дополнение 2026-08-27: «Двойной формат» — Release Gate отчёт + строка DISCOVERY_STATUS для Orca-парсера | done | T01 | spec → T01 |
| G04 | Дополнение 2026-08-27: «Жёсткие ограничения» — DECISIONS.md/ADR/фазовые контракты M1 неприкосновенны; пересмотр только NEEDS_APPROVAL | done | T01 | spec → T01 |
| G05 | Дополнение 2026-08-27: «Да, read-only MCP» — jira-atlassian read-only для release-critic; вход PA-XX валиден | done | T01 | spec → T01 |
| G06 | Дополнение 2026-08-27: план утверждён; ASSUMED одобрены (языки; Gate ID RG-<дата>-<slug>; dry-run PMM-7 DRY-RUN; briefmaker остаётся в Task tool) | done | T01 | spec → T01 |
