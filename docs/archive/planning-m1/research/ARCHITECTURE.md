# Architecture Research

**Domain:** Data pipeline platform — immutable raw ingestion → quarantine staging → reconciliation → atomic domain release
**Researched:** 2026-08-12
**Confidence:** HIGH — patterns derive directly from project constraints (single VPS, Docker Compose, PostgreSQL 15+, fail-closed, SHA-256 provenance)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  EXTERNAL SOURCES                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ WB Stats API │  │ WB Fin API   │  │ WB Analytics API       │ │
│  │ SecretRef-1  │  │ SecretRef-2  │  │ SecretRef-3             │ │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬───────────┘ │
│         │                 │                        │             │
│  ┌──────┴─────────────────┴────────────────────────┴──────────┐  │
│  │              XLSX Intake (manual upload path)              │  │
│  └─────────────────────────────────────────────────────────── ┘  │
└──────────────────────────────────────────────────────────────────┘
                        ↓ raw bytes + SHA-256
┌──────────────────────────────────────────────────────────────────┐
│  RAW ARTIFACT STORE (private Docker volume, immutable)           │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  /artifacts/{source}/{date}/{artifact_id}.{ext}             │ │
│  │  artifact_manifest table: id, sha256, source, fetched_at    │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                        ↓ parse + stage
┌──────────────────────────────────────────────────────────────────┐
│  POSTGRESQL 15 — quarantine schema (tenant-safe staging)         │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ quarantine.orders│  │ quarantine.fin   │  ... per domain      │
│  │ artifact_id FK   │  │ artifact_id FK   │                     │
│  └────────┬─────────┘  └────────┬─────────┘                     │
│           │                     │                               │
│  ┌────────▼─────────────────────▼────────────────────────────┐  │
│  │          RECONCILIATION ENGINE                             │  │
│  │  WB official (canonical) vs Torgstat (supporting)         │  │
│  │  Unexplained delta != 0  →  BLOCK release                 │  │
│  └────────────────────────────┬───────────────────────────── ┘  │
│                               │ pass                            │
│  ┌────────────────────────────▼───────────────────────────────┐  │
│  │  RELEASE MANAGER (atomic, per-domain)                      │  │
│  │  inventory_releases.current_ptr ──► public.inventory_*     │  │
│  │  finance_releases.current_ptr   ──► public.finance_*       │  │
│  │  last_known_good preserved on any failure                  │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                        ↓ read-only queries
┌──────────────────────────────────────────────────────────────────┐
│  DATA HEALTH PAGE (VPN/SSH tunnel only, no public binding)       │
│  Read: sources · attempts · releases · freshness                 │
│  Read: reconciliation status · quarantine · lineage → sha256     │
└──────────────────────────────────────────────────────────────────┘
                        ↑ incidents
┌──────────────────────────────────────────────────────────────────┐
│  SCHEDULER + ALERT GATEWAY                                       │
│  TypeScript scheduler → PostgreSQL run ledger → collector        │
│  Telegram bot (sanitized — no secrets in message text)           │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| `services/collector/src/sources/wb-statistics` | Fetch official WB Statistics READ with SecretRef-1; write raw to artifact store | TypeScript + native fetch |
| `adapters/wb_analytics` | Same pattern with SecretRef-2 | |
| `adapters/wb_finance` | Same pattern with SecretRef-3 | |
| `services/collector/src/sources/manual-wb` | Accept manual XLSX; hash + store; stage to quarantine | Existing bounded TypeScript OOXML reader |
| `services/collector/src/sources/torgstat` | Imported read adapter with no production entrypoint until signed gate | Structurally unwired module, not an env flag |
| `pipeline/ingest` | Parse artifact → quarantine rows; record artifact_id FK on every row | |
| `pipeline/reconcile` | Load quarantine; compare WB vs Torgstat for order_count per cabinet+SKU+day; classify delta | |
| `pipeline/release` | Advance domain release pointer atomically; write release_attempts; keep last_known_good | |
| `services/collector/migrations` | Ordered immutable SQL migrations owned by the data-plane | |
| `artifacts/manifest` | SHA-256 computation + artifact_manifest CRUD | |
| `services/collector/scripts/scheduler.ts` | One scheduler owner with bounded retry, hard timeout and PostgreSQL lease | |
| `alerts` | Telegram bot wrapper; strips secrets before send | |
| `app` | FastAPI read-only routes; served on localhost only; VPN/SSH to reach | |

---

## Recommended Project Structure

