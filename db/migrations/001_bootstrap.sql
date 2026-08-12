BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL UNIQUE,
    sha256 char(64) NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (sha256 ~ '^[0-9a-f]{64}$')
);

COMMIT;
