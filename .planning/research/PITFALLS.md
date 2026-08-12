# Pitfalls Research

**Domain:** Data provenance platform / marketplace ETL pipeline (WB)
**Researched:** 2026-08-12
**Confidence:** HIGH (domain-specific, verified against project requirements)

---

## Critical Pitfalls

### Pitfall 1: Timezone boundary error in calendar_day computation

**What goes wrong:**
`calendar_day` computed as `DATE(timestamp AT TIME ZONE 'UTC')` on a server running UTC. Orders placed between 00:00 and 02:59 MSK get attributed to the previous calendar day. The 90-day backfill silently imports ~12% of daily data into wrong buckets; order_count reconciliation shows systematic off-by-one that looks like a WB bug.

**Why it happens:**
PostgreSQL `now()` returns UTC. `CURRENT_DATE` returns server date. Developers assume server timezone matches business timezone. WB XLSX exports use MSK dates natively, but API responses return UTC ISO-8601. The mismatch only surfaces when comparing XLSX vs API data for the same day — exactly the reconciliation M1-D is designed to catch.

**How to avoid:**
- Set `timezone = 'Europe/Moscow'` in `postgresql.conf` OR always use explicit `AT TIME ZONE 'Europe/Moscow'` in every date computation.
- Store all timestamps as `TIMESTAMPTZ`, never `TIMESTAMP`.
- Add a CI assertion: `SELECT NOW() AT TIME ZONE 'Europe/Moscow'` must equal `CURRENT_DATE` (passes only if server timezone is MSK).
- In Python workers: `datetime.now(tz=ZoneInfo('Europe/Moscow'))`, never `datetime.now()` or `datetime.utcnow()`.

**Warning signs:**
- Reconciliation shows consistent ±1 day discrepancy on days that straddle midnight MSK.
- XLSX import matches API for most SKUs but diverges for high-velocity SKUs with late-night orders.

**Phase to address:** M1-D (reconciliation setup) — enforce timezone discipline before first backfill.

---

### Pitfall 2: SHA-256 computed after transformation, not on raw bytes

**What goes wrong:**
The SHA-256 is computed on the decompressed or parsed content (e.g., after `gzip.decompress()` or after XLSX→DataFrame conversion), not on the raw bytes received from the network. Provenance chain breaks: the checksum in the manifest does not match the bytes stored in the volume. Worse: two ingestions of the same logical data produce different hashes if WB regenerates the file with different compression.

**Why it happens:**
Developers pipe data through a streaming parser and hash the output, not the input. Gzip decompression in Python returns a `bytes` object that feels like "the data," so the hash goes there.

**How to avoid:**
- Hash rule: `sha256(raw_bytes_as_received)` — before decompression, before any parsing. Store raw bytes to volume first, hash, then process.
- Implementation: `hashlib.sha256(response.content).hexdigest()` immediately after `requests.get()`, before passing `response.content` anywhere.
- Add integration test: download a fixture artifact, hash it, store it, re-read from volume, hash again, assert equal.

**Warning signs:**
- `manifest.sha256 != sha256(volume_file)` for the same artifact across two ingestion runs.
- Hash computation happens inside a `with gzip.open()` context.

**Phase to address:** M1-A (provenance foundation) — must be correct before any other pipeline work.

---

### Pitfall 3: Release pointer advances outside transaction

**What goes wrong:**
The release flow: (1) insert facts into staging, (2) run reconciliation, (3) advance release pointer. If step 3 is a separate SQL statement outside the reconciliation transaction, a crash between 2 and 3 leaves reconciled facts in staging with an un-advanced pointer. On restart, facts get re-inserted (duplicates) or reconciliation reruns on already-reconciled data. Worse variant: pointer advances before facts are fully committed — downstream readers see an empty release window.

**Why it happens:**
Release pointer update feels like "metadata," so developers put it after `COMMIT`. Reconciliation passes, they call `UPDATE release_pointers SET ...` separately. The two operations are logically one atomic action but implemented as two round trips.

