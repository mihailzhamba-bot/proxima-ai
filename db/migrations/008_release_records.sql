BEGIN;

CREATE TABLE release_attempts (
    release_id uuid PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    domain text NOT NULL CHECK (domain IN ('operational', 'inventory', 'financial')),
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    failure_code text CHECK (
        failure_code IS NULL
        OR failure_code IN ('QUALITY_FAILED', 'STALE_BATCH', 'CONFLICTING_BATCH', 'SCHEMA_DRIFT', 'PARTIAL_BATCH')
    ),
    started_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, release_id),
    UNIQUE (tenant_id, domain, release_id),
    CHECK (status <> 'SUCCEEDED' OR finished_at IS NOT NULL),
    CHECK (status <> 'FAILED' OR failure_code IS NOT NULL)
);

CREATE INDEX release_attempts_domain_idx
    ON release_attempts (tenant_id, domain, created_at DESC);

CREATE TABLE release_promoted_facts (
    release_id uuid NOT NULL,
    fact_attempt_id uuid NOT NULL,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    promoted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (release_id, fact_attempt_id),
    FOREIGN KEY (tenant_id, release_id)
        REFERENCES release_attempts (tenant_id, release_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, fact_attempt_id)
        REFERENCES fact_attempt_runs (tenant_id, attempt_id) ON DELETE RESTRICT
);

CREATE TABLE domain_release_pointers (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    domain text NOT NULL CHECK (domain IN ('operational', 'inventory', 'financial')),
    current_release_id uuid,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, domain),
    FOREIGN KEY (tenant_id, domain, current_release_id)
        REFERENCES release_attempts (tenant_id, domain, release_id) ON DELETE RESTRICT
);

CREATE VIEW public_order_counts_operational WITH (security_invoker = true) AS
SELECT f.fact_id, f.tenant_id, f.nm_id, f.calendar_day, f.order_count,
       r.release_id AS current_release_id, l.evidence_sha256, l.parser_version
FROM domain_release_pointers p
JOIN release_attempts r
  ON r.tenant_id = p.tenant_id AND r.domain = p.domain
 AND r.release_id = p.current_release_id AND r.status = 'SUCCEEDED'
JOIN release_promoted_facts pf
  ON pf.tenant_id = r.tenant_id AND pf.release_id = r.release_id
JOIN fact_attempt_runs a
  ON a.tenant_id = pf.tenant_id AND a.attempt_id = pf.fact_attempt_id AND a.status = 'SUCCEEDED'
JOIN fact_lineage_records l
  ON l.tenant_id = a.tenant_id AND l.attempt_id = a.attempt_id
JOIN fact_order_counts f
  ON f.tenant_id = a.tenant_id AND f.attempt_id = a.attempt_id
WHERE p.domain = 'operational';

CREATE VIEW public_order_counts_inventory WITH (security_invoker = true) AS
SELECT f.fact_id, f.tenant_id, f.nm_id, f.calendar_day, f.order_count,
       r.release_id AS current_release_id, l.evidence_sha256, l.parser_version
FROM domain_release_pointers p
JOIN release_attempts r
  ON r.tenant_id = p.tenant_id AND r.domain = p.domain
 AND r.release_id = p.current_release_id AND r.status = 'SUCCEEDED'
JOIN release_promoted_facts pf
  ON pf.tenant_id = r.tenant_id AND pf.release_id = r.release_id
JOIN fact_attempt_runs a
  ON a.tenant_id = pf.tenant_id AND a.attempt_id = pf.fact_attempt_id AND a.status = 'SUCCEEDED'
JOIN fact_lineage_records l
  ON l.tenant_id = a.tenant_id AND l.attempt_id = a.attempt_id
JOIN fact_order_counts f
  ON f.tenant_id = a.tenant_id AND f.attempt_id = a.attempt_id
WHERE p.domain = 'inventory';

CREATE VIEW public_order_counts_financial WITH (security_invoker = true) AS
SELECT f.fact_id, f.tenant_id, f.nm_id, f.calendar_day, f.order_count,
       r.release_id AS current_release_id, l.evidence_sha256, l.parser_version
FROM domain_release_pointers p
JOIN release_attempts r
  ON r.tenant_id = p.tenant_id AND r.domain = p.domain
 AND r.release_id = p.current_release_id AND r.status = 'SUCCEEDED'
JOIN release_promoted_facts pf
  ON pf.tenant_id = r.tenant_id AND pf.release_id = r.release_id
JOIN fact_attempt_runs a
  ON a.tenant_id = pf.tenant_id AND a.attempt_id = pf.fact_attempt_id AND a.status = 'SUCCEEDED'
JOIN fact_lineage_records l
  ON l.tenant_id = a.tenant_id AND l.attempt_id = a.attempt_id
JOIN fact_order_counts f
  ON f.tenant_id = a.tenant_id AND f.attempt_id = a.attempt_id
WHERE p.domain = 'financial';

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (8, 'release_records', '025085596556bdb63a5942a87cd7ba63469ddb6ba023f3245bc8fb006abfc94b');

COMMIT;
