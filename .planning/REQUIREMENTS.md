# Requirements - PROXIMA AI M1

## Architecture and provenance

- [x] **ARCH-01** Canonical monorepo сохраняет service boundary: TypeScript collector/data-plane, Python control-plane/Data Health, PostgreSQL 16 и Docker Compose.
- [x] **ARCH-02** Импортированный код имеет inventory с source repository, commit или working-tree SHA-256, destination и review status; source worktrees не изменяются.
- [x] **ARCH-03** Mermaid system/data/deployment/delivery diagrams хранятся как source и проходят render check в CI.
- [x] **ARCH-04** Root `make verify` проверяет TypeScript, Python, migrations, contracts, architecture render и secret scan одним exit code.

## Sources and immutable evidence

- [ ] **SRC-01** Manual official WB XLSX проходит один общий intake path и сохраняется byte-for-byte в private content-addressed storage.
- [ ] **SRC-02** Official WB Statistics, Analytics и Finance READ clients используют отдельные least-privilege SecretRef и никогда не сохраняют token values в Git, БД, logs или alerts.
- [ ] **SRC-03** Каждый XLSX или gzip JSON artifact имеет SHA-256 manifest с tenant/source/dataset/period/data_as_of/retrieved_at/schema/parser/provenance/locator metadata.
- [ ] **SRC-04** Повторный intake того же artifact идемпотентен; crash/restart не создаёт duplicate artifacts или facts. (Идемпотентность API pagination/retry - зона Phase 4: SRC-05, SRC-07.)
- [ ] **SRC-05** 90-day operational backfill является параметризованным workflow, а не hardcoded one-off path.
- [x] **SRC-06** Torgstat adapter остаётся structural-unwired в production; runtime env flag не может включить live session automation.
- [ ] **SRC-07** Неизвестный cabinet mapping, schema drift, auth failure, 429 exhaustion или неполный source остаются typed blocked/failed attempt.

## PostgreSQL, quality and releases

- [ ] **DATA-01** Tenant-safe metadata, staging/quarantine, normalized facts, source artifacts, attempts, quality checks и lineage создаются immutable ordered migrations.
- [ ] **DATA-02** Operational, inventory и financial datasets публикуются независимыми atomic domain releases.
- [ ] **DATA-03** Failed, partial, stale, conflicting и schema-drift attempt не двигает current release pointer; last-known-good сохраняется.
- [ ] **DATA-04** Текущий failed attempt виден отдельно от last-known-good, без подмены failure состоянием business health.
- [ ] **DATA-05** Каждый public fact разрешается до exact artifact SHA-256, manifest, parser/schema version и acquisition attempt.
- [ ] **DATA-06** Versioned MetricAuthority фиксирует canonical/supporting source, endpoint/export, field/date/status semantics, timezone, aggregation, owner и validity.
- [ ] **DATA-07** `order_count` сверяется по cabinet + SKU + calendar day `Europe/Moscow`; canonical = official WB API, supporting в M1 = official manual XLSX. Torgstat supporting отложен до M2 (structural-unwired; отсутствие фиксируется как `supporting_absent`) - data spike 2026-08-12: Torgstat-экспорты не дают daily grain.
- [ ] **DATA-08** Любое необъяснённое ненулевое расхождение `order_count` получает `conflict` и блокирует соответствующий release.
- [ ] **DATA-09** Runtime roles разделяют migration owner, source publisher, release publisher и read-only Data Health; cross-tenant и forbidden-write tests обязательны.
- [ ] **DATA-10** Migration roundtrip и crash-injection tests доказывают atomic pointer, last-known-good и recovery.

## Data Health

- [ ] **UI-01** Read-only FastAPI/Jinja Data Health доступен только на private/localhost interface и не имеет mutation endpoints.
- [ ] **UI-02** Mike видит sources, attempts, independent releases, freshness, reconciliation, quarantine и lineage до artifact checksum.
- [ ] **UI-03** Страница работает на 320px и при 200% text scaling, не раскрывает raw evidence, secrets или customer-sensitive payloads.

## Operations

- [ ] **OPS-01** One-VPS Docker Compose запускает PostgreSQL, collector scheduler/worker, Data Health и backup job с private volumes, non-root users и healthchecks.
- [ ] **OPS-02** Сбор идёт 7/7: primary 07:00, bounded retry 08:15, incident decision до 08:45, target ready 09:00 Europe/Moscow.
- [ ] **OPS-03** Telegram alerts содержат только sanitized run ID, dataset, status и private UI locator; raw exception text запрещён.
- [ ] **OPS-04** Restic шифрует PostgreSQL dumps, raw artifacts и manifests в S3-compatible storage; encryption key recovery не зависит только от VPS.
- [ ] **OPS-05** Automated isolated restore test подтверждает DB release, manifest и raw checksum; raw evidence не удаляется в пилоте.

## Delivery gates

- [ ] **PROC-01** Каждый vertical slice имеет clean implementation commit и CI evidence; для критических phases 3, 4 и 7 дополнительно independent cross-model deep review с 0 blocker/0 warning на том же commit; для остальных phases - авторская self-review, записанная в EVIDENCE.md (решение Mike 2026-08-12).
- [ ] **PROC-02** Architecture GO считается принятой через запрос Mike `Implement the plan` от 2026-08-12; Data GO и Live Deploy GO требуют отдельного Mike decision record с evidence locators.
- [x] **PROC-03** Legacy Linear issues от 2026-08-12 не переписываются; rebaseline hierarchy создаётся отдельно и связывается с repository phase contracts.

## Deferred beyond M1

- LLM runtime и SCN-001..008 implementation; существующий код только candidate reference.
- Ozon, advertising APIs, client-facing UI и multi-user access.
- Любой WB WRITE, client send или Torgstat live session automation.

## Traceability

Каждый M1 requirement назначен ровно одной owning phase. Более ранние phases используются только как dependencies.

| Requirement | Owning Phase | Status |
|-------------|--------------|--------|
| ARCH-01 | Phase 1 | Complete |
| ARCH-02 | Phase 1 | Complete |
| ARCH-03 | Phase 1 | Complete |
| ARCH-04 | Phase 1 | Complete |
| SRC-01 | Phase 2 | Pending |
| SRC-02 | Phase 4 | Pending |
| SRC-03 | Phase 2 | Pending |
| SRC-04 | Phase 2 | Pending |
| SRC-05 | Phase 4 | Pending |
| SRC-06 | Phase 1 | Complete |
| SRC-07 | Phase 4 | Pending |
| DATA-01 | Phase 3 | Pending |
| DATA-02 | Phase 3 | Pending |
| DATA-03 | Phase 3 | Pending |
| DATA-04 | Phase 3 | Pending |
| DATA-05 | Phase 3 | Pending |
| DATA-06 | Phase 5 | Pending |
| DATA-07 | Phase 5 | Pending |
| DATA-08 | Phase 5 | Pending |
| DATA-09 | Phase 3 | Pending |
| DATA-10 | Phase 3 | Pending |
| UI-01 | Phase 6 | Pending |
| UI-02 | Phase 6 | Pending |
| UI-03 | Phase 6 | Pending |
| OPS-01 | Phase 7 | Pending |
| OPS-02 | Phase 7 | Pending |
| OPS-03 | Phase 7 | Pending |
| OPS-04 | Phase 7 | Pending |
| OPS-05 | Phase 7 | Pending |
| PROC-01 | Phase 8 | Pending |
| PROC-02 | Phase 8 | Pending |
| PROC-03 | Phase 1 | Complete |
