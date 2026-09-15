BEGIN;

-- BetterAuth 1.7.1: configured email/password accounts use local:credential.
-- Preserve migration019 and existing table/account identity. OAuth is not enabled.
ALTER TABLE webapp_auth."account" ADD COLUMN issuer text NOT NULL DEFAULT 'local:credential';
CREATE UNIQUE INDEX auth_account_issuer_account_idx ON webapp_auth."account" (issuer, account_id);

-- checksum-policy: normalized-self-v1
INSERT INTO schema_migrations (version, name, sha256)
VALUES (20, 'auth_issuer', '1fed2fdbf24df1ebb9ccc9d80013b253383700507511d37b96f658ef42ef1f5e');
COMMIT;
