# Project State - PROXIMA AI

## Project Reference

**Core value:** Каждый факт в PostgreSQL прослеживается до официального WB-артефакта с SHA-256; ни одна неподтверждённая запись не проходит в production release.

**Milestone:** M1 - production-ready read-only data foundation для одного пилотного кабинета Bogatova Belle Robe.

**Current focus:** Phase 2 - Vertical Slice: Immutable Intake to Visible Facts.

**Roadmap:** 8 phases, 32/32 requirements mapped, 0 orphaned, 0 duplicate ownership.

## Current Position

**Phase:** 2 of 8 - Vertical Slice: Immutable Intake to Visible Facts
**Plan:** 02-01 and early-feedback 02-01A implemented; 02-02 is checkpointed on an official WB XLSX.
**Status:** Phase 2 in progress; Phase 2.1 end-to-end acceptance and its hosted CI evidence are complete; only the observed XLSX parser remains pending (checkpointed on the official XLSX from Mike).
**Progress:** `[#---------] 13%`

## Performance Metrics

| Metric | Current |
|--------|---------|
| Phases complete | 1/8 |
| Plans complete | 3/3 Phase 1; 2/3 Phase 2 |
| Requirements complete | 6/32 |
| Root verify evidence | 02-01 GitHub PASS on `56ebe000`; 02-01A local PASS on deployed `2d0f6ec` repeated 2026-08-14; hosted CI `verify` PASS on `1a211c9` (main, run completed 2026-08-14T19:25 UTC, observed 2026-08-15 - PA-12) |
| Independent cross-model reviews | 3/3 Phase 1 plans PASS with 0 blocker / 0 warning |
| Data GO | Pending separate Mike decision |
| Live Deploy GO | Pending separate Mike decision |

## Accumulated Context

### Decisions

- 2026-08-15 (Mike, PA-32): coding agents standard регенерирован из фактов репозитория; `CLAUDE.md` - относительный симлинк на `AGENTS.md`; owner Mihail Zhamba, квартальный цикл пересмотра, следующее ревью 2026-11-15.
- 2026-08-15 (Mike, PA-28): coding agents standard зафиксирован в `AGENTS.md` - Claude Code и Codex равноправны, доступ через vendor subscriptions, PAYG API только через отдельную Jira-задачу PA с reason/owner/spend limit/review date; credentials личные и не передаются сторонним агентам.
- 2026-08-12 (Mike): ценность M1 = фундамент для LLM-аналитики M2; provenance/качество не режутся, Data Health UI минимальный, время до реальных данных сжимается.
- 2026-08-12 (Mike): roadmap перестроен data-first - Phase 2 = вертикальный slice (intake -> manifest -> staging -> minimal facts -> минимальная localhost-страница).
- 2026-08-12 (Mike): independent cross-model review 0/0 обязателен только для критических phases 3, 4, 7; остальным - `make verify` + CI + self-review в EVIDENCE.md.
- 2026-08-12 (Mike): минимальный VPS поднимается к Phase 4, 90-day backfill выполняется на нём; базовый daily scheduler (без SLA-timeline и alerts) - тоже Phase 4. Полный ops-харднинг остаётся в Phase 7.
- 2026-08-13 (Mike): созданный Selectel VPS `135.106.186.210` оставляем после SSH preflight: Ubuntu 24.04 LTS, 6 vCPU, 12,247,548 KiB RAM, root filesystem 126,752,366,592 bytes (12 GiB / 120 GiB provider class). Лимит 3,000 RUB/месяц сохраняется, фактическая цена Selectel пока не проверена. Входящий трафик только TCP/22, private UI - только SSH tunnel.
- 2026-08-13 (Mike): Phase 2.1 - staging exception для ранней обратной связи: одна маржа, один deterministic out-of-stock signal, один ручной Telegram send; scheduler, production release pointer, Data GO и Live Deploy GO не двигаются.
- 2026-08-12 (data spike): reconciliation M1 = official WB API (canonical) vs official manual XLSX (supporting); Torgstat supporting отложен до M2, его экспорты не дают daily grain. См. `.planning/research/DATA-SPIKE-2026-08-12.md`.
- Raw evidence is immutable, content-addressed, outside Git and retained for the full pilot.
- Operational, inventory and financial releases have independent atomic pointers; failure preserves last-known-good and remains visible separately.
- `order_count` is the first authority/reconciliation metric at `cabinet + SKU + calendar_day`, timezone `Europe/Moscow`.
- One VPS and one Docker Compose stack are the M1 deployment boundary.
- Each phase requires a clean implementation commit, root `make verify` and CI evidence before advance; independent cross-model review `0 blocker / 0 warning` обязателен для phases 3, 4, 7, остальным - self-review в EVIDENCE.md (обновлено 2026-08-12).
- Architecture GO is accepted by Mike's `Implement the plan` request dated 2026-08-12. Data GO and Live Deploy GO remain separate pending decision records.
- LLM runtime, Ozon, WB Advertising, WB WRITE, client-facing UI and Torgstat live sessions are deferred beyond M1.