```
proxima-ai/
├── services/
│   ├── collector/          # TypeScript sources, raw commit, ETL, scheduler, SQL migrations
│   └── control-plane/      # Python FastAPI Data Health and future decision workflows
├── contracts/              # JSON Schema, authority map and release interfaces
├── architecture/           # Mermaid sources and rendered deliverables
├── infra/                  # Docker Compose, backup and restore checks
├── tests/                  # cross-service and deployment acceptance
│   └── release/            # atomic domain release logic
├── db/
│   ├── migrations/         # Alembic versions (one per slice)
│   ├── schemas/            # DDL source of truth (Mermaid ER)
│   └── fixtures/           # anonymized test fixtures (real structure, fake values)
├── artifacts/
│   ├── manifest.py         # SHA-256, store, verify
│   └── tests/
├── scheduler/
│   ├── jobs.py             # job definitions + retry config
│   └── backoff.py          # bounded exponential backoff
├── alerts/
│   └── telegram.py         # sanitized send_alert()
├── app/
│   ├── main.py             # FastAPI, read-only routes
│   ├── routes/             # sources, releases, lineage, reconciliation
│   └── templates/          # Jinja2 health page
├── contracts/
│   ├── er-diagram.mmd      # Mermaid ER source
│   ├── authority-map.yaml  # per-metric canonical source versioned
│   └── openapi.yaml        # Data Health page API contract
├── tests/
│   ├── integration/        # vertical slice tests hitting real PG
│   └── unit/               # pure logic tests
├── docker/
│   ├── worker.Dockerfile
│   └── app.Dockerfile
├── docker-compose.yml      # single VPS stack
├── Makefile                # make verify, make test, make migrate
├── pyproject.toml / go.mod
└── .planning/
```

### Structure Rationale

- **`adapters/`** owns all external I/O — one subfolder per source. Changing a WB API endpoint touches exactly one subfolder, zero shared code.
- **`pipeline/`** is pure domain logic — no I/O, easy to unit-test. Depends on adapters via interface, not directly.
- **`db/migrations/`** uses one migration file per vertical slice. Each slice lands its own schema change atomically before any code using that change merges.
- **`artifacts/manifest.py`** is the single SHA-256 authority — nothing writes to the artifact store without going through it.
- **`contracts/`** holds machine-readable contracts committed in Git. Mermaid renders to SVG/PDF in CI. `authority-map.yaml` is the file-side of the versioned authority map (mirrors the DB table).
- **`tests/integration/`** hits a real PostgreSQL — no mocking the DB (mocks mask schema drift, which is exactly what this system must catch).

---

## Architectural Patterns

### Pattern 1: Quarantine-then-Promote

**What:** Every incoming fact lands in `quarantine.*` first. Nothing reaches `public.*` without passing reconciliation and release manager approval.

**When to use:** Always — this is non-negotiable given the data fidelity requirement.

**Trade-offs:** Adds one schema boundary and one reconciliation pass. Cost is worth it: corrupt data that reached production is the failure mode this entire system exists to prevent.

```sql
-- quarantine schema receives raw parsed rows
INSERT INTO quarantine.orders (artifact_id, cabinet_id, sku, calendar_day, order_count)
VALUES ($1, $2, $3, $4::date AT TIME ZONE 'Europe/Moscow', $5);

-- promotion only happens via release manager after reconciliation_records.status = 'passed'
INSERT INTO public.inventory_orders SELECT * FROM quarantine.orders
WHERE reconciliation_id = $1;
```

### Pattern 2: Release Pointer with Last-Known-Good

**What:** Each domain has a `release_pointer` table with `current_id` and `last_known_good_id`. Advance `current_id` atomically in a transaction. On any failure, `current_id` stays at `last_known_good_id` and the failure is written to `release_attempts` with full diagnostic.

**When to use:** Every domain release attempt — inventory and finance are independent rows, so a finance failure never blocks inventory.

**Trade-offs:** Requires pointer indirection for all reads (join or view). Benefit: consumers always read a consistent, validated snapshot; never a partial state.

```sql
-- release_pointers table
CREATE TABLE release_pointers (
    domain          TEXT PRIMARY KEY,          -- 'inventory' | 'finance'
    current_id      BIGINT REFERENCES releases(id),
    last_known_good BIGINT REFERENCES releases(id),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- advance atomically; on exception, caller records failure, pointer unchanged
BEGIN;
  UPDATE release_pointers SET current_id = $new_release_id, last_known_good = current_id
  WHERE domain = $domain AND current_id IS NOT NULL;
  -- validate new release passes schema checks
  COMMIT;
```

### Pattern 3: SHA-256 Artifact Manifest as Provenance Chain

