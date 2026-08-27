# Project State - PROXIMA AI

## Project Reference

**Core value:** Каждый факт в PostgreSQL прослеживается до официального WB-артефакта с SHA-256; ни одна неподтверждённая запись не проходит в production release.

**Milestone:** M1 - production-ready read-only data foundation для одного пилотного кабинета Bogatova Belle Robe.

**Product layer (2026-08-16, разделение трекеров уточнено 2026-08-17):** `.planning/PRODUCT-VISION.md` - консолидированное видение M1->M2 (AI Daily Manager)->M3 (SaaS 50+ кабинетов). Четыре трека исполнения, гейты V1/V2/V3. Jira **PA**: эпики PA-36 (Трек A - M1), PA-35 (Трек C - discovery), PA-34 (Трек D - SaaS, заморожен до V3), PA-37 (Трек B - исторический указатель; инфраструктура PA-38/39/41/44 живёт под ним). M1-задачи PA-18..24 привязаны к PA-36. Jira **PMM** «Proxima M2-M3» (id 10043): весь backlog M2/M3 - эпики PMM-3 (W1-срез) и PMM-6 (Governance). Разделение зафиксировано в PRODUCT-VISION.md, раздел «Трекер».

**Current focus:** V1-сигнал; PA-41 W1 + SCN-008 adapter slice завершены, при сохранении M1 read-only гейтов.

**Roadmap:** 8 phases, 32/32 requirements mapped, 0 orphaned, 0 duplicate ownership.

## Current Position

**Phase:** 2 of 8 - Vertical Slice: Immutable Intake to Visible Facts
**Plan:** 02-01, 02-01A, 02-01B implemented; 02-02 cancelled by Mike 2026-08-25 (manual XLSX path dropped from M1).
**Status:** Phase 2 закрывается с descope criterion №5 по решению Mike 2026-08-27; visible facts переносятся в Phase 3/6. PA-41 W1 и SCN-008 adapter slice импортированы/проверены; W2 ждёт PMM-29.
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

- 2026-08-27 (Mike): V1-сигнал выбран главной целью на 30 дней; Phase 2 закрывается с descope criterion №5, visible facts переносятся в Phase 3/6. PA-41 W1 + SCN-008 adapter slice завершены; Jira reconciliation pending; PMM-29 остаётся за `mihailzhamba-bot`.

- 2026-08-25 (Mike): PA-13 enforcement отменён - временный RW-opt-in для Analytics восстановлен (revert `267cc3c` = `fd95fcb`, задеплоено на VPS `fd95fcb` 2026-08-25). Причина: READ-only Analytics токен так и не создан, а оба имеющихся RW-токена от 2026-08-16 имеют криптографически битые подписи в сохранённых копиях Амировой (WB 401 `crypto/ecdsa: verification error`; канал передачи проверен чистым - вставки Statistics/Finance побайтово идентичны рабочим). Условие закрытия исключения: свежесозданный живой Analytics токен (при READ-only - вернуть enforcement `267cc3c` повторным revert).
- 2026-08-25 (Mike): Plan 02-02 (XLSX parser → staging → preview) отменён; ручная XLSX-нога исключена из M1. Чекпоинт-файл получен и профилирован (см. EVIDENCE 02-02), parser-код не начинался. SRC-01/03/04 закрыты кодом 02-01; 2026-08-27 Mike выбрал закрытие Phase 2 с descope criterion №5, а visible facts перенёс в Phase 3/6.
- 2026-08-16 (Mike): продуктовое интервью (38 ответов + 12 рекомендаций as-is) - см. PRODUCT-VISION.md. Ключевое: web-first (не Telegram), Decision Inbox в v0, все 11 сценариев волнами W1-W4, Advertising API сразу, полный P&L трек (COGS с онбординга), MPStats-бенчмарки, pricing 10-20k ₽ фикс/кабинет. Гейт V1 = 1 сквозной сигнал (AI нашёл -> AM подтвердил -> клиент получил результат).
- 2026-08-16: мировой ресёрч `.planning/research/GLOBAL-LANDSCAPE-2026-08-16.md` - 12 рынков, ~30 продуктов. Прямые конкуренты: Sirena AI (490₽+), JVO (22.9-54k). Ниша 10-20k свободна. Заимствования: R-Karte декомпозиция, Anodot seasonal baseline + ₽-impact, Triple Whale Trust Layer, Lebesgue Auditor.
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
| A1 | ~~TS codegen из JSON Schema~~ **Закрыто 2026-08-16**: `make codegen` (json-schema-to-typescript) в verify-цепочке; типы в `services/collector/src/contracts/`; boundary-гейт различает generated vs рукописный | Phase 2 | Done |
| B6 | Additive-only доктрина миграций | Phase 3 CONTEXT | Записать при планировании Phase 3 |
| C9 | ADR: точные WB endpoints + наблюдаемые RPS limits | Phase 4 planning | Первый артефакт планирования Phase 4; заполнить из API-ноги data spike |
| D11 | Rotation policy WB токенов: владелец + cadence | до Phase 4 | Expiry наблюдён: токены живут ~180 дней (тестовый истекает 2027-02-01). Mike ротирует вручную по календарному напоминанию < 180 дней; на Phase 4 выпустить 3 токена с раздельными scope |
| C10 | Правило при mismatch manifest vs raw bytes | Phase 2 CONTEXT | Байты = истина; mismatch = quarantine + alert, pointer не двигается |
| D13 | Физическое место Restic encryption key вне VPS | Phase 7 | Password manager Mike + бумажная копия |
| E14 | RTO/RPO числа; где крутится isolated restore test | Phase 7 | RPO 24h из дневного цикла; RTO задать после замера на реальном объёме |
| F16/F17 | Incident playbook + severity matrix P0-P2 + decision tree 08:45 | Phase 7 | `docs/operations/incident-playbook.md` как deliverable фазы |
| E15 | Post-pilot retention raw evidence | Phase 8 | Решить на Data GO gate |

