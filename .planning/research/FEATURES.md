# Feature Research

**Domain:** Data platform — WB marketplace cabinet analytics with provenance-grade data integrity
**Researched:** 2026-08-12
**Confidence:** HIGH (derived directly from PROJECT.md requirements; no ambiguity in M1 scope)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features Mike expects to work on day one. Missing any of them = the system is not a data platform, it's a script.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| WB Statistics API ingestion | No stats data = no operational view of cabinet | MEDIUM | Separate SecretRef, least-privilege; read-only only |
| WB Analytics API ingestion | SKU-level analytics is core to seller intelligence | MEDIUM | Separate SecretRef; rate limits need bounded retry |
| WB Finance API ingestion | Financial data = P&L, commission reconciliation | MEDIUM | Separate SecretRef; highest sensitivity, strictest quarantine |
| XLSX manual upload intake | Historical data predates API coverage; primary source for backfill | LOW | Needs checksum on upload; intake pipeline, not ad-hoc script |
| SHA-256 artifact provenance | Every fact must trace to a source artifact; without this the core value proposition is absent | LOW | Applied at ingest time; stored in manifest + lineage table |
| PostgreSQL normalization layer | Raw artifacts are not queryable; normalized facts are the product | HIGH | Schema versioning, migration safety, domain separation |
| Fail-closed release pipeline | Partial release corrupts production state; last-known-good is always better | HIGH | Release pointer advances only on full success |
| Scheduler (7d/wk, ready by 09:00 MSK) | Stale data is worse than no data for operational decisions | MEDIUM | Bounded retry + exponential backoff + hard timeout |
| Telegram incident alerting | Failures need to reach Mike without polling the health page | LOW | Sanitized messages — no secrets in alert text |
| Restic + S3 encrypted backup | One VPS = single point of failure; backup is not optional | MEDIUM | Automated restore dry-run at each backup cycle |

### Differentiators (Competitive Advantage)

Features that make this platform trustworthy beyond "it runs." These are the moat for M2 client use.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Quarantine staging before reconciliation | Dirty data never touches production; caught early, not late | MEDIUM | Quarantine schema separate from production domain tables |
| order_count reconciliation (WB canonical vs Torgstat) | A discrepancy-blocking release gate is rare in seller tools; validates pipeline end-to-end | HIGH | Granularity: cabinet + SKU + calendar_day (Europe/Moscow); any unexplained nonzero delta blocks release |
| Atomic domain releases (inventory / finance separated) | Different SLAs per domain; shared release = coupling; independence = resilient rollback | HIGH | Release pointers are independent; one domain failure doesn't block the other |
| Last-known-good preservation on failure | Current failure exposed separately; Mike always has a valid baseline | MEDIUM | Requires pointer indirection in schema; never overwrite LKG with partial data |
| Versioned per-metric authority map | Auditable record of which source owns which metric, and when that changed | LOW | File in repo + table in PostgreSQL; critical for M2 multi-source expansion |
| Data Health page (lineage → checksum) | Full traceability: release status, quarantine, freshness, artifact checksum in one view | HIGH | VPN/SSH-only; read-only; no mutating endpoints |
| Immutable raw artifact store (outside Git) | Evidence preservation for the pilot; Git is wrong tool for binary blobs | LOW | Private Docker volume; artifacts never deleted during pilot |
| Automated restore test (dry-run) | Backup without tested restore is not a backup; automated dry-run removes human error | LOW | Runs at each backup cycle; failure = alert |
| Vertical slice + GO gates | Mike controls quality at key transitions without blocking parallel development | LOW | Process feature, not code; enforced by review gate |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| LLM runtime / AI recommendations in M1 | Obvious end goal of "AI" product | AI output quality is only as good as data quality; shipping LLM on unverified data = hallucinated recommendations on fake baselines | Build M1 foundation first; LLM in M2+ after data contract is validated |
| Client-facing UI in M1 | Sellers want dashboards | UI before data integrity = polishing a broken pipe; client trust harder to rebuild than to earn | Data Health page for Mike only; external UI in M2+ after pilot validates data |
| Ozon adapter in M1 | Platform diversification | Adds integration surface, second tenant, and divergent data models before WB pipeline is proven | Tenant-safe schema design yes, Ozon adapter code no |
| WB Advertising API integration | Ad data completes the P&L picture | Out-of-scope complexity for M1; advertising data is noisy and requires separate reconciliation logic | Add in M2+ with dedicated reconciliation metric |
| Torgstat live session automation | Richer data without API limits | WB ToS risk from session-based automation without explicit approval; a single ToS violation can revoke cabinet access | Torgstat adapter compiles but is fail-closed; activate only after written approval |
| WB WRITE operations | Auto-reorder, price management | Any write mutation is irreversible at marketplace scale; a bug in a write loop can cause financial damage | Explicit architectural ban; fail-closed by design; write capability in M3+ if at all |
| Real-time streaming ingestion | Lower data latency | Adds operational complexity (Kafka, streaming state) disproportionate to a single-cabinet pilot; 09:00 MSK batch meets all M1 needs | Scheduled batch collection; revisit if latency SLA emerges in M2 |
| Multi-cabinet support in M1 | Scale to all Proxima clients | One pilot = one verified data contract; multi-cabinet multiplies surface area before the contract is proven | Tenant-safe schema design; second cabinet only after pilot GO-gate |

