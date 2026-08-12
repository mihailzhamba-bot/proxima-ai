BEGIN;

CREATE TABLE schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL UNIQUE,
    sha256 char(64) NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (sha256 ~ '^[0-9a-f]{64}$')
);

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (1, 'bootstrap', 'e09d3cd86eb5bde4ed0dc87509987e7a6e7259dfef89a862988c54ad0e673af1');

COMMIT;