**What:** Every raw file (XLSX, gzip JSON) is hashed before storage. The hash is persisted in `artifact_manifest` and FK-referenced from every quarantine row derived from that artifact. A quarantine row without an `artifact_id` FK cannot exist (DB constraint).

**When to use:** Every ingest — no exceptions. The manifest is what makes "every fact traceable to an official WB artifact with checksum" true.

**Trade-offs:** Adds a hash computation step per artifact (negligible for files this size). Benefit: any row in PostgreSQL can be traced back to the exact byte sequence of the source file.

```python
def store_artifact(raw_bytes: bytes, source: str, fetched_at: datetime) -> str:
    digest = hashlib.sha256(raw_bytes).hexdigest()
    path = artifact_volume / source / fetched_at.date().isoformat() / f"{digest}.bin"
    path.write_bytes(raw_bytes)          # immutable: never overwrite
    db.execute(
        "INSERT INTO artifact_manifest (sha256, source, fetched_at, path) VALUES ($1,$2,$3,$4)",
        digest, source, fetched_at, str(path)
    )
    return digest
```

### Pattern 4: Fail-Closed Torgstat Adapter

**What:** The Torgstat adapter is compiled and present in the codebase but raises `TorgstatDisabledError` on any call path that would execute an actual session. A config flag (`TORGSTAT_ENABLED=false` default) enforces this. The scheduler's job definition checks this flag before invoking.

**When to use:** Always in M1. The adapter code exists for code review and future activation, not for execution.

**Trade-offs:** Slightly more complexity than just not writing the adapter. Benefit: when written permission arrives, the activation path is a config change with no new code — reducing the risk of rushed implementation at activation time.

### Pattern 5: Domain-Separated Reconciliation

**What:** `reconciliation_records` stores one row per (domain, source_pair, metric, calendar_day). The reconciler computes delta = wb_canonical - torgstat_supporting per cabinet+SKU+day. If any row has `abs(delta) > 0` AND `delta_explanation IS NULL`, the reconciliation fails for that domain.

**When to use:** Every pipeline run before release. Torgstat absent = supporting side is NULL = delta is NULL = not an unexplained discrepancy (NULL is not non-zero).

```sql
CREATE TABLE reconciliation_records (
    id              BIGSERIAL PRIMARY KEY,
    domain          TEXT NOT NULL,
    metric          TEXT NOT NULL,              -- 'order_count'
    cabinet_id      TEXT NOT NULL,
    sku             TEXT NOT NULL,
    calendar_day    DATE NOT NULL,              -- Europe/Moscow calendar day
    wb_value        NUMERIC,
    torgstat_value  NUMERIC,
    delta           NUMERIC GENERATED ALWAYS AS (wb_value - torgstat_value) STORED,
    delta_explanation TEXT,                     -- NULL = unexplained
    status          TEXT NOT NULL,              -- 'passed' | 'blocked' | 'pending'
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## Data Flow

### Ingest Flow (per scheduled run)

```
Scheduler trigger (daily, target 09:00 MSK)
    ↓
Adapter fetches from WB API (SecretRef from Docker secret)
    ↓
Raw bytes → SHA-256 hash computed
    ↓
Artifact written to private Docker volume (immutable path: sha256-keyed)
    ↓
artifact_manifest INSERT (sha256, source, fetched_at, path)
    ↓
Parser reads artifact, produces rows with artifact_id FK
    ↓
Quarantine INSERT (all-or-nothing transaction)
    │
    ├─ Success → mark ingest_attempt status='staged'
    └─ Any failure → rollback quarantine, mark ingest_attempt status='failed'
                     keep artifact (raw evidence never deleted)
                     → Alert Gateway → Telegram
```

### Reconciliation + Release Flow

```
Reconciler reads quarantine.* for this ingest_attempt
    ↓
For each (cabinet_id, sku, calendar_day):
    wb_value ← quarantine.wb_*
    torgstat_value ← quarantine.torgstat_* (NULL if adapter disabled)
    ↓
    delta = wb_value - torgstat_value
    unexplained = delta IS NOT NULL AND delta != 0 AND delta_explanation IS NULL
    ↓
    INSERT reconciliation_records
    ↓
Any unexplained delta? → status='blocked', STOP (release pointer unchanged)
    ↓
All clear → status='passed'
    ↓
Release Manager: BEGIN TRANSACTION
    INSERT INTO releases (domain, ingest_attempt_id, reconciliation_id)
    UPDATE release_pointers SET current_id = new_release.id,
                                last_known_good = current_id
    COMMIT
    ↓
    ├─ Success → mark release_attempts status='released'
    └─ Any failure → ROLLBACK, release_pointer unchanged, mark status='failed'
                     → Alert Gateway → Telegram