---

## Feature Dependencies

```
SHA-256 artifact provenance
    └──required by──> Quarantine staging
                          └──required by──> order_count reconciliation
                                                └──required by──> Atomic domain release
                                                                      └──required by──> Data Health page (release status)

XLSX intake + WB API ingestion
    └──feeds──> Quarantine staging

Atomic domain release
    └──required by──> Last-known-good preservation (pointer indirection)

Restic backup
    └──required by──> Automated restore test

Scheduler
    └──required by──> Telegram incident alerting (failure path)

Versioned per-metric authority map
    └──enhances──> order_count reconciliation (defines which source is canonical per metric)
```

### Dependency Notes

- **SHA-256 provenance is the root dependency** for everything downstream. It must be implemented in the intake pipeline, not retrofitted later — retrofitting breaks the lineage chain.
- **Quarantine before reconciliation** is a hard ordering constraint. Data that bypasses quarantine cannot be reconciled retroactively without reingestion.
- **order_count reconciliation** is the gate on atomic release. The reconciliation metric must be defined (authority map) before the release gate can be implemented.
- **Data Health page** depends on all upstream features being observable (attempts logged, freshness tracked, quarantine counts exposed). Build the page last, not first.
- **Automated restore test** is a dependency of backup — the backup feature is not complete without it.

---

## MVP Definition

M1 is itself the MVP — deliberately narrow to verify the data contract before scaling.

### Launch With (M1)

- [x] SHA-256 provenance at ingest (XLSX + API artifacts)
- [x] Immutable raw artifact store (private Docker volume)
- [x] WB Statistics + Analytics + Finance API ingestion (read-only, separate SecretRefs)
- [x] XLSX manual upload intake pipeline
- [x] Quarantine staging schema
- [x] order_count reconciliation (cabinet + SKU + calendar_day, Europe/Moscow)
- [x] Atomic domain releases (inventory and financial independent)
- [x] Last-known-good preservation on any failure
- [x] Versioned per-metric authority map (file + table)
- [x] Scheduler (7d/wk, target 09:00 MSK, bounded retry + hard timeout)
- [x] Telegram incident alerting (sanitized)
- [x] Data Health page (VPN/SSH-only, read-only, lineage → checksum)
- [x] Restic + S3 encrypted backup with automated restore dry-run
- [x] 90-day backfill from launch date (order_count)
- [x] make verify / just verify unified CI entry point
- [x] Mermaid architecture diagrams in repo

### Add After Pilot Validation (M2)