### Blockers

- ~~Дата-трек: нет живого Analytics токена~~ **Снято 2026-08-25**: свежесозданный RW-токен (батч 25.08, `01a03905…`, exp 2027-02-24) установлен; live-прогон `wb_async_report.py --allow-analytics-read-write` = DOWNLOADED/SUCCESS (1 220 строк, неделя 17-23.08, sha256 `ed58ad60…`). Хвост (не блокер): READ-only перевыпуск от Амировой → вернуть enforcement повторным revert `fd95fcb`; Finance RW из того же батча отклонён (рабочий остался READ-only). Боевой токен кабинета Богатовой нужен к Phase 4.
- First approved data release remains blocked on Phase 8 Data GO evidence.
- Live deployment remains blocked on separate Live Deploy GO.

## Session Continuity

**Last action:** 2026-08-25 (PA-9 grill → PA-13 rollback): Plan 02-02 отменён решением Mike после разбора ценности (машина parse-run/staging уедет в Phase 4, reconciliation-нога M1 сокращена); чекпоинт-XLSX кабинета Амировой получен и профилирован без коммита байтов. По решению Mike выполнен rollback PA-13: revert `267cc3c` = commit `fd95fcb`, `make verify` PASS (51 pytest + TS-гейты), задеплоено на VPS (pre-deploy dump `pre-pa13rw-20260825.dump` sha256 `000577e0…`, detached `fd95fcb`, npm ci+build green, владение docs/agent-system и scripts/agent исправлено на proxima-admin). Пруфы задеплоенного кода: flagless прогон `wb_async_report.py` отверг RW-токен (`WB token must be read-only`); с флагом валидатор пройден, WB ответил 401. Диагностика до конца: подписание батча 2026-08-16 битое в копиях Амировой (обе Analytics-подписи `crypto/ecdsa: verification error`; Statistics/Finance вставки побайтово идентичны рабочим установленным токенам - канал чист). Установлен одобренный Mike RW-токен №4 (`0600 proxima-admin`), временные файлы с токенами удалены локально и на VPS.

**Next action (по токену):** выполнено 2026-08-25 - свежий RW-токен №2 установлен, live-сбор прошёл (DOWNLOADED, 1 220 строк, подробности в EVIDENCE 02-01B). Не горит: READ-only перевыпуск → вернуть enforcement. Отдельно ждёт решения Mike: судьба Phase 2 после отмены 02-02 (закрыть с descope criterion №5 / держать открытой).

**Resume context:** Start from `.planning/ROADMAP.md` Phase 2. Treat `.planning/phases/01-architecture-provenance-import-baseline/EVIDENCE.md` as the completed upstream gate and preserve the Phase 1 source/Linear boundaries.

---
*Updated: 2026-08-25*