```

### Health Page Read Path

```
Mike (VPN/SSH tunnel) → localhost:8080/health
    ↓
FastAPI route handler (read-only)
    ↓
SELECT against: artifact_manifest, ingest_attempts, release_pointers,
                releases, reconciliation_records, release_attempts
    ↓
Jinja2 render → HTML table
```

No writes. No auth tokens exposed to browser. Page served on 127.0.0.1 inside VPS.

---

## PostgreSQL Schema Layout

```
artifact_manifest          -- every raw artifact + sha256
ingest_attempts            -- per-run metadata (source, started_at, status)
quarantine.orders          -- staged order facts (FK → artifact_manifest)
quarantine.finance         -- staged finance facts
reconciliation_records     -- per metric delta + explanation + status
releases                   -- completed release snapshots per domain
release_pointers           -- current_id + last_known_good per domain
release_attempts           -- every attempt incl failures
public.inventory_orders    -- promoted inventory (read by Health page)
public.finance_summary     -- promoted finance (read by Health page)
authority_map              -- versioned per-metric canonical source table
```

**Schema versioning rule:** each migration file is named `{NNN}_{slice_name}.sql`. Migration merges only after the slice's vertical test suite passes. This means schema in DB always matches code at that migration version.

---

## Docker Compose Stack

```yaml
services:
  postgres:
    image: postgres:15-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    secrets: [pg_password]

  artifacts:               # private volume — no container, just volume declaration
    # workers mount this volume read-write; postgres mounts nothing

  worker:
    build: docker/worker.Dockerfile
    volumes:
      - artifacts:/artifacts:rw
    secrets: [wb_stats_key, wb_analytics_key, wb_finance_key, pg_password]
    depends_on: [postgres]

  app:
    build: docker/app.Dockerfile
    ports:
      - "127.0.0.1:8080:8080"    # localhost only — VPN/SSH to reach
    depends_on: [postgres]

  backup:
    image: restic/restic
    environment:
      RESTIC_REPOSITORY: ${S3_RESTIC_REPO}
    secrets: [restic_password, s3_credentials]
    volumes:
      - pgdata:/backup/pgdata:ro
      - artifacts:/backup/artifacts:ro

volumes:
  pgdata:
  artifacts:
    driver_opts:
      type: tmpfs              # or named volume on real VPS

secrets:
  wb_stats_key:
    file: ./secrets/wb_stats_key
  wb_analytics_key:
    file: ./secrets/wb_analytics_key
  wb_finance_key:
    file: ./secrets/wb_finance_key
  pg_password:
    file: ./secrets/pg_password
  restic_password:
    file: ./secrets/restic_password
  s3_credentials:
    file: ./secrets/s3_credentials