**How to avoid:**
- Wrap in a single transaction: fact promotion + release pointer update in one `BEGIN`/`COMMIT`.
- Release pointer table has a `UNIQUE(domain, release_id)` constraint — duplicate pointer advance fails loudly.
- Add a `released_at` timestamp to facts; query `WHERE released_at IS NOT NULL` to distinguish promoted from quarantined.

**Warning signs:**
- `release_pointers.current` points to a window with zero facts.
- Facts table has duplicate `(cabinet_id, sku_id, calendar_day)` tuples in the same domain.

**Phase to address:** M1-C (release system) — transactional atomicity is the core invariant of the release design.

---

### Pitfall 4: XLSX column parsing by position instead of header name

**What goes wrong:**
WB silently changes XLSX column order or inserts new columns in quarterly updates. A parser using `df.iloc[:, 3]` for `order_count` starts reading `return_count` without error. The pipeline ingests wrong values that pass basic type validation (still integers) and advance to release. Discovered weeks later when reconciliation numbers look implausible.

**Why it happens:**
Openpyxl and pandas default to positional access if you iterate rows. The initial file has stable columns, so positional access "works" through development. WB does not version XLSX schemas publicly.

**How to avoid:**
- Always access by header name: `df['Количество заказов']`.
- Add an intake schema validator: assert expected columns exist and are typed correctly before processing any rows. Fail loudly on unexpected schema.
- Store the raw XLSX header row in the lineage record so schema drift is detectable retroactively.
- Test with both old and new XLSX fixtures when WB releases format changes.

**Warning signs:**
- `intake_schema_validator` is absent from the codebase.
- Parser code contains `df.iloc` or `row[N]` with numeric indices.

**Phase to address:** M1-B (XLSX intake pipeline) — before first real import.

---

### Pitfall 5: Quarantine table grows silently, masking systemic failures

**What goes wrong:**
Facts that fail reconciliation go to quarantine. Over 90-day backfill, quarantine accumulates thousands of rows. No monitoring threshold fires because quarantine is expected to have some rows. Three weeks in: 40% of daily facts are quarantined due to a schema drift issue introduced in week 2. Pipeline appears healthy (releases advancing with last-known-good), but the data is 3 weeks stale.

**Why it happens:**
Quarantine is designed as a holding area with no SLA. The Data Health page shows quarantine count but no alert fires on growth rate. Developers check quarantine during onboarding and see "some rows, expected," then never check again.

**How to avoid:**
- Alert on: quarantine row count > N per domain per day (threshold: >5% of daily ingestion volume).
- Alert on: quarantine growth rate > 2x week-over-week.
- Include quarantine age distribution in Data Health page (`oldest quarantine row: N days ago`).
- Explicitly define quarantine eviction policy: rows older than pilot duration → archived, not deleted.

**Warning signs:**
- Quarantine count grows monotonically with no corresponding reconciliation resolution events.
- Data Health page shows quarantine count but not quarantine growth rate or oldest entry age.

**Phase to address:** M1-C (release system) + M1-E (Data Health page) — monitoring must ship with the quarantine feature.

---

### Pitfall 6: order_count semantic ambiguity between WB data sources

**What goes wrong:**
WB Statistics API counts orders including cancelled-before-shipment. WB Analytics API counts only fulfilled orders. XLSX export from the seller cabinet counts orders as of export date, including status-changed orders that appear on a different day in the API. The reconciliation metric `order_count` compares these without pinning the exact definition — any discrepancy triggers a block, but the discrepancy is definitional, not a data error.

**Why it happens:**
"Order count" sounds unambiguous. It isn't. WB's own documentation uses the same term for different aggregation semantics across endpoints. The authority map requirement (`per-metric authority map`) exists precisely because of this, but if written without the semantic definition, it's incomplete.

