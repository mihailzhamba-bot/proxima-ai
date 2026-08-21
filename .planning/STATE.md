# Project State - PROXIMA AI

## Project Reference

**Core value:** Каждый факт в PostgreSQL прослеживается до официального WB-артефакта с SHA-256; ни одна неподтверждённая запись не проходит в production release.

**Milestone:** M1 - production-ready read-only data foundation для одного пилотного кабинета Bogatova Belle Robe.

**Product layer (2026-08-16, разделение трекеров уточнено 2026-08-17):** `.planning/PRODUCT-VISION.md` - консолидированное видение M1->M2 (AI Daily Manager)->M3 (SaaS 50+ кабинетов). Четыре трека исполнения, гейты V1/V2/V3. Jira **PA**: эпики PA-36 (Трек A - M1), PA-35 (Трек C - discovery), PA-34 (Трек D - SaaS, заморожен до V3), PA-37 (Трек B - исторический указатель; инфраструктура PA-38/39/41/44 живёт под ним). M1-задачи PA-18..24 привязаны к PA-36. Jira **PMM** «Proxima M2-M3» (id 10043): весь backlog M2/M3 - эпики PMM-3 (W1-срез) и PMM-6 (Governance). Разделение зафиксировано в PRODUCT-VISION.md, раздел «Трекер».

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

- Phase 2 slice: официальная XLSX-выгрузка из кабинета WB отсутствует - передаёт Mike (см. DATA-SPIKE F4). API-нога закрыта тестовым токеном Амировой 2026-08-12; боевой токен кабинета Богатовой нужен к Phase 4. Планирование Phase 2 не блокировано.
- First approved data release remains blocked on Phase 8 Data GO evidence.
- Live deployment remains blocked on separate Live Deploy GO.

## Session Continuity

**Last action:** 2026-08-17: аудит M2-бэклога. Найдено, что M2 существовал в двух местах: эпик PA-37 имел девять детей, пять из них дублировали срез PMM один-в-один (PA-43 = PMM-21, PA-47 = PMM-5 + PMM-25, PA-46 = PMM-26 + PMM-28, PA-38 п.1 = PMM-20 + PMM-23). Причина: прогон 2026-08-17 строил existing-карту по PA-37…PA-42, а PA-43…PA-48 были созданы 2026-08-16 в 21:04. Решение Mike: **PMM - единственный дом M2/M3**; PA-43/45/46/47/48 закрыты (метка `superseded-by-pmm`, откат обратим), PA-38/39/41/44 остались в PA. Принято **DEC-006**: LLM runtime и client-facing web UI разрешены вне M1-контура при трёх условиях (staging-данные, маркировка `unreleased`, release pointer не двигается) - без него весь W1-срез нарушал DEC-005. Заведены PMM-29…33 под четыре блокера критического пути (контракты сигнала, LLM-доступ, daily-цикл, evals). Метка правок `aios-fix-2026-08-17`. Отчёт: `docs/exec-plans/active/pmm-audit-2026-08-17.md`.

**Last action:** 2026-08-17: прогон `aios-run-2026-08-17` - создан Jira-проект **PMM** «Proxima M2-M3» (id 10043, company-managed) с 28 issue среза M2 при `engineers_fte = 1`; manifest и living plan в `docs/exec-plans/active/pm2-backlog-run.*`. Три верификационных утверждения прогона позже опровергнуты аудитом (см. `verification_correction` в манифесте).

**Last action:** 2026-08-16: продуктовая сессия - PRODUCT-VISION.md утверждён (50 решений), глобальный ресёрч-досье создано, Jira PA: эпики PA-34/35/36/37, задачи PA-38 (web-кабинет v0), PA-43 (Client Passport + PDF + Auditor), PA-44 (источники M2), PA-45 (волна W3), PA-46 (verification-петля), PA-47 (LLM Analyst + reviewer), PA-48 (волна W2); M1-задачи PA-18..24 привязаны к PA-36. *(Соответствие ключей исправлено 2026-08-17: в исходной записи PA-43/44/46/47/48 были перепутаны местами.)*
**Last action:** 2026-08-15: hosted CI `verify` PASS confirmed on `1a211c9` (run completed 2026-08-14T19:25 UTC) - 02-01A evidence gap closed (PA-12); coding agents standard regenerated and `CLAUDE.md` converted to a relative symlink (PA-32, PR #1, merge `11a7a12`).

**Next action:** Sprint 0 среза M2 в порядке: PMM-30 (DEC-006 уже на `main` через PR #9 `a2a7b12` от `mihailzhamba-bot` - прочитать формулировки и закрыть) → PMM-29 (контракты сигнала) → PMM-31 (LLM-доступ, egress с VPS проверить первым делом). Исполнение PMM-задач - за ботом (решение Mike 2026-08-17), этот агент ведёт бэклог. Параллельно Трек B: аудит scenario engine в Опрос-v2.2 (PA-39) - он теперь blocks PA-41, а PA-41 blocks PMM-5/20/23, то есть весь W1-срез. От Mike: XLSX пилота (Phase 2), боевой токен, интервью-слоты, онбординг AI-ops аналитика, COGS у Богатовой, юрлица и налоговые режимы (вход спайка PMM-2), четыре компонента в UI проекта PMM.
**Last action:** 2026-08-21 (PA-13): код задеплоен на VPS - detached checkout `6168968` (main с `ed2bbb9`) через git bundle, `npm ci`+build green, pre-deploy dump `pre-pa13-20260821-082129.dump` (sha256 `d35f2e9c…`); задеплоенный код доказал fail-closed офлайн: установленный RW-токен отвергнут (`WB token must be read-only`), флаг - unrecognized argument, dist чист. SSH-доступ восстановлен: ключ `id_ed25519_proxima_selectel_20260813` (passphrase в Keychain) под пользователем `proxima-admin` + passwordless sudo; подключение только без VPN (зафиксировано в runbook, PR #8 `ed2bbb9`).

**Next action (PA-13):** единственная зависимость - READ-only Analytics токен от Амировой (проверено 2026-08-21: на VPS и Mac его физически нет, обе копии - старый RW mask `0x4`). Когда токен получен: `install -m 0600 -o proxima-admin -g proxima-admin <файл> /etc/proxima-ai/secrets/wb_analytics_token` (или bundle через двухаргументный installer) → безфлаговый прогон `wb_async_report.py --tenant-id amirova-test` → PA-13 в «Готово». 2) Mike передает official pilot-cabinet XLSX для Plan 02-02.

**Resume context:** Start from `.planning/ROADMAP.md` Phase 2. Treat `.planning/phases/01-architecture-provenance-import-baseline/EVIDENCE.md` as the completed upstream gate and preserve the Phase 1 source/Linear boundaries.

---
*Updated: 2026-08-21*
