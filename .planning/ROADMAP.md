# Roadmap - PROXIMA AI M1

## Milestone Outcome

Mike получает production-ready read-only data foundation для пилотного WB-кабинета Bogatova Belle Robe: каждый опубликованный факт прослеживается до официального WB-артефакта и его SHA-256, а неподтверждённые данные не двигают production release pointer.

**Granularity:** Fine - 8 маленьких vertical phases по явному M1 rebaseline; `.planning/config.json` задаёт `depth: quick`, но не содержит отдельного `granularity` key.
**Coverage:** 32/32 M1 requirements назначены ровно одной owning phase.

## Execution Contract

Этот contract применяется к каждой phase до перехода к следующей:

1. Phase завершается отдельным clean implementation commit; planning-only изменения не считаются implementation evidence.
2. Root `make verify` проходит одним exit code и включает релевантные TypeScript, Python, PostgreSQL migration/contract, Mermaid render и secret-scan проверки.
3. CI evidence сохраняет commit SHA и locators результатов.
4. Independent cross-model deep review того же commit возвращает `0 blocker / 0 warning` для критических phases 3, 4 и 7 (atomic releases, official WB clients, operations/recovery); авторская self-review не считается independent review. Для остальных phases gate = root `make verify` + CI evidence + авторская self-review, записанная в EVIDENCE.md. (Решение Mike 2026-08-12.)
5. Source worktrees только читаются и остаются неизменными. Импорт разрешён только из зафиксированного commit или из явно allowlisted working-tree файла с byte SHA-256.
6. LLM runtime, Ozon, WB Advertising APIs, любые WB WRITE, client-facing UI и Torgstat live session automation не входят в M1.

## Source Import Boundary

- `torgstat-collector`: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Торгстат-автоматизация/torgstat-collector`, tracked baseline `610169a6bd3253fa351fa6fbe4ff571d4f4d5539`.
- `proxima-ai-manager`: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Опрос-v2.2`, tracked baseline `9cca25d1118ab74a113be43e4346a024b0c7abe7`.
- Оба source worktree запрещено мутировать, stash, clean или commit. Dirty additions из `torgstat-collector` рассматриваются только по allowlist с relative path, byte SHA-256, review status и destination; secrets, sessions, ignored runtime data и owner-owned unrelated changes исключены.

## Phases

- [x] **Phase 1: Architecture & Provenance Import Baseline** - Зафиксировать service boundaries, безопасный provenance-bound импорт и единый verification contract.
- [ ] **Phase 2: Vertical Slice - Immutable Intake to Visible Facts** - Провести официальный WB XLSX через единый idempotent intake в immutable content-addressed storage и довести вертикальным slice до минимальной localhost-страницы с `order_count` по дням.
- [ ] **Phase 3: PostgreSQL Quality & Atomic Releases** - Создать tenant-safe quarantine, lineage, runtime roles и fail-closed atomic domain releases.
- [ ] **Phase 4: Official WB READ & 90-Day Backfill** - Подключить три official READ источника и выполнить параметризуемый 90-дневный operational backfill на минимальном VPS с базовым daily scheduler.
- [ ] **Phase 5: order_count Authority & Reconciliation** - Зафиксировать семантику order_count и блокировать release при необъяснённом расхождении.
- [ ] **Phase 6: Data Health** - Дать Mike приватную read-only наблюдаемость от source attempt до artifact checksum.
- [ ] **Phase 7: VPS Operations & Recovery Readiness** - Подтвердить ежедневный scheduler, sanitized alerts, one-VPS stack, backup и изолированный restore.
- [ ] **Phase 8: Final Data Release Evidence Gate** - Собрать независимое evidence, получить отдельные Data GO и Live Deploy GO и допустить первый release.

## Phase Details

