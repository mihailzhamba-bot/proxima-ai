# AGENTS.md - PROXIMA AI

Единый контракт для coding-агентов (Claude Code / Codex / opencode). Claude Code читает этот файл через адаптер `CLAUDE.md` (`@AGENTS.md`).

<!-- bmad:context -->
<!-- Verified 2026-08-30 against fe810f6. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## PROXIMA AI

Приватная платформа Proxima для WB-кабинетов: сбор данных кабинета по WB API → PostgreSQL → утренняя сводка с отклонениями в веб-морде. Лестница M-00..M-05, цель 30.09 = M-03. TypeScript collector (`services/collector`), Python control-plane (`services/control-plane`, uv 3.14), Next.js webapp (`services/webapp`), PostgreSQL 16 в docker на одном VPS. Текущее состояние - `STATE.md`, решения - `DECISIONS.md`, факты инвентаризации - `docs/state/`, история M1 - `docs/archive/planning-m1/` (не требования).

## Policy

- Сервер `proxima` (135.106.186.210) - только чтение. Деплой, рестарт, правка на сервере - только после явного «деплой» от Mike в чате; план отката записан до деплоя.
- Значения токенов, паролей, ключей никуда не выводить - ни в лог, ни в отчёт, ни в коммит; только имя переменной или файла. Токены живут на VPS в `/etc/proxima-ai/secrets/` (0600); вызовы WB API - с сервера через `ssh proxima 'curl -H "Authorization: $(cat …)"'`.
- WB API только READ: split-токен с битом read-only на категорию; новый эндпоинт - сначала в allowlist `tools/verify_business_signal.py`. Analytics-токен на сервере пока read-write (PA-13) - только read-эндпоинты отчётов.
- Тесты - на фикстурах `fixtures/wb-api/` (gitignored, копия на VPS в `~/signal-inputs/fixtures/wb-api/`); живой WB API - только когда без него никак, ответ сразу в фикстуру.
- Каждая запись в БД помечена `run_id`, идемпотентна и удаляется по `run_id` целиком - требование к любому новому писателю.
- В Jira (PA, PMM) пишем только после approve таблиц синхронизации Mike (PRD §10, D17/D24: истина по задачам - файлы репозитория, направление одно, репо → Jira); задачи не удалять никогда. Ворота 2 пройдены 30.08.2026 (`DECISIONS.md`), запрета на запись больше нет - остался порядок approve.
- Один write-capable агент на рабочее дерево; параллельно - только read-only исследование. Стейджить только свои файлы: `git add <files>`, не `git add -A` / `git add .`.
- Не редактировать `services/collector/src/contracts/*.ts` - менять `contracts/*.schema.json` и `make codegen`; ручные правки тихо перезаписываются.
- Миграции `db/migrations/NNN_*.sql` не править и не переименовывать - только новая `NNN+1_<snake>.sql`, additive-only, `BEGIN…COMMIT`, self-checksum (`tools/verify_migrations.py`).
- Заморожено до октября: auth-зона webapp (`src/lib/auth*`, `src/app/api/auth/`, `src/app/login/`) и verbatim-дерево `services/control-plane/src/proxima/`. `db/`, `infra/`, `Makefile`, `src/lib/db/` открыты для единиц M-01.
- Чужой код - только через `provenance/import-inventory.json` + attestation (`make provenance`). Гейт байт-точен, но покрывает **только** рантайм-импорты в `services/collector/src/imported`; установленные библиотеки инструментов (BMAD, TEA, BAD) в рантайм не входят и записываются разделом `vendored_trees` того же файла со ссылкой на манифест источника; Torgstat и браузерная автоматизация в runtime запрещены (`tools/verify_runtime_boundary.py`).

## Where things are

