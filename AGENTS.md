# AGENTS.md - PROXIMA AI

Единый контракт для coding-агентов (Claude Code / Codex / opencode). Claude Code читает этот файл через адаптер `CLAUDE.md` (`@AGENTS.md`).

## Mandatory startup sequence (all agents)

Before ANY non-trivial task in this repo:

1. Read this file.
2. Classify the task: trivial (<30 min) / medium / major / critical.
3. Read routing targets relevant to the task class (table below).
4. Read `docs/agent-system/HANDOFF.md` - current state and exact next action.
5. Read `docs/agent-system/TASKS.md` - active task snapshot.
6. Check `docs/exec-plans/active/` - living plan for the active task, if any.
7. Check `git status` + last relevant commits (uncommitted work = someone's unfinished thread; see "Dirty-tree note" below).
8. Only then start working.

Do not ask the user "where did we stop". Recover state from repository files first; ask only if critical ambiguity remains after recovery.

## Что это за проект

Приватная data-платформа Proxima для WB-кабинетов. M1 = production-ready read-only data foundation одного пилотного кабинета (Bogatova Belle Robe): официальный WB-интент -> иммутабельные артефакты с SHA-256 -> нормализация в PostgreSQL -> атомарные доменные релизы. Продуктовый слой (M2 AI Daily Manager, M3 SaaS) описан в `.planning/PRODUCT-VISION.md`.

**Языки:** коммуникация и документация - русский; идентификаторы кода (переменные, функции, таблицы, поля) - английский.

## Карта контекста (читай перед работой)

| Что | Где |
|---|---|
| Продуктовое видение, треки A/B/C/D, решения Mike | `.planning/PRODUCT-VISION.md` |
| M1 roadmap, фазы, гейты | `.planning/ROADMAP.md` |
| Требования M1 (ARCH/SRC/DATA/UI/OPS/PROC) | `.planning/REQUIREMENTS.md` |
| Текущее состояние, открытые решения, блокеры | `.planning/STATE.md` |
| Мировой ресёрч конкурентов и паттернов | `.planning/research/GLOBAL-LANDSCAPE-2026-08-16.md` |
| Архитектурные карты (Mermaid) | `docs/architecture/*.mmd` |
| Architecture Decision Records | `docs/adr/*.md` (ADR-0001+; краткие записи-указатели в `docs/agent-system/DECISIONS.md`) |
| Дизайн-система платформы (UI-токены, spec-before-UI) | `DESIGN.md` (Google DESIGN.md spec; валидация: `npx @google/design.md lint DESIGN.md`) |
| Трекер задач | Jira проект PA (zhamba.atlassian.net) |
| Current state + exact next action (agent handoff) | `docs/agent-system/HANDOFF.md` |
| Active task snapshot | `docs/agent-system/TASKS.md` |
| Agent-system role map (which doc fills which role) | `docs/agent-system/README.md` |
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
| Node.js | >=22 <23 (локально 22.22.x) | collector/data-plane, TypeScript |
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

Определены в `.mcp.json` (Claude Code), `.codex/config.toml` (Codex) и `opencode.json` (opencode):

- **context7** - актуальные доки библиотек (FastAPI, pg16, TS) против галлюцинаций API
- **postgres** - Postgres MCP Pro в restricted-режиме; подключается через `DATABASE_URI` из окружения; секреты никогда не попадают в конфиги и Git

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
- Перед нетривиальной задачей - прочитать соотв. фазу в `.planning/ROADMAP.md` и CONTEXT фазы в `.planning/phases/`
- Weekly продуктовая сверка с Mike по трекам (решение №49)

## Working contract (English summary of the binding rules)

- Sequence: understand → plan → execute → verify → document. No state skips; INBOX → CODE → DONE is forbidden.
- **One main active task per repo.** A new main task starts only when the previous one is DONE, BLOCKED, or explicitly re-prioritized by Mike. New ideas go to Jira PA backlog / `_ai/INBOX.md`, not into active work.
- Every number needs a source and a date. Unknown → `UNKNOWN`. Never invent metrics, prices, statuses, cabinet IDs, SKU.
- Important knowledge lands in files (routing table above), not in chat memory.
- Fail closed: verification failed → work is NOT done. Fix, or mark BLOCKED with reason + handoff in `docs/agent-system/HANDOFF.md`.
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

## Dirty-tree note

As of 2026-08-16 the working tree carries pre-existing uncommitted changes (Makefile, README.md, package.json, package-lock.json, `.planning/STATE.md`, `tools/verify_runtime_boundary.py`, untracked `.mcp.json`, `opencode.json`, `.codex/`, planning docs). They belong to other threads. Do not revert, stage blindly (`git add -A` is forbidden) or commit them together with your work. Stage only files you actually changed.

## Definition of Done

Done = implemented + `scripts/agent/verify` passes (structural + typecheck + TS tests + pytest) + `make verify` green where the task touches code + no known regressions + review performed (independent cross-model review 0 blocker / 0 warning for critical phases 3, 4, 7) + routing-table docs updated if needed + `docs/agent-system/TASKS.md` / `HANDOFF.md` / ExecPlan updated.

<!-- autopilot:start -->
## Control-plane: LLM-диагноз (PMM-5, прогон сдан)

Построен слой LLM-диагноза сигналов WB в `services/control-plane` (пакет `proxima_control_plane.diagnosis`): сигнал (payload + context_extracts + source_refs) → промпт → LLM-клиент (mock по умолчанию) → диагноз по JSON-Schema с детерминированной проверкой, что все числа и source_refs взяты из входа → батч-артефакт + JSONL-аудит. Для агентов, дорабатывающих diagnosis (далее по плану: реальный LLM-провайдер и eval-пайплайн). Срез M2/M3 ведётся в Jira-проекте PMM.

## Команды

| Команда | Что делает |
|---------|------------|
| `make verify` | Полный verify-гейт репо (канонический, fail-closed) |
| `scripts/agent/verify` | Быстрый структурный subset для агента |

Тесты diagnosis (голый `uv run pytest` от корня НЕ работает):
```bash
uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests -q
```

CLI batch run (`diagnosis.toml` ищется от cwd вверх, не найден - дефолты):
```bash
uv run --python 3.14 --project services/control-plane python -m proxima_control_plane.diagnosis run --input signals.json --output diagnoses.json [--config diagnosis.toml]
```

CLI eval (печатает pass-rate; полный гейт 0.80 - в `eval_runner.py`):
```bash
uv run --python 3.14 --project services/control-plane python -m proxima_control_plane.diagnosis eval --dataset services/control-plane/tests/diagnosis/data/eval/cases.json
```

## Структура

```
services/control-plane/                         - Python-пакет proxima-control-plane (uv, Python >=3.14; deps: jsonschema)
  src/proxima_control_plane/diagnosis/          - вся построенная диагностика
    models.py                                   - DiagnosisInput/Diagnosis/BatchItem/BatchResult; parse_signal (сценарии SCN-001/005/008, trust=unreleased, source_refs непустой)
    schema/diagnosis.draft.v1.json              - draft-JSON-Schema диагноза; каноническая строится в PMM-29/contracts - НЕ переносить
    validator.py                                - validate_diagnosis(obj) -> list[str] (пусто = ок), jsonschema Draft 2020-12
    adapters/                                   - Protocol LLMClient, детерминированный MockLLMClient, factory.create_client (провайдера кроме mock нет)
    prompts/                                    - system.v1.md (анти-инъекция + запрет считать метрики) + builder.build_messages (DATA-блоки, справка DIAGNOSIS_INPUT, PROMPT_VERSION v1)
    service.py                                  - run_batch: retry невалидного ответа (max 2), timeout без retry, rollback-флаг llm_enabled, детерминизм-проверки чисел/ссылок, аудит
    audit.py / config.py / cli.py               - JSONL-аудит (глотает OSError); TOML-конфиг с дефолтами (provider=mock, timeout 90); CLI run|eval, exit 0/2
  tests/diagnosis/                              - pytest по каждому модулю + eval_runner.py (полные критерии) + data/eval/cases.json (12 кейсов: standard/closed_numbers/adversarial)
contracts/, services/collector/, db/, tools/    - другие треки; зона diagnosis-задач - только services/control-plane
```

## Подводные камни

- Python только через uv (3.14); системный 3.9 не подходит.
- MockLLMClient парсит блок DIAGNOSIS_INPUT из user-сообщения: перед `client.diagnose()` всегда звать `build_messages(signal)`, иначе ValueError.
- Детерминизм-проверка чисел: regex сканирует только текстовые поля (hypothesis/question/why_it_matters/confidence_note); числа из индексов списков входа (`payload.x[0].value` → токен «0») дают ложное срабатывание - в fixtures числовые значения JSON заменены SYNTH-строками.
- Timeout - финал без retry; retry только когда ответ невалиден по схеме или детерминизму.
- CLI возвращает 0, даже если часть сигналов failed (изоляция per-signal); exit 2 - только ошибка конфига/входа; битый envelope становится item failed, а не падением.
- `provider` отличный от mock → ValueError в factory; реального провайдера ещё нет (optional-группа `llm` в pyproject пустая, зарезервирована).
- Секретов нет: в конфиге только ИМЯ env-переменной `api_key_env` (по умолчанию PROXIMA_LLM_API_KEY), значение нигде не задаётся.
- Дефолтный audit_path `logs/diagnosis-audit.jsonl` - вне git (`logs/` в .gitignore).
- Не трогать: `contracts/` (PMM-29), `services/collector/`, `services/control-plane/src/proxima/` (verbatim-дерево PA-41), sibling-worktrees.
- Тексты диагноза и системный промпт - на русском; идентификаторы кода - английские.

## Как здесь работает Autopilot

Сборка ведётся навыком `/autopilot`. Требования, спецификация и таски — в `.autopilot/`.
Прогресс — `.autopilot/dashboard.html`. Правило: требование из `manifest.md`
может снять только пользователь.

Если работа продолжается — скажи «продолжи автопилот»: состояние поднимется
из `.autopilot/state.js`, переспрашивать ничего не нужно.

---

## Web-кабинет (services/webapp) - память яруса T2

Приватный UI Proxima: Next.js 16.3 App Router + Tailwind 4 + TS strict + vitest; данные - только демо-fixtures, экран под плашкой unreleased (DEC-006). Прогон PA-49 Warm Precision сдан (vitest 26 passed, make verify PASS, build зелёный).

### Команды

```
npm --workspace @proxima/webapp run dev      # dev; порт 3000 занят -> Next молча займёт 3001
npm --workspace @proxima/webapp test         # vitest run
npx vitest run src/tests/fx.test.ts --root services/webapp   # один файл
npm --workspace @proxima/webapp run typecheck | lint | build # по одной
make verify                                  # полный гейт из корня репо
make webapp-build | make webapp-lint         # те же цели из Makefile
ssh -N proxima-app                           # staging: http://localhost:3000, контейнер proxima-webapp-staging (loopback VPS)
```

### Структура (services/webapp)

- `src/app/layout.tsx` - шрифты Inter + IBM Plex Mono (next/font), ThemeProvider (next-themes)
- `src/app/(app)/` - защищённая зона: `layout.tsx` + страницы `dashboard | brief | inbox | admin | styleguide`
- `src/app/login/`, `src/app/api/auth/[...all]/route.ts` - better-auth обвязка (логику не трогать)
- `src/components/ui/` - примитивы: Button Card Badge GyrBadge FxBadge Skeleton EmptyState SectionError(+Boundary)
- `src/components/metrics/` - MetricStrip MetricCard Sparkline (inline SVG, `max-[379px]:hidden`)
- `src/components/brief/` - SignalRow BriefVerdict Digest CountUp
- `src/components/shell/` - app-sidebar (w-64) cabinet-switcher unreleased-banner
- `src/components/empty/` - InboxWorkflow KeyboardHint FutureBlock AdminModuleStub (6 модулей)
- `src/lib/data/` - шов данных (PA-50): `DataProvider`, выбор источника по `WEBAPP_DATA_MODE` (`fixtures` | `postgres`), доменные типы. Страницы ходят сюда, а не в fixtures напрямую
- `src/lib/fixtures/` - metrics brief shell: источник демо-данных за провайдером (getMetrics/getBrief, префикс fixture-)
- `src/lib/` - gyr.ts fx.ts format/rub.ts utils.ts (семантика и форматирование)
- `src/lib/auth.ts`, `src/lib/auth-client.ts`, `src/lib/db/` - auth + drizzle/pg, запретная зона
- `src/tests/` - fx gyr rub metrics brief-fixtures (5 файлов)
- `Dockerfile` - multi-stage standalone-сборка; секреты приходят окружением на VPS, в образ не печём

### Ключевые файлы

- `services/webapp/src/app/globals.css` - все CSS-токены обеих тем; единственное место с сырыми hex
- `services/webapp/src/lib/fixtures/metrics.ts` - `getMetrics(): readonly FixtureMetric[]`, `getMetrics.dataMode = "fixtures"`
- `services/webapp/src/lib/fixtures/brief.ts` - `getBrief(variant?: "daily"|"quiet")`
- `services/webapp/src/components/metrics/metric-strip.tsx` - метрическая полоса дашборда
- `services/webapp/src/app/(app)/brief/page.tsx` - `/brief?view=quiet` = тихий день («Критичных нет»)
- `services/webapp/src/app/(app)/styleguide/page.tsx` - живой стайлгайд примитивов
- `DESIGN.md` (корень репо) - канон дизайн-системы

### Архитектура

Поток зависимостей: `globals.css` (tokens) -> `lib/fixtures` (провайдер демо-данных) -> `components/ui` (примитивы) -> зоны `metrics | brief | shell | empty` -> страницы `(app)`.
Семантика живёт в либах, не в UI: дельта тонирована по `deltaGoodWhen` из fixtures, GYR/FX-статусы - `lib/gyr`/`lib/fx`.
Швы тестов: геттеры `lib/fixtures` (форма данных стабильна) + чистые `lib/gyr` + `lib/format/rub`; DOM проверяется smoke-сборкой и стайлгайдом, E2E нет.
Секции inbox/dashboard/admin обёрнуты SectionErrorBoundary (2/4/6 секций) - падение секции не роняет экран.

### Соглашения кода

- Сырые hex - только в `globals.css`; компоненты берут цвет исключительно через CSS-переменные.
- Любая демо-цифра на экране - с FxBadge (`lib/fx`, метка "FX"); fixtures обезличены, префикс `fixture-`, без реальных cabinet ID/SKU/цен.
- Плашка unreleased (решение DEC-006) остаётся на всех экранах, снимать нельзя.
- Язык UI русский, идентификаторы английские; без эмодзи, без комментариев в коде (кроме неочевидного).
- Запретная зона правок: `src/lib/auth*`, `src/app/api/auth/`, `src/app/login/`, `Dockerfile`, `infra/*`, `src/lib/db/*`, `Makefile`, `package.json` (новые зависимости = BLOCKED).

### Окружение (имена, не значения)

- `WEBAPP_REQUIRE_AUTH` - гейт auth на `(app)`, читается в `src/app/(app)/layout.tsx:18`
- `WEBAPP_DATA_DATABASE_URI` (fallback `DATABASE_URI`) - данные, `src/lib/db/client.ts:45,55`
- `AUTH_SECRET`, `AUTH_DATABASE_URI` - better-auth (`src/lib/auth.ts:11`, `src/lib/db/client.ts:33`)
- `NEXT_TELEMETRY_DISABLED`, `PUPPETEER_SKIP_DOWNLOAD` - выставлены в `Dockerfile`

### Подводные камни

- `eslint` запинен на `9.39.5` в `services/webapp/package.json`: eslint-config-next 16.3.3 заявляет peer `>=9`, но на eslint 10 конфиг не проверялся - не апгрейдить мимо пина.
- `**/.next/` в `.gitignore:10` держите: попади сборочный вывод в tracked-файлы, secret_scan (`make verify`) уронит гейт.
- `PUPPETEER_SKIP_DOWNLOAD=1` в Dockerfile (deps-stage): транзитивный puppeteer иначе тянет Chromium при `npm ci` - образу он не нужен.
- Тёмная тема: обе палитры (light ivory / dark stone) калиброваны в globals.css (`.dark` через next-themes); правка токена - сразу в двух темах.
- `next dev` при занятом 3000 молча уходит на 3001 - проверяйте адресную строку.

### Тесты

- `npm --workspace @proxima/webapp test` = vitest, 26 passed по 5 файлам (`src/tests/{fx,gyr,rub,metrics,brief-fixtures}.test.ts`).
- Один файл: `npx vitest run src/tests/metrics.test.ts --root services/webapp`.
- Юнит-тесты ходят только через швы (fixtures-геттеры, gyr, rub); разметку юнит-тестами не покрывать.

### Как здесь работает Autopilot

Прогон PA-49 Warm Precision (режим interview) сдан. Спека и таски - в `.autopilot/2026-08-25-pa49-warm-precision/`, прогресс - `.autopilot/dashboard.html`.
Продолжение работы: сказать «продолжи автопилот» - состояние поднимется из `.autopilot/state.js`, переспрашивать не нужно.
Правило неизменно: требование из `manifest.md` может снять только пользователь.

## Release Gate-слой - память яруса T1

Прогон 2026-08-27 release-cutter сдан. Read-only шлюз между планированием и Autopilot: критик доказательно ищет самый дешёвый безопасный путь до проверяемого релиза и имеет право сказать «задача не нужна» - с доказательствами, не вкусом модели.

### Пайплайн

Три слоя: `grill-me` (что именно делаем, какие решения не приняты) → `release-cutter` (нужно ли вообще, можно ли дешевле/переиспользовать) → `autopilot` (реализует только согласованный минимум). В пайплайне Orca major/critical `release-critic` занял место briefmaker (решение Mike): research репо + Jira → отчёт Release Gate.

### Команды

- `/release-gate <задача|PA-XX|PMM-XX|@файл>` - только аудит, НИКОГДА не запускает Autopilot; ключ Jira критик сам тянет через jira-atlassian MCP read-only.
- `/release-task <задача>` - оркестрация: gate → handoff-ветки (NEEDS_INPUT → реальный скилл grill-me, максимум один цикл Gate→Grill→Gate) → сохранение gate → Autopilot получает только раздел 12 отчёта + поля Scope lock.

### Структура

- `.opencode/skills/release-cutter/SKILL.md` - методология: workflow 8 шагов, вердикты, handoff, шаблон отчёта (13 секций)
- `.opencode/agents/release-critic.md` - субагент: deny-all + read/glob/grep/list/skill/webfetch/websearch, bash только git-readonly, Jira/Confluence только чтение
- `.opencode/commands/release-gate.md`, `.opencode/commands/release-task.md` - slash-команды
- `docs/release-gates/` - утверждённые gate-отчёты + README.md (вердикты, handoff, exemption-список); живой пример: `docs/release-gates/2026-08-27-pmm-7-dry-run.md`

### Контракты

- Gate ID `RG-<YYYYMMDD>-<slug>`; файл отчёта `docs/release-gates/<YYYY-MM-DD>-<slug>.md`; дочерние задачи ссылаются на Gate ID.
- Вердикты: KEEP / REUSE / SHRINK / DEFER / DROP / BLOCKED. Handoff-status: READY_AUTO / NEEDS_APPROVAL / NEEDS_INPUT / BLOCKED.
- Строка `DISCOVERY_STATUS: ...` - в шапке `## Gate` и последней строкой отчёта, парсится Orca-координатором: READY_AUTO→READY; DROP/DEFER→NOT_NEEDED; NEEDS_APPROVAL/NEEDS_INPUT/BLOCKED→напрямую.
- Один gate на epic покрывает дочерние задачи, пока они не выходят за Scope lock.

### Подводные камни

- `.opencode/agents/briefmaker.md` - legacy, не вызывать и не изменять (решение Mike); в major/critical диспетчеризуется release-critic.
- release-critic read-only: edit/write запрещены permissions, bash только `git status|log|show|diff|branch --show-current|rev-parse`, секреты не читает.
- Языки: SKILL.md и команды - русские; шаблон отчёта и секция «Release Gate» в AGENTS.md - английские; `docs/release-gates/README.md` - русский.
- Gate не нужен (exemption): typo, форматирование, test-only, узкий bugfix без изменения поведения/контрактов/архитектуры/данных/зависимостей/security/scope.
- `docs/agent-system/DECISIONS.md`, `docs/adr/*`, утверждённые фазовые контракты M1 критик не DROP/DEFER молча - только NEEDS_APPROVAL с явной ссылкой.

### Проверка

- Frontmatter (4 файла): `python3 -c "import yaml;[yaml.safe_load(open(f).read().split('---')[1]) for f in ['.opencode/skills/release-cutter/SKILL.md','.opencode/agents/release-critic.md','.opencode/commands/release-gate.md','.opencode/commands/release-task.md']]"`
- Маркеры AGENTS.md (паттерн якорим к началу строки, иначе grep считает сам этот блок): `grep -c '^<!-- autopilot:start -->' AGENTS.md` → 1; `grep -c '^<!-- release-gate:start -->' AGENTS.md` → 1.
<!-- autopilot:end -->
