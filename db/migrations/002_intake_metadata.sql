BEGIN;

CREATE TABLE tenants (
    tenant_id text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (tenant_id ~ '^[a-z0-9][a-z0-9_-]{2,63}$')
);

CREATE TABLE source_artifacts (
    artifact_id text PRIMARY KEY,
    content_sha256 char(64) NOT NULL UNIQUE,
    content_size bigint NOT NULL CHECK (content_size > 0),
    object_locator text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (artifact_id ~ '^artifact:sha256:[0-9a-f]{64}$'),
    CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK (object_locator ~ '^artifact://sha256/[0-9a-f]{64}$')
);

CREATE TABLE artifact_manifests (
    artifact_id text PRIMARY KEY REFERENCES source_artifacts(artifact_id) ON DELETE RESTRICT,
    manifest_sha256 char(64) NOT NULL UNIQUE,
    manifest_locator text NOT NULL UNIQUE,
    schema_version smallint NOT NULL CHECK (schema_version = 1),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE intake_attempts (
    attempt_id text PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    artifact_id text NOT NULL REFERENCES artifact_manifests(artifact_id) ON DELETE RESTRICT,
    source text NOT NULL CHECK (source = 'official_wb_manual'),
    dataset text NOT NULL CHECK (dataset ~ '^[a-z][a-z0-9_]{2,63}$'),
    period_from date NOT NULL,
    period_to date NOT NULL,
    data_as_of timestamptz NOT NULL,
    retrieved_at timestamptz NOT NULL,
    source_schema_version text NOT NULL CHECK (char_length(source_schema_version) BETWEEN 1 AND 64),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (attempt_id ~ '^attempt:sha256:[0-9a-f]{64}$'),
    CHECK (period_from <= period_to),
    UNIQUE (tenant_id, source, dataset, artifact_id)
);

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (2, 'intake_metadata', '446080a4af8fbab30f8906272a700f99c7cf5b5c3d76cc9adb1cca2183a80ad0');

COMMIT;
