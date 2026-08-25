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
2. Dispatch: `briefmaker` для major/critical → worktree + supervised worker
3. Ретрансляция вопросов: worker/briefmaker `ask` → decision gate для Mike (оркестратор не генерирует вопросы, только маршрутизирует)
4. Надзор: `check --wait` на `worker_done` / `escalation` (никакого sleep-polling; молчание воркера ≠ смерть воркера)
5. Verify-маршрутизация: `make verify`, `reviewer`, cross-model review для critical
6. Гейты: merge / deploy / irreversible - только явный approve Mike
7. Состояние: `docs/agent-system/HANDOFF.md` / `TASKS.md` / provenance обновляются на каждом переходе

### Quality pipeline (major/critical)

```
INTAKE → ORCHESTRATOR: классификация
  → BRIEFMAKER (.opencode/agents/briefmaker.md): research репо + grill-волны
    (вопросы к Mike только через оркестраторский gate)
  → [GATE: brief утверждён Mike]
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

## Dirty-tree note

As of 2026-08-16 the working tree carries pre-existing uncommitted changes (Makefile, README.md, package.json, package-lock.json, `.planning/STATE.md`, `tools/verify_runtime_boundary.py`, untracked `.mcp.json`, `opencode.json`, `.codex/`, planning docs). They belong to other threads. Do not revert, stage blindly (`git add -A` is forbidden) or commit them together with your work. Stage only files you actually changed.

## Definition of Done

Done = implemented + `scripts/agent/verify` passes (structural + typecheck + TS tests + pytest) + `make verify` green where the task touches code + no known regressions + review performed (independent cross-model review 0 blocker / 0 warning for critical phases 3, 4, 7) + routing-table docs updated if needed + `docs/agent-system/TASKS.md` / `HANDOFF.md` / ExecPlan updated.