- [ ] Second WB cabinet onboarding — trigger: M1 data contract validated, GO-gate passed
- [ ] Ozon adapter — trigger: WB pipeline stable, second tenant schema proven
- [ ] Additional reconciliation metrics (revenue, returns, commissions) — trigger: order_count gate stable
- [ ] WB Advertising API ingestion — trigger: separate reconciliation metric defined
- [ ] External client-facing dashboard — trigger: M1 data quality validated by Mike
- [ ] LLM recommendation layer (SCN-001..SCN-008) — trigger: M1 data foundation validated; M2 client UI in place

### Future Consideration (M3+)

- [ ] WB WRITE operations (price management, auto-reorder) — requires explicit architectural review and Mike GO-gate; high risk
- [ ] Multi-tenant SaaS delivery to Proxima clients — requires client auth, billing, tenant isolation hardening
- [ ] Real-time streaming ingestion — only if 09:00 MSK batch SLA becomes insufficient

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| SHA-256 provenance at ingest | HIGH | LOW | P1 |
| WB API ingestion (Statistics, Analytics, Finance) | HIGH | MEDIUM | P1 |
| XLSX intake pipeline | HIGH | LOW | P1 |
| Quarantine staging | HIGH | MEDIUM | P1 |
| Fail-closed release pipeline | HIGH | HIGH | P1 |
| order_count reconciliation | HIGH | HIGH | P1 |
| Atomic domain releases | HIGH | HIGH | P1 |
| Scheduler + bounded retry | HIGH | MEDIUM | P1 |
| Data Health page | HIGH | HIGH | P1 |
| Restic backup + restore test | HIGH | MEDIUM | P1 |
| Telegram alerting | MEDIUM | LOW | P1 |
| Last-known-good preservation | HIGH | MEDIUM | P1 |
| Per-metric authority map | MEDIUM | LOW | P1 |
| 90-day backfill | MEDIUM | MEDIUM | P1 |
| make verify / CI entry point | MEDIUM | LOW | P1 |
| Mermaid architecture diagrams | LOW | LOW | P2 |
| Torgstat adapter (compiled, fail-closed) | LOW | MEDIUM | P2 |
| LLM recommendation layer | HIGH | HIGH | P3 |
| Client-facing UI | HIGH | HIGH | P3 |
| Ozon adapter | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for M1 launch
- P2: Should have — adds safety or future-proofs without blocking M1
- P3: Deferred to M2+; out of M1 scope

---

## Competitor Feature Analysis

This is an internal data platform, not a consumer product. The relevant comparison is against typical seller analytics tools available to WB cabinet owners.

| Feature | Typical WB seller tools (MP Stats, Moneyplace, etc.) | Proxima AI M1 | Why our approach |
|---------|------------------------------------------------------|----------------|-----------------|
| Data source | Torgstat / unofficial scraping | WB official APIs + manual XLSX | Official sources only = no ToS risk, accurate numbers |
| Provenance | None — data appears, no audit trail | SHA-256 per artifact, lineage in DB | Every fact traceable to checksum; required for reconciliation |
| Data quality gate | None — whatever comes in goes to dashboard | Quarantine + reconciliation blocks bad data | Mike sees only verified data; no silent corruption |
| Reconciliation | None | order_count: WB canonical vs Torgstat; blocks release on discrepancy | Discrepancy detection before data enters production |
| Backup | Not relevant (SaaS) | Restic + S3 + automated restore test | Self-hosted = self-responsible; restore test is table stakes |
| Access control | Username/password, often shared | VPN/SSH-only for M1; no client exposure | Minimal attack surface during pilot |
| AI recommendations | Some tools have GPT integrations on raw data | None in M1 (explicit exclusion) | Trust the data first; recommendations on verified data only |

---

## Sources

- Project requirements: `.planning/PROJECT.md` (2026-08-12) — HIGH confidence (canonical, primary source)
- WB API structure: domain knowledge from MILV/Proxima context (WB Statistics, Analytics, Finance as separate APIs with separate auth) — MEDIUM confidence (verify against WB developer portal before implementation)
- Competitor landscape: Proxima agency operational knowledge (MP Stats, Moneyplace) — MEDIUM confidence

---

*Feature research for: Proxima AI — WB data platform, Milestone 1*
*Researched: 2026-08-12*