### Phase 1: Architecture & Provenance Import Baseline
**Goal**: Канонический monorepo имеет проверяемые архитектурные границы и воспроизводимый provenance import, не изменяя sibling source worktrees.
**Depends on**: Nothing
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, SRC-06, PROC-03
**Success Criteria** (what must be TRUE):
  1. Reviewer видит hybrid boundary `TypeScript collector/data-plane + Python control-plane/Data Health + PostgreSQL 16 + Docker Compose` и machine-readable cross-language contracts без Python rewrite существующего collector.
  2. Import inventory связывает каждый перенесённый файл с exact source path, baseline commit или byte SHA-256, destination и review status; pre/post evidence подтверждает, что оба source worktree не изменились.
  3. Mermaid system, data, deployment и delivery sources воспроизводимо рендерятся в SVG/PDF через root `make verify` вместе с TypeScript, Python, migrations, contracts и secret scan.
  4. Production entrypoints и dependency graph не содержат Torgstat adapter; runtime flag не может подключить live session automation.
  5. Rebaseline phase hierarchy существует отдельно, а legacy Linear history на 2026-08-12 остаётся неизменной и связана с repository phase contracts только reference links.
**Plans**: 3/3 complete

### Phase 2: Vertical Slice - Immutable Intake to Visible Facts
**Goal**: Официальный ручной WB XLSX становится неизменяемым evidence artifact до любого parsing или staging, и один вертикальный slice доводит его до видимых минимальных facts: intake -> manifest -> staging -> minimal facts -> минимальная read-only localhost-страница. (Data-first порядок, решение Mike 2026-08-12.) Slice-таблицы создаются каноническими ordered migrations (`002_...`+) аддитивно - никаких throwaway-таблиц вне migration ledger; Phase 3 наследует и расширяет их.
**Depends on**: Phase 1; data spike gate `.planning/research/DATA-SPIKE-2026-08-12.md` (official XLSX кабинета передаёт Mike; WB READ tokens нужны только Phase 4)
**Requirements**: SRC-01, SRC-03, SRC-04
**Success Criteria** (what must be TRUE):
  1. Operator передаёт официальный WB XLSX в один intake path и затем получает byte-for-byte artifact в private content-addressed storage вне Git.
  2. Manifest фиксирует SHA-256 исходных bytes до parsing и содержит tenant, source, dataset, period, `data_as_of`, `retrieved_at`, schema/parser versions, provenance и locator.
  3. Повторный intake того же artifact возвращает тот же identity и не создаёт duplicate artifacts или facts.
  4. Crash в любой точке intake можно повторить: raw evidence сохраняется, а partial или duplicate public state не возникает.
  5. (Slice-evidence, без requirement-owner.) Минимальная read-only страница на localhost показывает `order_count` по дням из staging/preview facts реального artifact с явной пометкой `unreleased`; production release pointer в slice не участвует. Полный Data Health (UI-01..03) остаётся в Phase 6, полный quality/release-механизм - в Phase 3.
**Plans**: 1/2 implemented - `02-01` verified; `02-02` waits for the official WB XLSX checkpoint.

### Phase 3: PostgreSQL Quality & Atomic Releases
**Goal**: Только полностью проверенные tenant-safe datasets публикуются атомарно, а любой сбой сохраняет last-known-good.
**Depends on**: Phase 2
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-09, DATA-10
**Success Criteria** (what must be TRUE):
  1. Ordered immutable migrations создают tenant-safe metadata, attempts, artifacts, staging/quarantine, normalized facts, quality checks, lineage и release records, наследуя и расширяя slice-миграции Phase 2; migration roundtrip проходит на real PostgreSQL.
  2. Operational, inventory и financial release pointers продвигаются независимо и только в одной transaction с promotion соответствующих facts.
  3. Failed, partial, stale, conflicting или schema-drift attempt оставляет current pointer на last-known-good и виден как отдельный текущий failure.
  4. Из любого public fact reviewer переходит к exact artifact SHA-256, manifest, parser/schema version и acquisition attempt.
  5. Отдельные runtime roles для migration owner, source publisher, release publisher и read-only Data Health проходят cross-tenant, forbidden-write и crash-injection tests.
**Plans**: TBD

