BEGIN;

GRANT UPDATE (status, failure_code, finished_at) ON fact_attempt_runs TO proxima_source_publisher;

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (10, 'promotion_attempt_completion', '3c02d120ba7f22b1f3a1de1be19cc3dd15cabbdcedaf8d6c8fba3bec8749dab5');

COMMIT;