**How to avoid:**
- Authority map entry for `order_count` must specify: which API endpoint, which status filter (`status IN ('confirmed', 'shipped')`), which date field (`order_date` vs `shipment_date`), and whether returns are excluded.
- Write the definition before implementing the reconciliation query.
- Add a comment in the reconciliation SQL that cites the authority map version: `-- authority_map v1: order_count = Statistics API, status!=cancelled, field=order_date`.

**Warning signs:**
- Reconciliation consistently shows ~5-15% discrepancy that can't be explained by timing.
- `per-metric authority map` file exists but doesn't specify status filters or date field semantics.

**Phase to address:** M1-D (order_count reconciliation) — define before writing the query.

---

### Pitfall 7: WB API pagination cursor lost on retry causes duplicate ingestion

**What goes wrong:**
WB Statistics API is paginated with a cursor. On a network error mid-pagination, retry logic restarts from the first page. Items already written to staging get re-inserted. Without a deduplication constraint or idempotency key on the staging table, duplicates pass reconciliation and inflate order_count.

**Why it happens:**
Retry-from-start is simpler to implement than cursor checkpointing. The early pages succeed quickly so the bug only surfaces on large date ranges (the 90-day backfill) where mid-pagination failures are probable.

**How to avoid:**
- Staging table has a `UNIQUE(cabinet_id, sku_id, calendar_day, source_api, artifact_sha256)` constraint. INSERT ON CONFLICT DO NOTHING makes re-insertion idempotent.
- Checkpoint cursor per ingestion run in a `ingestion_checkpoints` table. Resume from last cursor on restart.
- Test by simulating a crash at page 3 of 10 and verifying row count equals a clean run.

**Warning signs:**
- Staging table has no unique constraint on business keys.
- Retry logic unconditionally calls the first page endpoint.

**Phase to address:** M1-B (API ingestion) — idempotency must be designed in, not added later.

---

### Pitfall 8: Restic encryption key stored only on VPS

**What goes wrong:**
Restic repository password is in a file on the VPS disk or in an environment variable on the VPS. VPS disk fails or is wiped. All S3 snapshots exist but are encrypted with a key that no longer exists. Raw evidence and PostgreSQL dumps are permanently unrecoverable.

**Why it happens:**
"The key is on the server, the backups are in S3, those are separate systems" — this reasoning ignores that both systems can be simultaneously lost in a VPS rebuild scenario.

**How to avoid:**
- Store Restic password in a separate secret manager (Bitwarden, 1Password, or a second secure location physically separate from the VPS).
- Document the key recovery procedure in the runbook — not in the VPS, in a separate secure document.
- Add to the restore test: simulate key retrieval from the external location, not from VPS environment.

**Warning signs:**
- `RESTIC_PASSWORD_FILE=/etc/restic/password` pointing to a file on the VPS filesystem.
- No documented external key storage location.

**Phase to address:** M1-G (infrastructure + backup) — key escrow before first backup runs.

---

### Pitfall 9: Telegram alert leaking secrets or stack traces

**What goes wrong:**
An exception handler catches a `requests.exceptions.ConnectionError` that includes the API URL with embedded token query parameter (`?token=abc123`). The exception is formatted into the Telegram alert message. Token appears in Telegram chat history.

**Why it happens:**
Python exceptions stringify their arguments. `ConnectionError('Failed connecting to https://api.wb.ru/v1/stats?token=SECRET')` includes the full URL in `str(exc)`. Alert code uses `f"Error: {exc}"` without sanitization.

**How to avoid:**
- Telegram alert formatter must strip: tokens, passwords, connection strings, internal IPs.
- Pattern: log the full exception to structured logs, send only `error_type + error_code` to Telegram. Never forward raw exception messages to Telegram.
- Add a unit test: construct a fake exception with a mock token URL, run through the formatter, assert the token does not appear in the output string.

**Warning signs:**
- Alert formatter code does `str(exc)` or `repr(exc)` without filtering.
- WB API calls use token as a query parameter (common in WB Statistics API) rather than Authorization header.