### Phase 4: Official WB READ & 90-Day Backfill
**Goal**: Пилот получает complete official WB evidence через READ-only clients и воспроизводимый 90-дневный operational backfill, выполняемый на минимальном VPS с базовым ежедневным scheduler. (Решение Mike 2026-08-12: VPS и daily-сбор поднимаются здесь, а не big-bang в Phase 7.)
**Depends on**: Phase 3; Selectel Cloud VPS `135.106.186.210` в РФ создан и оставлен решением Mike 2026-08-13 после preflight (6 vCPU, 12 GiB / 120 GiB provider class; фактическая цена pending) и должен быть готов до выполнения backfill.
**Requirements**: SRC-02, SRC-05, SRC-07
**Success Criteria** (what must be TRUE):
  1. Statistics, Analytics и Finance clients используют три отдельные least-privilege SecretRef и не экспонируют token values в Git, PostgreSQL, logs или alerts.
  2. Production source surface содержит только документированные WB READ calls; WB Advertising и любые WRITE endpoints отсутствуют.
  3. Operator запускает backfill параметрами cabinet и date range на 90 calendar days от launch date, а повторный или возобновлённый run не дублирует факты.
  4. Unknown cabinet mapping, schema drift, auth failure, exhausted 429 retries или incomplete pagination завершаются typed `blocked`/`failed` attempt без движения release pointer.
  5. Для каждого backfill window видны completeness evidence и immutable gzip JSON artifacts до staging.
  6. (Preview-инфраструктура; ownership OPS-01 остаётся в Phase 7.) Минимальный VPS с Compose-стеком поднят; backfill выполняется на VPS, а не на ноутбуке.
  7. (Preview; ownership OPS-02/OPS-03 остаётся в Phase 7.) Базовый scheduler job запускает ежедневный сбор на VPS - без SLA-timeline 07:00-09:00 и без Telegram alerts; SLA-дисциплина и alerting формализуются в Phase 7.
**Plans**: TBD

### Phase 5: order_count Authority & Reconciliation
**Goal**: order_count имеет однозначную официальную семантику и выпускается только после fail-closed reconciliation.
**Depends on**: Phase 4
**Requirements**: DATA-06, DATA-07, DATA-08
**Success Criteria** (what must be TRUE):
  1. Versioned MetricAuthority в Git и PostgreSQL одинаково фиксирует canonical/supporting source, exact endpoint/export, field/date/status semantics, timezone, aggregation, owner и validity для `order_count`.
  2. Reviewer воспроизводит comparison на гранулярности `cabinet + SKU + calendar_day` с явным `Europe/Moscow`; canonical = official WB API, supporting в M1 = official manual XLSX (второй независимый официальный канал). Torgstat как supporting источник отложен до M2: data spike 2026-08-12 показал, что его экспорты агрегированы по неделям/периодам и daily grain не дают.
  3. Любое необъяснённое ненулевое расхождение получает status `conflict` и оставляет operational release pointer на last-known-good.
  4. Отсутствие structural-unwired Torgstat фиксируется как `supporting_absent`, не подменяет WB canonical value и не активирует session automation.
**Plans**: TBD

### Phase 6: Data Health
**Goal**: Mike может приватно проверить состояние данных и provenance без возможности что-либо изменить.
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03
**Success Criteria** (what must be TRUE):
  1. Mike открывает FastAPI/Jinja Data Health только через localhost/VPN/SSH path; public bind и mutation endpoints отсутствуют.
  2. Страница раздельно показывает sources, attempts, operational/inventory/financial releases, freshness, reconciliation, quarantine и current failure против last-known-good.
  3. Из опубликованного fact/release Mike переходит по lineage к manifest и exact artifact checksum.
  4. Интерфейс остаётся читаемым на 320px и при 200% text scaling и не выводит raw evidence, secrets или customer-sensitive payloads.
**Plans**: TBD
**UI hint**: yes

