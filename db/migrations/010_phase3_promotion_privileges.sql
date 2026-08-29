BEGIN;

GRANT UPDATE (status, finished_at) ON fact_attempt_runs TO proxima_source_publisher;

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (10, 'phase3_promotion_privileges', '497909d2cd87c8a8be562d72c1fb14a22a14c31d73d1541ffbd17f0c616ce60b');

COMMIT;