**Phase to address:** M1-F (scheduler + incidents) — sanitization must ship with the first alert.

---

### Pitfall 10: Torgstat adapter activatable through environment variables

**What goes wrong:**
Torgstat adapter "compiles but doesn't run" — but it's activated by checking `TORGSTAT_ENABLED=true` in the environment. Someone sets this in `.env` during local testing. The `.env` file is copied to VPS. Adapter activates in production without the required written authorization. WB session-based scraping starts, violating ToS.

**Why it happens:**
Feature flags via environment variables are easy. Disabling by default sounds safe. But "default off" with an env variable is trivially reversible. The required gate is a code-level block, not a config block.

**How to avoid:**
- Torgstat adapter must require a **compile-time or deployment-time code change**, not a runtime env flag, to activate.
- Alternatively: adapter code is in a separate module that is never imported by the main application until explicitly wired up.
- Add a CI check that production collector entrypoints and dependency graph contain no Torgstat adapter import until a signed gate is committed.

**Warning signs:**
- Torgstat enabled/disabled controlled by an environment variable rather than import/wire-up.
- `.env.example` contains `TORGSTAT_ENABLED=false` (implies it's a valid runtime setting).

**Phase to address:** M1-B (data sources) — Torgstat integration code must be structurally isolated, not just config-disabled.

---

### Pitfall 11: last-known-good pointer corrupted by failed migration

**What goes wrong:**
A schema migration (e.g., adding a column to the facts table) runs partially — adds column to one domain table but not another — then fails. Subsequent reconciliation uses the new query that references the missing column. Reconciliation fails with a database error. The release system tries to fall back to last-known-good but the release pointer table itself was included in the failed migration transaction. Last-known-good is now pointing to a nonexistent schema state.

**Why it happens:**
PostgreSQL DDL is not automatically transactional in all cases (though most DDL is in Postgres). Multi-table migrations are often written as sequential statements without explicit `BEGIN`/`ROLLBACK` guards. The last-known-good concept applies to data, not to schema state.

**How to avoid:**
- All schema migrations in a single `BEGIN`/`COMMIT` block. Test migration rollback explicitly.
- Separate schema migrations from data migrations. Never mix.
- `make verify` must include: apply migration to test DB, run full suite, rollback migration, run suite again.
- The release pointer table schema must be versioned separately from fact tables. Pointer format changes require a migration plan.

**Warning signs:**
- Migration files contain multiple `ALTER TABLE` statements without a wrapping transaction.
- No rollback procedure documented for each migration.

**Phase to address:** M1-C (schema + releases) — migration discipline established before first schema change.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip quarantine for "obviously clean" API data | Faster pipeline | Silent corruption when WB returns malformed data in expected shape | Never — quarantine is the invariant |
| Hardcode 90-day backfill window | Simpler initial code | Can't re-backfill after data corrections without code change | Never — make it a parameter |
| Use Python `datetime.now()` without tz | Fewer lines | Wrong calendar_day attribution for MSK boundary orders | Never — always use `ZoneInfo` |
| Store artifact path as relative path | Simpler during dev | Volume mount path changes break all lineage lookups | Never — use content-addressable key (sha256 as primary reference) |
| Single PostgreSQL user for all workers | Fewer secrets to manage | Finance worker can read inventory tables; violates least-privilege | Never for production pilot |
| Polling-based scheduler (`while True: sleep`) | Easy to implement | No visibility into missed runs; no bounded retry; no alerting | Never — use a proper scheduler with run history |
| Log level DEBUG in production | Easier debugging | Logs include full API responses (may contain PII or financial data) | Never — INFO in prod, DEBUG behind flag |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| WB Statistics API | Treat missing SKUs in response as zero orders | Missing SKU = API didn't return data for that SKU; do not insert zero; mark as `data_absent` in lineage |
| WB Finance API | Map settlement period directly to calendar days | Finance API returns settlement periods (not calendar days); expand period→day with a generated calendar table |
| WB XLSX export | Trust file's `Last Modified` date as export date | Always record import timestamp; WB XLSX timestamps are unreliable (set by Excel, not WB backend) |
| Docker secrets | Mount secret as env var `$(cat /run/secrets/wb_token)` in entrypoint | Mount as file, read in Python with `open('/run/secrets/wb_token').read().strip()` — never pass via shell interpolation (leaks to `ps aux`) |
| Restic S3 backup | Run `restic backup` without `--tag` | Tag every backup with run ID and domain: `--tag ingestion_run=abc123,domain=finance`; needed for targeted restore |
| PostgreSQL COPY | Use INSERT for bulk backfill | COPY FROM is 10-50x faster than multi-row INSERT for the 90-day backfill; use `psycopg2.copy_from()` or `COPY ... FROM STDIN` |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No index on `artifact_sha256` | Lineage lookups for Data Health page take seconds | `CREATE INDEX CONCURRENTLY idx_artifacts_sha256 ON raw_artifacts(sha256)` | At ~10K artifacts (3 months × multiple sources) |
| N+1 queries in Data Health page | Page load takes 5-10s; each metric freshness is a separate query | Single query with `GROUP BY domain, metric` | Immediately visible even with 1 cabinet |
| Full `facts` table scan for reconciliation | Reconciliation takes minutes instead of seconds | Composite index on `(cabinet_id, calendar_day, domain)` | At 90-day backfill (~90 × 500 SKU = 45K rows per domain) |
| No connection pooling (pg_bouncer or SQLAlchemy pool) | Workers spawn new connections per ingestion; PostgreSQL hits `max_connections` | Use `pool_size=5` in SQLAlchemy; or deploy pg_bouncer | When 3+ workers run concurrently |
| Restic backup running during ingestion peak | VPS CPU/IO spikes; ingestion fails with timeout | Schedule Restic at 03:00-05:00 MSK (off-peak); set `--limit-upload` | Immediately on a budget VPS with limited IOPS |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| PostgreSQL `pg_hba.conf` allows connections from `0.0.0.0/0` | PostgreSQL accessible from internet; brute-force or credential stuffing | Bind PostgreSQL to `127.0.0.1` only; access only from Docker internal network |
| Docker Compose without resource limits | A runaway ingestion worker consumes all VPS memory; OOM kills PostgreSQL | Set `mem_limit: 512m`, `cpus: '0.5'` per worker container in Compose |
| `.env` file with real credentials committed to Git | Credentials in git history; permanent secret rotation required | Add `.env` to `.gitignore` before first commit; use `.env.example` with placeholder values |
| No log rotation | Log files grow unboundedly; disk full kills PostgreSQL | Configure Docker log driver: `max-size: 50m`, `max-file: 5` per container |
| Data Health page accessible over plain HTTP | Session tokens intercepted; internal financial data exposed | Enforce HTTPS even for VPN-only access; use self-signed cert if no public domain |
| WB API token stored in process environment | `ps aux` output visible to any user on the VPS | Run workers as dedicated non-root user; use Docker secrets (files), not environment variables for tokens |

---

## "Looks Done But Isn't" Checklist

- [ ] **SHA-256 provenance:** Hash computed on raw received bytes, not decompressed/parsed output; verify the hash call precedes gzip/OOXML parsing.
- [ ] **Atomic release:** Release pointer update is in the same transaction as fact promotion — verify by checking for `BEGIN`/`COMMIT` wrapping both operations
- [ ] **Restore test:** Backup restoration has been actually tested end-to-end, not just `restic check` — verify there is a `restic restore` dry-run in CI or cron output logs
- [ ] **Quarantine monitoring:** Quarantine growth alert is wired up, not just quarantine count displayed — verify an alert fires on test data that exceeds threshold
- [ ] **Timezone:** All `calendar_day` computations use explicit `Europe/Moscow`; source scan rejects implicit local/UTC day derivation.
- [ ] **Telegram sanitization:** Alert formatter has unit test with a fake token in an exception URL — verify test exists and passes
- [ ] **Torgstat isolation:** Adapter code is not imported anywhere in the main application — `grep -r "torgstat" src/` shows no import in worker entrypoints
- [ ] **Finance/Inventory isolation:** Finance worker cannot query inventory tables — verify PostgreSQL role permissions with `\dp` on inventory tables logged in as finance_worker role
- [ ] **Backfill idempotency:** Running the 90-day backfill twice produces identical row counts — verify with a test that runs ingestion twice on the same fixture and counts rows

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| SHA-256 computed wrong | HIGH | Re-ingest all artifacts from source; lineage records must be rebuilt; partial if WB API only retains 90 days |
| Release pointer corrupted | MEDIUM | Restore pointer from `release_audit_log` (if exists) or from last Restic snapshot of PostgreSQL dump |
| Quarantine overflow | LOW | Write a backfill reconciliation job that processes quarantine in batches; no data loss, just delay |
| WB XLSX schema drift | MEDIUM | Roll back intake to last known-good schema version; re-parse affected artifacts from volume; update schema validator |
| Credentials in git history | HIGH | Rotate all affected tokens immediately; rewrite history with `git filter-repo`; requires force-push and all clones must be re-cloned |
| Restic key lost | CRITICAL | No recovery of encrypted backups; only recovery is from live PostgreSQL if VPS still accessible |
| Torgstat accidentally activated | HIGH | Immediately disable; assess WB ToS violation risk; may require rotating WB API credentials if session was associated with the same account |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Timezone drift in calendar_day | M1-D setup | CI test: `SELECT NOW() AT TIME ZONE 'Europe/Moscow'` matches expected MSK date |
| SHA-256 on wrong bytes | M1-A (provenance) | Integration test: re-read artifact from volume, hash matches manifest |
| Release pointer outside transaction | M1-C (release system) | Test: simulate crash between reconciliation and pointer update; verify no partial state |
| XLSX positional parsing | M1-B (XLSX intake) | Schema validator test: feed fixture with rotated columns, assert fail-fast |
| Quarantine silent growth | M1-C + M1-E | Alert fires in test when quarantine exceeds 5% of daily ingestion |
| order_count semantic ambiguity | M1-D (before query write) | Authority map reviewed and signed off before first reconciliation query |
| Pagination cursor lost | M1-B (API ingestion) | Idempotency test: ingest same fixture twice, row count identical |
| Restic key on VPS only | M1-G (infrastructure) | External key retrieval simulated in restore test |
| Telegram secret leak | M1-F (alerts) | Unit test: exception with fake token passes through formatter; token absent in output |
| Torgstat env-flag activation | M1-B (data sources) | CI: `grep -r 'TORGSTAT_ENABLED' src/` must return zero results in main application code |
| last-known-good corrupted by migration | M1-C (schema) | Migration rollback test in CI; apply + rollback + verify schema unchanged |

---

## Sources

- WB Statistics API behavior: domain knowledge from ETL pipeline patterns; WB does not publish pagination contract documentation publicly
- PostgreSQL transactional DDL: PostgreSQL 15 documentation (DDL is transactional in Postgres, unlike MySQL)
- Restic encryption model: official Restic documentation on repository format and key management
- Docker secrets file injection: Docker Compose v3.1+ secrets documentation
- Timezone handling in Python: PEP 615 (ZoneInfo), Python 3.9+ docs
- XLSX schema drift: observed risk handled by versioned report schemas and quarantined re-parse from immutable raw bytes.
- Data pipeline idempotency: Martin Fowler "Patterns of Enterprise Application Architecture" — idempotent receiver pattern

---

*Pitfalls research for: Proxima AI data platform — WB provenance pipeline*
*Researched: 2026-08-12*