- Начало сессии: `STATE.md` → `DECISIONS.md` → `docs/state/GATE-1.md`; handoff агентов - `docs/agent-system/HANDOFF.md`.
- Утренняя сводка встраивается в `services/webapp/src/app/(app)/brief/page.tsx` через `getBrief()` из `src/lib/fixtures/brief.ts`; Postgres-провайдер лежит в ветке `origin/ai/pa-50`.
- Незамерженный код по ступеням (детектор нормы, promotion дневного ряда, контракты сигнала) - `docs/state/MIGRATION-GAPS.md` §4; бэклог Jira с вердиктами - `docs/state/BACKLOG-REVIEW.md`.
- База регрессии до автотестов - `docs/state/WORKS-TODAY.md`: прогонять целиком перед релизом.
- Заметки автопилотов (webapp T2, release-gate T1, diagnosis PMM-5) - `docs/agent-system/autopilot-notes/`.

## Running and verifying

- Полный гейт - `make verify` (~40 с; сетевой: `npm ci`, `uv sync --locked`). Проверять строку `pg-roundtrip: PASS` - без Homebrew PG16 (`/opt/homebrew/opt/postgresql@16`) шаг даёт `SKIP` с exit 0 и миграции не проверены. При длинном `TMPDIR` - `TMPDIR=/tmp make verify`.
- `PUPPETEER_SKIP_DOWNLOAD=1` перед `npm ci` / `make verify`, иначе качается Chromium.
- Python только `uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests tools/tests`; `uv run pytest` из корня падает (`Failed to spawn: pytest`).
- Один vitest-файл: `npm --workspace @proxima/webapp exec -- vitest run src/tests/<file>`; `npx vitest … --root services/webapp` из корня даёт `vitest: command not found`.
- `npm test`, `npm run typecheck`, `scripts/agent/verify` проверяют только collector; webapp - `npm --workspace @proxima/webapp test | run typecheck | run lint` (в `make verify` входят test и typecheck, lint - нет).
- `next build` переписывает tracked `services/webapp/next-env.d.ts` - после сборки `git checkout -- services/webapp/next-env.d.ts`.
- `.githooks/pre-commit` не активен, пока не выполнено `git config core.hooksPath .githooks`.

## Conventions that differ from defaults

- Коммиты - английский с conventional-префиксом (`feat(webapp): …`); документация и общение - русский; идентификаторы кода - английский.
- Collector тестируется `node:test` через `tsx` (`services/collector/tests/`), webapp - vitest (`services/webapp/src/tests/`); jest нигде.
- Демо-данные webapp только из `src/lib/fixtures/` с префиксом `fixture-`; плашка unreleased на всех экранах (DEC-006).

## Known pitfalls