```

All secrets files live outside the repository. `.gitignore` includes `secrets/`.

---

## Scaling Considerations

This system is intentionally single-VPS for M1. The architecture is designed so that scaling to multi-tenant or multi-source does not require rewrites.

| Scale | Adjustment |
|-------|------------|
| 1 cabinet (M1) | Docker Compose, single worker process, shared PG schemas |
| 5-10 cabinets (M2) | Add `cabinet_id` discriminator to all fact tables (already present); add per-cabinet scheduler jobs; still Docker Compose |
| Multi-tenant (M3+) | Promote `cabinet_id` to schema-per-tenant isolation; consider separate PG instances per tenant; worker pool per tenant group |

**First bottleneck:** disk I/O on the artifact volume if ingesting many large XLSX files. Mitigation: gzip artifacts on write, store sha256 of original bytes before compression.

**Second bottleneck:** reconciliation query time if backfill covers long date ranges. Mitigation: partition `quarantine.*` and `reconciliation_records` by `calendar_day`.

---

## Anti-Patterns

### Anti-Pattern 1: Writing Directly to Production Schema

**What people do:** Skip quarantine, write parsed rows straight to `public.*` because it's simpler.

**Why it's wrong:** Any parse bug, API anomaly, or partial fetch lands in production with no rollback path. The data contract — "every fact traceable to a validated artifact" — cannot be enforced retroactively.

**Do this instead:** All parsed facts go to `quarantine.*` first. Promotion to `public.*` happens only through the release manager after reconciliation passes.

### Anti-Pattern 2: Shared Release Pointer Across Domains

**What people do:** One `current_release_id` for the entire database state.

**Why it's wrong:** A finance API failure blocks inventory release. Domains have different SLAs and failure modes. Coupling them creates unnecessary downtime.

**Do this instead:** One row in `release_pointers` per domain. `inventory` and `finance` advance independently.

### Anti-Pattern 3: Mutable Artifact Store

**What people do:** Overwrite or delete raw artifacts to save space.

**Why it's wrong:** SHA-256 provenance only works if the artifact at the recorded path matches the recorded hash. Deletion breaks the audit chain. Mutation is silently worse — hash check passes but content changed.

**Do this instead:** Artifacts are write-once. Path is SHA-256-keyed (content-addressable), so duplicate fetches are naturally deduplicated. Retention policy: no deletions during the pilot.

### Anti-Pattern 4: Secrets in Environment Variables at Compose Level

**What people do:** `environment: WB_API_KEY=abc123` in docker-compose.yml.

**Why it's wrong:** Secrets appear in `docker inspect`, process environment, and any crash dump. If docker-compose.yml is committed, they're in git history.

**Do this instead:** Docker secrets (`secrets:` block). Secret files live outside the repository (not in `./` of any git-tracked directory). Worker reads secret via `/run/secrets/wb_stats_key`.

### Anti-Pattern 5: Treating NULL Torgstat Delta as a Failure

**What people do:** Reconciliation treats any NULL on the Torgstat side as a reconciliation failure, blocking release even when Torgstat is disabled.

**Why it's wrong:** Torgstat is explicitly fail-closed by default. A NULL supporting value means "no data to compare," not "discrepancy detected." Blocking release when the supporting source is absent defeats the purpose of having it be optional.

**Do this instead:** Reconciliation rule is: `delta IS NOT NULL AND delta != 0 AND delta_explanation IS NULL` → block. NULL delta (one side absent) → pass with a `supporting_absent` annotation in the reconciliation record.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| WB Statistics API | REST, SecretRef from Docker secret, least-privilege token | Read-only endpoints only |
| WB Analytics API | Same pattern, separate SecretRef | Separate token scope |
| WB Finance API | Same pattern, separate SecretRef | Separate token scope |
| Telegram Bot API | HTTPS POST, sanitized payload builder | Secret = bot token in Docker secret; never in message body |
| S3-compatible storage | Restic CLI with env vars from Docker secret | Encrypted at rest; restore test on each backup cycle |

### Internal Boundaries

| Boundary | Communication | Contract |
|----------|---------------|----------|
| Adapter → Artifact Store | Function call: `manifest.store_artifact(bytes, source)` | Returns sha256, writes to volume |
| Adapter → Quarantine | DB INSERT with artifact_id FK | FK constraint enforces provenance |
| Reconciler → Release Manager | Function call: `release_manager.attempt(domain, reconciliation_id)` | Returns ReleaseResult (success/failure + reason) |
| Worker → App | Shared PostgreSQL | App is read-only; no direct RPC between services |
| Scheduler → Worker | Function call or subprocess | Job definition owns retry + timeout logic |
| Any component → Alerts | `alerts.send_alert(message: str)` | Sanitizer strips secrets before send |

---

## Authority Map

The per-metric authority map is versioned in two places simultaneously:

1. `contracts/authority-map.yaml` — file in Git, human-readable
2. `authority_map` PostgreSQL table — machine-queryable, with `effective_from` date

```yaml
# contracts/authority-map.yaml
version: 1
metrics:
  order_count:
    canonical: wb_official
    supporting: torgstat
    granularity: [cabinet_id, sku, calendar_day]
    timezone: Europe/Moscow
    effective_from: "2026-08-12"
```

Any change to authority mapping requires updating both file and table, and triggers a reconciliation re-run if it affects historical data. This is enforced by the `make verify` gate.

---

## `make verify` Gate

Single entry point for CI and local validation:

```makefile
verify:
    make lint          # ruff/mypy or golangci-lint
    make test          # pytest -x or go test ./...
    make contracts     # mermaid render + openapi validate
    make migration     # alembic check (no pending migrations)
    make authority     # contracts/authority-map.yaml == DB authority_map table
```

A vertical slice does not merge until `make verify` passes with zero errors and zero warnings.

---

## Sources

- PostgreSQL 15 documentation: partitioning, schemas, foreign keys — authoritative
- Docker Compose secrets documentation: `secrets:` block behavior — authoritative
- Restic documentation: backup + restore cycle — authoritative
- Existing TypeScript scheduler and run-ledger contracts from verified sibling collector — HIGH confidence after source audit
- WB API rate limiting: not publicly documented — LOW confidence; adapter must implement conservative backoff and treat 429 as hard stop

---
*Architecture research for: Proxima AI data platform (M1)*
*Researched: 2026-08-12*
