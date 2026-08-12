# Project State - PROXIMA AI

## Project Reference

**Core value:** Каждый факт в PostgreSQL прослеживается до официального WB-артефакта с SHA-256; ни одна неподтверждённая запись не проходит в production release.

**Milestone:** M1 - production-ready read-only data foundation для одного пилотного кабинета Bogatova Belle Robe.

**Current focus:** Phase 2 - Vertical Slice: Immutable Intake to Visible Facts.

**Roadmap:** 8 phases, 32/32 requirements mapped, 0 orphaned, 0 duplicate ownership.

## Current Position

**Phase:** 2 of 8 - Vertical Slice: Immutable Intake to Visible Facts
**Plan:** Not planned
**Status:** Phase 1 complete; ready for Phase 2 planning
**Progress:** `[#---------] 13%`

## Performance Metrics

| Metric | Current |
|--------|---------|
| Phases complete | 1/8 |
| Plans complete | 3/3 planned Phase 1 plans |
| Requirements complete | 6/32 |
| Root verify evidence | Phase 1 aggregate PASS, GitHub run 31586198951 |
| Independent cross-model reviews | 3/3 Phase 1 plans PASS with 0 blocker / 0 warning |
| Data GO | Pending separate Mike decision |
| Live Deploy GO | Pending separate Mike decision |

## Accumulated Context

### Decisions

- Official WB is canonical; Torgstat is supporting and structural-unwired for M1.
- 2026-08-12 (Mike): ценность M1 = фундамент для LLM-аналитики M2; provenance/качество не режутся, Data Health UI минимальный, время до реальных данных сжимается.
- 2026-08-12 (Mike): roadmap перестроен data-first - Phase 2 = вертикальный slice (intake -> manifest -> staging -> minimal facts -> минимальная localhost-страница).
- 2026-08-12 (Mike): independent cross-model review 0/0 обязателен только для критических phases 3, 4, 7; остальным - `make verify` + CI + self-review в EVIDENCE.md.
- 2026-08-12 (data spike): reconciliation M1 = official WB API (canonical) vs official manual XLSX (supporting); Torgstat supporting отложен до M2, его экспорты не дают daily grain. См. `.planning/research/DATA-SPIKE-2026-08-12.md`.
- Raw evidence is immutable, content-addressed, outside Git and retained for the full pilot.
- Operational, inventory and financial releases have independent atomic pointers; failure preserves last-known-good and remains visible separately.
- `order_count` is the first authority/reconciliation metric at `cabinet + SKU + calendar_day`, timezone `Europe/Moscow`.
- One VPS and one Docker Compose stack are the M1 deployment boundary.
- Each phase requires a clean implementation commit, root `make verify`, CI evidence and independent cross-model review with `0 blocker / 0 warning` before advance.
- Architecture GO is accepted by Mike's `Implement the plan` request dated 2026-08-12. Data GO and Live Deploy GO remain separate pending decision records.
- LLM runtime, Ozon, WB Advertising, WB WRITE, client-facing UI and Torgstat live sessions are deferred beyond M1.

### Source Boundaries

- `torgstat-collector`: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Торгстат-автоматизация/torgstat-collector` at `610169a6bd3253fa351fa6fbe4ff571d4f4d5539`.
- `proxima-ai-manager`: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Опрос-v2.2` at `9cca25d1118ab74a113be43e4346a024b0c7abe7`.
- Never mutate, stash, clean or commit either source worktree. Dirty candidates require explicit allowlist plus relative path, byte SHA-256, review status and destination.

### Todos

- Create Phase 2 implementation plan from `.planning/ROADMAP.md`.
- Keep official WB XLSX bytes outside Git and use only synthetic structural fixtures in tests.
- Keep evidence locators per phase for final Phase 8 gate.

### Open decisions (не потерять до своих фаз)

| # | Решение | Дедлайн | Рекомендация |
|---|---------|---------|--------------|
| A1 | TS codegen из JSON Schema (сейчас схемы валидирует только Python) | Phase 2 | json-schema-to-typescript в verify-цепочку |
| B6 | Additive-only доктрина миграций | Phase 3 CONTEXT | Записать при планировании Phase 3 |
| C9 | ADR: точные WB endpoints + наблюдаемые RPS limits | Phase 4 planning | Первый артефакт планирования Phase 4; заполнить из API-ноги data spike |
| D11 | Rotation policy WB токенов: владелец + cadence + фактический expiry | до Phase 4 | Mike ротирует вручную по календарному напоминанию |
| C10 | Правило при mismatch manifest vs raw bytes | Phase 2 CONTEXT | Байты = истина; mismatch = quarantine + alert, pointer не двигается |
| D13 | Физическое место Restic encryption key вне VPS | Phase 7 | Password manager Mike + бумажная копия |
| E14 | RTO/RPO числа; где крутится isolated restore test | Phase 7 | RPO 24h из дневного цикла; RTO задать после замера на реальном объёме |
| F16/F17 | Incident playbook + severity matrix P0-P2 + decision tree 08:45 | Phase 7 | `docs/operations/incident-playbook.md` как deliverable фазы |
| E15 | Post-pilot retention raw evidence | Phase 8 | Решить на Data GO gate |

### Blockers

- Phase 2 slice: официальная XLSX-выгрузка из кабинета и WB READ tokens отсутствуют на машине - передаёт Mike (см. DATA-SPIKE F4). Планирование Phase 2 не блокировано.
- First approved data release remains blocked on Phase 8 Data GO evidence.
- Live deployment remains blocked on separate Live Deploy GO.

## Session Continuity

**Last action:** 2026-08-12: data spike по реальным данным store_9725 (Torgstat exports, contract PASS, grain findings) и data-first перестройка roadmap по решениям Mike; см. `.planning/research/DATA-SPIKE-2026-08-12.md`.

**Next action:** Получить от Mike официальную XLSX-выгрузку кабинета + WB READ tokens (закрыть API/XLSX ноги spike), затем Plan Phase 2 vertical slice без чтения pilot business values и без XLSX bytes в Git.

**Resume context:** Start from `.planning/ROADMAP.md` Phase 2. Treat `.planning/phases/01-architecture-provenance-import-baseline/EVIDENCE.md` as the completed upstream gate and preserve the Phase 1 source/Linear boundaries.

---
*Updated: 2026-08-12*
