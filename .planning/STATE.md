# Project State - PROXIMA AI

## Project Reference

**Core value:** Каждый факт в PostgreSQL прослеживается до официального WB-артефакта с SHA-256; ни одна неподтверждённая запись не проходит в production release.

**Milestone:** M1 - production-ready read-only data foundation для одного пилотного кабинета Bogatova Belle Robe.

**Current focus:** Phase 1 - Architecture & Provenance Import Baseline.

**Roadmap:** 8 phases, 32/32 requirements mapped, 0 orphaned, 0 duplicate ownership.

## Current Position

**Phase:** 1 of 8 - Architecture & Provenance Import Baseline
**Plan:** Not planned
**Status:** Roadmap created; ready for phase planning
**Progress:** `[----------] 0%`

## Performance Metrics

| Metric | Current |
|--------|---------|
| Phases complete | 0/8 |
| Plans complete | 0/TBD |
| Requirements complete | 0/32 |
| Root verify evidence | 0 phase commits |
| Independent cross-model reviews | 0 passing phase reviews |
| Data GO | Pending separate Mike decision |
| Live Deploy GO | Pending separate Mike decision |

## Accumulated Context

### Decisions

- Official WB is canonical; Torgstat is supporting and structural-unwired for M1.
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

- Create Phase 1 implementation plan from `.planning/ROADMAP.md`.
- At Phase 1 start, record source worktree pre-import fingerprints and exact import allowlist.
- Keep evidence locators per phase for final Phase 8 gate.

### Blockers

- None for Phase 1 planning.
- First approved data release remains blocked on Phase 8 Data GO evidence.
- Live deployment remains blocked on separate Live Deploy GO.

## Session Continuity

**Last action:** Created decision-complete M1 roadmap and initialized state on 2026-08-12.

**Next action:** Run phase planning for Phase 1 without implementing or mutating sibling source worktrees.

**Resume context:** Start from `.planning/ROADMAP.md` Phase 1. Treat `.planning/SOURCE-INVENTORY.md` as the provenance boundary and `.planning/REQUIREMENTS.md` traceability table as the single ownership map.

---
*Updated: 2026-08-12*