### Source Boundaries

- `torgstat-collector`: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Торгстат-автоматизация/torgstat-collector` at `610169a6bd3253fa351fa6fbe4ff571d4f4d5539`.
- `proxima-ai-manager`: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Опрос-v2.2` at `9cca25d1118ab74a113be43e4346a024b0c7abe7`.
- Never mutate, stash, clean or commit either source worktree. Dirty candidates require explicit allowlist plus relative path, byte SHA-256, review status and destination.

### Todos

- Keep official WB XLSX bytes outside Git and use only synthetic structural fixtures in tests.
- Keep evidence locators per phase for final Phase 8 gate.

### Open decisions (не потерять до своих фаз)

| # | Решение | Дедлайн | Рекомендация |
|---|---------|---------|--------------|
| A1 | TS codegen из JSON Schema (сейчас схемы валидирует только Python) | Phase 2 | json-schema-to-typescript в verify-цепочку |
| B6 | Additive-only доктрина миграций | Phase 3 CONTEXT | Записать при планировании Phase 3 |
| C9 | ADR: точные WB endpoints + наблюдаемые RPS limits | Phase 4 planning | Первый артефакт планирования Phase 4; заполнить из API-ноги data spike |
| D11 | Rotation policy WB токенов: владелец + cadence | до Phase 4 | Expiry наблюдён: токены живут ~180 дней (тестовый истекает 2027-02-01). Mike ротирует вручную по календарному напоминанию < 180 дней; на Phase 4 выпустить 3 токена с раздельными scope |
| C10 | Правило при mismatch manifest vs raw bytes | Phase 2 CONTEXT | Байты = истина; mismatch = quarantine + alert, pointer не двигается |
| D13 | Физическое место Restic encryption key вне VPS | Phase 7 | Password manager Mike + бумажная копия |
| E14 | RTO/RPO числа; где крутится isolated restore test | Phase 7 | RPO 24h из дневного цикла; RTO задать после замера на реальном объёме |
| F16/F17 | Incident playbook + severity matrix P0-P2 + decision tree 08:45 | Phase 7 | `docs/operations/incident-playbook.md` как deliverable фазы |
| E15 | Post-pilot retention raw evidence | Phase 8 | Решить на Data GO gate |

### Blockers

- Phase 2 slice: официальная XLSX-выгрузка из кабинета WB отсутствует - передаёт Mike (см. DATA-SPIKE F4). API-нога закрыта тестовым токеном Амировой 2026-08-12; боевой токен кабинета Богатовой нужен к Phase 4. Планирование Phase 2 не блокировано.
- First approved data release remains blocked on Phase 8 Data GO evidence.
- Live deployment remains blocked on separate Live Deploy GO.

## Session Continuity

**Last action:** 2026-08-16 (PA-13): `--allow-analytics-read-write` RW-исключение удалено из коллектора, обоих Python-инструментов, installer, тестов и документации; Analytics RW теперь fail-closed везде; `make verify` PASS на `267cc3c`; DoD grep чист.

**Next action:** 1) VPS: установить READ-only Analytics токен Амировой через двухаргументный installer и прогнать безфлаговый async Analytics сбор (закрывает DoD PA-13). 2) Mike передает official pilot-cabinet XLSX для Plan 02-02.

**Resume context:** Start from `.planning/ROADMAP.md` Phase 2. Treat `.planning/phases/01-architecture-provenance-import-baseline/EVIDENCE.md` as the completed upstream gate and preserve the Phase 1 source/Linear boundaries.

---
*Updated: 2026-08-16*