- Переименование миграции без правки `INSERT INTO schema_migrations` ломает checksum - три коммита 29.08 (`fa57aa9`, `31cf85f`, `ad89513`).
- Codex падает на голом `enabled = false` в `[mcp_servers.X]` `.codex/config.toml` (27.08, PA-39/PA-41/PMM-12); канарейка - `codex mcp list` в `scripts/agent/verify`.
- `.openhands/hooks/verify-gate.sh` с `646ecb1` (31.08) `DATABASE_URI` не требует: `.env.task` подхватывается, если есть, гейт = только `make verify`. К разговорам, запущенным через `tools/orchestrator/` (`bad_dev_story.sh`, воркеры дирижёра), `.openhands/hooks.json` не применяется вовсе (`hook_config = null`) - красный `make verify` в песочнице ничего не остановит, гейт гоняется снаружи и в CI.
- На VPS claudette (песочница OpenHands под `openhands-agent` и сессии Claude Code под `proxima-admin`) нет PG16 `initdb`: `pg-roundtrip: SKIP`, `*.db.test.ts` и матрица политик выполняются только в CI на PR. Db-тесты писать строго по образцу `services/collector/tests/collect.db.test.ts`; с миграции 013 cleanup сначала снимает рёбра `collector_run_inputs` (`input_run_id` - `ON DELETE RESTRICT`, AD-3) и только потом удаляет прогоны, а `data_status_current` отдаёт строки только с GUC `proxima.tenant_id`, даже под owner-ролью (02.09.2026, PR #51).
- `make architecture` требует `chrome-headless-shell` версии из lock-файла в `~/.cache/puppeteer`; `PUPPETEER_SKIP_DOWNLOAD=1` его не ставит, а сетевая загрузка с VPS падает (`All providers failed`). Рабочий способ под `proxima-admin` - скопировать каталог `chrome-headless-shell/linux-<ver>` из кэша `openhands-agent`, где он уже есть (02.09.2026).
- `tools/orchestrator/bad_dev_story.sh` (ветка `feat/bmad-bad`, PR #47): `--run-id` без точек (`story-1-6`), `--branch` только `feat|fix|docs|chore/*`, `--source-dir` - чекаут с каталогом `.git` (linked worktree отвергается), результат - `refs/openhands/<run-id>/<attempt>/head` в source-dir. Story 1.6 прошла dispatch → PR за 15 мин (02.09.2026).

<!-- /bmad:context -->

## Mandatory startup sequence (all agents)

Before ANY non-trivial task in this repo:

1. Read this file.
2. Classify the task: trivial (<30 min) / medium / major / critical.
3. Read routing targets relevant to the task class (table below).
4. Read `docs/agent-system/HANDOFF.md` - current state and exact next action.
5. Read `docs/agent-system/TASKS.md` - active task snapshot.
6. Check `docs/exec-plans/active/` - living plan for the active task, if any.
7. Check `git status` + last relevant commits (uncommitted work = someone's unfinished thread; stage only files you changed).
8. Only then start working.

Do not ask the user "where did we stop". Recover state from repository files first; ask only if critical ambiguity remains after recovery.

## Что это за проект

См. блок `bmad:context` выше (ориентация) и `DECISIONS.md` D2: роадмап M1 заменён лестницей M-00..M-05 (30.08.2026). Описание M1 - `docs/archive/planning-m1/`, история.

**Языки:** коммуникация и документация - русский; коммиты - английский; идентификаторы кода - английский.

## Карта контекста (читай перед работой)

| Что | Где |
|---|---|
| Текущее состояние, открытые вопросы, с чего начинать сессию | `STATE.md` (корень) |
| **Действующие требования: что строим** | `_bmad-output/planning-artifacts/prds/prd-PROXIMA-AI-2026-08-28/prd.md` (PRD, зонт лестницы) |
| **Канонический контракт сентября** (CAP-1..CAP-8) | `_bmad-output/specs/spec-wb-morning-brief/SPEC.md` + `glossary.md` |
| **Архитектурные инварианты AD-1..AD-18** | `_bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md` |
| **Нарезка на эпики и истории; статусы** | `_bmad-output/planning-artifacts/epics.md`; `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| Гейт готовности нарезки к реализации | `_bmad-output/planning-artifacts/implementation-readiness.md` |
| Предложения по правкам нарезки (OLD → NEW) | `_bmad-output/planning-artifacts/sprint-change-proposal-*.md` |
| Кандидаты ступеней M-06+ | `_bmad-output/planning-artifacts/epics-candidates-m06.md` |
| Эталоны независимого пересчёта (зона аналитика) | `verification/golden/` (создаётся Story 6.1) |
| Управление: DoD-чеклист, реестры рисков и допущений | `docs/governance/` (реестры M2-среза - архив, действующие - PRD §14 и §9) |
| **Вход для нового человека-разработчика** | `docs/operations/dev-onboarding.md` |
| Выдача и отзыв доступов человеку | `docs/operations/access-provisioning.md` |
| Стандарт логов, статусов и алертов | `docs/operations/observability.md` |
| Что делать при сбое, расхождении цифр, утечке токена | `docs/operations/incident-runbook.md` |
| **Порядок первого релиза M-01 на сервере, с планом отката** | `docs/operations/release-m01.md` |
| **Словарь данных: таблицы, кто пишет, кто читает** | `docs/state/DATA-DICTIONARY.md` |
| Прочие операционные инструкции | `docs/operations/business-signal-runbook.md`, `agent-toolset.md` |
| Аудиты импортированного кода | `docs/audits/` |
| Решения D1-D22: лестница M-00..M-05 вместо M1, среды, конвейер, Ворота 1 (30.08.2026) | `DECISIONS.md` (корень) |
| Факты инвентаризации: сервер, веб-морда, WB API, миграция, база регрессии | `docs/state/*.md` |
| Продуктовое видение M1 - **архив снятой рамки** (D2 30.08 заменил M1 лестницей; действующее видение - PRD §1) | `docs/archive/planning-m1/PRODUCT-VISION.md` |
| M1 roadmap, фазы, гейты (архив, заменён лестницей M-00..M-05) | `docs/archive/planning-m1/ROADMAP.md` |
| Требования M1 (архив) | `docs/archive/planning-m1/REQUIREMENTS.md` |
| Состояние M1 на 25-29.08 (архив) | `docs/archive/planning-m1/STATE.md` |
| Мировой ресёрч конкурентов и паттернов | `docs/archive/planning-m1/research/GLOBAL-LANDSCAPE-2026-08-16.md` |
| Архитектурные карты (Mermaid) | `docs/architecture/*.mmd` |
| Architecture Decision Records | `docs/adr/*.md` (ADR-0001+; краткие записи-указатели в `docs/agent-system/DECISIONS.md`) |
| Дизайн-система платформы (UI-токены, spec-before-UI) | `DESIGN.md` (Google DESIGN.md spec; валидация: `npx @google/design.md lint DESIGN.md`) |
| Трекер задач | Jira проект PA (zhamba.atlassian.net) |
| Current state + exact next action (agent handoff) | `docs/agent-system/HANDOFF.md` |
| Active task snapshot | `docs/agent-system/TASKS.md` |
| Agent-system role map (which doc fills which role) | `docs/agent-system/README.md` |
| Роль второго человека (Владислав: независимый пересчёт цепочки, эталоны и гейт `shadow`, право блокировать релиз, сверка с кабинетом, приёмка по AC) | `docs/agent-system/roles/analyst-vladislav.md` |
| Rules: MUST / SHOULD / MAY | `docs/agent-system/RULES.md` |
| Verification stack + rubrics | `docs/agent-system/EVALS.md` + `scripts/agent/verify` |
| Stable facts, pitfalls, preferences | `docs/agent-system/MEMORY.md` |
| Past engineering decisions (do not reopen) | `docs/agent-system/DECISIONS.md` |
| Tools, access, dangerous operations | `docs/agent-system/TOOLS.md` |
| SSH к VPS не работает - диагностика | `infra/ssh-doctor` (read-only), раздел «SSH-доступ к VPS» ниже |
| Big-task living plans | `docs/exec-plans/active/<task-id>.md` |
| Reviewer subagent (opencode / Claude Code / Codex) | `.opencode/agents/reviewer.md`, `.claude/agents/reviewer.md`, `.codex/agents/reviewer.toml` |
| Release Gate (gate-отчёты, Scope lock) | `docs/release-gates/` + `.opencode/agents/release-critic.md` |

## Verify-контракт (главная команда)

```bash
make verify
```

Единый exit-code: install + codegen + typecheck + test (TS + pytest) + contracts + migrations + provenance + architecture render + boundary + secrets scan + vps contract + business-signal. Каждый vertical slice заканчивается clean implementation commit с прошедшим `make verify`. Критические фазы (3, 4, 7) требуют independent cross-model review 0 blocker / 0 warning.

## Стек и версии toolchain

| Компонент | Версия | Где |
|---|---|---|
| Node.js | >=22 <23 | collector/data-plane, TypeScript |
| Python | 3.14 (через uv, НЕ системный 3.9) | control-plane, tools |
| uv | >=0.11 | управление Python-окружением |
| PostgreSQL | 16 | VPS compose; локально - туннель |
| Mermaid CLI | 11.16.0 (devDependency) | рендер архитектуры |

Локального Docker нет - решение Mike 2026-08-16: dev-цикл БД идёт через SSH-туннель на staging VPS.

## Dev-доступ к PostgreSQL (VPS через туннель)

```bash
# 1. Туннель (держать открытым в отдельном терминале)
ssh -N proxima-db
# полная форма без алиаса:
# ssh -N -L 5433:localhost:5432 proxima-admin@135.106.186.210

# 2. Экспорт URI (credentials НЕ коммитить; реальные значения на VPS:
#    /etc/proxima-ai/secrets/ и path-only .env - см. README)
export DATABASE_URI="postgresql://<user>:<password>@localhost:5433/<db>"
```

Postgres MCP (restricted, read-only) использует ту же `DATABASE_URI`.

## SSH-доступ к VPS

Алиасы в `~/.ssh/config` (машина Mike): `proxima` - shell, `proxima-db` - туннель к Postgres.
Канонический admin-ключ: `~/.ssh/id_ed25519_proxima_selectel_20260813`
(`SHA256:CG+iddsvx2qxzSjJXC2v8nztu5LxkOb73ekmEYDNTXM`), защищён passphrase из macOS Keychain.

Три вещи, без которых подключение не работает:

- `IdentitiesOnly yes` - на сервере `MaxAuthTries 3`, перебор лишних ключей рвёт сессию до нужного;
- `UseKeychain yes` - без неё ssh не берёт passphrase из Keychain и падает в `Permission denied (publickey)`;
- пользователь **только** `proxima-admin`. Root заблокирован намеренно (`PermitRootLogin no`,
  `AllowUsers proxima-admin`, `passwd --lock root`) - `ssh root@135.106.186.210` не заработает никогда.

Диагностика одной командой: `bash infra/ssh-doctor` (read-only, проверяет маршрут/VPN, TCP/22,
host key, агент, реальный вход и туннель, и печатает следующий шаг).

## MCP-серверы проекта

`.mcp.json` (Claude Code), `.codex/config.toml` (Codex), `opencode.json` (opencode) держат только `jira-atlassian` (в `.codex/config.toml` открыты три read-глагола; запись - после approve таблиц Mike, D17/D24) и `node_repl` (`tools/node_repl_server.js` отсутствует - см. `docs/state/MIGRATION-GAPS.md` §5). context7 и Postgres MCP - user-level конфиги, не проектные; секреты в конфиги и Git не попадают.

## Жёсткие запреты (fail-closed)

1. **Никаких секретов** в Git, конфигах, логах, алертах, промптах. Токены живут на VPS (`/etc/proxima-ai/secrets/`, mode 0600). `.env` - вне Git.
2. **WB WRITE запрещён.** Только READ-endpoints. Любая мутирующая операция - архитектурное нарушение.
3. **Torgstat live session automation запрещена.** Адаптер structural-unwired; runtime-флаг не может его включить.
4. **Sibling-worktrees не мутировать:** `Опрос-v2.2` (baseline `9cca25d1`) и `torgstat-collector` (tag `baseline-lock`, rescue commit `0fba181` 2026-08-16; ETL work rescued). Импорт - только по allowlist с SHA-256.
5. **Не выдумывать данные.** Никаких фиктивных cabinet ID, SKU, цен, порогов - в тестах использовать structural fixtures с обезличенными значениями.
6. **LLM не считает метрики** (для M2-кода): цифры - детерминированный код; каждый факт со SourceRef; reviewer BLOCK'ает unsupported claims.
7. **Destructive ops** (`rm -rf`, `git push --force`, `drop table`, `reset --hard`) - только с явного подтверждения Mike.

## Конвенции кода

- TypeScript collector: `services/collector` (npm workspace `@proxima/collector`); тесты `services/collector/tests`
- Python control-plane: `services/control-plane` (uv project); тесты `services/control-plane/tests` + `tools/tests`
- Схемы контрактов: `contracts/*.schema.json` (канонические); TS-типы генерируются `make codegen` в `services/collector/src/contracts/` - не редактировать руками, перегенерировать
- Миграции: ordered immutable, additive-only (решение B6); ledger в `db/`
- Коммиты: атомарные, описательные (`fix: WB diagnostic YoY margin calc`, не `update`)

## Рабочий ритм

- Задачи в Jira PA; эпики: PA-36 (Трек A - M1), PA-37 (Трек B - value/сценарии), PA-35 (Трек C - discovery), PA-34 (Трек D - заморожен до V3)
- Перед нетривиальной задачей - прочитать `STATE.md`, `DECISIONS.md` и `docs/state/`; M1 - история в `docs/archive/planning-m1/`
- Weekly продуктовая сверка с Mike по трекам (решение №49)

## Working contract (English summary of the binding rules)

- Sequence: understand → plan → execute → verify → document. No state skips; INBOX → CODE → DONE is forbidden.
- **One main active task per repo.** A new main task starts only when the previous one is DONE, BLOCKED, or explicitly re-prioritized by Mike. New ideas go to the Jira PA/PMM backlog (writes only after Mike approves the sync tables, see PRD §10 and D17/D24), not into active work.
- Every number needs a source and a date. Unknown → `UNKNOWN`. Never invent metrics, prices, statuses, cabinet IDs, SKU.
- Important knowledge lands in files (routing table above), not in chat memory.
- Fail closed: verification failed → work is NOT done. Fix, or mark BLOCKED with reason + handoff in `docs/agent-system/HANDOFF.md`.
- Red CI on a worker's story PR: the orchestrator may fix the test harness only (test files, fixtures, cleanup order, DSN/GUC plumbing) and says so in the report; job code and SQL stay untouched - diagnosis and report to Mike, or a fix round to the worker after an explicit go (2026-09-02, story 1.6).
- Destructive/irreversible actions (production data, force push, secrets rotation, deploys, infra deletion) require explicit Mike approval (see «Жёсткие запреты»).
- Parallel agents only for independent work; reviewer does not blindly trust the worker.
- Repeated mistake → build a guardrail (rule / test / verify step / doc), not just an apology.

## Delegation protocol (orchestration)

The main agent in each tool (opencode `build`, Claude Code main session, Codex `default`/`worker`) is the orchestrator; it decides which subagents a task needs. Scale effort to the task class from the startup sequence:

| Class | Orchestration |
|---|---|
| trivial | none - solve inline, no subagents |
| medium | 1-2 read-only explore subagents in parallel for research; implement inline |
| major | parallel explore + architecture review (plan/explore) before edits; implement; `make verify`; then `reviewer` |
| critical (phases 3, 4, 7) | as major, plus independent cross-model review: run `reviewer` under a different model family than the implementer; gate 0 blockers / 0 warnings |

Every subagent task description must state: objective, file/scope boundaries, expected output format, and what NOT to do. Vague briefs duplicate work or leave gaps.

Parallelism: only read-only research runs in parallel. Write-capable agents never run simultaneously on the same tree; sequence writes.

Reviewer (`reviewer`): read-only, never fixes, never trusts implementer summaries - verdict format and gates are defined in the agent files (see routing table) and `docs/agent-system/EVALS.md`.

## Orca coordinator protocol (supervised orchestration)

Полный playbook: `docs/agent-system/ORCHESTRATION.md`. Краткий контракт здесь.

Оркестратор (Orca coordinator) - тонкий. Он НЕ делает доменную работу сам (не гриллит, не кодит, не ревьюит). Его задачи, исчерпывающе:

1. Intake и классификация (trivial / medium / major / critical - таблица выше)
2. Dispatch: `release-critic` (Release Gate через `/release-gate`) для major/critical → worktree + supervised worker
3. Ретрансляция вопросов: worker/release-critic `ask` → decision gate для Mike (оркестратор не генерирует вопросы, только маршрутизирует)
4. Надзор: `check --wait` на `worker_done` / `escalation` (никакого sleep-polling; молчание воркера ≠ смерть воркера)
5. Verify-маршрутизация: `make verify`, `reviewer`, cross-model review для critical
6. Гейты: merge / deploy / irreversible - только явный approve Mike
7. Состояние: `docs/agent-system/HANDOFF.md` / `TASKS.md` / provenance обновляются на каждом переходе

### Quality pipeline (major/critical)

```
INTAKE → ORCHESTRATOR: классификация
  → RELEASE-CRITIC (.opencode/agents/release-critic.md + /release-gate): research репо+Jira
    → отчёт Release Gate (вердикт + handoff-status + DISCOVERY_STATUS-строка;
    решения к Mike только через оркестраторский gate)
  → [GATE: gate утверждён Mike]
  → WORKTREE + WORKER: codex (код) | opencode (доки/аналитика)
    воркер работает под autopilot semi; brief = контракт
  → [GATE: worker_done] → make verify (+ reviewer; cross-model для critical)
  → [GATE: merge - Mike] → CLOSE: HANDOFF/TASKS/provenance
```

Правила:

- Trivial - мимо пайплайна, inline. Medium - короткий brief (QUICK), autopilot опционален.
- Воркер не стартует в autopilot без закрытого brief (DISCOVERY_STATUS: READY).
- Один write-capable воркер на дерево; research читается параллельно.
- Автоматизации по расписанию (утро/вечер) делают только статус/verify/doc-хвосты;
  grill и autopilot - интерактивные фазы, требуют Mike в контуре.
- Full handoff (без надзора) - отдельный режим, только по явному запросу Mike.

<!-- release-gate:start -->
## Release Gate

Major/critical work passes a Release Gate before Autopilot starts implementation. The gate is run by the read-only subagent `release-critic` (`.opencode/agents/release-critic.md`) following the `release-cutter` skill (`.opencode/skills/release-cutter/SKILL.md`).

- `/release-gate <task>` - audit only: returns a Release Gate report (verdict KEEP / REUSE / SHRINK / DEFER / DROP / BLOCKED, handoff-status, DISCOVERY_STATUS line). Never starts Autopilot. Inputs: task text, epic, roadmap, Jira key (`PA-XX`/`PMM-XX`, pulled read-only via Jira MCP), `@file`.
- `/release-task <task>` - orchestration: Release Gate → handle handoff-status (grill via `grill-me` when NEEDS_INPUT, max one Gate→Grill→Gate cycle) → approved Scope lock → restricted Autopilot brief (section 12 only).

Mandatory for major/critical tasks and new epics; one approved gate per epic covers child tasks while they stay inside its Scope lock. Exempt (no gate): typo fixes, formatting, test-only changes, narrow bugfixes that change no behavior/contracts/architecture/data/dependencies/security/scope. Do not run a full gate on every technical sub-step - if the plan is already minimal, the critic returns KEEP / READY_AUTO.

Approved gate reports live in `docs/release-gates/<YYYY-MM-DD>-<slug>.md` with Gate ID `RG-<YYYYMMDD>-<slug>`; child tasks reference the Gate ID. `docs/agent-system/DECISIONS.md`, `docs/adr/*` and approved M1 phase contracts are inviolable for the critic: revisiting them requires handoff-status NEEDS_APPROVAL with an explicit reference. See `docs/release-gates/README.md`.
<!-- release-gate:end -->

## Definition of Done

Done = implemented + `scripts/agent/verify` passes (structural + typecheck + TS tests + pytest) + `make verify` green where the task touches code + no known regressions + review performed (independent cross-model review 0 blocker / 0 warning for critical phases 3, 4, 7) + routing-table docs updated if needed + `docs/agent-system/TASKS.md` / `HANDOFF.md` / ExecPlan updated.

<!-- autopilot:start -->
Заметки автопилотов (PMM-5 diagnosis, PA-49 webapp T2, release-cutter T1) перенесены 30.08.2026 в `docs/agent-system/autopilot-notes/`. Актуальные правила - в блоке `bmad:context` выше.

## Product contracts v1 (PMM-29, 2026-08-29)

- Реализованы три канонические JSON Schema Draft 2020-12 в `contracts/`: `signal`, `diagnosis`, `decision-record`; примеры включают позитивные и `-bad-` негативные fixtures.
- `tools/verify_contracts.py` проверяет все схемы через glob, валидные examples и негативные `-bad-` examples с указанием поля; также проверяет positional `diagnosis.source_refs`.
- `make codegen` генерирует TS-типы с `AUTO-GENERATED` banner; Ajv contract tests покрывают positive/negative cases для всех трёх схем.
- Атомарные implementation commits: `f0fbc70`, `17c2d51`, `b20e2e9`. На момент записи `make verify` проходит.
- Приняты в `feat/m03-story-2.1` (коммиты `5f6484b`, `1911033`); по ревью D14 деньги переведены в строки с двумя знаками (AD-10): `signal.rub_assessment.value_rub` и `decision-record.$defs.metric.value` → `{"type":"string","pattern":"^-?[0-9]+\\.[0-9]{2}$"}`.
<!-- autopilot:end -->