### Phase 7: VPS Operations & Recovery Readiness
**Goal**: Один VPS ежедневно собирает данные, сообщает о сбоях и доказуемо восстанавливает release вместе с evidence.
**Depends on**: Phase 6
**Requirements**: OPS-01, OPS-02, OPS-03, OPS-04, OPS-05
**Success Criteria** (what must be TRUE):
  1. One-VPS Docker Compose поднимает PostgreSQL, collector scheduler/worker, Data Health и backup job с private volumes, non-root users и passing healthchecks.
  2. Run ledger подтверждает schedule 7/7: primary 07:00, bounded retry 08:15, incident decision до 08:45 и target-ready 09:00 `Europe/Moscow`, с exponential backoff и hard timeout.
  3. Тестовый incident отправляет в Telegram только sanitized run ID, dataset, status и private UI locator; raw exception, token, credential и customer payload отсутствуют.
  4. Restic создаёт encrypted off-site backup PostgreSQL dumps, raw artifacts и manifests; recovery key извлекается из независимого от VPS secure location.
  5. Automated isolated restore реально восстанавливает DB release, manifest и raw bytes с совпадающим checksum; raw evidence не удаляется весь pilot.
**Plans**: TBD

### Phase 8: Final Data Release Evidence Gate
**Goal**: Первый M1 data release и live deploy происходят только после проверяемого Mike decision record на полном evidence set.
**Depends on**: Phase 7
**Requirements**: PROC-01, PROC-02
**Success Criteria** (what must be TRUE):
  1. Для каждой Phase 1-7 Mike открывает evidence locator с clean implementation commit SHA, successful root `make verify` и CI result; для phases 3, 4, 7 дополнительно independent cross-model review `0 blocker / 0 warning` на том же commit, для остальных - записанная в EVIDENCE.md self-review (gate-правило 2026-08-12).
  2. First release evidence связывает official WB artifact bytes и SHA-256 manifest с acquisition attempt, quarantine checks, reconciliation result, atomic release ID и public fact lineage.
  3. Data GO записан отдельным Mike decision record с evidence locators до продвижения первого approved release; Architecture GO с запросом `Implement the plan` от 2026-08-12 остаётся исходным принятым gate.
  4. Live Deploy GO записан отдельно после passing scheduler, alert, backup, isolated restore и private-access evidence; без него stack не считается live.
**Plans**: TBD

## Requirement Coverage

| Requirement | Owning Phase |
|-------------|--------------|
| ARCH-01 | Phase 1 |
| ARCH-02 | Phase 1 |
| ARCH-03 | Phase 1 |
| ARCH-04 | Phase 1 |
| SRC-01 | Phase 2 |
| SRC-02 | Phase 4 |
| SRC-03 | Phase 2 |
| SRC-04 | Phase 2 |
| SRC-05 | Phase 4 |
| SRC-06 | Phase 1 |
| SRC-07 | Phase 4 |
| DATA-01 | Phase 3 |
| DATA-02 | Phase 3 |
| DATA-03 | Phase 3 |
| DATA-04 | Phase 3 |
| DATA-05 | Phase 3 |
| DATA-06 | Phase 5 |
| DATA-07 | Phase 5 |
| DATA-08 | Phase 5 |
| DATA-09 | Phase 3 |
| DATA-10 | Phase 3 |
| UI-01 | Phase 6 |
| UI-02 | Phase 6 |
| UI-03 | Phase 6 |
| OPS-01 | Phase 7 |
| OPS-02 | Phase 7 |
| OPS-03 | Phase 7 |
| OPS-04 | Phase 7 |
| OPS-05 | Phase 7 |
| PROC-01 | Phase 8 |
| PROC-02 | Phase 8 |
| PROC-03 | Phase 1 |

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Architecture & Provenance Import Baseline | 3/3 | Complete | 2026-08-12 |
| 2. Vertical Slice - Immutable Intake to Visible Facts | 0/TBD | Not started | - |
| 3. PostgreSQL Quality & Atomic Releases | 0/TBD | Not started | - |
| 4. Official WB READ & 90-Day Backfill | 0/TBD | Not started | - |
| 5. order_count Authority & Reconciliation | 0/TBD | Not started | - |
| 6. Data Health | 0/TBD | Not started | - |
| 7. VPS Operations & Recovery Readiness | 0/TBD | Not started | - |
| 8. Final Data Release Evidence Gate | 0/TBD | Not started | - |

---
*Created: 2026-08-12 for PROXIMA AI M1 rebaseline*
