BEGIN;

ALTER TABLE business_signal_raw_artifacts
    ADD COLUMN response_headers jsonb;

ALTER TABLE business_signal_raw_artifacts
    ADD CONSTRAINT business_signal_raw_artifacts_headers_object
    CHECK (response_headers IS NULL OR jsonb_typeof(response_headers) = 'object');

-- NULL means the row predates header capture; an empty object means headers
-- were captured and WB sent none of the allowlisted ones.

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (6, 'raw_artifact_headers', '0d56ab2b9d5a2a1e094e615833ae5793366616d6c9fab86cdbbd58d15872b8e5');

COMMIT;
