BEGIN;

CREATE TABLE release_attempts (
    release_id uuid PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    domain text NOT NULL CHECK (domain IN ('operational', 'inventory', 'financial')),
    status text NOT NULL CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    failure_code text,
    started_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (status <> 'SUCCEEDED' OR finished_at IS NOT NULL),
    CHECK (status <> 'FAILED' OR failure_code IS NOT NULL)
);

CREATE INDEX release_attempts_domain_idx
    ON release_attempts (tenant_id, domain, created_at DESC);

CREATE TABLE release_promoted_facts (
    release_id uuid NOT NULL REFERENCES release_attempts(release_id) ON DELETE RESTRICT,
    fact_attempt_id uuid NOT NULL REFERENCES fact_attempt_runs(attempt_id) ON DELETE RESTRICT,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    promoted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (release_id, fact_attempt_id)
);

CREATE TABLE domain_release_pointers (
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    domain text NOT NULL CHECK (domain IN ('operational', 'inventory', 'financial')),
    current_release_id uuid REFERENCES release_attempts(release_id) ON DELETE RESTRICT,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, domain),
    UNIQUE (tenant_id, domain, current_release_id)
);

CREATE VIEW public_order_counts_operational AS
SELECT f.fact_id, f.tenant_id, f.nm_id, f.calendar_day, f.order_count,
       r.release_id AS current_release_id, l.evidence_sha256, l.parser_version
FROM domain_release_pointers p
JOIN release_attempts r
  ON r.release_id = p.current_release_id AND r.status = 'SUCCEEDED' AND r.domain = p.domain
JOIN release_promoted_facts pf ON pf.release_id = r.release_id
JOIN fact_attempt_runs a ON a.attempt_id = pf.fact_attempt_id AND a.status = 'SUCCEEDED'
JOIN fact_lineage_records l ON l.attempt_id = a.attempt_id
JOIN fact_order_counts f ON f.attempt_id = a.attempt_id
WHERE p.domain = 'operational';

CREATE VIEW public_order_counts_inventory AS
SELECT f.fact_id, f.tenant_id, f.nm_id, f.calendar_day, f.order_count,
       r.release_id AS current_release_id, l.evidence_sha256, l.parser_version
FROM domain_release_pointers p
JOIN release_attempts r
  ON r.release_id = p.current_release_id AND r.status = 'SUCCEEDED' AND r.domain = p.domain
JOIN release_promoted_facts pf ON pf.release_id = r.release_id
JOIN fact_attempt_runs a ON a.attempt_id = pf.fact_attempt_id AND a.status = 'SUCCEEDED'
JOIN fact_lineage_records l ON l.attempt_id = a.attempt_id
JOIN fact_order_counts f ON f.attempt_id = a.attempt_id
WHERE p.domain = 'inventory';

CREATE VIEW public_order_counts_financial AS
SELECT f.fact_id, f.tenant_id, f.nm_id, f.calendar_day, f.order_count,
       r.release_id AS current_release_id, l.evidence_sha256, l.parser_version
FROM domain_release_pointers p
JOIN release_attempts r
  ON r.release_id = p.current_release_id AND r.status = 'SUCCEEDED' AND r.domain = p.domain
JOIN release_promoted_facts pf ON pf.release_id = r.release_id
JOIN fact_attempt_runs a ON a.attempt_id = pf.fact_attempt_id AND a.status = 'SUCCEEDED'
JOIN fact_lineage_records l ON l.attempt_id = a.attempt_id
JOIN fact_order_counts f ON f.attempt_id = a.attempt_id
WHERE p.domain = 'financial';

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (8, 'release_records', '32ea862b77df75ffe9cc3e19bd0fa4c9f6f2ab11698b90cfb4fd8d48755c33e6');

COMMIT;
